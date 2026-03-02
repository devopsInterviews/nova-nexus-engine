# Infrastructure API

The Infrastructure API provides endpoints for managing the marketplace, agents, MCP servers, and usage tracking.

## Base URL
`/api/marketplace`

## Endpoints

### 1. Get Agents
- **URL**: `/agents`
- **Method**: `GET`
- **Description**: Returns a list of all available agents in the marketplace.
- **Response**:
  ```json
  [
    {
      "id": 1,
      "name": "Agent Alpha",
      "description": "A powerful agent for data analysis.",
      "version": "1.0.0",
      "author": "Nova Nexus",
      "image_url": "https://example.com/agent-alpha.png",
      "created_at": "2023-10-01T12:00:00Z",
      "updated_at": "2023-10-01T12:00:00Z"
    }
  ]
  ```

### 2. Get MCP Servers
- **URL**: `/mcp-servers`
- **Method**: `GET`
- **Description**: Returns a list of all available MCP servers in the marketplace.
- **Response**:
  ```json
  [
    {
      "id": 1,
      "name": "Data Server",
      "description": "Provides data processing capabilities.",
      "version": "2.1.0",
      "author": "Nova Nexus",
      "image_url": "https://example.com/data-server.png",
      "created_at": "2023-10-01T12:00:00Z",
      "updated_at": "2023-10-01T12:00:00Z"
    }
  ]
  ```

### 3. Log Usage
- **URL**: `/usage`
- **Method**: `POST`
- **Description**: Logs the usage (e.g., install, run) of a marketplace item.
- **Request Body**:
  ```json
  {
    "item_type": "agent",
    "item_id": 1,
    "action": "install"
  }
  ```
- **Response**:
  ```json
  {
    "id": 1,
    "user_id": 42,
    "item_type": "agent",
    "item_id": 1,
    "action": "install",
    "timestamp": "2023-10-01T12:05:00Z"
  }
  ```

## Authentication
All endpoints require a valid JWT token passed in the `Authorization` header as a Bearer token.
