#!/usr/bin/env python3
"""
Startup script for the AIMA GPU Orchestration Service.

This script initializes and starts the GPU orchestration service,
including database setup, provider initialization, and FastAPI server.
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.main import app
from app.core.config import get_settings
from app.core.database import init_database, close_database


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("gpu_orchestration.log")
    ]
)

logger = logging.getLogger(__name__)


async def startup():
    """Initialize the service on startup."""
    try:
        logger.info("Starting AIMA GPU Orchestration Service...")
        
        # Get settings
        settings = get_settings()
        logger.info(f"Service configuration loaded (Debug: {settings.DEBUG})")
        
        # Initialize database
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialized successfully")
        
        logger.info("GPU Orchestration Service startup completed")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise


async def shutdown():
    """Clean up resources on shutdown."""
    try:
        logger.info("Shutting down AIMA GPU Orchestration Service...")
        
        # Close database connections
        await close_database()
        
        logger.info("Service shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    asyncio.create_task(shutdown())
    sys.exit(0)


async def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize service
        await startup()
        
        # Import uvicorn here to avoid import issues
        import uvicorn
        
        # Get settings
        settings = get_settings()
        
        # Start the server
        logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
        
        config = uvicorn.Config(
            app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level=settings.LOG_LEVEL.lower(),
            reload=settings.DEBUG,
            workers=1 if settings.DEBUG else 4,
            access_log=True,
            use_colors=True
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Service error: {e}")
        raise
    finally:
        await shutdown()


if __name__ == "__main__":
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            logger.error("Python 3.8 or higher is required")
            sys.exit(1)
        
        # Run the service
        asyncio.run(main())
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        sys.exit(1)