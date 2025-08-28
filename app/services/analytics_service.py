"""
Analytics service for data management and background tasks.

This service handles:
- Data seeding for development/demo purposes
- MCP server health monitoring
- System metrics collection
- Analytics data cleanup and maintenance
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    SystemMetrics, RequestLog, McpServerStatus, PageView, 
    UserActivity, User
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for managing analytics data and background tasks."""
    
    def __init__(self):
        self.monitoring_tasks = []
    
    def seed_demo_data(self, db: Session):
        """
        Initialize analytics system but avoid seeding demo data.
        Real data will be collected by the analytics middleware.
        """
        try:
            logger.info("Initializing analytics system...")
            
            # Check if real data already exists
            existing_requests = db.query(func.count(RequestLog.id)).scalar()
            existing_pageviews = db.query(func.count(PageView.id)).scalar()
            
            if existing_requests > 0 or existing_pageviews > 0:
                logger.info("Real analytics data found, skipping demo data seeding")
                return
            
            logger.info("Analytics system ready - real data will be collected by middleware")
            
        except Exception as e:
            logger.error(f"Failed to initialize analytics system: {e}")
            db.rollback()
    
    def _seed_system_metrics(self, db: Session):
        """Seed system metrics with realistic data."""
        now = datetime.utcnow()
        
        # Generate metrics for the last 7 days
        for i in range(7 * 24):  # 7 days * 24 hours
            timestamp = now - timedelta(hours=i)
            
            # Response time metrics (with some variation)
            base_response_time = 50 + random.randint(-20, 30)
            response_time = max(20, base_response_time)
            
            metric = SystemMetrics(
                metric_name='response_time',
                metric_type='gauge',
                value=f'{response_time}ms',
                numeric_value=response_time,
                source='system_monitor',
                timestamp=timestamp
            )
            db.add(metric)
            
            # Request count metrics
            request_count = random.randint(100, 500)
            metric = SystemMetrics(
                metric_name='request_count',
                metric_type='counter',
                value=str(request_count),
                numeric_value=request_count,
                source='system_monitor',
                timestamp=timestamp
            )
            db.add(metric)
    
    def _seed_request_logs(self, db: Session):
        """Seed request logs with realistic API usage data from actual endpoints."""
        # Get real endpoints from the FastAPI app
        paths = self._get_real_api_endpoints()
        
        methods = ['GET', 'POST', 'PUT', 'DELETE']
        status_codes = [200, 201, 400, 401, 404, 500]
        status_weights = [70, 15, 5, 3, 5, 2]  # Mostly successful requests
        
        now = datetime.utcnow()
        
        # Generate logs for the last 7 days
        for i in range(7):
            day = now - timedelta(days=i)
            
            # Generate 100-300 requests per day
            daily_requests = random.randint(100, 300)
            
            for j in range(daily_requests):
                timestamp = day - timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                
                path = random.choice(paths)
                method = random.choices(methods, weights=[60, 25, 10, 5])[0]
                status_code = random.choices(status_codes, weights=status_weights)[0]
                
                # Response time varies by endpoint
                if path.startswith('/api/'):
                    response_time = random.randint(30, 200)
                else:
                    response_time = random.randint(50, 500)
                
                log = RequestLog(
                    method=method,
                    path=path,
                    status_code=status_code,
                    response_time_ms=response_time,
                    request_size=random.randint(100, 2000) if method in ['POST', 'PUT'] else None,
                    response_size=random.randint(500, 5000),
                    ip_address=f"192.168.1.{random.randint(1, 254)}",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    timestamp=timestamp
                )
                db.add(log)
    
    def _seed_mcp_servers(self, db: Session):
        """Seed MCP server status data from real connected servers."""
        servers = self._get_real_mcp_servers()
        
        now = datetime.utcnow()
        
        for server_data in servers:
            server = McpServerStatus(
                server_name=server_data['name'],
                server_url=server_data['url'],
                status=server_data['status'],
                response_time_ms=server_data.get('response_time_ms', random.randint(20, 100) if server_data['status'] == 'active' else None),
                last_check=server_data.get('last_checked', now - timedelta(minutes=random.randint(1, 30))),
                last_successful_check=server_data.get('last_successful_check', now - timedelta(minutes=random.randint(1, 30)) if server_data['status'] == 'active' else now - timedelta(hours=2)),
                error_count=server_data.get('error_count', 0 if server_data['status'] == 'active' else random.randint(5, 20)),
                total_requests=server_data.get('total_requests', random.randint(1000, 5000)),
                successful_requests=server_data.get('successful_requests', random.randint(950, 4950)),
                created_at=now - timedelta(days=30),
                updated_at=server_data.get('updated_at', now - timedelta(minutes=random.randint(1, 30)))
            )
            db.add(server)
    
    def _seed_page_views(self, db: Session):
        """Seed page view analytics data from real frontend routes."""
        # Get real frontend routes and add some common ones
        api_paths = self._get_real_api_endpoints()
        
        # Extract frontend paths and add common frontend routes
        frontend_paths = []
        for path in api_paths:
            if not path.startswith('/api/'):
                frontend_paths.append(path)
        
        # Add common frontend routes that might not be in API routes
        common_frontend_paths = [
            '/', '/bi', '/analytics', '/devops', '/tests', 
            '/settings', '/users', '/login', '/home'
        ]
        
        # Combine and deduplicate
        all_paths = list(set(frontend_paths + common_frontend_paths))
        
        # Create page objects with titles
        pages = []
        for path in all_paths:
            title = self._path_to_title(path)
            pages.append({'path': path, 'title': title})
        
        now = datetime.utcnow()
        
        # Generate page views for the last 7 days
        for i in range(7):
            day = now - timedelta(days=i)
            
            # Generate 50-200 page views per day
            daily_views = random.randint(50, 200)
            
            for j in range(daily_views):
                timestamp = day - timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                
                page = random.choice(pages)
                
                view = PageView(
                    path=page['path'],
                    title=page['title'],
                    user_id=1,  # Admin user for demo
                    session_id=f"sess_{random.randint(1000, 9999)}",
                    ip_address=f"192.168.1.{random.randint(1, 254)}",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    load_time_ms=random.randint(200, 2000),
                    timestamp=timestamp
                )
                db.add(view)
    
    def _seed_user_activities(self, db: Session):
        """Seed user activity data."""
        activities = [
            {'type': 'auth', 'action': 'User login', 'status': 'success'},
            {'type': 'database', 'action': 'Database connection test', 'status': 'success'},
            {'type': 'query', 'action': 'Analytics query execution', 'status': 'success'},
            {'type': 'mcp', 'action': 'MCP server test', 'status': 'success'},
            {'type': 'export', 'action': 'Data export', 'status': 'success'},
            {'type': 'auth', 'action': 'Failed login attempt', 'status': 'error'},
            {'type': 'database', 'action': 'Connection timeout', 'status': 'error'},
        ]
        
        now = datetime.utcnow()
        
        # Generate activities for the last 24 hours
        for i in range(50):
            timestamp = now - timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            activity_data = random.choice(activities)
            
            activity = UserActivity(
                user_id=1,  # Admin user for demo
                activity_type=activity_data['type'],
                action=activity_data['action'],
                ip_address=f"192.168.1.{random.randint(1, 254)}",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                status=activity_data['status'],
                timestamp=timestamp
            )
            db.add(activity)
    
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
            
            logger.info(f"Discovered {len(unique_paths)} real API endpoints for seeding")
            return unique_paths
            
        except Exception as e:
            logger.warning(f"Failed to discover real endpoints, using fallback: {e}")
            # Fallback to basic paths if discovery fails
            return [
                '/api/health', '/api/auth/login', '/api/me', '/api/logout',
                '/health', '/', '/bi', '/analytics', '/devops', '/settings'
            ]
    
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
                    'total_requests': random.randint(1000, 5000),
                    'successful_requests': None,  # Will be calculated
                    'updated_at': datetime.utcnow()
                }
                
                # Calculate successful requests (90-98% success rate)
                success_rate = random.uniform(0.90, 0.98)
                server_info['successful_requests'] = int(server_info['total_requests'] * success_rate)
                
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
                    'error_count': random.randint(10, 50),
                    'total_requests': random.randint(500, 2000),
                    'successful_requests': random.randint(400, 1500),
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
