"""
SSO / OIDC Service for Authentik Integration.

This module implements the full OpenID Connect Authorization Code flow so that
portal users can authenticate via the company identity provider (Authentik).

Responsibilities
~~~~~~~~~~~~~~~~
1. **OIDC Discovery** — fetch provider metadata from the well-known endpoint
   so the portal never hard-codes Authentik URLs.
2. **Authorization URL** — build the redirect URL the browser follows to begin
   the Authentik login.
3. **Token Exchange** — swap the authorization code for ID / access tokens.
4. **ID Token Validation** — verify the cryptographic signature and standard
   claims (issuer, audience, expiry) using the provider's published JWKS.
5. **User Upsert** — create or update the portal ``User`` row from OIDC claims
   so the database is always the source of truth for identity.
6. **Group Sync** — reconcile the ``groups`` claim with the ``sso_groups`` and
   ``user_group_association`` tables.
7. **Login Event Logging** — record every SSO login attempt (success / failure)
   in the ``user_activities`` table for admin analytics.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~
* ``SSO_ENABLED``          — ``"true"`` to activate SSO (default ``"false"``).
* ``OIDC_ISSUER_URL``      — Authentik application provider URL.
* ``OIDC_CLIENT_ID``       — OAuth 2.0 client identifier.
* ``OIDC_CLIENT_SECRET``   — OAuth 2.0 client secret.
* ``OIDC_REDIRECT_URI``    — Callback URL registered in Authentik
                              (e.g. ``https://portal.company.com/api/sso/callback``).
* ``OIDC_SCOPES``          — Space-separated scopes (default
                              ``"openid email profile groups"``).

Security Notes
~~~~~~~~~~~~~~
* The ``state`` parameter is a short-lived, signed JWT so the portal does not
  need server-side session storage during the OIDC handshake.
* JWKS keys are cached in-memory and refreshed every 3 600 s (1 h) to avoid
  hitting the provider on every login.
* SSO users have ``hashed_password = NULL`` — they **cannot** fall back to
  local password login unless an admin explicitly sets one.
"""

import os
import time
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from jose import JWTError, jwt, jwk
from jose.utils import base64url_decode
from sqlalchemy.orm import Session

from app.models import User, UserActivity, SSOGroup, UserSession, user_group_association

logger = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------------------------
# Configuration — all values come from environment variables so the portal
# can be deployed to different environments without code changes.
# ---------------------------------------------------------------------------

SSO_ENABLED: bool = os.getenv("SSO_ENABLED", "false").lower() in ("true", "1", "yes")
OIDC_ISSUER_URL: str = os.getenv("OIDC_ISSUER_URL", "")
OIDC_CLIENT_ID: str = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET: str = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI: str = os.getenv("OIDC_REDIRECT_URI", "")
OIDC_SCOPES: str = os.getenv("OIDC_SCOPES", "openid email profile groups")

# Portal JWT settings (reused from auth_routes for consistency)
PORTAL_JWT_SECRET: str = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET_KEY", "your_default_secret_key"))
PORTAL_JWT_ALGORITHM: str = "HS256"
PORTAL_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# In-memory cache for OIDC discovery and JWKS
_oidc_config_cache: Dict[str, Any] = {}
_oidc_config_cache_time: float = 0.0
_jwks_cache: Dict[str, Any] = {}
_jwks_cache_time: float = 0.0
CACHE_TTL_SECONDS: int = 3600


# ===================================================================
# OIDC Discovery
# ===================================================================

