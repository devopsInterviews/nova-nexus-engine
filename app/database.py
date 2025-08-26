"""
Database configuration and session management for MCP Client.

This module handles database connection, session management, and provides
utilities for database operations including initialization and migrations.
"""

import os
import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import asyncio
from cryptography.fernet import Fernet
import base64
from datetime import datetime, timedelta

logger = logging.getLogger("uvicorn.error")

# Database configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
DATABASE_NAME = os.getenv("DATABASE_NAME", "mcp_client")
DATABASE_USER = os.getenv("DATABASE_USER", "mcp_user")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "your_password_here")

# Encryption key for sensitive data (should be set via environment in production)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

# Build database URL if not provided
if not DATABASE_URL:
    DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

logger.info(f"Database configuration: {DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}")

# Create database engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections after 5 minutes
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true"  # Enable SQL logging if needed
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Encryption utilities
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_password(password: str) -> str:
    """Encrypt a password for database storage."""
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """Decrypt a password from database storage."""
    return fernet.decrypt(encrypted_password.encode()).decode()

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI.
    
    Provides a database session that is automatically closed after use.
    Use this in FastAPI route dependencies.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    
    Use this for manual database operations outside of FastAPI.
    
    Example:
        with get_db_session() as db:
            user = db.query(User).filter(User.username == "admin").first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def init_database():
    """
    Initialize the database with tables and default data.
    
    Creates all tables defined in models and sets up initial admin user.
    This should be called during application startup.
    """
    from app.models import Base, User
    from app.auth import get_password_hash
    
    try:
        logger.info("Initializing database...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create default admin user if it doesn't exist
        with get_db_session() as db:
            admin_user = db.query(User).filter(User.username == "admin").first()
            if not admin_user:
                logger.info("Creating default admin user...")
                admin_user = User(
                    username="admin",
                    email="admin@nova-nexus.local",
                    hashed_password=get_password_hash("admin"),  # Default password, should be changed
                    full_name="System Administrator",
                    is_admin=True,
                    is_active=True,
                    preferences={
                        "theme": "dark",
                        "notifications": True,
                        "default_page": "/dashboard"
                    }
                )
                db.add(admin_user)
                db.commit()
                logger.info("Default admin user created successfully (username: admin, password: admin)")
            else:
                logger.info("Admin user already exists")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("Database connection check successful")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False

def get_database_info() -> dict:
    """
    Get database connection information for health checks.
    
    Returns:
        dict: Database connection information
    """
    try:
        with engine.connect() as connection:
            result = connection.execute("SELECT version()")
            version = result.fetchone()[0] if result else "Unknown"
            
        return {
            "status": "connected",
            "url": DATABASE_URL.replace(DATABASE_PASSWORD, "***") if DATABASE_PASSWORD in DATABASE_URL else DATABASE_URL,
            "database": DATABASE_NAME,
            "version": version
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "url": DATABASE_URL.replace(DATABASE_PASSWORD, "***") if DATABASE_PASSWORD in DATABASE_URL else DATABASE_URL,
            "database": DATABASE_NAME
        }

async def cleanup_expired_sessions():
    """
    Cleanup expired database sessions and old activity logs.
    
    This should be run periodically to maintain database performance.
    """
    from app.models import DatabaseSession, UserActivity
    from datetime import datetime, timedelta
    
    try:
        with get_db_session() as db:
            # Clean up expired sessions (older than 24 hours)
            expired_threshold = datetime.utcnow() - timedelta(hours=24)
            expired_sessions = db.query(DatabaseSession).filter(
                DatabaseSession.last_activity < expired_threshold,
                DatabaseSession.status != 'terminated'
            ).update({"status": "terminated", "ended_at": datetime.utcnow()})
            
            # Clean up old activity logs (older than 90 days)
            old_activity_threshold = datetime.utcnow() - timedelta(days=90)
            old_activities = db.query(UserActivity).filter(
                UserActivity.timestamp < old_activity_threshold
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleaned up {expired_sessions} expired sessions and {old_activities} old activity logs")
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {str(e)}")

# Database health check endpoint data
def get_db_health() -> dict:
    """Get database health status for monitoring."""
    try:
        info = get_database_info()
        return {
            "database": {
                "status": info["status"],
                "connection_pool": {
                    "size": engine.pool.size(),
                    "checked_in": engine.pool.checkedin(),
                    "checked_out": engine.pool.checkedout(),
                },
                "version": info.get("version", "Unknown")
            }
        }
    except Exception as e:
        return {
            "database": {
                "status": "error",
                "error": str(e)
            }
        }


def create_admin_user() -> Optional[dict]:
    """
    Create default admin user if it doesn't exist.
    
    This function is called during application startup to ensure
    there's always an admin user available for initial access.
    
    Returns:
        dict: Admin user information if created, None if already exists
    """
    try:
        from app.models import User
        from app.auth import get_password_hash, log_user_activity
        
        with get_db_session() as db:
            # Check if any admin user exists
            existing_admin = db.query(User).filter(User.is_admin == True).first()
            
            if existing_admin:
                logger.info(f"Admin user already exists: {existing_admin.username}")
                return None
            
            # Create default admin user
            admin_username = os.getenv("ADMIN_USERNAME", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            admin_email = os.getenv("ADMIN_EMAIL", "admin@mcp-client.local")
            
            hashed_password = get_password_hash(admin_password)
            
            admin_user = User(
                username=admin_username,
                email=admin_email,
                full_name="System Administrator",
                hashed_password=hashed_password,
                is_active=True,
                is_admin=True,
                created_at=datetime.utcnow(),
                login_count=0,
                preferences={
                    "theme": "dark",
                    "notifications": True,
                    "auto_created": True
                }
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            # Log the admin creation activity
            try:
                log_user_activity(
                    db=db,
                    user_id=admin_user.id,
                    activity_type="system",
                    action="Admin user created automatically",
                    status="success",
                    metadata={
                        "auto_created": True,
                        "username": admin_username,
                        "startup": True
                    }
                )
                db.commit()
            except Exception as log_error:
                logger.warning(f"Failed to log admin creation activity: {str(log_error)}")
            
            logger.info(f"Default admin user created: {admin_username}")
            logger.warning("SECURITY: Default admin credentials are being used. Please change them immediately!")
            logger.warning(f"Admin Username: {admin_username}")
            logger.warning(f"Admin Password: {admin_password}")
            
            return {
                "username": admin_username,
                "email": admin_email,
                "message": "Default admin user created. Please change credentials immediately!",
                "security_warning": True
            }
            
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")
        return None


def initialize_database():
    """
    Initialize database with required tables and default data.
    
    This function should be called during application startup to ensure
    the database is properly set up with all required tables and initial data.
    """
    try:
        from app.models import Base
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create default admin user
        logger.info("Checking for admin user...")
        admin_result = create_admin_user()
        
        if admin_result:
            logger.info("Database initialization completed with new admin user")
        else:
            logger.info("Database initialization completed (admin user already exists)")
            
        # Run cleanup of old data
        cleanup_expired_sessions()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise
