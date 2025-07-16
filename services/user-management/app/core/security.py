#!/usr/bin/env python3
"""
Security utilities for the AIMA User Management Service.

This module provides authentication, authorization, and security utilities.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class TokenError(SecurityError):
    """Exception for token-related errors."""
    pass


class AuthenticationError(SecurityError):
    """Exception for authentication errors."""
    pass


class AuthorizationError(SecurityError):
    """Exception for authorization errors."""
    pass


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error("Failed to hash password", error=str(e))
        raise SecurityError("Password hashing failed")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Failed to verify password", error=str(e))
        return False


def generate_password_reset_token() -> str:
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(32)


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(64)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(48)


class JWTManager:
    """Manages JWT token creation and validation."""
    
    def __init__(self):
        self.settings = get_settings()
        self.algorithm = self.settings.JWT_ALGORITHM
        self.secret_key = self.settings.SECRET_KEY
        self.access_token_expire_minutes = self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = self.settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    def create_access_token(
        self,
        subject: Union[str, Any],
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "access"
        }
        
        if additional_claims:
            to_encode.update(additional_claims)
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            logger.debug(
                "Access token created",
                subject=str(subject),
                expires_at=expire.isoformat()
            )
            
            return encoded_jwt
            
        except Exception as e:
            logger.error("Failed to create access token", error=str(e))
            raise TokenError("Token creation failed")
    
    def create_refresh_token(
        self,
        subject: Union[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "refresh"
        }
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            logger.debug(
                "Refresh token created",
                subject=str(subject),
                expires_at=expire.isoformat()
            )
            
            return encoded_jwt
            
        except Exception as e:
            logger.error("Failed to create refresh token", error=str(e))
            raise TokenError("Token creation failed")
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Validate token type
            token_type = payload.get("type")
            if token_type not in ["access", "refresh"]:
                raise TokenError("Invalid token type")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise TokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            raise TokenError("Invalid token")
        except Exception as e:
            logger.error("Failed to decode token", error=str(e))
            raise TokenError("Token decoding failed")
    
    def get_token_subject(self, token: str) -> str:
        """Extract subject from token."""
        payload = self.decode_token(token)
        return payload.get("sub")
    
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
            payload = self.decode_token(token)
            exp = payload.get("exp")
            if exp:
                return datetime.utcfromtimestamp(exp) < datetime.utcnow()
            return True
        except TokenError:
            return True
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token."""
        payload = self.decode_token(refresh_token)
        
        # Validate it's a refresh token
        if payload.get("type") != "refresh":
            raise TokenError("Invalid token type for refresh")
        
        subject = payload.get("sub")
        if not subject:
            raise TokenError("Invalid token subject")
        
        # Create new access token
        return self.create_access_token(subject)


class PermissionChecker:
    """Handles permission checking and role-based access control."""
    
    # Define role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        "user": 1,
        "moderator": 2,
        "admin": 3,
        "superadmin": 4
    }
    
    # Define permissions for each role
    ROLE_PERMISSIONS = {
        "user": [
            "read:own_profile",
            "update:own_profile",
            "delete:own_account"
        ],
        "moderator": [
            "read:own_profile",
            "update:own_profile",
            "delete:own_account",
            "read:user_profiles",
            "moderate:content"
        ],
        "admin": [
            "read:own_profile",
            "update:own_profile",
            "delete:own_account",
            "read:user_profiles",
            "update:user_profiles",
            "moderate:content",
            "manage:users",
            "read:system_config",
            "update:system_config"
        ],
        "superadmin": [
            "*"  # All permissions
        ]
    }
    
    @classmethod
    def has_permission(cls, user_role: str, required_permission: str) -> bool:
        """Check if a user role has a specific permission."""
        if user_role not in cls.ROLE_PERMISSIONS:
            return False
        
        role_permissions = cls.ROLE_PERMISSIONS[user_role]
        
        # Superadmin has all permissions
        if "*" in role_permissions:
            return True
        
        return required_permission in role_permissions
    
    @classmethod
    def has_role_level(cls, user_role: str, required_role: str) -> bool:
        """Check if user role meets minimum role level requirement."""
        user_level = cls.ROLE_HIERARCHY.get(user_role, 0)
        required_level = cls.ROLE_HIERARCHY.get(required_role, 0)
        
        return user_level >= required_level
    
    @classmethod
    def can_access_user_data(cls, requester_role: str, requester_id: str, target_user_id: str) -> bool:
        """Check if user can access another user's data."""
        # Users can always access their own data
        if requester_id == target_user_id:
            return True
        
        # Check if role has permission to read other user profiles
        return cls.has_permission(requester_role, "read:user_profiles")
    
    @classmethod
    def can_modify_user_data(cls, requester_role: str, requester_id: str, target_user_id: str) -> bool:
        """Check if user can modify another user's data."""
        # Users can always modify their own data
        if requester_id == target_user_id:
            return True
        
        # Check if role has permission to manage users
        return cls.has_permission(requester_role, "manage:users")


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return feedback."""
    settings = get_settings()
    
    issues = []
    score = 0
    
    # Length check
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        issues.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
    else:
        score += 1
    
    # Character type checks
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if settings.PASSWORD_REQUIRE_UPPERCASE and not has_upper:
        issues.append("Password must contain at least one uppercase letter")
    elif has_upper:
        score += 1
    
    if settings.PASSWORD_REQUIRE_LOWERCASE and not has_lower:
        issues.append("Password must contain at least one lowercase letter")
    elif has_lower:
        score += 1
    
    if settings.PASSWORD_REQUIRE_NUMBERS and not has_digit:
        issues.append("Password must contain at least one number")
    elif has_digit:
        score += 1
    
    if settings.PASSWORD_REQUIRE_SPECIAL and not has_special:
        issues.append("Password must contain at least one special character")
    elif has_special:
        score += 1
    
    # Calculate strength
    if score >= 4:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    elif score >= 2:
        strength = "weak"
    else:
        strength = "very_weak"
    
    return {
        "is_valid": len(issues) == 0,
        "strength": strength,
        "score": score,
        "issues": issues
    }


# Global instances
jwt_manager = JWTManager()
permission_checker = PermissionChecker()