async def get_oidc_config() -> Dict[str, Any]:
    """
    Fetch and cache the OpenID Connect discovery document.

    The discovery document lives at ``{issuer}/.well-known/openid-configuration``
    and contains the authorization, token, userinfo, and JWKS endpoints.

    Returns:
        dict: Parsed JSON of the OIDC discovery document.

    Raises:
        RuntimeError: If the discovery document cannot be fetched.
    """
    global _oidc_config_cache, _oidc_config_cache_time

    now = time.time()
    if _oidc_config_cache and (now - _oidc_config_cache_time) < CACHE_TTL_SECONDS:
        logger.debug("[SSO] Returning cached OIDC discovery document")
        return _oidc_config_cache

    discovery_url = f"{OIDC_ISSUER_URL.rstrip('/')}/.well-known/openid-configuration"
    logger.info("[SSO] Fetching OIDC discovery document from %s", discovery_url)

    async with httpx.AsyncClient(verify=True, timeout=15.0) as client:
        resp = await client.get(discovery_url)
        if resp.status_code != 200:
            logger.error(
                "[SSO] Failed to fetch OIDC discovery: HTTP %d — %s",
                resp.status_code, resp.text,
            )
            raise RuntimeError(f"OIDC discovery failed with HTTP {resp.status_code}")

    _oidc_config_cache = resp.json()
    _oidc_config_cache_time = now
    logger.info(
        "[SSO] OIDC discovery loaded — authorization_endpoint=%s, token_endpoint=%s",
        _oidc_config_cache.get("authorization_endpoint"),
        _oidc_config_cache.get("token_endpoint"),
    )
    return _oidc_config_cache


async def get_jwks() -> Dict[str, Any]:
    """
    Fetch and cache the provider's JSON Web Key Set (JWKS).

    The JWKS is used to verify the cryptographic signature of ID tokens.

    Returns:
        dict: Parsed JWKS document with ``keys`` array.
    """
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < CACHE_TTL_SECONDS:
        logger.debug("[SSO] Returning cached JWKS")
        return _jwks_cache

    oidc_config = await get_oidc_config()
    jwks_uri = oidc_config["jwks_uri"]
    logger.info("[SSO] Fetching JWKS from %s", jwks_uri)

    async with httpx.AsyncClient(verify=True, timeout=15.0) as client:
        resp = await client.get(jwks_uri)
        if resp.status_code != 200:
            logger.error("[SSO] Failed to fetch JWKS: HTTP %d", resp.status_code)
            raise RuntimeError(f"JWKS fetch failed with HTTP {resp.status_code}")

    _jwks_cache = resp.json()
    _jwks_cache_time = now
    logger.info("[SSO] JWKS loaded — %d key(s) available", len(_jwks_cache.get("keys", [])))
    return _jwks_cache


# ===================================================================
# Authorization URL
# ===================================================================

def build_authorization_url(state: str) -> str:
    """
    Construct the Authentik authorization URL for the OIDC Authorization Code flow.

    The browser is redirected to this URL so the user can authenticate
    with their company credentials.

    Args:
        state: An opaque, signed value used for CSRF protection.

    Returns:
        str: Full authorization URL with query parameters.
    """
    # We build the URL synchronously from the cached config; callers must
    # ensure the config has been fetched at least once.
    authorization_endpoint = _oidc_config_cache.get("authorization_endpoint", "")
    if not authorization_endpoint:
        raise RuntimeError("OIDC config not loaded — call get_oidc_config() first")

    params = {
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": OIDC_SCOPES,
        "state": state,
    }
    query_string = "&".join(f"{k}={httpx.URL(v) if k == 'redirect_uri' else v}" for k, v in params.items())
    # Use proper URL encoding via httpx
    url = str(httpx.URL(authorization_endpoint).copy_merge_params(params))
    logger.info("[SSO] Built authorization URL (client_id=%s, scopes=%s)", OIDC_CLIENT_ID, OIDC_SCOPES)
    return url


def create_state_token() -> str:
    """
    Create a short-lived, signed JWT used as the OIDC ``state`` parameter.

    Embedding the state in a JWT avoids the need for server-side session
    storage during the OIDC handshake.  The token is verified on callback
    to prevent CSRF attacks.

    Returns:
        str: Signed JWT that expires in 10 minutes.
    """
    payload = {
        "nonce": secrets.token_urlsafe(24),
        "exp": datetime.utcnow() + timedelta(minutes=10),
        "type": "oidc_state",
    }
    token = jwt.encode(payload, PORTAL_JWT_SECRET, algorithm=PORTAL_JWT_ALGORITHM)
    logger.debug("[SSO] Created OIDC state token (expires in 10 min)")
    return token


