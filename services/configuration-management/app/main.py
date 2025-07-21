#!/usr/bin/env python3
"""
Main application module for the AIMA Configuration Management Service.

This module sets up the FastAPI application with all necessary middleware,
routers, and configuration for the configuration management service.
"""

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.redis import RedisManager
from app.api.v1 import config, health
from app.models.database import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/config_service.log", mode="a")
    ]
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Global managers
db_manager: DatabaseManager = None
redis_manager: RedisManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events with graceful startup/shutdown."""
    global db_manager, redis_manager
    
    # Startup
    logger.info("Starting AIMA Configuration Management Service...")
    
    startup_success = False
    try:
        # Phase 1: Database initialization (Bottom-to-Top principle)
        logger.info("Phase 1: Initializing database connection...")
        db_manager = DatabaseManager()
        await db_manager.initialize_async()
        
        logger.info("✓ Database initialized successfully")
        
        # Phase 2: Redis initialization
        logger.info("Phase 2: Initializing Redis connection...")
        from app.core.redis import redis_manager, configuration_cache
        await redis_manager.initialize()
        
        if redis_manager.is_connected():
            logger.info("✓ Redis initialized successfully")
            # Update the global configuration_cache to use the initialized redis_manager
            configuration_cache.redis_manager = redis_manager
        else:
            logger.warning("⚠ Redis initialization failed - running without cache")
        
        # Phase 3: Service validation
        logger.info("Phase 3: Validating service configuration...")
        
        # Store managers in app state
        app.state.db_manager = db_manager
        app.state.redis_manager = redis_manager
        app.state.configuration_cache = configuration_cache
        
        logger.info("✓ Configuration service validated")
        
        startup_success = True
        logger.info("🚀 AIMA Configuration Management Service started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start service: {e}")
        
        # Graceful cleanup on startup failure
        try:
            from app.core.redis import redis_manager
            if redis_manager:
                await redis_manager.close()
            if db_manager:
                await db_manager.close()
        except Exception as cleanup_error:
            logger.error(f"Error during startup cleanup: {cleanup_error}")
        
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AIMA Configuration Management Service...")
    
    try:
        # Graceful shutdown in reverse order
        from app.core.redis import redis_manager
        if redis_manager:
            logger.info("Disconnecting Redis...")
            await redis_manager.close()
            logger.info("✓ Redis connections closed")
        
        if db_manager:
            logger.info("Disconnecting database...")
            await db_manager.close()
            logger.info("✓ Database connections closed")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("🛑 AIMA Configuration Management Service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AIMA Configuration Management Service",
    description="""
    Configuration Management Service for the AIMA (AI Media Analysis) system.
    
    This service provides centralized configuration management with:
    - Hierarchical configuration storage
    - Version control and change tracking
    - Real-time configuration updates
    - Secure handling of sensitive data
    - Caching for high performance
    
    ## Features
    
    - **Configuration CRUD**: Create, read, update, and delete configurations
    - **Category Management**: Organize configurations by categories
    - **Change Tracking**: Full audit trail of configuration changes
    - **Bulk Operations**: Update multiple configurations at once
    - **Caching**: Redis-based caching for improved performance
    - **Security**: JWT-based authentication and role-based access control
    - **Health Monitoring**: Comprehensive health checks and metrics
    
    ## Authentication
    
    All endpoints require JWT authentication. Admin privileges are required
    for most configuration management operations.
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error for {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP {exc.status_code} for {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception for {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__
        }
    )


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} for {request.method} {request.url} "
        f"in {process_time:.4f}s"
    )
    
    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Include routers
app.include_router(health.router)
app.include_router(config.router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with service information."""
    return {
        "service": "AIMA Configuration Management",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1"
    }


# API version endpoint
@app.get("/api/v1", tags=["API Info"])
async def api_info() -> Dict[str, Any]:
    """API version information."""
    return {
        "api_version": "v1",
        "service": "Configuration Management",
        "endpoints": {
            "configurations": "/api/v1/config",
            "health": "/health",
            "metrics": "/metrics"
        }
    }


if __name__ == "__main__":
    # Import time here to avoid circular imports
    import time
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )