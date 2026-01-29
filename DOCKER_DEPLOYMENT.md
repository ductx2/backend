# Docker Deployment Guide - FastAPI Backend

This guide covers deploying the revolutionary FastAPI backend using Docker with optimal performance configurations.

## 🐳 Docker Features

### Optimized Container Configuration
- **Base Image**: Python 3.13 slim for minimal size
- **Security**: Non-root user execution
- **Performance**: Pre-compiled Python bytecode
- **Resource Limits**: Production-ready constraints
- **Health Checks**: Automatic health monitoring

### Selenium Chrome Support
- **Google Chrome**: Installed for Drishti IAS scraping
- **ChromeDriver**: Automatic driver management
- **Headless Mode**: Optimized for container environments
- **Display**: Virtual display for browser automation

## 🚀 Quick Start

### 1. Build the Docker Image
```bash
cd backend
docker build -t upsc-fastapi-backend:latest .
```

### 2. Create Environment File
```bash
# Create .env file with your configuration
cp .env.production .env

# Edit .env with your actual values:
API_KEY=your-secure-32-character-api-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
GEMINI_API_KEY=your-google-gemini-api-key
```

### 3. Run with Docker Compose
```bash
docker-compose up -d
```

### 4. Verify Deployment
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f fastapi-backend

# Test health endpoint
curl http://localhost:8000/api/health
```

## 🔧 Configuration Options

### Environment Variables
```bash
# Core Configuration
ENVIRONMENT=production
API_DOCS_ENABLED=false
LOG_LEVEL=INFO

# Performance Settings
MAX_ARTICLES_PER_SOURCE=50
MIN_UPSC_RELEVANCE=40
CACHE_TTL_MINUTES=15

# Security Settings
CORS_ORIGINS=["https://your-frontend.com"]

# Required Secrets
API_KEY=your-api-key
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-service-key
GEMINI_API_KEY=your-gemini-key
```

### Resource Limits
```yaml
# Production resource configuration
deploy:
  resources:
    limits:
      cpus: '2.0'      # Maximum CPU cores
      memory: 2G       # Maximum memory
    reservations:
      cpus: '0.5'      # Reserved CPU cores
      memory: 512M     # Reserved memory
```

## 🏗️ Production Deployment

### 1. Build Production Image
```bash
# Build optimized production image
docker build -t upsc-fastapi-backend:prod \
  --target production \
  --build-arg BUILD_ENV=production .
```

### 2. Deploy with Docker Swarm
```bash
# Initialize swarm (if not already done)
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml upsc-backend
```

### 3. Deploy with Kubernetes
```bash
# Generate Kubernetes manifests
docker-compose config | kompose convert -f -

# Deploy to Kubernetes
kubectl apply -f upsc-backend-*
```

## 📊 Monitoring & Health Checks

### Container Health
```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' upsc-backend

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' upsc-backend
```

### Application Metrics
```bash
# Get performance metrics
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/api/rss/performance/metrics

# Check unified system status
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/api/unified/status
```

### Log Monitoring
```bash
# Follow application logs
docker-compose logs -f fastapi-backend

# View specific service logs
docker logs upsc-backend --tail 100 -f

# Export logs for analysis
docker logs upsc-backend > backend-logs.txt
```

## 🔍 Troubleshooting

### Common Issues

**Container Build Failures**
```bash
# Clear Docker cache
docker system prune -a

# Build with verbose output
docker build --no-cache --progress=plain -t upsc-fastapi-backend .
```

**Chrome/Selenium Issues**
```bash
# Check Chrome installation
docker exec upsc-backend google-chrome --version

# Test display configuration
docker exec upsc-backend echo $DISPLAY

# Debug Selenium setup
docker exec upsc-backend python -c "from selenium import webdriver; print('Selenium OK')"
```

**Memory/Performance Issues**
```bash
# Check container resource usage
docker stats upsc-backend

# Increase memory limits in docker-compose.yml
# memory: 4G  # Increase if needed
```

**Network Connectivity**
```bash
# Test external connectivity
docker exec upsc-backend curl -I https://www.drishtiias.com

# Check DNS resolution
docker exec upsc-backend nslookup www.google.com

# Test Supabase connectivity
docker exec upsc-backend curl -I https://your-project.supabase.co
```

### Debug Commands
```bash
# Interactive shell in container
docker exec -it upsc-backend /bin/bash

# Check Python environment
docker exec upsc-backend python --version
docker exec upsc-backend pip list

# Test API endpoints
docker exec upsc-backend curl -f http://localhost:8000/api/health

# Run internal tests
docker exec upsc-backend python test_live_processing.py
```

## 🚀 Performance Optimizations

### Container Optimizations
- **Multi-stage builds**: Reduced image size
- **Layer caching**: Faster subsequent builds
- **Minimal base image**: Python 3.13 slim
- **Compiled bytecode**: Pre-compiled Python files
- **Non-root user**: Enhanced security

### Application Optimizations
- **Revolutionary RSS processing**: 10x+ performance improvement
- **Parallel source processing**: Simultaneous RSS and Drishti scraping
- **Smart caching**: Dynamic TTL-based caching
- **Bulk database operations**: Optimized Supabase interactions
- **Single-pass AI**: 66%+ cost reduction with Gemini 2.5 Flash

### Chrome/Selenium Optimizations
- **Headless mode**: Reduced resource usage
- **Optimized arguments**: Performance-focused Chrome configuration
- **Virtual display**: Xvfb for GUI-less environments
- **Memory limits**: Prevent Chrome memory leaks

## 🔐 Security Best Practices

### Container Security
- **Non-root execution**: Application runs as `appuser`
- **Minimal attack surface**: Only essential packages installed
- **Read-only filesystem**: Where possible
- **Resource limits**: Prevent resource exhaustion

### Application Security
- **API key authentication**: Bearer token security
- **Input validation**: Comprehensive request validation
- **CORS configuration**: Restricted origins
- **Environment isolation**: Secrets via environment variables

## 📈 Scaling Considerations

### Horizontal Scaling
```yaml
# Scale with Docker Compose
docker-compose up -d --scale fastapi-backend=3

# Load balancer configuration needed for multiple instances
```

### Vertical Scaling
```yaml
# Increase container resources
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
```

### Microservices Architecture
- **RSS Processor**: Separate container for RSS processing
- **Drishti Scraper**: Dedicated container for web scraping
- **Database Service**: External Supabase (managed)
- **AI Service**: Gemini API (external)

## 🎯 Production Checklist

- [ ] Environment variables configured
- [ ] Resource limits set appropriately
- [ ] Health checks enabled
- [ ] Logging configured
- [ ] Monitoring setup
- [ ] Backup strategy defined
- [ ] Security measures implemented
- [ ] Performance validated
- [ ] Documentation updated
- [ ] Team training completed

The Docker deployment provides a robust, scalable, and secure environment for the revolutionary FastAPI backend with all its performance optimizations intact!