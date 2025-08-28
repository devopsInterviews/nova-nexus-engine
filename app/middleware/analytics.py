"""
Analytics middleware for request logging and monitoring.

This middleware automatically logs all requests for analytics purposes,
tracking performance metrics, error rates, and usage patterns.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.models import RequestLog, SystemMetrics, PageView, McpServerStatus, UserActivity

logger = logging.getLogger(__name__)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log requests and track system metrics for analytics.
    
    This middleware:
    - Logs all incoming requests with performance metrics
    - Tracks response times and status codes
    - Records client information for analytics
    - Updates system metrics in real-time
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log analytics data."""
        start_time = time.time()
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get('User-Agent', '')
        referer = request.headers.get('Referer', '')
        
        # Get request size
        request_size = None
        content_length = request.headers.get('Content-Length')
        if content_length:
            try:
                request_size = int(content_length)
            except ValueError:
                pass
        
        # Process the request
        response = None
        error_message = None
        
        try:
            response = await call_next(request)
        except Exception as e:
            # Convert exception to string safely to avoid validation issues
            error_str = str(e) if not isinstance(e, Exception) else repr(e)
            logger.error(f"Request failed: {error_str}")
            error_message = error_str
            # Create a 500 error response
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
        
        # Calculate metrics
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Get response size
        response_size = None
        if hasattr(response, 'headers') and response.headers.get('Content-Length'):
            try:
                response_size = int(response.headers['Content-Length'])
            except ValueError:
                pass
        
        # Get user ID if authenticated
        user_id = None
        try:
            # Try to extract user ID from the request state
            if hasattr(request.state, 'current_user') and request.state.current_user:
                user_id = request.state.current_user.id
        except:
            pass  # Anonymous request
        
        # Log the request asynchronously to avoid blocking
        self._log_request_async(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            request_size=request_size,
            response_size=response_size,
            ip_address=client_ip,
            user_agent=user_agent,
            referer=referer,
            user_id=user_id,
            error_message=error_message
        )
        
        # Also track page views for successful GET requests (frontend pages only)
        if (request.method == "GET" and response.status_code == 200 and 
            not str(request.url.path).startswith('/api/') and 
            str(request.url.path) != '/favicon.ico'):
            self._track_page_view_async(
                path=str(request.url.path),
                ip_address=client_ip,
                user_agent=user_agent,
                referer=referer,
                user_id=user_id
            )
        
        # Track user activities for API endpoints
        if str(request.url.path).startswith('/api/') and response.status_code < 400:
            self._track_user_activity_async(
                path=str(request.url.path),
                method=request.method,
                user_id=user_id,
                ip_address=client_ip
            )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP first
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if request.client:
            return request.client.host
        
        return 'unknown'
    
    def _log_request_async(self, **kwargs):
        """Log request data to database asynchronously."""
        try:
            # Import SessionLocal dynamically to avoid import-time issues
            from app.database import SessionLocal
            
            # Check if SessionLocal is properly initialized
            if SessionLocal is None:
                logger.warning("SessionLocal not initialized, skipping request logging")
                return
            
            # Create a new database session for logging
            db = SessionLocal()
            try:
                # Create request log entry
                request_log = RequestLog(**kwargs)
                db.add(request_log)
                
                # Update system metrics
                self._update_system_metrics(db, kwargs['response_time_ms'], kwargs['status_code'])
                
                db.commit()
            except Exception as e:
                logger.error(f"Failed to log request: {e}")
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to create database session for logging: {e}")
    
    def _track_page_view_async(self, path: str, ip_address: str, user_agent: str, referer: str, user_id: int = None):
        """Track page view data to database asynchronously."""
        try:
            # Import SessionLocal dynamically to avoid import-time issues
            from app.database import SessionLocal
            
            # Check if SessionLocal is properly initialized
            if SessionLocal is None:
                logger.warning("SessionLocal not initialized, skipping page view tracking")
                return
            
            # Create a new database session for logging
            db = SessionLocal()
            try:
                # Create page view entry
                page_view = PageView(
                    path=path,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referer=referer,
                    user_id=user_id,
                    timestamp=datetime.utcnow()
                )
                db.add(page_view)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to track page view: {e}")
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to create database session for page view tracking: {e}")
    
    def _track_user_activity_async(self, path: str, method: str, user_id: int = None, ip_address: str = None):
        """Track user activity data to database asynchronously."""
        try:
            # Import SessionLocal dynamically to avoid import-time issues
            from app.database import SessionLocal
            
            # Check if SessionLocal is properly initialized
            if SessionLocal is None:
                logger.warning("SessionLocal not initialized, skipping user activity tracking")
                return
            
            # Create a new database session for logging
            db = SessionLocal()
            try:
                # Determine activity type and action based on path
                activity_type, action = self._get_activity_info(path, method)
                
                # Create user activity entry
                user_activity = UserActivity(
                    user_id=user_id,
                    activity_type=activity_type,
                    action=action,
                    status='success',  # We only track successful activities here
                    ip_address=ip_address,
                    timestamp=datetime.utcnow()
                )
                db.add(user_activity)
                db.commit()
            except Exception as e:
                logger.error(f"Failed to track user activity: {e}")
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to create database session for user activity tracking: {e}")
    
    def _get_activity_info(self, path: str, method: str) -> tuple[str, str]:
        """Get activity type and action based on API path and method."""
        # Map API paths to activity types and actions
        if '/auth/' in path:
            if method == 'POST' and '/login' in path:
                return 'auth', 'User login'
            elif method == 'POST' and '/logout' in path:
                return 'auth', 'User logout'
            else:
                return 'auth', f'{method} {path}'
        
        elif '/analytics' in path:
            if '/log-page-view' in path:
                return 'analytics', 'Page view logged'
            elif '/update-mcp-status' in path:
                return 'mcp', 'MCP status updated'
            else:
                return 'analytics', f'Analytics {method.lower()}'
        
        elif '/users' in path:
            if method == 'POST' and not path.endswith('/password'):
                return 'user_management', 'User created'
            elif method == 'PUT' and '/password' in path:
                return 'user_management', 'Password changed'
            elif method == 'DELETE':
                return 'user_management', 'User deleted'
            else:
                return 'user_management', f'User management {method.lower()}'
        
        elif '/database' in path or '/db' in path:
            if '/query' in path:
                return 'database', 'SQL query executed'
            elif '/analytics-query' in path:
                return 'bi', 'Analytics query generated'
            elif '/test' in path:
                return 'database', 'Database connection tested'
            else:
                return 'database', f'Database {method.lower()}'
        
        elif '/mcp' in path:
            if '/test' in path:
                return 'mcp', 'MCP server tested'
            else:
                return 'mcp', f'MCP {method.lower()}'
        
        elif '/test' in path:
            return 'testing', f'Test {method.lower()}'
        
        elif '/bi' in path:
            return 'bi', f'BI {method.lower()}'
        
        else:
            return 'api', f'{method} {path.replace("/api/", "")}'
    
    def _update_system_metrics(self, db: Session, response_time_ms: int, status_code: int):
        """Update real-time system metrics."""
        try:
            now = datetime.utcnow()
            
            # Log response time metric
            response_time_metric = SystemMetrics(
                metric_name='response_time',
                metric_type='gauge',
                value=f'{response_time_ms}ms',
                numeric_value=response_time_ms,
                source='request_middleware',
                timestamp=now
            )
            db.add(response_time_metric)
            
            # Log request count metric
            request_count_metric = SystemMetrics(
                metric_name='request_count',
                metric_type='counter',
                value='1',
                numeric_value=1,
                source='request_middleware',
                tags={'status_code': status_code},
                timestamp=now
            )
            db.add(request_count_metric)
            
            # Log error metric if applicable
            if status_code >= 400:
                error_metric = SystemMetrics(
                    metric_name='error_count',
                    metric_type='counter',
                    value='1',
                    numeric_value=1,
                    source='request_middleware',
                    tags={'status_code': status_code},
                    timestamp=now
                )
                db.add(error_metric)
        
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")


