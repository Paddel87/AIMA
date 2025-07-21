#!/usr/bin/env python3
"""
Audit service for the AIMA User Management Service.

This module contains the business logic for audit log operations.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.core.database import AuditLog
from app.models.schemas import AuditAction, AuditLogResponse


class AuditService:
    """Service class for audit log operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_audit_log(
        self,
        action: AuditAction,
        resource_type: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> AuditLog:
        """Create an audit log entry."""
        try:
            audit_log = AuditLog(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id) if user_id else None,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)
            
            return audit_log
            
        except Exception as e:
            self.db.rollback()
            raise e
    
    async def get_audit_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AuditLog]:
        """Get audit logs with filtering."""
        query = self.db.query(AuditLog)
        
        # Apply filters
        if user_id:
            query = query.filter(AuditLog.user_id == uuid.UUID(user_id))
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        # Order by timestamp descending and apply pagination
        logs = query.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()
        
        return logs
    
    async def get_audit_log_count(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """Get total count of audit logs with filtering."""
        query = self.db.query(AuditLog)
        
        # Apply filters
        if user_id:
            query = query.filter(AuditLog.user_id == uuid.UUID(user_id))
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        return query.count()
    
    async def get_user_activity(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[AuditLog]:
        """Get recent activity for a specific user."""
        logs = self.db.query(AuditLog).filter(
            AuditLog.user_id == uuid.UUID(user_id)
        ).order_by(desc(AuditLog.timestamp)).limit(limit).all()
        
        return logs
    
    async def get_recent_activity(
        self,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get recent system activity."""
        logs = self.db.query(AuditLog).order_by(
            desc(AuditLog.timestamp)
        ).limit(limit).all()
        
        return logs
    
    async def cleanup_old_logs(
        self,
        days_to_keep: int = 90
    ) -> int:
        """Clean up old audit logs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = self.db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff_date
        ).delete()
        
        self.db.commit()
        
        return deleted_count