#!/usr/bin/env python3
"""
Permissions module for the AIMA User Management Service.

This module contains permission checking functions and decorators.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.database import User
from app.models.schemas import UserRole


def require_role(required_role: UserRole):
    """Decorator to require a specific role or higher."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        # Role hierarchy: superadmin > admin > moderator > user
        role_hierarchy = {
            UserRole.USER: 0,
            UserRole.MODERATOR: 1,
            UserRole.ADMIN: 2,
            UserRole.SUPERADMIN: 3
        }
        
        user_role_level = role_hierarchy.get(current_user.role, 0)
        required_role_level = role_hierarchy.get(required_role, 0)
        
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}"
            )
        
        return current_user
    
    return role_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role or higher."""
    return require_role(UserRole.ADMIN)(current_user)


def require_moderator(current_user: User = Depends(get_current_user)) -> User:
    """Require moderator role or higher."""
    return require_role(UserRole.MODERATOR)(current_user)


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Require superadmin role."""
    return require_role(UserRole.SUPERADMIN)(current_user)


def check_user_access(target_user_id: str, current_user: User) -> bool:
    """Check if current user can access target user's data."""
    # Users can access their own data
    if str(current_user.id) == target_user_id:
        return True
    
    # Admins and above can access any user's data
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.MODERATOR: 1,
        UserRole.ADMIN: 2,
        UserRole.SUPERADMIN: 3
    }
    
    user_role_level = role_hierarchy.get(current_user.role, 0)
    return user_role_level >= role_hierarchy[UserRole.ADMIN]


def check_user_modification_access(target_user: User, current_user: User) -> bool:
    """Check if current user can modify target user's data."""
    # Users can modify their own data (limited)
    if target_user.id == current_user.id:
        return True
    
    # Role hierarchy check
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.MODERATOR: 1,
        UserRole.ADMIN: 2,
        UserRole.SUPERADMIN: 3
    }
    
    current_user_level = role_hierarchy.get(current_user.role, 0)
    target_user_level = role_hierarchy.get(target_user.role, 0)
    
    # Admins can modify users and moderators
    # Superadmins can modify anyone
    # Users cannot modify others
    # Moderators can modify users but not other moderators or admins
    
    if current_user_level >= role_hierarchy[UserRole.SUPERADMIN]:
        return True
    elif current_user_level >= role_hierarchy[UserRole.ADMIN]:
        return target_user_level < role_hierarchy[UserRole.ADMIN]
    elif current_user_level >= role_hierarchy[UserRole.MODERATOR]:
        return target_user_level < role_hierarchy[UserRole.MODERATOR]
    
    return False


def require_user_access(target_user_id: str):
    """Decorator to require access to a specific user's data."""
    def access_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if not check_user_access(target_user_id, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to user data"
            )
        return current_user
    
    return access_checker


def require_user_modification_access(target_user: User):
    """Decorator to require modification access to a specific user."""
    def modification_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not check_user_modification_access(target_user, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to modify user data"
            )
        return current_user
    
    return modification_checker


def is_admin_or_above(user: User) -> bool:
    """Check if user has admin role or above."""
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.MODERATOR: 1,
        UserRole.ADMIN: 2,
        UserRole.SUPERADMIN: 3
    }
    
    user_role_level = role_hierarchy.get(user.role, 0)
    return user_role_level >= role_hierarchy[UserRole.ADMIN]


def is_moderator_or_above(user: User) -> bool:
    """Check if user has moderator role or above."""
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.MODERATOR: 1,
        UserRole.ADMIN: 2,
        UserRole.SUPERADMIN: 3
    }
    
    user_role_level = role_hierarchy.get(user.role, 0)
    return user_role_level >= role_hierarchy[UserRole.MODERATOR]


def is_superadmin(user: User) -> bool:
    """Check if user has superadmin role."""
    return user.role == UserRole.SUPERADMIN