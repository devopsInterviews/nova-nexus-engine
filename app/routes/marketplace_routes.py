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

Background threads (started from client.py on application startup):
  start_ttl_cleanup_thread()   — runs every 24 h; removes dev items whose TTL
                                  has elapsed from the DB.
  start_cluster_sync_thread()  — runs every 10 min; calls
                                  GET {INFRA_CHARTS_API_SERVER}/api/infra/deployments
                                  and warns about any DEPLOYED DB item whose Helm
                                  release is no longer present in the cluster.
                                  Deletion is currently disabled (observation-only
                                  mode); see _run_cluster_sync() to enable it.
"""

import os
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db_session
import app.database as _database  # accessed at call-time so SessionLocal is never None
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
MARKETPLACE_TTL_ENABLED: bool = os.getenv("MARKETPLACE_TTL_ENABLED", "false").lower() == "true"
INFRA_CHARTS_API_SERVER: Optional[str] = os.getenv("INFRA_CHARTS_API_SERVER")

# 5-minute timeout for infra API calls (deploy/delete can take a while)
INFRA_API_TIMEOUT_SECONDS: int = 300

# When LOG_LEVEL=DEBUG the full request payload and response body are logged
_DEBUG_INFRA = os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

logger.info(
    "[MARKETPLACE] Config — max_agents=%d, max_mcp=%d, ttl_enabled=%s, dev_ttl=%d days, infra_api=%s",
    MARKETPLACE_MAX_AGENTS_PER_USER,
    MARKETPLACE_MAX_MCP_PER_USER,
    MARKETPLACE_TTL_ENABLED,
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


class ItemUpdate(BaseModel):
    """Partial update — only provided fields will be changed."""
    name: Optional[str] = None
    description: Optional[str] = None
    how_to_use: Optional[str] = None
    bitbucket_repo: Optional[str] = None
    icon: Optional[str] = None


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


class CloneRequest(BaseModel):
    """Optional body for the clone/fork endpoint."""
    fork_name: Optional[str] = None   # desired name for the fork; defaults to "{source} - Fork"


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

_MCP_BASE_HEADERS: Dict[str, str] = {
    "Content-Type": "application/json",
    # MCP spec: client must advertise both formats
    "Accept": "application/json, text/event-stream",
}
_MCP_PROTOCOL_VERSION = "2024-11-05"
_MCP_FETCH_TIMEOUT = 15


def _parse_mcp_response(resp: http_requests.Response, label: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JSON-RPC response from an MCP server.

    Handles both response formats that the MCP streamable-HTTP transport
    may use:
      • application/json   → parsed directly
      • text/event-stream  → body is scanned for 'data:' lines that contain
                             a JSON-RPC object with a 'result' or 'error' key

    Returns the parsed dict, or None if nothing useful was found.
    Logs Content-Type and a body preview unconditionally.
    """
    content_type = resp.headers.get("Content-Type", "")
    logger.info(
        "[MARKETPLACE][MCP-TOOLS] %s → HTTP %d (Content-Type: %s) body: %s",
        label, resp.status_code, content_type, resp.text[:600],
    )

    if "text/event-stream" in content_type:
        import json as _json
        for line in resp.text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload_str = line[len("data:"):].strip()
            if not payload_str:
                continue
            try:
                parsed = _json.loads(payload_str)
                if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                    return parsed
            except ValueError:
                continue
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] %s — SSE body had no parseable JSON-RPC frame.",
            label,
        )
        return None

    try:
        return resp.json()
    except Exception as exc:
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] %s — could not decode JSON body: %s", label, exc,
        )
        return None


