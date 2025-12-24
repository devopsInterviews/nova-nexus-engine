"""
Research API Routes for IDA MCP Connection Management.

This module provides endpoints for managing IDA MCP connections,
allowing users to register their workstations and deploy MCP server pods.

Endpoints:
- GET  /research/mcp/versions      - Get allowed MCP server versions
- GET  /research/ida-bridge        - Get current user's IDA bridge config
- POST /research/ida-bridge        - Create/update user's IDA bridge config
- POST /research/ida-bridge/deploy - Deploy user's MCP server (placeholder)
- POST /research/ida-bridge/undeploy - Undeploy user's MCP server (placeholder)
- GET  /research/ida-bridge/status - Get deployment status
"""

import os
import re
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import User, IdaMcpConnection, IdaMcpDeployAudit, IdaMcpConnectionStatus
from app.routes.auth_routes import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/research", tags=["Research"])

# ============================================================
# Configuration
# ============================================================

# Allowed MCP server versions/image tags
ALLOWED_MCP_VERSIONS = os.getenv(
    "ALLOWED_MCP_VERSIONS", 
    "v1.0.0,v1.1.0,v1.2.0,latest"
).split(",")

# Allowed hostname domain patterns (regex)
ALLOWED_HOSTNAME_PATTERNS = os.getenv(
    "ALLOWED_HOSTNAME_PATTERNS",
    r".*\.corp\.example\.com$,.*\.internal$,localhost"
).split(",")

# Allowed IDA port range
IDA_PORT_MIN = int(os.getenv("IDA_PORT_MIN", "1024"))
IDA_PORT_MAX = int(os.getenv("IDA_PORT_MAX", "65535"))

# Proxy port allocation range
PROXY_PORT_MIN = int(os.getenv("PROXY_PORT_MIN", "9001"))
PROXY_PORT_MAX = int(os.getenv("PROXY_PORT_MAX", "9999"))


# ============================================================
# Pydantic Models
# ============================================================

class McpVersionsResponse(BaseModel):
    """Response model for MCP versions list."""
    versions: List[str]
    default_version: str


class IdaBridgeConfigRequest(BaseModel):
    """Request model for creating/updating IDA bridge configuration."""
    hostname_fqdn: str = Field(
        ..., 
        min_length=1, 
        max_length=255,
        description="Workstation FQDN (e.g., mypc.corp.example.com)"
    )
    ida_port: int = Field(
        ..., 
        ge=1024, 
        le=65535,
        description="IDA plugin listening port (e.g., 9100, 13337)"
    )
    mcp_version: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="MCP server version/image tag to deploy"
    )
    
    @validator('hostname_fqdn')
    def validate_hostname(cls, v):
        """Validate hostname against allowed domain patterns."""
        v = v.strip().lower()
        
        # Check if hostname matches any allowed pattern
        for pattern in ALLOWED_HOSTNAME_PATTERNS:
            pattern = pattern.strip()
            if pattern and re.match(pattern, v, re.IGNORECASE):
                return v
        
        # If ALLOWED_HOSTNAME_PATTERNS is empty or only contains empty strings, allow all
        non_empty_patterns = [p.strip() for p in ALLOWED_HOSTNAME_PATTERNS if p.strip()]
        if not non_empty_patterns:
            return v
            
        raise ValueError(
            f"Hostname '{v}' does not match allowed domain patterns. "
            f"Allowed patterns: {', '.join(non_empty_patterns)}"
        )
    
    @validator('ida_port')
    def validate_ida_port(cls, v):
        """Validate IDA port is within allowed range."""
        if v < IDA_PORT_MIN or v > IDA_PORT_MAX:
            raise ValueError(
                f"IDA port must be between {IDA_PORT_MIN} and {IDA_PORT_MAX}"
            )
        return v
    
    @validator('mcp_version')
    def validate_mcp_version(cls, v):
        """Validate MCP version is in allowed list."""
        v = v.strip()
        if v not in ALLOWED_MCP_VERSIONS:
            raise ValueError(
                f"MCP version '{v}' is not allowed. "
                f"Allowed versions: {', '.join(ALLOWED_MCP_VERSIONS)}"
            )
        return v


