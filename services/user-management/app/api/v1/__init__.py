#!/usr/bin/env python3
"""
API v1 package for the AIMA User Management Service.

This package contains all v1 API routes and endpoints.
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .admin import router as admin_router
from .health import router as health_router

# Create main API router for v1
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_router.include_router(health_router)

__all__ = ["api_router"]