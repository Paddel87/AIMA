#!/usr/bin/env python3
"""
Media-specific Pydantic models for the AIMA Media Lifecycle Management Service.

This module contains models for media files, processing jobs, tags,
and related operations.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, validator, field_validator
from enum import Enum

from .common import BaseResponse, PaginatedResponse, ProcessingStatus, ProcessingProgress


class MediaType(str, Enum):
    """Media type enumeration."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class MediaStatus(str, Enum):
    """Media file status enumeration."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProcessingOperation(str, Enum):
    """Processing operation enumeration."""
    THUMBNAIL = "thumbnail"
    TRANSCODE = "transcode"
    METADATA_EXTRACTION = "metadata_extraction"
    COMPRESSION = "compression"
    FORMAT_CONVERSION = "format_conversion"
    WATERMARK = "watermark"
    RESIZE = "resize"
    CROP = "crop"
    ROTATE = "rotate"


class StorageTier(str, Enum):
    """Storage tier enumeration."""
    HOT = "hot"  # Frequently accessed
    WARM = "warm"  # Occasionally accessed
    COLD = "cold"  # Rarely accessed
    ARCHIVE = "archive"  # Long-term storage


class MediaDimensions(BaseModel):
    """Media dimensions model."""
    
    width: int = Field(ge=1, description="Width in pixels")
    height: int = Field(ge=1, description="Height in pixels")
    aspect_ratio: Optional[float] = Field(default=None, description="Aspect ratio (width/height)")
    
    def model_post_init(self, __context) -> None:
        """Calculate aspect ratio after initialization."""
        if self.aspect_ratio is None:
            self.aspect_ratio = round(self.width / self.height, 3)


class MediaMetadata(BaseModel):
    """Media metadata model."""
    
    model_config = ConfigDict(extra="allow")
    
    # Common metadata
    duration: Optional[float] = Field(default=None, description="Duration in seconds (for video/audio)")
    dimensions: Optional[MediaDimensions] = Field(default=None, description="Media dimensions")
    bitrate: Optional[int] = Field(default=None, description="Bitrate in bps")
    frame_rate: Optional[float] = Field(default=None, description="Frame rate (for video)")
    sample_rate: Optional[int] = Field(default=None, description="Sample rate (for audio)")
    channels: Optional[int] = Field(default=None, description="Number of audio channels")
    
    # File metadata
    format: Optional[str] = Field(default=None, description="File format")
    codec: Optional[str] = Field(default=None, description="Codec used")
    color_space: Optional[str] = Field(default=None, description="Color space")
    
    # EXIF data (for images)
    exif: Optional[Dict[str, Any]] = Field(default=None, description="EXIF data")
    
    # Custom metadata
    custom: Optional[Dict[str, Any]] = Field(default=None, description="Custom metadata")
    
    # Extraction metadata
    extraction_timestamp: Optional[datetime] = Field(default=None, description="When metadata was extracted")
    extraction_version: Optional[str] = Field(default=None, description="Metadata extractor version")


class MediaTagCreate(BaseModel):
    """Model for creating media tags."""
    
    name: str = Field(min_length=1, max_length=100, description="Tag name")
    value: Optional[str] = Field(default=None, max_length=500, description="Tag value")
    category: Optional[str] = Field(default=None, max_length=50, description="Tag category")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate tag name."""
        if not v.strip():
            raise ValueError("Tag name cannot be empty")
        return v.strip().lower()


class MediaTagResponse(BaseModel):
    """Media tag response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(description="Tag ID")
    name: str = Field(description="Tag name")
    value: Optional[str] = Field(default=None, description="Tag value")
    category: Optional[str] = Field(default=None, description="Tag category")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MediaFileCreate(BaseModel):
    """Model for creating media files."""
    
    filename: str = Field(min_length=1, max_length=255, description="Original filename")
    title: Optional[str] = Field(default=None, max_length=200, description="Media title")
    description: Optional[str] = Field(default=None, max_length=1000, description="Media description")
    tags: Optional[List[MediaTagCreate]] = Field(default=None, description="Media tags")
    metadata: Optional[MediaMetadata] = Field(default=None, description="Media metadata")
    storage_tier: StorageTier = Field(default=StorageTier.HOT, description="Storage tier")
    is_public: bool = Field(default=False, description="Whether the file is publicly accessible")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Validate filename."""
        if not v.strip():
            raise ValueError("Filename cannot be empty")
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Filename contains invalid characters: {invalid_chars}")
        
        return v.strip()