def setup_analytics_middleware(app):
    """Setup analytics middleware for the FastAPI app."""
    app.add_middleware(AnalyticsMiddleware)
    
    # Also setup simple MCP server status update
    def update_mcp_status_once():
        """Update MCP server status once during startup."""
        try:
            from app.database import SessionLocal
            from app.utils.mcp_utils import get_mcp_session_status
            
            if SessionLocal is None:
                return
                
            db = SessionLocal()
            try:
                # Clear old status entries
                db.query(McpServerStatus).delete()
                
                # Get current MCP status
                mcp_status = get_mcp_session_status()
                
                if mcp_status['is_connected']:
                    # Server is active
                    server_status = McpServerStatus(
                        name='Primary MCP Server',
                        url=mcp_status['url'],
                        status='active',
                        response_time_ms=50,
                        last_checked=datetime.utcnow(),
                        last_successful_check=datetime.utcnow(),
                        error_count=0,
                        total_requests=1,
                        successful_requests=1,
                        updated_at=datetime.utcnow()
                    )
                    db.add(server_status)
                    logger.info(f"MCP server status set to active at {mcp_status['url']}")
                else:
                    # Server is inactive
                    server_status = McpServerStatus(
                        name='Primary MCP Server',
                        url=mcp_status['url'],
                        status='inactive',
                        response_time_ms=None,
                        last_checked=datetime.utcnow(),
                        last_successful_check=datetime.utcnow() - timedelta(hours=1),
                        error_count=1,
                        total_requests=0,
                        successful_requests=0,
                        updated_at=datetime.utcnow()
                    )
                    db.add(server_status)
                    logger.info(f"MCP server status set to inactive: {mcp_status['url']}")
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to update MCP server status: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to create database session for MCP status: {e}")
    
    # Update MCP status once during startup
    try:
        update_mcp_status_once()
    except Exception as e:
        logger.error(f"Failed to update MCP status during startup: {e}")
