"""
Authentication route handlers for local (username/password) login.

This module provides the core authentication endpoints that the frontend
uses to log in with local credentials.  The SSO flow lives in
``sso_routes.py`` but both flows issue the same portal JWT so the rest of
the API does not need to distinguish between them.

Endpoints:
    POST /api/login   — authenticate with username + password, return JWT.
    GET  /api/me      — return the current user's profile (token required).
    POST /api/logout  — server-side logout hook (token invalidation is
                        client-side; this endpoint is for consistency).
    GET  /api/profile — extended profile information.
"""

import os
import hashlib
import datetime
import logging
from typing import List, Optional

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import User, UserActivity, UserSession

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["Authentication"])

SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET_KEY", "your_default_secret_key"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

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

import os

DEFAULT_ALLOWED_TABS = [t.strip() for t in os.getenv("DEFAULT_ALLOWED_TABS", "Home,Settings").split(",")]

class UserResponse(BaseModel):
    """Pydantic model for user data returned by the API."""
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool
    auth_provider: str = "local"
    created_at: datetime.datetime | None
    creation_date: datetime.datetime | None
    last_login: datetime.datetime | None
    login_count: int
    groups: list[str] = []
    allowed_tabs: list[str] = []

    class Config:
        from_attributes = True

def get_user_allowed_tabs(user: User, db: Session) -> list[str]:
    """Helper to determine which tabs a user can access."""
    if user.is_admin or user.username == 'admin':
        return ['Home', 'DevOps', 'BI', 'Analytics', 'Tests', 'Users', 'Settings', 'Admin', 'Research']
    
    from app.models import TabPermission
    group_ids = [g.id for g in user.groups] if user.groups else []
    
    perms = db.query(TabPermission).filter(
        (TabPermission.user_id == user.id) |
        (TabPermission.group_id.in_(group_ids))
    ).all()
    
    allowed_tabs = list(set([p.tab_name for p in perms]))
    for dt in DEFAULT_ALLOWED_TABS:
        if dt not in allowed_tabs:
            allowed_tabs.append(dt)
    
    return allowed_tabs


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
async def login_for_access_token(
    form_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """
    Authenticate a local user with username/password and return a portal JWT.

    This endpoint handles the **local login path** (as opposed to the SSO
    path in ``/api/sso/login``).  Both paths issue the same portal JWT so
    the rest of the API is auth-method agnostic.

    Flow:
        1. Look up user by username.
        2. Verify the password hash.
        3. Reject SSO-only users who have no local password set.
        4. Update ``last_login`` and ``login_count``.
        5. Issue a portal JWT.
        6. Persist the session in ``user_sessions`` for admin visibility.
        7. Log the login event in ``user_activities``.

    Args:
        form_data: Username and password from the request body.
        request: FastAPI request (for IP / user-agent extraction).
        db: Database session.

    Returns:
        Token with ``access_token`` and ``token_type``.
    """
    ip = _extract_client_ip(request)
    ua = request.headers.get("User-Agent")

    logger.info("[AUTH] Local login attempt for username='%s' from ip=%s", form_data.username, ip)

    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        logger.warning("[AUTH] Login failed — user '%s' not found (ip=%s)", form_data.username, ip)
        _log_login_failure(db, form_data.username, ip, ua, "User not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # SSO-only users cannot use local login
    if user.hashed_password is None:
        logger.warning(
            "[AUTH] Login failed — user '%s' is SSO-only, no local password (ip=%s)",
            form_data.username, ip,
        )
        _log_login_failure(db, form_data.username, ip, ua, "SSO-only user attempted local login")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses company SSO. Please use 'Login with Company Credentials'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.check_password(form_data.password):
        logger.warning("[AUTH] Login failed — wrong password for user '%s' (ip=%s)", form_data.username, ip)
        _log_login_failure(db, form_data.username, ip, ua, "Incorrect password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update login statistics
    user.last_login = datetime.datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    # Issue JWT
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "user_id": user.id,
        "sub": user.username,
        "auth_provider": user.auth_provider or "local",
        "exp": expires_at,
    }
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Persist the session
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        auth_method="local",
        ip_address=ip,
        user_agent=ua,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)

    # Log the login event
    activity = UserActivity(
        user_id=user.id,
        activity_type="login",
        action="Local login",
        status="success",
        ip_address=ip,
        user_agent=ua,
        activity_metadata={
            "auth_method": "local",
            "login_count": user.login_count,
        },
    )
    db.add(activity)
    db.commit()

    logger.info(
        "[AUTH] Local login successful — user_id=%d username='%s' ip=%s login_count=%d",
        user.id, user.username, ip, user.login_count,
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    """
    Returns the details of the currently authenticated user.
    """
    user_dict = current_user.to_dict()
    user_dict["allowed_tabs"] = get_user_allowed_tabs(current_user, db)
    return user_dict

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint - mainly for consistency.
    The actual logout is handled client-side by removing the token.
    """
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    """
    Get current user profile information including SSO-related fields.
    """
    logger.debug("[AUTH] Profile requested for user_id=%d username='%s'", current_user.id, current_user.username)
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
                "auth_provider": getattr(current_user, 'auth_provider', 'local'),
                "last_login": current_user.last_login,
                "login_count": current_user.login_count,
                "preferences": getattr(current_user, 'preferences', {}) or {},
                "groups": [g.name for g in current_user.groups] if hasattr(current_user, 'groups') and current_user.groups else [],
                "allowed_tabs": get_user_allowed_tabs(current_user, db)
            }
        }
    }


# -------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------

def _extract_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from proxy headers or the direct connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None


def _log_login_failure(
    db: Session,
    username: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    reason: str,
) -> None:
    """Record a failed local login attempt for admin analytics."""
    try:
        activity = UserActivity(
            user_id=None,
            activity_type="login",
            action="Local login failed",
            status="failure",
            ip_address=ip_address,
            user_agent=user_agent,
            activity_metadata={"auth_method": "local", "attempted_username": username},
            error_message=reason,
        )
        db.add(activity)
        db.commit()
        logger.debug("[AUTH] Login failure logged — username='%s' reason='%s'", username, reason)
    except Exception as exc:
        logger.error("[AUTH] Failed to log login failure: %s", exc)
        db.rollback()
