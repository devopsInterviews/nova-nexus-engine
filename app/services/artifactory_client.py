"""
Artifactory API Client for fetching Docker image versions.

This module provides functionality to:
1. Connect to JFrog Artifactory
2. Fetch Docker image tags from a repository
3. Cache results to minimize API calls

Uses pyartifactory library for cleaner Artifactory integration.
"""

import os
import logging
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

try:
    from pyartifactory import Artifactory
    from pyartifactory.exception import ArtifactoryError
except ImportError:
    Artifactory = None
    ArtifactoryError = Exception
    logging.warning("pyartifactory not installed. Install with: pip install pyartifactory")

logger = logging.getLogger("uvicorn.error")

# ============================================================
# Configuration
# ============================================================

ARTIFACTORY_ENABLED = os.getenv("ARTIFACTORY_ENABLED", "false").lower() == "true"
ARTIFACTORY_URL = os.getenv("ARTIFACTORY_URL", "")  # e.g., https://artifactory.company.internal
ARTIFACTORY_REPO = os.getenv("ARTIFACTORY_REPO", "docker-local")  # Docker repository name
ARTIFACTORY_IMAGE = os.getenv("ARTIFACTORY_IMAGE", "ida-pro-mcp")  # Image name
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
# Data Classes
# ============================================================

@dataclass
class ArtifactoryConfig:
    """Configuration for Artifactory client initialization."""
    url: str
    repo: str
    image: str
    username: str = ""
    password: str = ""
    verify_ssl: bool = True


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

class ArtifactoryClient:
    """Client for fetching Docker image tags from JFrog Artifactory."""
    
    def __init__(
        self,
        url: str = ARTIFACTORY_URL,
        repo: str = ARTIFACTORY_REPO,
        image: str = ARTIFACTORY_IMAGE,
        username: str = ARTIFACTORY_USERNAME,
        password: str = ARTIFACTORY_PASSWORD,
        verify_ssl: bool = ARTIFACTORY_VERIFY_SSL
    ):
        if Artifactory is None:
            raise ImportError("pyartifactory is required. Install with: pip install pyartifactory")
        
        self.url = url.rstrip("/")
        self.repo = repo
        self.image = image
        self.verify_ssl = verify_ssl
        
        # Initialize Artifactory client
        auth = (username, password) if username and password else None
        self.artifactory = Artifactory(
            url=self.url,
            auth=auth,
            verify=verify_ssl
        )
        
        if not verify_ssl:
            logger.warning(f"[ARTIFACTORY] SSL verification is DISABLED")
        logger.info(f"[ARTIFACTORY] Initialized client for {self.url}/{repo}/{image}")
    
    def get_docker_tags(self, use_cache: bool = True) -> Tuple[List[str], Optional[str]]:
        """
        Fetch Docker image tags from Artifactory.
        
        Args:
            use_cache: Whether to use cached results if available
            
        Returns:
            Tuple of (list of tags, error message if any)
        """
        global _version_cache
        
        # Check cache first
        if use_cache and _version_cache.is_valid():
            logger.debug("[ARTIFACTORY] Returning cached versions")
            return _version_cache.get(), None
        
        try:
            logger.info(f"[ARTIFACTORY] Fetching tags for {self.repo}/{self.image}")
            
            # Use artifacts API to list Docker tags
            # Docker images in Artifactory are stored as: repo/image/tag/manifest.json
            artifact_path = f"{self.repo}/{self.image}"
            
            # Get folder info which lists all tags as subfolders
            folder_info = self.artifactory.artifacts.info(artifact_path)
            
            tags = []
            if hasattr(folder_info, 'children') and folder_info.children:
                for child in folder_info.children:
                    if child.folder:
                        # Each subfolder is a tag
                        tag_name = child.uri.strip('/')
                        if tag_name:
                            tags.append(tag_name)
            
            # Sort tags: put 'latest' first, then sort rest by version
            tags = self._sort_tags(tags)
            
            logger.info(f"[ARTIFACTORY] Found {len(tags)} tags: {tags[:5]}{'...' if len(tags) > 5 else ''}")
            
            # Update cache
            _version_cache.set(tags)
            
            return tags, None
            
        except ArtifactoryError as e:
            error_msg = f"Artifactory API error: {str(e)}"
            logger.error(f"[ARTIFACTORY] {error_msg}")
            return [], error_msg
        except Exception as e:
            error_msg = f"Error fetching tags: {str(e)}"
            logger.error(f"[ARTIFACTORY] {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            return [], error_msg
    
    def _sort_tags(self, tags: List[str]) -> List[str]:
        """
        Sort Docker tags with 'latest' first, then by semantic version.
        
        Handles tags like: latest, v1.0.0, v1.2.3, 1.0.0, sha-abc123
        """
        def tag_sort_key(tag: str) -> tuple:
            # 'latest' always first
            if tag.lower() == 'latest':
                return (0, 0, 0, 0, '')
            
            # Try to parse semantic version
            import re
            version_match = re.match(r'^v?(\d+)\.(\d+)\.(\d+)(.*)$', tag)
            if version_match:
                major, minor, patch, suffix = version_match.groups()
                # Sort versions in descending order (newest first)
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
        # Artifactory not enabled or failed, use fallback
        logger.debug("[ARTIFACTORY] Using fallback versions")
        return FALLBACK_VERSIONS, FALLBACK_VERSIONS[-1] if FALLBACK_VERSIONS else "latest", None
    
    versions, error = client.get_docker_tags(use_cache=use_cache)
    
    if not versions:
        # Failed to fetch, use fallback
        logger.warning(f"[ARTIFACTORY] Fetch failed, using fallback versions. Error: {error}")
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
