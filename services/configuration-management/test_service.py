#!/usr/bin/env python3
"""
Test script for the AIMA Configuration Management Service.

This script runs a simplified version of the service for testing purposes
without requiring Docker or external dependencies.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create a simple test FastAPI app
app = FastAPI(
    title="AIMA Configuration Management Service (Test Mode)",
    description="Test version of the Configuration Management Service",
    version="1.0.0-test"
)

@app.get("/")
async def root():
    return {
        "service": "AIMA Configuration Management (Test Mode)",
        "status": "running",
        "version": "1.0.0-test",
        "message": "Service is running in test mode without database"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "configuration-management",
        "mode": "test",
        "checks": {
            "application": {
                "status": "healthy",
                "message": "Application is running"
            },
            "database": {
                "status": "not_configured",
                "message": "Running in test mode without database"
            },
            "redis": {
                "status": "not_configured",
                "message": "Running in test mode without Redis"
            }
        }
    }

@app.get("/api/v1/config")
async def get_test_configs():
    return {
        "items": [
            {
                "key": "system.service_name",
                "value": "AIMA Configuration Management",
                "data_type": "string",
                "category": "system",
                "description": "Test configuration",
                "is_readonly": True
            },
            {
                "key": "system.version",
                "value": "1.0.0-test",
                "data_type": "string",
                "category": "system",
                "description": "Service version",
                "is_readonly": True
            }
        ],
        "total": 2,
        "message": "Test data - no database connection"
    }

@app.get("/info")
async def service_info():
    return {
        "service": "AIMA Configuration Management",
        "version": "1.0.0-test",
        "mode": "test",
        "endpoints": {
            "health": "/health",
            "config": "/api/v1/config",
            "docs": "/docs"
        },
        "note": "This is a test version running without database dependencies"
    }

if __name__ == "__main__":
    logger.info("Starting Configuration Management Service in test mode...")
    
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8002,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service failed to start: {e}")
        sys.exit(1)