import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at?: string;
  last_login?: string;
  login_count: number;
  preferences: Record<string, any>;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: RegisterData) => Promise<void>;
  updateProfile: (userData: Partial<User>) => Promise<void>;
  isLoading: boolean;
  error: string | null;
  clearError: () => void;
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

const API_BASE_URL = '/api';

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  // Lightweight JWT decode (no external lib) to check expiry
  const isTokenExpired = (jwt?: string | null) => {
    if (!jwt) return true;
    const parts = jwt.split('.');
    if (parts.length !== 3) return false; // if structure unexpected, attempt server verify instead of hard logout
    try {
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
      if (!payload.exp) return false; // no exp claim, treat as non‑expiring
      const now = Math.floor(Date.now() / 1000);
      return payload.exp < now - 5; // small clock skew tolerance
    } catch {
      return false;
    }
  };

  // Initialize auth state from localStorage and verify token with debounce to avoid race on rapid refresh
  useEffect(() => {
    let cancelled = false;
    const initializeAuth = async () => {
      const savedToken = localStorage.getItem('auth_token');
      const savedUser = localStorage.getItem('auth_user');
      if (!savedToken) {
        setIsInitializing(false);
        return;
      }

      // Pre-load saved user immediately for UX
      if (savedUser) {
        try {
          const parsedUser = JSON.parse(savedUser);
          setUser(parsedUser);
          setToken(savedToken);
        } catch { /* ignore parse error */ }
      }

      // Skip server verify if clearly expired
      if (isTokenExpired(savedToken)) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        setUser(null);
        setToken(null);
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

  const login = async (username: string, password: string): Promise<void> => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Step 1: Login to get the access token
      const loginResponse = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const loginData = await loginResponse.json();

      if (!loginResponse.ok) {
        throw new Error(loginData.detail || 'Login failed');
      }

      const { access_token } = loginData;
      
      // Step 2: Get user data using the token
      const userResponse = await fetch(`${API_BASE_URL}/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${access_token}`,
        },
      });

      const userData = await userResponse.json();

      if (!userResponse.ok) {
        throw new Error(userData.detail || 'Failed to get user data');
      }

      // Store auth data
      setToken(access_token);
      setUser(userData);
      
      // Persist to localStorage
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('auth_user', JSON.stringify(userData));
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (userData: RegisterData): Promise<void> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
      }

      // User created successfully, but not logged in yet
      // You might want to auto-login here or redirect to login
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Registration failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const updateProfile = async (userData: Partial<User>): Promise<void> => {
    if (!token) {
      throw new Error('Not authenticated');
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(userData),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Profile update failed');
      }

      // Update user data
      setUser(data);
      localStorage.setItem('auth_user', JSON.stringify(data));
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Profile update failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    // Clear auth state
    setUser(null);
    setToken(null);
    setError(null);
    
    // Clear localStorage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    
    // Optionally call logout endpoint
    if (token) {
      fetch(`${API_BASE_URL}/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }).catch(err => {
        console.warn('Logout request failed:', err);
      });
    }
  };

  const contextValue: AuthContextType = {
    user,
    token,
    login,
    logout,
    register,
    updateProfile,
    isLoading: isLoading || isInitializing,
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
