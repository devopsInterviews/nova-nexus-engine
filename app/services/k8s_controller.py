"""
Kubernetes Controller for IDA MCP Server Deployments.

This module provides functionality to:
1. Deploy per-user MCP server pods
2. Manage nginx proxy ConfigMaps (listen_ports.conf, port_map.conf)
3. Reload nginx when configuration changes

Architecture:
- Each user gets their own MCP server pod
- A shared nginx proxy routes traffic based on allocated proxy ports
- ConfigMaps are updated dynamically as users deploy/delete their MCP servers
"""

import os
import logging
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger("uvicorn.error")

# ============================================================
# Configuration
# ============================================================

# Namespace where IDA MCP resources are deployed (set via Helm)
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")

# IDA Proxy deployment name (set via Helm based on release name)
IDA_PROXY_DEPLOYMENT = os.getenv("IDA_PROXY_DEPLOYMENT", "mcp-client-ida-proxy")
IDA_PROXY_CONFIGMAP_PORTS = os.getenv("IDA_PROXY_CONFIGMAP_PORTS", "mcp-client-ida-proxy-listen-ports")
IDA_PROXY_CONFIGMAP_MAP = os.getenv("IDA_PROXY_CONFIGMAP_MAP", "mcp-client-ida-proxy-port-map")

# IDA MCP Server configuration (prefixed to avoid K8s service discovery conflicts)
IDA_MCP_SERVER_IMAGE_REPO = os.getenv("IDA_MCP_SERVER_IMAGE_REPO", "nginxdemos/hello")
IDA_MCP_SERVER_PORT = int(os.getenv("IDA_MCP_SERVER_PORT", "80"))
IDA_MCP_SERVER_HEALTH_PATH = os.getenv("IDA_MCP_SERVER_HEALTH_PATH", "/")

# Service configuration for MCP server pods
IDA_MCP_SERVICE_NETWORK_POOL = os.getenv("IDA_MCP_SERVICE_NETWORK_POOL", "")

# Bitbucket GitOps configuration (for ArgoCD-managed deployments)
BITBUCKET_ENABLED = os.getenv("BITBUCKET_ENABLED", "false").lower() == "true"
BITBUCKET_URL = os.getenv("BITBUCKET_URL", "")
BITBUCKET_PROJECT = os.getenv("BITBUCKET_PROJECT", "")
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO", "")
BITBUCKET_BRANCH = os.getenv("BITBUCKET_BRANCH", "main")
BITBUCKET_VALUES_PATH = os.getenv("BITBUCKET_VALUES_PATH", "values.yaml")
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME", "")
BITBUCKET_PASSWORD = os.getenv("BITBUCKET_PASSWORD", "")
BITBUCKET_EMAIL = os.getenv("BITBUCKET_EMAIL", "mcp-client@system.local")
BITBUCKET_VERIFY_SSL = os.getenv("BITBUCKET_VERIFY_SSL", "true").lower() == "true"

# Labels for resource management
LABEL_APP = "ida-mcp"
LABEL_COMPONENT_MCP = "mcp-server"
LABEL_COMPONENT_PROXY = "proxy"

logger.info(f"[K8S_CONTROLLER] Initialized with namespace={K8S_NAMESPACE}")
logger.info(f"[K8S_CONTROLLER] Proxy deployment={IDA_PROXY_DEPLOYMENT}")
logger.info(f"[K8S_CONTROLLER] IDA MCP image repo={IDA_MCP_SERVER_IMAGE_REPO}")
logger.info(f"[K8S_CONTROLLER] IDA MCP server port={IDA_MCP_SERVER_PORT}, health path={IDA_MCP_SERVER_HEALTH_PATH}")
logger.info(f"[K8S_CONTROLLER] Bitbucket GitOps enabled={BITBUCKET_ENABLED}")

