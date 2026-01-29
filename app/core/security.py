"""
FastAPI Security Module - API Key Authentication
Production-ready authentication system for backend security

Features:
- Bearer token authentication with API key validation
- Secure dependency injection for protected endpoints
- Environment-based API key configuration
- Security headers for production deployment
- Rate limiting preparation (future integration)

Compatible with FastAPI 0.116.1 and Python 3.13.5
"""

from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param

from .config import get_settings

# Initialize settings for API key validation
settings = get_settings()

# HTTPBearer security scheme for Bearer token authentication
security = HTTPBearer(
    scheme_name="Bearer Token",
    description="API key required for authentication",
    auto_error=False  # Custom error handling
)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    """
    Verify API key authentication
    
    Args:
        credentials: HTTPAuthorizationCredentials from Bearer token
        
    Returns:
        bool: True if authentication successful
        
    Raises:
        HTTPException: 401 if authentication fails
    """
    
    # Check if credentials provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required for authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate the API key
    provided_key = credentials.credentials
    expected_key = settings.api_key
    
    if not provided_key or provided_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True


async def get_current_user(authenticated: bool = Depends(verify_api_key)) -> dict:
    """
    Get current authenticated user information
    Used as dependency for endpoints requiring authentication
    
    Args:
        authenticated: Result from verify_api_key dependency
        
    Returns:
        dict: User information (system user for API key auth)
    """
    return {
        "user_type": "api_client",
        "authenticated": True,
        "permissions": ["read", "write", "admin"],
        "api_version": "1.0.0"
    }


def create_security_headers() -> dict:
    """
    Create security headers for production deployment
    
    Returns:
        dict: Security headers for HTTP responses
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com;",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }


class APIKeyAuth:
    """
    API Key Authentication Class
    Provides reusable authentication methods for different endpoint types
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    def authenticate_request(self, authorization: Optional[str]) -> bool:
        """
        Authenticate request using Authorization header
        
        Args:
            authorization: Authorization header value
            
        Returns:
            bool: True if authentication successful
        """
        if not authorization:
            return False
        
        scheme, credentials = get_authorization_scheme_param(authorization)
        
        if scheme.lower() != "bearer":
            return False
        
        return credentials == self.settings.api_key
    
    def is_valid_key(self, api_key: str) -> bool:
        """
        Validate API key directly
        
        Args:
            api_key: API key to validate
            
        Returns:
            bool: True if key is valid
        """
        return api_key == self.settings.api_key


# Global authentication instance
auth = APIKeyAuth()


# Common authentication dependencies for different access levels
async def require_authentication(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Basic authentication requirement
    Use for endpoints requiring authentication
    """
    await verify_api_key(credentials)
    return await get_current_user(True)


async def require_admin_access(
    user: dict = Depends(require_authentication)
) -> dict:
    """
    Admin access requirement
    Use for administrative endpoints
    """
    # For API key auth, all authenticated users have admin access
    return user


# Security configuration for FastAPI app
SECURITY_CONFIG = {
    "dependencies": {
        "authentication": require_authentication,
        "admin": require_admin_access
    },
    "headers": create_security_headers(),
    "schemes": {
        "bearer": security
    }
}