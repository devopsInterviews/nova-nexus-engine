"""
Research API Routes for IDA MCP Connection Management.

This module provides endpoints for managing IDA MCP connections,
allowing users to register their workstations and deploy MCP server pods.

Endpoints:
- GET  /research/mcp/versions      - Get allowed MCP server versions
- GET  /research/ida-bridge        - Get current user's IDA bridge config
- POST /research/ida-bridge/deploy - Deploy user's MCP server
- DELETE /research/ida-bridge      - Delete/undeploy user's MCP server
- POST /research/ida-bridge/upgrade - Upgrade MCP server version
- GET  /research/ida-bridge/status - Get deployment status
"""

import os
import re
import logging
import traceback
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
ALLOWED_MCP_VERSIONS = [v.strip() for v in ALLOWED_MCP_VERSIONS if v.strip()]

logger.info(f"[RESEARCH] Loaded MCP versions: {ALLOWED_MCP_VERSIONS}")

# Allowed hostname domain patterns (regex) - empty means allow all
ALLOWED_HOSTNAME_PATTERNS_RAW = os.getenv("ALLOWED_HOSTNAME_PATTERNS", "")
ALLOWED_HOSTNAME_PATTERNS = [p.strip() for p in ALLOWED_HOSTNAME_PATTERNS_RAW.split(",") if p.strip()]

logger.info(f"[RESEARCH] Loaded hostname patterns: {ALLOWED_HOSTNAME_PATTERNS or 'ALL ALLOWED'}")

# Allowed IDA port range
IDA_PORT_MIN = int(os.getenv("IDA_PORT_MIN", "1024"))
IDA_PORT_MAX = int(os.getenv("IDA_PORT_MAX", "65535"))

logger.info(f"[RESEARCH] IDA port range: {IDA_PORT_MIN}-{IDA_PORT_MAX}")

# Proxy port allocation range
PROXY_PORT_MIN = int(os.getenv("PROXY_PORT_MIN", "9001"))
PROXY_PORT_MAX = int(os.getenv("PROXY_PORT_MAX", "9999"))

logger.info(f"[RESEARCH] Proxy port range: {PROXY_PORT_MIN}-{PROXY_PORT_MAX}")


# ============================================================
# Pydantic Models
# ============================================================

class McpVersionsResponse(BaseModel):
    """Response model for MCP versions list."""
    versions: List[str]
    default_version: str


class IdaBridgeDeployRequest(BaseModel):
    """Request model for deploying IDA bridge."""
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
        """Validate hostname - allow all if no patterns configured."""
        v = v.strip().lower()
        logger.debug(f"[RESEARCH] Validating hostname: {v}")
        
        # If no patterns configured, allow all hostnames
        if not ALLOWED_HOSTNAME_PATTERNS:
            logger.debug(f"[RESEARCH] No hostname restrictions, allowing: {v}")
            return v
        
        # Check if hostname matches any allowed pattern
        for pattern in ALLOWED_HOSTNAME_PATTERNS:
            try:
                if re.match(pattern, v, re.IGNORECASE):
                    logger.debug(f"[RESEARCH] Hostname {v} matched pattern: {pattern}")
                    return v
            except re.error as e:
                logger.warning(f"[RESEARCH] Invalid regex pattern '{pattern}': {e}")
                continue
        
        error_msg = f"Hostname '{v}' does not match allowed domain patterns: {', '.join(ALLOWED_HOSTNAME_PATTERNS)}"
        logger.warning(f"[RESEARCH] {error_msg}")
        raise ValueError(error_msg)
    
    @validator('ida_port')
    def validate_ida_port(cls, v):
        """Validate IDA port is within allowed range."""
        logger.debug(f"[RESEARCH] Validating IDA port: {v}")
        if v < IDA_PORT_MIN or v > IDA_PORT_MAX:
            error_msg = f"IDA port must be between {IDA_PORT_MIN} and {IDA_PORT_MAX}"
            logger.warning(f"[RESEARCH] {error_msg}")
            raise ValueError(error_msg)
        return v
    
    @validator('mcp_version')
    def validate_mcp_version(cls, v):
        """Validate MCP version is in allowed list."""
        v = v.strip()
        logger.debug(f"[RESEARCH] Validating MCP version: {v}")
        if v not in ALLOWED_MCP_VERSIONS:
            error_msg = f"MCP version '{v}' is not allowed. Allowed: {', '.join(ALLOWED_MCP_VERSIONS)}"
            logger.warning(f"[RESEARCH] {error_msg}")
            raise ValueError(error_msg)
        return v


