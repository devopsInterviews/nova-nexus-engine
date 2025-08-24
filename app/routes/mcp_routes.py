"""
MCP (Model Context Protocol) Testing Routes

This module provides API endpoints for testing and interacting with MCP servers,
including tool discovery, execution, and server management. These routes are
separate from database operations to maintain clear separation of concerns.

Endpoints:
- GET /mcp/servers - List available MCP servers with real connection data
- GET /mcp/servers/{server_id}/tools - Get actual tools from connected MCP server
- POST /mcp/servers/{server_id}/tools/{tool_name}/execute - Execute MCP tools with real parameters
- GET /mcp/health - Check MCP server connection health
- GET /api/endpoints - Discover available FastAPI endpoints

Author: Nova Nexus Engine
Date: August 2025
"""

import logging
import json
import time
from datetime import timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

# Set up logging for this module
logger = logging.getLogger(__name__)

# Create router for MCP-related endpoints
router = APIRouter(prefix="/mcp", tags=["MCP Testing"])

@router.get("/servers")
async def get_mcp_servers():
    """
    Get list of available MCP servers with real connection information
    
    This endpoint connects to the actual MCP session and retrieves live server data
    instead of returning mock data. It provides real server capabilities and status.
    
    Returns:
        JSONResponse: List of connected MCP servers with their actual capabilities
        
    Logs:
        - INFO: Server discovery initiation and results
        - DEBUG: Detailed server capability information
        - WARNING: Connection issues or missing servers
        - ERROR: MCP session failures with stack traces
    """
    from app.client import _mcp_session  # Import here to avoid circular imports
    
    logger.info("GET /mcp/servers - Real MCP server discovery initiated")
    
    try:
        if not _mcp_session:
            logger.warning("MCP session not initialized - no servers available")
            return JSONResponse({
                "servers": [],
                "message": "MCP session not initialized",
                "status": "warning"
            })
        
        logger.debug("Retrieving server capabilities from active MCP session")
        
        # Get actual server information from the MCP session
        try:
            # List available tools to understand server capabilities
            logger.debug("Calling list_tools on MCP session")
            list_tools_start = time.time()
            
            tools_result = await _mcp_session.list_tools()
            
            list_tools_time = time.time() - list_tools_start
            logger.info(f"MCP list_tools completed in {list_tools_time:.2f}s")
            
            # Extract tool information
            tools = []
            if hasattr(tools_result, 'tools') and tools_result.tools:
                for tool in tools_result.tools:
                    tool_info = {
                        "name": getattr(tool, 'name', 'unknown'),
                        "description": getattr(tool, 'description', 'No description available'),
                        "input_schema": getattr(tool, 'inputSchema', {})
                    }
                    tools.append(tool_info)
                    logger.debug(f"Found tool: {tool_info['name']} - {tool_info['description'][:100]}...")
            
            logger.info(f"Successfully discovered {len(tools)} tools from MCP server")
            
            # Create server information based on actual connection
            server_info = {
                "id": "primary_mcp_server",
                "name": "Primary MCP Server", 
                "url": getattr(_mcp_session, '_url', 'Unknown URL'),
                "status": "connected",
                "tool_count": len(tools),
                "capabilities": {
                    "tools": True,
                    "resources": hasattr(_mcp_session, 'list_resources'),
                    "prompts": hasattr(_mcp_session, 'list_prompts')
                },
                "connection_time": list_tools_time,
                "last_checked": time.time()
            }
            
            logger.info(
                f"MCP server info: {server_info['name']} with {server_info['tool_count']} tools, "
                f"status: {server_info['status']}"
            )
            
            return JSONResponse({
                "servers": [server_info],
                "total_servers": 1,
                "status": "success",
                "timestamp": time.time()
            })
            
        except Exception as mcp_error:
            logger.error(f"Failed to communicate with MCP server: {str(mcp_error)}", exc_info=True)
            
            # Return server info with error status
            error_server_info = {
                "id": "primary_mcp_server",
                "name": "Primary MCP Server",
                "status": "error",
                "error": str(mcp_error),
                "tool_count": 0,
                "capabilities": {},
                "last_checked": time.time()
            }
            
            return JSONResponse({
                "servers": [error_server_info],
                "total_servers": 1,
                "status": "error",
                "message": f"MCP server communication failed: {str(mcp_error)}",
                "timestamp": time.time()
            })
            
    except Exception as e:
        logger.error(f"MCP server discovery failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Server discovery failed: {str(e)}",
                "servers": [],
                "timestamp": time.time()
            }
        )

