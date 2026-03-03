/**
 * Marketplace Page
 *
 * Centralised hub for AI Agents and MCP Servers.
 * Features:
 *  - Colour-coded status legend (Built / Dev-Deployed / Release-Deployed)
 *  - Per-card TTL countdown for dev deployments
 *  - Image upload (converted to base64 and stored in the DB)
 *  - Deploy modal with Artifactory chart-version selector
 *  - Fork/Clone button to create parallel deployments from the same build
 *  - Public /ping registration visible in usage counters
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ThemedTabs,
  ThemedTabsList,
  ThemedTabsTrigger,
  ThemedTabsContent,
} from "@/components/ui/themed-tabs";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/context/auth-context";
import { toast } from "sonner";
import {
  Activity,
  Blocks,
  Calendar,
  ChevronRight,
  Clock,
  Cloud,
  Copy,
  ExternalLink,
  Github,
  Hammer,
  Plus,
  Rocket,
  Search,
  Sparkles,
  Trash2,
  UploadCloud,
  Users,
  Zap,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface MarketplaceItem {
  id: number;
  name: string;
  description: string;
  item_type: "agent" | "mcp_server";
  owner_id: number;
  owner_name: string;
  icon: string | null;
  bitbucket_repo: string | null;
  how_to_use: string | null;
  url_to_connect: string | null;
  tools_exposed: { name: string }[];
  deployment_status: "CREATED" | "BUILT" | "DEPLOYED";
  version: string;
  environment: "dev" | "release";
  chart_version: string | null;
  ttl_days: number | null;
  ttl_remaining_days: number | null;
  deployed_at: string | null;
  created_at: string;
  usage_count: number;
  unique_users: number;
}

interface MarketplaceConfig {
  max_agents_per_user: number;
  max_mcp_per_user: number;
  dev_ttl_days: number;
}

// ─── Status helpers ───────────────────────────────────────────────────────────

function getStatusMeta(item: MarketplaceItem) {
  if (item.deployment_status === "DEPLOYED" && item.environment === "release") {
    return {
      topBar: "bg-emerald-500",
      border: "border-emerald-500/40",
      hoverBorder: "hover:border-emerald-400",
      glow: "hover:shadow-emerald-500/20",
      badgeClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      label: "Deployed · Release",
    };
  }
  if (item.deployment_status === "DEPLOYED" && item.environment === "dev") {
    return {
      topBar: "bg-violet-500",
      border: "border-violet-500/40",
      hoverBorder: "hover:border-violet-400",
      glow: "hover:shadow-violet-500/20",
      badgeClass: "bg-violet-500/15 text-violet-400 border-violet-500/30",
      label: "Deployed · Dev",
    };
  }
  if (item.deployment_status === "BUILT") {
    return {
      topBar: "bg-amber-500",
      border: "border-amber-500/30",
      hoverBorder: "hover:border-amber-400",
      glow: "hover:shadow-amber-500/20",
      badgeClass: "bg-amber-500/15 text-amber-400 border-amber-500/30",
      label: "Built",
    };
  }
  return {
    topBar: "",
    border: "border-border/40",
    hoverBorder: "hover:border-primary/60",
    glow: "hover:shadow-primary/20",
    badgeClass: "bg-muted text-muted-foreground border-border/50",
    label: "Created",
  };
}

function getTtlColor(remaining: number | null): string {
  if (remaining === null) return "";
  if (remaining <= 3) return "text-red-400 bg-red-500/10 border-red-500/30";
  if (remaining <= 7) return "text-orange-400 bg-orange-500/10 border-orange-500/30";
  return "text-violet-400 bg-violet-500/10 border-violet-500/30";
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function EntityIcon({
  icon,
  item_type,
  size = "md",
}: {
  icon: string | null;
  item_type: string;
  size?: "sm" | "md" | "lg";
}) {
  const dim = size === "lg" ? "w-20 h-20" : size === "md" ? "w-14 h-14" : "w-10 h-10";
  const iconSize = size === "lg" ? 36 : size === "md" ? 26 : 18;

  if (icon) {
    return (
      <img
        src={icon}
        alt="entity icon"
        className={`${dim} rounded-xl object-cover border border-border/50 shrink-0`}
      />
    );
  }
  return (
    <div
      className={`${dim} rounded-xl bg-primary/10 flex items-center justify-center border border-primary/20 shrink-0`}
    >
      {item_type === "agent" ? (
        <Zap size={iconSize} className="text-primary/80" />
      ) : (
        <Blocks size={iconSize} className="text-primary/80" />
      )}
    </div>
  );
}

function ColorLegend({ devTtlDays }: { devTtlDays: number }) {
  const items = [
    {
      color: "bg-amber-500",
      label: "Built",
      desc: "Ready to deploy — select a chart version to go live",
    },
    {
      color: "bg-violet-500",
      label: "Dev Deployed",
      desc: `Auto-expires after ${devTtlDays} days`,
    },
    {
      color: "bg-emerald-500",
      label: "Release Deployed",
      desc: "Persistent — no expiry",
    },
    {
      color: "bg-border/0 border border-dashed border-border",
      label: "Created",
      desc: "Not yet built — trigger CI/CD to build",
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-2 px-5 py-3 rounded-xl bg-muted/20 border border-border/30 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/60 mr-1">
        Legend
      </span>
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-2">
          <span className={`inline-block w-5 h-1.5 rounded-full ${item.color}`} />
          <span className="font-medium text-foreground/80">{item.label}</span>
          <span className="text-muted-foreground/60 hidden sm:inline">— {item.desc}</span>
        </span>
      ))}
    </div>
  );
}

function ItemCard({
  item,
  onClick,
}: {
  item: MarketplaceItem;
  onClick: () => void;
}) {
  const meta = getStatusMeta(item);
  const showTtl =
    item.deployment_status === "DEPLOYED" &&
    item.environment === "dev" &&
    item.ttl_remaining_days !== null;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      className={`
        group relative cursor-pointer rounded-2xl overflow-hidden
        bg-surface/60 backdrop-blur-sm
        border-2 ${meta.border} ${meta.hoverBorder}
        transition-all duration-200
        hover:scale-[1.018] hover:shadow-xl ${meta.glow}
        flex flex-col h-full
      `}
    >
      {/* Coloured status top bar */}
      {meta.topBar && (
        <div className={`absolute top-0 inset-x-0 h-1 ${meta.topBar} z-10`} />
      )}

      <CardHeader className="pt-5 pb-3 gap-0">
        <div className="flex items-start gap-3">
          <EntityIcon icon={item.icon} item_type={item.item_type} />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-base leading-tight truncate group-hover:text-primary transition-colors">
              {item.name}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              by{" "}
              <span className="text-foreground/70 font-medium">{item.owner_name}</span>
            </p>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              <span className="text-[10px] font-semibold bg-muted/60 border border-border/50 px-1.5 py-0.5 rounded-md text-muted-foreground">
                v{item.version}
              </span>
              <span
                className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md border ${
                  item.environment === "release"
                    ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                    : "bg-orange-500/10 text-orange-400 border-orange-500/30"
                }`}
              >
                {item.environment.toUpperCase()}
              </span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 pt-0 pb-2">
        <p className="text-sm text-muted-foreground line-clamp-3 leading-relaxed">
          {item.description}
        </p>

        {/* TTL badge */}
        {showTtl && (
          <div
            className={`inline-flex items-center gap-1.5 mt-2.5 text-xs font-semibold px-2 py-1 rounded-lg border ${getTtlColor(item.ttl_remaining_days)}`}
          >
            <Clock size={11} />
            {item.ttl_remaining_days === 0
              ? "Expiring today"
              : `${item.ttl_remaining_days}d left`}
          </div>
        )}
      </CardContent>

      <CardFooter className="border-t border-border/30 bg-muted/10 py-2.5 px-4 flex items-center justify-between gap-2 mt-auto">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1" title="Total calls">
            <Activity size={12} className="text-primary/60" />
            <span className="font-semibold text-foreground/70">{item.usage_count}</span>
          </span>
          <span className="flex items-center gap-1" title="Unique users">
            <Users size={12} className="text-emerald-500/60" />
            <span className="font-semibold text-foreground/70">{item.unique_users}</span>
          </span>
        </div>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${meta.badgeClass}`}
        >
          {meta.label}
        </span>
      </CardFooter>
    </div>
  );
}