# Initialize Bitbucket client if enabled
bitbucket_manager = None
if BITBUCKET_ENABLED:
    try:
        from app.services.bitbucket_client import ValuesFileManager, BitbucketClient
        bitbucket_client = BitbucketClient(
            base_url=BITBUCKET_URL,
            project=BITBUCKET_PROJECT,
            repo=BITBUCKET_REPO,
            branch=BITBUCKET_BRANCH,
            values_path=BITBUCKET_VALUES_PATH,
            username=BITBUCKET_USERNAME,
            password=BITBUCKET_PASSWORD,
            email=BITBUCKET_EMAIL,
            verify_ssl=BITBUCKET_VERIFY_SSL
        )
        bitbucket_manager = ValuesFileManager(bitbucket_client)
        logger.info(f"[K8S_CONTROLLER] Bitbucket client initialized for {BITBUCKET_URL}/{BITBUCKET_PROJECT}/{BITBUCKET_REPO}")
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to initialize Bitbucket client: {e}")
        BITBUCKET_ENABLED = False


# ============================================================
# Data Classes
# ============================================================

@dataclass
class McpServerConfig:
    """Configuration for deploying an MCP server."""
    user_id: int
    username: str
    hostname_fqdn: str
    ida_port: int
    proxy_port: int
    mcp_version: str


@dataclass
class ProxyPortMapping:
    """Mapping of proxy port to upstream target."""
    proxy_port: int
    upstream_host: str
    upstream_port: int


# ============================================================
# Kubernetes Client Initialization
# ============================================================

_k8s_client = None
_k8s_apps_v1 = None
_k8s_core_v1 = None


def get_k8s_clients():
    """
    Initialize and return Kubernetes API clients.
    
    Supports both in-cluster and local kubeconfig authentication.
    """
    global _k8s_client, _k8s_apps_v1, _k8s_core_v1
    
    if _k8s_core_v1 is not None:
        return _k8s_core_v1, _k8s_apps_v1
    
    try:
        from kubernetes import client, config
        
        # Try in-cluster config first (when running in K8s)
        try:
            config.load_incluster_config()
            logger.info("[K8S_CONTROLLER] Loaded in-cluster Kubernetes config")
        except config.ConfigException:
            # Fall back to kubeconfig for local development
            config.load_kube_config()
            logger.info("[K8S_CONTROLLER] Loaded kubeconfig from default location")
        
        _k8s_core_v1 = client.CoreV1Api()
        _k8s_apps_v1 = client.AppsV1Api()
        
        return _k8s_core_v1, _k8s_apps_v1
        
    except ImportError:
        logger.warning("[K8S_CONTROLLER] kubernetes package not installed - K8s operations will be simulated")
        return None, None
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to initialize Kubernetes client: {e}")
        return None, None


# ============================================================
# MCP Server Pod Management
# ============================================================

def deploy_mcp_server(config: McpServerConfig) -> Tuple[bool, str, Optional[str]]:
    """
    Deploy an MCP server pod for a user.
    
    Args:
        config: MCP server configuration
        
    Returns:
        Tuple of (success, message, mcp_endpoint_url)
    """
    logger.info(f"[K8S_CONTROLLER] ========== DEPLOY MCP SERVER ==========")
    logger.info(f"[K8S_CONTROLLER] User: {config.user_id} ({config.username})")
    logger.info(f"[K8S_CONTROLLER] Target: {config.hostname_fqdn}:{config.ida_port}")
    logger.info(f"[K8S_CONTROLLER] Proxy port: {config.proxy_port}")
    logger.info(f"[K8S_CONTROLLER] MCP version: {config.mcp_version}")
    
    core_v1, apps_v1 = get_k8s_clients()
    
    if core_v1 is None:
        # Simulation mode for development
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - no actual K8s deployment")
        mcp_url = f"http://ida-proxy.{K8S_NAMESPACE}.svc.cluster.local:{config.proxy_port}/"
        return True, "Simulated deployment successful", mcp_url
    
    try:
        from kubernetes import client
        
        # Resource names
        deployment_name = f"mcp-server-user-{config.user_id}"
        service_name = f"mcp-server-user-{config.user_id}"
        
        # Labels for this user's resources
        labels = {
            "app": LABEL_APP,
            "component": LABEL_COMPONENT_MCP,
            "user-id": str(config.user_id),
            "username": config.username[:63],  # K8s label max length
        }
        
        # ============================================================
        # Create/Update Deployment
        # ============================================================
        
        # IDA Proxy service name (same namespace)
        ida_proxy_host = f"{IDA_PROXY_DEPLOYMENT}.{K8S_NAMESPACE}.svc.cluster.local"
        
        container = client.V1Container(
            name="mcp-server",
            image=f"{IDA_MCP_SERVER_IMAGE_REPO}:{config.mcp_version}",
            image_pull_policy="Always",  # Always pull to get latest fixes
            ports=[client.V1ContainerPort(container_port=IDA_MCP_SERVER_PORT)],
            env=[
                # Proxy connection - MCP server uses these to reach IDA via proxy
                client.V1EnvVar(name="IDA_PROXY_HOST", value=ida_proxy_host),
                client.V1EnvVar(name="IDA_PROXY_PORT", value=str(config.proxy_port)),
                # Original IDA info (for reference/logging)
                client.V1EnvVar(name="IDA_HOST", value=config.hostname_fqdn),
                client.V1EnvVar(name="IDA_PORT", value=str(config.ida_port)),
                # Server config
                client.V1EnvVar(name="SERVER_PORT", value=str(IDA_MCP_SERVER_PORT)),
                client.V1EnvVar(name="USER_ID", value=str(config.user_id)),
            ],
            resources=client.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "500m", "memory": "512Mi"}
            ),
            liveness_probe=client.V1Probe(
                tcp_socket=client.V1TCPSocketAction(port=IDA_MCP_SERVER_PORT),
                initial_delay_seconds=10,
                period_seconds=30
            ),
            readiness_probe=client.V1Probe(
                tcp_socket=client.V1TCPSocketAction(port=IDA_MCP_SERVER_PORT),
                initial_delay_seconds=5,
                period_seconds=10
            )
        )
        
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=labels),
            spec=client.V1PodSpec(containers=[container])
        )
        
        spec = client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=template
        )
        
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=deployment_name, labels=labels),
            spec=spec
        )
        
        # Check if deployment exists
        try:
            existing = apps_v1.read_namespaced_deployment(deployment_name, K8S_NAMESPACE)
            logger.info(f"[K8S_CONTROLLER] Updating existing deployment: {deployment_name}")
            apps_v1.replace_namespaced_deployment(deployment_name, K8S_NAMESPACE, deployment)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"[K8S_CONTROLLER] Creating new deployment: {deployment_name}")
                apps_v1.create_namespaced_deployment(K8S_NAMESPACE, deployment)
            else:
                raise
        
        # ============================================================
        # Create/Update Service (LoadBalancer with network labels)
        # ============================================================
        
        # Service labels include network-pool and Egress-policy
        service_labels = labels.copy()
        if IDA_MCP_SERVICE_NETWORK_POOL:
            service_labels["network-pool"] = IDA_MCP_SERVICE_NETWORK_POOL
        service_labels["Egress-policy"] = "enabled"
        
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=service_name, labels=service_labels),
            spec=client.V1ServiceSpec(
                type="LoadBalancer",
                selector=labels,
                ports=[client.V1ServicePort(port=IDA_MCP_SERVER_PORT, target_port=IDA_MCP_SERVER_PORT)]
            )
        )
        
        try:
            existing = core_v1.read_namespaced_service(service_name, K8S_NAMESPACE)
            logger.info(f"[K8S_CONTROLLER] Updating existing service: {service_name}")
            # Services need special handling - delete and recreate
            core_v1.delete_namespaced_service(service_name, K8S_NAMESPACE)
            core_v1.create_namespaced_service(K8S_NAMESPACE, service)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                logger.info(f"[K8S_CONTROLLER] Creating new service: {service_name}")
                core_v1.create_namespaced_service(K8S_NAMESPACE, service)
            else:
                raise
        
        # ============================================================
        # Update Proxy Configuration
        # ============================================================
        
        success, msg = update_proxy_config_add(
            proxy_port=config.proxy_port, 
            upstream_host=config.hostname_fqdn, 
            upstream_port=config.ida_port,
            user_id=config.user_id,
            username=config.username
        )
        if not success:
            logger.error(f"[K8S_CONTROLLER] Failed to update proxy config: {msg}")
            # Continue anyway - MCP server is deployed
        
        # Reload nginx
        reload_success, reload_msg = reload_nginx_proxy()
        if not reload_success:
            logger.warning(f"[K8S_CONTROLLER] Failed to reload nginx: {reload_msg}")
        
        # Generate MCP endpoint URL - points to the MCP Server Service (for OpenWebUI)
        # OpenWebUI → MCP Server Service → MCP Server Pod → ida-proxy → developer workstation
        mcp_url = f"http://{service_name}.{K8S_NAMESPACE}.svc.cluster.local:{IDA_MCP_SERVER_PORT}/"
        
        # Also log the proxy URL for direct testing
        proxy_test_url = f"http://{IDA_PROXY_DEPLOYMENT}.{K8S_NAMESPACE}.svc.cluster.local:{config.proxy_port}/"
        
        logger.info(f"[K8S_CONTROLLER] ========== DEPLOY SUCCESS ==========")
        logger.info(f"[K8S_CONTROLLER] MCP URL (for OpenWebUI): {mcp_url}")
        logger.info(f"[K8S_CONTROLLER] Proxy URL (for direct testing): {proxy_test_url}")
        
        return True, f"MCP server deployed successfully", mcp_url
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to deploy MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, f"Deployment failed: {str(e)}", None


