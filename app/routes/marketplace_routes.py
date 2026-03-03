"""
Marketplace API routes.

Entity lifecycle: CREATE (= BUILT) → DEPLOY → REDEPLOY / DELETE

Additional endpoints:
  GET  /config            — server-side limits for the frontend
  GET  /charts            — list available Helm chart names from Artifactory
  GET  /chart-versions    — list versions for a specific chart
  POST /ping              — PUBLIC, no auth; agents/MCP servers self-report usage
  POST /items/{id}/clone  — fork a deployed item for a parallel deployment
  POST /redeploy          — undeploy then re-deploy with a new chart/version
  background task         — daily TTL expiry check
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db_session, SessionLocal
from app.models import MarketplaceItem, MarketplaceUsage, User
from app.routes.auth_routes import get_current_user
from app.services.artifactory_client import (
    get_marketplace_chart_versions,
    get_marketplace_charts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["Marketplace"])

# ─── Runtime configuration ───────────────────────────────────────────────────
MARKETPLACE_MAX_AGENTS_PER_USER: int = int(os.getenv("MARKETPLACE_MAX_AGENTS_PER_USER", "5"))
MARKETPLACE_MAX_MCP_PER_USER: int = int(os.getenv("MARKETPLACE_MAX_MCP_PER_USER", "5"))
MARKETPLACE_DEV_TTL_DAYS: int = int(os.getenv("MARKETPLACE_DEV_TTL_DAYS", "10"))
INFRA_MARKETPLACE_API_SERVER: Optional[str] = os.getenv("INFRA_MARKETPLACE_API_SERVER")

logger.info(
    "[MARKETPLACE] Config — max_agents=%d, max_mcp=%d, dev_ttl=%d days, infra_api=%s",
    MARKETPLACE_MAX_AGENTS_PER_USER,
    MARKETPLACE_MAX_MCP_PER_USER,
    MARKETPLACE_DEV_TTL_DAYS,
    INFRA_MARKETPLACE_API_SERVER or "not set",
)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    name: str
    description: str
    item_type: str                                   # 'agent' or 'mcp_server'
    icon: Optional[str] = None                       # base64 data URI or plain URL
    bitbucket_repo: Optional[str] = None
    how_to_use: Optional[str] = None
    tools_exposed: Optional[List[Dict[str, Any]]] = None


class DeployRequest(BaseModel):
    item_id: int
    environment: str        # 'dev' or 'release'
    chart_name: str = ""    # Artifactory chart name
    chart_version: str = "latest"


class RedeployRequest(BaseModel):
    item_id: int
    environment: str        # 'dev' or 'release'
    chart_name: str = ""    # New Artifactory chart name
    chart_version: str = "latest"


class UsageRequest(BaseModel):
    item_id: int
    action: str             # 'call', 'install', 'deploy'


class PingRequest(BaseModel):
    """
    Public self-report payload sent by a running Agent or MCP Server.
    No authentication is required for this endpoint.
    """
    entity_name: str
    entity_type: str        # 'agent' or 'mcp_server'
    user_identifier: Optional[str] = None  # optional caller identifier
    action: str = "call"


# ─── Helper: build infra API base URL ────────────────────────────────────────

def _infra_url() -> Optional[str]:
    if not INFRA_MARKETPLACE_API_SERVER:
        return None
    srv = INFRA_MARKETPLACE_API_SERVER
    return srv if srv.startswith("http") else f"http://{srv}"


# ─── Helper: enrich item dict with usage counts ───────────────────────────────

def _enrich_item(item: MarketplaceItem, db: Session) -> Dict[str, Any]:
    item_dict = item.to_dict()
    usage_count = db.query(MarketplaceUsage).filter_by(item_id=item.id).count()
    unique_users = (
        db.query(func.count(func.distinct(MarketplaceUsage.user_id)))
        .filter(MarketplaceUsage.item_id == item.id)
        .scalar()
        or 0
    )
    item_dict["usage_count"] = usage_count
    item_dict["unique_users"] = unique_users
    return item_dict


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/config")
def get_marketplace_config():
    """Return server-side marketplace configuration values to the frontend."""
    return {
        "max_agents_per_user": MARKETPLACE_MAX_AGENTS_PER_USER,
        "max_mcp_per_user": MARKETPLACE_MAX_MCP_PER_USER,
        "dev_ttl_days": MARKETPLACE_DEV_TTL_DAYS,
    }


@router.get("/items")
def get_marketplace_items(db: Session = Depends(get_db_session)):
    """
    Fetch all marketplace items with usage stats.
    Auto-seeds rich mock data on first run so the UI is immediately testable.
    """
    items = db.query(MarketplaceItem).all()
    if not items:
        _seed_mock_data(db)
        items = db.query(MarketplaceItem).all()
    return [_enrich_item(item, db) for item in items]


@router.post("/items")
def create_marketplace_item(
    req: ItemCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create (= register + build) a new Agent or MCP Server.

    Creating immediately sets status to BUILT — since the CI/CD scaffolding step
    is handled asynchronously by the infra team, this simplifies the UX to a
    single action: Create → then Deploy.
    """
    if req.item_type == "agent":
        user_count = (
            db.query(MarketplaceItem)
            .filter_by(owner_id=current_user.id, item_type="agent")
            .count()
        )
        if user_count >= MARKETPLACE_MAX_AGENTS_PER_USER:
            logger.warning(
                "[MARKETPLACE] User %s hit agent limit (%d/%d)",
                current_user.username, user_count, MARKETPLACE_MAX_AGENTS_PER_USER,
            )
            raise HTTPException(
                status_code=429,
                detail=f"Agent limit reached ({MARKETPLACE_MAX_AGENTS_PER_USER} max).",
            )
    elif req.item_type == "mcp_server":
        user_count = (
            db.query(MarketplaceItem)
            .filter_by(owner_id=current_user.id, item_type="mcp_server")
            .count()
        )
        if user_count >= MARKETPLACE_MAX_MCP_PER_USER:
            logger.warning(
                "[MARKETPLACE] User %s hit MCP server limit (%d/%d)",
                current_user.username, user_count, MARKETPLACE_MAX_MCP_PER_USER,
            )
            raise HTTPException(
                status_code=429,
                detail=f"MCP server limit reached ({MARKETPLACE_MAX_MCP_PER_USER} max).",
            )

    item = MarketplaceItem(
        name=req.name,
        description=req.description,
        item_type=req.item_type,
        owner_id=current_user.id,
        icon=req.icon,
        bitbucket_repo=req.bitbucket_repo,
        how_to_use=req.how_to_use,
        url_to_connect=None,  # set by infra after first deploy
        tools_exposed=req.tools_exposed or [],
        # Start as BUILT — Create = Build in the current workflow
        deployment_status="BUILT",
        version="1.0.0",
        environment="dev",
        ttl_days=MARKETPLACE_DEV_TTL_DAYS,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' created %s '%s' (id=%d) → status=BUILT",
        current_user.username, item.item_type, item.name, item.id,
    )

    # ── Infra hook ──────────────────────────────────────────────────────────
    infra = _infra_url()
    if infra:
        logger.info(
            "[MARKETPLACE] TODO: POST %s/api/infra/build — entity=%s owner=%s",
            infra, item.name, current_user.username,
        )
        # TODO: uncomment when infra is ready
        # http_requests.post(f"{infra}/api/infra/build", json={
        #     "entity_name": item.name,
        #     "entity_type": item.item_type,
        #     "description": item.description,
        #     "owner_username": current_user.username,
        #     "template_type": "python_fastapi",
        # }, timeout=10)
    # ────────────────────────────────────────────────────────────────────────

    return _enrich_item(item, db)


