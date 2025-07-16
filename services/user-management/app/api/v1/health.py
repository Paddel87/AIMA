#!/usr/bin/env python3
"""
Health check API routes for the AIMA User Management Service.

This module provides health check endpoints for monitoring
service status and dependencies.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db, health_check as db_health_check
from app.core.redis import health_check as redis_health_check
from app.core.messaging import health_check as messaging_health_check
from app.core.config import settings
from app.models.schemas import (
    HealthCheckResponse,
    DetailedHealthCheckResponse,
    ServiceStatus,
    ComponentHealth
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "/",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Basic health check endpoint"
)
async def health_check():
    """Basic health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        service="user-management",
        version=settings.APP_VERSION
    )


@router.get(
    "/ready",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Check if service is ready to accept requests"
)
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check - verifies service can handle requests."""
    try:
        # Check database connectivity
        start_time = time.time()
        db_healthy = await db_health_check()
        db_response_time = (time.time() - start_time) * 1000
        
        if not db_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "unhealthy",
                    "message": "Database connection failed",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Check Redis connectivity
        start_time = time.time()
        redis_healthy = await redis_health_check()
        redis_response_time = (time.time() - start_time) * 1000
        
        if not redis_healthy:
            logger.warning("Redis health check failed during readiness check")
            # Redis failure is not critical for basic readiness
        
        return HealthCheckResponse(
            status="ready",
            timestamp=datetime.now(timezone.utc),
            service="user-management",
            version=settings.APP_VERSION,
            details={
                "database_response_time_ms": round(db_response_time, 2),
                "redis_response_time_ms": round(redis_response_time, 2),
                "redis_healthy": redis_healthy
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "message": "Service readiness check failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get(
    "/live",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Check if service is alive"
)
async def liveness_check():
    """Liveness check - verifies service is running."""
    return HealthCheckResponse(
        status="alive",
        timestamp=datetime.now(timezone.utc),
        service="user-management",
        version=settings.APP_VERSION,
        details={
            "uptime_seconds": time.time() - getattr(liveness_check, 'start_time', time.time()),
            "environment": settings.ENVIRONMENT
        }
    )


# Set start time for uptime calculation
liveness_check.start_time = time.time()


@router.get(
    "/detailed",
    response_model=DetailedHealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Comprehensive health check of all service components"
)
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check of all service components."""
    components = {}
    overall_status = ServiceStatus.HEALTHY
    
    # Check database
    try:
        start_time = time.time()
        db_healthy = await db_health_check()
        db_response_time = (time.time() - start_time) * 1000
        
        components["database"] = ComponentHealth(
            status=ServiceStatus.HEALTHY if db_healthy else ServiceStatus.UNHEALTHY,
            response_time_ms=round(db_response_time, 2),
            details={
                "type": "postgresql",
                "host": settings.DATABASE_HOST,
                "port": settings.DATABASE_PORT,
                "database": settings.DATABASE_NAME
            }
        )
        
        if not db_healthy:
            overall_status = ServiceStatus.UNHEALTHY
            
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        components["database"] = ComponentHealth(
            status=ServiceStatus.UNHEALTHY,
            error=str(e),
            details={"type": "postgresql"}
        )
        overall_status = ServiceStatus.UNHEALTHY
    
    # Check Redis
    try:
        start_time = time.time()
        redis_healthy = await redis_health_check()
        redis_response_time = (time.time() - start_time) * 1000
        
        components["redis"] = ComponentHealth(
            status=ServiceStatus.HEALTHY if redis_healthy else ServiceStatus.DEGRADED,
            response_time_ms=round(redis_response_time, 2),
            details={
                "type": "redis",
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "database": settings.REDIS_DB
            }
        )
        
        if not redis_healthy and overall_status == ServiceStatus.HEALTHY:
            overall_status = ServiceStatus.DEGRADED
            
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        components["redis"] = ComponentHealth(
            status=ServiceStatus.DEGRADED,
            error=str(e),
            details={"type": "redis"}
        )
        if overall_status == ServiceStatus.HEALTHY:
            overall_status = ServiceStatus.DEGRADED
    
    # Check messaging (RabbitMQ)
    try:
        start_time = time.time()
        messaging_healthy = await messaging_health_check()
        messaging_response_time = (time.time() - start_time) * 1000
        
        components["messaging"] = ComponentHealth(
            status=ServiceStatus.HEALTHY if messaging_healthy else ServiceStatus.DEGRADED,
            response_time_ms=round(messaging_response_time, 2),
            details={
                "type": "rabbitmq",
                "host": settings.RABBITMQ_HOST,
                "port": settings.RABBITMQ_PORT,
                "vhost": settings.RABBITMQ_VHOST
            }
        )
        
        if not messaging_healthy and overall_status == ServiceStatus.HEALTHY:
            overall_status = ServiceStatus.DEGRADED
            
    except Exception as e:
        logger.error("Messaging health check failed", error=str(e))
        components["messaging"] = ComponentHealth(
            status=ServiceStatus.DEGRADED,
            error=str(e),
            details={"type": "rabbitmq"}
        )
        if overall_status == ServiceStatus.HEALTHY:
            overall_status = ServiceStatus.DEGRADED
    
    # Check external services (placeholder)
    components["external_services"] = ComponentHealth(
        status=ServiceStatus.HEALTHY,
        details={
            "media_service": "not_checked",
            "job_service": "not_checked",
            "gpu_service": "not_checked"
        }
    )
    
    # Calculate overall response time
    total_response_time = sum(
        comp.response_time_ms or 0 
        for comp in components.values()
    )
    
    response = DetailedHealthCheckResponse(
        status=overall_status.value,
        timestamp=datetime.now(timezone.utc),
        service="user-management",
        version=settings.APP_VERSION,
        components=components,
        details={
            "environment": settings.ENVIRONMENT,
            "debug_mode": settings.DEBUG,
            "total_response_time_ms": round(total_response_time, 2),
            "uptime_seconds": time.time() - getattr(liveness_check, 'start_time', time.time()),
            "memory_usage": "not_implemented",
            "cpu_usage": "not_implemented"
        }
    )
    
    # Return appropriate HTTP status based on overall health
    if overall_status == ServiceStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.dict()
        )
    elif overall_status == ServiceStatus.DEGRADED:
        raise HTTPException(
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            detail=response.dict()
        )
    
    return response


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Health metrics",
    description="Get basic health metrics for monitoring"
)
async def health_metrics(db: Session = Depends(get_db)):
    """Get basic health metrics."""
    try:
        # Database metrics
        db_start = time.time()
        db_healthy = await db_health_check()
        db_response_time = (time.time() - db_start) * 1000
        
        # Redis metrics
        redis_start = time.time()
        redis_healthy = await redis_health_check()
        redis_response_time = (time.time() - redis_start) * 1000
        
        # Messaging metrics
        messaging_start = time.time()
        messaging_healthy = await messaging_health_check()
        messaging_response_time = (time.time() - messaging_start) * 1000
        
        metrics = {
            "service_status": 1 if db_healthy else 0,
            "database_status": 1 if db_healthy else 0,
            "database_response_time_ms": round(db_response_time, 2),
            "redis_status": 1 if redis_healthy else 0,
            "redis_response_time_ms": round(redis_response_time, 2),
            "messaging_status": 1 if messaging_healthy else 0,
            "messaging_response_time_ms": round(messaging_response_time, 2),
            "uptime_seconds": time.time() - getattr(liveness_check, 'start_time', time.time()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error("Health metrics collection failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "METRICS_ERROR",
                "message": "Failed to collect health metrics"
            }
        )