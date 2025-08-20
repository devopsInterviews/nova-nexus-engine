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
  id?: string;
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
    console.log(`Making API request to: ${url}`, options);
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    // Try to parse the response as JSON
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      console.warn('Response was not JSON:', text);
      data = { message: text };
    }

    if (!response.ok) {
      console.error('API error response:', data);
      return {
        status: 'error',
        error: data.detail || data.message || 'Server returned an error',
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
      error: error instanceof Error 
        ? `Network error: ${error.message}` 
        : 'Failed to connect to server',
    };
  }
}

// API services
export const dbService = {
  // Health check for API connectivity
  checkApiHealth: async (): Promise<ApiResponse<{ status: string; service: string }>> => {
    return fetchApi('/api/health');
  },
  
  // Test database connection
  testConnection: async (connection: DbConnection): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    return fetchApi('/api/test-connection', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Save database connection
  saveConnection: async (connection: DbConnection): Promise<ApiResponse<{ id: string }>> => {
    return fetchApi('/api/save-connection', {
      method: 'POST',
      body: JSON.stringify(connection),
    });
  },

  // Get saved connections
  getSavedConnections: async (): Promise<ApiResponse<DbConnection[]>> => {
    return fetchApi('/api/get-connections');
  },

  // List database tables
  listTables: async (connection: DbConnection): Promise<ApiResponse<string[]>> => {
    const res = await fetchApi<{ tables: string[] }>(`/api/list-tables`, {
      method: 'POST',
      body: JSON.stringify(connection),
    });
    if (res.status === 'success' && res.data) {
      return { status: 'success', data: res.data.tables as unknown as string[] };
    }
    return res as unknown as ApiResponse<string[]>;
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
