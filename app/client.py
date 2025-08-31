"""
Main FastAPI application server.
This is the central application file that:
1. Initializes the FastAPI server with middleware and routes
2. Establishes MCP (Model Context Protocol) server connections
3. Sets up authentication, analytics, and database systems
4. Provides webhook endpoints for external system integrations
5. Serves the frontend SPA and handles API routing

Key integrations:
- MCP Server: For AI/ML model interactions
- Database: PostgreSQL with SQLAlchemy ORM
- Analytics: Request logging and performance monitoring
- Authentication: JWT-based user authentication
- Frontend: Serves React SPA and API endpoints

Environment Variables:
- MCP_SERVER_URL: URL for MCP server connection
- LOG_LEVEL: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- JWT_SECRET_KEY: Secret key for JWT token signing
"""

import os
import json
import logging
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from contextlib import AsyncExitStack
from datetime import timedelta
from app.llm_client import LLMClient
from app.prompts import *
from app.database import init_db
from app.middleware.analytics import setup_analytics_middleware
from app.services.analytics_service import analytics_service


# Load environment variables from .env file in parent directory
# This loads configuration like database URLs, API keys, and feature flags
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configuration variables with sensible defaults
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8050/mcp/")  # MCP server endpoint for AI model interactions
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()  # Logging verbosity: DEBUG, INFO, WARNING, ERROR

# Directory paths for serving static files and templates
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Project root directory
STATIC_DIR = os.path.join(BASE_DIR, "static")  # Static assets (CSS, JS, images)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")  # Jinja2 HTML templates

