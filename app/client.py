import os
import json
import asyncio
import logging
import re

from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple, Any
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from contextlib import AsyncExitStack
from datetime import timedelta
from app.llm_client import LLMClient
from app.prompts import *
from app.database import init_db


# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8050/mcp/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

BASE_DIR    = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR  = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR  = os.path.join(BASE_DIR, "templates")


uvicorn_logger = logging.getLogger("uvicorn.error")

if LOG_LEVEL != "INFO":
    logging.basicConfig(level=getattr(logging, LOG_LEVEL))
    uvicorn_logger.setLevel(getattr(logging, LOG_LEVEL))

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

    llm_client = LLMClient()
    globals()["llm_client"] = llm_client
    logger.info("LLMClient initialized and ready.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("shutdown_event: enter")
    try:
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

    

@app.post("/suggest-keys")
async def suggest_keys_api(request: Request):
    """
    POST /suggest-keys
    Expects JSON: {
      host, port, user, password, database,
      user_prompt,
      confluenceSpace, confluenceTitle
    }
    """
    # --- helpers for safe logging ---
    def _mask_secret(s: str, show: int = 2) -> str:
        if s is None:
            return "None"
        s = str(s)
        return (s[:show] + "..." + s[-show:]) if len(s) > (show * 2) else "***"

    def _sample_list(lst, n=25):
        return lst[:n]

    def _truncate(s: str, n: int = 600) -> str:
        s = s or ""
        return s if len(s) <= n else (s[:n] + f"... <+{len(s)-n} chars>")

    try:
        data = await request.json()
        logger.info(
            "suggest_keys_api: start space=%r title=%r host=%s port=%s db=%s user=%s",
            data.get("confluenceSpace"), data.get("confluenceTitle"),
            data.get("host"), data.get("port"), data.get("database"), data.get("user")
        )

        # Validate required fields (now including Confluence identifiers)
        required = ["host","port","user","password","database","user_prompt","confluenceSpace","confluenceTitle"]
        for field in required:
            if field not in data or data[field] in (None, ""):
                logger.error("suggest_keys_api: missing field=%r", field)
                raise ValueError(f"Missing field: {field}")

        log_copy = dict(data)
        log_copy["password"] = _mask_secret(log_copy.get("password"))
        log_copy["user_prompt"] = _truncate(log_copy.get("user_prompt"), 200)
        logger.debug("suggest_keys_api: validated payload (sanitized): %s", log_copy)

        # --- 1) Fetch key->description dict from MCP first ---
        desc_args = {
            "space": data["confluenceSpace"],
            "title": data["confluenceTitle"],
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],  # not logging this raw
            "database": data["database"],
        }
        safe_desc_args = dict(desc_args)
        safe_desc_args["password"] = _mask_secret(desc_args["password"])
        logger.info("suggest_keys_api: calling collect_db_confluence_key_descriptions … args=%s", safe_desc_args)

        desc_res = await _mcp_session.call_tool(
            "collect_db_confluence_key_descriptions",
            arguments=desc_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts = getattr(desc_res, "content", []) or []
        logger.debug("suggest_keys_api: collect_db_confluence_key_descriptions returned %d content part(s)", len(parts))

        desc_text_parts = [m.text for m in parts if getattr(m, "text", None)]
        desc_text = desc_text_parts[0] if desc_text_parts else "{}"
        logger.debug("suggest_keys_api: descriptions JSON length=%d chars", len(desc_text))

        try:
            key_descriptions = json.loads(desc_text)
            logger.info("suggest_keys_api: parsed descriptions entries=%d", len(key_descriptions))
            logger.debug(
                "suggest_keys_api: sample descriptions keys=%s",
                _sample_list(list(key_descriptions.keys()))
            )
        except json.JSONDecodeError as je:
            logger.warning("suggest_keys_api: failed to parse descriptions JSON (%s), falling back to empty {}", je)
            key_descriptions = {}

        # --- 2) Build an AUGMENTED *USER* PROMPT (not system prompt) with descriptions ---
        augmented_user_prompt = (
            (data.get("user_prompt") or "").rstrip()
            + "\n\n---\n"
            + "KNOWN_COLUMN_DESCRIPTIONS_JSON:\n"
            + json.dumps(key_descriptions, ensure_ascii=False)
            + "\n\nGuidance: Prefer columns whose names or descriptions semantically match the request. "
              "Output one column per line in structure: table.column - description - value type."
        )
        logger.info(
            "suggest_keys_api: augmented_user_prompt built (length=%d chars, desc_count=%d)",
            len(augmented_user_prompt), len(key_descriptions)
        )
        logger.debug("suggest_keys_api: augmented_user_prompt (truncated): %s", _truncate(augmented_user_prompt))

        # --- 3) Call the MCP tool for suggestions with original SYSTEM prompt and augmented USER prompt ---
        tool_args = {
            "space": data["confluenceSpace"],
            "title": data["confluenceTitle"],
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],  # not logging this raw
            "database": data["database"],
            "system_prompt": BI_ANALYTICS_PROMPT,     # unchanged system prompt
            "user_prompt": augmented_user_prompt,     # descriptions moved here
        }
        safe_tool_args = dict(tool_args)
        safe_tool_args["password"] = _mask_secret(safe_tool_args["password"])
        safe_tool_args["user_prompt"] = f"<redacted user prompt, {len(augmented_user_prompt)} chars>"
        safe_tool_args["system_prompt"] = f"<BI_ANALYTICS_PROMPT, {len(BI_ANALYTICS_PROMPT)} chars>"
        logger.info("suggest_keys_api: calling suggest_keys_for_analytics … args=%s", safe_tool_args)

        result = await _mcp_session.call_tool(
            "suggest_keys_for_analytics",
            arguments=tool_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts2 = getattr(result, "content", []) or []
        logger.debug("suggest_keys_api: suggest_keys_for_analytics returned %d content part(s)", len(parts2))

        full_text = "\n".join(m.text for m in parts2 if getattr(m, "text", None))
        logger.debug("suggest_keys_api: raw suggestion text length=%d chars", len(full_text))

        keys = [k.strip() for k in full_text.replace(",", "\n").splitlines() if k.strip()]
        logger.info("suggest_keys_api: extracted %d suggested key(s)", len(keys))
        logger.debug("suggest_keys_api: suggested keys sample=%s", _sample_list(keys))

        return JSONResponse({"suggested_keys": keys})

    except Exception as e:
        logger.error("Error in suggest_keys_api: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/suggest-keys", response_class=HTMLResponse)
async def suggest_keys_ui():
    """
    GET /suggest-keys
    Serves an interactive HTML page for entering DB credentials
    and an analytics question, then displays the suggested keys.
    """
    # Safely JSON-encode the system prompt for injection into JS
    system_prompt_json = json.dumps(BI_ANALYTICS_PROMPT)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BI Key Suggester</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/modern-normalize/1.1.0/modern-normalize.min.css">
  <style>
    body { background: #f5f7fa; font-family: Arial, sans-serif; margin: 0; padding: 0; }
    .container { max-width: 700px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    h1 { text-align: center; margin-bottom: 20px; }
    .form-group { margin-bottom: 15px; }
    label { display: block; font-weight: bold; margin-bottom: 5px; }
    input, textarea { width: 100%; padding: 10px; font-size: 1rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 12px; font-size: 1rem; background: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
    button:disabled { background: #aaa; cursor: not-allowed; }
    .output { background: #eef1f5; padding: 15px; border-radius: 4px; margin-top: 20px; white-space: pre-wrap; min-height: 100px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>BI Key Suggester</h1>
    <div class="form-group"><label for="host">Host</label><input id="host" type="text" value="127.0.0.1"></div>
    <div class="form-group"><label for="port">Port</label><input id="port" type="number" value="5432"></div>
    <div class="form-group"><label for="user">User</label><input id="user" type="text" value="malluser"></div>
    <div class="form-group"><label for="password">Password</label><input id="password" type="password" value="mallpass"></div>
    <div class="form-group"><label for="database">Database</label><input id="database" type="text" value="malldb"></div>
    <div class="form-group"><label for="confluenceSpace">confluenceSpace</label><input id="confluenceSpace" type="text" value="AAA"></div>
    <div class="form-group"><label for="confluenceTitle">confluenceTitle</label><input id="confluenceTitle" type="text" value="Demo - database keys description"></div>
    <div class="form-group"><label for="user_prompt">Analytics Question</label><textarea id="user_prompt" rows="4"></textarea></div>
    <button id="submit">Get Suggested Keys</button>
    <div id="output" class="output"></div>
  </div>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      console.log('UI loaded');
      document.getElementById('submit').addEventListener('click', onSubmit);
    });

    async function onSubmit() {
      console.log('Submit clicked');
      const btn = document.getElementById('submit');
      const out = document.getElementById('output');
      btn.disabled = true;
      out.textContent = 'Thinking…';

      const payload = {
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value),
        user: document.getElementById('user').value,
        password: document.getElementById('password').value,
        database: document.getElementById('database').value,
        confluenceSpace: document.getElementById('confluenceSpace').value,
        confluenceTitle: document.getElementById('confluenceTitle').value,
        user_prompt: document.getElementById('user_prompt').value,
        system_prompt: """ + system_prompt_json + """
      };

      try {
        const resp = await fetch('/suggest-keys', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        console.log('Fetch response:', resp);
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        console.log('Data:', data);
        out.textContent = data.suggested_keys.join('\\n');
      } catch (err) {
        console.error(err);
        out.textContent = 'Error: ' + err.message;
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>"""

    return HTMLResponse(html)


@app.post("/analytics-query")
async def analytics_query_api(request: Request):
    """
    POST /analytics-query
    Expects:
      {
        "host": str, "port": int, "user": str, "password": str, "database": str,
        "analytics_prompt": str, "system_prompt": str,
        # optional:
        "confluenceSpace": str, "confluenceTitle": str
      }
    """
    try:
        data = await request.json()
        logger.info(
            "analytics_query_api: start host=%s port=%s db=%s user=%s space=%r title=%r",
            data.get("host"), data.get("port"), data.get("database"), data.get("user"),
            data.get("confluenceSpace"), data.get("confluenceTitle")
        )

        # validate required only
        for f in ("host", "port", "user", "password", "database", "analytics_prompt", "system_prompt"):
            if f not in data or data[f] is None:
                logger.error("analytics_query_api: missing field=%r", f)
                raise ValueError(f"Missing field: {f}")

        # 1) (optional) get Confluence key->description and append to analytics_prompt
        analytics_prompt = data["analytics_prompt"]
        space = data.get("confluenceSpace")
        title = data.get("confluenceTitle")
        if space and title:
            logger.info("analytics_query_api: fetching Confluence descriptions space=%r title=%r", space, title)
            desc_args = {
                "space": space, "title": title,
                "host": data["host"], "port": data["port"],
                "user": data["user"], "password": data["password"],
                "database": data["database"],
            }
            desc_res = await _mcp_session.call_tool(
                "collect_db_confluence_key_descriptions",
                arguments=desc_args,
                read_timeout_seconds=timedelta(seconds=600)
            )
            desc_text = next((m.text for m in (getattr(desc_res, "content", []) or []) if getattr(m, "text", None)), "{}")
            try:
                key_desc = json.loads(desc_text)
                logger.info("analytics_query_api: descriptions entries=%d", len(key_desc))
                analytics_prompt = (
                    analytics_prompt.rstrip()
                    + "\n\n---\nKNOWN_COLUMN_DESCRIPTIONS_JSON:\n"
                    + json.dumps(key_desc, ensure_ascii=False)
                )
                logger.debug("analytics_query_api: augmented analytics_prompt length=%d", len(analytics_prompt))
            except json.JSONDecodeError:
                logger.warning("analytics_query_api: descriptions not valid JSON; ignoring")

        # 2) call MCP tool (same signature as before)
        args = {
            "host": data["host"], "port": data["port"], "user": data["user"],
            "password": data["password"], "database": data["database"],
            "analytics_prompt": analytics_prompt,                 # may be augmented
            "system_prompt": data["system_prompt"]
        }
        logger.info("analytics_query_api: calling run_analytics_query_on_database …")
        res = await _mcp_session.call_tool(
            "run_analytics_query_on_database",
            arguments=args,
            read_timeout_seconds=timedelta(seconds=600)
        )
        logger.info("analytics_query_api: tool returned %d part(s)", len(getattr(res, "content", []) or []))

        # 3) tool returns list-of-dicts (same behavior as your original)
        rows = []
        for i, msg in enumerate(res.content):
            try:
                rows_obj = json.loads(msg.text)
                if isinstance(rows_obj, list):
                    rows.extend(rows_obj)
                else:
                    rows.append(rows_obj)
            except Exception as pe:
                logger.warning("analytics_query_api: failed to parse part %d as JSON: %s", i, pe)

        logger.info("analytics_query_api: final rows=%d", len(rows))
        if rows:
            logger.debug("analytics_query_api: first row sample=%s", rows[0])

        return JSONResponse({"rows": rows})
    except Exception as e:
        logger.error("Error in analytics_query_api: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/analytics-query", response_class=HTMLResponse)
async def analytics_query_ui():
    """
    GET /analytics-query
    Serves an interactive form for DB creds + analytics prompt.
    On submit, posts to /analytics-query and renders the result.
    """
    prompt_json = json.dumps(BI_SQL_GENERATION_PROMPT)
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>Run Analytics Query</title>
  <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/modern-normalize/1.1.0/modern-normalize.min.css\">
  <style>
    body {{ background:#f5f7fa; font-family:Arial,sans-serif; margin:0; padding:0; }}
    .container {{ max-width:800px; margin:40px auto; background:#fff; padding:30px; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.1); }}
    h1 {{ text-align:center; margin-bottom:20px; }}
    .form-group {{ margin-bottom:15px; }}
    label {{ display:block; font-weight:bold; margin-bottom:5px; }}
    input, textarea {{ width:100%; padding:10px; font-size:1rem; border:1px solid #ccc; border-radius:4px; box-sizing:border-box; }}
    button {{ width:100%; padding:12px; font-size:1rem; background:#17a2b8; color:#fff; border:none; border-radius:4px; cursor:pointer; }}
    button:disabled {{ background:#aaa; cursor:not-allowed; }}
    table {{ width:100%; border-collapse:collapse; margin-top:20px; }}
    th, td {{ padding:8px 12px; border:1px solid #ddd; text-align:left; }}
    th {{ background:#f0f0f0; }}
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Run Analytics Query</h1>
    <div class=\"form-group\"><label for=\"host\">Host</label><input id=\"host\" value=\"127.0.0.1\"></div>
    <div class=\"form-group\"><label for=\"port\">Port</label><input id=\"port\" type=\"number\" value=\"5432\"></div>
    <div class=\"form-group\"><label for=\"user\">User</label><input id=\"user\" value=\"malluser\"></div>
    <div class=\"form-group\"><label for=\"password\">Password</label><input id=\"password\" type=\"password\" value=\"mallpass\"></div>
    <div class=\"form-group\"><label for=\"database\">Database</label><input id=\"database\" value=\"malldb\"></div>
    <div class=\"form-group\"><label for=\"confluenceSpace\">confluenceSpace</label><input id=\"confluenceSpace\" value=\"AAA\"></div>
    <div class=\"form-group\"><label for=\"confluenceTitle\">confluenceTitle</label><input id=\"confluenceTitle\" value=\"Demo - database keys description\"></div>
    <div class=\"form-group\"><label for=\"analytics_prompt\">Analytics Prompt</label><textarea id=\"analytics_prompt\" rows=\"4\"></textarea></div>
    <button id=\"submit\">Run Query</button>
    <table id=\"output-table\" style=\"display:none\"><thead><tr id=\"header-row\"></tr></thead><tbody id=\"output\"></tbody></table>
  </div>
  <script>
    const systemPrompt = {prompt_json};
    document.addEventListener('DOMContentLoaded', () => {{
      document.getElementById('submit').addEventListener('click', onSubmit);
    }});
    async function onSubmit() {{
      const btn = document.getElementById('submit');
      const table = document.getElementById('output-table');
      const headerRow = document.getElementById('header-row');
      const body = document.getElementById('output');
      btn.disabled = true;
      headerRow.innerHTML = '';
      body.innerHTML = '';
      table.style.display = 'none';
      const payload = {{
        host: document.getElementById('host').value,
        port: +document.getElementById('port').value,
        user: document.getElementById('user').value,
        password: document.getElementById('password').value,
        database: document.getElementById('database').value,
        confluenceSpace: document.getElementById('confluenceSpace').value,
        confluenceTitle: document.getElementById('confluenceTitle').value,
        analytics_prompt: document.getElementById('analytics_prompt').value,
        system_prompt: systemPrompt
      }};
      try {{
        const resp = await fetch('/analytics-query', {{ method: 'POST', headers: {{'Content-Type':'application/json'}}, body: JSON.stringify(payload) }});
        if (!resp.ok) throw new Error(await resp.text());
        const {{ rows }} = await resp.json();
        if (!rows.length) {{
          body.innerHTML = '<tr><td><em>No results.</em></td></tr>';
        }} else {{
          Object.keys(rows[0]).forEach(col => {{
            const th = document.createElement('th'); th.textContent = col; headerRow.appendChild(th);
          }});
          rows.forEach(r => {{
            const tr = document.createElement('tr');
            Object.values(r).forEach(val => {{ const td = document.createElement('td'); td.textContent = val; tr.appendChild(td); }});
            body.appendChild(tr);
          }});
        }}
        table.style.display = 'table';
      }} catch (err) {{
        alert('Error: ' + err.message);
      }} finally {{
        btn.disabled = false;
      }}
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(html)


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

@app.post("/sync-all-tables")
async def sync_all_tables(request: Request):
    payload = await request.json()
    for field in (
        "database_type", "host", "port", "user",
        "password", "database", "space", "title", "limit"
    ):
        if field not in payload:
            raise HTTPException(400, f"Missing '{field}'")

    common_args = {
        "host":          payload["host"],
        "port":          payload["port"],
        "user":          payload["user"],
        "password":      payload["password"],
        "database":      payload["database"],
        "database_type": payload["database_type"],
    }

    # 1) List tables (single-chunk as before)
    list_res = await _mcp_session.call_tool(
        "list_database_tables",
        arguments=common_args,
        read_timeout_seconds=timedelta(seconds=60),
    )
    tables = json.loads(list_res.content[0].text)
    logger.debug(f"Found the tables: {tables}")
    # 2) Fetch schema map (single-chunk as before)
    keys_res = await _mcp_session.call_tool(
        "list_database_keys",
        arguments=common_args,
        read_timeout_seconds=timedelta(seconds=60),
    )
    schema_map = json.loads(keys_res.content[0].text)
    logger.debug(f"The keys that were found for each table are: {schema_map}")
    results = []

    for tbl in tables:
        all_cols = schema_map.get(tbl, [])
        if not all_cols:
            results.append({"table": tbl, "newColumns": [], "error": "no_schema"})
            continue

        # 3a) Compute delta (now join all chunks)
        delta_res = await _mcp_session.call_tool(
            "get_table_delta_keys",
            arguments={
                "space":   payload["space"],
                "title":   payload["title"],
                "columns": [f"{tbl}.{c}" for c in all_cols]
            },
            read_timeout_seconds=timedelta(seconds=60),
        )
        delta_chunks = [msg.text for msg in delta_res.content]
        logger.debug("Delta chunks for %s: %r", tbl, delta_chunks)
        delta_text = "".join(delta_chunks)
        logger.debug("Combined delta JSON for %s: %s", tbl, delta_text)
        try:
            missing = json.loads(delta_text)
        except Exception as e:
            logger.warning("Failed to parse delta JSON for %s: %s", tbl, e)
            missing = []

        if not missing:
            results.append({"table": tbl, "newColumns": [], "error": None})
            continue

        # 3b) Describe only the missing columns (also join all chunks)
        desc_res = await _mcp_session.call_tool(
            "describe_columns",
            arguments={
                **common_args,
                "table":   tbl,
                "columns": [c.split(".",1)[1] for c in missing],
                "limit":   payload["limit"],
            },
            read_timeout_seconds=None,
        )
        desc_chunks = [msg.text for msg in desc_res.content]
        logger.debug("Description chunks for %s: %r", tbl, desc_chunks)
        desc_text = "".join(desc_chunks)
        logger.debug("Combined descriptions JSON for %s: %s", tbl, desc_text)
        try:
            descriptions = json.loads(desc_text)
        except Exception as e:
            logger.error("Failed to parse descriptions JSON for %s: %s", tbl, e)
            descriptions = []

        # 3c) Sync delta descriptions to Confluence (single-chunk)
        sync_res = await _mcp_session.call_tool(
            "sync_confluence_table_delta",
            arguments={
                "space": payload["space"],
                "title": payload["title"],
                "data":  descriptions
            },
            read_timeout_seconds=timedelta(seconds=300),
        )
        sync_info = {"delta": []}
        if sync_res.content:
            try:
                sync_info = json.loads(sync_res.content[0].text)
            except Exception as e:
                logger.error("Failed to parse sync JSON for %s: %s", tbl, e)

        results.append({
            "table":      tbl,
            "newColumns": sync_info.get("delta", []),
            "error":      None
        })

    return JSONResponse({"results": results})


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