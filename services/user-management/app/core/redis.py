#!/usr/bin/env python3
"""
Redis connection and session management for the AIMA User Management Service.

This module handles Redis connections for caching and session storage.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional, Dict

import redis.asyncio as redis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Redis connection pools
redis_pool = None
session_redis = None
cache_redis = None


async def init_redis() -> None:
    """Initialize Redis connections."""
    global redis_pool, session_redis, cache_redis
    
    settings = get_settings()
    
    try:
        # Create connection pool
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True
        )
        
        # Create Redis clients for different purposes
        session_redis = redis.Redis(
            connection_pool=redis_pool,
            db=settings.REDIS_SESSION_DB
        )
        
        cache_redis = redis.Redis(
            connection_pool=redis_pool,
            db=settings.REDIS_CACHE_DB
        )
        
        # Test connections
        await session_redis.ping()
        await cache_redis.ping()
        
        logger.info(
            "Redis connections initialized",
            session_db=settings.REDIS_SESSION_DB,
            cache_db=settings.REDIS_CACHE_DB
        )
        
    except Exception as e:
        logger.error("Failed to initialize Redis connections", error=str(e))
        raise


async def close_redis() -> None:
    """Close Redis connections."""
    global redis_pool, session_redis, cache_redis
    
    if session_redis:
        await session_redis.close()
    
    if cache_redis:
        await cache_redis.close()
    
    if redis_pool:
        await redis_pool.disconnect()
    
    logger.info("Redis connections closed")


class SessionManager:
    """Manages user sessions in Redis."""
    
    def __init__(self):
        self.redis = session_redis
        self.key_prefix = "session:"
    
    async def create_session(
        self,
        user_id: str,
        session_token: str,
        expires_in_hours: int = 8,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create a new user session."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=expires_in_hours)).isoformat(),
            "metadata": metadata or {}
        }
        
        key = f"{self.key_prefix}{session_token}"
        await self.redis.setex(
            key,
            timedelta(hours=expires_in_hours),
            json.dumps(session_data)
        )
        
        logger.debug(
            "Session created",
            user_id=user_id,
            session_token=session_token[:8] + "...",
            expires_in_hours=expires_in_hours
        )
    
    async def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get session data by token."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        key = f"{self.key_prefix}{session_token}"
        session_data = await self.redis.get(key)
        
        if session_data:
            return json.loads(session_data)
        
        return None
    
    async def update_session(
        self,
        session_token: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Update session metadata."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        session_data = await self.get_session(session_token)
        if not session_data:
            return False
        
        session_data["metadata"].update(metadata)
        session_data["updated_at"] = datetime.utcnow().isoformat()
        
        key = f"{self.key_prefix}{session_token}"
        ttl = await self.redis.ttl(key)
        
        if ttl > 0:
            await self.redis.setex(key, ttl, json.dumps(session_data))
            return True
        
        return False
    
    async def delete_session(self, session_token: str) -> bool:
        """Delete a session."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        key = f"{self.key_prefix}{session_token}"
        result = await self.redis.delete(key)
        
        logger.debug(
            "Session deleted",
            session_token=session_token[:8] + "...",
            existed=bool(result)
        )
        
        return bool(result)
    
    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        pattern = f"{self.key_prefix}*"
        deleted_count = 0
        
        async for key in self.redis.scan_iter(match=pattern):
            session_data = await self.redis.get(key)
            if session_data:
                data = json.loads(session_data)
                if data.get("user_id") == user_id:
                    await self.redis.delete(key)
                    deleted_count += 1
        
        logger.debug(
            "User sessions deleted",
            user_id=user_id,
            count=deleted_count
        )
        
        return deleted_count


class CacheManager:
    """Manages application cache in Redis."""
    
    def __init__(self):
        self.redis = cache_redis
        self.key_prefix = "cache:"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        cache_key = f"{self.key_prefix}{key}"
        value = await self.redis.get(cache_key)
        
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: Optional[int] = None
    ) -> None:
        """Set cached value."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        cache_key = f"{self.key_prefix}{key}"
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if expire_seconds:
            await self.redis.setex(cache_key, expire_seconds, value)
        else:
            await self.redis.set(cache_key, value)
    
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        cache_key = f"{self.key_prefix}{key}"
        result = await self.redis.delete(cache_key)
        return bool(result)
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self.redis:
            raise RuntimeError("Redis not initialized")
        
        cache_pattern = f"{self.key_prefix}{pattern}"
        deleted_count = 0
        
        async for key in self.redis.scan_iter(match=cache_pattern):
            await self.redis.delete(key)
            deleted_count += 1
        
        return deleted_count


async def health_check() -> bool:
    """Check Redis health."""
    try:
        if not session_redis or not cache_redis:
            return False
        
        await session_redis.ping()
        await cache_redis.ping()
        
        return True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False


# Global instances
session_manager = SessionManager()
cache_manager = CacheManager()