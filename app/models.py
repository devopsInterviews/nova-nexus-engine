"""
Database models for MCP Client authentication and user management.

This module defines SQLAlchemy models for user authentication, user management,
database connections, test configurations, and user activity tracking.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any, Optional, List
import json

Base = declarative_base()


class User(Base):
    """
    User model for authentication and user management.
    
    Stores user credentials, profile information, and access control data.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # User status and permissions
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Activity tracking
    login_count = Column(Integer, default=0, nullable=False)
    
    # Profile settings (stored as JSON)
    preferences = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    database_connections = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    test_configurations = relationship("TestConfiguration", back_populates="user", cascade="all, delete-orphan")
    test_executions = relationship("TestExecution", back_populates="user", cascade="all, delete-orphan")
    user_activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for API responses (excluding sensitive data)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "login_count": self.login_count,
            "preferences": self.preferences
        }


class DatabaseConnection(Base):
    """
    Database connection configurations for each user.
    
    Stores user-specific database connection profiles with encrypted credentials.
    """
    __tablename__ = "database_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Connection details
    name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)  # Encrypted password
    database_type = Column(String(50), nullable=False)  # postgres, mysql, etc.
    
    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list, nullable=False)  # For categorization
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="database_connections")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_connection_name', 'user_id', 'name'),
        Index('idx_user_active_connections', 'user_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<DatabaseConnection(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """Convert connection to dictionary for API responses."""
        data = {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "database_type": self.database_type,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active
        }
        
        if include_password:
            # In practice, this would decrypt the password
            data["password"] = "***ENCRYPTED***"
            
        return data


class TestConfiguration(Base):
    """
    User test configurations and saved tests.
    
    Replaces the current localStorage-based test saving with database persistence.
    """
    __tablename__ = "test_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Test metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    test_type = Column(String(50), nullable=False)  # 'mcp-server', 'mcp-client', etc.
    
    # Test configuration (stored as JSON)
    configuration = Column(JSON, nullable=False)
    
    # Test results and status
    last_result = Column(JSON, nullable=True)
    last_execution = Column(DateTime(timezone=True), nullable=True)
    execution_count = Column(Integer, default=0, nullable=False)
    
    # Categorization
    tags = Column(JSON, default=list, nullable=False)
    category = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)  # For sharing tests
    
    # Relationships
    user = relationship("User", back_populates="test_configurations")
    executions = relationship("TestExecution", back_populates="test_config", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_test_name', 'user_id', 'name'),
        Index('idx_user_test_type', 'user_id', 'test_type'),
        Index('idx_user_active_tests', 'user_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<TestConfiguration(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test configuration to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type,
            "configuration": self.configuration,
            "last_result": self.last_result,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "execution_count": self.execution_count,
            "tags": self.tags,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "is_public": self.is_public
        }


class UserActivity(Base):
    """
    User activity tracking for audit and analytics.
    
    Tracks user actions, login history, and system usage for admin monitoring.
    """
    __tablename__ = "user_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Activity details
    activity_type = Column(String(100), nullable=False)  # 'login', 'logout', 'test_run', 'db_connection', etc.
    action = Column(String(255), nullable=False)  # Specific action description
    
    # Context and metadata
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    # Additional data (stored as JSON)
    metadata = Column(JSON, default=dict, nullable=False)
    
    # Status and result
    status = Column(String(50), nullable=False)  # 'success', 'failure', 'error'
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_activities")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_activity_type', 'user_id', 'activity_type'),
        Index('idx_user_activity_timestamp', 'user_id', 'timestamp'),
        Index('idx_activity_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, activity_type='{self.activity_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert activity to dictionary for API responses."""
        return {
            "id": self.id,
            "activity_type": self.activity_type,
            "action": self.action,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
            "status": self.status,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class TestExecution(Base):
    """Model for storing test execution records."""
    __tablename__ = "test_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    test_config_id = Column(Integer, ForeignKey("test_configurations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    execution_data = Column(JSON, nullable=False)  # Input data used for execution
    result = Column(JSON, nullable=False)  # Execution result/response
    status = Column(String(50), nullable=False)  # success, failure, error
    execution_time_ms = Column(Integer, nullable=True)  # Execution time in milliseconds
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    test_config = relationship("TestConfiguration", back_populates="executions")
    user = relationship("User", back_populates="test_executions")
    
    def to_dict(self):
        """Convert the model instance to a dictionary."""
        return {
            "id": self.id,
            "test_config_id": self.test_config_id,
            "user_id": self.user_id,
            "execution_data": self.execution_data,
            "result": self.result,
            "status": self.status,
            "execution_time_ms": self.execution_time_ms,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }


class DatabaseSession(Base):
    """
    Active database sessions tracking.
    
    Tracks active database connections and sessions for monitoring and cleanup.
    """
    __tablename__ = "database_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    
    # Session details
    session_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), nullable=False)  # 'active', 'idle', 'terminated'
    
    # Connection metadata
    ip_address = Column(String(45), nullable=True)
    client_info = Column(JSON, default=dict, nullable=False)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Performance metrics
    queries_executed = Column(Integer, default=0, nullable=False)
    data_transferred = Column(Integer, default=0, nullable=False)  # in bytes
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_sessions', 'user_id', 'status'),
        Index('idx_session_activity', 'last_activity'),
        Index('idx_session_id', 'session_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "status": self.status,
            "ip_address": self.ip_address,
            "client_info": self.client_info,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "queries_executed": self.queries_executed,
            "data_transferred": self.data_transferred
        }


# Additional utility models can be added here as needed
