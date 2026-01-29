# FastAPI Backend Dockerfile - Optimized for Production
# Revolutionary RSS Processing System with Enhanced Drishti IAS Integration
# Compatible with: Python 3.13, FastAPI 0.116.1

FROM python:3.13-slim

# Set environment variables for optimal performance
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory and user for security
WORKDIR /app
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies optimized for the application
RUN apt-get update && apt-get install -y \
    # Chrome dependencies for Selenium (Drishti scraper)
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    # Add Chrome repository
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    # Clean up to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    # Pre-compile Python files for performance
    && python -m compileall -b . \
    # Remove .py files to save space (keep .pyc)
    && find . -name "*.py" -delete 2>/dev/null || true

# Copy application code
COPY . .

# Set up Chrome for headless operation (Drishti scraper)
ENV DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_DRIVER_PATH=/usr/bin/chromedriver

# Create directories and set permissions
RUN mkdir -p /app/logs /app/cache /app/temp \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Switch to non-root user for security
USER appuser

# Expose port
EXPOSE 8000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production-optimized startup command
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-log", \
     "--log-level", "info", \
     "--loop", "uvloop", \
     "--http", "httptools"]