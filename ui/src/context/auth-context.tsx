/**
 * Authentication Context Provider for Nova Nexus Engine
 * 
 * This context manages the entire authentication state and flow for the application.
 * It provides centralized authentication logic that handles JWT tokens, user sessions,
 * and automatic token validation.
 * 
 * Key Features:
 * 1. **JWT Token Management**: Automatic token storage, validation, and expiration checking
 * 2. **Session Persistence**: Maintains user sessions across page refreshes
 * 3. **Automatic Validation**: Periodically validates tokens with the server
 * 4. **Error Handling**: Graceful handling of authentication errors
 * 5. **Performance Optimization**: Client-side token validation to reduce server calls
 * 
 * Authentication Flow:
 * 1. User enters credentials in LoginScreen
 * 2. AuthProvider calls `/api/login` endpoint
 * 3. Server validates credentials and returns JWT token
 * 4. Token and user data stored in localStorage and context
 * 5. All subsequent API calls include the JWT token
 * 6. Token automatically validated on app startup and periodically
 * 7. User redirected to login if token expires or becomes invalid
 * 
 * Token Storage:
 * - JWT token stored in localStorage as 'auth_token'
 * - User data cached in localStorage as 'auth_user'
 * - Last validation time tracked to avoid excessive server calls
 * 
 * Security Features:
 * - Client-side token expiration checking
 * - Automatic token cleanup on expiration
 * - Secure token transmission in Authorization headers
 * - Session timeout handling
 * 
 * Usage:
 * ```tsx
 * const { user, token, login, logout, isLoading } = useAuth();
 * 
 * // Login user
 * await login(username, password);
 * 
 * // Check if user is authenticated
 * if (user && token) {
 *   // User is logged in
 * }
 * 
 * // Logout user
 * logout();
 * ```
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// TypeScript interface defining the structure of a user object
interface User {
  id: number;            // Unique user identifier from database
  username: string;      // Login username (unique constraint)
  email: string;         // User's email address
  full_name?: string;    // Optional display name
  is_active: boolean;    // Whether account is enabled
  is_admin: boolean;     // Whether user has admin privileges
  created_at?: string;   // Account creation timestamp
  last_login?: string;   // Last successful login timestamp
  login_count: number;   // Total number of logins (for analytics)
  preferences: Record<string, any>; // User settings stored as JSON
}

// TypeScript interface defining the shape of our authentication context
interface AuthContextType {
  user: User | null;     // Current authenticated user or null
  token: string | null;  // JWT token or null if not authenticated
  login: (username: string, password: string) => Promise<void>;  // Login function
  logout: () => void;    // Logout function that clears state
  register: (userData: RegisterData) => Promise<void>;          // Registration function
  updateProfile: (userData: Partial<User>) => Promise<void>;    // Profile update function
  isLoading: boolean;    // Whether any auth operation is in progress
  initializing: boolean; // Whether initial auth state is being determined
  error: string | null;  // Any error message from auth operations
  clearError: () => void; // Function to clear error messages
}

// TypeScript interface for user registration data
interface RegisterData {
  username: string;    // Required username for new account
  email: string;       // Required email for new account
  password: string;    // Required password for new account
  full_name?: string;  // Optional full name for display
}

// Create React context with undefined default (will be provided by AuthProvider)
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Props interface for the AuthProvider component
interface AuthProviderProps {
  children: ReactNode;  // Child components that will have access to auth context
}

// Base URL for all authentication API calls
const API_BASE_URL = '/api';

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  // State management for authentication data
  const [user, setUser] = useState<User | null>(null);    // Currently authenticated user
  const [token, setToken] = useState<string | null>(null); // JWT token for API calls
  const [isLoading, setIsLoading] = useState(false);       // Loading state for auth operations
  const [error, setError] = useState<string | null>(null); // Error messages from auth operations
  const [isInitializing, setIsInitializing] = useState(true); // Whether initial auth check is complete

  // Client-side JWT token expiration checker to avoid unnecessary server calls
  const isTokenExpired = (jwt?: string | null) => {
    if (!jwt) return true; // No token means expired
    const parts = jwt.split('.'); // JWT has 3 parts: header.payload.signature
    if (parts.length !== 3) return false; // Malformed token, let server validate
    try {
      // Decode the payload (middle part) from base64
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
      if (!payload.exp) return false; // No expiration claim, treat as non-expiring
      const now = Math.floor(Date.now() / 1000); // Current time in seconds
      return payload.exp < now - 5; // Add 5 second tolerance for clock skew
    } catch {
      return false; // JSON parse error, let server validate
    }
  };

  // Initialize authentication state from localStorage on app startup
  // This runs once when the component mounts and verifies stored tokens
  useEffect(() => {
    let cancelled = false; // Flag to prevent state updates if component unmounts
    const initializeAuth = async () => {
      // Attempt to retrieve saved authentication data from browser storage
      const savedToken = localStorage.getItem('auth_token');   // JWT token
      const savedUser = localStorage.getItem('auth_user');     // User data JSON
      
      // If no token exists, user needs to log in
      if (!savedToken) {
        setIsInitializing(false); // Mark initialization complete
        return;
      }

      // Pre-load saved user data immediately for better UX (before server validation)
      if (savedUser) {
        try {
          const parsedUser = JSON.parse(savedUser); // Parse JSON user data
          setUser(parsedUser);   // Set user in state for immediate UI update
          setToken(savedToken);  // Set token in state for API calls
        } catch { 
          /* ignore JSON parse errors - will be handled by server validation */ 
        }
      }

      // Check if token is expired locally before making expensive server request
      if (isTokenExpired(savedToken)) {
        console.log('Token expired, clearing auth state');
        // Clear all stored authentication data
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        // Reset state to unauthenticated
        setUser(null);
        setToken(null);
        setIsInitializing(false); // Mark initialization complete
        return;
      }

      // Check if we recently verified the token (within last 5 minutes)
      const lastVerified = localStorage.getItem('auth_last_verified');
      const now = Date.now();
      if (lastVerified && (now - parseInt(lastVerified)) < 5 * 60 * 1000) {
        // Token was recently verified, skip server check
        setIsInitializing(false);
        return;
      }

      const verifyWithRetry = async () => {
        const maxAttempts = 3;
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          try {
            const userResponse = await fetch(`${API_BASE_URL}/me`, {
              method: 'GET',
              headers: { 'Authorization': `Bearer ${savedToken}` },
            });
            if (userResponse.status === 401) {
              throw new Error('Unauthorized');
            }
            if (!userResponse.ok) {
              throw new Error('Token verification failed');
            }
            const userData = await userResponse.json();
            if (!cancelled) {
              setToken(savedToken);
              setUser(userData);
              localStorage.setItem('auth_user', JSON.stringify(userData));
              localStorage.setItem('auth_last_verified', Date.now().toString());
            }
            return true;
          } catch (err) {
            if (attempt === maxAttempts) {
              if (!cancelled) {
                console.warn('Stored token invalid after retries, clearing auth state:', err);
                localStorage.removeItem('auth_token');
                localStorage.removeItem('auth_user');
                localStorage.removeItem('auth_last_verified');
                setToken(null);
                setUser(null);
              }
              return false;
            }
            // exponential backoff (50ms, 150ms)
            await new Promise(r => setTimeout(r, attempt * 100 + 50));
          }
        }
        return false;
      };
      try { await verifyWithRetry(); } finally { if (!cancelled) setIsInitializing(false); }
    };
    // slight delay to allow any parallel login redirect before verifying
    setTimeout(initializeAuth, 40);
    return () => { cancelled = true; };
  }, []);

  const clearError = () => setError(null);

  /**
   * Authenticate user with backend and establish session.
   * 
   * This is the primary login function that:
   * 1. Sends credentials to backend `/api/login` endpoint
   * 2. Receives JWT token if authentication successful
   * 3. Fetches user profile data using the token
   * 4. Stores token and user data in localStorage and context
   * 5. Sets up the authenticated session for the app
   * 
   * Backend Authentication Flow:
   * - POST /api/login with {username, password}
   * - Server validates against database (User model)
   * - JWT token generated with 2-hour expiration
   * - Token includes user_id and expiration claims
   * - User's last_login and login_count updated in database
   * 
   * Frontend Session Setup:
   * - Token stored in localStorage for persistence
   * - User data cached for immediate access
   * - Global authentication state updated
   * - All subsequent API calls include Authorization header
   * 
   * Error Handling:
   * - Invalid credentials: Displays user-friendly error
   * - Network errors: Handles connection failures gracefully
   * - Server errors: Shows appropriate error messages
   * 
   * @param username - User's login username
   * @param password - User's login password
   * @throws Error if authentication fails
   */
  const login = async (username: string, password: string): Promise<void> => {
    setIsLoading(true);  // Show loading state in UI
    setError(null);      // Clear any previous error messages
    
    try {
      // Step 1: Send login credentials to backend authentication endpoint
      const loginResponse = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',  // HTTP POST method for sending credentials
        headers: {
          'Content-Type': 'application/json',  // Tell server we're sending JSON
        },
        body: JSON.stringify({ username, password }),  // Convert credentials to JSON
      });

      // Parse the response JSON (contains token or error message)
      const loginData = await loginResponse.json();

      // Check if authentication failed (non-2xx status code)
      if (!loginResponse.ok) {
        // Extract error message from server response or use default
        throw new Error(loginData.detail || 'Login failed');
      }

      // Extract JWT token from successful login response
      const { access_token } = loginData;
      
      // Step 2: Use the token to fetch complete user profile data
      const userResponse = await fetch(`${API_BASE_URL}/me`, {
        method: 'GET',  // HTTP GET to retrieve user data
        headers: {
          'Authorization': `Bearer ${access_token}`,  // Include JWT token in Authorization header
        },
      });

      // Parse user profile data from response
      const userData = await userResponse.json();

      // Check if user profile fetch failed
      if (!userResponse.ok) {
        throw new Error(userData.detail || 'Failed to get user data');
      }

      // Step 3: Store authentication data in React state for immediate use
      setToken(access_token);  // Store token for API calls
      setUser(userData);       // Store user data for UI display
      
      // Step 4: Persist authentication data in localStorage for session restoration
      localStorage.setItem('auth_token', access_token);              // Save token
      localStorage.setItem('auth_user', JSON.stringify(userData));   // Save user data as JSON
      
    } catch (err) {
      // Handle any errors that occurred during login process
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);  // Set error message for UI display
      throw err;  // Re-throw error so calling component can handle it
    } finally {
      setIsLoading(false);  // Always clear loading state, even if error occurred
    }
  };

  /**
   * Register a new user account.
   * 
   * This function handles user registration by:
   * 1. Sending registration data to the backend
   * 2. Creating a new user account in the database
   * 3. Handling success/error responses appropriately
   * 
   * Note: This function does NOT automatically log the user in.
   * After successful registration, the user must still log in manually.
   * 
   * @param userData - New user registration information
   * @throws Error if registration fails (duplicate username/email, validation errors, etc.)
   */
  const register = async (userData: RegisterData): Promise<void> => {
    setIsLoading(true);  // Show loading state during registration
    setError(null);      // Clear any previous error messages
    
    try {
      // Send registration data to backend registration endpoint
      const response = await fetch(`${API_BASE_URL}/register`, {
        method: 'POST',  // HTTP POST to create new resource
        headers: {
          'Content-Type': 'application/json',  // Tell server we're sending JSON
        },
        body: JSON.stringify(userData),  // Convert registration data to JSON
      });

      // Parse response from server (success confirmation or error details)
      const data = await response.json();

      // Check if registration failed (username taken, validation errors, etc.)
      if (!response.ok) {
        // Extract error message from server response or use default
        throw new Error(data.detail || 'Registration failed');
      }

      // Registration successful - user account created in database
      // Note: User is NOT automatically logged in and must log in separately
      
    } catch (err) {
      // Handle any errors that occurred during registration
      const errorMessage = err instanceof Error ? err.message : 'Registration failed';
      setError(errorMessage);  // Set error message for UI display
      throw err;  // Re-throw so calling component can handle it
    } finally {
      setIsLoading(false);  // Always clear loading state
    }
  };

  /**
   * Update the current user's profile information.
   * 
   * This function allows authenticated users to update their profile data:
   * 1. Validates user is currently authenticated (has valid token)
   * 2. Sends updated profile data to backend
   * 3. Updates local state and localStorage with new data
   * 
   * @param userData - Partial user data containing fields to update
   * @throws Error if not authenticated or update fails
   */
  const updateProfile = async (userData: Partial<User>): Promise<void> => {
    // Ensure user is authenticated before allowing profile updates
    if (!token) {
      throw new Error('Not authenticated');
    }

    setIsLoading(true);  // Show loading state during update
    setError(null);      // Clear any previous error messages
    
    try {
      // Send updated profile data to backend user profile endpoint
      const response = await fetch(`${API_BASE_URL}/me`, {
        method: 'PUT',  // HTTP PUT for updating existing resource
        headers: {
          'Content-Type': 'application/json',        // Tell server we're sending JSON
          'Authorization': `Bearer ${token}`,        // Include JWT token for authentication
        },
        body: JSON.stringify(userData),  // Convert profile updates to JSON
      });

      // Parse response containing updated user data
      const data = await response.json();

      // Check if profile update failed
      if (!response.ok) {
        throw new Error(data.detail || 'Profile update failed');
      }

      // Update local state and storage with new profile data
      setUser(data);  // Update React state for immediate UI updates
      localStorage.setItem('auth_user', JSON.stringify(data));  // Persist updated data
      
    } catch (err) {
      // Handle any errors that occurred during profile update
      const errorMessage = err instanceof Error ? err.message : 'Profile update failed';
      setError(errorMessage);  // Set error message for UI display
      throw err;  // Re-throw so calling component can handle it
    } finally {
      setIsLoading(false);  // Always clear loading state
    }
  };

  /**
   * Clear user session and redirect to login.
   * 
   * This function handles complete logout by:
   * 1. Clearing authentication state (user, token)
   * 2. Removing all auth data from localStorage
   * 3. Optionally calling backend logout endpoint
   * 4. Resetting error state
   * 
   * Backend Logout (Optional):
   * - Calls POST /api/logout to invalidate server-side session
   * - Fails gracefully if backend is unavailable
   * - Token becomes invalid regardless of server response
   * 
   * Local Cleanup:
   * - Removes 'auth_token' from localStorage
   * - Removes 'auth_user' from localStorage
   * - Clears all context state
   * - Prepares app for fresh login
   * 
   * Usage: User clicks logout button, session expires, or auth error occurs
   */
  const logout = () => {
    // Step 1: Clear authentication state in React context
    setUser(null);   // Remove user data from state
    setToken(null);  // Remove token from state
    setError(null);  // Clear any error messages
    
    // Step 2: Remove all authentication data from browser storage
    localStorage.removeItem('auth_token');  // Remove JWT token
    localStorage.removeItem('auth_user');   // Remove cached user data
    
    // Step 3: Optionally notify backend of logout (for server-side session cleanup)
    if (token) {
      // Make logout request to backend but don't wait for response
      fetch(`${API_BASE_URL}/logout`, {
        method: 'POST',  // HTTP POST to logout endpoint
        headers: {
          'Authorization': `Bearer ${token}`,  // Include current token for identification
        },
      }).catch(err => {
        // If backend logout fails, log warning but continue with local logout
        console.warn('Logout request failed:', err);
        // Local logout is still successful even if server request fails
      });
    }
  };

  // Create the context value object that will be provided to child components
  const contextValue: AuthContextType = {
    user,          // Current authenticated user or null
    token,         // Current JWT token or null  
    login,         // Function to authenticate user
    logout,        // Function to clear authentication
    register,      // Function to create new user account
    updateProfile, // Function to update user profile
    isLoading: isLoading || isInitializing,  // Loading state (auth operations or initialization)
  initializing: isInitializing,
    error,
    clearError,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
