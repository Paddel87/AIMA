#!/usr/bin/env python3
"""
Webhook-specific Pydantic models for the AIMA Media Lifecycle Management Service.

This module contains models for webhook events, subscriptions, and notifications.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, HttpUrl
from enum import Enum

from .common import BaseResponse, ProcessingStatus
from .media import MediaType, MediaStatus, ProcessingOperation


class WebhookEventType(str, Enum):
    """Webhook event type enumeration."""
    # Media file events
    MEDIA_UPLOADED = "media.uploaded"
    MEDIA_PROCESSING_STARTED = "media.processing.started"
    MEDIA_PROCESSING_COMPLETED = "media.processing.completed"
    MEDIA_PROCESSING_FAILED = "media.processing.failed"
    MEDIA_DELETED = "media.deleted"
    MEDIA_ARCHIVED = "media.archived"
    MEDIA_RESTORED = "media.restored"
    MEDIA_EXPIRED = "media.expired"
    
    # Processing job events
    JOB_QUEUED = "job.queued"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    
    # Storage events
    STORAGE_QUOTA_WARNING = "storage.quota.warning"
    STORAGE_QUOTA_EXCEEDED = "storage.quota.exceeded"
    STORAGE_TIER_CHANGED = "storage.tier.changed"
    
    # System events
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH_CHECK = "system.health_check"


class WebhookDeliveryStatus(str, Enum):
    """Webhook delivery status enumeration."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class WebhookSubscriptionStatus(str, Enum):
    """Webhook subscription status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    EXPIRED = "expired"


class WebhookEventData(BaseModel):
    """Base webhook event data model."""
    
    model_config = ConfigDict(extra="allow")
    
    event_id: UUID = Field(description="Unique event ID")
    event_type: WebhookEventType = Field(description="Event type")
    timestamp: datetime = Field(description="Event timestamp")
    source: str = Field(description="Event source service")
    version: str = Field(default="1.0", description="Event schema version")


class MediaEventData(WebhookEventData):
    """Media-specific webhook event data."""
    
    file_id: UUID = Field(description="Media file ID")
    filename: str = Field(description="Original filename")
    media_type: MediaType = Field(description="Media type")
    status: MediaStatus = Field(description="Media status")
    owner_id: UUID = Field(description="Owner user ID")
    file_size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    
    # Optional fields based on event type
    download_url: Optional[str] = Field(default=None, description="Download URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    error_message: Optional[str] = Field(default=None, description="Error message if applicable")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Media metadata")


class ProcessingJobEventData(WebhookEventData):
    """Processing job webhook event data."""
    
    job_id: UUID = Field(description="Processing job ID")
    file_id: UUID = Field(description="Media file ID")
    operation: ProcessingOperation = Field(description="Processing operation")
    status: ProcessingStatus = Field(description="Job status")
    progress_percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Progress percentage")
    
    # Job details
    priority: int = Field(description="Job priority")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Operation parameters")
    
    # Results
    result_file_id: Optional[UUID] = Field(default=None, description="Result file ID")
    result_url: Optional[str] = Field(default=None, description="Result download URL")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Performance metrics
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    cpu_time: Optional[float] = Field(default=None, description="CPU time in seconds")
    memory_usage: Optional[int] = Field(default=None, description="Peak memory usage in bytes")


class StorageEventData(WebhookEventData):
    """Storage-related webhook event data."""
    
    user_id: Optional[UUID] = Field(default=None, description="User ID (if user-specific)")
    total_size: int = Field(description="Total storage size in bytes")
    quota: Optional[int] = Field(default=None, description="Storage quota in bytes")
    quota_used_percentage: Optional[float] = Field(default=None, description="Percentage of quota used")
    
    # Event-specific data
    file_id: Optional[UUID] = Field(default=None, description="Related file ID")
    old_tier: Optional[str] = Field(default=None, description="Previous storage tier")
    new_tier: Optional[str] = Field(default=None, description="New storage tier")
    threshold_percentage: Optional[float] = Field(default=None, description="Quota threshold percentage")


class SystemEventData(WebhookEventData):
    """System-related webhook event data."""
    
    service_name: str = Field(description="Service name")
    severity: str = Field(description="Event severity (info, warning, error, critical)")
    message: str = Field(description="Event message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional event details")
    
    # Health check specific
    health_status: Optional[str] = Field(default=None, description="Health check status")
    response_time: Optional[float] = Field(default=None, description="Response time in seconds")
    
    # Maintenance specific
    maintenance_start: Optional[datetime] = Field(default=None, description="Maintenance start time")
    maintenance_end: Optional[datetime] = Field(default=None, description="Maintenance end time")
    affected_services: Optional[List[str]] = Field(default=None, description="Affected services")


class WebhookPayload(BaseModel):
    """Complete webhook payload model."""
    
    # Webhook metadata
    webhook_id: UUID = Field(description="Webhook delivery ID")
    subscription_id: UUID = Field(description="Webhook subscription ID")
    delivery_attempt: int = Field(ge=1, description="Delivery attempt number")
    
    # Event data
    data: Union[MediaEventData, ProcessingJobEventData, StorageEventData, SystemEventData] = Field(
        description="Event data", discriminator="event_type"
    )
    
    # Signature for verification
    signature: str = Field(description="HMAC signature for payload verification")
    timestamp: datetime = Field(description="Webhook delivery timestamp")


class WebhookSubscriptionCreate(BaseModel):
    """Model for creating webhook subscriptions."""
    
    url: HttpUrl = Field(description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(min_length=1, description="Event types to subscribe to")
    
    # Optional configuration
    name: Optional[str] = Field(default=None, max_length=100, description="Subscription name")
    description: Optional[str] = Field(default=None, max_length=500, description="Subscription description")
    secret: Optional[str] = Field(default=None, min_length=16, max_length=64, description="Secret for signature verification")
    
    # Filtering
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Event filters")
    
    # Delivery configuration
    timeout_seconds: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=10, le=3600, description="Delay between retries in seconds")
    
    # Status
    is_active: bool = Field(default=True, description="Whether the subscription is active")
    expires_at: Optional[datetime] = Field(default=None, description="Subscription expiration time")
    
    @field_validator('events')
    @classmethod
    def validate_events(cls, v):
        """Validate event types."""
        if len(set(v)) != len(v):
            raise ValueError("Duplicate event types are not allowed")
        return v


class WebhookSubscriptionUpdate(BaseModel):
    """Model for updating webhook subscriptions."""
    
    url: Optional[HttpUrl] = Field(default=None, description="Webhook endpoint URL")
    events: Optional[List[WebhookEventType]] = Field(default=None, description="Event types to subscribe to")
    name: Optional[str] = Field(default=None, max_length=100, description="Subscription name")
    description: Optional[str] = Field(default=None, max_length=500, description="Subscription description")
    secret: Optional[str] = Field(default=None, min_length=16, max_length=64, description="Secret for signature verification")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Event filters")
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=300, description="Request timeout in seconds")
    retry_attempts: Optional[int] = Field(default=None, ge=0, le=10, description="Number of retry attempts")
    retry_delay_seconds: Optional[int] = Field(default=None, ge=10, le=3600, description="Delay between retries in seconds")
    is_active: Optional[bool] = Field(default=None, description="Whether the subscription is active")
    expires_at: Optional[datetime] = Field(default=None, description="Subscription expiration time")


class WebhookSubscriptionResponse(BaseModel):
    """Webhook subscription response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(description="Subscription ID")
    user_id: UUID = Field(description="Owner user ID")
    url: str = Field(description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(description="Subscribed event types")
    
    # Configuration
    name: Optional[str] = Field(default=None, description="Subscription name")
    description: Optional[str] = Field(default=None, description="Subscription description")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Event filters")
    
    # Delivery configuration
    timeout_seconds: int = Field(description="Request timeout in seconds")
    retry_attempts: int = Field(description="Number of retry attempts")
    retry_delay_seconds: int = Field(description="Delay between retries in seconds")
    
    # Status
    status: WebhookSubscriptionStatus = Field(description="Subscription status")
    is_active: bool = Field(description="Whether the subscription is active")
    
    # Statistics
    total_deliveries: int = Field(default=0, description="Total delivery attempts")
    successful_deliveries: int = Field(default=0, description="Successful deliveries")
    failed_deliveries: int = Field(default=0, description="Failed deliveries")
    last_delivery_at: Optional[datetime] = Field(default=None, description="Last delivery attempt timestamp")
    last_success_at: Optional[datetime] = Field(default=None, description="Last successful delivery timestamp")
    
    # Timestamps
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(description="Delivery ID")
    subscription_id: UUID = Field(description="Subscription ID")
    event_id: UUID = Field(description="Event ID")
    event_type: WebhookEventType = Field(description="Event type")
    
    # Delivery details
    url: str = Field(description="Delivery URL")
    attempt: int = Field(description="Delivery attempt number")
    status: WebhookDeliveryStatus = Field(description="Delivery status")
    
    # HTTP details
    http_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    response_headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP response headers")
    response_body: Optional[str] = Field(default=None, description="HTTP response body")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Timing
    request_duration: Optional[float] = Field(default=None, description="Request duration in seconds")
    
    # Timestamps
    created_at: datetime = Field(description="Creation timestamp")
    delivered_at: Optional[datetime] = Field(default=None, description="Delivery timestamp")
    next_retry_at: Optional[datetime] = Field(default=None, description="Next retry timestamp")


class WebhookTestRequest(BaseModel):
    """Webhook test request model."""
    
    url: HttpUrl = Field(description="Webhook endpoint URL to test")
    event_type: WebhookEventType = Field(description="Event type to simulate")
    secret: Optional[str] = Field(default=None, description="Secret for signature verification")
    timeout_seconds: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")


class WebhookTestResponse(BaseResponse):
    """Webhook test response model."""
    
    success: bool = Field(description="Whether the test was successful")
    http_status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    response_headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP response headers")
    response_body: Optional[str] = Field(default=None, description="HTTP response body")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    request_duration: float = Field(description="Request duration in seconds")
    test_payload: Dict[str, Any] = Field(description="Test payload that was sent")


class WebhookStatsResponse(BaseResponse):
    """Webhook statistics response model."""
    
    subscription_id: UUID = Field(description="Subscription ID")
    period_start: datetime = Field(description="Statistics period start")
    period_end: datetime = Field(description="Statistics period end")
    
    # Delivery statistics
    total_events: int = Field(description="Total events generated")
    total_deliveries: int = Field(description="Total delivery attempts")
    successful_deliveries: int = Field(description="Successful deliveries")
    failed_deliveries: int = Field(description="Failed deliveries")
    pending_deliveries: int = Field(description="Pending deliveries")
    
    # Performance metrics
    average_response_time: Optional[float] = Field(default=None, description="Average response time in seconds")
    success_rate: float = Field(description="Success rate percentage")
    
    # Event type breakdown
    events_by_type: Dict[WebhookEventType, int] = Field(description="Event count by type")
    
    # Status code breakdown
    status_codes: Dict[str, int] = Field(description="Response status code counts")


class WebhookRetryRequest(BaseModel):
    """Webhook retry request model."""
    
    delivery_ids: List[UUID] = Field(min_length=1, max_length=100, description="Delivery IDs to retry")
    force_retry: bool = Field(default=False, description="Force retry even if max attempts reached")


class WebhookRetryResponse(BaseResponse):
    """Webhook retry response model."""
    
    retried_count: int = Field(description="Number of deliveries retried")
    skipped_count: int = Field(description="Number of deliveries skipped")
    retry_job_ids: List[UUID] = Field(description="Background job IDs for retries")