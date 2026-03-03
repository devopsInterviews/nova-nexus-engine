"""
Marketplace API routes.

Handles the full lifecycle of AI Agents and MCP Servers:
  CREATE → BUILD → DEPLOY (dev / release) → DELETE

Also provides:
  - Public /ping endpoint for agents/MCP servers to self-report calls (no auth).
  - GET /chart-versions for fetching available Helm chart versions from Artifactory.
  - POST /items/{id}/clone  for forking a build into a new independent deployment.
  - Background TTL expiry task (started from client.py).
  - GET /config  so the frontend can read server-side limits without hard-coding them.
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
from app.services.artifactory_client import get_marketplace_chart_versions

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
    url_to_connect: Optional[str] = None
    tools_exposed: Optional[List[Dict[str, Any]]] = None


class BuildRequest(BaseModel):
    item_id: int


class DeployRequest(BaseModel):
    item_id: int
    environment: str        # 'dev' or 'release'
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


# ─── Helper: compute ttl_remaining_days from an item dict ────────────────────
# (also available via MarketplaceItem.to_dict(), kept here for explicit seeding)

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
    """Create a new Agent or MCP Server. Enforces per-user creation limits."""
    # Enforce limits
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
                detail=f"You have reached the maximum number of agents ({MARKETPLACE_MAX_AGENTS_PER_USER}).",
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
                detail=f"You have reached the maximum number of MCP servers ({MARKETPLACE_MAX_MCP_PER_USER}).",
            )

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
        environment="dev",
        ttl_days=MARKETPLACE_DEV_TTL_DAYS,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' created %s '%s' (id=%d)",
        current_user.username, item.item_type, item.name, item.id,
    )
    return _enrich_item(item, db)


@router.post("/build")
def build_marketplace_item(
    req: BuildRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Transition item status from CREATED → BUILT.

    Triggers an infra API call (commented out until the infra team builds it).
    """
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to build this item")

    prev_status = item.deployment_status
    item.deployment_status = "BUILT"
    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' triggered build for '%s' (id=%d): %s → BUILT",
        current_user.username, item.name, item.id, prev_status,
    )

    # ── Infra hook (uncomment when infrastructure is ready) ──────────────────
    infra = _infra_url()
    if infra:
        try:
            # TODO: uncomment when infra is ready
            # http_requests.post(f"{infra}/api/infra/build", json={
            #     "entity_name": item.name,
            #     "entity_type": item.item_type,
            #     "description": item.description,
            #     "owner_username": current_user.username,
            #     "template_type": "python_fastapi",
            #     "bitbucket_project": "AI_AGENTS",
            # }, timeout=10)
            pass
        except Exception as exc:
            logger.warning("[MARKETPLACE] Could not reach infra build endpoint: %s", exc)
    # ─────────────────────────────────────────────────────────────────────────

    return {"status": "ok", "message": "Build completed", "item": _enrich_item(item, db)}


