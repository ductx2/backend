# UPSC Backend API

FastAPI backend for UPSC platform with Groq and Gemini AI integration.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- **Health Check**: `GET /api/health`
- **Current Affairs**: `POST /api/current-affairs/*`
- **Daily Solutions**: `POST /api/daily-solutions/*`
- **Drishti Scraper**: `POST /api/drishti/*`
- **Flow API**: `POST /api/flow/*`
- **Automation**: `POST /api/automation/*`

## Key Services

- **Groq LLM Service** - Multi-API key rotation for AI processing
- **Gemini Service** - Centralized Google Gemini integration
- **Content Extractor** - Universal web content extraction
- **RSS Processor** - Optimized RSS feed processing
- **Drishti Scraper** - Chrome-free web scraping

## Configuration

Environment variables (see main project `.env`):
- `SUPABASE_URL` - Database connection
- `SUPABASE_SERVICE_ROLE_KEY` - Database service key
- `GEMINI_API_KEY` - Google Gemini API
- `GROQ_API_KEYS` - Groq API keys (comma-separated)
- `FASTAPI_API_KEY` - API authentication

## Tech Stack

- Python 3.13.5
- FastAPI 0.116.1
- Supabase (PostgreSQL)
- Google Gemini 2.5 Flash
- Groq API
- LiteLLM (Multi-provider routing)
