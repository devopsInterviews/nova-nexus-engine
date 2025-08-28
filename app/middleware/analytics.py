"""
Analytics middleware for request logging and monitoring.

This middleware automatically logs all requests for analytics purposes,
tracking performance metrics, error rates, and usage patterns.
"""

import time
import logging
from datetime import datetime
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.models import RequestLog, SystemMetrics

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
