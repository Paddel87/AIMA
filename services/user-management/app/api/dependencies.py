#!/usr/bin/env python3
"""
API dependencies for the AIMA User Management Service.

This module provides dependency injection functions for authentication,
authorization, and other common API requirements.
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db, User
from app.core.security import jwt_manager, permission_checker
from app.core.exceptions import (
    TokenError,
    UserNotFoundError,
    AccountDisabledError,
    InsufficientPermissionsError,
    get_http_status_code
)
from app.models.schemas import UserRole

logger = structlog.get_logger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    try:
        # Decode JWT token
        payload = jwt_manager.decode_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise TokenError("Invalid token payload")
        
        # Get user from database
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        
        if not user:
            raise UserNotFoundError(user_id)
        
        return user
        
    except (TokenError, UserNotFoundError) as e:
        logger.warning(
            "Authentication failed",
            error=e.error_code,
            token=credentials.credentials[:10] + "..."
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except ValueError as e:
        logger.warning(
            "Invalid user ID format",
            error=str(e),
            token=credentials.credentials[:10] + "..."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "INVALID_TOKEN",
                "message": "Invalid token format"
            }
        )
    except Exception as e:
        logger.error(
            "Authentication error",
            error=str(e),
            token=credentials.credentials[:10] + "..."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during authentication"
            }
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current authenticated and active user."""
    try:
        if not current_user.is_active:
            raise AccountDisabledError(str(current_user.id))
        
        return current_user
        
    except AccountDisabledError as e:
        logger.warning(
            "Inactive user attempted access",
            user_id=str(current_user.id),
            username=current_user.username
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )


def require_role(required_role: UserRole):
    """Dependency factory for role-based access control."""
    async def check_role(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        try:
            if not permission_checker.has_role_level(current_user.role, required_role):
                raise InsufficientPermissionsError(
                    f"role:{required_role}",
                    current_user.role
                )
            
            return current_user
            
        except InsufficientPermissionsError as e:
            logger.warning(
                "Insufficient role level",
                user_id=str(current_user.id),
                username=current_user.username,
                user_role=current_user.role,
                required_role=required_role
            )
            raise HTTPException(
                status_code=get_http_status_code(e),
                detail=e.to_dict()
            )
    
    return check_role


def require_permission(required_permission: str):
    """Dependency factory for permission-based access control."""
    async def check_permission(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        try:
            if not permission_checker.has_permission(current_user.role, required_permission):
                raise InsufficientPermissionsError(
                    required_permission,
                    current_user.role
                )
            
            return current_user
            
        except InsufficientPermissionsError as e:
            logger.warning(
                "Insufficient permissions",
                user_id=str(current_user.id),
                username=current_user.username,
                user_role=current_user.role,
                required_permission=required_permission
            )
            raise HTTPException(
                status_code=get_http_status_code(e),
                detail=e.to_dict()
            )
    
    return check_permission


def require_user_access(allow_self: bool = True):
    """Dependency factory for user data access control."""
    async def check_user_access(
        target_user_id: str,
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        try:
            # Check if user can access the target user's data
            can_access = permission_checker.can_access_user_data(
                requester_role=current_user.role,
                requester_id=str(current_user.id),
                target_user_id=target_user_id
            )
            
            if not can_access:
                if allow_self and str(current_user.id) == target_user_id:
                    return current_user
                
                raise InsufficientPermissionsError(
                    "read:user_profiles",
                    current_user.role
                )
            
            return current_user
            
        except InsufficientPermissionsError as e:
            logger.warning(
                "Insufficient permissions for user data access",
                user_id=str(current_user.id),
                username=current_user.username,
                target_user_id=target_user_id,
                user_role=current_user.role
            )
            raise HTTPException(
                status_code=get_http_status_code(e),
                detail=e.to_dict()
            )
    
    return check_user_access


def require_user_modify_access():
    """Dependency factory for user data modification access control."""
    async def check_user_modify_access(
        target_user_id: str,
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        try:
            # Check if user can modify the target user's data
            can_modify = permission_checker.can_modify_user_data(
                requester_role=current_user.role,
                requester_id=str(current_user.id),
                target_user_id=target_user_id
            )
            
            if not can_modify:
                raise InsufficientPermissionsError(
                    "manage:users",
                    current_user.role
                )
            
            return current_user
            
        except InsufficientPermissionsError as e:
            logger.warning(
                "Insufficient permissions for user data modification",
                user_id=str(current_user.id),
                username=current_user.username,
                target_user_id=target_user_id,
                user_role=current_user.role
            )
            raise HTTPException(
                status_code=get_http_status_code(e),
                detail=e.to_dict()
            )
    
    return check_user_modify_access


# Pre-defined dependency instances for common roles
require_admin = require_role(UserRole.ADMIN)
require_moderator = require_role(UserRole.MODERATOR)
require_superadmin = require_role(UserRole.SUPERADMIN)

# Pre-defined dependency instances for common permissions
require_user_management = require_permission("manage:users")
require_system_config = require_permission("read:system_config")
require_system_config_update = require_permission("update:system_config")


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def validate_uuid(uuid_string: str, field_name: str = "ID") -> str:
    """Validate UUID format and return the string."""
    try:
        uuid.UUID(uuid_string)
        return uuid_string
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_UUID",
                "message": f"Invalid {field_name} format",
                "details": {"field": field_name, "value": uuid_string}
            }
        )


def get_pagination_params(
    page: int = 1,
    per_page: int = 20,
    sort_by: Optional[str] = None,
    sort_order: str = "asc"
) -> dict:
    """Get and validate pagination parameters."""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_PAGINATION",
                "message": "Page number must be greater than 0",
                "details": {"page": page}
            }
        )
    
    if per_page < 1 or per_page > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_PAGINATION",
                "message": "Per page must be between 1 and 100",
                "details": {"per_page": per_page}
            }
        )
    
    if sort_order not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_SORT_ORDER",
                "message": "Sort order must be 'asc' or 'desc'",
                "details": {"sort_order": sort_order}
            }
        )
    
    return {
        "page": page,
        "per_page": per_page,
        "sort_by": sort_by,
        "sort_order": sort_order
    }


class RateLimitChecker:
    """Rate limiting dependency."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def __call__(self, request, current_user: Optional[User] = Depends(get_optional_current_user)):
        """Check rate limit for the current user or IP."""
        # In a real implementation, you would check rate limits using Redis
        # For now, this is a placeholder
        
        identifier = str(current_user.id) if current_user else request.client.host
        
        # TODO: Implement actual rate limiting logic with Redis
        # For now, just log the request
        logger.debug(
            "Rate limit check",
            identifier=identifier,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds
        )
        
        return True


# Pre-defined rate limiters
login_rate_limiter = RateLimitChecker(max_requests=5, window_seconds=300)  # 5 attempts per 5 minutes
api_rate_limiter = RateLimitChecker(max_requests=100, window_seconds=60)   # 100 requests per minute