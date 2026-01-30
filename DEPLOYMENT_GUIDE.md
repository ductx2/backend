# FastAPI Backend Deployment Guide - Railway

This guide covers deploying the revolutionary FastAPI backend to Railway with optimal performance configurations.

## 🚀 Pre-Deployment Checklist

### Required Environment Variables

Set these in your Railway dashboard:

```bash
# Security & Authentication
API_KEY=your-secure-32-character-api-key
ENVIRONMENT=production

# Database (from existing UPSC project)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

# AI Processing
GEMINI_API_KEY=your-google-gemini-api-key

# Optional Performance Settings
MAX_ARTICLES_PER_SOURCE=50
MIN_UPSC_RELEVANCE=40
CACHE_TTL_MINUTES=15
API_DOCS_ENABLED=false
LOG_LEVEL=INFO
```

### Frontend Integration

```bash
CORS_ORIGINS=["https://www.vaidra.in", "https://your-domain.com"]
```

## 📦 Deployment Steps

### 1. Railway Setup

1. Connect your GitHub repository to Railway
2. Select the `backend` folder as the root directory
3. Railway will automatically detect the Python project

### 2. Environment Configuration

In Railway dashboard > Variables:

- Add all environment variables listed above
- Ensure `PORT` is handled automatically by Railway
- Set `RAILWAY_ENVIRONMENT=production`

### 3. Build Configuration

Railway uses the included configurations:

- `railway.json` - Railway-specific settings
- `requirements.txt` - Python dependencies
- `Procfile` - Process configuration
- `runtime.txt` - Python version specification

### 4. Deployment Commands

Railway will automatically run:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 🎯 Performance Optimizations

### Revolutionary RSS Processing

- **Parallel Processing**: 6 RSS sources processed simultaneously
- **Performance**: 10x+ faster than legacy sequential processing
- **Caching**: Smart TTL-based caching system
- **Error Handling**: Robust retry mechanisms

### Enhanced Drishti IAS Scraping

- **Browser Automation**: Selenium with Chrome headless mode
- **Content Extraction**: BeautifulSoup for reliable parsing
- **Anti-Detection**: Stealth mode for stable scraping
- **Content Preference**: Drishti content prioritized over RSS

### AI Processing Efficiency

- **Model**: Gemini 2.5 Flash for optimal performance
- **Structured Output**: Native responseSchema for JSON generation
- **Cost Reduction**: 66%+ savings with single-pass processing
- **Batch Processing**: Efficient API usage patterns

### Database Operations

- **Bulk Operations**: Optimized Supabase interactions
- **Duplicate Detection**: Content hash-based deduplication
- **Error Recovery**: Graceful handling of database issues
- **Connection Pooling**: Efficient connection management

## 🔒 Security Features

### Authentication

- **API Key**: Bearer token authentication
- **Admin Access**: Multi-level permission system
- **CORS**: Properly configured for frontend integration
- **Input Validation**: Comprehensive request validation

### Rate Limiting & Monitoring

- **Health Checks**: `/api/health` endpoint for monitoring
- **Performance Metrics**: Real-time processing statistics
- **Error Tracking**: Comprehensive logging system
- **Resource Usage**: Optimized memory and CPU usage

## 🌐 API Endpoints

### Core Endpoints

- `GET /` - Service status and information
- `GET /api/health` - Health check and system status
- `GET /api/auth/verify` - Authentication verification
- `GET /api/auth/admin/status` - Admin dashboard

### Revolutionary RSS Processing

- `POST /api/extract/rss-sources` - Process all 6 RSS sources (Master Plan endpoint)
- `GET /api/rss/sources/health` - RSS sources health status
- `GET /api/rss/performance/metrics` - Performance metrics
- `POST /api/rss/test/parallel-fetch` - Performance testing

### Enhanced Drishti IAS Scraping

- `POST /api/drishti/scrape/daily-current-affairs` - Daily content
- `POST /api/drishti/scrape/editorial-content` - Editorial articles
- `POST /api/drishti/scrape/comprehensive` - Full scraping
- `GET /api/drishti/scraper/status` - Scraper health

### Unified Content Processing

- `POST /api/unified/process-all-sources` - Complete processing
- `POST /api/unified/process-rss-only` - RSS only
- `POST /api/unified/process-drishti-only` - Drishti only
- `GET /api/unified/content-preference/test` - Test preference logic

## 📊 Monitoring & Analytics

### Performance Metrics

- Processing speed (articles/second)
- Source success rates
- AI processing efficiency
- Database operation performance
- Cache hit rates

### Health Monitoring

- RSS source availability
- Database connectivity
- AI service status
- Memory and CPU usage
- Error rates and patterns

## 🚨 Troubleshooting

### Common Issues

**Environment Variables Missing**

- Check Railway dashboard Variables section
- Ensure all required secrets are set
- Verify environment format matches requirements

**Database Connection Issues**

- Validate Supabase URL and service key
- Check network connectivity from Railway
- Verify RLS policies allow service role access

**AI Processing Failures**

- Check Gemini API key validity
- Verify API quotas and limits
- Review model availability and regions

**RSS Processing Errors**

- Check RSS source availability
- Verify network access to RSS URLs
- Review caching and TTL settings

### Debug Commands

```bash
# Check service health
curl https://your-app.railway.app/api/health

# Verify authentication
curl -H "Authorization: Bearer YOUR_API_KEY" https://your-app.railway.app/api/auth/verify

# Test RSS processing
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" https://your-app.railway.app/api/extract/rss-sources
```

## 🎉 Post-Deployment Validation

1. **Health Check**: Verify `/api/health` returns status "healthy"
2. **Authentication**: Test API key authentication works
3. **RSS Processing**: Run parallel RSS fetch test
4. **Database**: Confirm Supabase connectivity
5. **AI Processing**: Validate Gemini integration
6. **Performance**: Confirm 10x+ speed improvement achieved

## 📈 Performance Benchmarks

### Expected Performance

- **RSS Fetching**: 6 sources in 2-4 seconds (10x+ improvement)
- **AI Processing**: 66%+ cost reduction vs legacy
- **Database Operations**: Bulk processing with sub-second response
- **Memory Usage**: Optimized for Railway's resource limits
- **CPU Usage**: Efficient parallel processing

### Monitoring Commands

```bash
# Get performance metrics
curl -H "Authorization: Bearer YOUR_API_KEY" https://your-app.railway.app/api/rss/performance/metrics

# Check unified system status
curl -H "Authorization: Bearer YOUR_API_KEY" https://your-app.railway.app/api/unified/status

# Validate content preference logic
curl -X GET -H "Authorization: Bearer YOUR_API_KEY" https://your-app.railway.app/api/unified/content-preference/test
```

## 🔗 Integration with Next.js Frontend

Update your Next.js environment variables:

```bash
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
FASTAPI_API_KEY=your-api-key
```

The backend is now ready for production workload with revolutionary performance improvements!
