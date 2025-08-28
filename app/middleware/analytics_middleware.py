"""
Analytics middleware for tracking real user interactions.
"""

import time
import logging
from datetime import datetime
from typing import Optional
from fastapi import Request, Response
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AnalyticsMiddleware:
    """Middleware to track real user interactions and API usage."""
    
    def __init__(self):
        self.start_time = time.time()
    
    async def __call__(self, request: Request, call_next):
        """Process request and track analytics data."""
        start_time = time.time()
        
        # Call the next middleware/route
        response = await call_next(request)
        
        # Calculate response time
        process_time = time.time() - start_time
        response_time_ms = int(process_time * 1000)
        
        # Track the request asynchronously (don't block response)
        try:
            await self._track_request(request, response, response_time_ms)
        except Exception as e:
            logger.warning(f"Failed to track analytics: {e}")
        
        return response
    
    async def _track_request(self, request: Request, response: Response, response_time_ms: int):
        """Track request data in the database."""
        try:
            from app.database import SessionLocal
            from app.models import RequestLog, PageView
            
            if not SessionLocal:
                return
            
            db = SessionLocal()
            try:
                # Get user info if available
                user_id = None
                try:
                    # Try to get user from request state (set by auth middleware)
                    user_id = getattr(request.state, 'user_id', None)
                except:
                    pass
                
                # Extract client info
                client_ip = self._get_client_ip(request)
                user_agent = request.headers.get('user-agent', '')
                referer = request.headers.get('referer', '')
                
                # Track API requests (RequestLog)
                if request.url.path.startswith('/api/'):
                    request_log = RequestLog(
                        method=request.method,
                        path=str(request.url.path),
                        status_code=response.status_code,
                        response_time_ms=response_time_ms,
                        request_size=self._get_request_size(request),
                        response_size=len(response.body) if hasattr(response, 'body') else None,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        referer=referer,
                        user_id=user_id,
                        error_message=None if response.status_code < 400 else f"HTTP {response.status_code}",
                        timestamp=datetime.utcnow()
                    )
                    db.add(request_log)
                
                # Track page views for frontend routes (PageView)
                if (request.method == 'GET' and 
                    not request.url.path.startswith('/api/') and 
                    not request.url.path.startswith('/static/') and
                    response.status_code == 200):
                    
                    page_view = PageView(
                        path=str(request.url.path),
                        title=self._get_page_title(request.url.path),
                        user_id=user_id,
                        session_id=self._get_session_id(request),
                        ip_address=client_ip,
                        user_agent=user_agent,
                        referer=referer,
                        load_time_ms=response_time_ms,
                        timestamp=datetime.utcnow()
                    )
                    db.add(page_view)
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Failed to save analytics data: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Analytics middleware error: {e}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
    
    def _get_request_size(self, request: Request) -> Optional[int]:
        """Get request content length."""
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                return int(content_length)
            except:
                pass
        return None
    
    def _get_session_id(self, request: Request) -> str:
        """Get or generate session ID."""
        # Try to get session from cookies or headers
        session_id = request.headers.get('x-session-id')
        if not session_id:
            # Generate a simple session ID from IP + User-Agent
            ip = self._get_client_ip(request)
            ua = request.headers.get('user-agent', '')
            session_id = f"sess_{hash(f'{ip}_{ua}')}"[-8:]
        return session_id
    
    def _get_page_title(self, path: str) -> str:
        """Convert path to human-readable title."""
        if path == '/':
            return 'Home'
        
        # Remove leading slash and convert to title
        clean_path = path.lstrip('/')
        
        # Map common paths
        title_map = {
            'bi': 'Business Intelligence',
            'analytics': 'Analytics Dashboard',
            'devops': 'DevOps Tools',
            'tests': 'Testing Suite',
            'users': 'User Management',
            'settings': 'Settings',
            'login': 'Login Page',
            'home': 'Home Dashboard'
        }
        
        if clean_path in title_map:
            return title_map[clean_path]
        
        # Default: capitalize and replace hyphens/underscores
        parts = clean_path.replace('-', ' ').replace('_', ' ').split('/')
        return ' '.join(word.capitalize() for word in parts if word)


# Global middleware instance
analytics_middleware = AnalyticsMiddleware()
