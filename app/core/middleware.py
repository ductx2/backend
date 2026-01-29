"""
FastAPI Middleware Configuration
Production-ready middleware stack for security, CORS, and performance

Middleware Stack:
1. Security headers middleware
2. CORS middleware (configured from settings)
3. Request logging middleware
4. Error handling middleware
5. Rate limiting preparation (future)

Compatible with FastAPI 0.116.1 and Python 3.13.5
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .security import create_security_headers

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Security Headers Middleware
    Adds security headers to all HTTP responses
    """
    
    def __init__(self, app):
        self.app = app
        self.security_headers = create_security_headers()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Add security headers to response
                    headers = dict(message.get("headers", []))
                    for key, value in self.security_headers.items():
                        headers[key.encode()] = value.encode()
                    message["headers"] = list(headers.items())
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    """
    Request Logging Middleware
    Logs all incoming requests with timing information
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            
            # Extract request information
            method = scope.get("method", "")
            path = scope.get("path", "")
            
            # Log request start
            logger.info(f"Request started: {method} {path}")
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Calculate request duration
                    duration = time.time() - start_time
                    status_code = message.get("status", 0)
                    
                    # Log request completion
                    logger.info(
                        f"Request completed: {method} {path} - "
                        f"Status: {status_code} - Duration: {duration:.3f}s"
                    )
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


class ErrorHandlingMiddleware:
    """
    Global Error Handling Middleware
    Catches and formats unhandled exceptions
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            try:
                await self.app(scope, receive, send)
            except Exception as exc:
                # Log the error
                logger.error(f"Unhandled exception: {exc}", exc_info=True)
                
                # Send error response
                response = JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "Internal server error",
                        "message": "An unexpected error occurred",
                        "type": "server_error"
                    }
                )
                
                await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)


def configure_cors(app) -> None:
    """
    Configure CORS middleware with settings from configuration
    
    Args:
        app: FastAPI application instance
    """
    cors_config = settings.get_cors_config()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
        expose_headers=["X-Total-Count", "X-Request-ID"]
    )
    
    logger.info(f"CORS configured with origins: {cors_config['allow_origins']}")


def configure_middleware(app) -> None:
    """
    Configure all middleware for the FastAPI application
    Order matters - middleware is applied in reverse order
    
    Args:
        app: FastAPI application instance
    """
    
    # 1. Error handling (outermost - catches all errors)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # 2. Request logging
    if not settings.is_production:
        app.add_middleware(RequestLoggingMiddleware)
    
    # 3. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 4. CORS (innermost - handles preflight requests)
    configure_cors(app)
    
    logger.info("All middleware configured successfully")


# Middleware configuration for easy import
MIDDLEWARE_CONFIG = {
    "security_headers": SecurityHeadersMiddleware,
    "request_logging": RequestLoggingMiddleware, 
    "error_handling": ErrorHandlingMiddleware,
    "configure_all": configure_middleware
}