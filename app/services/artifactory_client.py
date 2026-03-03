"""
Artifactory API Client for fetching Docker image versions.

This module provides functionality to:
1. Connect to JFrog Artifactory
2. Fetch Docker image tags from a repository using Docker Registry V2 API
3. Cache results to minimize API calls

Uses the requests library for REST API calls.
"""

import os
import re
import logging
import time
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("uvicorn.error")

# ============================================================
# Configuration
# ============================================================

ARTIFACTORY_ENABLED = os.getenv("ARTIFACTORY_ENABLED", "false").lower() == "true"
ARTIFACTORY_URL = os.getenv("ARTIFACTORY_URL", "")  # e.g., https://artifactory.company.internal
ARTIFACTORY_REPO = os.getenv("ARTIFACTORY_REPO", "docker-local")  # Docker repository name
ARTIFACTORY_IMAGE = os.getenv("ARTIFACTORY_IMAGE", "ida-pro-mcp")  # Image name (can include path like "repo/image")

# PyPI specific configuration in Artifactory
ARTIFACTORY_PYPI_REPO = os.getenv("ARTIFACTORY_PYPI_REPO", "pypi-local")
ARTIFACTORY_PYPI_PACKAGE = os.getenv("ARTIFACTORY_PYPI_PACKAGE", "ida-pro-mcp")

ARTIFACTORY_USERNAME = os.getenv("ARTIFACTORY_USERNAME", "")
ARTIFACTORY_PASSWORD = os.getenv("ARTIFACTORY_PASSWORD", "")  # API key or password
ARTIFACTORY_VERIFY_SSL = os.getenv("ARTIFACTORY_VERIFY_SSL", "true").lower() == "true"

# Cache configuration
CACHE_TTL_SECONDS = int(os.getenv("ARTIFACTORY_CACHE_TTL", "300"))  # 5 minutes default

# Fallback versions if Artifactory is not available
FALLBACK_VERSIONS = os.getenv("FALLBACK_MCP_VERSIONS", "v1.0.0,latest").split(",")
FALLBACK_VERSIONS = [v.strip() for v in FALLBACK_VERSIONS if v.strip()]

logger.info(f"[ARTIFACTORY] Enabled: {ARTIFACTORY_ENABLED}")
if ARTIFACTORY_ENABLED:
    logger.info(f"[ARTIFACTORY] URL: {ARTIFACTORY_URL}")
    logger.info(f"[ARTIFACTORY] Repo: {ARTIFACTORY_REPO}, Image: {ARTIFACTORY_IMAGE}")
    logger.info(f"[ARTIFACTORY] SSL Verification: {ARTIFACTORY_VERIFY_SSL}")
    logger.info(f"[ARTIFACTORY] Cache TTL: {CACHE_TTL_SECONDS}s")


# ============================================================
# Version Cache
# ============================================================

class VersionCache:
    """Simple in-memory cache for Docker image versions."""
    
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._versions: List[str] = []
        self._last_fetch: float = 0
        self._ttl = ttl_seconds
    
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._versions:
            return False
        return (time.time() - self._last_fetch) < self._ttl
    
    def get(self) -> List[str]:
        """Get cached versions."""
        return self._versions.copy()
    
    def set(self, versions: List[str]):
        """Update cache with new versions."""
        self._versions = versions.copy()
        self._last_fetch = time.time()
        logger.debug(f"[ARTIFACTORY] Cached {len(versions)} versions")
    
    def invalidate(self):
        """Clear the cache."""
        self._versions = []
        self._last_fetch = 0


# Global cache instance
_version_cache = VersionCache()


# ============================================================
# Artifactory API Client
# ============================================================

@dataclass
class ArtifactoryConfig:
    """Configuration for Artifactory client."""
    url: str
    repo: str
    image: str
    username: str = ""
    password: str = ""
    verify_ssl: bool = True


