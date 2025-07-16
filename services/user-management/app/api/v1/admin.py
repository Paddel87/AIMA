"""Admin API routes for user management."""

from datetime import datetime, timedelta
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.user import User, UserSession, AuditLog
from app.schemas.admin import (
    AdminStatsResponse,
    SystemHealthResponse,
    UserActivityResponse,
    AuditLogResponse,
    BulkUserActionRequest,
    BulkUserActionResponse,
    SystemConfigResponse,
    SystemConfigUpdate
)
from app.schemas.user import UserResponse
from app.services.user_service import UserService
from app.services.audit_service import AuditService
from app.core.permissions import require_admin

router = APIRouter()


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Get comprehensive admin statistics."""
    # User statistics
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = total_users - active_users
    
    # Users by role
    users_by_role = {}
    for role in ["admin", "user", "analyst", "viewer"]:
        count = db.query(User).filter(User.role == role).count()
        users_by_role[role] = count
    
    # Users by status
    users_by_status = {}
    for status_val in ["active", "suspended", "pending", "deleted"]:
        count = db.query(User).filter(User.status == status_val).count()
        users_by_status[status_val] = count
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = db.query(User).filter(
        User.created_at >= thirty_days_ago
    ).count()
    
    # Login statistics
    total_logins = db.query(func.sum(User.login_count)).scalar() or 0
    recent_logins = db.query(User).filter(
        User.last_login >= thirty_days_ago
    ).count() if thirty_days_ago else 0
    
    # Session statistics
    active_sessions = db.query(UserSession).filter(
        UserSession.status == "active",
        UserSession.expires_at > datetime.utcnow()
    ).count()
    
    total_sessions = db.query(UserSession).count()
    
    # Security statistics
    locked_accounts = db.query(User).filter(
        User.account_locked_until > datetime.utcnow()
    ).count()
    
    failed_login_attempts = db.query(
        func.sum(User.failed_login_attempts)
    ).scalar() or 0
    
    return AdminStatsResponse(
        user_stats={
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "by_role": users_by_role,
            "by_status": users_by_status,
            "new_30d": new_users_30d
        },
        session_stats={
            "active": active_sessions,
            "total": total_sessions
        },
        security_stats={
            "locked_accounts": locked_accounts,
            "failed_login_attempts": failed_login_attempts
        },
        activity_stats={
            "total_logins": total_logins,
            "recent_logins": recent_logins
        }
    )


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Get system health status."""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "healthy"
        db_message = "Database connection successful"
    except Exception as e:
        db_status = "unhealthy"
        db_message = f"Database error: {str(e)}"
    
    # Check for system issues
    issues = []
    
    # Check for too many failed login attempts
    high_failed_logins = db.query(User).filter(
        User.failed_login_attempts > 10
    ).count()
    
    if high_failed_logins > 0:
        issues.append(f"{high_failed_logins} users with high failed login attempts")
    
    # Check for expired sessions that haven't been cleaned up
    expired_sessions = db.query(UserSession).filter(
        UserSession.status == "active",
        UserSession.expires_at < datetime.utcnow()
    ).count()
    
    if expired_sessions > 100:
        issues.append(f"{expired_sessions} expired sessions need cleanup")
    
    # Overall system status
    overall_status = "healthy" if db_status == "healthy" and not issues else "warning"
    
    return SystemHealthResponse(
        status=overall_status,
        database={
            "status": db_status,
            "message": db_message
        },
        issues=issues,
        timestamp=datetime.utcnow()
    )


@router.get("/activity", response_model=List[UserActivityResponse])
async def get_user_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=500, description="Number of activities to return"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type")
) -> Any:
    """Get recent user activity."""
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    if action:
        query = query.filter(AuditLog.action == action)
    
    activities = query.limit(limit).all()
    
    return [
        UserActivityResponse(
            id=activity.id,
            user_id=activity.user_id,
            action=activity.action,
            resource_type=activity.resource_type,
            resource_id=activity.resource_id,
            details=activity.details,
            ip_address=activity.ip_address,
            user_agent=activity.user_agent,
            success=activity.success,
            error_message=activity.error_message,
            created_at=activity.created_at
        )
        for activity in activities
    ]


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = Query(0, ge=0, description="Number of logs to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter")
) -> Any:
    """Get audit logs with filtering."""
    audit_service = AuditService(db)
    
    logs = await audit_service.get_audit_logs(
        skip=skip,
        limit=limit,
        user_id=user_id,
        action=action,
        start_date=start_date,
        end_date=end_date
    )
    
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            success=log.success,
            error_message=log.error_message,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.post("/bulk-actions", response_model=BulkUserActionResponse)
