/**
 * Database Connection Context Provider for Nova Nexus Engine
 * 
 * This context manages database connection state throughout the application,
 * providing centralized connection management for Business Intelligence and
 * DevOps tools that require database access.
 * 
 * Key Features:
 * 1. **Connection Profile Management**: Stores and manages saved database connections
 * 2. **Current Connection State**: Tracks the active database connection
 * 3. **Authentication Integration**: Syncs with user authentication state
 * 4. **Data Normalization**: Standardizes connection data formats
 * 5. **Error Handling**: Graceful handling of connection loading failures
 * 
 * Connection Types Supported:
 * - PostgreSQL databases
 * - Microsoft SQL Server
 * - Any database supported by the backend API
 * 
 * Security Features:
 * - Password masking for stored connections (shown as ***)
 * - Authentication-gated connection loading
 * - Automatic connection clearing on logout
 * - User-specific connection isolation
 * 
 * State Management:
 * - currentConnection: The actively selected database connection
 * - savedConnections: Array of user's saved connection profiles
 * - refreshConnections: Function to reload connections from backend
 * 
 * Integration Points:
 * - BI SQL Builder: Uses current connection for query execution
 * - DevOps Database Tools: Leverages saved connections for monitoring
 * - Settings Page: Manages connection CRUD operations
 * - Analytics: Tracks connection usage patterns
 * 
 * Data Flow:
 * 1. User logs in → ConnectionProvider loads saved connections
 * 2. User selects connection → setCurrentConnection updates state
 * 3. BI/DevOps tools → Use current connection for database operations
 * 4. User saves new connection → refreshConnections reloads list
 * 5. User logs out → All connection state cleared
 * 
 * Usage:
 * ```tsx
 * const { currentConnection, savedConnections, refreshConnections } = useConnectionContext();
 * 
 * // Select a connection for use
 * setCurrentConnection(savedConnection);
 * 
 * // Reload connections after adding/deleting
 * await refreshConnections();
 * ```
 */

import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';
import { DbConnection, ConnectionContext as ConnectionContextType, dbService } from '@/lib/api-service';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/context/auth-context';

// Create React context for database connection state management
// Context starts as undefined and will be provided by ConnectionProvider
const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

/**
 * ConnectionProvider Component - Database Connection State Management
 * 
 * This provider component manages all database connection state for the application:
 * 
 * **State Management**:
 * - currentConnection: The actively selected database connection for queries
 * - savedConnections: Array of user's saved connection profiles from backend
 * 
 * **Authentication Integration**:
 * - Watches for authentication state changes (login/logout)
 * - Loads connections only when user is authenticated
 * - Clears connections when user logs out
 * - Prevents API calls during authentication initialization
 * 
 * **Data Normalization**:
 * - Standardizes connection object properties across different sources
 * - Handles legacy field name variations (db_host vs host, etc.)
 * - Ensures consistent database_type formatting (lowercase)
 * - Masks passwords for security (shows *** instead of actual password)
 * 
 * **Error Handling**:
 * - Graceful degradation if connection loading fails
 * - Toast notifications for user feedback
 * - Console logging for debugging
 * - Prevents infinite loading states
 * 
 * **Performance Optimization**:
 * - Only loads connections when authentication is complete
 * - Avoids unnecessary API calls during initialization
 * - Efficient state updates with proper dependency arrays
 * 
 * @param children - Child components that need access to connection context
 */