@router.get("/servers/{server_id}/tools")
async def get_mcp_server_tools(server_id: str):
    """
    Get real tools from the connected MCP server
    
    This endpoint retrieves actual tool definitions from the MCP server,
    including their names, descriptions, and input schemas for parameter validation.
    
    Args:
        server_id (str): ID of the MCP server (currently supports 'primary_mcp_server')
        
    Returns:
        JSONResponse: List of actual tools with their schemas and descriptions
        
    Logs:
        - INFO: Tool discovery process and results
        - DEBUG: Individual tool details and schema information
        - WARNING: Server not found or tool discovery issues
        - ERROR: MCP communication failures with detailed traces
    """
    from app.client import _mcp_session
    
    logger.info(f"GET /mcp/servers/{server_id}/tools - Real tool discovery initiated")
    
    try:
        if not _mcp_session:
            logger.warning(f"MCP session not available for server {server_id}")
            raise HTTPException(status_code=503, detail="MCP session not initialized")
        
        if server_id != "primary_mcp_server":
            logger.warning(f"Unknown server ID requested: {server_id}")
            raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
        
        logger.debug("Fetching real tools from MCP server")
        tools_start_time = time.time()
        
        # Get actual tools from MCP server
        tools_result = await _mcp_session.list_tools()
        
        tools_fetch_time = time.time() - tools_start_time
        logger.info(f"MCP tools fetched in {tools_fetch_time:.2f}s")
        
        # Process real tool data
        tools = []
        if hasattr(tools_result, 'tools') and tools_result.tools:
            for tool in tools_result.tools:
                # Extract real tool information
                tool_name = getattr(tool, 'name', 'unknown_tool')
                tool_description = getattr(tool, 'description', 'No description available')
                tool_schema = getattr(tool, 'inputSchema', {})
                
                logger.debug(f"Processing tool: {tool_name}")
                logger.debug(f"Tool description: {tool_description[:200]}...")
                
                # Extract parameters from schema
                parameters = []
                if isinstance(tool_schema, dict) and 'properties' in tool_schema:
                    required_params = tool_schema.get('required', [])
                    
                    for param_name, param_def in tool_schema['properties'].items():
                        parameter_info = {
                            "name": param_name,
                            "type": param_def.get('type', 'string'),
                            "description": param_def.get('description', f'Parameter {param_name}'),
                            "required": param_name in required_params,
                            "default": param_def.get('default', ''),
                            "enum": param_def.get('enum', [])
                        }
                        parameters.append(parameter_info)
                        logger.debug(f"  Parameter: {param_name} ({parameter_info['type']}) - Required: {parameter_info['required']}")
                
                tool_info = {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": parameters,
                    "parameter_count": len(parameters),
                    "required_params": len([p for p in parameters if p['required']]),
                    "schema": tool_schema  # Include full schema for advanced usage
                }
                
                tools.append(tool_info)
                
            logger.info(f"Successfully processed {len(tools)} real tools from MCP server")
            
            # Log summary of tools found
            for tool in tools:
                logger.info(
                    f"Tool '{tool['name']}': {tool['parameter_count']} params "
                    f"({tool['required_params']} required)"
                )
        else:
            logger.warning("No tools found in MCP server response")
            
        return JSONResponse({
            "server_id": server_id,
            "tools": tools,
            "total_tools": len(tools),
            "fetch_time": tools_fetch_time,
            "status": "success",
            "timestamp": time.time()
        })
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to get tools for server {server_id}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Failed to get tools: {str(e)}",
                "server_id": server_id,
                "tools": [],
                "timestamp": time.time()
            }
        )

