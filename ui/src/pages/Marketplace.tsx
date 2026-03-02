import React, { useEffect, useState } from "react";
import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import { toast } from "sonner";

export default function Marketplace() {
  const { token } = useAuth();
  const [agents, setAgents] = useState<any[]>([]);
  const [mcpServers, setMcpServers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [agentsRes, serversRes] = await Promise.all([
          fetch('/api/marketplace/agents', {
            headers: { Authorization: `Bearer ${token}` }
          }),
          fetch('/api/marketplace/mcp-servers', {
            headers: { Authorization: `Bearer ${token}` }
          })
        ]);
        
        if (agentsRes.ok) setAgents(await agentsRes.json());
        if (serversRes.ok) setMcpServers(await serversRes.json());
      } catch (error) {
        console.error("Failed to fetch marketplace data", error);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      fetchData();
    }
  }, [token]);

  const handleAction = async (itemType: string, itemId: number, action: string) => {
    try {
      const res = await fetch('/api/marketplace/usage', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ item_type: itemType, item_id: itemId, action })
      });
      
      if (res.ok) {
        toast.success(`Successfully ${action}ed item!`);
      } else {
        toast.error(`Failed to ${action} item.`);
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold gradient-text mb-2">Marketplace</h1>
        <p className="text-muted-foreground">
          Discover and install Agents and MCP Servers
        </p>
      </div>

      <ThemedTabs defaultValue="agents" className="w-full">
        <ThemedTabsList className="grid w-full grid-cols-2">
          <ThemedTabsTrigger value="agents">Agents</ThemedTabsTrigger>
          <ThemedTabsTrigger value="mcp-servers">MCP Servers</ThemedTabsTrigger>
        </ThemedTabsList>

        <ThemedTabsContent value="agents">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
            {loading ? <p>Loading...</p> : agents.length === 0 ? <p>No agents available.</p> : agents.map(agent => (
              <Card key={agent.id}>
                <CardHeader>
                  <CardTitle>{agent.name}</CardTitle>
                  <CardDescription>v{agent.version} by {agent.author}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p>{agent.description}</p>
                </CardContent>
                <CardFooter>
                  <Button onClick={() => handleAction('agent', agent.id, 'install')}>Install</Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </ThemedTabsContent>

        <ThemedTabsContent value="mcp-servers">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
            {loading ? <p>Loading...</p> : mcpServers.length === 0 ? <p>No MCP servers available.</p> : mcpServers.map(server => (
              <Card key={server.id}>
                <CardHeader>
                  <CardTitle>{server.name}</CardTitle>
                  <CardDescription>v{server.version} by {server.author}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p>{server.description}</p>
                </CardContent>
                <CardFooter>
                  <Button onClick={() => handleAction('mcp_server', server.id, 'install')}>Install</Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </ThemedTabsContent>
      </ThemedTabs>
    </div>
  );
}
