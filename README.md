# MCP Client 🚀

A cutting-edge **Model Context Protocol (MCP) management platform** with a cyberpunk-inspired interface for managing AI servers, database connections, analytics, and user workflows.

## 🌟 Overview

 Full-stack web application that bridges the gap between AI/ML models and enterprise systems. It provides a unified interface for managing MCP servers, executing database queries, monitoring system performance, and automating workflows through intelligent integrations.

### Key Capabilities
- 🤖 **MCP Server Management**: Connect and manage AI/ML model servers
- 🗄️ **Database Integration**: Multi-database query execution and management
- 📊 **Real-time Analytics**: System performance and user activity monitoring
- 🔐 **Enterprise Authentication**: JWT-based security with role management
- 🎯 **Workflow Automation**: CI/CD integrations and webhook processing
- 🎨 **Modern UI**: Cyberpunk-themed responsive interface

## 🏗️ Architecture

### Backend (FastAPI + Python)
```
app/
├── client.py              # Main FastAPI application
├── models.py              # Database models (SQLAlchemy)
├── database.py            # Database configuration
├── auth.py                # Authentication utilities
├── middleware/            # Request processing middleware
│   └── analytics.py       # Request logging and metrics
├── routes/                # API endpoint definitions
│   ├── auth_routes.py     # Authentication endpoints
│   ├── analytics_routes.py # System metrics APIs
│   ├── users_routes.py    # User management
│   └── db_routes.py       # Database operations
└── services/              # Business logic services
    └── analytics_service.py # Analytics processing
```

### Frontend (React + TypeScript)
```
ui/src/
├── App.tsx                # Root application component
├── components/            # Reusable UI components
│   ├── auth/             # Authentication components
│   ├── layout/           # Layout and navigation
│   ├── analytics/        # Analytics tracking
│   └── ui/               # Base UI components
├── context/               # Global state management
│   ├── auth-context.tsx  # Authentication state
│   └── connection-context.tsx # Database connections
├── pages/                 # Route components
│   ├── Home.tsx          # Dashboard
│   ├── Analytics.tsx     # System metrics
│   ├── Users.tsx         # User management
│   └── DevOps.tsx        # DevOps tools
└── lib/                   # Utilities and services
    └── api-service.ts     # API communication layer
```

## 🚀 Getting Started

### Quick Start with Docker (Recommended) 🐳

For the fastest development setup, use Docker Compose:

```bash
# Clone and setup
git clone <repository-url>
cd mcp-client
cp .env.example .env

# Start development environment
docker-compose up --build
```

**Access the application:**
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs

📖 **See [DOCKER.md](./DOCKER.md) for comprehensive Docker setup instructions, including:**
- Multiple deployment profiles (basic, full, nginx, mcp)
- Helper scripts for easy management
- Troubleshooting and development tips
- Production deployment guidance

### Manual Setup (Traditional)

#### Prerequisites
- **Python 3.8+** with FastAPI and SQLAlchemy
- **Node.js 16+** with npm/yarn
- **PostgreSQL** database
- **MCP Server** (optional for full functionality)

#### Backend Setup

1. **Install Dependencies**
```bash
cd app/
pip install -r requirements.txt
```

2. **Environment Configuration**
```bash
# Create .env file
cp .env.example .env

# Configure variables
MCP_SERVER_URL=http://localhost:8050/mcp/
DATABASE_URL=postgresql://user:password@localhost/mcp_client
JWT_SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=120
```

