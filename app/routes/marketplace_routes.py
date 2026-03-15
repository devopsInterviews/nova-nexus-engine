"""
Marketplace API routes.

Entity lifecycle: CREATE (= BUILT) → DEPLOY → REDEPLOY / DELETE

Additional endpoints:
  GET  /config            — server-side limits for the frontend
  GET  /charts            — list available Helm chart names from Artifactory
  GET  /chart-versions    — list versions for a specific chart
  POST /ping              — PUBLIC, no auth; agents/MCP servers self-report usage
                            See PingRequest for full docs and curl examples.
  POST /items/{id}/clone  — fork a deployed item for a parallel deployment
  POST /redeploy          — undeploy then re-deploy with a new chart/version
"""

import os
import logging
import threading
import time
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
INFRA_CHARTS_API_SERVER: Optional[str] = os.getenv("INFRA_CHARTS_API_SERVER")

# 5-minute timeout for infra API calls (deploy/delete can take a while)
INFRA_API_TIMEOUT_SECONDS: int = 300

logger.info(
    "[MARKETPLACE] Config — max_agents=%d, max_mcp=%d, dev_ttl=%d days, infra_api=%s",
    MARKETPLACE_MAX_AGENTS_PER_USER,
    MARKETPLACE_MAX_MCP_PER_USER,
    MARKETPLACE_DEV_TTL_DAYS,
    INFRA_CHARTS_API_SERVER or "not set",
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
    # Public DNS / URL that users will interact with; forwarded in values_override at deploy time
    public_connection_url: Optional[str] = None


class ItemUpdate(BaseModel):
    """Partial update — only provided fields will be changed."""
    name: Optional[str] = None
    description: Optional[str] = None
    how_to_use: Optional[str] = None
    bitbucket_repo: Optional[str] = None
    icon: Optional[str] = None


class CallRequest(BaseModel):
    """Payload for the Run/Call proxy endpoint."""
    prompt: str
    user_identifier: Optional[str] = None  # overrides current_user.username if set


class DeployRequest(BaseModel):
    item_id: int
    environment: str        # 'dev' or 'release'
    chart_name: str = ""    # Artifactory chart name
    chart_version: str = "latest"
    # Optional Helm values overrides supplied by the user in the deploy dialog
    values_override: Optional[Dict[str, Any]] = None


class RedeployRequest(BaseModel):
    item_id: int
    environment: str        # 'dev' or 'release'
    chart_name: str = ""    # New Artifactory chart name
    chart_version: str = "latest"
    # Optional Helm values overrides supplied by the user in the redeploy dialog
    values_override: Optional[Dict[str, Any]] = None


class UsageRequest(BaseModel):
    item_id: int
    action: str             # 'call', 'install', 'deploy'


class PingRequest(BaseModel):
    """
    Public self-report payload sent by a running Agent or MCP Server.
    No authentication is required for this endpoint.

    ─── Usage Tracking API — /api/marketplace/ping ───────────────────────────
    This is a PUBLIC endpoint (no JWT token required). Agents and MCP Servers
    should call it on every invocation to report usage to the portal.

    Request body (JSON):
        entity_name     (str, required)  — exact name as registered in the marketplace
        entity_type     (str, required)  — "agent" or "mcp_server"
        user_identifier (str, optional)  — username / email of the person triggering the call
        action          (str, optional)  — event type; defaults to "call"
                                           common values: "call", "tool_use"
        tool_name       (str, optional)  — for MCP servers: the specific tool that was invoked
                                           (e.g. "search_jira", "create_ticket")

    ─── Example: Agent call ──────────────────────────────────────────────────
    curl -X POST https://portal.company.internal/api/marketplace/ping \\
      -H "Content-Type: application/json" \\
      -d '{
            "entity_name": "My Research Agent",
            "entity_type": "agent",
            "user_identifier": "john.doe@company.com",
            "action": "call"
          }'

    ─── Example: MCP Server tool invocation ──────────────────────────────────
    curl -X POST https://portal.company.internal/api/marketplace/ping \\
      -H "Content-Type: application/json" \\
      -d '{
            "entity_name": "Jira Integration MCP",
            "entity_type": "mcp_server",
            "user_identifier": "jane.smith",
            "action": "tool_use",
            "tool_name": "create_ticket"
          }'

    ─── Success response (200 OK) ────────────────────────────────────────────
    {
      "status": "ok",
      "item_id": 42,
      "item_name": "Jira Integration MCP"
    }

    ─── Error responses ──────────────────────────────────────────────────────
    404  entity_name + entity_type combo not found in the marketplace
    422  missing / invalid required fields (FastAPI validation)
    ──────────────────────────────────────────────────────────────────────────
    """
    entity_name: str
    entity_type: str                    # 'agent' or 'mcp_server'
    user_identifier: Optional[str] = None  # optional caller username / email
    action: str = "call"               # 'call' for agents, 'tool_use' for MCP tool invocations
    tool_name: Optional[str] = None    # MCP only: the specific tool that was invoked


# ─── Helper: build infra API base URL ────────────────────────────────────────

def _infra_url() -> Optional[str]:
    if not INFRA_CHARTS_API_SERVER:
        return None
    srv = INFRA_CHARTS_API_SERVER
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
        public_connection_url=req.public_connection_url or None,
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

    logger.info(
        "[MARKETPLACE] User '%s' deploying '%s' (id=%d) → env=%s chart=%s@%s",
        current_user.username, item.name, item.id,
        req.environment, req.chart_name, req.chart_version,
    )

    # ── Call infra API ───────────────────────────────────────────────────────
    infra = _infra_url()
    public_url_from_infra: Optional[str] = None

    if infra:
        # Merge the item's pre-configured public_connection_url (if any) with
        # user-provided values_override entries. User entries win on conflicts.
        merged_overrides: Dict[str, Any] = {}
        if item.public_connection_url:
            merged_overrides["public_connection_url"] = item.public_connection_url
        if req.values_override:
            merged_overrides.update(req.values_override)

        infra_payload: Dict[str, Any] = {
            "entity_name": item.name,
            "entity_type": item.item_type,
            "chart_name": req.chart_name or item.name,
            "chart_version": req.chart_version,
            "owner_username": current_user.username,
            "target_environment": req.environment,
        }
        if merged_overrides:
            infra_payload["values_override"] = merged_overrides

        try:
            logger.info(
                "[MARKETPLACE] POST %s/api/infra/deploy — payload=%s",
                infra, infra_payload,
            )
            infra_resp = http_requests.post(
                f"{infra}/api/infra/deploy",
                json=infra_payload,
                timeout=INFRA_API_TIMEOUT_SECONDS,
            )
            infra_resp.raise_for_status()
            infra_data = infra_resp.json()
            logger.info(
                "[MARKETPLACE] Infra deploy response for '%s': %s", item.name, infra_data
            )
            public_url_from_infra = infra_data.get("public_connection_url")
        except http_requests.exceptions.Timeout:
            logger.error("[MARKETPLACE] Infra deploy timed out for '%s' (id=%d)", item.name, item.id)
            raise HTTPException(
                status_code=504,
                detail="Infra API did not respond within 5 minutes. Please try again.",
            )
        except http_requests.exceptions.ConnectionError as exc:
            logger.error("[MARKETPLACE] Infra deploy connection error for '%s': %s", item.name, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach the infra API server: {exc}",
            )
        except http_requests.exceptions.HTTPError as exc:
            error_body: str = ""
            try:
                error_body = exc.response.json().get("detail") or exc.response.text
            except Exception:
                error_body = str(exc)
            logger.error(
                "[MARKETPLACE] Infra deploy HTTP error for '%s': %s — %s",
                item.name, exc, error_body,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Infra API returned an error: {error_body}",
            )
        except Exception as exc:
            logger.error(
                "[MARKETPLACE] Unexpected infra deploy error for '%s': %s", item.name, exc, exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Unexpected error calling infra API: {exc}")
    # ────────────────────────────────────────────────────────────────────────

    item.deployment_status = "DEPLOYED"
    item.environment = req.environment
    item.chart_name = req.chart_name or item.name
    item.chart_version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None
    if public_url_from_infra:
        item.url_to_connect = public_url_from_infra

    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "message": f"Deployed to {req.environment}",
        "item": _enrich_item(item, db),
        "connection_url": public_url_from_infra,
    }


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

    logger.info(
        "[MARKETPLACE] User '%s' redeploying '%s' (id=%d): %s@%s/%s → %s@%s/%s",
        current_user.username, item.name, item.id,
        old_chart, old_version, old_env,
        req.chart_name, req.chart_version, req.environment,
    )

    # ── Call infra API ───────────────────────────────────────────────────────
    infra = _infra_url()
    public_url_from_infra: Optional[str] = None

    if infra:
        # Step 1 — undeploy old deployment
        delete_payload: Dict[str, Any] = {
            "entity_name": item.name,
            "entity_type": item.item_type,
            "owner_username": current_user.username,
            "target_environment": old_env,
        }
        try:
            logger.info(
                "[MARKETPLACE] POST %s/api/infra/delete (redeploy step 1) — payload=%s",
                infra, delete_payload,
            )
            del_resp = http_requests.post(
                f"{infra}/api/infra/delete",
                json=delete_payload,
                timeout=INFRA_API_TIMEOUT_SECONDS,
            )
            del_resp.raise_for_status()
            logger.info("[MARKETPLACE] Infra delete (redeploy) succeeded for '%s'", item.name)
        except http_requests.exceptions.Timeout:
            logger.error("[MARKETPLACE] Infra delete (redeploy) timed out for '%s'", item.name)
            raise HTTPException(status_code=504, detail="Infra API did not respond within 5 minutes (delete step).")
        except http_requests.exceptions.ConnectionError as exc:
            logger.error("[MARKETPLACE] Infra delete (redeploy) connection error: %s", exc)
            raise HTTPException(status_code=502, detail=f"Could not reach the infra API server: {exc}")
        except http_requests.exceptions.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.response.json().get("detail") or exc.response.text
            except Exception:
                error_body = str(exc)
            logger.error("[MARKETPLACE] Infra delete (redeploy) HTTP error: %s — %s", exc, error_body)
            raise HTTPException(status_code=502, detail=f"Infra API error during undeploy: {error_body}")
        except Exception as exc:
            logger.error("[MARKETPLACE] Unexpected infra delete (redeploy) error: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unexpected error calling infra API (delete step): {exc}")

        # Step 2 — deploy new
        merged_overrides: Dict[str, Any] = {}
        if item.public_connection_url:
            merged_overrides["public_connection_url"] = item.public_connection_url
        if req.values_override:
            merged_overrides.update(req.values_override)

        deploy_payload: Dict[str, Any] = {
            "entity_name": item.name,
            "entity_type": item.item_type,
            "chart_name": req.chart_name or item.chart_name or item.name,
            "chart_version": req.chart_version,
            "owner_username": current_user.username,
            "target_environment": req.environment,
        }
        if merged_overrides:
            deploy_payload["values_override"] = merged_overrides

        try:
            logger.info(
                "[MARKETPLACE] POST %s/api/infra/deploy (redeploy step 2) — payload=%s",
                infra, deploy_payload,
            )
            dep_resp = http_requests.post(
                f"{infra}/api/infra/deploy",
                json=deploy_payload,
                timeout=INFRA_API_TIMEOUT_SECONDS,
            )
            dep_resp.raise_for_status()
            infra_data = dep_resp.json()
            logger.info(
                "[MARKETPLACE] Infra redeploy response for '%s': %s", item.name, infra_data
            )
            public_url_from_infra = infra_data.get("public_connection_url")
        except http_requests.exceptions.Timeout:
            logger.error("[MARKETPLACE] Infra deploy (redeploy) timed out for '%s'", item.name)
            raise HTTPException(status_code=504, detail="Infra API did not respond within 5 minutes (deploy step).")
        except http_requests.exceptions.ConnectionError as exc:
            logger.error("[MARKETPLACE] Infra deploy (redeploy) connection error: %s", exc)
            raise HTTPException(status_code=502, detail=f"Could not reach the infra API server: {exc}")
        except http_requests.exceptions.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.response.json().get("detail") or exc.response.text
            except Exception:
                error_body = str(exc)
            logger.error("[MARKETPLACE] Infra deploy (redeploy) HTTP error: %s — %s", exc, error_body)
            raise HTTPException(status_code=502, detail=f"Infra API error during redeploy: {error_body}")
        except Exception as exc:
            logger.error("[MARKETPLACE] Unexpected infra deploy (redeploy) error: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unexpected error calling infra API (deploy step): {exc}")
    # ────────────────────────────────────────────────────────────────────────

    item.environment = req.environment
    item.chart_name = req.chart_name or item.chart_name
    item.chart_version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if req.environment == "dev" else None
    if public_url_from_infra:
        item.url_to_connect = public_url_from_infra

    db.commit()
    db.refresh(item)

    return {
        "status": "ok",
        "message": f"Redeployed to {req.environment}",
        "item": _enrich_item(item, db),
        "connection_url": public_url_from_infra,
    }


@router.post("/items/{item_id}/extend-ttl")
def extend_item_ttl(
    item_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Extend the TTL of a dev-deployed item by resetting its deployed_at timestamp to now.
    This effectively gives it a fresh TTL window equal to the configured dev TTL days.
    Release items (no TTL) are unaffected.
    """
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to extend this item's TTL")
    if item.deployment_status != "DEPLOYED":
        raise HTTPException(status_code=400, detail="Only DEPLOYED items can have their TTL extended")
    if item.environment == "release":
        raise HTTPException(status_code=400, detail="Release deployments have no TTL — nothing to extend")

    item.deployed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    logger.info(
        "[MARKETPLACE] TTL extended for '%s' (id=%d) by '%s' — new expiry in %s days",
        item.name, item.id, current_user.username, item.ttl_days,
    )
    return {"status": "ok", "message": f"TTL extended by {item.ttl_days} days", "item": _enrich_item(item, db)}


@router.patch("/items/{item_id}")
def update_marketplace_item(
    item_id: int,
    req: ItemUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Partially update an item's metadata (name, description, how_to_use,
    bitbucket_repo, icon).  Only the owner or an admin may edit.
    """
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to edit this item")

    changed: List[str] = []
    if req.name is not None and req.name != item.name:
        item.name = req.name;  changed.append("name")
    if req.description is not None and req.description != item.description:
        item.description = req.description;  changed.append("description")
    if req.how_to_use is not None and req.how_to_use != item.how_to_use:
        item.how_to_use = req.how_to_use;  changed.append("how_to_use")
    if req.bitbucket_repo is not None and req.bitbucket_repo != item.bitbucket_repo:
        item.bitbucket_repo = req.bitbucket_repo;  changed.append("bitbucket_repo")
    if req.icon is not None and req.icon != item.icon:
        item.icon = req.icon;  changed.append("icon")

    if not changed:
        logger.info(
            "[MARKETPLACE] PATCH /items/%d by '%s' — no changes detected.",
            item_id, current_user.username,
        )
        return _enrich_item(item, db)

    db.commit()
    db.refresh(item)
    logger.info(
        "[MARKETPLACE] User '%s' updated item '%s' (id=%d) — changed fields: %s",
        current_user.username, item.name, item.id, ", ".join(changed),
    )
    return _enrich_item(item, db)


@router.post("/items/{item_id}/call")
def call_marketplace_item(
    item_id: int,
    req: CallRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Proxy a prompt to a deployed item's connection URL and return the response.

    This allows users to test/interact with a running Agent or MCP Server
    directly from the portal without needing direct cluster access.

    The request body `{"prompt": "...", "user": "username"}` is forwarded to the
    item's `url_to_connect`.  A usage record is written regardless of outcome.
    """
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.deployment_status != "DEPLOYED":
        raise HTTPException(status_code=400, detail="Item is not deployed — deploy it first.")
    if not item.url_to_connect:
        raise HTTPException(
            status_code=400,
            detail="No connection URL set for this item. The URL is assigned by infra after deployment.",
        )

    caller = req.user_identifier or current_user.username
    payload = {"prompt": req.prompt, "user": caller, "item_name": item.name}

    logger.info(
        "[MARKETPLACE] User '%s' calling item '%s' (id=%d) at %s — prompt length=%d",
        current_user.username, item.name, item.id, item.url_to_connect, len(req.prompt),
    )

    result: Any = None
    error_msg: Optional[str] = None
    try:
        response = http_requests.post(
            item.url_to_connect,
            json=payload,
            timeout=30,
            # Internal cluster URLs may use self-signed certs; allow both
            verify=False,
        )
        logger.info(
            "[MARKETPLACE] Call to '%s' returned HTTP %d (%.2fs)",
            item.url_to_connect, response.status_code,
            response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0,
        )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            result = response.json()
        else:
            result = response.text

    except http_requests.exceptions.Timeout:
        error_msg = "Request timed out after 30 seconds."
        logger.warning(
            "[MARKETPLACE] Call to '%s' (item id=%d) timed out.", item.url_to_connect, item.id
        )
    except http_requests.exceptions.ConnectionError as exc:
        error_msg = f"Could not connect to {item.url_to_connect}: {exc}"
        logger.error(
            "[MARKETPLACE] Call connection error for item id=%d: %s", item.id, exc
        )
    except Exception as exc:
        error_msg = f"Unexpected error: {exc}"
        logger.error(
            "[MARKETPLACE] Unexpected call error for item id=%d: %s", item.id, exc, exc_info=True
        )

    # Always log a usage record
    usage = MarketplaceUsage(user_id=current_user.id, item_id=item.id, action="call")
    db.add(usage)
    db.commit()
    logger.info(
        "[MARKETPLACE] Usage record written — item '%s' (id=%d) called by '%s'",
        item.name, item.id, current_user.username,
    )

    if error_msg:
        return {"status": "error", "error": error_msg, "response": None}
    return {"status": "ok", "response": result}


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

    # For deployed items, call infra first — raise on error so user sees the problem
    infra_error = _call_infra_undeploy(
        item,
        owner_username=current_user.username if current_user else "system",
        reason="manual_user_deletion",
        raise_on_error=(item.deployment_status == "DEPLOYED"),
    )
    if infra_error and item.deployment_status != "DEPLOYED":
        # Non-deployed item — infra call is a no-op, but log the warning
        logger.warning(
            "[MARKETPLACE] Infra undeploy warning during delete for '%s' (id=%d): %s",
            item.name, item_id, infra_error,
        )

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

    See the PingRequest docstring above for full usage docs and curl examples.
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
        tool_name=req.tool_name,
    )
    db.add(usage)
    db.commit()

    logger.info(
        "[MARKETPLACE] Public ping — item '%s' (id=%d), caller='%s', action='%s'%s",
        item.name, item.id, req.user_identifier or "anonymous", req.action,
        f", tool='{req.tool_name}'" if req.tool_name else "",
    )
    return {"status": "ok", "item_id": item.id, "item_name": item.name}


# ─── Background TTL Expiry Task ───────────────────────────────────────────────

def _call_infra_undeploy(
    item: MarketplaceItem,
    owner_username: str = "system",
    reason: str = "ttl_expired",
    raise_on_error: bool = False,
) -> Optional[str]:
    """
    Call the infra API to delete/undeploy a running deployment.

    Returns None on success or if infra is not configured.
    Returns an error message string if the call fails and raise_on_error is False.
    Raises HTTPException if raise_on_error is True and the call fails.
    """
    if item.deployment_status != "DEPLOYED":
        return None

    infra = _infra_url()
    if not infra:
        logger.info(
            "[MARKETPLACE] Infra API not configured — skipping undeploy for '%s' (id=%d)",
            item.name, item.id,
        )
        return None

    payload: Dict[str, Any] = {
        "entity_name": item.name,
        "entity_type": item.item_type,
        "owner_username": owner_username,
        "target_environment": item.environment,
    }
    try:
        logger.info(
            "[MARKETPLACE] POST %s/api/infra/delete — entity='%s' reason=%s payload=%s",
            infra, item.name, reason, payload,
        )
        resp = http_requests.post(
            f"{infra}/api/infra/delete",
            json=payload,
            timeout=INFRA_API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        logger.info(
            "[MARKETPLACE] Infra undeploy succeeded for '%s' (id=%d): %s",
            item.name, item.id, resp.json(),
        )
        return None
    except http_requests.exceptions.Timeout:
        msg = "Infra API did not respond within 5 minutes."
        logger.error("[MARKETPLACE] Infra undeploy timed out for '%s' (id=%d)", item.name, item.id)
    except http_requests.exceptions.ConnectionError as exc:
        msg = f"Could not reach the infra API server: {exc}"
        logger.error("[MARKETPLACE] Infra undeploy connection error for '%s' (id=%d): %s", item.name, item.id, exc)
    except http_requests.exceptions.HTTPError as exc:
        try:
            msg = exc.response.json().get("detail") or exc.response.text
        except Exception:
            msg = str(exc)
        logger.error("[MARKETPLACE] Infra undeploy HTTP error for '%s' (id=%d): %s", item.name, item.id, msg)
    except Exception as exc:
        msg = f"Unexpected error: {exc}"
        logger.error("[MARKETPLACE] Unexpected infra undeploy error for '%s' (id=%d): %s", item.name, item.id, exc, exc_info=True)

    if raise_on_error:
        raise HTTPException(status_code=502, detail=f"Infra API error during undeploy: {msg}")
    return msg


# ─── Background TTL Expiry Task ───────────────────────────────────────────────

def _run_ttl_expiry_sync() -> int:
    """
    Deletes DB rows for dev deployments whose TTL has elapsed.
    The infra API server independently tears down the k8s resources on its side;
    this only cleans up our database records.
    """
    db: Session = SessionLocal()
    deleted = 0
    try:
        now = datetime.now(timezone.utc)
        expired_items = (
            db.query(MarketplaceItem)
            .filter(
                MarketplaceItem.deployment_status == "DEPLOYED",
                MarketplaceItem.environment == "dev",
                MarketplaceItem.deployed_at.isnot(None),
                MarketplaceItem.ttl_days.isnot(None),
            )
            .all()
        )

        for item in expired_items:
            deployed_at = (
                item.deployed_at.replace(tzinfo=timezone.utc)
                if item.deployed_at.tzinfo is None
                else item.deployed_at
            )
            if (now - deployed_at).days >= item.ttl_days:
                logger.info(
                    "[MARKETPLACE] TTL expired — removing '%s' (id=%d, deployed=%s, ttl=%dd)",
                    item.name, item.id, item.deployed_at.isoformat(), item.ttl_days,
                )
                db.delete(item)
                deleted += 1

        if deleted:
            db.commit()
            logger.info("[MARKETPLACE] TTL cleanup — removed %d expired item(s) from DB.", deleted)
        else:
            logger.debug("[MARKETPLACE] TTL cleanup — no expired items.")
    except Exception as exc:
        db.rollback()
        logger.error("[MARKETPLACE] TTL cleanup error: %s", exc, exc_info=True)
    finally:
        db.close()

    return deleted


def start_ttl_cleanup_thread() -> threading.Thread:
    """
    Daemon thread that runs a DB-only TTL expiry check every 24 hours.
    Infra handles k8s teardown; this only removes the stale DB rows.
    A daemon thread keeps uvicorn's event loop free so the pod shuts down cleanly.
    """
    def _target() -> None:
        logger.info("[MARKETPLACE] TTL cleanup thread started (interval=24h).")
        while True:
            time.sleep(86_400)
            try:
                _run_ttl_expiry_sync()
            except Exception as exc:
                logger.error("[MARKETPLACE] TTL cleanup thread error: %s", exc, exc_info=True)

    thread = threading.Thread(target=_target, daemon=True, name="marketplace-ttl-cleanup")
    thread.start()
    logger.info("[MARKETPLACE] TTL cleanup daemon thread launched (tid=%s).", thread.ident)
    return thread


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