@router.post("/deploy")
def deploy_marketplace_item(
    req: DeployRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Deploy an item to dev or release.

    Creates a deployment record in the DB (status → DEPLOYED, stores chart_version,
    deployed_at, and ttl_days for dev).  The actual Helm deploy call to infra is
    stubbed out until the infra team is ready.
    """
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to deploy this item")
    if item.deployment_status not in ("BUILT", "DEPLOYED"):
        raise HTTPException(
            status_code=400,
            detail="Item must be in BUILT or DEPLOYED status before deploying.",
        )

    item.deployment_status = "DEPLOYED"
    item.environment = req.environment
    item.chart_version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None

    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] User '%s' deployed '%s' (id=%d) to %s with chart version %s",
        current_user.username, item.name, item.id, req.environment, req.chart_version,
    )

    # ── Infra hook (uncomment when infrastructure is ready) ──────────────────
    infra = _infra_url()
    if infra:
        try:
            # TODO: uncomment when infra is ready
            # http_requests.post(f"{infra}/api/infra/deploy", json={
            #     "entity_name": item.name,
            #     "entity_type": item.item_type,
            #     "chart_name": f"{item.name}-chart",
            #     "chart_version": req.chart_version,
            #     "owner_username": current_user.username,
            #     "target_environment": req.environment,
            #     "ttl_days": MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None,
            #     "quota_profile": "standard",
            #     "tools_exposed": [t.get("name") for t in (item.tools_exposed or [])],
            # }, timeout=10)
            pass
        except Exception as exc:
            logger.warning("[MARKETPLACE] Could not reach infra deploy endpoint: %s", exc)
    # ─────────────────────────────────────────────────────────────────────────

    return {"status": "ok", "message": f"Deployed to {req.environment}", "item": _enrich_item(item, db)}


@router.post("/items/{item_id}/clone")
def clone_marketplace_item(
    item_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fork an existing BUILT or DEPLOYED item into a fresh copy owned by the
    current user. The clone starts with BUILT status so it can be deployed
    independently to any environment (e.g. two dev instances + one release from
    the same build template).
    """
    source = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source item not found")
    if source.deployment_status not in ("BUILT", "DEPLOYED"):
        raise HTTPException(
            status_code=400, detail="Only BUILT or DEPLOYED items can be cloned."
        )

    # Check limits for the cloning user
    if source.item_type == "agent":
        user_count = (
            db.query(MarketplaceItem)
            .filter_by(owner_id=current_user.id, item_type="agent")
            .count()
        )
        if user_count >= MARKETPLACE_MAX_AGENTS_PER_USER:
            raise HTTPException(
                status_code=429,
                detail=f"Agent limit reached ({MARKETPLACE_MAX_AGENTS_PER_USER}).",
            )

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
        chart_version=source.chart_version,
        ttl_days=MARKETPLACE_DEV_TTL_DAYS,
        deployed_at=None,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    logger.info(
        "[MARKETPLACE] User '%s' cloned '%s' (id=%d) → new item '%s' (id=%d)",
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

    _call_infra_undeploy(item, reason="manual_user_deletion")

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
        "[MARKETPLACE] Usage logged — item '%s' (id=%d) by '%s': %s",
        item.name, req.item_id, current_user.username, req.action,
    )
    return usage.to_dict()


@router.post("/ping")
def public_ping(req: PingRequest, db: Session = Depends(get_db_session)):
    """
    PUBLIC endpoint — no authentication required.

    Agents and MCP servers call this to self-report usage.  The system matches
    the entity by name and type, then writes a row to marketplace_usage so
    the portal can show accurate call counts and unique user metrics.
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
            "[MARKETPLACE] /ping received for unknown entity '%s' (%s)",
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


@router.get("/chart-versions")
def get_chart_versions(
    environment: str = "dev",
    chart_name: str = "marketplace-entity",
):
    """
    Return available Helm chart versions from Artifactory for the given environment.

    The frontend calls this when the user opens the Deploy dialog so they can
    select the exact chart version to deploy.

    Query params:
        environment  — 'dev' or 'release'
        chart_name   — Helm chart name (defaults to generic 'marketplace-entity')
    """
    versions, error = get_marketplace_chart_versions(chart_name, environment)
    if error:
        logger.warning(
            "[MARKETPLACE] chart-versions fetch warning (env=%s, chart=%s): %s",
            environment, chart_name, error,
        )
    return {"environment": environment, "chart_name": chart_name, "versions": versions}


# ─── Background TTL Expiry Task ───────────────────────────────────────────────

def _call_infra_undeploy(item: MarketplaceItem, reason: str = "ttl_expired") -> None:
    """Fire-and-forget infra undeploy call (stubbed until infra is ready)."""
    infra = _infra_url()
    if infra:
        try:
            # TODO: uncomment when infra is ready
            # http_requests.delete(
            #     f"{infra}/api/infra/deploy/{item.id}",
            #     json={"owner_username": item.owner.username if item.owner else "system", "reason": reason},
            #     timeout=10,
            # )
            pass
        except Exception as exc:
            logger.warning("[MARKETPLACE] Could not reach infra undeploy endpoint: %s", exc)


def _run_ttl_expiry_sync() -> int:
    """
    Synchronous TTL check.  Runs in a background thread / async task.

    Finds all DEPLOYED dev items whose ``deployed_at + ttl_days`` has passed,
    calls the infra undeploy hook, then removes them from the DB.

    Returns:
        Number of items expired and deleted.
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
                    "[MARKETPLACE] TTL expired — deleting item '%s' (id=%d, deployed=%s, ttl=%d days)",
                    item.name, item.id, item.deployed_at.isoformat(), item.ttl_days,
                )
                _call_infra_undeploy(item, reason="ttl_expired")
                db.delete(item)
                deleted += 1

        if deleted:
            db.commit()
            logger.info("[MARKETPLACE] TTL cleanup complete — removed %d expired item(s).", deleted)
        else:
            logger.debug("[MARKETPLACE] TTL cleanup complete — no expired items found.")
    except Exception as exc:
        db.rollback()
        logger.error("[MARKETPLACE] TTL cleanup error: %s", exc, exc_info=True)
    finally:
        db.close()

    return deleted