3. **Database Initialization**
```bash
# The app will automatically create tables on startup
python -m uvicorn client:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

1. **Install Dependencies**
```bash
cd ui/
npm install
```

2. **Environment Configuration**
```bash
# Create .env file
VITE_API_BASE_URL=http://localhost:8000
```

3. **Start Development Server**
```bash
npm run dev
```

#### Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔐 Authentication Flow

### User Login Process
1. **User Input**: User enters credentials in the cyberpunk-themed login screen
2. **Frontend Validation**: React Hook Form validates input format
3. **API Request**: AuthContext sends POST request to `/api/login`
4. **Backend Verification**: Server validates credentials against User model
5. **JWT Generation**: Server creates JWT token with 2-hour expiration
6. **Token Storage**: Frontend stores token in localStorage
7. **Session Setup**: User data cached in React Context
8. **Protected Access**: Token included in all subsequent API requests

### JWT Token Details
- **Expiration**: 2 hours (configurable)
- **Claims**: user_id, username, expiration
- **Storage**: localStorage (frontend) + HTTP-only cookie option
- **Validation**: Client-side expiration check + server verification

### Session Management
- **Auto-refresh**: Token validated every 5 minutes
- **Graceful expiry**: Automatic logout when token expires
- **Session restoration**: App remembers user on page refresh
- **Security**: Automatic cleanup of invalid tokens

## 📊 Analytics & Monitoring

### Request Tracking
Every HTTP request is automatically logged with:
- **Performance Metrics**: Response time, request/response sizes
- **User Context**: Authenticated user ID, IP address
- **Error Tracking**: Status codes, error messages
- **Activity Classification**: API categorization (auth, database, MCP, etc.)

### Real-time Metrics
The analytics system provides:
- **System Uptime**: Availability percentage based on successful requests
- **Response Times**: 95th percentile performance metrics
- **Active Users**: Real-time user session tracking
- **Error Rates**: HTTP error categorization and trends
- **Page Views**: Frontend navigation and user journey tracking

### Database Schema
Key analytics tables:
- **request_logs**: HTTP request performance data
- **user_activities**: User action audit trail
- **page_views**: Frontend page visit tracking
- **system_metrics**: Real-time performance indicators

## 🗄️ Database Management

### Connection Profiles
Users can create and manage database connections:
- **Multi-Database Support**: PostgreSQL, MySQL, SQL Server
- **Secure Storage**: Encrypted password storage
- **Connection Testing**: Live connection validation
- **User Isolation**: Private connection profiles per user

### Query Execution
- **SQL Editor**: Syntax highlighting and validation
- **Result Display**: Tabular data presentation
- **Export Options**: CSV, JSON data export
- **Query History**: Saved queries and execution logs

### Schema Exploration
- **Table Listing**: Database schema browsing
- **Column Details**: Data types and constraints
- **Relationship Mapping**: Foreign key relationships
- **Index Information**: Performance optimization insights

## 🤖 MCP Integration

### Model Context Protocol
The application connects to MCP servers for:
- **AI Model Access**: Language models and specialized AI tools
- **Tool Execution**: Jenkins, Confluence, database tools
- **Workflow Automation**: CI/CD pipeline integration
- **Data Processing**: Intelligent data analysis and insights

### Supported Tools
- **Jenkins Integration**: Build monitoring and analysis
- **Confluence Management**: Documentation automation
- **Database Operations**: Schema analysis and data insights
- **Code Analysis**: Automated code review and recommendations

### Webhook Endpoints
- **`/events/code-analysis`**: CI/CD code analysis results
- **`/events/jira`**: JIRA ticket investigation automation
- **`/events/jenkins`**: Jenkins build failure analysis

## 👥 User Management

### User Roles
- **Admin Users**: Full system access, user management
- **Regular Users**: Standard feature access, own data only
- **Role-based Permissions**: Tab-specific access control

### User Features
- **Profile Management**: Personal information and preferences
- **Password Security**: Bcrypt hashing with salt
- **Activity Tracking**: Login history and action audit
- **Session Management**: Active session monitoring

### Admin Capabilities
- **User CRUD**: Create, update, delete user accounts
- **Permission Assignment**: Role and access management
- **Activity Monitoring**: User behavior analytics
- **System Health**: Overall platform monitoring

## 🎨 User Interface

### Cyberpunk Theme
- **Color Scheme**: Dark backgrounds with neon accents
- **Typography**: Futuristic fonts and spacing
- **Animations**: Smooth transitions with Framer Motion
- **Visual Effects**: Glowing borders and gradient effects

### Responsive Design
- **Mobile-First**: Touch-friendly interface
- **Tablet Optimization**: Adaptive layouts
- **Desktop Experience**: Full-featured interface
- **Accessibility**: Screen reader and keyboard support

### Navigation
- **Sidebar Menu**: Collapsible navigation with active states
- **Breadcrumbs**: Clear navigation hierarchy
- **Quick Actions**: Contextual action buttons
- **Search**: Global search functionality

## 🔧 Development Guide

### Adding New Features

#### Backend API Endpoints
1. **Create Route Module**: Add new file in `app/routes/`
2. **Define Pydantic Models**: Request/response schemas
3. **Implement Business Logic**: Database operations and processing
4. **Add Authentication**: Protect endpoints with `get_current_user`
5. **Include Router**: Add to main app in `client.py`

#### Frontend Components
1. **Create Component**: Add to appropriate `components/` subdirectory
2. **Define TypeScript Types**: Interfaces for props and data
3. **Implement Logic**: State management and API integration
4. **Add Styling**: Tailwind CSS with cyberpunk theme
5. **Update Navigation**: Add routes and menu items

#### Database Models
1. **Define Model Class**: Add to `app/models.py`
2. **Add Relationships**: Foreign keys and associations
3. **Create Migration**: Update database schema
4. **Add API Endpoints**: CRUD operations
5. **Update Frontend**: UI for new data

### Testing Strategy
- **Backend Tests**: pytest with test database
- **Frontend Tests**: Jest + React Testing Library
- **Integration Tests**: Full workflow testing
- **E2E Tests**: Cypress for user journey testing

### Performance Optimization
- **Database Indexing**: Optimize query performance
- **API Caching**: Redis for frequently accessed data
- **Frontend Optimization**: Code splitting and lazy loading
- **CDN Integration**: Static asset delivery

## 🚀 Deployment

### Production Environment
- **Backend**: Docker containerization with Gunicorn
- **Frontend**: Static build served by nginx
- **Database**: PostgreSQL with connection pooling
- **Monitoring**: Prometheus + Grafana for metrics

### CI/CD Pipeline
- **Code Analysis**: Automatic security and quality scans
- **Testing**: Automated test execution
- **Building**: Docker image creation
- **Deployment**: Rolling updates with health checks

### Security Considerations
- **HTTPS**: TLS encryption for all communications
- **Input Validation**: Comprehensive data sanitization
- **SQL Injection**: Parameterized queries with SQLAlchemy
- **XSS Prevention**: Output encoding and CSP headers

## 📈 Analytics Dashboard

### System Overview
- **Uptime Metrics**: System availability tracking
- **Performance Trends**: Response time analysis
- **User Activity**: Login patterns and feature usage
- **Error Monitoring**: Error rates and categorization

### Business Intelligence
- **Usage Analytics**: Feature adoption and user engagement
- **Performance Insights**: Bottleneck identification
- **Capacity Planning**: Resource utilization trends
- **ROI Tracking**: System value and efficiency metrics

## 🤝 Contributing

### Development Workflow
1. **Fork Repository**: Create personal copy
2. **Feature Branch**: Create branch for new feature
3. **Development**: Implement changes with tests
4. **Pull Request**: Submit for code review
5. **Merge**: Deploy after approval

### Code Standards
- **Python**: Black formatting, flake8 linting
- **TypeScript**: ESLint + Prettier formatting
- **Documentation**: Comprehensive inline comments
- **Testing**: Minimum 80% code coverage

### Issue Reporting
- **Bug Reports**: Include reproduction steps
- **Feature Requests**: Describe use case and value
- **Security Issues**: Private disclosure process
- **Performance**: Include profiling data

## 📞 Support

### Documentation
- **API Reference**: OpenAPI documentation at `/docs`
- **User Guide**: Frontend help and tutorials
- **Developer Docs**: Architecture and integration guides
- **Troubleshooting**: Common issues and solutions

### Community
- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Community questions and ideas
- **Wiki**: User-contributed documentation
- **Changelog**: Release notes and updates

---

**MCP Client** - Bridging AI and Enterprise Systems with Style 🚀✨
