import logging
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

@router.post("/test-connection")
async def test_connection(request: Request):
    """
    Test a database connection
    """
    try:
        from app.client import _mcp_session  # Import here to avoid circular imports
        
        # Parse request body
        data = await request.json()
        required_fields = ["host", "port", "user", "password", "database", "database_type"]
        for field in required_fields:
            if field not in data:
                return JSONResponse({
                    "success": False,
                    "message": f"Missing required field: {field}"
                })
        
        # Extract connection details
        host = data["host"]
        port = int(data["port"])
        user = data["user"]
        password = data["password"]
        database = data["database"]
        db_type = data["database_type"]
        
        logger.info(f"Testing connection to {db_type} database at {host}:{port}")
        
        # Use list_database_tables tool to test the connection
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
        tables_text = result.content[0].text if result.content else "[]"
        tables = json.loads(tables_text)
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully connected to {database} database ({len(tables)} tables found)"
        })
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
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

# In-memory storage for connections (would be replaced with a persistent store)
saved_connections = []
connection_id_counter = 1
