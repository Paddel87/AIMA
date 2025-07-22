#!/usr/bin/env python3
"""
Caching Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive caching functionality including
multi-level caching, cache warming, invalidation strategies, and
performance optimization for media processing operations.
"""

import logging
import asyncio
import json
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import UUID
import time
from functools import wraps
import weakref
from collections import OrderedDict, defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from ..core.redis_client import CacheManager
from ..core.database import MediaFile, ProcessingJob, User
from .audit_service import AuditService, AuditEventType, AuditSeverity
from .monitoring_service import MonitoringService


logger = logging.getLogger(__name__)


class CacheLevel(str, Enum):
    """Cache levels for multi-level caching."""
    L1_MEMORY = "l1_memory"  # In-memory cache
    L2_REDIS = "l2_redis"    # Redis cache
    L3_DATABASE = "l3_database"  # Database cache


class CacheStrategy(str, Enum):
    """Cache strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out
    ADAPTIVE = "adaptive"  # Adaptive based on access patterns


class InvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""
    TTL_BASED = "ttl_based"
    EVENT_BASED = "event_based"
    MANUAL = "manual"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"


class CacheEventType(str, Enum):
    """Cache event types for invalidation."""
    MEDIA_UPLOADED = "media_uploaded"
    MEDIA_UPDATED = "media_updated"
    MEDIA_DELETED = "media_deleted"
    PROCESSING_COMPLETED = "processing_completed"
    USER_UPDATED = "user_updated"
    METADATA_UPDATED = "metadata_updated"
    THUMBNAIL_GENERATED = "thumbnail_generated"
    TRANSCODING_COMPLETED = "transcoding_completed"


@dataclass
class CacheEntry:
    """Represents a cache entry."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl: Optional[int] = None  # seconds
    tags: Optional[Set[str]] = None
    size: Optional[int] = None  # bytes
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl)
    
    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0  # number of entries
    memory_usage: int = 0  # bytes
    hit_rate: float = 0.0
    avg_access_time: float = 0.0
    
    def calculate_hit_rate(self):
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        self.hit_rate = (self.hits / total * 100) if total > 0 else 0.0


class MemoryCache:
    """In-memory LRU cache implementation."""
    
    def __init__(self, max_size: int = 1000, max_memory: int = 100 * 1024 * 1024):  # 100MB
        self.max_size = max_size
        self.max_memory = max_memory
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = CacheStats()
        self.access_times: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        start_time = time.time()
        
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # Check if expired
                if entry.is_expired():
                    del self.cache[key]
                    self.stats.misses += 1
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                entry.touch()
                
                self.stats.hits += 1
                access_time = time.time() - start_time
                self.access_times[key].append(access_time)
                
                # Keep only recent access times
                if len(self.access_times[key]) > 100:
                    self.access_times[key] = self.access_times[key][-50:]
                
                return entry.value
            else:
                self.stats.misses += 1
                return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[Set[str]] = None):
        """Set value in cache."""
        async with self._lock:
            # Calculate size
            try:
                size = len(pickle.dumps(value))
            except:
                size = 1024  # Default size if can't serialize
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=1,
                ttl=ttl,
                tags=tags,
                size=size
            )
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats.memory_usage -= old_entry.size or 0
                del self.cache[key]
            
            # Add new entry
            self.cache[key] = entry
            self.stats.memory_usage += size
            self.stats.size = len(self.cache)
            
            # Evict if necessary
            await self._evict_if_necessary()
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                self.stats.memory_usage -= entry.size or 0
                del self.cache[key]
                self.stats.size = len(self.cache)
                if key in self.access_times:
                    del self.access_times[key]
                return True
            return False
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.access_times.clear()
            self.stats = CacheStats()
    
    async def invalidate_by_tags(self, tags: Set[str]):
        """Invalidate cache entries by tags."""
        async with self._lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                if entry.tags and entry.tags.intersection(tags):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                entry = self.cache[key]
                self.stats.memory_usage -= entry.size or 0
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                self.stats.evictions += 1
            
            self.stats.size = len(self.cache)
    
    async def _evict_if_necessary(self):
        """Evict entries if cache limits are exceeded."""
        # Evict by size
        while len(self.cache) > self.max_size:
            key, entry = self.cache.popitem(last=False)  # Remove least recently used
            self.stats.memory_usage -= entry.size or 0
            if key in self.access_times:
                del self.access_times[key]
            self.stats.evictions += 1
        
        # Evict by memory
        while self.stats.memory_usage > self.max_memory and self.cache:
            key, entry = self.cache.popitem(last=False)
            self.stats.memory_usage -= entry.size or 0
            if key in self.access_times:
                del self.access_times[key]
            self.stats.evictions += 1
        
        self.stats.size = len(self.cache)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self.stats.calculate_hit_rate()
        
        # Calculate average access time
        all_times = []
        for times in self.access_times.values():
            all_times.extend(times)
        
        if all_times:
            self.stats.avg_access_time = sum(all_times) / len(all_times)
        
        return self.stats


