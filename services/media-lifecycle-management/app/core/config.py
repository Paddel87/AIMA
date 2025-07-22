#!/usr/bin/env python3
"""
Configuration settings for the AIMA Media Lifecycle Management Service.

This module contains all configuration settings and environment variables
for the media lifecycle management service.
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    APP_NAME: str = Field(default="AIMA Media Lifecycle Management", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    ENVIRONMENT: str = Field(default="development", description="Environment (development, staging, production)")
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8003, description="Server port")
    WORKERS: int = Field(default=1, description="Number of worker processes")
    DEV_AUTO_RELOAD: bool = Field(default=True, description="Auto-reload in development")
    
    # Database settings
    DATABASE_URL: str = Field(
        default="postgresql://aima_user:aima_password@postgres:5432/aima",
        description="Database connection URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Database max overflow connections")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, description="Database pool timeout in seconds")
    
    # Redis settings
    REDIS_URL: str = Field(
        default="redis://:aima_password@redis:6379/2",
        description="Redis connection URL"
    )
    REDIS_POOL_SIZE: int = Field(default=10, description="Redis connection pool size")
    REDIS_TIMEOUT: int = Field(default=5, description="Redis operation timeout in seconds")
    
    # Object Storage settings (MinIO/S3)
    STORAGE_ENDPOINT: str = Field(default="minio:9000", description="Storage endpoint")
    STORAGE_ACCESS_KEY: str = Field(default="aima_user", description="Storage access key")
    STORAGE_SECRET_KEY: str = Field(default="aima_password", description="Storage secret key")
    STORAGE_BUCKET_NAME: str = Field(default="aima-media", description="Storage bucket name")
    STORAGE_SECURE: bool = Field(default=False, description="Use HTTPS for storage")
    STORAGE_REGION: str = Field(default="us-east-1", description="Storage region")
    
    # Media processing settings
    MAX_FILE_SIZE: int = Field(default=500 * 1024 * 1024, description="Maximum file size in bytes (500MB)")
    ALLOWED_MIME_TYPES: List[str] = Field(
        default=[
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
            "video/mp4", "video/avi", "video/mov", "video/wmv", "video/flv", "video/webm",
            "audio/mp3", "audio/wav", "audio/flac", "audio/aac", "audio/ogg"
        ],
        description="Allowed MIME types for upload"
    )
    THUMBNAIL_SIZE: tuple = Field(default=(200, 200), description="Thumbnail size (width, height)")
    VIDEO_PREVIEW_DURATION: int = Field(default=10, description="Video preview duration in seconds")
    
    # Security settings
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for encryption"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-jwt-secret-key-change-in-production",
        description="JWT secret key"
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT access token expiration")
    
    # External service URLs
    USER_MANAGEMENT_URL: str = Field(
        default="http://user-management:8000",
        description="User Management Service URL"
    )
    CONFIGURATION_MANAGEMENT_URL: str = Field(
        default="http://configuration-management:8002",
        description="Configuration Management Service URL"
    )
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "http://localhost"],
        description="Allowed CORS origins"
    )
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json, text)")
    LOG_FILE: Optional[str] = Field(default=None, description="Log file path")
    
    # Monitoring settings
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    METRICS_PORT: int = Field(default=9003, description="Metrics server port")
    
    # Cache settings
    CACHE_TTL: int = Field(default=3600, description="Default cache TTL in seconds")
    MEDIA_METADATA_CACHE_TTL: int = Field(default=7200, description="Media metadata cache TTL")
    
    # Processing settings
    ENABLE_VIRUS_SCAN: bool = Field(default=False, description="Enable virus scanning")
    ENABLE_THUMBNAIL_GENERATION: bool = Field(default=True, description="Enable thumbnail generation")
    ENABLE_METADATA_EXTRACTION: bool = Field(default=True, description="Enable metadata extraction")
    
    # Cleanup settings
    TEMP_FILE_CLEANUP_INTERVAL: int = Field(default=3600, description="Temp file cleanup interval in seconds")
    TEMP_FILE_MAX_AGE: int = Field(default=86400, description="Max age for temp files in seconds")
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level setting."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @validator("MAX_FILE_SIZE")
    def validate_max_file_size(cls, v):
        """Validate maximum file size."""
        if v <= 0:
            raise ValueError("Maximum file size must be positive")
        if v > 1024 * 1024 * 1024:  # 1GB
            raise ValueError("Maximum file size cannot exceed 1GB")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
    
    @property
    def database_url_async(self) -> str:
        """Get asynchronous database URL."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()