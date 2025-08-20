import logging
import json
import traceback
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional

# Create router with tags for API documentation
router = APIRouter(tags=["database"])
logger = logging.getLogger("uvicorn.error")

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
            
        # Validate required fields
        required_fields = ["host", "port", "user", "password", "database", "database_type"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
        # Extract connection details
        host = data["host"]
        port = int(data["port"])
        user = data["user"]
        password = data["password"]
        database = data["database"]
        db_type = data["database_type"]
        
        logger.info(f"Testing connection to {db_type} database at {host}:{port}")
        
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
    return JSONResponse(saved_connections)

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
        
        # Validate required fields
        required_fields = ["host", "port", "user", "password", "database", "database_type"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
        logger.info(f"Listing tables for {data['database_type']} database")
        
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
            tables_text = result.content[0].text
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
        
        # Validate required fields
        required_fields = ["host", "port", "user", "password", "database", "database_type", "table"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
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
            columns_text = result.content[0].text
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
        
        # Validate required fields
        required_fields = ["host", "port", "user", "password", "database", "database_type", "user_prompt"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
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
                    "database_type": data["database_type"],
                    "user_prompt": data["user_prompt"],
                }
            )
            
            # Process the response
            parts = [msg.text for msg in result.content]
            columns_text = "".join(parts)
            
            # Parse the columns
            columns = []
            for line in columns_text.splitlines():
                line = line.strip()
                if line:
                    # Format can be "table.column - description - type" or simpler
                    parts = [p.strip() for p in line.split("-", 2)]
                    column = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else ""
                    data_type = parts[2].strip() if len(parts) > 2 else ""
                    
                    columns.append({
                        "name": column,
                        "description": description,
                        "data_type": data_type
                    })
            
            return JSONResponse({
                "status": "success",
                "data": {
                    "suggested_columns": columns
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
        
        # Validate required fields
        required_fields = ["host", "port", "user", "password", "database", "database_type", "analytics_prompt"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
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
                    "database_type": data["database_type"],
                    "analytics_prompt": data["analytics_prompt"],
                    "system_prompt": system_prompt
                }
            )
            
            # Process the response
            rows = []
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
saved_connections = []
connection_id_counter = 1


