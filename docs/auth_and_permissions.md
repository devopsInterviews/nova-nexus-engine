# Authentication and Permissions Flow

This document explains how authentication (both Local and SSO) and tab-based authorization work in the MCP Client Portal.

## 1. Authentication Flow

The portal supports two parallel authentication paths. Regardless of which path a user takes, they end up with the same **Portal JWT Token**, which is used by the frontend to authenticate against the backend API.

### Local Login Path
1. **User Action:** User enters their username and password on the login screen.
2. **Backend Validation:** The frontend sends a `POST /api/login` request. The backend verifies the hash against the local `users` database table.
3. **Token Issuance:** If valid, the backend creates a Portal JWT Token (signed with the portal's `SECRET_KEY` / `JWT_SECRET_KEY` environment variable).
4. **Session Persistence:** The session is saved to the `user_sessions` table, and a login event is written to `user_activities`.

### SSO (OpenID Connect) Path
1. **User Action:** User clicks "Login with Company Credentials".
2. **Redirect to IdP:** Frontend hits `GET /api/sso/login`. The backend generates a secure `state` parameter (a short-lived, signed JWT to prevent CSRF) and redirects the browser to the Authentik (or other IdP) authorization endpoint.
3. **IdP Authentication:** The user signs into their company account.
4. **Callback:** Authentik redirects back to `GET /api/sso/callback` with an authorization `code`.
5. **Token Exchange:** The backend securely exchanges the `code` with Authentik for an `id_token` and an `access_token` (Server-to-Server).
6. **OIDC Validation:** The backend validates the `id_token`'s signature using the provider's JWKS (JSON Web Key Set). 
7. **User Upsert:** The backend reads the claims (email, name, groups) from the `id_token` (or queries the userinfo endpoint). It automatically creates or updates the user in the `users` table and synchronizes their group memberships in the `sso_groups` table.
8. **Portal Token Issuance:** The backend issues a **Portal JWT Token** (the exact same format as the local login token), completely independent from the OIDC token. The Authentik tokens are discarded; the portal relies purely on its own JWT from this point forward.
9. **Redirect to Frontend:** The backend redirects the browser to `/sso/callback?token=<portal_jwt_token>`. The React app captures this token, saves it to `localStorage`, and logs the user in.

**Key Concept:** We **do not** check the OIDC token on every request. The OIDC token is solely used during the login handshake to verify identity. Once verified, the portal produces its own JWT.

## 2. The Portal JWT Token

The token sent back to the frontend (and subsequently used as a `Bearer` token in the `Authorization` header for all `/api/*` calls) is signed using the portal's `SECRET_KEY`.

**What it contains:**
```json
{
  "user_id": 1,
  "sub": "johndoe",
  "auth_provider": "sso", // or "local"
  "exp": 1725114000 // Expiration timestamp
}
```

Notice that the token **does not** contain the user's groups or permissions. Because permissions can change dynamically while a user is logged in, we evaluate permissions on the fly in the backend.

## 3. Authorization and Permissions Flow

Authorization in the portal is strictly Tab-Based. Permissions are assigned to either individual Users or entire SSO Groups. If a user is granted access to a tab, they can view the tab in the frontend and execute the backend APIs associated with it.

### The Database Truth
Permissions are stored in the `tab_permissions` database table, linking a `tab_name` to either a `user_id` or a `group_id`.

### Backend Validation (API Protection)
When the frontend makes a request to a protected API endpoint (e.g., `GET /api/database/list`):
1. The backend middleware intercepts the request and reads the `Bearer` token.
2. The `require_tab_permission("BI")` dependency decodes the token and fetches the user from the database.
3. The backend calculates `get_user_allowed_tabs(user, db)`:
   - If the user is an admin (`is_admin=True` or username `admin`), they get all tabs.
   - Otherwise, the backend queries `tab_permissions` for any records matching the user's ID **or** any of the Group IDs the user belongs to.
   - It also automatically appends any tabs defined in the `DEFAULT_ALLOWED_TABS` environment variable (e.g., Home, Settings).
4. If the required tab (e.g., "BI") is in the user's allowed list, the request proceeds. If not, the backend throws a `403 Forbidden` error.

### Frontend Validation (UI Protection)
The frontend must accurately reflect what the backend allows, ensuring a seamless user experience.
1. When the app loads or the user logs in, the frontend calls `GET /api/profile` (or `/api/users/me`).
2. The backend responds with the user profile, which includes the dynamically calculated `allowed_tabs` array.
3. **Sidebar Rendering:** The `AppSidebar.tsx` component iterates through its navigation items. If a tab is not in the user's `allowed_tabs` array, it is hidden from the menu.
4. **URL Navigation:** The `PrivateRoute` wrapper around React Router checks if the user tries to manually navigate to a URL they shouldn't access. If they try to bypass the sidebar by typing `/bi` directly into the browser, the frontend router checks `user.allowed_tabs` and redirects them to a `Forbidden` Access Denied page.

## Summary of Environment Variables

- `SSO_ENABLED` (true/false): Tells the backend whether to accept SSO connections and the frontend whether to show the SSO login button.
- `OIDC_ISSUER_URL`: The Authentik application issuer URL (used for discovery and token validation).
- `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET`: Credentials to authenticate the portal to Authentik.
- `OIDC_REDIRECT_URI`: The backend callback URL (e.g., `http://localhost:8000/api/sso/callback`).
- `SECRET_KEY` / `JWT_SECRET_KEY`: The cryptographic secret used by the portal to sign its own session tokens.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: How long the portal session lasts before the user must log in again.
- `DEFAULT_ALLOWED_TABS`: A comma-separated list of tabs (e.g., "Home,Settings") that every authenticated user receives automatically, regardless of specific database permissions.