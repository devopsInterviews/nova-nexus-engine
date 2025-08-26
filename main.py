"""
MCP Client - Main Application Entry Point

This module configures and starts the FastAPI application server with comprehensive
logging configuration for development and production environments.

Features:
- Environment-based configuration
- Comprehensive logging setup with structured formatting
- Application health monitoring
- Development vs production configurations

Environment Variables:
- CLIENT_HOST: Server host address (default: 0.0.0.0)
- CLIENT_PORT: Server port number (default: 8000)
- LOG_LEVEL: Logging level (default: INFO)
- ENV: Environment type (development/production)

Usage:
    python main.py

Production Deployment:
    gunicorn -k uvicorn.workers.UvicornWorker main:app --workers 4
"""

import logging
import logging.config
import os
import sys
from datetime import datetime

import uvicorn
from dotenv import load_dotenv

from app.client import app

# Load environment variables
load_dotenv()

# Configuration
CLIENT_HOST = os.getenv("CLIENT_HOST", "0.0.0.0")
CLIENT_PORT = int(os.getenv("CLIENT_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENV = os.getenv("ENV", "development").lower()

def setup_logging():
    """
    Configure comprehensive logging for the MCP Client application
    
    Sets up structured logging with:
    - Console and file output
    - Timestamp and level formatting
    - Separate loggers for different components
    - Environment-appropriate log levels
    """
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Define log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": log_format,
                "datefmt": date_format
            },
            "simple": {
                "format": "%(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": "detailed",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": f"{log_dir}/mcp_client.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": f"{log_dir}/mcp_client_errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 3
            }
        },
        "loggers": {
            "": {  # Root logger
                "level": LOG_LEVEL,
                "handlers": ["console", "file"]
            },
            "app": {  # Application logger
                "level": "DEBUG" if ENV == "development" else "INFO",
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["file"],
                "propagate": False
            }
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Get application logger
    logger = logging.getLogger("app")
    logger.info("=" * 80)
    logger.info("MCP Client - Application Starting")
    logger.info("=" * 80)
    logger.info(f"Environment: {ENV}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Host: {CLIENT_HOST}")
    logger.info(f"Port: {CLIENT_PORT}")
    logger.info(f"Logs Directory: {os.path.abspath(log_dir)}")
    logger.info(f"Startup Time: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    return logger

if __name__ == "__main__":
    """
    Main application entry point
    
    Configures logging and starts the FastAPI server with appropriate settings
    for the current environment.
    """
    
    # Setup comprehensive logging
    logger = setup_logging()
    
    try:
        logger.info("Initializing MCP Client FastAPI application")
        
        # Server configuration
        server_config = {
            "app": "app.client:app",
            "host": CLIENT_HOST,
            "port": CLIENT_PORT,
            "reload": ENV == "development",
            "log_config": None,  # Use our custom logging config
            "log_level": LOG_LEVEL.lower()
        }
        
        logger.info(f"Starting server with configuration: {server_config}")
        logger.info("Server will be available at http://%s:%s", CLIENT_HOST, CLIENT_PORT)
        logger.info("API documentation available at http://%s:%s/docs", CLIENT_HOST, CLIENT_PORT)
        
        # Start the server
        # Note: In production, replace with:
        # gunicorn -k uvicorn.workers.UvicornWorker main:app --workers 4
        uvicorn.run(**server_config)
        
    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error("Failed to start MCP Client: %s", str(e), exc_info=True)
        sys.exit(1)
    finally:
        logger.info("MCP Client shutdown complete")
        logging.shutdown()
