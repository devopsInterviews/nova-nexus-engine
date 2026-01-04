"""
Bitbucket API Client for managing Helm values files.

This module provides functionality to:
1. Read values files from Bitbucket repository
2. Update port mappings in the values file
3. Commit changes back to Bitbucket

This enables GitOps workflow where ArgoCD syncs changes from git.
Uses atlassian-python-api library for cleaner Bitbucket integration.
"""

import os
import logging
import yaml
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    from atlassian import Bitbucket
except ImportError:
    Bitbucket = None
    logging.warning("atlassian-python-api not installed. Install with: pip install atlassian-python-api")

logger = logging.getLogger("uvicorn.error")

# ============================================================
# Configuration
# ============================================================

BITBUCKET_ENABLED = os.getenv("BITBUCKET_ENABLED", "false").lower() == "true"
BITBUCKET_URL = os.getenv("BITBUCKET_URL", "")  # e.g., https://bitbucket.example.com
BITBUCKET_PROJECT = os.getenv("BITBUCKET_PROJECT", "")  # e.g., "MYPROJECT"
BITBUCKET_REPO = os.getenv("BITBUCKET_REPO", "")  # e.g., "helm-values"
BITBUCKET_BRANCH = os.getenv("BITBUCKET_BRANCH", "main")
BITBUCKET_VALUES_PATH = os.getenv("BITBUCKET_VALUES_PATH", "")  # e.g., "charts/mcp-client/values.yaml"
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME", "")
BITBUCKET_PASSWORD = os.getenv("BITBUCKET_PASSWORD", "")  # App password or access token
BITBUCKET_VERIFY_SSL = os.getenv("BITBUCKET_VERIFY_SSL", "true").lower() == "true"  # Set to false for self-signed certs

logger.info(f"[BITBUCKET] Enabled: {BITBUCKET_ENABLED}")
if BITBUCKET_ENABLED:
    logger.info(f"[BITBUCKET] URL: {BITBUCKET_URL}")
    logger.info(f"[BITBUCKET] Project: {BITBUCKET_PROJECT}, Repo: {BITBUCKET_REPO}")
    logger.info(f"[BITBUCKET] Branch: {BITBUCKET_BRANCH}, Path: {BITBUCKET_VALUES_PATH}")
    logger.info(f"[BITBUCKET] SSL Verification: {BITBUCKET_VERIFY_SSL}")


# ============================================================
# Data Classes
# ============================================================

@dataclass
class PortMapping:
    """Represents a port mapping for the IDA proxy."""
    proxy_port: int
    upstream_host: str
    upstream_port: int
    user_id: Optional[int] = None
    username: Optional[str] = None


@dataclass
class BitbucketConfig:
    """Configuration for Bitbucket client initialization."""
    base_url: str
    project: str
    repo: str
    branch: str = "main"
    values_path: str = "values.yaml"
    username: str = ""
    password: str = ""
    verify_ssl: bool = True


# ============================================================
# Bitbucket API Client (using atlassian-python-api)
# ============================================================

