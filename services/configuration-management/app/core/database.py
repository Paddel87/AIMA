#!/usr/bin/env python3
"""
Database configuration and session management for the AIMA Configuration Management Service.

This module handles database connections, session management, and provides
utilities for database operations.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)

# Synchronous database engine and session
engine = create_engine(
    settings.database_url_sync,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Asynchronous database engine and session
async_engine = create_async_engine(
    settings.database_url_async,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance (if using SQLite)."""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=1000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


def get_db() -> Session:
    """Get synchronous database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session as context manager."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database context error: {e}")
            await session.rollback()
            raise


def create_tables():
    """Create all database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def drop_tables():
    """Drop all database tables."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


async def create_tables_async():
    """Create all database tables asynchronously."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully (async)")
    except Exception as e:
        logger.error(f"Error creating database tables (async): {e}")
        raise


async def drop_tables_async():
    """Drop all database tables asynchronously."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully (async)")
    except Exception as e:
        logger.error(f"Error dropping database tables (async): {e}")
        raise


def check_database_connection() -> bool:
    """Check if database connection is working."""
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def check_database_connection_async() -> bool:
    """Check if async database connection is working."""
    try:
        async with async_engine.connect() as connection:
            await connection.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Async database connection check failed: {e}")
        return False


def get_database_info() -> dict:
    """Get database information."""
    try:
        with engine.connect() as connection:
            result = connection.execute("SELECT version()")
            version = result.scalar()
            
        return {
            "url": settings.DATABASE_URL,
            "version": version,
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "status": "connected"
        }
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return {
            "url": settings.DATABASE_URL,
            "status": "error",
            "error": str(e)
        }


class DatabaseManager:
    """Database manager for handling database operations."""
    
    def __init__(self):
        self.engine = engine
        self.async_engine = async_engine
        self.SessionLocal = SessionLocal
        self.AsyncSessionLocal = AsyncSessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a new async database session as context manager."""
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Async database session error: {e}")
                await session.rollback()
                raise
    
    def health_check(self) -> bool:
        """Perform database health check."""
        return check_database_connection()
    
    async def async_health_check(self) -> bool:
        """Perform async database health check."""
        return await check_database_connection_async()
    
    def initialize(self):
        """Initialize database (create tables)."""
        create_tables()
    
    async def initialize_async(self):
        """Initialize database asynchronously (create tables)."""
        await create_tables_async()
    
    def cleanup(self):
        """Cleanup database connections."""
        try:
            self.engine.dispose()
            logger.info("Database connections cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up database connections: {e}")
    
    async def cleanup_async(self):
        """Cleanup async database connections."""
        try:
            await self.async_engine.dispose()
            logger.info("Async database connections cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up async database connections: {e}")
    
    async def close(self):
        """Close database connections."""
        await self.cleanup_async()


# Global database manager instance
db_manager = DatabaseManager()