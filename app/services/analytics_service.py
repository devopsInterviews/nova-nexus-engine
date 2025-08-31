"""
Analytics service for data management and background tasks.

This service handles:
- MCP server health monitoring
- System metrics collection
- Analytics data cleanup and maintenance
- Real-time data collection coordination
"""

import asyncio
import logging
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
        self.monitoring_tasks = []
    
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
        """Start background monitoring tasks."""
        logger.info("Starting analytics monitoring tasks...")
        
        # Start MCP server monitoring
        monitor_task = asyncio.create_task(self._monitor_mcp_servers())
        self.monitoring_tasks.append(monitor_task)
        
        # Start metrics cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_old_data())
        self.monitoring_tasks.append(cleanup_task)
    
    async def stop_monitoring(self):
        """Stop all background monitoring tasks."""
        logger.info("Stopping analytics monitoring tasks...")
        
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        self.monitoring_tasks.clear()
    
    async def _monitor_mcp_servers(self):
        """Background task to monitor MCP server health."""
        while True:
            try:
                # Import SessionLocal dynamically to avoid initialization issues
                from app.database import SessionLocal
                
                if SessionLocal is None:
                    logger.warning("SessionLocal not initialized, skipping MCP monitoring")
                    await asyncio.sleep(60)
                    continue
                
                db = SessionLocal()
                try:
                    # Get all registered servers
                    servers = db.query(McpServerStatus).all()
                    
                    for server in servers:
                        await self._check_server_health(db, server)
                    
                    db.commit()
                except Exception as e:
                    logger.error(f"Error monitoring MCP servers: {e}")
                    db.rollback()
                finally:
                    db.close()
                
                # Wait 5 minutes before next check
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in MCP monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _check_server_health(self, db: Session, server: McpServerStatus):
        """Check health of a single MCP server."""
        try:
            import aiohttp
            import time
            
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{server.server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_time = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        server.status = 'active'
                        server.response_time_ms = response_time
                        server.last_successful_check = datetime.utcnow()
                        server.error_count = 0
                        server.error_message = None
                    else:
                        server.status = 'error'
                        server.error_count += 1
                        server.error_message = f"HTTP {response.status}"
                    
                    server.last_check = datetime.utcnow()
                    server.total_requests += 1
                    
                    if server.status == 'active':
                        server.successful_requests += 1
        
        except Exception as e:
            logger.warning(f"Failed to check server {server.server_name}: {e}")
            server.status = 'error'
            server.error_count += 1
            server.error_message = str(e)
            server.last_check = datetime.utcnow()
            server.total_requests += 1
    
    async def _cleanup_old_data(self):
        """Background task to cleanup old analytics data."""
        while True:
            try:
                # Import SessionLocal dynamically to avoid initialization issues
                from app.database import SessionLocal
                
                if SessionLocal is None:
                    logger.warning("SessionLocal not initialized, skipping data cleanup")
                    await asyncio.sleep(3600)
                    continue
                
                db = SessionLocal()
                try:
                    now = datetime.utcnow()
                    
                    # Keep only last 30 days of request logs
                    thirty_days_ago = now - timedelta(days=30)
                    deleted_logs = db.query(RequestLog).filter(
                        RequestLog.timestamp < thirty_days_ago
                    ).delete()
                    
                    # Keep only last 90 days of page views
                    ninety_days_ago = now - timedelta(days=90)
                    deleted_views = db.query(PageView).filter(
                        PageView.timestamp < ninety_days_ago
                    ).delete()
                    
                    # Keep only last 7 days of system metrics
                    seven_days_ago = now - timedelta(days=7)
                    deleted_metrics = db.query(SystemMetrics).filter(
                        SystemMetrics.timestamp < seven_days_ago
                    ).delete()
                    
                    db.commit()
                    
                    if deleted_logs or deleted_views or deleted_metrics:
                        logger.info(
                            f"Cleaned up old data: {deleted_logs} request logs, "
                            f"{deleted_views} page views, {deleted_metrics} metrics"
                        )
                
                except Exception as e:
                    logger.error(f"Error cleaning up old data: {e}")
                    db.rollback()
                finally:
                    db.close()
                
                # Run cleanup daily
                await asyncio.sleep(86400)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in cleanup task: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry


# Global analytics service instance
analytics_service = AnalyticsService()
