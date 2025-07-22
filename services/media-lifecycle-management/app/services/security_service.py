#!/usr/bin/env python3
"""
Security Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive security features including authentication,
authorization, encryption, security monitoring, and threat detection.
"""

import logging
import hashlib
import secrets
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, asdict
import re
import ipaddress
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload

from ..core.database import User, APIKey, SecurityEvent, MediaFile
from ..core.redis_client import CacheManager
from ..middleware.error_handling import (
    AuthenticationError, AuthorizationError, SecurityError
)
from .audit_service import AuditService, AuditEventType, AuditSeverity


logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    API_CLIENT = "api_client"
    SERVICE_ACCOUNT = "service_account"


class Permission(str, Enum):
    """System permissions."""
    # Media permissions
    MEDIA_READ = "media:read"
    MEDIA_WRITE = "media:write"
    MEDIA_DELETE = "media:delete"
    MEDIA_SHARE = "media:share"
    MEDIA_PROCESS = "media:process"
    
    # User management permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # API permissions
    API_KEY_CREATE = "api_key:create"
    API_KEY_REVOKE = "api_key:revoke"
    
    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"


class SecurityEventType(str, Enum):
    """Security event types."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"
    SECURITY_SCAN = "security_scan"
    MALWARE_DETECTED = "malware_detected"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityContext:
    """Security context for requests."""
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    api_key_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    permissions: List[Permission] = None
    roles: List[UserRole] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.roles is None:
            self.roles = []


@dataclass
class AuthenticationResult:
    """Result of authentication attempt."""
    success: bool
    user_id: Optional[UUID] = None
    session_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    requires_mfa: bool = False
    account_locked: bool = False


@dataclass
class SecurityThreat:
    """Security threat detection result."""
    threat_id: UUID
    threat_type: str
    threat_level: ThreatLevel
    description: str
    source_ip: Optional[str] = None
    user_id: Optional[UUID] = None
    detected_at: Optional[datetime] = None
    indicators: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()


class SecurityService:
    """Service for security operations and threat detection."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        audit_service: Optional[AuditService] = None
    ):
        self.cache = cache_manager
        self.audit_service = audit_service
        
        # Security configuration
        self.jwt_secret = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        self.password_min_length = 8
        self.max_login_attempts = 5
        self.account_lockout_duration = timedelta(minutes=30)
        
        # Rate limiting
        self.rate_limit_window = 300  # 5 minutes
        self.max_requests_per_window = 100
        
        # Encryption
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Security monitoring
        self.threat_detection_enabled = True
        self.suspicious_patterns = {
            "multiple_failed_logins": 5,
            "rapid_requests": 50,
            "unusual_access_patterns": 10,
            "large_file_downloads": 5
        }
        
        # Role-based permissions
        self.role_permissions = {
            UserRole.ADMIN: [
                Permission.MEDIA_READ, Permission.MEDIA_WRITE, Permission.MEDIA_DELETE,
                Permission.MEDIA_SHARE, Permission.MEDIA_PROCESS,
                Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE,
                Permission.SYSTEM_ADMIN, Permission.SYSTEM_MONITOR, Permission.SYSTEM_CONFIG,
                Permission.API_KEY_CREATE, Permission.API_KEY_REVOKE,
                Permission.AUDIT_READ, Permission.AUDIT_EXPORT
            ],
            UserRole.USER: [
                Permission.MEDIA_READ, Permission.MEDIA_WRITE, Permission.MEDIA_SHARE,
                Permission.MEDIA_PROCESS
            ],
            UserRole.VIEWER: [
                Permission.MEDIA_READ
            ],
            UserRole.API_CLIENT: [
                Permission.MEDIA_READ, Permission.MEDIA_WRITE, Permission.MEDIA_PROCESS
            ],
            UserRole.SERVICE_ACCOUNT: [
                Permission.MEDIA_READ, Permission.MEDIA_WRITE, Permission.MEDIA_PROCESS,
                Permission.SYSTEM_MONITOR
            ]
        }
    
    # Authentication methods
    
    async def authenticate_user(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthenticationResult:
        """
        Authenticate a user with username and password.
        
        Args:
            db: Database session
            username: Username or email
            password: Plain text password
            ip_address: Client IP address
            user_agent: Client user agent
        
        Returns:
            Authentication result
        """
        try:
            # Check rate limiting
            if await self._is_rate_limited(ip_address, "login"):
                await self._log_security_event(
                    db, SecurityEventType.BRUTE_FORCE_ATTEMPT,
                    ip_address=ip_address, user_agent=user_agent
                )
                return AuthenticationResult(
                    success=False,
                    error_message="Too many login attempts. Please try again later."
                )
            
            # Get user
            user_query = select(User).where(
                or_(User.username == username, User.email == username)
            )
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                await self._increment_rate_limit(ip_address, "login")
                await self._log_security_event(
                    db, SecurityEventType.LOGIN_FAILURE,
                    ip_address=ip_address, user_agent=user_agent,
                    details={"reason": "user_not_found", "username": username}
                )
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            # Check if account is locked
            if await self._is_account_locked(user.id):
                await self._log_security_event(
                    db, SecurityEventType.LOGIN_FAILURE,
                    user_id=user.id, ip_address=ip_address, user_agent=user_agent,
                    details={"reason": "account_locked"}
                )
                return AuthenticationResult(
                    success=False,
                    account_locked=True,
                    error_message="Account is locked due to suspicious activity"
                )
            
            # Verify password
            if not self._verify_password(password, user.password_hash):
                await self._handle_failed_login(db, user.id, ip_address, user_agent)
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            # Check if user is active
            if not user.is_active:
                await self._log_security_event(
                    db, SecurityEventType.LOGIN_FAILURE,
                    user_id=user.id, ip_address=ip_address, user_agent=user_agent,
                    details={"reason": "account_inactive"}
                )
                return AuthenticationResult(
                    success=False,
                    error_message="Account is inactive"
                )
            
            # Generate tokens
            session_token = await self._generate_session_token(user)
            refresh_token = await self._generate_refresh_token(user)
            
            # Store session
            session_id = str(uuid4())
            await self._store_session(
                session_id, user.id, session_token, ip_address, user_agent
            )
            
            # Clear failed login attempts
            await self._clear_failed_login_attempts(user.id)
            
            # Log successful login
            await self._log_security_event(
                db, SecurityEventType.LOGIN_SUCCESS,
                user_id=user.id, ip_address=ip_address, user_agent=user_agent
            )
            
            return AuthenticationResult(
                success=True,
                user_id=user.id,
                session_token=session_token,
                refresh_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            )
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication service temporarily unavailable"
            )
    
    async def authenticate_api_key(
        self,
        db: AsyncSession,
        api_key: str,
        ip_address: Optional[str] = None
    ) -> AuthenticationResult:
        """
        Authenticate using API key.
        
        Args:
            db: Database session
            api_key: API key
            ip_address: Client IP address
        
        Returns:
            Authentication result
        """
        try:
            # Hash the API key for lookup
            api_key_hash = self._hash_api_key(api_key)
            
            # Get API key record
            api_key_query = select(APIKey).where(
                and_(
                    APIKey.key_hash == api_key_hash,
                    APIKey.is_active == True,
                    or_(
                        APIKey.expires_at.is_(None),
                        APIKey.expires_at > datetime.utcnow()
                    )
                )
            ).options(selectinload(APIKey.user))
            
            api_key_result = await db.execute(api_key_query)
            api_key_record = api_key_result.scalar_one_or_none()
            
            if not api_key_record:
                await self._log_security_event(
                    db, SecurityEventType.LOGIN_FAILURE,
                    ip_address=ip_address,
                    details={"reason": "invalid_api_key"}
                )
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid API key"
                )
            
            # Update last used timestamp
            api_key_record.last_used_at = datetime.utcnow()
            api_key_record.usage_count += 1
            await db.commit()
            
            # Generate session token for API key
            session_token = await self._generate_api_session_token(api_key_record)
            
            return AuthenticationResult(
                success=True,
                user_id=api_key_record.user_id,
                session_token=session_token,
                expires_at=datetime.utcnow() + timedelta(hours=1)  # API sessions are shorter
            )
            
        except Exception as e:
            logger.error(f"API key authentication error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication service temporarily unavailable"
            )
    
    async def validate_session_token(
        self,
        db: AsyncSession,
        token: str
    ) -> Optional[SecurityContext]:
        """
        Validate a session token and return security context.
        
        Args:
            db: Database session
            token: Session token
        
        Returns:
            Security context if valid, None otherwise
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            
            user_id = UUID(payload.get("user_id"))
            session_id = payload.get("session_id")
            token_type = payload.get("type", "session")
            
            # Check if session is still valid
            session_key = f"session:{session_id}"
            session_data = await self.cache.get(session_key)
            
            if not session_data:
                return None
            
            # Get user and permissions
            user_query = select(User).where(User.id == user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user or not user.is_active:
                return None
            
            # Get user permissions
            permissions = self._get_user_permissions(user.roles)
            
            return SecurityContext(
                user_id=user_id,
                session_id=session_id,
                permissions=permissions,
                roles=user.roles
            )
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.debug("Invalid token")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None
    
    async def logout_user(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: UUID,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Logout a user and invalidate their session.
        
        Args:
            db: Database session
            session_id: Session ID to invalidate
            user_id: User ID
            ip_address: Client IP address
        
        Returns:
            True if logout was successful
        """
        try:
            # Remove session from cache
            session_key = f"session:{session_id}"
            await self.cache.delete(session_key)
            
            # Log logout event
            await self._log_security_event(
                db, SecurityEventType.LOGOUT,
                user_id=user_id, ip_address=ip_address
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    # Authorization methods
    
    def check_permission(
        self,
        security_context: SecurityContext,
        required_permission: Permission
    ) -> bool:
        """
        Check if user has required permission.
        
        Args:
            security_context: User's security context
            required_permission: Required permission
        
        Returns:
            True if user has permission
        """
        return required_permission in security_context.permissions
    
    def check_resource_access(
        self,
        security_context: SecurityContext,
        resource_type: str,
        resource_id: UUID,
        action: str
    ) -> bool:
        """
        Check if user can access a specific resource.
        
        Args:
            security_context: User's security context
            resource_type: Type of resource (e.g., 'media_file')
            resource_id: Resource ID
            action: Action to perform (e.g., 'read', 'write', 'delete')
        
        Returns:
            True if access is allowed
        """
        # Admin users have access to everything
        if UserRole.ADMIN in security_context.roles:
            return True
        
        # Check basic permissions first
        permission_map = {
            "media_file": {
                "read": Permission.MEDIA_READ,
                "write": Permission.MEDIA_WRITE,
                "delete": Permission.MEDIA_DELETE,
                "share": Permission.MEDIA_SHARE,
                "process": Permission.MEDIA_PROCESS
            }
        }
        
        if resource_type in permission_map and action in permission_map[resource_type]:
            required_permission = permission_map[resource_type][action]
            if not self.check_permission(security_context, required_permission):
                return False
        
        # Additional resource-specific checks can be added here
        # For example, checking if user owns the resource
        
        return True
    
    async def require_permission(
        self,
        db: AsyncSession,
        security_context: SecurityContext,
        required_permission: Permission,
        ip_address: Optional[str] = None
    ):
        """
        Require a specific permission, raise exception if not authorized.
        
        Args:
            db: Database session
            security_context: User's security context
            required_permission: Required permission
            ip_address: Client IP address
        
        Raises:
            AuthorizationError: If user doesn't have permission
        """
        if not self.check_permission(security_context, required_permission):
            await self._log_security_event(
                db, SecurityEventType.PERMISSION_DENIED,
                user_id=security_context.user_id,
                ip_address=ip_address,
                details={"required_permission": required_permission.value}
            )
            raise AuthorizationError(f"Permission denied: {required_permission.value}")
    
    # Password management
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password
            password_hash: Stored password hash
        
        Returns:
            True if password matches
        """
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if len(password) < self.password_min_length:
            issues.append(f"Password must be at least {self.password_min_length} characters long")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        }
        
        if password.lower() in common_passwords:
            issues.append("Password is too common")
        
        return len(issues) == 0, issues
    
    async def change_password(
        self,
        db: AsyncSession,
        user_id: UUID,
        old_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Change user password.
        
        Args:
            db: Database session
            user_id: User ID
            old_password: Current password
            new_password: New password
            ip_address: Client IP address
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get user
            user_query = select(User).where(User.id == user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                return False, "User not found"
            
            # Verify old password
            if not self._verify_password(old_password, user.password_hash):
                await self._log_security_event(
                    db, SecurityEventType.LOGIN_FAILURE,
                    user_id=user_id, ip_address=ip_address,
                    details={"reason": "invalid_old_password"}
                )
                return False, "Current password is incorrect"
            
            # Validate new password
            is_valid, issues = self.validate_password_strength(new_password)
            if not is_valid:
                return False, "; ".join(issues)
            
            # Update password
            user.password_hash = self.hash_password(new_password)
            user.password_changed_at = datetime.utcnow()
            await db.commit()
            
            # Log password change
            await self._log_security_event(
                db, SecurityEventType.PASSWORD_CHANGE,
                user_id=user_id, ip_address=ip_address
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Password change error: {e}")
            await db.rollback()
            return False, "Password change failed"
    
    # API Key management
    
    async def create_api_key(
        self,
        db: AsyncSession,
        user_id: UUID,
        name: str,
        permissions: List[Permission],
        expires_at: Optional[datetime] = None
    ) -> Tuple[str, UUID]:
        """
        Create a new API key.
        
        Args:
            db: Database session
            user_id: User ID
            name: API key name
            permissions: List of permissions
            expires_at: Expiration date (optional)
        
        Returns:
            Tuple of (api_key, api_key_id)
        """
        try:
            # Generate API key
            api_key = self._generate_api_key()
            api_key_hash = self._hash_api_key(api_key)
            
            # Create API key record
            api_key_record = APIKey(
                id=uuid4(),
                user_id=user_id,
                name=name,
                key_hash=api_key_hash,
                permissions=[p.value for p in permissions],
                expires_at=expires_at,
                created_at=datetime.utcnow(),
                is_active=True
            )
            
            db.add(api_key_record)
            await db.commit()
            
            # Log API key creation
            await self._log_security_event(
                db, SecurityEventType.API_KEY_CREATED,
                user_id=user_id,
                details={"api_key_name": name, "api_key_id": str(api_key_record.id)}
            )
            
            return api_key, api_key_record.id
            
        except Exception as e:
            logger.error(f"API key creation error: {e}")
            await db.rollback()
            raise SecurityError(f"Failed to create API key: {str(e)}")
    
    async def revoke_api_key(
        self,
        db: AsyncSession,
        api_key_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Revoke an API key.
        
        Args:
            db: Database session
            api_key_id: API key ID
            user_id: User ID (for authorization)
        
        Returns:
            True if revoked successfully
        """
        try:
            # Get API key
            api_key_query = select(APIKey).where(
                and_(
                    APIKey.id == api_key_id,
                    APIKey.user_id == user_id,
                    APIKey.is_active == True
                )
            )
            
            api_key_result = await db.execute(api_key_query)
            api_key_record = api_key_result.scalar_one_or_none()
            
            if not api_key_record:
                return False
            
            # Revoke API key
            api_key_record.is_active = False
            api_key_record.revoked_at = datetime.utcnow()
            await db.commit()
            
            # Log API key revocation
            await self._log_security_event(
                db, SecurityEventType.API_KEY_REVOKED,
                user_id=user_id,
                details={"api_key_name": api_key_record.name, "api_key_id": str(api_key_id)}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"API key revocation error: {e}")
            await db.rollback()
            return False
    
    # Encryption methods
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
        
        Returns:
            Encrypted data (base64 encoded)
        """
        encrypted_data = self.cipher_suite.encrypt(data.encode('utf-8'))
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted data (base64 encoded)
        
        Returns:
            Decrypted data
        """
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted_data = self.cipher_suite.decrypt(encrypted_bytes)
        return decrypted_data.decode('utf-8')
    
    # Threat detection
    
    async def detect_threats(
        self,
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        activity_data: Optional[Dict[str, Any]] = None
    ) -> List[SecurityThreat]:
        """
        Detect security threats based on activity patterns.
        
        Args:
            db: Database session
            user_id: User ID
            ip_address: IP address
            activity_data: Additional activity data
        
        Returns:
            List of detected threats
        """
        threats = []
        
        if not self.threat_detection_enabled:
            return threats
        
        try:
            # Check for multiple failed logins
            if user_id:
                failed_logins = await self._get_failed_login_count(user_id)
                if failed_logins >= self.suspicious_patterns["multiple_failed_logins"]:
                    threats.append(SecurityThreat(
                        threat_id=uuid4(),
                        threat_type="multiple_failed_logins",
                        threat_level=ThreatLevel.HIGH,
                        description=f"Multiple failed login attempts detected for user {user_id}",
                        user_id=user_id,
                        indicators={"failed_login_count": failed_logins}
                    ))
            
            # Check for rapid requests from IP
            if ip_address:
                request_count = await self._get_request_count(ip_address)
                if request_count >= self.suspicious_patterns["rapid_requests"]:
                    threats.append(SecurityThreat(
                        threat_id=uuid4(),
                        threat_type="rapid_requests",
                        threat_level=ThreatLevel.MEDIUM,
                        description=f"Rapid requests detected from IP {ip_address}",
                        source_ip=ip_address,
                        indicators={"request_count": request_count}
                    ))
            
            # Check for unusual access patterns
            if user_id and activity_data:
                unusual_activity = await self._detect_unusual_activity(user_id, activity_data)
                if unusual_activity:
                    threats.append(SecurityThreat(
                        threat_id=uuid4(),
                        threat_type="unusual_access_pattern",
                        threat_level=ThreatLevel.MEDIUM,
                        description="Unusual access pattern detected",
                        user_id=user_id,
                        indicators=unusual_activity
                    ))
            
            # Log detected threats
            for threat in threats:
                await self._log_security_event(
                    db, SecurityEventType.SUSPICIOUS_ACTIVITY,
                    user_id=threat.user_id,
                    ip_address=threat.source_ip,
                    details={
                        "threat_id": str(threat.threat_id),
                        "threat_type": threat.threat_type,
                        "threat_level": threat.threat_level.value,
                        "indicators": threat.indicators
                    }
                )
            
            return threats
            
        except Exception as e:
            logger.error(f"Threat detection error: {e}")
            return []
    
    async def scan_file_for_malware(
        self,
        file_path: str,
        file_content: Optional[bytes] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Scan a file for malware (placeholder implementation).
        
        Args:
            file_path: Path to file
            file_content: File content bytes
        
        Returns:
            Tuple of (is_safe, threat_description)
        """
        try:
            # This is a placeholder implementation
            # In a real system, you would integrate with antivirus APIs
            # like ClamAV, VirusTotal, etc.
            
            # Basic checks
            if file_path:
                # Check file extension
                dangerous_extensions = {
                    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
                    '.vbs', '.js', '.jar', '.ps1', '.sh'
                }
                
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext in dangerous_extensions:
                    return False, f"Potentially dangerous file type: {file_ext}"
            
            if file_content:
                # Check for suspicious patterns
                suspicious_patterns = [
                    b'eval(', b'exec(', b'system(', b'shell_exec(',
                    b'<script', b'javascript:', b'vbscript:'
                ]
                
                for pattern in suspicious_patterns:
                    if pattern in file_content:
                        return False, f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Malware scan error: {e}")
            return False, f"Scan failed: {str(e)}"
    
    # Helper methods
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = "encryption.key"
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _generate_api_key(self) -> str:
        """Generate a new API key."""
        return f"aima_{secrets.token_urlsafe(32)}"
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    async def _generate_session_token(self, user: User) -> str:
        """Generate a session token for a user."""
        session_id = str(uuid4())
        payload = {
            "user_id": str(user.id),
            "session_id": session_id,
            "type": "session",
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    async def _generate_refresh_token(self, user: User) -> str:
        """Generate a refresh token for a user."""
        payload = {
            "user_id": str(user.id),
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    async def _generate_api_session_token(self, api_key: APIKey) -> str:
        """Generate a session token for API key authentication."""
        payload = {
            "user_id": str(api_key.user_id),
            "api_key_id": str(api_key.id),
            "type": "api_session",
            "permissions": api_key.permissions,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    async def _store_session(
        self,
        session_id: str,
        user_id: UUID,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Store session data in cache."""
        session_data = {
            "user_id": str(user_id),
            "token": token,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat()
        }
        
        session_key = f"session:{session_id}"
        await self.cache.set(
            session_key, session_data,
            ttl=self.access_token_expire_minutes * 60
        )
    
    def _get_user_permissions(self, roles: List[UserRole]) -> List[Permission]:
        """Get permissions for user roles."""
        permissions = set()
        
        for role in roles:
            if role in self.role_permissions:
                permissions.update(self.role_permissions[role])
        
        return list(permissions)
    
    async def _is_rate_limited(self, ip_address: Optional[str], action: str) -> bool:
        """Check if IP is rate limited for an action."""
        if not ip_address:
            return False
        
        rate_limit_key = f"rate_limit:{action}:{ip_address}"
        current_count = await self.cache.get(rate_limit_key) or 0
        
        return current_count >= self.max_requests_per_window
    
    async def _increment_rate_limit(self, ip_address: Optional[str], action: str):
        """Increment rate limit counter."""
        if not ip_address:
            return
        
        rate_limit_key = f"rate_limit:{action}:{ip_address}"
        current_count = await self.cache.get(rate_limit_key) or 0
        
        await self.cache.set(
            rate_limit_key, current_count + 1,
            ttl=self.rate_limit_window
        )
    
    async def _is_account_locked(self, user_id: UUID) -> bool:
        """Check if user account is locked."""
        lock_key = f"account_lock:{user_id}"
        lock_data = await self.cache.get(lock_key)
        
        if not lock_data:
            return False
        
        lock_time = datetime.fromisoformat(lock_data["locked_at"])
        return datetime.utcnow() - lock_time < self.account_lockout_duration
    
    async def _handle_failed_login(
        self,
        db: AsyncSession,
        user_id: UUID,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ):
        """Handle failed login attempt."""
        # Increment failed login count
        failed_count = await self._increment_failed_login_count(user_id)
        
        # Log failed login
        await self._log_security_event(
            db, SecurityEventType.LOGIN_FAILURE,
            user_id=user_id, ip_address=ip_address, user_agent=user_agent,
            details={"reason": "invalid_password", "failed_count": failed_count}
        )
        
        # Lock account if too many failures
        if failed_count >= self.max_login_attempts:
            await self._lock_account(db, user_id, ip_address)
    
    async def _increment_failed_login_count(self, user_id: UUID) -> int:
        """Increment failed login count for user."""
        failed_key = f"failed_logins:{user_id}"
        current_count = await self.cache.get(failed_key) or 0
        new_count = current_count + 1
        
        await self.cache.set(failed_key, new_count, ttl=3600)  # 1 hour
        return new_count
    
    async def _clear_failed_login_attempts(self, user_id: UUID):
        """Clear failed login attempts for user."""
        failed_key = f"failed_logins:{user_id}"
        await self.cache.delete(failed_key)
    
    async def _lock_account(
        self,
        db: AsyncSession,
        user_id: UUID,
        ip_address: Optional[str]
    ):
        """Lock user account."""
        lock_key = f"account_lock:{user_id}"
        lock_data = {
            "locked_at": datetime.utcnow().isoformat(),
            "reason": "too_many_failed_logins"
        }
        
        await self.cache.set(
            lock_key, lock_data,
            ttl=int(self.account_lockout_duration.total_seconds())
        )
        
        # Log account lock
        await self._log_security_event(
            db, SecurityEventType.ACCOUNT_LOCKED,
            user_id=user_id, ip_address=ip_address,
            details={"reason": "too_many_failed_logins"}
        )
    
    async def _get_failed_login_count(self, user_id: UUID) -> int:
        """Get failed login count for user."""
        failed_key = f"failed_logins:{user_id}"
        return await self.cache.get(failed_key) or 0
    
    async def _get_request_count(self, ip_address: str) -> int:
        """Get request count for IP address."""
        request_key = f"requests:{ip_address}"
        return await self.cache.get(request_key) or 0
    
    async def _detect_unusual_activity(
        self,
        user_id: UUID,
        activity_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Detect unusual activity patterns."""
        # This is a placeholder for more sophisticated anomaly detection
        # In a real system, you might use machine learning models
        
        unusual_indicators = {}
        
        # Check for unusual time patterns
        current_hour = datetime.utcnow().hour
        if current_hour < 6 or current_hour > 22:  # Outside normal hours
            unusual_indicators["unusual_time"] = current_hour
        
        # Check for unusual file access patterns
        if "files_accessed" in activity_data:
            files_count = activity_data["files_accessed"]
            if files_count > 50:  # Accessing many files quickly
                unusual_indicators["high_file_access"] = files_count
        
        return unusual_indicators if unusual_indicators else None
    
    async def _log_security_event(
        self,
        db: AsyncSession,
        event_type: SecurityEventType,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log a security event."""
        try:
            if self.audit_service:
                from .audit_service import AuditContext, AuditEvent
                
                context = AuditContext(
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Map security event to audit event
                audit_event_type = AuditEventType.SUSPICIOUS_ACTIVITY
                if event_type in [SecurityEventType.LOGIN_SUCCESS, SecurityEventType.LOGIN_FAILURE]:
                    audit_event_type = AuditEventType.USER_LOGIN if event_type == SecurityEventType.LOGIN_SUCCESS else AuditEventType.USER_LOGIN_FAILED
                elif event_type == SecurityEventType.LOGOUT:
                    audit_event_type = AuditEventType.USER_LOGOUT
                
                severity = AuditSeverity.HIGH if "failure" in event_type.value or "denied" in event_type.value else AuditSeverity.MEDIUM
                
                audit_event = AuditEvent(
                    event_type=audit_event_type,
                    severity=severity,
                    status="failure" if "failure" in event_type.value else "success",
                    message=f"Security event: {event_type.value}",
                    context=context,
                    details=details
                )
                
                await self.audit_service.log_event(db, audit_event)
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")