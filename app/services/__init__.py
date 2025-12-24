"""
Services module for MCP Client application.

This module contains business logic services including:
- Analytics service
- DBT analysis service  
- Kubernetes controller for IDA MCP deployments
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
]
