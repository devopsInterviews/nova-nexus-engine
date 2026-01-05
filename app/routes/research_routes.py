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
from app.routes.users_routes import is_admin as require_admin  # Admin dependency
from app.services.k8s_controller import (
    McpServerConfig, 
    deploy_mcp_server, 
    delete_mcp_server, 
    upgrade_mcp_server,
    get_mcp_server_status,
    health_check as k8s_health_check
)
from app.services.artifactory_client import (
    get_mcp_versions as get_mcp_versions_from_artifactory,
    is_artifactory_enabled,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/research", tags=["Research"])

# ============================================================
# Configuration
# ============================================================

# Fallback MCP server versions/image tags (used when Artifactory is disabled)
FALLBACK_MCP_VERSIONS = os.getenv(
    "ALLOWED_MCP_VERSIONS", 
    "v1.0.0,v1.1.0,v1.2.0,latest"
).split(",")
FALLBACK_MCP_VERSIONS = [v.strip() for v in FALLBACK_MCP_VERSIONS if v.strip()]

logger.info(f"[RESEARCH] Fallback MCP versions: {FALLBACK_MCP_VERSIONS}")
logger.info(f"[RESEARCH] Artifactory integration enabled: {is_artifactory_enabled()}")


def get_allowed_versions() -> List[str]:
    """Get allowed MCP versions - from Artifactory or fallback."""
    versions, default, error = get_mcp_versions_from_artifactory(use_cache=True)
    if versions:
        return versions
    return FALLBACK_MCP_VERSIONS

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
        """Validate MCP version is in allowed list (dynamically fetched)."""
        v = v.strip()
        logger.debug(f"[RESEARCH] Validating MCP version: {v}")
        allowed_versions = get_allowed_versions()
        if v not in allowed_versions:
            error_msg = f"MCP version '{v}' is not allowed. Allowed: {', '.join(allowed_versions)}"
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
        """Validate MCP version is in allowed list (dynamically fetched)."""
        v = v.strip()
        allowed_versions = get_allowed_versions()
        if v not in allowed_versions:
            raise ValueError(f"MCP version '{v}' is not allowed. Allowed: {', '.join(allowed_versions)}")
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
    proxy_test_url: Optional[str] = None  # For direct testing: curl to this URL to reach IDA
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
        # Ensure payload and result are properly serializable JSON
        # Convert to dict if they're Pydantic models or other objects
        serialized_payload = None
        if payload is not None:
            if hasattr(payload, 'dict'):
                serialized_payload = payload.dict()
            elif hasattr(payload, 'model_dump'):
                serialized_payload = payload.model_dump()
            elif isinstance(payload, dict):
                # Ensure all values are JSON serializable
                serialized_payload = {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v 
                                      for k, v in payload.items()}
            else:
                serialized_payload = {"value": str(payload)}
        
        serialized_result = None
        if result is not None:
            if hasattr(result, 'dict'):
                serialized_result = result.dict()
            elif hasattr(result, 'model_dump'):
                serialized_result = result.model_dump()
            elif isinstance(result, dict):
                # Ensure all values are JSON serializable
                serialized_result = {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v 
                                     for k, v in result.items()}
            else:
                serialized_result = {"value": str(result)}
        
        logger.debug(f"[RESEARCH] Audit payload: {serialized_payload}")
        logger.debug(f"[RESEARCH] Audit result: {serialized_result}")
        
        audit = IdaMcpDeployAudit(
            user_id=user_id,
            action=action,
            payload=serialized_payload,
            result=serialized_result,
            status=action_status,
            error_message=error_message
        )
        db.add(audit)
        db.commit()
        logger.debug(f"[RESEARCH] Audit logged successfully")
    except Exception as e:
        logger.error(f"[RESEARCH] Failed to log audit: {e}")
        logger.error(traceback.format_exc())
        db.rollback()


# ============================================================
# API Endpoints
# ============================================================

@router.get("/mcp/versions", response_model=McpVersionsResponse)
async def get_mcp_versions(current_user: User = Depends(get_current_user)):
    """Get list of allowed MCP server versions (from Artifactory or fallback)."""
    logger.info(f"[RESEARCH] User {current_user.id} ({current_user.username}) requesting MCP versions")
    
    # Fetch versions from Artifactory (with caching) or fallback
    versions, default_version, error = get_mcp_versions_from_artifactory(use_cache=True)
    
    if error:
        logger.warning(f"[RESEARCH] Artifactory fetch had error: {error}, using fallback versions")
    
    response = McpVersionsResponse(
        versions=versions if versions else FALLBACK_MCP_VERSIONS,
        default_version=default_version if default_version else (FALLBACK_MCP_VERSIONS[-1] if FALLBACK_MCP_VERSIONS else "latest")
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
        # Deploy MCP Server via Kubernetes Controller
        # ============================================================
        mcp_config = McpServerConfig(
            user_id=current_user.id,
            username=current_user.username,
            hostname_fqdn=config.hostname_fqdn,
            ida_port=config.ida_port,
            proxy_port=connection.proxy_port,
            mcp_version=config.mcp_version
        )
        
        logger.info(f"[RESEARCH] Calling K8s controller to deploy MCP server")
        k8s_success, k8s_message, mcp_url = deploy_mcp_server(mcp_config)
        
        if not k8s_success:
            logger.error(f"[RESEARCH] K8s deployment failed: {k8s_message}")
            connection.status = IdaMcpConnectionStatus.ERROR.value
            connection.last_error = k8s_message
            db.commit()
            
            log_audit_action(
                db, current_user.id, "deploy",
                payload={
                    "hostname_fqdn": connection.hostname_fqdn,
                    "ida_port": connection.ida_port,
                    "mcp_version": connection.mcp_version,
                    "proxy_port": connection.proxy_port
                },
                action_status="failure",
                error_message=k8s_message
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Kubernetes deployment failed: {k8s_message}"
            )
        
        # Update with MCP endpoint URL from K8s controller
        # Also allow override via environment variable for external access
        mcp_base_url = os.getenv("MCP_GATEWAY_BASE_URL", "")
        if mcp_base_url:
            connection.mcp_endpoint_url = f"{mcp_base_url}:{connection.proxy_port}/"
        else:
            connection.mcp_endpoint_url = mcp_url
        
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
        
        # Build proxy test URL for direct testing
        k8s_namespace = os.getenv("K8S_NAMESPACE", "ida-mcp-servers")
        ida_proxy_deployment = os.getenv("IDA_PROXY_DEPLOYMENT", "ida-proxy")
        proxy_test_url = f"http://{ida_proxy_deployment}.{k8s_namespace}.svc.cluster.local:{connection.proxy_port}/"
        
        return DeployResponse(
            success=True,
            message="MCP server deployed successfully",
            status=connection.status,
            proxy_port=connection.proxy_port,
            mcp_endpoint_url=connection.mcp_endpoint_url,
            proxy_test_url=proxy_test_url,
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
        old_hostname = connection.hostname_fqdn
        old_ida_port = connection.ida_port
        old_mcp_version = connection.mcp_version
        
        logger.info(f"[RESEARCH] Deleting config: id={connection.id}, proxy_port={old_proxy_port}")
        
        # ============================================================
        # Delete MCP Server via Kubernetes Controller
        # ============================================================
        logger.info(f"[RESEARCH] Calling K8s controller to delete MCP server")
        k8s_success, k8s_message = delete_mcp_server(current_user.id, old_proxy_port)
        
        if not k8s_success:
            logger.warning(f"[RESEARCH] K8s deletion had issues: {k8s_message}")
            # Continue anyway - we still want to delete from database
        
        # Delete the configuration
        db.delete(connection)
        db.commit()
        
        logger.info(f"[RESEARCH] Successfully deleted config for user {current_user.id}")
        
        log_audit_action(
            db, current_user.id, "delete",
            payload={
                "proxy_port": old_proxy_port, 
                "old_status": old_status,
                "hostname_fqdn": old_hostname,
                "ida_port": old_ida_port,
                "mcp_version": old_mcp_version
            },
            result={"message": "Deleted successfully", "k8s_message": k8s_message},
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
        # Upgrade MCP Server via Kubernetes Controller
        # ============================================================
        logger.info(f"[RESEARCH] Calling K8s controller to upgrade MCP server")
        k8s_success, k8s_message = upgrade_mcp_server(current_user.id, upgrade_request.new_mcp_version)
        
        if not k8s_success:
            logger.error(f"[RESEARCH] K8s upgrade failed: {k8s_message}")
            connection.status = IdaMcpConnectionStatus.ERROR.value
            connection.last_error = k8s_message
            connection.mcp_version = old_version  # Revert version
            db.commit()
            
            log_audit_action(
                db, current_user.id, "upgrade",
                payload={"old_version": old_version, "new_version": upgrade_request.new_mcp_version},
                action_status="failure",
                error_message=k8s_message
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Kubernetes upgrade failed: {k8s_message}"
            )
        
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


@router.get("/k8s/health")
async def k8s_controller_health(
    current_user: User = Depends(get_current_user)
):
    """
    Get the health status of the Kubernetes controller.
    
    Returns information about K8s connectivity and proxy status.
    """
    logger.info(f"[RESEARCH] User {current_user.id} checking K8s health")
    
    health = k8s_health_check()
    
    return {
        "status": "ok" if health.get("k8s_connected") else "simulation_mode",
        "k8s_connected": health.get("k8s_connected", False),
        "proxy_status": health.get("proxy_status", "unknown"),
        "namespace": health.get("namespace", "unknown")
    }


# ============================================================
# Admin Endpoints - Manage All Users' MCP Servers
# ============================================================

class AdminIdaBridgeResponse(BaseModel):
    """Extended response model for admin view with user info."""
    id: int
    user_id: int
    username: str
    email: Optional[str]
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


class AdminIdaBridgeListResponse(BaseModel):
    """Response model for admin list of all IDA bridge connections."""
    connections: List[AdminIdaBridgeResponse]
    total: int


@router.get("/admin/ida-bridge/all", response_model=AdminIdaBridgeListResponse)
async def admin_get_all_ida_bridges(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session)
):
    """
    Get all IDA bridge configurations (Admin only).
    
    Returns all users' IDA MCP connections for administrative management.
    """
    logger.info(f"[RESEARCH] Admin {current_user.username} retrieving all IDA bridge configs")
    
    try:
        # Query all connections with user info
        connections = db.query(IdaMcpConnection, User).join(
            User, IdaMcpConnection.user_id == User.id
        ).all()
        
        result = []
        for conn, user in connections:
            result.append(AdminIdaBridgeResponse(
                id=conn.id,
                user_id=conn.user_id,
                username=user.username,
                email=user.email,
                hostname_fqdn=conn.hostname_fqdn,
                ida_port=conn.ida_port,
                proxy_port=conn.proxy_port,
                mcp_version=conn.mcp_version,
                mcp_endpoint_url=conn.mcp_endpoint_url,
                status=conn.status,
                last_error=conn.last_error,
                created_at=conn.created_at.isoformat() if conn.created_at else None,
                updated_at=conn.updated_at.isoformat() if conn.updated_at else None,
                last_deploy_at=conn.last_deploy_at.isoformat() if conn.last_deploy_at else None,
                last_healthcheck_at=conn.last_healthcheck_at.isoformat() if conn.last_healthcheck_at else None
            ))
        
        logger.info(f"[RESEARCH] Admin {current_user.username} retrieved {len(result)} IDA bridges")
        
        return AdminIdaBridgeListResponse(
            connections=result,
            total=len(result)
        )
        
    except SQLAlchemyError as e:
        logger.error(f"[RESEARCH] Database error in admin get all: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/admin/ida-bridge/{target_user_id}", response_model=DeployResponse)
async def admin_delete_ida_bridge(
    target_user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session)
):
    """
    Delete/undeploy an IDA bridge for a specific user (Admin only).
    
    Allows administrators to remove MCP server deployments for any user.
    """
    logger.info(f"[RESEARCH] Admin {current_user.username} deleting IDA bridge for user {target_user_id}")
    
    try:
        # Get the target user
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user:
            logger.warning(f"[RESEARCH] Admin {current_user.username}: User {target_user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {target_user_id} not found"
            )
        
        # Get the connection
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == target_user_id
        ).first()
        
        if not connection:
            logger.warning(f"[RESEARCH] Admin {current_user.username}: No IDA bridge for user {target_user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No IDA bridge configuration found for user {target_user.username}"
            )
        
        # Log admin action
        log_audit_action(
            db=db,
            user_id=current_user.id,  # Admin who performed the action
            action="admin_delete",
            payload={
                "target_user_id": target_user_id,
                "target_username": target_user.username,
                "hostname_fqdn": connection.hostname_fqdn,
                "proxy_port": connection.proxy_port
            },
            action_status="in_progress"
        )
        
        # Delete the MCP server if deployed
        proxy_port = connection.proxy_port
        if connection.status == IdaMcpConnectionStatus.DEPLOYED.value and proxy_port:
            logger.info(f"[RESEARCH] Admin {current_user.username}: Deleting MCP server for user {target_user.username}")
            success, message = delete_mcp_server(target_user_id, proxy_port)
            
            if not success:
                logger.error(f"[RESEARCH] Admin delete failed for user {target_user_id}: {message}")
                connection.status = IdaMcpConnectionStatus.ERROR.value
                connection.last_error = f"Admin delete failed: {message}"
                db.commit()
                
                log_audit_action(
                    db=db,
                    user_id=current_user.id,
                    action="admin_delete",
                    payload={"target_user_id": target_user_id},
                    result={"error": message},
                    action_status="error",
                    error_message=message
                )
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete MCP server: {message}"
                )
        
        # Delete the database record
        db.delete(connection)
        db.commit()
        
        log_audit_action(
            db=db,
            user_id=current_user.id,
            action="admin_delete",
            payload={"target_user_id": target_user_id, "target_username": target_user.username},
            result={"success": True},
            action_status="success"
        )
        
        logger.info(f"[RESEARCH] Admin {current_user.username} successfully deleted IDA bridge for user {target_user.username}")
        
        return DeployResponse(
            success=True,
            message=f"IDA bridge for user {target_user.username} has been deleted by admin",
            status=IdaMcpConnectionStatus.UNDEPLOYED.value,
            proxy_port=None,
            mcp_endpoint_url=None,
            config=None
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[RESEARCH] Database error in admin delete: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/admin/ida-bridge/{target_user_id}/upgrade", response_model=DeployResponse)
async def admin_upgrade_ida_bridge(
    target_user_id: int,
    upgrade_request: IdaBridgeUpgradeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session)
):
    """
    Upgrade MCP server version for a specific user (Admin only).
    
    Allows administrators to upgrade MCP server versions for any user.
    """
    logger.info(f"[RESEARCH] Admin {current_user.username} upgrading IDA bridge for user {target_user_id} to {upgrade_request.new_mcp_version}")
    
    try:
        # Get the target user
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if not target_user:
            logger.warning(f"[RESEARCH] Admin {current_user.username}: User {target_user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {target_user_id} not found"
            )
        
        # Get the connection
        connection = db.query(IdaMcpConnection).filter(
            IdaMcpConnection.user_id == target_user_id
        ).first()
        
        if not connection:
            logger.warning(f"[RESEARCH] Admin {current_user.username}: No IDA bridge for user {target_user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No IDA bridge configuration found for user {target_user.username}"
            )
        
        if connection.status != IdaMcpConnectionStatus.DEPLOYED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot upgrade: MCP server is not deployed (status: {connection.status})"
            )
        
        # Log admin action
        log_audit_action(
            db=db,
            user_id=current_user.id,
            action="admin_upgrade",
            payload={
                "target_user_id": target_user_id,
                "target_username": target_user.username,
                "old_version": connection.mcp_version,
                "new_version": upgrade_request.new_mcp_version
            },
            action_status="in_progress"
        )
        
        # Perform the upgrade
        success, message = upgrade_mcp_server(
            target_user_id,
            upgrade_request.new_mcp_version
        )
        
        if success:
            connection.mcp_version = upgrade_request.new_mcp_version
            connection.updated_at = datetime.utcnow()
            db.commit()
            
            log_audit_action(
                db=db,
                user_id=current_user.id,
                action="admin_upgrade",
                payload={"target_user_id": target_user_id, "new_version": upgrade_request.new_mcp_version},
                result={"success": True},
                action_status="success"
            )
            
            logger.info(f"[RESEARCH] Admin {current_user.username} upgraded user {target_user.username} to {upgrade_request.new_mcp_version}")
            
            return DeployResponse(
                success=True,
                message=f"MCP server for user {target_user.username} upgraded to {upgrade_request.new_mcp_version} by admin",
                status=connection.status,
                proxy_port=connection.proxy_port,
                mcp_endpoint_url=connection.mcp_endpoint_url,
                config=IdaBridgeConfigResponse(
                    id=connection.id,
                    user_id=connection.user_id,
                    hostname_fqdn=connection.hostname_fqdn,
                    ida_port=connection.ida_port,
                    proxy_port=connection.proxy_port,
                    mcp_version=connection.mcp_version,
                    mcp_endpoint_url=connection.mcp_endpoint_url,
                    status=connection.status,
                    last_error=connection.last_error,
                    created_at=connection.created_at.isoformat() if connection.created_at else None,
                    updated_at=connection.updated_at.isoformat() if connection.updated_at else None,
                    last_deploy_at=connection.last_deploy_at.isoformat() if connection.last_deploy_at else None,
                    last_healthcheck_at=connection.last_healthcheck_at.isoformat() if connection.last_healthcheck_at else None
                )
            )
        else:
            connection.status = IdaMcpConnectionStatus.ERROR.value
            connection.last_error = f"Admin upgrade failed: {message}"
            db.commit()
            
            log_audit_action(
                db=db,
                user_id=current_user.id,
                action="admin_upgrade",
                payload={"target_user_id": target_user_id},
                result={"error": message},
                action_status="error",
                error_message=message
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upgrade MCP server: {message}"
            )
            
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[RESEARCH] Database error in admin upgrade: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
