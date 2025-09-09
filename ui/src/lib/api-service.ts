// API Service for communication with the backend
// This file handles all HTTP requests to our FastAPI server

// Base URL configuration for API requests
// This determines where our frontend sends HTTP requests
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const viteEnv = (typeof import.meta !== 'undefined' ? (import.meta as any).env : undefined) as any; // Get Vite environment variables (build-time config)
const API_BASE_URL = (viteEnv && viteEnv.VITE_API_BASE_URL)  // Try environment variable first
  || (typeof window !== 'undefined' ? window.location.origin.replace(/:\d+$/, ':8000') : '')  // Fallback: current domain but port 8000
  || 'http://localhost:8000'; // Final fallback: localhost development server

// TypeScript interface: defines the shape/structure of database connection objects
// "export" means other files can import and use this interface
export interface DbConnection {
  id?: string;              // Optional field (? means it might not exist) - unique identifier
  host: string;             // Required string - database server address (like "localhost" or "db.company.com")
  port: number;             // Required number - database port (like 5432 for PostgreSQL)
  user: string;             // Required string - database username
  password: string;         // Required string - database password
  database: string;         // Required string - name of the database to connect to
  database_type: string;    // Required string - type of database ("postgresql", "mysql", etc.)
  name?: string;            // Optional string - human-friendly name for this connection
}

// Generic TypeScript interface for all API responses
// <T> is a generic type parameter - it can be any type when used
export interface ApiResponse<T> {
  status: 'success' | 'error';  // Union type: can only be "success" OR "error"
  data?: T;                     // Optional data of type T (only present on success)
  error?: string;               // Optional error message (only present on error)
}

// Main function for making HTTP requests to our API
// <T> is a generic type - the caller specifies what type of data they expect back
// async/await: this function runs asynchronously (doesn't block other code)
async function fetchApi<T>(
  endpoint: string,                     // The API path (like "/api/users")
  options: RequestInit = {}             // HTTP options (method, headers, body) with default empty object
): Promise<ApiResponse<T>> {            // Returns a Promise that resolves to ApiResponse<T>
  try {                                 // try/catch block for error handling
    const url = `${API_BASE_URL}${endpoint}`;  // Template literal: combines base URL + endpoint
    console.log(`API -> ${options.method || 'GET'} ${url}`, options.body ? JSON.parse(options.body as string) : undefined); // Log request details
    
    // Get authentication token from browser's localStorage (persists between sessions)
    const token = localStorage.getItem('auth_token');  // Returns string or null
    
    // Build HTTP headers object
    const headers: HeadersInit = {        // HeadersInit is a TypeScript type for HTTP headers
      'Content-Type': 'application/json', // Tell server we're sending JSON data
      ...(options.headers || {}),         // Spread operator: merge any existing headers
    };
    
    // Add authentication header if we have a token
    if (token) {                          // if statement: only run when token exists
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;  // Type assertion + bearer token format
    }
    
    // Make the actual HTTP request using the fetch API
    const response = await fetch(url, {   // await: wait for the HTTP request to complete
      ...options,                         // Spread existing options (method, body, etc.)
      headers,                            // Use our prepared headers
    });

    // Handle authentication errors (401 = Unauthorized)
    if (response.status === 401) {        // HTTP status code 401 means authentication failed
      const hadToken = !!token;           // Double negation converts to boolean: true if token exists
      if (hadToken) {                     // Only try to handle expired tokens if we had one
        // Smart token validation: check if JWT is actually expired before forcing logout
        let shouldLogout = true;          // Default assumption: logout needed
        try {
          const parts = token.split('.'); // JWT format: header.payload.signature
          if (parts.length === 3) {       // Valid JWT has exactly 3 parts
            // Decode the payload (middle part) from base64
            const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))); // Handle URL-safe base64
            const now = Math.floor(Date.now() / 1000); // Current time in seconds (JWT uses seconds)
            if (payload.exp && payload.exp > now + 5) { // If token expires more than 5 seconds from now
              shouldLogout = false;       // Token is still valid - might be temporary server issue
            }
          }
        } catch { /* ignore decode errors -> proceed to logout */ } // If JWT parsing fails, logout anyway
        
        if (shouldLogout) {               // Token is expired or invalid
          localStorage.removeItem('auth_token');    // Clear stored token
          localStorage.removeItem('auth_user');     // Clear stored user info
          if (!window.location.pathname.includes('/login')) { // Don't redirect if already on login page
            window.location.href = '/login';        // Redirect to login page
          }
          return { status: 'error', error: 'Authentication required. Please log in again.' };
        } else {
          // Token should be valid - might be temporary server issue
          return { status: 'error', error: 'Temporary authorization issue. Please retry.' };
        }
      }
      return { status: 'error', error: 'Unauthorized' }; // No token was provided
    }

    // Parse the response data
    let data;                             // Variable to hold parsed response
    const contentType = response.headers.get('content-type'); // Get the response content type
    if (contentType && contentType.includes('application/json')) { // Check if response is JSON
      data = await response.json();       // Parse JSON response
    } else {
      const text = await response.text(); // Get response as plain text
      console.warn('Response was not JSON:', text); // Log unexpected non-JSON response
      data = { message: text };           // Wrap text in object for consistency
    }

    // Check if the HTTP request failed (status codes 400-599)
    if (!response.ok) {                   // response.ok is false for status codes 400+
      console.error('API error response:', data); // Log error details
      return {
        status: 'error',                  // Return error response
        error: data.detail || data.message || 'Server returned an error', // Extract error message
      };
    }

    // Smart response unwrapping: some APIs wrap data in { status, data }
    if (data && typeof data === 'object' && 'status' in data && 'data' in data) {
      const inner = (data as any).data;   // Extract the inner data
      return { status: 'success', data: inner as T }; // Return unwrapped data
    }

    return { status: 'success', data: data as T }; // Return data as-is
  } catch (error) {                       // Catch network errors, parsing errors, etc.
    console.error('API request failed:', error); // Log the error
    return {
      status: 'error',
      error: error instanceof Error       // Check if error is an Error object
        ? `Network error: ${error.message}` // Use error message if available
        : 'Failed to connect to server',  // Generic message for unknown errors
    };
  }
}

