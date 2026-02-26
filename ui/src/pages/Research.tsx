/**
 * Research Page Component
 * 
 * This page allows users to configure and deploy their IDA MCP connection.
 * Users can register their workstation hostname, IDA port, and select an MCP version.
 * Once deployed, they receive an MCP URL to add in Open WebUI.
 * 
 * Layout:
 * - Left side: Configuration form with Deploy button
 * - Right side: Setup instructions
 * - Bottom: Deployed MCP Server details with Delete/Upgrade options
 */

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Search,
  Server,
  Plug,
  Copy,
  Check,
  RefreshCw,
  AlertCircle,
  Rocket,
  Trash2,
  ArrowUp,
  Info,
  ExternalLink,
  Clock,
  Network,
  GitBranch,
  Terminal,
  BookOpen
} from "lucide-react";
import { researchService, IdaBridgeConfig, IdaBridgeStatus, McpVersionsResponse } from "@/lib/api-service";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/context/auth-context";

/**
 * Status badge variant mapping based on deployment status
 */
const statusVariants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string; color: string }> = {
  NEW: { variant: "secondary", label: "Not Deployed", color: "" },
  DEPLOYING: { variant: "default", label: "Deploying...", color: "bg-yellow-500" },
  DEPLOYED: { variant: "default", label: "Running", color: "bg-green-500" },
  ERROR: { variant: "destructive", label: "Error", color: "" },
  UNDEPLOYED: { variant: "secondary", label: "Undeployed", color: "" },
  NOT_CONFIGURED: { variant: "outline", label: "Not Configured", color: "" },
};

