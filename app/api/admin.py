"""
Admin API Endpoints

One-time operational endpoints for managing Render deployments:
- POST /api/admin/hindu-login  — Seeds Hindu cookies into Supabase (run once after fresh deploy)

Compatible with: FastAPI 0.116.1, Python 3.13.5
Created: 2026-02-26
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging
from datetime import datetime

from ..core.security import require_admin_access
from ..core.config import get_settings

router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


@router.post("/hindu-login", response_model=Dict[str, Any])
async def trigger_hindu_login(
    user: dict = Depends(require_admin_access),
):
    """
    Seed Hindu session cookies into Supabase.

    Call this once after a fresh Render deploy (or when Hindu scraping returns 0 articles
    due to expired/missing cookies). It reads HINDU_EMAIL and HINDU_PASSWORD from env,
    performs the Piano SSO login, and saves the resulting cookies to Supabase so that
    subsequent pipeline runs can use them without re-logging in.

    This endpoint is idempotent — running it again simply refreshes the cookies.
    """
    settings = get_settings()

    email = settings.HINDU_EMAIL
    password = settings.HINDU_PASSWORD

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "HINDU_EMAIL and HINDU_PASSWORD env vars are not set. "
                "Set them in the Render dashboard and redeploy."
            ),
        )

    try:
        from app.services.playwright_session import PlaywrightSessionManager

        logger.info("[admin/hindu-login] Starting Hindu login for %s", email)
        session = PlaywrightSessionManager()
        try:
            await session.login_hindu(email, password)
        finally:
            await session.close()

        logger.info(
            "[admin/hindu-login] Hindu login successful, cookies saved to Supabase"
        )
        return {
            "success": True,
            "message": "Hindu login successful. Cookies saved to Supabase. Next pipeline run will use them.",
            "email": email,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("[admin/hindu-login] Login failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hindu login failed: {str(e)}",
        )