def delete_mcp_server(user_id: int, proxy_port: int) -> Tuple[bool, str]:
    """
    Delete an MCP server pod for a user.
    
    Args:
        user_id: User ID
        proxy_port: Allocated proxy port to remove
        
    Returns:
        Tuple of (success, message)
    """
    logger.info(f"[K8S_CONTROLLER] ========== DELETE MCP SERVER ==========")
    logger.info(f"[K8S_CONTROLLER] User: {user_id}")
    logger.info(f"[K8S_CONTROLLER] Proxy port: {proxy_port}")
    
    core_v1, apps_v1 = get_k8s_clients()
    
    if core_v1 is None:
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - no actual K8s deletion")
        return True, "Simulated deletion successful"
    
    try:
        from kubernetes import client
        
        deployment_name = f"mcp-server-user-{user_id}"
        service_name = f"mcp-server-user-{user_id}"
        
        # Delete deployment
        try:
            apps_v1.delete_namespaced_deployment(deployment_name, K8S_NAMESPACE)
            logger.info(f"[K8S_CONTROLLER] Deleted deployment: {deployment_name}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                raise
            logger.warning(f"[K8S_CONTROLLER] Deployment not found: {deployment_name}")
        
        # Delete service
        try:
            core_v1.delete_namespaced_service(service_name, K8S_NAMESPACE)
            logger.info(f"[K8S_CONTROLLER] Deleted service: {service_name}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                raise
            logger.warning(f"[K8S_CONTROLLER] Service not found: {service_name}")
        
        # Update proxy configuration
        if proxy_port:
            success, msg = update_proxy_config_remove(proxy_port)
            if not success:
                logger.error(f"[K8S_CONTROLLER] Failed to update proxy config: {msg}")
            
            # Reload nginx
            reload_success, reload_msg = reload_nginx_proxy()
            if not reload_success:
                logger.warning(f"[K8S_CONTROLLER] Failed to reload nginx: {reload_msg}")
        
        logger.info(f"[K8S_CONTROLLER] ========== DELETE SUCCESS ==========")
        return True, "MCP server deleted successfully"
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to delete MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, f"Deletion failed: {str(e)}"


def upgrade_mcp_server(user_id: int, new_version: str) -> Tuple[bool, str]:
    """
    Upgrade an MCP server to a new version.
    
    Args:
        user_id: User ID
        new_version: New MCP server version/image tag
        
    Returns:
        Tuple of (success, message)
    """
    logger.info(f"[K8S_CONTROLLER] ========== UPGRADE MCP SERVER ==========")
    logger.info(f"[K8S_CONTROLLER] User: {user_id}")
    logger.info(f"[K8S_CONTROLLER] New version: {new_version}")
    
    core_v1, apps_v1 = get_k8s_clients()
    
    if core_v1 is None:
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - no actual K8s upgrade")
        return True, "Simulated upgrade successful"
    
    try:
        from kubernetes import client
        
        deployment_name = f"mcp-server-user-{user_id}"
        
        # Get existing deployment
        deployment = apps_v1.read_namespaced_deployment(deployment_name, K8S_NAMESPACE)
        
        # Update image tag
        old_image = deployment.spec.template.spec.containers[0].image
        new_image = f"{IDA_MCP_SERVER_IMAGE_REPO}:{new_version}"
        deployment.spec.template.spec.containers[0].image = new_image
        
        logger.info(f"[K8S_CONTROLLER] Upgrading from {old_image} to {new_image}")
        
        # Apply update
        apps_v1.replace_namespaced_deployment(deployment_name, K8S_NAMESPACE, deployment)
        
        logger.info(f"[K8S_CONTROLLER] ========== UPGRADE SUCCESS ==========")
        return True, f"MCP server upgraded to {new_version}"
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to upgrade MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, f"Upgrade failed: {str(e)}"


# ============================================================
# Nginx Proxy ConfigMap Management
# ============================================================

def get_proxy_config() -> Tuple[Dict[int, str], List[int]]:
    """
    Get current proxy configuration from ConfigMaps.
    
    Returns:
        Tuple of (port_mappings dict, listen_ports list)
    """
    core_v1, _ = get_k8s_clients()
    
    if core_v1 is None:
        return {}, []
    
    try:
        # Get port map ConfigMap
        port_map_cm = core_v1.read_namespaced_config_map(IDA_PROXY_CONFIGMAP_MAP, K8S_NAMESPACE)
        port_map_data = port_map_cm.data.get("port_map.conf", "")
        
        # Parse port mappings
        port_mappings = {}
        for line in port_map_data.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.rstrip(";").split()
                if len(parts) >= 2:
                    try:
                        port = int(parts[0])
                        upstream = parts[1]
                        port_mappings[port] = upstream
                    except ValueError:
                        continue
        
        # Get listen ports ConfigMap
        listen_cm = core_v1.read_namespaced_config_map(IDA_PROXY_CONFIGMAP_PORTS, K8S_NAMESPACE)
        listen_data = listen_cm.data.get("listen_ports.conf", "")
        
        # Parse listen ports
        listen_ports = []
        for line in listen_data.strip().split("\n"):
            line = line.strip()
            if line.startswith("listen "):
                try:
                    port = int(line.replace("listen ", "").rstrip(";"))
                    listen_ports.append(port)
                except ValueError:
                    continue
        
        return port_mappings, listen_ports
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to get proxy config: {e}")
        return {}, []


def update_proxy_config_add(
    proxy_port: int, 
    upstream_host: str, 
    upstream_port: int,
    user_id: Optional[int] = None,
    username: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Add a new port mapping to the proxy configuration.
    
    If Bitbucket GitOps is enabled, updates the values file in Bitbucket
    and lets ArgoCD sync the changes. Otherwise, updates ConfigMaps directly.
    
    Args:
        proxy_port: Port the proxy listens on
        upstream_host: Target hostname (user's workstation FQDN)
        upstream_port: Target port (IDA plugin port)
        user_id: User ID (used for GitOps tracking)
        username: Username (used for GitOps tracking)
        
    Returns:
        Tuple of (success, message)
    """
    logger.info(f"[K8S_CONTROLLER] Adding proxy mapping: {proxy_port} -> {upstream_host}:{upstream_port}")
    
    # Use Bitbucket GitOps if enabled
    if BITBUCKET_ENABLED and bitbucket_manager is not None:
        logger.info("[K8S_CONTROLLER] Using Bitbucket GitOps for proxy config update")
        try:
            success, message = bitbucket_manager.add_port_mapping(
                proxy_port=proxy_port,
                upstream_host=upstream_host,
                upstream_port=upstream_port,
                user_id=user_id or 0,
                username=username or "unknown"
            )
            if success:
                logger.info(f"[K8S_CONTROLLER] Port mapping added via Bitbucket. ArgoCD will sync.")
            return success, message
        except Exception as e:
            logger.error(f"[K8S_CONTROLLER] Bitbucket update failed: {e}")
            return False, f"Bitbucket update failed: {e}"
    
    # Direct ConfigMap update (non-GitOps mode)
    core_v1, _ = get_k8s_clients()
    
    if core_v1 is None:
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - proxy config not updated")
        return True, "Simulated config update"
    
    try:
        # Get current config
        port_mappings, listen_ports = get_proxy_config()
        
        # Add new mapping
        port_mappings[proxy_port] = f"{upstream_host}:{upstream_port}"
        if proxy_port not in listen_ports:
            listen_ports.append(proxy_port)
        
        # Update ConfigMaps
        return _write_proxy_config(port_mappings, listen_ports)
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to add proxy mapping: {e}")
        return False, str(e)


def update_proxy_config_remove(proxy_port: int) -> Tuple[bool, str]:
    """
    Remove a port mapping from the proxy configuration.
    
    If Bitbucket GitOps is enabled, updates the values file in Bitbucket
    and lets ArgoCD sync the changes. Otherwise, updates ConfigMaps directly.
    
    Args:
        proxy_port: Port to remove
        
    Returns:
        Tuple of (success, message)
    """
    logger.info(f"[K8S_CONTROLLER] Removing proxy mapping for port: {proxy_port}")
    
    # Use Bitbucket GitOps if enabled
    if BITBUCKET_ENABLED and bitbucket_manager is not None:
        logger.info("[K8S_CONTROLLER] Using Bitbucket GitOps for proxy config removal")
        try:
            success, message = bitbucket_manager.remove_port_mapping(proxy_port)
            if success:
                logger.info(f"[K8S_CONTROLLER] Port mapping removed via Bitbucket. ArgoCD will sync.")
            return success, message
        except Exception as e:
            logger.error(f"[K8S_CONTROLLER] Bitbucket update failed: {e}")
            return False, f"Bitbucket update failed: {e}"
    
    # Direct ConfigMap update (non-GitOps mode)
    core_v1, _ = get_k8s_clients()
    
    if core_v1 is None:
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - proxy config not updated")
        return True, "Simulated config removal"
    
    try:
        # Get current config
        port_mappings, listen_ports = get_proxy_config()
        
        # Remove mapping
        if proxy_port in port_mappings:
            del port_mappings[proxy_port]
        if proxy_port in listen_ports:
            listen_ports.remove(proxy_port)
        
        # Update ConfigMaps
        return _write_proxy_config(port_mappings, listen_ports)
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to remove proxy mapping: {e}")
        return False, str(e)


def _write_proxy_config(port_mappings: Dict[int, str], listen_ports: List[int]) -> Tuple[bool, str]:
    """
    Write proxy configuration to ConfigMaps.
    
    Args:
        port_mappings: Dict of proxy_port -> upstream
        listen_ports: List of ports to listen on
        
    Returns:
        Tuple of (success, message)
    """
    core_v1, _ = get_k8s_clients()
    
    if core_v1 is None:
        return False, "K8s client not available"
    
    try:
        from kubernetes import client
        
        # Generate port_map.conf content
        port_map_lines = ["# PROXY_PORT   UPSTREAM_HOST:UPSTREAM_PORT;"]
        port_map_lines.append("# Auto-generated by MCP Client - do not edit manually")
        port_map_lines.append(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        port_map_lines.append("")
        for port in sorted(port_mappings.keys()):
            upstream = port_mappings[port]
            port_map_lines.append(f"{port}          {upstream};")
        port_map_content = "\n".join(port_map_lines)
        
        # Generate listen_ports.conf content
        listen_lines = ["# Auto-generated by MCP Client - do not edit manually"]
        listen_lines.append(f"# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        listen_lines.append("")
        for port in sorted(listen_ports):
            listen_lines.append(f"listen {port};")
        listen_content = "\n".join(listen_lines)
        
        logger.debug(f"[K8S_CONTROLLER] port_map.conf:\n{port_map_content}")
        logger.debug(f"[K8S_CONTROLLER] listen_ports.conf:\n{listen_content}")
        
        # Update port map ConfigMap
        port_map_cm = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(
                name=IDA_PROXY_CONFIGMAP_MAP,
                labels={"app": LABEL_APP, "component": LABEL_COMPONENT_PROXY}
            ),
            data={"port_map.conf": port_map_content}
        )
        
        try:
            core_v1.replace_namespaced_config_map(IDA_PROXY_CONFIGMAP_MAP, K8S_NAMESPACE, port_map_cm)
            logger.info(f"[K8S_CONTROLLER] Updated ConfigMap: {IDA_PROXY_CONFIGMAP_MAP}")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                core_v1.create_namespaced_config_map(K8S_NAMESPACE, port_map_cm)
                logger.info(f"[K8S_CONTROLLER] Created ConfigMap: {IDA_PROXY_CONFIGMAP_MAP}")
            else:
                raise
        
        # Update listen ports ConfigMap
        listen_cm = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(
                name=IDA_PROXY_CONFIGMAP_PORTS,
                labels={"app": LABEL_APP, "component": LABEL_COMPONENT_PROXY}
            ),
            data={"listen_ports.conf": listen_content}
        )
        
        try:
            core_v1.replace_namespaced_config_map(IDA_PROXY_CONFIGMAP_PORTS, K8S_NAMESPACE, listen_cm)
            logger.info(f"[K8S_CONTROLLER] Updated ConfigMap: {IDA_PROXY_CONFIGMAP_PORTS}")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                core_v1.create_namespaced_config_map(K8S_NAMESPACE, listen_cm)
                logger.info(f"[K8S_CONTROLLER] Created ConfigMap: {IDA_PROXY_CONFIGMAP_PORTS}")
            else:
                raise
        
        return True, "Proxy config updated"
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to write proxy config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, str(e)


# ============================================================
# Nginx Proxy Reload
# ============================================================

def reload_nginx_proxy() -> Tuple[bool, str]:
    """
    Reload nginx to pick up configuration changes.
    
    This uses kubectl exec to send SIGHUP to nginx, which causes
    it to reload configuration without dropping connections.
    
    Alternative: Could also do a rolling restart of the deployment.
    
    Returns:
        Tuple of (success, message)
    """
    logger.info(f"[K8S_CONTROLLER] Reloading nginx proxy")
    
    core_v1, apps_v1 = get_k8s_clients()
    
    if core_v1 is None:
        logger.warning("[K8S_CONTROLLER] Running in simulation mode - nginx not reloaded")
        return True, "Simulated nginx reload"
    
    try:
        from kubernetes import client
        from kubernetes.stream import stream
        
        # Find nginx pod
        pods = core_v1.list_namespaced_pod(
            K8S_NAMESPACE,
            label_selector=f"app={LABEL_APP},component={LABEL_COMPONENT_PROXY}"
        )
        
        if not pods.items:
            logger.warning(f"[K8S_CONTROLLER] No nginx proxy pods found")
            return False, "No nginx proxy pods found"
        
        pod_name = pods.items[0].metadata.name
        logger.info(f"[K8S_CONTROLLER] Found nginx pod: {pod_name}")
        
        # Execute nginx reload command
        # nginx -s reload sends SIGHUP which reloads config
        exec_command = ["nginx", "-s", "reload"]
        
        resp = stream(
            core_v1.connect_get_namespaced_pod_exec,
            pod_name,
            K8S_NAMESPACE,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )
        
        logger.info(f"[K8S_CONTROLLER] Nginx reload response: {resp}")
        return True, "Nginx reloaded successfully"
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to reload nginx: {e}")
        
        # Fallback: restart the deployment
        logger.info("[K8S_CONTROLLER] Attempting fallback: restart deployment")
        try:
            return _restart_nginx_deployment()
        except Exception as e2:
            logger.error(f"[K8S_CONTROLLER] Fallback restart also failed: {e2}")
            return False, f"Reload failed: {str(e)}, Restart also failed: {str(e2)}"


def _restart_nginx_deployment() -> Tuple[bool, str]:
    """
    Restart nginx deployment by updating an annotation.
    
    This triggers a rolling restart which ensures the new
    ConfigMap values are mounted.
    """
    _, apps_v1 = get_k8s_clients()
    
    if apps_v1 is None:
        return False, "K8s client not available"
    
    try:
        from kubernetes import client
        
        # Get deployment
        deployment = apps_v1.read_namespaced_deployment(IDA_PROXY_DEPLOYMENT, K8S_NAMESPACE)
        
        # Add/update restart annotation
        if deployment.spec.template.metadata.annotations is None:
            deployment.spec.template.metadata.annotations = {}
        
        deployment.spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] = \
            time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Apply update
        apps_v1.replace_namespaced_deployment(IDA_PROXY_DEPLOYMENT, K8S_NAMESPACE, deployment)
        
        logger.info(f"[K8S_CONTROLLER] Restarted deployment: {IDA_PROXY_DEPLOYMENT}")
        return True, "Nginx deployment restarted"
        
    except Exception as e:
        logger.error(f"[K8S_CONTROLLER] Failed to restart nginx deployment: {e}")
        return False, str(e)


# ============================================================
# Status and Health Check Functions
# ============================================================

def get_mcp_server_status(user_id: int) -> Dict:
    """
    Get the status of a user's MCP server deployment.
    
    Returns:
        Dict with status information
    """
    core_v1, apps_v1 = get_k8s_clients()
    
    if core_v1 is None:
        return {"status": "unknown", "message": "K8s client not available (simulation mode)"}
    
    try:
        deployment_name = f"mcp-server-user-{user_id}"
        
        deployment = apps_v1.read_namespaced_deployment(deployment_name, K8S_NAMESPACE)
        
        ready_replicas = deployment.status.ready_replicas or 0
        desired_replicas = deployment.spec.replicas or 1
        
        if ready_replicas >= desired_replicas:
            status = "running"
            message = "MCP server is running"
        elif ready_replicas > 0:
            status = "partial"
            message = f"MCP server partially ready ({ready_replicas}/{desired_replicas})"
        else:
            status = "pending"
            message = "MCP server is starting..."
        
        return {
            "status": status,
            "message": message,
            "ready_replicas": ready_replicas,
            "desired_replicas": desired_replicas,
            "image": deployment.spec.template.spec.containers[0].image
        }
        
    except Exception as e:
        if "404" in str(e):
            return {"status": "not_found", "message": "MCP server not deployed"}
        return {"status": "error", "message": str(e)}


def health_check() -> Dict:
    """
    Check the health of the K8s controller and proxy.
    
    Returns:
        Dict with health status
    """
    core_v1, apps_v1 = get_k8s_clients()
    
    result = {
        "k8s_connected": core_v1 is not None,
        "proxy_status": "unknown",
        "namespace": K8S_NAMESPACE
    }
    
    if core_v1 is None:
        result["proxy_status"] = "simulation_mode"
        return result
    
    try:
        # Check proxy deployment
        deployment = apps_v1.read_namespaced_deployment(IDA_PROXY_DEPLOYMENT, K8S_NAMESPACE)
        ready = deployment.status.ready_replicas or 0
        
        if ready > 0:
            result["proxy_status"] = "running"
        else:
            result["proxy_status"] = "not_ready"
            
    except Exception as e:
        result["proxy_status"] = f"error: {str(e)}"
    
    return result
