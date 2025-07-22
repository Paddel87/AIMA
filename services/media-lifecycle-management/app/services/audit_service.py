#!/usr/bin/env python3
"""
Audit Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive audit logging, compliance tracking,
and security monitoring for all system activities.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, asdict
from ipaddress import ip_address, IPv4Address, IPv6Address

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload

from ..core.database import AuditLog, MediaFile, ProcessingJob
from ..core.redis_client import CacheManager
from ..models.common import ProcessingStatus
from ..middleware.error_handling import MediaServiceException


logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types."""
    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    
    # Media file events
    MEDIA_UPLOADED = "media_uploaded"
    MEDIA_DOWNLOADED = "media_downloaded"
    MEDIA_VIEWED = "media_viewed"
    MEDIA_UPDATED = "media_updated"
    MEDIA_DELETED = "media_deleted"
    MEDIA_RESTORED = "media_restored"
    MEDIA_ARCHIVED = "media_archived"
    MEDIA_SHARED = "media_shared"
    MEDIA_UNSHARED = "media_unshared"
    
    # Processing events
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    PROCESSING_CANCELLED = "processing_cancelled"
    
    # Storage events
    STORAGE_QUOTA_EXCEEDED = "storage_quota_exceeded"
    STORAGE_CLEANUP = "storage_cleanup"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIGURATION_CHANGED = "configuration_changed"
    MAINTENANCE_MODE = "maintenance_mode"
    
    # Security events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    SECURITY_SCAN = "security_scan"
    
    # Data events
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_PURGE = "data_purge"
    GDPR_REQUEST = "gdpr_request"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditStatus(str, Enum):
    """Audit event status."""
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class AuditContext:
    """Context information for audit events."""
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    api_key_id: Optional[UUID] = None
    service_name: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: str(v) if isinstance(v, UUID) else v 
                for k, v in asdict(self).items() if v is not None}


