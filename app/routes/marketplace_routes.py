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
    
    # --- Auto-seed Mock Data if empty ---
    if not items:
        # Get the first available user to be the owner (fallback to 1 if none exists, though DB constraints might fail if 1 doesn't exist)
        first_user = db.query(User).first()
        owner_id = first_user.id if first_user else 1
        
        # Create a mock agent (BUILT)
        agent = MarketplaceItem(
            name="Data Analysis Agent",
            description="Analyzes complex datasets using pandas and returns natural language summaries with insights.",
            item_type="agent",
            owner_id=owner_id,
            icon="https://cdn-icons-png.flaticon.com/512/2042/2042885.png",
            bitbucket_repo="https://bitbucket.company.internal/projects/AI/repos/data-agent",
            how_to_use="Call this agent with a reference to a dataset or ask it to pull data from the DB.",
            url_to_connect="",
            tools_exposed=[],
            deployment_status="BUILT",
            version="1.2.0",
            environment="dev"
        )
        
        # Create a mock MCP Server (DEPLOYED)
        mcp_server = MarketplaceItem(
            name="Jira Integration MCP",
            description="Provides tools to create, update, and search Jira tickets directly from the portal.",
            item_type="mcp_server",
            owner_id=owner_id,
            icon="https://cdn-icons-png.flaticon.com/512/5968/5968875.png",
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/jira-mcp",
            how_to_use="Enable this MCP in your research tab to allow the LLM to manage your Jira board.",
            url_to_connect="http://jira-mcp.mcp-gateway.company.internal",
            tools_exposed=[{"name": "create_ticket"}, {"name": "search_tickets"}],
            deployment_status="DEPLOYED",
            version="2.0.1",
            environment="release"
        )
        
        try:
            db.add(agent)
            db.add(mcp_server)
            db.commit()
            
            # Also add some mock usage data
            db.add(MarketplaceUsage(user_id=owner_id, item_id=mcp_server.id, action="call"))
            db.add(MarketplaceUsage(user_id=owner_id, item_id=mcp_server.id, action="call"))
            db.add(MarketplaceUsage(user_id=owner_id, item_id=agent.id, action="install"))
            db.commit()
            
            items = db.query(MarketplaceItem).all()
        except Exception as e:
            db.rollback()
            logger.warning(f"Could not seed mock marketplace items: {e}")
    # -------------------------------------
    
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
            # TODO: Future implementation when infrastructure is ready.
            # The API server is not ready yet, so we just comment this out.
            # requests.post(f"{api_url}/build", json={
            #     "entity_name": item.name,
            #     "entity_type": item.item_type,
            #     "description": item.description,
            #     "owner_username": current_user.username
            # }, timeout=5)
            pass
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
            # TODO: Future implementation when infrastructure is ready.
            # The API server is not ready yet, so we just comment this out.
            # requests.post(f"{api_url}/deploy", json={
            #     "entity_name": item.name,
            #     "entity_type": item.item_type,
            #     "owner_username": current_user.username,
            #     "target_environment": req.environment,
            #     "chart_version": item.version,
            #     "ttl_days": 10 if req.environment == "dev" else None
            # }, timeout=5)
            pass
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
            # TODO: Future implementation when infrastructure is ready.
            # The API server is not ready yet, so we just comment this out.
            # requests.delete(f"{api_url}/deploy/{item_id}", json={
            #     "owner_username": current_user.username,
            #     "reason": "manual_user_deletion"
            # }, timeout=5)
            pass
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
