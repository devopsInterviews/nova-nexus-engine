"""
SSO / OIDC Route Handlers.

This module exposes the HTTP endpoints that implement the OIDC Authorization
Code flow for company SSO login via Authentik.

Endpoints
~~~~~~~~~
* ``GET  /api/sso/config``   — public; returns whether SSO is enabled so the
  frontend can decide whether to render the "Login with Company Credentials"
  button.
* ``GET  /api/sso/login``    — public; redirects the browser to Authentik's
  authorization endpoint to begin the login.
* ``GET  /api/sso/callback`` — public; handles the redirect back from
  Authentik, exchanges the authorization code for tokens, upserts the user,
  issues a portal JWT, and redirects the browser to the frontend SPA with the
  token in the query string.

ASCII Flow
~~~~~~~~~~
::

    Browser
      |
      | Click "Login with Company Credentials"
      v
    Portal UI  ──────────────────>  GET /api/sso/login
      |                                  |
      |                      302 → Authentik authorization_endpoint
      |                                  |
      |            <──── Authentik redirect back with ?code=...&state=...
      v
    GET /api/sso/callback
      |
      | validate state → exchange code → validate id_token
      | → upsert user/groups → log login event → issue portal token
      | → persist session
      v
    302 → /sso/callback?token=<portal-jwt>
      |
    Frontend picks up token, stores in localStorage, navigates to /

Security
~~~~~~~~
* The ``state`` parameter is a signed JWT — no server-side session storage
  required during the OIDC handshake.
* The authorization code is exchanged server-to-server (Authentik never sees
  the portal JWT).
* SSO login failures are logged with full context for admin review.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.services.sso_service import (
    SSO_ENABLED,
    OIDC_CLIENT_ID,
    OIDC_ISSUER_URL,
    OIDC_REDIRECT_URI,
    build_authorization_url,
    create_state_token,
    exchange_code_for_tokens,
    fetch_userinfo,
    get_oidc_config,
    issue_portal_token,
    persist_session,
    upsert_sso_user,
    validate_id_token,
    verify_state_token,
)
from app.models import UserActivity, SSOGroup, User
from app.routes.auth_routes import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/sso", tags=["SSO / OIDC"])

def is_admin(current_user: User = Depends(get_current_user)):
    """Dependency to check if the current user is an admin."""
    if hasattr(current_user, 'is_admin'):
        if not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    elif current_user.username != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@router.get("/groups")
async def get_sso_groups(
    current_user: User = Depends(is_admin),
    db: Session = Depends(get_db_session)
):
    """
    Return all SSO groups from the database.
    """
    groups = db.query(SSOGroup).all()
    return {
        "status": "success",
        "groups": [g.to_dict() for g in groups]
    }


# -------------------------------------------------------------------
# Helper — extract client context from the request for audit logging
# -------------------------------------------------------------------

def _client_ip(request: Request) -> Optional[str]:
    """Extract the real client IP from proxy headers or the direct connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None


def _client_ua(request: Request) -> Optional[str]:
    """Extract the User-Agent header."""
    return request.headers.get("User-Agent")


# ===================================================================
# GET /api/sso/config — frontend checks whether to show the SSO button
# ===================================================================

@router.get("/config")
async def sso_config():
    """
    Return the current SSO configuration for the frontend.

    The frontend calls this endpoint on the login page to decide whether
    to render the "Login with Company Credentials" button.  No
    authentication is required — this is a public endpoint that exposes
    only non-sensitive configuration.

    Returns:
        dict: ``{ enabled, login_url, provider_name }``
    """
    logger.info("[SSO] /config requested — SSO_ENABLED=%s", SSO_ENABLED)
    return {
        "enabled": SSO_ENABLED,
        "login_url": "/api/sso/login" if SSO_ENABLED else None,
        "provider_name": "Company Credentials",
    }


# ===================================================================
# GET /api/sso/login — redirect to Authentik
# ===================================================================

@router.get("/login")
async def sso_login(request: Request):
    """
    Initiate the OIDC Authorization Code flow.

    1. Verify that SSO is enabled.
    2. Fetch/refresh the OIDC discovery document (cached).
    3. Create a signed ``state`` token for CSRF protection.
    4. Build the Authentik authorization URL.
    5. Return a ``302 Found`` redirect to Authentik.

    The user authenticates with Authentik and is redirected back to
    ``/api/sso/callback`` with an authorization code.
    """
    if not SSO_ENABLED:
        logger.warning("[SSO] Login attempt but SSO is disabled")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO is not enabled on this portal instance",
        )

    logger.info(
        "[SSO] Login initiated from ip=%s ua=%s",
        _client_ip(request), _client_ua(request),
    )

    # Ensure the OIDC discovery document is loaded
    await get_oidc_config()

    # Create a CSRF-safe state parameter
    state = create_state_token()

    # Build the full authorization URL
    auth_url = build_authorization_url(state)

    logger.info("[SSO] Redirecting user to Authentik authorization endpoint")
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


# ===================================================================
# GET /api/sso/callback — handle the redirect back from Authentik
# ===================================================================

