"""
Automation API Endpoints
Master Plan Implementation - Phase 4.1

Implements automation endpoints as specified in FASTAPI_IMPLEMENTATION_MASTER_PLAN.md:
- POST /api/automation/daily - Runs complete 5-step pipeline
- GET /api/automation/status

Compatible with: FastAPI 0.116.1, Python 3.13.5
Created: 2025-08-30
Updated: 2026-01-31 - Switched to direct complete_pipeline call for proper structured output
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any, Optional
import logging
from datetime import datetime

# Local imports
from ..core.security import require_authentication, require_admin_access
from ..core.database import get_database, SupabaseConnection
from ..core.config import get_settings

# Import complete_pipeline function directly
from .simplified_flow import (
    step1_extract_rss,
    step2_analyze_relevance,
    step3_extract_content,
    step4_refine_content,
    step5_save_to_database,
    AnalysisRequest,
    RefinementRequest,
    SaveRequest,
)

# Initialize router and logger
router = APIRouter(prefix="/api/automation", tags=["Automation"])
logger = logging.getLogger(__name__)


@router.post("/daily", response_model=Dict[str, Any])
async def execute_daily_automation(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_admin_access),
    db: SupabaseConnection = Depends(get_database),
):
    """
    🎯 MASTER PLAN ENDPOINT: Execute daily automation

    Runs the complete 5-step pipeline directly:
    1. RSS extraction
    2. UPSC relevance analysis (with structured LLM output)
    3. Content extraction
    4. AI refinement
    5. Database save

    Returns immediately and runs pipeline in background to prevent 502 timeout.
    """
    try:
        logger.info("🚀 Starting daily automation - direct complete-pipeline execution")

        # Start pipeline in background (non-blocking)
        background_tasks.add_task(_run_complete_pipeline_background, user, db)

        # Return immediately (no timeout wait)
        return {
            "success": True,
            "message": "Daily automation started in background. Check logs for progress.",
            "pipeline": "complete-pipeline (5 steps)",
            "status": "processing",
            "steps": [
                "1. RSS extraction",
                "2. UPSC relevance analysis (structured LLM)",
                "3. Content extraction",
                "4. AI refinement",
                "5. Database save",
            ],
            "monitoring": {
                "check_logs": "Render logs will show progress",
                "check_database": "Check current_affairs table for new articles",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error starting daily automation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Daily automation failed to start: {str(e)}",
        )


async def _run_complete_pipeline_background(user: dict, db: SupabaseConnection):
    """
    Background task that runs the complete 5-step pipeline.

    This directly calls the pipeline functions for proper structured LLM output:
    - key_vocabulary (technical terms with definitions)
    - category (politics, economy, science, etc.)
    - gs_paper (GS1, GS2, GS3, GS4)
    - upsc_relevance (varied scores based on content)
    """
    try:
        logger.info("📊 Background pipeline started - 5-step complete-pipeline")
        start_time = datetime.utcnow()

        # Step 1: Extract RSS
        logger.info("📰 Step 1: Extracting RSS feeds...")
        step1_response = await step1_extract_rss(user)
        articles = step1_response["data"]["articles"]
        logger.info(f"   ✅ Extracted {len(articles)} articles from RSS feeds")

        if not articles:
            logger.warning("❌ No articles extracted from RSS feeds")
            return

        # Step 2: Analyze relevance (this is where structured LLM output happens)
        logger.info("🔍 Step 2: Analyzing UPSC relevance with structured LLM...")
        analysis_request = AnalysisRequest(articles=articles)
        step2_response = await step2_analyze_relevance(analysis_request, user)
        relevant_articles = step2_response["data"]["relevant_articles"]
        logger.info(f"   ✅ Found {len(relevant_articles)} UPSC-relevant articles")

        if not relevant_articles:
            logger.warning("❌ No articles passed UPSC relevance filter")
            return

        # Step 3: Extract content (from top 20 relevant articles)
        logger.info("📄 Step 3: Extracting full content...")
        top_articles = relevant_articles[:20]  # Limit for performance
        extraction_request_data = {
            "selected_articles": [
                {"title": a["title"], "url": a.get("source_url", a.get("url", ""))}
                for a in top_articles
            ]
        }
        step3_response = await step3_extract_content(extraction_request_data, user)
        extracted_articles = step3_response["data"]["extracted_articles"]
        logger.info(f"   ✅ Extracted content from {len(extracted_articles)} articles")

        if not extracted_articles:
            logger.warning("❌ No articles had extractable content")
            return

        # Step 4: Refine content
        logger.info("✨ Step 4: Refining content with AI...")
        refinement_request = RefinementRequest(articles=extracted_articles)
        step4_response = await step4_refine_content(refinement_request, user)
        refined_articles = step4_response["data"]["refined_articles"]
        logger.info(f"   ✅ Refined {len(refined_articles)} articles")

        if not refined_articles:
            logger.warning("❌ No articles were successfully refined")
            return

        # Step 5: Save to database
        logger.info("💾 Step 5: Saving to database...")
        save_request = SaveRequest(processed_articles=refined_articles)
        step5_response = await step5_save_to_database(save_request, user, db)
        saved_count = step5_response["data"]["saved_articles"]
        duplicates = step5_response["data"]["duplicates_skipped"]
        logger.info(f"   ✅ Saved {saved_count} articles, skipped {duplicates} duplicates")

        processing_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"🎉 Complete pipeline finished: {saved_count} articles saved in {processing_time:.2f}s"
        )
        logger.info(
            f"   📊 Pipeline stats: {len(articles)} RSS → {len(relevant_articles)} relevant → "
            f"{len(extracted_articles)} extracted → {len(refined_articles)} refined → {saved_count} saved"
        )

    except Exception as e:
        logger.error(f"❌ Background pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


@router.get("/status", response_model=Dict[str, Any])
async def get_automation_status(
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database),
):
    """
    📊 Get automation system status
    """
    try:
        # Get recent article count
        today = datetime.utcnow().date().isoformat()

        return {
            "success": True,
            "message": "Automation system status retrieved",
            "system_status": {
                "pipeline": "complete-pipeline (5 steps)",
                "llm_output": "structured (key_vocabulary, category, gs_paper)",
                "automation_ready": True,
            },
            "pipeline_steps": [
                "1. RSS extraction (6 premium sources)",
                "2. UPSC relevance analysis (structured LLM)",
                "3. Content extraction (full article)",
                "4. AI refinement (summaries, key points)",
                "5. Database save (deduplication)",
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation status: {str(e)}",
        )
