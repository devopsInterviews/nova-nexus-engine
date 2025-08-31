# Analytics System Deep Dive

## 📊 Analytics Architecture Overview

The analytics system provides comprehensive monitoring, performance tracking, and user behavior analysis through a multi-layered approach.

## 🏗️ System Components

### 1. Analytics Middleware (`app/middleware/analytics.py`)

**Purpose**: Automatically capture all HTTP request data

**What It Does**:
- Wraps every incoming HTTP request
- Captures performance metrics (response time, request size)
- Extracts user context (authenticated user, IP address)
- Logs errors and exceptions
- Categorizes activities by API endpoint
- Stores data asynchronously to avoid blocking requests

**Key Methods**:
- `dispatch()`: Main request processing wrapper
- `_extract_user_from_token()`: JWT token parsing for user identification
- `_log_request_async()`: Database logging without blocking
- `_get_activity_info()`: Categorizes requests into meaningful activities

### 2. Analytics Service (`app/services/analytics_service.py`)

**Purpose**: Background processing and real-time analytics management

**Responsibilities**:
- Real-time data collection coordination
- Background monitoring tasks
- Data aggregation and processing
- Real-time metrics calculation

### 3. Analytics Routes (`app/routes/analytics_routes.py`)

**Purpose**: API endpoints for dashboard and metrics

**Key Endpoints**:
- `/analytics/system-overview`: Dashboard statistics
- `/analytics/key-metrics`: Performance metrics
- `/analytics/top-pages`: Most visited pages
- `/analytics/error-analysis`: Error categorization

## 📈 Data Collection Strategy

### Request Logging

**Every HTTP request captures**:
```python
RequestLog(
    method='GET',                    # HTTP method
    path='/api/users',              # Request path
    status_code=200,                # Response status
    response_time_ms=45,            # Performance timing
    request_size=1024,              # Request body size
    response_size=2048,             # Response body size
    ip_address='192.168.1.100',     # Client IP
    user_agent='Mozilla/5.0...',    # Browser/client info
    user_id=123,                    # Authenticated user (if any)
    timestamp=datetime.utcnow()     # Request timestamp
)
```

### User Activity Tracking

**API requests categorized by functionality**:
```python
UserActivity(
    user_id=123,                    # User performing action
    activity_type='database',      # Category (auth, database, mcp, etc.)
    action='SQL query executed',   # Specific action description
    status='success',              # success/failure/error
    ip_address='192.168.1.100',   # Client IP
    timestamp=datetime.utcnow()    # Activity timestamp
)
```

### Page View Tracking

**Frontend navigation monitoring**:
```python
PageView(
    path='/analytics',             # Page route
    title='Analytics Dashboard',   # Page title
    user_id=123,                  # Authenticated user
    session_id='abc123',          # Session identifier
    load_time_ms=1200,           # Page load performance
    referer='/dashboard',         # Previous page
    timestamp=datetime.utcnow()   # Visit timestamp
)
```

### System Metrics

**Real-time performance indicators**:
```python
SystemMetrics(
    metric_name='response_time',   # Metric identifier
    metric_type='gauge',          # gauge/counter/histogram
    value='45ms',                 # Human-readable value
    numeric_value=45,             # Numeric value for calculations
    source='request_middleware',  # Data source
    timestamp=datetime.utcnow()   # Metric timestamp
)
```

## 🎯 Activity Classification

### Activity Types & Meanings

**Authentication Activities** (`activity_type: 'auth'`):
- User login/logout
- Token refresh
- Password changes
- Registration attempts

**Database Activities** (`activity_type: 'database'`):
- SQL query execution
- Connection testing
- Schema exploration
- Data export operations

**User Management** (`activity_type: 'user_management'`):
- User creation/deletion
- Permission changes
- Profile updates
- Admin operations

**MCP Activities** (`activity_type: 'mcp'`):
- MCP server connections
- Tool executions
- Webhook processing
- AI model interactions

**Analytics Activities** (`activity_type: 'analytics'`):
- Dashboard views
- Report generation
- Metric queries
- System monitoring

### Classification Logic

```python
def _get_activity_info(self, path: str, method: str) -> tuple[str, str]:
    """
    Examples of path-to-activity mapping:
    
    POST /api/auth/login → ('auth', 'User login')
    GET /api/database/query → ('database', 'SQL query executed')
    POST /api/users → ('user_management', 'User created')
    GET /api/mcp/tools → ('mcp', 'MCP tools listed')
    POST /api/analytics/log-page-view → ('analytics', 'Page view logged')
    """
```

## 📊 Dashboard Metrics

### System Overview Calculations

**1. System Uptime**:
```sql
-- Calculate uptime as percentage of successful requests
SELECT 
    (COUNT(*) FILTER (WHERE status_code < 400) * 100.0 / COUNT(*)) as uptime_percentage
FROM request_logs 
WHERE timestamp >= NOW() - INTERVAL '30 days';
```

**2. Active Users**:
```sql
-- Count unique users who logged in within last 24 hours
SELECT COUNT(DISTINCT id) 
FROM users 
WHERE last_login >= NOW() - INTERVAL '24 hours';
```