class IdaBridgeConfigResponse(BaseModel):
    """Response model for IDA bridge configuration."""
    id: int
    user_id: int
    hostname_fqdn: str
    ida_port: int
    proxy_port: Optional[int]
    mcp_version: str
    mcp_endpoint_url: Optional[str]
    status: str
    last_error: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    last_deploy_at: Optional[str]
    last_healthcheck_at: Optional[str]
    
    class Config:
        from_attributes = True


class IdaBridgeStatusResponse(BaseModel):
    """Response model for deployment status."""
    status: str
    proxy_port: Optional[int]
    mcp_endpoint_url: Optional[str]
    last_error: Optional[str]
    last_deploy_at: Optional[str]
    last_healthcheck_at: Optional[str]
    is_deployed: bool
    message: str


class DeployResponse(BaseModel):
    """Response model for deploy/undeploy actions."""
    success: bool
    message: str
    status: str
    proxy_port: Optional[int]
    mcp_endpoint_url: Optional[str]


# ============================================================
# Helper Functions
# ============================================================

def allocate_proxy_port(db: Session) -> int:
    """
    Allocate the next available proxy port from the configured range.
    
    Uses database to find the lowest unallocated port in the range.
    Thread-safe via database unique constraint on proxy_port.
    
    Args:
        db: Database session
        
    Returns:
        int: Allocated proxy port number
        
    Raises:
        HTTPException: If no ports are available in the range
    """
    # Get all currently allocated ports
    allocated_ports = db.query(IdaMcpConnection.proxy_port).filter(
        IdaMcpConnection.proxy_port.isnot(None)
    ).all()
    allocated_set = {p[0] for p in allocated_ports}
    
    # Find the first available port in range
    for port in range(PROXY_PORT_MIN, PROXY_PORT_MAX + 1):
        if port not in allocated_set:
            return port
    
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"No proxy ports available in range {PROXY_PORT_MIN}-{PROXY_PORT_MAX}"
    )


def log_audit_action(
    db: Session,
    user_id: int,
    action: str,
    payload: dict = None,
    result: dict = None,
    action_status: str = "success",
    error_message: str = None
):
    """Log an audit record for IDA MCP deployment actions."""
    audit = IdaMcpDeployAudit(
        user_id=user_id,
        action=action,
        payload=payload,
        result=result,
        status=action_status,
        error_message=error_message
    )
    db.add(audit)
    db.commit()


# ============================================================
# API Endpoints
# ============================================================

@router.get("/mcp/versions", response_model=McpVersionsResponse)
async def get_mcp_versions(current_user: User = Depends(get_current_user)):
    """
    Get list of allowed MCP server versions.
    
    Returns the list of MCP server image tags that users can select
    when configuring their IDA bridge connection.
    """
    return McpVersionsResponse(
        versions=ALLOWED_MCP_VERSIONS,
        default_version=ALLOWED_MCP_VERSIONS[-1] if ALLOWED_MCP_VERSIONS else "latest"
    )


@router.get("/ida-bridge", response_model=Optional[IdaBridgeConfigResponse])
async def get_ida_bridge_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get the current user's IDA bridge configuration.
    
    Returns the saved configuration including hostname, port, MCP version,
    deployment status, and generated MCP URL if deployed.
    """
    connection = db.query(IdaMcpConnection).filter(
        IdaMcpConnection.user_id == current_user.id
    ).first()
    
    if not connection:
        return None
    
    return IdaBridgeConfigResponse(**connection.to_dict())


@router.post("/ida-bridge", response_model=IdaBridgeConfigResponse)
async def upsert_ida_bridge_config(
    config: IdaBridgeConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Create or update the user's IDA bridge configuration.
    
    If a configuration already exists for the user, it will be updated.
    If no configuration exists, a new one will be created.
    
    Note: This endpoint only saves the configuration. To actually deploy
    the MCP server pod, use the /ida-bridge/deploy endpoint.
    """
    logger.info(f"User {current_user.id} ({current_user.username}) upserting IDA bridge config: "
                f"hostname={config.hostname_fqdn}, port={config.ida_port}, version={config.mcp_version}")
    
    # Check if configuration already exists
    connection = db.query(IdaMcpConnection).filter(
        IdaMcpConnection.user_id == current_user.id
    ).first()
    
    if connection:
        # Update existing configuration
        connection.hostname_fqdn = config.hostname_fqdn
        connection.ida_port = config.ida_port
        connection.mcp_version = config.mcp_version
        connection.updated_at = datetime.utcnow()
        
        # If deployed, mark as needing re-deploy (status stays same for now)
        # The actual re-deploy happens when user clicks Deploy
        
        log_audit_action(
            db, current_user.id, "update_config",
            payload=config.dict(),
            result={"message": "Configuration updated"},
            action_status="success"
        )
        
        logger.info(f"Updated IDA bridge config for user {current_user.id}")
    else:
        # Create new configuration
        connection = IdaMcpConnection(
            user_id=current_user.id,
            hostname_fqdn=config.hostname_fqdn,
            ida_port=config.ida_port,
            mcp_version=config.mcp_version,
            status=IdaMcpConnectionStatus.NEW.value
        )
        db.add(connection)
        
        log_audit_action(
            db, current_user.id, "create_config",
            payload=config.dict(),
            result={"message": "Configuration created"},
            action_status="success"
        )
        
        logger.info(f"Created new IDA bridge config for user {current_user.id}")
    
    db.commit()
    db.refresh(connection)
    
    return IdaBridgeConfigResponse(**connection.to_dict())