class IdaBridgeUpgradeRequest(BaseModel):
    """Request model for upgrading MCP server version."""
    new_mcp_version: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="New MCP server version to upgrade to"
    )
    
    @validator('new_mcp_version')
    def validate_mcp_version(cls, v):
        """Validate MCP version is in allowed list."""
        v = v.strip()
        if v not in ALLOWED_MCP_VERSIONS:
            raise ValueError(f"MCP version '{v}' is not allowed. Allowed: {', '.join(ALLOWED_MCP_VERSIONS)}")
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
    # Additional fields for UI
    hostname_fqdn: Optional[str]
    ida_port: Optional[int]
    mcp_version: Optional[str]


class DeployResponse(BaseModel):
    """Response model for deploy/undeploy actions."""
    success: bool
    message: str
    status: str
    proxy_port: Optional[int]
    mcp_endpoint_url: Optional[str]
    config: Optional[IdaBridgeConfigResponse]


# ============================================================
# Helper Functions
# ============================================================

def allocate_proxy_port(db: Session) -> int:
    """
    Allocate the next available proxy port from the configured range.
    """
    logger.info(f"[RESEARCH] Allocating proxy port from range {PROXY_PORT_MIN}-{PROXY_PORT_MAX}")
    
    # Get all currently allocated ports
    allocated_ports = db.query(IdaMcpConnection.proxy_port).filter(
        IdaMcpConnection.proxy_port.isnot(None)
    ).all()
    allocated_set = {p[0] for p in allocated_ports}
    
    logger.debug(f"[RESEARCH] Currently allocated ports: {allocated_set}")
    
    # Find the first available port in range
    for port in range(PROXY_PORT_MIN, PROXY_PORT_MAX + 1):
        if port not in allocated_set:
            logger.info(f"[RESEARCH] Allocated proxy port: {port}")
            return port
    
    logger.error(f"[RESEARCH] No proxy ports available in range {PROXY_PORT_MIN}-{PROXY_PORT_MAX}")
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
    logger.debug(f"[RESEARCH] Logging audit: user={user_id}, action={action}, status={action_status}")
    try:
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
        logger.debug(f"[RESEARCH] Audit logged successfully")
    except Exception as e:
        logger.error(f"[RESEARCH] Failed to log audit: {e}")
        db.rollback()


# ============================================================
# API Endpoints
# ============================================================

@router.get("/mcp/versions", response_model=McpVersionsResponse)
async def get_mcp_versions(current_user: User = Depends(get_current_user)):
    """Get list of allowed MCP server versions."""
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) requesting MCP versions")
    
    response = McpVersionsResponse(
        versions=ALLOWED_MCP_VERSIONS,
        default_version=ALLOWED_MCP_VERSIONS[-1] if ALLOWED_MCP_VERSIONS else "latest"
    )
    
    logger.debug(f"[RESEARCH] Returning versions: {response.versions}, default: {response.default_version}")
    return response


@router.get("/ida-bridge", response_model=Optional[IdaBridgeConfigResponse])
async def get_ida_bridge_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get the current user's IDA bridge configuration."""
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) getting IDA bridge config")
    
    try:
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == current_user.id
        ).first()
        
        if not connection:
            logger.info(f"[RESEARCH] No config found for user {current_user.id}")
            return None
        
        logger.info(f"[RESEARCH] Found config for user {current_user.id}: status={connection.status}")
        return IdaBridgeConfigResponse(**connection.to_dict())
        
    except SQLAlchemyError as e:
        logger.error(f"[RESEARCH] Database error getting config: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/ida-bridge/deploy", response_model=DeployResponse)
