#!/usr/bin/env python3
"""
Monitoring Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive system monitoring, health checks,
performance metrics, and alerting capabilities.
"""

import logging
import psutil
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, asdict
import json
import time
from collections import defaultdict, deque

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload

from ..core.database import MediaFile, ProcessingJob, AuditLog
from ..core.redis_client import CacheManager
from ..models.common import ProcessingStatus
from ..middleware.error_handling import MediaServiceException
from .notification_service import NotificationService


logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class Metric:
    """Metric data point."""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    tags: Optional[Dict[str, str]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.tags is None:
            self.tags = {}


@dataclass
class Alert:
    """Alert definition."""
    id: UUID
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    condition: str
    threshold: Union[int, float]
    current_value: Union[int, float]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemMetrics:
    """System-level metrics."""
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_io_bytes: Dict[str, int]
    disk_io_bytes: Dict[str, int]
    load_average: List[float]
    uptime_seconds: int
    process_count: int
    timestamp: datetime


@dataclass
class ApplicationMetrics:
    """Application-level metrics."""
    active_connections: int
    request_rate: float
    error_rate: float
    response_time_avg: float
    response_time_p95: float
    response_time_p99: float
    cache_hit_rate: float
    queue_size: int
    active_jobs: int
    failed_jobs: int
    timestamp: datetime


class MonitoringService:
    """Service for system monitoring and health checks."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        notification_service: Optional[NotificationService] = None
    ):
        self.cache = cache_manager
        self.notification_service = notification_service
        
        # Configuration
        self.health_check_interval = 30  # seconds
        self.metrics_collection_interval = 10  # seconds
        self.alert_check_interval = 60  # seconds
        self.metrics_retention_hours = 24
        
        # Health check registry
        self.health_checks: Dict[str, Callable] = {}
        
        # Metrics storage
        self.metrics_buffer: deque = deque(maxlen=1000)
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Alert management
        self.active_alerts: Dict[UUID, Alert] = {}
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.request_times: deque = deque(maxlen=1000)
        self.error_counts: defaultdict = defaultdict(int)
        
        # Background tasks
        self._monitoring_tasks: List[asyncio.Task] = []
        self._is_monitoring = False
        
        # Register default health checks
        self._register_default_health_checks()
        self._register_default_alert_rules()
    
    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        
        # Start monitoring tasks
        self._monitoring_tasks = [
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._metrics_collection_loop()),
            asyncio.create_task(self._alert_check_loop()),
            asyncio.create_task(self._cleanup_old_metrics_loop())
        ]
        
        logger.info("Monitoring service started")
    
    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        
        # Cancel all monitoring tasks
        for task in self._monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        
        self._monitoring_tasks.clear()
        logger.info("Monitoring service stopped")
    
    def register_health_check(self, name: str, check_func: Callable):
        """Register a custom health check."""
        self.health_checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    def register_alert_rule(
        self,
        name: str,
        condition: str,
        threshold: Union[int, float],
        severity: AlertSeverity = AlertSeverity.WARNING,
        description: str = ""
    ):
        """Register an alert rule."""
        self.alert_rules[name] = {
            "condition": condition,
            "threshold": threshold,
            "severity": severity,
            "description": description or f"Alert for {name}"
        }
        logger.info(f"Registered alert rule: {name}")
    
    async def run_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = await check_func()
                response_time = (time.time() - start_time) * 1000
                
                if isinstance(result, HealthCheck):
                    result.response_time_ms = response_time
                    results[name] = result
                else:
                    # Convert simple result to HealthCheck
                    status = HealthStatus.HEALTHY if result else HealthStatus.CRITICAL
                    message = "Check passed" if result else "Check failed"
                    
                    results[name] = HealthCheck(
                        name=name,
                        status=status,
                        message=message,
                        response_time_ms=response_time
                    )
                    
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check failed: {str(e)}"
                )
        
        # Cache results
        await self._cache_health_check_results(results)
        
        return results
    
    async def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_io_bytes = {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv
            }
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_io_bytes = {
                "bytes_read": disk_io.read_bytes if disk_io else 0,
                "bytes_write": disk_io.write_bytes if disk_io else 0
            }
            
            # Load average (Unix-like systems)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                load_avg = [0.0, 0.0, 0.0]  # Windows doesn't have load average
            
            # System uptime
            boot_time = psutil.boot_time()
            uptime = int(time.time() - boot_time)
            
            # Process count
            process_count = len(psutil.pids())
            
            metrics = SystemMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory_percent,
                disk_usage_percent=disk_percent,
                network_io_bytes=network_io_bytes,
                disk_io_bytes=disk_io_bytes,
                load_average=load_avg,
                uptime_seconds=uptime,
                process_count=process_count,
                timestamp=datetime.utcnow()
            )
            
            # Store metrics
            await self._store_metric(Metric(
                name="system.cpu_usage",
                value=cpu_percent,
                metric_type=MetricType.GAUGE
            ))
            
            await self._store_metric(Metric(
                name="system.memory_usage",
                value=memory_percent,
                metric_type=MetricType.GAUGE
            ))
            
            await self._store_metric(Metric(
                name="system.disk_usage",
                value=disk_percent,
                metric_type=MetricType.GAUGE
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            raise MediaServiceException(f"System metrics collection failed: {str(e)}")
    
    async def get_application_metrics(
        self,
        db: AsyncSession
    ) -> ApplicationMetrics:
        """Get current application metrics."""
        try:
            # Get Redis connection count
            redis_info = await self.cache.get_info()
            active_connections = redis_info.get("connected_clients", 0)
            
            # Calculate request rate (requests per second)
            current_time = time.time()
            recent_requests = [
                req_time for req_time in self.request_times
                if current_time - req_time <= 60  # Last minute
            ]
            request_rate = len(recent_requests) / 60.0
            
            # Calculate error rate
            total_errors = sum(self.error_counts.values())
            total_requests = len(self.request_times)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            # Calculate response times
            if self.request_times:
                response_times = list(self.request_times)
                response_times.sort()
                
                avg_time = sum(response_times) / len(response_times)
                p95_index = int(len(response_times) * 0.95)
                p99_index = int(len(response_times) * 0.99)
                
                response_time_avg = avg_time
                response_time_p95 = response_times[p95_index] if p95_index < len(response_times) else avg_time
                response_time_p99 = response_times[p99_index] if p99_index < len(response_times) else avg_time
            else:
                response_time_avg = response_time_p95 = response_time_p99 = 0.0
            
            # Get cache hit rate
            cache_stats = await self.cache.get_stats()
            cache_hit_rate = cache_stats.get("hit_rate", 0.0)
            
            # Get processing job metrics
            active_jobs_query = select(func.count(ProcessingJob.id)).where(
                ProcessingJob.status.in_([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING])
            )
            active_jobs_result = await db.execute(active_jobs_query)
            active_jobs = active_jobs_result.scalar() or 0
            
            failed_jobs_query = select(func.count(ProcessingJob.id)).where(
                and_(
                    ProcessingJob.status == ProcessingStatus.FAILED,
                    ProcessingJob.created_at >= datetime.utcnow() - timedelta(hours=1)
                )
            )
            failed_jobs_result = await db.execute(failed_jobs_query)
            failed_jobs = failed_jobs_result.scalar() or 0
            
            # Queue size (approximate)
            queue_size = active_jobs  # Simplified
            
            metrics = ApplicationMetrics(
                active_connections=active_connections,
                request_rate=request_rate,
                error_rate=error_rate,
                response_time_avg=response_time_avg,
                response_time_p95=response_time_p95,
                response_time_p99=response_time_p99,
                cache_hit_rate=cache_hit_rate,
                queue_size=queue_size,
                active_jobs=active_jobs,
                failed_jobs=failed_jobs,
                timestamp=datetime.utcnow()
            )
            
            # Store metrics
            await self._store_metric(Metric(
                name="app.request_rate",
                value=request_rate,
                metric_type=MetricType.GAUGE
            ))
            
            await self._store_metric(Metric(
                name="app.error_rate",
                value=error_rate,
                metric_type=MetricType.GAUGE
            ))
            
            await self._store_metric(Metric(
                name="app.response_time_avg",
                value=response_time_avg,
                metric_type=MetricType.GAUGE
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get application metrics: {e}")
            raise MediaServiceException(f"Application metrics collection failed: {str(e)}")
    
    async def record_request(self, response_time: float, status_code: int):
        """Record a request for metrics."""
        self.request_times.append(time.time())
        
        if status_code >= 400:
            self.error_counts[status_code] += 1
        
        await self._store_metric(Metric(
            name="http.request_duration",
            value=response_time,
            metric_type=MetricType.TIMER,
            tags={"status_code": str(status_code)}
        ))
    
    async def get_metrics_history(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical metrics data."""
        try:
            cache_key = f"metrics_history:{metric_name}"
            cached_data = await self.cache.get(cache_key)
            
            if cached_data:
                # Filter by time range
                filtered_data = [
                    point for point in cached_data
                    if start_time <= datetime.fromisoformat(point["timestamp"]) <= end_time
                ]
                return filtered_data
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get metrics history: {e}")
            return []
    
    async def create_alert(
        self,
        name: str,
        description: str,
        severity: AlertSeverity,
        condition: str,
        threshold: Union[int, float],
        current_value: Union[int, float],
        details: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            id=uuid4(),
            name=name,
            description=description,
            severity=severity,
            status=AlertStatus.ACTIVE,
            condition=condition,
            threshold=threshold,
            current_value=current_value,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            details=details
        )
        
        self.active_alerts[alert.id] = alert
        
        # Send notification
        if self.notification_service:
            await self._send_alert_notification(alert)
        
        # Cache alert
        await self._cache_alert(alert)
        
        logger.warning(f"Alert created: {name} - {description}")
        return alert
    
    async def resolve_alert(self, alert_id: UUID, resolved_by: Optional[UUID] = None) -> bool:
        """Resolve an active alert."""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        # Cache resolved alert
        await self._cache_resolved_alert(alert)
        
        logger.info(f"Alert resolved: {alert.name}")
        return True
    
    async def acknowledge_alert(
        self,
        alert_id: UUID,
        acknowledged_by: UUID
    ) -> bool:
        """Acknowledge an active alert."""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by
        alert.updated_at = datetime.utcnow()
        
        # Cache updated alert
        await self._cache_alert(alert)
        
        logger.info(f"Alert acknowledged: {alert.name} by {acknowledged_by}")
        return True
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    async def get_monitoring_dashboard_data(self, db: AsyncSession) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        try:
            # Get health checks
            health_checks = await self.run_health_checks()
            
            # Get system metrics
            system_metrics = await self.get_system_metrics()
            
            # Get application metrics
            app_metrics = await self.get_application_metrics(db)
            
            # Get active alerts
            active_alerts = await self.get_active_alerts()
            
            # Get recent metrics
            recent_metrics = await self._get_recent_metrics()
            
            # Calculate overall health status
            overall_status = self._calculate_overall_health(health_checks, active_alerts)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": overall_status.value,
                "health_checks": {
                    name: {
                        "status": check.status.value,
                        "message": check.message,
                        "response_time_ms": check.response_time_ms,
                        "timestamp": check.timestamp.isoformat()
                    }
                    for name, check in health_checks.items()
                },
                "system_metrics": {
                    "cpu_usage_percent": system_metrics.cpu_usage_percent,
                    "memory_usage_percent": system_metrics.memory_usage_percent,
                    "disk_usage_percent": system_metrics.disk_usage_percent,
                    "load_average": system_metrics.load_average,
                    "uptime_seconds": system_metrics.uptime_seconds,
                    "process_count": system_metrics.process_count
                },
                "application_metrics": {
                    "active_connections": app_metrics.active_connections,
                    "request_rate": app_metrics.request_rate,
                    "error_rate": app_metrics.error_rate,
                    "response_time_avg": app_metrics.response_time_avg,
                    "response_time_p95": app_metrics.response_time_p95,
                    "response_time_p99": app_metrics.response_time_p99,
                    "cache_hit_rate": app_metrics.cache_hit_rate,
                    "queue_size": app_metrics.queue_size,
                    "active_jobs": app_metrics.active_jobs,
                    "failed_jobs": app_metrics.failed_jobs
                },
                "active_alerts": [
                    {
                        "id": str(alert.id),
                        "name": alert.name,
                        "description": alert.description,
                        "severity": alert.severity.value,
                        "status": alert.status.value,
                        "created_at": alert.created_at.isoformat(),
                        "current_value": alert.current_value,
                        "threshold": alert.threshold
                    }
                    for alert in active_alerts
                ],
                "recent_metrics": recent_metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get monitoring dashboard data: {e}")
            raise MediaServiceException(f"Monitoring dashboard data collection failed: {str(e)}")
    
    # Background monitoring loops
    
    async def _health_check_loop(self):
        """Background loop for running health checks."""
        while self._is_monitoring:
            try:
                await self.run_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _metrics_collection_loop(self):
        """Background loop for collecting metrics."""
        while self._is_monitoring:
            try:
                # This would be called with a database session in practice
                # For now, we'll just collect system metrics
                await self.get_system_metrics()
                await asyncio.sleep(self.metrics_collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection loop error: {e}")
                await asyncio.sleep(self.metrics_collection_interval)
    
    async def _alert_check_loop(self):
        """Background loop for checking alert conditions."""
        while self._is_monitoring:
            try:
                await self._check_alert_conditions()
                await asyncio.sleep(self.alert_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Alert check loop error: {e}")
                await asyncio.sleep(self.alert_check_interval)
    
    async def _cleanup_old_metrics_loop(self):
        """Background loop for cleaning up old metrics."""
        while self._is_monitoring:
            try:
                await self._cleanup_old_metrics()
                await asyncio.sleep(3600)  # Run every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics cleanup loop error: {e}")
                await asyncio.sleep(3600)
    
    # Helper methods
    
    def _register_default_health_checks(self):
        """Register default health checks."""
        self.register_health_check("database", self._check_database_health)
        self.register_health_check("redis", self._check_redis_health)
        self.register_health_check("disk_space", self._check_disk_space_health)
        self.register_health_check("memory", self._check_memory_health)
        self.register_health_check("cpu", self._check_cpu_health)
    
    def _register_default_alert_rules(self):
        """Register default alert rules."""
        self.register_alert_rule(
            "high_cpu_usage",
            "system.cpu_usage > threshold",
            80.0,
            AlertSeverity.WARNING,
            "CPU usage is above 80%"
        )
        
        self.register_alert_rule(
            "high_memory_usage",
            "system.memory_usage > threshold",
            85.0,
            AlertSeverity.WARNING,
            "Memory usage is above 85%"
        )
        
        self.register_alert_rule(
            "high_disk_usage",
            "system.disk_usage > threshold",
            90.0,
            AlertSeverity.CRITICAL,
            "Disk usage is above 90%"
        )
        
        self.register_alert_rule(
            "high_error_rate",
            "app.error_rate > threshold",
            5.0,
            AlertSeverity.WARNING,
            "Error rate is above 5%"
        )
    
    async def _check_database_health(self) -> HealthCheck:
        """Check database connectivity."""
        try:
            # This would need a database session in practice
            # For now, return a mock healthy status
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection is healthy"
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}"
            )
    
    async def _check_redis_health(self) -> HealthCheck:
        """Check Redis connectivity."""
        try:
            await self.cache.ping()
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection is healthy"
            )
        except Exception as e:
            return HealthCheck(
                name="redis",
                status=HealthStatus.CRITICAL,
                message=f"Redis connection failed: {str(e)}"
            )
    
    async def _check_disk_space_health(self) -> HealthCheck:
        """Check disk space usage."""
        try:
            disk = psutil.disk_usage('/')
            usage_percent = (disk.used / disk.total) * 100
            
            if usage_percent > 95:
                status = HealthStatus.CRITICAL
                message = f"Disk usage critical: {usage_percent:.1f}%"
            elif usage_percent > 85:
                status = HealthStatus.WARNING
                message = f"Disk usage high: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {usage_percent:.1f}%"
            
            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                details={"usage_percent": usage_percent}
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check disk space: {str(e)}"
            )
    
    async def _check_memory_health(self) -> HealthCheck:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            if usage_percent > 95:
                status = HealthStatus.CRITICAL
                message = f"Memory usage critical: {usage_percent:.1f}%"
            elif usage_percent > 85:
                status = HealthStatus.WARNING
                message = f"Memory usage high: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {usage_percent:.1f}%"
            
            return HealthCheck(
                name="memory",
                status=status,
                message=message,
                details={"usage_percent": usage_percent}
            )
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check memory usage: {str(e)}"
            )
    
    async def _check_cpu_health(self) -> HealthCheck:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > 95:
                status = HealthStatus.CRITICAL
                message = f"CPU usage critical: {cpu_percent:.1f}%"
            elif cpu_percent > 80:
                status = HealthStatus.WARNING
                message = f"CPU usage high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"
            
            return HealthCheck(
                name="cpu",
                status=status,
                message=message,
                details={"usage_percent": cpu_percent}
            )
        except Exception as e:
            return HealthCheck(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check CPU usage: {str(e)}"
            )
    
    async def _store_metric(self, metric: Metric):
        """Store a metric data point."""
        try:
            # Add to buffer
            self.metrics_buffer.append({
                "name": metric.name,
                "value": metric.value,
                "type": metric.metric_type.value,
                "tags": metric.tags,
                "timestamp": metric.timestamp.isoformat()
            })
            
            # Add to history
            self.metrics_history[metric.name].append({
                "value": metric.value,
                "timestamp": metric.timestamp.isoformat()
            })
            
            # Cache recent metrics
            cache_key = f"metrics:{metric.name}"
            await self.cache.set(cache_key, metric.value, ttl=300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Failed to store metric {metric.name}: {e}")
    
    async def _cache_health_check_results(self, results: Dict[str, HealthCheck]):
        """Cache health check results."""
        try:
            cache_data = {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "response_time_ms": check.response_time_ms
                }
                for name, check in results.items()
            }
            
            await self.cache.set("health_checks", cache_data, ttl=300)
            
        except Exception as e:
            logger.error(f"Failed to cache health check results: {e}")
    
    async def _cache_alert(self, alert: Alert):
        """Cache an alert."""
        try:
            cache_key = f"alert:{alert.id}"
            alert_data = {
                "id": str(alert.id),
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat(),
                "updated_at": alert.updated_at.isoformat()
            }
            
            await self.cache.set(cache_key, alert_data, ttl=3600)
            
        except Exception as e:
            logger.error(f"Failed to cache alert: {e}")
    
    async def _cache_resolved_alert(self, alert: Alert):
        """Cache a resolved alert."""
        try:
            cache_key = f"resolved_alert:{alert.id}"
            alert_data = {
                "id": str(alert.id),
                "name": alert.name,
                "description": alert.description,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat(),
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None
            }
            
            await self.cache.set(cache_key, alert_data, ttl=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to cache resolved alert: {e}")
    
    async def _send_alert_notification(self, alert: Alert):
        """Send notification for an alert."""
        try:
            if not self.notification_service:
                return
            
            # Send email notification
            await self.notification_service.send_email_notification(
                recipient_email="admin@example.com",  # This should be configurable
                template_name="alert_notification",
                template_data={
                    "alert_name": alert.name,
                    "alert_description": alert.description,
                    "alert_severity": alert.severity.value,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "created_at": alert.created_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
    
    async def _check_alert_conditions(self):
        """Check all alert rule conditions."""
        try:
            for rule_name, rule_config in self.alert_rules.items():
                await self._evaluate_alert_rule(rule_name, rule_config)
                
        except Exception as e:
            logger.error(f"Failed to check alert conditions: {e}")
    
    async def _evaluate_alert_rule(self, rule_name: str, rule_config: Dict[str, Any]):
        """Evaluate a specific alert rule."""
        try:
            condition = rule_config["condition"]
            threshold = rule_config["threshold"]
            severity = rule_config["severity"]
            description = rule_config["description"]
            
            # Get current metric value based on condition
            if "system.cpu_usage" in condition:
                current_value = await self.cache.get("metrics:system.cpu_usage") or 0
            elif "system.memory_usage" in condition:
                current_value = await self.cache.get("metrics:system.memory_usage") or 0
            elif "system.disk_usage" in condition:
                current_value = await self.cache.get("metrics:system.disk_usage") or 0
            elif "app.error_rate" in condition:
                current_value = await self.cache.get("metrics:app.error_rate") or 0
            else:
                return  # Unknown condition
            
            # Check if condition is met
            condition_met = False
            if "> threshold" in condition:
                condition_met = current_value > threshold
            elif "< threshold" in condition:
                condition_met = current_value < threshold
            elif "== threshold" in condition:
                condition_met = current_value == threshold
            
            # Check if alert already exists
            existing_alert = None
            for alert in self.active_alerts.values():
                if alert.name == rule_name:
                    existing_alert = alert
                    break
            
            if condition_met and not existing_alert:
                # Create new alert
                await self.create_alert(
                    name=rule_name,
                    description=description,
                    severity=severity,
                    condition=condition,
                    threshold=threshold,
                    current_value=current_value
                )
            elif not condition_met and existing_alert:
                # Resolve existing alert
                await self.resolve_alert(existing_alert.id)
            elif existing_alert:
                # Update existing alert with current value
                existing_alert.current_value = current_value
                existing_alert.updated_at = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Failed to evaluate alert rule {rule_name}: {e}")
    
    async def _get_recent_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get recent metrics for dashboard."""
        try:
            recent_metrics = {}
            
            for metric_name, history in self.metrics_history.items():
                # Get last 20 data points
                recent_metrics[metric_name] = list(history)[-20:]
            
            return recent_metrics
            
        except Exception as e:
            logger.error(f"Failed to get recent metrics: {e}")
            return {}
    
    def _calculate_overall_health(
        self,
        health_checks: Dict[str, HealthCheck],
        active_alerts: List[Alert]
    ) -> HealthStatus:
        """Calculate overall system health status."""
        # Check for critical alerts
        critical_alerts = [
            alert for alert in active_alerts
            if alert.severity == AlertSeverity.CRITICAL
        ]
        
        if critical_alerts:
            return HealthStatus.CRITICAL
        
        # Check for critical health checks
        critical_checks = [
            check for check in health_checks.values()
            if check.status == HealthStatus.CRITICAL
        ]
        
        if critical_checks:
            return HealthStatus.CRITICAL
        
        # Check for warnings
        warning_alerts = [
            alert for alert in active_alerts
            if alert.severity == AlertSeverity.WARNING
        ]
        
        warning_checks = [
            check for check in health_checks.values()
            if check.status == HealthStatus.WARNING
        ]
        
        if warning_alerts or warning_checks:
            return HealthStatus.WARNING
        
        return HealthStatus.HEALTHY
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics data."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.metrics_retention_hours)
            
            # Clean up metrics buffer
            self.metrics_buffer = deque([
                metric for metric in self.metrics_buffer
                if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
            ], maxlen=1000)
            
            # Clean up metrics history
            for metric_name in self.metrics_history:
                self.metrics_history[metric_name] = deque([
                    point for point in self.metrics_history[metric_name]
                    if datetime.fromisoformat(point["timestamp"]) > cutoff_time
                ], maxlen=100)
            
            logger.debug("Cleaned up old metrics data")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")