@dataclass
class AuditEvent:
    """Audit event data structure."""
    event_type: AuditEventType
    severity: AuditSeverity
    status: AuditStatus
    message: str
    context: AuditContext
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class AuditService:
    """Service for audit logging and compliance tracking."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        
        # Configuration
        self.retention_days = 2555  # 7 years for compliance
        self.high_frequency_events_ttl = 3600  # 1 hour cache for high-frequency events
        self.batch_size = 100
        self.max_details_size = 10000  # Max size for details field
        
        # Security monitoring
        self.suspicious_activity_threshold = {
            "failed_logins": 5,
            "rate_limit_hits": 10,
            "unusual_access_patterns": 3
        }
        
        # Event batching for performance
        self.event_batch: List[AuditEvent] = []
        self.last_batch_flush = datetime.utcnow()
        self.batch_flush_interval = timedelta(seconds=30)
    
    async def log_event(
        self,
        db: AsyncSession,
        event: AuditEvent,
        immediate_flush: bool = False
    ) -> bool:
        """
        Log an audit event.
        
        Args:
            db: Database session
            event: Audit event to log
            immediate_flush: Whether to flush immediately (for critical events)
        
        Returns:
            True if event was logged successfully
        """
        try:
            # Validate event
            self._validate_event(event)
            
            # Sanitize sensitive data
            sanitized_event = self._sanitize_event(event)
            
            # Add to batch
            self.event_batch.append(sanitized_event)
            
            # Check if we should flush
            should_flush = (
                immediate_flush or
                len(self.event_batch) >= self.batch_size or
                datetime.utcnow() - self.last_batch_flush >= self.batch_flush_interval or
                sanitized_event.severity == AuditSeverity.CRITICAL
            )
            
            if should_flush:
                await self._flush_event_batch(db)
            
            # Cache recent events for quick access
            await self._cache_recent_event(sanitized_event)
            
            # Check for suspicious activity
            await self._check_suspicious_activity(db, sanitized_event)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return False
    
    async def log_authentication_event(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        user_id: Optional[UUID],
        context: AuditContext,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log authentication-related events.
        """
        severity = AuditSeverity.MEDIUM if success else AuditSeverity.HIGH
        status = AuditStatus.SUCCESS if success else AuditStatus.FAILURE
        
        message = self._get_event_message(event_type, success, details)
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            status=status,
            message=message,
            context=context,
            resource_type="user",
            resource_id=user_id,
            details=details
        )
        
        return await self.log_event(db, event, immediate_flush=not success)
    
    async def log_media_event(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        media_file: MediaFile,
        context: AuditContext,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log media file-related events.
        """
        severity = self._get_media_event_severity(event_type)
        status = AuditStatus.SUCCESS if success else AuditStatus.FAILURE
        
        message = self._get_media_event_message(event_type, media_file, success)
        
        # Add media file details
        event_details = {
            "filename": media_file.filename,
            "media_type": media_file.media_type.value,
            "file_size": media_file.file_size,
            "storage_tier": media_file.storage_tier.value if media_file.storage_tier else None
        }
        
        if details:
            event_details.update(details)
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            status=status,
            message=message,
            context=context,
            resource_type="media_file",
            resource_id=media_file.id,
            details=event_details
        )
        
        return await self.log_event(db, event)
    
    async def log_processing_event(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        processing_job: ProcessingJob,
        context: AuditContext,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log processing job-related events.
        """
        severity = AuditSeverity.LOW
        status = AuditStatus.SUCCESS
        
        if event_type == AuditEventType.PROCESSING_FAILED:
            severity = AuditSeverity.MEDIUM
            status = AuditStatus.FAILURE
        
        message = self._get_processing_event_message(event_type, processing_job)
        
        # Add processing job details
        event_details = {
            "operation": processing_job.operation.value,
            "status": processing_job.status.value,
            "processing_time": processing_job.processing_time
        }
        
        if details:
            event_details.update(details)
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            status=status,
            message=message,
            context=context,
            resource_type="processing_job",
            resource_id=processing_job.id,
            details=event_details
        )
        
        return await self.log_event(db, event)
    
    async def log_security_event(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        context: AuditContext,
        severity: AuditSeverity = AuditSeverity.HIGH,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log security-related events.
        """
        message = self._get_security_event_message(event_type, details)
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            status=AuditStatus.WARNING,
            message=message,
            context=context,
            resource_type="security",
            details=details
        )
        
        return await self.log_event(db, event, immediate_flush=True)
    
    async def log_system_event(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        message: str,
        context: AuditContext,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log system-related events.
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            status=AuditStatus.SUCCESS,
            message=message,
            context=context,
            resource_type="system",
            details=details
        )
        
        return await self.log_event(db, event)
    
    async def search_audit_logs(
        self,
        db: AsyncSession,
        filters: Dict[str, Any],
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search audit logs with filters.
        
        Args:
            db: Database session
            filters: Search filters
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            Search results with logs and metadata
        """
        try:
            # Build query conditions
            conditions = []
            
            if "event_types" in filters:
                conditions.append(AuditLog.event_type.in_(filters["event_types"]))
            
            if "severity" in filters:
                conditions.append(AuditLog.severity.in_(filters["severity"]))
            
            if "status" in filters:
                conditions.append(AuditLog.status.in_(filters["status"]))
            
            if "user_id" in filters:
                conditions.append(AuditLog.user_id == filters["user_id"])
            
            if "resource_type" in filters:
                conditions.append(AuditLog.resource_type == filters["resource_type"])
            
            if "resource_id" in filters:
                conditions.append(AuditLog.resource_id == filters["resource_id"])
            
            if "start_date" in filters:
                conditions.append(AuditLog.timestamp >= filters["start_date"])
            
            if "end_date" in filters:
                conditions.append(AuditLog.timestamp <= filters["end_date"])
            
            if "ip_address" in filters:
                conditions.append(AuditLog.ip_address == filters["ip_address"])
            
            if "search_text" in filters:
                search_text = f"%{filters['search_text']}%"
                conditions.append(
                    or_(
                        AuditLog.message.ilike(search_text),
                        AuditLog.details.astext.ilike(search_text)
                    )
                )
            
            # Get total count
            count_query = select(func.count(AuditLog.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            count_result = await db.execute(count_query)
            total_count = count_result.scalar() or 0
            
            # Get logs
            logs_query = select(AuditLog).order_by(AuditLog.timestamp.desc())
            
            if conditions:
                logs_query = logs_query.where(and_(*conditions))
            
            logs_query = logs_query.limit(limit).offset(offset)
            
            logs_result = await db.execute(logs_query)
            logs = logs_result.scalars().all()
            
            # Convert to dict format
            log_data = []
            for log in logs:
                log_dict = {
                    "id": str(log.id),
                    "event_type": log.event_type,
                    "severity": log.severity,
                    "status": log.status,
                    "message": log.message,
                    "timestamp": log.timestamp.isoformat(),
                    "user_id": str(log.user_id) if log.user_id else None,
                    "session_id": log.session_id,
                    "request_id": log.request_id,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id) if log.resource_id else None,
                    "details": log.details
                }
                log_data.append(log_dict)
            
            return {
                "logs": log_data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(logs) < total_count
            }
            
        except Exception as e:
            logger.error(f"Failed to search audit logs: {e}")
            raise MediaServiceException(f"Audit log search failed: {str(e)}")
    
    async def get_audit_statistics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """
        Get audit statistics for a time period.
        
        Args:
            db: Database session
            start_date: Start date for statistics
            end_date: End date for statistics
            group_by: Grouping interval (day, hour, week)
        
        Returns:
            Audit statistics
        """
        try:
            # Get event counts by type
            event_type_query = select(
                AuditLog.event_type,
                func.count(AuditLog.id).label('count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).group_by(AuditLog.event_type)
            
            event_type_result = await db.execute(event_type_query)
            event_type_stats = {row.event_type: row.count for row in event_type_result}
            
            # Get severity distribution
            severity_query = select(
                AuditLog.severity,
                func.count(AuditLog.id).label('count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).group_by(AuditLog.severity)
            
            severity_result = await db.execute(severity_query)
            severity_stats = {row.severity: row.count for row in severity_result}
            
            # Get status distribution
            status_query = select(
                AuditLog.status,
                func.count(AuditLog.id).label('count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).group_by(AuditLog.status)
            
            status_result = await db.execute(status_query)
            status_stats = {row.status: row.count for row in status_result}
            
            # Get timeline data
            if group_by == "hour":
                time_format = "YYYY-MM-DD HH24:00:00"
            elif group_by == "week":
                time_format = "YYYY-WW"
            else:  # day
                time_format = "YYYY-MM-DD"
            
            timeline_query = select(
                func.to_char(AuditLog.timestamp, time_format).label('period'),
                func.count(AuditLog.id).label('count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).group_by('period').order_by('period')
            
            timeline_result = await db.execute(timeline_query)
            timeline_stats = [
                {"period": row.period, "count": row.count}
                for row in timeline_result
            ]
            
            # Get top users by activity
            user_activity_query = select(
                AuditLog.user_id,
                func.count(AuditLog.id).label('activity_count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                    AuditLog.user_id.isnot(None)
                )
            ).group_by(AuditLog.user_id).order_by(
                func.count(AuditLog.id).desc()
            ).limit(10)
            
            user_activity_result = await db.execute(user_activity_query)
            user_activity_stats = [
                {"user_id": str(row.user_id), "activity_count": row.activity_count}
                for row in user_activity_result
            ]
            
            # Get top IP addresses
            ip_activity_query = select(
                AuditLog.ip_address,
                func.count(AuditLog.id).label('request_count')
            ).where(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                    AuditLog.ip_address.isnot(None)
                )
            ).group_by(AuditLog.ip_address).order_by(
                func.count(AuditLog.id).desc()
            ).limit(10)
            
            ip_activity_result = await db.execute(ip_activity_query)
            ip_activity_stats = [
                {"ip_address": row.ip_address, "request_count": row.request_count}
                for row in ip_activity_result
            ]
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "group_by": group_by
                },
                "event_types": event_type_stats,
                "severity_distribution": severity_stats,
                "status_distribution": status_stats,
                "timeline": timeline_stats,
                "top_users": user_activity_stats,
                "top_ip_addresses": ip_activity_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get audit statistics: {e}")
            raise MediaServiceException(f"Audit statistics query failed: {str(e)}")
    
    async def cleanup_old_audit_logs(
        self,
        db: AsyncSession
    ) -> int:
        """
        Clean up old audit logs based on retention policy.
        
        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Delete old logs
            delete_query = text(
                "DELETE FROM audit_logs WHERE timestamp < :cutoff_date"
            ).bindparam(cutoff_date=cutoff_date)
            
            result = await db.execute(delete_query)
            deleted_count = result.rowcount
            
            await db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
            await db.rollback()
            return 0
    
    async def export_audit_logs(
        self,
        db: AsyncSession,
        filters: Dict[str, Any],
        format: str = "json"
    ) -> bytes:
        """
        Export audit logs for compliance or analysis.
        
        Args:
            db: Database session
            filters: Export filters
            format: Export format (json, csv)
        
        Returns:
            Exported data as bytes
        """
        try:
            # Get logs using search function
            search_result = await self.search_audit_logs(
                db, filters, limit=10000, offset=0
            )
            
            logs = search_result["logs"]
            
            if format.lower() == "json":
                export_data = json.dumps({
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "filters": filters,
                    "total_logs": len(logs),
                    "logs": logs
                }, indent=2)
                return export_data.encode('utf-8')
            
            elif format.lower() == "csv":
                import csv
                import io
                
                output = io.StringIO()
                
                if logs:
                    fieldnames = logs[0].keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for log in logs:
                        # Convert complex fields to JSON strings
                        row = {}
                        for key, value in log.items():
                            if isinstance(value, (dict, list)):
                                row[key] = json.dumps(value)
                            else:
                                row[key] = value
                        writer.writerow(row)
                
                return output.getvalue().encode('utf-8')
            
            else:
                raise MediaServiceException(f"Unsupported export format: {format}")
            
        except Exception as e:
            logger.error(f"Failed to export audit logs: {e}")
            raise MediaServiceException(f"Audit log export failed: {str(e)}")
    
    # Helper methods
    
    def _validate_event(self, event: AuditEvent):
        """Validate audit event data."""
        if not event.message:
            raise ValueError("Event message is required")
        
        if event.details and len(json.dumps(event.details)) > self.max_details_size:
            raise ValueError("Event details too large")
        
        # Validate IP address if provided
        if event.context.ip_address:
            try:
                ip_address(event.context.ip_address)
            except ValueError:
                raise ValueError(f"Invalid IP address: {event.context.ip_address}")
    
    def _sanitize_event(self, event: AuditEvent) -> AuditEvent:
        """Sanitize event data to remove sensitive information."""
        # Create a copy to avoid modifying the original
        sanitized_details = None
        if event.details:
            sanitized_details = self._sanitize_details(event.details.copy())
        
        # Sanitize user agent (remove potentially sensitive info)
        sanitized_user_agent = None
        if event.context.user_agent:
            sanitized_user_agent = event.context.user_agent[:500]  # Limit length
        
        # Create sanitized context
        sanitized_context = AuditContext(
            user_id=event.context.user_id,
            session_id=event.context.session_id,
            request_id=event.context.request_id,
            ip_address=event.context.ip_address,
            user_agent=sanitized_user_agent,
            api_key_id=event.context.api_key_id,
            service_name=event.context.service_name,
            endpoint=event.context.endpoint,
            method=event.context.method
        )
        
        return AuditEvent(
            event_type=event.event_type,
            severity=event.severity,
            status=event.status,
            message=event.message[:1000],  # Limit message length
            context=sanitized_context,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            details=sanitized_details,
            timestamp=event.timestamp
        )
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from event details."""
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'credential',
            'authorization', 'cookie', 'session'
        }
        
        sanitized = {}
        for key, value in details.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive information
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def _flush_event_batch(self, db: AsyncSession):
        """Flush the current batch of events to the database."""
        if not self.event_batch:
            return
        
        try:
            # Create audit log records
            audit_logs = []
            for event in self.event_batch:
                audit_log = AuditLog(
                    id=uuid4(),
                    event_type=event.event_type,
                    severity=event.severity,
                    status=event.status,
                    message=event.message,
                    timestamp=event.timestamp,
                    user_id=event.context.user_id,
                    session_id=event.context.session_id,
                    request_id=event.context.request_id,
                    ip_address=event.context.ip_address,
                    user_agent=event.context.user_agent,
                    api_key_id=event.context.api_key_id,
                    service_name=event.context.service_name,
                    endpoint=event.context.endpoint,
                    method=event.context.method,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    details=event.details
                )
                audit_logs.append(audit_log)
            
            # Bulk insert
            db.add_all(audit_logs)
            await db.commit()
            
            logger.debug(f"Flushed {len(self.event_batch)} audit events to database")
            
            # Clear batch
            self.event_batch.clear()
            self.last_batch_flush = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to flush audit event batch: {e}")
            await db.rollback()
            # Don't clear batch on error - will retry later
    
    async def _cache_recent_event(self, event: AuditEvent):
        """Cache recent events for quick access."""
        try:
            cache_key = f"recent_audit_events:{event.context.user_id or 'system'}"
            
            # Get existing recent events
            recent_events = await self.cache.get(cache_key) or []
            
            # Add new event
            event_data = {
                "event_type": event.event_type.value,
                "severity": event.severity.value,
                "status": event.status.value,
                "message": event.message,
                "timestamp": event.timestamp.isoformat(),
                "resource_type": event.resource_type,
                "resource_id": str(event.resource_id) if event.resource_id else None
            }
            
            recent_events.append(event_data)
            
            # Keep only last 50 events
            if len(recent_events) > 50:
                recent_events = recent_events[-50:]
            
            # Cache for 1 hour
            await self.cache.set(cache_key, recent_events, ttl=3600)
            
        except Exception as e:
            logger.error(f"Failed to cache recent audit event: {e}")
    
    async def _check_suspicious_activity(
        self,
        db: AsyncSession,
        event: AuditEvent
    ):
        """Check for suspicious activity patterns."""
        try:
            # Check for failed login attempts
            if event.event_type == AuditEventType.USER_LOGIN_FAILED:
                await self._check_failed_login_pattern(db, event)
            
            # Check for rate limit violations
            elif event.event_type == AuditEventType.RATE_LIMIT_EXCEEDED:
                await self._check_rate_limit_pattern(db, event)
            
            # Check for unusual access patterns
            elif event.event_type in [AuditEventType.MEDIA_DOWNLOADED, AuditEventType.MEDIA_VIEWED]:
                await self._check_access_pattern(db, event)
            
        except Exception as e:
            logger.error(f"Failed to check suspicious activity: {e}")
    
    async def _check_failed_login_pattern(
        self,
        db: AsyncSession,
        event: AuditEvent
    ):
        """Check for suspicious failed login patterns."""
        if not event.context.ip_address:
            return
        
        # Count recent failed logins from same IP
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        failed_login_query = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.event_type == AuditEventType.USER_LOGIN_FAILED,
                AuditLog.ip_address == event.context.ip_address,
                AuditLog.timestamp >= one_hour_ago
            )
        )
        
        result = await db.execute(failed_login_query)
        failed_count = result.scalar() or 0
        
        if failed_count >= self.suspicious_activity_threshold["failed_logins"]:
            # Log suspicious activity
            await self.log_security_event(
                db=db,
                event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                context=event.context,
                severity=AuditSeverity.HIGH,
                details={
                    "pattern": "multiple_failed_logins",
                    "failed_count": failed_count,
                    "time_window": "1_hour",
                    "threshold": self.suspicious_activity_threshold["failed_logins"]
                }
            )
    
    async def _check_rate_limit_pattern(
        self,
        db: AsyncSession,
        event: AuditEvent
    ):
        """Check for rate limit violation patterns."""
        # Similar implementation to failed login pattern
        pass
    
    async def _check_access_pattern(
        self,
        db: AsyncSession,
        event: AuditEvent
    ):
        """Check for unusual access patterns."""
        # Implementation for detecting unusual access patterns
        pass
    
    def _get_event_message(
        self,
        event_type: AuditEventType,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate event message based on type and context."""
        messages = {
            AuditEventType.USER_LOGIN: "User login successful" if success else "User login failed",
            AuditEventType.USER_LOGOUT: "User logout",
            AuditEventType.TOKEN_REFRESH: "Token refresh successful" if success else "Token refresh failed",
            AuditEventType.ACCESS_GRANTED: "Access granted",
            AuditEventType.ACCESS_DENIED: "Access denied"
        }
        
        base_message = messages.get(event_type, event_type.value.replace('_', ' ').title())
        
        if details and "reason" in details:
            base_message += f": {details['reason']}"
        
        return base_message
    
    def _get_media_event_message(
        self,
        event_type: AuditEventType,
        media_file: MediaFile,
        success: bool
    ) -> str:
        """Generate media event message."""
        action = event_type.value.replace('media_', '').replace('_', ' ')
        status = "successful" if success else "failed"
        return f"Media file {action} {status}: {media_file.filename}"
    
    def _get_processing_event_message(
        self,
        event_type: AuditEventType,
        processing_job: ProcessingJob
    ) -> str:
        """Generate processing event message."""
        action = event_type.value.replace('processing_', '').replace('_', ' ')
        return f"Processing job {action}: {processing_job.operation.value}"
    
    def _get_security_event_message(
        self,
        event_type: AuditEventType,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate security event message."""
        base_message = event_type.value.replace('_', ' ').title()
        
        if details:
            if "pattern" in details:
                base_message += f" - Pattern: {details['pattern']}"
            if "reason" in details:
                base_message += f" - Reason: {details['reason']}"
        
        return base_message
    
    def _get_media_event_severity(self, event_type: AuditEventType) -> AuditSeverity:
        """Get severity level for media events."""
        high_severity_events = {
            AuditEventType.MEDIA_DELETED,
            AuditEventType.MEDIA_SHARED,
            AuditEventType.MEDIA_UNSHARED
        }
        
        if event_type in high_severity_events:
            return AuditSeverity.HIGH
        
        return AuditSeverity.MEDIUM