class ArtifactoryClient:
    """
    Client for fetching Docker image tags from JFrog Artifactory.
    
    Uses the Docker Registry V2 API:
    GET /artifactory/api/docker/<repo>/v2/<image>/tags/list
    """
    
    def __init__(
        self,
        url: str = ARTIFACTORY_URL,
        repo: str = ARTIFACTORY_REPO,
        image: str = ARTIFACTORY_IMAGE,
        username: str = ARTIFACTORY_USERNAME,
        password: str = ARTIFACTORY_PASSWORD,
        verify_ssl: bool = ARTIFACTORY_VERIFY_SSL,
        pypi_repo: str = ARTIFACTORY_PYPI_REPO,
        pypi_package: str = ARTIFACTORY_PYPI_PACKAGE
    ):
        # Normalize URL - remove trailing slash and /artifactory suffix if present
        # This ensures consistent URL construction
        self.base_url = url.rstrip("/")
        if self.base_url.endswith("/artifactory"):
            self.base_url = self.base_url[:-12]  # Remove /artifactory
        
        self.repo = repo
        self.image = image
        self.pypi_repo = pypi_repo
        self.pypi_package = pypi_package
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        
        if not verify_ssl:
            logger.warning("[ARTIFACTORY] SSL verification is DISABLED")
        logger.info(f"[ARTIFACTORY] Initialized client for {self.base_url}/artifactory - repo: {repo}, image: {image}")
    
    def _get_auth(self) -> Optional[Tuple[str, str]]:
        """Get authentication tuple if credentials are configured."""
        if self.username and self.password:
            return (self.username, self.password)
        return None
    
    def get_docker_tags(self, use_cache: bool = True) -> Tuple[List[str], Optional[str]]:
        """
        Fetch Docker image tags from Artifactory using Docker Registry V2 API.
        
        Tries multiple API path formats:
        1. /artifactory/api/docker/<repo>/v2/<image>/tags/list (standard)
        2. /api/docker/<repo>/v2/<image>/tags/list (some installations)
        
        Args:
            use_cache: Whether to use cached results if available
            
        Returns:
            Tuple of (list of tags sorted by version, error message if any)
        """
        global _version_cache
        
        # Check cache first
        if use_cache and _version_cache.is_valid():
            logger.debug("[ARTIFACTORY] Returning cached versions")
            return _version_cache.get(), None
        
        # Try different API path formats
        api_paths = [
            f"/artifactory/api/docker/{self.repo}/v2/{self.image}/tags/list",
        ]
        
        last_error = None
        
        for api_path in api_paths:
            try:
                docker_api_url = f"{self.base_url}{api_path}"
                
                logger.info(f"[ARTIFACTORY] Trying: {docker_api_url}")
                
                response = requests.get(
                    docker_api_url,
                    auth=self._get_auth(),
                    verify=self.verify_ssl,
                    timeout=30
                )
                
                logger.debug(f"[ARTIFACTORY] Response status: {response.status_code}")
                
                if response.status_code == 404:
                    logger.debug(f"[ARTIFACTORY] 404 for path: {api_path}")
                    last_error = f"Not found with path: {api_path}"
                    continue  # Try next path format
                
                response.raise_for_status()
                
                # Parse response: {"name": "image", "tags": ["v1", "v2", ...]}
                data = response.json()
                tags = data.get('tags', []) or []
                
                if not tags:
                    logger.warning(f"[ARTIFACTORY] No tags found for {self.repo}/{self.image}")
                    return [], "No tags found"
                
                # Sort tags: 'latest' first, then by semantic version (newest first)
                tags = self._sort_tags(tags)
                
                logger.info(f"[ARTIFACTORY] Found {len(tags)} tags: {tags[:5]}{'...' if len(tags) > 5 else ''}")
                
                # Update cache
                _version_cache.set(tags)
                
                return tags, None
                
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                logger.debug(f"[ARTIFACTORY] {last_error}")
                continue
            except ValueError as e:
                last_error = f"Parse error: {str(e)}"
                logger.debug(f"[ARTIFACTORY] {last_error}")
                continue
        
        # All paths failed
        error_msg = f"Failed to fetch tags. Last error: {last_error}"
        logger.error(f"[ARTIFACTORY] {error_msg}")
        logger.error(f"[ARTIFACTORY] Please verify:")
        logger.error(f"[ARTIFACTORY]   - Repo name: {self.repo}")
        logger.error(f"[ARTIFACTORY]   - Image name: {self.image}")
        logger.error(f"[ARTIFACTORY]   - Test manually: curl -u user:pass {self.base_url}/artifactory/api/docker/{self.repo}/v2/{self.image}/tags/list")
        return [], error_msg
    
    @staticmethod
    def _sort_tags(tags: List[str]) -> List[str]:
        """
        Sort Docker tags with 'latest' first, then by semantic version (descending).
        
        Handles tags like: latest, v1.0.0, v1.2.3, 1.0.0, sha-abc123
        """
        def tag_sort_key(tag: str) -> tuple:
            # 'latest' always first
            if tag.lower() == 'latest':
                return (0, 0, 0, 0, '')
            
            # Try to parse semantic version
            version_match = re.match(r'^v?(\d+)\.(\d+)\.(\d+)(.*)$', tag)
            if version_match:
                major, minor, patch, suffix = version_match.groups()
                # Negative values for descending order (newest first)
                return (1, -int(major), -int(minor), -int(patch), suffix)
            
            # Other tags at the end, sorted alphabetically
            return (2, 0, 0, 0, tag)
        
        return sorted(tags, key=tag_sort_key)

    def get_pypi_tags(self, use_cache: bool = True) -> Tuple[List[str], Optional[str]]:
        """
        Fetch PyPI package versions from Artifactory using the PyPI Simple API HTML.
        
        Args:
            use_cache: Whether to use cached results if available
            
        Returns:
            Tuple of (list of versions sorted newest first, error message if any)
        """
        global _version_cache
        
        if use_cache and _version_cache.is_valid():
            logger.debug("[ARTIFACTORY] Returning cached PyPI versions")
            return _version_cache.get(), None
            
        # Try standard PyPI simple API first, then fallback to the path the user sees in UI
        api_paths = [
            f"/artifactory/api/pypi/{self.pypi_repo}/simple/{self.pypi_package}",
            f"/artifactory/api/pypi/{self.pypi_repo}/pypi/{self.pypi_package}"
        ]
        
        last_error = None
        
        for api_path in api_paths:
            pypi_api_url = f"{self.base_url}{api_path}"
            logger.info(f"[ARTIFACTORY] Trying PyPI API: {pypi_api_url}")
            
            try:
                response = requests.get(
                    pypi_api_url,
                    auth=self._get_auth(),
                    verify=self.verify_ssl,
                    timeout=30
                )
                
                if response.status_code == 404:
                    last_error = f"Not found with path: {pypi_api_url}"
                    continue
                    
                response.raise_for_status()
                
                # The response is HTML containing links to the packages
                # <a href="ida-pro-mcp-1.0.0.tar.gz">ida-pro-mcp-1.0.0.tar.gz</a>
                html_content = response.text
                
                # Extract versions using regex based on the package name
                # Pattern matches package-name-1.2.3.tar.gz or package_name-1.2.3-py3-none-any.whl
                pkg_name_normalized = self.pypi_package.replace('-', '[-_]')
                pattern = rf'{pkg_name_normalized}-([0-9a-zA-Z.]+)(?:\.tar\.gz|-py[0-9].*\.whl|\.zip)'
                
                matches = set(re.findall(pattern, html_content, re.IGNORECASE))
                tags = list(matches)
                
                if not tags:
                    logger.warning(f"[ARTIFACTORY] No tags found for PyPI package {self.pypi_package} at {pypi_api_url}")
                    last_error = "No tags found in HTML"
                    continue
                    
                # Sort tags semantically, newest first
                def sort_key(v):
                    parts = re.split(r'[.-]', v.lstrip('v'))
                    return [-int(p) if p.isdigit() else 0 for p in parts]
                    
                try:
                    tags.sort(key=sort_key)
                except Exception:
                    tags.sort(reverse=True)
                    
                logger.info(f"[ARTIFACTORY] Found {len(tags)} PyPI versions: {tags[:5]}{'...' if len(tags) > 5 else ''}")
                
                _version_cache.set(tags)
                return tags, None
                
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                
        return [], last_error


