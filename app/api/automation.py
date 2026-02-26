"""
Automation API Endpoints
Master Plan Implementation - Phase 4.1

Implements automation endpoints as specified in FASTAPI_IMPLEMENTATION_MASTER_PLAN.md:
- POST /api/automation/daily - Runs complete unified pipeline (Hindu Playwright + RSS + AI enrichment)
- GET /api/automation/status

Compatible with: FastAPI 0.116.1, Python 3.13.5
Created: 2025-08-30
Updated: 2026-02-26 - Wired to UnifiedPipeline (replaces simplified_flow RSS-only pipeline)
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any
import logging
from datetime import datetime

# Local imports
from ..core.security import require_authentication, require_admin_access
from ..core.database import get_database, SupabaseConnection

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
    Run the complete unified pipeline:
    1. Fetch all sources (Hindu Playwright multi-section + RSS + PIB + ORF + MEA + IDSA)
    2. Date filter (36h)
    3. Content extraction
    4. Pass 1 batch scoring (relevance, GS paper, keywords)
    5. Threshold filter (55) + MUST_KNOW bypass
    6. ArticleSelector (semantic dedup + GS balance)
    6.5. LLM content enhancement
    7. Pass 2 knowledge card generation
    8. Save to database

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
            "pipeline": "unified-pipeline (Hindu Playwright + RSS + full AI enrichment)",
            "status": "processing",
            "steps": [
                "1. Fetch all sources (Hindu Playwright + RSS + PIB + ORF + MEA + IDSA)",
                "2. Date filter (36h)",
                "3. Content extraction",
                "4. Pass 1 batch scoring",
                "5. Relevance threshold filter (55)",
                "6. ArticleSelector",
                "6.5. LLM content enhancement",
                "7. Pass 2 knowledge cards",
                "8. Save to database",
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
    Background task: runs UnifiedPipeline end-to-end and saves results to DB.
    Produces ~25-30 fully enriched UPSC knowledge cards per run.
    """
    try:
        from app.services.unified_pipeline import UnifiedPipeline
        logger.info("🚀 UnifiedPipeline started (Hindu Playwright + RSS + AI enrichment)")
        start_time = datetime.utcnow()

        pipeline = UnifiedPipeline()
        result = await pipeline.run(max_articles=30, save_to_db=True)

        processing_time = (datetime.utcnow() - start_time).total_seconds()
        saved = result.get("db_save", {}).get("saved", 0)
        errors = result.get("db_save", {}).get("errors", 0)

        logger.info(
            "🎉 UnifiedPipeline complete in %.2fs: fetched=%d enriched=%d saved=%d errors=%d",
            processing_time,
            result.get("total_fetched", 0),
            result.get("total_enriched", 0),
            saved,
            errors,
        )
        logger.info("   GS distribution: %s", result.get("gs_distribution", {}))

    except Exception as e:
        logger.error("❌ UnifiedPipeline background task failed: %s", e)
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
                "pipeline": "unified-pipeline (Hindu Playwright + RSS + full AI enrichment)",
                "sources": [
                    "The Hindu (Playwright, 6 sections: editorial, national, international, economy, sci_tech, environment)",
                    "RSS feeds (LiveLaw, PIB)",
                    "ORF, MEA, IDSA (httpx scrapers)",
                ],
                "enrichment": "Pass 1 scoring → ArticleSelector → LLM enhancement → Pass 2 knowledge cards",
                "automation_ready": True,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation status: {str(e)}",
        )
