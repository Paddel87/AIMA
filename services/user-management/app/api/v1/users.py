#!/usr/bin/env python3
"""
User management API routes for the AIMA User Management Service.

This module handles user CRUD operations, profile management,
and user administration endpoints.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import structlog

from app.core.database import get_db, User
from app.core.exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    BusinessLogicError,
    get_http_status_code
)
from app.models.schemas import (
    UserCreate,
    UserUpdate,
    UserAdminUpdate,
    UserResponse,
    UserListResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    UserStatsResponse,
    SuccessResponse,
    UserRole,
    UserStatus,
    UserFilterParams
)
from app.services.user_service import UserService
from app.api.dependencies import (
    get_current_active_user,
    require_admin,
    require_user_management,
    require_user_access,
    require_user_modify_access,
    validate_uuid,
    get_pagination_params
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def get_client_info(request: Request) -> dict:
    """Extract client information from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user (admin only)"
)
async def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_management)
):
    """Create a new user."""
    try:
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        user = await user_service.create_user(
            user_data=user_data,
            created_by=str(current_user.id),
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except (UserAlreadyExistsError, InsufficientPermissionsError) as e:
        logger.warning(
            "User creation failed",
            username=user_data.username,
            email=user_data.email,
            error=e.error_code,
            created_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "User creation error",
            username=user_data.username,
            error=str(e),
            created_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during user creation"
            }
        )


@router.get(
    "/",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users",
    description="Get paginated list of users with filtering options"
)
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_management),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    status: Optional[UserStatus] = Query(None, description="Filter by status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex=r"^(asc|desc)$", description="Sort order")
):
    """Get paginated list of users with filtering."""
    try:
        # Build query
        query = db.query(User)
        
        # Apply filters
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.full_name.ilike(search_term)
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if status:
            query = query.filter(User.status == status)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if sort_by and hasattr(User, sort_by):
            sort_column = getattr(User, sort_by)
            if sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(User.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * per_page
        users = query.offset(offset).limit(per_page).all()
        
        # Calculate pagination info
        pages = (total + per_page - 1) // per_page
        
        # Convert to response models
        user_responses = [
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                status=user.status,
                last_login=user.last_login,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            for user in users
        ]
        
        return UserListResponse(
            users=user_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(
            "User list error",
            error=str(e),
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred while fetching users"
            }
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user",
    description="Get user by ID"
)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user by ID."""
    try:
        # Validate UUID format
        validate_uuid(user_id, "user_id")
        
        # Check access permissions
        from app.core.security import permission_checker
        can_access = permission_checker.can_access_user_data(
            requester_role=current_user.role,
            requester_id=str(current_user.id),
            target_user_id=user_id
        )
        
        if not can_access:
            raise InsufficientPermissionsError(
                "read:user_profiles",
                current_user.role
            )
        
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except (UserNotFoundError, InsufficientPermissionsError) as e:
        logger.warning(
            "User access failed",
            user_id=user_id,
            error=e.error_code,
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Get user error",
            user_id=user_id,
            error=str(e),
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred while fetching user"
            }
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user",
    description="Update user information"
)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user information."""
    try:
        # Validate UUID format
        validate_uuid(user_id, "user_id")
        
        # Check modify permissions
        from app.core.security import permission_checker
        can_modify = permission_checker.can_modify_user_data(
            requester_role=current_user.role,
            requester_id=str(current_user.id),
            target_user_id=user_id
        )
        
        if not can_modify:
            raise InsufficientPermissionsError(
                "manage:users",
                current_user.role
            )
        
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        user = await user_service.update_user(
            user_id=user_id,
            user_data=user_data,
            updated_by=str(current_user.id),
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except (UserNotFoundError, UserAlreadyExistsError, InsufficientPermissionsError) as e:
        logger.warning(
            "User update failed",
            user_id=user_id,
            error=e.error_code,
            updated_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "User update error",
            user_id=user_id,
            error=str(e),
            updated_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during user update"
            }
        )


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete user",
    description="Delete user (soft delete)"
)
async def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_management)
):
    """Delete user (soft delete)."""
    try:
        # Validate UUID format
        validate_uuid(user_id, "user_id")
        
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        await user_service.delete_user(
            user_id=user_id,
            deleted_by=str(current_user.id),
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        return SuccessResponse(
            message="User deleted successfully",
            data={"user_id": user_id}
        )
        
    except (UserNotFoundError, BusinessLogicError, InsufficientPermissionsError) as e:
        logger.warning(
            "User deletion failed",
            user_id=user_id,
            error=e.error_code,
            deleted_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "User deletion error",
            user_id=user_id,
            error=str(e),
            deleted_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during user deletion"
            }
        )


