#!/usr/bin/env python3
"""
Redis configuration and cache management for the AIMA Configuration Management Service.

This module handles Redis connections, caching operations, and provides
utilities for configuration caching.
"""

import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis manager for handling cache operations."""
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._connection_pool = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        await self.connect()
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._connection_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            
            self._redis = Redis(
                connection_pool=self._connection_pool,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Test connection
            await self._redis.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connection."""
        await self.disconnect()
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        try:
            if self._redis:
                await self._redis.close()
            if self._connection_pool:
                await self._connection_pool.disconnect()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._redis is not None
    
    @property
    def redis(self) -> Redis:
        """Get Redis client instance."""
        if not self._redis:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            if not self._redis:
                return False
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    async def get_info(self) -> dict:
        """Get Redis server information."""
        try:
            if not self._redis:
                return {"status": "disconnected"}
            
            info = await self._redis.info()
            return {
                "status": "connected",
                "version": info.get("redis_version"),
                "memory_used": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed")
            }
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            return {"status": "error", "error": str(e)}


class ConfigurationCache:
    """Cache manager specifically for configuration data."""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
        self.key_prefix = "aima:config:"
        self.default_ttl = settings.REDIS_CACHE_TTL
    
    def _make_key(self, key: str) -> str:
        """Create cache key with prefix."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get configuration value from cache."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return None
            
            cache_key = self._make_key(key)
            value = await self.redis_manager.redis.get(cache_key)
            
            if value is not None:
                return json.loads(value)
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set configuration value in cache."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return False
            
            cache_key = self._make_key(key)
            serialized_value = json.dumps(value, default=str)
            
            if ttl is None:
                ttl = self.default_ttl
            
            await self.redis_manager.redis.setex(
                cache_key, 
                ttl, 
                serialized_value
            )
            return True
            
        except (RedisError, json.JSONEncodeError) as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete configuration value from cache."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return False
            
            cache_key = self._make_key(key)
            result = await self.redis_manager.redis.delete(cache_key)
            return result > 0
            
        except RedisError as e:
            logger.warning(f"Cache delete error for key '{key}': {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete multiple keys matching pattern."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return 0
            
            cache_pattern = self._make_key(pattern)
            keys = await self.redis_manager.redis.keys(cache_pattern)
            
            if keys:
                return await self.redis_manager.redis.delete(*keys)
            return 0
            
        except RedisError as e:
            logger.warning(f"Cache delete pattern error for pattern '{pattern}': {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """Clear all configuration cache."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return False
            
            pattern = f"{self.key_prefix}*"
            keys = await self.redis_manager.redis.keys(pattern)
            
            if keys:
                await self.redis_manager.redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} configuration cache entries")
            
            return True
            
        except RedisError as e:
            logger.error(f"Error clearing configuration cache: {e}")
            return False
    
    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        try:
            if not settings.CONFIG_CACHE_ENABLED:
                return {"enabled": False}
            
            pattern = f"{self.key_prefix}*"
            keys = await self.redis_manager.redis.keys(pattern)
            
            # Get memory usage for cache keys
            total_memory = 0
            for key in keys[:100]:  # Limit to avoid performance issues
                try:
                    memory = await self.redis_manager.redis.memory_usage(key)
                    if memory:
                        total_memory += memory
                except:
                    pass
            
            return {
                "enabled": True,
                "total_keys": len(keys),
                "memory_usage_bytes": total_memory,
                "default_ttl": self.default_ttl
            }
            
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Global Redis manager and cache instances
redis_manager = RedisManager()
configuration_cache = ConfigurationCache(redis_manager)


async def get_redis() -> Redis:
    """Get Redis client instance."""
    return redis_manager.redis


async def get_cache() -> ConfigurationCache:
    """Get configuration cache instance."""
    return configuration_cache