class MediaFileUpdate(BaseModel):
    """Model for updating media files."""
    
    title: Optional[str] = Field(default=None, max_length=200, description="Media title")
    description: Optional[str] = Field(default=None, max_length=1000, description="Media description")
    storage_tier: Optional[StorageTier] = Field(default=None, description="Storage tier")
    is_public: Optional[bool] = Field(default=None, description="Whether the file is publicly accessible")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    metadata: Optional[MediaMetadata] = Field(default=None, description="Media metadata")


class MediaFileResponse(BaseModel):
    """Media file response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(description="Media file ID")
    filename: str = Field(description="Original filename")
    title: Optional[str] = Field(default=None, description="Media title")
    description: Optional[str] = Field(default=None, description="Media description")
    
    # File properties
    file_size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    media_type: MediaType = Field(description="Media type")
    checksum: str = Field(description="File checksum")
    
    # Status and processing
    status: MediaStatus = Field(description="Media file status")
    processing_progress: Optional[ProcessingProgress] = Field(default=None, description="Processing progress")
    
    # Storage information
    storage_path: str = Field(description="Storage path")
    storage_tier: StorageTier = Field(description="Storage tier")
    storage_bucket: str = Field(description="Storage bucket")
    
    # Access control
    is_public: bool = Field(description="Whether the file is publicly accessible")
    owner_id: UUID = Field(description="Owner user ID")
    
    # URLs
    download_url: Optional[str] = Field(default=None, description="Download URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")
    preview_url: Optional[str] = Field(default=None, description="Preview URL")
    
    # Metadata
    metadata: Optional[MediaMetadata] = Field(default=None, description="Media metadata")
    tags: List[MediaTagResponse] = Field(default_factory=list, description="Media tags")
    
    # Timestamps
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    last_accessed: Optional[datetime] = Field(default=None, description="Last access timestamp")


class MediaFileListResponse(PaginatedResponse[MediaFileResponse]):
    """Paginated media file list response."""
    pass


class MediaUploadRequest(BaseModel):
    """Media upload request model."""
    
    filename: str = Field(description="Original filename")
    content_type: str = Field(description="Content type")
    file_size: int = Field(ge=1, description="File size in bytes")
    checksum: Optional[str] = Field(default=None, description="File checksum for verification")
    
    # Optional metadata
    title: Optional[str] = Field(default=None, max_length=200, description="Media title")
    description: Optional[str] = Field(default=None, max_length=1000, description="Media description")
    tags: Optional[List[MediaTagCreate]] = Field(default=None, description="Media tags")
    storage_tier: StorageTier = Field(default=StorageTier.HOT, description="Storage tier")
    is_public: bool = Field(default=False, description="Whether the file is publicly accessible")
    
    @field_validator('file_size')
    @classmethod
    def validate_file_size(cls, v):
        """Validate file size."""
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if v > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
        return v


class MediaUploadResponse(BaseResponse):
    """Media upload response model."""
    
    file_id: UUID = Field(description="Media file ID")
    upload_url: str = Field(description="Pre-signed upload URL")
    upload_id: str = Field(description="Upload session ID")
    expires_at: datetime = Field(description="Upload URL expiration")
    max_file_size: int = Field(description="Maximum allowed file size")
    allowed_content_types: List[str] = Field(description="Allowed content types")


class MediaProcessingRequest(BaseModel):
    """Media processing request model."""
    
    operation: ProcessingOperation = Field(description="Processing operation")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Operation parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Processing priority (1=highest, 10=lowest)")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for completion notification")
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v, info):
        """Validate operation parameters."""
        if v is None:
            return v
        
        operation = info.data.get('operation')
        
        # Validate parameters based on operation type
        if operation == ProcessingOperation.THUMBNAIL:
            required_params = ['width', 'height']
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Parameter '{param}' is required for thumbnail operation")
            
            if not isinstance(v['width'], int) or not isinstance(v['height'], int):
                raise ValueError("Width and height must be integers")
            
            if v['width'] <= 0 or v['height'] <= 0:
                raise ValueError("Width and height must be positive")
        
        elif operation == ProcessingOperation.RESIZE:
            if 'width' not in v and 'height' not in v:
                raise ValueError("Either width or height must be specified for resize operation")
        
        elif operation == ProcessingOperation.TRANSCODE:
            if 'format' not in v:
                raise ValueError("Format parameter is required for transcode operation")
        
        return v


class ProcessingJobResponse(BaseModel):
    """Processing job response model."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(description="Job ID")
    file_id: UUID = Field(description="Media file ID")
    operation: ProcessingOperation = Field(description="Processing operation")
    status: ProcessingStatus = Field(description="Job status")
    progress: Optional[ProcessingProgress] = Field(default=None, description="Job progress")
    
    # Job details
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Operation parameters")
    priority: int = Field(description="Job priority")
    
    # Results
    result_file_id: Optional[UUID] = Field(default=None, description="Result file ID")
    result_url: Optional[str] = Field(default=None, description="Result download URL")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Timestamps
    created_at: datetime = Field(description="Job creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")
    
    # Performance metrics
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    cpu_time: Optional[float] = Field(default=None, description="CPU time in seconds")
    memory_usage: Optional[int] = Field(default=None, description="Peak memory usage in bytes")


