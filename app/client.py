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


# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8050/mcp/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

BASE_DIR    = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR  = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR  = os.path.join(BASE_DIR, "templates")

# Configure logging with timestamps for all loggers
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "app.middleware.analytics": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        },
        "fastapi": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False
        }
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["default"]
    }
}

# Apply logging configuration
logging.config.dictConfig(logging_config)

# Initialize FastAPI
app = FastAPI(title="MCP Client")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Add CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup analytics middleware for request logging
setup_analytics_middleware(app)

# Get logger with consistent formatting
logger = logging.getLogger("uvicorn.error")

# Import and include database routes
from app.routes.db_routes import router as db_router
# Import and include MCP testing routes
from app.routes.mcp_routes import router as mcp_router
# Import and include auth routes
from app.routes.auth_routes import router as auth_router
# Import and include user routes
from app.routes.users_routes import router as users_router
# Import and include test routes
from app.routes.test_routes import router as test_router
from app.routes.internal_data_routes import router as internal_data_router
# Import and include permissions routes
from app.routes.permissions_routes import router as permissions_router
# Import and include analytics routes
from app.routes.analytics_routes import router as analytics_router

# Expose database/API routes under /api to match UI calls
app.include_router(db_router, prefix="/api")
# Expose MCP testing routes under /api to match frontend expectations
app.include_router(mcp_router, prefix="/api")
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
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        logger.info("%s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception:
        logger.error("Unhandled error for %s %s", request.method, request.url.path, exc_info=True)
        raise

# AsyncExitStack to manage context managers in the same task
_exit_stack: AsyncExitStack
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
    Create and initialize the streamable http client and MCP session.
    Uses AsyncExitStack to ensure enter/exit occur in the same task.
    """
    global _exit_stack, _mcp_session
    _exit_stack = AsyncExitStack()

    # Establish http transport
    _http_transport = await _exit_stack.enter_async_context(
        streamablehttp_client(MCP_SERVER_URL, timeout = timedelta(seconds=600), sse_read_timeout = timedelta(seconds=600))
    )
    read_stream, write_stream, _ = _http_transport

    # Create and initialize MCP session
    _mcp_session = await _exit_stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )
    await _mcp_session.initialize()
    logger.info(f"MCP session initialized and connected to {MCP_SERVER_URL}")

    # Initialize the database
    init_db()

    # Seed demo data for development
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # Check if we need to seed demo data (if no request logs exist)
        from app.models import RequestLog
        existing_logs = db.query(RequestLog).first()
        if not existing_logs:
            logger.info("Seeding demo analytics data...")
            analytics_service.seed_demo_data(db)
    except Exception as e:
        logger.warning(f"Could not seed demo data: {e}")
    finally:
        db.close()

    # Start analytics monitoring
    await analytics_service.start_monitoring()

    llm_client = LLMClient()
    globals()["llm_client"] = llm_client
    logger.info("LLMClient initialized and ready.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("shutdown_event: enter")
    try:
        # Stop analytics monitoring
        await analytics_service.stop_monitoring()
        
        await _exit_stack.aclose()
    except Exception as e:
        logger.error("shutdown_event: error during aclose(): %s", e, exc_info=True)
    else:
        logger.info("shutdown_event: exit cleanly")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception during request %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

@app.get("/", response_class=HTMLResponse)
async def spa_root(request: Request):
    # templates points at your templates dir
    return templates.TemplateResponse("ui.html", {"request": request})


@app.post("/events/code-analysis", status_code=202)
async def code_analysis_endpoint(request: Request) -> QueryResponse:
    """
    Accept any JSON body, log it in full, then feed it to the LLM.
    Currently it supports getting only 1 json file.
    """
    # 1️⃣  Parse the raw JSON body
    try:
        payload = await request.json()
    except json.JSONDecodeError as err:
        logger.error("Invalid JSON body: %s", err, exc_info=True)
        raise HTTPException(status_code=400, detail="Body must be valid JSON")

    # 2️⃣  Log the entire payload for debugging / auditing
    logger.info("Received code-analysis payload:\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False))

    # 3️⃣  Build the LLM prompt (same template as before)
    prompt_text = CODE_ANALYSIS_PROMPT.format(
        reports_json=json.dumps(payload, indent=2, ensure_ascii=False)
    )

    # 4️⃣  Send to LLM and return its answer
    try:
        answer = await llm_client.process_query(
            user_query=prompt_text,
            session=_mcp_session
        )
        logger.info("LLM Final Answer:\n%s", answer)
        return QueryResponse(answer=answer)
    except Exception as err:
        logger.error("❌  LLM processing failed: %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail=str(err))


@app.post("/events/jira", status_code=202)
async def jira_endpoint(request: Request):

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
    return templates.TemplateResponse("ui.html", {"request": request})