def verify_state_token(state: str) -> bool:
    """
    Verify the ``state`` token returned in the OIDC callback.

    Args:
        state: The state parameter from the callback query string.

    Returns:
        True if the token is valid and not expired, False otherwise.
    """
    try:
        payload = jwt.decode(state, PORTAL_JWT_SECRET, algorithms=[PORTAL_JWT_ALGORITHM])
        if payload.get("type") != "oidc_state":
            logger.warning("[SSO] State token has wrong type: %s", payload.get("type"))
            return False
        logger.debug("[SSO] State token verified successfully")
        return True
    except JWTError as exc:
        logger.warning("[SSO] State token verification failed: %s", exc)
        return False


# ===================================================================
# Token Exchange
# ===================================================================

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """
    Exchange the authorization code for ID and access tokens.

    This is step 2 of the Authorization Code flow — the backend sends the
    code to Authentik's token endpoint along with the client credentials.

    Args:
        code: The authorization code received from Authentik.

    Returns:
        dict: Token response containing ``id_token``, ``access_token``, etc.

    Raises:
        RuntimeError: If the token exchange fails.
    """
    oidc_config = await get_oidc_config()
    token_endpoint = oidc_config["token_endpoint"]

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OIDC_REDIRECT_URI,
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
    }

    logger.info("[SSO] Exchanging authorization code at %s", token_endpoint)

    async with httpx.AsyncClient(verify=True, timeout=15.0) as client:
        resp = await client.post(token_endpoint, data=payload)
        if resp.status_code != 200:
            logger.error(
                "[SSO] Token exchange failed: HTTP %d — %s",
                resp.status_code, resp.text,
            )
            raise RuntimeError(f"Token exchange failed with HTTP {resp.status_code}: {resp.text}")

    token_data = resp.json()
    logger.info("[SSO] Token exchange successful — received id_token and access_token")
    return token_data


# ===================================================================
# ID Token Validation
# ===================================================================

async def validate_id_token(id_token: str) -> Dict[str, Any]:
    """
    Validate and decode the OIDC ID token using the provider's JWKS.

    Validation checks:
    * Signature verified against Authentik's published keys.
    * ``iss`` (issuer) matches the configured issuer URL.
    * ``aud`` (audience) contains the portal's client ID.
    * ``exp`` (expiry) has not passed.

    Args:
        id_token: The raw JWT string from the token response.

    Returns:
        dict: Decoded ID token claims.

    Raises:
        RuntimeError: If validation fails for any reason.
    """
    jwks_data = await get_jwks()

    # Decode the token header to find the signing key
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    logger.debug("[SSO] ID token header kid=%s, alg=%s", kid, unverified_header.get("alg"))

    # Find the matching key in the JWKS
    signing_key = None
    for key_data in jwks_data.get("keys", []):
        if key_data.get("kid") == kid:
            signing_key = key_data
            break

    if not signing_key:
        logger.error("[SSO] No matching key found in JWKS for kid=%s", kid)
        raise RuntimeError(f"No matching JWKS key for kid={kid}")

    # Determine the expected issuer — Authentik may or may not include a
    # trailing slash; accept both.
    issuer = OIDC_ISSUER_URL.rstrip("/")

    try:
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=OIDC_CLIENT_ID,
            issuer=[issuer, issuer + "/"],
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        logger.error("[SSO] ID token validation failed: %s", exc)
        raise RuntimeError(f"ID token validation failed: {exc}")

    logger.info(
        "[SSO] ID token validated — sub=%s, email=%s, name=%s, groups=%s",
        claims.get("sub"),
        claims.get("email"),
        claims.get("name", claims.get("preferred_username")),
        claims.get("groups", []),
    )
    return claims


# ===================================================================
# UserInfo (fallback for missing claims)
# ===================================================================