async def deploy_ida_bridge(
    config: IdaBridgeDeployRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Deploy the user's MCP server pod.
    
    This endpoint:
    1. Creates or updates the user's IDA bridge configuration
    2. Allocates a proxy port if not already allocated
    3. Creates/updates the per-user MCP server Kubernetes resources
    4. Returns the MCP endpoint URL for Open WebUI
    """
    logger.info(f"[RESEARCH] ========== DEPLOY START ==========")
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) requesting deployment")
    logger.info(f"[RESEARCH] Config: hostname={config.hostname_fqdn}, port={config.ida_port}, version={config.mcp_version}")
    
    try:
        # Check if configuration already exists
        logger.debug(f"[RESEARCH] Checking for existing config for user {current_user.id}")
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == current_user.id
        ).first()
        
        if connection:
            logger.info(f"[RESEARCH] Updating existing config (id={connection.id})")
            # Update existing configuration
            connection.hostname_fqdn = config.hostname_fqdn
            connection.ida_port = config.ida_port
            connection.mcp_version = config.mcp_version
            connection.updated_at = datetime.utcnow()
        else:
            logger.info(f"[RESEARCH] Creating new config for user {current_user.id}")
            # Create new configuration
            connection = IdaMcpConnection(
                user_id=current_user.id,
                hostname_fqdn=config.hostname_fqdn,
                ida_port=config.ida_port,
                mcp_version=config.mcp_version,
                status=IdaMcpConnectionStatus.NEW.value
            )
            db.add(connection)
            logger.debug(f"[RESEARCH] Added new connection to session")
        
        # Flush to get the ID if new
        db.flush()
        logger.debug(f"[RESEARCH] Flushed session, connection id={connection.id}")
        
        # Allocate proxy port if not already allocated
        if connection.proxy_port is None:
            logger.info(f"[RESEARCH] No proxy port allocated, allocating new one")
            connection.proxy_port = allocate_proxy_port(db)
        else:
            logger.info(f"[RESEARCH] Using existing proxy port: {connection.proxy_port}")
        
        # Update status to deploying
        connection.status = IdaMcpConnectionStatus.DEPLOYING.value
        connection.last_error = None
        
        logger.debug(f"[RESEARCH] Committing DEPLOYING status")
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
        logger.info(f"[RESEARCH] [PLACEHOLDER] Would deploy K8s resources here")
        
        # Generate MCP endpoint URL (placeholder - actual URL depends on Ingress config)
        mcp_base_url = os.getenv("MCP_GATEWAY_BASE_URL", "https://mcp-gateway.company.internal")
        connection.mcp_endpoint_url = f"{mcp_base_url}/research/mcp/{current_user.id}/"
        
        logger.info(f"[RESEARCH] Generated MCP URL: {connection.mcp_endpoint_url}")
        
        # Mark as deployed (in real implementation, this would be after K8s confirms ready)
        connection.status = IdaMcpConnectionStatus.DEPLOYED.value
        connection.last_deploy_at = datetime.utcnow()
        
        logger.debug(f"[RESEARCH] Committing DEPLOYED status")
        db.commit()
        db.refresh(connection)
        
        logger.info(f"[RESEARCH] Successfully deployed for user {current_user.id}")
        logger.info(f"[RESEARCH] Final state: id={connection.id}, proxy_port={connection.proxy_port}, status={connection.status}")
        
        # Log audit
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
        
        logger.info(f"[RESEARCH] ========== DEPLOY SUCCESS ==========")
        
        return DeployResponse(
            success=True,
            message="MCP server deployed successfully",
            status=connection.status,
            proxy_port=connection.proxy_port,
            mcp_endpoint_url=connection.mcp_endpoint_url,
            config=IdaBridgeConfigResponse(**connection.to_dict())
        )
        
    except HTTPException:
        logger.error(f"[RESEARCH] HTTPException during deploy")
        raise
    except SQLAlchemyError as e:
        logger.error(f"[RESEARCH] Database error during deploy: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        log_audit_action(
            db, current_user.id, "deploy",
            payload={"hostname_fqdn": config.hostname_fqdn},
            action_status="failure",
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[RESEARCH] Unexpected error during deploy: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        # Try to update status to error
        try:
            if connection:
                connection.status = IdaMcpConnectionStatus.ERROR.value
                connection.last_error = str(e)
                db.commit()
        except:
            pass
        
        log_audit_action(
            db, current_user.id, "deploy",
            payload={"hostname_fqdn": config.hostname_fqdn},
            action_status="failure",
            error_message=str(e)
        )
        
        logger.info(f"[RESEARCH] ========== DEPLOY FAILED ==========")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy MCP server: {str(e)}"
        )


@router.delete("/ida-bridge", response_model=DeployResponse)
async def delete_ida_bridge(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Delete/undeploy the user's MCP server pod.
    
    This endpoint:
    1. Removes the per-user MCP server Kubernetes resources
    2. Removes the proxy routing configuration
    3. Deletes the configuration from the database
    """
    logger.info(f"[RESEARCH] ========== DELETE START ==========")
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) requesting deletion")
    
    try:
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == current_user.id
        ).first()
        
        if not connection:
            logger.warning(f"[RESEARCH] No config found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No IDA bridge configuration found"
            )
        
        old_proxy_port = connection.proxy_port
        old_status = connection.status
        
        logger.info(f"[RESEARCH] Deleting config: id={connection.id}, proxy_port={old_proxy_port}")
        
        # ============================================================
        # PLACEHOLDER: Kubernetes cleanup logic goes here
        #
        # The actual implementation will:
        # 1. Delete per-user MCP server Deployment/Service/Ingress
        # 2. Remove proxy ConfigMap port mapping
        # 3. Trigger proxy reload
        # ============================================================
        logger.info(f"[RESEARCH] [PLACEHOLDER] Would delete K8s resources here")
        
        # Delete the configuration
        db.delete(connection)
        db.commit()
        
        logger.info(f"[RESEARCH] Successfully deleted config for user {current_user.id}")
        
        log_audit_action(
            db, current_user.id, "delete",
            payload={"proxy_port": old_proxy_port, "old_status": old_status},
            result={"message": "Deleted successfully"},
            action_status="success"
        )
        
        logger.info(f"[RESEARCH] ========== DELETE SUCCESS ==========")
        
        return DeployResponse(
            success=True,
            message="MCP server deleted successfully",
            status="DELETED",
            proxy_port=None,
            mcp_endpoint_url=None,
            config=None
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"[RESEARCH] Database error during delete: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[RESEARCH] Unexpected error during delete: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        logger.info(f"[RESEARCH] ========== DELETE FAILED ==========")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MCP server: {str(e)}"
        )


