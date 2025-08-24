import { useState, useEffect } from "react";

interface ApiEndpoint {
  path: string;
  method: string;
  description: string;
  parameters?: string[];
  tags: string[];
}

interface RequestParameter {
  key: string;
  value: string;
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

const McpClientTestTab = () => {
  const [endpoints, setEndpoints] = useState<ApiEndpoint[]>([]);
  const [groupedEndpoints, setGroupedEndpoints] = useState<{ [key: string]: ApiEndpoint[] }>({});
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>("");
  const [requestParameters, setRequestParameters] = useState<RequestParameter[]>([]);
  const [requestType, setRequestType] = useState<'body' | 'query'>('body');
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [savedTests, setSavedTests] = useState<SavedEndpointTest[]>([]);
  const [testName, setTestName] = useState<string>("");

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
          key: param,
          value: ""
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
    setExecutionResult(null);
    setError("");
  }, [selectedEndpoint, endpoints]);

  const fetchEndpoints = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/mcp/api/endpoints");
      const data = await response.json();
      
      if (data.endpoints) {
        setEndpoints(data.endpoints);
        setGroupedEndpoints(data.grouped_endpoints || {});
      }
    } catch (err) {
      console.error("Failed to fetch endpoints:", err);
      setError("Failed to load API endpoints");
    } finally {
      setLoading(false);
    }
  };

  const addParameter = () => {
    setRequestParameters([...requestParameters, { key: "", value: "" }]);
  };

  const updateParameter = (index: number, field: 'key' | 'value', value: string) => {
    const updated = [...requestParameters];
    updated[index][field] = value;
    setRequestParameters(updated);
  };

  const removeParameter = (index: number) => {
    setRequestParameters(requestParameters.filter((_, i) => i !== index));
  };

  const executeEndpoint = async () => {
    if (!selectedEndpoint) {
      setError("Please select an endpoint");
      return;
    }

    const [method, path] = selectedEndpoint.split(' ', 2);
    
    try {
      setLoading(true);
      setError("");
      
      // Convert parameters to object
      const parameterObject: { [key: string]: string } = {};
      requestParameters.forEach(param => {
        if (param.key && param.value) {
          parameterObject[param.key] = param.value;
        }
      });

      let url = `/api${path}`;
      let options: RequestInit = {
        method: method,
        headers: {
          "Content-Type": "application/json",
        },
      };

      if (requestType === 'query' || method === 'GET') {
        // Add parameters as query string
        const queryParams = new URLSearchParams();
        Object.entries(parameterObject).forEach(([key, value]) => {
          queryParams.append(key, value);
        });
        if (queryParams.toString()) {
          url += `?${queryParams.toString()}`;
        }
      } else {
        // Add parameters as request body
        options.body = JSON.stringify(parameterObject);
      }

      const response = await fetch(url, options);
      const result = await response.json();
      
      // Create detailed result object
      const executionResult = {
        status: response.ok ? "success" : "error",
        status_code: response.status,
        method: method,
        url: url,
        request_type: requestType,
        parameters_sent: parameterObject,
        response: result,
        response_headers: Object.fromEntries(response.headers.entries()),
        timestamp: new Date().toISOString()
      };
      
      setExecutionResult(executionResult);
      
      if (!response.ok) {
        setError(`HTTP ${response.status}: ${result.error || result.detail || "Request failed"}`);
      }
    } catch (err) {
      console.error("Endpoint execution failed:", err);
      setError("Failed to execute endpoint");
      const errorResult = {
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
        method: method,
        url: `/api${path}`,
        parameters_sent: {},
        timestamp: new Date().toISOString()
      };
      setExecutionResult(errorResult);
    } finally {
      setLoading(false);
    }
  };

  const saveTest = () => {
    if (!testName || !selectedEndpoint) {
      setError("Please provide a test name and select an endpoint");
      return;
    }

    const [method, path] = selectedEndpoint.split(' ', 2);
    const newTest: SavedEndpointTest = {
      id: Date.now().toString(),
      name: testName,
      endpoint_path: path,
      method: method,
      parameters: [...requestParameters],
      request_type: requestType,
      created_at: new Date().toISOString()
    };

    const updated = [...savedTests, newTest];
    setSavedTests(updated);
    localStorage.setItem("mcp-client-tests", JSON.stringify(updated));
    setTestName("");
    setError("");
  };

  const loadTest = (test: SavedEndpointTest) => {
    setSelectedEndpoint(`${test.method} ${test.endpoint_path}`);
    setRequestParameters([...test.parameters]);
    setRequestType(test.request_type);
    setExecutionResult(null);
    setError("");
  };

  const deleteTest = (testId: string) => {
    const updated = savedTests.filter(t => t.id !== testId);
    setSavedTests(updated);
    localStorage.setItem("mcp-client-tests", JSON.stringify(updated));
  };

  const selectedEndpointInfo = endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-2">FastAPI Client Testing</h3>
        <p className="text-sm text-muted-foreground">
          Test FastAPI endpoints by selecting an endpoint, providing parameters, and choosing request type.
          You can send data as request body (JSON) or query parameters.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Endpoint Selection */}
      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">1. Select API Endpoint</h4>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Available Endpoints ({endpoints.length} total)
            </label>
            <select 
              value={selectedEndpoint} 
              onChange={(e) => setSelectedEndpoint(e.target.value)}
              className="w-full p-2 border rounded"
            >
              <option value="">Choose an endpoint to test</option>
              {Object.entries(groupedEndpoints).map(([tag, taggedEndpoints]) => (
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

          {selectedEndpointInfo && (
            <div className="text-sm bg-gray-50 p-3 rounded">
              <p className="font-medium">Description:</p>
              <p className="text-gray-600 mb-2">{selectedEndpointInfo.description}</p>
              <div className="flex items-center space-x-4 mb-2">
                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                  selectedEndpointInfo.method === 'GET' ? 'bg-blue-100 text-blue-800' :
                  selectedEndpointInfo.method === 'POST' ? 'bg-green-100 text-green-800' :
                  selectedEndpointInfo.method === 'PUT' ? 'bg-yellow-100 text-yellow-800' :
                  selectedEndpointInfo.method === 'DELETE' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {selectedEndpointInfo.method}
                </span>
                <span className="text-sm text-gray-600">{selectedEndpointInfo.path}</span>
              </div>
              {selectedEndpointInfo.parameters && selectedEndpointInfo.parameters.length > 0 && (
                <div>
                  <p className="font-medium">Expected Parameters:</p>
                  <div className="text-xs text-gray-600">
                    {selectedEndpointInfo.parameters.join(", ")}
                  </div>
                </div>
              )}
              <div className="mt-2">
                <p className="font-medium">Tags:</p>
                <div className="space-x-1">
                  {selectedEndpointInfo.tags.map((tag) => (
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

      {/* Request Type Selection */}
      {selectedEndpoint && (
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">2. Request Type</h4>
          <div className="space-y-2">
            <label className="flex items-center space-x-2">
              <input
                type="radio"
                value="body"
                checked={requestType === 'body'}
                onChange={(e) => setRequestType(e.target.value as 'body' | 'query')}
                disabled={selectedEndpointInfo?.method === 'GET'}
              />
              <span>Request Body (JSON)</span>
              <span className="text-xs text-gray-500">- Send parameters as JSON in request body</span>
            </label>
            <label className="flex items-center space-x-2">
              <input
                type="radio"
                value="query"
                checked={requestType === 'query'}
                onChange={(e) => setRequestType(e.target.value as 'body' | 'query')}
              />
              <span>Query Parameters</span>
              <span className="text-xs text-gray-500">- Send parameters in URL query string</span>
            </label>
          </div>
        </div>
      )}

      {/* Parameter Configuration */}
      {selectedEndpoint && (
        <div className="border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium">3. Configure Parameters</h4>
            <button
              onClick={addParameter}
              className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
            >
              + Add Parameter
            </button>
          </div>
          <div className="space-y-4">
            <div className="text-xs text-gray-600 bg-blue-50 p-2 rounded">
              <strong>Request Type:</strong> {requestType === 'body' ? 'JSON Body' : 'URL Query Parameters'}
              <br />
              <strong>Final URL:</strong> /api{selectedEndpointInfo?.path}
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
                      value={param.key}
                      onChange={(e) => updateParameter(index, 'key', e.target.value)}
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
                      className="px-2 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div>
              <button 
                onClick={executeEndpoint} 
                disabled={loading || !selectedEndpoint}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300"
              >
                {loading ? "Executing..." : "🚀 Execute Endpoint"}
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
              placeholder="Test configuration name"
              value={testName}
              onChange={(e) => setTestName(e.target.value)}
              className="flex-1 p-2 border rounded"
            />
            <button 
              onClick={saveTest} 
              disabled={!testName}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
            >
              💾 Save Test
            </button>
          </div>
        </div>
      )}

      {/* Execution Results */}
      {executionResult && (
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">Execution Results</h4>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center space-x-2">
                <span className="font-medium">Status:</span>
                <span className={`inline-block px-2 py-1 rounded text-xs ${
                  executionResult.status === "success" ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}>
                  {executionResult.status} {executionResult.status_code && `(${executionResult.status_code})`}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="font-medium">Method:</span>
                <span className="text-gray-600">{executionResult.method}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="font-medium">URL:</span>
                <span className="text-gray-600 text-xs">{executionResult.url}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="font-medium">Request Type:</span>
                <span className="text-gray-600">{executionResult.request_type}</span>
              </div>
            </div>
            
            {executionResult.parameters_sent && Object.keys(executionResult.parameters_sent).length > 0 && (
              <div>
                <label className="block text-sm font-medium mb-2">Parameters Sent:</label>
                <textarea
                  value={JSON.stringify(executionResult.parameters_sent, null, 2)}
                  readOnly
                  className="w-full p-2 border rounded font-mono text-xs"
                  rows={4}
                />
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium mb-2">Response:</label>
              <textarea
                value={JSON.stringify(executionResult.response, null, 2)}
                readOnly
                className="w-full p-3 border rounded font-mono text-xs"
                rows={12}
              />
            </div>
          </div>
        </div>
      )}

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
                <div className="space-x-2">
                  <button 
                    onClick={() => loadTest(test)}
                    className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
                  >
                    Load
                  </button>
                  <button 
                    onClick={() => deleteTest(test.id)}
                    className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
                  >
                    Delete
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