class MediaProcessingResponse(BaseResponse):
    """Media processing response model."""
    
    job: ProcessingJobResponse = Field(description="Processing job details")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    queue_position: Optional[int] = Field(default=None, description="Position in processing queue")


class MediaMetadataResponse(BaseResponse):
    """Media metadata response model."""
    
    file_id: UUID = Field(description="Media file ID")
    metadata: MediaMetadata = Field(description="Extracted metadata")
    extraction_job_id: Optional[UUID] = Field(default=None, description="Metadata extraction job ID")


class StorageUsageStats(BaseModel):
    """Storage usage statistics model."""
    
    total_files: int = Field(description="Total number of files")
    total_size: int = Field(description="Total size in bytes")
    by_media_type: Dict[MediaType, Dict[str, Union[int, float]]] = Field(
        description="Usage statistics by media type"
    )
    by_storage_tier: Dict[StorageTier, Dict[str, Union[int, float]]] = Field(
        description="Usage statistics by storage tier"
    )
    by_status: Dict[MediaStatus, int] = Field(
        description="File count by status"
    )


class StorageUsageResponse(BaseResponse):
    """Storage usage response model."""
    
    user_id: Optional[UUID] = Field(default=None, description="User ID (if user-specific)")
    stats: StorageUsageStats = Field(description="Storage usage statistics")
    quota: Optional[int] = Field(default=None, description="Storage quota in bytes")
    quota_used_percentage: Optional[float] = Field(default=None, description="Percentage of quota used")


class MediaSearchRequest(BaseModel):
    """Media search request model."""
    
    query: Optional[str] = Field(default=None, description="Search query")
    media_types: Optional[List[MediaType]] = Field(default=None, description="Filter by media types")
    statuses: Optional[List[MediaStatus]] = Field(default=None, description="Filter by statuses")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    
    # Date filters
    created_after: Optional[datetime] = Field(default=None, description="Created after date")
    created_before: Optional[datetime] = Field(default=None, description="Created before date")
    
    # Size filters
    min_size: Optional[int] = Field(default=None, ge=0, description="Minimum file size")
    max_size: Optional[int] = Field(default=None, ge=0, description="Maximum file size")
    
    # Dimension filters (for images/videos)
    min_width: Optional[int] = Field(default=None, ge=1, description="Minimum width")
    max_width: Optional[int] = Field(default=None, ge=1, description="Maximum width")
    min_height: Optional[int] = Field(default=None, ge=1, description="Minimum height")
    max_height: Optional[int] = Field(default=None, ge=1, description="Maximum height")
    
    # Duration filters (for video/audio)
    min_duration: Optional[float] = Field(default=None, ge=0, description="Minimum duration in seconds")
    max_duration: Optional[float] = Field(default=None, ge=0, description="Maximum duration in seconds")
    
    @field_validator('max_size')
    @classmethod
    def validate_max_size(cls, v, info):
        """Validate max_size is greater than min_size."""
        if v is not None and info.data.get('min_size') is not None:
            if v < info.data['min_size']:
                raise ValueError("max_size must be greater than min_size")
        return v


class MediaBulkOperationRequest(BaseModel):
    """Bulk operation request model."""
    
    file_ids: List[UUID] = Field(min_length=1, max_length=100, description="List of file IDs")
    operation: str = Field(description="Operation to perform")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Operation parameters")
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate operation type."""
        allowed_operations = ['delete', 'archive', 'change_tier', 'add_tags', 'remove_tags']
        if v not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v


class MediaAnalyticsRequest(BaseModel):
    """Media analytics request model."""
    
    start_date: datetime = Field(description="Start date for analytics")
    end_date: datetime = Field(description="End date for analytics")
    metrics: List[str] = Field(description="Metrics to include")
    group_by: Optional[str] = Field(default=None, description="Group results by field")
    
    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        """Validate end_date is after start_date."""
        if info.data.get('start_date') and v <= info.data['start_date']:
            raise ValueError("end_date must be after start_date")
        return v


class MediaAnalyticsResponse(BaseResponse):
    """Media analytics response model."""
    
    period: Dict[str, datetime] = Field(description="Analytics period")
    metrics: Dict[str, Any] = Field(description="Analytics metrics")
    trends: Optional[Dict[str, List[Dict[str, Any]]]] = Field(default=None, description="Trend data")