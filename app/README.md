# Backend Application Documentation

## Overview

The backend is a FastAPI-based application that serves as the main server for the MCP Client. It provides authentication, database management, MCP (Model Context Protocol) integration, analytics, and various API endpoints for the frontend.

## Architecture

### Core Components

1. **FastAPI Application (`client.py`)** - Main application entry point
2. **Database Layer (`database.py`, `models.py`)** - SQLAlchemy-based data persistence
3. **Authentication System (`auth.py`, `routes/auth_routes.py`)** - JWT-based authentication
4. **MCP Integration (`llm_client.py`)** - Model Context Protocol client
5. **Analytics System (`middleware/analytics.py`, `services/analytics_service.py`)** - Request logging and metrics
6. **Route Modules (`routes/`)** - API endpoint definitions

## Key Features

### 1. Authentication & Authorization

**JWT Token-Based Authentication:**
- Located in: `app/auth.py` and `app/routes/auth_routes.py`
- Token expiration: 2 hours (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Password hashing: bcrypt via passlib
- User roles: Admin and regular users

**Authentication Flow:**
1. User sends username/password to `/api/login`
2. Server validates credentials against database
3. JWT token generated with user ID and expiration
4. Token returned to client for subsequent requests
5. Protected endpoints verify JWT via `get_current_user` dependency

**Key Functions:**
- `create_access_token()` - Generates JWT tokens
- `verify_password()` - Validates user passwords
- `get_current_user()` - Extracts user from JWT token
- `User.check_password()` - Model method for password verification

### 2. Database Models & Persistence

**Core Models (in `app/models.py`):**

- **User**: User accounts with authentication and profile data
  - Fields: username, email, hashed_password, is_admin, last_login, preferences
  - Methods: `set_password()`, `check_password()`, `to_dict()`
  
- **DatabaseConnection**: User-specific database connection profiles
  - Fields: host, port, database, username, encrypted_password, database_type
  - Purpose: Store and manage user's database connections
  
- **UserActivity**: Audit trail for user actions
  - Fields: activity_type, action, ip_address, status, timestamp
  - Purpose: Track user behavior for analytics and security
  
- **RequestLog**: HTTP request logging for analytics
  - Fields: method, path, status_code, response_time_ms, user_id
  - Purpose: Performance monitoring and usage analytics
  
- **TestConfiguration**: Saved test configurations
  - Fields: name, test_type, configuration, last_result
  - Purpose: Persist user test setups

### 3. MCP (Model Context Protocol) Integration

**Purpose:** Connects to external MCP servers for AI/ML model interactions

**Key Components:**
- `app/llm_client.py` - LLM client implementation
- MCP session management in `client.py`
- Tool invocation and response handling

**How it works:**
1. Startup establishes MCP session (`startup_event()`)
2. Client can call various MCP tools via `_mcp_session.call_tool()`
3. Supports tools like Jenkins integration, database queries, Confluence updates
4. Session persists across requests for performance

### 4. Analytics & Monitoring

**Analytics Middleware (`app/middleware/analytics.py`):**

**Purpose:** Automatically tracks all HTTP requests for analytics and monitoring

**What it captures:**
- Request method, path, response time
- Client IP, User-Agent, HTTP status codes
- User ID (when authenticated)
- Request/response sizes
- Error messages for failed requests

**How it works:**
1. Middleware wraps every HTTP request
2. Captures request start time
3. Processes request through normal flow
4. Calculates metrics (response time, etc.)
5. Asynchronously logs to database
6. Updates real-time system metrics

**Analytics Service (`app/services/analytics_service.py`):**
- Background monitoring tasks
- Real-time data collection coordination
- Aggregated metrics calculation

### 5. Route Structure

**API Routes (all under `/api` prefix):**

- `/auth/` - Authentication (login, logout, user management)
- `/users/` - User CRUD operations 
- `/db/` - Database connection testing and queries
- `/mcp/` - MCP server interactions and testing
- `/analytics/` - System metrics and analytics data
- `/test/` - Test execution and management
- `/permissions/` - Role-based access control

### 6. Configuration & Environment

**Key Environment Variables:**
- `MCP_SERVER_URL` - URL for MCP server connection
- `JWT_SECRET_KEY` - Secret for JWT token signing
- `DATABASE_URL` - Database connection string
- `LOG_LEVEL` - Logging verbosity
- `ACCESS_TOKEN_EXPIRE_MINUTES` - JWT token lifetime

**Configuration Files:**
- `logging_config.json` - Logging configuration
- `.env` - Environment variables (not in repo)

## Database Schema

### Tables Created

1. **users** - User accounts and authentication
2. **database_connections** - User database connection profiles  
3. **test_configurations** - Saved test setups
4. **user_activities** - User action audit trail
5. **request_logs** - HTTP request analytics
6. **page_views** - Frontend page visit tracking
7. **system_metrics** - Real-time system performance data
8. **mcp_server_status** - MCP server health monitoring

### Relationships

- User → DatabaseConnections (1:many)
- User → TestConfigurations (1:many) 
- User → UserActivities (1:many)
- User → RequestLogs (1:many)

## Startup Process

1. **Environment Loading** - Load .env variables
2. **Logging Setup** - Configure structured logging
3. **FastAPI Initialization** - Create app with middleware
4. **CORS Configuration** - Allow frontend connections
5. **Analytics Middleware** - Add request tracking
6. **Route Registration** - Include all API route modules
7. **MCP Connection** - Establish MCP server session
8. **Database Initialization** - Create tables and initialize analytics
9. **Background Services** - Start analytics monitoring

## Request Flow

### Typical API Request:
1. **Request Arrival** - FastAPI receives HTTP request
2. **Analytics Middleware** - Captures request details and start time
3. **CORS Processing** - Handles cross-origin requests
4. **Route Matching** - FastAPI routes to appropriate handler
5. **Authentication** - JWT verification (if protected endpoint)
6. **Business Logic** - Execute endpoint-specific code
7. **Response Generation** - Create HTTP response
8. **Analytics Completion** - Log metrics and performance data
9. **Response Return** - Send response to client

### Authentication Flow:
1. Client sends credentials to `/api/login`
2. Server validates against database
3. JWT token generated and returned
4. Client stores token (localStorage)
5. Subsequent requests include `Authorization: Bearer <token>`
6. Server validates token on protected endpoints
7. User context available throughout request

## Key Utilities

### Database Utils (`app/database.py`)
- `get_db_session()` - Dependency for database access
- `init_db()` - Create tables and initial setup

### Auth Utils (`app/auth.py`)
- Token generation and verification
- Password hashing utilities
- User session management

### MCP Utils (`app/utils/mcp_utils.py`)
- MCP session status checking
- Tool invocation helpers

## Development Guidelines

### Adding New API Endpoints:
1. Create new route module in `app/routes/`
2. Define pydantic models for request/response
3. Add authentication dependency if needed
4. Include router in `client.py`
5. Add analytics tracking if needed

### Adding New Database Models:
1. Define model class in `app/models.py`
2. Add relationships to existing models
3. Create migration or update `init_db()`
4. Add to_dict() method for API serialization

### Error Handling:
- Use HTTPException for API errors
- Log errors with structured logging
- Return consistent error response format
- Track errors in analytics for monitoring

## Security Considerations

- JWT tokens expire after 2 hours
- Passwords hashed with bcrypt
- SQL injection protection via SQLAlchemy ORM
- CORS configured for specific origins
- Input validation via Pydantic models
- User activity tracking for audit trail

## Performance & Monitoring

- Request timing tracked automatically
- Database queries optimized with indexes
- Background analytics processing
- Connection pooling for database
- Asynchronous request handling where possible
- Real-time system metrics collection
