import logging
import json
import traceback
import os
import time
import re
from pathlib import Path
from datetime import timedelta, datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.prompts import BI_ANALYTICS_PROMPT
from app.database import get_db_session
from app.models import DatabaseConnection as DBConnection, User
from app.routes.auth_routes import get_current_user

# Create router with tags for API documentation
router = APIRouter(tags=["database"])  # prefix inherited from app.include_router("/api")
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


def _load_saved_connections(user_id: int, db: Session) -> List[Dict[str, Any]]:
    connections = db.query(DBConnection).filter_by(user_id=user_id).all()
    conn_list = []
    for conn in connections:
        conn_list.append({
            "id": conn.id,
            "name": conn.name,  # Use 'name' field
            "host": conn.host,  # Use 'host' field
            "port": conn.port,  # Use 'port' field
            "user": conn.username,  # Use 'username' field
            "password": conn.encrypted_password,  # Use 'encrypted_password' field
            "database": conn.database,  # Use 'database' field
            "database_type": conn.database_type,  # Use 'database_type' field
        })
    return conn_list

def _persist_saved_connections(user_id: int, conn_data: Dict[str, Any], db: Session) -> int:
    # Basic password encoding (TODO: implement proper encryption in production)
    password = conn_data['password']
    # For now, just store as-is since the field is named encrypted_password
    # In production, you would use proper encryption here
    
    new_conn = DBConnection(
        user_id=user_id,
        name=conn_data['name'],  # Use 'name' not 'connection_name'
        database_type=conn_data['database_type'],  # Use 'database_type' not 'db_type'
        host=conn_data['host'],  # Use 'host' not 'db_host'
        port=conn_data['port'],  # Use 'port' not 'db_port'
        username=conn_data['user'],  # Use 'username' not 'db_user'
        encrypted_password=password,  # Store password (should be encrypted in production)
        database=conn_data['database']  # Use 'database' not 'db_name'
    )
    db.add(new_conn)
    db.commit()
    db.refresh(new_conn)
    return new_conn.id