def _fetch_mcp_tools(url: str, item_name: str) -> List[Dict[str, Any]]:
    """
    Fetch the tool list from a running MCP server using the MCP
    Streamable-HTTP transport (POST {url}).

    ── Protocol flow ───────────────────────────────────────────────────────────
    Some MCP server implementations require a session to be established before
    they will accept method calls.  We therefore use a two-step flow:

      Step 1 — initialize
        POST {url} with method="initialize".
        If the server returns an Mcp-Session-Id response header we include it
        in all subsequent requests.  If the server returns a JSON-RPC error
        here we still proceed to tools/list — some servers skip initialization.

      Step 2 — notifications/initialized  (fire-and-forget)
        Notify the server that the client is ready.  We do not wait for or
        inspect the response.

      Step 3 — tools/list
        POST {url} with method="tools/list" (and the session header if we
        got one).

    Both application/json and text/event-stream responses are handled at each
    step via _parse_mcp_response().

    Returns a list of {"name": str, "description": str} dicts.
    Returns an empty list on any error — callers treat this as a soft failure
    that never blocks the deploy flow.
    """
    logger.info(
        "[MARKETPLACE][MCP-TOOLS] Starting tool discovery for '%s' → %s",
        item_name, url,
    )

    try:
        # ── Step 1: initialize ───────────────────────────────────────────────
        init_payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "nova-nexus-portal", "version": "1.0"},
            },
        }
        logger.info(
            "[MARKETPLACE][MCP-TOOLS] [1/3] initialize → POST %s", url,
        )
        init_resp = http_requests.post(
            url, json=init_payload, headers=_MCP_BASE_HEADERS,
            timeout=_MCP_FETCH_TIMEOUT,
        )

        # Capture session ID — present when the server requires session binding
        session_id = (
            init_resp.headers.get("Mcp-Session-Id")
            or init_resp.headers.get("mcp-session-id")
        )
        if session_id:
            logger.info(
                "[MARKETPLACE][MCP-TOOLS] Session established: Mcp-Session-Id=%s", session_id,
            )
        else:
            logger.info(
                "[MARKETPLACE][MCP-TOOLS] No Mcp-Session-Id returned — server runs sessionless.",
            )

        request_headers = {**_MCP_BASE_HEADERS}
        if session_id:
            request_headers["Mcp-Session-Id"] = session_id

        init_data = _parse_mcp_response(init_resp, f"[initialize] '{item_name}'")
        if init_data and "error" in init_data:
            logger.warning(
                "[MARKETPLACE][MCP-TOOLS] initialize returned JSON-RPC error for '%s': %s "
                "— proceeding to tools/list anyway.",
                item_name, init_data["error"],
            )

        # ── Step 2: notifications/initialized (fire-and-forget) ─────────────
        try:
            notif_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            logger.info(
                "[MARKETPLACE][MCP-TOOLS] [2/3] notifications/initialized → POST %s", url,
            )
            http_requests.post(
                url, json=notif_payload, headers=request_headers,
                timeout=5,
            )
        except Exception as notif_exc:
            # Non-critical — log and continue
            logger.debug(
                "[MARKETPLACE][MCP-TOOLS] notifications/initialized failed for '%s': %s — continuing.",
                item_name, notif_exc,
            )

        # ── Step 3: tools/list ───────────────────────────────────────────────
        tools_payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        logger.info(
            "[MARKETPLACE][MCP-TOOLS] [3/3] tools/list → POST %s", url,
        )
        tools_resp = http_requests.post(
            url, json=tools_payload, headers=request_headers,
            timeout=_MCP_FETCH_TIMEOUT,
        )
        tools_resp.raise_for_status()

        tools_data = _parse_mcp_response(tools_resp, f"[tools/list] '{item_name}'")
        if tools_data is None:
            logger.warning(
                "[MARKETPLACE][MCP-TOOLS] Could not parse tools/list response for '%s' — "
                "tools_exposed not updated.",
                item_name,
            )
            return []

        if "error" in tools_data:
            logger.warning(
                "[MARKETPLACE][MCP-TOOLS] tools/list JSON-RPC error for '%s': %s — "
                "tools_exposed not updated.",
                item_name, tools_data["error"],
            )
            return []

        tools_raw = tools_data.get("result", {}).get("tools", [])
        tools = [
            {"name": t.get("name", ""), "description": t.get("description", "")}
            for t in tools_raw
            if t.get("name")
        ]
        logger.info(
            "[MARKETPLACE][MCP-TOOLS] ✓ '%s' — %d tool(s) discovered: %s",
            item_name, len(tools), [t["name"] for t in tools],
        )
        return tools

    except http_requests.exceptions.Timeout:
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] TIMEOUT (%ds) for '%s' (url=%s) — "
            "tools_exposed not updated.",
            _MCP_FETCH_TIMEOUT, item_name, url,
        )
    except http_requests.exceptions.ConnectionError as exc:
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] CONNECTION ERROR for '%s' (url=%s): %s — "
            "tools_exposed not updated.",
            item_name, url, exc,
        )
    except http_requests.exceptions.HTTPError as exc:
        raw_body = exc.response.text if exc.response is not None else ""
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] HTTP %d error for '%s' (url=%s) — body: %s — "
            "tools_exposed not updated.",
            exc.response.status_code if exc.response is not None else -1,
            item_name, url, raw_body,
        )
    except Exception as exc:
        logger.warning(
            "[MARKETPLACE][MCP-TOOLS] Unexpected error for '%s' (url=%s): %s — "
            "tools_exposed not updated.",
            item_name, url, exc, exc_info=True,
        )
    return []


def _apply_mcp_url_suffix(url: str, item_type: str) -> str:
    """
    For MCP server deployments the SSE/streamable-HTTP endpoint lives at /mcp.
    Append the suffix when the URL does not already end with it.

    Examples:
      "http://host:8080"      + mcp_server → "http://host:8080/mcp"
      "http://host:8080/"     + mcp_server → "http://host:8080/mcp"
      "http://host:8080/mcp"  + mcp_server → "http://host:8080/mcp"  (no-op)
      "http://host:8080"      + agent      → "http://host:8080"       (no-op)
    """
    if item_type != "mcp_server":
        return url
    base = url.rstrip("/")
    if not base.endswith("/mcp"):
        base = f"{base}/mcp"
    return base


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
        "ttl_enabled": MARKETPLACE_TTL_ENABLED,
    }


@router.get("/items")
def get_marketplace_items(db: Session = Depends(get_db_session)):
    """Fetch all marketplace items with usage stats."""
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
    # Global duplicate-name check (case-insensitive, across all users and types).
    # Two items with the same name would produce identical Helm release names and
    # cause silent infra conflicts, so we reject at creation time.
    existing = (
        db.query(MarketplaceItem)
        .filter(func.lower(MarketplaceItem.name) == req.name.strip().lower())
        .first()
    )
    if existing:
        logger.warning(
            "[MARKETPLACE] Duplicate name rejected — '%s' already exists (id=%d, owner=%s)",
            req.name, existing.id, existing.owner.username if existing.owner else "unknown",
        )
        raise HTTPException(
            status_code=409,
            detail=f"An agent or MCP server named \"{req.name.strip()}\" already exists."
                   " Choose a different name.",
        )

    if not current_user.is_admin:
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
        version="",
        environment="dev",
        ttl_days=MARKETPLACE_DEV_TTL_DAYS if MARKETPLACE_TTL_ENABLED else None,
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


