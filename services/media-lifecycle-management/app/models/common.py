#!/usr/bin/env python3
"""
Common Pydantic models for the AIMA Media Lifecycle Management Service.

This module contains base models and common response structures
used across the API.
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

# Generic type for paginated responses
T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response model for all API responses."""
    
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    success: bool = Field(default=True, description="Whether the request was successful")
    message: Optional[str] = Field(default=None, description="Optional message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    error: bool = Field(default=True, description="Indicates this is an error response")
    error_code: str = Field(description="Error code for programmatic handling")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for distributed tracing")


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    
    field: str = Field(description="Field that failed validation")
    message: str = Field(description="Validation error message")
    type: str = Field(description="Type of validation error")
    input: Optional[Any] = Field(default=None, description="Input value that failed validation")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with detailed field errors."""
    
    validation_errors: List[ValidationErrorDetail] = Field(
        description="List of validation errors"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class SortOrder(str, Enum):
    """Sort order enumeration."""
    ASC = "asc"
    DESC = "desc"


class SortParams(BaseModel):
    """Sorting parameters."""
    
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="Sort order")


class FilterParams(BaseModel):
    """Base filtering parameters."""
    
    search: Optional[str] = Field(default=None, description="Search query")
    created_after: Optional[datetime] = Field(default=None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(default=None, description="Filter by creation date (before)")
    updated_after: Optional[datetime] = Field(default=None, description="Filter by update date (after)")
    updated_before: Optional[datetime] = Field(default=None, description="Filter by update date (before)")


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    total_items: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_previous: bool = Field(description="Whether there is a previous page")
    
    @classmethod
    def create(cls, page: int, page_size: int, total_items: int) -> "PaginationMeta":
        """Create pagination metadata from parameters."""
        total_pages = (total_items + page_size - 1) // page_size  # Ceiling division
        
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )


class PaginatedResponse(BaseResponse, Generic[T]):
    """Generic paginated response model."""
    
    data: List[T] = Field(description="List of items")
    pagination: PaginationMeta = Field(description="Pagination metadata")


class HealthStatus(str, Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class ServiceHealth(BaseModel):
    """Individual service health status."""
    
    name: str = Field(description="Service name")
    status: HealthStatus = Field(description="Service health status")
    response_time: Optional[float] = Field(default=None, description="Response time in seconds")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional health details")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check timestamp")


class HealthCheckResponse(BaseResponse):
    """Health check response model."""
    
    status: HealthStatus = Field(description="Overall health status")
    version: str = Field(description="Service version")
    uptime: float = Field(description="Service uptime in seconds")
    services: List[ServiceHealth] = Field(description="Individual service health statuses")
    system_info: Optional[Dict[str, Any]] = Field(default=None, description="System information")


class MetricsResponse(BaseResponse):
    """Metrics response model."""
    
    metrics: Dict[str, Any] = Field(description="Service metrics")
    collection_time: datetime = Field(default_factory=datetime.utcnow, description="Metrics collection timestamp")


class ConfigurationItem(BaseModel):
    """Configuration item model."""
    
    key: str = Field(description="Configuration key")
    value: Any = Field(description="Configuration value")
    description: Optional[str] = Field(default=None, description="Configuration description")
    is_sensitive: bool = Field(default=False, description="Whether the value is sensitive")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class ConfigurationResponse(BaseResponse):
    """Configuration response model."""
    
    configurations: List[ConfigurationItem] = Field(description="List of configuration items")


class BulkOperationResult(BaseModel):
    """Result of a bulk operation."""
    
    total: int = Field(description="Total number of items processed")
    successful: int = Field(description="Number of successful operations")
    failed: int = Field(description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="List of errors")


class BulkOperationResponse(BaseResponse):
    """Bulk operation response model."""
    
    result: BulkOperationResult = Field(description="Bulk operation result")


class FileInfo(BaseModel):
    """Basic file information model."""
    
    filename: str = Field(description="Original filename")
    size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    checksum: Optional[str] = Field(default=None, description="File checksum")


class UploadInfo(BaseModel):
    """File upload information."""
    
    upload_id: str = Field(description="Unique upload identifier")
    filename: str = Field(description="Original filename")
    size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    upload_url: Optional[str] = Field(default=None, description="Pre-signed upload URL")
    expires_at: Optional[datetime] = Field(default=None, description="Upload URL expiration")


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingProgress(BaseModel):
    """Processing progress information."""
    
    percentage: float = Field(ge=0, le=100, description="Progress percentage")
    current_step: Optional[str] = Field(default=None, description="Current processing step")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional progress details")


class AsyncOperationResponse(BaseResponse):
    """Response for asynchronous operations."""
    
    operation_id: str = Field(description="Unique operation identifier")
    status: ProcessingStatus = Field(description="Operation status")
    progress: Optional[ProcessingProgress] = Field(default=None, description="Operation progress")
    result_url: Optional[str] = Field(default=None, description="URL to get operation result")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for status updates")


class WebhookEvent(BaseModel):
    """Webhook event model."""
    
    event_id: str = Field(description="Unique event identifier")
    event_type: str = Field(description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(description="Event data")
    retry_count: int = Field(default=0, description="Number of delivery retries")


class APIKeyInfo(BaseModel):
    """API key information model."""
    
    key_id: str = Field(description="API key identifier")
    name: str = Field(description="API key name")
    permissions: List[str] = Field(description="List of permissions")
    created_at: datetime = Field(description="Creation timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    last_used: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    is_active: bool = Field(default=True, description="Whether the key is active")


class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    
    limit: int = Field(description="Rate limit")
    remaining: int = Field(description="Remaining requests")
    reset_time: datetime = Field(description="Reset timestamp")
    window: int = Field(description="Time window in seconds")


class ServiceInfo(BaseModel):
    """Service information model."""
    
    name: str = Field(description="Service name")
    version: str = Field(description="Service version")
    description: str = Field(description="Service description")
    api_version: str = Field(description="API version")
    documentation_url: Optional[str] = Field(default=None, description="Documentation URL")
    support_contact: Optional[str] = Field(default=None, description="Support contact")
    terms_of_service: Optional[str] = Field(default=None, description="Terms of service URL")


class ServiceInfoResponse(BaseResponse):
    """Service information response."""
    
    service: ServiceInfo = Field(description="Service information")
    endpoints: List[str] = Field(description="Available endpoints")
    features: List[str] = Field(description="Supported features")
    limits: Dict[str, Any] = Field(description="Service limits")