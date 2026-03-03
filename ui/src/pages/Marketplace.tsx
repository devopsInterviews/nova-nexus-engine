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
import { Users, Activity, Trash2, Github, ExternalLink, Blocks, Calendar, Plus, Rocket, Hammer, Cloud, Play } from "lucide-react";

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

  const handleBuild = async (itemId: number) => {
    try {
      const res = await fetch('/api/marketplace/build', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ item_id: itemId })
      });
      if (res.ok) {
        toast.success("Build triggered successfully!");
        fetchData();
      } else {
        toast.error("Failed to build item.");
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  const handleDeploy = async (itemId: number, environment: string) => {
    try {
      const res = await fetch('/api/marketplace/deploy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ item_id: itemId, environment })
      });
      if (res.ok) {
        toast.success(`Deployed successfully to ${environment}!`);
        fetchData();
      } else {
        toast.error("Failed to deploy item.");
      }
    } catch (error) {
      toast.error(`Error: ${error}`);
    }
  };

  const handleDelete = async (itemId: number) => {
    if (!confirm("Are you sure you want to delete this item? This will also undeploy it.")) return;
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

    let borderClass = "border-surface-elevated";
    if (item.deployment_status === "BUILT") borderClass = "border-yellow-500/50";
    if (item.deployment_status === "DEPLOYED") borderClass = "border-green-500/50";

    return (
      <Dialog>
        <DialogTrigger asChild>
          <Card className={`cursor-pointer hover:border-primary transition-all flex flex-col h-full relative overflow-hidden group bg-surface/50 border-2 ${borderClass} shadow-md hover:shadow-xl`}>
            {item.deployment_status === "BUILT" && (
              <div className="absolute top-0 right-0 left-0 h-1 bg-yellow-500" title="Ready to be deployed" />
            )}
            {item.deployment_status === "DEPLOYED" && (
              <div className="absolute top-0 right-0 left-0 h-1 bg-green-500" title="Deployed" />
            )}
            
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  {item.icon ? (
                    <img src={item.icon} alt="icon" className="w-14 h-14 rounded-xl object-cover border border-border" />
                  ) : (
                    <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
                      {item.item_type === 'agent' ? <Activity size={28} /> : <Blocks size={28} />}
                    </div>
                  )}
                  <div>
                    <CardTitle className="text-xl leading-tight">{item.name}</CardTitle>
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                      By <span className="font-medium text-foreground/70">{item.owner_name}</span>
                    </p>
                    <div className="flex gap-2 mt-1.5">
                       <span className="text-[10px] font-medium bg-muted px-1.5 py-0.5 rounded text-muted-foreground">v{item.version || '1.0.0'}</span>
                       <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${(item.environment || 'dev') === 'release' ? 'bg-blue-500/10 text-blue-500' : 'bg-orange-500/10 text-orange-500'}`}>
                         {(item.environment || 'dev').toUpperCase()}
                       </span>
                    </div>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 pt-2">
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
              <div className="text-xs font-medium px-2 py-1 rounded-full bg-background border">
                {item.deployment_status}
              </div>
            </CardFooter>
          </Card>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4 mb-2">
                {item.icon ? (
                  <img src={item.icon} alt="icon" className="w-16 h-16 rounded-xl object-cover shadow-sm border border-border" />
                ) : (
                  <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center text-primary shadow-sm border border-primary/20">
                    {item.item_type === 'agent' ? <Activity size={32} /> : <Blocks size={32} />}
                  </div>
                )}
                <div>
                  <DialogTitle className="text-2xl font-bold">{item.name}</DialogTitle>
                  <DialogDescription className="mt-1 flex items-center gap-3">
                    <span>Owner: <strong>{item.owner_name}</strong></span>
                    <span>Status: <strong>{item.deployment_status}</strong></span>
                  </DialogDescription>
                </div>
              </div>
            </div>
          </DialogHeader>
          
          <div className="space-y-6 py-2">
            <div>
              <h4 className="font-medium mb-2 flex items-center gap-2"><Blocks size={16}/> Description</h4>
              <p className="text-sm text-muted-foreground bg-muted/30 p-4 rounded-lg border border-border/50">{item.description}</p>
            </div>

            {item.how_to_use && (
              <div>
                <h4 className="font-medium mb-2">How to Use</h4>
                <p className="text-sm text-muted-foreground bg-muted/30 p-4 rounded-lg border border-border/50">{item.how_to_use}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex flex-col gap-1">
                 <span className="text-xs text-muted-foreground">Version Info</span>
                 <span className="text-sm font-medium">Chart Version: {item.version || '1.0.0'}</span>
                 <span className="text-xs text-muted-foreground mt-1">
                   {(item.environment || 'dev') === 'dev' ? 'Dev environment (Auto-undeploys in 10 days)' : 'Release environment (Persistent)'}
                 </span>
              </div>

              {item.bitbucket_repo && (
                <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex items-center gap-3">
                  <Github size={20} className="text-muted-foreground"/>
                  <div className="flex flex-col overflow-hidden">
                    <span className="text-xs text-muted-foreground">Repository</span>
                    <a href={item.bitbucket_repo} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate">
                      View Source Code
                    </a>
                  </div>
                </div>
              )}
              
              {item.url_to_connect && (
                <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex items-center gap-3">
                  <ExternalLink size={20} className="text-muted-foreground"/>
                  <div className="flex flex-col overflow-hidden">
                    <span className="text-xs text-muted-foreground">Connection URL</span>
                    <a href={item.url_to_connect} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline truncate">
                      {item.url_to_connect}
                    </a>
                  </div>
                </div>
              )}
              
              <div className="bg-muted/30 p-3 rounded-lg border border-border/50 flex items-center gap-3">
                <Calendar size={20} className="text-muted-foreground"/>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">Created At</span>
                  <span className="text-sm truncate">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
            
            <div className="flex gap-8 pt-4 border-t px-2">
               <div className="flex flex-col items-center">
                 <span className="text-3xl font-bold text-primary">{item.usage_count}</span>
                 <span className="text-sm text-muted-foreground">Total Calls</span>
               </div>
               <div className="flex flex-col items-center">
                 <span className="text-3xl font-bold text-success">{item.unique_users}</span>
                 <span className="text-sm text-muted-foreground">Unique Users</span>
               </div>
            </div>
          </div>

          <DialogFooter className="flex flex-col sm:flex-row justify-between items-center sm:justify-between w-full pt-4 border-t gap-4">
            <div className="flex gap-2">
              {isOwnerOrAdmin && (
                <Button variant="destructive" onClick={() => handleDelete(item.id)}>
                  <Trash2 className="w-4 h-4 mr-2" /> Delete
                </Button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 justify-end">
              {isOwnerOrAdmin && item.deployment_status === "CREATED" && (
                <Button variant="outline" onClick={() => handleBuild(item.id)}>
                  <Hammer className="w-4 h-4 mr-2" /> Build CI/CD
                </Button>
              )}
              
              {isOwnerOrAdmin && (item.deployment_status === "BUILT" || item.deployment_status === "DEPLOYED") && (
                <>
                  <Button variant="outline" className="border-orange-500 text-orange-500 hover:bg-orange-500 hover:text-white" onClick={() => handleDeploy(item.id, 'dev')}>
                    <Cloud className="w-4 h-4 mr-2" /> Deploy (Dev)
                  </Button>
                  <Button variant="outline" className="border-blue-500 text-blue-500 hover:bg-blue-500 hover:text-white" onClick={() => handleDeploy(item.id, 'release')}>
                    <Rocket className="w-4 h-4 mr-2" /> Deploy (Release)
                  </Button>
                </>
              )}
              
              {item.deployment_status === "DEPLOYED" && (
                <Button className="bg-primary" onClick={() => handleAction(item.id, 'call')}>
                  <Play className="w-4 h-4 mr-2" /> Run / Call
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  };

  return (
    <div className="space-y-8 p-6 pb-12 w-full h-full flex flex-col">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold gradient-text mb-3">Marketplace</h1>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Discover, build, and deploy Agents and MCP Servers to share with the team. 
            Avoid tribal knowledge by publishing your tools here.
          </p>
        </div>
        
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button size="lg" className="bg-gradient-primary text-primary-foreground shadow-lg hover:shadow-xl transition-all">
              <Plus className="w-5 h-5 mr-2" /> Create Entity
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold">Create New Entity</DialogTitle>
              <DialogDescription className="text-base">
                Register a new Agent or MCP Server. After creation, you can Build and Deploy it via our Infrastructure APIs.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-6 mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label className="text-base font-medium">Type *</Label>
                  <select 
                    className="w-full rounded-md border border-input bg-background px-3 py-2.5 text-sm shadow-sm focus:ring-primary focus:border-primary"
                    value={formData.item_type}
                    onChange={(e) => setFormData({...formData, item_type: e.target.value})}
                  >
                    <option value="agent">Agent</option>
                    <option value="mcp_server">MCP Server</option>
                  </select>
                </div>
                
                <div className="space-y-2">
                  <Label className="text-base font-medium">Name *</Label>
                  <Input className="py-2.5" required value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="E.g. Data Analysis Agent" />
                </div>

                <div className="space-y-2 md:col-span-2">
                  <Label className="text-base font-medium">Description *</Label>
                  <Textarea className="min-h-[100px] py-2.5" required value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="What does it do? When should someone use it?" />
                </div>
                
                <div className="space-y-2">
                  <Label className="text-base font-medium">Icon URL (Optional)</Label>
                  <Input className="py-2.5" value={formData.icon} onChange={e => setFormData({...formData, icon: e.target.value})} placeholder="https://example.com/icon.png" />
                </div>

                <div className="space-y-2">
                  <Label className="text-base font-medium">Bitbucket Repo URL</Label>
                  <Input className="py-2.5" value={formData.bitbucket_repo} onChange={e => setFormData({...formData, bitbucket_repo: e.target.value})} placeholder="https://bitbucket.org/..." />
                </div>

                <div className="space-y-2 md:col-span-2">
                  <Label className="text-base font-medium">Connection URL (Optional)</Label>
                  <Input className="py-2.5" value={formData.url_to_connect} onChange={e => setFormData({...formData, url_to_connect: e.target.value})} placeholder="http://..." />
                </div>

                <div className="space-y-2 md:col-span-2">
                  <Label className="text-base font-medium">How to Use (Optional)</Label>
                  <Textarea className="min-h-[100px] py-2.5" value={formData.how_to_use} onChange={e => setFormData({...formData, how_to_use: e.target.value})} placeholder="Instructions, examples, prerequisites..." />
                </div>
              </div>
              
              <DialogFooter className="mt-8 border-t pt-6">
                <Button type="button" variant="outline" size="lg" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
                <Button type="submit" size="lg" className="bg-primary text-primary-foreground">Register Entity</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <ThemedTabs defaultValue="agents" className="w-full flex-1 flex flex-col">
        <ThemedTabsList className="grid w-full grid-cols-3">
          <ThemedTabsTrigger value="agents" className="text-base py-3">Agents</ThemedTabsTrigger>
          <ThemedTabsTrigger value="mcp-servers" className="text-base py-3">MCP Servers</ThemedTabsTrigger>
          <ThemedTabsTrigger value="skills" className="text-base py-3">Skills</ThemedTabsTrigger>
        </ThemedTabsList>

        <div className="mt-8 flex-1">
          <ThemedTabsContent value="agents" className="h-full">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground text-lg animate-pulse">Loading agents...</p>
              </div>
            ) : agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-xl bg-surface/30">
                 <Activity size={48} className="text-muted-foreground/30 mb-4" />
                 <p className="text-muted-foreground text-lg">No agents found.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 auto-rows-fr">
                {agents.map(agent => (
                  <ItemCard key={agent.id} item={agent} />
                ))}
              </div>
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="mcp-servers" className="h-full">
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground text-lg animate-pulse">Loading MCP servers...</p>
              </div>
            ) : mcpServers.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-xl bg-surface/30">
                 <Blocks size={48} className="text-muted-foreground/30 mb-4" />
                 <p className="text-muted-foreground text-lg">No MCP servers found.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 auto-rows-fr">
                {mcpServers.map(server => (
                  <ItemCard key={server.id} item={server} />
                ))}
              </div>
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="skills" className="h-full">
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] border-2 rounded-2xl border-dashed border-border/60 bg-gradient-to-b from-surface/50 to-background">
              <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mb-6 shadow-inner">
                <Blocks size={40} className="text-primary/70" />
              </div>
              <h3 className="text-3xl font-bold text-foreground mb-3">Coming Soon</h3>
              <p className="text-muted-foreground/80 text-lg max-w-lg text-center leading-relaxed">
                Skills will allow you to compose capabilities from different agents and MCP servers to tackle complex workflows autonomously.
              </p>
            </div>
          </ThemedTabsContent>
        </div>
      </ThemedTabs>
    </div>
  );
}