@router.post("/test-connection")
async def test_connection(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Test a database connection with comprehensive logging and error handling
    
    Args:
        request (Request): HTTP request containing database connection parameters
        
    Returns:
        JSONResponse: Success/failure status with detailed connection information
        
    Logs:
        - INFO: Connection test initiation with masked credentials
        - DEBUG: Connection parameter validation and resolution
        - INFO: MCP tool execution details
        - WARNING: Connection issues or timeouts
        - ERROR: Connection failures with detailed error information
    """
    logger.info("POST /test-connection - Database connection test initiated")
    
    try:
        from app.client import _mcp_session  # Import here to avoid circular imports
        
        # Parse request body with validation
        try:
            data = await request.json()
            logger.debug("Request JSON parsed successfully")
        except Exception as e:
            logger.error(f"Failed to parse request JSON: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Invalid JSON in request: {str(e)}"
                }
            )
            
        logger.debug("Resolving connection parameters from saved profiles or direct input")
        
        # Allow referencing saved profile via connection_id/name
        saved_connections = _load_saved_connections(current_user.id, db)
        payload = _resolve_connection_payload(data, saved_connections)
        
        # Extract connection details with validation
        required_fields = ["host", "port", "user", "password", "database", "database_type"]
        for field in required_fields:
            if field not in payload:
                logger.warning(f"Missing required connection field: {field}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": f"Missing required field: {field}"
                    }
                )
        
        host = payload["host"]
        port = int(payload["port"])
        user = payload["user"]
        password = payload["password"]
        database = payload["database"]
        db_type = payload["database_type"]
        
        # Log connection attempt with masked password
        logger.info(
            f"Testing connection to {db_type} database: {host}:{port}/{database} as user '{user}'"
        )
        logger.debug(f"Password length: {len(password)} characters (masked for security)")
        
        # Use list_database_tables tool to test the connection
        try:
            logger.debug("Executing list_database_tables MCP tool for connection test")
            start_time = time.time()
            
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
            
            execution_time = time.time() - start_time
            logger.info(f"MCP tool executed successfully in {execution_time:.2f}s")
            
            # If we get here without an exception, the connection worked
            if result.content and len(result.content) > 0:
                tables_text = result.content[0].text
                tables = json.loads(tables_text)
                
                logger.info(f"Connection successful - found {len(tables)} tables in database '{database}'")
                logger.debug(f"Sample tables: {tables[:5] if len(tables) > 5 else tables}")
                
                # Track user activity for successful connection test
                try:
                    from app.models import UserActivity
                    user_activity = UserActivity(
                        user_id=current_user.id,
                        activity_type='database',
                        action='Database connection tested',
                        status='success',
                        ip_address=request.client.host if request.client else None,
                        timestamp=datetime.utcnow()
                    )
                    db.add(user_activity)
                    db.commit()
                    logger.debug("User activity tracked for connection test")
                except Exception as activity_error:
                    logger.warning(f"Failed to track user activity: {activity_error}")
                    # Don't fail the request if activity tracking fails
                
                return JSONResponse({
                    "success": True,
                    "message": f"Successfully connected to {database} database ({len(tables)} tables found)",
                    "execution_time": execution_time,
                    "table_count": len(tables)
                })
            else:
                logger.warning("Connection test returned no content - database may be empty")
                return JSONResponse({
                    "success": True,
                    "message": f"Connected to {database} database but no tables were found",
                    "execution_time": execution_time,
                    "table_count": 0
                })
                
        except Exception as tool_error:
            logger.error(f"MCP tool execution failed: {str(tool_error)}", exc_info=True)
            return JSONResponse({
                "success": False,
                "message": f"Database connection error: {str(tool_error)}"
            })
        
    except Exception as e:
        logger.error(f"Connection test failed with unexpected error: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "message": f"Connection failed: {str(e)}"
        })

@router.post("/save-connection")
async def save_connection(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Save a database connection configuration with comprehensive validation and logging
    
    Args:
        request (Request): HTTP request containing connection details to save
        
    Returns:
        JSONResponse: Success status with new connection ID
        
    Logs:
        - INFO: Save operation initiation
        - DEBUG: Field validation and processing
        - INFO: Successful save with connection details (masked)
        - WARNING: Missing required fields
        - ERROR: Save operation failures
        
    Note:
        In production, passwords should be encrypted before storage
    """
    logger.info("POST /save-connection - Saving new database connection configuration")
    
    try:
        data = await request.json()
        logger.debug("Connection data received, validating required fields")
        
        required_fields = ["host", "port", "user", "password", "database", "database_type", "name"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.warning(f"Missing required fields for connection save: {missing_fields}")
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        logger.debug("All required fields present, saving connection to DB")
        
        connection_id = _persist_saved_connections(current_user.id, data, db)
        
        logger.info(
            f"Successfully saved connection '{data['name']}' with ID {connection_id} for user {current_user.username}"
        )
        
        return JSONResponse({
            "id": str(connection_id),
            "success": True,
            "message": f"Connection '{data['name']}' saved successfully"
        })
    
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"Error saving connection: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-connection/{connection_id}")
async def delete_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Delete a saved connection by ID
    """
    try:
        conn = db.query(DBConnection).filter_by(id=connection_id, user_id=current_user.id).first()
        
        if conn:
            db.delete(conn)
            db.commit()
            logger.info(f"Deleted connection id={connection_id} for user {current_user.username}")
            return JSONResponse({
                "status": "success",
                "message": f"Connection {connection_id} deleted successfully"
            })
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Connection {connection_id} not found or you don't have permission to delete it"
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
async def get_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get all saved connections for the current user
    """
    saved_connections = _load_saved_connections(current_user.id, db)
    redacted = [
        {**c, "password": _mask_secret(c.get("password"))}
        for c in saved_connections
    ]
    logger.info(f"Returning {len(saved_connections)} saved connections for user {current_user.username}")
    return JSONResponse(redacted)

@router.get("/health")
async def api_health_check():
    """
    Simple health check endpoint to verify API is running
    """
    return JSONResponse({
        "status": "ok", 
        "service": "database-api"
    })

@router.post("/list-tables")
async def list_tables(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    List tables in the database
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()

        # Resolve from profile if needed
        saved_connections = _load_saved_connections(current_user.id, db)
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
async def describe_columns(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Describe columns in a table
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        # Parse request data
        data = await request.json()
        
        # Resolve from profile
        saved_connections = _load_saved_connections(current_user.id, db)
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

@router.post("/get-table-rows")
async def get_table_rows(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Return first N rows for a table. Mirrors logic of describe/list resolving saved profile."""
    from app.client import _mcp_session  # local import to avoid circular dependency
    try:
        data = await request.json()
        saved_connections = _load_saved_connections(current_user.id, db)
        data = _resolve_connection_payload(data, saved_connections)
        if "table" not in data:
            return JSONResponse(status_code=400, content={"status":"error","error":"Missing required field: table"})
        limit = int(data.get("limit", 100))
        logger.info(f"Fetching up to {limit} rows from table {data['table']} ({data['database_type']})")
        try:
            result = await _mcp_session.call_tool(
                "get_table_rows",  # expect MCP tool exposed
                arguments={
                    "host": data["host"],
                    "port": data["port"],
                    "user": data["user"],
                    "password": data["password"],
                    "database": data["database"],
                    "database_type": data["database_type"],
                    "table": data["table"],
                    "limit": limit
                }
            )
            rows_text = result.content[0].text if result.content else "{}"
            payload = json.loads(rows_text) if rows_text.strip() else {"rows": []}
            # Normalize
            columns = payload.get("columns")
            rows = payload.get("rows") or []
            if not columns and rows:
                # derive columns from first row
                first = rows[0]
                if isinstance(first, dict):
                    columns = list(first.keys())
            return JSONResponse({
                "status": "success",
                "data": {
                    "columns": columns or [],
                    "rows": rows,
                    "total_rows": payload.get("total_rows")
                }
            })
        except Exception as tool_error:
            logger.error(f"get_table_rows tool error: {tool_error}")
            return JSONResponse(status_code=500, content={"status":"error","error":f"Get rows failed: {tool_error}"})
    except Exception as e:
        logger.error(f"get_table_rows request failed: {e}")
        return JSONResponse(status_code=500, content={"status":"error","error":f"Request processing failed: {e}"})

@router.post("/suggest-columns")
async def suggest_columns(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Suggest columns based on natural language prompt with enhanced schema integration.
    
    3 MAIN STEPS:
    1. Fetch enhanced schema with descriptions and types from MCP
    2. Build prompt and call LLM for column suggestions  
    3. Parse LLM response and return selected columns with metadata
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    # --- Helper functions for safe logging ---
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
        saved_connections = _load_saved_connections(current_user.id, db)
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

        # ==========================================
        # STEP 1: FETCH ENHANCED SCHEMA FROM MCP
        # ==========================================
        logger.info("🔄 STEP 1: Fetching enhanced schema with confluence descriptions and types...")
        
        enhanced_args = {
            "space": data["confluenceSpace"],
            "title": data["confluenceTitle"],
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],
            "database": data["database"],
            "database_type": data.get("database_type", "postgres"),
        }
        
        safe_enhanced_args = dict(enhanced_args)
        safe_enhanced_args["password"] = _mask_secret(enhanced_args["password"])
        logger.info("suggest_columns: enhanced schema args (sanitized): %s", safe_enhanced_args)

        enhanced_res = await _mcp_session.call_tool(
            "get_enhanced_schema_with_confluence",
            arguments=enhanced_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts = getattr(enhanced_res, "content", []) or []
        logger.debug("suggest_columns: get_enhanced_schema_with_confluence returned %d content part(s)", len(parts))

        enhanced_text_parts = [m.text for m in parts if getattr(m, "text", None)]
        enhanced_text = enhanced_text_parts[0] if enhanced_text_parts else "{}"
        logger.debug("suggest_columns: enhanced schema JSON length=%d chars", len(enhanced_text))

        try:
            enhanced_schema = json.loads(enhanced_text)
            logger.info("✅ STEP 1 COMPLETE: Parsed enhanced schema with %d schema.table entries", len(enhanced_schema))
            
            # Log sample for debugging
            if enhanced_schema:
                sample_key = list(enhanced_schema.keys())[0]
                sample_columns = enhanced_schema[sample_key][:3]  # First 3 columns
                logger.debug("suggest_columns: sample enhanced schema entry '%s': %s", sample_key, sample_columns)
                
        except json.JSONDecodeError as je:
            logger.warning("suggest_columns: failed to parse enhanced schema JSON (%s), falling back to empty {}", je)
            enhanced_schema = {}

        # ==========================================
        # STEP 2: BUILD PROMPT AND CALL LLM  
        # ==========================================
        logger.info("🔄 STEP 2: Building enhanced user prompt and calling LLM...")
        
        # Convert enhanced schema to a format suitable for LLM
        formatted_schema_info = []
        for schema_table, columns in enhanced_schema.items():
            formatted_schema_info.append(f"\n{schema_table}:")
            for col in columns:
                col_name = col.get("name", "")
                col_desc = col.get("description", "No description")
                col_type = col.get("type", "UNKNOWN")
                formatted_schema_info.append(f"  - {col_name} ({col_type}): {col_desc}")
        
        schema_text = "\n".join(formatted_schema_info)
        
        augmented_user_prompt = (
            (data.get("user_prompt") or "").rstrip()
            + "\n\n---\n"
            + "AVAILABLE COLUMNS WITH DESCRIPTIONS AND TYPES:\n"
            + schema_text
            + "\n\nIMPORTANT: Select relevant columns from the list above. "
              "Return ONLY the column names in this exact format (one per line):\n\n"
              "table.column - schema\n\n"
              "Examples:\n"
              "sales.customer_id - public\n"
              "products.name - inventory\n"
              "orders.total_amount - sales\n\n"
              "STRICT REQUIREMENTS:\n"
              "- Use EXACTLY the format: table.column - schema\n"
              "- One column per line\n"
              "- No greetings, explanations, or additional text\n"
              "- No descriptions or comments\n"
              "- Just the column identifiers in the exact format shown"
        )
        
        logger.info(
            "suggest_columns: augmented_user_prompt built (length=%d chars, schema_entries=%d)",
            len(augmented_user_prompt), len(enhanced_schema)
        )
        logger.debug("suggest_columns: augmented_user_prompt (truncated): %s", _truncate(augmented_user_prompt))

        # Call the MCP tool for suggestions
        tool_args = {
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],
            "database": data["database"],
            "system_prompt": BI_ANALYTICS_PROMPT,
            "user_prompt": augmented_user_prompt,
        }
        safe_tool_args = dict(tool_args)
        safe_tool_args["password"] = _mask_secret(safe_tool_args["password"])
        safe_tool_args["user_prompt"] = f"<redacted user prompt, {len(augmented_user_prompt)} chars>"
        safe_tool_args["system_prompt"] = f"<BI_ANALYTICS_PROMPT, {len(BI_ANALYTICS_PROMPT)} chars>"
        logger.info("suggest_columns: calling suggest_keys_for_analytics ‡ args=%s", safe_tool_args)

        result = await _mcp_session.call_tool(
            "suggest_keys_for_analytics",
            arguments=tool_args,
            read_timeout_seconds=timedelta(seconds=600)
        )

        parts2 = getattr(result, "content", []) or []
        logger.debug("suggest_columns: suggest_keys_for_analytics returned %d content part(s)", len(parts2))

        full_text = "\n".join(m.text for m in parts2 if getattr(m, "text", None))
        logger.info("✅ STEP 2 COMPLETE: LLM returned response (%d chars)", len(full_text))
        logger.debug("suggest_columns: full LLM response:\n%s", full_text)

        # ==========================================
        # STEP 3: PARSE LLM RESPONSE AND RETURN  
        # ==========================================
        logger.info("🔄 STEP 3: Parsing LLM response and building final column list...")

        # Parse LLM response - expecting format "table.column - schema"
        raw_lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        logger.info("suggest_columns: extracted %d raw line(s) from LLM", len(raw_lines))
        logger.debug("suggest_columns: raw lines sample=%s", _sample_list(raw_lines))
        
        # Log each line for debugging
        for i, line in enumerate(raw_lines):
            logger.debug("suggest_columns: line %d: %r", i+1, line)

        # Process LLM selections and lookup details from enhanced schema
        columns: List[Dict[str, Any]] = []
        
        for line in raw_lines:
            logger.debug("suggest_columns: processing line: %s", line)
            
            try:
                # Parse the required format: "table.column - schema"
                if " - " not in line:
                    logger.warning("suggest_columns: skipping malformed line (no ' - '): %s", line)
                    continue
                    
                parts = line.split(" - ", 1)
                if len(parts) != 2:
                    logger.warning("suggest_columns: skipping malformed line (wrong parts): %s", line)
                    continue
                    
                table_column = parts[0].strip()
                suggested_schema = parts[1].strip()
                
                # Validate table.column format
                if "." not in table_column:
                    logger.warning("suggest_columns: skipping invalid table.column format: %s", table_column)
                    continue
                    
                logger.debug("suggest_columns: parsed line '%s' -> table_column='%s', schema='%s'", 
                           line, table_column, suggested_schema)
                
                # Look up this column in enhanced schema
                table_name = table_column.split(".", 1)[0]
                column_name = table_column.split(".", 1)[1]
                
                schema_table_key = f"{suggested_schema}.{table_name}"
                column_details = None
                
                # Find the column in enhanced schema
                if schema_table_key in enhanced_schema:
                    for col in enhanced_schema[schema_table_key]:
                        if col.get("name") == column_name:
                            column_details = col
                            break
                
                if not column_details:
                    logger.warning("suggest_columns: column %s not found in enhanced schema", table_column)
                    # Add with minimal info
                    columns.append({
                        "name": table_column,
                        "description": "Description not available",
                        "data_type": "UNKNOWN"
                    })
                    continue
                
                # Extract data from enhanced schema
                logger.debug("suggest_columns: found column_details for %s: %s", table_column, column_details)
                
                description = column_details.get("description", "Description not available")
                data_type = column_details.get("type", "UNKNOWN")
                
                logger.info("suggest_columns: extracted for %s - description='%s', type='%s'", 
                          table_column, description, data_type)
                
                # Create the response
                formatted_column = {
                    "name": table_column,
                    "description": description,
                    "data_type": data_type
                }
                
                columns.append(formatted_column)
                logger.debug("suggest_columns: added column: %s", formatted_column)
                
            except Exception as e:
                logger.error("suggest_columns: error processing line '%s': %s", line, e)
                continue

        logger.info("✅ STEP 3 COMPLETE: Successfully processed %d columns from LLM suggestions", len(columns))

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

        logger.info("🎉 suggest_columns: COMPLETE - returning %d columns to frontend", len(columns))
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
async def analytics_query(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Execute an analytics query with AI assistance and comprehensive logging
    
    This endpoint replicates the working analytics_query_api function from client.py
    with enhanced logging for debugging and monitoring
    
    Args:
        request (Request): HTTP request containing query parameters and connection info
        
    Returns:
        JSONResponse: Query results with SQL and row data
        
    Logs:
        - INFO: Query execution start with connection details
        - DEBUG: Confluence integration and prompt augmentation
        - INFO: MCP tool execution timing and results
        - WARNING: Missing required fields or invalid parameters
        - ERROR: Query execution failures with detailed stack traces
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    logger.info("POST /analytics-query - Analytics query execution initiated")
    
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
        logger.info("Analytics query request received, parsing payload")
        logger.debug(f"Request payload keys: {list(data.keys())}")
        
        # Resolve connection profile first
        saved_connections = _load_saved_connections(current_user.id, db)
        data = _resolve_connection_payload(data, saved_connections)
        
        logger.info(
            f"Analytics query - Connection: {data.get('database_type')} database '{data.get('database')}' "
            f"at {data.get('host')}:{data.get('port')} as user '{data.get('user')}'"
        )
        
        if data.get("confluenceSpace") and data.get("confluenceTitle"):
            logger.debug(
                f"Confluence integration enabled - Space: '{data.get('confluenceSpace')}', "
                f"Title: '{data.get('confluenceTitle')}'"
            )

        # Validate required fields
        required = ["host", "port", "user", "password", "database", "analytics_prompt", "system_prompt"]
        missing_fields = [field for field in required if field not in data or data[field] in (None, "")]
        
        if missing_fields:
            logger.warning(f"Missing required fields for analytics query: {missing_fields}")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "error": f"Missing required fields: {', '.join(missing_fields)}"}
            )

        log_copy = dict(data)
        log_copy["password"] = _mask_secret(log_copy.get("password"))
        log_copy["analytics_prompt"] = _truncate(log_copy.get("analytics_prompt"), 200)
        log_copy["system_prompt"] = _truncate(log_copy.get("system_prompt"), 100)
        logger.debug(f"Validated payload (sanitized): {log_copy}")

        # --- Step 1: (Optional) Get Confluence descriptions and augment prompt ---
        analytics_prompt = data["analytics_prompt"]
        space = data.get("confluenceSpace")
        title = data.get("confluenceTitle")
        
        if space and title:
            logger.info(f"Fetching Confluence descriptions from space '{space}', title '{title}'")
            desc_args = {
                "space": space,
                "title": title,
                "host": data["host"],
                "port": data["port"],
                "user": data["user"],
                "password": data["password"],
                "database": data["database"],
            }
            
            try:
                logger.debug("Executing collect_db_confluence_key_descriptions MCP tool")
                desc_start_time = time.time()
                
                desc_res = await _mcp_session.call_tool(
                    "collect_db_confluence_key_descriptions",
                    arguments=desc_args,
                    read_timeout_seconds=timedelta(seconds=600)
                )
                
                desc_execution_time = time.time() - desc_start_time
                logger.debug(f"Confluence descriptions fetched in {desc_execution_time:.2f}s")
                
                desc_text = next((m.text for m in (getattr(desc_res, "content", []) or []) if getattr(m, "text", None)), "{}")
                logger.debug(f"Descriptions JSON length: {len(desc_text)} characters")
                
                try:
                    key_desc = json.loads(desc_text)
                    logger.info(f"Successfully parsed {len(key_desc)} column descriptions from Confluence")
                    
                    # Augment analytics prompt with descriptions
                    original_length = len(analytics_prompt)
                    analytics_prompt = (
                        analytics_prompt.rstrip()
                        + "\n\n---\nKNOWN_COLUMN_DESCRIPTIONS_JSON:\n"
                        + json.dumps(key_desc, ensure_ascii=False)
                    )
                    logger.debug(
                        f"Analytics prompt augmented with descriptions: "
                        f"{original_length} -> {len(analytics_prompt)} characters"
                    )
                except json.JSONDecodeError:
                    logger.warning("Confluence descriptions not valid JSON; proceeding without augmentation")
                    
            except Exception as confluence_error:
                logger.warning(f"Failed to fetch Confluence descriptions: {str(confluence_error)}")
                logger.debug("Proceeding with analytics query without Confluence augmentation")

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
        safe_tool_args["analytics_prompt"] = f"<{len(analytics_prompt)} chars>"
        safe_tool_args["system_prompt"] = f"<{len(data['system_prompt'])} chars>"
        logger.info(f"Executing run_analytics_query_on_database MCP tool")
        logger.debug(f"Tool arguments (sanitized): {safe_tool_args}")

        query_start_time = time.time()
        
        result = await _mcp_session.call_tool(
            "run_analytics_query_on_database",
            arguments=tool_args,
            read_timeout_seconds=timedelta(seconds=600)
        )
        
        query_execution_time = time.time() - query_start_time
        logger.info(f"Analytics query executed successfully in {query_execution_time:.2f}s")
        logger.debug(f"MCP tool returned {len(getattr(result, 'content', []) or [])} content parts")

        # --- Step 3: Process the response ---
        rows = []
        sql_query = None
        
        logger.debug("Processing MCP tool response content")
        
        for i, msg in enumerate(result.content):
            msg_text = getattr(msg, 'text', '')
            logger.debug(f"Processing response part {i+1}/{len(result.content)} (length: {len(msg_text)})")
            
            # The MCP server returns {"rows": rows, "sql": sql} as JSON
            try:
                response_data = json.loads(msg_text)
                if isinstance(response_data, dict) and 'rows' in response_data:
                    # This is the structured response from MCP server
                    rows = response_data.get('rows', [])
                    sql_query = response_data.get('sql', None)
                    logger.info(
                        f"Parsed structured response: {len(rows) if isinstance(rows, list) else 0} rows, "
                        f"SQL query: {'present' if sql_query else 'missing'}"
                    )
                    if sql_query:
                        logger.debug(f"Generated SQL: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
                    break  # We found the main response, no need to process other parts
                else:
                    logger.debug(f"Response part {i+1} contains JSON but not in expected format")
            except json.JSONDecodeError:
                # Not JSON, might be additional text from the AI
                logger.debug(f"Response part {i+1} is not JSON (length: {len(msg_text)})")

        logger.info(f"Analytics query processing complete: {len(rows)} rows returned")
        if isinstance(rows, list) and len(rows) > 0:
            logger.debug(f"Sample result columns: {list(rows[0].keys()) if rows[0] else 'N/A'}")

        # Track user activity for successful analytics query
        try:
            from app.models import UserActivity
            user_activity = UserActivity(
                user_id=current_user.id,
                activity_type='bi',
                action='Analytics query generated',
                status='success',
                ip_address=request.client.host if request.client else None,
                timestamp=datetime.utcnow()
            )
            db.add(user_activity)
            db.commit()
            logger.debug("User activity tracked for analytics query")
        except Exception as activity_error:
            logger.warning(f"Failed to track user activity: {activity_error}")
            # Don't fail the request if activity tracking fails

        # Return the results
        return JSONResponse({
            "status": "success",
            "data": {
                "rows": rows,
                "sql": sql_query,
                "execution_time": query_execution_time,
                "row_count": len(rows) if isinstance(rows, list) else 0
            }
        })
                
    except Exception as e:
        logger.error(f"Analytics query failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Analytics query failed: {str(e)}"
            }
        )

# In-memory storage for connections (would be replaced with a persistent store)
# saved_connections: List[Dict[str, Any]] = _load_saved_connections()
connection_id_counter = 1

@router.post("/sync-all-tables")
async def sync_all_tables(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Sync all tables to Confluence by calling the existing sync_all_tables function
    from client.py through the MCP session
    """
    from app.client import _mcp_session  # Import here to avoid circular imports

@router.post("/sync-all-tables-with-progress")
async def sync_all_tables_with_progress(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Sync all tables to Confluence with detailed progress reporting.
    Returns intermediate progress updates instead of waiting for completion.
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    # --- Helper functions for safe logging ---
    def _mask_secret(s: str, show: int = 2) -> str:
        if s is None:
            return "None"
        s = str(s)
        return (s[:show] + "..." + s[-show:]) if len(s) > (show * 2) else "***"

    try:
        # Parse and validate request data
        data = await request.json()
        logger.info("sync_all_tables: received request with payload keys: %s", list(data.keys()))
        
        # Resolve connection profile first
        saved_connections = _load_saved_connections(current_user.id, db)
        data = _resolve_connection_payload(data, saved_connections)
        
        logger.info(
            "sync_all_tables: start space=%r title=%r host=%s port=%s db=%s user=%s limit=%s",
            data.get("space"), data.get("title"),
            data.get("host"), data.get("port"), data.get("database"), data.get("user"),
            data.get("limit")
        )

        # Validate required fields
        required = ["host", "port", "user", "password", "database", "database_type", "space", "title", "limit"]
        for field in required:
            if field not in data or data[field] in (None, ""):
                logger.error("sync_all_tables: missing field=%r", field)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": f"Missing required field: {field}"}
                )

        log_copy = dict(data)
        log_copy["password"] = _mask_secret(log_copy.get("password"))
        logger.debug("sync_all_tables: validated payload (sanitized): %s", log_copy)

        # Prepare the payload for the MCP sync function
        common_args = {
            "host": data["host"],
            "port": data["port"],
            "user": data["user"],
            "password": data["password"],
            "database": data["database"],
            "database_type": data["database_type"],
        }

        # --- Step 1: List tables ---
        logger.info("sync_all_tables: fetching list of tables")
        list_res = await _mcp_session.call_tool(
            "list_database_tables",
            arguments=common_args,
            read_timeout_seconds=timedelta(seconds=60),
        )
        tables = json.loads(list_res.content[0].text)
        logger.info("sync_all_tables: found %d tables: %s", len(tables), tables[:5])  # Log first 5 tables

        # --- Step 2: Fetch schema map ---
        logger.info("sync_all_tables: fetching database keys/schema")
        keys_res = await _mcp_session.call_tool(
            "list_database_keys",
            arguments=common_args,
            read_timeout_seconds=timedelta(seconds=60),
        )
        schema_map = json.loads(keys_res.content[0].text)
        logger.debug("sync_all_tables: schema map keys: %s", list(schema_map.keys())[:10])  # Log first 10 schema keys

        # --- Step 2.5: Ensure Confluence table exists before processing columns ---
        logger.info("🏗️ Ensuring Confluence table structure exists before processing columns")
        try:
            table_init_res = await _mcp_session.call_tool(
                "sync_confluence_table_delta",
                arguments={
                    "space": data["space"],
                    "title": data["title"],
                    "data": []  # Empty data to trigger table creation if needed
                },
                read_timeout_seconds=timedelta(seconds=60),
            )
            
            if table_init_res.content:
                table_init_info = json.loads(table_init_res.content[0].text)
                logger.info("✅ Table initialization result: %s", table_init_info.get("message", "Unknown"))
            else:
                logger.warning("⚠️ Table initialization returned no content")
                
        except Exception as table_init_error:
            logger.error("❌ Failed to initialize table structure: %s", table_init_error)
            # Continue anyway - the individual sync calls might still work

        # --- Step 3: Process each table ---
        results = []
        total_tables = len(tables)
        processed_tables = 0

        for tbl in tables:
            processed_tables += 1
            logger.info("sync_all_tables: processing table %d/%d: %s", processed_tables, total_tables, tbl)
            
            all_cols = schema_map.get(tbl, [])
            if not all_cols:
                logger.warning("sync_all_tables: no schema found for table %s", tbl)
                results.append({"table": tbl, "newColumns": [], "error": "no_schema"})
                continue

            # --- Step 3a: Compute delta (which columns are missing from Confluence) ---
            logger.debug("sync_all_tables: computing delta for table %s with %d columns", tbl, len(all_cols))
            logger.info("🔍 About to call get_table_delta_keys for table %s with columns: %s", tbl, [f"{tbl}.{c}" for c in all_cols][:5])
            
            try:
                delta_res = await _mcp_session.call_tool(
                    "get_table_delta_keys",
                    arguments={
                        "space": data["space"],
                        "title": data["title"],
                        "columns": [f"{tbl}.{c}" for c in all_cols]
                    },
                    read_timeout_seconds=timedelta(seconds=60),
                )
                delta_chunks = [msg.text for msg in delta_res.content]
                delta_text = "".join(delta_chunks)
                logger.info("📊 get_table_delta_keys returned: %s", delta_text[:500])
                logger.debug("sync_all_tables: delta JSON for %s: %s", tbl, delta_text[:200])
                
                try:
                    missing = json.loads(delta_text)
                    logger.info("✅ Successfully parsed delta JSON: %d missing columns", len(missing))
                except Exception as parse_e:
                    logger.error("❌ Failed to parse delta JSON for %s: %s. Raw response: %s", tbl, parse_e, delta_text[:300])
                    missing = []
                    
            except Exception as tool_e:
                logger.error("❌ get_table_delta_keys tool failed for %s: %s", tbl, tool_e, exc_info=True)
                missing = []

            if not missing:
                logger.info("sync_all_tables: no missing columns for table %s", tbl)
                results.append({"table": tbl, "newColumns": [], "error": None})
                continue

            logger.info("sync_all_tables: found %d missing columns for table %s", len(missing), tbl)

            # --- Step 3b: Describe only the missing columns ---
            logger.debug("sync_all_tables: describing missing columns for table %s", tbl)
            desc_res = await _mcp_session.call_tool(
                "describe_columns",
                arguments={
                    **common_args,
                    "table": tbl,
                    "columns": [c.split(".", 1)[1] for c in missing],
                    "limit": data["limit"],
                },
                read_timeout_seconds=None,
            )
            desc_chunks = [msg.text for msg in desc_res.content]
            desc_text = "".join(desc_chunks)
            logger.debug("sync_all_tables: description JSON for %s (length=%d)", tbl, len(desc_text))
            
            try:
                descriptions = json.loads(desc_text)
                logger.info("✅ Parsed descriptions JSON: %d entries", len(descriptions))
                if descriptions:
                    logger.debug("📋 Sample description entry: %s", descriptions[0])
            except Exception as e:
                logger.error("sync_all_tables: failed to parse descriptions JSON for %s: %s", tbl, e)
                descriptions = []

            # --- Step 3c: Sync delta descriptions to Confluence ---
            logger.info("🔗 About to sync %d descriptions to Confluence for table %s", len(descriptions), tbl)
            if not descriptions:
                logger.warning("⚠️  No descriptions to sync for table %s - this might prevent table creation!", tbl)
            
            logger.debug("sync_all_tables: syncing %d descriptions to Confluence for table %s", len(descriptions), tbl)
            sync_res = await _mcp_session.call_tool(
                "sync_confluence_table_delta",
                arguments={
                    "space": data["space"],
                    "title": data["title"],
                    "data": descriptions
                },
                read_timeout_seconds=timedelta(seconds=300),
            )
            
            logger.info("📊 sync_confluence_table_delta completed for table %s", tbl)
            logger.debug("📋 Raw sync response: %s", sync_res.content[0].text if sync_res.content else "No content")
            
            sync_info = {"delta": []}
            if sync_res.content:
                try:
                    sync_info = json.loads(sync_res.content[0].text)
                    logger.info("✅ Parsed sync response: %s", sync_info)
                except Exception as e:
                    logger.error("sync_all_tables: failed to parse sync JSON for %s: %s", tbl, e)

            synced_columns = sync_info.get("delta", [])
            logger.info("📈 sync_all_tables: synced %d columns for table %s", len(synced_columns), tbl)

            results.append({
                "table": tbl,
                "newColumns": synced_columns,
                "error": None
            })

        # --- Step 4: Generate summary ---
        total_synced_columns = sum(len(r["newColumns"]) for r in results)
        successful_tables = len([r for r in results if r["error"] is None])
        failed_tables = len([r for r in results if r["error"] is not None])

        logger.info(
            "sync_all_tables: completed - %d tables processed, %d successful, %d failed, %d total columns synced",
            total_tables, successful_tables, failed_tables, total_synced_columns
        )

        return JSONResponse({
            "status": "success",
            "data": {
                "results": results,
                "summary": {
                    "total_tables": total_tables,
                    "successful_tables": successful_tables,
                    "failed_tables": failed_tables,
                    "total_synced_columns": total_synced_columns
                }
            }
        })
                
    except Exception as e:
        logger.error("sync_all_tables: error occurred: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Table sync failed: {str(e)}"
            }
        )

@router.post("/sync-all-tables-with-progress-stream")
async def sync_all_tables_with_progress_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Sync all tables to Confluence with real-time progress streaming.
    Returns Server-Sent Events for real-time progress updates.
    """
    from app.client import _mcp_session
    import asyncio
    import time
    import json
    
    # --- Helper functions for safe logging ---
    def _mask_secret(s: str, show: int = 2) -> str:
        if s is None:
            return "None"
        s = str(s)
        return (s[:show] + "..." + s[-show:]) if len(s) > (show * 2) else "***"

    # Parse and validate request data OUTSIDE the generator
    try:
        data = await request.json()
        logger.info("sync_all_tables_with_progress_stream: received request")
        
        # Resolve connection profile first
        saved_connections = _load_saved_connections(current_user.id, db)
        data = _resolve_connection_payload(data, saved_connections)
        
        # Validate required fields
        required = ["host", "port", "user", "password", "database", "database_type", "space", "title", "limit"]
        for field in required:
            if field not in data or data[field] in (None, ""):
                logger.error("sync_all_tables_with_progress_stream: missing field=%r", field)
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": f"Missing required field: {field}"}
                )
    except Exception as e:
        logger.error("sync_all_tables_with_progress_stream: request parsing error: %s", str(e))
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": f"Invalid request: {str(e)}"}
        )

    async def generate_progress_stream():
        try:
            # Prepare common arguments
            common_args = {
                "host": data["host"],
                "port": data["port"],
                "user": data["user"],
                "password": data["password"],
                "database": data["database"],
                "database_type": data["database_type"],
            }

            # Send initial progress
            progress_data = {
                "status": "running",
                "stage": "initializing",
                "current_table": None,
                "current_table_index": 0,
                "total_tables": 0,
                "progress_percentage": 0,
                "stage_details": "Starting sync process...",
                "tables_processed": [],
                "tables_pending": [],
                "summary": {
                    "total_tables": 0,
                    "successful_tables": 0,
                    "failed_tables": 0,
                    "total_synced_columns": 0
                },
                "start_time": time.time()
            }
            yield f"data: {json.dumps(progress_data)}\n\n"

            # --- Stage 1: List tables (5% of progress) ---
            logger.info("sync_all_tables_with_progress_stream: Stage 1 - Listing tables")
            progress_data.update({
                "stage": "listing_tables",
                "progress_percentage": 5,
                "stage_details": "Fetching database tables..."
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            list_res = await _mcp_session.call_tool(
                "list_database_tables",
                arguments=common_args,
                read_timeout_seconds=timedelta(seconds=60),
            )
            tables = json.loads(list_res.content[0].text)
            logger.info("sync_all_tables_with_progress_stream: found %d tables", len(tables))
            
            progress_data.update({
                "total_tables": len(tables),
                "tables_pending": tables.copy(),
                "summary": {"total_tables": len(tables), "successful_tables": 0, "failed_tables": 0, "total_synced_columns": 0}
            })
            yield f"data: {json.dumps(progress_data)}\n\n"

            # --- Stage 2: Fetch schema map (10% of progress) ---
            logger.info("sync_all_tables_with_progress_stream: Stage 2 - Fetching schema")
            progress_data.update({
                "stage": "fetching_schema",
                "progress_percentage": 10,
                "stage_details": "Loading database schema and keys..."
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            keys_res = await _mcp_session.call_tool(
                "list_database_keys",
                arguments=common_args,
                read_timeout_seconds=timedelta(seconds=60),
            )
            schema_map = json.loads(keys_res.content[0].text)
            logger.info("sync_all_tables_with_progress_stream: loaded schema for %d tables", len(schema_map))

            # --- Stage 2.5: Ensure Confluence table exists (12% of progress) ---
            logger.info("sync_all_tables_with_progress_stream: Stage 2.5 - Ensuring table structure exists")
            progress_data.update({
                "stage": "initializing_table",
                "progress_percentage": 12,
                "stage_details": "Creating Confluence table structure if needed..."
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            try:
                table_init_res = await _mcp_session.call_tool(
                    "sync_confluence_table_delta",
                    arguments={
                        "space": data["space"],
                        "title": data["title"],
                        "data": []  # Empty data to trigger table creation if needed
                    },
                    read_timeout_seconds=timedelta(seconds=60),
                )
                
                if table_init_res.content:
                    table_init_info = json.loads(table_init_res.content[0].text)
                    logger.info("✅ Table initialization result: %s", table_init_info.get("message", "Unknown"))
                    progress_data["stage_details"] = f"Table structure ready: {table_init_info.get('message', 'Unknown status')}"
                else:
                    logger.warning("⚠️ Table initialization returned no content")
                    progress_data["stage_details"] = "Table structure status unknown"
                    
                yield f"data: {json.dumps(progress_data)}\n\n"
                    
            except Exception as table_init_error:
                logger.error("❌ Failed to initialize table structure: %s", table_init_error)
                progress_data["stage_details"] = f"Table initialization failed: {str(table_init_error)}"
                yield f"data: {json.dumps(progress_data)}\n\n"
                # Continue anyway - the individual sync calls might still work

            # --- Stage 3: Process each table (85% of progress, distributed among tables) ---
            results = []
            table_progress_increment = 85 / len(tables) if tables else 0
            
            for table_index, tbl in enumerate(tables):
                current_progress = 10 + (table_index * table_progress_increment)
                logger.info("sync_all_tables_with_progress_stream: processing table %d/%d: %s", table_index + 1, len(tables), tbl)
                
                # Update progress for current table
                progress_data.update({
                    "stage": "processing_table",
                    "current_table": tbl,
                    "current_table_index": table_index + 1,
                    "progress_percentage": int(current_progress),
                    "stage_details": f"Processing table '{tbl}' ({table_index + 1}/{len(tables)})",
                    "tables_pending": tables[table_index + 1:]
                })
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                all_cols = schema_map.get(tbl, [])
                if not all_cols:
                    logger.warning("sync_all_tables_with_progress_stream: no schema found for table %s", tbl)
                    result = {"table": tbl, "newColumns": [], "error": "no_schema", "stage": "completed"}
                    results.append(result)
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["failed_tables"] += 1
                    continue

                # Sub-stage 3a: Compute delta
                progress_data["stage_details"] = f"Computing delta for table '{tbl}' - checking {len(all_cols)} columns"
                yield f"data: {json.dumps(progress_data)}\n\n"
                logger.debug("sync_all_tables_with_progress_stream: computing delta for table %s", tbl)
                logger.info("🔍 About to call get_table_delta_keys for table %s with columns: %s", tbl, [f"{tbl}.{c}" for c in all_cols][:5])
                
                try:
                    delta_res = await _mcp_session.call_tool(
                        "get_table_delta_keys",
                        arguments={
                            "space": data["space"],
                            "title": data["title"],
                            "columns": [f"{tbl}.{c}" for c in all_cols]
                        },
                        read_timeout_seconds=timedelta(seconds=60),
                    )
                    delta_chunks = [msg.text for msg in delta_res.content]
                    delta_text = "".join(delta_chunks)
                    logger.info("📊 get_table_delta_keys returned: %s", delta_text[:500])
                    
                    try:
                        missing = json.loads(delta_text)
                        logger.info("✅ Successfully parsed delta JSON: %d missing columns", len(missing))
                    except Exception as parse_e:
                        logger.error("❌ Failed to parse delta JSON for %s: %s. Raw response: %s", tbl, parse_e, delta_text[:300])
                        missing = []
                        
                except Exception as tool_e:
                    logger.error("❌ get_table_delta_keys tool failed for %s: %s", tbl, tool_e, exc_info=True)
                    missing = []

                if not missing:
                    logger.info("sync_all_tables_with_progress_stream: no missing columns for table %s", tbl)
                    progress_data["stage_details"] = f"No new columns found for table '{tbl}' - already up to date"
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    result = {"table": tbl, "newColumns": [], "error": None, "stage": "completed"}
                    results.append(result)
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["successful_tables"] += 1
                    continue

                # Sub-stage 3b: Describe missing columns
                progress_data["stage_details"] = f"Found {len(missing)} missing columns for '{tbl}' - generating descriptions"
                yield f"data: {json.dumps(progress_data)}\n\n"
                logger.info("sync_all_tables_with_progress_stream: found %d missing columns for table %s", len(missing), tbl)
                
                desc_res = await _mcp_session.call_tool(
                    "describe_columns",
                    arguments={
                        **common_args,
                        "table": tbl,
                        "columns": [c.split(".", 1)[1] for c in missing],
                        "limit": data["limit"],
                    },
                    read_timeout_seconds=None,
                )
                desc_chunks = [msg.text for msg in desc_res.content]
                desc_text = "".join(desc_chunks)
                
                try:
                    descriptions = json.loads(desc_text)
                except Exception as e:
                    logger.error("sync_all_tables_with_progress_stream: failed to parse descriptions JSON for %s: %s", tbl, e)
                    descriptions = []

                # Sub-stage 3c: Sync to Confluence
                progress_data["stage_details"] = f"Syncing {len(descriptions)} descriptions to Confluence for table '{tbl}'"
                yield f"data: {json.dumps(progress_data)}\n\n"
                logger.debug("sync_all_tables_with_progress_stream: syncing descriptions to Confluence for table %s", tbl)
                
                sync_res = await _mcp_session.call_tool(
                    "sync_confluence_table_delta",
                    arguments={
                        "space": data["space"],
                        "title": data["title"],
                        "data": descriptions
                    },
                    read_timeout_seconds=timedelta(seconds=300),
                )
                
                sync_info = {"delta": []}
                if sync_res.content:
                    try:
                        sync_info = json.loads(sync_res.content[0].text)
                    except Exception as e:
                        logger.error("sync_all_tables_with_progress_stream: failed to parse sync JSON for %s: %s", tbl, e)

                synced_columns = sync_info.get("delta", [])
                logger.info("sync_all_tables_with_progress_stream: synced %d columns for table %s", len(synced_columns), tbl)

                # Update completion for this table
                progress_data["stage_details"] = f"Completed table '{tbl}' - synced {len(synced_columns)} new columns"
                yield f"data: {json.dumps(progress_data)}\n\n"

                result = {"table": tbl, "newColumns": synced_columns, "error": None, "stage": "completed"}
                results.append(result)
                progress_data["tables_processed"].append(result)
                progress_data["summary"]["successful_tables"] += 1
                progress_data["summary"]["total_synced_columns"] += len(synced_columns)

            # --- Stage 4: Finalization (100%) ---
            total_synced_columns = sum(len(r["newColumns"]) for r in results)
            successful_tables = len([r for r in results if r["error"] is None])
            failed_tables = len([r for r in results if r["error"] is not None])
            
            end_time = time.time()
            duration = end_time - progress_data["start_time"]

            final_progress = {
                "status": "completed",
                "stage": "completed",
                "current_table": None,
                "current_table_index": len(tables),
                "total_tables": len(tables),
                "progress_percentage": 100,
                "stage_details": f"Sync completed! Processed {len(tables)} tables in {duration:.1f}s",
                "tables_processed": progress_data["tables_processed"],
                "tables_pending": [],
                "summary": {
                    "total_tables": len(tables),
                    "successful_tables": successful_tables,
                    "failed_tables": failed_tables,
                    "total_synced_columns": total_synced_columns
                },
                "results": results,
                "start_time": progress_data["start_time"],
                "end_time": end_time,
                "duration": duration
            }

            yield f"data: {json.dumps(final_progress)}\n\n"
            yield f"data: [DONE]\n\n"

            logger.info(
                "sync_all_tables_with_progress_stream: completed - %d tables processed, %d successful, %d failed, %d total columns synced in %.1fs",
                len(tables), successful_tables, failed_tables, total_synced_columns, duration
            )
                    
        except Exception as e:
            logger.error("sync_all_tables_with_progress_stream: error occurred: %s", str(e), exc_info=True)
            error_data = {
                "status": "error",
                "error": f"Table sync failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_progress_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@router.get("/endpoints")
async def get_api_endpoints():
    """
    Get list of all available API endpoints for testing
    
    Returns:
        JSONResponse: Comprehensive list of API endpoints with metadata
        
    Logs:
        - INFO: Request received
        - DEBUG: Endpoint catalog generation
        - INFO: Response statistics
        - ERROR: Any failures during endpoint discovery
        
    Note:
        In a production environment, this could be generated dynamically
        from FastAPI's OpenAPI schema for automatic endpoint discovery
    """
    logger.info("GET /endpoints - Fetching list of all available API endpoints for testing")
    
    try:
        logger.debug("Generating comprehensive API endpoint catalog")
        
        # This endpoint returns a list of all available endpoints
        # In a real implementation, this could be generated from FastAPI's OpenAPI schema
        endpoints = [
            {
                "path": "/api/health",
                "method": "GET",
                "description": "Check API health status",
                "tags": ["system"]
            },
            {
                "path": "/api/test-connection",
                "method": "POST",
                "description": "Test database connection",
                "parameters": ["host", "port", "user", "password", "database", "database_type"],
                "tags": ["database"]
            },
            {
                "path": "/api/save-connection", 
                "method": "POST",
                "description": "Save a new database connection",
                "parameters": ["connection_name", "host", "port", "user", "password", "database", "database_type"],
                "tags": ["database"]
            },
            {
                "path": "/api/get-connections",
                "method": "GET", 
                "description": "Get all saved database connections",
                "tags": ["database"]
            },
            {
                "path": "/api/delete-connection/{connection_id}",
                "method": "DELETE",
                "description": "Delete a saved database connection",
                "parameters": ["connection_id"],
                "tags": ["database"]
            },
            {
                "path": "/api/list-tables",
                "method": "POST",
                "description": "List all tables in database",
                "parameters": ["host", "port", "user", "password", "database", "database_type"],
                "tags": ["database"]
            },
            {
                "path": "/api/describe-columns",
                "method": "POST", 
                "description": "Get AI descriptions of database columns",
                "parameters": ["host", "port", "user", "password", "database", "database_type", "table", "columns", "limit"],
                "tags": ["database", "ai"]
            },
            {
                "path": "/api/suggest-columns",
                "method": "POST",
                "description": "Get AI column suggestions for queries",
                "parameters": ["connection_name", "query"],
                "tags": ["database", "ai"]
            },
            {
                "path": "/api/analytics-query",
                "method": "POST",
                "description": "Execute analytics query with AI assistance",
                "parameters": ["connection_name", "query"],
                "tags": ["analytics"]
            },
            {
                "path": "/api/sync-all-tables",
                "method": "POST",
                "description": "Sync all database tables to Confluence",
                "parameters": ["connection_name", "space", "title", "limit"],
                "tags": ["sync"]
            },
            {
                "path": "/api/sync-all-tables-with-progress-stream",
                "method": "POST",
                "description": "Sync tables with real-time progress streaming",
                "parameters": ["connection_name", "space", "title", "limit"],
                "tags": ["sync"]
            }
        ]
        
        # Count endpoints by method and tag
        method_counts = {}
        tag_counts = {}
        for endpoint in endpoints:
            method = endpoint["method"]
            method_counts[method] = method_counts.get(method, 0) + 1
            for tag in endpoint["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        logger.info(f"Successfully generated {len(endpoints)} API endpoints")
        logger.debug(f"Endpoints by method: {method_counts}")
        logger.debug(f"Endpoints by tag: {tag_counts}")
        
        return JSONResponse({
            "status": "success",
            "data": endpoints
        })
        
    except Exception as e:
        logger.error(f"Failed to get API endpoints: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": f"Failed to get endpoints: {str(e)}"}
        )