@router.post("/servers/{server_id}/tools/{tool_name}/execute")
async def execute_mcp_tool(server_id: str, tool_name: str, request: Request):
    """
    Execute a real MCP tool with provided parameters
    
    This endpoint executes actual MCP tools on the connected server with the
    provided parameters, returning real results from the tool execution.
    
    Args:
        server_id (str): ID of the MCP server
        tool_name (str): Name of the tool to execute
        request (Request): HTTP request containing tool parameters
        
    Returns:
        JSONResponse: Real execution results from the MCP tool
        
    Logs:
        - INFO: Tool execution start, parameters, and completion timing
        - DEBUG: Detailed parameter processing and result parsing
        - WARNING: Invalid parameters or tool not found
        - ERROR: Execution failures with full error context
    """
    from app.client import _mcp_session
    
    logger.info(f"POST /mcp/servers/{server_id}/tools/{tool_name}/execute - Real tool execution initiated")
    
    try:
        if not _mcp_session:
            logger.warning(f"MCP session not available for tool execution: {tool_name}")
            raise HTTPException(status_code=503, detail="MCP session not initialized")
        
        if server_id != "primary_mcp_server":
            logger.warning(f"Unknown server ID for tool execution: {server_id}")
            raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
        
        # Parse execution parameters
        try:
            data = await request.json()
            parameters = data.get('parameters', {})
            logger.info(f"Executing tool '{tool_name}' with {len(parameters)} parameters")
            logger.debug(f"Tool parameters: {list(parameters.keys())}")
            
            # Log parameter values (safely)
            for param_name, param_value in parameters.items():
                if 'password' in param_name.lower():
                    logger.debug(f"  {param_name}: [MASKED]")
                else:
                    value_str = str(param_value)[:100] + "..." if len(str(param_value)) > 100 else str(param_value)
                    logger.debug(f"  {param_name}: {value_str}")
                    
        except Exception as parse_error:
            logger.error(f"Failed to parse tool execution parameters: {str(parse_error)}")
            raise HTTPException(status_code=400, detail="Invalid JSON parameters")
        
        # Execute the real MCP tool
        logger.info(f"Calling MCP tool '{tool_name}' on server")
        execution_start_time = time.time()
        
        try:
            # Execute the actual tool
            result = await _mcp_session.call_tool(
                tool_name,
                arguments=parameters,
                read_timeout_seconds=timedelta(seconds=600)
            )
            
            execution_time = time.time() - execution_start_time
            logger.info(f"Tool '{tool_name}' executed successfully in {execution_time:.2f}s")
            
            # Process real results
            result_content = []
            if hasattr(result, 'content') and result.content:
                for i, content_item in enumerate(result.content):
                    if hasattr(content_item, 'text'):
                        content_text = content_item.text
                        logger.debug(f"Result content part {i+1}: {len(content_text)} characters")
                        
                        # Try to parse as JSON for structured data
                        try:
                            parsed_content = json.loads(content_text)
                            result_content.append({
                                "type": "json",
                                "data": parsed_content,
                                "raw": content_text
                            })
                            logger.debug(f"Parsed JSON result part {i+1}")
                        except json.JSONDecodeError:
                            result_content.append({
                                "type": "text", 
                                "data": content_text,
                                "raw": content_text
                            })
                            logger.debug(f"Raw text result part {i+1}")
                    elif hasattr(content_item, 'image'):
                        logger.debug(f"Result contains image data in part {i+1}")
                        result_content.append({
                            "type": "image",
                            "data": "Image data present",
                            "raw": "Binary image data"
                        })
                        
            logger.info(f"Tool execution complete: {len(result_content)} result parts")
            
            # Return real execution results
            return JSONResponse({
                "status": "success",
                "server_id": server_id,
                "tool_name": tool_name,
                "execution_time": execution_time,
                "result": {
                    "content": result_content,
                    "content_count": len(result_content),
                    "is_error": getattr(result, 'isError', False)
                },
                "parameters_used": parameters,
                "timestamp": time.time()
            })
            
        except Exception as tool_error:
            execution_time = time.time() - execution_start_time
            logger.error(
                f"MCP tool '{tool_name}' execution failed after {execution_time:.2f}s: {str(tool_error)}", 
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "execution_time": execution_time,
                    "error": str(tool_error),
                    "parameters_used": parameters,
                    "timestamp": time.time()
                }
            )
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Tool execution setup failed for {tool_name}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Tool execution failed: {str(e)}",
                "server_id": server_id,
                "tool_name": tool_name,
                "timestamp": time.time()
            }
        )

