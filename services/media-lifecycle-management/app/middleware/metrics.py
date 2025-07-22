#!/usr/bin/env python3
"""
Metrics middleware for the AIMA Media Lifecycle Management Service.

This middleware collects performance metrics, request statistics, and
custom business metrics for monitoring and observability.
"""

import time
from typing import Callable, Dict, Any
from collections import defaultdict, Counter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog
from prometheus_client import Counter as PrometheusCounter, Histogram, Gauge, CollectorRegistry

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Centralized metrics collection."""
    
    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry()
        self._setup_prometheus_metrics()
        
        # In-memory metrics for quick access
        self.request_counts = defaultdict(int)
        self.response_times = []
        self.error_counts = defaultdict(int)
        self.active_requests = 0
        
    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics."""
        # Request metrics
        self.http_requests_total = PrometheusCounter(
            'http_requests_total',
            'Total number of HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        self.http_requests_in_progress = Gauge(
            'http_requests_in_progress',
            'Number of HTTP requests currently being processed',
            registry=self.registry
        )
        
        # Media-specific metrics
        self.media_files_uploaded_total = PrometheusCounter(
            'media_files_uploaded_total',
            'Total number of media files uploaded',
            ['file_type', 'status'],
            registry=self.registry
        )
        
        self.media_files_processed_total = PrometheusCounter(
            'media_files_processed_total',
            'Total number of media files processed',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.media_processing_duration_seconds = Histogram(
            'media_processing_duration_seconds',
            'Media processing duration in seconds',
            ['operation', 'file_type'],
            registry=self.registry
        )
        
        self.media_storage_bytes = Gauge(
            'media_storage_bytes',
            'Total bytes stored in media storage',
            ['bucket'],
            registry=self.registry
        )
        
        self.media_files_count = Gauge(
            'media_files_count',
            'Total number of media files',
            ['status'],
            registry=self.registry
        )
        
        # System metrics
        self.database_connections_active = Gauge(
            'database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.redis_connections_active = Gauge(
            'redis_connections_active',
            'Number of active Redis connections',
            registry=self.registry
        )
        
        self.cache_operations_total = PrometheusCounter(
            'cache_operations_total',
            'Total number of cache operations',
            ['operation', 'result'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = PrometheusCounter(
            'errors_total',
            'Total number of errors',
            ['error_type', 'endpoint'],
            registry=self.registry
        )
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        # Prometheus metrics
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        # In-memory metrics
        key = f"{method}:{endpoint}:{status_code}"
        self.request_counts[key] += 1
        self.response_times.append(duration)
        
        # Keep only last 1000 response times
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
    
    def record_media_upload(self, file_type: str, status: str):
        """Record media upload metrics."""
        self.media_files_uploaded_total.labels(
            file_type=file_type,
            status=status
        ).inc()
    
    def record_media_processing(self, operation: str, file_type: str, duration: float, status: str):
        """Record media processing metrics."""
        self.media_files_processed_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.media_processing_duration_seconds.labels(
            operation=operation,
            file_type=file_type
        ).observe(duration)
    
    def record_error(self, error_type: str, endpoint: str):
        """Record error metrics."""
        self.errors_total.labels(
            error_type=error_type,
            endpoint=endpoint
        ).inc()
        
        self.error_counts[f"{error_type}:{endpoint}"] += 1
    
    def update_storage_metrics(self, bucket: str, bytes_used: int):
        """Update storage usage metrics."""
        self.media_storage_bytes.labels(bucket=bucket).set(bytes_used)
    
    def update_file_count(self, status: str, count: int):
        """Update file count metrics."""
        self.media_files_count.labels(status=status).set(count)
    
    def increment_active_requests(self):
        """Increment active request counter."""
        self.active_requests += 1
        self.http_requests_in_progress.set(self.active_requests)
    
    def decrement_active_requests(self):
        """Decrement active request counter."""
        self.active_requests = max(0, self.active_requests - 1)
        self.http_requests_in_progress.set(self.active_requests)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        total_requests = sum(self.request_counts.values())
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            "total_requests": total_requests,
            "active_requests": self.active_requests,
            "average_response_time": round(avg_response_time, 4),
            "total_errors": sum(self.error_counts.values()),
            "top_endpoints": dict(Counter(self.request_counts).most_common(10)),
            "top_errors": dict(Counter(self.error_counts).most_common(5))
        }


# Global metrics collector
metrics_collector = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP request metrics."""
    
    def __init__(self, app, collector: MetricsCollector = None):
        super().__init__(app)
        self.collector = collector or metrics_collector
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        # Extract endpoint pattern (remove IDs and query params)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method
        
        # Increment active requests
        self.collector.increment_active_requests()
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            self.collector.record_request(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests
            duration = time.time() - start_time
            
            # Record error metrics
            self.collector.record_error(
                error_type=type(e).__name__,
                endpoint=endpoint
            )
            
            # Record failed request
            self.collector.record_request(
                method=method,
                endpoint=endpoint,
                status_code=500,  # Assume 500 for unhandled exceptions
                duration=duration
            )
            
            raise
            
        finally:
            # Decrement active requests
            self.collector.decrement_active_requests()
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics grouping."""
        # Remove query parameters
        if '?' in path:
            path = path.split('?')[0]
        
        # Replace common ID patterns with placeholders
        import re
        
        # UUID pattern
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )
        
        # Numeric ID pattern
        path = re.sub(r'/\d+', '/{id}', path)
        
        # File hash pattern (common in media services)
        path = re.sub(r'/[a-f0-9]{32,}', '/{hash}', path)
        
        return path


class BusinessMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting business-specific metrics."""
    
    def __init__(self, app, collector: MetricsCollector = None):
        super().__init__(app)
        self.collector = collector or metrics_collector
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect business metrics."""
        response = await call_next(request)
        
        # Collect business metrics based on endpoint and response
        await self._collect_business_metrics(request, response)
        
        return response
    
    async def _collect_business_metrics(self, request: Request, response: Response):
        """Collect business-specific metrics."""
        try:
            path = request.url.path
            method = request.method
            status_code = response.status_code
            
            # Media upload metrics
            if path.startswith('/api/v1/media/upload') and method == 'POST':
                if status_code == 201:
                    # Extract file type from content-type or filename
                    content_type = request.headers.get('content-type', '')
                    file_type = self._extract_file_type(content_type)
                    
                    self.collector.record_media_upload(
                        file_type=file_type,
                        status='success'
                    )
                else:
                    self.collector.record_media_upload(
                        file_type='unknown',
                        status='failed'
                    )
            
            # Media processing metrics
            elif '/process' in path and method == 'POST':
                operation = self._extract_operation_from_path(path)
                if status_code == 200:
                    # Processing duration would be tracked separately in the processing service
                    pass
            
            # Download metrics
            elif '/download' in path and method == 'GET':
                if status_code == 200:
                    # Track successful downloads
                    pass
            
        except Exception as e:
            logger.warning("Failed to collect business metrics", error=str(e))
    
    def _extract_file_type(self, content_type: str) -> str:
        """Extract file type from content type."""
        if not content_type:
            return 'unknown'
        
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type.startswith('audio/'):
            return 'audio'
        elif content_type.startswith('application/pdf'):
            return 'document'
        elif content_type.startswith('text/'):
            return 'text'
        else:
            return 'other'
    
    def _extract_operation_from_path(self, path: str) -> str:
        """Extract processing operation from path."""
        if 'thumbnail' in path:
            return 'thumbnail'
        elif 'transcode' in path:
            return 'transcode'
        elif 'metadata' in path:
            return 'metadata'
        else:
            return 'unknown'


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector