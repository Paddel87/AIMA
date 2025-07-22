#!/usr/bin/env python3
"""
Analytics Service for the AIMA Media Lifecycle Management Service.

This module provides analytics, reporting, and insights for media files,
usage patterns, and system performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload

from ..core.database import MediaFile, MediaTag, ProcessingJob, StorageUsage
from ..core.redis_client import CacheManager
from ..models.media import (
    MediaType, MediaStatus, ProcessingOperation, StorageTier,
    StorageUsageStats, MediaAnalyticsRequest, MediaAnalyticsResponse
)
from ..models.common import ProcessingStatus
from ..middleware.error_handling import MediaServiceException


logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for media analytics and reporting."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.cache_ttl = 300  # 5 minutes
    
    async def get_storage_usage_stats(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> StorageUsageStats:
        """
        Get storage usage statistics.
        """
        try:
            # Build cache key
            cache_key = f"storage_stats:{user_id or 'global'}:{start_date}:{end_date}"
            
            # Try cache first
            cached_stats = await self.cache.get(cache_key)
            if cached_stats:
                return StorageUsageStats(**cached_stats)
            
            # Build query conditions
            conditions = []
            if user_id:
                conditions.append(MediaFile.owner_id == user_id)
            if start_date:
                conditions.append(MediaFile.created_at >= start_date)
            if end_date:
                conditions.append(MediaFile.created_at <= end_date)
            
            # Exclude deleted files
            conditions.append(MediaFile.status != MediaStatus.DELETED)
            
            # Get total stats
            total_query = select(
                func.count(MediaFile.id).label('total_files'),
                func.sum(MediaFile.file_size).label('total_size')
            )
            
            if conditions:
                total_query = total_query.where(and_(*conditions))
            
            total_result = await db.execute(total_query)
            total_row = total_result.first()
            
            total_files = total_row.total_files or 0
            total_size = total_row.total_size or 0
            
            # Get stats by media type
            media_type_query = select(
                MediaFile.media_type,
                func.count(MediaFile.id).label('count'),
                func.sum(MediaFile.file_size).label('size'),
                func.avg(MediaFile.file_size).label('avg_size')
            )
            
            if conditions:
                media_type_query = media_type_query.where(and_(*conditions))
            
            media_type_query = media_type_query.group_by(MediaFile.media_type)
            
            media_type_result = await db.execute(media_type_query)
            media_type_rows = media_type_result.all()
            
            by_media_type = {}
            for row in media_type_rows:
                by_media_type[row.media_type] = {
                    'count': row.count,
                    'size': row.size or 0,
                    'avg_size': float(row.avg_size or 0),
                    'percentage': (row.size or 0) / total_size * 100 if total_size > 0 else 0
                }
            
            # Get stats by storage tier
            storage_tier_query = select(
                MediaFile.storage_tier,
                func.count(MediaFile.id).label('count'),
                func.sum(MediaFile.file_size).label('size')
            )
            
            if conditions:
                storage_tier_query = storage_tier_query.where(and_(*conditions))
            
            storage_tier_query = storage_tier_query.group_by(MediaFile.storage_tier)
            
            storage_tier_result = await db.execute(storage_tier_query)
            storage_tier_rows = storage_tier_result.all()
            
            by_storage_tier = {}
            for row in storage_tier_rows:
                by_storage_tier[row.storage_tier] = {
                    'count': row.count,
                    'size': row.size or 0,
                    'percentage': (row.size or 0) / total_size * 100 if total_size > 0 else 0
                }
            
            # Get stats by status
            status_query = select(
                MediaFile.status,
                func.count(MediaFile.id).label('count')
            )
            
            if conditions:
                status_query = status_query.where(and_(*conditions))
            
            status_query = status_query.group_by(MediaFile.status)
            
            status_result = await db.execute(status_query)
            status_rows = status_result.all()
            
            by_status = {row.status: row.count for row in status_rows}
            
            # Create stats object
            stats = StorageUsageStats(
                total_files=total_files,
                total_size=total_size,
                by_media_type=by_media_type,
                by_storage_tier=by_storage_tier,
                by_status=by_status
            )
            
            # Cache the results
            await self.cache.set(
                cache_key,
                stats.model_dump(),
                ttl=self.cache_ttl
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage usage stats: {e}")
            raise MediaServiceException(f"Analytics query failed: {str(e)}")
    
    async def get_media_analytics(
        self,
        db: AsyncSession,
        request: MediaAnalyticsRequest,
        user_id: Optional[UUID] = None
    ) -> MediaAnalyticsResponse:
        """
        Get comprehensive media analytics.
        """
        try:
            # Build cache key
            cache_key = f"media_analytics:{user_id}:{request.start_date}:{request.end_date}:{hash(str(request.metrics))}"
            
            # Try cache first
            cached_analytics = await self.cache.get(cache_key)
            if cached_analytics:
                return MediaAnalyticsResponse(**cached_analytics)
            
            metrics = {}
            trends = {}
            
            # Process each requested metric
            for metric in request.metrics:
                if metric == "upload_count":
                    metrics["upload_count"] = await self._get_upload_count(
                        db, request.start_date, request.end_date, user_id
                    )
                    
                    if request.group_by == "day":
                        trends["upload_count"] = await self._get_upload_trend_by_day(
                            db, request.start_date, request.end_date, user_id
                        )
                
                elif metric == "storage_usage":
                    metrics["storage_usage"] = await self._get_storage_usage_metric(
                        db, request.start_date, request.end_date, user_id
                    )
                
                elif metric == "processing_jobs":
                    metrics["processing_jobs"] = await self._get_processing_jobs_metric(
                        db, request.start_date, request.end_date, user_id
                    )
                
                elif metric == "popular_formats":
                    metrics["popular_formats"] = await self._get_popular_formats(
                        db, request.start_date, request.end_date, user_id
                    )
                
                elif metric == "user_activity":
                    metrics["user_activity"] = await self._get_user_activity(
                        db, request.start_date, request.end_date, user_id
                    )
            
            # Create response
            response_data = {
                "success": True,
                "message": "Analytics retrieved successfully",
                "period": {
                    "start_date": request.start_date,
                    "end_date": request.end_date
                },
                "metrics": metrics,
                "trends": trends if trends else None
            }
            
            # Cache the results
            await self.cache.set(
                cache_key,
                response_data,
                ttl=self.cache_ttl
            )
            
            return MediaAnalyticsResponse(**response_data)
            
        except Exception as e:
            logger.error(f"Failed to get media analytics: {e}")
            raise MediaServiceException(f"Analytics query failed: {str(e)}")
    
    async def _get_upload_count(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> int:
        """Get total upload count for the period."""
        conditions = [
            MediaFile.created_at >= start_date,
            MediaFile.created_at <= end_date
        ]
        
        if user_id:
            conditions.append(MediaFile.owner_id == user_id)
        
        query = select(func.count(MediaFile.id)).where(and_(*conditions))
        result = await db.execute(query)
        return result.scalar() or 0
    
    async def _get_upload_trend_by_day(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get upload trend by day."""
        conditions = [
            MediaFile.created_at >= start_date,
            MediaFile.created_at <= end_date
        ]
        
        if user_id:
            conditions.append(MediaFile.owner_id == user_id)
        
        # Use database-specific date truncation
        query = select(
            func.date(MediaFile.created_at).label('date'),
            func.count(MediaFile.id).label('count')
        ).where(and_(*conditions)).group_by(func.date(MediaFile.created_at)).order_by('date')
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "date": row.date.isoformat(),
                "count": row.count
            }
            for row in rows
        ]
    
    async def _get_storage_usage_metric(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get storage usage metrics."""
        conditions = [
            MediaFile.created_at >= start_date,
            MediaFile.created_at <= end_date,
            MediaFile.status != MediaStatus.DELETED
        ]
        
        if user_id:
            conditions.append(MediaFile.owner_id == user_id)
        
        query = select(
            func.sum(MediaFile.file_size).label('total_size'),
            func.avg(MediaFile.file_size).label('avg_size'),
            func.max(MediaFile.file_size).label('max_size'),
            func.min(MediaFile.file_size).label('min_size')
        ).where(and_(*conditions))
        
        result = await db.execute(query)
        row = result.first()
        
        return {
            "total_size": row.total_size or 0,
            "avg_size": float(row.avg_size or 0),
            "max_size": row.max_size or 0,
            "min_size": row.min_size or 0
        }
    
    async def _get_processing_jobs_metric(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get processing jobs metrics."""
        conditions = [
            ProcessingJob.created_at >= start_date,
            ProcessingJob.created_at <= end_date
        ]
        
        if user_id:
            # Join with MediaFile to filter by user
            query = select(
                ProcessingJob.status,
                func.count(ProcessingJob.id).label('count'),
                func.avg(ProcessingJob.processing_time).label('avg_processing_time')
            ).select_from(
                ProcessingJob.join(MediaFile, ProcessingJob.file_id == MediaFile.id)
            ).where(
                and_(
                    *conditions,
                    MediaFile.owner_id == user_id
                )
            ).group_by(ProcessingJob.status)
        else:
            query = select(
                ProcessingJob.status,
                func.count(ProcessingJob.id).label('count'),
                func.avg(ProcessingJob.processing_time).label('avg_processing_time')
            ).where(and_(*conditions)).group_by(ProcessingJob.status)
        
        result = await db.execute(query)
        rows = result.all()
        
        stats_by_status = {}
        total_jobs = 0
        total_processing_time = 0
        
        for row in rows:
            stats_by_status[row.status] = {
                "count": row.count,
                "avg_processing_time": float(row.avg_processing_time or 0)
            }
            total_jobs += row.count
            if row.avg_processing_time:
                total_processing_time += row.avg_processing_time * row.count
        
        return {
            "total_jobs": total_jobs,
            "avg_processing_time": total_processing_time / total_jobs if total_jobs > 0 else 0,
            "by_status": stats_by_status
        }
    
    async def _get_popular_formats(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get popular file formats."""
        conditions = [
            MediaFile.created_at >= start_date,
            MediaFile.created_at <= end_date,
            MediaFile.status != MediaStatus.DELETED
        ]
        
        if user_id:
            conditions.append(MediaFile.owner_id == user_id)
        
        query = select(
            MediaFile.mime_type,
            func.count(MediaFile.id).label('count'),
            func.sum(MediaFile.file_size).label('total_size')
        ).where(and_(*conditions)).group_by(MediaFile.mime_type).order_by(
            func.count(MediaFile.id).desc()
        ).limit(10)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "mime_type": row.mime_type,
                "count": row.count,
                "total_size": row.total_size or 0
            }
            for row in rows
        ]
    
    async def _get_user_activity(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get user activity metrics."""
        if user_id:
            # Single user activity
            conditions = [
                MediaFile.created_at >= start_date,
                MediaFile.created_at <= end_date,
                MediaFile.owner_id == user_id
            ]
            
            # Get upload activity by hour
            query = select(
                func.extract('hour', MediaFile.created_at).label('hour'),
                func.count(MediaFile.id).label('count')
            ).where(and_(*conditions)).group_by(
                func.extract('hour', MediaFile.created_at)
            ).order_by('hour')
            
            result = await db.execute(query)
            rows = result.all()
            
            activity_by_hour = {int(row.hour): row.count for row in rows}
            
            # Get most active day
            day_query = select(
                func.date(MediaFile.created_at).label('date'),
                func.count(MediaFile.id).label('count')
            ).where(and_(*conditions)).group_by(
                func.date(MediaFile.created_at)
            ).order_by(func.count(MediaFile.id).desc()).limit(1)
            
            day_result = await db.execute(day_query)
            most_active_day = day_result.first()
            
            return {
                "activity_by_hour": activity_by_hour,
                "most_active_day": {
                    "date": most_active_day.date.isoformat() if most_active_day else None,
                    "count": most_active_day.count if most_active_day else 0
                }
            }
        else:
            # Global user activity
            conditions = [
                MediaFile.created_at >= start_date,
                MediaFile.created_at <= end_date
            ]
            
            # Get top active users
            query = select(
                MediaFile.owner_id,
                func.count(MediaFile.id).label('upload_count'),
                func.sum(MediaFile.file_size).label('total_size')
            ).where(and_(*conditions)).group_by(MediaFile.owner_id).order_by(
                func.count(MediaFile.id).desc()
            ).limit(10)
            
            result = await db.execute(query)
            rows = result.all()
            
            top_users = [
                {
                    "user_id": str(row.owner_id),
                    "upload_count": row.upload_count,
                    "total_size": row.total_size or 0
                }
                for row in rows
            ]
            
            return {"top_users": top_users}
    
    async def get_processing_performance_metrics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        operation: Optional[ProcessingOperation] = None
    ) -> Dict[str, Any]:
        """Get processing performance metrics."""
        try:
            conditions = [
                ProcessingJob.created_at >= start_date,
                ProcessingJob.created_at <= end_date,
                ProcessingJob.status == ProcessingStatus.COMPLETED,
                ProcessingJob.processing_time.isnot(None)
            ]
            
            if operation:
                conditions.append(ProcessingJob.operation == operation)
            
            # Get performance stats
            query = select(
                ProcessingJob.operation,
                func.count(ProcessingJob.id).label('total_jobs'),
                func.avg(ProcessingJob.processing_time).label('avg_time'),
                func.min(ProcessingJob.processing_time).label('min_time'),
                func.max(ProcessingJob.processing_time).label('max_time'),
                func.percentile_cont(0.5).within_group(ProcessingJob.processing_time).label('median_time'),
                func.percentile_cont(0.95).within_group(ProcessingJob.processing_time).label('p95_time')
            ).where(and_(*conditions)).group_by(ProcessingJob.operation)
            
            result = await db.execute(query)
            rows = result.all()
            
            performance_by_operation = {}
            for row in rows:
                performance_by_operation[row.operation] = {
                    "total_jobs": row.total_jobs,
                    "avg_time": float(row.avg_time or 0),
                    "min_time": float(row.min_time or 0),
                    "max_time": float(row.max_time or 0),
                    "median_time": float(row.median_time or 0),
                    "p95_time": float(row.p95_time or 0)
                }
            
            # Get failure rate
            failure_query = select(
                ProcessingJob.operation,
                func.count(ProcessingJob.id).label('total'),
                func.sum(
                    func.case(
                        (ProcessingJob.status == ProcessingStatus.FAILED, 1),
                        else_=0
                    )
                ).label('failed')
            ).where(
                and_(
                    ProcessingJob.created_at >= start_date,
                    ProcessingJob.created_at <= end_date,
                    ProcessingJob.operation == operation if operation else True
                )
            ).group_by(ProcessingJob.operation)
            
            failure_result = await db.execute(failure_query)
            failure_rows = failure_result.all()
            
            for row in failure_rows:
                if row.operation in performance_by_operation:
                    failure_rate = (row.failed / row.total * 100) if row.total > 0 else 0
                    performance_by_operation[row.operation]["failure_rate"] = failure_rate
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "performance_by_operation": performance_by_operation
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing performance metrics: {e}")
            raise MediaServiceException(f"Performance metrics query failed: {str(e)}")
    
    async def get_system_health_metrics(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get system health metrics."""
        try:
            now = datetime.utcnow()
            last_hour = now - timedelta(hours=1)
            last_day = now - timedelta(days=1)
            
            # Get recent upload rate
            upload_rate_query = select(
                func.count(MediaFile.id).label('uploads_last_hour')
            ).where(
                and_(
                    MediaFile.created_at >= last_hour,
                    MediaFile.created_at <= now
                )
            )
            
            upload_result = await db.execute(upload_rate_query)
            uploads_last_hour = upload_result.scalar() or 0
            
            # Get processing queue size
            queue_query = select(
                func.count(ProcessingJob.id).label('pending_jobs')
            ).where(ProcessingJob.status == ProcessingStatus.PENDING)
            
            queue_result = await db.execute(queue_query)
            pending_jobs = queue_result.scalar() or 0
            
            # Get error rate
            error_query = select(
                func.count(ProcessingJob.id).label('total_jobs'),
                func.sum(
                    func.case(
                        (ProcessingJob.status == ProcessingStatus.FAILED, 1),
                        else_=0
                    )
                ).label('failed_jobs')
            ).where(
                and_(
                    ProcessingJob.created_at >= last_day,
                    ProcessingJob.created_at <= now
                )
            )
            
            error_result = await db.execute(error_query)
            error_row = error_result.first()
            
            total_jobs = error_row.total_jobs or 0
            failed_jobs = error_row.failed_jobs or 0
            error_rate = (failed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            # Get storage usage
            storage_query = select(
                func.count(MediaFile.id).label('total_files'),
                func.sum(MediaFile.file_size).label('total_size')
            ).where(MediaFile.status != MediaStatus.DELETED)
            
            storage_result = await db.execute(storage_query)
            storage_row = storage_result.first()
            
            return {
                "timestamp": now.isoformat(),
                "upload_rate": {
                    "uploads_last_hour": uploads_last_hour,
                    "uploads_per_minute": uploads_last_hour / 60
                },
                "processing_queue": {
                    "pending_jobs": pending_jobs
                },
                "error_rate": {
                    "percentage_last_24h": error_rate,
                    "failed_jobs_last_24h": failed_jobs,
                    "total_jobs_last_24h": total_jobs
                },
                "storage": {
                    "total_files": storage_row.total_files or 0,
                    "total_size_bytes": storage_row.total_size or 0,
                    "total_size_gb": (storage_row.total_size or 0) / (1024**3)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get system health metrics: {e}")
            raise MediaServiceException(f"Health metrics query failed: {str(e)}")
    
    async def clear_analytics_cache(self, pattern: Optional[str] = None) -> int:
        """
        Clear analytics cache.
        
        Args:
            pattern: Cache key pattern to match (e.g., "storage_stats:*")
        
        Returns:
            Number of cache entries cleared
        """
        try:
            if pattern:
                # Clear specific pattern
                keys = await self.cache.get_keys(pattern)
                if keys:
                    await self.cache.delete_many(keys)
                    return len(keys)
            else:
                # Clear all analytics cache
                patterns = [
                    "storage_stats:*",
                    "media_analytics:*",
                    "processing_performance:*",
                    "system_health:*"
                ]
                
                total_cleared = 0
                for p in patterns:
                    keys = await self.cache.get_keys(p)
                    if keys:
                        await self.cache.delete_many(keys)
                        total_cleared += len(keys)
                
                return total_cleared
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to clear analytics cache: {e}")
            return 0