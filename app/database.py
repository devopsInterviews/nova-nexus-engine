import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import logging

# Import all models from the models module to ensure they are registered with SQLAlchemy
# This ensures that Base.metadata.create_all() will create all tables
from app.models import (
    Base, User, DatabaseConnection, TestConfiguration, UserActivity, 
    TestExecution, DatabaseSession, SystemMetrics, RequestLog, 
    McpServerStatus, PageView
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_url():
    """
    Constructs the database connection URL from environment variables.

    Returns:
        str: The full PostgreSQL connection string.
    """
    return f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"

engine = None
SessionLocal = None

def init_db():
    """
    Initializes the database connection, engine, and session.

    This function performs the following steps:
    1. Constructs the database URL.
    2. Creates the SQLAlchemy engine.
    3. Retries connecting to the database to ensure it's available.
    4. Creates all tables defined in the models (if they don't exist).
    5. Creates the sessionmaker `SessionLocal`.
    6. Ensures the default 'admin' user exists.

    This function is called once at application startup.
    """
    global engine, SessionLocal
    db_url = get_db_url()
    engine = create_engine(db_url)
    
    max_retries = 10
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            connection = engine.connect()
            connection.close()
            logger.info("Database connection successful.")
            break
        except OperationalError as e:
            logger.warning(f"Database connection failed. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            logger.error(f"Error: {e}")
            time.sleep(retry_delay)
    else:
        logger.error("Could not connect to the database after multiple retries. Exiting.")
        exit(1)

    # This is the line that creates the tables.
    # It checks for the existence of tables and creates any that are missing.
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create admin user if it doesn't exist
    session = SessionLocal()
    try:
        admin_user = session.query(User).filter_by(username='admin').first()
        if not admin_user:
            logger.info("Admin user not found, creating one.")
            admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
            admin_user = User(
                username='admin',
                email='admin@company.com',
                full_name='System Administrator',
                is_admin=True,
                is_active=True
            )
            admin_user.set_password(admin_password)
            session.add(admin_user)
            session.commit()
            logger.info("Admin user created.")
        else:
            # Update existing admin user to have admin privileges
            if not getattr(admin_user, 'is_admin', False):
                admin_user.is_admin = True
                session.commit()
                logger.info("Admin user updated with admin privileges.")
            logger.info("Admin user already exists.")
    finally:
        session.close()

def get_db_session():
    """
    FastAPI dependency to provide a database session to API endpoints.

    This function yields a new database session for each request and ensures
    it is closed afterward.

    Raises:
        Exception: If the database is not initialized.

    Yields:
        Session: The SQLAlchemy database session.
    """
    if SessionLocal is None:
        raise Exception("Database is not initialized. Call init_db() first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

