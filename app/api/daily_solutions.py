"""
Daily Solutions API Endpoints
Serves pre-generated daily content from the edge function
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime, date as date_type
from pydantic import BaseModel

# Local imports
from ..core.security import require_authentication
from ..core.database import get_database, SupabaseConnection
from ..core.config import get_settings

# Initialize router and logger
router = APIRouter(prefix="/api/daily-solutions", tags=["Daily Solutions"])
logger = logging.getLogger(__name__)

class UserProgressUpdate(BaseModel):
    """Request model for user progress updates"""
    content_id: str
    content_type: str  # 'current_affair', 'editorial', 'practice_question'
    completed: bool
    session_date: Optional[str] = None

class DailySolutionsResponse(BaseModel):
    """Response model for daily solutions"""
    success: bool
    date: str
    content: Dict[str, Any]
    user_progress: Dict[str, Any]
    stats: Dict[str, int]
    message: str

@router.get("/{date}", response_model=Dict[str, Any])
async def get_daily_solutions(
    date: str,
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database)
):
    """
    🎯 Get daily solutions for a specific date
    
    Returns pre-generated content from the daily_solutions table:
    - Current Affairs (4-5 items)
    - Editorial Analysis (3 items)  
    - Practice Questions (8-10 items combining PYQ + practice)
    """
    try:
        logger.info(f"Fetching daily solutions for date: {date}, user: {user.get('id')}")
        
        # Validate date format
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD format."
            )
        
        # Fetch daily solutions from database
        daily_solution = await db.client.table("daily_solutions").select("*").eq("date", date).single().execute()
        
        if daily_solution.data is None:
            # No solutions exist for this date - trigger generation
            logger.info(f"No solutions exist for {date}, triggering generation")
            await trigger_daily_generation(date, db)
            
            # Return pending response
            return {
                "success": False,
                "message": f"Daily solutions for {date} are being generated. Please try again in a few moments.",
                "date": date,
                "status": "generating",
                "retry_after": 30
            }
        
        solution = daily_solution.data
        
        # Check if generation is still in progress
        if solution.get("status") == "generating":
            return {
                "success": False,
                "message": f"Daily solutions for {date} are still being generated. Please try again in a few moments.",
                "date": date,
                "status": "generating",
                "retry_after": 15
            }
        
        # Check if generation failed
        if solution.get("status") == "failed":
            return {
                "success": False,
                "message": f"Daily solutions generation failed for {date}. Please contact support.",
                "date": date,
                "status": "failed",
                "error": solution.get("error_message", "Unknown error")
            }
        
        # Get user progress for this date
        user_progress = await get_user_progress(user["id"], date, db)
        
        # Format response
        response_data = {
            "success": True,
            "message": f"Daily solutions retrieved successfully for {date}",
            "date": date,
            "status": solution.get("status", "ready"),
            "generated_at": solution.get("generated_at"),
            "content": {
                "current_affairs": solution.get("current_affairs", []),
                "editorial_analysis": solution.get("editorial_analysis", []),
                "practice_questions": solution.get("practice_questions", [])
            },
            "user_progress": user_progress,
            "stats": {
                "current_affairs_count": len(solution.get("current_affairs", [])),
                "editorial_analysis_count": len(solution.get("editorial_analysis", [])),
                "practice_questions_count": len(solution.get("practice_questions", [])),
                "total_items": len(solution.get("current_affairs", [])) + 
                              len(solution.get("editorial_analysis", [])) + 
                              len(solution.get("practice_questions", []))
            },
            "generation_stats": solution.get("generation_stats", {}),
            "performance": {
                "ai_enhanced": solution.get("generation_stats", {}).get("ai_api_used", False),
                "response_time": "< 200ms (pre-generated)"
            }
        }
        
        logger.info(f"Successfully returned daily solutions for {date}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving daily solutions for date {date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve daily solutions: {str(e)}"
        )

@router.post("/progress", response_model=Dict[str, Any])
async def update_user_progress(
    progress_update: UserProgressUpdate,
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database)
):
    """
    📊 Update user progress for daily solutions content
    
    Tracks completion of:
    - Current affairs articles
    - Editorial analysis pieces
    - Practice questions
    """
    try:
        user_id = user["id"]
        session_date = progress_update.session_date or date_type.today().isoformat()
        
        logger.info(f"Updating progress for user {user_id}: {progress_update.content_type} - {progress_update.content_id}")
        
        # Upsert progress record
        progress_data = {
            "user_id": user_id,
            "content_id": progress_update.content_id,
            "content_type": progress_update.content_type,
            "is_completed": progress_update.completed,
            "session_date": session_date,
            "completed_at": datetime.utcnow().isoformat() if progress_update.completed else None,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Check if record exists
        existing = await db.client.table("content_progress").select("id").eq("user_id", user_id).eq("content_id", progress_update.content_id).eq("session_date", session_date).execute()
        
        if existing.data:
            # Update existing record
            result = await db.client.table("content_progress").update(progress_data).eq("id", existing.data[0]["id"]).execute()
        else:
            # Insert new record
            result = await db.client.table("content_progress").insert(progress_data).execute()
        
        if result.data:
            # Update daily progress summary
            await update_daily_progress_summary(user_id, session_date, db)
            
            return {
                "success": True,
                "message": f"Progress updated for {progress_update.content_type}",
                "user_id": user_id,
                "content_id": progress_update.content_id,
                "completed": progress_update.completed,
                "session_date": session_date
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update progress"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update progress: {str(e)}"
        )

@router.get("/progress/{date}", response_model=Dict[str, Any])
async def get_daily_progress(
    date: str,
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database)
):
    """
    📈 Get user's daily progress summary
    """
    try:
        user_id = user["id"]
        
        # Get progress summary
        progress = await get_user_progress(user_id, date, db)
        
        return {
            "success": True,
            "date": date,
            "user_id": user_id,
            "progress": progress
        }
        
    except Exception as e:
        logger.error(f"Error getting daily progress for {date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily progress: {str(e)}"
        )

@router.post("/generate", response_model=Dict[str, Any])
async def trigger_generation(
    background_tasks: BackgroundTasks,
    date: Optional[str] = None,
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database)
):
    """
    🚀 Manually trigger daily solutions generation
    
    Admin endpoint to generate content for a specific date
    """
    try:
        target_date = date or date_type.today().isoformat()
        
        logger.info(f"Manual generation triggered for date: {target_date}")
        
        # Add background task to trigger edge function
        background_tasks.add_task(trigger_daily_generation, target_date, db)
        
        return {
            "success": True,
            "message": f"Daily solutions generation started for {target_date}",
            "date": target_date,
            "status": "triggered"
        }
        
    except Exception as e:
        logger.error(f"Error triggering generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger generation: {str(e)}"
        )

# Helper functions

async def get_user_progress(user_id: str, date: str, db: SupabaseConnection) -> Dict[str, Any]:
    """Get user's progress for a specific date"""
    try:
        # Get progress summary
        summary_result = await db.client.table("daily_progress_summary").select("*").eq("user_id", user_id).eq("session_date", date).execute()
        
        if summary_result.data:
            summary = summary_result.data[0]
            return {
                "current_affairs": {
                    "completed": summary.get("current_affairs_completed", 0),
                    "total": summary.get("current_affairs_total", 0),
                    "percentage": calculate_percentage(summary.get("current_affairs_completed", 0), summary.get("current_affairs_total", 0))
                },
                "editorial": {
                    "completed": summary.get("editorial_completed", 0),
                    "total": summary.get("editorial_total", 0),
                    "percentage": calculate_percentage(summary.get("editorial_completed", 0), summary.get("editorial_total", 0))
                },
                "practice": {
                    "completed": summary.get("practice_completed", 0),
                    "total": summary.get("practice_total", 0),
                    "percentage": calculate_percentage(summary.get("practice_completed", 0), summary.get("practice_total", 0))
                },
                "overall": {
                    "percentage": summary.get("overall_completion_percentage", 0)
                }
            }
        else:
            # Initialize progress summary if it doesn't exist
            await initialize_daily_progress_summary(user_id, date, db)
            return {
                "current_affairs": {"completed": 0, "total": 5, "percentage": 0},
                "editorial": {"completed": 0, "total": 3, "percentage": 0},
                "practice": {"completed": 0, "total": 8, "percentage": 0},
                "overall": {"percentage": 0}
            }
            
    except Exception as e:
        logger.error(f"Error getting user progress: {e}")
        return {}

