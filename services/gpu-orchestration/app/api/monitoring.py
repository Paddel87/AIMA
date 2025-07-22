#!/usr/bin/env python3
"""
Monitoring API endpoints for the AIMA GPU Orchestration Service.

This module provides REST API endpoints for monitoring, metrics, and health checks.
"""

import asyncio
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from ..core.database import get_db
from ..core.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for API
class SystemMetricsResponse(BaseModel):
    """Response model for system metrics."""
    timestamp: str
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_total_gb: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_total_gb: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    uptime_seconds: float


class ServiceMetricsResponse(BaseModel):
    """Response model for service metrics."""
    timestamp: str
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_instances: int
    running_instances: int
    total_cost_usd: float
    average_job_duration_minutes: float
    average_queue_wait_time_minutes: float
    job_success_rate_percent: float
    provider_health_status: Dict[str, str]


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics."""
    timestamp: str
    api_response_time_ms: float
    database_query_time_ms: float
    provider_api_latency_ms: Dict[str, float]
    job_throughput_per_hour: float
    instance_utilization_percent: float
    cost_efficiency_score: float
    error_rate_percent: float


class AlertResponse(BaseModel):
    """Response model for alerts."""
    id: str
    severity: str  # "critical", "warning", "info"
    title: str
    description: str
    timestamp: str
    resolved: bool
    component: str
    metrics: Dict[str, Any]


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, Dict[str, Any]]
    dependencies: Dict[str, Dict[str, Any]]


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """Comprehensive health check for the service."""
    try:
        start_time = datetime.utcnow()
        settings = get_settings()
        
        # Check database connectivity
        db_healthy = True
        db_latency = 0.0
        try:
            db_start = datetime.utcnow()
            await db.execute("SELECT 1")
            db_latency = (datetime.utcnow() - db_start).total_seconds() * 1000
        except Exception as e:
            db_healthy = False
            logger.error(f"Database health check failed: {e}")
        
        # Check Redis connectivity (if configured)
        redis_healthy = True
        redis_latency = 0.0
        # TODO: Implement Redis health check
        
        # Check RabbitMQ connectivity (if configured)
        rabbitmq_healthy = True
        rabbitmq_latency = 0.0
        # TODO: Implement RabbitMQ health check
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Determine overall status
        if db_healthy and redis_healthy and rabbitmq_healthy:
            if cpu_percent < 80 and memory.percent < 80 and disk.percent < 80:
                status = "healthy"
            else:
                status = "degraded"
        else:
            status = "unhealthy"
        
        return HealthCheckResponse(
            status=status,
            timestamp=start_time.isoformat(),
            version="1.0.0",
            uptime_seconds=psutil.boot_time(),
            components={
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "latency_ms": db_latency,
                    "url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "hidden"
                },
                "redis": {
                    "status": "healthy" if redis_healthy else "unhealthy",
                    "latency_ms": redis_latency,
                    "url": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}"
                },
                "rabbitmq": {
                    "status": "healthy" if rabbitmq_healthy else "unhealthy",
                    "latency_ms": rabbitmq_latency,
                    "url": f"{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}"
                }
            },
            dependencies={
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


@router.get("/metrics/system", response_model=SystemMetricsResponse)
async def get_system_metrics():
    """Get current system metrics."""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        disk_percent = (disk.used / disk.total) * 100
        
        # Network metrics
        network = psutil.net_io_counters()
        
        # Uptime
        uptime = datetime.utcnow().timestamp() - psutil.boot_time()
        
        return SystemMetricsResponse(
            timestamp=datetime.utcnow().isoformat(),
            cpu_usage_percent=cpu_percent,
            memory_usage_percent=memory.percent,
            memory_total_gb=round(memory_total_gb, 2),
            memory_available_gb=round(memory_available_gb, 2),
            disk_usage_percent=round(disk_percent, 2),
            disk_total_gb=round(disk_total_gb, 2),
            disk_free_gb=round(disk_free_gb, 2),
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            uptime_seconds=uptime
        )
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/metrics/service", response_model=ServiceMetricsResponse)
async def get_service_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get service-specific metrics."""
    try:
        # TODO: Implement actual database queries for metrics
        # For now, return sample data
        
        return ServiceMetricsResponse(
            timestamp=datetime.utcnow().isoformat(),
            total_jobs=0,
            queued_jobs=0,
            running_jobs=0,
            completed_jobs=0,
            failed_jobs=0,
            total_instances=0,
            running_instances=0,
            total_cost_usd=0.0,
            average_job_duration_minutes=0.0,
            average_queue_wait_time_minutes=0.0,
            job_success_rate_percent=100.0,
            provider_health_status={}
        )
        
    except Exception as e:
        logger.error(f"Error getting service metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service metrics")


