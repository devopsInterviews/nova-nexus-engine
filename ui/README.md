# Frontend Application Documentation

## Overview

The frontend is a modern React TypeScript application built with Vite, featuring a cyberpunk-themed UI for managing MCP (Model Context Protocol) servers, database connections, analytics, and user management.

## Technology Stack

### Core Technologies
- **React 18** - Component-based UI library
- **TypeScript** - Type-safe JavaScript development
- **Vite** - Fast build tool and development server
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Animation library for smooth transitions
- **React Router** - Client-side routing

### UI Component Library
- **shadcn/ui** - Headless, accessible component library
- **Radix UI** - Primitive components for complex UI
- **Lucide React** - Icon library
- **React Hook Form** - Form handling and validation

### State Management & Data Fetching
- **React Context** - Global state management
- **TanStack Query** - Server state and caching
- **Custom Hooks** - Reusable stateful logic

## Application Architecture

### Directory Structure

```
ui/src/
├── components/          # Reusable UI components
│   ├── admin/          # Admin-specific components
│   ├── analytics/      # Analytics and tracking
│   ├── auth/           # Authentication components
│   ├── bi/             # Business Intelligence
│   ├── devops/         # DevOps-related components
│   ├── layout/         # Layout and navigation
│   ├── tests/          # Test-related components
│   └── ui/             # Base UI components (shadcn)
├── context/            # React Context providers
├── hooks/              # Custom React hooks
├── lib/                # Utilities and services
├── pages/              # Route components
└── App.tsx             # Root application component
```

### Key Components

#### 1. Authentication System

**Location:** `src/components/auth/` and `src/context/auth-context.tsx`

**Components:**
- `LoginScreen.tsx` - Animated login interface with robot character
- `AuthProvider` - Context provider for authentication state

**Authentication Flow:**
1. User enters credentials in LoginScreen
2. AuthProvider handles login API call
3. JWT token stored in localStorage
4. User data cached in context
5. PrivateRoute components protect authenticated areas
6. Token automatically verified on app startup

**Key Features:**
- Automatic token expiration checking
- Client-side JWT validation to reduce server calls
- Graceful error handling and user feedback
- Token refresh and session restoration

#### 2. Global State Management

**AuthContext (`src/context/auth-context.tsx`):**
- Manages user authentication state
- Handles login/logout operations
- Provides user data throughout app
- Token validation and refresh

**ConnectionContext (`src/context/connection-context.tsx`):**
- Manages database connection profiles
- Provides saved connections to components
- Handles connection CRUD operations
- Syncs with backend API

#### 3. API Service Layer

**Location:** `src/lib/api-service.ts`

**Purpose:** Centralized API communication with backend

**Key Features:**
- Automatic JWT token inclusion
- Response error handling
- Type-safe API calls
- Smart data unwrapping
- Connection timeout handling

**Database Service:**
- Connection testing and management
- Query execution
- Table schema inspection
- User connection CRUD operations

#### 4. Routing & Navigation

**App Router (`src/App.tsx`):**
```tsx
Routes:
├── /login              # Authentication
├── /                   # Main app (requires auth)
│   ├── /               # Home dashboard
│   ├── /devops/*       # DevOps tools and monitoring
│   ├── /bi/*           # Business Intelligence
│   ├── /analytics      # System analytics
│   ├── /tests          # Test management
│   ├── /settings       # User settings
│   └── /users          # User management (admin)
└── /*                  # 404 Not Found
```

**Protected Routes:**
- All routes except `/login` require authentication
- `PrivateRoute` component handles protection
- Automatic redirect to login if not authenticated
- Session restoration on page refresh

#### 5. Layout System

**AppLayout (`src/components/layout/AppLayout.tsx`):**
- Main application shell
- Navigation sidebar with route highlights
- User profile and logout functionality
- Responsive design for mobile/desktop

**Navigation Features:**
- Active route highlighting
- Cyberpunk-themed styling
- User avatar and quick actions
- Role-based menu items (admin features)

## Page Components

### 1. Home Dashboard (`src/pages/Home.tsx`)
- System overview statistics
- Real-time metrics display
- Recent activity feed
- Quick access to main features

### 2. DevOps Page (`src/pages/DevOps.tsx`)
- MCP server management
- Jenkins integration
- Infrastructure monitoring
- Deployment tools

### 3. BI (Business Intelligence) (`src/pages/BI.tsx`)
- Data visualization
- Report generation
- Database query interface
- Analytics dashboards

