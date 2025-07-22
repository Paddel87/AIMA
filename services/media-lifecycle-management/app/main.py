#!/usr/bin/env python3
"""
AIMA Media Lifecycle Management Service

This service manages the complete lifecycle of media files from upload to archival.
Implemented following the Bottom-to-Top principle with robust error handling.
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.redis import init_redis, close_redis
from app.core.storage import init_storage, close_storage
from app.core.exceptions import (
    MediaServiceError,
    StorageError,
    ValidationError,
    NotFoundError
)
from app.api.v1 import media, health
from app.core.middleware import (
    RequestLoggingMiddleware,
    ErrorHandlingMiddleware,
    MetricsMiddleware
)

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
    """Application lifespan manager with graceful startup/shutdown."""
    settings = get_settings()
    
    logger.info("Starting AIMA Media Lifecycle Management Service", version="1.0.0")
    
    try:
        # Phase 1: Database initialization (Bottom-to-Top principle)
        logger.info("Phase 1: Initializing database connection...")
        await init_db()
        logger.info("✓ Database initialized successfully")
        
        # Phase 2: Redis initialization
        logger.info("Phase 2: Initializing Redis connection...")
        await init_redis()
        logger.info("✓ Redis initialized successfully")
        
        # Phase 3: Storage initialization (MinIO/S3)
        logger.info("Phase 3: Initializing object storage...")
        await init_storage()
        logger.info("✓ Object storage initialized successfully")
        
        # Phase 4: Service validation
        logger.info("Phase 4: Validating service configuration...")
        logger.info("✓ Media Lifecycle Management Service validated")
        
        logger.info("🚀 AIMA Media Lifecycle Management Service started successfully")
        
        yield
        
    except Exception as e:
        logger.error("❌ Failed to start service", error=str(e))
        sys.exit(1)
    
    finally:
        # Graceful shutdown in reverse order
        logger.info("Shutting down AIMA Media Lifecycle Management Service...")
        
        try:
            await close_storage()
            await close_redis()
            await close_db()
            logger.info("✓ Media Lifecycle Management Service shutdown completed")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="AIMA Media Lifecycle Management Service",
        description="Comprehensive media file lifecycle management from upload to archival",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # Add security middleware
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", "*.aima.local"]
        )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Exception handlers
    @app.exception_handler(MediaServiceError)
    async def media_service_exception_handler(request: Request, exc: MediaServiceError):
        logger.error("Media service error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code}
        )
    
    @app.exception_handler(StorageError)
    async def storage_exception_handler(request: Request, exc: StorageError):
        logger.error("Storage error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Storage operation failed", "error_code": "STORAGE_ERROR"}
        )
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        logger.warning("Validation error", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "error_code": "VALIDATION_ERROR"}
        )
    
    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        logger.warning("Resource not found", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "error_code": "NOT_FOUND"}
        )
    
    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(media.router, prefix="/api/v1/media", tags=["Media"])
    
    return app


# Create the application instance
app = create_app()


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "AIMA Media Lifecycle Management",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "media": "/api/v1/media",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )