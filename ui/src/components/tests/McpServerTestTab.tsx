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
  key: string;
  value: string;
}

interface SavedTest {
  id: string;
  name: string;
  server_id: string;
  tool_name: string;
  parameters: ToolParameter[];
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

  // Load saved tests from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("mcp-server-tests");
    if (saved) {
      try {
        setSavedTests(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to load saved tests:", e);
      }
    }
  }, []);

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
            key: p.name,
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
      const response = await fetch("/api/mcp/servers");
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
      const response = await fetch(`/api/mcp/servers/${serverId}/tools`);
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
    setToolParameters([...toolParameters, { key: "", value: "" }]);
  };

  const updateParameter = (index: number, field: 'key' | 'value', value: string) => {
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
        if (param.key && param.value) {
          parameterObject[param.key] = param.value;
        }
      });

      const response = await fetch(`/api/mcp/servers/${selectedServer}/tools/${selectedTool}/execute`, {
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

  const saveTest = () => {
    if (!testName || !selectedServer || !selectedTool) {
      return;
    }

    const newTest: SavedTest = {
      id: Date.now().toString(),
      name: testName,
      server_id: selectedServer,
      tool_name: selectedTool,
      parameters: [...toolParameters],
      created_at: new Date().toISOString()
    };

    const updated = [...savedTests, newTest];
    setSavedTests(updated);
    localStorage.setItem("mcp-server-tests", JSON.stringify(updated));
    setTestName("");
  };

  const loadTest = (test: SavedTest) => {
    setSelectedServer(test.server_id);
    setSelectedTool(test.tool_name);
    setToolParameters([...test.parameters]);
    setResponse(null);
  };

  const deleteTest = (testId: string) => {
    const updated = savedTests.filter(t => t.id !== testId);
    setSavedTests(updated);
    localStorage.setItem("mcp-server-tests", JSON.stringify(updated));
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

      <input
        type="text"
        placeholder="Filter tools..."
        value={filterText}
        onChange={(e) => setFilterText(e.target.value)}
        className="w-full p-2 border rounded mb-4"
      />

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
                  Available Tools ({tools.length})
                </label>
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
                onClick={executeTool} 
                disabled={loading || !selectedTool}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-300"
              >
                {loading ? "Executing..." : "▶ Execute Tool"}
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
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
            >
              💾 Save Test
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

export default McpServerTestTab;