class CacheWarmer:
    """Cache warming service."""
    
    def __init__(self, caching_service: 'CachingService'):
        self.caching_service = caching_service
        self.warming_tasks: Dict[str, asyncio.Task] = {}
    
    async def warm_user_data(self, db: AsyncSession, user_id: UUID):
        """Warm cache with user-related data."""
        try:
            # Warm user profile
            await self.caching_service.get_user_profile(db, user_id)
            
            # Warm user's recent media files
            await self.caching_service.get_user_media_files(db, user_id, limit=50)
            
            # Warm user's processing jobs
            await self.caching_service.get_user_processing_jobs(db, user_id, limit=20)
            
            logger.info(f"Cache warmed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to warm cache for user {user_id}: {e}")
    
    async def warm_popular_content(self, db: AsyncSession):
        """Warm cache with popular content."""
        try:
            # Warm popular media files
            await self.caching_service.get_popular_media_files(db, limit=100)
            
            # Warm recent uploads
            await self.caching_service.get_recent_uploads(db, limit=50)
            
            # Warm system statistics
            await self.caching_service.get_system_stats(db)
            
            logger.info("Cache warmed with popular content")
            
        except Exception as e:
            logger.error(f"Failed to warm popular content cache: {e}")
    
    async def schedule_warming(self, task_name: str, coro: Callable, interval: int):
        """Schedule periodic cache warming."""
        async def warming_loop():
            while True:
                try:
                    await coro()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Cache warming task {task_name} failed: {e}")
                    await asyncio.sleep(60)  # Wait before retrying
        
        if task_name in self.warming_tasks:
            self.warming_tasks[task_name].cancel()
        
        self.warming_tasks[task_name] = asyncio.create_task(warming_loop())
        logger.info(f"Scheduled cache warming task: {task_name}")
    
    async def stop_all_warming(self):
        """Stop all warming tasks."""
        for task_name, task in self.warming_tasks.items():
            task.cancel()
            logger.info(f"Stopped cache warming task: {task_name}")
        
        self.warming_tasks.clear()