**3. Response Time (95th Percentile)**:
```sql
-- Get 95th percentile response time for performance monitoring
SELECT response_time_ms 
FROM request_logs 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
  AND response_time_ms IS NOT NULL
ORDER BY response_time_ms
LIMIT 1 OFFSET (
    SELECT COUNT(*) * 0.95 
    FROM request_logs 
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
);
```

**4. Error Rate**:
```sql
-- Calculate error percentage
SELECT 
    (COUNT(*) FILTER (WHERE status_code >= 400) * 100.0 / COUNT(*)) as error_rate
FROM request_logs 
WHERE timestamp >= NOW() - INTERVAL '24 hours';
```

### Top Pages Analysis

```sql
-- Most visited pages in last 24 hours
SELECT 
    path,
    COUNT(*) as views,
    COUNT(DISTINCT user_id) as unique_users
FROM page_views 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY path 
ORDER BY views DESC 
LIMIT 10;
```

### Error Analysis

```sql
-- Error breakdown by status code
SELECT 
    status_code,
    COUNT(*) as error_count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM request_logs 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
  AND status_code >= 400
GROUP BY status_code 
ORDER BY error_count DESC;
```

## 🔄 Real-time Processing

### Asynchronous Logging

**Why Async?**
- Prevents analytics from blocking user requests
- Handles database connection failures gracefully
- Scales better under high load
- Separates concerns (user experience vs. monitoring)

**Implementation**:
```python
def _log_request_async(self, **kwargs):
    """
    Logs request data without blocking the HTTP response.
    Creates new database session to avoid connection conflicts.
    Handles logging failures gracefully.
    """
    try:
        db = SessionLocal()
        request_log = RequestLog(**kwargs)
        db.add(request_log)
        db.commit()
    except Exception as e:
        logger.error(f"Analytics logging failed: {e}")
        # Failure doesn't affect user request
    finally:
        db.close()
```

### Performance Impact

**Middleware Overhead**:
- ~1-2ms per request for data collection
- Async logging adds no response time
- Memory efficient with immediate database writes
- Database indexes optimize query performance

**Database Performance**:
- Indexes on timestamp columns for fast queries
- Separate analytics database connection pool
- Configurable data retention policies
- Batch processing for heavy analytics queries

## 📱 Frontend Analytics Integration

### Page View Tracker

**Component**: `PageViewTracker.tsx`

**Functionality**:
```typescript
// Automatically tracks route changes
useEffect(() => {
    const trackPageView = async () => {
        await fetch('/api/analytics/log-page-view', {
            method: 'POST',
            body: JSON.stringify({
                path: location.pathname,
                title: document.title,
                loadTime: performance.now()
            })
        });
    };
    
    trackPageView();
}, [location]);
```

### Real-time Dashboard Updates

**Auto-refresh Strategy**:
```typescript
// Dashboard refreshes every 30 seconds
useEffect(() => {
    const interval = setInterval(() => {
        refetchMetrics();
    }, 30000);
    
    return () => clearInterval(interval);
}, []);
```

## 🔧 Development & Debugging

### Analytics Testing

**Real Data Collection**:
The analytics system captures real data automatically through:
- Analytics middleware logging all HTTP requests
- MCP server health monitoring
- User activity tracking
- System performance metrics

**Testing Endpoints**:
- `GET /api/analytics/db-status`: Database schema validation
- `POST /api/analytics/update-mcp-status`: Manual status updates
- Debug logging for troubleshooting

### Performance Monitoring

**Key Metrics to Watch**:
- Analytics middleware execution time
- Database connection pool usage
- Memory consumption of logging queues
- Failed analytics writes (should be rare)

### Configuration Options

**Environment Variables**:
```bash
# Analytics configuration
ANALYTICS_ENABLED=true
ANALYTICS_BATCH_SIZE=100
ANALYTICS_RETENTION_DAYS=90
ANALYTICS_ASYNC_TIMEOUT=5

# Database performance
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

## 🎯 Business Intelligence Use Cases

### User Behavior Analysis

**Questions Answered**:
- Which features are most/least used?
- What's the typical user journey through the app?
- When do users typically log in and for how long?
- Which database operations are most common?

**Data Sources**:
- `user_activities` for feature usage
- `page_views` for navigation patterns
- `request_logs` for API usage trends

### Performance Optimization

**Insights Provided**:
- Slowest API endpoints requiring optimization
- Peak usage times for capacity planning
- Error patterns indicating system issues
- User experience impact of performance changes

### Security Monitoring

**Security Analytics**:
- Failed login attempts from specific IPs
- Unusual access patterns or times
- Admin operation audit trails
- Suspicious database query patterns

## 🔒 Privacy & Compliance

### Data Protection

**What We DON'T Log**:
- User passwords or sensitive credentials
- Personal data beyond usernames/emails
- Full request/response bodies with sensitive info
- Credit card or payment information

**What We DO Log**:
- Request performance metrics
- Feature usage patterns
- Error rates and system health
- User activity for audit purposes

### GDPR Compliance

**User Rights**:
- Data export: Users can request their analytics data
- Data deletion: Analytics data removed on account deletion
- Data minimization: Only necessary data collected
- Retention limits: Configurable data retention periods

### Security Measures

**Analytics Data Security**:
- Database encryption at rest
- Secure transmission (HTTPS)
- Access controls on analytics endpoints
- Regular security audits of logged data

This analytics system provides comprehensive insights while maintaining performance, security, and user privacy standards.
