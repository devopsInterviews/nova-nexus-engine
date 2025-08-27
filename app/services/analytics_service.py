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
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
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
        Seed the database with demo data for development/testing.
        This creates realistic sample data for the dashboard.
        """
        try:
            logger.info("Seeding demo analytics data...")
            
            # Seed system metrics
            self._seed_system_metrics(db)
            
            # Seed request logs
            self._seed_request_logs(db)
            
            # Seed MCP server status
            self._seed_mcp_servers(db)
            
            # Seed page views
            self._seed_page_views(db)
            
            # Seed user activities
            self._seed_user_activities(db)
            
            db.commit()
            logger.info("Demo data seeded successfully")
            
        except Exception as e:
            logger.error(f"Failed to seed demo data: {e}")
            db.rollback()
    
    def _seed_system_metrics(self, db: Session):
        """Seed system metrics with realistic data."""
        now = datetime.utcnow()
        
        # Generate metrics for the last 7 days
        for i in range(7 * 24):  # 7 days * 24 hours
            timestamp = now - timedelta(hours=i)
            
            # Response time metrics (with some variation)
            import random
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
        """Seed request logs with realistic API usage data."""
        import random
        
        paths = [
            '/api/health', '/api/list-tables', '/api/test-connection',
            '/api/describe-columns', '/api/analytics-query', '/api/auth/login',
            '/api/users/profile', '/api/save-connection', '/', '/bi',
            '/analytics', '/devops', '/settings'
        ]
        
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
        """Seed MCP server status data."""
        servers = [
            {
                'name': 'jenkins-mcp-server',
                'url': 'http://jenkins-mcp:8050/mcp/',
                'status': 'active'
            },
            {
                'name': 'confluence-mcp-server', 
                'url': 'http://confluence-mcp:8051/mcp/',
                'status': 'active'
            },
            {
                'name': 'database-mcp-server',
                'url': 'http://db-mcp:8052/mcp/',
                'status': 'active'
            },
            {
                'name': 'logs-mcp-server',
                'url': 'http://logs-mcp:8053/mcp/',
                'status': 'inactive'
            }
        ]
        
        now = datetime.utcnow()
        
        for server_data in servers:
            server = McpServerStatus(
                server_name=server_data['name'],
                server_url=server_data['url'],
                status=server_data['status'],
                response_time_ms=random.randint(20, 100) if server_data['status'] == 'active' else None,
                last_check=now - timedelta(minutes=random.randint(1, 30)),
                last_successful_check=now - timedelta(minutes=random.randint(1, 30)) if server_data['status'] == 'active' else now - timedelta(hours=2),
                error_count=0 if server_data['status'] == 'active' else random.randint(5, 20),
                total_requests=random.randint(1000, 5000),
                successful_requests=random.randint(950, 4950),
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(minutes=random.randint(1, 30))
            )
            db.add(server)
    
    def _seed_page_views(self, db: Session):
        """Seed page view analytics data."""
        import random
        
        pages = [
            {'path': '/', 'title': 'Home'},
            {'path': '/bi', 'title': 'Business Intelligence'},
            {'path': '/analytics', 'title': 'Analytics'},
            {'path': '/devops', 'title': 'DevOps'},
            {'path': '/tests', 'title': 'Tests'},
            {'path': '/settings', 'title': 'Settings'},
            {'path': '/users', 'title': 'Users'},
            {'path': '/login', 'title': 'Login'}
        ]
        
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
        import random
        
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
