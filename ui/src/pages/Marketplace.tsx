import React, { useEffect, useState } from "react";
import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { useAuth } from "@/context/auth-context";
import { toast } from "sonner";
import { Users, Activity, Trash2, Github, ExternalLink, Blocks, Calendar, Plus } from "lucide-react";

export default function Marketplace() {
  const { token, user } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    item_type: "agent",
    icon: "",
    bitbucket_repo: "",
    how_to_use: "",
    url_to_connect: ""
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/marketplace/items', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setItems(await res.json());
      }
    } catch (error) {
      console.error("Failed to fetch marketplace data", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchData();
    }
  }, [token]);

  const handleAction = async (itemId: number, action: string) => {
    try {
      const res = await fetch('/api/marketplace/usage', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ item_id: itemId, action })
      });
      
      if (res.ok) {
        toast.success(`Successfully recorded action: ${action}`);
        fetchData(); // Refresh usage stats
      } else {
        toast.error(`Failed to record action.`);
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/marketplace/items', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      });
      
      if (res.ok) {
        toast.success(`Successfully created ${formData.item_type}!`);
        setIsCreateOpen(false);
        setFormData({
          name: "", description: "", item_type: "agent", icon: "",
          bitbucket_repo: "", how_to_use: "", url_to_connect: ""
        });
        fetchData();
      } else {
        toast.error("Failed to create item.");
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  const handleDelete = async (itemId: number) => {
    if (!confirm("Are you sure you want to delete this item?")) return;
    try {
      const res = await fetch(`/api/marketplace/items/${itemId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        toast.success("Item deleted.");
        fetchData();
      } else {
        toast.error("Failed to delete item.");
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  const agents = items.filter(i => i.item_type === 'agent');
  const mcpServers = items.filter(i => i.item_type === 'mcp_server');

  const ItemCard = ({ item }: { item: any }) => {
    const isOwnerOrAdmin = user?.is_admin || user?.id === item.owner_id;

    return (
      <Dialog>
        <DialogTrigger asChild>
          <Card className="cursor-pointer hover:border-primary transition-colors flex flex-col h-full relative overflow-hidden group bg-surface/50 border-surface-elevated">
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {item.icon ? (
                    <img src={item.icon} alt="icon" className="w-10 h-10 rounded-md object-cover" />
                  ) : (
                    <div className="w-10 h-10 rounded-md bg-primary/10 flex items-center justify-center text-primary">
                      {item.item_type === 'agent' ? <Activity size={20} /> : <Blocks size={20} />}
                    </div>
                  )}
                  <div>
                    <CardTitle className="text-lg">{item.name}</CardTitle>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                      By <span className="font-medium text-foreground/70">{item.owner_name}</span>
                    </p>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1">
              <p className="text-sm text-muted-foreground line-clamp-3">
                {item.description}
              </p>
            </CardContent>
            <CardFooter className="pt-0 border-t border-border/50 bg-muted/20 py-3 mt-auto flex items-center justify-between">
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5" title="Total Calls">
                  <Activity size={14} className="text-primary/70" />
                  <span className="font-medium">{item.usage_count}</span> calls
                </span>
                <span className="flex items-center gap-1.5" title="Unique Users">
                  <Users size={14} className="text-success/70" />
                  <span className="font-medium">{item.unique_users}</span> users
                </span>
              </div>
            </CardFooter>
          </Card>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <div className="flex items-center gap-3 mb-2">
              {item.icon ? (
                <img src={item.icon} alt="icon" className="w-12 h-12 rounded-lg object-cover" />
              ) : (
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  {item.item_type === 'agent' ? <Activity size={24} /> : <Blocks size={24} />}
                </div>
              )}
              <div>
                <DialogTitle className="text-2xl">{item.name}</DialogTitle>
                <DialogDescription>
                  Owner: {item.owner_name} • Status: {item.deployment_status}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <h4 className="font-medium mb-1 flex items-center gap-2"><Blocks size={16}/> Description</h4>
              <p className="text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">{item.description}</p>
            </div>

            {item.how_to_use && (
              <div>
                <h4 className="font-medium mb-1">How to Use</h4>
                <p className="text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">{item.how_to_use}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              {item.bitbucket_repo && (
                <div className="bg-muted/30 p-3 rounded-md flex items-center gap-2">
                  <Github size={16} className="text-muted-foreground"/>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground">Repository</span>
                    <a href={item.bitbucket_repo} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate">
                      View Source
                    </a>
                  </div>
                </div>
              )}
              
              {item.url_to_connect && (
                <div className="bg-muted/30 p-3 rounded-md flex items-center gap-2">
                  <ExternalLink size={16} className="text-muted-foreground"/>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground">Connection URL</span>
                    <a href={item.url_to_connect} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate">
                      {item.url_to_connect}
                    </a>
                  </div>
                </div>
              )}
              
              <div className="bg-muted/30 p-3 rounded-md flex items-center gap-2">
                <Calendar size={16} className="text-muted-foreground"/>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">Created At</span>
                  <span className="text-sm truncate">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
            
            <div className="flex gap-4 pt-4 border-t">
               <div className="flex flex-col items-center">
                 <span className="text-2xl font-bold text-primary">{item.usage_count}</span>
                 <span className="text-xs text-muted-foreground">Total Calls</span>
               </div>
               <div className="flex flex-col items-center">
                 <span className="text-2xl font-bold text-success">{item.unique_users}</span>
                 <span className="text-xs text-muted-foreground">Unique Users</span>
               </div>
            </div>
          </div>

          <DialogFooter className="flex justify-between items-center sm:justify-between w-full">
            <div>
              {isOwnerOrAdmin && (
                <Button variant="destructive" size="sm" onClick={() => handleDelete(item.id)}>
                  <Trash2 className="w-4 h-4 mr-2" /> Delete
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => handleAction(item.id, 'install')}>Install</Button>
              <Button onClick={() => handleAction(item.id, 'call')}>Call / Run</Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text mb-2">Marketplace</h1>
          <p className="text-muted-foreground">
            Discover, build, and deploy Agents and MCP Servers to share with the team.
          </p>
        </div>
        
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
              <Plus className="w-4 h-4 mr-2" /> Create New
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Create New Entity</DialogTitle>
              <DialogDescription>
                Build and deploy a new Agent or MCP Server. Infrastructure will handle the CI/CD deployment.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label>Type</Label>
                <select 
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                  value={formData.item_type}
                  onChange={(e) => setFormData({...formData, item_type: e.target.value})}
                >
                  <option value="agent">Agent</option>
                  <option value="mcp_server">MCP Server</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input required value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="E.g. Data Analysis Agent" />
              </div>
              
              <div className="space-y-2">
                <Label>Description *</Label>
                <Textarea required value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="What does it do?" />
              </div>
              
              <div className="space-y-2">
                <Label>Bitbucket Repo URL</Label>
                <Input value={formData.bitbucket_repo} onChange={e => setFormData({...formData, bitbucket_repo: e.target.value})} placeholder="https://bitbucket.org/..." />
              </div>

              <div className="space-y-2">
                <Label>Connection URL (Optional)</Label>
                <Input value={formData.url_to_connect} onChange={e => setFormData({...formData, url_to_connect: e.target.value})} placeholder="http://..." />
              </div>

              <div className="space-y-2">
                <Label>How to Use</Label>
                <Textarea value={formData.how_to_use} onChange={e => setFormData({...formData, how_to_use: e.target.value})} placeholder="Instructions..." />
              </div>
              
              <DialogFooter className="mt-6">
                <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                <Button type="submit">Create</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <ThemedTabs defaultValue="agents" className="w-full">
        <ThemedTabsList className="grid w-full grid-cols-3 max-w-md">
          <ThemedTabsTrigger value="agents">Agents</ThemedTabsTrigger>
          <ThemedTabsTrigger value="mcp-servers">MCP Servers</ThemedTabsTrigger>
          <ThemedTabsTrigger value="skills">Skills</ThemedTabsTrigger>
        </ThemedTabsList>

        <div className="mt-8">
          <ThemedTabsContent value="agents">
            {loading ? (
              <p className="text-muted-foreground text-center py-12">Loading agents...</p>
            ) : agents.length === 0 ? (
              <p className="text-muted-foreground text-center py-12">No agents found.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {agents.map(agent => (
                  <ItemCard key={agent.id} item={agent} />
                ))}
              </div>
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="mcp-servers">
            {loading ? (
              <p className="text-muted-foreground text-center py-12">Loading MCP servers...</p>
            ) : mcpServers.length === 0 ? (
              <p className="text-muted-foreground text-center py-12">No MCP servers found.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {mcpServers.map(server => (
                  <ItemCard key={server.id} item={server} />
                ))}
              </div>
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="skills">
            <div className="flex flex-col items-center justify-center py-24 text-center border rounded-xl border-dashed border-border/60 bg-muted/10">
              <Blocks size={48} className="text-muted-foreground/30 mb-4" />
              <h3 className="text-2xl font-semibold text-muted-foreground">Coming Soon</h3>
              <p className="text-muted-foreground/70 mt-2 max-w-md">
                Skills will allow you to compose capabilities from different agents and MCP servers. Stay tuned!
              </p>
            </div>
          </ThemedTabsContent>
        </div>
      </ThemedTabs>
    </div>
  );
}