@router.get("/charts")
def get_available_charts(environment: str = "dev"):
    """
    Return all chart names available in Artifactory for the given environment.
    The frontend presents these in the Deploy dialog so the user can select
    which chart to deploy.
    """
    charts, error = get_marketplace_charts(environment)
    if error:
        logger.warning(
            "[MARKETPLACE] chart list warning (env=%s): %s", environment, error
        )
    return {"environment": environment, "charts": charts}


@router.get("/chart-versions")
def get_chart_versions(
    environment: str = "dev",
    chart_name: str = "",
):
    """
    Return available Helm chart versions for a specific chart name and environment.
    Called after the user selects a chart name in the Deploy dialog.
    """
    if not chart_name:
        raise HTTPException(status_code=400, detail="chart_name is required")

    versions, error = get_marketplace_chart_versions(chart_name, environment)
    if error:
        logger.warning(
            "[MARKETPLACE] chart-versions warning (env=%s, chart=%s): %s",
            environment, chart_name, error,
        )
    return {"environment": environment, "chart_name": chart_name, "versions": versions}


@router.post("/deploy")
def deploy_marketplace_item(
    req: DeployRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Deploy a BUILT item to dev or release.
    Stores chart_name, chart_version, deployed_at, and ttl_days in the DB.
    The actual Helm deploy call is stubbed — logged and commented out.
    """
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to deploy this item")
    if item.deployment_status not in ("BUILT", "DEPLOYED"):
        raise HTTPException(
            status_code=400,
            detail="Item must be BUILT or DEPLOYED before deploying.",
        )

    item.deployment_status = "DEPLOYED"
    item.environment = req.environment
    item.chart_name = req.chart_name or item.name
    item.chart_version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None

    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' deployed '%s' (id=%d) → env=%s chart=%s@%s",
        current_user.username, item.name, item.id,
        req.environment, req.chart_name, req.chart_version,
    )

    infra = _infra_url()
    if infra:
        logger.info(
            "[MARKETPLACE] TODO: POST %s/api/infra/deploy — entity=%s chart=%s@%s env=%s ttl=%s",
            infra, item.name, req.chart_name, req.chart_version,
            req.environment, MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else "none",
        )
        # TODO: uncomment when infra is ready
        # http_requests.post(f"{infra}/api/infra/deploy", json={
        #     "entity_name": item.name,
        #     "entity_type": item.item_type,
        #     "chart_name": req.chart_name,
        #     "chart_version": req.chart_version,
        #     "owner_username": current_user.username,
        #     "target_environment": req.environment,
        #     "ttl_days": MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None,
        #     "quota_profile": "standard",
        # }, timeout=10)

    return {"status": "ok", "message": f"Deployed to {req.environment}", "item": _enrich_item(item, db)}


@router.post("/redeploy")
def redeploy_marketplace_item(
    req: RedeployRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Redeploy a DEPLOYED item with a new chart name/version or environment.

    Workflow:
      1. Call infra undeploy (logged, TODO)
      2. Call infra deploy with new spec (logged, TODO)
      3. Update DB record with new chart_name, chart_version, deployed_at, ttl_days
    """
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to redeploy this item")
    if item.deployment_status != "DEPLOYED":
        raise HTTPException(
            status_code=400,
            detail="Only DEPLOYED items can be redeployed. Deploy it first.",
        )

    old_chart = item.chart_name
    old_version = item.chart_version
    old_env = item.environment

    item.environment = req.environment
    item.chart_name = req.chart_name or item.chart_name
    item.chart_version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None

    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' redeployed '%s' (id=%d): %s@%s/%s → %s@%s/%s",
        current_user.username, item.name, item.id,
        old_chart, old_version, old_env,
        req.chart_name, req.chart_version, req.environment,
    )

    infra = _infra_url()
    if infra:
        logger.info(
            "[MARKETPLACE] TODO: DELETE %s/api/infra/deploy/%d (old deployment) then re-deploy",
            infra, item.id,
        )
        # TODO: uncomment when infra is ready
        # Step 1 — undeploy old
        # http_requests.delete(f"{infra}/api/infra/deploy/{item.id}", json={
        #     "owner_username": current_user.username,
        #     "reason": "redeploy",
        # }, timeout=10)
        # Step 2 — deploy new
        # http_requests.post(f"{infra}/api/infra/deploy", json={
        #     "entity_name": item.name,
        #     "entity_type": item.item_type,
        #     "chart_name": req.chart_name,
        #     "chart_version": req.chart_version,
        #     "owner_username": current_user.username,
        #     "target_environment": req.environment,
        #     "ttl_days": MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None,
        # }, timeout=10)

    return {"status": "ok", "message": f"Redeployed to {req.environment}", "item": _enrich_item(item, db)}


