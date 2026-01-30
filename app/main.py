"""
FastAPI Backend for UPSC Current Affairs Platform
Main application entry point with integrated security and middleware

Created: 2025-08-29
Compatible with: Python 3.13.5, FastAPI 0.116.1

Features:
- API Key authentication with Bearer token support
- Production-ready middleware stack
- CORS configuration for Next.js integration
- Comprehensive error handling and logging
- Railway deployment ready
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

# Import configuration and security
from app.core.config import get_settings, Settings
from app.core.security import (
    require_authentication,
    require_admin_access,
    SECURITY_CONFIG,
)
from app.core.middleware import configure_middleware
from app.core.database import get_database, SupabaseConnection

# Import API routers - Streamlined (removed deprecated drishti_scraper_api)
from app.api import current_affairs, automation, simplified_flow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Create FastAPI application with integrated security and middleware
    Following 2025 best practices for production deployment
    """
    settings = get_settings()

    # FastAPI application with metadata and security
    app = FastAPI(
        title="UPSC Current Affairs API",
        description="FastAPI backend for processing current affairs from RSS sources and Drishti IAS scraping",
        version="1.0.0",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_tags=[
            {
                "name": "Health",
                "description": "Health check and system status endpoints",
            },
            {
                "name": "Authentication",
                "description": "API authentication and security endpoints",
            },
            {
                "name": "Current Affairs",
                "description": "RSS and Drishti IAS content processing endpoints",
            },
        ],
    )

    # Configure all middleware (security, CORS, logging, error handling)
    configure_middleware(app)

    return app


# Create the FastAPI application instance
app = create_application()


@app.get("/")
async def root():
    """
    Root endpoint - health check
    """
    return {
        "service": "UPSC Current Affairs FastAPI Backend",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "docs": "/docs" if get_settings().environment == "development" else "disabled",
    }


@app.get("/api/health", tags=["Health"])
async def health_check(db: SupabaseConnection = Depends(get_database)):
    """
    Health check endpoint for monitoring and Railway deployment
    Public endpoint - no authentication required
    Includes database connectivity check
    """
    settings = get_settings()

    # Check database health
    db_health = await db.health_check()

    return {
        "status": "healthy" if db_health.get("status") == "healthy" else "degraded",
        "service": "upsc-current-affairs-api",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "python_version": "3.13.5",
        "fastapi_version": "0.116.1",
        "configuration": {
            "supabase_configured": bool(
                settings.supabase_url and settings.supabase_service_key
            ),
            "gemini_configured": bool(settings.gemini_api_key),
            "api_key_configured": bool(settings.api_key),
        },
        "database": {
            "status": db_health.get("status", "unknown"),
            "connection": db_health.get("connection", "unknown"),
            "table_accessible": db_health.get("table_accessible", False),
            "total_records": db_health.get("total_records", 0),
        },
    }


@app.get("/api/auth/verify", tags=["Authentication"])
async def verify_authentication(user: dict = Depends(require_authentication)):
    """
    Verify API key authentication
    Protected endpoint - requires Bearer token authentication
    """
    return {
        "success": True,
        "message": "Authentication successful",
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
    }


@app.get("/api/auth/admin/status", tags=["Authentication"])
async def admin_status(
    user: dict = Depends(require_admin_access),
    db: SupabaseConnection = Depends(get_database),
):
    """
    Admin status endpoint with database statistics
    Protected endpoint - requires admin-level authentication
    """
    settings = get_settings()

    # Get database statistics
    db_health = await db.health_check()
    current_affairs_count = await db.get_current_affairs_count()

    return {
        "success": True,
        "message": "Admin access granted",
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
        "system_info": {
            "environment": settings.environment,
            "configuration_valid": settings.validate_required_settings()[
                "all_required_configured"
            ],
            "cors_origins": settings.cors_origins,
            "max_articles_per_source": settings.max_articles_per_source,
            "min_upsc_relevance": settings.min_upsc_relevance,
        },
        "database_stats": {
            "status": db_health.get("status", "unknown"),
            "total_current_affairs": current_affairs_count,
            "connection_healthy": db_health.get("table_accessible", False),
        },
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Global HTTP exception handler
    """
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Global exception handler for unexpected errors
    """
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ✅ CORE API ENDPOINTS - Streamlined Architecture (using router's own tags)
app.include_router(simplified_flow.router)
app.include_router(current_affairs.router)
app.include_router(automation.router)
# Removed: drishti_scraper_api.router (deprecated)

# 🎯 Clean, focused API - No legacy aliases needed

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="info",
    )
