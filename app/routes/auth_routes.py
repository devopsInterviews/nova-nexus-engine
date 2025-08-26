"""
Authentication and user management API routes for MCP Client.

This module provides REST API endpoints for user authentication, registration,
profile management, and admin user management functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.database import get_db
from app.models import User, UserActivity, DatabaseConnection, TestConfiguration
from app.auth import (
    authenticate_user, create_access_token, create_refresh_token, verify_token,
    get_password_hash, get_current_user, get_current_admin_user, log_user_activity,
    get_client_ip, get_user_agent, update_last_login, auth_rate_limiter
)

logger = logging.getLogger("uvicorn.error")

# Create router for authentication endpoints
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# Pydantic models for request/response validation

class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, regex="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    
    @validator('username')
    def validate_username(cls, v):
        if v.lower() in ['admin', 'root', 'system', 'api', 'www', 'mail']:
            raise ValueError('Username not allowed')
        return v

class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")

class UserResponse(BaseModel):
    """Schema for user data in responses."""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]
    login_count: int
    preferences: Dict[str, Any]

class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class UserUpdate(BaseModel):
    """Schema for user profile updates."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    preferences: Optional[Dict[str, Any]] = None

class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

class AdminUserUpdate(BaseModel):
    """Schema for admin user updates."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None

class UserActivityResponse(BaseModel):
    """Schema for user activity data."""
    id: int
    activity_type: str
    action: str
    ip_address: Optional[str]
    status: str
    timestamp: datetime
    metadata: Dict[str, Any]

class UserStatsResponse(BaseModel):
    """Schema for user statistics."""
    total_users: int
    active_users: int
    admin_users: int
    recent_logins: int
    new_users_today: int


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    Creates a new user with the provided credentials and profile information.
    Performs validation to ensure username and email uniqueness.
    """
    logger.info(f"User registration attempt for username: {user_data.username}")
    
    # Check if username already exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username, User.email == user_data.email)
    ).first()
    
    if existing_user:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
    
    # Create new user
    try:
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            is_active=True,
            is_admin=False,  # Regular users are not admin by default
            preferences={
                "theme": "dark",
                "notifications": True,
                "default_page": "/dashboard"
            }
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Log registration activity
        log_user_activity(
            db=db,
            user_id=new_user.id,
            activity_type="registration",
            action="User account created",
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        logger.info(f"User registered successfully: {new_user.username} (ID: {new_user.id})")
        
        return UserResponse(**new_user.to_dict())
        
    except Exception as e:
        db.rollback()
        logger.error(f"User registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access tokens.
    
    Validates credentials and returns JWT access and refresh tokens.
    Implements rate limiting to prevent brute force attacks.
    """
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    logger.info(f"Login attempt for user: {login_data.username} from IP: {client_ip}")
    
    # Check rate limiting
    if auth_rate_limiter.is_rate_limited(client_ip, login_data.username):
        logger.warning(f"Rate limited login attempt for {login_data.username} from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    # Authenticate user
    user = authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        # Record failed attempt
        auth_rate_limiter.record_attempt(client_ip, login_data.username)
        
        # Log failed login attempt
        potential_user = db.query(User).filter(
            or_(User.username == login_data.username, User.email == login_data.username)
        ).first()
        
        if potential_user:
            log_user_activity(
                db=db,
                user_id=potential_user.id,
                activity_type="login",
                action="Failed login attempt",
                status="failure",
                ip_address=client_ip,
                user_agent=user_agent,
                error_message="Invalid credentials"
            )
        
        logger.warning(f"Failed login attempt for user: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=60)  # 1 hour
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username}
    )
    
    # Update last login info
    update_last_login(db, user, client_ip)
    
    logger.info(f"Successful login for user: {user.username} (ID: {user.id})")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_token_expires.total_seconds()),
        user=UserResponse(**user.to_dict())
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Validates refresh token and returns new access and refresh tokens.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    # Verify refresh token
    payload = verify_token(credentials.credentials, "refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username}
    )
    
    logger.info(f"Token refreshed for user: {user.username} (ID: {user.id})")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_token_expires.total_seconds()),
        user=UserResponse(**user.to_dict())
    )


@router.post("/logout")
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout current user and invalidate session.
    
    In a production system, you might want to maintain a token blacklist.
    """
    # Log logout activity
    log_user_activity(
        db=db,
        user_id=current_user.id,
        activity_type="logout",
        action="User logged out",
        status="success",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request)
    )
    
    logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile information."""
    return UserResponse(**current_user.to_dict())


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile information.
    
    Allows users to update their email, full name, and preferences.
    """
    try:
        # Check if email is being changed and if it's already taken
        if user_update.email and user_update.email != current_user.email:
            existing_user = db.query(User).filter(
                and_(User.email == user_update.email, User.id != current_user.id)
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already in use"
                )
            current_user.email = user_update.email
        
        # Update other fields
        if user_update.full_name is not None:
            current_user.full_name = user_update.full_name
        
        if user_update.preferences is not None:
            # Merge with existing preferences
            current_preferences = current_user.preferences or {}
            current_preferences.update(user_update.preferences)
            current_user.preferences = current_preferences
        
        current_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        
        # Log profile update
        log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="profile_update",
            action="Profile information updated",
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            metadata={"updated_fields": list(user_update.dict(exclude_unset=True).keys())}
        )
        
        logger.info(f"Profile updated for user: {current_user.username} (ID: {current_user.id})")
        
        return UserResponse(**current_user.to_dict())
        
    except Exception as e:
        db.rollback()
        logger.error(f"Profile update failed for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/change-password")
