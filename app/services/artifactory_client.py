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
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("uvicorn.error")

# ============================================================
# Configuration
# ============================================================

ARTIFACTORY_ENABLED = os.getenv("ARTIFACTORY_ENABLED", "false").lower() == "true"
ARTIFACTORY_URL = os.getenv("ARTIFACTORY_URL", "")  # e.g., https://artifactory.company.internal
ARTIFACTORY_REPO = os.getenv("ARTIFACTORY_REPO", "docker-local")  # Docker repository name
ARTIFACTORY_IMAGE = os.getenv("ARTIFACTORY_IMAGE", "ida-pro-mcp")  # Image name (can include path like "repo/image")
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
        verify_ssl: bool = ARTIFACTORY_VERIFY_SSL
    ):
        # Normalize URL - remove trailing slash and /artifactory suffix if present
        # This ensures consistent URL construction
        self.base_url = url.rstrip("/")
        if self.base_url.endswith("/artifactory"):
            self.base_url = self.base_url[:-12]  # Remove /artifactory
        
        self.repo = repo
        self.image = image
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
    Get available MCP server versions.
    
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


def invalidate_version_cache():
    """Force refresh of version cache on next request."""
    global _version_cache
    _version_cache.invalidate()
    logger.info("[ARTIFACTORY] Version cache invalidated")


def is_artifactory_enabled() -> bool:
    """Check if Artifactory integration is enabled."""
    return ARTIFACTORY_ENABLED