// Helper function to build request payloads for database operations
// This function handles security: if password looks masked (****), only send connection ID
function buildPayload(conn: DbConnection, extra?: Record<string, any>) { // extra is optional object with any additional data
  const looksMasked = typeof conn.password === 'string' && /\*{3,}/.test(conn.password); // Regex: check if password has 3+ asterisks
  
  // Build base connection object with required fields
  const base: Record<string, any> = {     // Record<string, any> = object with string keys and any values
    host: conn.host,                      // Copy database connection details
    port: conn.port,
    user: conn.user,
    database: conn.database,
    database_type: conn.database_type,
    name: conn.name,
  };
  
  if (conn.id) base.connection_id = conn.id; // Add connection ID if it exists
  if (!looksMasked && conn.password) base.password = conn.password; // Only include real password, not masked ones
  
  // Validation: warn about missing required fields
  ["host","port","user","database","database_type"].forEach(k => { // Array.forEach: run function for each item
    if (base[k] === undefined || base[k] === null) { // Check if field is missing
      console.warn(`buildPayload missing field ${k} for connection`, conn); // Log warning
    }
  });
  
  return { ...base, ...(extra || {}) };   // Spread operator: merge base object with extra data
}

// Object containing all database-related API functions
// "export const" makes this object available to other files
export const dbService = {
  // Simple health check to verify API is running
  // Promise<ApiResponse<...>> means this function returns a Promise that resolves to an ApiResponse
  checkApiHealth: async (): Promise<ApiResponse<{ status: string; service: string }>> => {
    return fetchApi('/api/health');       // GET request to health endpoint
  },
  
  // Test if database connection works without saving it
  testConnection: async (connection: DbConnection): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    const body = buildPayload(connection); // Convert connection to API payload
    return fetchApi('/api/test-connection', {
      method: 'POST',                     // POST request (sending data)
      body: JSON.stringify(body),         // Convert JavaScript object to JSON string
    });
  },

  // Save a database connection profile for later use
  saveConnection: async (connection: DbConnection): Promise<ApiResponse<{ id: string }>> => {
    return fetchApi('/api/save-connection', {
      method: 'POST',                     // POST to create new resource
      body: JSON.stringify(connection),   // Send the full connection object
    });
  },

  // Get all saved database connections for current user
  getSavedConnections: async (): Promise<ApiResponse<DbConnection[]>> => { // DbConnection[] = array of DbConnection objects
    return fetchApi('/api/get-connections'); // Simple GET request
  },

  // Delete a saved connection by its ID
  deleteConnection: async (connectionId: string): Promise<ApiResponse<{ message: string }>> => {
    return fetchApi(`/api/delete-connection/${connectionId}`, { // Template literal: insert connectionId into URL
      method: 'DELETE',                   // DELETE HTTP method for removing resources
    });
  },

  // Get list of all table names in the database
  listTables: async (connection: DbConnection): Promise<ApiResponse<string[]>> => { // string[] = array of strings
    const body = buildPayload(connection); // Prepare connection payload
    return fetchApi<string[]>('/api/list-tables', { // <string[]> explicitly tells TypeScript what data type to expect
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Get detailed information about columns in a specific table
  // Intersection type (&): combines DbConnection with additional fields
  describeColumns: async (connection: DbConnection & { table: string; limit?: number }): 
    Promise<ApiResponse<Array<{ column: string; description: string; data_type: string }>>> => {
    // Destructuring assignment: extract specific properties from object
    const { table, limit = 100, ...conn } = connection as any; // Default limit to 100, spread rest into conn
    const body = buildPayload(conn as DbConnection, { table, limit }); // Merge base connection with table-specific data
    return fetchApi<Array<{ column: string; description: string; data_type: string }>>('/api/describe-columns', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Get actual data from a table (rows and column names)
  getTableRows: async (connection: DbConnection & { table: string; limit?: number }):
    Promise<ApiResponse<{ columns: string[]; rows: any[] }>> => { // Returns object with columns array and rows array
    const { table, limit = 100, ...conn } = connection as any; // Extract table name and limit, rest goes to conn
    const body = buildPayload(conn as DbConnection, { table, limit }); // Build request payload
    return fetchApi<{ columns: string[]; rows: any[] }>("/api/get-table-rows", {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // AI-powered column suggestion based on natural language description
  suggestColumns: async (connection: DbConnection & { 
    user_prompt: string;            // Required: what the user wants to analyze
    confluenceSpace?: string;       // Optional: Confluence space for context
    confluenceTitle?: string;       // Optional: Confluence page for context
  }): Promise<ApiResponse<{ suggested_columns: Array<{ name: string; description: string; data_type: string }> }>> => {
    const { user_prompt, confluenceSpace, confluenceTitle, ...conn } = connection as any; // Destructure all parameters
    const body = buildPayload(conn as DbConnection, { user_prompt, confluenceSpace, confluenceTitle }); // Include all in payload
    return fetchApi<{ suggested_columns: Array<{ name: string; description: string; data_type: string }> }>('/api/suggest-columns', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Run natural language analytics queries (AI converts to SQL)
  runAnalyticsQuery: async (connection: DbConnection & { 
    analytics_prompt: string;       // Required: the analytics question in natural language
    system_prompt?: string;         // Optional: system instructions for AI
    confluenceSpace?: string;       // Optional: Confluence context
    confluenceTitle?: string;       // Optional: specific page context
  }): Promise<ApiResponse<{ rows: Record<string, any>[]; sql?: string }>> => { // Record<string, any> = object with string keys
    const { analytics_prompt, system_prompt, confluenceSpace, confluenceTitle, ...conn } = connection as any;
    const body = buildPayload(conn as DbConnection, { analytics_prompt, system_prompt, confluenceSpace, confluenceTitle });
    return fetchApi<{ rows: Record<string, any>[]; sql?: string }>('/api/analytics-query', { // Results plus optional SQL query
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Synchronize all database tables to Confluence documentation
  syncAllTables: async (connection: DbConnection & {
    space: string;                  // Confluence space name
    title: string;                  // Confluence page title
    limit: number;                  // Maximum rows to process per table
  }): Promise<ApiResponse<{ 
    results: Array<{                // Array of results, one per table
      table: string;                // Table name that was processed
      newColumns: Array<{ column: string; description: string }>; // New documentation added
      error: string | null;         // Error message if sync failed for this table
    }>
  }>> => {
    const { space, title, limit, ...conn } = connection as any; // Extract sync parameters
    const body = buildPayload(conn as DbConnection, { space, title, limit }); // Build sync request
    return fetchApi<{ 
      results: Array<{
        table: string;
        newColumns: Array<{ column: string; description: string }>;
        error: string | null;       // Union type: string OR null
      }>
    }>('/api/sync-all-tables', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Sync all tables with detailed progress tracking
  // Returns comprehensive progress information including timing and stage details
  syncAllTablesWithProgress: async (connection: DbConnection & {
    space: string;                  // Confluence space name
    title: string;                  // Confluence page title  
    limit: number;                  // Row processing limit
  }): Promise<ApiResponse<{
    status: string;                 // Current operation status
    stage: string;                  // What stage of sync we're in
    current_table: string | null;   // Table currently being processed (null if between tables)
    current_table_index: number;    // Index of current table (0-based)
    total_tables: number;           // Total number of tables to process
    progress_percentage: number;     // Progress as percentage (0-100)
    stage_details: string;          // Human-readable stage description
    tables_processed: Array<{       // Array of completed tables with results
      table: string;                // Table name
      newColumns: Array<{ column: string; description: string }>; // New columns documented
      error: string | null;         // Error if processing failed
      stage: string;                // Final stage reached for this table
    }>;
    tables_pending: string[];       // Array of table names still to be processed
    summary: {                      // Overall summary statistics
      total_tables: number;         // Total tables in operation
      successful_tables: number;    // Number that completed successfully
      failed_tables: number;        // Number that failed
      total_synced_columns: number; // Total columns documented across all tables
    };
    results?: Array<{               // Optional final results (present when complete)
      table: string;
      newColumns: Array<{ column: string; description: string }>;
      error: string | null;
    }>;
    start_time?: number;            // Optional: when sync started (timestamp)
    end_time?: number;              // Optional: when sync completed (timestamp)  
    duration?: number;              // Optional: total time taken (seconds)
  }>> => {
    const { space, title, limit, ...conn } = connection as any; // Extract parameters
    const body = buildPayload(conn as DbConnection, { space, title, limit }); // Build request
    return fetchApi<{               // Complex response type with all progress details
      status: string;
      stage: string;
      current_table: string | null;
      current_table_index: number;
      total_tables: number;
      progress_percentage: number;
      stage_details: string;
      tables_processed: Array<{
        table: string;
        newColumns: Array<{ column: string; description: string }>;
        error: string | null;
        stage: string;
      }>;
      tables_pending: string[];
      summary: {
        total_tables: number;
        successful_tables: number;
        failed_tables: number;
        total_synced_columns: number;
      };
      results?: Array<{
        table: string;
        newColumns: Array<{ column: string; description: string }>;
        error: string | null;
      }>;
      start_time?: number;
      end_time?: number;
      duration?: number;
    }>('/api/sync-all-tables-with-progress', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Real-time streaming sync with live progress updates
  // This function establishes a streaming connection to get live updates during sync
  syncAllTablesWithProgressStream: async (
    connection: DbConnection & {      // Connection plus sync parameters
      space: string;
      title: string;
      limit: number;
    },
    onProgress: (progressData: any) => void  // Callback function: called each time progress updates
  ): Promise<{ status: 'success' | 'error', error?: string }> => { // Simplified return type for streaming
    const { space, title, limit, ...conn } = connection as any; // Extract parameters
    const body = buildPayload(conn as DbConnection, { space, title, limit }); // Build request payload
    
    try {
      const authToken = localStorage.getItem('auth_token'); // Get authentication token
      
      // Manual fetch for streaming (fetchApi doesn't handle streams well)
      const response = await fetch('/api/sync-all-tables-with-progress-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}), // Conditional spread: add auth if token exists
        },
        body: JSON.stringify(body),     // Send connection data
      });

      if (!response.ok) {             // Check for HTTP errors
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Set up streaming reader for real-time updates
      const reader = response.body?.getReader(); // Optional chaining: only call getReader if body exists
      if (!reader) {
        throw new Error('No response body reader available');
      }

      const decoder = new TextDecoder(); // Converts binary data to text
      let buffer = '';                  // Buffer for incomplete JSON lines

      // Infinite loop to read streaming data
      while (true) {                    // Continue until stream ends
        const { done, value } = await reader.read(); // Read next chunk of data
        
        if (done) {                     // Stream ended
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6); // Remove 'data: ' prefix
            
            if (data === '[DONE]') {
              return { status: 'success' };
            }
            
            try {
              const progressData = JSON.parse(data);
              onProgress(progressData);
              
              if (progressData.status === 'error') {
                return { status: 'error', error: progressData.error };
              }
            } catch (e) {
              console.warn('Failed to parse progress data:', data, e);
            }
          }
        }
      }

      return { status: 'success' };
    } catch (error) {
      console.error('Stream sync error:', error);
      return { status: 'error', error: error instanceof Error ? error.message : 'Unknown error' };
    }
  },

  // Log dbt file upload from SQL Builder - dbt tab
  logDbtFileUpload: async (fileData: {
    fileName: string;
    fileSize: number;
    fileType: string;
    contentPreview: string;
  }): Promise<ApiResponse<{ fileName: string; fileSize: number; logged_at: string }>> => {
    return fetchApi('/api/log-dbt-file-upload', {
      method: 'POST',
      body: JSON.stringify(fileData),
    });
  },
};

// Separate object for analytics-related API calls
export const analyticsService = {
  // Get system overview dashboard data (stats + recent activity)
  getSystemOverview: async (): Promise<ApiResponse<{
    stats: Array<{                        // Array of metric cards for dashboard
      title: string;                      // Metric name like "System Uptime"
      value: string;                      // Current value like "99.9%"
      description: string;                // Additional context like "Last 30 days"
      status: 'success' | 'warning' | 'error' | 'info'; // Visual status indicator
      trend: 'up' | 'down' | 'stable';    // Trend direction for arrow icons
      trendValue: string;                 // Trend percentage like "+2.1%"
    }>;
    recentActivity: Array<{               // Recent system activity feed
      action: string;                     // What action occurred
      status: string;                     // Result of the action
      time: string;                       // When it happened
      type: 'success' | 'warning' | 'error'; // Type for styling/icons
    }>;
  }>> => {
    return fetchApi('/api/analytics/system-overview'); // Simple GET request
  },

  // Get key metrics (simplified version without activity feed)
  getKeyMetrics: async (): Promise<ApiResponse<{
    metrics: Array<{                      // Same structure as stats above but different endpoint
      title: string;                      // Metric display name
      value: string;                      // Current metric value
      description: string;                // Explanatory text
      status: 'success' | 'warning' | 'error' | 'info'; // Status for coloring
      trend: 'up' | 'down' | 'stable';    // Trend direction
      trendValue: string;                 // Trend change amount
    }>;
  }>> => {
    return fetchApi('/api/analytics/key-metrics'); // Different endpoint, similar data structure
  },

  // Get top pages by view count with configurable parameters
  getTopPages: async (limit: number = 10, hours: number = 24): Promise<ApiResponse<{
    topPages: Array<{                     // Array of top pages by traffic
      path: string;                       // URL path of the page
      views: string;                      // Number of views (as string for display)
      change: string;                     // Change from previous period
    }>;
  }>> => {
    return fetchApi(`/api/analytics/top-pages?limit=${limit}&hours=${hours}`); // Template literal with query parameters
  },

  // Get error analysis by type for the specified time period
  getErrorAnalysis: async (hours: number = 24): Promise<ApiResponse<{
    errorsByType: Array<{                 // Categorized error breakdown
      type: string;                       // Error category/type
      count: number;                      // Number of occurrences
      percentage: number;                 // Percentage of total errors
    }>;
  }>> => {
    return fetchApi(`/api/analytics/error-analysis?hours=${hours}`); // Single query parameter
  },

  // Send page view tracking data to server (for analytics collection)
  logPageView: async (data: {
    path: string;                         // Required: page path that was viewed
    title?: string;                       // Optional: page title
    loadTime?: number;                    // Optional: page load time in milliseconds
  }): Promise<ApiResponse<{ message: string }>> => {
    return fetchApi('/api/analytics/log-page-view', {
      method: 'POST',                     // POST because we're sending data to server
      body: JSON.stringify(data),         // Convert tracking data to JSON
    });
  },

  // Trigger MCP (Model Context Protocol) server status update
  updateMcpStatus: async (): Promise<ApiResponse<{ message: string }>> => {
    return fetchApi('/api/analytics/update-mcp-status', {
      method: 'POST',                     // POST for action/command endpoints
    });                                   // No body needed - action is implied by endpoint
  },

  // Trigger test activity (development/testing feature)
  triggerTestActivity: async (): Promise<ApiResponse<{ message: string }>> => {
    return fetchApi('/api/analytics/trigger-test-activity', {
      method: 'POST',                     // POST to trigger the test action
    });                                   // No additional data required
  },
};

// TypeScript interface for connection context (shared state between components)
export interface ConnectionContext {
  currentConnection: DbConnection | null; // Currently selected database connection (null if none selected)
  setCurrentConnection: (conn: DbConnection | null) => void; // Function to update the current connection
  savedConnections: DbConnection[];       // Array of all saved database connections
  setSavedConnections: (conns: DbConnection[]) => void; // Function to update saved connections list
  refreshConnections: () => Promise<void>; // Function to reload connections from server
}

// Export combined API service object for easy importing
// Usage: import apiService from './api-service' then apiService.db.testConnection()
export default {
  db: dbService,                          // Database operations
  analytics: analyticsService,            // Analytics and monitoring
};