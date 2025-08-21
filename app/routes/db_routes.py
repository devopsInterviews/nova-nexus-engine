import logging
import json
import traceback
import os
from pathlib import Path
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from app.prompts import BI_ANALYTICS_PROMPT

# Create router with tags for API documentation
router = APIRouter(prefix="", tags=["database"])  # prefix inherited from app.include_router("/api")
logger = logging.getLogger("uvicorn.error")

def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    s = str(value)
    return (s[:2] + "***" + s[-2:]) if len(s) > 4 else "***"

def _resolve_connection_payload(data: Dict[str, Any], saved: List[Dict[str, Any]]):
    """Allow using connection_id or name to populate host/port/user/... fields."""
    # If full fields provided, return as-is
    required = ["host","port","user","password","database","database_type"]
    if all(k in data and data[k] not in (None, "") for k in required):
        return data
    # Try resolve by id
    conn = None
    cid = data.get("connection_id")
    cname = data.get("connection_name") or data.get("name")
    if cid:
        conn = next((c for c in saved if str(c.get("id")) == str(cid)), None)
    if not conn and cname:
        conn = next((c for c in saved if c.get("name") == cname), None)
    if not conn:
        raise HTTPException(status_code=400, detail="Missing DB credentials and no matching connection profile found")
    merged = {**conn, **{k:v for k,v in data.items() if v not in (None, "")}}
    # Normalize types
    try:
        merged["port"] = int(merged["port"])  # type: ignore
    except Exception:
        pass
    return merged


# Simple JSON file persistence for saved connections
DATA_DIR = "/home/appuser/data"
os.makedirs(DATA_DIR, exist_ok=True)
CONNECTIONS_FILE = os.path.join(DATA_DIR, "connections.json")

def _load_saved_connections() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(CONNECTIONS_FILE):
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        logger.error("Failed to load connections.json", exc_info=True)
    return []

def _persist_saved_connections(conns: List[Dict[str, Any]]):
    try:
        with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(conns, f, indent=2)
    except Exception:
        logger.error("Failed to write connections.json", exc_info=True)

@router.post("/test-connection")
async def test_connection(request: Request):
    """
    Test a database connection
    """
    try:
        from app.client import _mcp_session  # Import here to avoid circular imports
        
        # Parse request body
        try:
            data = await request.json()
            logger.debug(f"Received test connection request: {data}")
        except Exception as e:
            logger.error(f"Failed to parse request JSON: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Invalid JSON in request: {str(e)}"
                }
            )
            
        # Allow referencing saved profile via connection_id/name
        payload = _resolve_connection_payload(data, saved_connections)
        # Extract connection details
        host = payload["host"]
        port = int(payload["port"])
        user = payload["user"]
        password = payload["password"]
        database = payload["database"]
        db_type = payload["database_type"]
        
        logger.info(
            "Testing connection to %s at %s:%s db=%s user=%s",
            db_type, host, port, database, user
        )
        
        # Use list_database_tables tool to test the connection
        try:
            result = await _mcp_session.call_tool(
                "list_database_tables",
                arguments={
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": password,
                    "database": database,
                    "database_type": db_type
                }
            )
            
            # If we get here without an exception, the connection worked
            if result.content and len(result.content) > 0:
                tables_text = result.content[0].text
                tables = json.loads(tables_text)
                
                logger.info(f"Connection successful, found {len(tables)} tables")
                return JSONResponse({
                    "success": True,
                    "message": f"Successfully connected to {database} database ({len(tables)} tables found)"
                })
            else:
                logger.warning("Connection test returned no content")
                return JSONResponse({
                    "success": True,
                    "message": f"Connected to {database} database but no tables were found"
                })
        except Exception as tool_error:
            logger.error(f"MCP tool error: {str(tool_error)}")
            logger.error(traceback.format_exc())
            return JSONResponse({
                "success": False,
                "message": f"Database connection error: {str(tool_error)}"
            })
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "success": False,
            "message": f"Connection failed: {str(e)}"
        })

