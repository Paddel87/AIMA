#!/usr/bin/env python3
"""
Database configuration and session management for the AIMA GPU Orchestration Service.

This module provides SQLAlchemy configuration, async session management,
and database initialization utilities.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .config import get_settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Global variables for database engine and session factory
engine = None
SessionLocal = None


def get_database_url() -> str:
    """Get the database URL from settings."""
    settings = get_settings()
    return settings.DATABASE_URL


def create_database_engine():
    """Create and configure the database engine."""
    global engine
    
    if engine is not None:
        return engine
    
    database_url = get_database_url()
    
    # Configure engine with async support
    engine = create_async_engine(
        database_url,
        echo=get_settings().DEBUG,  # Log SQL queries in debug mode
        pool_size=get_settings().DATABASE_POOL_SIZE,
        max_overflow=get_settings().DATABASE_MAX_OVERFLOW,
        pool_timeout=30,
        pool_recycle=3600,  # Recycle connections after 1 hour
        poolclass=NullPool if "sqlite" in database_url else None,
        future=True
    )
    
    logger.info(f"Database engine created for: {database_url.split('@')[1] if '@' in database_url else 'local'}")
    return engine


def create_session_factory():
    """Create the session factory."""
    global SessionLocal
    
    if SessionLocal is not None:
        return SessionLocal
    
    engine = create_database_engine()
    
    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False
    )
    
    logger.info("Database session factory created")
    return SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    session_factory = create_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_database():
    """Initialize the database by creating all tables."""
    try:
        engine = create_database_engine()
        
        # Import all models to ensure they are registered
        from ..models.gpu_models import (
            GPUInstance,
            GPUJob,
            ProviderConfig,
            JobTemplate,
            ResourceQuota
        )
        
        logger.info("Creating database tables...")
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
        # Initialize default data
        await init_default_data()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def init_default_data():
    """Initialize default data in the database."""
    try:
        session_factory = create_session_factory()
        
        async with session_factory() as session:
            # Import models
            from ..models.gpu_models import (
                ProviderConfig,
                JobTemplate,
                ResourceQuota,
                GPUProvider,
                JobType
            )
            
            # Check if default data already exists
            existing_providers = await session.execute(
                "SELECT COUNT(*) FROM provider_configs"
            )
            if existing_providers.scalar() > 0:
                logger.info("Default data already exists, skipping initialization")
                return
            
            logger.info("Initializing default data...")
            
            # Create default provider configurations
            settings = get_settings()
            
            # RunPod provider config
            if settings.RUNPOD_API_KEY:
                runpod_config = ProviderConfig(
                    provider=GPUProvider.RUNPOD,
                    name="RunPod Default",
                    api_key=settings.RUNPOD_API_KEY,
                    api_url=settings.RUNPOD_API_URL,
                    enabled=True,
                    priority=1,
                    config={
                        "default_region": "US-OR-1",
                        "max_instances": 10,
                        "timeout_minutes": 60
                    }
                )
                session.add(runpod_config)
            
            # Vast.ai provider config
            if settings.VAST_API_KEY:
                vast_config = ProviderConfig(
                    provider=GPUProvider.VAST,
                    name="Vast.ai Default",
                    api_key=settings.VAST_API_KEY,
                    api_url=settings.VAST_API_URL,
                    enabled=True,
                    priority=2,
                    config={
                        "default_region": "US",
                        "max_instances": 5,
                        "timeout_minutes": 45
                    }
                )
                session.add(vast_config)
            
            # AWS provider config
            if settings.AWS_ACCESS_KEY_ID:
                aws_config = ProviderConfig(
                    provider=GPUProvider.AWS,
                    name="AWS Default",
                    api_key=settings.AWS_ACCESS_KEY_ID,
                    api_secret=settings.AWS_SECRET_ACCESS_KEY,
                    api_url="https://ec2.amazonaws.com",
                    enabled=True,
                    priority=3,
                    config={
                        "default_region": "us-west-2",
                        "max_instances": 3,
                        "timeout_minutes": 30
                    }
                )
                session.add(aws_config)
            
            # Create default job templates
            
            # LLaVA-1.6 34B template
            llava_template = JobTemplate(
                name="LLaVA-1.6 34B Analysis",
                job_type=JobType.LLAVA,
                description="Multimodal analysis using LLaVA-1.6 34B model",
                config={
                    "model_name": "llava-v1.6-34b",
                    "gpu_type": "RTX4090",
                    "gpu_count": 4,
                    "memory_gb": 96,
                    "docker_image": "aima/llava:1.6-34b",
                    "timeout_minutes": 120,
                    "max_batch_size": 8
                },
                resource_requirements={
                    "gpu_memory_gb": 24,
                    "system_memory_gb": 32,
                    "storage_gb": 100,
                    "cpu_cores": 8
                },
                is_public=True
            )
            session.add(llava_template)
            
            # Llama 3.1 70B template
            llama_template = JobTemplate(
                name="Llama 3.1 70B Text Generation",
                job_type=JobType.LLAMA,
                description="Text generation using Llama 3.1 70B model",
                config={
                    "model_name": "llama-3.1-70b",
                    "gpu_type": "RTX4090",
                    "gpu_count": 2,
                    "memory_gb": 48,
                    "docker_image": "aima/llama:3.1-70b",
                    "timeout_minutes": 90,
                    "max_sequence_length": 4096
                },
                resource_requirements={
                    "gpu_memory_gb": 24,
                    "system_memory_gb": 64,
                    "storage_gb": 50,
                    "cpu_cores": 16
                },
                is_public=True
            )
            session.add(llama_template)
            
            # Training template
            training_template = JobTemplate(
                name="Model Training",
                job_type=JobType.TRAINING,
                description="General model training template",
                config={
                    "gpu_type": "RTX4090",
                    "gpu_count": 1,
                    "memory_gb": 24,
                    "docker_image": "aima/training:latest",
                    "timeout_minutes": 480,
                    "checkpoint_interval": 100
                },
                resource_requirements={
                    "gpu_memory_gb": 24,
                    "system_memory_gb": 32,
                    "storage_gb": 200,
                    "cpu_cores": 8
                },
                is_public=True
            )
            session.add(training_template)
            
            # Batch processing template
            batch_template = JobTemplate(
                name="Batch Processing",
                job_type=JobType.BATCH_PROCESSING,
                description="High-throughput batch processing template",
                config={
                    "gpu_type": "RTX4090",
                    "gpu_count": 1,
                    "memory_gb": 24,
                    "docker_image": "aima/batch:latest",
                    "timeout_minutes": 240,
                    "batch_size": 32
                },
                resource_requirements={
                    "gpu_memory_gb": 24,
                    "system_memory_gb": 16,
                    "storage_gb": 100,
                    "cpu_cores": 4
                },
                is_public=True
            )
            session.add(batch_template)
            
            # Create default resource quotas
            default_quota = ResourceQuota(
                user_id="default",
                max_concurrent_jobs=5,
                max_gpu_hours_per_day=24,
                max_cost_per_day_usd=100.0,
                max_instances_per_provider=3,
                allowed_gpu_types=["RTX4090", "RTX3090", "A100"],
                allowed_providers=[GPUProvider.RUNPOD, GPUProvider.VAST],
                priority_boost=0
            )
            session.add(default_quota)
            
            # Admin quota
            admin_quota = ResourceQuota(
                user_id="admin",
                max_concurrent_jobs=20,
                max_gpu_hours_per_day=100,
                max_cost_per_day_usd=500.0,
                max_instances_per_provider=10,
                allowed_gpu_types=["RTX4090", "RTX3090", "A100", "H100"],
                allowed_providers=[GPUProvider.RUNPOD, GPUProvider.VAST, GPUProvider.AWS],
                priority_boost=10
            )
            session.add(admin_quota)
            
            await session.commit()
            logger.info("Default data initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize default data: {e}")
        raise


async def close_database():
    """Close database connections."""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")


# Event listeners for connection management
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance."""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries in debug mode."""
    if get_settings().DEBUG:
        context._query_start_time = logger.info(f"Executing query: {statement[:100]}...")


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time in debug mode."""
    if get_settings().DEBUG and hasattr(context, '_query_start_time'):
        total = logger.info(f"Query completed in {total:.3f}s")