# Multi-stage Dockerfile for AIMA Media Lifecycle Management Service
# Based on the proven Foundation Services template

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Development stage
FROM base as development

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs && chown -R appuser:appuser /app

USER appuser

EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]

# Production stage
FROM base as production

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-dev -r requirements.txt

# Copy only necessary application files
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY start_service.py .

# Create logs directory
RUN mkdir -p logs && chown -R appuser:appuser /app

USER appuser

EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["python", "start_service.py"]