@router.post("/save-connection")
async def save_connection(request: Request):
    """
    Save a database connection (for demo purposes, this is just stored in memory)
    """
    # In a real application, you would store this in a database
    global connection_id_counter
    
    try:
        data = await request.json()
        required_fields = ["host", "port", "user", "password", "database", "database_type", "name"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        connection_id = len(saved_connections) + 1

        connection = {
            "id": str(connection_id),
            "name": data["name"],
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],  # In a real app, encrypt this!
            "database": data["database"],
            "database_type": data["database_type"]
        }
        
        saved_connections.append(connection)
        _persist_saved_connections(saved_connections)
        logger.info(
            "Saved connection id=%s name=%s %s:%s/%s user=%s",
            connection_id, connection["name"], connection["host"], connection["port"], connection["database"], connection["user"]
        )
        
        return JSONResponse({
            "id": str(connection_id)
        })
    
    except Exception as e:
        logger.error(f"Error saving connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-connection/{connection_id}")
async def delete_connection(connection_id: str):
    """
    Delete a saved connection by ID
    """
    try:
        global saved_connections
        # Find and remove the connection
        original_count = len(saved_connections)
        saved_connections = [conn for conn in saved_connections if str(conn.get("id")) != connection_id]
        
        if len(saved_connections) < original_count:
            # Connection was found and deleted
            _persist_saved_connections(saved_connections)
            logger.info("Deleted connection id=%s", connection_id)
            return JSONResponse({
                "status": "success",
                "message": f"Connection {connection_id} deleted successfully"
            })
        else:
            # Connection not found
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Connection {connection_id} not found"
                }
            )
    except Exception as e:
        logger.error(f"Error deleting connection {connection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to delete connection: {str(e)}"
            }
        )

@router.get("/get-connections")
async def get_connections():
    """
    Get all saved connections
    """
    # sync from disk in case other processes modified it
    global saved_connections
    saved_connections = _load_saved_connections()
    # Do not return passwords in response
    redacted = [
        {**c, "password": _mask_secret(c.get("password"))}
        for c in saved_connections
    ]
    logger.info("Returning %d saved connections", len(saved_connections))
    return JSONResponse(redacted)

@router.get("/health")
async def api_health_check():
    """
    Simple health check endpoint to verify API is running
    """
    return JSONResponse({
        "status": "ok", 
        "service": "database-api",
        "connections_count": len(saved_connections)
    })

@router.post("/list-tables")
async def list_tables(request: Request):
    """
    List tables in the database
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()

        # Resolve from profile if needed
        data = _resolve_connection_payload(data, saved_connections)

        logger.info("Listing tables for %s on %s:%s/%s", data['database_type'], data['host'], data['port'], data['database'])

        # Call MCP tool to list tables
        try:
            result = await _mcp_session.call_tool(
                "list_database_tables",
                arguments={
                    "host": data["host"],
                    "port": data["port"],
                    "user": data["user"],
                    "password": data["password"],
                    "database": data["database"],
                    "database_type": data["database_type"]
                }
            )
            
            # Process the response
            tables_text = result.content[0].text if result.content else "[]"
            tables = json.loads(tables_text)
            
            return JSONResponse({
                "status": "success",
                "data": tables
            })
                
        except Exception as tool_error:
            logger.error(f"List tables tool error: {str(tool_error)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": f"List tables failed: {str(tool_error)}"
                }
            )
            
    except Exception as e:
        logger.error(f"List tables request failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Request processing failed: {str(e)}"
            }
        )

@router.post("/describe-columns")
async def describe_columns(request: Request):
    """
    Describe columns in a table
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()
        
        # Resolve from profile
        data = _resolve_connection_payload(data, saved_connections)
        if "table" not in data:
            return JSONResponse(status_code=400, content={"status":"error","error":"Missing required field: table"})
        
        logger.info(f"Describing columns for table {data['table']} in {data['database_type']} database")
        
        # Call MCP tool to describe columns
        try:
            result = await _mcp_session.call_tool(
                "describe_table_columns",
                arguments={
                    "host": data["host"],
                    "port": data["port"],
                    "user": data["user"],
                    "password": data["password"],
                    "database": data["database"],
                    "database_type": data["database_type"],
                    "table": data["table"],
                    "limit": data.get("limit", 100)
                }
            )
            
            # Process the response
            columns_text = result.content[0].text if result.content else "[]"
            columns = json.loads(columns_text)
            
            # Transform to include data types
            formatted_columns = []
            for col in columns:
                formatted_columns.append({
                    "column": col.get("column", ""),
                    "description": col.get("description", ""),
                    "data_type": col.get("data_type", "")
                })
            
            return JSONResponse({
                "status": "success",
                "data": formatted_columns
            })
                
        except Exception as tool_error:
            logger.error(f"Describe columns tool error: {str(tool_error)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": f"Describe columns failed: {str(tool_error)}"
                }
            )
            
    except Exception as e:
        logger.error(f"Describe columns request failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Request processing failed: {str(e)}"
            }
        )

