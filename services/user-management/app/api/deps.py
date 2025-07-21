#!/usr/bin/env python3
"""
Dependency aliases for the AIMA User Management Service.

This module provides convenient aliases for commonly used dependencies.
"""

from .dependencies import (
    get_current_active_user,
    get_current_user,
    get_optional_current_user,
    get_db,
    require_role,
    require_permission,
    require_user_access,
    require_user_modify_access
)

__all__ = [
    "get_current_active_user",
    "get_current_user",
    "get_optional_current_user",
    "get_db",
    "require_role",
    "require_permission",
    "require_user_access",
    "require_user_modify_access"
]