async def run_ttl_expiry_cleanup():
    """
    Async background loop that runs the TTL expiry check every 24 hours.
    Start this with ``asyncio.create_task(run_ttl_expiry_cleanup())`` in the
    FastAPI startup event.
    """
    logger.info("[MARKETPLACE] TTL expiry background task started (interval=24h).")
    while True:
        await asyncio.sleep(86_400)  # 24 hours
        try:
            _run_ttl_expiry_sync()
        except Exception as exc:
            logger.error("[MARKETPLACE] TTL background task error: %s", exc, exc_info=True)


# ─── Mock Data Seeding ───────────────────────────────────────────────────────

_MOCK_AGENT_ICON = (
    "https://api.dicebear.com/7.x/bottts/svg?seed=DataAgent&backgroundColor=b6e3f4"
)
_MOCK_JIRA_ICON = (
    "https://api.dicebear.com/7.x/bottts/svg?seed=JiraMCP&backgroundColor=c0aede"
)
_MOCK_K8S_ICON = (
    "https://api.dicebear.com/7.x/bottts/svg?seed=K8sAgent&backgroundColor=d1f4cc"
)
_MOCK_GITHUB_ICON = (
    "https://api.dicebear.com/7.x/bottts/svg?seed=GithubMCP&backgroundColor=ffd5dc"
)


