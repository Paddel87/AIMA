#!/usr/bin/env python3
"""
Database models for GPU Orchestration Service.

This module defines the SQLAlchemy models for GPU instances, jobs,
and provider configurations.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class GPUProvider(str, Enum):
    """GPU provider types."""
    RUNPOD = "runpod"
    VAST = "vast"
    AWS = "aws"
    LOCAL = "local"


class GPUType(str, Enum):
    """GPU hardware types."""
    RTX4090 = "RTX4090"
    RTX3090 = "RTX3090"
    A100 = "A100"
    H100 = "H100"
    V100 = "V100"
    T4 = "T4"


class InstanceStatus(str, Enum):
    """GPU instance status."""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobType(str, Enum):
    """Job types for different models."""
    LLAVA_INFERENCE = "llava_inference"
    LLAMA_INFERENCE = "llama_inference"
    TRAINING = "training"
    BATCH_PROCESSING = "batch_processing"
    CUSTOM = "custom"


class GPUInstance(Base):
    """GPU instance model."""
    __tablename__ = "gpu_instances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, index=True)
    provider_instance_id = Column(String(255), nullable=False)
    gpu_type = Column(String(50), nullable=False)
    gpu_count = Column(Integer, nullable=False, default=1)
    memory_gb = Column(Integer, nullable=False)
    vcpus = Column(Integer, nullable=False)
    storage_gb = Column(Integer, nullable=False)
    
    # Status and lifecycle
    status = Column(String(50), nullable=False, default=InstanceStatus.PENDING, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    
    # Network and access
    public_ip = Column(String(45), nullable=True)
    private_ip = Column(String(45), nullable=True)
    ssh_port = Column(Integer, nullable=True)
    api_port = Column(Integer, nullable=True)
    
    # Cost tracking
    hourly_cost_usd = Column(Float, nullable=False)
    total_cost_usd = Column(Float, nullable=False, default=0.0)
    
    # Configuration
    docker_image = Column(String(255), nullable=True)
    environment_vars = Column(JSON, nullable=True)
    startup_script = Column(Text, nullable=True)
    
    # Metadata
    region = Column(String(100), nullable=True)
    availability_zone = Column(String(100), nullable=True)
    preemptible = Column(Boolean, nullable=False, default=False)
    auto_terminate_minutes = Column(Integer, nullable=True)
    
    # Provider-specific data
    provider_metadata = Column(JSON, nullable=True)
    
    # Relationships
    jobs = relationship("GPUJob", back_populates="instance")
    
    __table_args__ = (
        Index("idx_gpu_instances_provider_status", "provider", "status"),
        Index("idx_gpu_instances_created_at", "created_at"),
        UniqueConstraint("provider", "provider_instance_id", name="uq_provider_instance"),
    )


class GPUJob(Base):
    """GPU job model."""
    __tablename__ = "gpu_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Job configuration
    job_type = Column(String(50), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, 10 is highest
    
    # Resource requirements
    required_gpu_type = Column(String(50), nullable=True)
    required_gpu_count = Column(Integer, nullable=False, default=1)
    required_memory_gb = Column(Integer, nullable=False)
    max_runtime_minutes = Column(Integer, nullable=False, default=60)
    
    # Status and lifecycle
    status = Column(String(50), nullable=False, default=JobStatus.QUEUED, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Instance assignment
    instance_id = Column(UUID(as_uuid=True), ForeignKey("gpu_instances.id"), nullable=True, index=True)
    
    # Job data
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Progress tracking
    progress_percentage = Column(Float, nullable=False, default=0.0)
    estimated_completion_at = Column(DateTime(timezone=True), nullable=True)
    
    # Cost tracking
    estimated_cost_usd = Column(Float, nullable=True)
    actual_cost_usd = Column(Float, nullable=True)
    
    # Retry configuration
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Metadata
    tags = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    instance = relationship("GPUInstance", back_populates="jobs")
    
    __table_args__ = (
        Index("idx_gpu_jobs_user_status", "user_id", "status"),
        Index("idx_gpu_jobs_priority_created", "priority", "created_at"),
        Index("idx_gpu_jobs_job_type", "job_type"),
    )


class ProviderConfig(Base):
    """Provider configuration model."""
    __tablename__ = "provider_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, unique=True)
    
    # Configuration
    enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, 10 is highest
    max_instances = Column(Integer, nullable=False, default=5)
    max_hourly_cost_usd = Column(Float, nullable=False, default=10.0)
    
    # API configuration
    api_endpoint = Column(String(255), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    webhook_secret_encrypted = Column(Text, nullable=True)
    
    # Default instance configuration
    default_gpu_type = Column(String(50), nullable=True)
    default_docker_image = Column(String(255), nullable=True)
    default_region = Column(String(100), nullable=True)
    
    # Provider-specific settings
    provider_settings = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(50), nullable=False, default="unknown")
    
    __table_args__ = (
        Index("idx_provider_configs_enabled", "enabled"),
        Index("idx_provider_configs_priority", "priority"),
    )


class JobTemplate(Base):
    """Job template model for predefined job configurations."""
    __tablename__ = "job_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Template configuration
    job_type = Column(String(50), nullable=False)
    model_name = Column(String(255), nullable=False)
    docker_image = Column(String(255), nullable=False)
    
    # Resource requirements
    required_gpu_type = Column(String(50), nullable=True)
    required_gpu_count = Column(Integer, nullable=False, default=1)
    required_memory_gb = Column(Integer, nullable=False)
    max_runtime_minutes = Column(Integer, nullable=False, default=60)
    
    # Default configuration
    default_environment_vars = Column(JSON, nullable=True)
    startup_script = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=False)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("idx_job_templates_job_type", "job_type"),
        Index("idx_job_templates_model_name", "model_name"),
    )


class ResourceQuota(Base):
    """Resource quota model for users/organizations."""
    __tablename__ = "resource_quotas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    
    # Quota limits
    max_concurrent_instances = Column(Integer, nullable=False, default=2)
    max_concurrent_jobs = Column(Integer, nullable=False, default=10)
    max_daily_cost_usd = Column(Float, nullable=False, default=100.0)
    max_monthly_cost_usd = Column(Float, nullable=False, default=1000.0)
    
    # Current usage
    current_instances = Column(Integer, nullable=False, default=0)
    current_jobs = Column(Integer, nullable=False, default=0)
    daily_cost_usd = Column(Float, nullable=False, default=0.0)
    monthly_cost_usd = Column(Float, nullable=False, default=0.0)
    
    # Reset tracking
    daily_reset_at = Column(DateTime(timezone=True), nullable=False)
    monthly_reset_at = Column(DateTime(timezone=True), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index("idx_resource_quotas_user_id", "user_id"),
    )