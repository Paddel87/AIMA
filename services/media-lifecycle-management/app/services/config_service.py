#!/usr/bin/env python3
"""
Configuration Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive configuration management including
settings validation, environment-specific configurations, dynamic updates,
and secure storage of sensitive configuration data.
"""

import logging
import os
import json
import yaml
from typing import Any, Dict, List, Optional, Union, Type, get_type_hints
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
import secrets
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text

from ..core.redis_client import CacheManager
from ..middleware.error_handling import ConfigurationError, ValidationError as CustomValidationError
from .security_service import SecurityService
from .audit_service import AuditService, AuditEventType, AuditSeverity


logger = logging.getLogger(__name__)


class ConfigScope(str, Enum):
    """Configuration scope levels."""
    GLOBAL = "global"
    SERVICE = "service"
    USER = "user"
    TENANT = "tenant"
    ENVIRONMENT = "environment"


class ConfigType(str, Enum):
    """Configuration value types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    LIST = "list"
    DICT = "dict"
    SECRET = "secret"
    URL = "url"
    EMAIL = "email"
    PATH = "path"


class Environment(str, Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ConfigSchema:
    """Configuration schema definition."""
    key: str
    config_type: ConfigType
    default_value: Any = None
    required: bool = False
    description: str = ""
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    sensitive: bool = False
    scope: ConfigScope = ConfigScope.GLOBAL
    environment_specific: bool = False
    
    def validate_value(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a configuration value against this schema."""
        try:
            # Type validation
            if self.config_type == ConfigType.STRING:
                if not isinstance(value, str):
                    return False, f"Expected string, got {type(value).__name__}"
            elif self.config_type == ConfigType.INTEGER:
                if not isinstance(value, int):
                    return False, f"Expected integer, got {type(value).__name__}"
            elif self.config_type == ConfigType.FLOAT:
                if not isinstance(value, (int, float)):
                    return False, f"Expected float, got {type(value).__name__}"
            elif self.config_type == ConfigType.BOOLEAN:
                if not isinstance(value, bool):
                    return False, f"Expected boolean, got {type(value).__name__}"
            elif self.config_type == ConfigType.LIST:
                if not isinstance(value, list):
                    return False, f"Expected list, got {type(value).__name__}"
            elif self.config_type == ConfigType.DICT:
                if not isinstance(value, dict):
                    return False, f"Expected dict, got {type(value).__name__}"
            elif self.config_type == ConfigType.JSON:
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    return False, "Value is not JSON serializable"
            
            # Custom validation rules
            if self.validation_rules:
                if "min_length" in self.validation_rules and isinstance(value, str):
                    if len(value) < self.validation_rules["min_length"]:
                        return False, f"String too short (min: {self.validation_rules['min_length']})"
                
                if "max_length" in self.validation_rules and isinstance(value, str):
                    if len(value) > self.validation_rules["max_length"]:
                        return False, f"String too long (max: {self.validation_rules['max_length']})"
                
                if "min_value" in self.validation_rules and isinstance(value, (int, float)):
                    if value < self.validation_rules["min_value"]:
                        return False, f"Value too small (min: {self.validation_rules['min_value']})"
                
                if "max_value" in self.validation_rules and isinstance(value, (int, float)):
                    if value > self.validation_rules["max_value"]:
                        return False, f"Value too large (max: {self.validation_rules['max_value']})"
                
                if "allowed_values" in self.validation_rules:
                    if value not in self.validation_rules["allowed_values"]:
                        return False, f"Value not in allowed list: {self.validation_rules['allowed_values']}"
                
                if "pattern" in self.validation_rules and isinstance(value, str):
                    import re
                    if not re.match(self.validation_rules["pattern"], value):
                        return False, f"Value doesn't match pattern: {self.validation_rules['pattern']}"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"


