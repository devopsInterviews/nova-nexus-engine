# Infrastructure API Expectations

This document outlines the endpoints, HTTP methods, and JSON payloads the
**Infrastructure Team** must implement for the Marketplace portal to trigger
automated builds, deployments, and cleanup of AI Agents and MCP Servers.

## Overview

The portal manages the **logical** marketplace representation (database state,
UI, usage metrics) and relies on the Infrastructure API for all **physical**
operations in Kubernetes:

| Step | Portal Action | Infra Responsibility |
|------|--------------|---------------------|
| 1 | User clicks **Build CI/CD** | Scaffold Bitbucket repo + Jenkins Multibranch Pipeline |
| 2 | Developer pushes code | Jenkins builds Docker image + Helm chart → Artifactory |
| 3 | User clicks **Deploy Dev / Release** | Helm deploy to K8s, return `connection_url` |
| 4 | TTL expires (dev only) | Portal calls undeploy; Infra tears down the K8s deployment |
| 5 | User clicks **Delete** | Portal calls undeploy; Infra tears down the K8s deployment |

> **Current status**: All infra calls in the portal backend are **stubbed out**
> (commented `# TODO: uncomment when infra is ready`).  Database state changes
> happen immediately so the UI works end-to-end without the infra layer.

---

## 1. Build Entity

Scaffold a Bitbucket repo and Jenkins Multibranch Pipeline for the entity.

- **Method**: `POST`
- **URL**: `POST /api/infra/build`

### Request Body