@router.get("/metrics/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get performance metrics."""
    try:
        # TODO: Implement actual performance metrics collection
        # For now, return sample data
        
        return PerformanceMetricsResponse(
            timestamp=datetime.utcnow().isoformat(),
            api_response_time_ms=50.0,
            database_query_time_ms=10.0,
            provider_api_latency_ms={
                "runpod": 150.0,
                "vast": 200.0
            },
            job_throughput_per_hour=0.0,
            instance_utilization_percent=0.0,
            cost_efficiency_score=85.0,
            error_rate_percent=0.0
        )
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of alerts")
):
    """Get current alerts and warnings."""
    try:
        # TODO: Implement actual alert system
        # For now, return sample alerts
        
        sample_alerts = [
            AlertResponse(
                id="alert-001",
                severity="warning",
                title="High CPU Usage",
                description="CPU usage has been above 80% for the last 10 minutes",
                timestamp=(datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                resolved=False,
                component="system",
                metrics={"cpu_percent": 85.2}
            ),
            AlertResponse(
                id="alert-002",
                severity="info",
                title="Provider API Latency",
                description="RunPod API latency is higher than usual",
                timestamp=(datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                resolved=True,
                component="provider",
                metrics={"latency_ms": 250.0}
            )
        ]
        
        # Apply filters
        filtered_alerts = sample_alerts
        
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a.severity == severity]
        
        if resolved is not None:
            filtered_alerts = [a for a in filtered_alerts if a.resolved == resolved]
        
        # Apply limit
        filtered_alerts = filtered_alerts[:limit]
        
        return {"alerts": filtered_alerts}
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alerts")


@router.get("/prometheus")
async def prometheus_metrics():
    """Get Prometheus-formatted metrics."""
    try:
        # TODO: Implement custom Prometheus metrics
        # For now, return basic metrics
        
        registry = CollectorRegistry()
        # Add custom metrics here
        
        metrics_data = generate_latest(registry)
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
        
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@router.get("/dashboard")
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive dashboard data."""
    try:
        # Collect all metrics for dashboard
        system_metrics = await get_system_metrics()
        service_metrics = await get_service_metrics(db)
        performance_metrics = await get_performance_metrics(db)
        health_status = await health_check(db)
        alerts = await get_alerts(resolved=False, limit=10)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health": health_status,
            "system": system_metrics,
            "service": service_metrics,
            "performance": performance_metrics,
            "alerts": alerts["alerts"]
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")


@router.get("/logs")
async def get_recent_logs(
    level: Optional[str] = Query("INFO", description="Log level filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    component: Optional[str] = Query(None, description="Filter by component")
):
    """Get recent log entries."""
    try:
        # TODO: Implement log retrieval from logging system
        # For now, return sample log data
        
        sample_logs = [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
                "level": "INFO",
                "component": "gpu_orchestrator",
                "message": "Job submitted successfully",
                "job_id": "job-123",
                "user_id": "user123"
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=2)).isoformat(),
                "level": "WARNING",
                "component": "runpod_provider",
                "message": "API rate limit approaching",
                "requests_remaining": 10
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                "level": "INFO",
                "component": "job_manager",
                "message": "Job queue processed",
                "jobs_processed": 5
            }
        ]
        
        # Apply filters
        filtered_logs = sample_logs
        
        if level and level != "ALL":
            filtered_logs = [log for log in filtered_logs if log["level"] == level]
        
        if component:
            filtered_logs = [log for log in filtered_logs if log["component"] == component]
        
        # Apply limit
        filtered_logs = filtered_logs[:limit]
        
        return {"logs": filtered_logs}
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get logs")


@router.get("/status")
async def get_service_status():
    """Get overall service status summary."""
    try:
        settings = get_settings()
        
        return {
            "service": "gpu-orchestration",
            "version": "1.0.0",
            "status": "running",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": "production" if settings.PRODUCTION else "development",
            "debug_mode": settings.DEBUG,
            "api_host": settings.API_HOST,
            "api_port": settings.API_PORT,
            "configured_providers": settings.configured_gpu_providers,
            "features": {
                "job_management": True,
                "gpu_orchestration": True,
                "cost_optimization": settings.COST_OPTIMIZATION_ENABLED,
                "monitoring": settings.METRICS_ENABLED,
                "auto_scaling": True
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service status")