# ============================================================
# Module-level Functions
# ============================================================

_artifactory_client: Optional[ArtifactoryClient] = None


def get_artifactory_client() -> Optional[ArtifactoryClient]:
    """Get the singleton ArtifactoryClient instance."""
    global _artifactory_client
    
    if not ARTIFACTORY_ENABLED:
        return None
    
    if _artifactory_client is None:
        try:
            _artifactory_client = ArtifactoryClient()
        except Exception as e:
            logger.error(f"[ARTIFACTORY] Failed to initialize client: {e}")
            return None
    
    return _artifactory_client


def get_mcp_versions(use_cache: bool = True) -> Tuple[List[str], str, Optional[str]]:
    """
    Get available MCP server versions (Docker tags).
    
    Tries Artifactory first, falls back to FALLBACK_VERSIONS if unavailable.
    
    Args:
        use_cache: Whether to use cached results
        
    Returns:
        Tuple of (versions list, default version, error message if any)
    """
    client = get_artifactory_client()
    
    if client is None:
        logger.debug("[ARTIFACTORY] Using fallback versions (Artifactory disabled)")
        return FALLBACK_VERSIONS, FALLBACK_VERSIONS[-1] if FALLBACK_VERSIONS else "latest", None
    
    versions, error = client.get_docker_tags(use_cache=use_cache)
    
    if not versions:
        logger.warning(f"[ARTIFACTORY] Fetch failed, using fallback. Error: {error}")
        return FALLBACK_VERSIONS, FALLBACK_VERSIONS[-1] if FALLBACK_VERSIONS else "latest", error
    
    # Default to 'latest' if available, otherwise first version
    default = "latest" if "latest" in versions else (versions[0] if versions else "latest")
    
    return versions, default, None


