
import os
import time
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(128))
    creation_date = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime)
    login_count = Column(Integer, default=0)
    db_connections = relationship("DBConnection", back_populates="user", cascade="all, delete-orphan")
    tests = relationship("Test", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class DBConnection(Base):
    __tablename__ = 'db_connections'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    connection_name = Column(String(100), nullable=False)
    db_type = Column(String(50), nullable=False)
    db_host = Column(String(100), nullable=False)
    db_port = Column(Integer, nullable=False)
    db_user = Column(String(100), nullable=False)
    db_password = Column(String(100), nullable=False)
    db_name = Column(String(100), nullable=False)
    user = relationship("User", back_populates="db_connections")

class Test(Base):
    __tablename__ = 'tests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_name = Column(String(100), nullable=False)
    test_data = Column(Text, nullable=False)
    creation_date = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="tests")


def get_db_url():
    return f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"

engine = None
SessionLocal = None

def init_db():
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

    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create admin user if it doesn't exist
    session = SessionLocal()
    try:
        admin_user = session.query(User).filter_by(username='admin').first()
        if not admin_user:
            logger.info("Admin user not found, creating one.")
            admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
            admin_user = User(username='admin')
            admin_user.set_password(admin_password)
            session.add(admin_user)
            session.commit()
            logger.info("Admin user created.")
        else:
            logger.info("Admin user already exists.")
    finally:
        session.close()

def get_db_session():
    if SessionLocal is None:
        raise Exception("Database is not initialized. Call init_db() first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