### 4. Analytics (`src/pages/Analytics.tsx`)
- System performance metrics
- User activity analytics
- Error tracking and analysis
- Real-time monitoring

### 5. Tests (`src/pages/Tests.tsx`)
- Test configuration management
- Test execution interface
- Results tracking
- Saved test profiles

### 6. Users (`src/pages/Users.tsx`) - Admin Only
- User account management
- Permission configuration
- Activity monitoring
- Role assignment

### 7. Settings (`src/pages/Settings.tsx`)
- User profile management
- Application preferences
- Theme customization
- Connection settings

## Key Features

### 1. Database Connection Management

**Purpose:** Manage user's database connection profiles

**How it works:**
1. Users create connection profiles with credentials
2. Connections stored securely on backend
3. Frontend provides testing and management interface
4. Live connection status monitoring
5. Quick connection switching

**Components:**
- Connection forms with validation
- Connection testing interface
- Saved connections list
- Connection status indicators

### 2. Analytics & Monitoring

**Page View Tracking (`src/components/analytics/PageViewTracker.tsx`):**
- Automatically tracks page visits
- Sends data to backend analytics API
- Performance timing measurement
- User journey analysis

**Real-time Metrics:**
- System performance monitoring
- Error rate tracking
- User activity analytics
- Response time measurement

### 3. Test Management

**Test Configuration:**
- Save and manage test setups
- Execute tests against MCP servers
- Track test results and history
- Share test configurations

**Test Types:**
- MCP server connectivity tests
- Database connection tests
- API endpoint tests
- Performance benchmarks

### 4. User Interface Features

**Cyberpunk Theme:**
- Dark color scheme with neon accents
- Glowing borders and effects
- Animated transitions
- Futuristic typography

**Responsive Design:**
- Mobile-first approach
- Tablet and desktop optimizations
- Touch-friendly interactions
- Adaptive layouts

**Accessibility:**
- Keyboard navigation support
- Screen reader compatibility
- High contrast options
- Focus management

## Data Flow

### 1. Authentication Flow
```
User Login → AuthContext → API Call → JWT Token → localStorage → Global State
```

### 2. API Request Flow
```
Component → API Service → Auth Header → Backend → Response → State Update
```

### 3. Navigation Flow
```
Route Change → Page View Tracker → Analytics API → Component Mount → Data Fetch
```

### 4. Database Connection Flow
```
Connection Form → Validation → API Call → Backend Test → Status Update → UI Feedback
```

## State Management Patterns

### 1. Server State (TanStack Query)
- API data caching
- Background refetching
- Optimistic updates
- Error handling

### 2. Client State (React Context)
- Authentication state
- User preferences
- UI state (modals, forms)
- Navigation state

### 3. Form State (React Hook Form)
- Form validation
- Field state management
- Submission handling
- Error display

## Performance Optimizations

### 1. Code Splitting
- Route-based code splitting
- Lazy loading of components
- Bundle size optimization

### 2. Caching Strategy
- API response caching
- Image and asset caching
- Service worker implementation
- Local storage optimization

### 3. Rendering Optimizations
- React.memo for expensive components
- useMemo for computed values
- useCallback for event handlers
- Virtual scrolling for large lists

## Development Workflow

### 1. Adding New Pages
1. Create page component in `src/pages/`
2. Add route to `App.tsx`
3. Update navigation in `AppLayout`
4. Add any required API calls
5. Update TypeScript types

### 2. Adding New API Endpoints
1. Add function to `api-service.ts`
2. Define TypeScript interfaces
3. Add error handling
4. Update components to use new endpoint

### 3. Styling Guidelines
- Use Tailwind CSS utility classes
- Follow cyberpunk color scheme
- Maintain consistent spacing
- Use CSS variables for theme colors

## Security Considerations

### 1. Token Management
- JWT tokens stored in localStorage
- Automatic token expiration handling
- Secure token transmission
- Token validation before API calls

### 2. Input Validation
- Form validation with React Hook Form
- Type checking with TypeScript
- Sanitization of user inputs
- XSS prevention measures

### 3. Route Protection
- Private route wrapper components
- Authentication state checking
- Automatic redirects
- Session timeout handling

## Build & Deployment

### 1. Development
```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run preview      # Preview production build
npm run lint         # Run ESLint
```

### 2. Production Build
- TypeScript compilation
- Asset optimization
- Bundle minification
- Source map generation

### 3. Environment Configuration
- Environment-specific API URLs
- Feature flags
- Debug mode toggles
- Analytics configuration