@dataclass
class ConfigValue:
    """Configuration value with metadata."""
    key: str
    value: Any
    config_type: ConfigType
    scope: ConfigScope = ConfigScope.GLOBAL
    environment: Optional[Environment] = None
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    version: int = 1
    encrypted: bool = False
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class DatabaseConfig(BaseModel):
    """Database configuration model."""
    host: str = Field(..., description="Database host")
    port: int = Field(5432, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    pool_size: int = Field(10, description="Connection pool size")
    max_overflow: int = Field(20, description="Max pool overflow")
    pool_timeout: int = Field(30, description="Pool timeout in seconds")
    pool_recycle: int = Field(3600, description="Pool recycle time in seconds")
    echo: bool = Field(False, description="Enable SQL echo")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @property
    def connection_string(self) -> str:
        """Get database connection string."""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseModel):
    """Redis configuration model."""
    host: str = Field("localhost", description="Redis host")
    port: int = Field(6379, description="Redis port")
    password: Optional[str] = Field(None, description="Redis password")
    database: int = Field(0, description="Redis database number")
    max_connections: int = Field(10, description="Max connections")
    socket_timeout: int = Field(5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(5, description="Socket connect timeout")
    retry_on_timeout: bool = Field(True, description="Retry on timeout")
    health_check_interval: int = Field(30, description="Health check interval")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('database')
    def validate_database(cls, v):
        if not 0 <= v <= 15:
            raise ValueError('Redis database must be between 0 and 15')
        return v


class StorageConfig(BaseModel):
    """Storage configuration model."""
    provider: str = Field(..., description="Storage provider (s3, azure, gcs, local)")
    bucket_name: Optional[str] = Field(None, description="Storage bucket/container name")
    region: Optional[str] = Field(None, description="Storage region")
    access_key: Optional[str] = Field(None, description="Access key")
    secret_key: Optional[str] = Field(None, description="Secret key")
    endpoint_url: Optional[str] = Field(None, description="Custom endpoint URL")
    local_path: Optional[str] = Field(None, description="Local storage path")
    max_file_size: int = Field(100 * 1024 * 1024, description="Max file size in bytes")
    allowed_extensions: List[str] = Field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi", ".mov"],
        description="Allowed file extensions"
    )
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed_providers = ['s3', 'azure', 'gcs', 'local']
        if v not in allowed_providers:
            raise ValueError(f'Provider must be one of: {allowed_providers}')
        return v
    
    @validator('max_file_size')
    def validate_max_file_size(cls, v):
        if v <= 0:
            raise ValueError('Max file size must be positive')
        return v


class SecurityConfig(BaseModel):
    """Security configuration model."""
    jwt_secret: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expiration")
    refresh_token_expire_days: int = Field(7, description="Refresh token expiration")
    password_min_length: int = Field(8, description="Minimum password length")
    max_login_attempts: int = Field(5, description="Max login attempts")
    account_lockout_minutes: int = Field(30, description="Account lockout duration")
    rate_limit_requests: int = Field(100, description="Rate limit requests per window")
    rate_limit_window_seconds: int = Field(300, description="Rate limit window")
    encryption_key: Optional[str] = Field(None, description="Data encryption key")
    
    @validator('access_token_expire_minutes')
    def validate_access_token_expire(cls, v):
        if not 1 <= v <= 1440:  # 1 minute to 24 hours
            raise ValueError('Access token expiration must be between 1 and 1440 minutes')
        return v
    
    @validator('password_min_length')
    def validate_password_min_length(cls, v):
        if not 6 <= v <= 128:
            raise ValueError('Password min length must be between 6 and 128')
        return v


