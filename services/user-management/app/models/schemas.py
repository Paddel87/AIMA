#!/usr/bin/env python3
"""
Pydantic schemas for the AIMA User Management Service.

This module defines all request and response models for the API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, validator
from pydantic.types import UUID4


class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AuditAction(str, Enum):
    """Audit action enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ROLE_CHANGE = "role_change"
    ACCOUNT_LOCK = "account_lock"
    ACCOUNT_UNLOCK = "account_unlock"


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        orm_mode = True
        use_enum_values = True
        validate_assignment = True
        allow_population_by_field_name = True


# User schemas
class UserBase(BaseSchema):
    """Base user schema with common fields."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must contain only letters, numbers, hyphens, and underscores')
        return v.lower()


class UserUpdate(BaseSchema):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    
    @validator('full_name')
    def validate_full_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Full name cannot be empty')
        return v.strip() if v else None


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID4
    status: UserStatus
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config(BaseSchema.Config):
        fields = {
            'id': 'user_id'
        }


class UserListResponse(BaseSchema):
    """Schema for paginated user list response."""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


# Authentication schemas
class LoginRequest(BaseSchema):
    """Schema for login request."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class LoginResponse(BaseSchema):
    """Schema for login response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseSchema):
    """Schema for refresh token request."""
    refresh_token: str


class RefreshTokenResponse(BaseSchema):
    """Schema for refresh token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseSchema):
    """Schema for logout request."""
    all_sessions: bool = False


# Password schemas
class PasswordChangeRequest(BaseSchema):
    """Schema for password change request."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordResetRequest(BaseSchema):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseSchema):
    """Schema for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordStrengthResponse(BaseSchema):
    """Schema for password strength validation response."""
    is_valid: bool
    strength: str
    score: int
    issues: List[str]


# Session schemas
class SessionResponse(BaseSchema):
    """Schema for session response."""
    id: UUID4
    user_id: UUID4
    session_token: str
    status: SessionStatus
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    expires_at: datetime


class SessionListResponse(BaseSchema):
    """Schema for session list response."""
    sessions: List[SessionResponse]
    total: int


# Profile schemas
class ProfileResponse(UserResponse):
    """Schema for user profile response with additional details."""
    login_count: int = 0
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    email_verified: bool = False
    two_factor_enabled: bool = False


class ProfileUpdateRequest(BaseSchema):
    """Schema for profile update request."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    
    @validator('full_name')
    def validate_full_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Full name cannot be empty')
        return v.strip() if v else None


# Admin schemas
class UserAdminUpdate(UserUpdate):
    """Schema for admin user updates with additional fields."""
    status: Optional[UserStatus] = None
    login_count: Optional[int] = None
    failed_login_attempts: Optional[int] = None
    account_locked_until: Optional[datetime] = None
    email_verified: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None


# Audit schemas
class AuditLogResponse(BaseSchema):
    """Schema for audit log response."""
    id: UUID4
    user_id: Optional[UUID4] = None
    action: AuditAction
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


class AuditLogListResponse(BaseSchema):
    """Schema for audit log list response."""
    logs: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


# Service status enumeration
class ServiceStatus(str, Enum):
    """Service status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# Health check schemas
class HealthCheckResponse(BaseSchema):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    service: str
    version: str
    details: Optional[Dict[str, Any]] = None


class ComponentHealth(BaseSchema):
    """Schema for component health status."""
    status: ServiceStatus
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class DetailedHealthCheckResponse(BaseSchema):
    """Schema for detailed health check response."""
    status: str
    timestamp: datetime
    service: str
    version: str
    components: Dict[str, ComponentHealth]
    details: Optional[Dict[str, Any]] = None


class ServiceHealthResponse(BaseSchema):
    """Schema for individual service health response."""
    status: str
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# Error schemas
class ErrorResponse(BaseSchema):
    """Schema for error responses."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorResponse(ErrorResponse):
    """Schema for validation error responses."""
    field_errors: Optional[Dict[str, List[str]]] = None


# Success schemas
class SuccessResponse(BaseSchema):
    """Schema for generic success responses."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Pagination schemas
class PaginationParams(BaseSchema):
    """Schema for pagination parameters."""
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field("asc", pattern=r"^(asc|desc)$", description="Sort order")


class UserFilterParams(PaginationParams):
    """Schema for user filtering parameters."""
    search: Optional[str] = Field(None, description="Search term for username, email, or full name")
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    status: Optional[UserStatus] = Field(None, description="Filter by user status")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    created_after: Optional[datetime] = Field(None, description="Filter users created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before this date")


# Statistics schemas
class UserStatsResponse(BaseSchema):
    """Schema for user statistics response."""
    total_users: int
    active_users: int
    inactive_users: int
    suspended_users: int
    pending_users: int
    users_by_role: Dict[str, int]
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int
    login_stats: Dict[str, int]


# Configuration schemas
class SystemConfigResponse(BaseSchema):
    """Schema for system configuration response."""
    password_policy: Dict[str, Any]
    session_settings: Dict[str, Any]
    security_settings: Dict[str, Any]
    feature_flags: Dict[str, bool]


class SystemConfigUpdate(BaseSchema):
    """Schema for system configuration update."""
    password_policy: Optional[Dict[str, Any]] = None
    session_settings: Optional[Dict[str, Any]] = None
    security_settings: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, bool]] = None


# Admin schemas
class AdminStatsResponse(BaseSchema):
    """Schema for admin statistics response."""
    user_stats: UserStatsResponse
    system_health: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]


class SystemHealthResponse(BaseSchema):
    """Schema for system health response."""
    status: str
    services: Dict[str, ServiceHealthResponse]
    uptime: float
    memory_usage: Dict[str, float]
    cpu_usage: float
    disk_usage: Dict[str, float]


class UserActivityResponse(BaseSchema):
    """Schema for user activity response."""
    user_id: UUID4
    username: str
    last_login: Optional[datetime]
    login_count: int
    failed_attempts: int
    recent_actions: List[AuditLogResponse]


class BulkUserActionRequest(BaseSchema):
    """Schema for bulk user action request."""
    user_ids: List[UUID4]
    action: str
    parameters: Optional[Dict[str, Any]] = None


class BulkUserActionResponse(BaseSchema):
    """Schema for bulk user action response."""
    success_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]