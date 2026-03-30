"""
usageTracker.py
===============
Fire-and-forget usage reporting to the AI Portal marketplace
``/api/marketplace/ping`` endpoint.

Because the agent exposes a single MCP tool (``run_agent``), tracking is done
inline inside that tool rather than via ASGI middleware.  The ping is launched
as a background task so it never blocks or delays the agent response.

Configuration (env vars, picked up via AppConfig)
-------------------------------------------------
PORTAL_BASE_URL
    Base URL of the AI Portal, e.g. ``https://portal.company.internal``.
    If empty / unset the ping is skipped silently.

AGENT_MARKETPLACE_NAME
    Exact ``name`` of this agent as registered in the marketplace
    (must match the DB entry or ``/ping`` returns 404).

PORTAL_SSL_VERIFY
    Whether to verify TLS certificates when calling the portal (default True).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    """Decode the payload section of a JWT *without* signature verification."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return json.loads(raw)
    except Exception:
        return {}


def extract_user_from_jwt(token: str) -> Optional[str]:
    """
    Return the best available user identifier from a JWT token.

    Checks these standard claims in order:
    ``preferred_username``, ``email``, ``upn``, ``unique_name``,
    ``sub``, ``username``.

    Returns *None* if the token cannot be decoded or no claim is present.
    """
    payload = _decode_jwt_payload(token)
    for claim in ("preferred_username", "email", "upn", "unique_name", "sub", "username"):
        value = payload.get(claim)
        if value:
            return str(value)
    return None


# ─── Ping helper ──────────────────────────────────────────────────────────────

def _post_ping_sync(
    portal_ping_url: str,
    entity_name: str,
    user_identifier: Optional[str],
    ssl_verify: bool,
) -> None:
    """Blocking HTTP POST to the portal ping endpoint (runs in a thread pool)."""
    payload = {
        "entity_name": entity_name,
        "entity_type": "agent",
        "user_identifier": user_identifier,
        "action": "call",
    }
    try:
        resp = requests.post(
            portal_ping_url,
            json=payload,
            verify=ssl_verify,
            timeout=5,
        )
        if resp.status_code == 200:
            logger.debug(
                "Usage ping OK  entity=%s  user=%s",
                entity_name,
                user_identifier or "anonymous",
            )
        else:
            logger.debug(
                "Usage ping → HTTP %d  entity=%s  user=%s",
                resp.status_code,
                entity_name,
                user_identifier or "anonymous",
            )
    except Exception as exc:
        logger.debug("Usage ping failed  entity=%s: %s", entity_name, exc)


async def fire_ping(
    portal_ping_url: str,
    entity_name: str,
    user_identifier: Optional[str],
    ssl_verify: bool = True,
) -> None:
    """Async wrapper: runs the blocking HTTP call in the default thread pool."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _post_ping_sync,
        portal_ping_url,
        entity_name,
        user_identifier,
        ssl_verify,
    )


def schedule_ping(
    portal_ping_url: str,
    entity_name: str,
    user_identifier: Optional[str],
    ssl_verify: bool = True,
) -> None:
    """
    Schedule a fire-and-forget ping on the running event loop.

    Must be called from within an async context (i.e. inside an ``async def``
    function).  Any error is silently discarded so agent execution is never
    interrupted.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            fire_ping(portal_ping_url, entity_name, user_identifier, ssl_verify),
            name=f"usage-ping-{entity_name}",
        )
    except RuntimeError:
        pass
