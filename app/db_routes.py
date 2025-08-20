import os
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# Create a router to organize database endpoints
router = APIRouter(prefix="/db", tags=["database"])
logger = logging.getLogger("uvicorn.error")

# Models for requests and responses
class ConnectionRequest(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str
    database_type: str
    name: Optional[str] = None

class TestConnectionResponse(BaseModel):
    success: bool
    message: str

class SavedConnectionResponse(BaseModel):
    id: str

# In-memory storage for connections (would be replaced with a persistent store)
connections_store: List[Dict[str, Any]] = []
connection_id_counter = 1

@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(connection: ConnectionRequest, request: Request):
    """
    Test a database connection using MCP tooling
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    try:
        logger.info(f"Testing connection to {connection.database_type} database at {connection.host}:{connection.port}")
        
        # Use different MCP tools based on database type
        if connection.database_type.lower() in ["postgres", "postgresql"]:
            tool_name = "list_database_tables"  # Use existing tool to test connection
        elif connection.database_type.lower() in ["mssql", "sql server"]:
            tool_name = "list_database_tables"  # Same tool works for both
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported database type: {connection.database_type}")
        
        # Call MCP tool to test the connection
        result = await _mcp_session.call_tool(
            tool_name,
            arguments={
                "host": connection.host,
                "port": connection.port,
                "user": connection.user,
                "password": connection.password,
                "database": connection.database,
                "database_type": connection.database_type
            }
        )
        
        # If we get here without an exception, the connection worked
        return TestConnectionResponse(
            success=True,
            message=f"Successfully connected to {connection.database} database"
        )
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return TestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )

@router.post("/save-connection", response_model=SavedConnectionResponse)
async def save_connection(connection: ConnectionRequest):
    """
    Save a database connection
    """
    global connection_id_counter
    
    # Generate a unique ID
    conn_id = str(connection_id_counter)
    connection_id_counter += 1
    
    # Create connection entry (without password for storage)
    connection_data = {
        "id": conn_id,
        "name": connection.name or f"Connection {conn_id}",
        "host": connection.host,
        "port": connection.port,
        "user": connection.user,
        "database": connection.database,
        "database_type": connection.database_type,
        # Store password securely in a real implementation
        "password": connection.password,  # For demonstration only
    }
    
    # Store the connection
    connections_store.append(connection_data)
    logger.info(f"Saved new connection with ID: {conn_id}")
    
    return SavedConnectionResponse(id=conn_id)

@router.get("/get-connections", response_model=List[Dict[str, Any]])
async def get_connections():
    """
    Retrieve saved database connections
    """
    return connections_store

# Export the router to be included in main app
