/**
 * Main Application Component for MCP Client Frontend
 * 
 * This is the root component that orchestrates the entire React application.
 * It sets up the foundational architecture including:
 * 
 * 1. **Provider Hierarchy**: Establishes the context provider chain for:
 *    - QueryClient: React Query for server state management
 *    - AuthProvider: Authentication state and JWT token management
 *    - ConnectionProvider: Database connection state management
 *    - TooltipProvider: UI component tooltip functionality
 * 
 * 2. **Routing Architecture**: Single Page Application (SPA) routing with:
 *    - BrowserRouter: HTML5 history API based routing
 *    - Protected routes: Authentication-required pages
 *    - Public routes: Login page accessible without authentication
 *    - Nested routes: Sub-routing within main application areas
 * 
 * 3. **Global Components**: Application-wide functionality:
 *    - PageViewTracker: Analytics tracking for page navigation
 *    - Toast notifications: User feedback system
 *    - Loading states: Authentication initialization handling
 * 
 * 4. **Authentication Flow**: Centralized auth logic with:
 *    - PrivateRoute wrapper: Protects authenticated pages
 *    - LoginWrapper: Handles authentication process
 *    - Session restoration: Automatic login on app startup
 * 
 * Application Structure:
 * - /login: Public authentication page
 * - /: Protected application (requires authentication)
 *   - / (index): Home dashboard
 *   - /devops/*: DevOps tools and monitoring
 *   - /bi/*: Business Intelligence and SQL tools  
 *   - /analytics: System analytics and metrics
 *   - /tests: Test execution and management
 *   - /research: User's own IDA MCP server management
 *   - /admin: Administrative panel (is_admin only) - Research, Users, System tabs
 *   - /settings: User preferences and configuration
 *   - /users: User management features
 * - /*: 404 Not Found page for unmatched routes
 */

import React from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { PageViewTracker } from "./components/analytics/PageViewTracker";
import Home from "./pages/Home";
import DevOps from "./pages/DevOps";
import BI from "./pages/BI";
import Analytics from "./pages/Analytics";
import Tests from "./pages/Tests";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import { LoginScreen } from "./components/auth/LoginScreen";
import Users from "./pages/Users";
import Research from "./pages/Research";
import Admin from "./pages/Admin";
import { ConnectionProvider } from "@/context/connection-context";
import { AuthProvider, useAuth } from "@/context/auth-context";

// Create React Query client for server state management
// This handles API caching, background refetching, and optimistic updates
const queryClient = new QueryClient();


/**
 * PrivateRoute Component - Route Protection Wrapper
 * 
 * This component implements route-level authentication protection:
 * 
 * **Authentication Check Flow**:
 * 1. Checks if user authentication is still initializing (token validation)
 * 2. Shows loading state during initialization to prevent flash
 * 3. Allows access if user and token exist (authenticated state)
 * 4. Redirects to login page if not authenticated
 * 
 * **Session Restoration**:
 * - On app startup, checks localStorage for existing JWT token
 * - Validates token expiration client-side for performance
 * - Verifies token with server if recently validated
 * - Maintains session across browser refreshes
 * 
 * **Loading State Management**:
 * - Displays "Restoring session..." during auth initialization
 * - Prevents premature redirects while checking stored tokens
 * - Provides smooth UX during authentication state determination
 * 
 * **Redirect Logic**:
 * - Uses React Router's Navigate with replace: true
 * - Prevents back button navigation to protected content
 * - Logs authentication state for debugging
 * 
 * @param children - Protected component to render if authenticated
 * @returns Loading state, protected content, or redirect to login
 */
const PrivateRoute = ({ children }: { children: React.ReactElement }) => {
  const { user, token, initializing } = useAuth(); // Get authentication state from context
  
  // Show loading state while determining authentication status
  // This prevents the flash of login page during token validation
  if (initializing) {
    return <div className="flex items-center justify-center h-screen text-sm text-muted-foreground">Restoring session...</div>;
  }
  
  // User is authenticated - render the protected content
  if (user && token) return children;
  
  // Debug logging for authentication troubleshooting
  console.debug('PrivateRoute redirecting to /login', { 
    hasUser: !!user, 
    hasToken: !!token, 
    initializing 
  });
  
  // Redirect to login page if not authenticated
  // replace: true prevents back button from returning to protected content
  return <Navigate to="/login" replace />;
};

/**
 * LoginWrapper Component - Authentication Interface
 * 
 * This component bridges the LoginScreen UI with the authentication context:
 * 
 * **Login Process Flow**:
 * 1. User enters credentials in LoginScreen form
 * 2. handleLogin calls auth context login function
 * 3. AuthContext sends credentials to backend /api/login
 * 4. Backend validates and returns JWT token
 * 5. Token and user data stored in localStorage and context
 * 6. User redirected to home page on success
 * 
 * **Error Handling**:
 * - Network errors: Connection failures, timeouts
 * - Authentication errors: Invalid credentials, account disabled
 * - Server errors: Backend service unavailable
 * - All errors displayed in LoginScreen UI
 * 
 * **Navigation Logic**:
 * - Successful login redirects to "/" (home page)
 * - Uses replace: true to prevent back button to login
 * - Integrates with React Router navigation
 * 
 * **State Management**:
 * - Leverages AuthContext for loading and error states
 * - Clears previous errors before new login attempt
 * - Provides visual feedback during authentication
 * 
 * @returns LoginScreen component with integrated authentication
 */
