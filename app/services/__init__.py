"""
Services module for MCP Client application.

This module contains business logic services including:
- Analytics service
- DBT analysis service  
- Kubernetes controller for IDA MCP deployments
- Artifactory client for Docker image versions
"""

from app.services.k8s_controller import (
    McpServerConfig,
    deploy_mcp_server,
    delete_mcp_server,
    upgrade_mcp_server,
    get_mcp_server_status,
    health_check,
    update_proxy_config_add,
    update_proxy_config_remove,
    reload_nginx_proxy,
)

from app.services.artifactory_client import (
    get_mcp_versions as get_mcp_versions_from_artifactory,
    invalidate_version_cache,
    is_artifactory_enabled,
)

__all__ = [
    "McpServerConfig",
    "deploy_mcp_server",
    "delete_mcp_server",
    "upgrade_mcp_server",
    "get_mcp_server_status",
    "health_check",
    "update_proxy_config_add",
    "update_proxy_config_remove",
    "reload_nginx_proxy",
    "get_mcp_versions_from_artifactory",
    "invalidate_version_cache",
    "is_artifactory_enabled",
]