@router.get("/suggest-chart")
def suggest_chart_for_item(item_name: str, environment: str = "dev"):
    """
    Suggest the Helm chart whose name most closely matches the given item name.

    Used by the deploy dialog to pre-fill the chart filter field.
    Returns empty (None) rather than guessing when the decision is ambiguous.

    ── Scoring ────────────────────────────────────────────────────────────────
    Both names are first sanitised into lowercase hyphen-slugs using
    _normalize_name_for_helm so that "My Jira MCP!" and "my-jira-mcp" compare
    identically.

      Step 1 — Token Dice coefficient
        score = 2 × |A ∩ B| / (|A| + |B|)
        where A and B are the sets of hyphen-delimited tokens in each slug.
        Range: 0.0 – 1.0.  Exact token-set match → 1.0.

      Step 2 — Prefix bonus (+0.15, capped at 1.0)
        Applied when one slug is a prefix of the other.  Rewards charts whose
        name is literally a prefix/extension of the item name.

      Step 3 — Substring bonus (+0.10, capped at 1.0)
        Applied when one full slug appears inside the other as a substring
        (and the prefix bonus was not already awarded).

    ── Decision thresholds ────────────────────────────────────────────────────
      MINIMUM_SCORE   = 0.50   The winner must reach at least this score.
                               Below this, no chart is close enough to suggest.

      CONFIDENCE_GAP  = 0.25   The winner must be at least 0.25 ahead of the
                               runner-up. If two charts are similarly named,
                               we return nothing — the user picks manually.

      EXACT_THRESHOLD = 0.90   If the top score is ≥ 0.90 (near-exact or exact
                               slug match), the gap check is skipped entirely:
                               there is no meaningful ambiguity at this level.

    All candidates are logged at DEBUG; the top-3 by score and the final
    decision (with reason) are logged at INFO regardless of outcome.
    """
    MINIMUM_SCORE   = 0.50
    CONFIDENCE_GAP  = 0.25
    EXACT_THRESHOLD = 0.90

    charts, error = get_marketplace_charts(environment)
    if error:
        logger.warning(
            "[MARKETPLACE][SUGGEST] Chart list error (env=%s): %s — no suggestion returned.",
            environment, error,
        )
    if not charts:
        logger.info(
            "[MARKETPLACE][SUGGEST] No charts available for env=%s — no suggestion returned.",
            environment,
        )
        return {"suggested_chart": None, "score": 0.0}

    normalized_item = _normalize_name_for_helm(item_name)
    item_tokens = set(t for t in normalized_item.split("-") if t)

    logger.info(
        "[MARKETPLACE][SUGGEST] Scoring item='%s' (normalized='%s', tokens=%s) "
        "against %d chart(s) in env=%s  "
        "[min=%.2f  gap=%.2f  exact=%.2f]",
        item_name, normalized_item, sorted(item_tokens),
        len(charts), environment,
        MINIMUM_SCORE, CONFIDENCE_GAP, EXACT_THRESHOLD,
    )

    # Collect (score, chart_name) for all candidates then sort.
    scored: List[tuple] = []

    for chart in charts:
        normalized_chart = _normalize_name_for_helm(chart)
        chart_tokens = set(t for t in normalized_chart.split("-") if t)

        # ── Step 1: Dice on token sets ───────────────────────────────────────
        if not item_tokens or not chart_tokens:
            score = 0.0
        elif normalized_chart == normalized_item:
            score = 1.0
        else:
            intersection = item_tokens & chart_tokens
            score = 2 * len(intersection) / (len(item_tokens) + len(chart_tokens))

        # ── Step 2: Prefix bonus ─────────────────────────────────────────────
        if normalized_item.startswith(normalized_chart) or normalized_chart.startswith(normalized_item):
            score = min(1.0, score + 0.15)
        # ── Step 3: Substring bonus (only if prefix didn't already fire) ─────
        elif normalized_chart in normalized_item or normalized_item in normalized_chart:
            score = min(1.0, score + 0.10)

        logger.debug(
            "[MARKETPLACE][SUGGEST]   chart='%s' (normalized='%s', tokens=%s) → score=%.3f",
            chart, normalized_chart, sorted(chart_tokens), score,
        )
        scored.append((score, chart))

    # Sort descending by score, then alphabetically for determinism on ties.
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Log the top-3 candidates for easy debugging.
    top3 = scored[:3]
    logger.info(
        "[MARKETPLACE][SUGGEST] Top candidates for '%s': %s",
        item_name,
        [(c, round(s, 3)) for s, c in top3],
    )

    best_score, best_chart = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    gap = best_score - second_score

    # ── Decision ─────────────────────────────────────────────────────────────
    if best_score < MINIMUM_SCORE:
        logger.info(
            "[MARKETPLACE][SUGGEST] ✗ No suggestion — best='%s' score=%.3f < min=%.2f",
            best_chart, best_score, MINIMUM_SCORE,
        )
        return {"suggested_chart": None, "score": round(best_score, 3)}

    if best_score < EXACT_THRESHOLD and gap < CONFIDENCE_GAP:
        logger.info(
            "[MARKETPLACE][SUGGEST] ✗ Ambiguous — best='%s' (%.3f) vs runner-up='%s' (%.3f) "
            "gap=%.3f < required=%.2f — no suggestion returned to avoid misleading the user.",
            best_chart, best_score, scored[1][1], second_score, gap, CONFIDENCE_GAP,
        )
        return {"suggested_chart": None, "score": round(best_score, 3)}

    logger.info(
        "[MARKETPLACE][SUGGEST] ✓ Clear winner for '%s' → '%s' "
        "(score=%.3f, gap=%.3f, runner-up='%s' at %.3f)",
        item_name, best_chart, best_score, gap,
        scored[1][1] if len(scored) > 1 else "none",
        second_score,
    )
    return {"suggested_chart": best_chart, "score": round(best_score, 3)}


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
        sanitized_name = _sanitize_entity_name(item.name)
        if sanitized_name != item.name:
            logger.info(
                "[MARKETPLACE][DEPLOY] entity_name sanitized: '%s' → '%s'",
                item.name, sanitized_name,
            )

        infra_payload: Dict[str, Any] = {
            "entity_name": sanitized_name,
            "entity_type": item.item_type,
            "chart_name": req.chart_name or sanitized_name,
            "chart_version": req.chart_version,
            "owner_username": current_user.username,
            "target_environment": req.environment,
            "deployment_type": "deploy",
        }
        if req.values_override:
            infra_payload["values_override"] = req.values_override

        try:
            logger.info(
                "[MARKETPLACE][DEPLOY] → POST %s/api/infra/deploy | entity='%s' env=%s chart=%s@%s",
                infra, sanitized_name, req.environment, req.chart_name, req.chart_version,
            )
            if _DEBUG_INFRA:
                logger.debug("[MARKETPLACE][DEPLOY] Full payload: %s", infra_payload)

            infra_resp = http_requests.post(
                f"{infra}/api/infra/deploy",
                json=infra_payload,
                timeout=INFRA_API_TIMEOUT_SECONDS,
            )

            # Log the full response unconditionally — always visible regardless of log level.
            # Placed before raise_for_status() so the body is captured on both success and error.
            logger.info(
                "[MARKETPLACE][DEPLOY] Infra API responded HTTP %d — body: %s",
                infra_resp.status_code, infra_resp.text,
            )

            infra_resp.raise_for_status()
            infra_data = infra_resp.json()
            logger.info(
                "[MARKETPLACE][DEPLOY] ✓ Success for '%s' | status=%s deployment_id=%s namespace=%s public_url=%s",
                item.name,
                infra_data.get("status"),
                infra_data.get("deployment_id"),
                infra_data.get("namespace"),
                infra_data.get("public_connection_url"),
            )
            public_url_from_infra = infra_data.get("public_connection_url")
        except http_requests.exceptions.Timeout:
            logger.error(
                "[MARKETPLACE][DEPLOY] ✗ TIMEOUT — infra did not respond within %ds for '%s' (id=%d). "
                "Target: %s/api/infra/deploy",
                INFRA_API_TIMEOUT_SECONDS, item.name, item.id, infra,
            )
            raise HTTPException(
                status_code=504,
                detail="Infra API did not respond within 5 minutes. Please try again.",
            )
        except http_requests.exceptions.ConnectionError as exc:
            logger.error(
                "[MARKETPLACE][DEPLOY] ✗ CONNECTION ERROR for '%s' (id=%d) → %s/api/infra/deploy: %s",
                item.name, item.id, infra, exc,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Could not reach the infra API server: {exc}",
            )
        except http_requests.exceptions.HTTPError as exc:
            raw_body: str = exc.response.text if exc.response is not None else ""
            try:
                body_json = exc.response.json()
                error_detail = (
                    body_json.get("detail")
                    or body_json.get("message")
                    or body_json.get("error")
                    or raw_body
                )
            except Exception:
                error_detail = raw_body or str(exc)
            logger.error(
                "[MARKETPLACE][DEPLOY] ✗ HTTP %d ERROR for '%s' (id=%d) — full response body: %s",
                exc.response.status_code if exc.response is not None else -1,
                item.name, item.id, raw_body,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Infra API error: {error_detail}",
            )
        except Exception as exc:
            logger.error(
                "[MARKETPLACE][DEPLOY] ✗ UNEXPECTED ERROR for '%s' (id=%d): %s",
                item.name, item.id, exc, exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Unexpected error calling infra API: {exc}")
    # ────────────────────────────────────────────────────────────────────────

    item.deployment_status = "DEPLOYED"
    item.environment = req.environment
    item.chart_name = req.chart_name or item.name
    item.chart_version = req.chart_version
    item.version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if (MARKETPLACE_TTL_ENABLED and req.environment == "dev") else None
    if public_url_from_infra:
        final_url = _apply_mcp_url_suffix(public_url_from_infra, item.item_type)
        item.url_to_connect = final_url
        if final_url != public_url_from_infra:
            logger.info(
                "[MARKETPLACE][DEPLOY] MCP server URL suffixed: '%s' → '%s'",
                public_url_from_infra, final_url,
            )
        public_url_from_infra = final_url

    db.commit()
    db.refresh(item)

    # For MCP servers, fetch the live tool list from the newly deployed URL and
    # persist it so the marketplace card can display it immediately.
    if item.item_type == "mcp_server" and item.url_to_connect:
        tools = _fetch_mcp_tools(item.url_to_connect, item.name)
        if tools:
            item.tools_exposed = tools
            db.commit()
            db.refresh(item)
        else:
            logger.info(
                "[MARKETPLACE][DEPLOY] tools_exposed not updated for '%s' (id=%d) — "
                "fetch returned no tools (server may still be initialising).",
                item.name, item.id,
            )

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
    Upgrade a DEPLOYED item to a new chart name/version or environment.

    The infra API runs `helm upgrade --install` internally, so no prior
    undeploy call is needed.  We call deploy directly and let Helm handle
    the in-place upgrade.

    Workflow:
      1. Call infra deploy with new spec (helm upgrade --install)
      2. Update DB record with new chart_name, chart_version, deployed_at, ttl_days
    """
    item = db.query(MarketplaceItem).filter_by(id=req.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to redeploy this item")
    if item.deployment_status != "DEPLOYED":
        raise HTTPException(
            status_code=400,
            detail="Only DEPLOYED items can be upgraded. Deploy it first.",
        )

    old_chart = item.chart_name
    old_version = item.chart_version
    old_env = item.environment

    logger.info(
        "[MARKETPLACE] User '%s' upgrading '%s' (id=%d): %s@%s/%s → %s@%s/%s",
        current_user.username, item.name, item.id,
        old_chart, old_version, old_env,
        req.chart_name, req.chart_version, req.environment,
    )

    # ── Call infra API (helm upgrade --install — no prior delete needed) ─────
    infra = _infra_url()
    public_url_from_infra: Optional[str] = None

    if infra:
        sanitized_name = _sanitize_entity_name(item.name)
        if sanitized_name != item.name:
            logger.info(
                "[MARKETPLACE][REDEPLOY] entity_name sanitized: '%s' → '%s'",
                item.name, sanitized_name,
            )

        deploy_payload: Dict[str, Any] = {
            "entity_name": sanitized_name,
            "entity_type": item.item_type,
            "chart_name": req.chart_name or item.chart_name or sanitized_name,
            "chart_version": req.chart_version,
            "owner_username": current_user.username,
            "target_environment": req.environment,
            "deployment_type": "upgrade",
        }
        if req.values_override:
            deploy_payload["values_override"] = req.values_override

        try:
            logger.info(
                "[MARKETPLACE][REDEPLOY] → POST %s/api/infra/deploy | entity='%s' env=%s chart=%s@%s",
                infra, item.name, req.environment, req.chart_name, req.chart_version,
            )
            if _DEBUG_INFRA:
                logger.debug("[MARKETPLACE][REDEPLOY] Deploy payload: %s", deploy_payload)

            dep_resp = http_requests.post(
                f"{infra}/api/infra/deploy",
                json=deploy_payload,
                timeout=INFRA_API_TIMEOUT_SECONDS,
            )

            # Log the full response unconditionally — always visible regardless of log level.
            # Placed before raise_for_status() so the body is captured on both success and error.
            logger.info(
                "[MARKETPLACE][REDEPLOY] Infra API responded HTTP %d — body: %s",
                dep_resp.status_code, dep_resp.text,
            )

            dep_resp.raise_for_status()
            infra_data = dep_resp.json()
            logger.info(
                "[MARKETPLACE][REDEPLOY] ✓ Deploy succeeded for '%s' | status=%s deployment_id=%s namespace=%s public_url=%s",
                item.name,
                infra_data.get("status"),
                infra_data.get("deployment_id"),
                infra_data.get("namespace"),
                infra_data.get("public_connection_url"),
            )
            public_url_from_infra = infra_data.get("public_connection_url")
        except http_requests.exceptions.Timeout:
            logger.error(
                "[MARKETPLACE][REDEPLOY] ✗ TIMEOUT for '%s' (id=%d) → %s/api/infra/deploy",
                item.name, item.id, infra,
            )
            raise HTTPException(status_code=504, detail="Infra API did not respond within 5 minutes.")
        except http_requests.exceptions.ConnectionError as exc:
            logger.error(
                "[MARKETPLACE][REDEPLOY] ✗ CONNECTION ERROR for '%s' (id=%d): %s",
                item.name, item.id, exc,
            )
            raise HTTPException(status_code=502, detail=f"Could not reach the infra API server: {exc}")
        except http_requests.exceptions.HTTPError as exc:
            raw_body = exc.response.text if exc.response is not None else ""
            try:
                body_json = exc.response.json()
                error_detail = (
                    body_json.get("detail")
                    or body_json.get("message")
                    or body_json.get("error")
                    or raw_body
                )
            except Exception:
                error_detail = raw_body or str(exc)
            logger.error(
                "[MARKETPLACE][REDEPLOY] ✗ HTTP %d ERROR for '%s' (id=%d) — full response body: %s",
                exc.response.status_code if exc.response is not None else -1,
                item.name, item.id, raw_body,
            )
            raise HTTPException(status_code=502, detail=f"Infra API error: {error_detail}")
        except Exception as exc:
            logger.error(
                "[MARKETPLACE][REDEPLOY] ✗ UNEXPECTED ERROR for '%s' (id=%d): %s",
                item.name, item.id, exc, exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Unexpected error calling infra API: {exc}")
    # ────────────────────────────────────────────────────────────────────────

    item.environment = req.environment
    item.chart_name = req.chart_name or item.chart_name
    item.chart_version = req.chart_version
    item.version = req.chart_version
    item.deployed_at = datetime.now(timezone.utc)
    item.ttl_days = MARKETPLACE_DEV_TTL_DAYS if (MARKETPLACE_TTL_ENABLED and req.environment == "dev") else None
    if public_url_from_infra:
        final_url = _apply_mcp_url_suffix(public_url_from_infra, item.item_type)
        item.url_to_connect = final_url
        if final_url != public_url_from_infra:
            logger.info(
                "[MARKETPLACE][REDEPLOY] MCP server URL suffixed: '%s' → '%s'",
                public_url_from_infra, final_url,
            )
        public_url_from_infra = final_url

    db.commit()
    db.refresh(item)

    # Re-fetch tool list after upgrade — the new chart version may expose
    # different tools.
    if item.item_type == "mcp_server" and item.url_to_connect:
        tools = _fetch_mcp_tools(item.url_to_connect, item.name)
        if tools:
            item.tools_exposed = tools
            db.commit()
            db.refresh(item)
        else:
            logger.info(
                "[MARKETPLACE][REDEPLOY] tools_exposed not updated for '%s' (id=%d) — "
                "fetch returned no tools (server may still be initialising).",
                item.name, item.id,
            )

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


@router.post("/items/{item_id}/clone")
def clone_marketplace_item(
    item_id: int,
    req: CloneRequest = CloneRequest(),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fork a BUILT or DEPLOYED item into a fresh BUILT copy owned by the current user.
    The clone starts as BUILT so it can be independently deployed to any environment.

    An optional fork_name may be provided in the request body.  If omitted the
    name defaults to "{source.name} - Fork".  The name is checked for global
    uniqueness (case-insensitive) before the clone is created.
    """
    source = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source item not found")
    if source.deployment_status not in ("BUILT", "DEPLOYED"):
        raise HTTPException(
            status_code=400, detail="Only BUILT or DEPLOYED items can be cloned."
        )

    # Resolve and validate fork name
    desired_name = (req.fork_name or "").strip() or f"{source.name} - Fork"
    existing = (
        db.query(MarketplaceItem)
        .filter(func.lower(MarketplaceItem.name) == desired_name.lower())
        .first()
    )
    if existing:
        logger.warning(
            "[MARKETPLACE] Fork of '%s' (id=%d) by '%s' rejected — "
            "name '%s' already exists (id=%d).",
            source.name, source.id, current_user.username, desired_name, existing.id,
        )
        raise HTTPException(
            status_code=409,
            detail=f"An item named \"{desired_name}\" already exists. Choose a different name.",
        )

    if not current_user.is_admin:
        if source.item_type == "agent":
            user_count = (
                db.query(MarketplaceItem)
                .filter_by(owner_id=current_user.id, item_type="agent")
                .count()
            )
            if user_count >= MARKETPLACE_MAX_AGENTS_PER_USER:
                logger.warning(
                    "[MARKETPLACE] User '%s' hit agent limit during fork (%d/%d) — fork of '%s' (id=%d) rejected.",
                    current_user.username, user_count, MARKETPLACE_MAX_AGENTS_PER_USER,
                    source.name, source.id,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Agent limit reached ({MARKETPLACE_MAX_AGENTS_PER_USER} max). Delete one before forking.",
                )
        elif source.item_type == "mcp_server":
            user_count = (
                db.query(MarketplaceItem)
                .filter_by(owner_id=current_user.id, item_type="mcp_server")
                .count()
            )
            if user_count >= MARKETPLACE_MAX_MCP_PER_USER:
                logger.warning(
                    "[MARKETPLACE] User '%s' hit MCP server limit during fork (%d/%d) — fork of '%s' (id=%d) rejected.",
                    current_user.username, user_count, MARKETPLACE_MAX_MCP_PER_USER,
                    source.name, source.id,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"MCP server limit reached ({MARKETPLACE_MAX_MCP_PER_USER} max). Delete one before forking.",
                )

    clone = MarketplaceItem(
        name=desired_name,
        description=source.description,
        item_type=source.item_type,
        owner_id=current_user.id,
        icon=source.icon,
        bitbucket_repo=source.bitbucket_repo,
        how_to_use=source.how_to_use,
        url_to_connect=None,
        tools_exposed=source.tools_exposed,
        deployment_status="BUILT",
        version="",
        environment="dev",
        chart_name=source.chart_name,
        chart_version=source.chart_version,
        ttl_days=MARKETPLACE_DEV_TTL_DAYS if MARKETPLACE_TTL_ENABLED else None,
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
    db_only: bool = False,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an item. Only the owner or an admin may delete.

    db_only=true (admin only) — removes the DB record immediately without
    calling the infra undeploy API.  Useful when the deployment is already
    gone from the cluster and only the stale DB row needs to be cleaned up.
    """
    item = db.query(MarketplaceItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")

    if db_only:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Only admins may use the db_only deletion mode.",
            )
        logger.warning(
            "[MARKETPLACE] Admin '%s' is removing '%s' (id=%d, status=%s) from DB only"
            " — infra undeploy SKIPPED.",
            current_user.username, item.name, item_id, item.deployment_status,
        )
    else:
        # For deployed items, call infra first — raise on error so user sees the problem
        infra_error = _call_infra_undeploy(
            item,
            owner_username=current_user.username if current_user else "system",
            reason="manual_user_deletion",
            raise_on_error=(item.deployment_status == "DEPLOYED"),
        )
        if infra_error and item.deployment_status != "DEPLOYED":
            logger.warning(
                "[MARKETPLACE] Infra undeploy warning during delete for '%s' (id=%d): %s",
                item.name, item_id, infra_error,
            )

    db.delete(item)
    db.commit()
    logger.info(
        "[MARKETPLACE] User '%s' deleted item '%s' (id=%d) [db_only=%s]",
        current_user.username, item.name, item_id, db_only,
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
            "[MARKETPLACE][DELETE] → POST %s/api/infra/delete | entity='%s' env=%s reason=%s",
            infra, item.name, item.environment, reason,
        )
        logger.info("[MARKETPLACE][DELETE] Full payload: %s", payload)

        resp = http_requests.post(
            f"{infra}/api/infra/delete",
            json=payload,
            timeout=INFRA_API_TIMEOUT_SECONDS,
        )

        # Log the full response unconditionally before raise_for_status() so the
        # body is always captured in the log regardless of success or failure.
        logger.info(
            "[MARKETPLACE][DELETE] Infra API responded HTTP %d — body: %s",
            resp.status_code, resp.text,
        )

        resp.raise_for_status()
        logger.info(
            "[MARKETPLACE][DELETE] ✓ Undeploy succeeded for '%s' (id=%d).",
            item.name, item.id,
        )
        return None
    except http_requests.exceptions.Timeout:
        msg = "Infra API did not respond within 5 minutes."
        logger.error(
            "[MARKETPLACE][DELETE] ✗ TIMEOUT — infra did not respond within %ds for '%s' (id=%d). "
            "Target: %s/api/infra/delete",
            INFRA_API_TIMEOUT_SECONDS, item.name, item.id, infra,
        )
    except http_requests.exceptions.ConnectionError as exc:
        msg = f"Could not reach the infra API server: {exc}"
        logger.error(
            "[MARKETPLACE][DELETE] ✗ CONNECTION ERROR for '%s' (id=%d) → %s/api/infra/delete: %s",
            item.name, item.id, infra, exc,
        )
    except http_requests.exceptions.HTTPError as exc:
        raw_body = exc.response.text if exc.response is not None else ""
        try:
            msg = exc.response.json().get("detail") or raw_body
        except Exception:
            msg = raw_body or str(exc)
        logger.error(
            "[MARKETPLACE][DELETE] ✗ HTTP %d ERROR for '%s' (id=%d) — full response body: %s",
            exc.response.status_code if exc.response is not None else -1,
            item.name, item.id, raw_body,
        )
    except Exception as exc:
        msg = f"Unexpected error: {exc}"
        logger.error(
            "[MARKETPLACE][DELETE] ✗ UNEXPECTED ERROR for '%s' (id=%d): %s",
            item.name, item.id, exc, exc_info=True,
        )

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
    db: Session = _database.SessionLocal()
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


# ─── Background Cluster Deployment Reconciliation ────────────────────────────

def _sanitize_entity_name(raw_name: str) -> str:
    """
    Sanitize a marketplace item display name before sending it as entity_name
    to the infra API.

    Rules (applied in order):
      1. Lowercase the entire string.
      2. Replace every character that is not alphanumeric, a hyphen, or an
         underscore with a single hyphen.  This covers spaces, @, #, !, dots,
         slashes, brackets, etc.
      3. Collapse runs of two or more consecutive hyphens into one hyphen.
         (Underscores that were in the original name are preserved unchanged.)
      4. Strip any leading or trailing hyphens / underscores.

    Examples:
      "My Jira MCP!"        → "my-jira-mcp"
      "Data @Analysis #v2"  → "data-analysis-v2"
      "code_review-agent"   → "code_review-agent"   (underscore kept)
      "  --odd-- name--"    → "odd-name"
    """
    s = raw_name.lower()
    s = re.sub(r"[^a-z0-9\-_]", "-", s)   # replace specials with dash
    s = re.sub(r"-{2,}", "-", s)            # collapse consecutive dashes
    s = s.strip("-_")
    return s


def _normalize_name_for_helm(name: str) -> str:
    """
    Normalise a Marketplace item name to the Helm-compatible slug that the
    infra API uses when building a Helm release name:

      - Convert to lowercase
      - Replace every run of non-alphanumeric characters with a single hyphen
      - Strip leading / trailing hyphens

    Examples:
      "Data Analysis Agent" → "data-analysis-agent"
      "My Jira MCP!"       → "my-jira-mcp"
      "my-test-app2"       → "my-test-app2"
    """
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _parse_release_components(release_name: str) -> Optional[Dict[str, str]]:
    """
    Decompose a Helm release name into its structural components.

    Full naming convention (defined by the infra team):
      {project}-{entity_type}-{entity_name}-{target_environment}

    Since entity_name itself can contain hyphens, we extract:
      • parts[0]     → project       (skipped during matching — not stored in DB)
      • parts[1]     → entity_type   (e.g. 'agent', 'mcp')
      • parts[2:-1]  → entity_name   (re-joined with '-'; may be multi-segment)
      • parts[-1]    → environment   (e.g. 'dev', 'release')

    Returns None when the name has fewer than 4 segments (cannot be a valid
    marketplace release and will be silently skipped during reconciliation).

    Examples:
      "infra-agent-my-test-app2-dev"
        → {project: 'infra', entity_type: 'agent',
           entity_name: 'my-test-app2', environment: 'dev'}

      "infra-mcp-jira-integration-mcp-release"
        → {project: 'infra', entity_type: 'mcp',
           entity_name: 'jira-integration-mcp', environment: 'release'}
    """
    parts = release_name.split('-')
    if len(parts) < 4:
        return None
    return {
        "project":     parts[0],
        "entity_type": parts[1],
        "entity_name": '-'.join(parts[2:-1]),
        "environment": parts[-1],
    }


def _item_matches_release(item: MarketplaceItem, parsed: Dict[str, str]) -> bool:
    """
    Return True when a parsed Helm release name corresponds to this DB item.

    The project segment is intentionally ignored (not stored in the DB).
    Matching is done on the remaining three fields:

      environment  — exact match against item.environment
      entity_name  — exact match against the normalised item.name
      entity_type  — 'agent' matches item_type='agent'
                     'mcp' OR 'mcp_server' both match item_type='mcp_server'
                     (infra may shorten 'mcp_server' to 'mcp' in the slug)
    """
    if parsed["environment"] != item.environment:
        return False
    if parsed["entity_name"] != _normalize_name_for_helm(item.name):
        return False
    # Accept the DB value verbatim OR the commonly shortened slug form
    expected_types = {item.item_type, item.item_type.replace("_server", "")}
    return parsed["entity_type"] in expected_types


def _run_cluster_sync() -> None:
    """
    Reconcile every DEPLOYED Marketplace item against the live Helm releases
    reported by GET {INFRA_CHARTS_API_SERVER}/api/infra/deployments.

    Workflow
    ────────
    1. Fetch the full release list from the infra API.
    2. Parse every release name into {project, entity_type, entity_name,
       environment}.  The project segment is ignored — it is not stored in the
       DB — so matching is done on the remaining three fields only.
    3. For each DEPLOYED item in the DB:
         • FOUND   → log at INFO; item is healthy, no action taken.
         • MISSING → log at WARNING explaining that the item should be deleted
                     from the DB because its deployment no longer exists in
                     the cluster.

    NOTE: Deletion is intentionally disabled for now.
    When an orphaned item is detected we only emit a WARNING log.
    Once the matching logic has been validated in production the commented-out
    deletion block below can be re-enabled.

    All findings (both present and absent) are written to the application log
    so operators can audit what the reconciliation found each cycle.
    """
    infra = _infra_url()
    if not infra:
        logger.debug(
            "[MARKETPLACE][SYNC] INFRA_CHARTS_API_SERVER not configured — cluster sync skipped."
        )
        return

    deployments_url = f"{infra}/api/infra/deployments"

    # ── Step 1: Fetch active releases from infra ──────────────────────────────
    try:
        logger.info(
            "[MARKETPLACE][SYNC] ── Cluster sync cycle starting ──────────────────────"
        )
        logger.info(
            "[MARKETPLACE][SYNC] Fetching active deployments from %s", deployments_url
        )
        resp = http_requests.get(deployments_url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except http_requests.exceptions.Timeout:
        logger.error(
            "[MARKETPLACE][SYNC] Timed out (30s) fetching %s — sync aborted.", deployments_url
        )
        return
    except http_requests.exceptions.ConnectionError as exc:
        logger.error(
            "[MARKETPLACE][SYNC] Connection error fetching %s: %s — sync aborted.",
            deployments_url, exc,
        )
        return
    except http_requests.exceptions.HTTPError as exc:
        logger.error(
            "[MARKETPLACE][SYNC] HTTP %d error from infra deployments API: %s — sync aborted.",
            exc.response.status_code if exc.response is not None else -1, exc,
        )
        return
    except Exception as exc:
        logger.error(
            "[MARKETPLACE][SYNC] Unexpected error fetching deployments: %s — sync aborted.",
            exc, exc_info=True,
        )
        return

    releases: List[Dict[str, Any]] = payload.get("releases", [])
    total_in_cluster: int = payload.get("total", len(releases))

    logger.info(
        "[MARKETPLACE][SYNC] Infra reports %d active release(s) (total=%d).",
        len(releases), total_in_cluster,
    )

    # Parse every release name upfront; skip names that are too short to be
    # valid marketplace releases and log them so nothing is silently ignored.
    parsed_releases: List[Dict[str, str]] = []
    for r in releases:
        name = r.get("name", "")
        parsed = _parse_release_components(name)
        if parsed is None:
            logger.debug(
                "[MARKETPLACE][SYNC] Skipping release '%s' — fewer than 4 segments,"
                " not a marketplace release.",
                name,
            )
            continue
        parsed_releases.append(parsed)
        logger.info(
            "[MARKETPLACE][SYNC] Cluster release '%s'"
            " → project='%s' type='%s' name='%s' env='%s'",
            name,
            parsed["project"], parsed["entity_type"],
            parsed["entity_name"], parsed["environment"],
        )

    # ── Step 2: Cross-reference with DB ──────────────────────────────────────
    db: Session = _database.SessionLocal()
    try:
        deployed_items = (
            db.query(MarketplaceItem)
            .filter(MarketplaceItem.deployment_status == "DEPLOYED")
            .all()
        )

        if not deployed_items:
            logger.info(
                "[MARKETPLACE][SYNC] No DEPLOYED items in DB — nothing to reconcile."
            )
            return

        logger.info(
            "[MARKETPLACE][SYNC] Reconciling %d DEPLOYED DB item(s) against"
            " %d parsed cluster release(s) …",
            len(deployed_items), len(parsed_releases),
        )

        items_missing: List[MarketplaceItem] = []

        for item in deployed_items:
            normalised = _normalize_name_for_helm(item.name)
            matched = any(
                _item_matches_release(item, p) for p in parsed_releases
            )
            if matched:
                logger.info(
                    "[MARKETPLACE][SYNC] ✓ FOUND   — '%s' (id=%d, type=%s, env=%s,"
                    " normalised_name='%s') matched a cluster release.",
                    item.name, item.id, item.item_type, item.environment, normalised,
                )
            else:
                logger.warning(
                    "[MARKETPLACE][SYNC] ✗ MISSING — '%s' (id=%d, type=%s, env=%s,"
                    " normalised_name='%s') has no matching release in the cluster.",
                    item.name, item.id, item.item_type, item.environment, normalised,
                )
                items_missing.append(item)

        if not items_missing:
            logger.info(
                "[MARKETPLACE][SYNC] All %d DEPLOYED item(s) are present in the cluster."
                " No action needed.",
                len(deployed_items),
            )
            return

        # ── Orphan report ─────────────────────────────────────────────────────
        logger.warning(
            "[MARKETPLACE][SYNC] %d orphaned item(s) detected (deployment gone from"
            " cluster): %s",
            len(items_missing),
            [f"'{i.name}' (id={i.id}, type={i.item_type}, env={i.environment})"
             for i in items_missing],
        )
        for item in items_missing:
            logger.warning(
                "[MARKETPLACE][SYNC] ACTION REQUIRED — '%s' (id=%d) should be deleted"
                " from the DB: its Helm release no longer exists in the cluster."
                " Deletion is currently DISABLED (observation-only mode)."
                " Re-enable the deletion block in _run_cluster_sync() when ready.",
                item.name, item.id,
            )

        # ── Deletion block — DISABLED (observation-only mode) ─────────────────
        # Uncomment the lines below once the matching logic has been validated
        # in production and you are confident the orphan detection is accurate.
        #
        # for item in items_missing:
        #     db.delete(item)
        # db.commit()
        # logger.info(
        #     "[MARKETPLACE][SYNC] ✓ Deleted %d orphaned item(s) from DB successfully.",
        #     len(items_missing),
        # )

    except Exception as exc:
        db.rollback()
        logger.error(
            "[MARKETPLACE][SYNC] DB error during reconciliation: %s", exc, exc_info=True
        )
    finally:
        db.close()
        logger.info("[MARKETPLACE][SYNC] ── Cluster sync cycle complete ────────────────────")


def start_cluster_sync_thread() -> threading.Thread:
    """
    Daemon thread that reconciles DEPLOYED Marketplace items against live Helm
    releases every 10 minutes by calling GET /api/infra/deployments.

    If INFRA_CHARTS_API_SERVER is not set, each cycle exits immediately after a
    single debug log — no performance cost in environments without infra.

    The thread is a daemon so uvicorn shuts down cleanly without waiting for it.
    """
    interval_seconds = 600  # 10 minutes

    def _target() -> None:
        logger.info(
            "[MARKETPLACE] Cluster sync thread started"
            " (interval=%ds / %.0f min).",
            interval_seconds, interval_seconds / 60,
        )
        while True:
            time.sleep(interval_seconds)
            try:
                _run_cluster_sync()
            except Exception as exc:
                logger.error(
                    "[MARKETPLACE] Cluster sync thread unhandled error: %s",
                    exc, exc_info=True,
                )

    thread = threading.Thread(
        target=_target, daemon=True, name="marketplace-cluster-sync"
    )
    thread.start()
    logger.info(
        "[MARKETPLACE] Cluster sync daemon thread launched (tid=%s).", thread.ident
    )
    return thread