export default function Research() {
  // Form state
  const [hostname, setHostname] = useState("");
  const [idaPort, setIdaPort] = useState<number | "">("");
  const [mcpVersion, setMcpVersion] = useState("");

  // API response state
  const [config, setConfig] = useState<IdaBridgeConfig | null>(null);
  const [status, setStatus] = useState<IdaBridgeStatus | null>(null);
  const [versions, setVersions] = useState<McpVersionsResponse | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dialog state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
  const [showChangelogDialog, setShowChangelogDialog] = useState(false);
  const [newVersionForUpgrade, setNewVersionForUpgrade] = useState("");
  const [versionSearch, setVersionSearch] = useState("");
  const [upgradeVersionSearch, setUpgradeVersionSearch] = useState("");
  const [isProvisioningMcp, setIsProvisioningMcp] = useState(false);

  const { toast } = useToast();
  const { user } = useAuth();

  /**
   * Load initial data: MCP versions, existing config, and status
   */
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Load MCP versions
      const versionsRes = await researchService.getMcpVersions();
      if (versionsRes.status === "success" && versionsRes.data) {
        setVersions(versionsRes.data);
        // Set default version if no version selected
        if (!mcpVersion && versionsRes.data.default_version) {
          setMcpVersion(versionsRes.data.default_version);
        }
      }

      // Load existing config
      const configRes = await researchService.getIdaBridgeConfig();
      if (configRes.status === "success" && configRes.data) {
        setConfig(configRes.data);
        // Populate form with existing values
        setHostname(configRes.data.hostname_fqdn || "");
        setIdaPort(configRes.data.ida_port || "");
        setMcpVersion(configRes.data.mcp_version || versions?.default_version || "");
      }

      // Load status
      const statusRes = await researchService.getIdaBridgeStatus();
      if (statusRes.status === "success" && statusRes.data) {
        setStatus(statusRes.data);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load data";
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [mcpVersion, toast]);

  useEffect(() => {
    loadData();
  }, []);

  /**
   * Deploy the MCP server - creates config and deploys in one step
   */
  const handleDeploy = async () => {
    // Validation
    if (!hostname.trim()) {
      toast({
        title: "Validation Error",
        description: "Hostname is required",
        variant: "destructive",
      });
      return;
    }

    if (!idaPort || Number(idaPort) < 1024 || Number(idaPort) > 65535) {
      toast({
        title: "Validation Error",
        description: "IDA port must be between 1024 and 65535",
        variant: "destructive",
      });
      return;
    }

    if (!mcpVersion) {
      toast({
        title: "Validation Error",
        description: "Please select an MCP version",
        variant: "destructive",
      });
      return;
    }

    setIsDeploying(true);
    setError(null);

    try {
      const result = await researchService.deployIdaBridge({
        hostname_fqdn: hostname.trim().toLowerCase(),
        ida_port: Number(idaPort),
        mcp_version: mcpVersion,
      });

      if (result.status === "success" && result.data) {
        toast({
          title: "Deployment Successful",
          description: result.data.message,
        });
        // Reload all data
        await loadData();
      } else {
        throw new Error(result.error || "Deployment failed");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Deployment failed";
      setError(errorMessage);
      toast({
        title: "Deployment Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsDeploying(false);
    }
  };

  /**
   * Delete the MCP server and config
   */
  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    setShowDeleteDialog(false);

    try {
      const result = await researchService.undeployIdaBridge();

      if (result.status === "success" && result.data) {
        setConfig(null);
        setStatus(null);
        // Clear form
        setHostname("");
        setIdaPort("");
        setMcpVersion(versions?.default_version || "");

        toast({
          title: "Deleted Successfully",
          description: "MCP server configuration has been removed.",
        });
        // Reload all data
        await loadData();
      } else {
        throw new Error(result.error || "Delete failed");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Delete failed";
      setError(errorMessage);
      toast({
        title: "Delete Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  /**
   * Upgrade MCP server to new version
   */
  const handleUpgrade = async () => {
    if (!newVersionForUpgrade || newVersionForUpgrade === config?.mcp_version) {
      toast({
        title: "Invalid Selection",
        description: "Please select a different version to upgrade to",
        variant: "destructive",
      });
      return;
    }

    setIsUpgrading(true);
    setError(null);
    setShowUpgradeDialog(false);

    try {
      const result = await researchService.upgradeIdaBridge(newVersionForUpgrade);

      if (result.status === "success" && result.data) {
        toast({
          title: "Upgrade Successful",
          description: result.data.message,
        });
        // Reload all data
        await loadData();
      } else {
        throw new Error(result.error || "Upgrade failed");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Upgrade failed";
      setError(errorMessage);
      toast({
        title: "Upgrade Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsUpgrading(false);
    }
  };

  /**
   * Provision MCP server in OpenWebUI using infrastructure API
   */
  const handleProvisionMcp = async () => {
    if (!status?.mcp_endpoint_url && !config?.mcp_endpoint_url) return;
    if (!versions?.infra_api_server || !versions?.mcp_nginx_dns || !user?.email) {
      toast({
        title: "Configuration Error",
        description: "Missing required configuration for MCP provisioning.",
        variant: "destructive",
      });
      return;
    }

    setIsProvisioningMcp(true);
    try {
      const response = await fetch(`http://${versions.infra_api_server}/add-mcp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: user.email,
          mcp_id: `ida-mcp-${user.id}-${config?.id || Date.now()}`,
          mcp_name: `IDA MCP - ${config?.hostname_fqdn || hostname}`,
          mcp_url: `${versions.mcp_nginx_dns}/mcp`,
          description: `Personal IDA MCP connection for ${user.username}`,
          auth_type: "none",
          key: ""
        })
      });

      if (!response.ok) throw new Error("Failed to provision MCP in OpenWebUI");

      toast({
        title: "Success",
        description: "MCP server provisioned in OpenWebUI.",
      });
    } catch (err) {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "Failed to provision MCP",
        variant: "destructive",
      });
    } finally {
      setIsProvisioningMcp(false);
    }
  };

  /**
   * Copy MCP URL to clipboard
   */
  const handleCopyUrl = async () => {
    const url = status?.mcp_endpoint_url || config?.mcp_endpoint_url;
    if (url) {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast({
        title: "Copied!",
        description: "MCP URL copied to clipboard",
      });
      setTimeout(() => setCopied(false), 2000);
    }
  };

  /**
   * Refresh status
   */
  const handleRefresh = async () => {
    await loadData();
    toast({
      title: "Refreshed",
      description: "Status updated",
    });
  };

  /**
   * Open upgrade dialog with proper state
   */
  const openUpgradeDialog = () => {
    setNewVersionForUpgrade(config?.mcp_version || "");
    setShowUpgradeDialog(true);
  };

  // Get current status info
  const currentStatus = status?.status || config?.status || "NOT_CONFIGURED";
  const statusInfo = statusVariants[currentStatus] || statusVariants.NOT_CONFIGURED;
  const isDeployed = status?.is_deployed || currentStatus === "DEPLOYED";
  const hasConfig = config !== null;
  const mcpUrl = status?.mcp_endpoint_url || config?.mcp_endpoint_url;

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex flex-col md:flex-row md:items-start justify-between gap-4"
      >
        <div>
          <h1 className="text-3xl font-bold gradient-text mb-2 flex items-center gap-3">
            <Search className="w-8 h-8" />
            Research (Phase 1: IDA)
          </h1>
          <p className="text-muted-foreground max-w-2xl">
            Research is where we connect real researcher tooling to LLM workflows. The portal does not try to host IDA centrally. Instead, the portal makes the connection repeatable, supportable, and governable. <span className="text-xs opacity-75">(JADX & Ghidra coming soon)</span>
          </p>
        </div>
        
        {/* Bitbucket Repository Link Box */}
        <Card className="glass border-border/50 max-w-sm w-full md:w-auto shrink-0">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
              <GitBranch className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h4 className="font-medium text-sm">Contribute to the Plugin</h4>
              <a 
                href={versions?.bitbucket_url || "https://bitbucket.example.com/projects/RES/repos/ida-pro-mcp"}
                target="_blank" 
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline flex items-center gap-1 mt-1"
              >
                View on Bitbucket <ExternalLink className="w-3 h-3" />
              </a>
              {versions?.changelog_content && (
                <button
                  onClick={() => setShowChangelogDialog(true)}
                  className="text-xs text-primary hover:underline flex items-center gap-1 mt-1 bg-transparent border-none p-0 cursor-pointer"
                >
                  View Changelog <BookOpen className="w-3 h-3" />
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Error Alert */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content: Configuration + Instructions Side by Side */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="grid grid-cols-1 lg:grid-cols-3 gap-6"
      >
        {/* Configuration Card - Takes 2/3 */}
        <Card className="glass border-border/50 lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Plug className="w-5 h-5 text-primary" />
                  {hasConfig && isDeployed ? "Update IDA Connection" : "Connect Workstation"}
                </CardTitle>
                <CardDescription>
                  {hasConfig && isDeployed
                    ? "Modify your workstation connection settings and reconnect"
                    : "Register your workstation hostname and port to establish the bridge."
                  }
                </CardDescription>
              </div>
              <Button
                onClick={handleRefresh}
                disabled={isLoading}
                variant="ghost"
                size="icon"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Configuration Form */}
            <div className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {/* Hostname Field */}
                <div className="space-y-2">
                  <Label htmlFor="hostname">Workstation Hostname (FQDN)</Label>
                  <Input
                    id="hostname"
                    placeholder="mypc.corp.example.com or localhost"
                    value={hostname}
                    onChange={(e) => setHostname(e.target.value)}
                    disabled={isLoading || isDeploying || isDeleting || isUpgrading}
                  />
                </div>

                {/* IDA Port Field */}
                <div className="space-y-2">
                  <Label htmlFor="ida-port">IDA Plugin Port</Label>
                  <Input
                    id="ida-port"
                    type="number"
                    placeholder="13337"
                    min={1024}
                    max={65535}
                    value={idaPort}
                    onChange={(e) => setIdaPort(e.target.value ? parseInt(e.target.value) : "")}
                    disabled={isLoading || isDeploying || isDeleting || isUpgrading}
                  />
                </div>
              </div>

              {/* MCP Version Select - with search */}
              <div className="space-y-2">
                <Label htmlFor="mcp-version">MCP Server Version</Label>
                <Select
                  value={mcpVersion}
                  onValueChange={setMcpVersion}
                  disabled={isLoading || isDeploying || isDeleting || isUpgrading}
                >
                  <SelectTrigger id="mcp-version">
                    <SelectValue placeholder="Select version" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Search input for filtering versions */}
                    <div className="px-2 pb-2">
                      <Input
                        placeholder="Search versions..."
                        value={versionSearch}
                        onChange={(e) => setVersionSearch(e.target.value)}
                        className="h-8"
                      />
                    </div>
                    {versions?.versions
                      .filter(v => v.toLowerCase().includes(versionSearch.toLowerCase()))
                      .map((version) => (
                        <SelectItem key={version} value={version}>
                          {version}
                          {version === versions.default_version && " (recommended)"}
                        </SelectItem>
                      ))}
                    {versions?.versions.filter(v => v.toLowerCase().includes(versionSearch.toLowerCase())).length === 0 && (
                      <div className="px-2 py-2 text-sm text-muted-foreground">No matching versions</div>
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Connect Button */}
            <Button
              onClick={handleDeploy}
              disabled={isLoading || isDeploying || isDeleting || isUpgrading || !hostname || !idaPort || !mcpVersion}
              className="w-full bg-gradient-primary mt-4"
              size="lg"
            >
              {isDeploying ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Network className="w-4 h-4 mr-2" />
              )}
              {hasConfig && isDeployed ? "Update & Reconnect" : "Connect"}
            </Button>
            
            <div className="flex justify-between items-center pt-4 border-t mt-4">
              <span className="text-sm font-medium">Auto-Provision in Chat</span>
              <Button 
                onClick={handleProvisionMcp} 
                disabled={isProvisioningMcp || !isDeployed}
                className="bg-gradient-primary shadow-sm h-9"
              >
                {isProvisioningMcp ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Check className="w-4 h-4 mr-2" />
                )}
                Add to OpenWebUI
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Instructions Card - Takes 1/3 */}
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BookOpen className="w-5 h-5 text-primary" />
              Installation & Setup
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4 text-sm">
              <div className="bg-surface/50 p-3 rounded-lg border">
                <h4 className="font-semibold mb-2 text-primary">Prerequisites</h4>
                <ul className="list-disc pl-4 space-y-1 text-muted-foreground text-xs">
                  <li>Python (3.11 or higher)</li>
                  <li>Use <code className="bg-muted px-1 py-0.5 rounded">idapyswitch</code> to switch to the newest Python version</li>
                  <li>IDA Pro (8.3 or higher, 9 recommended). <em>IDA Free is not supported.</em></li>
                </ul>
              </div>

              <div className="space-y-3">
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">1</span>
                  <div className="space-y-2 w-full">
                    <p className="text-muted-foreground font-medium">Install the plugin via pip</p>
                    <div className="flex gap-2">
                      <Input 
                        readOnly 
                        value={versions?.pip_cmd_base && mcpVersion ? `${versions.pip_cmd_base}==${mcpVersion}` : "Loading..."} 
                        className="font-mono text-xs h-8 bg-muted" 
                      />
                      <Button 
                        size="icon" 
                        variant="outline" 
                        className="h-8 w-8 flex-shrink-0"
                        onClick={() => {
                          if (versions?.pip_cmd_base && mcpVersion) {
                            navigator.clipboard.writeText(`${versions.pip_cmd_base}==${mcpVersion}`);
                            toast({ title: "Copied pip command" });
                          }
                        }}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">2</span>
                  <div className="space-y-2 w-full">
                    <p className="text-muted-foreground font-medium">Run setup command</p>
                    <div className="flex gap-2">
                      <Input readOnly value="ida-pro-mcp --install" className="font-mono text-xs h-8 bg-muted" />
                      <Button 
                        size="icon" 
                        variant="outline" 
                        className="h-8 w-8 flex-shrink-0"
                        onClick={() => {
                          navigator.clipboard.writeText("ida-pro-mcp --install");
                          toast({ title: "Copied setup command" });
                        }}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="text-xs text-yellow-500 mt-1">
                      <strong>Important:</strong> Make sure you completely restart IDA after running this command.
                    </div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">3</span>
                  <div>
                    <p className="text-muted-foreground font-medium">Start the server in IDA</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Open any file in IDA, then navigate to:
                    </p>
                    <div className="font-mono bg-muted px-2 py-1 rounded inline-block mt-2 text-xs">Edit &rarr; Plugins &rarr; MCP</div>
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-sm font-bold text-primary">4</span>
                  <div>
                    <p className="text-muted-foreground font-medium">Register connection</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Enter your workstation hostname and the port shown in IDA in the form on the left, then click Connect.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t space-y-3">
              <h4 className="font-semibold text-sm flex items-center gap-2">
                <Terminal className="w-4 h-4 text-primary" /> 
                Local Client Alternative
              </h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                If you prefer to connect a local client like Cline instead of using the portal, you can directly configure it to communicate with the local server:
              </p>
              <div className="flex gap-2">
                <Input readOnly value="http://localhost:13337" className="font-mono text-xs h-8 bg-muted" />
                <Button 
                  size="icon" 
                  variant="outline" 
                  className="h-8 w-8 flex-shrink-0"
                  onClick={() => {
                    navigator.clipboard.writeText("http://localhost:13337");
                    toast({ title: "Copied localhost URL" });
                  }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Deployed Server Details Card - Only shown when deployed */}
      <AnimatePresence>
        {hasConfig && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Server className="w-5 h-5 text-primary" />
                    Your MCP Server
                  </span>
                  <Badge
                    variant={statusInfo.variant}
                    className={isDeployed ? 'bg-green-600 text-white' : ''}
                  >
                    {isDeployed && <span className="w-2 h-2 rounded-full bg-white mr-2 animate-pulse" />}
                    {statusInfo.label}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Status Message */}
                <p className="text-muted-foreground">
                  {status?.message || "Loading status..."}
                </p>

                {/* Details Grid */}
                <div className="rounded-lg border bg-surface/50 p-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="space-y-1">
                      <span className="text-muted-foreground flex items-center gap-1">
                        <Network className="w-3 h-3" /> Hostname
                      </span>
                      <span className="font-medium block truncate" title={config.hostname_fqdn}>
                        {config.hostname_fqdn}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-muted-foreground">IDA Port</span>
                      <span className="font-medium block">{config.ida_port}</span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-muted-foreground">Proxy Port</span>
                      <span className="font-medium block">{config.proxy_port || "Not allocated"}</span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-muted-foreground">MCP Version</span>
                      <span className="font-medium block">{config.mcp_version}</span>
                    </div>
                  </div>

                  {config.last_deploy_at && (
                    <div className="mt-3 pt-3 border-t text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Last deployed: {new Date(config.last_deploy_at).toLocaleString()}
                    </div>
                  )}
                </div>

                {/* MCP URL & Provisioning (when deployed) */}
                {isDeployed && mcpUrl && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>MCP Server URL</Label>
                      <div className="flex gap-2">
                        <Input
                          value={mcpUrl}
                          readOnly
                          className="font-mono text-sm bg-muted"
                        />
                        <Button
                          onClick={handleCopyUrl}
                          variant="outline"
                          size="icon"
                        >
                          {copied ? (
                            <Check className="w-4 h-4 text-green-500" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>

                    <div className="bg-surface/50 p-4 rounded-lg border space-y-3">
                      <h4 className="font-semibold text-sm flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-primary" />
                        Use in OpenWebUI
                      </h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        To use this connection, it must be added to your OpenWebUI profile. 
                        You can do this automatically or manually.
                      </p>
                      
                      <div className="flex flex-col sm:flex-row gap-3 pt-2">
                        <Button 
                          variant="outline" 
                          className="w-full"
                          onClick={() => window.open(versions?.openwebui_url || "https://chat.company.internal", "_blank")}
                        >
                          <ExternalLink className="w-4 h-4 mr-2" />
                          Open WebUI Manually
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error Display */}
                {(status?.last_error || config.last_error) && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{status?.last_error || config.last_error}</AlertDescription>
                  </Alert>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-3 pt-2">
                  <Button
                    onClick={openUpgradeDialog}
                    disabled={isLoading || isDeploying || isDeleting || isUpgrading || !isDeployed}
                    variant="outline"
                  >
                    {isUpgrading ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <ArrowUp className="w-4 h-4 mr-2" />
                    )}
                    Upgrade Version
                  </Button>

                  <Button
                    onClick={() => setShowDeleteDialog(true)}
                    disabled={isLoading || isDeploying || isDeleting || isUpgrading}
                    variant="destructive"
                  >
                    {isDeleting ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4 mr-2" />
                    )}
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete MCP Server?</DialogTitle>
            <DialogDescription>
              This will stop your MCP server pod, remove all routing configuration,
              and delete your configuration. You'll need to redeploy to use the
              IDA integration again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade Dialog */}
      <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upgrade MCP Server Version</DialogTitle>
            <DialogDescription>
              Select a new version to upgrade your MCP server.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Current Version */}
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <span className="text-sm text-muted-foreground">Current Version</span>
              <Badge variant="secondary">{config?.mcp_version}</Badge>
            </div>

            {/* Arrow */}
            <div className="flex justify-center">
              <ArrowUp className="w-6 h-6 text-primary rotate-180" />
            </div>

            {/* New Version Selection - with search */}
            <div className="space-y-2">
              <Label>New Version</Label>
              <Select
                value={newVersionForUpgrade}
                onValueChange={setNewVersionForUpgrade}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select new version" />
                </SelectTrigger>
                <SelectContent>
                  {/* Search input for filtering versions */}
                  <div className="px-2 pb-2">
                    <Input
                      placeholder="Search versions..."
                      value={upgradeVersionSearch}
                      onChange={(e) => setUpgradeVersionSearch(e.target.value)}
                      className="h-8"
                    />
                  </div>
                  {versions?.versions
                    .filter(v => v !== config?.mcp_version)
                    .filter(v => v.toLowerCase().includes(upgradeVersionSearch.toLowerCase()))
                    .map((version) => (
                      <SelectItem key={version} value={version}>
                        {version}
                        {version === versions.default_version && " (recommended)"}
                      </SelectItem>
                    ))}
                  {versions?.versions
                    .filter(v => v !== config?.mcp_version)
                    .filter(v => v.toLowerCase().includes(upgradeVersionSearch.toLowerCase())).length === 0 && (
                      <div className="px-2 py-2 text-sm text-muted-foreground">No matching versions</div>
                    )}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUpgradeDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpgrade}
              disabled={!newVersionForUpgrade || newVersionForUpgrade === config?.mcp_version}
              className="bg-gradient-primary"
            >
              <ArrowUp className="w-4 h-4 mr-2" />
              Upgrade
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Changelog Dialog */}
      <Dialog open={showChangelogDialog} onOpenChange={setShowChangelogDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Changelog</DialogTitle>
            <DialogDescription>
              Recent updates and changes to the IDA MCP Plugin.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 p-4 bg-muted rounded-md overflow-x-auto">
            <pre className="text-sm whitespace-pre-wrap font-mono">
              {versions?.changelog_content || "No changelog available."}
            </pre>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowChangelogDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
