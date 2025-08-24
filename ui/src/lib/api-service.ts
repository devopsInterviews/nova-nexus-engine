// API Service for communication with the backend

// Base URL for API requests
// Ensure this points to your FastAPI host (defaults to local dev)
// Prefer Vite env, fallback to current origin or default localhost
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const viteEnv = (typeof import.meta !== 'undefined' ? (import.meta as any).env : undefined) as any;
const API_BASE_URL = (viteEnv && viteEnv.VITE_API_BASE_URL) 
  || (typeof window !== 'undefined' ? window.location.origin.replace(/:\d+$/, ':8000') : '') 
  || 'http://localhost:8000';

// Types for database connections
export interface DbConnection {
  id?: string;
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

// Generic fetch wrapper with error handling and smart unwrapping of backend {status,data}
async function fetchApi<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
  console.log(`API -> ${options.method || 'GET'} ${url}`, options.body ? JSON.parse(options.body as string) : undefined);
    
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

    // If backend wraps as { status, data }, unwrap it.
    if (data && typeof data === 'object' && 'status' in data && 'data' in data) {
      const inner = (data as any).data;
      return { status: 'success', data: inner as T };
    }

    return { status: 'success', data: data as T };
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

// Helper to build payload: if we have a saved profile id and no clear-text password, send only connection_id
function buildPayload(conn: DbConnection, extra?: Record<string, any>) {
  const looksMasked = typeof conn.password === 'string' && conn.password.includes('*');
  if (conn.id && (looksMasked || !conn.password)) {
    return { connection_id: conn.id, ...(extra || {}) };
  }
  return { ...conn, ...(extra || {}) };
}

// API services
export const dbService = {
  // Health check for API connectivity
  checkApiHealth: async (): Promise<ApiResponse<{ status: string; service: string }>> => {
    return fetchApi('/api/health');
  },
  
  // Test database connection
  testConnection: async (connection: DbConnection): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    const body = buildPayload(connection);
    return fetchApi('/api/test-connection', {
      method: 'POST',
      body: JSON.stringify(body),
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

  // Delete a saved connection
  deleteConnection: async (connectionId: string): Promise<ApiResponse<{ message: string }>> => {
    return fetchApi(`/api/delete-connection/${connectionId}`, {
      method: 'DELETE',
    });
  },

  // List database tables
  listTables: async (connection: DbConnection): Promise<ApiResponse<string[]>> => {
    const body = buildPayload(connection);
    return fetchApi<string[]>('/api/list-tables', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Describe table columns
  describeColumns: async (connection: DbConnection & { table: string; limit?: number }): 
    Promise<ApiResponse<Array<{ column: string; description: string; data_type: string }>>> => {
    const { table, limit = 100, ...conn } = connection as any;
    const body = buildPayload(conn as DbConnection, { table, limit });
    return fetchApi<Array<{ column: string; description: string; data_type: string }>>('/api/describe-columns', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Suggest columns based on natural language query
  suggestColumns: async (connection: DbConnection & { 
    user_prompt: string;
    confluenceSpace?: string;
    confluenceTitle?: string;
  }): Promise<ApiResponse<{ suggested_columns: Array<{ name: string; description: string; data_type: string }> }>> => {
    const { user_prompt, confluenceSpace, confluenceTitle, ...conn } = connection as any;
    const body = buildPayload(conn as DbConnection, { user_prompt, confluenceSpace, confluenceTitle });
    return fetchApi<{ suggested_columns: Array<{ name: string; description: string; data_type: string }> }>('/api/suggest-columns', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Run analytics query
  runAnalyticsQuery: async (connection: DbConnection & { 
    analytics_prompt: string;
    system_prompt?: string;
    confluenceSpace?: string;
    confluenceTitle?: string;
  }): Promise<ApiResponse<{ rows: Record<string, any>[]; sql?: string }>> => {
    const { analytics_prompt, system_prompt, confluenceSpace, confluenceTitle, ...conn } = connection as any;
    const body = buildPayload(conn as DbConnection, { analytics_prompt, system_prompt, confluenceSpace, confluenceTitle });
    return fetchApi<{ rows: Record<string, any>[]; sql?: string }>('/api/analytics-query', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Sync all tables to Confluence
  syncAllTables: async (connection: DbConnection & {
    space: string;
    title: string;
    limit: number;
  }): Promise<ApiResponse<{ 
    results: Array<{
      table: string;
      newColumns: Array<{ column: string; description: string }>;
      error: string | null;
    }>
  }>> => {
    const { space, title, limit, ...conn } = connection as any;
    const body = buildPayload(conn as DbConnection, { space, title, limit });
    return fetchApi<{ 
      results: Array<{
        table: string;
        newColumns: Array<{ column: string; description: string }>;
        error: string | null;
      }>
    }>('/api/sync-all-tables', {
      method: 'POST',
      body: JSON.stringify(body),
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