def get_pypi_versions(use_cache: bool = True) -> Tuple[List[str], str, Optional[str]]:
    """
    Get available PyPI package versions.
    
    Tries Artifactory PyPI API first, falls back to FALLBACK_VERSIONS if unavailable.
    
    Args:
        use_cache: Whether to use cached results
        
    Returns:
        Tuple of (versions list, default version, error message if any)
    """
    client = get_artifactory_client()
    
    if client is None:
        logger.debug("[ARTIFACTORY] Using fallback versions for PyPI (Artifactory disabled)")
        return FALLBACK_VERSIONS, FALLBACK_VERSIONS[0] if FALLBACK_VERSIONS else "latest", None
        
    versions, error = client.get_pypi_tags(use_cache=use_cache)
    
    if not versions:
        logger.warning(f"[ARTIFACTORY] PyPI fetch failed, using fallback. Error: {error}")
        return FALLBACK_VERSIONS, FALLBACK_VERSIONS[0] if FALLBACK_VERSIONS else "latest", error
        
    default = versions[0] if versions else "latest"
    
    return versions, default, None


def invalidate_version_cache():
    """Force refresh of version cache on next request."""
    global _version_cache
    _version_cache.invalidate()
    logger.info("[ARTIFACTORY] Version cache invalidated")


def is_artifactory_enabled() -> bool:
    """Check if Artifactory integration is enabled."""
    return ARTIFACTORY_ENABLED


# ============================================================
# Marketplace Helm Chart Version Fetching
# ============================================================

# Separate Artifactory paths for marketplace Helm charts.
# Format: "<repo>/<subfolder-path>" — e.g. "helm-dev-local/marketplace"
ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV = os.getenv(
    "ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV", "helm-dev-local/marketplace"
)
ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE = os.getenv(
    "ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE", "helm-release-local/marketplace"
)

# Separate version caches keyed by environment
_chart_version_caches: Dict[str, "VersionCache"] = {
    "dev": VersionCache(),
    "release": VersionCache(),
}

def get_marketplace_charts(
    environment: str = "dev",
    use_cache: bool = True,
) -> Tuple[List[str], Optional[str]]:
    """
    Return all Helm chart names (i.e. folder names) available in the configured
    Artifactory marketplace path for the given environment.

    The frontend presents this list in the Deploy dialog so the user can pick
    which chart (entity) they want to deploy.

    Returns:
        Tuple of (sorted chart-name list, error message or None)
    """
    if not ARTIFACTORY_ENABLED:
        logger.debug("[ARTIFACTORY] Chart list skipped (Artifactory disabled).")
        return [
            "data-analysis-agent", "jira-integration-mcp", "k8s-ops-agent",
            "github-actions-mcp", "vault-secrets-mcp", "slack-notifier-agent",
        ], None

    repo_path = (
        ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV
        if environment == "dev"
        else ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE
    )

    client = get_artifactory_client()
    if client is None:
        return [], "Artifactory client unavailable"

    # GET /artifactory/api/storage/<repo>/<path>?list&deep=0&listFolders=1
    parts = repo_path.split("/", 1)
    repo = parts[0]
    sub_path = parts[1] if len(parts) > 1 else ""
    url = f"{client.base_url}/artifactory/api/storage/{repo}/{sub_path}?list&deep=0&listFolders=1"
    logger.info("[ARTIFACTORY] Fetching chart list from: %s", url)

    try:
        response = requests.get(
            url,
            auth=client._get_auth(),
            verify=client.verify_ssl,
            timeout=15,
        )
        if response.status_code == 404:
            logger.warning("[ARTIFACTORY] Chart list path not found: %s", url)
            return [], f"Path not found: {url}"

        response.raise_for_status()
        data = response.json()
        folders = [
            entry["uri"].strip("/")
            for entry in data.get("files", [])
            if entry.get("folder", False)
        ]
        folders.sort()
        logger.info("[ARTIFACTORY] Found %d charts in %s: %s", len(folders), repo_path, folders[:8])
        return folders, None

    except requests.exceptions.RequestException as exc:
        err = f"Request error: {exc}"
        logger.error("[ARTIFACTORY] %s", err)
        return [], err
    except Exception as exc:
        err = f"Unexpected error: {exc}"
        logger.error("[ARTIFACTORY] %s", err)
        return [], err


