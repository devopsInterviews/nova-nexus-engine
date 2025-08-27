import os
import datetime
from typing import List, Optional

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import User

router = APIRouter(tags=["Authentication"])

SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # 2 hours (as requested)

# Pydantic Models
class Token(BaseModel):
    """Pydantic model for the authentication token response."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Pydantic model for the data encoded in the token."""
    username: str | None = None

class UserLogin(BaseModel):
    """Pydantic model for the user login request."""
    username: str
    password: str

class UserResponse(BaseModel):
    """Pydantic model for user data returned by the API."""
    id: int
    username: str
    creation_date: datetime.datetime | None
    last_login: datetime.datetime | None
    login_count: int

    class Config:
        orm_mode = True


async def get_current_user(request: Request, db: Session = Depends(get_db_session)) -> User:
    """
    FastAPI dependency to get the current authenticated user from a token.

    It extracts the token from the 'x-access-token' or 'Authorization' header,
    validates it, and retrieves the corresponding user from the database.

    This function is used as a dependency in all protected endpoints to ensure
    the user is authenticated.

    Args:
        request (Request): The incoming request object.
        db (Session): The database session.

    Raises:
        HTTPException: If the token is missing, invalid, or the user is not found.

    Returns:
        User: The authenticated user object.
    """
    token = request.headers.get('x-access-token') or request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(db: Session, request: Request) -> Optional[User]:
    """
    Helper function to get current user without raising exceptions.
    Used for optional authentication scenarios like analytics logging.
    
    Args:
        db: Database session
        request: FastAPI request object
        
    Returns:
        User or None: The authenticated user if valid token exists, None otherwise
    """
    try:
        # Try to get authorization header
        token = request.headers.get('x-access-token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return None
        
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            return None
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        return user
        
    except Exception:
        # Any error means no valid user
        return None

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: UserLogin, db: Session = Depends(get_db_session)):
    """
    Authenticates a user and returns a JWT access token.

    This is the primary endpoint for user login. It checks the provided
    username and password, and if valid, generates and returns an access token.
    It also updates the user's last login time and login count.

    Args:
        form_data (UserLogin): The username and password from the request body.
        db (Session): The database session.

    Returns:
        Token: An object containing the access token and token type.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.check_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user.last_login = datetime.datetime.utcnow()
    user.login_count += 1
    db.commit()

    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"user_id": user.id, "sub": user.username}
    expire = datetime.datetime.utcnow() + access_token_expires
    to_encode.update({"exp": expire})
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Returns the details of the currently authenticated user.

    This endpoint is used by the frontend to verify that the user is logged in
    and to get their user information.

    Args:
        current_user (User): The authenticated user, injected by `get_current_user`.

    Returns:
        UserResponse: The details of the current user.
    """
    return current_user

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint - mainly for consistency.
    The actual logout is handled client-side by removing the token.
    """
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile information.
    """
    return {
        "status": "success",
        "data": {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": getattr(current_user, 'email', '') or '',
                "full_name": getattr(current_user, 'full_name', None),
                "is_active": getattr(current_user, 'is_active', True),
                "is_admin": getattr(current_user, 'is_admin', current_user.username == 'admin'),
                "last_login": current_user.last_login,
                "login_count": current_user.login_count,
                "preferences": getattr(current_user, 'preferences', {}) or {}
            }
        }
    }
