# FastAPI Authentication System

## Overview

Production-ready API Key authentication system using Bearer tokens for the UPSC Current Affairs FastAPI backend.

## Features

- **Bearer Token Authentication**: Standard HTTP Authorization header with Bearer scheme
- **API Key Validation**: Secure API key verification against configured environment variable
- **Security Headers**: Comprehensive security headers for production deployment
- **CORS Configuration**: Configured for Next.js frontend integration
- **Middleware Stack**: Production-ready middleware for security, logging, and error handling
- **Authentication Dependencies**: Reusable FastAPI dependencies for different access levels

## Authentication Flow

```
1. Client includes Authorization header: "Bearer your_api_key"
2. FastAPI security middleware extracts Bearer token
3. Token validated against FASTAPI_API_KEY environment variable
4. Valid authentication grants access to protected endpoints
5. Invalid/missing tokens return 401 Unauthorized
```

## Environment Variables

```bash
# Required for authentication
FASTAPI_API_KEY=upsc_backend_secure_key_2025_production

# Inherited from main project (.env)
NEXT_PUBLIC_SUPABASE_URL=https://sxzrdqkbjdnrxuhjqxub.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_key
GEMINI_API_KEY=your_gemini_key
```

## API Endpoints

### Public Endpoints (No Authentication)

- `GET /` - Root endpoint with service information
- `GET /api/health` - Health check for monitoring

### Protected Endpoints (Requires Authentication)

- `GET /api/auth/verify` - Verify API key authentication
- `GET /api/auth/admin/status` - Admin status and system information

## Usage Examples

### Valid Request

```bash
curl -H "Authorization: Bearer upsc_backend_secure_key_2025_dev" \
     http://localhost:8000/api/auth/verify
```

**Response:**

```json
{
  "success": true,
  "message": "Authentication successful",
  "timestamp": "2025-08-29T18:56:36.065176Z",
  "user": {
    "user_type": "api_client",
    "authenticated": true,
    "permissions": ["read", "write", "admin"],
    "api_version": "1.0.0"
  }
}
```

### Invalid Request

```bash
curl -H "Authorization: Bearer invalid_key" \
     http://localhost:8000/api/auth/verify
```

**Response:**

```json
{
  "detail": "Invalid API key"
}
```

### Missing Authentication

```bash
curl http://localhost:8000/api/auth/verify
```

**Response:**

```json
{
  "detail": "API key required for authentication"
}
```

## Security Features

### Security Headers

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`

### CORS Configuration

```python
{
    "allow_origins": [
        "http://localhost:3000",           # Next.js development
        "https://www.vaidra.in"            # Production frontend
    ],
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE"],
    "allow_headers": ["*"]
}
```

## Implementation Details

### Core Files

1. **`app/core/security.py`** - Authentication logic and dependencies
2. **`app/core/middleware.py`** - Security middleware and CORS configuration
3. **`app/main.py`** - FastAPI application with integrated authentication

### Dependencies

```python
from app.core.security import require_authentication, require_admin_access

# Basic authentication
@app.get("/api/protected")
async def protected_endpoint(user: dict = Depends(require_authentication)):
    return {"message": "Access granted", "user": user}

# Admin access
@app.get("/api/admin")
async def admin_endpoint(user: dict = Depends(require_admin_access)):
    return {"message": "Admin access granted", "user": user}
```

### Middleware Stack (Applied in Order)

1. **Error Handling** - Catches unhandled exceptions
2. **Request Logging** - Logs requests in development
3. **Security Headers** - Adds security headers to responses
4. **CORS** - Handles cross-origin requests

## Testing

### Configuration Test

```bash
cd backend
python test_authentication.py
```

### Live Testing (Server Running)

```bash
# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test authentication
curl -H "Authorization: Bearer your_api_key" http://localhost:8000/api/auth/verify
```

## Integration with Next.js Frontend

```typescript
// Frontend API client configuration
const API_BASE_URL = 'http://localhost:8000'; // or your Railway URL
const API_KEY = process.env.FASTAPI_API_KEY;

const fetchWithAuth = async (endpoint: string, options = {}) => {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
};

// Usage example
const data = await fetchWithAuth('/api/auth/verify');
```

## Production Deployment

### Railway Configuration

```bash
# Set environment variable in Railway
FASTAPI_API_KEY=upsc_backend_secure_key_2025_production
```

### Security Checklist

- ✅ API key is randomly generated and secure
- ✅ HTTPS enforced in production
- ✅ Security headers configured
- ✅ CORS properly restricted
- ✅ Error messages don't expose sensitive information
- ✅ Request logging configured for monitoring

## Error Handling

### Authentication Errors

- **401 Unauthorized** - Invalid or missing API key
- **403 Forbidden** - Valid key but insufficient permissions (future use)
- **500 Internal Server Error** - Server-side authentication error

### Error Response Format

```json
{
  "success": false,
  "error": "Error description",
  "timestamp": "2025-08-29T18:56:36.065176Z"
}
```

## Future Enhancements

- Rate limiting by API key
- Multiple API keys with different permissions
- JWT token authentication for user-specific access
- API key rotation mechanism
- Audit logging for security events

---

_Authentication system implemented: 2025-08-29_  
_Compatible with: FastAPI 0.116.1, Python 3.13.5_
