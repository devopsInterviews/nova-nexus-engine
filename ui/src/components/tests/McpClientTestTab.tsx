import { useState, useEffect } from "react";

interface ApiEndpoint {
  path: string;
  method: string;
  description: string;
  parameters?: string[];
  tags: string[];
}

interface RequestParameter {
  name: string;
  value: string;
  type?: string;
}

interface SavedEndpointTest {
  id: string;
  name: string;
  endpoint_path: string;
  method: string;
  parameters: RequestParameter[];
  request_type: 'body' | 'query';
  created_at: string;
}

export const McpClientTestTab = () => {
  const [endpoints, setEndpoints] = useState<ApiEndpoint[]>([]);
  const [groupedEndpoints, setGroupedEndpoints] = useState<{ [key: string]: ApiEndpoint[] }>({});
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>("");
  const [requestParameters, setRequestParameters] = useState<RequestParameter[]>([]);
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [savedTests, setSavedTests] = useState<SavedEndpointTest[]>([]);
  const [requestType, setRequestType] = useState<'body' | 'query'>('body');
  const [filterText, setFilterText] = useState("");
  const [methodFilter, setMethodFilter] = useState<"ALL" | "GET" | "POST">("ALL");
  const [testName, setTestName] = useState("");

  // Load saved tests from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("mcp-client-tests");
    if (saved) {
      try {
        setSavedTests(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to load saved tests:", e);
      }
    }
  }, []);

  // Fetch available API endpoints on component mount
  useEffect(() => {
    fetchEndpoints();
  }, []);

  // Reset parameters when endpoint is selected
  useEffect(() => {
    if (selectedEndpoint) {
      const endpoint = endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint);
      if (endpoint && endpoint.parameters) {
        // Initialize parameters based on endpoint definition
        const initialParams: RequestParameter[] = endpoint.parameters.map(param => ({
          name: param,
          value: "",
          type: "string"
        }));
        setRequestParameters(initialParams);
        
        // Set default request type based on method
        setRequestType(endpoint.method === 'GET' ? 'query' : 'body');
      } else {
        setRequestParameters([]);
      }
    } else {
      setRequestParameters([]);
    }
    setResponse(null);
  }, [selectedEndpoint, endpoints]);

  useEffect(() => {
    if (endpoints.length > 0) {
      // Filter endpoints based on text input and method filter
      const filtered = endpoints.filter(endpoint => {
        const matchesText = endpoint.path.toLowerCase().includes(filterText.toLowerCase());
        const matchesMethod = methodFilter === "ALL" || endpoint.method === methodFilter;
        return matchesText && matchesMethod;
      });
      
      // Group filtered endpoints by tags
      const grouped = filtered.reduce((acc, endpoint) => {
        endpoint.tags.forEach(tag => {
          if (!acc[tag]) {
            acc[tag] = [];
          }
          acc[tag].push(endpoint);
        });
        return acc;
      }, {} as { [key: string]: ApiEndpoint[] });
      
      setGroupedEndpoints(grouped);
    }
  }, [endpoints, filterText, methodFilter]);

  const fetchEndpoints = async () => {
    try {
      setLoading(true);
      // Backend mcp_router is mounted at /api, so discovery endpoint is /api/all-endpoints
      const response = await fetch("/api/all-endpoints");
      const data = await response.json();
      
      if (data.endpoints) {
        setEndpoints(data.endpoints);
        setGroupedEndpoints(data.grouped_endpoints || {});
      }
    } catch (err) {
      console.error("Failed to fetch endpoints:", err);
    } finally {
      setLoading(false);
    }
  };

  const executeEndpoint = async () => {
    if (!selectedEndpoint) return;

    setLoading(true);
    setResponse(null);

    const endpointDetails = endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint);
    if (!endpointDetails) {
      setLoading(false);
      return;
    }

    const params = requestParameters.reduce((acc, p) => {
      acc[p.name] = p.value;
      return acc;
    }, {} as Record<string, any>);

    try {
      let res;
      // The discovered path doesn't include /api prefix, so we need to add it
      const url = endpointDetails.path.startsWith('/api') ? endpointDetails.path : `/api${endpointDetails.path}`;
      const options: RequestInit = {
        method: endpointDetails.method,
        headers: {
          "Content-Type": "application/json",
        },
      };

      if (endpointDetails.method === 'POST') {
        options.body = JSON.stringify(params);
        res = await fetch(url, options);
      } else { // GET request
        const query = new URLSearchParams(params).toString();
        const fullUrl = query ? `${url}?${query}` : url;
        res = await fetch(fullUrl, { ...options, method: 'GET' });
      }
      
      // Check if response is successful and contains JSON
      let data;
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        data = await res.json();
      } else {
        // If not JSON, get text content (likely HTML error page)
        const textContent = await res.text();
        data = { 
          error: `Server returned ${res.status} ${res.statusText}`,
          content_type: contentType,
          raw_response: textContent.substring(0, 500) // Limit response length
        };
      }
      
      setResponse({ status: res.status, data });
    } catch (error) {
      console.error("Error executing endpoint:", error);
      setResponse({ status: 500, data: { error: (error as Error).message } });
    } finally {
      setLoading(false);
    }
  };

  const handleEndpointChange = (value: string) => {
    setSelectedEndpoint(value);
    setRequestParameters([]);
    setResponse(null);
  };

  const addParameter = () => {
    setRequestParameters([...requestParameters, { name: "", value: "" }]);
  };

  const updateParameter = (index: number, field: 'name' | 'value', value: string) => {
    const updated = [...requestParameters];
    updated[index][field] = value;
    setRequestParameters(updated);
  };

  const removeParameter = (index: number) => {
    setRequestParameters(requestParameters.filter((_, i) => i !== index));
  };

  const saveTest = () => {
    if (!selectedEndpoint) return;

    const newTest: SavedEndpointTest = {
      id: Date.now().toString(),
      name: `${selectedEndpoint} - ${new Date().toISOString()}`,
      endpoint_path: selectedEndpoint.split(' ')[1],
      method: selectedEndpoint.split(' ')[0],
      parameters: requestParameters,
      request_type: requestType,
      created_at: new Date().toISOString(),
    };

    const updatedTests = [...savedTests, newTest];
    setSavedTests(updatedTests);
    localStorage.setItem("mcp-client-tests", JSON.stringify(updatedTests));
  };

  const loadTest = (test: SavedEndpointTest) => {
    setSelectedEndpoint(`${test.method} ${test.endpoint_path}`);
    setRequestParameters(test.parameters);
    setRequestType(test.request_type);
    setResponse(null);
  };

  const deleteTest = (id: string) => {
    const updatedTests = savedTests.filter(t => t.id !== id);
    setSavedTests(updatedTests);
    localStorage.setItem("mcp-client-tests", JSON.stringify(updatedTests));
  };

  const filteredEndpoints = Object.entries(groupedEndpoints).filter(([tag]) => tag.toLowerCase().includes(filterText.toLowerCase()));

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-2">FastAPI Client Testing</h3>
        <p className="text-sm text-muted-foreground">
          Test FastAPI client endpoints with interactive interfaces
        </p>
      </div>

      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="Filter endpoints..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          className="w-full p-2 border rounded"
        />
        <div className="flex items-center space-x-2">
          <button 
            onClick={() => setMethodFilter('ALL')} 
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              methodFilter === 'ALL' 
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg transform scale-105' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:shadow-md'
            }`}
          >
            ALL
          </button>
          <button 
            onClick={() => setMethodFilter('GET')} 
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              methodFilter === 'GET' 
                ? 'bg-gradient-to-r from-green-500 to-green-600 text-white shadow-lg transform scale-105' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:shadow-md'
            }`}
          >
            GET
          </button>
          <button 
            onClick={() => setMethodFilter('POST')} 
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              methodFilter === 'POST' 
                ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-lg transform scale-105' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:shadow-md'
            }`}
          >
            POST
          </button>
        </div>
      </div>

      {/* Endpoint Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="font-medium mb-3">1. Select API Endpoint</h4>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Available Endpoints ({endpoints.length} total)
              </label>
              <select 
                value={selectedEndpoint} 
                onChange={(e) => handleEndpointChange(e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="">Choose an endpoint to test</option>
                {filteredEndpoints.map(([tag, taggedEndpoints]) => (
                  <optgroup key={tag} label={`${tag.toUpperCase()} (${(taggedEndpoints as ApiEndpoint[]).length})`}>
                    {(taggedEndpoints as ApiEndpoint[]).map((endpoint) => (
                      <option key={`${endpoint.method} ${endpoint.path}`} value={`${endpoint.method} ${endpoint.path}`}>
                        {endpoint.method} {endpoint.path}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {selectedEndpoint && (
              <div className="text-sm bg-gray-50 p-3 rounded">
                <p className="font-medium">Description:</p>
                <p className="text-gray-600 mb-2">{endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.description}</p>
                <div className="flex items-center space-x-4 mb-2">
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                    endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'GET' ? 'bg-blue-100 text-blue-800' :
                    endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'POST' ? 'bg-green-100 text-green-800' :
                    endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'PUT' ? 'bg-yellow-100 text-yellow-800' :
                    endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'DELETE' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method}
                  </span>
                  <span className="text-sm text-gray-600">{endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.path}</span>
                </div>
                {endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.parameters && endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.parameters.length > 0 && (
                  <div>
                    <p className="font-medium">Expected Parameters:</p>
                    <div className="text-xs text-gray-600">
                      {endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.parameters.join(", ")}
                    </div>
                  </div>
                )}
                <div className="mt-2">
                  <p className="font-medium">Tags:</p>
                  <div className="space-x-1">
                    {endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.tags.map((tag) => (
                      <span key={tag} className="inline-block px-1 py-0.5 bg-gray-200 text-gray-700 rounded text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Parameter Configuration */}
        {selectedEndpoint && (
          <div className="border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium">2. Configure Parameters & Request Type</h4>
              <button
                onClick={addParameter}
                className="inline-flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-medium rounded-lg shadow-md hover:from-blue-600 hover:to-blue-700 hover:shadow-lg transform hover:scale-105 transition-all duration-200"
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd"/>
                </svg>
                <span>Add Parameter</span>
              </button>
            </div>
            
            {/* Request Type Selection */}
            <div className="mb-4 p-3 bg-gray-50 rounded">
              <h5 className="font-medium mb-2 text-sm">Request Type:</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="radio"
                    value="body"
                    checked={requestType === 'body'}
                    onChange={(e) => setRequestType(e.target.value as 'body' | 'query')}
                    disabled={endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'GET'}
                  />
                  <span className="text-sm">Request Body (JSON)</span>
                  <span className="text-xs text-gray-500">- Send parameters as JSON in request body</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="radio"
                    value="query"
                    checked={requestType === 'query'}
                    onChange={(e) => setRequestType(e.target.value as 'body' | 'query')}
                  />
                  <span className="text-sm">Query Parameters</span>
                  <span className="text-xs text-gray-500">- Send parameters in URL query string</span>
                </label>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="text-xs text-gray-600 bg-blue-50 p-2 rounded">
                <strong>Request Type:</strong> {requestType === 'body' ? 'JSON Body' : 'URL Query Parameters'}
                <br />
                <strong>Final URL:</strong> {endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.path}
                {requestType === 'query' && requestParameters.length > 0 && (
                  <>?{requestParameters.filter(p => p.key && p.value).map(p => `${p.key}=${p.value}`).join('&')}</>
                )}
              </div>
              
              {requestParameters.length === 0 ? (
                <p className="text-sm text-gray-600">
                  No parameters configured. Click "Add Parameter" to add request parameters.
                </p>
              ) : (
                <div className="space-y-3">
                  {requestParameters.map((param, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <input
                        type="text"
                        placeholder="Parameter name"
                        value={param.name}
                        onChange={(e) => updateParameter(index, 'name', e.target.value)}
                        className="flex-1 p-2 border rounded"
                      />
                      <input
                        type="text"
                        placeholder="Parameter value"
                        value={param.value}
                        onChange={(e) => updateParameter(index, 'value', e.target.value)}
                        className="flex-2 p-2 border rounded"
                      />
                      <button
                        onClick={() => removeParameter(index)}
                        className="px-2 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 shadow-md hover:shadow-lg transform hover:scale-105 transition-all duration-200"
                        title="Remove parameter"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <button 
                  onClick={executeEndpoint} 
                  disabled={loading || !selectedEndpoint}
                  className="w-full px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white font-medium rounded-lg shadow-lg hover:from-green-600 hover:to-green-700 hover:shadow-xl disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
                >
                  {loading ? (
                    <div className="flex items-center justify-center space-x-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Executing...</span>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center space-x-2">
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                        <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd"/>
                      </svg>
                      <span>Execute Endpoint</span>
                    </div>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Save Test Configuration */}
        {selectedEndpoint && (
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-3">4. Save Test Configuration</h4>
            <div className="flex space-x-2">
              <input
                type="text"
                placeholder="Enter test name..."
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                className="flex-1 p-2 border rounded"
              />
              <button 
                onClick={saveTest} 
                disabled={loading || !selectedEndpoint}
                className="px-6 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium rounded-lg shadow-md hover:from-blue-600 hover:to-blue-700 hover:shadow-lg disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M7.707 10.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V6a1 1 0 10-2 0v5.586l-1.293-1.293z"/>
                    <path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v1a1 1 0 11-2 0V4H7v1a1 1 0 11-2 0V4z"/>
                  </svg>
                  <span>Save Test</span>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* Response */}
        {response && (
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-3">3. Response</h4>
            <div className="text-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">Status:</span>
                <span className={`px-2 py-1 rounded text-xs ${
                  response.status === 200 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}>
                  {response.status}
                </span>
              </div>
              <pre className="bg-gray-50 p-3 rounded text-xs font-mono overflow-x-auto">
                {JSON.stringify(response.data, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* Saved Tests */}
      {savedTests.length > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">Saved Test Configurations</h4>
          <div className="space-y-2">
            {savedTests.map((test) => (
              <div key={test.id} className="flex items-center justify-between p-3 border rounded">
                <div>
                  <div className="font-medium">{test.name}</div>
                  <div className="text-sm text-gray-600">
                    {test.method} {test.endpoint_path} ({test.parameters.length} params, {test.request_type}) - {new Date(test.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <button 
                    onClick={() => loadTest(test)}
                    className="inline-flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 text-white text-sm font-medium rounded-lg shadow-md hover:from-indigo-600 hover:to-indigo-700 hover:shadow-lg transform hover:scale-105 transition-all duration-200"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd"/>
                    </svg>
                    <span>Load</span>
                  </button>
                  <button 
                    onClick={() => deleteTest(test.id)}
                    className="inline-flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white text-sm font-medium rounded-lg shadow-md hover:from-red-600 hover:to-red-700 hover:shadow-lg transform hover:scale-105 transition-all duration-200"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" clipRule="evenodd"/>
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
                    </svg>
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default McpClientTestTab;