async def fetch_userinfo(access_token: str) -> Dict[str, Any]:
    """
    Fetch additional user attributes from the OIDC UserInfo endpoint.

    This is used as a fallback when the ID token does not contain all
    required claims (e.g. ``groups``).

    Args:
        access_token: The OAuth 2.0 access token.

    Returns:
        dict: UserInfo claims.
    """
    oidc_config = await get_oidc_config()
    userinfo_endpoint = oidc_config.get("userinfo_endpoint")
    if not userinfo_endpoint:
        logger.warning("[SSO] No userinfo_endpoint in OIDC config")
        return {}

    logger.info("[SSO] Fetching userinfo from %s", userinfo_endpoint)

    async with httpx.AsyncClient(verify=True, timeout=15.0) as client:
        resp = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            logger.warning("[SSO] UserInfo request failed: HTTP %d", resp.status_code)
            return {}

    userinfo = resp.json()
    logger.info("[SSO] UserInfo received — keys: %s", list(userinfo.keys()))
    return userinfo


# ===================================================================
# User Upsert — create or update from OIDC claims
# ===================================================================

def upsert_sso_user(
    db: Session,
    claims: Dict[str, Any],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """
    Create or update a portal user from OIDC identity claims.

    On **first login** the portal automatically creates the user in the
    ``users`` table using attributes from Authentik (email, full name,
    group membership).

    On **subsequent logins** the portal refreshes identity fields (name,
    email, groups) and continues the login statistics and activity logging.

    Args:
        db: Active SQLAlchemy session.
        claims: Decoded ID token / UserInfo claims.
        ip_address: Client IP for audit logging.
        user_agent: Client user-agent for audit logging.

    Returns:
        User: The created or updated user object.
    """
    sub = claims.get("sub")
    email = claims.get("email", "")
    full_name = claims.get("name") or claims.get("preferred_username") or ""
    preferred_username = claims.get("preferred_username") or email.split("@")[0] if email else sub
    groups_claim: List[str] = claims.get("groups", [])

    logger.info(
        "[SSO] Upserting user — sub=%s, email=%s, username=%s, groups=%s",
        sub, email, preferred_username, groups_claim,
    )

    # Look up by SSO subject ID first, then fall back to email
    user = db.query(User).filter(User.sso_subject_id == sub).first()
    is_new_user = False

    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            logger.info(
                "[SSO] Matched existing user by email=%s (id=%d), linking SSO subject",
                email, user.id,
            )

    if user:
        # Refresh identity fields from Authentik on every login
        user.email = email or user.email
        user.full_name = full_name or user.full_name
        user.sso_subject_id = sub
        user.auth_provider = "sso"
        logger.info("[SSO] Updated existing user id=%d username=%s", user.id, user.username)
    else:
        # First-time SSO login — create a new user
        is_new_user = True
        # Ensure username uniqueness
        base_username = preferred_username
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=None,
            is_active=True,
            is_admin=False,
            auth_provider="sso",
            sso_subject_id=sub,
            preferences={},
        )
        db.add(user)
        db.flush()
        logger.info("[SSO] Created new SSO user id=%d username=%s", user.id, user.username)

    # Update login stats
    user.last_login = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1

    # Sync groups
    _sync_user_groups(db, user, groups_claim)

    # Log the login event
    _log_sso_login(db, user, is_new_user, ip_address, user_agent, claims)

    db.commit()
    db.refresh(user)
    return user


# ===================================================================
# Group Sync
# ===================================================================

