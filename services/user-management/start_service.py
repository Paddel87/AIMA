#!/usr/bin/env python3
"""
Startup script for the AIMA User Management Service.

This script starts the User Management Service with proper configuration
and environment setup.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))


def setup_environment():
    """Setup environment variables and configuration."""
    # Set default environment if not specified
    if not os.getenv("ENVIRONMENT"):
        os.environ["ENVIRONMENT"] = "development"
    
    # Ensure required directories exist
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Set Python path
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))


def main():
    """Main entry point."""
    setup_environment()
    
    try:
        import uvicorn
        from app.main import app
        from app.core.config import get_settings
        
        settings = get_settings()
        
        print(f"Starting AIMA User Management Service...")
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Debug mode: {settings.DEBUG}")
        print(f"Host: {settings.HOST}")
        print(f"Port: {settings.PORT}")
        
        # Start the server
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG and settings.DEV_AUTO_RELOAD,
            log_level="info" if settings.DEBUG else "warning",
            access_log=settings.DEBUG,
            workers=1 if settings.DEBUG else settings.WORKERS
        )
        
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Please ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()