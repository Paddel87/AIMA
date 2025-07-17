#!/usr/bin/env python3
"""
Dependency injection for the AIMA Configuration Management Service.

This module provides dependency injection functions for FastAPI endpoints,
including authentication, authorization, and service dependencies.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
import httpx

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_cache
from app.services.config_service import ConfigurationService

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme for JWT tokens
security = HTTPBearer()


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass


class AuthorizationError(Exception):
    """Custom exception for authorization errors."""
    pass


async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token with the user management service.
    
    Args:
        token: JWT token to verify
        
    Returns:
        User information from the token
        
    Raises:
        AuthenticationError: If token is invalid or verification fails
    """
    try:
        # First try to decode the token locally for basic validation
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": True}
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
        
        # Verify with user management service if available
        if settings.USER_MANAGEMENT_URL:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"{settings.USER_MANAGEMENT_URL}/api/v1/auth/verify",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        return user_data
                    elif response.status_code == 401:
                        raise AuthenticationError("Token verification failed")
                    else:
                        logger.warning(f"User service returned status {response.status_code}")
                        # Fall back to local token data if service is unavailable
                        return payload
                        
                except httpx.RequestError as e:
                    logger.warning(f"Failed to verify token with user service: {e}")
                    # Fall back to local token data if service is unavailable
                    return payload
        
        # Return local payload if no user service configured
        return payload
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise AuthenticationError("Token verification failed")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Current user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        user = await verify_token(credentials.credentials)
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current active user (not disabled).
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user information
        
    Raises:
        HTTPException: If user is disabled
    """
    if current_user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Require admin role for the current user.
    
    Args:
        current_user: Current active user
        
    Returns:
        Admin user information
        
    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def require_role(required_role: str):
    """
    Create a dependency that requires a specific role.
    
    Args:
        required_role: The role required to access the endpoint
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        user_role = current_user.get("role")
        
        # Admin can access everything
        if user_role == "admin":
            return current_user
        
        # Check specific role
        if user_role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        
        return current_user
    
    return role_checker


def get_config_service(
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
) -> ConfigurationService:
    """
    Get configuration service instance.
    
    Args:
        db: Database session
        cache: Redis cache instance
        
    Returns:
        ConfigurationService instance
    """
    return ConfigurationService(cache=cache)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, None otherwise.
    
    This is useful for endpoints that can work with or without authentication.
    
    Args:
        credentials: Optional HTTP authorization credentials
        
    Returns:
        User information if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        user = await verify_token(credentials.credentials)
        return user
    except AuthenticationError:
        return None
    except Exception as e:
        logger.warning(f"Optional authentication failed: {e}")
        return None


class RateLimiter:
    """
    Simple rate limiter for API endpoints.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def __call__(
        self,
        current_user: Dict[str, Any] = Depends(get_current_user),
        cache = Depends(get_cache)
    ) -> Dict[str, Any]:
        """
        Check rate limit for the current user.
        
        Args:
            current_user: Current authenticated user
            cache: Redis cache instance
            
        Returns:
            User information if within rate limit
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        if not cache.redis_manager.is_connected():
            # If Redis is not available, skip rate limiting
            return current_user
        
        user_id = current_user.get("user_id", "unknown")
        key = f"rate_limit:{user_id}"
        
        try:
            # Get current request count
            current_count = await cache.redis_manager.redis.get(key)
            
            if current_count is None:
                # First request in window
                await cache.redis_manager.redis.setex(
                    key, self.window_seconds, 1
                )
            else:
                current_count = int(current_count)
                if current_count >= self.max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded"
                    )
                
                # Increment counter
                await cache.redis_manager.redis.incr(key)
            
            return current_user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Rate limiting error: {e}")
            # If rate limiting fails, allow the request
            return current_user


# Pre-configured rate limiters
standard_rate_limit = RateLimiter(max_requests=100, window_seconds=60)
strict_rate_limit = RateLimiter(max_requests=10, window_seconds=60)