# Configure structured logging for the entire application
# This creates a consistent logging format across all components
logging_config = {
    "version": 1,  # Required field for dictConfig
    "disable_existing_loggers": False,  # Keep existing loggers intact
    "formatters": {
        "default": {
            # Standard format: timestamp - level - message (e.g., "2025-08-31 10:15:30 - INFO - User logged in")
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"  # ISO date format for consistency
        }
    },
    "handlers": {
        "default": {
            "formatter": "default",  # Use the formatter defined above
            "class": "logging.StreamHandler",  # Log to stdout/stderr
            "stream": "ext://sys.stdout"  # Explicit stdout for container compatibility
        }
    },
    "loggers": {
        # Configure specific loggers for different components
        "uvicorn": {  # Web server logs (startup, shutdown, etc.)
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False  # Don't pass to parent loggers
        },
        "uvicorn.error": {  # Error-specific uvicorn logs
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "uvicorn.access": {  # HTTP access logs (requests, responses)
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "app.middleware.analytics": {  # Analytics middleware logs
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "fastapi": {  # FastAPI framework logs
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        }
    },
    "root": {  # Root logger catches all unspecified loggers
        "level": LOG_LEVEL,
        "handlers": ["default"]
    }
}

# Apply the logging configuration to the Python logging system
logging.config.dictConfig(logging_config)

# Initialize the FastAPI application instance
app = FastAPI(title="MCP Client")  # Creates the main web application

# Mount static file serving for CSS, JS, images, etc.
# This serves files from /static directory at /static URL path
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize Jinja2 template engine for serving HTML templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Add CORS (Cross-Origin Resource Sharing) middleware
# This allows the React frontend to make API calls to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # WARNING: In production, specify exact frontend URL instead of wildcard
    allow_credentials=True,  # Allow cookies and authorization headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all request headers
)

# Setup analytics middleware that logs every HTTP request
# This must be added after CORS but before route handlers
setup_analytics_middleware(app)

# Get a logger instance for this module using the configured logging
logger = logging.getLogger("uvicorn.error")

# Import all route modules that define API endpoints
# These imports must be after app creation to avoid circular dependencies
from app.routes.db_routes import router as db_router  # Database operations
from app.routes.mcp_routes import router as mcp_router  # MCP server interactions
from app.routes.auth_routes import router as auth_router  # Authentication endpoints
from app.routes.users_routes import router as users_router  # User management
from app.routes.test_routes import router as test_router  # Test execution
from app.routes.internal_data_routes import router as internal_data_router  # Internal data APIs
from app.routes.permissions_routes import router as permissions_router  # Role-based permissions
from app.routes.analytics_routes import router as analytics_router  # System metrics

# Register all route modules with the FastAPI app under /api prefix
# This makes all endpoints accessible at /api/... URLs
app.include_router(db_router, prefix="/api")  # Database routes: /api/database/*
app.include_router(mcp_router, prefix="/api")  # MCP routes: /api/mcp/*
# Expose auth routes under /api
app.include_router(auth_router, prefix="/api")
# Expose user routes under /api
app.include_router(users_router, prefix="/api")
# Expose test routes under /api
app.include_router(test_router, prefix="/api")
app.include_router(internal_data_router, prefix="/api")
# Expose permissions routes under /api
app.include_router(permissions_router, prefix="/api")
# Expose analytics routes under /api
app.include_router(analytics_router, prefix="/api")

# Lightweight request logging middleware (doesn't consume body)
@app.middleware("http")  # Decorator registers this function as HTTP middleware that runs on every request
async def log_requests(request: Request, call_next):
    try:
        # Log the incoming request method and path (e.g., "GET /api/users")
        logger.info("%s %s", request.method, request.url.path)
        # Call the next middleware or route handler and get the response
        response = await call_next(request)
        # Log the completed request with status code (e.g., "GET /api/users -> 200")
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        # Return the response to continue the chain
        return response
    except Exception:
        # If any error occurs during request processing, log it with full stack trace
        logger.error("Unhandled error for %s %s", request.method, request.url.path, exc_info=True)
        # Re-raise the exception so FastAPI can handle it properly
        raise

# Global variables to manage MCP (Model Context Protocol) connection lifecycle
# AsyncExitStack manages async context managers (like connections) in the same task
_exit_stack: AsyncExitStack
# ClientSession holds the actual MCP connection to the AI model
_mcp_session: ClientSession


# Global LLM client instance
llm_client: LLMClient

# Schemas
class QueryRequest(BaseModel):
    query: str = Field(..., description="The user’s natural-language query")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The LLM’s final answer")


@app.on_event("startup")
async def startup_event():
    """
    Application startup initialization.
    
    This function runs when the FastAPI server starts and performs critical setup:
    
    1. **MCP Connection Setup**: Establishes connection to MCP server for AI model interactions
       - Creates HTTP transport with timeout configuration
       - Initializes MCP session for tool calling
       - Logs connection status for monitoring
    
    2. **Database Initialization**: 
       - Creates all database tables if they don't exist
       - Sets up SQLAlchemy engine and session factory
       - Ensures database schema is current
    
    3. **Analytics Service**: 
       - Starts background monitoring tasks
       - Initializes real-time metrics collection
       - Sets up performance tracking for actual usage data
    
    4. **LLM Client Setup**: 
       - Initializes the Language Model client for MCP interactions
       - Makes it globally available for request handlers
       - Configures timeout and retry settings
    
    Error Handling:
    - MCP connection failures are logged but don't stop startup
    - Database errors are logged with details
    - Individual component failures are isolated
    
    Environment Dependencies:
    - MCP_SERVER_URL: Must be accessible for MCP functionality
    - Database connection: Required for data persistence
    """
    global _exit_stack, _mcp_session  # Access global variables for MCP connection management
    _exit_stack = AsyncExitStack()  # Create stack to manage multiple async context managers

    # Establish HTTP transport connection to MCP server
    # streamablehttp_client creates bidirectional streaming connection for real-time communication
    _http_transport = await _exit_stack.enter_async_context(
        streamablehttp_client(
            MCP_SERVER_URL,  # Server URL from environment variable
            timeout = timedelta(seconds=600),  # 10 minute timeout for long operations
            sse_read_timeout = timedelta(seconds=600)  # Server-sent events read timeout
        )
    )
    # Extract the read and write streams from the transport tuple
    read_stream, write_stream, _ = _http_transport

    # Create MCP client session using the established streams
    # ClientSession handles the MCP protocol communication
    _mcp_session = await _exit_stack.enter_async_context(
        ClientSession(read_stream, write_stream)  # Pass streams for bidirectional communication
    )
    # Initialize the session to complete the MCP handshake
    await _mcp_session.initialize()
    logger.info(f"MCP session initialized and connected to {MCP_SERVER_URL}")

    # Initialize the database by creating all tables defined in models.py
    init_db()

    # Initialize analytics system for real-time data collection
    from app.database import SessionLocal  # Import database session factory
    db = SessionLocal()  # Create a new database session
    try:
        # Initialize analytics system for real data collection
        logger.info("Initializing analytics system...")
        analytics_service.initialize_analytics(db)  # Initialize analytics for real data collection
    except Exception as e:
        # Log warning if initialization fails but don't crash the application
        logger.warning(f"Could not initialize analytics: {e}")
    finally:
        db.close()  # Always close the database session to prevent connection leaks

    # Start analytics monitoring background tasks for real-time metrics collection
    await analytics_service.start_monitoring()

    # Initialize the LLM client for AI model interactions
    llm_client = LLMClient()  # Create instance of language model client
    globals()["llm_client"] = llm_client  # Make it globally accessible to all route handlers
    logger.info("LLMClient initialized and ready.")


@app.on_event("shutdown")  # Decorator registers this function to run when FastAPI shuts down
async def shutdown_event():
    """
    Application shutdown cleanup.
    
    This function runs when the FastAPI server is shutting down and performs:
    1. Stops analytics monitoring background tasks
    2. Closes all MCP connections and async context managers
    3. Cleans up resources to prevent memory leaks
    """
    logger.info("shutdown_event: enter")
    try:
        # Stop analytics monitoring background tasks gracefully
        await analytics_service.stop_monitoring()
        
        # Close all async context managers managed by the exit stack
        # This includes MCP session and HTTP transport connections
        await _exit_stack.aclose()
    except Exception as e:
        # Log any errors during shutdown but don't crash
        logger.error("shutdown_event: error during aclose(): %s", e, exc_info=True)
    else:
        logger.info("shutdown_event: exit cleanly")


@app.exception_handler(Exception)  # Global exception handler for any unhandled exceptions
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that catches any unhandled errors in the application.
    
    This provides a safety net for unexpected errors and ensures:
    1. All errors are logged with full context
    2. Clients receive a standardized error response
    3. Server doesn't crash on unexpected exceptions
    """
    # Log the full error with request context and stack trace
    logger.error("Unhandled exception during request %s %s: %s", request.method, request.url, exc, exc_info=True)
    # Return standardized JSON error response to client
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

@app.get("/", response_class=HTMLResponse)  # Root route serves the React SPA
async def spa_root(request: Request):
    """
    Serves the React single-page application at the root URL.
    
    This endpoint returns the main HTML template that loads the React app.
    The template includes all necessary CSS and JS bundles.
    """
    # Use Jinja2 template engine to render the main UI template
    # templates points to your templates directory containing ui.html
    return templates.TemplateResponse("ui.html", {"request": request})


@app.post("/events/code-analysis", status_code=202)
async def code_analysis_endpoint(request: Request) -> QueryResponse:
    """
    Webhook endpoint for automated code analysis.
    
    This endpoint receives code analysis reports (typically from CI/CD pipelines) 
    and processes them through the LLM for intelligent insights and recommendations.
    
    **Use Case**: 
    - Triggered by CI/CD systems after code scans
    - Processes static analysis results, security scans, or quality reports
    - Returns AI-generated insights and recommendations
    
    **Request Flow**:
    1. Receives JSON payload containing analysis reports
    2. Logs full payload for audit and debugging
    3. Formats data using CODE_ANALYSIS_PROMPT template
    4. Sends to LLM via MCP session for analysis
    5. Returns AI-generated insights and recommendations
    
    **Expected JSON Structure**:
    ```json
    {
        "scan_results": {...},
        "vulnerabilities": [...],
        "code_quality": {...},
        "metadata": {...}
    }
    ```
    
    **Response**: AI analysis with recommendations for code improvement
    
    **Integration Points**:
    - CI/CD pipelines (Jenkins, GitHub Actions, etc.)
    - Security scanning tools (SonarQube, Snyk, etc.)
    - Code quality tools (ESLint, Pylint, etc.)
    """
    # 1️⃣  Parse the raw JSON body from the incoming HTTP request
    try:
        payload = await request.json()  # Extract JSON payload from request body
    except json.JSONDecodeError as err:
        # If JSON is malformed, log error and return 400 Bad Request
        logger.error("Invalid JSON body: %s", err, exc_info=True)
        raise HTTPException(status_code=400, detail="Body must be valid JSON")

    # 2️⃣  Log the entire payload for debugging and audit trail
    # This helps track what data was received for troubleshooting
    logger.info("Received code-analysis payload:\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False))

    # 3️⃣  Build the LLM prompt using the predefined template
    # CODE_ANALYSIS_PROMPT contains instructions for how to analyze the code reports
    prompt_text = CODE_ANALYSIS_PROMPT.format(
        reports_json=json.dumps(payload, indent=2, ensure_ascii=False)  # Insert JSON into template
    )

    # 4️⃣  Send the formatted prompt to the LLM via MCP session and return response
    try:
        # Process the query through the LLM client using the established MCP session
        answer = await llm_client.process_query(
            user_query=prompt_text,  # The formatted prompt with code analysis data
            session=_mcp_session     # Global MCP session for AI communication
        )
        # Log the LLM's response for debugging and monitoring
        logger.info("LLM Final Answer:\n%s", answer)
        # Return the AI analysis wrapped in the response model
        return QueryResponse(answer=answer)
    except Exception as err:
        # If LLM processing fails, log error and return 500 Internal Server Error
        logger.error("❌  LLM processing failed: %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail=str(err))


@app.post("/events/jira", status_code=202)
async def jira_endpoint(request: Request):
    """
    Webhook endpoint for JIRA ticket analysis and investigation.
    
    This endpoint processes JIRA webhook events to automatically investigate
    and analyze tickets using AI-powered insights.
    
    **Use Case**:
    - Triggered when JIRA tickets are created or updated
    - Automatically analyzes ticket content for context and severity
    - Provides AI-driven investigation recommendations
    - Links related incidents and knowledge base articles
    
    **Request Flow**:
    1. Receives JIRA webhook with ticket information
    2. Extracts ticket ID from the message field
    3. Uses JIRA_INVESTIGATION_USER_PROMPT to analyze ticket
    4. Queries LLM for investigation insights and recommendations
    5. Returns structured analysis for ticket context
    
    **Expected Message Format**:
    ```json
    {
        "message": "{\"field\": \"ticket_id\", \"value\": \"PROJ-123\"}"
    }
    ```
    
    **AI Analysis Includes**:
    - Ticket severity assessment
    - Related incident correlation
    - Investigation steps recommendations
    - Resource and documentation links
    
    **Integration Points**:
    - JIRA webhooks for ticket events
    - ServiceNow for incident management
    - Knowledge base systems
    - Monitoring and alerting platforms
    """

    evt = await request.json()
    raw_msg = evt.get("message")

    if raw_msg is None:
        logger.error("Jira ticket missing 'message' field. What we got: %s", evt)
        raise HTTPException(status_code=400, detail="Missing message field")
    
    try:
        parsed = json.loads(raw_msg)
    except json.JSONDecodeError as e:
        logger.exception("Failed to parse jira message JSON: %s", raw_msg)
        raise HTTPException(status_code=400, detail="Invalid JSON in message")

    value = parsed.get("value")
    field = parsed.get("field")
    logger.info("Parsed anomaly with field = %s value = %s", field, value)
    user_query = JIRA_INVESTIGATION_USER_PROMPT.format(ticket_id=value)

    try:
        answer = await llm_client.process_query(user_query=user_query, session=_mcp_session)
        logger.info(f"LLM Final Answer: {answer}")
        return QueryResponse(answer=answer)
    except Exception as e:
        logger.error("❌  run_query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/events/jenkins", status_code=202)
async def jenkins_anomaly_endpoint(request: Request):
    evt = await request.json()
    raw_msg = evt.get("message")

    if raw_msg is None:
        logger.error("Anomaly webhook missing 'message' field. What we got: %s", evt)
        raise HTTPException(status_code=400, detail="Missing message field")
    
    try:
        parsed = json.loads(raw_msg)
    except json.JSONDecodeError as e:
        logger.exception("Failed to parse anomaly message JSON: %s", raw_msg)
        raise HTTPException(status_code=400, detail="Invalid JSON in message")

    value = parsed.get("value")
    field = parsed.get("field")
    logger.info("Parsed anomaly with field = %s value = %s", field, value)
    user_query = JENKINS_INVESTIGATION_USER_PROMPT.format(trace_id=value)

    try:
        answer = await llm_client.process_query(user_query=user_query, session=_mcp_session)
        logger.info(f"LLM Final Answer: {answer}")
        return QueryResponse(answer=answer)
    except Exception as e:
        logger.error("❌  run_query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """
    General API health check endpoint
    """
    logger.info("Health check called")
    return {"status": "ok", "service": "mcp-client"}


@app.get("/tools", summary="List MCP server tools")
async def list_tools() -> Dict[str, Any]:
    """
    Retrieve and return the list of all available MCP tools from the server.

    Returns:
        JSON containing tool names and descriptions.
    """
    try:
        tools_result = await _mcp_session.list_tools()
    except Exception as e:
        logger.error("Failed to list tools: %s", e)
        raise HTTPException(status_code=500, detail="Could not retrieve tools list")

    tools_info = [
        {"name": tool.name, "description": tool.description}
        for tool in tools_result.tools
    ]
    return {"tools": tools_info}


async def run_query(user_query: str):
    """
    Accepts a user query, runs the MCP→LLM function-calling loop,
    and returns the final answer.
    """
    try:
        answer = await llm_client.process_query(user_query, _mcp_session)
        return QueryResponse(answer=answer)
    
    except Exception as e:
        logger.error("Error in process_query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/prompt-test")
async def enhance_query():
    """
    Endpoint to send a user query (and optional system prompt) to the LLM
    and return the enhanced version.
    """
    try:
        response = await llm_client.query_llm(
            usr_prompt="What is the best song in the history of music if you need to mention one",
            sys_prompt=None)

        return response
    
    except Exception as e:
        logger.error("Error enhancing query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/console-test")
async def get_console(job_name: str, build_number: str):
    """
    Fetch the full Jenkins console output for the given job and build.
    You can hit this via your browser:
      http://localhost:8000/console-test?job_name=my-job&build_number=42
    """
    try:
        result = await _mcp_session.call_tool(
            "fetch_job_console_output",
            arguments={"job_name": job_name, "build_number": build_number}
        )
        console_text = result.content[0].text
        return console_text
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/window-test")
async def window_test(job_name: str, build_number: str):
    """
      http://localhost:8000/window-test?job_name=my-job&build_number=42
    """
    try:
        result = await _mcp_session.call_tool(
            "retrieve_job_logs_window_time",
            arguments={"root_job": job_name, "root_build": build_number}
        )
        console_text = result.content[0].text
        return console_text
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/log-paths-test")
async def log_paths_test(
    environment: str,
    vm_name: str,
    start_time: str,
    end_time: str
):
    """
    Test the fetch_log_file_paths MCP tool via browser:
      http://localhost:8000/log-paths-test?
        environment=production&
        vm_name=web-server-01&
        start_time=2025-06-08T12:00:00Z&
        end_time=2025-06-08T12:30:00Z
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_server_log_file_paths",
            arguments={
                "environment": environment,
                "vm_name":     vm_name,
                "start_time":  start_time,
                "end_time":    end_time
            }
        )
        # return the parsed JSON body of the tool response
        return res.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/app-logs-for-paths-test")
async def app_logs_for_paths_test(
    environment: str,
    vm_name: str,
    start_time: str,
    end_time: str,
    paths: str  # comma-separated list of file paths
):
    """
    Test the fetch_application_logs_for_paths MCP tool via browser:
      http://localhost:8000/app-logs-for-paths-test?
        environment=prod&
        vm_name=web-01&
        start_time=2025-06-08T12:00:00Z&
        end_time=2025-06-08T12:30:00Z&
        paths=C:\\APP\\Logs\\file1.log,C:\\APP\\Logs\\file2.log
    """
    try:
        log_list = paths.split(",")
        result = await _mcp_session.call_tool(
            "fetch_application_server_logs_by_path",
            arguments={
                "environment":    environment,
                "vm_name":        vm_name,
                "log_file_paths": log_list,
                "start_time":     start_time,
                "end_time":       end_time
            }
        )
        print(result.content[0].text)
        return result.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/containers-test")
async def containers_test(
    environment: str,
    vm_name: str,
    start_time: str,
    end_time: str
):
    """
    Test fetch_containers_for_server via browser:
      http://localhost:8000/containers-test?
        environment=production&
        vm_name=web-server-01&
        start_time=2025-06-08T00:00:00Z&
        end_time=2025-06-08T23:59:59Z
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_containers_for_server",
            arguments={
                "environment": environment,
                "vm_name":     vm_name,
                "start_time":  start_time,
                "end_time":    end_time
            }
        )
        # returns a JSON map of app → [container_ids]
        return res.content[0].json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs-for-container-test")
async def logs_for_container_test(
    environment: str,
    vm_name: str,
    container_id: str,
    start_time: str,
    end_time: str
):
    """
    Test fetch_logs_for_container via browser:
      http://localhost:8000/logs-for-container-test?
        environment=production&
        vm_name=web-server-01&
        container_id=cid-1234&
        start_time=2025-06-08T00:00:00Z&
        end_time=2025-06-08T23:59:59Z
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_logs_for_container",
            arguments={
                "environment":  environment,
                "vm_name":      vm_name,
                "container_id": container_id,
                "start_time":   start_time,
                "end_time":     end_time
            }
        )
        # returns newline-delimited log messages as plain text
        return res.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/build-parameters-test")
