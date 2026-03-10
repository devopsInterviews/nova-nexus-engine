from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db_session
from app.models import User, SSOGroup, TabPermission
from app.routes.auth_routes import get_current_user
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Permissions"])

class TabPermissionsUpdate(BaseModel):
    tab_name: str
    user_ids: List[int]
    group_ids: List[int]

class PermissionsUpdate(BaseModel):
    permissions: List[TabPermissionsUpdate]

class PermissionsResponse(BaseModel):
    status: str
    data: Dict[str, dict]

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get current tab permissions for all users and groups.
    """
    try:
        # Get all permissions from DB
        all_perms = db.query(TabPermission).all()
        
        # Build the response structure
        permissions = {}
        
        for p in all_perms:
            if p.tab_name not in permissions:
                permissions[p.tab_name] = {"users": [], "groups": []}
            if p.user_id is not None:
                permissions[p.tab_name]["users"].append(p.user_id)
            if p.group_id is not None:
                permissions[p.tab_name]["groups"].append(p.group_id)
        
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Update tab permissions for users and groups.
    """
    try:
        # Clear all existing permissions
        db.query(TabPermission).delete()
        
        permissions_dict = {}
        for tab_perm in permissions_update.permissions:
            tab_name = tab_perm.tab_name
            permissions_dict[tab_name] = {"users": tab_perm.user_ids, "groups": tab_perm.group_ids}
            
            # Add new user permissions
            for uid in tab_perm.user_ids:
                db.add(TabPermission(tab_name=tab_name, user_id=uid))
                
            # Add new group permissions
            for gid in tab_perm.group_ids:
                db.add(TabPermission(tab_name=tab_name, group_id=gid))
                
        db.commit()
        
        logger.info(f"Permissions updated by user {current_user.username}")
        
        return {
            "status": "success",
            "data": permissions_dict
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

class AdminGroupRequest(BaseModel):
    group_id: int


@router.get("/admin-groups")
async def get_admin_groups(
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session),
):
    """Return IDs of SSO groups that have been granted portal admin access."""
    groups = db.query(SSOGroup).filter(SSOGroup.is_admin == True).all()
    return {"group_ids": [g.id for g in groups]}


@router.post("/admin-groups", status_code=201)
async def grant_admin_group(
    req: AdminGroupRequest,
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session),
):
    """Grant portal admin role to an SSO group."""
    group = db.query(SSOGroup).filter(SSOGroup.id == req.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.is_admin = True
    db.commit()
    logger.info("Admin granted to group '%s' (id=%d) by %s", group.name, group.id, current_user.username)
    return {"status": "ok", "group_id": group.id}


@router.delete("/admin-groups/{group_id}", status_code=200)
async def revoke_admin_group(
    group_id: int,
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session),
):
    """Revoke portal admin role from an SSO group."""
    group = db.query(SSOGroup).filter(SSOGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.is_admin = False
    db.commit()
    logger.info("Admin revoked from group '%s' (id=%d) by %s", group.name, group.id, current_user.username)
    return {"status": "ok", "group_id": group.id}


@router.get("/permissions/user/{user_id}")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get permissions for a specific user.
    """
    try:
        if current_user.id != user_id and not getattr(current_user, 'is_admin', current_user.username == 'admin'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        from app.routes.auth_routes import get_user_allowed_tabs
        allowed_tabs = get_user_allowed_tabs(user, db)
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "username": user.username,
                "allowed_tabs": allowed_tabs
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