@router.get("/health")
async def mcp_health_check():
    """
    Check the health and connectivity of the MCP server
    
    This endpoint performs a real health check by attempting to communicate
    with the MCP server and verifying its responsiveness.
    
    Returns:
        JSONResponse: Health status with connection details and latency
        
    Logs:
        - INFO: Health check initiation and results
        - DEBUG: Detailed connectivity information
        - WARNING: Degraded performance or partial connectivity
        - ERROR: Complete connectivity failures
    """
    from app.client import _mcp_session
    
    logger.info("GET /mcp/health - MCP server health check initiated")
    
    try:
        if not _mcp_session:
            logger.warning("MCP session not initialized for health check")
            return JSONResponse({
                "status": "unhealthy",
                "message": "MCP session not initialized",
                "connected": False,
                "timestamp": time.time()
            })
        
        # Perform actual health check by listing tools (lightweight operation)
        logger.debug("Performing real connectivity test via list_tools")
        health_start_time = time.time()
        
        try:
            tools_result = await _mcp_session.list_tools()
            health_check_time = time.time() - health_start_time
            
            tool_count = len(getattr(tools_result, 'tools', []))
            
            logger.info(f"MCP health check successful: {tool_count} tools available, latency: {health_check_time:.3f}s")
            
            # Determine health status based on response time
            if health_check_time < 1.0:
                health_status = "healthy"
            elif health_check_time < 5.0:
                health_status = "slow"
                logger.warning(f"MCP server responding slowly: {health_check_time:.3f}s")
            else:
                health_status = "degraded"
                logger.warning(f"MCP server severely degraded: {health_check_time:.3f}s")
            
            return JSONResponse({
                "status": health_status,
                "connected": True,
                "response_time": health_check_time,
                "tool_count": tool_count,
                "session_active": True,
                "message": f"MCP server responding in {health_check_time:.3f}s",
                "timestamp": time.time()
            })
            
        except Exception as connectivity_error:
            health_check_time = time.time() - health_start_time
            logger.error(f"MCP connectivity test failed after {health_check_time:.3f}s: {str(connectivity_error)}")
            
            return JSONResponse({
                "status": "unhealthy",
                "connected": False,
                "response_time": health_check_time,
                "error": str(connectivity_error),
                "session_active": _mcp_session is not None,
                "message": "MCP server not responding",
                "timestamp": time.time()
            })
            
    except Exception as e:
        logger.error(f"MCP health check failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Health check failed: {str(e)}",
                "connected": False,
                "timestamp": time.time()
            }
        )

# API Endpoint Discovery (moved from db_routes.py)
@router.get("/all-endpoints", tags=["API Discovery"])
async def get_api_endpoints(request: Request):
    """
    Discover all available FastAPI endpoints with real route information
    
    This endpoint introspects the FastAPI application to provide real-time
    information about all available routes, their methods, and parameters.
    
    Returns:
        JSONResponse: Complete list of available API endpoints with metadata
        
    Logs:
        - INFO: Endpoint discovery process and results
        - DEBUG: Individual route details and parameter information
    """
    logger.info("GET /api/all-endpoints - API endpoint discovery initiated")
    
    try:
        from app.client import app  # Get the FastAPI app instance
        
        logger.debug("Introspecting FastAPI application routes")
        discovery_start_time = time.time()
        
        endpoints = []
        route_count = 0
        
        # Get real routes from FastAPI app
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                route_count += 1
                
                # Extract real route information
                methods = [method for method in route.methods if method != 'HEAD']
                path = route.path
                name = getattr(route, 'name', 'unnamed_route')
                
                # Skip SPA routes, static files, and internal routes
                if path in ['/', '/{full_path:path}'] or path.startswith('/static') or 'openapi' in path.lower() or path in ['/docs', '/redoc']:
                    continue
                
                # Get route tags if available
                tags = []
                if hasattr(route, 'endpoint') and hasattr(route.endpoint, '__wrapped__'):
                    # Try to get tags from route operation
                    operation = getattr(route, 'dependant', None)
                    if operation and hasattr(operation, 'call'):
                        tags = getattr(operation.call, '__tags__', [])
                
                logger.debug(f"Found route: {methods} {path} (name: {name})")
                
                # Create separate endpoint for each HTTP method to match frontend expectations
                for method in methods:
                    endpoint_info = {
                        "path": path,
                        "method": method,  # Single method instead of array
                        "name": name,
                        "tags": tags if tags else ["untagged"],
                        "summary": getattr(route, 'summary', ''),
                        "description": getattr(route, 'description', ''),
                        "parameters": []  # Add empty parameters list for frontend compatibility
                    }
                    
                    endpoints.append(endpoint_info)
        
        discovery_time = time.time() - discovery_start_time
        logger.info(f"API discovery complete: {len(endpoints)} endpoints found in {discovery_time:.3f}s")
        
        # Group endpoints by tag for better organization
        grouped_endpoints = {}
        for endpoint in endpoints:
            for tag in endpoint['tags']:
                if tag not in grouped_endpoints:
                    grouped_endpoints[tag] = []
                grouped_endpoints[tag].append(endpoint)
        
        logger.debug(f"Endpoints grouped into {len(grouped_endpoints)} categories")
        
        return JSONResponse({
            "endpoints": endpoints,
            "grouped_endpoints": grouped_endpoints,
            "total_endpoints": len(endpoints),
            "total_routes": route_count,
            "discovery_time": discovery_time,
            "categories": list(grouped_endpoints.keys()),
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"API endpoint discovery failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": f"Endpoint discovery failed: {str(e)}",
                "endpoints": [],
                "timestamp": time.time()
            }
        )
