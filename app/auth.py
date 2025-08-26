"""
Authentication and authorization utilities for MCP Client.

This module provides JWT token-based authentication, password hashing,
user session management, and role-based access control.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserActivity
import secrets
import hashlib

logger = logging.getLogger("uvicorn.error")

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

def get_password_hash(password: str) -> str:
    """Hash a password for storing in the database."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: The data to encode in the token
        expires_delta: Token expiration time
        
    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: The data to encode in the token
        
    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        token_type: Expected token type ('access' or 'refresh')
        
    Returns:
        dict: Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        db: Database session
        username: Username or email
        password: Plain text password
        
    Returns:
        User: User object if authentication successful, None otherwise
    """
    # Try to find user by username or email
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    return user

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    This is a FastAPI dependency that can be used to protect routes.
    
    Args:
        credentials: HTTP Authorization credentials
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    payload = verify_token(credentials.credentials, "access")
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current active user (convenience dependency).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    return current_user

def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current admin user (for admin-only routes).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current admin user
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def log_user_activity(
    db: Session,
    user_id: int,
    activity_type: str,
    action: str,
    status: str = "success",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
):
    """
    Log user activity for audit and monitoring.
    
    Args:
        db: Database session
        user_id: User ID
        activity_type: Type of activity (login, logout, etc.)
        action: Specific action description
        status: Activity status (success, failure, error)
        ip_address: Client IP address
        user_agent: Client user agent
        metadata: Additional metadata
        error_message: Error message if applicable
    """
    try:
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            action=action,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            error_message=error_message
        )
        db.add(activity)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log user activity: {str(e)}")
        db.rollback()

def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP address from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Client IP address
    """
    # Check for forwarded IP in headers (for reverse proxy setups)
    forwarded_ip = request.headers.get("X-Forwarded-For")
    if forwarded_ip:
        return forwarded_ip.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client IP
    return request.client.host if request.client else None

def get_user_agent(request: Request) -> Optional[str]:
    """
    Extract user agent from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: User agent string
    """
    return request.headers.get("User-Agent")

def create_session_token(user_id: int, session_data: Dict[str, Any]) -> str:
    """
    Create a session token for tracking user sessions.
    
    Args:
        user_id: User ID
        session_data: Additional session data
        
    Returns:
        str: Session token
    """
    session_string = f"{user_id}:{datetime.utcnow().isoformat()}:{secrets.token_hex(16)}"
    for key, value in session_data.items():
        session_string += f":{key}:{value}"
    
    return hashlib.sha256(session_string.encode()).hexdigest()

def update_last_login(db: Session, user: User, ip_address: Optional[str] = None):
    """
    Update user's last login information.
    
    Args:
        db: Database session
        user: User object
        ip_address: Client IP address
    """
    try:
        user.last_login = datetime.utcnow()
        user.login_count += 1
        db.commit()
        
        # Log login activity
        log_user_activity(
            db=db,
            user_id=user.id,
            activity_type="login",
            action="User logged in",
            status="success",
            ip_address=ip_address,
            metadata={"login_count": user.login_count}
        )
        
    except Exception as e:
        logger.error(f"Failed to update last login for user {user.id}: {str(e)}")
        db.rollback()

# Optional: Rate limiting for authentication attempts
class AuthRateLimiter:
    """Simple in-memory rate limiter for authentication attempts."""
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts = {}  # {ip_address: [(timestamp, username), ...]}
    
    def is_rate_limited(self, ip_address: str, username: str) -> bool:
        """Check if IP/username combination is rate limited."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        # Clean old attempts
        if ip_address in self.attempts:
            self.attempts[ip_address] = [
                (timestamp, user) for timestamp, user in self.attempts[ip_address]
                if timestamp > window_start
            ]
        
        # Count recent attempts for this IP/username
        recent_attempts = [
            attempt for attempt in self.attempts.get(ip_address, [])
            if attempt[1] == username
        ]
        
        return len(recent_attempts) >= self.max_attempts
    
    def record_attempt(self, ip_address: str, username: str):
        """Record an authentication attempt."""
        if ip_address not in self.attempts:
            self.attempts[ip_address] = []
        
        self.attempts[ip_address].append((datetime.utcnow(), username))

# Global rate limiter instance
auth_rate_limiter = AuthRateLimiter()