class CachingService:
    """Main caching service with multi-level caching support."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        audit_service: Optional[AuditService] = None,
        monitoring_service: Optional[MonitoringService] = None
    ):
        self.redis_cache = cache_manager
        self.audit_service = audit_service
        self.monitoring_service = monitoring_service
        
        # Initialize memory cache
        self.memory_cache = MemoryCache(max_size=1000, max_memory=100 * 1024 * 1024)
        
        # Cache configuration
        self.default_ttl = 3600  # 1 hour
        self.long_ttl = 24 * 3600  # 24 hours
        self.short_ttl = 300  # 5 minutes
        
        # Cache warming
        self.cache_warmer = CacheWarmer(self)
        
        # Invalidation tracking
        self.invalidation_patterns: Dict[CacheEventType, List[str]] = {
            CacheEventType.MEDIA_UPLOADED: [
                "user_media:*",
                "recent_uploads",
                "system_stats",
                "popular_media"
            ],
            CacheEventType.MEDIA_UPDATED: [
                "media:*",
                "user_media:*",
                "media_metadata:*"
            ],
            CacheEventType.MEDIA_DELETED: [
                "media:*",
                "user_media:*",
                "system_stats",
                "popular_media"
            ],
            CacheEventType.PROCESSING_COMPLETED: [
                "processing_job:*",
                "user_jobs:*",
                "media:*"
            ],
            CacheEventType.USER_UPDATED: [
                "user:*",
                "user_profile:*"
            ],
            CacheEventType.METADATA_UPDATED: [
                "media_metadata:*",
                "media:*"
            ],
            CacheEventType.THUMBNAIL_GENERATED: [
                "media_thumbnail:*",
                "media:*"
            ],
            CacheEventType.TRANSCODING_COMPLETED: [
                "media_variants:*",
                "media:*",
                "processing_job:*"
            ]
        }
    
    async def get(
        self,
        key: str,
        levels: List[CacheLevel] = None,
        deserialize: bool = True
    ) -> Optional[Any]:
        """Get value from cache with multi-level support."""
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        start_time = time.time()
        
        try:
            # Try each cache level in order
            for level in levels:
                if level == CacheLevel.L1_MEMORY:
                    value = await self.memory_cache.get(key)
                    if value is not None:
                        await self._record_cache_hit(key, level, time.time() - start_time)
                        return value
                
                elif level == CacheLevel.L2_REDIS:
                    value = await self.redis_cache.get(key)
                    if value is not None:
                        # Promote to L1 cache
                        await self.memory_cache.set(key, value, ttl=self.short_ttl)
                        await self._record_cache_hit(key, level, time.time() - start_time)
                        return value
            
            # Cache miss
            await self._record_cache_miss(key, time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        levels: List[CacheLevel] = None,
        tags: Optional[Set[str]] = None
    ):
        """Set value in cache with multi-level support."""
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            # Set in each specified cache level
            for level in levels:
                if level == CacheLevel.L1_MEMORY:
                    await self.memory_cache.set(key, value, ttl=ttl, tags=tags)
                
                elif level == CacheLevel.L2_REDIS:
                    await self.redis_cache.set(key, value, ttl=ttl)
            
            await self._record_cache_set(key, levels)
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
    
    async def delete(self, key: str, levels: List[CacheLevel] = None) -> bool:
        """Delete key from cache."""
        if levels is None:
            levels = [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS]
        
        success = False
        
        try:
            for level in levels:
                if level == CacheLevel.L1_MEMORY:
                    if await self.memory_cache.delete(key):
                        success = True
                
                elif level == CacheLevel.L2_REDIS:
                    if await self.redis_cache.delete(key):
                        success = True
            
            if success:
                await self._record_cache_delete(key, levels)
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern."""
        try:
            # Get matching keys from Redis
            keys = await self.redis_cache.scan_keys(pattern)
            
            # Delete from all levels
            for key in keys:
                await self.delete(key)
            
            logger.info(f"Invalidated {len(keys)} cache entries matching pattern: {pattern}")
            
        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {pattern}: {e}")
    
    async def invalidate_by_tags(self, tags: Set[str]):
        """Invalidate cache entries by tags."""
        try:
            # Invalidate from memory cache
            await self.memory_cache.invalidate_by_tags(tags)
            
            # For Redis, we need to scan and check tags (if stored)
            # This is a simplified implementation
            logger.info(f"Invalidated cache entries with tags: {tags}")
            
        except Exception as e:
            logger.error(f"Cache tag invalidation error: {e}")
    
    async def invalidate_by_event(self, event_type: CacheEventType, context: Dict[str, Any] = None):
        """Invalidate cache based on event type."""
        try:
            patterns = self.invalidation_patterns.get(event_type, [])
            
            for pattern in patterns:
                # Replace placeholders with context values
                if context:
                    for key, value in context.items():
                        pattern = pattern.replace(f"{{{key}}}", str(value))
                
                await self.invalidate_pattern(pattern)
            
            logger.info(f"Cache invalidated for event: {event_type.value}")
            
        except Exception as e:
            logger.error(f"Event-based cache invalidation error: {e}")
    
    def cache_result(
        self,
        key_template: str = None,
        ttl: int = None,
        levels: List[CacheLevel] = None,
        tags: Set[str] = None
    ):
        """Decorator for caching function results."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_template:
                    # Use template with function arguments
                    key_args = {f"arg{i}": arg for i, arg in enumerate(args)}
                    key_args.update(kwargs)
                    cache_key = key_template.format(**key_args)
                else:
                    # Generate key from function name and arguments
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
                
                # Try to get from cache
                cached_result = await self.get(cache_key, levels=levels)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl=ttl, levels=levels, tags=tags)
                
                return result
            
            return wrapper
        return decorator
    
    # Specific caching methods for common operations
    
    async def get_user_profile(self, db: AsyncSession, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached user profile."""
        cache_key = f"user_profile:{user_id}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            profile_data = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
                "is_active": user.is_active,
                "storage_quota": user.storage_quota,
                "storage_used": user.storage_used
            }
            
            await self.set(
                cache_key,
                profile_data,
                ttl=self.long_ttl,
                tags={"user_data", f"user_{user_id}"}
            )
            
            return profile_data
        
        return None
    
    async def get_user_media_files(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get cached user media files."""
        cache_key = f"user_media:{user_id}:{limit}:{offset}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(MediaFile)
            .where(MediaFile.user_id == user_id)
            .order_by(MediaFile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        media_files = result.scalars().all()
        
        media_data = []
        for media in media_files:
            media_data.append({
                "id": str(media.id),
                "filename": media.filename,
                "file_type": media.file_type,
                "file_size": media.file_size,
                "status": media.status,
                "created_at": media.created_at.isoformat(),
                "thumbnail_url": media.thumbnail_url
            })
        
        await self.set(
            cache_key,
            media_data,
            ttl=self.default_ttl,
            tags={"user_media", f"user_{user_id}"}
        )
        
        return media_data
    
    async def get_user_processing_jobs(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get cached user processing jobs."""
        cache_key = f"user_jobs:{user_id}:{limit}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(ProcessingJob)
            .join(MediaFile)
            .where(MediaFile.user_id == user_id)
            .order_by(ProcessingJob.created_at.desc())
            .limit(limit)
        )
        jobs = result.scalars().all()
        
        job_data = []
        for job in jobs:
            job_data.append({
                "id": str(job.id),
                "job_type": job.job_type,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            })
        
        await self.set(
            cache_key,
            job_data,
            ttl=self.default_ttl,
            tags={"user_jobs", f"user_{user_id}"}
        )
        
        return job_data
    
    async def get_media_metadata(self, db: AsyncSession, media_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached media metadata."""
        cache_key = f"media_metadata:{media_id}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == media_id)
        )
        media = result.scalar_one_or_none()
        
        if media and media.metadata:
            await self.set(
                cache_key,
                media.metadata,
                ttl=self.long_ttl,
                tags={"media_metadata", f"media_{media_id}"}
            )
            
            return media.metadata
        
        return None
    
    async def get_popular_media_files(self, db: AsyncSession, limit: int = 100) -> List[Dict[str, Any]]:
        """Get cached popular media files."""
        cache_key = f"popular_media:{limit}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # This would typically involve more complex analytics
        # For now, we'll use recent uploads as a proxy
        result = await db.execute(
            select(MediaFile)
            .where(MediaFile.status == "completed")
            .order_by(MediaFile.created_at.desc())
            .limit(limit)
        )
        media_files = result.scalars().all()
        
        media_data = []
        for media in media_files:
            media_data.append({
                "id": str(media.id),
                "filename": media.filename,
                "file_type": media.file_type,
                "file_size": media.file_size,
                "created_at": media.created_at.isoformat(),
                "thumbnail_url": media.thumbnail_url
            })
        
        await self.set(
            cache_key,
            media_data,
            ttl=self.default_ttl,
            tags={"popular_media"}
        )
        
        return media_data
    
    async def get_recent_uploads(self, db: AsyncSession, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cached recent uploads."""
        cache_key = f"recent_uploads:{limit}"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(MediaFile)
            .order_by(MediaFile.created_at.desc())
            .limit(limit)
        )
        media_files = result.scalars().all()
        
        media_data = []
        for media in media_files:
            media_data.append({
                "id": str(media.id),
                "filename": media.filename,
                "file_type": media.file_type,
                "file_size": media.file_size,
                "status": media.status,
                "created_at": media.created_at.isoformat()
            })
        
        await self.set(
            cache_key,
            media_data,
            ttl=self.short_ttl,
            tags={"recent_uploads"}
        )
        
        return media_data
    
    async def get_system_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get cached system statistics."""
        cache_key = "system_stats"
        
        cached = await self.get(cache_key)
        if cached:
            return cached
        
        # Calculate stats from database
        total_files_result = await db.execute(select(func.count(MediaFile.id)))
        total_files = total_files_result.scalar()
        
        total_size_result = await db.execute(select(func.sum(MediaFile.file_size)))
        total_size = total_size_result.scalar() or 0
        
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar()
        
        stats = {
            "total_files": total_files,
            "total_size": total_size,
            "total_users": total_users,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.set(
            cache_key,
            stats,
            ttl=self.default_ttl,
            tags={"system_stats"}
        )
        
        return stats
    
    async def _record_cache_hit(self, key: str, level: CacheLevel, access_time: float):
        """Record cache hit metrics."""
        if self.monitoring_service:
            await self.monitoring_service.record_metric(
                f"cache.{level.value}.hits",
                1
            )
            await self.monitoring_service.record_metric(
                f"cache.{level.value}.access_time",
                access_time
            )
    
    async def _record_cache_miss(self, key: str, access_time: float):
        """Record cache miss metrics."""
        if self.monitoring_service:
            await self.monitoring_service.record_metric(
                "cache.misses",
                1
            )
            await self.monitoring_service.record_metric(
                "cache.miss_access_time",
                access_time
            )
    
    async def _record_cache_set(self, key: str, levels: List[CacheLevel]):
        """Record cache set metrics."""
        if self.monitoring_service:
            for level in levels:
                await self.monitoring_service.record_metric(
                    f"cache.{level.value}.sets",
                    1
                )
    
    async def _record_cache_delete(self, key: str, levels: List[CacheLevel]):
        """Record cache delete metrics."""
        if self.monitoring_service:
            for level in levels:
                await self.monitoring_service.record_metric(
                    f"cache.{level.value}.deletes",
                    1
                )
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        memory_stats = self.memory_cache.get_stats()
        
        # Get Redis stats (simplified)
        redis_info = await self.redis_cache.get_info()
        
        return {
            "memory_cache": asdict(memory_stats),
            "redis_cache": {
                "connected": redis_info.get("connected", False),
                "memory_usage": redis_info.get("used_memory", 0),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the caching service."""
        try:
            # Test memory cache
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.utcnow().isoformat()}
            
            await self.memory_cache.set(test_key, test_value, ttl=60)
            retrieved = await self.memory_cache.get(test_key)
            memory_healthy = retrieved is not None
            
            # Test Redis cache
            await self.redis_cache.set(test_key, test_value, ttl=60)
            redis_retrieved = await self.redis_cache.get(test_key)
            redis_healthy = redis_retrieved is not None
            
            # Cleanup
            await self.memory_cache.delete(test_key)
            await self.redis_cache.delete(test_key)
            
            stats = await self.get_cache_stats()
            
            return {
                "status": "healthy" if (memory_healthy and redis_healthy) else "degraded",
                "memory_cache_healthy": memory_healthy,
                "redis_cache_healthy": redis_healthy,
                "stats": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def start_cache_warming(self, db: AsyncSession):
        """Start cache warming tasks."""
        # Schedule popular content warming every 30 minutes
        await self.cache_warmer.schedule_warming(
            "popular_content",
            lambda: self.cache_warmer.warm_popular_content(db),
            1800  # 30 minutes
        )
        
        logger.info("Cache warming started")
    
    async def stop_cache_warming(self):
        """Stop cache warming tasks."""
        await self.cache_warmer.stop_all_warming()
        logger.info("Cache warming stopped")