@router.post("/suggest-columns")
async def suggest_columns(request: Request):
    """
    Suggest columns based on natural language prompt with confluence integration
    Replicates the working suggest_keys_api function from client.py
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    # --- Helper functions for safe logging (copied from working client.py) ---
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
        # Parse and validate request data
        data = await request.json()
        logger.info("suggest_columns: received request with payload keys: %s", list(data.keys()))
        
        # Resolve connection profile first
        saved_connections = _load_saved_connections()
        data = _resolve_connection_payload(data, saved_connections)
        
        logger.info(
            "suggest_columns: start space=%r title=%r host=%s port=%s db=%s user=%s",
            data.get("confluenceSpace"), data.get("confluenceTitle"),
            data.get("host"), data.get("port"), data.get("database"), data.get("user")
        )

        # Validate required fields (including Confluence identifiers)
        required = ["host","port","user","password","database","user_prompt","confluenceSpace","confluenceTitle"]
        for field in required:
            if field not in data or data[field] in (None, ""):
                logger.error("suggest_columns: missing field=%r", field)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": f"Missing required field: {field}"}
                )

        log_copy = dict(data)
        log_copy["password"] = _mask_secret(log_copy.get("password"))
        log_copy["user_prompt"] = _truncate(log_copy.get("user_prompt"), 200)
        logger.debug("suggest_columns: validated payload (sanitized): %s", log_copy)

        # --- Step 1: Fetch key->description dict from MCP first ---
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
        logger.info("suggest_columns: calling collect_db_confluence_key_descriptions … args=%s", safe_desc_args)

        desc_res = await _mcp_session.call_tool(
            "collect_db_confluence_key_descriptions",
            arguments=desc_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts = getattr(desc_res, "content", []) or []
        logger.debug("suggest_columns: collect_db_confluence_key_descriptions returned %d content part(s)", len(parts))

        desc_text_parts = [m.text for m in parts if getattr(m, "text", None)]
        desc_text = desc_text_parts[0] if desc_text_parts else "{}"
        logger.debug("suggest_columns: descriptions JSON length=%d chars", len(desc_text))

        try:
            key_descriptions = json.loads(desc_text)
            logger.info("suggest_columns: parsed descriptions entries=%d", len(key_descriptions))
            logger.debug(
                "suggest_columns: sample descriptions keys=%s",
                _sample_list(list(key_descriptions.keys()))
            )
        except json.JSONDecodeError as je:
            logger.warning("suggest_columns: failed to parse descriptions JSON (%s), falling back to empty {}", je)
            key_descriptions = {}

        # --- Step 2: Build an AUGMENTED *USER* PROMPT (not system prompt) with descriptions ---
        augmented_user_prompt = (
            (data.get("user_prompt") or "").rstrip()
            + "\n\n---\n"
            + "KNOWN_COLUMN_DESCRIPTIONS_JSON:\n"
            + json.dumps(key_descriptions, ensure_ascii=False)
            + "\n\nGuidance: Prefer columns whose names or descriptions semantically match the request. "
              "Output one column per line in structure: table.column - description - value type."
        )
        logger.info(
            "suggest_columns: augmented_user_prompt built (length=%d chars, desc_count=%d)",
            len(augmented_user_prompt), len(key_descriptions)
        )
        logger.debug("suggest_columns: augmented_user_prompt (truncated): %s", _truncate(augmented_user_prompt))

        # --- Step 3: Call the MCP tool for suggestions with SYSTEM prompt and augmented USER prompt ---
        tool_args = {
            "space": data["confluenceSpace"],
            "title": data["confluenceTitle"],
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],  # not logging this raw
            "database": data["database"],
            "system_prompt": BI_ANALYTICS_PROMPT,     # CRITICAL: This was missing!
            "user_prompt": augmented_user_prompt,     # descriptions moved here
        }
        safe_tool_args = dict(tool_args)
        safe_tool_args["password"] = _mask_secret(safe_tool_args["password"])
        safe_tool_args["user_prompt"] = f"<redacted user prompt, {len(augmented_user_prompt)} chars>"
        safe_tool_args["system_prompt"] = f"<BI_ANALYTICS_PROMPT, {len(BI_ANALYTICS_PROMPT)} chars>"
        logger.info("suggest_columns: calling suggest_keys_for_analytics … args=%s", safe_tool_args)

        result = await _mcp_session.call_tool(
            "suggest_keys_for_analytics",
            arguments=tool_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts2 = getattr(result, "content", []) or []
        logger.debug("suggest_columns: suggest_keys_for_analytics returned %d content part(s)", len(parts2))

        full_text = "\n".join(m.text for m in parts2 if getattr(m, "text", None))
        logger.debug("suggest_columns: raw suggestion text length=%d chars", len(full_text))

        keys = [k.strip() for k in full_text.replace(",", "\n").splitlines() if k.strip()]
        logger.info("suggest_columns: extracted %d suggested key(s)", len(keys))
        logger.debug("suggest_columns: suggested keys sample=%s", _sample_list(keys))

        # --- Step 4: Format response to match frontend expectations ---
        # Parse the suggested keys into structured format
        columns: List[Dict[str, Any]] = []
        for key in keys:
            logger.debug("suggest_columns: parsing key: %s", key)
            # Parse format: "table.column - description - value type"
            parts = [p.strip() for p in key.split(" - ", 2)]  # Fixed: use " - " with spaces
            column_name = parts[0] if parts else key
            description = parts[1] if len(parts) > 1 else ""
            data_type = parts[2] if len(parts) > 2 else "TEXT"
            
            parsed_column = {
                "name": column_name,
                "description": description,
                "data_type": data_type
            }
            
            logger.debug("suggest_columns: parsed column: %s", parsed_column)
            columns.append(parsed_column)

        logger.info("suggest_columns: parsed %d columns successfully", len(columns))

        # Create the response format expected by the frontend
        response_data = {
            "status": "success",
            "data": {
                "suggested_columns": columns,
                "suggested_columns_map": {
                    c["name"]: {
                        "description": c["description"],
                        "data_type": c["data_type"]
                    } for c in columns
                }
            }
        }

        logger.info("suggest_columns: successfully processed %d columns, returning response", len(columns))
        return JSONResponse(response_data)
                
    except Exception as e:
        logger.error("suggest_columns: error occurred: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Column suggestion failed: {str(e)}"
            }
        )

@router.post("/analytics-query")
async def analytics_query(request: Request):
    """
    Run an analytics query based on natural language with confluence integration
    Replicates the working analytics_query_api function from client.py
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    # --- Helper functions for safe logging (copied from working client.py) ---
    def _mask_secret(s: str, show: int = 2) -> str:
        if s is None:
            return "None"
        s = str(s)
        return (s[:show] + "..." + s[-show:]) if len(s) > (show * 2) else "***"

    def _truncate(s: str, n: int = 600) -> str:
        s = s or ""
        return s if len(s) <= n else (s[:n] + f"... <+{len(s)-n} chars>")
    
    try:
        # Parse and validate request data
        data = await request.json()
        logger.info("analytics_query: received request with payload keys: %s", list(data.keys()))
        
        # Resolve connection profile first
        saved_connections = _load_saved_connections()
        data = _resolve_connection_payload(data, saved_connections)
        
        logger.info(
            "analytics_query: start host=%s port=%s db=%s user=%s space=%r title=%r",
            data.get("host"), data.get("port"), data.get("database"), data.get("user"),
            data.get("confluenceSpace"), data.get("confluenceTitle")
        )

        # Validate required fields
        required = ["host", "port", "user", "password", "database", "analytics_prompt", "system_prompt"]
        for field in required:
            if field not in data or data[field] in (None, ""):
                logger.error("analytics_query: missing field=%r", field)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": f"Missing required field: {field}"}
                )

        log_copy = dict(data)
        log_copy["password"] = _mask_secret(log_copy.get("password"))
        log_copy["analytics_prompt"] = _truncate(log_copy.get("analytics_prompt"), 200)
        log_copy["system_prompt"] = _truncate(log_copy.get("system_prompt"), 100)
        logger.debug("analytics_query: validated payload (sanitized): %s", log_copy)

        # --- Step 1: (Optional) Get Confluence descriptions and augment prompt ---
        analytics_prompt = data["analytics_prompt"]
        space = data.get("confluenceSpace")
        title = data.get("confluenceTitle")
        
        if space and title:
            logger.info("analytics_query: fetching Confluence descriptions space=%r title=%r", space, title)
            desc_args = {
                "space": space,
                "title": title,
                "host": data["host"],
                "port": data["port"],
                "user": data["user"],
                "password": data["password"],
                "database": data["database"],
            }
            
            desc_res = await _mcp_session.call_tool(
                "collect_db_confluence_key_descriptions",
                arguments=desc_args,
                read_timeout_seconds=timedelta(seconds=600)
            )
            
            desc_text = next((m.text for m in (getattr(desc_res, "content", []) or []) if getattr(m, "text", None)), "{}")
            logger.debug("analytics_query: descriptions JSON length=%d chars", len(desc_text))
            
            try:
                key_desc = json.loads(desc_text)
                logger.info("analytics_query: descriptions entries=%d", len(key_desc))
                analytics_prompt = (
                    analytics_prompt.rstrip()
                    + "\n\n---\nKNOWN_COLUMN_DESCRIPTIONS_JSON:\n"
                    + json.dumps(key_desc, ensure_ascii=False)
                )
                logger.debug("analytics_query: augmented analytics_prompt length=%d", len(analytics_prompt))
            except json.JSONDecodeError:
                logger.warning("analytics_query: descriptions not valid JSON; ignoring")

        # --- Step 2: Call MCP tool to run analytics query ---
        tool_args = {
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],
            "database": data["database"],
            "analytics_prompt": analytics_prompt,  # may be augmented
            "system_prompt": data["system_prompt"]
        }
        
        safe_tool_args = dict(tool_args)
        safe_tool_args["password"] = _mask_secret(safe_tool_args["password"])
        safe_tool_args["analytics_prompt"] = f"<redacted analytics prompt, {len(analytics_prompt)} chars>"
        safe_tool_args["system_prompt"] = f"<redacted system prompt, {len(data['system_prompt'])} chars>"
        logger.info("analytics_query: calling run_analytics_query_on_database … args=%s", safe_tool_args)

        result = await _mcp_session.call_tool(
            "run_analytics_query_on_database",
            arguments=tool_args,
            read_timeout_seconds=timedelta(seconds=600)
        )
        
        logger.info("analytics_query: tool returned %d part(s)", len(getattr(result, "content", []) or []))

        # --- Step 3: Process the response ---
        rows = []
        sql_query = None
        
        logger.info("analytics_query: processing %d content parts from MCP tool", len(result.content))
        
        for i, msg in enumerate(result.content):
            msg_text = getattr(msg, 'text', '')
            logger.info("analytics_query: processing message part %d", i)
            
            # The MCP server returns {"rows": rows, "sql": sql} as JSON
            try:
                response_data = json.loads(msg_text)
                if isinstance(response_data, dict) and 'rows' in response_data:
                    # This is the structured response from MCP server
                    rows = response_data.get('rows', [])
                    sql_query = response_data.get('sql', None)
                    logger.info("analytics_query: found structured response with %d rows and SQL: %s", 
                              len(rows) if isinstance(rows, list) else 0, 
                              "present" if sql_query else "missing")
                    break  # We found the main response, no need to process other parts
                else:
                    logger.debug("analytics_query: JSON found but not structured response format")
            except json.JSONDecodeError:
                # Not JSON, might be additional text from the AI
                logger.debug("analytics_query: message part %d is not JSON", i)

        logger.info("analytics_query: processing complete - %d rows, SQL: %s", 
                   len(rows), "found" if sql_query else "not found")

        # Return the results
        return JSONResponse({
            "status": "success",
            "data": {
                "rows": rows,
                "sql": sql_query
            }
        })
                
    except Exception as e:
        logger.error("analytics_query: error occurred: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Analytics query failed: {str(e)}"
            }
        )

# In-memory storage for connections (would be replaced with a persistent store)
saved_connections: List[Dict[str, Any]] = _load_saved_connections()
connection_id_counter = 1


