"""
Analytics service for data management and background tasks.

This service handles:
- MCP server health monitoring
- System metrics collection
- Analytics data cleanup and maintenance
- Real-time data collection coordination
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models import (
    SystemMetrics, RequestLog, McpServerStatus, PageView, 
    UserActivity, User
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for managing analytics data and background tasks."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    
    def initialize_analytics(self, db: Session):
        """
        Initialize analytics system.
        Real data will be collected by the analytics middleware.
        """
        try:
            logger.info("Analytics system initialized - ready to collect real data")
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics system: {e}")
            db.rollback()
    
    def _get_real_mcp_servers(self) -> List[Dict[str, Any]]:
        """
        Get real MCP server information from the active connections.
        
        Returns:
            List[Dict]: List of real MCP server data with connection status
        """
        try:
            # Import MCP session dynamically to avoid circular imports
            from app.client import _mcp_session
            
            servers = []
            
            if _mcp_session:
                logger.info("Discovering real MCP servers from active session")
                
                # Get basic server info from the session
                server_info = {
                    'name': 'Primary MCP Server',
                    'url': getattr(_mcp_session, '_url', 'Unknown URL'),
                    'status': 'active',
                    'response_time_ms': None,
                    'last_checked': datetime.utcnow(),
                    'last_successful_check': datetime.utcnow(),
                    'error_count': 0,
                    'total_requests': 0,  # Start fresh for real tracking
                    'successful_requests': 0,  # Start fresh for real tracking
                    'updated_at': datetime.utcnow()
                }
                
                servers.append(server_info)
                logger.info(f"Found active MCP server: {server_info['name']} at {server_info['url']}")
                
            else:
                logger.warning("No active MCP session found, creating placeholder server entry")
                # Create a placeholder entry for disconnected state
                servers.append({
                    'name': 'Primary MCP Server',
                    'url': 'Unknown - Not Connected',
                    'status': 'inactive',
                    'response_time_ms': None,
                    'last_checked': datetime.utcnow() - timedelta(minutes=30),
                    'last_successful_check': datetime.utcnow() - timedelta(hours=2),
                    'error_count': 0,
                    'total_requests': 0,
                    'successful_requests': 0,
                    'updated_at': datetime.utcnow() - timedelta(minutes=30)
                })
            
            return servers
            
        except Exception as e:
            logger.error(f"Failed to discover real MCP servers: {e}")
            # Fallback to a basic disconnected server entry
            return [{
                'name': 'Primary MCP Server',
                'url': 'Connection Error',
                'status': 'error',
                'response_time_ms': None,
                'last_checked': datetime.utcnow(),
                'last_successful_check': datetime.utcnow() - timedelta(hours=1),
                'error_count': 1,
                'total_requests': 0,
                'successful_requests': 0,
                'updated_at': datetime.utcnow()
            }]
    
    def _path_to_title(self, path: str) -> str:
        """
        Convert a URL path to a human-readable title.
        
        Args:
            path (str): URL path (e.g., '/api/users', '/analytics')
            
        Returns:
            str: Human-readable title (e.g., 'API Users', 'Analytics')
        """
        if path == '/':
            return 'Home'
        
        # Remove leading slash and API prefix
        clean_path = path.lstrip('/')
        if clean_path.startswith('api/'):
            clean_path = clean_path[4:]  # Remove 'api/'
        
        # Split by slashes and hyphens, capitalize each word
        parts = clean_path.replace('/', ' ').replace('-', ' ').replace('_', ' ').split()
        title_parts = [part.capitalize() for part in parts if part]
        
        title = ' '.join(title_parts)
        
        # Special cases for better readability
        title_map = {
            'Bi': 'Business Intelligence',
            'Api': 'API',
            'Mcp': 'MCP',
            'Auth': 'Authentication',
            'Db': 'Database'
        }
        
        for old, new in title_map.items():
            title = title.replace(old, new)
        
        return title if title else 'Unknown Page'
    
    def _get_real_api_endpoints(self) -> List[str]:
        """
        Get real API endpoints from the FastAPI application.
        
        Returns:
            List[str]: List of actual endpoint paths from the application
        """
        try:
            # Import FastAPI app dynamically to avoid circular imports
            from app.client import app
            
            paths = []
            for route in app.routes:
                if hasattr(route, 'path') and hasattr(route, 'methods'):
                    path = route.path
                    
                    # Skip non-API routes
                    if (path in ['/', '/{full_path:path}'] or 
                        path.startswith('/static') or 
                        'openapi' in path.lower() or 
                        path in ['/docs', '/redoc']):
                        continue
                    
                    paths.append(path)
            
            # Remove duplicates and sort
            unique_paths = list(set(paths))
            unique_paths.sort()
            
            logger.info(f"Discovered {len(unique_paths)} real API endpoints")
            return unique_paths
            
        except Exception as e:
            logger.warning(f"Failed to discover real endpoints, using fallback: {e}")
            # Fallback to basic paths if discovery fails
            return [
                '/api/health', '/api/auth/login', '/api/me', '/api/logout',
                '/health', '/', '/bi', '/analytics', '/devops', '/settings'
            ]

    async def start_monitoring(self):
        """
        Start background monitoring as daemon threads.

        Daemon threads are used instead of asyncio.create_task() for the same reason
        the TTL cleanup was converted: asyncio.sleep() calls inside tasks keep the
        event loop busy. When uvicorn receives SIGTERM, it waits for the ASGI lifespan
        shutdown to complete. If outstanding asyncio tasks include long sleeps (e.g.
        asyncio.sleep(300)), the shutdown blocks until those sleeps finish — causing
        the pod to appear stuck or to restart at exactly the sleep interval.

        Daemon threads use time.sleep() which is transparent to the event loop and
        are killed automatically when the process exits.
        """
        logger.info("Starting analytics monitoring daemon threads...")
        self._stop_event.clear()

        t1 = threading.Thread(
            target=self._monitor_mcp_servers_thread,
            daemon=True,
            name="analytics-mcp-monitor",
        )
        t2 = threading.Thread(
            target=self._cleanup_old_data_thread,
            daemon=True,
            name="analytics-data-cleanup",
        )
        t1.start()
        t2.start()
        self._threads = [t1, t2]
        logger.info(
            "Analytics daemon threads started (monitor tid=%s, cleanup tid=%s).",
            t1.ident, t2.ident,
        )

    async def stop_monitoring(self):
        """Signal monitoring threads to stop at their next sleep boundary."""
        logger.info("Stopping analytics monitoring threads...")
        self._stop_event.set()
        self._threads.clear()

    def _interruptible_sleep(self, seconds: float) -> bool:
        """
        Sleep for `seconds` but wake up early if _stop_event is set.
        Returns True if the thread should continue, False if it should exit.
        """
        return not self._stop_event.wait(timeout=seconds)

    def _monitor_mcp_servers_thread(self) -> None:
        """Daemon thread: check MCP server health every 5 minutes."""
        logger.info("[ANALYTICS] MCP monitor thread started.")
        while not self._stop_event.is_set():
            try:
                from app.database import SessionLocal

                if SessionLocal is None:
                    logger.warning("[ANALYTICS] SessionLocal not ready, skipping MCP check.")
                else:
                    db: Session = SessionLocal()
                    try:
                        servers = db.query(McpServerStatus).all()
                        for server in servers:
                            self._check_server_health_sync(db, server)
                        db.commit()
                    except Exception as exc:
                        logger.error("[ANALYTICS] Error monitoring MCP servers: %s", exc)
                        db.rollback()
                    finally:
                        db.close()
            except Exception as exc:
                logger.error("[ANALYTICS] Unexpected error in MCP monitor thread: %s", exc)

            if not self._interruptible_sleep(300):
                break

        logger.info("[ANALYTICS] MCP monitor thread exiting.")

    def _check_server_health_sync(self, db: Session, server: McpServerStatus) -> None:
        """Synchronous health check for a single MCP server (runs in thread, safe to block)."""
        try:
            import requests as http_requests
            start = time.time()
            resp = http_requests.get(
                f"{server.server_url}/health",
                timeout=10,
                verify=False,
            )
            response_time = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                server.status = "active"
                server.response_time_ms = response_time
                server.last_successful_check = datetime.utcnow()
                server.error_count = 0
                server.error_message = None
            else:
                server.status = "error"
                server.error_count += 1
                server.error_message = f"HTTP {resp.status_code}"

            server.last_check = datetime.utcnow()
            server.total_requests += 1
            if server.status == "active":
                server.successful_requests += 1

        except Exception as exc:
            logger.warning("[ANALYTICS] Health check failed for %s: %s", server.server_name, exc)
            server.status = "error"
            server.error_count += 1
            server.error_message = str(exc)
            server.last_check = datetime.utcnow()
            server.total_requests += 1

    def _cleanup_old_data_thread(self) -> None:
        """Daemon thread: purge old analytics rows once per day."""
        logger.info("[ANALYTICS] Data-cleanup thread started.")
        while not self._stop_event.is_set():
            try:
                from app.database import SessionLocal

                if SessionLocal is None:
                    logger.warning("[ANALYTICS] SessionLocal not ready, skipping data cleanup.")
                else:
                    db: Session = SessionLocal()
                    try:
                        now = datetime.utcnow()
                        deleted_logs = (
                            db.query(RequestLog)
                            .filter(RequestLog.timestamp < now - timedelta(days=30))
                            .delete()
                        )
                        deleted_views = (
                            db.query(PageView)
                            .filter(PageView.timestamp < now - timedelta(days=90))
                            .delete()
                        )
                        deleted_metrics = (
                            db.query(SystemMetrics)
                            .filter(SystemMetrics.timestamp < now - timedelta(days=7))
                            .delete()
                        )
                        db.commit()
                        if deleted_logs or deleted_views or deleted_metrics:
                            logger.info(
                                "[ANALYTICS] Cleanup: %d request logs, %d page views, %d metrics removed.",
                                deleted_logs, deleted_views, deleted_metrics,
                            )
                        else:
                            logger.debug("[ANALYTICS] Cleanup: nothing to remove.")
                    except Exception as exc:
                        logger.error("[ANALYTICS] Error during data cleanup: %s", exc)
                        db.rollback()
                    finally:
                        db.close()
            except Exception as exc:
                logger.error("[ANALYTICS] Unexpected error in cleanup thread: %s", exc)

            if not self._interruptible_sleep(86400):
                break

        logger.info("[ANALYTICS] Data-cleanup thread exiting.")


# Global analytics service instance
analytics_service = AnalyticsService()
