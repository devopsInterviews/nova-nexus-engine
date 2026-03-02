import os
import requests
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

class BuildRequest(BaseModel):
    item_id: int

class DeployRequest(BaseModel):
    item_id: int
    environment: str # 'dev' or 'release'

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
        deployment_status="CREATED",
        version="1.0.0",
        environment="dev"
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    
    logger.info(f"User {current_user.username} created a new marketplace item: {item.name}")
    return item.to_dict()

@router.post("/build")
def build_marketplace_item(req: BuildRequest, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to build this item")

    # Update state to BUILT
    item.deployment_status = "BUILT"
    db.commit()
    db.refresh(item)

    # Optional real infra call (mocked for now but fully implemented request)
    infra_api_server = os.getenv("INFRA_MARKETPLACE_API_SERVER")
    if infra_api_server:
        api_url = infra_api_server if infra_api_server.startswith("http") else f"http://{infra_api_server}"
        try:
            requests.post(f"{api_url}/build", json={
                "entity_name": item.name,
                "entity_type": item.item_type,
                "description": item.description,
                "owner_username": current_user.username
            }, timeout=5)
        except Exception as e:
            logger.warning(f"Could not reach infra build endpoint: {e}")

    return {"status": "ok", "message": "Build completed", "item": item.to_dict()}

@router.post("/deploy")
def deploy_marketplace_item(req: DeployRequest, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to deploy this item")

    # Update state
    item.deployment_status = "DEPLOYED"
    item.environment = req.environment
    db.commit()
    db.refresh(item)

    # Optional real infra call
    infra_api_server = os.getenv("INFRA_MARKETPLACE_API_SERVER")
    if infra_api_server:
        api_url = infra_api_server if infra_api_server.startswith("http") else f"http://{infra_api_server}"
        try:
            requests.post(f"{api_url}/deploy", json={
                "entity_name": item.name,
                "entity_type": item.item_type,
                "owner_username": current_user.username,
                "target_environment": req.environment,
                "chart_version": item.version,
                "ttl_days": 10 if req.environment == "dev" else None
            }, timeout=5)
        except Exception as e:
            logger.warning(f"Could not reach infra deploy endpoint: {e}")

    return {"status": "ok", "message": "Deployed successfully", "item": item.to_dict()}

@router.delete("/items/{item_id}")
def delete_marketplace_item(item_id: int, db: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    """Delete a marketplace item. Only owner or admin can delete."""
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")
        
    # Attempt to hit infrastructure to delete
    infra_api_server = os.getenv("INFRA_MARKETPLACE_API_SERVER")
    if infra_api_server:
        api_url = infra_api_server if infra_api_server.startswith("http") else f"http://{infra_api_server}"
        try:
            requests.delete(f"{api_url}/deploy/{item_id}", json={
                "owner_username": current_user.username,
                "reason": "manual_user_deletion"
            }, timeout=5)
        except Exception as e:
            logger.warning(f"Could not reach infra delete endpoint: {e}")

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
