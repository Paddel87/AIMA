#!/usr/bin/env python3
"""
Error handling middleware for the AIMA Media Lifecycle Management Service.

This middleware provides centralized error handling, logging, and response
formatting for all types of exceptions that may occur in the application.
"""

import traceback
from typing import Callable, Dict, Any, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

logger = structlog.get_logger(__name__)


class MediaServiceException(Exception):
    """Base exception for media service errors."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code or "MEDIA_SERVICE_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class MediaProcessingError(MediaServiceException):
    """Exception for media processing errors."""
    
    def __init__(self, message: str, operation: str = None, file_type: str = None, **kwargs):
        super().__init__(message, "MEDIA_PROCESSING_ERROR", {
            "operation": operation,
            "file_type": file_type,
            **kwargs
        })


class StorageError(MediaServiceException):
    """Exception for storage-related errors."""
    
    def __init__(self, message: str, operation: str = None, bucket: str = None, **kwargs):
        super().__init__(message, "STORAGE_ERROR", {
            "operation": operation,
            "bucket": bucket,
            **kwargs
        })


class AuthenticationError(MediaServiceException):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, "AUTHENTICATION_ERROR", kwargs)


class AuthorizationError(MediaServiceException):
    """Exception for authorization errors."""
    
    def __init__(self, message: str = "Access denied", required_permission: str = None, **kwargs):
        super().__init__(message, "AUTHORIZATION_ERROR", {
            "required_permission": required_permission,
            **kwargs
        })


class ValidationError(MediaServiceException):
    """Exception for validation errors."""
    
    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(message, "VALIDATION_ERROR", {
            "field": field,
            "value": value,
            **kwargs
        })


class RateLimitError(MediaServiceException):
    """Exception for rate limiting errors."""
    
    def __init__(self, message: str = "Rate limit exceeded", limit: int = None, window: int = None, **kwargs):
        super().__init__(message, "RATE_LIMIT_ERROR", {
            "limit": limit,
            "window": window,
            **kwargs
        })


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling."""
    
    def __init__(self, app, debug: bool = False, include_traceback: bool = False):
        super().__init__(app)
        self.debug = debug
        self.include_traceback = include_traceback
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with error handling."""
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            return await self._handle_exception(request, e)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle different types of exceptions."""
        # Get request context for logging
        request_id = getattr(request.state, 'request_id', 'unknown')
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        # Base error response structure
        error_response = {
            "error": True,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "timestamp": self._get_timestamp()
        }
        
        # Handle different exception types
        if isinstance(exc, MediaServiceException):
            return await self._handle_media_service_exception(request, exc, error_response)
        
        elif isinstance(exc, HTTPException):
            return await self._handle_http_exception(request, exc, error_response)
        
        elif isinstance(exc, StarletteHTTPException):
            return await self._handle_starlette_http_exception(request, exc, error_response)
        
        elif isinstance(exc, RequestValidationError):
            return await self._handle_validation_exception(request, exc, error_response)
        
        else:
            return await self._handle_generic_exception(request, exc, error_response)
    
    async def _handle_media_service_exception(self, request: Request, exc: MediaServiceException, error_response: Dict) -> JSONResponse:
        """Handle custom media service exceptions."""
        status_code = self._get_status_code_for_error(exc.error_code)
        
        error_response.update({
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details
        })
        
        # Log error with appropriate level
        log_level = "warning" if status_code < 500 else "error"
        getattr(logger, log_level)(
            "Media service exception",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            status_code=status_code,
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )
    
    async def _handle_http_exception(self, request: Request, exc: HTTPException, error_response: Dict) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        error_response.update({
            "error_code": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code
        })
        
        logger.warning(
            "HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    async def _handle_starlette_http_exception(self, request: Request, exc: StarletteHTTPException, error_response: Dict) -> JSONResponse:
        """Handle Starlette HTTP exceptions."""
        error_response.update({
            "error_code": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code
        })
        
        logger.warning(
            "Starlette HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    async def _handle_validation_exception(self, request: Request, exc: RequestValidationError, error_response: Dict) -> JSONResponse:
        """Handle request validation exceptions."""
        # Format validation errors
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        error_response.update({
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "validation_errors": validation_errors
        })
        
        logger.warning(
            "Request validation failed",
            validation_errors=validation_errors,
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response
        )
    
    async def _handle_generic_exception(self, request: Request, exc: Exception, error_response: Dict) -> JSONResponse:
        """Handle generic unhandled exceptions."""
        error_response.update({
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred"
        })
        
        # Add debug information if enabled
        if self.debug:
            error_response["debug"] = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)
            }
            
            if self.include_traceback:
                error_response["debug"]["traceback"] = traceback.format_exc()
        
        # Log error with full details
        logger.error(
            "Unhandled exception",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback=traceback.format_exc(),
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response
        )
    
    def _get_status_code_for_error(self, error_code: str) -> int:
        """Map error codes to HTTP status codes."""
        error_code_mapping = {
            "AUTHENTICATION_ERROR": status.HTTP_401_UNAUTHORIZED,
            "AUTHORIZATION_ERROR": status.HTTP_403_FORBIDDEN,
            "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "RATE_LIMIT_ERROR": status.HTTP_429_TOO_MANY_REQUESTS,
            "MEDIA_PROCESSING_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "STORAGE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
            "MEDIA_SERVICE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
        
        return error_code_mapping.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


class GlobalExceptionHandler:
    """Global exception handler for FastAPI application."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
    
    async def http_exception_handler(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions globally."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "timestamp": self._get_timestamp()
            }
        )
    
    async def validation_exception_handler(self, request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle validation exceptions globally."""
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "validation_errors": validation_errors,
                "path": request.url.path,
                "method": request.method,
                "timestamp": self._get_timestamp()
            }
        )
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"