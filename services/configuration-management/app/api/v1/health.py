#!/usr/bin/env python3
"""
Health check endpoints for the AIMA Configuration Management Service.

This module provides health check and monitoring endpoints to verify
the service status and dependencies.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_db, DatabaseManager
from app.core.redis import get_cache, ConfigurationCache
from app.models.schemas import HealthCheckResponse, MetricsResponse
from app.services.config_service import ConfigurationService
from app.api.dependencies import get_optional_user, require_admin

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Health & Monitoring"])

# Service start time for uptime calculation
START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check the health status of the configuration management service."
)
async def health_check(
    db: Session = Depends(get_db),
    cache: ConfigurationCache = Depends(get_cache),
    current_user: Dict[str, Any] = Depends(get_optional_user)
) -> HealthCheckResponse:
    """Perform a comprehensive health check of the service."""
    try:
        health_status = "healthy"
        checks = {}
        
        # Check database connectivity
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = {
                "status": "healthy",
                "message": "Database connection successful"
            }
        except Exception as e:
            checks["database"] = {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
            health_status = "unhealthy"
        
        # Check Redis connectivity
        try:
            if cache.redis_manager.is_connected():
                # Test Redis with a simple operation
                test_key = "health_check_test"
                await cache.redis_manager.redis.set(test_key, "test", ex=10)
                test_value = await cache.redis_manager.redis.get(test_key)
                await cache.redis_manager.redis.delete(test_key)
                
                if test_value == "test":
                    checks["redis"] = {
                        "status": "healthy",
                        "message": "Redis connection successful"
                    }
                else:
                    checks["redis"] = {
                        "status": "degraded",
                        "message": "Redis connection unstable"
                    }
                    if health_status == "healthy":
                        health_status = "degraded"
            else:
                checks["redis"] = {
                    "status": "unhealthy",
                    "message": "Redis not connected"
                }
                if health_status == "healthy":
                    health_status = "degraded"
        except Exception as e:
            checks["redis"] = {
                "status": "unhealthy",
                "message": f"Redis check failed: {str(e)}"
            }
            if health_status == "healthy":
                health_status = "degraded"
        
        # Check configuration service
        try:
            config_service = ConfigurationService(cache=cache)
            # Try to get metrics as a service health check
            metrics = await config_service.get_metrics(db)
            checks["configuration_service"] = {
                "status": "healthy",
                "message": "Configuration service operational",
                "details": {
                    "total_configurations": metrics.get("total_configurations", 0)
                }
            }
        except Exception as e:
            checks["configuration_service"] = {
                "status": "unhealthy",
                "message": f"Configuration service check failed: {str(e)}"
            }
            health_status = "unhealthy"
        
        # Calculate uptime
        uptime_seconds = int(time.time() - START_TIME)
        
        return HealthCheckResponse(
            status=health_status,
            timestamp=datetime.now(timezone.utc),
            version=settings.APP_VERSION,
            uptime_seconds=uptime_seconds,
            checks=checks
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc),
            version=settings.APP_VERSION,
            uptime_seconds=int(time.time() - START_TIME),
            checks={
                "general": {
                    "status": "unhealthy",
                    "message": f"Health check failed: {str(e)}"
                }
            }
        )


@router.get(
    "/health/ready",
    summary="Readiness check",
    description="Check if the service is ready to accept requests."
)
async def readiness_check(
    db: Session = Depends(get_db),
    cache: ConfigurationCache = Depends(get_cache)
) -> Dict[str, Any]:
    """Check if the service is ready to handle requests."""
    try:
        # Check critical dependencies
        ready = True
        checks = {}
        
        # Database must be available
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ready"
        except Exception as e:
            checks["database"] = f"not ready: {str(e)}"
            ready = False
        
        # Redis is optional but preferred
        try:
            if cache.redis_manager.is_connected():
                checks["redis"] = "ready"
            else:
                checks["redis"] = "not connected (degraded mode)"
        except Exception as e:
            checks["redis"] = f"error: {str(e)}"
        
        if ready:
            return {
                "status": "ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": checks
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "not ready",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "checks": checks
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
        )


@router.get(
    "/health/live",
    summary="Liveness check",
    description="Check if the service is alive and responding."
)
async def liveness_check() -> Dict[str, Any]:
    """Simple liveness check - just verify the service is responding."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - START_TIME)
    }


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Service metrics",
    description="Get detailed service metrics and statistics."
)
async def get_service_metrics(
    db: Session = Depends(get_db),
    cache: ConfigurationCache = Depends(get_cache),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> MetricsResponse:
    """Get comprehensive service metrics (admin only)."""
    try:
        config_service = ConfigurationService(cache=cache)
        
        # Get configuration metrics
        config_metrics = await config_service.get_metrics(db)
        
        # Get system metrics
        uptime_seconds = int(time.time() - START_TIME)
        
        # Get database metrics
        db_metrics = {}
        try:
            # Get database connection info
            result = db.execute(text(
                "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active'"
            ))
            db_metrics["active_connections"] = result.scalar()
        except Exception as e:
            logger.warning(f"Could not get database metrics: {e}")
            db_metrics["active_connections"] = "unknown"
        
        # Get Redis metrics
        redis_metrics = {}
        try:
            if cache.redis_manager.is_connected():
                info = await cache.redis_manager.redis.info()
                redis_metrics = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory", 0),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
        except Exception as e:
            logger.warning(f"Could not get Redis metrics: {e}")
            redis_metrics["status"] = "unavailable"
        
        return MetricsResponse(
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=uptime_seconds,
            total_configurations=config_metrics.get("total_configurations", 0),
            configurations_by_category=config_metrics.get("configurations_by_category", {}),
            sensitive_configurations=config_metrics.get("sensitive_configurations", 0),
            readonly_configurations=config_metrics.get("readonly_configurations", 0),
            recent_changes=config_metrics.get("recent_changes", 0),
            database_metrics=db_metrics,
            redis_metrics=redis_metrics
        )
        
    except Exception as e:
        logger.error(f"Error getting service metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve service metrics"
        )


@router.get(
    "/info",
    summary="Service information",
    description="Get basic service information."
)
async def get_service_info() -> Dict[str, Any]:
    """Get basic service information."""
    return {
        "service": "AIMA Configuration Management",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "started_at": datetime.fromtimestamp(START_TIME, tz=timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - START_TIME),
        "api_docs": "/docs",
        "health_check": "/health"
    }