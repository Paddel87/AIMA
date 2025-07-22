#!/usr/bin/env python3
"""
API dependencies for the AIMA Media Lifecycle Management Service.

This module provides dependency injection functions for authentication,
authorization, and other common API requirements.
"""

import jwt
from datetime import datetime
from typing import Dict, Any, List, Optional
from functools import wraps

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import structlog

from app.core.config import get_settings
from app.core.redis_client import get_cache, get_session_manager

logger = structlog.get_logger(__name__)
security = HTTPBearer()
settings = get_settings()


class AuthenticationError(Exception):
    """Authentication error."""
    pass


class AuthorizationError(Exception):
    """Authorization error."""
    pass


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current authenticated user from JWT token."""
    try:
        token = credentials.credentials
        
        # Try to get user from cache first
        cache = get_cache()
        cache_key = f"user_token:{token[:32]}"  # Use first 32 chars as cache key
        cached_user = await cache.get(cache_key)
        
        if cached_user:
            logger.debug("User retrieved from cache", user_id=cached_user.get("id"))
            return cached_user
        
        # Decode JWT token
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract user information from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify token with user management service
        user_data = await verify_token_with_user_service(token)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or token invalid",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Cache user data for 5 minutes
        await cache.set(cache_key, user_data, ttl=300)
        
        logger.debug("User authenticated successfully", user_id=user_data.get("id"))
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def verify_token_with_user_service(token: str) -> Optional[Dict[str, Any]]:
    """Verify token with user management service."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.USER_MANAGEMENT_URL}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return None
            else:
                logger.warning(
                    "Unexpected response from user service",
                    status_code=response.status_code,
                    response=response.text
                )
                return None
                
    except httpx.TimeoutException:
        logger.error("Timeout verifying token with user service")
        return None
    except Exception as e:
        logger.error("Error verifying token with user service", error=str(e))
        return None


async def get_user_permissions(user_id: str) -> List[str]:
    """Get user permissions from user management service."""
    try:
        cache = get_cache()
        cache_key = f"user_permissions:{user_id}"
        
        # Try cache first
        cached_permissions = await cache.get(cache_key)
        if cached_permissions:
            return cached_permissions
        
        # Fetch from user service
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.USER_MANAGEMENT_URL}/api/v1/users/{user_id}/permissions"
            )
            
            if response.status_code == 200:
                permissions = response.json().get("permissions", [])
                # Cache for 10 minutes
                await cache.set(cache_key, permissions, ttl=600)
                return permissions
            else:
                logger.warning(
                    "Failed to get user permissions",
                    user_id=user_id,
                    status_code=response.status_code
                )
                return []
                
    except Exception as e:
        logger.error("Error getting user permissions", user_id=user_id, error=str(e))
        return []


def require_permissions(required_permissions: List[str]):
    """Dependency factory for permission-based authorization."""
    async def check_permissions(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> None:
        """Check if user has required permissions."""
        try:
            user_id = current_user.get("id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user data"
                )
            
            # Get user permissions
            user_permissions = await get_user_permissions(str(user_id))
            
            # Check if user has all required permissions
            missing_permissions = []
            for permission in required_permissions:
                if permission not in user_permissions:
                    missing_permissions.append(permission)
            
            if missing_permissions:
                logger.warning(
                    "Access denied - missing permissions",
                    user_id=user_id,
                    required=required_permissions,
                    missing=missing_permissions
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {', '.join(missing_permissions)}"
                )
            
            logger.debug(
                "Permission check passed",
                user_id=user_id,
                permissions=required_permissions
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Permission check failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed"
            )
    
    return check_permissions


def require_roles(required_roles: List[str]):
    """Dependency factory for role-based authorization."""
    async def check_roles(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> None:
        """Check if user has required roles."""
        try:
            user_roles = current_user.get("roles", [])
            
            # Check if user has any of the required roles
            has_role = any(role in user_roles for role in required_roles)
            
            if not has_role:
                logger.warning(
                    "Access denied - missing roles",
                    user_id=current_user.get("id"),
                    required=required_roles,
                    user_roles=user_roles
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join(required_roles)}"
                )
            
            logger.debug(
                "Role check passed",
                user_id=current_user.get("id"),
                roles=required_roles
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Role check failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Role check failed"
            )
    
    return check_roles


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None
    except Exception:
        return None


async def validate_api_key(
    request: Request,
    api_key: Optional[str] = None
) -> bool:
    """Validate API key for service-to-service communication."""
    try:
        # Get API key from header or query parameter
        if not api_key:
            api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return False
        
        # Validate against configured API keys
        valid_api_keys = settings.API_KEYS
        if api_key in valid_api_keys:
            logger.debug("API key validation successful")
            return True
        
        logger.warning("Invalid API key provided", api_key=api_key[:8] + "...")
        return False
        
    except Exception as e:
        logger.error("API key validation failed", error=str(e))
        return False


def require_api_key():
    """Dependency for API key authentication."""
    async def check_api_key(request: Request) -> None:
        """Check if request has valid API key."""
        is_valid = await validate_api_key(request)
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "ApiKey"}
            )
    
    return check_api_key


async def get_request_context(request: Request) -> Dict[str, Any]:
    """Get request context information."""
    return {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
        "timestamp": datetime.utcnow().isoformat()
    }


def rate_limit(requests_per_minute: int = 60):
    """Rate limiting dependency."""
    async def check_rate_limit(
        request: Request,
        current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
    ) -> None:
        """Check rate limit for user or IP."""
        try:
            from app.core.redis_client import get_rate_limiter
            
            rate_limiter = get_rate_limiter()
            
            # Use user ID if authenticated, otherwise use IP
            if current_user:
                key = f"user:{current_user.get('id')}"
            else:
                key = f"ip:{request.client.host}"
            
            is_allowed, info = await rate_limiter.is_allowed(
                key, requests_per_minute, 60
            )
            
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(requests_per_minute),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(int(info["reset_time"]))
                    }
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Fail open - allow request if rate limiting fails
    
    return check_rate_limit


async def get_service_health() -> Dict[str, Any]:
    """Get service health information."""
    try:
        from app.core.database import engine
        from app.core.redis_client import redis_manager
        from app.core.storage import storage_manager
        
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }
        
        # Check database
        try:
            if engine:
                async with engine.begin() as conn:
                    await conn.execute("SELECT 1")
                health["services"]["database"] = "healthy"
            else:
                health["services"]["database"] = "not_initialized"
        except Exception as e:
            health["services"]["database"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"
        
        # Check Redis
        try:
            redis_healthy = await redis_manager.health_check()
            health["services"]["redis"] = "healthy" if redis_healthy else "unhealthy"
            if not redis_healthy:
                health["status"] = "degraded"
        except Exception as e:
            health["services"]["redis"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"
        
        # Check storage
        try:
            # Simple check - try to list objects (this is a lightweight operation)
            await storage_manager.s3_client.list_objects_v2(
                Bucket=storage_manager.bucket_name,
                MaxKeys=1
            )
            health["services"]["storage"] = "healthy"
        except Exception as e:
            health["services"]["storage"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"
        
        return health
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }