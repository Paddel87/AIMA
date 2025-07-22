#!/usr/bin/env python3
"""
Database configuration and models for the AIMA Media Lifecycle Management Service.

This module contains SQLAlchemy models and database configuration
for media lifecycle management.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, JSON,
    BigInteger, Float, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Database base class
Base = declarative_base()

# Global database variables
engine = None
SessionLocal = None


class MediaType(str, Enum):
    """Media type enumeration."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class MediaStatus(str, Enum):
    """Media processing status enumeration."""
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class StorageTier(str, Enum):
    """Storage tier enumeration."""
    HOT = "hot"          # Frequently accessed
    WARM = "warm"        # Occasionally accessed
    COLD = "cold"        # Rarely accessed
    ARCHIVE = "archive"  # Long-term storage


class MediaFile(Base):
    """Media file model."""
    __tablename__ = "media_files"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Basic file information
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False, index=True)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256
    
    # Media type and status
    media_type = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=MediaStatus.UPLOADING, index=True)
    
    # Storage information
    storage_path = Column(String(500), nullable=False)
    storage_bucket = Column(String(100), nullable=False)
    storage_tier = Column(String(20), nullable=False, default=StorageTier.HOT)
    
    # Media metadata
    width = Column(Integer, nullable=True)  # For images and videos
    height = Column(Integer, nullable=True)  # For images and videos
    duration = Column(Float, nullable=True)  # For videos and audio (in seconds)
    bitrate = Column(Integer, nullable=True)  # For videos and audio
    frame_rate = Column(Float, nullable=True)  # For videos
    
    # Additional metadata (flexible JSON field)
    metadata = Column(JSONB, nullable=True)
    
    # Processing information
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_error = Column(Text, nullable=True)
    
    # Thumbnail and preview
    thumbnail_path = Column(String(500), nullable=True)
    preview_path = Column(String(500), nullable=True)
    
    # User and audit information
    uploaded_by = Column(UUID(as_uuid=True), nullable=True, index=True)  # User ID
    upload_ip = Column(String(45), nullable=True)  # IPv4/IPv6
    upload_user_agent = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime, nullable=True)  # Last access time
    
    # Soft delete
    deleted_at = Column(DateTime, nullable=True, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    
    # Relationships
    tags = relationship("MediaTag", back_populates="media_file", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="media_file", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_media_files_type_status', 'media_type', 'status'),
        Index('idx_media_files_created_at', 'created_at'),
        Index('idx_media_files_uploaded_by', 'uploaded_by'),
        Index('idx_media_files_deleted', 'is_deleted', 'deleted_at'),
    )
    
    def __repr__(self):
        return f"<MediaFile(id={self.id}, filename={self.filename}, type={self.media_type})>"


class MediaTag(Base):
    """Media tag model for categorization."""
    __tablename__ = "media_tags"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=False)
    tag_name = Column(String(100), nullable=False, index=True)
    tag_value = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    media_file = relationship("MediaFile", back_populates="tags")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('media_file_id', 'tag_name', name='uq_media_tags_file_name'),
        Index('idx_media_tags_name_value', 'tag_name', 'tag_value'),
    )


class ProcessingJob(Base):
    """Processing job model for tracking media processing tasks."""
    __tablename__ = "processing_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    media_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id"), nullable=False)
    
    # Job information
    job_type = Column(String(50), nullable=False, index=True)  # thumbnail, metadata, transcode, etc.
    status = Column(String(20), nullable=False, default="pending", index=True)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, higher is more priority
    
    # Processing details
    input_parameters = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Resource usage
    cpu_time = Column(Float, nullable=True)  # CPU time in seconds
    memory_peak = Column(BigInteger, nullable=True)  # Peak memory usage in bytes
    
    # Relationships
    media_file = relationship("MediaFile", back_populates="processing_jobs")
    
    # Indexes
    __table_args__ = (
        Index('idx_processing_jobs_status_priority', 'status', 'priority'),
        Index('idx_processing_jobs_type_status', 'job_type', 'status'),
        Index('idx_processing_jobs_created_at', 'created_at'),
    )


class StorageUsage(Base):
    """Storage usage tracking model."""
    __tablename__ = "storage_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Usage metrics
    bucket_name = Column(String(100), nullable=False, index=True)
    storage_tier = Column(String(20), nullable=False, index=True)
    total_files = Column(BigInteger, nullable=False, default=0)
    total_size = Column(BigInteger, nullable=False, default=0)  # in bytes
    
    # Time period
    measurement_date = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Additional metrics
    avg_file_size = Column(BigInteger, nullable=True)
    largest_file_size = Column(BigInteger, nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('bucket_name', 'storage_tier', 'measurement_date', 
                        name='uq_storage_usage_bucket_tier_date'),
        Index('idx_storage_usage_date', 'measurement_date'),
    )


async def init_db():
    """Initialize database connection and create tables."""
    global engine, SessionLocal
    
    settings = get_settings()
    
    try:
        # Create async engine
        engine = create_async_engine(
            settings.database_url_async,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            echo=settings.DEBUG,
            future=True
        )
        
        # Create session factory
        SessionLocal = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_db():
    """Close database connections."""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_db_sync():
    """Get synchronous database session (for Alembic migrations)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    settings = get_settings()
    sync_engine = create_engine(settings.database_url_sync)
    SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()