@router.post("/items/{item_id}/clone")
def clone_marketplace_item(
    item_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fork a BUILT or DEPLOYED item into a fresh BUILT copy owned by the current user.
    The clone starts as BUILT so it can be independently deployed to any environment.
    """
    source = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source item not found")
    if source.deployment_status not in ("BUILT", "DEPLOYED"):
        raise HTTPException(
            status_code=400, detail="Only BUILT or DEPLOYED items can be cloned."
        )

    if source.item_type == "agent":
        user_count = (
            db.query(MarketplaceItem)
            .filter_by(owner_id=current_user.id, item_type="agent")
            .count()
        )
        if user_count >= MARKETPLACE_MAX_AGENTS_PER_USER:
            raise HTTPException(status_code=429, detail="Agent limit reached.")

    clone = MarketplaceItem(
        name=f"{source.name} (Fork)",
        description=source.description,
        item_type=source.item_type,
        owner_id=current_user.id,
        icon=source.icon,
        bitbucket_repo=source.bitbucket_repo,
        how_to_use=source.how_to_use,
        url_to_connect=None,
        tools_exposed=source.tools_exposed,
        deployment_status="BUILT",
        version=source.version,
        environment="dev",
        chart_name=source.chart_name,
        chart_version=source.chart_version,
        ttl_days=MARKETPLACE_DEV_TTL_DAYS,
        deployed_at=None,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    logger.info(
        "[MARKETPLACE] User '%s' forked '%s' (id=%d) → new item '%s' (id=%d)",
        current_user.username, source.name, source.id, clone.name, clone.id,
    )
    return _enrich_item(clone, db)


@router.delete("/items/{item_id}")
def delete_marketplace_item(
    item_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete an item. Only the owner or an admin may delete."""
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")

    _call_infra_undeploy(item, current_user.username if current_user else "system", reason="manual_user_deletion")

    db.delete(item)
    db.commit()
    logger.info(
        "[MARKETPLACE] User '%s' deleted item '%s' (id=%d)",
        current_user.username, item.name, item_id,
    )
    return {"status": "ok"}


@router.post("/usage")
def log_usage(
    req: UsageRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Log an authenticated usage event for a marketplace item."""
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    usage = MarketplaceUsage(
        user_id=current_user.id,
        item_id=req.item_id,
        action=req.action,
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)

    logger.info(
        "[MARKETPLACE] Usage — item '%s' (id=%d) by '%s': %s",
        item.name, req.item_id, current_user.username, req.action,
    )
    return usage.to_dict()


@router.post("/ping")
def public_ping(req: PingRequest, db: Session = Depends(get_db_session)):
    """
    PUBLIC endpoint — no authentication required.

    Agents and MCP servers call this to self-report usage so the portal
    can show accurate call counts and unique user metrics.
    """
    item = (
        db.query(MarketplaceItem)
        .filter(
            MarketplaceItem.name == req.entity_name,
            MarketplaceItem.item_type == req.entity_type,
        )
        .first()
    )

    if not item:
        logger.warning(
            "[MARKETPLACE] /ping — unknown entity '%s' (%s)",
            req.entity_name, req.entity_type,
        )
        raise HTTPException(
            status_code=404,
            detail=f"No marketplace item found with name '{req.entity_name}' and type '{req.entity_type}'.",
        )

    usage = MarketplaceUsage(
        user_id=None,
        user_identifier=req.user_identifier,
        item_id=item.id,
        action=req.action,
    )
    db.add(usage)
    db.commit()

    logger.info(
        "[MARKETPLACE] Public ping — item '%s' (id=%d), caller='%s', action='%s'",
        item.name, item.id, req.user_identifier or "anonymous", req.action,
    )
    return {"status": "ok", "item_id": item.id, "item_name": item.name}


# ─── Background TTL Expiry Task ───────────────────────────────────────────────

def _call_infra_undeploy(item: MarketplaceItem, owner_username: str = "system", reason: str = "ttl_expired") -> None:
    """Log and stub the infra undeploy call."""
    infra = _infra_url()
    if infra:
        logger.info(
            "[MARKETPLACE] TODO: DELETE %s/api/infra/deploy/%d owner=%s reason=%s",
            infra, item.id, owner_username, reason,
        )
        # TODO: uncomment when infra is ready
        # http_requests.delete(
        #     f"{infra}/api/infra/deploy/{item.id}",
        #     json={"owner_username": owner_username, "reason": reason},
        #     timeout=10,
        # )


def _run_ttl_expiry_sync() -> int:
    """
    Synchronous TTL check — finds expired dev deployments and removes them.
    Intended to run from the async background loop every 24 hours.
    """
    db: Session = SessionLocal()
    deleted = 0
    try:
        now = datetime.now(timezone.utc)
        deployed_dev_items = (
            db.query(MarketplaceItem)
            .filter(
                MarketplaceItem.deployment_status == "DEPLOYED",
                MarketplaceItem.environment == "dev",
                MarketplaceItem.deployed_at.isnot(None),
                MarketplaceItem.ttl_days.isnot(None),
            )
            .all()
        )

        for item in deployed_dev_items:
            deployed_at = (
                item.deployed_at.replace(tzinfo=timezone.utc)
                if item.deployed_at.tzinfo is None
                else item.deployed_at
            )
            elapsed_days = (now - deployed_at).days
            if elapsed_days >= item.ttl_days:
                logger.info(
                    "[MARKETPLACE] TTL expired — deleting '%s' (id=%d, deployed=%s, ttl=%dd)",
                    item.name, item.id, item.deployed_at.isoformat(), item.ttl_days,
                )
                _call_infra_undeploy(item, reason="ttl_expired")
                db.delete(item)
                deleted += 1

        if deleted:
            db.commit()
            logger.info("[MARKETPLACE] TTL cleanup — removed %d expired item(s).", deleted)
        else:
            logger.debug("[MARKETPLACE] TTL cleanup — no expired items.")
    except Exception as exc:
        db.rollback()
        logger.error("[MARKETPLACE] TTL cleanup error: %s", exc, exc_info=True)
    finally:
        db.close()

    return deleted


async def run_ttl_expiry_cleanup():
    """
    Async loop that runs the TTL expiry check every 24 hours.
    Started from client.py via asyncio.create_task().
    """
    logger.info("[MARKETPLACE] TTL expiry background task started (interval=24h).")
    while True:
        await asyncio.sleep(86_400)  # 24 hours
        try:
            _run_ttl_expiry_sync()
        except Exception as exc:
            logger.error("[MARKETPLACE] TTL background task error: %s", exc, exc_info=True)


# ─── Mock Data Seeding ───────────────────────────────────────────────────────

_AVATAR_BASE = "https://api.dicebear.com/7.x/bottts/svg"

def _seed_mock_data(db: Session) -> None:
    """Seed rich mock data so the UI is immediately testable on a fresh DB."""
    first_user = db.query(User).first()
    if not first_user:
        logger.warning("[MARKETPLACE] Cannot seed — no users in DB yet.")
        return

    owner_id = first_user.id
    now = datetime.now(timezone.utc)

    items_to_add = [
        MarketplaceItem(
            name="Data Analysis Agent",
            description="Analyzes complex datasets and returns natural language summaries with statistical insights, trend detection, and anomaly flagging.",
            item_type="agent", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=DataAgent&backgroundColor=b6e3f4",
            bitbucket_repo="https://bitbucket.company.internal/projects/AI/repos/data-agent",
            how_to_use="Ask: 'summarize the latest sales data' or 'find anomalies in the weekly report'.",
            url_to_connect="http://data-agent.release.svc.cluster.local",
            tools_exposed=[], deployment_status="DEPLOYED", version="2.1.0",
            environment="release", chart_name="data-analysis-agent", chart_version="2.1.0",
            ttl_days=None, deployed_at=now - timedelta(days=5),
        ),
        MarketplaceItem(
            name="Jira Integration MCP",
            description="Exposes tools to create, update, search, and comment on Jira issues directly from any LLM chat session or portal workflow.",
            item_type="mcp_server", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=JiraMCP&backgroundColor=c0aede",
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/jira-mcp",
            how_to_use="Enable in Research tab. Say 'create a P1 bug for the login failure' or 'list open tickets for sprint 42'.",
            url_to_connect="http://jira-mcp.mcp-gateway.company.internal",
            tools_exposed=[{"name": "create_ticket"}, {"name": "update_ticket"}, {"name": "search_tickets"}],
            deployment_status="DEPLOYED", version="2.0.1", environment="release",
            chart_name="jira-integration-mcp", chart_version="2.0.1",
            ttl_days=None, deployed_at=now - timedelta(days=30),
        ),
        MarketplaceItem(
            name="K8s Ops Agent",
            description="Monitors Kubernetes cluster health, surfaces failing pods, and can apply Helm rollbacks on command — your AI SRE companion.",
            item_type="agent", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=K8sAgent&backgroundColor=d1f4cc",
            bitbucket_repo="https://bitbucket.company.internal/projects/OPS/repos/k8s-agent",
            how_to_use="Ask 'check the prod cluster', 'list failing pods in namespace X', or 'roll back payments to v1.3'.",
            url_to_connect="http://k8s-agent.dev.svc.cluster.local",
            tools_exposed=[], deployment_status="DEPLOYED", version="0.9.4",
            environment="dev", chart_name="k8s-ops-agent", chart_version="0.9.4",
            # 8 days ago → only 2 days left on a 10-day TTL (shows red warning)
            ttl_days=10, deployed_at=now - timedelta(days=8),
        ),
        MarketplaceItem(
            name="GitHub Actions MCP",
            description="Trigger workflows, inspect run logs, download artifacts, and manage GitHub Actions pipelines from natural language.",
            item_type="mcp_server", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=GithubMCP&backgroundColor=ffd5dc",
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/gh-actions-mcp",
            how_to_use="Say 'trigger the nightly build' or 'show last 5 failed CI runs for the backend repo'.",
            url_to_connect="",
            tools_exposed=[{"name": "trigger_workflow"}, {"name": "list_runs"}, {"name": "get_run_logs"}],
            deployment_status="BUILT", version="1.0.0",
            environment="dev", chart_name=None, chart_version=None,
            ttl_days=10, deployed_at=None,
        ),
        MarketplaceItem(
            name="Vault Secrets MCP",
            description="Securely fetches secrets from HashiCorp Vault and injects them into your workflows — no more hardcoded credentials.",
            item_type="mcp_server", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=VaultMCP&backgroundColor=fffdd0",
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/vault-mcp",
            how_to_use="Ask 'get the DB password for prod' or 'rotate the API keys for service X'.",
            url_to_connect="http://vault-mcp.dev.svc.cluster.local",
            tools_exposed=[{"name": "get_secret"}, {"name": "rotate_secret"}],
            deployment_status="DEPLOYED", version="1.3.0",
            environment="dev", chart_name="vault-secrets-mcp", chart_version="1.3.0",
            # 6 days ago → 4 days left (orange warning)
            ttl_days=10, deployed_at=now - timedelta(days=6),
        ),
        MarketplaceItem(
            name="Slack Notifier Agent",
            description="Sends intelligent notifications, summaries, and alerts to Slack channels based on events across your systems.",
            item_type="agent", owner_id=owner_id,
            icon=f"{_AVATAR_BASE}?seed=SlackAgent&backgroundColor=e0c3fc",
            bitbucket_repo="https://bitbucket.company.internal/projects/AI/repos/slack-agent",
            how_to_use="Ask 'send a daily standup summary to #engineering' or 'alert #on-call about this incident'.",
            url_to_connect="",
            tools_exposed=[], deployment_status="BUILT", version="1.1.0",
            environment="dev", chart_name=None, chart_version=None,
            ttl_days=10, deployed_at=None,
        ),
    ]

    try:
        for item in items_to_add:
            db.add(item)
        db.flush()

        jira = next(i for i in items_to_add if i.name == "Jira Integration MCP")
        data = next(i for i in items_to_add if i.name == "Data Analysis Agent")
        k8s = next(i for i in items_to_add if i.name == "K8s Ops Agent")

        for record in [
            MarketplaceUsage(user_id=owner_id, item_id=jira.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira.id, action="deploy"),
            MarketplaceUsage(user_id=owner_id, item_id=data.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=data.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=k8s.id, action="call"),
        ]:
            db.add(record)

        db.commit()
        logger.info("[MARKETPLACE] Seeded %d mock items.", len(items_to_add))
    except Exception as exc:
        db.rollback()
        logger.warning("[MARKETPLACE] Seeding failed: %s", exc)
