"""
Analytics routes for system metrics and performance monitoring.

This module provides endpoints for:
- System metrics (uptime, response time, active users, etc.)
- Request analytics and traffic analysis
- Error tracking and analysis
- MCP server health monitoring
- Page view analytics
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, desc, text
from sqlalchemy.orm import Session

from app.database import get_db_session, User
from app.routes.auth_routes import get_current_user
from app.models import SystemMetrics, RequestLog, McpServerStatus, PageView, UserActivity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/system-overview")
async def get_system_overview(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get system overview statistics for the homepage dashboard.
    
    Returns:
        - System uptime percentage
        - Active MCP servers count
        - Average response time
        - Active users count
        - Recent activity events
    """
    try:
        # Calculate system uptime (based on successful vs failed requests in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        total_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= thirty_days_ago
        ).scalar() or 0
        
        successful_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= thirty_days_ago,
            RequestLog.status_code < 400
        ).scalar() or 0
        
        uptime_percentage = (successful_requests / total_requests * 100) if total_requests > 0 else 100.0
        
        # Get active MCP servers count
        active_servers = db.query(func.count(McpServerStatus.id)).filter(
            McpServerStatus.status == 'active'
        ).scalar() or 0
        
        # Calculate average response time (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        avg_response_time = db.query(func.avg(RequestLog.response_time_ms)).filter(
            RequestLog.timestamp >= yesterday,
            RequestLog.response_time_ms.isnot(None)
        ).scalar() or 0
        
        # Get active users count (users who logged in within last 24 hours)
        active_users = db.query(func.count(User.id.distinct())).filter(
            User.last_login >= yesterday
        ).scalar() or 0
        
        # Get recent activity (last 10 events)
        recent_activity = db.query(UserActivity).order_by(
            desc(UserActivity.timestamp)
        ).limit(10).all()
        
        # Calculate trends (compare with previous period)
        week_ago = datetime.utcnow() - timedelta(days=7)
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        
        # Server count trend
        servers_last_week = db.query(func.count(McpServerStatus.id)).filter(
            McpServerStatus.status == 'active',
            McpServerStatus.updated_at >= week_ago
        ).scalar() or 0
        
        servers_prev_week = db.query(func.count(McpServerStatus.id)).filter(
            McpServerStatus.status == 'active',
            McpServerStatus.updated_at >= two_weeks_ago,
            McpServerStatus.updated_at < week_ago
        ).scalar() or 0
        
        server_trend = servers_last_week - servers_prev_week
        
        # Response time trend
        avg_response_last_week = db.query(func.avg(RequestLog.response_time_ms)).filter(
            RequestLog.timestamp >= week_ago,
            RequestLog.response_time_ms.isnot(None)
        ).scalar() or 0
        
        avg_response_prev_week = db.query(func.avg(RequestLog.response_time_ms)).filter(
            RequestLog.timestamp >= two_weeks_ago,
            RequestLog.timestamp < week_ago,
            RequestLog.response_time_ms.isnot(None)
        ).scalar() or 0
        
        response_time_trend = avg_response_last_week - avg_response_prev_week
        
        # Active users trend
        users_last_week = db.query(func.count(User.id.distinct())).filter(
            User.last_login >= week_ago
        ).scalar() or 0
        
        users_prev_week = db.query(func.count(User.id.distinct())).filter(
            User.last_login >= two_weeks_ago,
            User.last_login < week_ago
        ).scalar() or 0
        
        users_trend = users_last_week - users_prev_week
        
        return {
            "status": "success",
            "data": {
                "stats": [
                    {
                        "title": "System Uptime",
                        "value": f"{uptime_percentage:.1f}%",
                        "description": "Last 30 days",
                        "status": "success" if uptime_percentage >= 99.0 else "warning" if uptime_percentage >= 95.0 else "error",
                        "trend": "stable",
                        "trendValue": f"{uptime_percentage - 99.0:+.1f}%"
                    },
                    {
                        "title": "Active Servers",
                        "value": str(active_servers),
                        "description": "Connected MCP servers",
                        "status": "success" if active_servers > 0 else "warning",
                        "trend": "up" if server_trend > 0 else "down" if server_trend < 0 else "stable",
                        "trendValue": f"{server_trend:+d}" if server_trend != 0 else "0"
                    },
                    {
                        "title": "Response Time",
                        "value": f"{int(avg_response_time)}ms",
                        "description": "Average latency",
                        "status": "success" if avg_response_time < 100 else "warning" if avg_response_time < 500 else "error",
                        "trend": "down" if response_time_trend < 0 else "up" if response_time_trend > 0 else "stable",
                        "trendValue": f"{response_time_trend:+.0f}ms" if response_time_trend != 0 else "0ms"
                    },
                    {
                        "title": "Active Users",
                        "value": str(active_users),
                        "description": "Last 24 hours",
                        "status": "info",
                        "trend": "up" if users_trend > 0 else "down" if users_trend < 0 else "stable",
                        "trendValue": f"{users_trend:+d}" if users_trend != 0 else "0"
                    }
                ],
                "recentActivity": [
                    {
                        "action": activity.action,
                        "status": "Completed" if activity.status == "success" else "Failed" if activity.status == "error" else "Running",
                        "time": _time_ago(activity.timestamp),
                        "type": "success" if activity.status == "success" else "error" if activity.status == "error" else "warning"
                    }
                    for activity in recent_activity
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get system overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch system overview")


@router.get("/key-metrics")
async def get_key_metrics(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get key analytics metrics for the analytics dashboard.
    
    Returns:
        - Total requests (24h)
        - Active sessions
        - Response time (95th percentile)
        - Error rate
    """
    try:
        # Calculate metrics for last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Total requests
        total_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= yesterday
        ).scalar() or 0
        
        # Previous day for comparison
        day_before = datetime.utcnow() - timedelta(days=2)
        prev_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= day_before,
            RequestLog.timestamp < yesterday
        ).scalar() or 0
        
        requests_change = ((total_requests - prev_requests) / prev_requests * 100) if prev_requests > 0 else 0
        
        # Active sessions (unique users in last hour)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        active_sessions = db.query(func.count(User.id.distinct())).filter(
            User.last_login >= hour_ago
        ).scalar() or 0
        
        # Previous hour for comparison
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        prev_sessions = db.query(func.count(User.id.distinct())).filter(
            User.last_login >= two_hours_ago,
            User.last_login < hour_ago
        ).scalar() or 0
        
        sessions_change = ((active_sessions - prev_sessions) / prev_sessions * 100) if prev_sessions > 0 else 0
        
        # Response time (95th percentile)
        response_times = db.execute(text("""
            SELECT response_time_ms 
            FROM request_logs 
            WHERE timestamp >= :yesterday 
              AND response_time_ms IS NOT NULL 
            ORDER BY response_time_ms
        """), {"yesterday": yesterday}).fetchall()
        
        if response_times:
            times = [row[0] for row in response_times]
            percentile_95_index = int(len(times) * 0.95)
            response_time_95th = times[percentile_95_index] if percentile_95_index < len(times) else times[-1]
        else:
            response_time_95th = 0
        
        # Previous day response time for comparison
        prev_response_times = db.execute(text("""
            SELECT response_time_ms 
            FROM request_logs 
            WHERE timestamp >= :day_before 
              AND timestamp < :yesterday
              AND response_time_ms IS NOT NULL 
            ORDER BY response_time_ms
        """), {"day_before": day_before, "yesterday": yesterday}).fetchall()
        
        if prev_response_times:
            prev_times = [row[0] for row in prev_response_times]
            prev_percentile_95_index = int(len(prev_times) * 0.95)
            prev_response_time_95th = prev_times[prev_percentile_95_index] if prev_percentile_95_index < len(prev_times) else prev_times[-1]
        else:
            prev_response_time_95th = response_time_95th
            
        response_time_change = response_time_95th - prev_response_time_95th
        
        # Error rate
        error_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= yesterday,
            RequestLog.status_code >= 400
        ).scalar() or 0
        
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Previous day error rate for comparison
        prev_error_requests = db.query(func.count(RequestLog.id)).filter(
            RequestLog.timestamp >= day_before,
            RequestLog.timestamp < yesterday,
            RequestLog.status_code >= 400
        ).scalar() or 0
        
        prev_error_rate = (prev_error_requests / prev_requests * 100) if prev_requests > 0 else 0
        error_rate_change = error_rate - prev_error_rate
        
        return {
            "status": "success",
            "data": {
                "metrics": [
                    {
                        "title": "Total Requests",
                        "value": _format_number(total_requests),
                        "description": "Last 24 hours",
                        "status": "success",
                        "trend": "up" if requests_change > 0 else "down" if requests_change < 0 else "stable",
                        "trendValue": f"{requests_change:+.1f}%"
                    },
                    {
                        "title": "Active Sessions",
                        "value": str(active_sessions),
                        "description": "Current active users",
                        "status": "info",
                        "trend": "up" if sessions_change > 0 else "down" if sessions_change < 0 else "stable",
                        "trendValue": f"{sessions_change:+.1f}%"
                    },
                    {
                        "title": "Response Time",
                        "value": f"{response_time_95th}ms",
                        "description": "95th percentile",
                        "status": "success" if response_time_95th < 200 else "warning" if response_time_95th < 1000 else "error",
                        "trend": "down" if response_time_change < 0 else "up" if response_time_change > 0 else "stable",
                        "trendValue": f"{response_time_change:+d}ms"
                    },
                    {
                        "title": "Error Rate",
                        "value": f"{error_rate:.2f}%",
                        "description": "Last hour",
                        "status": "success" if error_rate < 1 else "warning" if error_rate < 5 else "error",
                        "trend": "down" if error_rate_change < 0 else "up" if error_rate_change > 0 else "stable",
                        "trendValue": f"{error_rate_change:+.2f}%"
                    }
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get key metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch key metrics")


@router.get("/top-pages")
async def get_top_pages(
    limit: int = 10,
    hours: int = 24,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get top pages by view count.
    
    Args:
        limit: Number of pages to return (default: 10)
        hours: Time window in hours (default: 24)
    """
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        prev_threshold = datetime.utcnow() - timedelta(hours=hours*2)
        
        # Current period page views
        current_views = db.execute(text("""
            SELECT path, COUNT(*) as views
            FROM page_views 
            WHERE timestamp >= :threshold
            GROUP BY path 
            ORDER BY views DESC 
            LIMIT :limit
        """), {"threshold": time_threshold, "limit": limit}).fetchall()
        
        # Previous period page views for comparison
        prev_views = db.execute(text("""
            SELECT path, COUNT(*) as views
            FROM page_views 
            WHERE timestamp >= :prev_threshold 
              AND timestamp < :threshold
            GROUP BY path
        """), {"prev_threshold": prev_threshold, "threshold": time_threshold}).fetchall()
        
        # Create lookup dict for previous period
        prev_views_dict = {row[0]: row[1] for row in prev_views}
        
        top_pages = []
        for path, views in current_views:
            prev_views_count = prev_views_dict.get(path, 0)
            change = ((views - prev_views_count) / prev_views_count * 100) if prev_views_count > 0 else 100
            
            top_pages.append({
                "path": path,
                "views": _format_number(views),
                "change": f"{change:+.0f}%"
            })
        
        return {
            "status": "success",
            "data": {
                "topPages": top_pages
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get top pages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top pages")


@router.get("/error-analysis")
async def get_error_analysis(
    hours: int = 24,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get error analysis by status code.
    
    Args:
        hours: Time window in hours (default: 24)
    """
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        # Get error counts by status code
        error_counts = db.execute(text("""
            SELECT status_code, COUNT(*) as count
            FROM request_logs 
            WHERE timestamp >= :threshold 
              AND status_code >= 400
            GROUP BY status_code 
            ORDER BY count DESC
        """), {"threshold": time_threshold}).fetchall()
        
        total_errors = sum(count for _, count in error_counts)
        
        # Map status codes to descriptions
        status_descriptions = {
            400: "400 Bad Request",
            401: "401 Unauthorized", 
            403: "403 Forbidden",
            404: "404 Not Found",
            500: "500 Internal Server Error",
            502: "502 Bad Gateway",
            503: "503 Service Unavailable",
            504: "504 Gateway Timeout"
        }
        
        errors_by_type = []
        for status_code, count in error_counts:
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            description = status_descriptions.get(status_code, f"{status_code} Error")
            
            errors_by_type.append({
                "type": description,
                "count": count,
                "percentage": int(percentage)
            })
        
        return {
            "status": "success",
            "data": {
                "errorsByType": errors_by_type
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get error analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch error analysis")


@router.post("/log-page-view")
async def log_page_view(
    request: Request,
    data: Dict[str, Any],
    db: Session = Depends(get_db_session)
):
    """
    Log a page view for analytics.
    
    Expected data:
        - path: Page path
        - title: Page title (optional)
        - loadTime: Page load time in ms (optional)
    """
    try:
        # Get client IP
        client_ip = request.client.host if request.client else None
        if hasattr(request, 'headers'):
            # Check for forwarded IP
            forwarded = request.headers.get('X-Forwarded-For')
            if forwarded:
                client_ip = forwarded.split(',')[0].strip()
        
        # Get user agent
        user_agent = request.headers.get('User-Agent') if hasattr(request, 'headers') else None
        
        # Get referer
        referer = request.headers.get('Referer') if hasattr(request, 'headers') else None
        
        # Try to get current user (optional)
        user_id = None
        try:
            from app.routes.auth_routes import get_current_user_optional
            current_user = await get_current_user_optional(db, request)
            if current_user:
                user_id = current_user.id
        except:
            pass  # Anonymous user
        
        # Create page view record
        page_view = PageView(
            path=data.get('path', '/'),
            title=data.get('title'),
            user_id=user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            referer=referer,
            load_time_ms=data.get('loadTime')
        )
        
        db.add(page_view)
        db.commit()
        
        return {"status": "success", "message": "Page view logged"}
        
    except Exception as e:
        logger.error(f"Failed to log page view: {e}")
        db.rollback()
        return {"status": "error", "message": "Failed to log page view"}


# Helper functions
def _time_ago(timestamp: datetime) -> str:
    """Convert timestamp to human-readable time ago format."""
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.total_seconds() < 60:
        return f"{int(diff.total_seconds())} sec ago"
    elif diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() // 60)} min ago"
    elif diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() // 3600)} hr ago"
    else:
        return f"{int(diff.total_seconds() // 86400)} day ago"


def _format_number(num: int) -> str:
    """Format number with K/M suffixes."""
    if num >= 1000000:
        return f"{num / 1000000:.1f}M"
    elif num >= 1000:
        return f"{num / 1000:.1f}K"
    else:
        return str(num)