async def build_parameters_test(
    job_name: str,
    build_number: int
):
    """
    Test the fetch_jenkins_build_parameters MCP tool via browser:
      http://localhost:8000/build-parameters-test?job_name=my-job&build_number=42
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_jenkins_build_parameters",
            arguments={
                "job_name": job_name,
                "build_number": build_number
            }
        )
        # returns a JSON dict of parameter names to values
        return res.content[0].json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/build-time-window-test")
async def build_time_window_test(
    job_name: str,
    build_number: int
):
    """
    Test the fetch_build_time_window MCP tool via browser:
      http://localhost:8000/build-time-window-test?job_name=my-job&build_number=42
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_build_time_window",
            arguments={
                "job_name":     job_name,
                "build_number": build_number
            }
        )
        # returns a JSON dict with start_time and end_time
        return res.content[0].json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job-console-test")
async def job_console_test(
    job_name: str,
    build_number: int
):
    """
    Test the fetch_job_console_output MCP tool via browser:
      http://localhost:8000/job-console-test?job_name=my-job&build_number=42
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_job_console_output",
            arguments={"job_name": job_name, "build_number": build_number}
        )
        # return the raw console text
        return res.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/downstream-test")
async def job_console_test(
    job_name: str,
    build_number: int
):
    """
    Test the fetch_job_console_output MCP tool via browser:
      http://localhost:8000/downstream-test?job_name=my-job&build_number=42
    """
    try:
        res = await _mcp_session.call_tool(
            "fetch_root_and_all_downstream_jobs_outputs",
            arguments={"root_job": job_name, "root_build": build_number}
        )
        # return the raw console text
        return res.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/get-confluence-page-test")
async def get_confluence_page_test(
    space: str,
    title: str
):
    """
    Test the fetch_job_console_output MCP tool via browser:
      http://localhost:8000/get-confluence-page-test?space=AAA&title=Demo%20-%20database%20keys%20description
    """
    try:
        res = await _mcp_session.call_tool(
            "get_confluence_page_content",
            arguments={"space": space, "title": title}
        )
        # return the raw console text
        return res.content[0].text
    except Exception as e:
        logger.error("Error in get_confluence_page_content:", exc_info=True)
        # include repr(e) so even empty messages show their type
        raise HTTPException(status_code=500, detail=repr(e))

@app.get("/list-databases-test")
async def list_database_test(
        host: str,
        port: int,
        user: str,
        password: str,
):
    """
    Test the fetch_job_console_output MCP tool via browser:
      http://localhost:8000/list-databases-test?host=<ip>&port=5432&user=malluser&password=mall
    """
    try:
        res = await _mcp_session.call_tool(
            "list_databases",
            arguments={"host": host, "port": port, "user": user, "password": password}
        )
        # return the raw console text
        return res.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bitbucket-comment-test")
async def bitbucket_comment_test(
    pr_id: int,
    comment: str,
    project: str = None,
    repo: str = None,
):
    """
    Test the post_bitbucket_comment MCP tool via browser:
      http://localhost:8000/bitbucket-comment-test?
        pr_id=42&
        comment=Scan%20completed%20successfully!&
        project=MYPROJ&
        repo=my-repo
    """
    try:
        arguments = {
            "pr_id": pr_id,
            "comment": comment,
        }

        if project:
            arguments["project"] = project
        if repo:
            arguments["repo"] = repo

        result = await _mcp_session.call_tool("post_bitbucket_comment", arguments=arguments)

        return result.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/list-bitbucket-files-test")
async def list_bitbucket_files_test(
    project: str,
    repo:    str,
    path:    str = "",
    at_ref:  str = "refs/heads/master"
):
    """
    Browser-testable endpoint:
      http://localhost:8000/list-bitbucket-files-test?
        project=<PROJ>&repo=<repo>&path=<optional>&at_ref=<branch>
    """
    try:
        res = await _mcp_session.call_tool(
            "list_bitbucket_files",
            arguments={
                "project": project,
                "repo":    repo,
                "path":    path,
                "at_ref":  at_ref
            }
        )
        chunks = [msg.text for msg in res.content]
        return "\n".join(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list-tables-test")
async def list_tables_test(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = "postgres",
    database_type: str = "postgres"
):
    """
    Test the list_database_tables MCP tool via browser:
      http://localhost:8000/list-tables-test?
        host=<ip>&port=5432&user=malluser&
        password=mallpass&database=malldb&
        database_type=postgres

    Supports both Postgres and MSSQL by passing `database_type`.
    """
    try:
        res = await _mcp_session.call_tool(
            "list_database_tables",
            arguments={
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database,
                "database_type": database_type
            }
        )
        chunks = [msg.text for msg in res.content]
        return "\n".join(chunks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list-all-keys-test")
async def list_keys_test(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = "postgres",
    database_type: str = "postgres"
):
    """
    Test the list_database_keys MCP tool via browser:
      http://localhost:8000/list-all-keys-test?
        host=<ip>&port=5432&user=malluser&
        password=mallpass&database=malldb&
        database_type=mssql

    Supports both Postgres and MSSQL by passing `database_type`.
    """
    try:
        res = await _mcp_session.call_tool(
            "list_database_keys",
            arguments={
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database,
                "database_type": database_type
            }
        )
        chunks = [msg.text for msg in res.content]
        return "\n".join(chunks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/describe-all-columns")
async def describe_api(request: Request):
    data = await request.json()
    # now require space/title too
    required = ["host","port","user","password","database","table","limit","space","title"]
    for f in required:
        if f not in data:
            raise HTTPException(400, f"Missing {f}")

    # 1️⃣ call describe_table_columns
    res = await _mcp_session.call_tool(
        "describe_table_columns",
        arguments={
            "host":     data["host"],
            "port":     data["port"],
            "user":     data["user"],
            "password": data["password"],
            "database": data["database"],
            "table":    data["table"],
            "limit":    data["limit"],
        },
        read_timeout_seconds=timedelta(seconds=600)
    )
    raw = res.content[0].text

    # 2️⃣ parse into Python list
    try:
        rows = json.loads(raw)
    except ValueError:
        return JSONResponse(
            status_code=500,
            content={"error": "Invalid JSON from tool", "raw": raw}
        )

    # 3️⃣ now call your new Confluence‐updater tool
    update_res = await _mcp_session.call_tool(
        "sync_confluence_table_delta",
        arguments={
            "space": data["space"],
            "title": data["title"],
            "data":  rows
        },
        # give Confluence plenty of time to accept & version-bump
        read_timeout_seconds=timedelta(seconds=300)
    )
    # unwrap its JSON, which is the Confluence response
    updated_page = update_res.content[0].json()

    # 4️⃣ return both the describe rows and the Confluence update
    return JSONResponse({
        "descriptions": rows,
        "confluence_update": updated_page
    })

@app.get("/describe-all-columns", response_class=HTMLResponse)
async def describe_all_ui(request: Request):
    return templates.TemplateResponse("describe_table_columns.html", {"request": request})


@app.get("/test-update-confluence")
async def test_update_confluence():
    """
    Trigger the update_confluence_table MCP tool with a simple payload:
      - space: "TEST"
      - title: "Test Page"
      - data: one dummy row
    Returns the raw Confluence API response so you can see if it succeeded.
    """
    # 1) Build a minimal test payload
    test_args = {
        "space": "AAA",
        "title": "Demo - database keys description",
        "data": [
            {
                "column": "foo.bar",
                "description": "This is a test description"
            }
        ]
    }

    try:
        # 2) Invoke the MCP tool (allow a bit of time for Confluence)
        res = await _mcp_session.call_tool(
            "update_confluence_table",
            arguments=test_args,
            read_timeout_seconds=timedelta(seconds=120)
        )
        # 3) Unwrap the JSON response from the tool
        updated = res.content[0].json()

        # 4) Return it directly so you can inspect version bump, etc.
        return JSONResponse(status_code=200, content=updated)

    except Exception as e:
        # If anything goes wrong, return the error details
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sync-all-tables", response_class=HTMLResponse)
async def sync_ui(request: Request):
    """
    Renders the modern Tailwind-based UI for triggering and monitoring sync.
    """
    return templates.TemplateResponse("sync_tables.html", {"request": request})


def parse_sql_keys(sql_text: str, only_new: bool = False) -> List[str]:
    """
    Extract column names from a CREATE TABLE (…) block and
    return them as 'TableName.ColumnName', inferring TableName
    from the CREATE TABLE header in the SQL.
    """
    # 1) Find the table name
    table_match = re.search(
        r'CREATE\s+TABLE\s+\[?[A-Za-z0-9_]+\]?\.\[?([A-Za-z0-9_]+)\]?', 
        sql_text, 
        re.IGNORECASE
    )
    if not table_match:
        raise ValueError("Could not find CREATE TABLE statement with a table name")
    table_name = table_match.group(1)
    
    # 2) Now extract columns
    keys: List[str] = []
    in_columns = False

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        
        # Detect start of the column definitions
        if line.upper().startswith("CREATE TABLE"):
            in_columns = True
            continue
        if not in_columns:
            continue
        
        # Stop at the closing parenthesis
        if line.startswith(")"):
            break
        
        # Match "[ColumnName] ..." lines
        col_match = re.match(r'^\[([^\]]+)\]\s', line)
        if col_match:
            col = col_match.group(1)
            keys.append(f"{table_name}.{col}")

    return keys

@app.post("/pr-sync")
async def on_pr_event(request: Request):
    logger.debug("[on_pr_event] endpoint called")
    body = await request.json()
    logger.debug("[on_pr_event] payload: %s", body)
    required = ["project","repo","pr_id","branch","author","path_prefix","space","title"]
    for field in required:
        if field not in body:
            logger.error("[on_pr_event] Missing field: %s", field)
            raise HTTPException(400, f"Missing '{field}' in payload")
    project     = body["project"]
    repo = body["repo"]
    if repo.endswith(".git"):
        repo = repo[:-4]
    pr_id       = body["pr_id"]
    branch      = body["branch"]
    author      = body["author"]
    path_prefix = body["path_prefix"]
    space       = body["space"]
    title       = body["title"]


    logger.debug("[on_pr_event] values - project:%s repo:%s pr_id:%s branch:%s author:%s path_prefix:%s", 
                 project, repo, pr_id, branch, author, path_prefix)

    # Step 1: Get changed SQL files
    logger.debug("[on_pr_event] calling list_pr_changed_files tool")
    res = await _mcp_session.call_tool(
        "list_pr_changed_files",
        arguments={"project": project, "repo": repo, "pr_id": pr_id, "path_prefix": path_prefix}
    )
    changes = json.loads(res.content[0].text).get("files", [])
    logger.debug("[on_pr_event] changes from tool: %s", changes)

    # Step 2: Parse new keys
    new_keys = []
    for c in changes:
        logger.debug("[on_pr_event] processing file: %s type:%s", c["path"], c["type"])
        raw_res = await _mcp_session.call_tool(
            "get_bitbucket_file_raw",
            arguments={"project": project, "repo": repo, "path": c["path"], "at_ref": branch}
        )
        text = raw_res.content[0].text
        logger.debug("[on_pr_event] fetched file length=%d", len(text))
        keys = parse_sql_keys(text, only_new=(c["type"] == "MODIFY"))
        logger.debug("[on_pr_event] parsed keys: %s", keys)
        new_keys.extend(keys)

    # Step 3: Sync to Confluence
    logger.debug("[on_pr_event] syncing %d new keys to Confluence", len(new_keys))
    result = await _mcp_session.call_tool(
        "sync_confluence_table_delta",
        arguments={"space": space, "title": title, "data": [{"column": k, "description": ""} for k in new_keys]}
    )
    result = json.loads(result.content[0].text)
    # Step 4: Comment in Confluence
    if len(new_keys) > 0 and len(result["delta"]) > 0:
        new_columns = [entry["column"] for entry in result["delta"]]

        # build a comma-separated list
        columns_list = ", ".join(new_columns)

        # include both the count and the names in the comment
        comment = f"Hey @{author}, I’ve added {len(new_columns)} new key(s): {columns_list}. Please fill in descriptions!"
        
        logger.debug("[on_pr_event] posting comment: %s", comment)
        await _mcp_session.call_tool(
            "post_confluence_comment",
            arguments={"space": space, "title": title, "comment": comment}
        )
    else:
        logger.debug("[on_pr_event] Number of new keys is: %d. Not posting any comment", len(new_keys))


    logger.debug("[on_pr_event] completed, handled %d keys", len(new_keys))
    return JSONResponse({"status": "ok", "handled": len(new_keys)})


# SPA catch-all route - MUST be defined last to avoid intercepting API routes
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_catch_all(request: Request, full_path: str):
    """
    SPA (Single Page Application) catch-all route handler.
    
    **What is a SPA?**
    A Single Page Application (SPA) is a web application that loads a single HTML page
    and dynamically updates content as the user interacts with the app, without full
    page reloads. Popular examples include Gmail, Twitter, and Facebook.
    
    **How SPAs Work:**
    1. **Initial Load**: Browser requests any URL (e.g., `/analytics`, `/bi`, `/settings`)
    2. **Server Response**: Server always returns the same `ui.html` file
    3. **Client-Side Routing**: JavaScript (React Router) examines the URL and renders
       the appropriate component without server communication
    4. **Dynamic Updates**: Subsequent navigation happens entirely in JavaScript
    5. **API Calls**: Data fetching happens via AJAX calls to `/api/*` endpoints
    
    **Why This Route Exists:**
    - **URL Support**: Enables direct navigation to routes like `/analytics` or `/bi`
    - **Refresh Handling**: When users refresh the page on `/settings`, this route serves
      the React app instead of returning a 404 error
    - **Bookmarking**: Users can bookmark and share deep links to specific app pages
    - **SEO Friendly**: Search engines can crawl different URL paths
    
    **Route Pattern Explanation:**
    - `/{full_path:path}` - Catches ALL unmatched routes after API routes
    - Must be defined LAST to avoid intercepting `/api/*` endpoints
    - `full_path` parameter captures the entire path (e.g., "analytics/dashboard")
    
    **Example Flow:**
    1. User visits `http://localhost:5173/bi/sql-builder`
    2. This route catches the request since `/bi/sql-builder` doesn't match any API route
    3. Returns `ui.html` containing the React application
    4. React Router sees `/bi/sql-builder` in the URL and renders the SQL Builder component
    5. User sees the SQL Builder page without any server-side rendering
    
    **Technical Implementation:**
    - **Frontend**: React app with React Router for client-side routing
    - **Backend**: FastAPI serves the same HTML file for all non-API routes
    - **Templates**: Uses Jinja2 to serve `ui.html` with request context
    - **Static Assets**: CSS/JS bundles loaded by the HTML template
    
    **Benefits of SPA Architecture:**
    - **Fast Navigation**: No full page reloads between routes
    - **Rich Interactivity**: Smooth animations and state preservation
    - **Offline Capability**: Can work offline once initial assets are cached
    - **API-Driven**: Clean separation between frontend and backend
    
    Args:
        request (Request): FastAPI request object with headers, cookies, etc.
        full_path (str): The captured URL path (e.g., "analytics", "bi/dashboard")
        
    Returns:
        HTMLResponse: Always returns the same `ui.html` template containing the React SPA
        
    Note:
        This route will match ANY path that isn't handled by previous routes.
        Ensure all API routes are defined with `/api/` prefix to avoid conflicts.
    """
    # Always return the same React SPA entry point regardless of the requested path
    # The React Router will handle client-side routing based on the URL
    return templates.TemplateResponse("ui.html", {"request": request})