class MediaProcessingConfig(BaseModel):
    """Media processing configuration model."""
    max_concurrent_jobs: int = Field(5, description="Max concurrent processing jobs")
    job_timeout_minutes: int = Field(60, description="Job timeout in minutes")
    thumbnail_sizes: List[Dict[str, int]] = Field(
        default_factory=lambda: [
            {"width": 150, "height": 150},
            {"width": 300, "height": 300},
            {"width": 600, "height": 600}
        ],
        description="Thumbnail sizes to generate"
    )
    video_quality_levels: List[str] = Field(
        default_factory=lambda: ["480p", "720p", "1080p"],
        description="Video quality levels for transcoding"
    )
    supported_formats: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "image": ["jpg", "jpeg", "png", "gif", "webp"],
            "video": ["mp4", "avi", "mov", "mkv", "webm"],
            "audio": ["mp3", "wav", "flac", "aac"]
        },
        description="Supported media formats"
    )
    
    @validator('max_concurrent_jobs')
    def validate_max_concurrent_jobs(cls, v):
        if not 1 <= v <= 50:
            raise ValueError('Max concurrent jobs must be between 1 and 50')
        return v


class NotificationConfig(BaseModel):
    """Notification configuration model."""
    email_enabled: bool = Field(True, description="Enable email notifications")
    sms_enabled: bool = Field(False, description="Enable SMS notifications")
    push_enabled: bool = Field(True, description="Enable push notifications")
    
    # Email settings
    smtp_host: Optional[str] = Field(None, description="SMTP host")
    smtp_port: int = Field(587, description="SMTP port")
    smtp_username: Optional[str] = Field(None, description="SMTP username")
    smtp_password: Optional[str] = Field(None, description="SMTP password")
    smtp_use_tls: bool = Field(True, description="Use TLS for SMTP")
    from_email: Optional[str] = Field(None, description="From email address")
    
    # SMS settings
    sms_provider: Optional[str] = Field(None, description="SMS provider (twilio, aws_sns)")
    sms_api_key: Optional[str] = Field(None, description="SMS API key")
    sms_api_secret: Optional[str] = Field(None, description="SMS API secret")
    
    # Push notification settings
    fcm_server_key: Optional[str] = Field(None, description="FCM server key")
    apns_key_id: Optional[str] = Field(None, description="APNS key ID")
    apns_team_id: Optional[str] = Field(None, description="APNS team ID")
    apns_bundle_id: Optional[str] = Field(None, description="APNS bundle ID")
    
    @validator('smtp_port')
    def validate_smtp_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('SMTP port must be between 1 and 65535')
        return v


class ApplicationConfig(BaseModel):
    """Main application configuration model."""
    # Application settings
    app_name: str = Field("AIMA Media Lifecycle Management", description="Application name")
    app_version: str = Field("1.0.0", description="Application version")
    environment: Environment = Field(Environment.DEVELOPMENT, description="Environment")
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Log level")
    
    # Server settings
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    workers: int = Field(1, description="Number of workers")
    
    # Component configurations
    database: DatabaseConfig
    redis: RedisConfig
    storage: StorageConfig
    security: SecurityConfig
    media_processing: MediaProcessingConfig
    notifications: NotificationConfig
    
    # Feature flags
    features: Dict[str, bool] = Field(
        default_factory=lambda: {
            "analytics_enabled": True,
            "webhooks_enabled": True,
            "backup_enabled": True,
            "monitoring_enabled": True,
            "audit_enabled": True
        },
        description="Feature flags"
    )
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'Log level must be one of: {allowed_levels}')
        return v.upper()