class BitbucketClient:
    """Client for interacting with Bitbucket Server using atlassian-python-api."""
    
    def __init__(
        self,
        base_url: str = BITBUCKET_URL,
        project: str = BITBUCKET_PROJECT,
        repo: str = BITBUCKET_REPO,
        branch: str = BITBUCKET_BRANCH,
        values_path: str = BITBUCKET_VALUES_PATH,
        username: str = BITBUCKET_USERNAME,
        password: str = BITBUCKET_PASSWORD,
        verify_ssl: bool = BITBUCKET_VERIFY_SSL
    ):
        if Bitbucket is None:
            raise ImportError("atlassian-python-api is required. Install with: pip install atlassian-python-api")
        
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.repo = repo
        self.branch = branch
        self.values_path = values_path
        self.verify_ssl = verify_ssl
        
        # Initialize Bitbucket client from atlassian-python-api
        self.bitbucket = Bitbucket(
            url=self.base_url,
            username=username,
            password=password,
            verify_ssl=verify_ssl
        )
        
        if not verify_ssl:
            logger.warning(f"[BITBUCKET] SSL verification is DISABLED for {project}/{repo}")
        logger.info(f"[BITBUCKET] Initialized client for {project}/{repo}")
    
    def get_file_content(self, fetch_commit_id: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the content of the values file from Bitbucket.
        
        Args:
            fetch_commit_id: If True, also fetch the latest commit ID (extra API call).
                           Only needed when you plan to update the file for conflict detection.
        
        Returns:
            Tuple of (content, commit_id) or (None, None) on error
        """
        try:
            logger.info(f"[BITBUCKET] Fetching file: {self.values_path} from {self.project}/{self.repo} (branch: {self.branch})")
            
            # Get file content using atlassian-python-api
            # Correct parameters: project_key, repository_slug, filename, at, markup
            content = self.bitbucket.get_content_of_file(
                project_key=self.project,
                repository_slug=self.repo,
                filename=self.values_path,
                at=f"refs/heads/{self.branch}"
            )
            
            if content:
                commit_id = None
                
                # Only fetch commit ID if explicitly requested (for updates/conflict detection)
                if fetch_commit_id:
                    try:
                        commits_response = self.bitbucket.get_commits(
                            project_key=self.project,
                            repository_slug=self.repo,
                            hash_oldest=None,
                            hash_newest=self.branch,
                            limit=1
                        )
                        # Handle generator or dict response
                        if hasattr(commits_response, '__iter__') and not isinstance(commits_response, (dict, str)):
                            commits = list(commits_response)
                        elif isinstance(commits_response, dict):
                            commits = commits_response.get('values', [])
                        else:
                            commits = []
                        
                        commit_id = commits[0]['id'] if commits and len(commits) > 0 else None
                    except Exception as e:
                        logger.warning(f"[BITBUCKET] Could not fetch commit ID: {e}")
                        commit_id = None
                
                logger.info(f"[BITBUCKET] Successfully fetched file from branch '{self.branch}'{f' (commit: {commit_id})' if commit_id else ''}")
                return content, commit_id
            else:
                logger.error(f"[BITBUCKET] File not found or empty: {self.values_path}")
                return None, None
                
        except Exception as e:
            logger.error(f"[BITBUCKET] Error fetching file from {self.project}/{self.repo} (branch: {self.branch}): {e}")
            return None, None
    
    def update_file(self, content: str, commit_message: str, source_commit_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Update the values file in Bitbucket with new content.
        
        Args:
            content: New file content
            commit_message: Commit message
            source_commit_id: Optional base commit ID for conflict detection
            
        Returns:
            Tuple of (success, message or commit_id)
        """
        try:
            logger.info(f"[BITBUCKET] Updating file: {self.values_path} in {self.project}/{self.repo} (branch: {self.branch})")
            logger.debug(f"[BITBUCKET] Commit message: {commit_message}")
            
            # Update file using atlassian-python-api
            # Correct parameters: project_key, repository_slug, content, message, branch, filename, source_commit_id
            result = self.bitbucket.update_file(
                project_key=self.project,
                repository_slug=self.repo,
                content=content,
                message=commit_message,
                branch=self.branch,
                filename=self.values_path,
                source_commit_id=source_commit_id
            )
            
            # Extract commit ID from result
            commit_id = result.get('id') if isinstance(result, dict) else str(result)
            
            logger.info(f"[BITBUCKET] File updated successfully in branch '{self.branch}'. Commit: {commit_id}")
            return True, commit_id
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[BITBUCKET] Error updating file in {self.project}/{self.repo} (branch: {self.branch}): {error_msg}")
            
            # Handle common errors
            if "409" in error_msg or "conflict" in error_msg.lower():
                return False, "Conflict: File was modified by someone else. Please retry."
            elif "404" in error_msg:
                return False, "File or repository not found"
            elif "401" in error_msg or "403" in error_msg:
                return False, "Authentication failed. Check credentials."
            else:
                return False, f"Update failed: {error_msg}"


# ============================================================
# Values File Manager
# ============================================================

class ValuesFileManager:
    """Manages the Helm values file for port mappings."""
    
    def __init__(self, client: Optional[BitbucketClient] = None):
        self.client = client or BitbucketClient()
        self._cached_content: Optional[str] = None
    
    def get_port_mappings(self) -> List[PortMapping]:
        """
        Get current port mappings from the values file.
        
        Returns:
            List of PortMapping objects
        """
        content, _ = self.client.get_file_content()
        
        if content is None:
            logger.warning("[BITBUCKET] Could not fetch values file, returning empty mappings")
            return []
        
        self._cached_content = content

        
        try:
            values = yaml.safe_load(content)
            
            # Navigate to idaProxy.portMappings
            ida_proxy = values.get("idaProxy", {})
            mappings_list = ida_proxy.get("portMappings", [])
            
            mappings = []
            for m in mappings_list:
                mappings.append(PortMapping(
                    proxy_port=m.get("proxyPort"),
                    upstream_host=m.get("upstreamHost"),
                    upstream_port=m.get("upstreamPort"),
                    user_id=m.get("userId"),
                    username=m.get("username")
                ))
            
            logger.info(f"[BITBUCKET] Found {len(mappings)} port mappings")
            return mappings
            
        except yaml.YAMLError as e:
            logger.error(f"[BITBUCKET] Error parsing YAML: {e}")
            return []
    
    def add_port_mapping(
        self,
        proxy_port: int,
        upstream_host: str,
        upstream_port: int,
        user_id: int,
        username: str
    ) -> Tuple[bool, str]:
        """
        Add a new port mapping to the values file.
        
        Args:
            proxy_port: Port the proxy listens on
            upstream_host: Target hostname (user's workstation)
            upstream_port: Target port (IDA plugin port)
            user_id: User ID
            username: Username
            
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"[BITBUCKET] Adding port mapping: {proxy_port} -> {upstream_host}:{upstream_port}")
        
        # Fetch current content
        content, _ = self.client.get_file_content()
        
        if content is None:
            return False, "Could not fetch values file"
        
        try:
            values = yaml.safe_load(content)
            
            # Ensure idaProxy.portMappings exists
            if "idaProxy" not in values:
                values["idaProxy"] = {}
            if "portMappings" not in values["idaProxy"]:
                values["idaProxy"]["portMappings"] = []
            
            # Check if port already exists
            for m in values["idaProxy"]["portMappings"]:
                if m.get("proxyPort") == proxy_port:
                    # Update existing mapping
                    m["upstreamHost"] = upstream_host
                    m["upstreamPort"] = upstream_port
                    m["userId"] = user_id
                    m["username"] = username
                    break
            else:
                # Add new mapping
                values["idaProxy"]["portMappings"].append({
                    "proxyPort": proxy_port,
                    "upstreamHost": upstream_host,
                    "upstreamPort": upstream_port,
                    "userId": user_id,
                    "username": username
                })
            
            # Sort by proxy port for consistency
            values["idaProxy"]["portMappings"].sort(key=lambda x: x.get("proxyPort", 0))
            
            # Serialize back to YAML
            new_content = yaml.dump(values, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # Commit to Bitbucket (let Bitbucket handle conflicts)
            commit_message = f"[MCP-Client] Add port mapping {proxy_port} for user {username}"
            return self.client.update_file(new_content, commit_message, None)
            
        except yaml.YAMLError as e:
            error_msg = f"Error parsing/generating YAML: {e}"
            logger.error(f"[BITBUCKET] {error_msg}")
            return False, error_msg
    
    def remove_port_mapping(self, proxy_port: int) -> Tuple[bool, str]:
        """
        Remove a port mapping from the values file.
        
        Args:
            proxy_port: Port to remove
            
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"[BITBUCKET] Removing port mapping for port: {proxy_port}")
        
        # Fetch current content with commit ID for conflict detection
        content, commit_id = self.client.get_file_content(fetch_commit_id=True)
        
        if content is None:
            return False, "Could not fetch values file"
        
        try:
            values = yaml.safe_load(content)
            
            # Get current mappings
            ida_proxy = values.get("idaProxy", {})
            mappings = ida_proxy.get("portMappings", [])
            
            # Filter out the port to remove
            original_count = len(mappings)
            mappings = [m for m in mappings if m.get("proxyPort") != proxy_port]
            
            if len(mappings) == original_count:
                logger.warning(f"[BITBUCKET] Port {proxy_port} not found in mappings")
                return True, "Port not found (already removed)"
            
            values["idaProxy"]["portMappings"] = mappings
            
            # Serialize back to YAML
            new_content = yaml.dump(values, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # Commit to Bitbucket (let Bitbucket handle conflicts)
            commit_message = f"[MCP-Client] Remove port mapping {proxy_port}"
            return self.client.update_file(new_content, commit_message, None)
            
        except yaml.YAMLError as e:
            error_msg = f"Error parsing/generating YAML: {e}"
            logger.error(f"[BITBUCKET] {error_msg}")
            return False, error_msg


# ============================================================
# Module-level instance
# ============================================================

# Create a singleton instance for use throughout the app
_values_manager: Optional[ValuesFileManager] = None

def get_values_manager() -> ValuesFileManager:
    """Get the singleton ValuesFileManager instance."""
    global _values_manager
    if _values_manager is None:
        _values_manager = ValuesFileManager()
    return _values_manager


def is_bitbucket_enabled() -> bool:
    """Check if Bitbucket integration is enabled."""
    return BITBUCKET_ENABLED
