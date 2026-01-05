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
  Network
} from "lucide-react";
import { researchService, IdaBridgeConfig, IdaBridgeStatus, McpVersionsResponse } from "@/lib/api-service";
import { useToast } from "@/hooks/use-toast";

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
  const [newVersionForUpgrade, setNewVersionForUpgrade] = useState("");
  const [versionSearch, setVersionSearch] = useState("");
  const [upgradeVersionSearch, setUpgradeVersionSearch] = useState("");

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
                  {hasConfig && isDeployed ? "Update IDA Connection" : "Deploy IDA Connection"}
                </CardTitle>
                <CardDescription>
                  {hasConfig && isDeployed
                    ? "Modify your workstation connection settings and redeploy"
                    : "Configure your workstation to enable IDA integration through MCP"
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
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Hostname Field */}
              <div className="space-y-2 sm:col-span-2">
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
                  placeholder="9100"
                  min={1024}
                  max={65535}
                  value={idaPort}
                  onChange={(e) => setIdaPort(e.target.value ? parseInt(e.target.value) : "")}
                  disabled={isLoading || isDeploying || isDeleting || isUpgrading}
                />
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

            {/* Deploy Button */}
            <Button
              onClick={handleDeploy}
              disabled={isLoading || isDeploying || isDeleting || isUpgrading || !hostname || !idaPort || !mcpVersion}
              className="w-full bg-gradient-primary"
              size="lg"
            >
              {isDeploying ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4 mr-2" />
              )}
              {hasConfig && isDeployed ? "Update & Redeploy" : "Deploy MCP Server"}
            </Button>
          </CardContent>
        </Card>

        {/* Instructions Card - Takes 1/3 */}
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Info className="w-5 h-5 text-primary" />
              Quick Setup
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 text-sm">
              <div className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">1</span>
                <p className="text-muted-foreground">Install IDA MCP plugin on your workstation</p>
              </div>
              <div className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">2</span>
                <p className="text-muted-foreground">Allow firewall for your IDA port</p>
              </div>
              <div className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">3</span>
                <p className="text-muted-foreground">Enter hostname & port, then Deploy</p>
              </div>
              <div className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">4</span>
                <p className="text-muted-foreground">Copy MCP URL to Open WebUI Settings</p>
              </div>
            </div>

            <div className="pt-3 border-t text-xs text-muted-foreground">
              <p><strong>Tip:</strong> Use your machine's FQDN, not IP address. Check DNS resolves correctly.</p>
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

                {/* MCP URL (when deployed) */}
                {isDeployed && mcpUrl && (
                  <div className="space-y-2">
                    <Label>MCP Server URL (add this to Open WebUI)</Label>
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
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <ExternalLink className="w-3 h-3" />
                      Open WebUI → Settings → Connections → MCP Servers → Add Streamable HTTP
                    </p>
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
    </motion.div>
  );
}