async def initialize_daily_progress_summary(user_id: str, date: str, db: SupabaseConnection):
    """Initialize daily progress summary for a user"""
    try:
        await db.client.table("daily_progress_summary").upsert({
            "user_id": user_id,
            "session_date": date,
            "current_affairs_total": 5,
            "current_affairs_completed": 0,
            "editorial_total": 3,
            "editorial_completed": 0,
            "practice_total": 8,
            "practice_completed": 0,
            "overall_completion_percentage": 0
        }).execute()
        
    except Exception as e:
        logger.error(f"Error initializing progress summary: {e}")

async def update_daily_progress_summary(user_id: str, date: str, db: SupabaseConnection):
    """Update daily progress summary based on individual progress records"""
    try:
        # Get all progress for the date
        progress_result = await db.client.table("content_progress").select("*").eq("user_id", user_id).eq("session_date", date).execute()
        
        if progress_result.data:
            progress_records = progress_result.data
            
            # Count completions by type
            current_affairs_completed = len([p for p in progress_records if p.get("content_type") == "current_affair" and p.get("is_completed")])
            editorial_completed = len([p for p in progress_records if p.get("content_type") == "editorial" and p.get("is_completed")])
            practice_completed = len([p for p in progress_records if p.get("content_type") == "practice_question" and p.get("is_completed")])
            
            # Calculate overall percentage
            total_items = 5 + 3 + 8  # current affairs + editorial + practice
            completed_items = current_affairs_completed + editorial_completed + practice_completed
            overall_percentage = int((completed_items / total_items) * 100) if total_items > 0 else 0
            
            # Update summary
            await db.client.table("daily_progress_summary").upsert({
                "user_id": user_id,
                "session_date": date,
                "current_affairs_completed": current_affairs_completed,
                "editorial_completed": editorial_completed,
                "practice_completed": practice_completed,
                "overall_completion_percentage": overall_percentage,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            
    except Exception as e:
        logger.error(f"Error updating daily progress summary: {e}")

async def trigger_daily_generation(date: str, db: SupabaseConnection):
    """Trigger the edge function to generate daily solutions"""
    try:
        import httpx
        settings = get_settings()
        
        # Call edge function
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.supabase_url}/functions/v1/daily-solutions-generator",
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json"
                },
                json={"date": date},
                timeout=60.0
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully triggered generation for {date}")
            else:
                logger.error(f"Failed to trigger generation: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error triggering edge function: {e}")

def calculate_percentage(completed: int, total: int) -> int:
    """Calculate percentage completion"""
    return int((completed / total) * 100) if total > 0 else 0