import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import MarketplaceAgent, MarketplaceMcpServer, MarketplaceUsage, User
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["Marketplace"])

class UsageRequest(BaseModel):
    item_type: str
    item_id: int
    action: str

@router.get("/agents")
def get_agents(db: Session = Depends(get_db)):
    """Get all marketplace agents."""
    agents = db.query(MarketplaceAgent).all()
    return [agent.to_dict() for agent in agents]

@router.get("/mcp-servers")
def get_mcp_servers(db: Session = Depends(get_db)):
    """Get all marketplace MCP servers."""
    servers = db.query(MarketplaceMcpServer).all()
    return [server.to_dict() for server in servers]

@router.post("/usage")
def log_usage(req: UsageRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Log usage of a marketplace item."""
    usage = MarketplaceUsage(
        user_id=current_user.id,
        item_type=req.item_type,
        item_id=req.item_id,
        action=req.action
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage.to_dict()
