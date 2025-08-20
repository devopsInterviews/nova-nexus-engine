// API Service for communication with the backend

// Base URL for API requests
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Types for database connections
export interface DbConnection {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
  database_type: string;
  name?: string;
}

// Types for responses
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
}

// Generic fetch wrapper with error handling
async function fetchApi<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        status: 'error',
        error: data.detail || 'An unknown error occurred',
      };
    }

    return {
      status: 'success',
      data: data as T,
    };
  } catch (error) {
    console.error('API request failed:', error);
    return {
      status: 'error',
      error: error instanceof Error ? error.message : 'Network error',
    };
  }
}

// API services
export const dbService = {
  // Test database connection
  testConnection: async (connection: DbConnection): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    return fetchApi('/test-connection', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Save database connection
  saveConnection: async (connection: DbConnection): Promise<ApiResponse<{ id: string }>> => {
    return fetchApi('/save-connection', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Get saved connections
  getSavedConnections: async (): Promise<ApiResponse<DbConnection[]>> => {
    return fetchApi('/get-connections');
  },

  // List database tables
  listTables: async (connection: DbConnection): Promise<ApiResponse<string[]>> => {
    return fetchApi('/list-tables-test', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      // Using URLSearchParams to properly encode query parameters
      body: undefined, // GET requests don't have a body
    });
  },

  // Describe table columns
  describeColumns: async (connection: DbConnection & { table: string; limit: number; space: string; title: string }): 
    Promise<ApiResponse<Array<{ column: string; description: string }>>> => {
    return fetchApi('/describe-all-columns', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Suggest columns based on natural language query
  suggestColumns: async (connection: DbConnection & { 
    user_prompt: string;
    confluenceSpace: string;
    confluenceTitle: string;
  }): Promise<ApiResponse<{ suggested_keys: string[] }>> => {
    return fetchApi('/suggest-keys', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Run analytics query
  runAnalyticsQuery: async (connection: DbConnection & { 
    analytics_prompt: string;
    system_prompt: string;
    confluenceSpace?: string;
    confluenceTitle?: string;
  }): Promise<ApiResponse<{ rows: Record<string, any>[] }>> => {
    return fetchApi('/analytics-query', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },
};

// Context for storing connection info across tabs
export interface ConnectionContext {
  currentConnection: DbConnection | null;
  setCurrentConnection: (conn: DbConnection | null) => void;
  savedConnections: DbConnection[];
  setSavedConnections: (conns: DbConnection[]) => void;
  refreshConnections: () => Promise<void>;
}

// Export the API service
export default {
  db: dbService,
};
