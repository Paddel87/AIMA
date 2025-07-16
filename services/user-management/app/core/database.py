#!/usr/bin/env python3
"""
Database connection and session management for the AIMA User Management Service.

This module handles PostgreSQL database connections using SQLAlchemy async engine.
"""

import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Database engine and session maker
engine = None
SessionLocal = None

# Base class for all database models
Base = declarative_base()


class User(Base):
    """User model representing users in the system."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(255))
    last_name = Column(String(255))
    role = Column(String(50), nullable=False, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserSession(Base):
    """User session model for tracking active sessions."""
    
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(INET)
    user_agent = Column(Text)
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


class AuditLog(Base):
    """Audit log model for tracking user actions."""
    
    __tablename__ = "audit_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(255))
    ip_address = Column(INET)
    user_agent = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', timestamp={self.timestamp})>"


async def init_db() -> None:
    """Initialize database connection."""
    global engine, SessionLocal
    
    settings = get_settings()
    
    try:
        # Convert sync URL to async URL
        database_url = settings.DATABASE_URL
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not database_url.startswith("postgresql+asyncpg://"):
            database_url = f"postgresql+asyncpg://{database_url}"
        
        # Create async engine
        engine = create_async_engine(
            database_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            echo=settings.DATABASE_ECHO,
            future=True
        )
        
        # Create session maker
        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info(
            "Database connection initialized",
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW
        )
        
    except Exception as e:
        logger.error("Failed to initialize database connection", error=str(e))
        raise


async def close_db() -> None:
    """Close database connection."""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def health_check() -> bool:
    """Check database health."""
    try:
        if not engine:
            return False
        
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False