@router.post("/ida-bridge/upgrade", response_model=DeployResponse)
async def upgrade_ida_bridge(
    upgrade_request: IdaBridgeUpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Upgrade the MCP server to a new version.
    """
    logger.info(f"[RESEARCH] ========== UPGRADE START ==========")
    logger.info(f"[RESEARCH] User {current_user.id} upgrading to version: {upgrade_request.new_mcp_version}")
    
    try:
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == current_user.id
        ).first()
        
        if not connection:
            logger.warning(f"[RESEARCH] No config found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No IDA bridge configuration found. Deploy first."
            )
        
        old_version = connection.mcp_version
        logger.info(f"[RESEARCH] Upgrading from {old_version} to {upgrade_request.new_mcp_version}")
        
        if old_version == upgrade_request.new_mcp_version:
            logger.info(f"[RESEARCH] Already on requested version")
            return DeployResponse(
                success=True,
                message=f"Already running version {old_version}",
                status=connection.status,
                proxy_port=connection.proxy_port,
                mcp_endpoint_url=connection.mcp_endpoint_url,
                config=IdaBridgeConfigResponse(**connection.to_dict())
            )
        
        # Update version
        connection.mcp_version = upgrade_request.new_mcp_version
        connection.status = IdaMcpConnectionStatus.DEPLOYING.value
        connection.updated_at = datetime.utcnow()
        
        db.commit()
        
        # ============================================================
        # PLACEHOLDER: Kubernetes upgrade logic goes here
        # 
        # The actual implementation will:
        # 1. Update the MCP server Deployment with new image tag
        # 2. Wait for rollout to complete
        # ============================================================
        logger.info(f"[RESEARCH] [PLACEHOLDER] Would upgrade K8s deployment here")
        
        connection.status = IdaMcpConnectionStatus.DEPLOYED.value
        connection.last_deploy_at = datetime.utcnow()
        
        db.commit()
        db.refresh(connection)
        
        logger.info(f"[RESEARCH] Successfully upgraded to {upgrade_request.new_mcp_version}")
        
        log_audit_action(
            db, current_user.id, "upgrade",
            payload={"old_version": old_version, "new_version": upgrade_request.new_mcp_version},
            result={"message": "Upgraded successfully"},
            action_status="success"
        )
        
        logger.info(f"[RESEARCH] ========== UPGRADE SUCCESS ==========")
        
        return DeployResponse(
            success=True,
            message=f"MCP server upgraded from {old_version} to {upgrade_request.new_mcp_version}",
            status=connection.status,
            proxy_port=connection.proxy_port,
            mcp_endpoint_url=connection.mcp_endpoint_url,
            config=IdaBridgeConfigResponse(**connection.to_dict())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RESEARCH] Unexpected error during upgrade: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        logger.info(f"[RESEARCH] ========== UPGRADE FAILED ==========")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade MCP server: {str(e)}"
        )


@router.get("/ida-bridge/status", response_model=IdaBridgeStatusResponse)
async def get_ida_bridge_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get the deployment status of the user's MCP server."""
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) getting status")
    
    try:
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == current_user.id
        ).first()
        
        if not connection:
            logger.debug(f"[RESEARCH] No config found for user {current_user.id}")
            return IdaBridgeStatusResponse(
                status="NOT_CONFIGURED",
                proxy_port=None,
                mcp_endpoint_url=None,
                last_error=None,
                last_deploy_at=None,
                last_healthcheck_at=None,
                is_deployed=False,
                message="No IDA bridge configuration found. Deploy to get started.",
                hostname_fqdn=None,
                ida_port=None,
                mcp_version=None
            )
        
        is_deployed = connection.status == IdaMcpConnectionStatus.DEPLOYED.value
        
        status_messages = {
            IdaMcpConnectionStatus.NEW.value: "Configuration saved. Ready to deploy.",
            IdaMcpConnectionStatus.DEPLOYING.value: "MCP server is being deployed...",
            IdaMcpConnectionStatus.DEPLOYED.value: "MCP server is running. Add the MCP URL to Open WebUI.",
            IdaMcpConnectionStatus.ERROR.value: f"Deployment error: {connection.last_error or 'Unknown error'}",
            IdaMcpConnectionStatus.UNDEPLOYED.value: "MCP server is not deployed."
        }
        
        logger.debug(f"[RESEARCH] Status for user {current_user.id}: {connection.status}, deployed={is_deployed}")
        
        return IdaBridgeStatusResponse(
            status=connection.status,
            proxy_port=connection.proxy_port,
            mcp_endpoint_url=connection.mcp_endpoint_url,
            last_error=connection.last_error,
            last_deploy_at=connection.last_deploy_at.isoformat() if connection.last_deploy_at else None,
            last_healthcheck_at=connection.last_healthcheck_at.isoformat() if connection.last_healthcheck_at else None,
            is_deployed=is_deployed,
            message=status_messages.get(connection.status, "Unknown status"),
            hostname_fqdn=connection.hostname_fqdn,
            ida_port=connection.ida_port,
            mcp_version=connection.mcp_version
        )
        
    except SQLAlchemyError as e:
        logger.error(f"[RESEARCH] Database error getting status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# Keep the old POST endpoint for backward compatibility but redirect to deploy
@router.post("/ida-bridge", response_model=DeployResponse)
async def upsert_ida_bridge_config(
    config: IdaBridgeDeployRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    Legacy endpoint - redirects to deploy.
    For backward compatibility, this endpoint now triggers a deploy.
    """
    logger.info(f"[RESEARCH] Legacy POST /ida-bridge called, redirecting to deploy")
    return await deploy_ida_bridge(config, current_user, db)