@router.get(
    "/{user_id}/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user profile",
    description="Get detailed user profile information"
)
async def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed user profile."""
    try:
        # Validate UUID format
        validate_uuid(user_id, "user_id")
        
        # Check access permissions
        from app.core.security import permission_checker
        can_access = permission_checker.can_access_user_data(
            requester_role=current_user.role,
            requester_id=str(current_user.id),
            target_user_id=user_id
        )
        
        if not can_access:
            raise InsufficientPermissionsError(
                "read:user_profiles",
                current_user.role
            )
        
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        
        return ProfileResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
            login_count=user.login_count,
            failed_login_attempts=user.failed_login_attempts,
            account_locked_until=user.account_locked_until,
            password_changed_at=user.password_changed_at,
            email_verified=user.email_verified,
            two_factor_enabled=user.two_factor_enabled
        )
        
    except (UserNotFoundError, InsufficientPermissionsError) as e:
        logger.warning(
            "Profile access failed",
            user_id=user_id,
            error=e.error_code,
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Get profile error",
            user_id=user_id,
            error=str(e),
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred while fetching profile"
            }
        )


@router.put(
    "/{user_id}/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user profile",
    description="Update user profile information"
)
async def update_user_profile(
    user_id: str,
    profile_data: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user profile."""
    try:
        # Validate UUID format
        validate_uuid(user_id, "user_id")
        
        # Check modify permissions (users can modify their own profile)
        from app.core.security import permission_checker
        can_modify = permission_checker.can_modify_user_data(
            requester_role=current_user.role,
            requester_id=str(current_user.id),
            target_user_id=user_id
        )
        
        if not can_modify:
            raise InsufficientPermissionsError(
                "update:own_profile" if str(current_user.id) == user_id else "manage:users",
                current_user.role
            )
        
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        # Convert profile update to user update
        user_update = UserUpdate(
            email=profile_data.email,
            full_name=profile_data.full_name
        )
        
        user = await user_service.update_user(
            user_id=user_id,
            user_data=user_update,
            updated_by=str(current_user.id),
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        return ProfileResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
            login_count=user.login_count,
            failed_login_attempts=user.failed_login_attempts,
            account_locked_until=user.account_locked_until,
            password_changed_at=user.password_changed_at,
            email_verified=user.email_verified,
            two_factor_enabled=user.two_factor_enabled
        )
        
    except (UserNotFoundError, UserAlreadyExistsError, InsufficientPermissionsError) as e:
        logger.warning(
            "Profile update failed",
            user_id=user_id,
            error=e.error_code,
            updated_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Profile update error",
            user_id=user_id,
            error=str(e),
            updated_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during profile update"
            }
        )


@router.get(
    "/stats/overview",
    response_model=UserStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user statistics",
    description="Get user statistics overview (admin only)"
)
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get user statistics overview."""
    try:
        # Get total counts
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = db.query(User).filter(User.is_active == False).count()
        
        # Get counts by status
        suspended_users = db.query(User).filter(User.status == UserStatus.SUSPENDED).count()
        pending_users = db.query(User).filter(User.status == UserStatus.PENDING).count()
        
        # Get counts by role
        users_by_role = {}
        for role in UserRole:
            count = db.query(User).filter(User.role == role).count()
            users_by_role[role.value] = count
        
        # Get new user counts (placeholder - would need proper date filtering)
        new_users_today = 0
        new_users_this_week = 0
        new_users_this_month = 0
        
        # Get login stats (placeholder)
        login_stats = {
            "total_logins": db.query(func.sum(User.login_count)).scalar() or 0,
            "users_logged_in_today": 0,
            "users_logged_in_this_week": 0,
            "users_logged_in_this_month": 0
        }
        
        return UserStatsResponse(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            suspended_users=suspended_users,
            pending_users=pending_users,
            users_by_role=users_by_role,
            new_users_today=new_users_today,
            new_users_this_week=new_users_this_week,
            new_users_this_month=new_users_this_month,
            login_stats=login_stats
        )
        
    except Exception as e:
        logger.error(
            "User stats error",
            error=str(e),
            requested_by=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred while fetching user statistics"
            }
        )