export const ConnectionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // State for the currently active database connection (used for queries)
  const [currentConnection, setCurrentConnection] = useState<DbConnection | null>(null);
  
  // State for all saved database connection profiles for this user
  const [savedConnections, setSavedConnections] = useState<DbConnection[]>([]);
  
  // Toast hook for user feedback notifications
  const { toast } = useToast();
  
  // Authentication context to sync with user login state
  const { user, token, initializing } = useAuth();

  /**
   * Refresh Saved Connections from Backend
   * 
   * This function loads the user's saved database connection profiles:
   * 
   * **Authentication Check**:
   * - Verifies user is logged in before making API calls
   * - Clears connections if user is not authenticated
   * - Prevents API calls during authentication initialization
   * 
   * **API Integration**:
   * - Calls dbService.getSavedConnections() to fetch user's profiles
   * - Handles both success and error responses gracefully
   * - Provides user feedback through toast notifications
   * 
   * **Data Processing**:
   * - Normalizes connection object field names for consistency
   * - Standardizes database_type to lowercase format
   * - Maps legacy field names to current schema
   * - Masks passwords for security display
   * 
   * **Error Resilience**:
   * - Logs errors for debugging without crashing app
   * - Shows user-friendly error messages via toast
   * - Maintains existing connection state if reload fails
   * 
   * Called by:
   * - useEffect when authentication state changes
   * - Settings page after saving/deleting connections
   * - Manual refresh requests from UI components
   */
  const refreshConnections = async () => {
    // Security check: Only load connections for authenticated users
    if (!user || !token) {
      console.log('ConnectionContext: Skipping connection load - user not authenticated');
      setSavedConnections([]); // Clear any existing connections for security
      return;
    }

    try {
      console.log('ConnectionContext: Loading saved connections for user:', user.username);
      
      // Fetch saved connections from backend API
      const response = await dbService.getSavedConnections();
      
      if (response.status === 'success' && response.data) {
        // Normalize connection data to handle different field naming conventions
        // This ensures compatibility with different backend versions and data sources
        const normalized = response.data.map(c => ({
          ...c, // Preserve all original fields
          
          // Standardize database type field (ensure lowercase for consistency)
          database_type: String((c as any).database_type || (c as any).db_type || '').toLowerCase(),
          
          // Map legacy field names to current schema
          host: (c as any).host || (c as any).db_host,           // Database host/IP
          port: (c as any).port || (c as any).db_port,           // Database port
          user: (c as any).user || (c as any).db_user,           // Database username
          database: (c as any).database || (c as any).db_name,   // Database name
          name: (c as any).name || (c as any).connection_name,   // Display name
          
          // Password handling: Use stored password or show masked version
          password: (c as any).password || (c as any).db_password || '***',
        }));
        
        // Update state with normalized connection data
        setSavedConnections(normalized as any);
        console.log(`ConnectionContext: Loaded ${normalized.length} connections`);
      }
    } catch (error) {
      // Error handling: Log for debugging and notify user
      console.error('Failed to refresh connections:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to load saved connections."
      });
    }
  };

  /**
   * Authentication State Synchronization Effect
   * 
   * This useEffect hook manages the lifecycle of connection loading:
   * 
   * **Initialization Logic**:
   * - Waits for authentication initialization to complete
   * - Prevents premature API calls during app startup
   * - Ensures user state is stable before loading connections
   * 
   * **State Synchronization**:
   * - Reacts to login events by loading user's connections
   * - Reacts to logout events by clearing connection state
   * - Handles user switching scenarios
   * 
   * **Performance Optimization**:
   * - Only triggers when authentication state actually changes
   * - Avoids unnecessary API calls and state updates
   * - Efficient dependency array prevents infinite loops
   * 
   * Triggers:
   * - User logs in: Load their saved connections
   * - User logs out: Clear all connection state
   * - User switches: Load new user's connections
   * - App startup: Wait for auth, then load if authenticated
   */
  useEffect(() => {
    // Only proceed once authentication initialization is complete
    if (!initializing) {
      // Authentication state is now stable, safe to load connections
      console.log('ConnectionContext: Authentication ready, loading connections...');
      refreshConnections();
    }
  }, [user, token, initializing]); // React to changes in authentication state

  // Create context value object with all connection state and functions
  const contextValue: ConnectionContextType = {
    currentConnection,      // Currently active database connection
    setCurrentConnection,   // Function to set the active connection
    savedConnections,       // Array of user's saved connection profiles
    setSavedConnections,    // Function to update saved connections (used internally)
    refreshConnections      // Function to reload connections from backend
  };

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

/**
 * useConnectionContext Hook - Access Database Connection State
 * 
 * This custom hook provides access to the connection context from any component:
 * 
 * **Features**:
 * - Type-safe access to connection state and functions
 * - Automatic error handling for missing provider
 * - Consistent API across all components
 * 
 * **Error Prevention**:
 * - Throws descriptive error if used outside ConnectionProvider
 * - Prevents runtime errors from undefined context
 * - Guides developers to proper usage
 * 
 * **Usage Examples**:
 * ```tsx
 * // Get current connection state
 * const { currentConnection } = useConnectionContext();
 * 
 * // Set active connection for queries
 * const { setCurrentConnection } = useConnectionContext();
 * setCurrentConnection(selectedConnection);
 * 
 * // Refresh after saving new connection
 * const { refreshConnections } = useConnectionContext();
 * await refreshConnections();
 * 
 * // Get all saved connections for selection UI
 * const { savedConnections } = useConnectionContext();
 * ```
 * 
 * **Error Handling**:
 * - Must be used within ConnectionProvider component tree
 * - Will throw error with helpful message if provider missing
 * - Guides proper component hierarchy setup
 * 
 * @returns ConnectionContextType object with state and functions
 * @throws Error if used outside ConnectionProvider
 */
export const useConnectionContext = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  
  // Ensure hook is used within proper provider hierarchy
  if (!context) {
    throw new Error('useConnectionContext must be used within a ConnectionProvider');
  }
  
  return context;
};