@router.post("/ida-bridge/deploy", response_model=DeployResponse)
async def deploy_ida_bridge(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Deploy the user's MCP server pod.
    
    This endpoint:
    1. Allocates a proxy port if not already allocated
    2. Creates/updates the per-user MCP server Kubernetes resources
    3. Updates the proxy routing configuration
    4. Returns the MCP endpoint URL for Open WebUI
    
    Note: This is a placeholder implementation. The actual Kubernetes
    deployment logic will be implemented in the Deploy Controller.
    """
    logger.info(f"User {current_user.id} ({current_user.username}) requesting MCP deployment")
    
    # Get user's configuration
    connection = db.query(IdaMcpConnection).filter(
        IdaMcpConnection.user_id == current_user.id
    ).first()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No IDA bridge configuration found. Please save your configuration first."
        )
    
    try:
        # Allocate proxy port if not already allocated
        if connection.proxy_port is None:
            connection.proxy_port = allocate_proxy_port(db)
            logger.info(f"Allocated proxy port {connection.proxy_port} for user {current_user.id}")
        
        # Update status to deploying
        connection.status = IdaMcpConnectionStatus.DEPLOYING.value
        connection.last_error = None
        db.commit()
        
        # ============================================================
        # PLACEHOLDER: Kubernetes deployment logic goes here
        # 
        # The actual implementation will:
        # 1. Deploy per-user MCP server pod with environment variables
        # 2. Update proxy ConfigMap with port mapping
        # 3. Trigger proxy reload
        # 4. Wait for pod readiness
        # ============================================================
        
        # Generate MCP endpoint URL (placeholder - actual URL depends on Ingress config)
        mcp_base_url = os.getenv("MCP_GATEWAY_BASE_URL", "https://mcp-gateway.company.internal")
        connection.mcp_endpoint_url = f"{mcp_base_url}/research/mcp/{current_user.id}/"
        
        # Mark as deployed (in real implementation, this would be after K8s confirms ready)
        connection.status = IdaMcpConnectionStatus.DEPLOYED.value
        connection.last_deploy_at = datetime.utcnow()
        
        db.commit()
        db.refresh(connection)
        
        log_audit_action(
            db, current_user.id, "deploy",
            payload={
                "hostname_fqdn": connection.hostname_fqdn,
                "ida_port": connection.ida_port,
                "mcp_version": connection.mcp_version,
                "proxy_port": connection.proxy_port
            },
            result={
                "mcp_endpoint_url": connection.mcp_endpoint_url,
                "proxy_port": connection.proxy_port
            },
            action_status="success"
        )
        
        logger.info(f"Successfully deployed MCP for user {current_user.id} on proxy port {connection.proxy_port}")
        
        return DeployResponse(
            success=True,
            message="MCP server deployed successfully",
            status=connection.status,
            proxy_port=connection.proxy_port,
            mcp_endpoint_url=connection.mcp_endpoint_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy MCP for user {current_user.id}: {str(e)}")
        
        connection.status = IdaMcpConnectionStatus.ERROR.value
        connection.last_error = str(e)
        db.commit()
        
        log_audit_action(
            db, current_user.id, "deploy",
            payload={"hostname_fqdn": connection.hostname_fqdn},
            action_status="failure",
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy MCP server: {str(e)}"
        )


@router.post("/ida-bridge/undeploy", response_model=DeployResponse)
async def undeploy_ida_bridge(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Undeploy the user's MCP server pod.
    
    This endpoint:
    1. Removes the per-user MCP server Kubernetes resources
    2. Removes the proxy routing configuration
    3. Releases the allocated proxy port
    
    Note: This is a placeholder implementation. The actual Kubernetes
    cleanup logic will be implemented in the Deploy Controller.
    """
    logger.info(f"User {current_user.id} ({current_user.username}) requesting MCP undeployment")
    
    connection = db.query(IdaMcpConnection).filter(
        IdaMcpConnection.user_id == current_user.id
    ).first()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No IDA bridge configuration found"
        )
    
    if connection.status == IdaMcpConnectionStatus.UNDEPLOYED.value:
        return DeployResponse(
            success=True,
            message="MCP server is already undeployed",
            status=connection.status,
            proxy_port=None,
            mcp_endpoint_url=None
        )
    
    try:
        old_proxy_port = connection.proxy_port
        
        # ============================================================
        # PLACEHOLDER: Kubernetes cleanup logic goes here
        #
        # The actual implementation will:
        # 1. Delete per-user MCP server Deployment/Service/Ingress
        # 2. Remove proxy ConfigMap port mapping
        # 3. Trigger proxy reload
        # ============================================================
        
        # Release proxy port and clear deployment info
        connection.proxy_port = None
        connection.mcp_endpoint_url = None
        connection.status = IdaMcpConnectionStatus.UNDEPLOYED.value
        connection.last_error = None
        
        db.commit()
        
        log_audit_action(
            db, current_user.id, "undeploy",
            payload={"proxy_port": old_proxy_port},
            result={"message": "Undeployed successfully"},
            action_status="success"
        )
        
        logger.info(f"Successfully undeployed MCP for user {current_user.id}, released port {old_proxy_port}")
        
        return DeployResponse(
            success=True,
            message="MCP server undeployed successfully",
            status=connection.status,
            proxy_port=None,
            mcp_endpoint_url=None
        )
        
    except Exception as e:
        logger.error(f"Failed to undeploy MCP for user {current_user.id}: {str(e)}")
        
        connection.status = IdaMcpConnectionStatus.ERROR.value
        connection.last_error = str(e)
        db.commit()
        
        log_audit_action(
            db, current_user.id, "undeploy",
            action_status="failure",
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to undeploy MCP server: {str(e)}"
        )


