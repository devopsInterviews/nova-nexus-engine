import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2, RefreshCw, Loader2, CheckCircle, XCircle, Clock, ArrowUpCircle } from "lucide-react";
import { toast } from "sonner";
import apiService, { AdminMcpConnection } from "@/lib/api-service";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Admin MCP Servers Management Component
 * 
 * Displays within the Admin > Research tab.
 * Shows a comprehensive table of all users' IDA MCP server deployments.
 * 
 * Features:
 * - View all server details (user, hostname, ports, version, status)
 * - Upgrade any user's MCP server to a new version
 * - Delete any user's MCP server deployment
 * - Real-time status updates with refresh capability
 * 
 * Access: Rendered only within admin-protected routes (is_admin=true required).
 */
export function AdminMcpServers() {
  const [servers, setServers] = useState<AdminMcpConnection[]>([]);
  const [versions, setVersions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [upgradeDialogOpen, setUpgradeDialogOpen] = useState(false);
  const [selectedServer, setSelectedServer] = useState<AdminMcpConnection | null>(null);
  const [newVersion, setNewVersion] = useState("");
  const [versionSearch, setVersionSearch] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // Fetch all MCP servers on component mount
  useEffect(() => {
    loadServers();
  }, []);

  /**
   * Load all MCP servers from the API.
   */
  const loadServers = async () => {
    setLoading(true);
    try {
      // Load MCP servers
      const response = await apiService.admin.getAllMcpServers();
      if (response.status === 'success' && response.data) {
        setServers(response.data.connections || []);
      } else {
        toast.error("Failed to load MCP servers", {
          description: response.error || "Unknown error occurred",
        });
      }

      // Load available MCP versions
      const versionsRes = await apiService.research.getMcpVersions();
      if (versionsRes.status === 'success' && versionsRes.data) {
        setVersions(versionsRes.data.versions || []);
      }
    } catch (error) {
      toast.error("Error loading MCP servers", {
        description: error instanceof Error ? error.message : "Network error",
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle delete button click - opens confirmation dialog.
   */
  const handleDeleteClick = (server: AdminMcpConnection) => {
    setSelectedServer(server);
    setDeleteDialogOpen(true);
  };

  /**
   * Handle upgrade button click - opens version input dialog.
   */
  const handleUpgradeClick = (server: AdminMcpConnection) => {
    setSelectedServer(server);
    setNewVersion(server.mcp_version); // Pre-fill current version
    setUpgradeDialogOpen(true);
  };

  /**
   * Confirm and execute MCP server deletion.
   */
  const confirmDelete = async () => {
    if (!selectedServer) return;

    setActionLoading(selectedServer.user_id);
    try {
      const response = await apiService.admin.deleteMcpServer(selectedServer.user_id);
      if (response.status === 'success') {
        toast.success("MCP server deleted successfully", {
          description: `Deleted server for ${selectedServer.username}`,
        });
        await loadServers(); // Reload the list
      } else {
        toast.error("Failed to delete MCP server", {
          description: response.error || "Unknown error occurred",
        });
      }
    } catch (error) {
      toast.error("Error deleting MCP server", {
        description: error instanceof Error ? error.message : "Network error",
      });
    } finally {
      setActionLoading(null);
      setDeleteDialogOpen(false);
      setSelectedServer(null);
    }
  };

  /**
   * Confirm and execute MCP server version upgrade.
   */
  const confirmUpgrade = async () => {
    if (!selectedServer || !newVersion) {
      toast.error("Version is required");
      return;
    }

    setActionLoading(selectedServer.user_id);
    try {
      const response = await apiService.admin.upgradeMcpServer(selectedServer.user_id, newVersion);
      if (response.status === 'success') {
        toast.success("MCP server upgrade initiated", {
          description: `Upgrading ${selectedServer.username}'s server to ${newVersion}`,
        });
        await loadServers(); // Reload the list
      } else {
        toast.error("Failed to upgrade MCP server", {
          description: response.error || "Unknown error occurred",
        });
      }
    } catch (error) {
      toast.error("Error upgrading MCP server", {
        description: error instanceof Error ? error.message : "Network error",
      });
    } finally {
      setActionLoading(null);
      setUpgradeDialogOpen(false);
      setSelectedServer(null);
      setNewVersion("");
    }
  };

  /**
   * Render status badge with appropriate color and icon.
   */
  const renderStatusBadge = (status: string) => {
    const statusMap: Record<string, { variant: "default" | "destructive" | "secondary" | "outline", icon: any }> = {
      running: { variant: "default", icon: CheckCircle },
      deploying: { variant: "secondary", icon: Loader2 },
      failed: { variant: "destructive", icon: XCircle },
      pending: { variant: "outline", icon: Clock },
      not_deployed: { variant: "outline", icon: XCircle },
    };

    const config = statusMap[status] || statusMap.pending;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="gap-1">
        <Icon className={`h-3 w-3 ${status === "deploying" ? "animate-spin" : ""}`} />
        {status.replace(/_/g, " ").toUpperCase()}
      </Badge>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>MCP Servers</CardTitle>
          <CardDescription>Loading all users' MCP servers...</CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center items-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>MCP Servers</CardTitle>
              <CardDescription>
                Manage all users' MCP server deployments. Total servers: {servers.length}
              </CardDescription>
            </div>
            <Button onClick={loadServers} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {servers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No MCP servers deployed yet
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Hostname</TableHead>
                    <TableHead>IDA Port</TableHead>
                    <TableHead>Proxy Port</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last Deploy</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {servers.map((server) => (
                    <TableRow key={server.id}>
                      <TableCell className="font-medium">{server.username}</TableCell>
                      <TableCell className="text-muted-foreground">{server.email || "—"}</TableCell>
                      <TableCell className="font-mono text-sm">{server.hostname_fqdn}</TableCell>
                      <TableCell>{server.ida_port}</TableCell>
                      <TableCell>{server.proxy_port || "—"}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{server.mcp_version}</Badge>
                      </TableCell>
                      <TableCell>{renderStatusBadge(server.status)}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {server.last_deploy_at
                          ? new Date(server.last_deploy_at).toLocaleString()
                          : "Never"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleUpgradeClick(server)}
                            disabled={actionLoading === server.user_id || server.status === "deploying"}
                          >
                            {actionLoading === server.user_id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <ArrowUpCircle className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDeleteClick(server)}
                            disabled={actionLoading === server.user_id}
                          >
                            {actionLoading === server.user_id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete MCP Server</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the MCP server for user{" "}
              <span className="font-semibold">{selectedServer?.username}</span>?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade Version Dialog */}
      <Dialog open={upgradeDialogOpen} onOpenChange={setUpgradeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upgrade MCP Server</DialogTitle>
            <DialogDescription>
              Upgrade the MCP server for user{" "}
              <span className="font-semibold">{selectedServer?.username}</span> to a new version.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Current Version</Label>
              <Badge variant="outline" className="w-fit">{selectedServer?.mcp_version}</Badge>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="version">New Version</Label>
              <Select
                value={newVersion}
                onValueChange={setNewVersion}
              >
                <SelectTrigger>
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
                  {versions
                    .filter(v => v !== selectedServer?.mcp_version)
                    .filter(v => v.toLowerCase().includes(versionSearch.toLowerCase()))
                    .map((version) => (
                      <SelectItem key={version} value={version}>
                        {version}
                      </SelectItem>
                    ))}
                  {versions
                    .filter(v => v !== selectedServer?.mcp_version)
                    .filter(v => v.toLowerCase().includes(versionSearch.toLowerCase())).length === 0 && (
                      <div className="px-2 py-2 text-sm text-muted-foreground">No matching versions</div>
                    )}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpgradeDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={confirmUpgrade} disabled={!newVersion || newVersion === selectedServer?.mcp_version}>
              Upgrade
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
