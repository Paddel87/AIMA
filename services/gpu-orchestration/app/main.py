#!/usr/bin/env python3
"""
Main FastAPI application for the AIMA GPU Orchestration Service.

This service provides GPU resource orchestration, job management, and
integration with multiple GPU providers (RunPod, Vast.ai, etc.).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .core.config import get_settings
from .core.database import get_db, AsyncSession
from .services.gpu_orchestrator import GPUOrchestrator
from .services.job_manager import JobManager
from .api import jobs, instances, providers, templates, monitoring


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service instances
gpu_orchestrator: GPUOrchestrator = None
job_manager: JobManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global gpu_orchestrator, job_manager
    
    # Startup
    logger.info("Starting GPU Orchestration Service")
    
    try:
        # Initialize services
        gpu_orchestrator = GPUOrchestrator()
        job_manager = JobManager()
        
        # Start background services
        await job_manager.start()
        
        logger.info("GPU Orchestration Service started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down GPU Orchestration Service")
        
        try:
            if job_manager:
                await job_manager.stop()
            
            logger.info("GPU Orchestration Service shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="AIMA GPU Orchestration Service",
    description="GPU resource orchestration and job management for AIMA infrastructure",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get services
def get_gpu_orchestrator() -> GPUOrchestrator:
    """Get GPU orchestrator instance."""
    if gpu_orchestrator is None:
        raise HTTPException(status_code=503, detail="GPU orchestrator not initialized")
    return gpu_orchestrator


def get_job_manager() -> JobManager:
    """Get job manager instance."""
    if job_manager is None:
        raise HTTPException(status_code=503, detail="Job manager not initialized")
    return job_manager


# Include API routers
app.include_router(
    jobs.router,
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(get_gpu_orchestrator), Depends(get_job_manager)]
)

app.include_router(
    instances.router,
    prefix="/api/v1/instances",
    tags=["instances"],
    dependencies=[Depends(get_gpu_orchestrator)]
)

app.include_router(
    providers.router,
    prefix="/api/v1/providers",
    tags=["providers"],
    dependencies=[Depends(get_gpu_orchestrator)]
)

app.include_router(
    templates.router,
    prefix="/api/v1/templates",
    tags=["templates"],
    dependencies=[Depends(get_job_manager)]
)

app.include_router(
    monitoring.router,
    prefix="/api/v1/monitoring",
    tags=["monitoring"]
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        settings = get_settings()
        
        # Check service status
        service_status = {
            "status": "healthy",
            "service": "gpu-orchestration",
            "version": "1.0.0",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Check GPU orchestrator
        if gpu_orchestrator:
            provider_status = await gpu_orchestrator.get_provider_status()
            service_status["providers"] = provider_status
        
        return service_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Metrics endpoint for Prometheus
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    try:
        metrics_data = generate_latest()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail="Error generating metrics")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "AIMA GPU Orchestration Service",
        "version": "1.0.0",
        "description": "GPU resource orchestration and job management",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )