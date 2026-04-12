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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

logger = logging.getLogger(__name__)

# Strong references kept until each task finishes, preventing premature GC.
_background_tasks: Set[asyncio.Task] = set()


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
    await asyncio.to_thread(
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
        task = loop.create_task(
            fire_ping(portal_ping_url, entity_name, user_identifier, ssl_verify),
            name=f"usage-ping-{entity_name}",
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        pass


# ─── ASGI middleware ───────────────────────────────────────────────────────────

class AgentUsageTrackingMiddleware:
    """
    Pure ASGI middleware that intercepts MCP ``tools/call`` JSON-RPC requests
    to the agent's MCP server and fires a non-blocking usage ping to the portal
    marketplace.

    Mirrors the ``UsageTrackingMiddleware`` used by the Bitbucket MCP server,
    adapted for the agent entity type (``entity_type=agent``, ``action=call``).

    Wrapping strategy
    -----------------
    1. For every HTTP POST the body is fully buffered.
    2. If the JSON-RPC ``method`` is ``tools/call`` a background task is
       scheduled immediately (before the tool starts executing).
    3. The buffered body is replayed verbatim to the underlying MCP app so
       the tool receives its arguments unchanged.
    4. The response pipeline is **not touched** — SSE and chunked responses
       stream through unmodified.
    """

    _MCP_CALL_METHOD = "tools/call"

    def __init__(
        self,
        app: Any,
        portal_ping_url: str,
        entity_name: str,
        ssl_verify: bool = True,
    ) -> None:
        self.app = app
        self.portal_ping_url = portal_ping_url
        self.entity_name = entity_name
        self.ssl_verify = ssl_verify
        logger.info(
            "AgentUsageTrackingMiddleware active  entity='%s'  ping_url=%s",
            entity_name,
            portal_ping_url,
        )

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        # ── Buffer the full request body ──────────────────────────────────────
        chunks: List[bytes] = []
        while True:
            message = await receive()
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        # ── Schedule usage ping BEFORE forwarding (non-blocking) ─────────────
        self._maybe_schedule_ping(scope, body)

        # ── Replay buffered body back to the MCP handler ─────────────────────
        replayed = False

        async def replay_receive() -> Dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_auth_token(self, scope: Dict[str, Any]) -> Optional[str]:
        """Return the raw Bearer token from the request headers, or None."""
        headers: List[Tuple[bytes, bytes]] = scope.get("headers", [])
        for name, value in headers:
            if name.lower() == b"authorization":
                auth = value.decode("utf-8", errors="replace")
                if auth.lower().startswith("bearer "):
                    return auth.split(" ", 1)[1].strip()
        return None

    def _maybe_schedule_ping(self, scope: Dict[str, Any], body: bytes) -> None:
        """
        Parse the JSON-RPC body; if it is a ``tools/call`` request schedule
        a background ping task.  Any error is silently discarded.
        """
        try:
            data: Dict[str, Any] = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if data.get("method") != self._MCP_CALL_METHOD:
            return

        token = self._extract_auth_token(scope)
        user_identifier = extract_user_from_jwt(token) if token else None

        logger.debug(
            "Agent usage ping scheduled  entity=%s  user=%s",
            self.entity_name,
            user_identifier or "anonymous",
        )

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                fire_ping(
                    self.portal_ping_url,
                    self.entity_name,
                    user_identifier,
                    self.ssl_verify,
                ),
                name=f"usage-ping-{self.entity_name}",
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            pass
