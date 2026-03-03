/**
 * Marketplace — the team's internal App Store for AI Agents and MCP Servers.
 *
 * ─── React architecture note ──────────────────────────────────────────────────
 * • Sub-components (ItemCard, EntityIcon, etc.) are defined OUTSIDE this
 *   component so their identity is stable across re-renders.
 * • All three modals are inlined as plain JSX — NOT as nested function
 *   components.  This prevents the "input loses focus on every keystroke" bug.
 * • Each create-form field is a separate useState call, never grouped into a
 *   single object, so typing in one field doesn't touch another field's state.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import React, {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ThemedTabs,
  ThemedTabsList,
  ThemedTabsTrigger,
  ThemedTabsContent,
} from "@/components/ui/themed-tabs";
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
  AlertTriangle,
  Blocks,
  Bot,
  Calendar,
  ChevronRight,
  Circle,
  Clock,
  Cloud,
  Copy,
  Edit3,
  ExternalLink,
  Github,
  PackageSearch,
  Pencil,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Send,
  Sparkles,
  Tag,
  Trash2,
  UploadCloud,
  Users,
  X,
  Zap,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

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
  deployment_status: "BUILT" | "DEPLOYED";
  version: string;
  environment: "dev" | "release";
  chart_name: string | null;
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

// ─── Status / style helpers ────────────────────────────────────────────────────

function getItemStyle(item: MarketplaceItem) {
  if (item.deployment_status === "DEPLOYED") {
    if (item.environment === "release") {
      return {
        topBar: "bg-emerald-500",
        leftBar: "bg-emerald-500",
        ring: "border-emerald-500/50 hover:border-emerald-400/80",
        badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        label: "Deployed · Release", dot: "bg-emerald-500", pulse: true,
        envPill: "bg-sky-500/15 text-sky-400 border-sky-500/25",
      };
    }
    const r = item.ttl_remaining_days;
    if (r !== null && r <= 3) {
      return {
        topBar: "bg-red-500",
        leftBar: "bg-red-500",
        ring: "border-red-500/60 hover:border-red-400/90",
        badge: "bg-red-500/15 text-red-400 border-red-500/30",
        label: "Expiring Soon!", dot: "bg-red-500 animate-pulse", pulse: true,
        envPill: "bg-orange-500/15 text-orange-400 border-orange-500/25",
      };
    }
    if (r !== null && r <= 7) {
      return {
        topBar: "bg-orange-500",
        leftBar: "bg-orange-500",
        ring: "border-orange-500/50 hover:border-orange-400/80",
        badge: "bg-orange-500/15 text-orange-400 border-orange-500/30",
        label: "Deployed · Dev", dot: "bg-orange-400", pulse: false,
        envPill: "bg-orange-500/15 text-orange-400 border-orange-500/25",
      };
    }
    return {
      topBar: "bg-violet-500",
      leftBar: "bg-violet-500",
      ring: "border-violet-500/50 hover:border-violet-400/80",
      badge: "bg-violet-500/15 text-violet-400 border-violet-500/30",
      label: "Deployed · Dev", dot: "bg-violet-500", pulse: true,
      envPill: "bg-orange-500/15 text-orange-400 border-orange-500/25",
    };
  }
  return {
    topBar: "bg-amber-500",
    leftBar: "bg-amber-500",
    ring: "border-amber-500/45 hover:border-amber-400/75",
    badge: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    label: "Built", dot: "bg-amber-500", pulse: false,
    envPill: "bg-slate-500/15 text-slate-400 border-slate-500/25",
  };
}

function ttlCls(r: number | null) {
  if (r === null) return "";
  if (r <= 3) return "bg-red-500/10 text-red-400 border-red-500/20";
  if (r <= 7) return "bg-orange-500/10 text-orange-400 border-orange-500/20";
  return "bg-violet-500/10 text-violet-400 border-violet-500/20";
}

// ─── Sub-components (OUTSIDE main component) ──────────────────────────────────

const EntityIcon = memo(function EntityIcon({
  icon, item_type, size = "md",
}: { icon: string | null; item_type: string; size?: "sm" | "md" | "lg" | "xl" }) {
  const dim = { sm: "w-10 h-10", md: "w-16 h-16", lg: "w-18 h-18", xl: "w-20 h-20" }[size];
  const iconSz = { sm: 16, md: 28, lg: 32, xl: 36 }[size];

  if (icon) {
    return (
      <img src={icon} alt="icon"
        className={`${dim} rounded-2xl object-cover border border-border shrink-0`} />
    );
  }
  return (
    <div className={`${dim} rounded-2xl shrink-0 flex items-center justify-center border border-border
      ${item_type === "agent" ? "bg-sky-500/15" : "bg-violet-500/15"}`}>
      {item_type === "agent"
        ? <Zap size={iconSz} className="text-sky-400" />
        : <Blocks size={iconSz} className="text-violet-400" />}
    </div>
  );
});

const ItemCard = memo(function ItemCard({
  item, onClick,
}: { item: MarketplaceItem; onClick: () => void }) {
  const st = getItemStyle(item);
  const nearExpiry = item.ttl_remaining_days !== null && item.ttl_remaining_days <= 3;

  return (
    <div
      role="button" tabIndex={0} onClick={onClick}
      onKeyDown={e => e.key === "Enter" && onClick()}
      className={`
        group relative cursor-pointer rounded-2xl overflow-hidden flex flex-col
        bg-surface/60 backdrop-blur-sm
        border-2 ${st.ring}
        transition-all duration-200 ease-out min-h-[320px]
        hover:scale-[1.015] hover:shadow-2xl
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60
      `}
    >
      {/* Colored top status bar */}
      <div className={`absolute top-0 inset-x-0 h-[4px] ${st.topBar}`} />

      {/* Near-expiry banner */}
      {nearExpiry && (
        <div className="absolute top-[4px] inset-x-0 flex items-center justify-center gap-1.5 text-[10px] font-bold text-red-400 bg-red-500/10 border-b border-red-500/25 py-1 z-10 tracking-wide">
          <AlertTriangle size={9} className="shrink-0" /> AUTO-DELETE IN {item.ttl_remaining_days}d
        </div>
      )}

      {/* Main content */}
      <div className={`flex flex-col gap-4 p-5 flex-1 ${nearExpiry ? "pt-8" : "pt-6"}`}>

        {/* Icon + name row */}
        <div className="flex items-start gap-3.5">
          <EntityIcon icon={item.icon} item_type={item.item_type} size="md" />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-[15px] leading-snug text-foreground group-hover:text-primary transition-colors truncate">
              {item.name}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              by <span className="font-medium">{item.owner_name}</span>
            </p>
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-muted border border-border px-1.5 py-0.5 rounded text-muted-foreground">
                <Tag size={7} /> v{item.version}
              </span>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${st.envPill}`}>
                {item.environment.toUpperCase()}
              </span>
              {item.deployment_status === "DEPLOYED" && (
                <span className={`flex items-center gap-1 text-[10px] font-bold ${st.badge} px-1.5 py-0.5 rounded border`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${st.pulse ? "animate-pulse" : ""}`} />
                  LIVE
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Description — full-opacity muted text for legibility */}
        <p className="text-sm text-muted-foreground line-clamp-3 leading-relaxed flex-1">
          {item.description}
        </p>

        {/* TTL countdown */}
        {item.deployment_status === "DEPLOYED" && item.environment === "dev" && item.ttl_remaining_days !== null && (
          <div className={`self-start inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-lg border ${ttlCls(item.ttl_remaining_days)}`}>
            <Clock size={11} />
            {item.ttl_remaining_days === 0 ? "Expires today" : `${item.ttl_remaining_days}d left`}
          </div>
        )}

        {/* Chart reference */}
        {item.chart_name && (
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <PackageSearch size={11} className="shrink-0" />
            <span className="truncate font-mono">{item.chart_name}{item.chart_version ? `@${item.chart_version}` : ""}</span>
          </div>
        )}
      </div>

      {/* Footer metrics */}
      <div className="border-t border-border/50 bg-muted/20 px-5 py-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5" title="Total calls">
            <Activity size={11} className="text-primary/70" />
            <span className="font-semibold text-foreground">{item.usage_count.toLocaleString()}</span>
            <span>calls</span>
          </span>
          <span className="flex items-center gap-1.5" title="Unique users">
            <Users size={11} className="text-emerald-500/70" />
            <span className="font-semibold text-foreground">{item.unique_users}</span>
            <span>users</span>
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${st.badge}`}>
          {st.label}
        </span>
      </div>
    </div>
  );
});

function StatusLegend({ devTtlDays }: { devTtlDays: number }) {
  const items = [
    { dot: "bg-amber-500",           label: "Built",         sub: "Ready to deploy" },
    { dot: "bg-violet-500",          label: "Dev Deployed",  sub: `≤${devTtlDays}d TTL` },
    { dot: "bg-orange-500",          label: "Expiring",      sub: "≤7 days left" },
    { dot: "bg-red-500 animate-pulse", label: "Critical",    sub: "≤3 days — auto-delete" },
    { dot: "bg-emerald-500",         label: "Release",       sub: "Persistent" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/30 select-none">
        Status
      </span>
      {items.map(({ dot, label, sub }) => (
        <div key={label} className="flex items-center gap-1.5 text-xs">
          <span className={`w-2 h-2 rounded-full ${dot} shrink-0`} />
          <span className="font-semibold text-foreground/60">{label}</span>
          <span className="text-muted-foreground/35 hidden md:inline">· {sub}</span>
        </div>
      ))}
    </div>
  );
}

function InfoTile({ label, value, sub, valueCls = "", icon }: {
  label: string; value: string; sub?: string; valueCls?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5 bg-white/[0.025] border border-white/[0.06] rounded-xl p-3">
      {icon && <div className="mt-0.5 text-muted-foreground/40 shrink-0">{icon}</div>}
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-0.5">{label}</p>
        <p className={`text-sm font-semibold truncate ${valueCls || "text-foreground/80"}`}>{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground/45 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function StatBig({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className={`text-4xl font-black ${color} tabular-nums leading-none`}>{value.toLocaleString()}</span>
      <span className="text-xs text-muted-foreground/50 font-medium">{label}</span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Marketplace() {
  const { token, user } = useAuth();

  // ── Core state ─────────────────────────────────────────────────────────────
  const [items, setItems] = useState<MarketplaceItem[]>([]);
  const [config, setConfig] = useState<MarketplaceConfig>({ max_agents_per_user: 5, max_mcp_per_user: 5, dev_ttl_days: 10 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // ── Detail modal ───────────────────────────────────────────────────────────
  const [detailItem, setDetailItem] = useState<MarketplaceItem | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editHowTo, setEditHowTo] = useState("");
  const [editRepo, setEditRepo] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  // ── Delete confirmation ────────────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<MarketplaceItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ── Deploy / Redeploy modal ────────────────────────────────────────────────
  const [isDeployOpen, setIsDeployOpen] = useState(false);
  const [isRedeploy, setIsRedeploy] = useState(false);
  const [deployItem, setDeployItem] = useState<MarketplaceItem | null>(null);
  const [deployEnv, setDeployEnv] = useState<"dev" | "release">("dev");
  const [availableCharts, setAvailableCharts] = useState<string[]>([]);
  const [chartsLoading, setChartsLoading] = useState(false);
  const [chartFilter, setChartFilter] = useState("");
  const [selectedChart, setSelectedChart] = useState("");
  const [chartVersions, setChartVersions] = useState<string[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionFilter, setVersionFilter] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("latest");
  const [deployLoading, setDeployLoading] = useState(false);

  // ── Create modal — each field is a separate useState ───────────────────────
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createType, setCreateType] = useState("agent");
  const [createIcon, setCreateIcon] = useState("");
  const [createRepo, setCreateRepo] = useState("");
  const [createHowTo, setCreateHowTo] = useState("");
  const iconInputRef = useRef<HTMLInputElement>(null);

  // ── Run / Call modal ───────────────────────────────────────────────────────
  const [callItem, setCallItem] = useState<MarketplaceItem | null>(null);
  const [callPrompt, setCallPrompt] = useState("");
  const [callResponse, setCallResponse] = useState<string | null>(null);
  const [callError, setCallError] = useState<string | null>(null);
  const [callLoading, setCallLoading] = useState(false);

  // ── API helpers ───────────────────────────────────────────────────────────

  const authHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }), [token]);

  const fetchConfig = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch("/api/marketplace/config", { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) setConfig(await r.json());
    } catch { /* ignore */ }
  }, [token]);

  const fetchItems = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const r = await fetch("/api/marketplace/items", { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) setItems(await r.json());
      else toast.error("Failed to load marketplace items.");
    } catch { toast.error("Network error loading items."); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (token) { fetchConfig(); fetchItems(); }
  }, [token, fetchConfig, fetchItems]);

  // ── Reload when switching agent/mcp tabs ──────────────────────────────────
  const handleTabChange = useCallback((value: string) => {
    if (value === "agents" || value === "mcp-servers") fetchItems();
  }, [fetchItems]);

  // ── Chart loading ─────────────────────────────────────────────────────────

  const loadCharts = useCallback(async (env: "dev" | "release") => {
    setAvailableCharts([]);
    setChartsLoading(true);
    try {
      const r = await fetch(`/api/marketplace/charts?environment=${env}`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) { const d = await r.json(); setAvailableCharts(d.charts ?? []); }
      else setAvailableCharts([]);
    } catch { setAvailableCharts([]); }
    finally { setChartsLoading(false); }
  }, [token]);

  const loadVersions = useCallback(async (chartName: string, env: "dev" | "release") => {
    setChartVersions([]);
    setVersionFilter("");
    setSelectedVersion("latest");
    if (!chartName) return;
    setVersionsLoading(true);
    try {
      const r = await fetch(
        `/api/marketplace/chart-versions?environment=${env}&chart_name=${encodeURIComponent(chartName)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const d = await r.json();
        setChartVersions(d.versions ?? ["latest"]);
        setSelectedVersion(d.versions?.[0] ?? "latest");
      }
    } catch { setChartVersions(["latest"]); setSelectedVersion("latest"); }
    finally { setVersionsLoading(false); }
  }, [token]);

  const openDeploy = useCallback((item: MarketplaceItem, redeploy = false, initialEnv: "dev" | "release" = "dev") => {
    setDeployItem(item);
    setIsRedeploy(redeploy);
    setDeployEnv(initialEnv);
    setChartFilter("");
    setVersionFilter("");
    setSelectedChart("");
    setChartVersions([]);
    setSelectedVersion("latest");
    setIsDeployOpen(true);
    loadCharts(initialEnv);
  }, [loadCharts]);

  const handleDeployEnvChange = useCallback((env: "dev" | "release") => {
    setDeployEnv(env);
    setSelectedChart("");
    setChartVersions([]);
    setSelectedVersion("latest");
    loadCharts(env);
  }, [loadCharts]);

  const handleChartSelect = useCallback((chart: string) => {
    setSelectedChart(chart);
    loadVersions(chart, deployEnv);
  }, [loadVersions, deployEnv]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const resetCreate = useCallback(() => {
    setCreateName(""); setCreateDesc(""); setCreateType("agent");
    setCreateIcon(""); setCreateRepo(""); setCreateHowTo("");
  }, []);

  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    try {
      const r = await fetch("/api/marketplace/items", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          name: createName, description: createDesc, item_type: createType,
          icon: createIcon || null, bitbucket_repo: createRepo || null, how_to_use: createHowTo || null,
        }),
      });
      if (r.ok) {
        toast.success(`${createType === "agent" ? "Agent" : "MCP Server"} published — ready to deploy!`);
        setIsCreateOpen(false);
        resetCreate();
        fetchItems();
      } else {
        const e = await r.json();
        toast.error(e.detail || "Failed to publish entity.");
      }
    } catch { toast.error("Network error."); }
    finally { setCreateLoading(false); }
  }, [createName, createDesc, createType, createIcon, createRepo, createHowTo, authHeaders, fetchItems, resetCreate]);

  const startEdit = useCallback((item: MarketplaceItem) => {
    setEditName(item.name);
    setEditDesc(item.description);
    setEditHowTo(item.how_to_use || "");
    setEditRepo(item.bitbucket_repo || "");
    setEditMode(true);
  }, []);

  const handleSaveEdit = useCallback(async (item: MarketplaceItem) => {
    setEditLoading(true);
    try {
      const r = await fetch(`/api/marketplace/items/${item.id}`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({
          name: editName || undefined,
          description: editDesc || undefined,
          how_to_use: editHowTo || undefined,
          bitbucket_repo: editRepo || undefined,
        }),
      });
      if (r.ok) {
        const updated: MarketplaceItem = await r.json();
        setItems(prev => prev.map(i => i.id === updated.id ? updated : i));
        setDetailItem(updated);
        setEditMode(false);
        toast.success("Changes saved.");
      } else {
        const e = await r.json();
        toast.error(e.detail || "Save failed.");
      }
    } catch { toast.error("Network error."); }
    finally { setEditLoading(false); }
  }, [editName, editDesc, editHowTo, editRepo, authHeaders]);

  const handleDeploy = useCallback(async () => {
    if (!deployItem || !selectedChart) return;
    setDeployLoading(true);
    try {
      const endpoint = isRedeploy ? "/api/marketplace/redeploy" : "/api/marketplace/deploy";
      const r = await fetch(endpoint, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ item_id: deployItem.id, environment: deployEnv, chart_name: selectedChart, chart_version: selectedVersion }),
      });
      if (r.ok) {
        const d = await r.json();
        setItems(prev => prev.map(i => i.id === deployItem.id ? d.item : i));
        toast.success(`${isRedeploy ? "Redeployed" : "Deployed"} to ${deployEnv.toUpperCase()} — ${selectedChart}@${selectedVersion}`);
        setIsDeployOpen(false);
        setDetailItem(null);
      } else {
        const e = await r.json();
        toast.error(e.detail || "Deploy failed.");
      }
    } catch { toast.error("Network error."); }
    finally { setDeployLoading(false); }
  }, [deployItem, deployEnv, selectedChart, selectedVersion, isRedeploy, authHeaders]);

  const handleClone = useCallback(async (item: MarketplaceItem) => {
    try {
      const r = await fetch(`/api/marketplace/items/${item.id}/clone`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) {
        const d = await r.json();
        setItems(prev => [...prev, d]);
        toast.success("Fork created — deploy it independently.");
        setDetailItem(null);
      } else {
        const e = await r.json();
        toast.error(e.detail || "Fork failed.");
      }
    } catch { toast.error("Network error."); }
  }, [token]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      const r = await fetch(`/api/marketplace/items/${deleteTarget.id}`, {
        method: "DELETE", headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setItems(prev => prev.filter(i => i.id !== deleteTarget.id));
        toast.success(`"${deleteTarget.name}" deleted.`);
        setDeleteTarget(null);
        setDetailItem(null);
      } else {
        const e = await r.json();
        toast.error(e.detail || "Delete failed.");
      }
    } catch { toast.error("Network error."); }
    finally { setDeleteLoading(false); }
  }, [deleteTarget, token]);

  const handleCall = useCallback(async () => {
    if (!callItem || !callPrompt.trim()) return;
    setCallLoading(true);
    setCallResponse(null);
    setCallError(null);
    try {
      const r = await fetch(`/api/marketplace/items/${callItem.id}/call`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ prompt: callPrompt }),
      });
      const d = await r.json();
      if (r.ok && d.status === "ok") {
        setCallResponse(typeof d.response === "string" ? d.response : JSON.stringify(d.response, null, 2));
        // Refresh usage counter
        fetchItems();
      } else {
        setCallError(d.error || d.detail || "Unknown error");
      }
    } catch (err) {
      setCallError(String(err));
    } finally { setCallLoading(false); }
  }, [callItem, callPrompt, authHeaders, fetchItems]);

  const handleIconFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1_048_576) { toast.error("Image must be < 1 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => setCreateIcon(reader.result as string);
    reader.readAsDataURL(file);
  }, []);

  // ── Derived state ─────────────────────────────────────────────────────────

  const q = search.toLowerCase();
  const filter = useCallback((arr: MarketplaceItem[]) =>
    q ? arr.filter(i => i.name.toLowerCase().includes(q) || i.description.toLowerCase().includes(q)
      || i.owner_name?.toLowerCase().includes(q) || i.chart_name?.toLowerCase().includes(q)) : arr,
    [q]);

  const agents     = useMemo(() => filter(items.filter(i => i.item_type === "agent")),      [items, filter]);
  const mcpServers = useMemo(() => filter(items.filter(i => i.item_type === "mcp_server")), [items, filter]);

  const isOwnerOrAdmin = useCallback((item: MarketplaceItem) =>
    user?.is_admin || user?.id === item.owner_id, [user]);

  const filteredCharts   = useMemo(() => availableCharts.filter(c => c.toLowerCase().includes(chartFilter.toLowerCase())), [availableCharts, chartFilter]);
  const filteredVersions = useMemo(() => chartVersions.filter(v => v.toLowerCase().includes(versionFilter.toLowerCase())), [chartVersions, versionFilter]);

  const detailSynced = useMemo(
    () => detailItem ? (items.find(i => i.id === detailItem.id) ?? detailItem) : null,
    [detailItem, items]
  );

  const renderGrid = (list: MarketplaceItem[], emptyMsg: string, Icon: React.ElementType) => {
    if (loading) return <div className="flex items-center justify-center h-60"><p className="text-muted-foreground/50 animate-pulse">Loading…</p></div>;
    if (list.length === 0) return (
      <div className="flex flex-col items-center justify-center h-60 border border-dashed border-white/[0.07] rounded-2xl">
        <Icon size={48} className="opacity-10 mb-3" />
        <p className="text-muted-foreground/40 text-sm">{emptyMsg}</p>
      </div>
    );
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 auto-rows-fr">
        {list.map(item => <ItemCard key={item.id} item={item} onClick={() => { setDetailItem(item); setEditMode(false); }} />)}
      </div>
    );
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-5 p-6 pb-16 min-h-full">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black gradient-text tracking-tight mb-2">Marketplace</h1>
          <p className="text-muted-foreground/60 text-sm max-w-lg leading-relaxed">
            Your team's internal app store for AI. Publish Agents and MCP Servers once —
            discover, deploy, and use them without tribal knowledge.
          </p>
        </div>
        <Button size="lg" onClick={() => setIsCreateOpen(true)}
          className="shrink-0 gap-2 bg-gradient-primary text-primary-foreground shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all hover:scale-[1.02] font-bold">
          <Plus size={17} /> Publish Entity
        </Button>
      </div>

      <StatusLegend devTtlDays={config.dev_ttl_days} />

      {/* Tabs */}
      <ThemedTabs defaultValue="agents" className="flex-1 flex flex-col" onValueChange={handleTabChange}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <ThemedTabsList className="grid grid-cols-3 sm:w-auto sm:min-w-[380px]">
            <ThemedTabsTrigger value="agents" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Zap size={13} /> Agents
              <span className="ml-1 text-[10px] font-black bg-white/5 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "agent").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="mcp-servers" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Blocks size={13} /> MCP Servers
              <span className="ml-1 text-[10px] font-black bg-white/5 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "mcp_server").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="skills" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Sparkles size={13} /> Skills
            </ThemedTabsTrigger>
          </ThemedTabsList>
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <Input className="pl-8 h-9 text-sm bg-white/[0.03] border-white/[0.08]"
              placeholder="Search by name, owner, chart…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>

        <div className="mt-5 flex-1">
          <ThemedTabsContent value="agents">{renderGrid(agents, "No agents yet — publish the first one!", Zap)}</ThemedTabsContent>
          <ThemedTabsContent value="mcp-servers">{renderGrid(mcpServers, "No MCP servers yet.", Blocks)}</ThemedTabsContent>
          <ThemedTabsContent value="skills">
            <div className="flex flex-col items-center justify-center min-h-[420px] border border-dashed border-white/[0.07] rounded-2xl bg-gradient-to-b from-surface/20 to-background">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center mb-5">
                <Sparkles size={34} className="text-primary/60" />
              </div>
              <h3 className="text-2xl font-black mb-3">Coming Soon</h3>
              <p className="text-muted-foreground/50 text-sm max-w-md text-center leading-relaxed">
                Skills will let you compose Agents and MCP Servers into autonomous multi-step pipelines — without any glue code.
              </p>
              <div className="flex items-center gap-2 mt-5 text-xs text-primary/40">
                <ChevronRight size={12} /> Coming in the next release
              </div>
            </div>
          </ThemedTabsContent>
        </div>
      </ThemedTabs>

      {/* ══════════════════════════════════════════════════════════════════════
          DETAIL MODAL (inlined JSX)
          ══════════════════════════════════════════════════════════════════════ */}
      <Dialog open={!!detailSynced} onOpenChange={open => { if (!open) { setDetailItem(null); setEditMode(false); } }}>
        <DialogContent className="sm:max-w-[760px] max-h-[92vh] overflow-y-auto p-0">
          {detailSynced && (() => {
            const item = detailSynced;
            const st = getItemStyle(item);
            const canManage = isOwnerOrAdmin(item);
            return (
              <>
                <div className={`h-[3px] w-full ${st.topBar}`} />
                {/* Header */}
                <div className="px-7 pt-5 pb-4 border-b border-white/[0.06]">
                  <div className="flex items-start gap-4">
                    <EntityIcon icon={item.icon} item_type={item.item_type} size="xl" />
                    <div className="flex-1 min-w-0">
                      {editMode ? (
                        <Input value={editName} onChange={e => setEditName(e.target.value)}
                          className="text-xl font-black bg-white/[0.04] border-white/[0.1] mb-2" />
                      ) : (
                        <DialogTitle className="text-2xl font-black leading-tight">{item.name}</DialogTitle>
                      )}
                      <DialogDescription className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                        <span>by <strong className="text-foreground/60">{item.owner_name}</strong></span>
                        <span className={`font-bold px-2 py-0.5 rounded-full border ${st.badge}`}>{st.label}</span>
                        <span className={`font-bold px-2 py-0.5 rounded-full border text-[10px] ${st.envPill}`}>{item.environment.toUpperCase()}</span>
                        {item.deployment_status === "DEPLOYED" && (
                          <span className="flex items-center gap-1 text-emerald-400 text-[10px] font-bold">
                            <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${st.pulse ? "animate-pulse" : ""}`} /> LIVE
                          </span>
                        )}
                      </DialogDescription>
                    </div>
                    {canManage && !editMode && (
                      <Button size="sm" variant="ghost" className="shrink-0 gap-1.5 text-muted-foreground hover:text-foreground"
                        onClick={() => startEdit(item)}>
                        <Pencil size={13} /> Edit
                      </Button>
                    )}
                    {editMode && (
                      <Button size="sm" variant="ghost" className="shrink-0 text-muted-foreground"
                        onClick={() => setEditMode(false)}>
                        <X size={14} />
                      </Button>
                    )}
                  </div>
                </div>

                {/* Body */}
                <div className="px-7 py-5 space-y-4">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1.5">Description</p>
                    {editMode
                      ? <Textarea value={editDesc} onChange={e => setEditDesc(e.target.value)}
                          className="min-h-[80px] bg-white/[0.03] border-white/[0.08] resize-none" />
                      : <p className="text-sm text-muted-foreground/70 bg-white/[0.02] border border-white/[0.05] rounded-xl p-4 leading-relaxed">{item.description}</p>}
                  </div>

                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1.5">How to Use</p>
                    {editMode
                      ? <Textarea value={editHowTo} onChange={e => setEditHowTo(e.target.value)}
                          className="min-h-[72px] bg-white/[0.03] border-white/[0.08] resize-none"
                          placeholder="Example prompts, prerequisites…" />
                      : item.how_to_use
                        ? <p className="text-sm text-muted-foreground/70 bg-primary/[0.03] border border-primary/[0.12] rounded-xl p-4 leading-relaxed">{item.how_to_use}</p>
                        : <p className="text-sm text-muted-foreground/30 italic">Not provided.</p>}
                  </div>

                  {editMode && (
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1.5">Repo URL</p>
                      <Input value={editRepo} onChange={e => setEditRepo(e.target.value)}
                        placeholder="https://bitbucket.company.internal/…"
                        className="bg-white/[0.03] border-white/[0.08]" />
                    </div>
                  )}

                  {!editMode && (
                    <div className="grid grid-cols-2 gap-2.5">
                      <InfoTile label="Chart" icon={<PackageSearch size={14} />}
                        value={item.chart_name ?? "Not deployed yet"}
                        sub={item.chart_version ? `version ${item.chart_version}` : undefined} />
                      <InfoTile label="TTL / Persistence" icon={<Clock size={14} />}
                        value={item.environment === "release" ? "Persistent (no TTL)" : `Dev · ${item.ttl_days ?? config.dev_ttl_days}d TTL`}
                        valueCls={item.ttl_remaining_days !== null && item.ttl_remaining_days <= 3 ? "text-red-400" : ""}
                        sub={item.ttl_remaining_days !== null ? `${item.ttl_remaining_days} days remaining` : undefined} />
                      {item.bitbucket_repo && (
                        <div className="flex items-start gap-2.5 bg-white/[0.025] border border-white/[0.06] rounded-xl p-3">
                          <Github size={14} className="mt-0.5 text-muted-foreground/40 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-0.5">Repository</p>
                            <a href={item.bitbucket_repo} target="_blank" rel="noreferrer"
                              className="text-sm text-primary hover:underline truncate block">View Source ↗</a>
                          </div>
                        </div>
                      )}
                      {item.url_to_connect && (
                        <div className="flex items-start gap-2.5 bg-white/[0.025] border border-white/[0.06] rounded-xl p-3">
                          <ExternalLink size={14} className="mt-0.5 text-muted-foreground/40 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-0.5">Connection URL</p>
                            <a href={item.url_to_connect} target="_blank" rel="noreferrer"
                              className="text-sm text-primary hover:underline truncate block">{item.url_to_connect}</a>
                          </div>
                        </div>
                      )}
                      <InfoTile label="Created" icon={<Calendar size={14} />}
                        value={new Date(item.created_at).toLocaleDateString()} />
                      {(item.tools_exposed?.length ?? 0) > 0 && (
                        <InfoTile label="Tools Exposed" icon={<Blocks size={14} />}
                          value={item.tools_exposed.map(t => t.name).join(", ")} />
                      )}
                    </div>
                  )}

                  {!editMode && (
                    <div className="flex gap-10 pt-4 border-t border-white/[0.05]">
                      <StatBig value={item.usage_count} label="Total Calls" color="text-primary" />
                      <StatBig value={item.unique_users} label="Unique Users" color="text-emerald-400" />
                      {(item.tools_exposed?.length ?? 0) > 0 && (
                        <StatBig value={item.tools_exposed.length} label="Tools" color="text-violet-400" />
                      )}
                    </div>
                  )}
                </div>

                {/* Footer actions */}
                <div className="px-7 py-4 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-3 bg-black/10">
                  {editMode ? (
                    <div className="flex gap-2 w-full justify-end">
                      <Button variant="outline" size="sm" onClick={() => setEditMode(false)}>Cancel</Button>
                      <Button size="sm" disabled={editLoading}
                        className="bg-primary text-primary-foreground gap-1.5"
                        onClick={() => handleSaveEdit(item)}>
                        {editLoading ? "Saving…" : "Save Changes"}
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="flex gap-2">
                        {canManage && (
                          <Button variant="destructive" size="sm" className="gap-1.5"
                            onClick={() => setDeleteTarget(item)}>
                            <Trash2 size={13} /> Delete
                          </Button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 justify-end">
                        {canManage && item.deployment_status === "BUILT" && (<>
                          <Button size="sm" variant="outline"
                            className="gap-1.5 border-violet-500/30 text-violet-400 hover:bg-violet-600 hover:text-white hover:border-violet-600"
                            onClick={() => { setDetailItem(null); openDeploy(item, false, "dev"); }}>
                            <Cloud size={13} /> Deploy Dev
                          </Button>
                          <Button size="sm" variant="outline"
                            className="gap-1.5 border-emerald-500/30 text-emerald-400 hover:bg-emerald-600 hover:text-white hover:border-emerald-600"
                            onClick={() => { setDetailItem(null); openDeploy(item, false, "release"); }}>
                            <Rocket size={13} /> Deploy Release
                          </Button>
                        </>)}
                        {canManage && item.deployment_status === "DEPLOYED" && (
                          <Button size="sm" variant="outline"
                            className="gap-1.5 border-amber-500/30 text-amber-400 hover:bg-amber-600 hover:text-white hover:border-amber-600"
                            onClick={() => { setDetailItem(null); openDeploy(item, true, item.environment as "dev" | "release"); }}>
                            <RefreshCw size={13} /> Redeploy
                          </Button>
                        )}
                        {canManage && (item.deployment_status === "BUILT" || item.deployment_status === "DEPLOYED") && (
                          <Button size="sm" variant="outline" className="gap-1.5"
                            onClick={() => handleClone(item)}>
                            <Copy size={13} /> Fork
                          </Button>
                        )}
                        {item.deployment_status === "DEPLOYED" && (
                          <Button size="sm" className="gap-1.5 bg-primary text-primary-foreground"
                            onClick={() => { setDetailItem(null); setCallItem(item); setCallPrompt(""); setCallResponse(null); setCallError(null); }}>
                            <Zap size={13} /> Run / Call
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════════════
          DELETE CONFIRMATION DIALOG
          ══════════════════════════════════════════════════════════════════════ */}
      <Dialog open={!!deleteTarget} onOpenChange={open => { if (!open) setDeleteTarget(null); }}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle size={18} /> Delete "{deleteTarget?.name}"?
            </DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-3 mt-2">
                <p>This action cannot be undone. The following will happen:</p>
                <ul className="space-y-1.5 text-sm">
                  <li className="flex items-start gap-2">
                    <span className="text-destructive mt-0.5">•</span>
                    The item will be <strong>permanently removed</strong> from the Marketplace database.
                  </li>
                  {deleteTarget?.deployment_status === "DEPLOYED" && (
                    <li className="flex items-start gap-2">
                      <span className="text-destructive mt-0.5">•</span>
                      The deployment in the <strong>{deleteTarget.environment.toUpperCase()}</strong> cluster will be <strong>undeployed</strong> (when the infrastructure API is active).
                    </li>
                  )}
                  <li className="flex items-start gap-2">
                    <span className="text-destructive mt-0.5">•</span>
                    All usage history for this entity will also be deleted.
                  </li>
                </ul>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 mt-2">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" disabled={deleteLoading} onClick={handleDelete} className="gap-1.5">
              <Trash2 size={13} />
              {deleteLoading ? "Deleting…" : deleteTarget?.deployment_status === "DEPLOYED" ? "Delete & Undeploy" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════════════
          DEPLOY / REDEPLOY MODAL
          ══════════════════════════════════════════════════════════════════════ */}
      <Dialog open={isDeployOpen} onOpenChange={setIsDeployOpen}>
        <DialogContent className="sm:max-w-[580px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-black text-lg">
              {isRedeploy ? <RefreshCw size={17} className="text-amber-400" /> : <Rocket size={17} className="text-violet-400" />}
              {isRedeploy ? "Redeploy" : "Deploy"} — {deployItem?.name}
            </DialogTitle>
            <DialogDescription>Select environment, chart, and version from your Artifactory registry.</DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-1">
            {/* Environment */}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-2">Environment</p>
              <div className="grid grid-cols-2 gap-2">
                {(["dev", "release"] as const).map(env => (
                  <button key={env} type="button" onClick={() => handleDeployEnvChange(env)}
                    className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                      deployEnv === env
                        ? env === "dev" ? "border-violet-500 bg-violet-500/10 text-violet-400" : "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                        : "border-white/[0.08] text-muted-foreground/60 hover:border-white/[0.15]"
                    }`}>
                    {env === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
                    {env === "dev" ? "Dev" : "Release"}
                  </button>
                ))}
              </div>
              {deployEnv === "dev" && (
                <p className="text-xs text-violet-400/60 mt-2 flex items-center gap-1.5">
                  <Clock size={10} /> Auto-expires after {config.dev_ttl_days} days
                </p>
              )}
            </div>

            {/* Chart picker */}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-2">
                Chart from Artifactory ({deployEnv === "dev" ? "my-helm-dev-local" : "my-helm-release-local"})
              </p>
              <div className="relative mb-2">
                <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                <Input className="pl-7 h-8 text-sm bg-white/[0.03] border-white/[0.08]"
                  placeholder="Filter charts…" value={chartFilter} onChange={e => setChartFilter(e.target.value)} />
              </div>
              <div className="border border-white/[0.08] rounded-xl overflow-hidden max-h-44 overflow-y-auto bg-black/20">
                {chartsLoading
                  ? <p className="text-center text-muted-foreground/40 text-xs py-8 animate-pulse">Loading charts…</p>
                  : filteredCharts.length === 0
                    ? <p className="text-center text-muted-foreground/40 text-xs py-8">No charts found</p>
                    : filteredCharts.map(chart => (
                      <button key={chart} type="button" onClick={() => handleChartSelect(chart)}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2.5 transition-colors ${
                          selectedChart === chart ? "bg-primary/15 text-primary font-semibold" : "hover:bg-white/[0.04] text-foreground/65"
                        }`}>
                        <PackageSearch size={12} className="text-muted-foreground/40 shrink-0" />
                        <span className="font-mono truncate">{chart}</span>
                        {selectedChart === chart && <span className="ml-auto text-primary text-xs">✓</span>}
                      </button>
                    ))}
              </div>
            </div>

            {/* Versions */}
            {selectedChart && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40 mb-2">
                  Version — <span className="text-primary normal-case font-semibold">{selectedChart}</span>
                </p>
                <div className="relative mb-2">
                  <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
                  <Input className="pl-7 h-8 text-sm bg-white/[0.03] border-white/[0.08]"
                    placeholder="Filter versions…" value={versionFilter} onChange={e => setVersionFilter(e.target.value)} />
                </div>
                {versionsLoading
                  ? <p className="text-xs text-muted-foreground/40 animate-pulse">Loading versions…</p>
                  : filteredVersions.length === 0
                    ? <p className="text-xs text-muted-foreground/40">No versions found</p>
                    : <div className="flex flex-wrap gap-2">
                        {filteredVersions.map(v => (
                          <button key={v} type="button" onClick={() => setSelectedVersion(v)}
                            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold transition-all ${
                              selectedVersion === v ? "border-primary bg-primary/15 text-primary" : "border-white/[0.08] text-muted-foreground/60 hover:border-white/[0.2]"
                            }`}>{v}
                          </button>
                        ))}
                      </div>}
              </div>
            )}

            {/* Summary */}
            {selectedChart && selectedVersion && (
              <div className={`flex items-start gap-3 p-3 rounded-xl border text-sm ${
                deployEnv === "dev" ? "bg-violet-500/8 border-violet-500/20 text-violet-300" : "bg-emerald-500/8 border-emerald-500/20 text-emerald-300"
              }`}>
                {deployEnv === "dev" ? <Cloud size={14} className="mt-0.5 shrink-0" /> : <Rocket size={14} className="mt-0.5 shrink-0" />}
                <div>
                  <strong>{isRedeploy ? "Redeploying" : "Deploying"}</strong>{" "}
                  <code className="text-xs bg-black/20 px-1 rounded">{selectedChart}@{selectedVersion}</code>{" "}
                  to <strong>{deployEnv.toUpperCase()}</strong>.
                  {deployEnv === "dev" && <span className="text-[11px] block mt-0.5 opacity-60">Auto-expires in {config.dev_ttl_days} days.</span>}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsDeployOpen(false)}>Cancel</Button>
            <Button disabled={!selectedChart || !selectedVersion || deployLoading} onClick={handleDeploy}
              className={`gap-1.5 font-bold ${deployEnv === "dev" ? "bg-violet-600 hover:bg-violet-500 text-white" : "bg-emerald-600 hover:bg-emerald-500 text-white"}`}>
              {deployEnv === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
              {deployLoading ? "Working…" : isRedeploy ? "Redeploy" : "Deploy"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════════════
          RUN / CALL DIALOG
          ══════════════════════════════════════════════════════════════════════ */}
      <Dialog open={!!callItem} onOpenChange={open => { if (!open) { setCallItem(null); setCallPrompt(""); setCallResponse(null); setCallError(null); } }}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-black">
              <Zap size={17} className="text-primary" /> Test — {callItem?.name}
            </DialogTitle>
            <DialogDescription>
              Send a prompt to this {callItem?.item_type === "agent" ? "agent" : "MCP server"}.
              The request is proxied through the portal to its internal connection URL.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            {callItem?.url_to_connect ? (
              <p className="text-xs text-muted-foreground/50 font-mono bg-white/[0.02] border border-white/[0.06] rounded-lg px-3 py-2 truncate">
                {callItem.url_to_connect}
              </p>
            ) : (
              <div className="flex items-center gap-2 text-sm text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                <AlertTriangle size={14} /> No connection URL — redeploy to assign one.
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">Prompt</Label>
              <Textarea
                className="min-h-[100px] bg-white/[0.03] border-white/[0.08] resize-none font-mono text-sm"
                placeholder={`Send a message to ${callItem?.name}…`}
                value={callPrompt}
                onChange={e => setCallPrompt(e.target.value)}
              />
            </div>

            {callResponse !== null && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400/60 mb-1.5">Response</p>
                <pre className="text-xs text-foreground/70 bg-black/25 border border-white/[0.06] rounded-xl p-4 overflow-auto max-h-60 whitespace-pre-wrap font-mono leading-relaxed">
                  {callResponse}
                </pre>
              </div>
            )}
            {callError && (
              <div className="flex items-start gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <span>{callError}</span>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => { setCallItem(null); setCallPrompt(""); setCallResponse(null); setCallError(null); }}>
              Close
            </Button>
            <Button disabled={callLoading || !callPrompt.trim() || !callItem?.url_to_connect}
              onClick={handleCall} className="gap-1.5 bg-primary text-primary-foreground font-bold">
              <Send size={13} /> {callLoading ? "Sending…" : "Send Prompt"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════════════
          CREATE / PUBLISH MODAL
          ══════════════════════════════════════════════════════════════════════ */}
      <Dialog open={isCreateOpen} onOpenChange={open => { if (!open) { setIsCreateOpen(false); resetCreate(); } }}>
        <DialogContent className="sm:max-w-[740px] max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl font-black">
              <Sparkles size={19} className="text-primary" /> Publish New Entity
            </DialogTitle>
            <DialogDescription>
              Register an Agent or MCP Server. It will immediately be <strong>BUILT</strong> and ready to deploy.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreate} className="mt-3 space-y-5">
            {/* Icon upload */}
            <div className="flex items-start gap-5 p-4 rounded-2xl border border-white/[0.06] bg-white/[0.015]">
              <div onClick={() => iconInputRef.current?.click()}
                className="w-20 h-20 rounded-2xl border-2 border-dashed border-white/10 bg-black/20 flex items-center justify-center cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-all shrink-0 overflow-hidden group">
                {createIcon
                  ? <img src={createIcon} alt="preview" className="w-full h-full object-cover" />
                  : <div className="flex flex-col items-center gap-1 text-muted-foreground/20 group-hover:text-muted-foreground/50 transition-colors">
                      <UploadCloud size={20} /><span className="text-[9px] font-medium">Icon</span>
                    </div>}
              </div>
              <input ref={iconInputRef} type="file" accept="image/*" className="hidden" onChange={handleIconFile} />
              <div className="flex-1">
                <p className="text-sm font-semibold mb-1 text-foreground/70">Entity Icon</p>
                <p className="text-xs text-muted-foreground/40 mb-3">PNG / JPG / SVG · max 1 MB · stored in database</p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={() => iconInputRef.current?.click()}>
                    <UploadCloud size={11} />{createIcon ? "Change" : "Choose"}
                  </Button>
                  {createIcon && <Button type="button" variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={() => setCreateIcon("")}>Remove</Button>}
                </div>
              </div>
            </div>

            {/* Type + Name */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">
                  Type <span className="text-destructive">*</span>
                </Label>
                <div className="grid grid-cols-2 gap-2">
                  {(["agent", "mcp_server"] as const).map(t => (
                    <button key={t} type="button" onClick={() => setCreateType(t)}
                      className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                        createType === t ? "border-primary bg-primary/10 text-primary" : "border-white/[0.08] text-muted-foreground/50 hover:border-white/[0.15]"
                      }`}>
                      {t === "agent" ? <Zap size={13} /> : <Blocks size={13} />}
                      {t === "agent" ? "Agent" : "MCP"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input id="cn" required placeholder="e.g. Jira Integration MCP"
                  className="bg-white/[0.03] border-white/[0.08]"
                  value={createName} onChange={e => setCreateName(e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cd" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea id="cd" required className="min-h-[80px] bg-white/[0.03] border-white/[0.08] resize-none"
                placeholder="What does this entity do? When should someone use it?"
                value={createDesc} onChange={e => setCreateDesc(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="cr" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">Bitbucket Repo URL</Label>
              <Input id="cr" placeholder="https://bitbucket.company.internal/…"
                className="bg-white/[0.03] border-white/[0.08]"
                value={createRepo} onChange={e => setCreateRepo(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ch" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">How to Use</Label>
              <Textarea id="ch" className="min-h-[72px] bg-white/[0.03] border-white/[0.08] resize-none"
                placeholder="Example prompts, prerequisites, example inputs…"
                value={createHowTo} onChange={e => setCreateHowTo(e.target.value)} />
            </div>

            <DialogFooter className="pt-4 border-t border-white/[0.05] gap-2">
              <Button type="button" variant="outline" onClick={() => { setIsCreateOpen(false); resetCreate(); }}>Cancel</Button>
              <Button type="submit" disabled={createLoading || !createName.trim() || !createDesc.trim()}
                className="gap-1.5 bg-gradient-primary text-primary-foreground font-bold px-6">
                <Plus size={14} />{createLoading ? "Publishing…" : "Publish Entity"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
