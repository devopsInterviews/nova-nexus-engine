import React from "react";
import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { McpServerTestTab } from "../components/tests/McpServerTestTab";
import { McpClientTestTab } from "../components/tests/McpClientTestTab";

export default function Tests() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold gradient-text mb-2">MCP Testing Hub</h1>
        <p className="text-muted-foreground">
          Test MCP server tools and FastAPI client endpoints with interactive interfaces
        </p>
      </div>

      <div>
        <ThemedTabs defaultValue="mcp-server" className="w-full">
          <ThemedTabsList className="grid w-full grid-cols-2">
            <ThemedTabsTrigger value="mcp-server">MCP Server Tests</ThemedTabsTrigger>
            <ThemedTabsTrigger value="mcp-client">MCP Client Tests</ThemedTabsTrigger>
          </ThemedTabsList>

          <ThemedTabsContent value="mcp-server">
            <McpServerTestTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="mcp-client">
            <McpClientTestTab />
          </ThemedTabsContent>
        </ThemedTabs>
      </div>
    </div>
  );
}
