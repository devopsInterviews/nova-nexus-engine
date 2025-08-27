import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import User, get_db_session
from app.routes.auth_routes import get_current_user
import bcrypt
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users"])

# Pydantic Models for User management
class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime.datetime | None = None
    last_login: datetime.datetime | None = None
    login_count: int = 0
    preferences: dict = {}

    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    new_password: str

class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None

class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    email: str | None = None
    full_name: str | None = None


def is_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency function to check if the current user is an administrator.
    Raises an HTTPException with status 403 if the user is not admin.

    Args:
        current_user (User): The user object, injected by `get_current_user`.

    Returns:
        User: The user object if they are an admin.
    """
    # Check if user has is_admin attribute, fallback to username check for compatibility
    if hasattr(current_user, 'is_admin'):
        if not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    elif current_user.username != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@router.get("/users")
async def get_all_users(db: Session = Depends(get_db_session), current_user: User = Depends(is_admin)):
    """
    Retrieves a list of all users from the database.
    Returns data in the format expected by the frontend.
    """
    try:
        users = db.query(User).all()
        
        # Format users for response
        formatted_users = []
        for user in users:
            formatted_users.append({
                "id": user.id,
                "username": user.username,
                "email": getattr(user, 'email', '') or '',
                "full_name": getattr(user, 'full_name', None),
                "is_active": getattr(user, 'is_active', True),
                "is_admin": getattr(user, 'is_admin', user.username == 'admin'),
                "created_at": getattr(user, 'created_at', user.creation_date if hasattr(user, 'creation_date') else None),
                "last_login": user.last_login,
                "login_count": user.login_count,
                "preferences": getattr(user, 'preferences', {}) or {}
            })
        
        return {
            "status": "success",
            "data": {
                "users": formatted_users
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/users/{user_id}/password")
async def change_user_password(
    user_id: int,
    password_request: PasswordChangeRequest,
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session)
):
    """Change user password (admin only)"""
    try:
        # Find the user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password using the User model's method if available
        if hasattr(user, 'set_password'):
            user.set_password(password_request.new_password)
        else:
            # Fallback to direct bcrypt hashing
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password_request.new_password.encode('utf-8'), salt)
            user.hashed_password = hashed_password.decode('utf-8')
        
        db.commit()
        
        logger.info(f"Password changed for user {user.username} by admin {current_user.username}")
        
        return {
            "status": "success",
            "data": {
                "message": f"Password changed successfully for user {user.username}"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(is_admin)])
async def create_user(user: UserCreate, db: Session = Depends(get_db_session)):
    """
    Creates a new user in the database.

    This endpoint is protected and can only be accessed by an admin user.
    It is used in the 'Users' tab to add new users to the system.

    Args:
        user (UserCreate): The user data (username and password) from the request body.
        db (Session): The database session, injected by FastAPI.

    Returns:
        UserResponse: The newly created user object.
    """
    # Check if username already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists (if provided)
    if user.email:
        existing_email = db.query(User).filter(User.email == user.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    new_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=True,
        is_admin=False,
        preferences={}
    )
    new_user.set_password(user.password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"New user created: {new_user.username}")
    
    return new_user

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(is_admin)])
async def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db_session)):
    """
    Updates an existing user's information.

    This endpoint is protected and can only be accessed by an admin user.
    It allows changing a user's username and/or password from the 'Users' tab.

    Args:
        user_id (int): The ID of the user to update.
        user_update (UserUpdate): The new user data from the request body.
        db (Session): The database session, injected by FastAPI.

    Returns:
        UserResponse: The updated user object.
    """
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check username uniqueness if being changed
    if user_update.username and user_update.username != db_user.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Username already registered")
        db_user.username = user_update.username
    
    # Check email uniqueness if being changed
    if user_update.email and user_update.email != getattr(db_user, 'email', None):
        existing_email = db.query(User).filter(User.email == user_update.email).first()
        if existing_email and existing_email.id != user_id:
            raise HTTPException(status_code=400, detail="Email already registered")
        db_user.email = user_update.email
    
    # Update other fields
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
        
    if user_update.password:
        db_user.set_password(user_update.password)
        
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"User {db_user.username} updated")
    
    return db_user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int, 
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session)
):
    """
    Deletes a user from the database.
    Cannot delete admin users or self.
    """
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent deletion of admin users
        is_target_admin = getattr(db_user, 'is_admin', db_user.username == 'admin')
        if is_target_admin:
            raise HTTPException(status_code=403, detail="Cannot delete admin users")
        
        # Prevent self-deletion
        if db_user.id == current_user.id:
            raise HTTPException(status_code=403, detail="Cannot delete your own account")
        
        username = db_user.username
        db.delete(db_user)
        db.commit()
        
        logger.info(f"User {username} deleted by admin {current_user.username}")
        
        return {
            "status": "success",
            "data": {
                "message": f"User {username} deleted successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
