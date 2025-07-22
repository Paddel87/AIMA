#!/usr/bin/env python3
"""
Request logging middleware for the AIMA Media Lifecycle Management Service.

This middleware logs all incoming HTTP requests and responses with detailed
information for monitoring and debugging purposes.
"""

import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        super().__init__(app)
        self.log_body = log_body
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Start timing
        start_time = time.time()
        
        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Log request start
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=client_ip,
            user_agent=user_agent,
            headers=dict(request.headers) if logger.isEnabledFor(10) else None  # Debug level
        )
        
        # Log request body if enabled and appropriate
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            await self._log_request_body(request, request_id)
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log successful response
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=round(process_time, 4),
                response_size=response.headers.get("content-length"),
                content_type=response.headers.get("content-type")
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate processing time for failed requests
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                error=str(e),
                error_type=type(e).__name__,
                process_time=round(process_time, 4)
            )
            
            # Re-raise the exception
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _log_request_body(self, request: Request, request_id: str):
        """Log request body if appropriate."""
        try:
            content_type = request.headers.get("content-type", "")
            
            # Only log text-based content types
            if any(ct in content_type.lower() for ct in [
                "application/json",
                "application/x-www-form-urlencoded",
                "text/",
                "application/xml"
            ]):
                # Read body (this consumes the stream, so we need to be careful)
                body = await request.body()
                
                if len(body) <= self.max_body_size:
                    try:
                        body_str = body.decode("utf-8")
                        logger.debug(
                            "Request body",
                            request_id=request_id,
                            body=body_str,
                            content_type=content_type
                        )
                    except UnicodeDecodeError:
                        logger.debug(
                            "Request body (binary)",
                            request_id=request_id,
                            body_size=len(body),
                            content_type=content_type
                        )
                else:
                    logger.debug(
                        "Request body (too large)",
                        request_id=request_id,
                        body_size=len(body),
                        content_type=content_type
                    )
            
        except Exception as e:
            logger.warning(
                "Failed to log request body",
                request_id=request_id,
                error=str(e)
            )


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware with structured logging and correlation IDs."""
    
    def __init__(self, app, service_name: str = "media-lifecycle-management"):
        super().__init__(app)
        self.service_name = service_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with structured logging context."""
        # Generate correlation ID
        correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        
        # Create structured logging context
        log_context = {
            "service": self.service_name,
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "request_method": request.method,
            "request_path": request.url.path,
            "client_ip": self._get_client_ip(request)
        }
        
        # Bind context to logger
        bound_logger = logger.bind(**log_context)
        
        # Store in request state for use in other parts of the application
        request.state.logger = bound_logger
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            # Log successful request
            bound_logger.info(
                "Request processed successfully",
                status_code=response.status_code,
                process_time=round(process_time, 4)
            )
            
            # Add correlation headers to response
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log error with context
            bound_logger.error(
                "Request processing failed",
                error=str(e),
                error_type=type(e).__name__,
                process_time=round(process_time, 4)
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"