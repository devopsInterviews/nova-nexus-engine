# User Flow & System Integration Guide

## 🔄 Complete User Journey

This document provides a comprehensive walkthrough of the user experience and system interactions within MCP Client.

## 🚪 Initial Access & Authentication

### 1. Application Startup
```
User visits http://localhost:5173
↓
React App loads (App.tsx)
↓
AuthProvider initializes (auth-context.tsx)
↓
Check localStorage for 'auth_token'
↓
If token exists: Validate with backend
If no token: Redirect to /login
```

### 2. Login Process (Detailed)
```
LoginScreen.tsx renders with cyberpunk robot animation
↓
User enters username & password
↓
React Hook Form validates input
↓
AuthContext.login() called
↓
POST /api/login {username, password}
↓
Backend auth_routes.py processes request
↓
User.check_password() validates credentials
↓
JWT token generated (2-hour expiration)
↓
User.last_login & login_count updated
↓
Token + user data returned to frontend
↓
localStorage stores 'auth_token' & 'auth_user'
↓
AuthContext updates global state
↓
React Router redirects to dashboard (/)
↓
AppLayout renders with navigation
```

**Database Changes During Login:**
- `users.last_login` = current timestamp
- `users.login_count` += 1
- `user_activities` record created (activity_type: 'auth', action: 'User login')
- `request_logs` entry for login API call

### 3. Session Management
```
Every 5 minutes: Token validation check
↓
If token expired: Auto-logout + redirect to login
If token valid: Continue session
↓
Every API call includes Authorization: Bearer <token>
↓
Backend get_current_user() validates token
↓
User object attached to request context
```

## 🏠 Dashboard Experience

### 1. Home Page Load
```
Home.tsx component mounts
↓
useEffect triggers data fetching
↓
Multiple API calls executed in parallel:
- GET /api/analytics/system-overview
- GET /api/analytics/key-metrics  
- GET /api/mcp/status (if applicable)
↓
Analytics middleware logs page view
↓
Data rendered in dashboard cards
```

**Backend Processing:**
- Query `request_logs` for uptime calculation
- Query `user_activities` for recent activity
- Check MCP server connection status
- Return aggregated metrics

**Database Queries:**
```sql
-- Uptime calculation (last 30 days)
SELECT COUNT(*) FROM request_logs 
WHERE timestamp >= NOW() - INTERVAL '30 days' 
AND status_code < 400;

-- Active users (last 24 hours)  
SELECT COUNT(DISTINCT user_id) FROM users
WHERE last_login >= NOW() - INTERVAL '24 hours';

-- Response time (95th percentile)
SELECT response_time_ms FROM request_logs
WHERE timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY response_time_ms
LIMIT 1 OFFSET (SELECT COUNT(*) * 0.95 FROM request_logs);
```

### 2. Real-time Updates
```
Dashboard automatically refreshes every 30 seconds
↓
API calls repeat to get latest metrics
↓
Charts and numbers update with smooth animations
↓
Error states handled gracefully
```

## 🗄️ Database Management Flow

### 1. Connection Management
```
User clicks "Database" in navigation
↓
ConnectionContext loads saved connections
↓
GET /api/database/connections
↓
Database connections displayed in UI
↓
User can test, edit, or create connections
```

### 2. Creating New Connection
```
User clicks "Add Connection" button
↓
Modal form opens with connection fields
↓
User fills: host, port, database, username, password, type
↓
Form validation with React Hook Form
↓
POST /api/database/connections
↓
Backend creates DatabaseConnection model
↓
Password encrypted before storage
↓
Connection test performed
↓
Success/error feedback to user
↓
Connection list refreshed
```

**Database Changes:**
```sql
INSERT INTO database_connections (
    user_id, name, host, port, database, 
    username, encrypted_password, database_type,
    created_at, is_active
) VALUES (...);
```

### 3. Query Execution
```
User selects connection from dropdown
↓
SQL editor becomes available
↓
User enters SQL query
↓
Click "Execute" button
↓
POST /api/database/query
↓
Backend establishes database connection
↓
Query executed with timeout protection
↓
Results formatted and returned
↓
Table component renders results
↓
Export options available (CSV, JSON)
```

## 👥 User Management (Admin Only)

### 1. User Administration
```
Admin navigates to /users
↓
GET /api/users (admin-only endpoint)
↓
User list displayed with actions
↓
Admin can create, edit, delete users
↓
Permission assignments per tab/feature
```

### 2. Creating New User
```
Admin clicks "Create User"
↓
User form modal opens
↓
Admin enters: username, email, password, full_name
↓
Role selection (admin/regular user)
↓
POST /api/users
↓
Backend creates User model
↓
Password hashed with bcrypt
↓
User appears in list
↓
Email notification sent (if configured)
```

