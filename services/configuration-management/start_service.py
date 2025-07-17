#!/usr/bin/env python3
"""
Startup script for the AIMA Configuration Management Service.

This script handles service initialization, environment setup,
and graceful startup of the configuration management service.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

import uvicorn
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from core.config import get_settings
from core.database import DatabaseManager
from core.redis import RedisManager
from models.database import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
settings = get_settings()


class ServiceManager:
    """Manages the lifecycle of the configuration management service."""
    
    def __init__(self):
        self.db_manager = None
        self.redis_manager = None
        self.server = None
        self.shutdown_event = asyncio.Event()
    
    async def wait_for_database(self, max_retries: int = 30, retry_interval: int = 2):
        """Wait for database to become available."""
        logger.info("Waiting for database connection...")
        
        for attempt in range(max_retries):
            try:
                engine = create_engine(settings.DATABASE_URL)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Database connection successful")
                engine.dispose()
                return True
                
            except OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    await asyncio.sleep(retry_interval)
                else:
                    logger.error(f"Failed to connect to database after {max_retries} attempts")
                    return False
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                return False
        
        return False
    
    async def wait_for_redis(self, max_retries: int = 10, retry_interval: int = 2):
        """Wait for Redis to become available (optional)."""
        if not settings.REDIS_URL:
            logger.info("Redis not configured, skipping Redis check")
            return True
        
        logger.info("Waiting for Redis connection...")
        
        for attempt in range(max_retries):
            try:
                redis_manager = RedisManager()
                await redis_manager.initialize()
                
                if redis_manager.is_connected():
                    logger.info("Redis connection successful")
                    await redis_manager.close()
                    return True
                else:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Redis connection attempt {attempt + 1}/{max_retries} failed"
                        )
                        await asyncio.sleep(retry_interval)
                    else:
                        logger.warning(
                            f"Redis not available after {max_retries} attempts, "
                            "continuing without cache"
                        )
                        return True
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    await asyncio.sleep(retry_interval)
                else:
                    logger.warning(
                        f"Redis connection failed after {max_retries} attempts: {e}, "
                        "continuing without cache"
                    )
                    return True
        
        return True  # Redis is optional
    
    async def initialize_database(self):
        """Initialize database schema and default data."""
        logger.info("Initializing database schema...")
        
        try:
            self.db_manager = DatabaseManager()
            self.db_manager.initialize()
            
            # Run post-initialization script
            await self.run_post_init_script()
            
            # Insert default configurations if needed
            await self.insert_default_configurations()
            
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    async def run_post_init_script(self):
        """Run post-initialization SQL script to create views and indexes."""
        logger.info("Running post-initialization script...")
        
        try:
            import os
            import asyncpg
            
            # Path to post-init script
            script_path = os.path.join(
                os.path.dirname(__file__), 
                "init-scripts", 
                "02-post-init.sql"
            )
            
            if not os.path.exists(script_path):
                logger.warning(f"Post-init script not found: {script_path}")
                return
            
            # Read the script
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Execute the script
            async with self.db_manager.get_async_session() as session:
                # Get the raw connection
                connection = await session.connection()
                raw_connection = await connection.get_raw_connection()
                
                # Execute the script
                await raw_connection.driver_connection.execute(script_content)
                await session.commit()
            
            logger.info("Post-initialization script executed successfully")
            
        except Exception as e:
            logger.warning(f"Post-initialization script failed: {e}")
            # Don't fail the startup for this
    
    async def insert_default_configurations(self):
        """Insert default system configurations."""
        logger.info("Checking for default configurations...")
        
        try:
            from app.services.config_service import ConfigurationService
            from app.models.schemas import ConfigurationItemCreate, ConfigCategory, ConfigDataType
            
            # Get a database session
            async with self.db_manager.get_async_session() as session:
                # Initialize cache (optional)
                from app.core.redis import ConfigurationCache
                cache = ConfigurationCache()
                config_service = ConfigurationService(cache)
                
                # Default configurations
                default_configs = [
                    {
                        "key": "system.service_name",
                        "value": "AIMA Configuration Management",
                        "data_type": ConfigDataType.STRING,
                        "category": ConfigCategory.SYSTEM,
                        "description": "Name of the configuration management service",
                        "is_readonly": True,
                        "created_by": "system"
                    },
                    {
                        "key": "system.version",
                        "value": settings.APP_VERSION,
                        "data_type": ConfigDataType.STRING,
                        "category": ConfigCategory.SYSTEM,
                        "description": "Current service version",
                        "is_readonly": True,
                        "created_by": "system"
                    },
                    {
                        "key": "cache.default_ttl",
                        "value": "3600",
                        "data_type": ConfigDataType.INTEGER,
                        "category": ConfigCategory.PERFORMANCE,
                        "description": "Default cache TTL in seconds",
                        "is_readonly": False,
                        "created_by": "system"
                    },
                    {
                        "key": "api.rate_limit_requests",
                        "value": "100",
                        "data_type": ConfigDataType.INTEGER,
                        "category": ConfigCategory.SECURITY,
                        "description": "API rate limit requests per minute",
                        "is_readonly": False,
                        "created_by": "system"
                    },
                    {
                        "key": "logging.level",
                        "value": settings.LOG_LEVEL,
                        "data_type": ConfigDataType.STRING,
                        "category": ConfigCategory.SYSTEM,
                        "description": "Default logging level",
                        "is_readonly": False,
                        "created_by": "system"
                    }
                ]
                
                # Insert configurations that don't exist
                for config_data in default_configs:
                    existing = await config_service.get_configuration(
                        session, config_data["key"]
                    )
                    
                    if not existing:
                        config_create = ConfigurationItemCreate(**config_data)
                        await config_service.create_configuration(session, config_create)
                        logger.info(f"Created default configuration: {config_data['key']}")
                
                logger.info("Default configurations check completed")
                
        except Exception as e:
            logger.warning(f"Failed to insert default configurations: {e}")
    
    async def start_server(self):
        """Start the FastAPI server."""
        logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
        
        config = uvicorn.Config(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=True,
            reload=settings.ENVIRONMENT == "development"
        )
        
        self.server = uvicorn.Server(config)
        
        try:
            await self.server.serve()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
    
    async def shutdown(self):
        """Gracefully shutdown the service."""
        logger.info("Initiating graceful shutdown...")
        
        # Stop the server
        if self.server:
            self.server.should_exit = True
            logger.info("Server shutdown initiated")
        
        # Close database connections
        if self.db_manager:
            await self.db_manager.close()
            logger.info("Database connections closed")
        
        # Close Redis connections
        if self.redis_manager:
            await self.redis_manager.close()
            logger.info("Redis connections closed")
        
        logger.info("Graceful shutdown completed")
    
    async def run(self):
        """Run the complete service startup sequence."""
        try:
            logger.info("Starting AIMA Configuration Management Service...")
            
            # Wait for dependencies
            if not await self.wait_for_database():
                logger.error("Database is not available, cannot start service")
                return False
            
            await self.wait_for_redis()
            
            # Initialize database
            if not await self.initialize_database():
                logger.error("Database initialization failed, cannot start service")
                return False
            
            # Start the server
            await self.start_server()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Service startup failed: {e}")
            return False
        finally:
            await self.shutdown()


def setup_signal_handlers(service_manager: ServiceManager):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(service_manager.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Add file handler for logging
    file_handler = logging.FileHandler(logs_dir / "config_service.log")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
    
    # Create and run service manager
    service_manager = ServiceManager()
    setup_signal_handlers(service_manager)
    
    success = await service_manager.run()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())