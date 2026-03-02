import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.database import get_db_session
from app.models import MarketplaceItem, MarketplaceUsage, User
from app.routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["Marketplace"])

class ItemCreate(BaseModel):
    name: str
    description: str
    item_type: str
    icon: Optional[str] = None
    bitbucket_repo: Optional[str] = None
    how_to_use: Optional[str] = None
    url_to_connect: Optional[str] = None
    tools_exposed: Optional[List[Dict[str, Any]]] = None

class UsageRequest(BaseModel):
    item_id: int
    action: str

@router.get("/items")
def get_marketplace_items(db: Session = Depends(get_db_session)):
    """Get all marketplace items (agents and mcp servers)."""
    items = db.query(MarketplaceItem).all()
    
    results = []
    for item in items:
        item_dict = item.to_dict()
        usage_count = db.query(MarketplaceUsage).filter_by(item_id=item.id).count()
        unique_users = db.query(func.count(func.distinct(MarketplaceUsage.user_id))).filter_by(item_id=item.id).scalar() or 0
        
        item_dict['usage_count'] = usage_count
        item_dict['unique_users'] = unique_users
        results.append(item_dict)
        
    return results

@router.post("/items")
def create_marketplace_item(req: ItemCreate, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    """Create a new marketplace item (Agent or MCP Server)."""
    item = MarketplaceItem(
        name=req.name,
        description=req.description,
        item_type=req.item_type,
        owner_id=current_user.id,
        icon=req.icon,
        bitbucket_repo=req.bitbucket_repo,
        how_to_use=req.how_to_use,
        url_to_connect=req.url_to_connect,
        tools_exposed=req.tools_exposed or [],
        deployment_status="CREATED"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    
    logger.info(f"User {current_user.username} created a new marketplace item: {item.name}")
    return item.to_dict()

@router.delete("/items/{item_id}")
def delete_marketplace_item(item_id: int, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    """Delete a marketplace item. Only owner or admin can delete."""
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")
        
    db.delete(item)
    db.commit()
    logger.info(f"User {current_user.username} deleted marketplace item: {item.name}")
    return {"status": "ok"}

@router.post("/usage")
def log_usage(req: UsageRequest, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    """Log usage of a marketplace item."""
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    usage = MarketplaceUsage(
        user_id=current_user.id,
        item_id=req.item_id,
        action=req.action
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    
    logger.info(f"Usage logged for item {item.name} ({req.item_id}) by {current_user.username}: {req.action}")
    return usage.to_dict()
