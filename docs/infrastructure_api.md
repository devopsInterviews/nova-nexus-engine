# Infrastructure API Expectations

This document outlines the required endpoints and data structures the Infrastructure API must expose for the portal to integrate and trigger automated builds and deployments for Agents and MCP Servers.

## Abstract
The Portal is responsible for managing the logical marketplace representation and user context. It relies on the Infrastructure API to:
1. **Build Entities**: Provision templates, setup CI/CD multibranch pipelines, and store images in Artifactory.
2. **Deploy Entities**: Trigger actual deployment to Kubernetes, assign TTL (time-to-live), quotas, and bind to correct namespaces based on user context.
3. **Delete Entities**: Tear down deployments when users manually trigger deletion or TTL expires.

---

## 1. Build Entity Endpoint

When a user creates a new Agent or MCP Server, the portal will tell Infra to scaffold the Bitbucket repo and setup CI.

- **URL**: `POST /api/infra/build`
- **Method**: `POST`
- **Purpose**: Creates the repo, sets up standard structure, and provisions a Jenkins Multibranch Pipeline.
- **Request Body**:
  ```json
  {
    "entity_name": "data-analysis-agent",
    "entity_type": "agent",           // or "mcp_server"
    "description": "Agent for querying data",
    "owner_username": "jdoe",         // From identity context
    "template_type": "python_fastapi",// e.g., standard template used
    "bitbucket_project": "AI_AGENTS"
  }
  ```
- **Expected Response**:
  ```json
  {
    "status": "success",
    "bitbucket_repo_url": "https://bitbucket.example.com/projects/AI_AGENTS/repos/data-analysis-agent/browse",
    "ci_pipeline_url": "https://jenkins.example.com/job/AI_AGENTS/job/data-analysis-agent",
    "message": "Repository created and CI pipeline registered."
  }
  ```

---

## 2. Deploy Entity Endpoint

When a user requests to deploy/run an Agent or MCP Server to the cluster.

- **URL**: `POST /api/infra/deploy`
- **Method**: `POST`
- **Purpose**: Triggers a Helm deployment into the correct user namespace or project, injecting secrets and applying resource quotas.
- **Request Body**:
  ```json
  {
    "entity_name": "data-analysis-agent",
    "entity_type": "agent",
    "chart_name": "ai-agent-chart",
    "chart_version": "1.0.0",
    "artifactory_path": "docker-local/data-analysis-agent",
    "owner_username": "jdoe",
    "groups": ["data_scientists", "developers"],
    "target_environment": "dev",      // dev / staging / prod
    "ttl_days": 10,                   // Deployment will auto-cleanup in 10 days
    "quota_profile": "standard",      // e.g. cpu/mem constraints
    "tools_exposed": ["list_tables", "query_data"]
  }
  ```
- **Expected Response**:
  ```json
  {
    "status": "success",
    "deployment_id": "deploy-uuid-1234",
    "namespace": "agent-jdoe-dev",
    "connection_url": "http://data-analysis-agent.dev.svc.cluster.local",
    "message": "Deployment triggered successfully"
  }
  ```

---

## 3. Delete / Undeploy Entity Endpoint

When a user deletes a deployed agent, or when the admin clears the cluster.

- **URL**: `DELETE /api/infra/deploy/{deployment_id}`
- **Method**: `DELETE`
- **Purpose**: Destroys the pod/deployment in the cluster.
- **Request Body**:
  ```json
  {
    "owner_username": "jdoe",
    "reason": "manual_user_deletion"
  }
  ```
- **Expected Response**:
  ```json
  {
    "status": "success",
    "message": "Deployment and associated resources cleaned up."
  }
  ```

## Flow of Operations:
1. User clicks "Create New". Portal calls `/api/infra/build`.
2. Infra sets up Bitbucket repo & Jenkins.
3. User develops code, pushes to main branch -> Jenkins builds Docker image and Helm Chart -> pushes to Artifactory.
4. User clicks "Install" or "Deploy". Portal calls `/api/infra/deploy`.
5. Infra fetches the chart, deploys to Kubernetes, and returns the runtime URL.
6. The portal saves this URL to `marketplace_items.url_to_connect` in the DB.

