#!/usr/bin/env python3
"""
Custom exceptions for the AIMA User Management Service.

This module defines all custom exceptions used throughout the service.
"""

from typing import Any, Dict, Optional


class AIMAException(Exception):
    """Base exception for all AIMA-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ValidationError(AIMAException):
    """Raised when input validation fails."""
    pass


class AuthenticationError(AIMAException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(AIMAException):
    """Raised when authorization fails."""
    pass


class TokenError(AIMAException):
    """Raised when token operations fail."""
    pass


class UserNotFoundError(AIMAException):
    """Raised when a user is not found."""
    
    def __init__(self, user_identifier: str):
        super().__init__(
            f"User not found: {user_identifier}",
            "USER_NOT_FOUND",
            {"user_identifier": user_identifier}
        )


class UserAlreadyExistsError(AIMAException):
    """Raised when trying to create a user that already exists."""
    
    def __init__(self, field: str, value: str):
        super().__init__(
            f"User with {field} '{value}' already exists",
            "USER_ALREADY_EXISTS",
            {"field": field, "value": value}
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""
    
    def __init__(self):
        super().__init__(
            "Invalid username or password",
            "INVALID_CREDENTIALS"
        )


class AccountDisabledError(AuthenticationError):
    """Raised when trying to authenticate with a disabled account."""
    
    def __init__(self, user_id: str):
        super().__init__(
            "Account is disabled",
            "ACCOUNT_DISABLED",
            {"user_id": user_id}
        )


class AccountLockedError(AuthenticationError):
    """Raised when trying to authenticate with a locked account."""
    
    def __init__(self, user_id: str, unlock_time: Optional[str] = None):
        super().__init__(
            "Account is temporarily locked",
            "ACCOUNT_LOCKED",
            {"user_id": user_id, "unlock_time": unlock_time}
        )


class PasswordExpiredError(AuthenticationError):
    """Raised when password has expired."""
    
    def __init__(self, user_id: str):
        super().__init__(
            "Password has expired and must be changed",
            "PASSWORD_EXPIRED",
            {"user_id": user_id}
        )


class WeakPasswordError(ValidationError):
    """Raised when password doesn't meet strength requirements."""
    
    def __init__(self, issues: list):
        super().__init__(
            "Password does not meet security requirements",
            "WEAK_PASSWORD",
            {"issues": issues}
        )


class InvalidTokenError(TokenError):
    """Raised when a token is invalid or malformed."""
    
    def __init__(self, token_type: str = "token"):
        super().__init__(
            f"Invalid {token_type}",
            "INVALID_TOKEN",
            {"token_type": token_type}
        )


class ExpiredTokenError(TokenError):
    """Raised when a token has expired."""
    
    def __init__(self, token_type: str = "token"):
        super().__init__(
            f"{token_type.title()} has expired",
            "EXPIRED_TOKEN",
            {"token_type": token_type}
        )


class SessionNotFoundError(AIMAException):
    """Raised when a session is not found."""
    
    def __init__(self, session_token: str):
        super().__init__(
            "Session not found or expired",
            "SESSION_NOT_FOUND",
            {"session_token": session_token[:8] + "..."}
        )


class SessionExpiredError(AIMAException):
    """Raised when a session has expired."""
    
    def __init__(self, session_token: str):
        super().__init__(
            "Session has expired",
            "SESSION_EXPIRED",
            {"session_token": session_token[:8] + "..."}
        )


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, required_permission: str, user_role: str):
        super().__init__(
            f"Insufficient permissions. Required: {required_permission}",
            "INSUFFICIENT_PERMISSIONS",
            {
                "required_permission": required_permission,
                "user_role": user_role
            }
        )


class RoleNotFoundError(AIMAException):
    """Raised when a role is not found."""
    
    def __init__(self, role: str):
        super().__init__(
            f"Role not found: {role}",
            "ROLE_NOT_FOUND",
            {"role": role}
        )