@router.get("/ida-bridge/status", response_model=IdaBridgeStatusResponse)
async def get_ida_bridge_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Get the deployment status of the user's MCP server.
    
    Returns current status, proxy port, MCP URL, and any error messages.
    """
    connection = db.query(IdaMcpConnection).filter(
        IdaMcpConnection.user_id == current_user.id
    ).first()
    
    if not connection:
        return IdaBridgeStatusResponse(
            status="NOT_CONFIGURED",
            proxy_port=None,
            mcp_endpoint_url=None,
            last_error=None,
            last_deploy_at=None,
            last_healthcheck_at=None,
            is_deployed=False,
            message="No IDA bridge configuration found. Please configure your connection first."
        )
    
    is_deployed = connection.status == IdaMcpConnectionStatus.DEPLOYED.value
    
    status_messages = {
        IdaMcpConnectionStatus.NEW.value: "Configuration saved. Click Deploy to start your MCP server.",
        IdaMcpConnectionStatus.DEPLOYING.value: "MCP server is being deployed...",
        IdaMcpConnectionStatus.DEPLOYED.value: "MCP server is running. Add the MCP URL to Open WebUI.",
        IdaMcpConnectionStatus.ERROR.value: f"Deployment error: {connection.last_error or 'Unknown error'}",
        IdaMcpConnectionStatus.UNDEPLOYED.value: "MCP server is not deployed. Click Deploy to start."
    }
    
    return IdaBridgeStatusResponse(
        status=connection.status,
        proxy_port=connection.proxy_port,
        mcp_endpoint_url=connection.mcp_endpoint_url,
        last_error=connection.last_error,
        last_deploy_at=connection.last_deploy_at.isoformat() if connection.last_deploy_at else None,
        last_healthcheck_at=connection.last_healthcheck_at.isoformat() if connection.last_healthcheck_at else None,
        is_deployed=is_deployed,
        message=status_messages.get(connection.status, "Unknown status")
    )