async def perform_bulk_action(
    action_request: BulkUserActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Perform bulk actions on users."""
    user_service = UserService(db)
    
    results = {
        "success": [],
        "failed": [],
        "total_processed": len(action_request.user_ids)
    }
    
    for user_id in action_request.user_ids:
        try:
            if action_request.action == "activate":
                await user_service.update_user(
                    user_id,
                    {"is_active": True, "status": "active"}
                )
            elif action_request.action == "deactivate":
                await user_service.update_user(
                    user_id,
                    {"is_active": False, "status": "suspended"}
                )
            elif action_request.action == "delete":
                await user_service.delete_user(user_id)
            elif action_request.action == "unlock":
                await user_service.update_user(
                    user_id,
                    {
                        "account_locked_until": None,
                        "failed_login_attempts": 0
                    }
                )
            
            results["success"].append(str(user_id))
            
        except Exception as e:
            results["failed"].append({
                "user_id": str(user_id),
                "error": str(e)
            })
    
    return BulkUserActionResponse(
        action=action_request.action,
        results=results,
        performed_by=str(current_user.id),
        performed_at=datetime.utcnow()
    )


@router.get("/sessions", response_model=List[dict])
async def get_active_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    limit: int = Query(100, ge=1, le=1000, description="Number of sessions to return")
) -> Any:
    """Get active user sessions."""
    sessions = db.query(UserSession).filter(
        UserSession.status == "active",
        UserSession.expires_at > datetime.utcnow()
    ).order_by(UserSession.last_activity.desc()).limit(limit).all()
    
    return [
        {
            "id": str(session.id),
            "user_id": str(session.user_id),
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "expires_at": session.expires_at
        }
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Revoke a specific user session."""
    session = db.query(UserSession).filter(
        UserSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.status = "revoked"
    db.commit()
    
    # Log the action
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="session_revoke",
        resource_type="user_session",
        resource_id=str(session_id),
        details={"revoked_by_admin": True},
        success=True
    )
    
    return None


@router.post("/cleanup", response_model=dict)
async def cleanup_system(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Perform system cleanup tasks."""
    results = {}
    
    # Clean up expired sessions
    expired_sessions = db.query(UserSession).filter(
        UserSession.status == "active",
        UserSession.expires_at < datetime.utcnow()
    ).update({"status": "expired"})
    
    results["expired_sessions_cleaned"] = expired_sessions
    
    # Clean up old audit logs (older than 1 year)
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    old_logs = db.query(AuditLog).filter(
        AuditLog.created_at < one_year_ago
    ).count()
    
    # Don't actually delete in this example, just count
    results["old_audit_logs_found"] = old_logs
    
    db.commit()
    
    # Log the cleanup action
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="system_cleanup",
        resource_type="system",
        details=results,
        success=True
    )
    
    return {
        "message": "System cleanup completed",
        "results": results,
        "performed_by": str(current_user.id),
        "performed_at": datetime.utcnow()
    }


@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(
    current_user: User = Depends(require_admin)
) -> Any:
    """Get system configuration."""
    return SystemConfigResponse(
        max_login_attempts=settings.MAX_LOGIN_ATTEMPTS,
        session_timeout_minutes=settings.SESSION_TIMEOUT_MINUTES,
        password_min_length=settings.PASSWORD_MIN_LENGTH,
        password_require_uppercase=settings.PASSWORD_REQUIRE_UPPERCASE,
        password_require_lowercase=settings.PASSWORD_REQUIRE_LOWERCASE,
        password_require_numbers=settings.PASSWORD_REQUIRE_NUMBERS,
        password_require_symbols=settings.PASSWORD_REQUIRE_SYMBOLS,
        account_lockout_duration_minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES,
        rate_limit_requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS
    )


@router.put("/config", response_model=SystemConfigResponse)
async def update_system_config(
    config_update: SystemConfigUpdate,
    current_user: User = Depends(require_admin)
) -> Any:
    """Update system configuration."""
    # In a real implementation, this would update the configuration
    # For now, we'll just return the current config
    # This would typically involve updating environment variables or a config file
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Configuration updates not yet implemented"
    )