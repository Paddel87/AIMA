#!/usr/bin/env python3
"""
AIMA User Management Service

This service handles user authentication, authorization, and user management
for the AIMA system according to the technical blueprint and modularization design.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
import structlog

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis
from app.core.messaging import init_messaging, close_messaging
from app.core.exceptions import AIMAException
from app.core.middleware import LoggingMiddleware, MetricsMiddleware

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    
    logger.info("Starting AIMA User Management Service", version="1.0.0")
    
    try:
        # Initialize database connection
        await init_db()
        logger.info("Database connection initialized")
        
        # Initialize Redis connection
        await init_redis()
        logger.info("Redis connection initialized")
        
        # Initialize messaging
        await init_messaging()
        logger.info("Message broker connection initialized")
        
        logger.info("User Management Service startup completed")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start User Management Service", error=str(e))
        sys.exit(1)
    
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down User Management Service")
        
        await close_messaging()
        await close_redis()
        await close_db()
        
        logger.info("User Management Service shutdown completed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="AIMA User Management Service",
        description="User authentication, authorization, and management service for the AIMA system",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    
    # Include API routers
    app.include_router(api_router)
    
    # Add Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    # Global exception handler
    @app.exception_handler(AIMAException)
    async def aima_exception_handler(request: Request, exc: AIMAException):
        logger.error(
            "AIMA exception occurred",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            path=request.url.path
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception occurred",
            error=str(exc),
            path=request.url.path,
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred",
                    "details": None
                }
            }
        )
    
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_config=None,  # Use structlog instead
        access_log=False  # Use custom middleware instead
    )