class DatabaseError(AIMAException):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, details: Optional[str] = None):
        super().__init__(
            f"Database operation failed: {operation}",
            "DATABASE_ERROR",
            {"operation": operation, "details": details}
        )


class RedisError(AIMAException):
    """Raised when Redis operations fail."""
    
    def __init__(self, operation: str, details: Optional[str] = None):
        super().__init__(
            f"Redis operation failed: {operation}",
            "REDIS_ERROR",
            {"operation": operation, "details": details}
        )


class MessagingError(AIMAException):
    """Raised when messaging operations fail."""
    
    def __init__(self, operation: str, details: Optional[str] = None):
        super().__init__(
            f"Messaging operation failed: {operation}",
            "MESSAGING_ERROR",
            {"operation": operation, "details": details}
        )


class ConfigurationError(AIMAException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, setting: str, details: Optional[str] = None):
        super().__init__(
            f"Configuration error: {setting}",
            "CONFIGURATION_ERROR",
            {"setting": setting, "details": details}
        )


class RateLimitExceededError(AIMAException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: str, retry_after: Optional[int] = None):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window}",
            "RATE_LIMIT_EXCEEDED",
            {
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            }
        )


class ServiceUnavailableError(AIMAException):
    """Raised when a service is temporarily unavailable."""
    
    def __init__(self, service: str, details: Optional[str] = None):
        super().__init__(
            f"Service temporarily unavailable: {service}",
            "SERVICE_UNAVAILABLE",
            {"service": service, "details": details}
        )


class ExternalServiceError(AIMAException):
    """Raised when external service calls fail."""
    
    def __init__(self, service: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(
            f"External service error: {service}",
            "EXTERNAL_SERVICE_ERROR",
            {
                "service": service,
                "status_code": status_code,
                "details": details
            }
        )


class DataIntegrityError(AIMAException):
    """Raised when data integrity constraints are violated."""
    
    def __init__(self, constraint: str, details: Optional[str] = None):
        super().__init__(
            f"Data integrity violation: {constraint}",
            "DATA_INTEGRITY_ERROR",
            {"constraint": constraint, "details": details}
        )


class BusinessLogicError(AIMAException):
    """Raised when business logic rules are violated."""
    
    def __init__(self, rule: str, details: Optional[str] = None):
        super().__init__(
            f"Business logic violation: {rule}",
            "BUSINESS_LOGIC_ERROR",
            {"rule": rule, "details": details}
        )


class MaintenanceModeError(AIMAException):
    """Raised when system is in maintenance mode."""
    
    def __init__(self, estimated_duration: Optional[str] = None):
        super().__init__(
            "System is currently in maintenance mode",
            "MAINTENANCE_MODE",
            {"estimated_duration": estimated_duration}
        )


# Exception mapping for HTTP status codes
HTTP_EXCEPTION_MAP = {
    ValidationError: 400,
    WeakPasswordError: 400,
    UserAlreadyExistsError: 409,
    AuthenticationError: 401,
    InvalidCredentialsError: 401,
    AccountDisabledError: 401,
    AccountLockedError: 423,
    PasswordExpiredError: 401,
    TokenError: 401,
    InvalidTokenError: 401,
    ExpiredTokenError: 401,
    SessionNotFoundError: 401,
    SessionExpiredError: 401,
    AuthorizationError: 403,
    InsufficientPermissionsError: 403,
    UserNotFoundError: 404,
    RoleNotFoundError: 404,
    RateLimitExceededError: 429,
    ServiceUnavailableError: 503,
    MaintenanceModeError: 503,
    DatabaseError: 500,
    RedisError: 500,
    MessagingError: 500,
    ConfigurationError: 500,
    ExternalServiceError: 502,
    DataIntegrityError: 500,
    BusinessLogicError: 422,
    AIMAException: 500
}


def get_http_status_code(exception: Exception) -> int:
    """Get HTTP status code for an exception."""
    for exc_type, status_code in HTTP_EXCEPTION_MAP.items():
        if isinstance(exception, exc_type):
            return status_code
    return 500