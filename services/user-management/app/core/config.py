#!/usr/bin/env python3
"""
Configuration management for the AIMA User Management Service.

This module handles all configuration settings using Pydantic Settings
with environment variable support and validation.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables
    )
    
    # Application settings
    APP_NAME: str = "AIMA User Management Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8001, env="PORT")
    WORKERS: int = Field(default=1, env="WORKERS")
    
    # Security settings
    SECRET_KEY: str = Field(
        default="your-super-secret-key-change-this-in-production",
        env="SECRET_KEY"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-super-secret-jwt-key-change-this-in-production",
        env="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Password settings
    PASSWORD_MIN_LENGTH: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    PASSWORD_REQUIRE_SPECIAL_CHARS: bool = Field(
        default=True, env="PASSWORD_REQUIRE_SPECIAL_CHARS"
    )
    
    # Session settings
    SESSION_TIMEOUT_HOURS: int = Field(default=8, env="SESSION_TIMEOUT_HOURS")
    
    # CORS settings
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1", "*"],
        env="ALLOWED_HOSTS"
    )
    
    # Database settings
    DATABASE_URL: str = Field(
        default="postgresql://aima_user:aima_password@localhost:5432/aima",
        env="DATABASE_URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    DATABASE_ECHO: bool = Field(default=False, env="DATABASE_ECHO")
    
    # Redis settings
    REDIS_URL: str = Field(
        default="redis://:aima_password@localhost:6379/0",
        env="REDIS_URL"
    )
    REDIS_POOL_SIZE: int = Field(default=10, env="REDIS_POOL_SIZE")
    REDIS_SESSION_DB: int = Field(default=1, env="REDIS_SESSION_DB")
    REDIS_CACHE_DB: int = Field(default=2, env="REDIS_CACHE_DB")
    
    # Message broker settings
    RABBITMQ_URL: str = Field(
        default="amqp://aima_user:aima_password@localhost:5672/",
        env="RABBITMQ_URL"
    )
    RABBITMQ_EXCHANGE: str = Field(default="aima.events", env="RABBITMQ_EXCHANGE")
    RABBITMQ_QUEUE_PREFIX: str = Field(
        default="aima.user_management", env="RABBITMQ_QUEUE_PREFIX"
    )
    
    # Rate limiting settings
    RATE_LIMITING_ENABLED: bool = Field(default=True, env="RATE_LIMITING_ENABLED")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=100, env="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )
    
    # Monitoring settings
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    HEALTH_CHECK_INTERVAL: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # External service URLs
    CONFIGURATION_SERVICE_URL: str = Field(
        default="http://configuration-service:8000",
        env="CONFIGURATION_SERVICE_URL"
    )
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @validator("PASSWORD_MIN_LENGTH")
    def validate_password_min_length(cls, v):
        if v < 6:
            raise ValueError("PASSWORD_MIN_LENGTH must be at least 6")
        return v
    
    @validator("JWT_EXPIRATION_HOURS")
    def validate_jwt_expiration(cls, v):
        if v < 1 or v > 168:  # 1 hour to 1 week
            raise ValueError("JWT_EXPIRATION_HOURS must be between 1 and 168")
        return v
    



@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance for convenience
settings = get_settings()