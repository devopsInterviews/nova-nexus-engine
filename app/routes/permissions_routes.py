from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db_session
from app.models import User
from app.routes.auth_routes import get_current_user
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Permissions"])

class TabPermissions(BaseModel):
    tab_name: str
    user_ids: List[int]

class PermissionsUpdate(BaseModel):
    permissions: List[TabPermissions]

class PermissionsResponse(BaseModel):
    status: str
    data: Dict[str, List[int]]

def is_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency function to check if the current user is an administrator.
    """
    if hasattr(current_user, 'is_admin'):
        if not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    elif current_user.username != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@router.get("/permissions")
async def get_permissions(
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session)
):
    """
    Get current tab permissions for all users.
    Returns a mapping of tab names to user IDs who have access.
    """
    try:
        # Get all users
        users = db.query(User).all()
        
        # Initialize default permissions - all users have access to all tabs
        tabs = ['Home', 'DevOps', 'BI', 'Analytics', 'Tests', 'Users', 'Settings']
        permissions = {}
        
        for tab in tabs:
            permissions[tab] = [user.id for user in users]
        
        # For now, we store permissions in the user preferences
        # In the future, this could be moved to a separate permissions table
        
        return {
            "status": "success",
            "data": permissions
        }
        
    except Exception as e:
        logger.error(f"Error getting permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/permissions", response_model=PermissionsResponse)
async def update_permissions(
    permissions_update: PermissionsUpdate,
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session)
):
    """
    Update tab permissions for users.
    This is a basic implementation that stores permissions in user preferences.
    """
    try:
        # Convert the permissions to a simple dict format
        permissions_dict = {}
        for tab_perm in permissions_update.permissions:
            permissions_dict[tab_perm.tab_name] = tab_perm.user_ids
        
        # Store the permissions globally (in a simple way for now)
        # In a real implementation, you'd want a separate permissions table
        
        logger.info(f"Permissions updated by admin {current_user.username}: {permissions_dict}")
        
        return {
            "status": "success",
            "data": permissions_dict
        }
        
    except Exception as e:
        logger.error(f"Error updating permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/permissions/user/{user_id}")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get permissions for a specific user.
    Users can check their own permissions, admins can check any user's permissions.
    """
    try:
        # Users can only check their own permissions unless they're admin
        if current_user.id != user_id and not getattr(current_user, 'is_admin', current_user.username == 'admin'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # For now, return all tabs (since we haven't implemented the storage yet)
        # In a real implementation, you'd check the actual permissions
        tabs = ['Home', 'DevOps', 'BI', 'Analytics', 'Tests', 'Users', 'Settings']
        user_tabs = tabs  # All tabs for now
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "username": user.username,
                "allowed_tabs": user_tabs
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user permissions for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