const LoginWrapper = () => {
  const { login, isLoading, error, clearError } = useAuth(); // Get auth functions from context
  const navigate = useNavigate(); // React Router navigation hook

  /**
   * Handle user login submission
   * 
   * @param username - User's login username
   * @param password - User's login password
   */
  const handleLogin = async (username: string, password: string) => {
    try {
      clearError(); // Clear any previous error messages for fresh attempt
      
      // Use authentication context for proper backend authentication
      // This handles JWT token storage and user session setup
      await login(username, password);
      
      // Navigate to home page after successful authentication
      // replace: true prevents back button navigation to login page
      navigate('/', { replace: true });
      
    } catch (err) {
      console.error('Login failed:', err);
      // Re-throw the error to be handled by the LoginScreen component
      // This allows the UI to display appropriate error messages
      throw err;
    }
  };

  return (
    <LoginScreen
      onLogin={handleLogin}    // Pass authentication handler
      loading={isLoading}      // Pass loading state for UI feedback
      error={error}           // Pass error messages for display
    />
  );
};

/**
 * Main App Component - Application Root
 * 
 * This is the top-level component that establishes the entire application architecture:
 * 
 * **Provider Hierarchy** (outer to inner):
 * 1. QueryClientProvider: React Query for server state management and caching
 * 2. AuthProvider: Authentication state, JWT tokens, and user session management
 * 3. ConnectionProvider: Database connection profiles and state management
 * 4. TooltipProvider: UI tooltip functionality for interactive elements
 * 
 * **Global Components**:
 * - Toaster: Toast notification system for user feedback
 * - Sonner: Alternative toast implementation for variety
 * - PageViewTracker: Analytics tracking for navigation and user behavior
 * 
 * **Routing Structure**:
 * - BrowserRouter: HTML5 history API based routing for SPA navigation
 * - Public routes: /login (accessible without authentication)
 * - Protected routes: All other routes (require authentication)
 * - Nested routing: Sub-routes within main application areas
 * - Catch-all: 404 page for unmatched routes (must be last)
 * 
 * **Route Organization**:
 * - /login: Authentication page (public)
 * - /: Main application layout (protected)
 *   - Index route: Home dashboard
 *   - /devops/*: DevOps tools with sub-routing
 *   - /bi/*: Business Intelligence tools with sub-routing
 *   - /analytics: System metrics and analytics
 *   - /tests: Test execution and management
 *   - /settings: User preferences and configuration
 *   - /users: User management and admin features
 * - /*: 404 Not Found page (catch-all, must be last)
 * 
 * **Authentication Integration**:
 * - PrivateRoute wrapper protects authenticated pages
 * - LoginWrapper handles authentication process
 * - Session restoration on app startup
 * - Automatic redirect on token expiration
 * 
 * @returns Complete React application with routing and providers
 */
const App = () => (
  // React Query Provider: Server state management and caching
  <QueryClientProvider client={queryClient}>
    {/* Authentication Provider: User session and JWT token management */}
    <AuthProvider>
      {/* Connection Provider: Database connection state management */}
      <ConnectionProvider>
        {/* Tooltip Provider: UI tooltip functionality */}
        <TooltipProvider>
          {/* Toast notification systems for user feedback */}
          <Toaster />
          <Sonner />
          
          {/* Browser Router: SPA routing with HTML5 history API */}
          <BrowserRouter>
            {/* Analytics: Track page views for user behavior analytics */}
            <PageViewTracker />
            
            {/* Application Routes */}
            <Routes>
              {/* Public Route: Login page (no authentication required) */}
              <Route path="/login" element={<LoginWrapper />} />
              
              {/* Protected Routes: Main application (authentication required) */}
              <Route 
                path="/" 
                element={
                  <PrivateRoute>
                    <AppLayout />
                  </PrivateRoute>
                }
              >
                {/* Nested Routes within AppLayout */}
                <Route index element={<Home />} />                    {/* Dashboard home page */}
                <Route path="devops/*" element={<DevOps />} />        {/* DevOps tools with sub-routing */}
                <Route path="bi/*" element={<BI />} />                {/* Business Intelligence with sub-routing */}
                <Route path="analytics" element={<Analytics />} />    {/* System analytics and metrics */}
                <Route path="tests" element={<Tests />} />            {/* Test execution and management */}
                <Route path="research" element={<Research />} />      {/* Research/IDA MCP connection */}
                <Route path="admin" element={<Admin />} />            {/* Admin dashboard (is_admin only) */}
                <Route path="settings" element={<Settings />} />      {/* User preferences and configuration */}
                <Route path="users" element={<Users />} />            {/* User management and admin features */}
              </Route>
              
              {/* Catch-all Route: 404 Not Found (MUST BE LAST) */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ConnectionProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
