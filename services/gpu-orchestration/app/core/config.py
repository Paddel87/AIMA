#!/usr/bin/env python3
"""
Configuration management for the GPU Orchestration Service.

This module handles all configuration settings including database connections,
GPU provider credentials, and service-specific parameters.
"""

import os
from typing import Optional, List, Dict, Any
from functools import lru_cache

from pydantic import BaseSettings, Field, validator
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    # Service Configuration
    SERVICE_NAME: str = "gpu-orchestration"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_PREFIX: str = Field(default="/api/v1", env="API_PREFIX")
    
    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://aima_user:aima_password@localhost:5432/aima_db",
        env="DATABASE_URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=30, env="DATABASE_MAX_OVERFLOW")
    
    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    
    # RabbitMQ Configuration
    RABBITMQ_URL: str = Field(
        default="amqp://aima_user:aima_password@localhost:5672/aima_vhost",
        env="RABBITMQ_URL"
    )
    
    # GPU Provider Configuration
    
    # RunPod Configuration
    RUNPOD_API_KEY: Optional[str] = Field(default=None, env="RUNPOD_API_KEY")
    RUNPOD_API_URL: str = Field(
        default="https://api.runpod.io/graphql",
        env="RUNPOD_API_URL"
    )
    RUNPOD_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="RUNPOD_WEBHOOK_SECRET")
    
    # Vast.ai Configuration
    VAST_API_KEY: Optional[str] = Field(default=None, env="VAST_API_KEY")
    VAST_API_URL: str = Field(
        default="https://console.vast.ai/api/v0",
        env="VAST_API_URL"
    )
    
    # AWS Configuration (for potential EC2 instances)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    
    # Kubernetes Configuration
    KUBERNETES_CONFIG_PATH: Optional[str] = Field(default=None, env="KUBERNETES_CONFIG_PATH")
    KUBERNETES_NAMESPACE: str = Field(default="aima-gpu", env="KUBERNETES_NAMESPACE")
    
    # GPU Configuration
    DEFAULT_GPU_TYPE: str = Field(default="RTX4090", env="DEFAULT_GPU_TYPE")
    MAX_GPU_INSTANCES: int = Field(default=10, env="MAX_GPU_INSTANCES")
    GPU_TIMEOUT_MINUTES: int = Field(default=60, env="GPU_TIMEOUT_MINUTES")
    
    # LLaVA Configuration
    LLAVA_MODEL_NAME: str = Field(default="llava-v1.6-34b", env="LLAVA_MODEL_NAME")
    LLAVA_GPU_MEMORY_GB: int = Field(default=48, env="LLAVA_GPU_MEMORY_GB")
    LLAVA_MAX_INSTANCES: int = Field(default=4, env="LLAVA_MAX_INSTANCES")
    
    # Llama Configuration
    LLAMA_MODEL_NAME: str = Field(default="llama-3.1-70b", env="LLAMA_MODEL_NAME")
    LLAMA_GPU_MEMORY_GB: int = Field(default=48, env="LLAMA_GPU_MEMORY_GB")
    LLAMA_MAX_INSTANCES: int = Field(default=2, env="LLAMA_MAX_INSTANCES")
    
    # Cost Optimization
    MAX_HOURLY_COST_USD: float = Field(default=50.0, env="MAX_HOURLY_COST_USD")
    COST_OPTIMIZATION_ENABLED: bool = Field(default=True, env="COST_OPTIMIZATION_ENABLED")
    PREEMPTIBLE_INSTANCES_ALLOWED: bool = Field(default=True, env="PREEMPTIBLE_INSTANCES_ALLOWED")
    
    # Monitoring Configuration
    PROMETHEUS_PORT: int = Field(default=9090, env="PROMETHEUS_PORT")
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    
    # Security Configuration
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        env="SECRET_KEY"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Job Configuration
    MAX_CONCURRENT_JOBS: int = Field(default=20, env="MAX_CONCURRENT_JOBS")
    JOB_TIMEOUT_HOURS: int = Field(default=24, env="JOB_TIMEOUT_HOURS")
    JOB_RETRY_ATTEMPTS: int = Field(default=3, env="JOB_RETRY_ATTEMPTS")
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    @validator("REDIS_URL")
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must be a Redis URL")
        return v
    
    @property
    def gpu_providers_configured(self) -> List[str]:
        """Get list of configured GPU providers."""
        providers = []
        if self.RUNPOD_API_KEY:
            providers.append("runpod")
        if self.VAST_API_KEY:
            providers.append("vast")
        if self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY:
            providers.append("aws")
        return providers
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for specific GPU provider."""
        configs = {
            "runpod": {
                "api_key": self.RUNPOD_API_KEY,
                "api_url": self.RUNPOD_API_URL,
                "webhook_secret": self.RUNPOD_WEBHOOK_SECRET
            },
            "vast": {
                "api_key": self.VAST_API_KEY,
                "api_url": self.VAST_API_URL
            },
            "aws": {
                "access_key_id": self.AWS_ACCESS_KEY_ID,
                "secret_access_key": self.AWS_SECRET_ACCESS_KEY,
                "region": self.AWS_REGION
            }
        }
        return configs.get(provider, {})


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()