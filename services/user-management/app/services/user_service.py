#!/usr/bin/env python3
"""
User service for the AIMA User Management Service.

This module contains the business logic for user management operations.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import structlog

from app.core.database import User, UserSession, AuditLog
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    jwt_manager,
    permission_checker,
    generate_session_token,
    generate_password_reset_token
)
from app.core.redis import session_manager, cache_manager
from app.core.messaging import event_publisher, EventTypes
from app.core.exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    AccountDisabledError,
    AccountLockedError,
    PasswordExpiredError,
    WeakPasswordError,
    InsufficientPermissionsError,
    SessionNotFoundError,
    DatabaseError,
    BusinessLogicError
)
from app.models.schemas import (
    UserCreate,
    UserUpdate,
    UserAdminUpdate,
    PasswordChangeRequest,
    UserRole,
    UserStatus,
    SessionStatus,
    AuditAction
)

logger = structlog.get_logger(__name__)


class UserService:
    """Service class for user management operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_user(
        self,
        user_data: UserCreate,
        created_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> User:
        """Create a new user."""
        try:
            # Check if user already exists
            existing_user = self.db.query(User).filter(
                or_(
                    User.username == user_data.username.lower(),
                    User.email == user_data.email.lower()
                )
            ).first()
            
            if existing_user:
                if existing_user.username == user_data.username.lower():
                    raise UserAlreadyExistsError("username", user_data.username)
                else:
                    raise UserAlreadyExistsError("email", user_data.email)
            
            # Validate password strength
            password_validation = validate_password_strength(user_data.password)
            if not password_validation["is_valid"]:
                raise WeakPasswordError(password_validation["issues"])
            
            # Hash password
            hashed_password = hash_password(user_data.password)
            
            # Create user
            user = User(
                id=uuid.uuid4(),
                username=user_data.username.lower(),
                email=user_data.email.lower(),
                full_name=user_data.full_name,
                password_hash=hashed_password,
                role=user_data.role,
                status=UserStatus.ACTIVE if user_data.is_active else UserStatus.INACTIVE,
                is_active=user_data.is_active,
                email_verified=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                password_changed_at=datetime.utcnow()
            )
            
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            
            # Log audit event
            await self._create_audit_log(
                user_id=created_by,
                action=AuditAction.CREATE,
                resource_type="user",
                resource_id=str(user.id),
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
            )
            
            # Publish event
            await event_publisher.publish_user_event(
                event_type=EventTypes.USER_CREATED,
                user_id=str(user.id),
                data={
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "created_by": created_by
                }
            )
            
            logger.info(
                "User created successfully",
                user_id=str(user.id),
                username=user.username,
                created_by=created_by
            )
            
            return user
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (UserAlreadyExistsError, WeakPasswordError)):
                raise
            logger.error("Failed to create user", error=str(e))
            raise DatabaseError("create_user", str(e))
    
    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """Authenticate user and return user, access token, and refresh token."""
        try:
            # Find user
            user = self.db.query(User).filter(
                or_(
                    User.username == username.lower(),
                    User.email == username.lower()
                )
            ).first()
            
            if not user:
                # Log failed attempt
                await self._create_audit_log(
                    action=AuditAction.LOGIN,
                    resource_type="authentication",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"username": username, "success": False, "reason": "user_not_found"}
                )
                raise InvalidCredentialsError()
            
            # Check if account is active
            if not user.is_active or user.status != UserStatus.ACTIVE:
                await self._create_audit_log(
                    user_id=str(user.id),
                    action=AuditAction.LOGIN,
                    resource_type="authentication",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"username": username, "success": False, "reason": "account_disabled"}
                )
                raise AccountDisabledError(str(user.id))
            
            # Check if account is locked
            if user.account_locked_until and user.account_locked_until > datetime.utcnow():
                await self._create_audit_log(
                    user_id=str(user.id),
                    action=AuditAction.LOGIN,
                    resource_type="authentication",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"username": username, "success": False, "reason": "account_locked"}
                )
                raise AccountLockedError(str(user.id), user.account_locked_until.isoformat())
            
            # Verify password
            if not verify_password(password, user.password_hash):
                # Increment failed login attempts
                user.failed_login_attempts += 1
                
                # Lock account if too many failed attempts
                if user.failed_login_attempts >= 5:
                    user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
                    logger.warning(
                        "Account locked due to failed login attempts",
                        user_id=str(user.id),
                        attempts=user.failed_login_attempts
                    )
                
                self.db.commit()
                
                await self._create_audit_log(
                    user_id=str(user.id),
                    action=AuditAction.LOGIN,
                    resource_type="authentication",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"username": username, "success": False, "reason": "invalid_password"}
                )
                
                raise InvalidCredentialsError()
            
            # Check password expiration (if enabled)
            if (user.password_changed_at and 
                user.password_changed_at < datetime.utcnow() - timedelta(days=90)):
                await self._create_audit_log(
                    user_id=str(user.id),
                    action=AuditAction.LOGIN,
                    resource_type="authentication",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"username": username, "success": False, "reason": "password_expired"}
                )
                raise PasswordExpiredError(str(user.id))
            
            # Reset failed login attempts on successful authentication
            user.failed_login_attempts = 0
            user.login_count += 1
            user.last_login = datetime.utcnow()
            user.account_locked_until = None
            
            # Generate tokens
            access_token = jwt_manager.create_access_token(
                subject=str(user.id),
                additional_claims={
                    "username": user.username,
                    "role": user.role
                }
            )
            
            refresh_token = jwt_manager.create_refresh_token(subject=str(user.id))
            
            # Create session
            session_token = generate_session_token()
            await session_manager.create_session(
                user_id=str(user.id),
                session_token=session_token,
                expires_in_hours=8,
                metadata={
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "access_token": access_token[:10] + "..."
                }
            )
            
            # Save session to database
            db_session = UserSession(
                id=uuid.uuid4(),
                user_id=user.id,
                session_token=session_token,
                status=SessionStatus.ACTIVE,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=8)
            )
            
            self.db.add(db_session)
            self.db.commit()
            self.db.refresh(user)
            
            # Log successful login
            await self._create_audit_log(
                user_id=str(user.id),
                action=AuditAction.LOGIN,
                resource_type="authentication",
                ip_address=ip_address,
                user_agent=user_agent,
                details={"username": username, "success": True}
            )
            
            # Publish login event
            await event_publisher.publish_user_event(
                event_type=EventTypes.USER_LOGIN,
                user_id=str(user.id),
                data={
                    "username": user.username,
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }
            )
            
            logger.info(
                "User authenticated successfully",
                user_id=str(user.id),
                username=user.username
            )
            
            return user, access_token, refresh_token
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (InvalidCredentialsError, AccountDisabledError, 
                            AccountLockedError, PasswordExpiredError)):
                raise
            logger.error("Authentication failed", error=str(e))
            raise DatabaseError("authenticate_user", str(e))
    
    async def get_user_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        try:
            user = self.db.query(User).filter(User.id == uuid.UUID(user_id)).first()
            if not user:
                raise UserNotFoundError(user_id)
            return user
        except ValueError:
            raise UserNotFoundError(user_id)
        except Exception as e:
            logger.error("Failed to get user by ID", user_id=user_id, error=str(e))
            raise DatabaseError("get_user_by_id", str(e))
    
    async def get_user_by_username(self, username: str) -> User:
        """Get user by username."""
        try:
            user = self.db.query(User).filter(User.username == username.lower()).first()
            if not user:
                raise UserNotFoundError(username)
            return user
        except Exception as e:
            logger.error("Failed to get user by username", username=username, error=str(e))
            raise DatabaseError("get_user_by_username", str(e))
    
    async def get_user_by_email(self, email: str) -> User:
        """Get user by email."""
        try:
            user = self.db.query(User).filter(User.email == email.lower()).first()
            if not user:
                raise UserNotFoundError(email)
            return user
        except Exception as e:
            logger.error("Failed to get user by email", email=email, error=str(e))
            raise DatabaseError("get_user_by_email", str(e))
    
    async def update_user(
        self,
        user_id: str,
        user_data: UserUpdate,
        updated_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> User:
        """Update user information."""
        try:
            user = await self.get_user_by_id(user_id)
            
            # Track changes for audit log
            changes = {}
            
            # Update fields
            if user_data.email is not None and user_data.email != user.email:
                # Check if email is already taken
                existing_user = self.db.query(User).filter(
                    and_(
                        User.email == user_data.email.lower(),
                        User.id != user.id
                    )
                ).first()
                
                if existing_user:
                    raise UserAlreadyExistsError("email", user_data.email)
                
                changes["email"] = {"old": user.email, "new": user_data.email.lower()}
                user.email = user_data.email.lower()
                user.email_verified = False  # Reset email verification
            
            if user_data.full_name is not None:
                changes["full_name"] = {"old": user.full_name, "new": user_data.full_name}
                user.full_name = user_data.full_name
            
            if user_data.role is not None and user_data.role != user.role:
                changes["role"] = {"old": user.role, "new": user_data.role}
                user.role = user_data.role
            
            if user_data.is_active is not None and user_data.is_active != user.is_active:
                changes["is_active"] = {"old": user.is_active, "new": user_data.is_active}
                user.is_active = user_data.is_active
                user.status = UserStatus.ACTIVE if user_data.is_active else UserStatus.INACTIVE
            
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(user)
            
            # Log audit event if there were changes
            if changes:
                await self._create_audit_log(
                    user_id=updated_by,
                    action=AuditAction.UPDATE,
                    resource_type="user",
                    resource_id=str(user.id),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={"changes": changes}
                )
                
                # Publish update event
                await event_publisher.publish_user_event(
                    event_type=EventTypes.USER_UPDATED,
                    user_id=str(user.id),
                    data={
                        "username": user.username,
                        "changes": changes,
                        "updated_by": updated_by
                    }
                )
                
                # Publish role change event if role was changed
                if "role" in changes:
                    await event_publisher.publish_user_event(
                        event_type=EventTypes.USER_ROLE_CHANGED,
                        user_id=str(user.id),
                        data={
                            "username": user.username,
                            "old_role": changes["role"]["old"],
                            "new_role": changes["role"]["new"],
                            "updated_by": updated_by
                        }
                    )
            
            logger.info(
                "User updated successfully",
                user_id=str(user.id),
                changes=list(changes.keys()),
                updated_by=updated_by
            )
            
            return user
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (UserNotFoundError, UserAlreadyExistsError)):
                raise
            logger.error("Failed to update user", user_id=user_id, error=str(e))
            raise DatabaseError("update_user", str(e))
    
    async def change_password(
        self,
        user_id: str,
        password_data: PasswordChangeRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Change user password."""
        try:
            user = await self.get_user_by_id(user_id)
            
            # Verify current password
            if not verify_password(password_data.current_password, user.password_hash):
                raise InvalidCredentialsError()
            
            # Validate new password strength
            password_validation = validate_password_strength(password_data.new_password)
            if not password_validation["is_valid"]:
                raise WeakPasswordError(password_validation["issues"])
            
            # Check if new password is different from current
            if verify_password(password_data.new_password, user.password_hash):
                raise BusinessLogicError(
                    "new_password_same_as_current",
                    "New password must be different from current password"
                )
            
            # Hash new password
            new_password_hash = hash_password(password_data.new_password)
            
            # Update password
            user.password_hash = new_password_hash
            user.password_changed_at = datetime.utcnow()
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Invalidate all user sessions except current one
            await session_manager.delete_user_sessions(str(user.id))
            
            # Log audit event
            await self._create_audit_log(
                user_id=str(user.id),
                action=AuditAction.PASSWORD_CHANGE,
                resource_type="user",
                resource_id=str(user.id),
                ip_address=ip_address,
                user_agent=user_agent,
                details={"username": user.username}
            )
            
            # Publish password change event
            await event_publisher.publish_user_event(
                event_type=EventTypes.USER_PASSWORD_CHANGED,
                user_id=str(user.id),
                data={
                    "username": user.username,
                    "ip_address": ip_address
                }
            )
            
            logger.info(
                "Password changed successfully",
                user_id=str(user.id),
                username=user.username
            )
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (UserNotFoundError, InvalidCredentialsError, 
                            WeakPasswordError, BusinessLogicError)):
                raise
            logger.error("Failed to change password", user_id=user_id, error=str(e))
            raise DatabaseError("change_password", str(e))
    
    async def delete_user(
        self,
        user_id: str,
        deleted_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Delete user (soft delete)."""
        try:
            user = await self.get_user_by_id(user_id)
            
            # Prevent self-deletion
            if deleted_by == user_id:
                raise BusinessLogicError(
                    "cannot_delete_self",
                    "Users cannot delete their own account"
                )
            
            # Soft delete - mark as inactive and change status
            user.is_active = False
            user.status = UserStatus.SUSPENDED
            user.updated_at = datetime.utcnow()
            
            # Invalidate all user sessions
            await session_manager.delete_user_sessions(str(user.id))
            
            self.db.commit()
            
            # Log audit event
            await self._create_audit_log(
                user_id=deleted_by,
                action=AuditAction.DELETE,
                resource_type="user",
                resource_id=str(user.id),
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "username": user.username,
                    "email": user.email
                }
            )
            
            # Publish delete event
            await event_publisher.publish_user_event(
                event_type=EventTypes.USER_DELETED,
                user_id=str(user.id),
                data={
                    "username": user.username,
                    "email": user.email,
                    "deleted_by": deleted_by
                }
            )
            
            logger.info(
                "User deleted successfully",
                user_id=str(user.id),
                username=user.username,
                deleted_by=deleted_by
            )
            
        except Exception as e:
            self.db.rollback()
            if isinstance(e, (UserNotFoundError, BusinessLogicError)):
                raise
            logger.error("Failed to delete user", user_id=user_id, error=str(e))
            raise DatabaseError("delete_user", str(e))
    
    async def _create_audit_log(
        self,
        action: AuditAction,
        resource_type: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> None:
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
            # Note: Don't commit here, let the calling method handle the transaction
            
        except Exception as e:
            logger.error("Failed to create audit log", error=str(e))
            # Don't raise exception for audit log failures