// ─── Main Page Component ──────────────────────────────────────────────────────

export default function Marketplace() {
  const { token, user } = useAuth();

  const [items, setItems] = useState<MarketplaceItem[]>([]);
  const [config, setConfig] = useState<MarketplaceConfig>({
    max_agents_per_user: 5,
    max_mcp_per_user: 5,
    dev_ttl_days: 10,
  });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Detail modal
  const [selectedItem, setSelectedItem] = useState<MarketplaceItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Create modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    item_type: "agent",
    icon: "",
    bitbucket_repo: "",
    how_to_use: "",
    url_to_connect: "",
  });
  const iconInputRef = useRef<HTMLInputElement>(null);

  // Deploy modal
  const [isDeployOpen, setIsDeployOpen] = useState(false);
  const [deployEnv, setDeployEnv] = useState<"dev" | "release">("dev");
  const [chartVersions, setChartVersions] = useState<string[]>([]);
  const [selectedChartVersion, setSelectedChartVersion] = useState("latest");
  const [deployLoading, setDeployLoading] = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────────

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch("/api/marketplace/config", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setConfig(await res.json());
    } catch {
      /* ignore — defaults are fine */
    }
  }, [token]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/marketplace/items", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: MarketplaceItem[] = await res.json();
        setItems(data);
      }
    } catch {
      toast.error("Failed to load marketplace items.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchChartVersions = useCallback(
    async (env: "dev" | "release", chartName: string) => {
      try {
        const res = await fetch(
          `/api/marketplace/chart-versions?environment=${env}&chart_name=${encodeURIComponent(chartName)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.ok) {
          const data = await res.json();
          setChartVersions(data.versions ?? ["latest"]);
          setSelectedChartVersion(data.versions?.[0] ?? "latest");
        }
      } catch {
        setChartVersions(["latest"]);
        setSelectedChartVersion("latest");
      }
    },
    [token]
  );

  useEffect(() => {
    if (token) {
      fetchConfig();
      fetchItems();
    }
  }, [token, fetchConfig, fetchItems]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  const isOwnerOrAdmin = (item: MarketplaceItem) =>
    user?.is_admin || user?.id === item.owner_id;

  const openDetail = (item: MarketplaceItem) => {
    setSelectedItem(item);
    setIsDetailOpen(true);
  };

  const openDeploy = async (item: MarketplaceItem, env: "dev" | "release") => {
    setDeployEnv(env);
    setIsDeployOpen(true);
    setSelectedItem(item);
    await fetchChartVersions(env, item.name);
  };

  // ── Icon upload handler ────────────────────────────────────────────────────

  const handleIconFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1_048_576) {
      toast.error("Icon image must be smaller than 1 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () =>
      setFormData((prev) => ({ ...prev, icon: reader.result as string }));
    reader.readAsDataURL(file);
  };

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    try {
      const res = await fetch("/api/marketplace/items", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        toast.success(`${formData.item_type === "agent" ? "Agent" : "MCP Server"} created!`);
        setIsCreateOpen(false);
        setFormData({
          name: "", description: "", item_type: "agent",
          icon: "", bitbucket_repo: "", how_to_use: "", url_to_connect: "",
        });
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to create item.");
      }
    } catch {
      toast.error("Network error.");
    } finally {
      setCreateLoading(false);
    }
  };

  const handleBuild = async (item: MarketplaceItem) => {
    try {
      const res = await fetch("/api/marketplace/build", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ item_id: item.id }),
      });
      if (res.ok) {
        toast.success("Build triggered — status set to BUILT.");
        fetchItems();
        setIsDetailOpen(false);
      } else {
        const err = await res.json();
        toast.error(err.detail || "Build failed.");
      }
    } catch {
      toast.error("Network error.");
    }
  };

  const handleDeploy = async () => {
    if (!selectedItem) return;
    setDeployLoading(true);
    try {
      const res = await fetch("/api/marketplace/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          item_id: selectedItem.id,
          environment: deployEnv,
          chart_version: selectedChartVersion,
        }),
      });
      if (res.ok) {
        toast.success(`Deployed to ${deployEnv.toUpperCase()} (chart ${selectedChartVersion})!`);
        setIsDeployOpen(false);
        setIsDetailOpen(false);
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Deploy failed.");
      }
    } catch {
      toast.error("Network error.");
    } finally {
      setDeployLoading(false);
    }
  };

  const handleClone = async (item: MarketplaceItem) => {
    try {
      const res = await fetch(`/api/marketplace/items/${item.id}/clone`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        toast.success("Fork created — you can now deploy it independently.");
        setIsDetailOpen(false);
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Clone failed.");
      }
    } catch {
      toast.error("Network error.");
    }
  };

  const handleCall = async (item: MarketplaceItem) => {
    try {
      const res = await fetch("/api/marketplace/usage", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ item_id: item.id, action: "call" }),
      });
      if (res.ok) {
        toast.success("Call logged!");
        fetchItems();
      }
    } catch {
      toast.error("Network error.");
    }
  };

  const handleDelete = async (item: MarketplaceItem) => {
    if (!confirm(`Delete "${item.name}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/marketplace/items/${item.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        toast.success("Item deleted.");
        setIsDetailOpen(false);
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Delete failed.");
      }
    } catch {
      toast.error("Network error.");
    }
  };

  // ── Derived data ───────────────────────────────────────────────────────────

  const q = search.toLowerCase();
  const filtered = (arr: MarketplaceItem[]) =>
    arr.filter(
      (i) =>
        i.name.toLowerCase().includes(q) ||
        i.description.toLowerCase().includes(q) ||
        i.owner_name?.toLowerCase().includes(q)
    );

  const agents = filtered(items.filter((i) => i.item_type === "agent"));
  const mcpServers = filtered(items.filter((i) => i.item_type === "mcp_server"));

  // ── Render helpers ─────────────────────────────────────────────────────────

  const renderGrid = (list: MarketplaceItem[], emptyIcon: React.ReactNode, emptyMsg: string) => {
    if (loading)
      return (
        <div className="flex items-center justify-center h-48">
          <p className="text-muted-foreground animate-pulse">Loading…</p>
        </div>
      );
    if (list.length === 0)
      return (
        <div className="flex flex-col items-center justify-center h-52 border-2 border-dashed border-border/40 rounded-2xl bg-surface/20">
          <div className="opacity-20 mb-3">{emptyIcon}</div>
          <p className="text-muted-foreground">{emptyMsg}</p>
        </div>
      );
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 auto-rows-fr">
        {list.map((item) => (
          <ItemCard key={item.id} item={item} onClick={() => openDetail(item)} />
        ))}
      </div>
    );
  };

  // ─── Detail modal body ─────────────────────────────────────────────────────

  const DetailModal = () => {
    const item = selectedItem;
    if (!item) return null;
    const meta = getStatusMeta(item);
    const canManage = isOwnerOrAdmin(item);

    return (
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="sm:max-w-[720px] max-h-[90vh] overflow-y-auto p-0">
          {/* Header band */}
          <div className={`h-1.5 w-full ${meta.topBar || "bg-border/30"}`} />
          <div className="px-7 pt-5 pb-4 border-b border-border/40">
            <div className="flex items-start gap-4">
              <EntityIcon icon={item.icon} item_type={item.item_type} size="lg" />
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <DialogTitle className="text-2xl font-bold leading-tight">{item.name}</DialogTitle>
                    <DialogDescription className="mt-1 flex flex-wrap items-center gap-3 text-sm">
                      <span>Owner: <strong className="text-foreground/80">{item.owner_name}</strong></span>
                      <span>|</span>
                      <span className={`font-semibold px-2 py-0.5 rounded-md border text-xs ${meta.badgeClass}`}>
                        {meta.label}
                      </span>
                      <span
                        className={`text-xs font-semibold px-1.5 py-0.5 rounded-md border ${
                          item.environment === "release"
                            ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                            : "bg-orange-500/10 text-orange-400 border-orange-500/30"
                        }`}
                      >
                        {item.environment.toUpperCase()}
                      </span>
                    </DialogDescription>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="px-7 py-5 space-y-5">
            {/* Description */}
            <section>
              <h4 className="text-sm font-semibold mb-2 text-foreground/80">Description</h4>
              <p className="text-sm text-muted-foreground bg-muted/30 border border-border/40 rounded-xl p-4 leading-relaxed">
                {item.description}
              </p>
            </section>

            {/* How to use */}
            {item.how_to_use && (
              <section>
                <h4 className="text-sm font-semibold mb-2 text-foreground/80">How to Use</h4>
                <p className="text-sm text-muted-foreground bg-primary/5 border border-primary/20 rounded-xl p-4 leading-relaxed">
                  {item.how_to_use}
                </p>
              </section>
            )}

            {/* Info grid */}
            <div className="grid grid-cols-2 gap-3">
              <InfoTile
                label="Chart Version"
                value={item.chart_version || item.version || "1.0.0"}
                sub={
                  item.environment === "dev"
                    ? `Dev: auto-undeploys in ${item.ttl_days ?? config.dev_ttl_days} days`
                    : "Release: persistent (no TTL)"
                }
              />
              {item.ttl_remaining_days !== null && item.environment === "dev" && (
                <InfoTile
                  label="TTL Remaining"
                  value={
                    item.ttl_remaining_days === 0
                      ? "Expiring today"
                      : `${item.ttl_remaining_days} days`
                  }
                  valueClass={getTtlColor(item.ttl_remaining_days)}
                  sub={`Deployed: ${item.deployed_at ? new Date(item.deployed_at).toLocaleDateString() : "—"}`}
                />
              )}
              {item.bitbucket_repo && (
                <div className="bg-muted/30 border border-border/40 rounded-xl p-3 flex items-center gap-3">
                  <Github size={18} className="text-muted-foreground shrink-0" />
                  <div className="overflow-hidden">
                    <p className="text-xs text-muted-foreground">Repository</p>
                    <a
                      href={item.bitbucket_repo}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-primary hover:underline truncate block"
                    >
                      View Source Code ↗
                    </a>
                  </div>
                </div>
              )}
              {item.url_to_connect && (
                <div className="bg-muted/30 border border-border/40 rounded-xl p-3 flex items-center gap-3">
                  <ExternalLink size={18} className="text-muted-foreground shrink-0" />
                  <div className="overflow-hidden">
                    <p className="text-xs text-muted-foreground">Connection URL</p>
                    <a
                      href={item.url_to_connect}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-primary hover:underline truncate block"
                    >
                      {item.url_to_connect}
                    </a>
                  </div>
                </div>
              )}
              <div className="bg-muted/30 border border-border/40 rounded-xl p-3 flex items-center gap-3">
                <Calendar size={18} className="text-muted-foreground shrink-0" />
                <div>
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="text-sm font-medium">
                    {new Date(item.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Usage stats */}
            <div className="flex gap-8 py-4 border-t border-border/40 px-1">
              <StatBig value={item.usage_count} label="Total Calls" color="text-primary" />
              <StatBig value={item.unique_users} label="Unique Users" color="text-emerald-400" />
              {item.tools_exposed?.length > 0 && (
                <StatBig
                  value={item.tools_exposed.length}
                  label="Tools Exposed"
                  color="text-violet-400"
                />
              )}
            </div>
          </div>

          {/* Footer actions */}
          <div className="px-7 py-4 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-3 bg-muted/10">
            <div className="flex gap-2">
              {canManage && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(item)}
                  className="gap-1.5"
                >
                  <Trash2 size={14} /> Delete
                </Button>
              )}
            </div>

            <div className="flex flex-wrap gap-2 justify-end">
              {canManage && item.deployment_status === "CREATED" && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 border-amber-500/50 text-amber-400 hover:bg-amber-500 hover:text-white hover:border-amber-500"
                  onClick={() => handleBuild(item)}
                >
                  <Hammer size={14} /> Build CI/CD
                </Button>
              )}

              {canManage && (item.deployment_status === "BUILT" || item.deployment_status === "DEPLOYED") && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5 border-violet-500/50 text-violet-400 hover:bg-violet-500 hover:text-white hover:border-violet-500"
                    onClick={() => {
                      setIsDetailOpen(false);
                      openDeploy(item, "dev");
                    }}
                  >
                    <Cloud size={14} /> Deploy Dev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5 border-emerald-500/50 text-emerald-400 hover:bg-emerald-500 hover:text-white hover:border-emerald-500"
                    onClick={() => {
                      setIsDetailOpen(false);
                      openDeploy(item, "release");
                    }}
                  >
                    <Rocket size={14} /> Deploy Release
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    title="Fork this build to create a parallel deployment"
                    onClick={() => handleClone(item)}
                  >
                    <Copy size={14} /> Fork
                  </Button>
                </>
              )}

              {item.deployment_status === "DEPLOYED" && (
                <Button
                  size="sm"
                  className="gap-1.5 bg-primary text-primary-foreground"
                  onClick={() => handleCall(item)}
                >
                  <Zap size={14} /> Run / Call
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    );
  };

  // ─── Deploy modal ──────────────────────────────────────────────────────────

  const DeployModal = () => (
    <Dialog open={isDeployOpen} onOpenChange={setIsDeployOpen}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {deployEnv === "dev" ? (
              <Cloud size={18} className="text-violet-400" />
            ) : (
              <Rocket size={18} className="text-emerald-400" />
            )}
            Deploy to {deployEnv === "dev" ? "Dev" : "Release"}
          </DialogTitle>
          <DialogDescription>
            {selectedItem?.name} — select a Helm chart version then confirm.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label className="text-sm font-medium mb-2 block">Chart Version</Label>
            <select
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm focus:ring-1 focus:ring-primary focus:border-primary"
              value={selectedChartVersion}
              onChange={(e) => setSelectedChartVersion(e.target.value)}
            >
              {chartVersions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>

          {deployEnv === "dev" && (
            <div className="flex items-start gap-3 p-3 rounded-xl bg-violet-500/10 border border-violet-500/30 text-sm text-violet-300">
              <Clock size={16} className="mt-0.5 shrink-0" />
              <span>
                Dev deployments auto-expire after{" "}
                <strong>{config.dev_ttl_days} days</strong>. The system will
                automatically undeploy and remove this item when the TTL is reached.
              </span>
            </div>
          )}
          {deployEnv === "release" && (
            <div className="flex items-start gap-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-sm text-emerald-300">
              <Rocket size={16} className="mt-0.5 shrink-0" />
              <span>Release deployments are <strong>persistent</strong> and have no TTL.</span>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => setIsDeployOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleDeploy}
            disabled={deployLoading}
            className={
              deployEnv === "dev"
                ? "bg-violet-600 hover:bg-violet-500 text-white"
                : "bg-emerald-600 hover:bg-emerald-500 text-white"
            }
          >
            {deployLoading ? "Deploying…" : `Deploy to ${deployEnv === "dev" ? "Dev" : "Release"}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  // ─── Create modal ──────────────────────────────────────────────────────────

  const CreateModal = () => (
    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
      <DialogContent className="sm:max-w-[820px] max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2">
            <Sparkles size={20} className="text-primary" />
            Register New Entity
          </DialogTitle>
          <DialogDescription>
            Publish a new Agent or MCP Server to the Marketplace. After
            registration you can trigger a build and then deploy it.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleCreate} className="mt-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* Left: Icon upload */}
            <div className="md:col-span-2 flex items-start gap-6 p-4 rounded-2xl border border-border/40 bg-muted/20">
              <div
                className="w-24 h-24 rounded-2xl border-2 border-dashed border-border/50 bg-muted/30 flex items-center justify-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all shrink-0 overflow-hidden"
                onClick={() => iconInputRef.current?.click()}
              >
                {formData.icon ? (
                  <img src={formData.icon} alt="preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="flex flex-col items-center gap-1 text-muted-foreground/50">
                    <UploadCloud size={24} />
                    <span className="text-[10px]">Upload</span>
                  </div>
                )}
              </div>
              <input
                ref={iconInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleIconFile}
              />
              <div className="flex-1">
                <p className="font-medium text-sm mb-1">Entity Icon</p>
                <p className="text-xs text-muted-foreground mb-3">
                  Upload a square image (PNG, JPG, SVG — max 1 MB).
                  It will be stored in the database and shown on the card.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => iconInputRef.current?.click()}
                >
                  <UploadCloud size={14} />
                  {formData.icon ? "Change Image" : "Choose Image"}
                </Button>
                {formData.icon && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="ml-2 text-muted-foreground"
                    onClick={() => setFormData((p) => ({ ...p, icon: "" }))}
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>

            {/* Type selector */}
            <div className="space-y-2">
              <Label className="font-medium">
                Type <span className="text-destructive">*</span>
              </Label>
              <div className="grid grid-cols-2 gap-2">
                {(["agent", "mcp_server"] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setFormData((p) => ({ ...p, item_type: type }))}
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                      formData.item_type === type
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border/50 text-muted-foreground hover:border-border"
                    }`}
                  >
                    {type === "agent" ? <Zap size={16} /> : <Blocks size={16} />}
                    {type === "agent" ? "Agent" : "MCP Server"}
                  </button>
                ))}
              </div>
            </div>

            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="create-name" className="font-medium">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="create-name"
                required
                placeholder="e.g. Data Analysis Agent"
                value={formData.name}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
              />
            </div>

            {/* Description */}
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="create-desc" className="font-medium">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="create-desc"
                required
                className="min-h-[90px]"
                placeholder="What does this entity do? When should someone use it?"
                value={formData.description}
                onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
              />
            </div>

            {/* Bitbucket Repo */}
            <div className="space-y-2">
              <Label htmlFor="create-repo" className="font-medium">
                Bitbucket Repo URL
              </Label>
              <Input
                id="create-repo"
                placeholder="https://bitbucket.org/..."
                value={formData.bitbucket_repo}
                onChange={(e) => setFormData((p) => ({ ...p, bitbucket_repo: e.target.value }))}
              />
            </div>

            {/* Connection URL */}
            <div className="space-y-2">
              <Label htmlFor="create-url" className="font-medium">
                Connection URL
                <span className="ml-1 text-xs text-muted-foreground">(optional, set after deploy)</span>
              </Label>
              <Input
                id="create-url"
                placeholder="http://my-agent.svc.cluster.local"
                value={formData.url_to_connect}
                onChange={(e) => setFormData((p) => ({ ...p, url_to_connect: e.target.value }))}
              />
            </div>

            {/* How to Use */}
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="create-usage" className="font-medium">
                How to Use
              </Label>
              <Textarea
                id="create-usage"
                className="min-h-[80px]"
                placeholder="Instructions, example prompts, prerequisites..."
                value={formData.how_to_use}
                onChange={(e) => setFormData((p) => ({ ...p, how_to_use: e.target.value }))}
              />
            </div>
          </div>

          <DialogFooter className="mt-6 pt-5 border-t border-border/40 gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createLoading}
              className="gap-1.5 bg-primary text-primary-foreground px-6"
            >
              <Plus size={15} />
              {createLoading ? "Registering…" : "Register Entity"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  // ─── Page render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 p-6 pb-12 w-full flex flex-col">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-extrabold gradient-text tracking-tight mb-2">
            Marketplace
          </h1>
          <p className="text-muted-foreground text-base max-w-xl leading-relaxed">
            Discover, build, and deploy AI Agents and MCP Servers. Eliminate tribal
            knowledge — publish your tools here so the whole team can benefit.
          </p>
        </div>
        <Button
          size="lg"
          className="shrink-0 gap-2 bg-gradient-primary text-primary-foreground shadow-lg hover:shadow-xl transition-all"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus size={18} /> Create Entity
        </Button>
      </div>

      {/* Color legend */}
      <ColorLegend devTtlDays={config.dev_ttl_days} />

      {/* Tabs */}
      <ThemedTabs defaultValue="agents" className="w-full flex-1 flex flex-col">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <ThemedTabsList className="grid grid-cols-3 w-full sm:w-auto sm:min-w-[360px]">
            <ThemedTabsTrigger value="agents" className="py-2.5 text-sm">
              <Zap size={14} className="mr-1.5" />
              Agents
              <span className="ml-1.5 text-[10px] font-bold bg-muted/60 px-1.5 py-0.5 rounded-full">
                {items.filter((i) => i.item_type === "agent").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="mcp-servers" className="py-2.5 text-sm">
              <Blocks size={14} className="mr-1.5" />
              MCP Servers
              <span className="ml-1.5 text-[10px] font-bold bg-muted/60 px-1.5 py-0.5 rounded-full">
                {items.filter((i) => i.item_type === "mcp_server").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="skills" className="py-2.5 text-sm">
              <Sparkles size={14} className="mr-1.5" />
              Skills
            </ThemedTabsTrigger>
          </ThemedTabsList>

          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              className="pl-8 h-9 text-sm"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-6 flex-1">
          <ThemedTabsContent value="agents">
            {renderGrid(
              agents,
              <Zap size={52} />,
              search ? "No agents match your search." : "No agents yet — create one!"
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="mcp-servers">
            {renderGrid(
              mcpServers,
              <Blocks size={52} />,
              search ? "No MCP servers match your search." : "No MCP servers yet — create one!"
            )}
          </ThemedTabsContent>

          <ThemedTabsContent value="skills">
            <div className="flex flex-col items-center justify-center min-h-[420px] border-2 border-dashed border-border/40 rounded-2xl bg-gradient-to-b from-surface/40 to-background">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-5 ring-4 ring-primary/5">
                <Sparkles size={36} className="text-primary/70" />
              </div>
              <h3 className="text-2xl font-bold mb-3">Coming Soon</h3>
              <p className="text-muted-foreground/70 text-base max-w-md text-center leading-relaxed">
                <strong className="text-foreground/60">Skills</strong> will let you compose
                capabilities from multiple Agents and MCP Servers into autonomous
                multi-step workflows — without writing any glue code.
              </p>
              <div className="flex items-center gap-2 mt-5 text-sm text-primary/60">
                <ChevronRight size={14} />
                <span>Stay tuned for the next release</span>
              </div>
            </div>
          </ThemedTabsContent>
        </div>
      </ThemedTabs>

      {/* Modals */}
      <DetailModal />
      <DeployModal />
      <CreateModal />
    </div>
  );
}

// ─── Tiny helper components ───────────────────────────────────────────────────

function InfoTile({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-muted/30 border border-border/40 rounded-xl p-3 flex flex-col gap-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold ${valueClass ?? "text-foreground"}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground/70 mt-0.5">{sub}</p>}
    </div>
  );
}

function StatBig({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div className="flex flex-col items-center">
      <span className={`text-3xl font-extrabold ${color}`}>{value}</span>
      <span className="text-xs text-muted-foreground mt-0.5">{label}</span>
    </div>
  );
}