def get_marketplace_chart_versions(
    chart_name: str,
    environment: str = "dev",
    use_cache: bool = True,
) -> Tuple[List[str], Optional[str]]:
    """
    Fetch available Helm chart versions for a specific marketplace entity from Artifactory.

    The function lists all `*.tgz` files in the configured chart path and extracts
    version numbers from filenames of the form ``<chart_name>-<version>.tgz``.

    Two separate repository paths are supported:
      - ``dev``     → ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV
      - ``release`` → ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE

    Returns:
        Tuple of (sorted version list newest-first, error message or None)
    """
    if not ARTIFACTORY_ENABLED:
        logger.debug("[ARTIFACTORY] Marketplace chart version fetch skipped (Artifactory disabled).")
        return ["latest", "1.0.0"], None

    cache = _chart_version_caches.get(environment, VersionCache())
    if use_cache and cache.is_valid():
        logger.debug("[ARTIFACTORY] Returning cached chart versions for environment '%s'", environment)
        return cache.get(), None

    repo_path = (
        ARTIFACTORY_MARKETPLACE_CHART_REPO_DEV
        if environment == "dev"
        else ARTIFACTORY_MARKETPLACE_CHART_REPO_RELEASE
    )

    client = get_artifactory_client()
    if client is None:
        return ["latest", "1.0.0"], "Artifactory client unavailable"

    # Use the Artifactory file list API to enumerate files in the path
    # GET /artifactory/api/storage/<repo>/<path>?list&deep=0&listFolders=0
    parts = repo_path.split("/", 1)
    repo = parts[0]
    sub_path = parts[1] if len(parts) > 1 else ""
    url = f"{client.base_url}/artifactory/api/storage/{repo}/{sub_path}/{chart_name}?list&deep=0&listFolders=0"
    logger.info("[ARTIFACTORY] Fetching marketplace chart versions from: %s", url)

    try:
        response = requests.get(
            url,
            auth=client._get_auth(),
            verify=client.verify_ssl,
            timeout=15,
        )
        if response.status_code == 404:
            logger.warning("[ARTIFACTORY] Chart path not found: %s", url)
            return ["latest", "1.0.0"], f"Chart path not found: {url}"

        response.raise_for_status()
        data = response.json()
        files = data.get("files", [])

        versions: List[str] = []
        pattern = re.compile(
            rf"^/?{re.escape(chart_name)}-([0-9a-zA-Z.\-]+)\.tgz$"
        )
        for entry in files:
            uri = entry.get("uri", "")
            m = pattern.match(uri.lstrip("/"))
            if m:
                versions.append(m.group(1))

        if not versions:
            logger.warning("[ARTIFACTORY] No chart versions found for '%s' in %s", chart_name, repo_path)
            return ["latest", "1.0.0"], "No versions found"

        versions = ArtifactoryClient._sort_tags(versions)
        cache.set(versions)
        logger.info("[ARTIFACTORY] Found %d chart versions for '%s': %s", len(versions), chart_name, versions[:5])
        return versions, None

    except requests.exceptions.RequestException as exc:
        err = f"Request error: {exc}"
        logger.error("[ARTIFACTORY] %s", err)
        return ["latest", "1.0.0"], err
    except Exception as exc:
        err = f"Unexpected error: {exc}"
        logger.error("[ARTIFACTORY] %s", err)
        return ["latest", "1.0.0"], err
