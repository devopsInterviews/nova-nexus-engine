import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import logging

# Import all models from the models module to ensure they are registered with SQLAlchemy.
# Every model must be imported here so that Base.metadata.create_all() creates all tables
# — including the SSO-related tables (SSOGroup, UserSession, user_group_association).
from app.models import (
    Base, User, DatabaseConnection, TestConfiguration, UserActivity,
    TestExecution, DatabaseSession, SystemMetrics, RequestLog,
    McpServerStatus, PageView, IdaMcpConnection, IdaMcpDeployAudit,
    SSOGroup, UserSession, user_group_association, TabPermission,
    MarketplaceItem, MarketplaceUsage,
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

    # Inline schema migrations — add columns that were introduced after initial deployment.
    # SQLAlchemy create_all does not ALTER existing tables, so we handle it manually here.
    _run_schema_migrations(engine)
    
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

def _run_schema_migrations(engine) -> None:
    """
    Apply incremental DDL changes to existing databases.

    Each migration is idempotent: it checks for the column/index before
    running ALTER TABLE so repeated restarts are safe.
    """
    migrations = [
        # v1.x → tool_name column for granular MCP tool tracking via /api/marketplace/ping
        (
            "marketplace_usage",
            "tool_name",
            "ALTER TABLE marketplace_usage ADD COLUMN tool_name VARCHAR(255)",
        ),
        # v2.x → is_admin flag on SSO groups for group-level admin role grants
        (
            "sso_groups",
            "is_admin",
            "ALTER TABLE sso_groups ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE",
        ),
        # v3.x → last_error stores the infra API error message when a deploy fails,
        #         so status can be set to ERROR instead of silently reverting to BUILT.
        (
            "marketplace_items",
            "last_error",
            "ALTER TABLE marketplace_items ADD COLUMN last_error TEXT",
        ),
    ]

    with engine.connect() as conn:
        for table, column, ddl in migrations:
            try:
                # Check column existence via information_schema (works on PostgreSQL & SQLite)
                result = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c"
                    ),
                    {"t": table, "c": column},
                )
                if result.fetchone() is None:
                    conn.execute(text(ddl))
                    conn.commit()
                    logger.info("Schema migration applied: ADD COLUMN %s.%s", table, column)
            except Exception as exc:
                logger.warning("Schema migration skipped (%s.%s): %s", table, column, exc)


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