@router.get("/callback")
async def sso_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    """
    Handle the OIDC callback after the user authenticates with Authentik.

    This is the most critical endpoint in the SSO flow.  It performs:

    1. **Error check** — Authentik may return an error instead of a code.
    2. **State validation** — verify the signed state JWT to prevent CSRF.
    3. **Code exchange** — POST the code to Authentik's token endpoint to
       receive ``id_token`` and ``access_token``.
    4. **ID token validation** — verify signature, issuer, audience, expiry
       using the provider's JWKS.
    5. **UserInfo fallback** — fetch additional claims if the ID token is
       missing ``groups`` or ``email``.
    6. **User upsert** — create or update the user in the portal database
       including group membership synchronisation.
    7. **Portal token** — issue the portal-specific JWT that the frontend
       will use for all subsequent API calls.
    8. **Session persistence** — record the session for admin visibility.
    9. **Redirect** — send the browser to ``/sso/callback?token=...`` where
       the React frontend picks up the token.

    Query Parameters:
        code: Authorization code from Authentik.
        state: Signed state token for CSRF validation.
        error: Error code if Authentik denied the request.
        error_description: Human-readable error description.

    Returns:
        RedirectResponse: ``302`` redirect to the frontend callback page.
    """
    ip = _client_ip(request)
    ua = _client_ua(request)

    # --- Step 1: Check for errors from Authentik ---
    if error:
        logger.error(
            "[SSO] Authentik returned error=%s description='%s' ip=%s",
            error, error_description, ip,
        )
        _log_sso_failure(db, error_description or error, ip, ua)
        return RedirectResponse(
            url=f"/login?sso_error={error_description or error}",
            status_code=status.HTTP_302_FOUND,
        )

    # --- Step 2: Validate required parameters ---
    if not code or not state:
        logger.error("[SSO] Callback missing code or state — code=%s state=%s", bool(code), bool(state))
        _log_sso_failure(db, "Missing code or state parameter", ip, ua)
        return RedirectResponse(
            url="/login?sso_error=Invalid+callback+parameters",
            status_code=status.HTTP_302_FOUND,
        )

    # --- Step 3: Verify the state token (CSRF protection) ---
    if not verify_state_token(state):
        logger.error("[SSO] Invalid or expired state token from ip=%s", ip)
        _log_sso_failure(db, "Invalid or expired state token", ip, ua)
        return RedirectResponse(
            url="/login?sso_error=Invalid+state+token.+Please+try+again.",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        # --- Step 4: Exchange the authorization code for tokens ---
        token_response = await exchange_code_for_tokens(code)
        id_token_raw = token_response.get("id_token")
        access_token = token_response.get("access_token")

        if not id_token_raw:
            raise RuntimeError("No id_token in token response")

        # --- Step 5: Validate the ID token ---
        claims = await validate_id_token(id_token_raw)

        # --- Step 6: Fetch userinfo if groups/email missing ---
        if "groups" not in claims or "email" not in claims:
            logger.info("[SSO] ID token missing groups or email — fetching userinfo")
            userinfo = await fetch_userinfo(access_token)
            if "groups" not in claims and "groups" in userinfo:
                claims["groups"] = userinfo["groups"]
            if "email" not in claims and "email" in userinfo:
                claims["email"] = userinfo["email"]
            if "name" not in claims and "name" in userinfo:
                claims["name"] = userinfo["name"]
            if "preferred_username" not in claims and "preferred_username" in userinfo:
                claims["preferred_username"] = userinfo["preferred_username"]

        # --- Step 7: Upsert user and sync groups ---
        user = upsert_sso_user(db, claims, ip_address=ip, user_agent=ua)

        # --- Step 8: Issue portal-specific JWT ---
        portal_token, expires_at = issue_portal_token(user)

        # --- Step 9: Persist the session ---
        persist_session(
            db, user, portal_token,
            auth_method="sso",
            expires_at=expires_at,
            ip_address=ip,
            user_agent=ua,
        )

        logger.info(
            "[SSO] SSO login complete — user_id=%d username=%s email=%s ip=%s",
            user.id, user.username, user.email, ip,
        )

        # --- Step 10: Redirect to frontend with portal token ---
        return RedirectResponse(
            url=f"/sso/callback?token={portal_token}",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as exc:
        logger.error("[SSO] SSO callback processing failed: %s", exc, exc_info=True)
        _log_sso_failure(db, str(exc), ip, ua)
        return RedirectResponse(
            url="/login?sso_error=Authentication+failed.+Please+try+again.",
            status_code=status.HTTP_302_FOUND,
        )


# -------------------------------------------------------------------
# Internal helper — log SSO failures for admin analytics
# -------------------------------------------------------------------

def _log_sso_failure(
    db: Session,
    error_message: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    """
    Record a failed SSO login attempt in the activity log.

    This allows admins to see failed SSO attempts in the Analytics tab
    and investigate potential issues with the identity provider.
    """
    try:
        activity = UserActivity(
            user_id=None,
            activity_type="login",
            action="SSO login failed",
            status="failure",
            ip_address=ip_address,
            user_agent=user_agent,
            activity_metadata={"auth_method": "sso"},
            error_message=error_message,
        )
        db.add(activity)
        db.commit()
        logger.info("[SSO] Failure event logged — error='%s' ip=%s", error_message, ip_address)
    except Exception as log_exc:
        logger.error("[SSO] Failed to log SSO failure event: %s", log_exc)
        db.rollback()
