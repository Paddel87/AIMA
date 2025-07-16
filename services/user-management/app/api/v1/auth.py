#!/usr/bin/env python3
"""
Authentication API routes for the AIMA User Management Service.

This module handles authentication-related endpoints including login, logout,
token refresh, and password management.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.core.security import jwt_manager, validate_password_strength
from app.core.redis import session_manager
from app.core.exceptions import (
    InvalidCredentialsError,
    AccountDisabledError,
    AccountLockedError,
    PasswordExpiredError,
    TokenError,
    SessionNotFoundError,
    WeakPasswordError,
    get_http_status_code
)
from app.models.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordStrengthResponse,
    SuccessResponse,
    ErrorResponse,
    UserResponse
)
from app.services.user_service import UserService
from app.api.dependencies import get_current_user, get_current_active_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


def get_client_info(request: Request) -> Dict[str, Any]:
    """Extract client information from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user with username/email and password"
)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access and refresh tokens."""
    try:
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        user, access_token, refresh_token = await user_service.authenticate_user(
            username=login_data.username,
            password=login_data.password,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        # Calculate token expiration
        expires_in = jwt_manager.access_token_expire_minutes * 60
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse(
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
        )
        
    except (InvalidCredentialsError, AccountDisabledError, 
            AccountLockedError, PasswordExpiredError) as e:
        logger.warning(
            "Authentication failed",
            username=login_data.username,
            error=e.error_code,
            ip_address=client_info["ip_address"]
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Login error",
            username=login_data.username,
            error=str(e),
            ip_address=client_info["ip_address"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during login"
            }
        )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Get a new access token using a refresh token"
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request
):
    """Refresh access token using refresh token."""
    try:
        client_info = get_client_info(request)
        
        # Create new access token from refresh token
        access_token = jwt_manager.refresh_access_token(refresh_data.refresh_token)
        
        # Calculate token expiration
        expires_in = jwt_manager.access_token_expire_minutes * 60
        
        logger.debug(
            "Token refreshed successfully",
            ip_address=client_info["ip_address"]
        )
        
        return RefreshTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in
        )
        
    except TokenError as e:
        logger.warning(
            "Token refresh failed",
            error=e.error_code,
            ip_address=client_info["ip_address"]
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Token refresh error",
            error=str(e),
            ip_address=client_info["ip_address"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during token refresh"
            }
        )


@router.post(
    "/logout",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="Logout user and invalidate session"
)
async def logout(
    logout_data: LogoutRequest,
    request: Request,
    current_user = Depends(get_current_active_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Logout user and invalidate session(s)."""
    try:
        client_info = get_client_info(request)
        
        if logout_data.all_sessions:
            # Invalidate all user sessions
            deleted_count = await session_manager.delete_user_sessions(str(current_user.id))
            message = f"All sessions logged out ({deleted_count} sessions)"
        else:
            # Invalidate current session only
            # Extract session token from JWT or use a different method
            # For now, we'll invalidate all sessions as we don't have session token in JWT
            deleted_count = await session_manager.delete_user_sessions(str(current_user.id))
            message = "Current session logged out"
        
        logger.info(
            "User logged out",
            user_id=str(current_user.id),
            username=current_user.username,
            all_sessions=logout_data.all_sessions,
            ip_address=client_info["ip_address"]
        )
        
        return SuccessResponse(
            message=message,
            data={"sessions_invalidated": deleted_count}
        )
        
    except Exception as e:
        logger.error(
            "Logout error",
            user_id=str(current_user.id),
            error=str(e),
            ip_address=client_info["ip_address"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during logout"
            }
        )


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change user password"
)
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user password."""
    try:
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        await user_service.change_password(
            user_id=str(current_user.id),
            password_data=password_data,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        return SuccessResponse(
            message="Password changed successfully",
            data={"user_id": str(current_user.id)}
        )
        
    except (InvalidCredentialsError, WeakPasswordError) as e:
        logger.warning(
            "Password change failed",
            user_id=str(current_user.id),
            error=e.error_code
        )
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(
            "Password change error",
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during password change"
            }
        )


@router.post(
    "/request-password-reset",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Request a password reset token via email"
)
async def request_password_reset(
    reset_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request password reset token."""
    try:
        client_info = get_client_info(request)
        user_service = UserService(db)
        
        # Try to find user by email
        try:
            user = await user_service.get_user_by_email(reset_data.email)
            
            # Generate reset token (in a real implementation, this would be sent via email)
            # For now, we'll just log it
            reset_token = "password_reset_token_placeholder"
            
            logger.info(
                "Password reset requested",
                user_id=str(user.id),
                email=reset_data.email,
                ip_address=client_info["ip_address"]
            )
            
        except Exception:
            # Don't reveal if email exists or not for security reasons
            logger.info(
                "Password reset requested for non-existent email",
                email=reset_data.email,
                ip_address=client_info["ip_address"]
            )
        
        # Always return success to prevent email enumeration
        return SuccessResponse(
            message="If the email address exists, a password reset link has been sent",
            data={"email": reset_data.email}
        )
        
    except Exception as e:
        logger.error(
            "Password reset request error",
            email=reset_data.email,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during password reset request"
            }
        )


@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset password using reset token"
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reset password using reset token."""
    try:
        client_info = get_client_info(request)
        
        # In a real implementation, you would validate the reset token
        # and find the associated user
        
        # For now, return a placeholder response
        logger.info(
            "Password reset attempted",
            token=reset_data.token[:8] + "...",
            ip_address=client_info["ip_address"]
        )
        
        return SuccessResponse(
            message="Password reset functionality not yet implemented",
            data={"token": reset_data.token[:8] + "..."}
        )
        
    except Exception as e:
        logger.error(
            "Password reset error",
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during password reset"
            }
        )


@router.post(
    "/validate-password",
    response_model=PasswordStrengthResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate password strength",
    description="Check password strength and return validation results"
)
async def validate_password(
    password: str
):
    """Validate password strength."""
    try:
        validation_result = validate_password_strength(password)
        
        return PasswordStrengthResponse(
            is_valid=validation_result["is_valid"],
            strength=validation_result["strength"],
            score=validation_result["score"],
            issues=validation_result["issues"]
        )
        
    except Exception as e:
        logger.error("Password validation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred during password validation"
            }
        )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get current authenticated user information"
)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        status=current_user.status,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@router.get(
    "/verify-token",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Verify token",
    description="Verify if the current token is valid"
)
async def verify_token(
    current_user = Depends(get_current_user)
):
    """Verify if token is valid and return token info."""
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role,
        "timestamp": datetime.utcnow().isoformat()
    }