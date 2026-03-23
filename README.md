# CorteX

An internal enterprise AI platform that connects language models, tools, data, and teams in one place. It gives engineers a governed, self-service layer for deploying AI Agents and MCP Servers, running AI-assisted binary analysis, querying databases with natural language, and administering the platform — all from a single web UI.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Docker (recommended)](#docker-recommended)
  - [Manual setup](#manual-setup)
- [Configuration](#configuration)
- [Deployment](#deployment)
  - [Helm / Kubernetes](#helm--kubernetes)
- [Authentication](#authentication)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)

---

## Overview

The AI portal is a full-stack web application — FastAPI backend, React/TypeScript frontend — served as a single Docker container. It is designed to run inside a private Kubernetes cluster and acts as the central control plane for an organisation's AI tooling.

**Core goals:**

- Let any engineer deploy and share AI Agents and MCP Servers without DevOps involvement for every change.
- Provide AI-assisted tooling for reverse engineers (IDA Pro ↔ LLM), database analysts, and DevOps teams.
- Enforce access control through tab-based RBAC tied to OIDC group membership, so teams only see what they need.
- Give administrators full visibility into usage, deployments, and permissions from one interface.

---

## Features

### AI Marketplace

The internal App Store for AI Agents and MCP Servers.

- Create, deploy, redeploy, clone, and delete Agents and MCP Servers.
- Helm chart discovery and version selection from Artifactory (dev and release registries).
- Per-user creation limits configurable via environment variables; admins are unrestricted.
- Dev deployments have a configurable TTL (default 10 days) with automatic expiry via a background cleanup thread.
- A background cluster-sync thread reconciles the DB state against live Helm releases every 10 minutes and warns on drift.
- Public `/api/marketplace/ping` endpoint for deployed agents and MCP servers to self-report call metrics — no authentication required.
- Agents and MCP Servers can be forked by any user.
- MCP Server tool lists are auto-discovered from the live deployment endpoint after each deploy.

### Binary File Research (IDA MCP)

Connects IDA Pro workstations to a language model via the Model Context Protocol.

- Each user provisions their own dedicated MCP server pod in Kubernetes from the portal.
- Available server versions are pulled from an Artifactory Docker registry.
- Full lifecycle management: deploy, upgrade, undeploy, version tracking.
- Admin view showing all users' active deployments.
- Deployment state machine: `NEW → DEPLOYING → DEPLOYED → UNDEPLOYED / ERROR`.
- Full audit trail of every deploy and undeploy event.
- In-cluster nginx reverse proxy (IDA Proxy) routes external traffic to individual IDA workstations; port mappings are stored in Kubernetes ConfigMaps and optionally synced to Bitbucket for ArgoCD GitOps.

### Business Intelligence

AI-assisted database querying and schema exploration.

- Save multiple named database connection profiles (PostgreSQL, MySQL, and others).
- Natural language → SQL using a configurable LLM backend.
- Column suggestion from saved schema metadata, with AI-ranked relevance scoring.
- Sync database schemas to internal tables for schema-aware completions.
- dbt manifest upload and AI-assisted iterative SQL query generation with lineage awareness.
- Query result display with export.

### Analytics Dashboard

System-level observability for administrators.

- Active sessions, daily/weekly active users, login counts.
- HTTP request traffic over time with p95 response time.
- Top pages and feature usage breakdown.
- Error categorisation and rate trends.
- MCP server health status monitoring.
- Portal database health and connection status.
- Per-user activity breakdown over a 30-day sliding window.

### SSO / OIDC Integration

- Authentik OIDC provider out of the box (configurable to any compliant provider).
- Authorization Code flow; `openid email profile groups` scopes.
- Group membership synced at every login; groups mapped directly to tab permissions.
- Groups can be granted admin access, giving all members full portal access.
- Local accounts and SSO accounts coexist — users are disambiguated by `auth_provider` field.

### Administration

- User Management: create local users, change passwords, delete non-admin users, view login history and active sessions in real time.
- Permissions: per-tab access control for individual users and SSO groups. Configure which users or groups can access each portal section.
- Groups: read-only view of all SSO groups and their currently granted tabs.
- Database Tables: browse and preview internal portal database tables with pagination.

### DevOps Integrations

Dedicated tabs for Bitbucket, Jenkins, Jira, and Logs.

### MCP Connections & Tests

- Connect to external MCP servers, list available tools, and execute them interactively.
- Save and replay test configurations for both MCP clients and MCP servers.

---

## Architecture

```
nova-nexus-engine/
├── app/                         # Python FastAPI backend
│   ├── client.py                # Application entrypoint; router registration, startup hooks
│   ├── models.py                # SQLAlchemy ORM models
│   ├── database.py              # Session management, schema migrations
│   ├── auth.py                  # JWT utilities, password hashing
│   ├── llm_client.py            # OpenAI-compatible LLM client
│   ├── prompts.py               # LLM prompt templates
│   ├── middleware/
│   │   └── analytics_middleware.py  # Request logging on every HTTP call
│   ├── routes/
│   │   ├── auth_routes.py           # Login, /me, logout, profile
│   │   ├── users_routes.py          # User CRUD, role management
│   │   ├── permissions_routes.py    # Tab permissions, admin groups
│   │   ├── marketplace_routes.py    # Marketplace lifecycle + public ping
│   │   ├── research_routes.py       # IDA MCP deploy/upgrade/status
│   │   ├── db_routes.py             # DB connections, SQL, dbt
│   │   ├── analytics_routes.py      # System metrics APIs
│   │   ├── mcp_routes.py            # External MCP server connections
│   │   ├── sso_routes.py            # OIDC flow, group sync
│   │   ├── test_routes.py           # MCP test execution
│   │   └── internal_data_routes.py  # Internal table inspection
│   └── services/
│       ├── analytics_service.py     # Metrics aggregation, MCP health monitoring
│       ├── artifactory_client.py    # Docker/Helm/PyPI version discovery with TTL cache
│       ├── bitbucket_client.py      # GitOps: writes proxy port mappings to Bitbucket
│       ├── dbt_analysis_service.py  # dbt manifest parsing, dependency graph, iterative SQL
│       ├── k8s_controller.py        # In-cluster Kubernetes pod lifecycle controller
│       └── sso_service.py           # OIDC token exchange, user/group upsert
│
├── ui/                          # React 18 + TypeScript frontend (Vite)
│   └── src/
│       ├── App.tsx              # Root router and provider hierarchy
│       ├── pages/               # One file per route
│       │   ├── Home.tsx         # Feature overview dashboard
│       │   ├── Marketplace.tsx  # AI Marketplace
│       │   ├── Research.tsx     # IDA MCP bridge
│       │   ├── BI.tsx           # Business Intelligence
│       │   ├── Analytics.tsx    # System analytics
│       │   ├── Users.tsx        # Administration (users, permissions, groups, tables)
│       │   ├── DevOps.tsx       # DevOps integrations
│       │   ├── Tests.tsx        # MCP test runner
│       │   └── Settings.tsx     # User preferences
│       ├── components/
│       │   ├── layout/          # AppSidebar, AppHeader, GlobalCommandPalette
│       │   ├── admin/           # PermissionsManager, TableDataPreview
│       │   ├── bi/              # ConnectDBTab, SQLBuilderTab, SqlBuilderDbtTab, SyncTablesTab
│       │   ├── devops/          # BitbucketTab, JenkinsTab, JiraTab, LogsTab
│       │   └── tests/           # McpClientTestTab, McpServerTestTab
│       ├── context/
│       │   ├── auth-context.tsx       # JWT state, allowed_tabs, user profile
│       │   └── connection-context.tsx # Active DB connection profile
│       └── lib/
│           └── api-service.ts   # Typed API client layer
│
├── mcp-server/                  # Standalone MCP server (Confluence + DB introspection tools)
│
├── charts/                      # Helm chart for Kubernetes deployment
│   └── mcp-client/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/           # Deployment, Service, Ingress, PostgreSQL, IDA Proxy, RBAC
│
├── Dockerfile                   # Multi-stage build: Node 20 → Python 3.13 → minimal image
├── docker-compose.yml           # Dev stack: PostgreSQL 15 + app
├── main.py                      # Uvicorn entrypoint
├── requirements.txt
└── .env.example                 # Full environment variable reference
```

### Request flow

```
Browser → React SPA (served as static files from FastAPI)
              │
              └─ /api/* → FastAPI routes
                              │
                    ┌─────────┴───────────┐
                    │                     │
              Auth middleware        Tab RBAC check
              (JWT validation)       (TabPermission lookup)
                    │
              Route handler → SQLAlchemy → PostgreSQL
                    │
              Optional external calls:
                - Infra API (Helm deploy/delete)
                - Artifactory (chart/image versions)
                - Kubernetes API (IDA MCP pod management)
                - LLM API (SQL generation, analysis)
                - Bitbucket API (GitOps port mappings)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.13 |
| Backend framework | FastAPI + Uvicorn (ASGI) |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL 15 |
| Auth | JWT HS256 (`python-jose`), bcrypt (`passlib`) |
| SSO | OIDC / Authentik (`httpx`, `PyJWT`) |
| Kubernetes | `kubernetes` Python client (in-cluster) |
| Artifactory | REST API with TTL-cached responses |
| LLM | Any OpenAI-compatible API (`httpx`) |
| MCP | `mcp` Python SDK |
| Frontend language | TypeScript 5 |
| Frontend framework | React 18 |
| Build tool | Vite 5 + SWC |
| UI library | shadcn/ui (Radix UI) + Tailwind CSS 3 |
| State management | TanStack Query v5, React Context |
| Routing | React Router v6 |
| Forms | React Hook Form v7 + Zod |
| Animations | Framer Motion |
| Charts | Recharts |
| Icons | Lucide React |
| Toasts | Sonner |
| Container | Docker (multi-stage, non-root `appuser`) |
| Orchestration | Kubernetes + Helm 3 |

---

## Getting Started

### Docker (recommended)

The fastest way to run the portal locally. A single container serves both the frontend and backend.

```bash
git clone <repository-url>
cd nova-nexus-engine
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY and ADMIN_PASSWORD at minimum
docker-compose up --build
```

The application will be available at `http://localhost:8000`. The API documentation (OpenAPI) is at `http://localhost:8000/docs`.

Default credentials (configured via `ADMIN_PASSWORD` in `.env`):

```
Username: admin
Password: <value of ADMIN_PASSWORD>
```

### Manual setup

#### Prerequisites

- Python 3.13
- Node.js 20+
- PostgreSQL 15

#### Backend

```bash
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit DATABASE_URL, JWT_SECRET_KEY, ADMIN_PASSWORD

# Start the server (tables are created automatically on first run)
python main.py
```

The API will be available at `http://localhost:8000`.

#### Frontend

```bash
cd ui
npm install
npm run dev
```

The dev server will be available at `http://localhost:5173` and proxies `/api` requests to the backend.

#### Frontend production build

```bash
cd ui
npm run build
# Built assets land in ui/dist/ and are served by FastAPI from /static
```

---

## Configuration

All configuration is through environment variables. Copy `.env.example` to `.env` and adjust as needed.

### Required

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string — e.g. `postgresql://user:pass@host/dbname` |
| `JWT_SECRET_KEY` | Secret used to sign portal JWTs. Use a long random string in production. |
| `ADMIN_PASSWORD` | Password for the auto-created `admin` account on first run. |

### Authentication & SSO

| Variable | Default | Description |
|---|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | JWT lifetime in minutes. |
| `SSO_ENABLED` | `false` | Enable Authentik OIDC login. |
| `OIDC_ISSUER_URL` | — | OIDC provider base URL (e.g. `https://auth.company.internal/application/o/portal`). |
| `OIDC_CLIENT_ID` | — | OAuth2 client ID registered in Authentik. |
| `OIDC_CLIENT_SECRET` | — | OAuth2 client secret. |
| `OIDC_REDIRECT_URI` | — | Callback URL — must match the provider configuration. |
| `OIDC_SCOPES` | `openid email profile groups` | Space-separated OIDC scopes. |
| `DEFAULT_ALLOWED_TABS` | `Home,Settings` | Tabs that every authenticated user can access without an explicit permission grant. |

### LLM

| Variable | Description |
|---|---|
| `LLM_API_URL` | Base URL of any OpenAI-compatible API (e.g. your internal vLLM or LiteLLM proxy). |
| `LLM_MODEL` | Model name to use for completions. |
| `LLM_API_KEY` | API key (can be a dummy value for private deployments). |
| `LLM_SSL_VERIFY` | Set to `false` to disable TLS verification for self-signed certs. |

### Marketplace

| Variable | Default | Description |
|---|---|---|
| `MARKETPLACE_MAX_AGENTS_PER_USER` | `5` | Maximum number of Agents a non-admin user can create. |
| `MARKETPLACE_MAX_MCP_PER_USER` | `5` | Maximum number of MCP Servers a non-admin user can create. |
| `MARKETPLACE_DEV_TTL_DAYS` | `10` | Days before a dev-environment deployment is automatically expired. |
| `INFRA_CHARTS_API_SERVER` | — | Base URL of the infra API used for Helm deploy/undeploy calls. |
| `ARTIFACTORY_MARKETPLACE_HELM_REPO_DEV` | — | Artifactory Helm repo name for dev charts. |
| `ARTIFACTORY_MARKETPLACE_HELM_REPO_RELEASE` | — | Artifactory Helm repo name for release charts. |

### IDA MCP Research

| Variable | Description |
|---|---|
| `INFRA_API_SERVER` | Base URL of the infra API for MCP pod provisioning. |
| `ARTIFACTORY_PYPI_REPO` | Artifactory PyPI repo for IDA plugin version discovery. |
| `ARTIFACTORY_PYPI_PACKAGE` | Package name to query for available versions. |
| `BITBUCKET_IDA_MCP_REPO` | Link to the IDA plugin Bitbucket repository shown to users. |
| `PIP_INSTALL_CMD_BASE` | Install command shown in the UI for the IDA plugin. |

### External links

| Variable | Description |
|---|---|
| `OPENWEBUI_URL` | URL of the internal OpenWebUI instance linked from the home page. |
| `CONFLUENCE_URL` | URL of the company Confluence shown as documentation link. |
| `DEVELOPER_AUTH_PORTAL_URL` | URL of the developer portal for generating LLM API keys. |

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_ENVIRONMENT` | — | Display label shown in the header (e.g. `Production`, `Staging`). |
| `APP_VERSION` | — | Version string shown in the header. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. Set to `DEBUG` for full request/response payloads on infra calls. |
| `CLIENT_HOST` | `0.0.0.0` | Uvicorn bind address. |
| `CLIENT_PORT` | `8000` | Uvicorn bind port. |

---

## Deployment

### Helm / Kubernetes

The portal ships with a Helm chart under `charts/mcp-client/`.

```bash
helm install ai-portal charts/mcp-client \
  --namespace ai-portal \
  --create-namespace \
  -f my-values.yaml
```

The chart provisions:

| Resource | Description |
|---|---|
| `Deployment` | Main portal application |
| `Service` | ClusterIP for the portal |
| `Ingress` | Optional ingress with TLS |
| PostgreSQL `Deployment + PVC + Secret + Service` | Optional in-cluster PostgreSQL (can be disabled in favour of an external managed DB) |
| IDA Proxy `Deployment + Service + ConfigMaps` | Nginx reverse proxy that routes external connections to individual IDA Pro workstations |
| `ServiceAccount + Role + RoleBinding` | RBAC for the in-cluster Kubernetes controller that manages MCP server pods |

Key `values.yaml` sections:

```yaml
image:
  repository: your-registry/nova-nexus-engine
  tag: latest

env:
  JWT_SECRET_KEY: ""
  ADMIN_PASSWORD: ""
  DATABASE_URL: ""
  SSO_ENABLED: "true"
  OIDC_ISSUER_URL: ""
  OIDC_CLIENT_ID: ""
  OIDC_CLIENT_SECRET: ""
  OIDC_REDIRECT_URI: ""
  LLM_API_URL: ""
  LLM_MODEL: ""
  INFRA_CHARTS_API_SERVER: ""

postgres:
  enabled: true          # set false to use an external DB

idaMcp:
  enabled: true

idaProxy:
  enabled: true
```

See `charts/mcp-client/values.yaml` for the full schema with comments.

### Docker image build

```bash
docker build -t nova-nexus-engine:latest .
```

The multi-stage build:
1. **Stage 1 (Node 20 Alpine):** Installs frontend dependencies and runs `vite build`.
2. **Stage 2 (Python 3.13 slim):** Installs Python dependencies; copies the built UI assets.
3. **Final image:** Minimal image running as non-root `appuser` on port 8000.

---

## Authentication

### Local login

1. User submits username and password to `POST /api/login`.
2. The backend verifies the bcrypt hash and issues a signed JWT (HS256, configurable expiry, default 2 hours).
3. The frontend stores the token in `localStorage` and includes it as `Authorization: Bearer <token>` on all API calls.
4. On expiry the user is automatically redirected to the login screen.

### SSO / OIDC (Authentik)

1. User clicks "Login with SSO" — the frontend redirects to `GET /api/login` which builds the Authentik authorization URL and redirects the browser.
2. After authentication, Authentik redirects to `GET /api/callback` with an authorization code.
3. The backend exchanges the code for tokens, validates the `id_token` against the OIDC JWKS, and extracts user and group claims.
4. The user record is upserted (`auth_provider = 'sso'`); their group memberships are synced to `sso_groups` and `user_group_association`.
5. The portal issues its own JWT and sends it to the frontend — from this point the flow is identical to local login.

### Tab-based RBAC

Every protected route is guarded by `require_tab_permission(tab_name)`. This dependency queries `tab_permissions` for a matching `user_id` or any of the user's `group_id`s. Admins (`is_admin = true`) bypass all tab checks. Certain tabs are always accessible to all authenticated users via `DEFAULT_ALLOWED_TABS`.

---

## Database Schema

| Table | Description |
|---|---|
| `users` | Core user accounts. Stores username, bcrypt hash, email, `is_admin`, `auth_provider`, login stats. |
| `sso_groups` | OIDC groups synced from the identity provider. `is_admin` flag grants full portal access to all members. |
| `user_group_association` | Many-to-many join between users and groups. |
| `user_sessions` | Active portal sessions for real-time online status tracking. |
| `tab_permissions` | Each row grants a specific `tab_name` to a `user_id` or `group_id`. |
| `database_connections` | Saved DB connection profiles (host, port, database, user, encrypted password). |
| `marketplace_items` | Agent and MCP Server records. Tracks name, type, owner, deployment status, environment, Helm chart, TTL. |
| `marketplace_usage` | Call/tool_use events for marketplace items. Used for usage count and unique user metrics. |
| `ida_mcp_connections` | Per-user IDA MCP deployment state. State machine: `NEW → DEPLOYING → DEPLOYED → UNDEPLOYED / ERROR`. |
| `ida_mcp_deploy_audit` | Immutable audit log of every deploy and undeploy event for IDA MCP servers. |
| `request_logs` | HTTP request performance log (path, method, status, duration, user, IP). |
| `page_views` | Frontend page navigation events for analytics. |
| `user_activities` | Detailed user action audit trail. |
| `system_metrics` | Point-in-time system performance snapshots. |
| `mcp_server_status` | Health status and last-seen timestamps for connected MCP servers. |
| `test_configurations` | Saved MCP test setups. |
| `test_executions` | Stored test run results. |
| `database_sessions` | Query session tracking for the BI module. |

Schema migrations are handled inline at startup in `app/database.py` (`_run_schema_migrations`). There is no separate migration tool.

---

## API Reference

Interactive API documentation (Swagger UI) is available at `/docs` when the application is running. ReDoc is available at `/redoc`.

Key API groups:

| Prefix | Description |
|---|---|
| `POST /api/login` | Local authentication |
| `GET /api/callback` | OIDC callback |
| `GET /api/me` | Current user profile and allowed tabs |
| `/api/users` | User CRUD and role management |
| `/api/permissions` | Tab permission configuration |
| `/api/admin-groups` | Admin group management |
| `/api/marketplace/*` | Marketplace item lifecycle |
| `/api/research/*` | IDA MCP deployment and management |
| `/api/analytics/*` | System metrics and dashboards |
| `/api/sso/*` | SSO group sync and OIDC config |
| `/api/internal/*` | Internal database table inspection |

---

*The AI portal is an internal platform — contributions and issue reports are handled through the internal Bitbucket and Jira workflow.*
