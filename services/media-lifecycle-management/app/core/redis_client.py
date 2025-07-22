#!/usr/bin/env python3
"""
Redis client configuration for the AIMA Media Lifecycle Management Service.

This module provides Redis connection management, caching utilities,
and session management for the media lifecycle service.
"""

import json
import pickle
from typing import Any, Optional, Union, Dict, List
from datetime import datetime, timedelta

import redis.asyncio as redis
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Global Redis client
redis_client: Optional[Redis] = None


class RedisManager:
    """Redis connection and operation manager."""
    
    def __init__(self):
        self.client: Optional[Redis] = None
        self.settings = get_settings()
        
    async def connect(self) -> None:
        """Initialize Redis connection."""
        try:
            self.client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=self.settings.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=True,
                socket_timeout=self.settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=self.settings.REDIS_CONNECT_TIMEOUT,
                health_check_interval=30
            )
            
            # Test connection
            await self.client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            if not self.client:
                return False
            await self.client.ping()
            return True
        except Exception:
            return False


class CacheManager:
    """Cache operations manager."""
    
    def __init__(self, redis_client: Redis):
        self.client = redis_client
        self.default_ttl = 3600  # 1 hour
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            # Try to deserialize JSON first, then pickle
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    return pickle.loads(value.encode('latin-1'))
                except Exception:
                    return value
                    
        except RedisError as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or self.default_ttl
            
            # Serialize value
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, default=str)
            elif isinstance(value, (str, int, float, bool)):
                serialized_value = value
            else:
                serialized_value = pickle.dumps(value).decode('latin-1')
            
            await self.client.setex(key, ttl, serialized_value)
            return True
            
        except RedisError as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = await self.client.delete(key)
            return result > 0
        except RedisError as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return await self.client.exists(key) > 0
        except RedisError as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """Increment counter in cache."""
        try:
            pipe = self.client.pipeline()
            pipe.incr(key, amount)
            if ttl:
                pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except RedisError as e:
            logger.warning("Cache increment failed", key=key, error=str(e))
            return None
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            if not keys:
                return {}
            
            values = await self.client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        try:
                            result[key] = pickle.loads(value.encode('latin-1'))
                        except Exception:
                            result[key] = value
            
            return result
            
        except RedisError as e:
            logger.warning("Cache get_many failed", keys=keys, error=str(e))
            return {}
    
    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache."""
        try:
            if not mapping:
                return True
            
            ttl = ttl or self.default_ttl
            pipe = self.client.pipeline()
            
            for key, value in mapping.items():
                # Serialize value
                if isinstance(value, (dict, list, tuple)):
                    serialized_value = json.dumps(value, default=str)
                elif isinstance(value, (str, int, float, bool)):
                    serialized_value = value
                else:
                    serialized_value = pickle.dumps(value).decode('latin-1')
                
                pipe.setex(key, ttl, serialized_value)
            
            await pipe.execute()
            return True
            
        except RedisError as e:
            logger.warning("Cache set_many failed", error=str(e))
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        try:
            keys = await self.client.keys(pattern)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning("Cache clear_pattern failed", pattern=pattern, error=str(e))
            return 0


class SessionManager:
    """Session management using Redis."""
    
    def __init__(self, redis_client: Redis):
        self.client = redis_client
        self.session_prefix = "session:"
        self.default_ttl = 86400  # 24 hours
    
    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.session_prefix}{session_id}"
    
    async def create_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Create new session."""
        try:
            key = self._get_session_key(session_id)
            ttl = ttl or self.default_ttl
            
            session_data = {
                "data": data,
                "created_at": datetime.utcnow().isoformat(),
                "last_accessed": datetime.utcnow().isoformat()
            }
            
            await self.client.setex(key, ttl, json.dumps(session_data, default=str))
            return True
            
        except RedisError as e:
            logger.warning("Session creation failed", session_id=session_id, error=str(e))
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        try:
            key = self._get_session_key(session_id)
            session_data = await self.client.get(key)
            
            if session_data:
                data = json.loads(session_data)
                # Update last accessed time
                data["last_accessed"] = datetime.utcnow().isoformat()
                await self.client.setex(key, self.default_ttl, json.dumps(data, default=str))
                return data["data"]
            
            return None
            
        except RedisError as e:
            logger.warning("Session get failed", session_id=session_id, error=str(e))
            return None
    
    async def update_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Update session data."""
        try:
            key = self._get_session_key(session_id)
            ttl = ttl or self.default_ttl
            
            # Get existing session to preserve created_at
            existing = await self.client.get(key)
            created_at = datetime.utcnow().isoformat()
            
            if existing:
                existing_data = json.loads(existing)
                created_at = existing_data.get("created_at", created_at)
            
            session_data = {
                "data": data,
                "created_at": created_at,
                "last_accessed": datetime.utcnow().isoformat()
            }
            
            await self.client.setex(key, ttl, json.dumps(session_data, default=str))
            return True
            
        except RedisError as e:
            logger.warning("Session update failed", session_id=session_id, error=str(e))
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        try:
            key = self._get_session_key(session_id)
            result = await self.client.delete(key)
            return result > 0
        except RedisError as e:
            logger.warning("Session delete failed", session_id=session_id, error=str(e))
            return False
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        try:
            key = self._get_session_key(session_id)
            return await self.client.exists(key) > 0
        except RedisError as e:
            logger.warning("Session exists check failed", session_id=session_id, error=str(e))
            return False


class RateLimiter:
    """Rate limiting using Redis."""
    
    def __init__(self, redis_client: Redis):
        self.client = redis_client
        self.prefix = "rate_limit:"
    
    async def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier for the rate limit (e.g., user_id, ip_address)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, info_dict)
        """
        try:
            redis_key = f"{self.prefix}{key}"
            current_time = datetime.utcnow().timestamp()
            
            pipe = self.client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(redis_key, 0, current_time - window)
            
            # Count current requests
            pipe.zcard(redis_key)
            
            # Add current request
            pipe.zadd(redis_key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(redis_key, window)
            
            results = await pipe.execute()
            current_count = results[1]
            
            is_allowed = current_count < limit
            
            info = {
                "limit": limit,
                "remaining": max(0, limit - current_count - 1),
                "reset_time": current_time + window,
                "window": window
            }
            
            return is_allowed, info
            
        except RedisError as e:
            logger.warning("Rate limit check failed", key=key, error=str(e))
            # Fail open - allow request if Redis is down
            return True, {"limit": limit, "remaining": limit - 1, "reset_time": 0, "window": window}


# Global instances
redis_manager = RedisManager()
cache_manager: Optional[CacheManager] = None
session_manager: Optional[SessionManager] = None
rate_limiter: Optional[RateLimiter] = None


async def init_redis():
    """Initialize Redis connection and managers."""
    global redis_client, cache_manager, session_manager, rate_limiter
    
    try:
        await redis_manager.connect()
        redis_client = redis_manager.client
        
        # Initialize managers
        cache_manager = CacheManager(redis_client)
        session_manager = SessionManager(redis_client)
        rate_limiter = RateLimiter(redis_client)
        
        logger.info("Redis managers initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize Redis", error=str(e))
        raise


async def close_redis():
    """Close Redis connections."""
    await redis_manager.disconnect()


def get_cache() -> CacheManager:
    """Get cache manager instance."""
    if cache_manager is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return cache_manager


def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    if session_manager is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return session_manager


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance."""
    if rate_limiter is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return rate_limiter


def get_redis_client() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client