def _sync_user_groups(db: Session, user: User, group_names: List[str]) -> None:
    """
    Reconcile the user's group membership with the ``groups`` claim.

    Groups are created on-the-fly if they don't exist.  The user's
    membership set is replaced entirely with what Authentik reports —
    Authentik is the source of truth for group membership.

    Args:
        db: Active SQLAlchemy session.
        user: The portal user whose groups are being synced.
        group_names: List of group names from the OIDC ``groups`` claim.
    """
    if not group_names:
        logger.debug("[SSO] No groups in claims for user id=%d — clearing memberships", user.id)
        user.groups = []
        return

    resolved_groups: List[SSOGroup] = []
    for name in group_names:
        group = db.query(SSOGroup).filter(SSOGroup.name == name).first()
        if not group:
            group = SSOGroup(name=name, source="sso")
            db.add(group)
            db.flush()
            logger.info("[SSO] Created new SSO group: %s (id=%d)", name, group.id)
        resolved_groups.append(group)

    user.groups = resolved_groups
    logger.info(
        "[SSO] Synced groups for user id=%d: %s",
        user.id, [g.name for g in resolved_groups],
    )


# ===================================================================
# Login Event Logging
# ===================================================================

def _log_sso_login(
    db: Session,
    user: User,
    is_new_user: bool,
    ip_address: Optional[str],
    user_agent: Optional[str],
    claims: Dict[str, Any],
) -> None:
    """
    Record the SSO login event in the ``user_activities`` table.

    This powers the admin Analytics view: who logged in, when, how many
    times, and what identity attributes were received.

    Args:
        db: Active SQLAlchemy session.
        user: The authenticated user.
        is_new_user: Whether this is the user's first SSO login.
        ip_address: Client IP address.
        user_agent: Client user-agent string.
        claims: Raw OIDC claims for metadata capture.
    """
    action = "SSO first login — new user created" if is_new_user else "SSO login"
    metadata = {
        "auth_method": "sso",
        "login_count": user.login_count,
        "sso_subject_id": claims.get("sub"),
        "sso_email": claims.get("email"),
        "sso_groups": claims.get("groups", []),
        "is_new_user": is_new_user,
    }

    activity = UserActivity(
        user_id=user.id,
        activity_type="login",
        action=action,
        status="success",
        ip_address=ip_address,
        user_agent=user_agent,
        activity_metadata=metadata,
    )
    db.add(activity)
    logger.info(
        "[SSO] Login event logged — user_id=%d, action='%s', ip=%s",
        user.id, action, ip_address,
    )


# ===================================================================
# Portal Token Issuance
# ===================================================================

def issue_portal_token(user: User) -> Tuple[str, datetime]:
    """
    Issue a portal-specific JWT for the authenticated SSO user.

    After the Authentik login succeeds the portal still uses its own JWT
    (``Authorization: Bearer <portal-token>``) for all API calls.  This
    matches the existing local-login flow so the rest of the codebase
    does not need to distinguish between auth methods.

    Args:
        user: The authenticated portal user.

    Returns:
        tuple: ``(jwt_string, expiry_datetime)``
    """
    expires_at = datetime.utcnow() + timedelta(minutes=PORTAL_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user.id,
        "sub": user.username,
        "auth_provider": user.auth_provider,
        "exp": expires_at,
    }
    token = jwt.encode(payload, PORTAL_JWT_SECRET, algorithm=PORTAL_JWT_ALGORITHM)
    logger.info(
        "[SSO] Issued portal token for user id=%d username=%s (expires %s)",
        user.id, user.username, expires_at.isoformat(),
    )
    return token, expires_at


def persist_session(
    db: Session,
    user: User,
    token: str,
    auth_method: str,
    expires_at: datetime,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserSession:
    """
    Persist a session record so admins can see active sessions and revoke them.

    The raw JWT is **never** stored — only a SHA-256 hash is kept.

    Args:
        db: Active SQLAlchemy session.
        user: The authenticated user.
        token: The raw portal JWT (will be hashed before storage).
        auth_method: ``"local"`` or ``"sso"``.
        expires_at: Token expiration datetime.
        ip_address: Client IP address.
        user_agent: Client user-agent string.

    Returns:
        UserSession: The persisted session record.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        auth_method=auth_method,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)
    db.commit()
    logger.info(
        "[SSO] Session persisted — user_id=%d, auth_method=%s, token_hash=%s…",
        user.id, auth_method, token_hash[:12],
    )
    return session