**Database Changes:**
```sql
INSERT INTO users (
    username, email, hashed_password, full_name,
    is_active, is_admin, created_at, login_count
) VALUES (...);
```

## 📊 Analytics Collection

### 1. Automatic Tracking
```
Every HTTP request triggers analytics middleware
↓
AnalyticsMiddleware.dispatch() processes request
↓
Captures: method, path, IP, user-agent, user_id
↓
Measures response time and status code
↓
Asynchronously logs to database
↓
Updates real-time metrics
```

### 2. Page View Tracking
```
PageViewTracker component on every route
↓
useEffect on route change
↓
POST /api/analytics/log-page-view
↓
Records: path, title, user_id, timestamp
↓
Used for user journey analysis
```

### 3. User Activity Classification
```
API request categorized by path:
- /api/auth/* → 'auth' activity
- /api/users/* → 'user_management' activity  
- /api/database/* → 'database' activity
- /api/mcp/* → 'mcp' activity
- /api/analytics/* → 'analytics' activity
↓
Stored in user_activities table
↓
Enables feature usage analysis
```

## 🤖 MCP Integration

### 1. Server Connection
```
App startup: MCP session established
↓
streamablehttp_client creates HTTP transport
↓
ClientSession initialized with MCP server
↓
Available tools fetched and cached
↓
Connection status monitored
```

### 2. Tool Execution
```
User triggers MCP-powered feature
↓
Frontend calls backend API endpoint
↓
Backend uses _mcp_session.call_tool()
↓
Tool execution on remote MCP server
↓
Results processed and returned
↓
Frontend displays results to user
```

### 3. Webhook Processing
```
External system sends webhook to /events/*
↓
Webhook endpoint processes payload
↓
Data formatted for MCP tool
↓
AI analysis performed via MCP
↓
Results logged or acted upon
↓
Response sent back to external system
```

## 🎨 UI State Management

### 1. Global State (React Context)
```
AuthContext: user, token, login/logout functions
ConnectionContext: database connections
Theme/UI state: modals, notifications, loading states
```

### 2. Component State
```
Local state for forms, tables, charts
React Hook Form for form validation
TanStack Query for server state caching
```

### 3. Navigation & Routing
```
React Router handles route changes
↓
PrivateRoute checks authentication
↓
Page components mount with data fetching
↓
Navigation highlights active route
↓
Breadcrumbs update based on location
```

## 🔐 Security & Authorization

### 1. Route Protection
```
PrivateRoute wrapper on all authenticated routes
↓
Checks user && token in AuthContext
↓
Redirects to /login if not authenticated
↓
Allows access if authenticated
```

### 2. API Authorization
```
Every protected API call includes JWT token
↓
Backend get_current_user() dependency
↓
Token validated and user extracted
↓
User permissions checked for admin endpoints
↓
Request processed or 401/403 returned
```

### 3. Admin-Only Features
```
Admin users see additional navigation items
↓
Admin-only routes protected with role checks
↓
Backend endpoints validate is_admin flag
↓
UI conditionally renders admin features
```

## 📱 Error Handling & UX

### 1. API Error Handling
```
API call fails (network, server, auth error)
↓
fetchApi() catches and categorizes error
↓
Appropriate error message displayed
↓
User redirected to login if auth fails
↓
Retry mechanisms for transient failures
```

### 2. Form Validation
```
React Hook Form validates on blur/submit
↓
Real-time validation feedback
↓
Server validation errors displayed
↓
Success states with visual feedback
```

### 3. Loading States
```
API calls trigger loading indicators
↓
Skeleton screens for data loading
↓
Disabled buttons during form submission
↓
Progress indicators for long operations
```

## 🚀 Performance Optimizations

### 1. Frontend Optimizations
```
Code splitting by route
Lazy loading of components
Image optimization and lazy loading
React.memo for expensive components
useMemo/useCallback for computed values
```

### 2. Backend Optimizations
```
Database connection pooling
Query optimization with indexes
Async request processing
Caching frequently accessed data
Background job processing
```

### 3. Analytics Performance
```
Asynchronous logging (non-blocking)
Batch processing of analytics data
Database indexes on query columns
Configurable data retention policies
```

## 🔄 Data Synchronization

### 1. Real-time Updates
```
Dashboard auto-refreshes every 30 seconds
Connection status checked periodically
Form data validated in real-time
Optimistic updates with rollback on error
```

### 2. Cache Management
```
TanStack Query handles API response caching
localStorage for auth token persistence
Context state for frequently accessed data
Automatic cache invalidation on mutations
```

This comprehensive flow documentation shows how every user action cascades through the system, from frontend interactions to backend processing to database updates, providing a complete picture of the application's behavior and data flow.
