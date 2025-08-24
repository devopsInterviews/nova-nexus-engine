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
      
      setGroupedEndpoints(filtered);
    }
  }, [endpoints, filterText, methodFilter]);

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
      acc[p.key] = p.value;
      return acc;
    }, {} as Record<string, any>);

    try {
      let res;
      const url = endpointDetails.path;
      const options: RequestInit = {
        method: endpointDetails.method,
        headers: {
          "Content-Type": "application/json",
        },
      };

      if (endpointDetails.method === 'POST') {
        options.body = JSON.stringify(params);
        res = await fetch(url, options);
      } else { // Assuming GET
        const query = new URLSearchParams(params).toString();
        res = await fetch(`${url}?${query}`, options);
      }
      
      const data = await res.json();
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
        <div className="flex items-center space-x-1">
          <button onClick={() => setMethodFilter('ALL')} className={`px-3 py-1 rounded text-sm ${methodFilter === 'ALL' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}>ALL</button>
          <button onClick={() => setMethodFilter('GET')} className={`px-3 py-1 rounded text-sm ${methodFilter === 'GET' ? 'bg-green-500 text-white' : 'bg-gray-200'}`}>GET</button>
          <button onClick={() => setMethodFilter('POST')} className={`px-3 py-1 rounded text-sm ${methodFilter === 'POST' ? 'bg-yellow-500 text-white' : 'bg-gray-200'}`}>POST</button>
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
                  disabled={endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.method === 'GET'}
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
                <strong>Final URL:</strong> /api{endpoints.find(e => `${e.method} ${e.path}` === selectedEndpoint)?.path}
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
                value={requestParameters.length > 0 ? `${requestParameters[0].value} - ${new Date().toISOString()}` : ""}
                readOnly
                className="flex-1 p-2 border rounded"
              />
              <button 
                onClick={saveTest} 
                disabled={loading || !selectedEndpoint}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
              >
                💾 Save Test
              </button>
            </div>
          </div>
        )}

        {/* Response */}
        {response && (
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-3">Response</h4>
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