async def change_password(
    password_change: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password."""
    from app.auth import verify_password
    
    # Verify current password
    if not verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    try:
        # Update password
        current_user.hashed_password = get_password_hash(password_change.new_password)
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        # Log password change
        log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="password_change",
            action="Password changed",
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        logger.info(f"Password changed for user: {current_user.username} (ID: {current_user.id})")
        
        return {"message": "Password changed successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Password change failed for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


# Admin-only endpoints

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)."""
    query = db.query(User)
    
    if search:
        search_filter = or_(
            User.username.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
    return [UserResponse(**user.to_dict()) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(**user.to_dict())


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_by_admin(
    user_id: int,
    user_update: AdminUserUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user by admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # Update fields
        if user_update.email is not None:
            # Check email uniqueness
            existing = db.query(User).filter(
                and_(User.email == user_update.email, User.id != user_id)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already in use"
                )
            user.email = user_update.email
        
        if user_update.full_name is not None:
            user.full_name = user_update.full_name
        
        if user_update.is_active is not None:
            user.is_active = user_update.is_active
        
        if user_update.is_admin is not None:
            user.is_admin = user_update.is_admin
        
        if user_update.preferences is not None:
            current_preferences = user.preferences or {}
            current_preferences.update(user_update.preferences)
            user.preferences = current_preferences
        
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Log admin action
        log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="admin_action",
            action=f"Updated user {user.username}",
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            metadata={"target_user_id": user_id, "updated_fields": list(user_update.dict(exclude_unset=True).keys())}
        )
        
        logger.info(f"User {user_id} updated by admin {current_user.username}")
        
        return UserResponse(**user.to_dict())
        
    except Exception as e:
        db.rollback()
        logger.error(f"Admin user update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    try:
        username = user.username
        db.delete(user)
        db.commit()
        
        # Log admin action
        log_user_activity(
            db=db,
            user_id=current_user.id,
            activity_type="admin_action",
            action=f"Deleted user {username}",
            status="success",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            metadata={"deleted_user_id": user_id, "deleted_username": username}
        )
        
        logger.info(f"User {user_id} ({username}) deleted by admin {current_user.username}")
        
        return {"message": f"User {username} deleted successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"User deletion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.get("/users/{user_id}/activity", response_model=List[UserActivityResponse])
async def get_user_activity(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    activity_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get user activity log (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    query = db.query(UserActivity).filter(UserActivity.user_id == user_id)
    
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    
    activities = query.order_by(desc(UserActivity.timestamp)).offset(skip).limit(limit).all()
    
    return [UserActivityResponse(**activity.to_dict()) for activity in activities]


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get user statistics (admin only)."""
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.is_admin == True).count()
    
    # Recent logins (last 24 hours)
    recent_logins = db.query(User).filter(
        User.last_login >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    
    # New users today
    new_users_today = db.query(User).filter(
        User.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    return UserStatsResponse(
        total_users=total_users,
        active_users=active_users,
        admin_users=admin_users,
        recent_logins=recent_logins,
        new_users_today=new_users_today
    )
