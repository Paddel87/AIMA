#!/usr/bin/env python3
"""
API package for the AIMA User Management Service.

This package contains all API routes, dependencies, and middleware.
"""

from .v1 import api_router

__all__ = ["api_router"]