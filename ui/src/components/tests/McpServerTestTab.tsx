import { useState, useEffect } from "react";

interface McpServer {
  id: string;
  name: string;
  url?: string;
  status: string;
  tool_count: number;
  capabilities: {
    tools: boolean;
    resources: boolean;
    prompts: boolean;
  };
  connection_time?: number;
}

interface McpTool {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    default?: string;
    enum?: string[];
  }>;
  parameter_count: number;
  required_params: number;
}

interface ToolParameter {
  name: string;  // Changed from key to name to match backend
  value: string;
}

interface SavedTest {
  id: number;  // Changed from string to number to match DB
  name: string;
  server_id: string;
  tool_name: string;
  parameters: ToolParameter[];
  test_category: string;
  endpoint_path: string;
  method: string;
  request_type: string;
  created_at: string;
}

export const McpServerTestTab = () => {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [selectedServer, setSelectedServer] = useState<string>("");
  const [tools, setTools] = useState<McpTool[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>("");
  const [toolParameters, setToolParameters] = useState<ToolParameter[]>([]);
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [savedTests, setSavedTests] = useState<SavedTest[]>([]);
  const [testName, setTestName] = useState<string>("");
  const [filterText, setFilterText] = useState("");
  const [authToken, setAuthToken] = useState<string | null>(null);

  // Load auth token and fetch saved tests
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    setAuthToken(token);
    if (token) {
      fetchSavedTests(token);
      // Migrate old localStorage tests to database
      migrateLocalStorageTests(token);
    }
  }, []);

  // Migrate existing localStorage tests to database (one-time migration)
  const migrateLocalStorageTests = async (token: string) => {
    const oldTests = localStorage.getItem("mcp-server-tests");
    if (!oldTests) return;

    try {
      const parsedTests = JSON.parse(oldTests);
      console.log(`Migrating ${parsedTests.length} MCP server tests from localStorage to database...`);
      
      for (const oldTest of parsedTests) {
        // Convert old format to new format
        const testToSave = {
          name: oldTest.name,
          endpoint_path: `/servers/${oldTest.server_id}/tools/${oldTest.tool_name}/execute`,
          method: "POST",
          parameters: oldTest.parameters.map((p: any) => ({
            name: p.key || p.name,  // Handle both old and new formats
            value: p.value
          })),
          request_type: "body",
          test_category: "server",
          server_id: oldTest.server_id,
          tool_name: oldTest.tool_name,
        };

        try {
          const response = await fetch('/api/tests', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(testToSave),
          });

          if (!response.ok) {
            console.error(`Failed to migrate test ${oldTest.name}:`, await response.text());
          }
        } catch (error) {
          console.error(`Error migrating test ${oldTest.name}:`, error);
        }
      }

      // Remove old localStorage data after successful migration
      localStorage.removeItem("mcp-server-tests");
      console.log("Migration completed and localStorage cleared");
      
      // Refresh the saved tests list
      fetchSavedTests(token);
    } catch (e) {
      console.error("Failed to migrate localStorage tests:", e);
    }
  };

  // Load saved tests from the backend API
  const fetchSavedTests = async (token: string) => {
    if (!token) return;
    try {
      const response = await fetch("/api/tests?test_category=server", {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setSavedTests(data);
      } else {
        console.error("Failed to fetch saved tests:", response.statusText);
      }
    } catch (e) {
      console.error("Failed to load saved tests:", e);
    }
  };

  // Fetch available MCP servers on component mount
  useEffect(() => {
    fetchServers();
  }, []);

  // Fetch tools when server is selected
  useEffect(() => {
    if (selectedServer) {
      fetchTools(selectedServer);
    } else {
      setTools([]);
      setSelectedTool("");
    }
  }, [selectedServer]);

  // Reset parameters when tool is selected
  useEffect(() => {
    if (selectedTool) {
      const tool = tools.find(t => t.name === selectedTool);
      if (tool) {
        // Initialize parameters with required ones
        const initialParams: ToolParameter[] = tool.parameters
          .filter(p => p.required)
          .map(p => ({
            name: p.name,  // Changed from key to name
            value: p.default || ""
          }));
        setToolParameters(initialParams);
      }
    } else {
      setToolParameters([]);
    }
    setResponse(null);
  }, [selectedTool, tools]);

  // Filtered tools based on the search text
  const filteredTools = tools.filter(tool => 
    tool.name.toLowerCase().includes(filterText.toLowerCase())
  );

  const fetchServers = async () => {
    try {
      setLoading(true);
      // Backend mcp_router is mounted at /api, so servers endpoint is /api/servers
      const response = await fetch("/api/servers");
      const data = await response.json();
      
      if (data.servers) {
        setServers(data.servers);
        if (data.servers.length > 0) {
          setSelectedServer(data.servers[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch servers:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTools = async (serverId: string) => {
    try {
      setLoading(true);
      // Backend mcp_router is mounted at /api, so tools endpoint is /api/servers/{serverId}/tools
      const response = await fetch(`/api/servers/${serverId}/tools`);
      const data = await response.json();
      
      if (data.tools) {
        setTools(data.tools);
      }
    } catch (err) {
      console.error("Failed to fetch tools:", err);
    } finally {
      setLoading(false);
    }
  };

  const addParameter = () => {
    setToolParameters([...toolParameters, { name: "", value: "" }]);  // Changed from key to name
  };

  const updateParameter = (index: number, field: 'name' | 'value', value: string) => {  // Changed from key to name
    const updated = [...toolParameters];
    updated[index][field] = value;
    setToolParameters(updated);
  };

  const removeParameter = (index: number) => {
    setToolParameters(toolParameters.filter((_, i) => i !== index));
  };

  const executeTool = async () => {
    if (!selectedServer || !selectedTool) {
      return;
    }

    try {
      setLoading(true);
      
      // Convert parameters to object
      const parameterObject: { [key: string]: string } = {};
      toolParameters.forEach(param => {
        if (param.name && param.value) {  // Changed from key to name
          parameterObject[param.name] = param.value;
        }
      });

      const response = await fetch(`/api/servers/${selectedServer}/tools/${selectedTool}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          parameters: parameterObject
        }),
      });

      const result = await response.json();
      setResponse(result);
      
      if (!response.ok) {
        console.error(result.error || "Tool execution failed");
      }
    } catch (err) {
      console.error("Tool execution failed:", err);
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const saveTest = async () => {
    if (!testName || !selectedServer || !selectedTool || !authToken) {
      return;
    }

    const testToSave = {
      name: testName,
      endpoint_path: `/servers/${selectedServer}/tools/${selectedTool}/execute`,  // Mock endpoint path
      method: "POST",
      parameters: toolParameters,
      request_type: "body",
      test_category: "server",
      server_id: selectedServer,
      tool_name: selectedTool,
    };

    try {
      const response = await fetch('/api/tests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(testToSave),
      });

      if (response.ok) {
        const newTest = await response.json();
        setSavedTests([...savedTests, newTest]);
        setTestName("");
      } else {
        console.error("Failed to save test:", await response.text());
      }
    } catch (error) {
      console.error("Error saving test:", error);
    }
  };

  const loadTest = async (test: SavedTest) => {
    setResponse(null);
    
    // First set the server
    setSelectedServer(test.server_id);
    
    // Fetch tools for this server if not already loaded
    if (selectedServer !== test.server_id) {
      try {
        const response = await fetch(`/api/servers/${test.server_id}/tools`);
        const data = await response.json();
        if (data.tools) {
          setTools(data.tools);
        }
      } catch (error) {
        console.error("Error fetching tools for loaded test:", error);
      }
    }
    
    // Then set the tool
    setSelectedTool(test.tool_name);
    
    // Finally set the parameters with their values
    setToolParameters([...test.parameters]);
  };

  const deleteTest = async (testId: number) => {
    if (!authToken) return;
    try {
      const response = await fetch(`/api/tests/${testId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const updatedTests = savedTests.filter(t => t.id !== testId);
        setSavedTests(updatedTests);
      } else {
        console.error("Failed to delete test:", await response.text());
      }
    } catch (error) {
      console.error("Error deleting test:", error);
    }
  };

  const selectedToolInfo = tools.find(t => t.name === selectedTool);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-2">MCP Server Testing</h3>
        <p className="text-sm text-muted-foreground">
          Test MCP server tools with interactive interfaces
        </p>
      </div>

      {/* Server and Tool Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Server Selection */}
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">1. Select MCP Server</h4>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Available Servers</label>
              <select 
                value={selectedServer} 
                onChange={(e) => setSelectedServer(e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="">Choose an MCP server</option>
                {servers.map((server) => (
                  <option key={server.id} value={server.id}>
                    {server.name} ({server.status}) - {server.tool_count} tools
                  </option>
                ))}
              </select>
            </div>

            {selectedServer && (
              <div className="text-sm text-gray-600">
                {(() => {
                  const server = servers.find(s => s.id === selectedServer);
                  return server ? (
                    <div>
                      <p>Tools available: {server.tool_count}</p>
                      <p>Capabilities: {Object.entries(server.capabilities)
                        .filter(([_, enabled]) => enabled)
                        .map(([name, _]) => name)
                        .join(", ")}</p>
                      {server.connection_time && (
                        <p>Connection time: {server.connection_time.toFixed(2)}s</p>
                      )}
                    </div>
                  ) : null;
                })()}
              </div>
            )}
          </div>
        </div>

        {/* Tool Selection */}
        {tools.length > 0 && (
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-3">2. Select Tool</h4>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Available Tools ({filteredTools.length})
                </label>
                <input
                  type="text"
                  placeholder="Type to filter tools..."
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="w-full p-2 border rounded mb-2 text-sm"
                />
                <select 
                  value={selectedTool} 
                  onChange={(e) => setSelectedTool(e.target.value)}
                  className="w-full p-2 border rounded"
                >
                  <option value="">Choose a tool to test</option>
                  {filteredTools.map((tool) => (
                    <option key={tool.name} value={tool.name}>
                      {tool.name} ({tool.parameter_count} params, {tool.required_params} required)
                    </option>
                  ))}
                </select>
              </div>

              {selectedToolInfo && (
                <div className="text-sm bg-gray-50 p-3 rounded">
                  <p className="font-medium">Description:</p>
                  <p className="text-gray-600 mb-2">{selectedToolInfo.description}</p>
                  <div>
                    <p className="font-medium">Parameters:</p>
                    <div className="space-y-1">
                      {selectedToolInfo.parameters.map((param) => (
                        <div key={param.name} className="text-xs">
                          <span className={`inline-block px-2 py-1 rounded text-xs mr-2 ${
                            param.required ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {param.name}
                          </span>
                          <span className="text-gray-600">
                            {param.type} - {param.description}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Parameter Configuration */}
      {selectedTool && (
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
            {toolParameters.length === 0 ? (
              <p className="text-sm text-gray-600">
                No parameters configured. Click "Add Parameter" to add tool arguments.
              </p>
            ) : (
              <div className="space-y-3">
                {toolParameters.map((param, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <input
                      type="text"
                      placeholder="Parameter name"
                      value={param.name}  // Changed from key to name
                      onChange={(e) => updateParameter(index, 'name', e.target.value)}  // Changed from key to name
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
                onClick={executeTool} 
                disabled={loading || !selectedTool}
                className="w-full px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white font-medium rounded-lg shadow-lg hover:from-green-600 hover:to-green-700 hover:shadow-xl disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transform hover:scale-105 transition-all duration-200"
              >
                {loading ? (
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Executing...</span>
                  </div>
                ) : (
                  "Execute Tool"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save Test Configuration */}
      {selectedTool && (
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

      {/* Execution Results */}
      {response && (
        <div className="border rounded-lg p-4">
          <h4 className="font-medium mb-3">Execution Results</h4>
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <span className={`inline-block px-2 py-1 rounded text-xs ${
                response.status === "success" ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {response.status}
              </span>
              {response.execution_time && (
                <span className="text-sm text-gray-600">
                  Executed in {response.execution_time.toFixed(3)}s
                </span>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Response:</label>
              <textarea
                value={JSON.stringify(response, null, 2)}
                readOnly
                className="w-full p-3 border rounded font-mono text-xs"
                rows={15}
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
                    {test.tool_name} ({test.parameters.length} params) - {new Date(test.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={async () => await loadTest(test)}
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

export default McpServerTestTab;
