#!/usr/bin/env python3
"""
Pydantic schemas for the AIMA Configuration Management Service.

This module defines the request/response models for the API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConfigDataType(str, Enum):
    """Configuration data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    ARRAY = "array"


class ConfigCategory(str, Enum):
    """Configuration categories."""
    SYSTEM = "system"
    FEATURE_FLAGS = "feature_flags"
    MODELS = "models"
    GPU_PROVIDERS = "gpu_providers"
    ANALYSIS = "analysis"
    SECURITY = "security"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class ChangeType(str, Enum):
    """Configuration change types."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


# Configuration Item Schemas
class ConfigurationItemBase(BaseSchema):
    """Base configuration item schema."""
    key: str = Field(..., min_length=1, max_length=255, description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    data_type: ConfigDataType = Field(..., description="Data type of the configuration value")
    category: ConfigCategory = Field(..., description="Configuration category")
    description: Optional[str] = Field(None, description="Configuration description")
    is_sensitive: bool = Field(default=False, description="Whether the configuration contains sensitive data")
    is_readonly: bool = Field(default=False, description="Whether the configuration is read-only")
    validation_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for validation")
    default_value: Optional[Any] = Field(None, description="Default value")


class ConfigurationItemCreate(ConfigurationItemBase):
    """Schema for creating a configuration item."""
    created_by: Optional[str] = Field(None, description="User ID who created this configuration")


class ConfigurationItemUpdate(BaseSchema):
    """Schema for updating a configuration item."""
    value: Optional[Any] = Field(None, description="New configuration value")
    description: Optional[str] = Field(None, description="Updated description")
    is_sensitive: Optional[bool] = Field(None, description="Updated sensitivity flag")
    validation_schema: Optional[Dict[str, Any]] = Field(None, description="Updated validation schema")
    updated_by: Optional[str] = Field(None, description="User ID who updated this configuration")
    change_reason: Optional[str] = Field(None, description="Reason for the change")


class ConfigurationItemResponse(ConfigurationItemBase):
    """Schema for configuration item response."""
    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]
    
    @validator('value', pre=True)
    def mask_sensitive_value(cls, v, values):
        """Mask sensitive configuration values."""
        if values.get('is_sensitive', False):
            return "***MASKED***"
        return v


class ConfigurationItemFullResponse(ConfigurationItemBase):
    """Schema for full configuration item response (admin only)."""
    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]


# Configuration History Schemas
class ConfigurationHistoryResponse(BaseSchema):
    """Schema for configuration history response."""
    id: int
    config_key: str
    old_value: Optional[Any]
    new_value: Any
    change_type: ChangeType
    changed_by: Optional[str]
    change_reason: Optional[str]
    changed_at: datetime
    version_before: Optional[int]
    version_after: int


# Configuration Template Schemas
class ConfigurationTemplateBase(BaseSchema):
    """Base configuration template schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    template_data: Dict[str, Any] = Field(..., description="Template configuration data")
    category: ConfigCategory = Field(..., description="Template category")
    is_active: bool = Field(default=True, description="Whether the template is active")


class ConfigurationTemplateCreate(ConfigurationTemplateBase):
    """Schema for creating a configuration template."""
    created_by: Optional[str] = Field(None, description="User ID who created this template")


class ConfigurationTemplateUpdate(BaseSchema):
    """Schema for updating a configuration template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated template name")
    description: Optional[str] = Field(None, description="Updated description")
    template_data: Optional[Dict[str, Any]] = Field(None, description="Updated template data")
    is_active: Optional[bool] = Field(None, description="Updated active status")


class ConfigurationTemplateResponse(ConfigurationTemplateBase):
    """Schema for configuration template response."""
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]


# Bulk Operations Schemas
class BulkConfigurationUpdate(BaseSchema):
    """Schema for bulk configuration updates."""
    configurations: List[Dict[str, Any]] = Field(..., description="List of configuration updates")
    updated_by: Optional[str] = Field(None, description="User ID performing the bulk update")
    change_reason: Optional[str] = Field(None, description="Reason for the bulk change")


class BulkConfigurationResponse(BaseSchema):
    """Schema for bulk configuration response."""
    success_count: int = Field(..., description="Number of successful updates")
    error_count: int = Field(..., description="Number of failed updates")
    errors: List[Dict[str, str]] = Field(default=[], description="List of errors")


# Query Schemas
class ConfigurationQuery(BaseSchema):
    """Schema for configuration queries."""
    category: Optional[ConfigCategory] = Field(None, description="Filter by category")
    key_pattern: Optional[str] = Field(None, description="Filter by key pattern (supports wildcards)")
    include_sensitive: bool = Field(default=False, description="Include sensitive configurations")
    include_readonly: bool = Field(default=True, description="Include read-only configurations")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")


class ConfigurationListResponse(BaseSchema):
    """Schema for configuration list response."""
    items: List[ConfigurationItemResponse]
    total: int = Field(..., description="Total number of configurations")
    limit: int = Field(..., description="Applied limit")
    offset: int = Field(..., description="Applied offset")


# System Schemas
class HealthCheckResponse(BaseSchema):
    """Schema for health check response."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="Service version")
    uptime_seconds: int = Field(..., description="Service uptime in seconds")
    checks: Dict[str, Any] = Field(..., description="Detailed health checks")


class MetricsResponse(BaseSchema):
    """Schema for metrics response."""
    total_configurations: int = Field(..., description="Total number of configurations")
    configurations_by_category: Dict[str, int] = Field(..., description="Configurations grouped by category")
    recent_changes: int = Field(..., description="Number of recent changes (last 24h)")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")


# Error Schemas
class ErrorResponse(BaseSchema):
    """Schema for error responses."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")