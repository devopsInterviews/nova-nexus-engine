/**
 * Research Page Component
 * 
 * This page allows users to configure and deploy their IDA MCP connection.
 * Users can register their workstation hostname, IDA port, and select an MCP version.
 * Once deployed, they receive an MCP URL to add in Open WebUI.
 * 
 * Features:
 * - Form for configuring IDA connection (hostname, port, MCP version)
 * - Deploy/Undeploy buttons for managing MCP server
 * - Status display with deployment state and MCP URL
 * - Copy-to-clipboard for MCP URL
 * - Error handling and validation
 */

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  Search, 
  Server, 
  Plug, 
  Copy, 
  Check, 
  RefreshCw, 
  AlertCircle,
  Rocket,
  Power,
  Info,
  ExternalLink
} from "lucide-react";
import { researchService, IdaBridgeConfig, IdaBridgeStatus, McpVersionsResponse } from "@/lib/api-service";
import { useToast } from "@/hooks/use-toast";

/**
 * Status badge variant mapping based on deployment status
 */
const statusVariants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
  NEW: { variant: "secondary", label: "Not Deployed" },
  DEPLOYING: { variant: "default", label: "Deploying..." },
  DEPLOYED: { variant: "default", label: "Deployed" },
  ERROR: { variant: "destructive", label: "Error" },
  UNDEPLOYED: { variant: "secondary", label: "Undeployed" },
  NOT_CONFIGURED: { variant: "outline", label: "Not Configured" },
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
  const [isSaving, setIsSaving] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isUndeploying, setIsUndeploying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { toast } = useToast();

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
   * Save configuration to the database
   */
  const handleSave = async () => {
    if (!hostname.trim()) {
      toast({
        title: "Validation Error",
        description: "Hostname is required",
        variant: "destructive",
      });
      return;
    }
    
    if (!idaPort || idaPort < 1024 || idaPort > 65535) {
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
    
    setIsSaving(true);
    setError(null);
    
    try {
      const result = await researchService.saveIdaBridgeConfig({
        hostname_fqdn: hostname.trim().toLowerCase(),
        ida_port: Number(idaPort),
        mcp_version: mcpVersion,
      });
      
      if (result.status === "success" && result.data) {
        setConfig(result.data);
        toast({
          title: "Configuration Saved",
          description: "Your IDA bridge configuration has been saved successfully.",
        });
        // Reload status
        await loadData();
      } else {
        throw new Error(result.error || "Failed to save configuration");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to save configuration";
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Deploy the MCP server
   */
  const handleDeploy = async () => {
    // Save first if there are changes
    if (
      config?.hostname_fqdn !== hostname ||
      config?.ida_port !== idaPort ||
      config?.mcp_version !== mcpVersion
    ) {
      await handleSave();
    }
    
    setIsDeploying(true);
    setError(null);
    
    try {
      const result = await researchService.deployIdaBridge();
      
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
   * Undeploy the MCP server
   */
  const handleUndeploy = async () => {
    setIsUndeploying(true);
    setError(null);
    
    try {
      const result = await researchService.undeployIdaBridge();
      
      if (result.status === "success" && result.data) {
        toast({
          title: "Undeployment Successful",
          description: result.data.message,
        });
        // Reload all data
        await loadData();
      } else {
        throw new Error(result.error || "Undeployment failed");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Undeployment failed";
      setError(errorMessage);
      toast({
        title: "Undeployment Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsUndeploying(false);
    }
  };

  /**
   * Copy MCP URL to clipboard
   */
  const handleCopyUrl = async () => {
    if (status?.mcp_endpoint_url) {
      await navigator.clipboard.writeText(status.mcp_endpoint_url);
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

  // Get current status info
  const currentStatus = status?.status || "NOT_CONFIGURED";
  const statusInfo = statusVariants[currentStatus] || statusVariants.NOT_CONFIGURED;
  const isDeployed = status?.is_deployed || false;

  return (
    <motion.div
      className="space-y-6 max-w-4xl"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h1 className="text-3xl font-bold gradient-text mb-2 flex items-center gap-3">
          <Search className="w-8 h-8" />
          Research
        </h1>
        <p className="text-muted-foreground">
          Connect Open WebUI to your local IDA instance via MCP server
        </p>
      </motion.div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </motion.div>
      )}

      {/* IDA MCP Connection Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plug className="w-5 h-5 text-primary" />
              IDA MCP Connection
            </CardTitle>
            <CardDescription>
              Configure your workstation connection to enable IDA integration through MCP
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Configuration Form */}
            <div className="grid gap-4">
              {/* Hostname Field */}
              <div className="space-y-2">
                <Label htmlFor="hostname">Workstation Hostname (FQDN)</Label>
                <Input
                  id="hostname"
                  placeholder="mypc.corp.example.com"
                  value={hostname}
                  onChange={(e) => setHostname(e.target.value)}
                  disabled={isLoading || isDeploying || isUndeploying}
                />
                <p className="text-xs text-muted-foreground">
                  Enter your workstation's fully qualified domain name (FQDN), not IP address
                </p>
              </div>

              {/* IDA Port Field */}
              <div className="space-y-2">
                <Label htmlFor="ida-port">IDA Plugin Port</Label>
                <Input
                  id="ida-port"
                  type="number"
                  placeholder="9100"
                  min={1024}
                  max={65535}
                  value={idaPort}
                  onChange={(e) => setIdaPort(e.target.value ? parseInt(e.target.value) : "")}
                  disabled={isLoading || isDeploying || isUndeploying}
                />
                <p className="text-xs text-muted-foreground">
                  The port where your IDA MCP plugin is listening (typically 9100 or 13337)
                </p>
              </div>

              {/* MCP Version Select */}
              <div className="space-y-2">
                <Label htmlFor="mcp-version">MCP Server Version</Label>
                <Select
                  value={mcpVersion}
                  onValueChange={setMcpVersion}
                  disabled={isLoading || isDeploying || isUndeploying}
                >
                  <SelectTrigger id="mcp-version">
                    <SelectValue placeholder="Select MCP version" />
                  </SelectTrigger>
                  <SelectContent>
                    {versions?.versions.map((version) => (
                      <SelectItem key={version} value={version}>
                        {version}
                        {version === versions.default_version && " (recommended)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Select the MCP server version to deploy
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={handleSave}
                disabled={isLoading || isSaving || isDeploying || isUndeploying}
                variant="outline"
              >
                {isSaving ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Server className="w-4 h-4 mr-2" />
                )}
                Save Configuration
              </Button>
              
              <Button
                onClick={handleDeploy}
                disabled={isLoading || isSaving || isDeploying || isUndeploying || !hostname || !idaPort || !mcpVersion}
                className="bg-gradient-primary"
              >
                {isDeploying ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Rocket className="w-4 h-4 mr-2" />
                )}
                Deploy
              </Button>
              
              <Button
                onClick={handleUndeploy}
                disabled={isLoading || isSaving || isDeploying || isUndeploying || !isDeployed}
                variant="destructive"
              >
                {isUndeploying ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Power className="w-4 h-4 mr-2" />
                )}
                Undeploy
              </Button>
              
              <Button
                onClick={handleRefresh}
                disabled={isLoading}
                variant="ghost"
                size="icon"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Status Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Server className="w-5 h-5 text-primary" />
                Deployment Status
              </span>
              <Badge variant={statusInfo.variant} className={isDeployed ? 'animate-pulse bg-success' : ''}>
                {statusInfo.label}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Status Message */}
            <p className="text-muted-foreground">
              {status?.message || "Loading status..."}
            </p>

            {/* Status Details Table */}
            {config && (
              <div className="rounded-lg border bg-surface/50 p-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Hostname:</span>
                    <span className="ml-2 font-medium">{config.hostname_fqdn}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">IDA Port:</span>
                    <span className="ml-2 font-medium">{config.ida_port}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Proxy Port:</span>
                    <span className="ml-2 font-medium">{config.proxy_port || "Not allocated"}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">MCP Version:</span>
                    <span className="ml-2 font-medium">{config.mcp_version}</span>
                  </div>
                  {config.last_deploy_at && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Last Deployed:</span>
                      <span className="ml-2 font-medium">
                        {new Date(config.last_deploy_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* MCP URL (when deployed) */}
            {isDeployed && status?.mcp_endpoint_url && (
              <div className="space-y-2">
                <Label>MCP Server URL</Label>
                <div className="flex gap-2">
                  <Input
                    value={status.mcp_endpoint_url}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    onClick={handleCopyUrl}
                    variant="outline"
                    size="icon"
                  >
                    {copied ? (
                      <Check className="w-4 h-4 text-success" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Add this URL in Open WebUI Settings → Connections → MCP Servers as a Streamable HTTP connection
                </p>
              </div>
            )}

            {/* Error Display */}
            {status?.last_error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Deployment Error</AlertTitle>
                <AlertDescription>{status.last_error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Help/Instructions Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="w-5 h-5 text-primary" />
              Setup Instructions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 text-sm">
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">1</span>
                <div>
                  <p className="font-medium">Enable IDA Plugin</p>
                  <p className="text-muted-foreground">Install and enable the IDA MCP plugin on your workstation. Make sure it's listening on the configured port.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">2</span>
                <div>
                  <p className="font-medium">Configure Firewall</p>
                  <p className="text-muted-foreground">Allow inbound connections to your IDA port from the proxy server IP range.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">3</span>
                <div>
                  <p className="font-medium">Enter Configuration</p>
                  <p className="text-muted-foreground">Fill in your workstation hostname (FQDN, not IP) and IDA plugin port above.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">4</span>
                <div>
                  <p className="font-medium">Deploy MCP Server</p>
                  <p className="text-muted-foreground">Click Deploy to allocate a proxy port and start your MCP server pod.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">5</span>
                <div>
                  <p className="font-medium">Add to Open WebUI</p>
                  <p className="text-muted-foreground">Copy the MCP URL and add it in Open WebUI Settings → Connections → MCP Servers.</p>
                </div>
              </div>
            </div>
            
            <div className="pt-4 border-t">
              <p className="text-xs text-muted-foreground">
                <strong>Troubleshooting:</strong> If you encounter connection issues, verify your hostname resolves correctly via DNS, 
                ensure your firewall allows the connection, and check that your IDA plugin is running.
              </p>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