def _seed_mock_data(db: Session) -> None:
    """Seed rich mock data so the UI is immediately testable on a fresh DB."""
    first_user = db.query(User).first()
    if not first_user:
        logger.warning("[MARKETPLACE] Cannot seed mock data — no users in DB yet.")
        return

    owner_id = first_user.id
    now = datetime.now(timezone.utc)

    items_to_add = [
        # 1 — Agent (BUILT, dev)
        MarketplaceItem(
            name="Data Analysis Agent",
            description=(
                "Analyzes complex datasets using pandas and returns natural language summaries "
                "with statistical insights, trend detection, and anomaly flagging."
            ),
            item_type="agent",
            owner_id=owner_id,
            icon=_MOCK_AGENT_ICON,
            bitbucket_repo="https://bitbucket.company.internal/projects/AI/repos/data-agent",
            how_to_use=(
                "Call this agent with a reference to a dataset or SQL query. "
                "Ask it to 'summarize the latest sales data' or 'find anomalies in the weekly report'."
            ),
            url_to_connect="",
            tools_exposed=[],
            deployment_status="BUILT",
            version="1.2.0",
            environment="dev",
            chart_version=None,
            ttl_days=MARKETPLACE_DEV_TTL_DAYS,
            deployed_at=None,
        ),
        # 2 — MCP Server (DEPLOYED, release)
        MarketplaceItem(
            name="Jira Integration MCP",
            description=(
                "Exposes tools to create, update, search, and comment on Jira issues "
                "directly from the portal or any LLM chat session."
            ),
            item_type="mcp_server",
            owner_id=owner_id,
            icon=_MOCK_JIRA_ICON,
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/jira-mcp",
            how_to_use=(
                "Enable this MCP in the Research tab to let the LLM manage your Jira board. "
                "Available tools: create_ticket, update_ticket, search_tickets, add_comment."
            ),
            url_to_connect="http://jira-mcp.mcp-gateway.company.internal",
            tools_exposed=[
                {"name": "create_ticket"},
                {"name": "update_ticket"},
                {"name": "search_tickets"},
                {"name": "add_comment"},
            ],
            deployment_status="DEPLOYED",
            version="2.0.1",
            environment="release",
            chart_version="2.0.1",
            ttl_days=None,
            deployed_at=now,
        ),
        # 3 — Agent (DEPLOYED, dev) — close to expiry for visual demo
        MarketplaceItem(
            name="K8s Ops Agent",
            description=(
                "Monitors Kubernetes cluster health, surfaces failing pods, "
                "suggests remediation steps, and can apply Helm rollbacks on command."
            ),
            item_type="agent",
            owner_id=owner_id,
            icon=_MOCK_K8S_ICON,
            bitbucket_repo="https://bitbucket.company.internal/projects/OPS/repos/k8s-agent",
            how_to_use=(
                "Ask this agent to 'check the prod cluster', 'list failing pods in namespace X', "
                "or 'roll back the payments deployment to version 1.3'."
            ),
            url_to_connect="http://k8s-agent.dev.svc.cluster.local",
            tools_exposed=[],
            deployment_status="DEPLOYED",
            version="0.9.4",
            environment="dev",
            chart_version="0.9.4",
            ttl_days=MARKETPLACE_DEV_TTL_DAYS,
            # Deployed 8 days ago — only 2 days remaining when TTL is 10, shows warning
            deployed_at=now - timedelta(days=8),
        ),
        # 4 — MCP Server (CREATED, dev)
        MarketplaceItem(
            name="GitHub Actions MCP",
            description=(
                "Provides tools to trigger GitHub Actions workflows, list run statuses, "
                "download artifacts, and inspect workflow logs."
            ),
            item_type="mcp_server",
            owner_id=owner_id,
            icon=_MOCK_GITHUB_ICON,
            bitbucket_repo="https://bitbucket.company.internal/projects/MCP/repos/gh-actions-mcp",
            how_to_use=(
                "Enable in Research tab. Say 'trigger the nightly build workflow' or "
                "'show me the last 5 failed CI runs for the backend repo'."
            ),
            url_to_connect="",
            tools_exposed=[
                {"name": "trigger_workflow"},
                {"name": "list_runs"},
                {"name": "get_run_logs"},
            ],
            deployment_status="CREATED",
            version="1.0.0",
            environment="dev",
            chart_version=None,
            ttl_days=MARKETPLACE_DEV_TTL_DAYS,
            deployed_at=None,
        ),
    ]

    try:
        for item in items_to_add:
            db.add(item)
        db.flush()  # get IDs without committing

        # Add usage records for the Jira MCP and K8s Agent
        jira_item = next(i for i in items_to_add if i.name == "Jira Integration MCP")
        k8s_item = next(i for i in items_to_add if i.name == "K8s Ops Agent")

        usage_records = [
            MarketplaceUsage(user_id=owner_id, item_id=jira_item.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira_item.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira_item.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=jira_item.id, action="deploy"),
            MarketplaceUsage(user_id=owner_id, item_id=k8s_item.id, action="call"),
            MarketplaceUsage(user_id=owner_id, item_id=k8s_item.id, action="call"),
        ]
        for u in usage_records:
            db.add(u)

        db.commit()
        logger.info("[MARKETPLACE] Mock data seeded successfully (%d items).", len(items_to_add))
    except Exception as exc:
        db.rollback()
        logger.warning("[MARKETPLACE] Could not seed mock data: %s", exc)
