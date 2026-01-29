# UPSC Current Affairs FastAPI Backend

Production-ready FastAPI backend for processing current affairs from RSS sources and Drishti IAS scraping.

## 🚀 Quick Start

### Prerequisites
- Python 3.13.5+
- All environment variables configured (see main project .env)

### Installation
```bash
cd backend
pip install -r requirements.txt
```

### Development Server
```bash
# From backend directory
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access Points
- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/api/health
- **Documentation**: http://localhost:8000/docs (development only)

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── core/             # Configuration and settings
│   ├── api/              # API endpoints
│   ├── services/         # Business logic
│   ├── models/           # Pydantic schemas
│   └── utils/            # Helper functions
├── tests/                # Test suite
├── docs/                 # Documentation
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## 🔧 Configuration

Environment variables are loaded from the main project .env file:
- `SUPABASE_URL` - Database connection
- `SUPABASE_SERVICE_ROLE_KEY` - Database service key  
- `GEMINI_API_KEY` - AI processing
- `FASTAPI_API_KEY` - API authentication

## 📊 Current Status

✅ **Completed**:
- FastAPI application structure
- Basic health check endpoint
- Production-ready configuration
- Python 3.13.5 compatibility
- Requirements.txt with latest versions

🔄 **In Progress**:
- Environment configuration
- API authentication
- Database integration
- RSS processing migration
- Drishti IAS scraping

## 🧪 Testing

```bash
# Run tests
cd backend
pytest

# Run with coverage
pytest --cov=app
```

## 📈 Production Deployment

Ready for Railway deployment with proper health checks and environment configuration.

---

*Created: 2025-08-29*  
*Python: 3.13.5*  
*FastAPI: 0.116.1*