class ConfigService:
    """Service for configuration management."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        security_service: Optional[SecurityService] = None,
        audit_service: Optional[AuditService] = None
    ):
        self.cache = cache_manager
        self.security_service = security_service
        self.audit_service = audit_service
        
        # Configuration storage
        self.config_schemas: Dict[str, ConfigSchema] = {}
        self.config_values: Dict[str, ConfigValue] = {}
        
        # Environment and paths
        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
        self.config_dir = Path(os.getenv("CONFIG_DIR", "config"))
        self.config_file = self.config_dir / f"{self.environment.value}.yaml"
        
        # Cache settings
        self.cache_ttl = 300  # 5 minutes
        self.cache_prefix = "config"
        
        # Initialize default schemas
        self._initialize_default_schemas()
        
        # Load configuration
        self.app_config: Optional[ApplicationConfig] = None
        self._load_configuration()
    
    def _initialize_default_schemas(self):
        """Initialize default configuration schemas."""
        schemas = [
            # Database configuration
            ConfigSchema(
                key="database.host",
                config_type=ConfigType.STRING,
                default_value="localhost",
                required=True,
                description="Database host",
                scope=ConfigScope.GLOBAL,
                environment_specific=True
            ),
            ConfigSchema(
                key="database.port",
                config_type=ConfigType.INTEGER,
                default_value=5432,
                description="Database port",
                validation_rules={"min_value": 1, "max_value": 65535}
            ),
            ConfigSchema(
                key="database.password",
                config_type=ConfigType.SECRET,
                required=True,
                description="Database password",
                sensitive=True
            ),
            
            # Redis configuration
            ConfigSchema(
                key="redis.host",
                config_type=ConfigType.STRING,
                default_value="localhost",
                description="Redis host",
                environment_specific=True
            ),
            ConfigSchema(
                key="redis.port",
                config_type=ConfigType.INTEGER,
                default_value=6379,
                description="Redis port",
                validation_rules={"min_value": 1, "max_value": 65535}
            ),
            
            # Security configuration
            ConfigSchema(
                key="security.jwt_secret",
                config_type=ConfigType.SECRET,
                required=True,
                description="JWT secret key",
                sensitive=True,
                validation_rules={"min_length": 32}
            ),
            ConfigSchema(
                key="security.access_token_expire_minutes",
                config_type=ConfigType.INTEGER,
                default_value=30,
                description="Access token expiration in minutes",
                validation_rules={"min_value": 1, "max_value": 1440}
            ),
            
            # Storage configuration
            ConfigSchema(
                key="storage.provider",
                config_type=ConfigType.STRING,
                default_value="local",
                description="Storage provider",
                validation_rules={"allowed_values": ["s3", "azure", "gcs", "local"]}
            ),
            ConfigSchema(
                key="storage.max_file_size",
                config_type=ConfigType.INTEGER,
                default_value=100 * 1024 * 1024,  # 100MB
                description="Maximum file size in bytes",
                validation_rules={"min_value": 1024}  # 1KB minimum
            ),
            
            # Feature flags
            ConfigSchema(
                key="features.analytics_enabled",
                config_type=ConfigType.BOOLEAN,
                default_value=True,
                description="Enable analytics features"
            ),
            ConfigSchema(
                key="features.webhooks_enabled",
                config_type=ConfigType.BOOLEAN,
                default_value=True,
                description="Enable webhook functionality"
            ),
            
            # Media processing
            ConfigSchema(
                key="media_processing.max_concurrent_jobs",
                config_type=ConfigType.INTEGER,
                default_value=5,
                description="Maximum concurrent processing jobs",
                validation_rules={"min_value": 1, "max_value": 50}
            ),
            
            # Notification settings
            ConfigSchema(
                key="notifications.email_enabled",
                config_type=ConfigType.BOOLEAN,
                default_value=True,
                description="Enable email notifications"
            )
        ]
        
        for schema in schemas:
            self.config_schemas[schema.key] = schema
    
    def _load_configuration(self):
        """Load configuration from files and environment."""
        try:
            # Load from YAML file if exists
            config_data = {}
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f) or {}
            
            # Override with environment variables
            env_overrides = self._load_from_environment()
            config_data.update(env_overrides)
            
            # Validate and create application config
            self.app_config = ApplicationConfig(**config_data)
            
            logger.info(f"Configuration loaded for environment: {self.environment.value}")
            
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise ConfigurationError(f"Invalid configuration: {e}")
        except Exception as e:
            logger.error(f"Configuration loading error: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Database configuration
        if os.getenv("DATABASE_URL"):
            # Parse DATABASE_URL if provided
            db_url = os.getenv("DATABASE_URL")
            # This is a simplified parser, you might want to use a proper URL parser
            env_config["database"] = {"connection_string": db_url}
        else:
            db_config = {}
            if os.getenv("DB_HOST"):
                db_config["host"] = os.getenv("DB_HOST")
            if os.getenv("DB_PORT"):
                db_config["port"] = int(os.getenv("DB_PORT"))
            if os.getenv("DB_NAME"):
                db_config["database"] = os.getenv("DB_NAME")
            if os.getenv("DB_USER"):
                db_config["username"] = os.getenv("DB_USER")
            if os.getenv("DB_PASSWORD"):
                db_config["password"] = os.getenv("DB_PASSWORD")
            
            if db_config:
                env_config["database"] = db_config
        
        # Redis configuration
        redis_config = {}
        if os.getenv("REDIS_HOST"):
            redis_config["host"] = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            redis_config["port"] = int(os.getenv("REDIS_PORT"))
        if os.getenv("REDIS_PASSWORD"):
            redis_config["password"] = os.getenv("REDIS_PASSWORD")
        if os.getenv("REDIS_DB"):
            redis_config["database"] = int(os.getenv("REDIS_DB"))
        
        if redis_config:
            env_config["redis"] = redis_config
        
        # Security configuration
        security_config = {}
        if os.getenv("JWT_SECRET"):
            security_config["jwt_secret"] = os.getenv("JWT_SECRET")
        if os.getenv("ENCRYPTION_KEY"):
            security_config["encryption_key"] = os.getenv("ENCRYPTION_KEY")
        
        if security_config:
            env_config["security"] = security_config
        
        # Storage configuration
        storage_config = {}
        if os.getenv("STORAGE_PROVIDER"):
            storage_config["provider"] = os.getenv("STORAGE_PROVIDER")
        if os.getenv("STORAGE_BUCKET"):
            storage_config["bucket_name"] = os.getenv("STORAGE_BUCKET")
        if os.getenv("STORAGE_REGION"):
            storage_config["region"] = os.getenv("STORAGE_REGION")
        if os.getenv("STORAGE_ACCESS_KEY"):
            storage_config["access_key"] = os.getenv("STORAGE_ACCESS_KEY")
        if os.getenv("STORAGE_SECRET_KEY"):
            storage_config["secret_key"] = os.getenv("STORAGE_SECRET_KEY")
        
        if storage_config:
            env_config["storage"] = storage_config
        
        # Application settings
        if os.getenv("APP_NAME"):
            env_config["app_name"] = os.getenv("APP_NAME")
        if os.getenv("APP_VERSION"):
            env_config["app_version"] = os.getenv("APP_VERSION")
        if os.getenv("DEBUG"):
            env_config["debug"] = os.getenv("DEBUG").lower() in ("true", "1", "yes")
        if os.getenv("LOG_LEVEL"):
            env_config["log_level"] = os.getenv("LOG_LEVEL")
        if os.getenv("HOST"):
            env_config["host"] = os.getenv("HOST")
        if os.getenv("PORT"):
            env_config["port"] = int(os.getenv("PORT"))
        
        return env_config
    
    # Configuration retrieval methods
    
    def get_config(self) -> ApplicationConfig:
        """Get the complete application configuration."""
        if not self.app_config:
            raise ConfigurationError("Configuration not loaded")
        return self.app_config
    
    async def get_value(
        self,
        key: str,
        scope: ConfigScope = ConfigScope.GLOBAL,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        default: Any = None
    ) -> Any:
        """Get a configuration value."""
        try:
            # Try cache first
            cache_key = self._get_cache_key(key, scope, tenant_id, user_id)
            cached_value = await self.cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Get from configuration
            config_value = await self._get_config_value(key, scope, tenant_id, user_id)
            
            if config_value is not None:
                # Cache the value
                await self.cache.set(cache_key, config_value.value, ttl=self.cache_ttl)
                return config_value.value
            
            # Check schema for default value
            if key in self.config_schemas:
                schema = self.config_schemas[key]
                if schema.default_value is not None:
                    return schema.default_value
            
            return default
            
        except Exception as e:
            logger.error(f"Error getting config value {key}: {e}")
            return default
    
    async def set_value(
        self,
        db: AsyncSession,
        key: str,
        value: Any,
        scope: ConfigScope = ConfigScope.GLOBAL,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        updated_by: Optional[UUID] = None
    ) -> bool:
        """Set a configuration value."""
        try:
            # Validate against schema if exists
            if key in self.config_schemas:
                schema = self.config_schemas[key]
                is_valid, error_message = schema.validate_value(value)
                
                if not is_valid:
                    raise CustomValidationError(f"Invalid value for {key}: {error_message}")
                
                # Encrypt sensitive values
                if schema.sensitive and self.security_service:
                    value = self.security_service.encrypt_data(str(value))
                    encrypted = True
                else:
                    encrypted = False
            else:
                encrypted = False
            
            # Create or update config value
            config_value = ConfigValue(
                key=key,
                value=value,
                config_type=self.config_schemas.get(key, ConfigSchema(key, ConfigType.STRING)).config_type,
                scope=scope,
                tenant_id=tenant_id,
                user_id=user_id,
                updated_by=updated_by,
                updated_at=datetime.utcnow(),
                encrypted=encrypted
            )
            
            # Store in database (implementation depends on your database schema)
            await self._store_config_value(db, config_value)
            
            # Update cache
            cache_key = self._get_cache_key(key, scope, tenant_id, user_id)
            await self.cache.set(cache_key, value, ttl=self.cache_ttl)
            
            # Log configuration change
            if self.audit_service:
                from .audit_service import AuditContext, AuditEvent
                
                context = AuditContext(user_id=updated_by)
                audit_event = AuditEvent(
                    event_type=AuditEventType.CONFIGURATION_CHANGED,
                    severity=AuditSeverity.MEDIUM,
                    status="success",
                    message=f"Configuration value updated: {key}",
                    context=context,
                    details={
                        "key": key,
                        "scope": scope.value,
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "user_id": str(user_id) if user_id else None
                    }
                )
                
                await self.audit_service.log_event(db, audit_event)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting config value {key}: {e}")
            return False
    
    async def delete_value(
        self,
        db: AsyncSession,
        key: str,
        scope: ConfigScope = ConfigScope.GLOBAL,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        deleted_by: Optional[UUID] = None
    ) -> bool:
        """Delete a configuration value."""
        try:
            # Remove from database
            await self._delete_config_value(db, key, scope, tenant_id, user_id)
            
            # Remove from cache
            cache_key = self._get_cache_key(key, scope, tenant_id, user_id)
            await self.cache.delete(cache_key)
            
            # Log configuration deletion
            if self.audit_service:
                from .audit_service import AuditContext, AuditEvent
                
                context = AuditContext(user_id=deleted_by)
                audit_event = AuditEvent(
                    event_type=AuditEventType.CONFIGURATION_CHANGED,
                    severity=AuditSeverity.MEDIUM,
                    status="success",
                    message=f"Configuration value deleted: {key}",
                    context=context,
                    details={
                        "key": key,
                        "scope": scope.value,
                        "action": "delete"
                    }
                )
                
                await self.audit_service.log_event(db, audit_event)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting config value {key}: {e}")
            return False
    
    # Schema management
    
    def register_schema(self, schema: ConfigSchema):
        """Register a configuration schema."""
        self.config_schemas[schema.key] = schema
        logger.debug(f"Registered config schema: {schema.key}")
    
    def get_schema(self, key: str) -> Optional[ConfigSchema]:
        """Get configuration schema for a key."""
        return self.config_schemas.get(key)
    
    def get_all_schemas(self) -> Dict[str, ConfigSchema]:
        """Get all registered configuration schemas."""
        return self.config_schemas.copy()
    
    # Configuration validation
    
    async def validate_configuration(self) -> Tuple[bool, List[str]]:
        """Validate the current configuration."""
        errors = []
        
        try:
            # Validate application config
            if self.app_config:
                # This will raise ValidationError if invalid
                ApplicationConfig(**self.app_config.dict())
            else:
                errors.append("Application configuration not loaded")
            
            # Validate individual config values against schemas
            for key, schema in self.config_schemas.items():
                if schema.required:
                    value = await self.get_value(key)
                    if value is None:
                        errors.append(f"Required configuration missing: {key}")
                    else:
                        is_valid, error_message = schema.validate_value(value)
                        if not is_valid:
                            errors.append(f"Invalid value for {key}: {error_message}")
            
            return len(errors) == 0, errors
            
        except ValidationError as e:
            errors.extend([str(err) for err in e.errors()])
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    # Configuration export/import
    
    async def export_configuration(
        self,
        scope: Optional[ConfigScope] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Export configuration to a dictionary."""
        try:
            config_data = {}
            
            if self.app_config:
                config_dict = self.app_config.dict()
                
                # Filter sensitive data if requested
                if not include_sensitive:
                    config_dict = self._filter_sensitive_data(config_dict)
                
                config_data.update(config_dict)
            
            return config_data
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return {}
    
    async def import_configuration(
        self,
        db: AsyncSession,
        config_data: Dict[str, Any],
        updated_by: Optional[UUID] = None,
        validate_only: bool = False
    ) -> Tuple[bool, List[str]]:
        """Import configuration from a dictionary."""
        errors = []
        
        try:
            # Validate the configuration data
            try:
                ApplicationConfig(**config_data)
            except ValidationError as e:
                errors.extend([str(err) for err in e.errors()])
                return False, errors
            
            if validate_only:
                return True, []
            
            # Update configuration values
            for key, value in self._flatten_dict(config_data).items():
                success = await self.set_value(
                    db, key, value, updated_by=updated_by
                )
                if not success:
                    errors.append(f"Failed to set {key}")
            
            # Reload configuration
            self._load_configuration()
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            return False, [str(e)]
    
    # Utility methods
    
    def _get_cache_key(
        self,
        key: str,
        scope: ConfigScope,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> str:
        """Generate cache key for configuration value."""
        parts = [self.cache_prefix, scope.value, key]
        
        if tenant_id:
            parts.append(f"tenant:{tenant_id}")
        if user_id:
            parts.append(f"user:{user_id}")
        
        return ":".join(parts)
    
    async def _get_config_value(
        self,
        key: str,
        scope: ConfigScope,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> Optional[ConfigValue]:
        """Get configuration value from storage."""
        # This is a placeholder - implement based on your database schema
        # For now, return None to fall back to defaults
        return None
    
    async def _store_config_value(self, db: AsyncSession, config_value: ConfigValue):
        """Store configuration value in database."""
        # This is a placeholder - implement based on your database schema
        pass
    
    async def _delete_config_value(
        self,
        db: AsyncSession,
        key: str,
        scope: ConfigScope,
        tenant_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ):
        """Delete configuration value from database."""
        # This is a placeholder - implement based on your database schema
        pass
    
    def _filter_sensitive_data(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Filter sensitive data from configuration dictionary."""
        sensitive_keys = {
            "password", "secret", "key", "token", "credential",
            "private", "auth", "api_key", "access_key", "secret_key"
        }
        
        def filter_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            filtered = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    filtered[k] = filter_dict(v)
                elif any(sensitive in k.lower() for sensitive in sensitive_keys):
                    filtered[k] = "[REDACTED]"
                else:
                    filtered[k] = v
            return filtered
        
        return filter_dict(config_dict)
    
    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: str = "."
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    # Configuration reload
    
    async def reload_configuration(self):
        """Reload configuration from files and environment."""
        try:
            self._load_configuration()
            
            # Clear cache
            cache_pattern = f"{self.cache_prefix}:*"
            await self.cache.delete_pattern(cache_pattern)
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            raise ConfigurationError(f"Failed to reload configuration: {e}")
    
    # Health check
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform configuration health check."""
        try:
            is_valid, errors = await self.validate_configuration()
            
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "environment": self.environment.value,
                "config_loaded": self.app_config is not None,
                "schemas_registered": len(self.config_schemas),
                "validation_errors": errors if not is_valid else [],
                "last_reload": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }