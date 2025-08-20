import logging
import json
import traceback
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional

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
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONNECTIONS_FILE = DATA_DIR / "connections.json"

def _load_saved_connections() -> List[Dict[str, Any]]:
    try:
        if CONNECTIONS_FILE.exists():
            with CONNECTIONS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        logger.error("Failed to load connections.json", exc_info=True)
    return []

def _persist_saved_connections(conns: List[Dict[str, Any]]):
    try:
        with CONNECTIONS_FILE.open("w", encoding="utf-8") as f:
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
    Suggest columns based on natural language prompt
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()
        
        # Resolve from profile and require prompt
        data = _resolve_connection_payload(data, saved_connections)
        if not data.get("user_prompt"):
            return JSONResponse(status_code=400, content={"status":"error","error":"Missing required field: user_prompt"})
        
        logger.info(f"Suggesting columns for {data['database_type']} database based on user prompt")
        
        # Call MCP tool to suggest columns
        try:
            result = await _mcp_session.call_tool(
                "suggest_keys_for_analytics",
                arguments={
                    "host": data["host"],
                    "port": data["port"],
                    "user": data["user"],
                    "password": data["password"],
                    "database": data["database"],
                    "database_type": data.get("database_type","postgres"),
                    "user_prompt": data["user_prompt"],
                }
            )
            
            # Process the response
            parts = [msg.text for msg in result.content]
            columns_text = "".join(parts)
            
            # Parse the columns
            # Accept either JSON payload or newline text; prefer JSON of shape [{name,description,data_type}]
            columns: List[Dict[str, Any]] = []
            parsed = None
            try:
                parsed = json.loads(columns_text)
            except Exception:
                parsed = None
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                for item in parsed:
                    columns.append({
                        "name": item.get("name") or item.get("column") or "",
                        "description": item.get("description", ""),
                        "data_type": item.get("data_type") or item.get("type") or ""
                    })
            else:
                for line in columns_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split("-", 2)]
                    column = parts[0] if parts else ""
                    description = parts[1] if len(parts) > 1 else ""
                    data_type = parts[2] if len(parts) > 2 else ""
                    columns.append({"name": column, "description": description, "data_type": data_type})
            
            return JSONResponse({
                "status": "success",
                "data": {
                    "suggested_columns": columns,
                    "suggested_columns_map": {c["name"]: {"description": c["description"], "data_type": c["data_type"]} for c in columns}
                }
            })
                
        except Exception as tool_error:
            logger.error(f"Column suggestion tool error: {str(tool_error)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": f"Column suggestion failed: {str(tool_error)}"
                }
            )
            
    except Exception as e:
        logger.error(f"Column suggestion request failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Request processing failed: {str(e)}"
            }
        )

@router.post("/analytics-query")
async def analytics_query(request: Request):
    """
    Run an analytics query based on natural language
    """
    from app.client import _mcp_session, BI_SQL_GENERATION_PROMPT  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()
        
        # Resolve from profile and require analytics prompt
        data = _resolve_connection_payload(data, saved_connections)
        if not data.get("analytics_prompt"):
            return JSONResponse(status_code=400, content={"status":"error","error":"Missing required field: analytics_prompt"})
        
        logger.info(f"Running analytics query for {data['database_type']} database based on prompt")
        
        # Get system prompt or use default
        system_prompt = data.get("system_prompt", BI_SQL_GENERATION_PROMPT)
        
        # Call MCP tool to run analytics query
        try:
            result = await _mcp_session.call_tool(
                "run_analytics_query_on_database",
                arguments={
                    "host": data["host"],
                    "port": data["port"],
                    "user": data["user"],
                    "password": data["password"],
                    "database": data["database"],
            "database_type": data.get("database_type","postgres"),
                    "analytics_prompt": data["analytics_prompt"],
                    "system_prompt": system_prompt
                }
            )
            # Process the response
            rows: List[Dict[str, Any]] = []
            for msg in result.content:
                try:
                    rows_obj = json.loads(msg.text)
                    if isinstance(rows_obj, list):
                        rows.extend(rows_obj)
                    else:
                        rows.append(rows_obj)
                except Exception as parse_error:
                    logger.warning(f"Failed to parse analytics result chunk: {parse_error}")

            return JSONResponse({
                "status": "success",
                "data": {
                    "rows": rows
                }
            })

        except Exception as tool_error:
            logger.error(f"Analytics query tool error: {str(tool_error)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": f"Analytics query failed: {str(tool_error)}"
                }
            )
            
    except Exception as e:
        logger.error(f"Analytics query request failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Request processing failed: {str(e)}"
            }
        )

# In-memory storage for connections (would be replaced with a persistent store)
saved_connections: List[Dict[str, Any]] = _load_saved_connections()
connection_id_counter = 1