```json
{
  "entity_name":      "data-analysis-agent",
  "entity_type":      "agent",
  "description":      "Analyzes datasets and returns natural language summaries.",
  "owner_username":   "jdoe",
  "template_type":    "python_fastapi",
  "bitbucket_project":"AI_AGENTS"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `entity_name` | string | Slug-style name (lowercased, hyphens OK) |
| `entity_type` | `"agent"` \| `"mcp_server"` | |
| `description` | string | Used as repo description |
| `owner_username` | string | Portal username of the creator |
| `template_type` | string | Scaffold template to use (`python_fastapi`, `node_express`, …) |
| `bitbucket_project` | string | Bitbucket project key |

### Expected Response `200 OK`

```json
{
  "status": "success",
  "bitbucket_repo_url": "https://bitbucket.company.com/projects/AI_AGENTS/repos/data-analysis-agent/browse",
  "ci_pipeline_url":    "https://jenkins.company.com/job/AI_AGENTS/job/data-analysis-agent",
  "message":            "Repository created and CI pipeline registered."
}
```

The portal will save `bitbucket_repo_url` to `marketplace_items.bitbucket_repo`.

---

## 2. Deploy Entity

Perform a Helm deployment of a built entity into the Kubernetes cluster.

- **Method**: `POST`
- **URL**: `POST /api/infra/deploy`

### Request Body

```json
{
  "entity_name":       "data-analysis-agent",
  "entity_type":       "agent",
  "chart_name":        "data-analysis-agent-chart",
  "chart_version":     "1.2.0",
  "artifactory_path":  "helm-dev-local/marketplace/data-analysis-agent",
  "owner_username":    "jdoe",
  "groups":            ["data_scientists", "developers"],
  "target_environment":"dev",
  "ttl_days":          10,
  "quota_profile":     "standard",
  "tools_exposed":     ["list_tables", "query_data"]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `chart_version` | string | Version string selected by the user in the Deploy dialog |
| `target_environment` | `"dev"` \| `"release"` | |
| `ttl_days` | integer \| null | `null` for release (persistent); set from `MARKETPLACE_DEV_TTL_DAYS` env for dev |
| `artifactory_path` | string | Full path to the chart in Artifactory |
| `quota_profile` | string | K8s resource quota preset |

### Expected Response `200 OK`

```json
{
  "status":         "success",
  "deployment_id":  "deploy-uuid-1234",
  "namespace":      "agent-jdoe-dev",
  "connection_url": "http://data-analysis-agent.dev.svc.cluster.local",
  "message":        "Deployment triggered successfully."
}
```

The portal will save `connection_url` to `marketplace_items.url_to_connect`.

---

## 3. Undeploy / Delete Entity

Tear down a running Kubernetes deployment.

Called from the portal in two cases:
1. **Manual deletion** — user clicks **Delete**.
2. **TTL expiry** — the portal's daily background task finds a dev deployment
   whose `deployed_at + ttl_days < now` and triggers this endpoint before
   removing the DB record.

- **Method**: `DELETE`
- **URL**: `DELETE /api/infra/deploy/{deployment_id}`

### Request Body

```json
{
  "owner_username": "jdoe",
  "reason":         "ttl_expired"
}
```

Possible `reason` values: `"manual_user_deletion"`, `"ttl_expired"`.

### Expected Response `200 OK`

```json
{
  "status":  "success",
  "message": "Deployment and associated resources cleaned up."
}
```

---

## 4. Chart Version Discovery (Artifactory)

The portal lists available Helm chart versions for the **Deploy** dialog using
the Artifactory File List API.  The infra team must ensure charts are published
to the configured paths:

| Environment | Artifactory Path (default) |
|-------------|---------------------------|
| `dev`       | `helm-dev-local/marketplace/<chart-name>/` |
| `release`   | `helm-release-local/marketplace/<chart-name>/` |

Chart filenames must follow the convention `<chart-name>-<semver>.tgz`
(e.g. `data-analysis-agent-1.2.0.tgz`) so the portal can extract version numbers.

Portal endpoint: `GET /api/marketplace/chart-versions?environment=dev&chart_name=<name>`

---

## 5. Public Ping Endpoint (Portal → Usage Metrics)

Running Agents and MCP Servers can self-report calls to the portal's public
listener so the Marketplace shows accurate usage statistics — **no auth token
required**.

- **Method**: `POST`
- **URL**: `POST /api/marketplace/ping`

### Request Body

```json
{
  "entity_name":      "Jira Integration MCP",
  "entity_type":      "mcp_server",
  "user_identifier":  "jdoe",
  "action":           "call"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `entity_name` | string | ✅ | Must match `marketplace_items.name` exactly |
| `entity_type` | `"agent"` \| `"mcp_server"` | ✅ | |
| `user_identifier` | string | ❌ | Optional caller identifier (username / service account) |
| `action` | string | ❌ | Default `"call"`. Allowed: `"call"`, `"install"` |

### Expected Response `200 OK`

```json
{
  "status":    "ok",
  "item_id":   42,
  "item_name": "Jira Integration MCP"
}
```

---

## Environment Variables Required

| Variable | Example | Purpose |
|----------|---------|---------|
| `INFRA_MARKETPLACE_API_SERVER` | `marketplace-infra-api.company.internal` | Base URL of the infra API |
| `MARKETPLACE_MAX_AGENTS_PER_USER` | `5` | Per-user agent creation limit |
| `MARKETPLACE_MAX_MCP_PER_USER` | `5` | Per-user MCP server creation limit |
| `MARKETPLACE_DEV_TTL_DAYS` | `10` | Dev deployment lifetime in days |
| `ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV` | `helm-dev-local/marketplace` | Artifactory path for dev charts |
| `ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE` | `helm-release-local/marketplace` | Artifactory path for release charts |

---

## Full Flow Diagram

```
User: Create Entity
  → Portal: POST /api/marketplace/items  (DB: CREATED)

User: Build CI/CD
  → Portal: POST /api/marketplace/build  (DB: BUILT)
  → [TODO] Infra: POST /api/infra/build  (scaffold repo + CI)
  → Developer pushes code → Jenkins → Docker image + Helm chart → Artifactory

User: Deploy Dev / Release
  → Portal fetches chart versions:  GET /api/marketplace/chart-versions?environment=dev
  → User selects version, confirms
  → Portal: POST /api/marketplace/deploy  (DB: DEPLOYED, stores chart_version + deployed_at)
  → [TODO] Infra: POST /api/infra/deploy  (K8s Helm deploy, returns connection_url)
  → Portal saves connection_url to DB

Daily background task (portal):
  → Finds dev items where deployed_at + ttl_days < now
  → [TODO] Infra: DELETE /api/infra/deploy/{id}
  → Portal removes item from DB

User: Delete
  → Portal: DELETE /api/marketplace/items/{id}
  → [TODO] Infra: DELETE /api/infra/deploy/{id}
  → Portal removes item from DB

Agent / MCP self-report:
  → POST /api/marketplace/ping  (no auth required)
  → Portal increments usage counters in marketplace_usage table
```
