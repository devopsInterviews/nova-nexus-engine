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
import { motion } from "framer-motion";
import { useSearchParams } from "react-router-dom";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/context/auth-context";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Blocks,
  Calendar,
  ChevronRight,
  Clock,
  Cloud,
  Copy,
  ExternalLink,
  Filter,
  Github,
  Info,
  PackageSearch,
  Pencil,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Send,
  Sparkles,
  Store,
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

/**
 * Status categories for filtering:
 * - "built"     → BUILT (not deployed)
 * - "deployed"  → DEPLOYED dev, TTL > 7 days
 * - "expiring"  → DEPLOYED dev, TTL ≤ 7 days (replaces old "critical" + "expiring")
 * - "release"   → DEPLOYED release (persistent, no TTL)
 */
type StatusFilter = "all" | "built" | "deployed" | "expiring" | "release";

function getStatusCategory(item: MarketplaceItem): Exclude<StatusFilter, "all"> {
  if (item.deployment_status === "BUILT") return "built";
  if (item.environment === "release") return "release";
  const r = item.ttl_remaining_days;
  if (r !== null && r <= 7) return "expiring";
  return "deployed";
}

function getItemStyle(item: MarketplaceItem) {
  /* Neutral card border — no per-status frame coloring */
  const ring = "border-border/50 hover:border-border/80";

  if (item.deployment_status === "DEPLOYED") {
    if (item.environment === "release") {
      return {
        topBar: "bg-[#00C986]",          /* Deployed — palette success green */
        leftBar: "bg-[#00C986]",
        ring,
        badge: "bg-[#00C986]/10 text-[#007a52] border-[#00C986]/35 dark:bg-[#00C986]/20 dark:text-[#00C986] dark:border-[#00C986]/40",
        label: "Release", dot: "bg-[#00C986]", pulse: true,
        envPill: "bg-[#55C5E2]/10 text-[#1a7a96] border-[#55C5E2]/35 dark:bg-[#55C5E2]/20 dark:text-[#55C5E2] dark:border-[#55C5E2]/40",
        hoverShadow: "hover:shadow-[0_12px_32px_rgba(0,201,134,0.18)]",
      };
    }
    const r = item.ttl_remaining_days;
    /* ≤7 days: Expiring — palette error/expiring color */
    if (r !== null && r <= 7) {
      return {
        topBar: "bg-[#F16C6C]",
        leftBar: "bg-[#F16C6C]",
        ring,
        badge: "bg-[#F16C6C]/10 text-[#c03232] border-[#F16C6C]/35 dark:bg-[#F16C6C]/20 dark:text-[#F16C6C] dark:border-[#F16C6C]/40",
        label: "Expiring", dot: "bg-[#F16C6C] animate-pulse", pulse: true,
        envPill: "bg-[#FFB24C]/10 text-[#935900] border-[#FFB24C]/35 dark:bg-[#FFB24C]/20 dark:text-[#FFB24C] dark:border-[#FFB24C]/40",
        hoverShadow: "hover:shadow-[0_12px_32px_rgba(241,108,108,0.18)]",
      };
    }
    /* Dev deployed (healthy) — palette warning orange */
    return {
      topBar: "bg-[#FFB24C]",
      leftBar: "bg-[#FFB24C]",
      ring,
      badge: "bg-[#FFB24C]/10 text-[#935900] border-[#FFB24C]/35 dark:bg-[#FFB24C]/20 dark:text-[#FFB24C] dark:border-[#FFB24C]/40",
      label: "Dev Deployed", dot: "bg-[#FFB24C]", pulse: true,
      envPill: "bg-[#FFB24C]/10 text-[#935900] border-[#FFB24C]/35 dark:bg-[#FFB24C]/20 dark:text-[#FFB24C] dark:border-[#FFB24C]/40",
      hoverShadow: "hover:shadow-[0_12px_32px_rgba(255,178,76,0.18)]",
    };
  }
  /* Built — palette built/yellow */
  return {
    topBar: "bg-[#FFE64C]",
    leftBar: "bg-[#FFE64C]",
    ring,
    badge: "bg-[#FFE64C]/20 text-[#7a6200] border-[#FFE64C]/50 dark:bg-[#FFE64C]/15 dark:text-[#FFE64C] dark:border-[#FFE64C]/40",
    label: "Built", dot: "bg-[#FFE64C]", pulse: false,
    envPill: "bg-border/30 text-muted-foreground border-border/50 dark:bg-muted/20 dark:text-muted-foreground dark:border-border/40",
    hoverShadow: "hover:shadow-[0_12px_32px_rgba(255,230,76,0.18)]",
  };
}

function ttlCls(r: number | null) {
  if (r === null) return "";
  if (r <= 7) return "bg-[#F16C6C]/10 text-[#c03232] border-[#F16C6C]/35 dark:bg-[#F16C6C]/15 dark:text-[#F16C6C] dark:border-[#F16C6C]/30";
  return "bg-[#FFB24C]/10 text-[#935900] border-[#FFB24C]/40 dark:bg-[#FFB24C]/15 dark:text-[#FFB24C] dark:border-[#FFB24C]/30";
}

// ─── Sub-components (OUTSIDE main component) ──────────────────────────────────

const EntityIcon = memo(function EntityIcon({
  icon, item_type, size = "md",
}: { icon: string | null; item_type: string; size?: "sm" | "md" | "lg" | "xl" }) {
  const dim = { sm: "w-8 h-8", md: "w-10 h-10", lg: "w-16 h-16", xl: "w-20 h-20" }[size];
  const iconSz = { sm: 14, md: 18, lg: 28, xl: 34 }[size];

  if (icon) {
    return (
      <img src={icon} alt="icon"
        className={`${dim} rounded-xl object-cover border border-border/50 shrink-0 shadow-lg`} />
    );
  }
  return (
    <div className={`${dim} rounded-xl shrink-0 flex items-center justify-center shadow-lg bg-gradient-primary`}>
      {item_type === "agent"
        ? <Zap size={iconSz} className="text-white" />
        : <Blocks size={iconSz} className="text-white" />}
    </div>
  );
});

/**
 * ItemCard — consistent card layout with equal heights via flex-col structure.
 * The AUTO-DELETE banner has been removed to prevent height inconsistency.
 */
const ItemCard = memo(function ItemCard({
  item, onClick,
}: { item: MarketplaceItem; onClick: () => void }) {
  const st = getItemStyle(item);

  return (
    <motion.div
      role="button" tabIndex={0} onClick={onClick}
      onKeyDown={e => e.key === "Enter" && onClick()}
      className={`
        relative cursor-pointer rounded-2xl border ${st.ring} overflow-hidden flex flex-col
        transition-shadow duration-300 ${st.hoverShadow}
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60
      `}
      style={{ background: "hsl(var(--surface) / 0.8)" }}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
    >
      {/* Status-colored top stripe — no full border frame */}
      <div className={`h-1.5 w-full ${st.topBar} rounded-t-2xl`} />

      {/* Main content */}
      <div className="p-6 flex-1 flex flex-col">
        {/* Icon */}
        {item.icon ? (
          <img src={item.icon} alt="icon"
            className="w-10 h-10 rounded-xl object-cover border border-border/30 shadow-lg mb-3 shrink-0" />
        ) : (
          <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center shadow-lg mb-3 shrink-0">
            {item.item_type === "agent" ? <Zap className="w-5 h-5 text-white" /> : <Blocks className="w-5 h-5 text-white" />}
          </div>
        )}

        {/* Owner tagline */}
        <p className="text-xs text-muted-foreground mb-1">
          by <span className="font-semibold">{item.owner_name}</span>
        </p>

        {/* Title */}
        <h3 className="text-lg font-bold text-foreground mb-2 leading-snug">
          {item.name}
        </h3>

        {/* Description */}
        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3 flex-1">
          {item.description}
        </p>

        {/* Status + environment badges */}
        <div className="flex flex-wrap items-center gap-1.5 mt-4">
          {item.deployment_status === "DEPLOYED" ? (
            <span className={`flex items-center gap-1 text-[10px] font-bold ${st.badge} px-2.5 py-1 rounded-full border`}>
              <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${st.pulse ? "animate-pulse" : ""}`} />
              RUNNING
            </span>
          ) : (
            <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${st.badge}`}>BUILT</span>
          )}
          <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${st.envPill}`}>
            {item.environment === "release" ? "RELEASE" : "DEV"}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground/50 bg-muted/30 border border-border/30 px-1.5 py-0.5 rounded">
            <Tag size={7} className="inline mr-0.5 opacity-60" />v{item.version}
          </span>
        </div>

        {/* TTL info (no banner — just inline badge) */}
        {item.deployment_status === "DEPLOYED" && item.environment !== "release" && item.ttl_remaining_days !== null ? (
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-lg border ${ttlCls(item.ttl_remaining_days)}`}>
              <Clock size={10} />
              {item.ttl_remaining_days === 0 ? "Expires today" : `${item.ttl_remaining_days}d left`}
            </span>
            {item.chart_name && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/45 font-mono">
                <PackageSearch size={10} />
                <span className="truncate max-w-[120px]">{item.chart_name}</span>
              </span>
            )}
          </div>
        ) : item.deployment_status === "DEPLOYED" && item.environment === "release" ? (
          <div className="mt-3">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-lg border bg-[#00C986]/10 text-[#007a52] border-[#00C986]/35 dark:bg-[#00C986]/15 dark:text-[#00C986] dark:border-[#00C986]/30">
              <Sparkles size={9} /> Persistent · No expiry
            </span>
          </div>
        ) : item.chart_name ? (
          <div className="mt-3">
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/45 font-mono">
              <PackageSearch size={10} />
              <span className="truncate max-w-[120px]">{item.chart_name}</span>
            </span>
          </div>
        ) : null}
      </div>

      {/* Footer stats */}
      <div className="border-t border-border/40 px-6 py-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Activity size={11} className="text-primary/70" />
            <span className="font-semibold text-foreground">{item.usage_count.toLocaleString()}</span>
            calls
          </span>
          <span className="flex items-center gap-1.5">
            <Users size={11} className="text-[#00C986]/80" />
            <span className="font-semibold text-foreground">{item.unique_users}</span>
            users
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${st.badge}`}>
          {st.label}
        </span>
      </div>
    </motion.div>
  );
});

// Status filter button component
function StatusFilterButton({
  active, dot, label, count, onClick,
}: { active: boolean; dot: string; label: string; count?: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border transition-all ${
        active
          ? "border-primary/50 bg-primary/10 text-foreground font-semibold"
          : "border-border/50 text-muted-foreground/70 hover:border-border hover:text-foreground"
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${dot} shrink-0`} />
      <span>{label}</span>
      {count !== undefined && (
        <span className={`text-[9px] font-black px-1 py-0 rounded ${active ? "bg-primary/20" : "bg-muted/40"}`}>
          {count}
        </span>
      )}
    </button>
  );
}

function StatusLegend({
  devTtlDays,
  items,
  statusFilter,
  onFilterChange,
}: {
  devTtlDays: number;
  items: MarketplaceItem[];
  statusFilter: StatusFilter;
  onFilterChange: (f: StatusFilter) => void;
}) {
  const counts = {
    all: items.length,
    built: items.filter(i => getStatusCategory(i) === "built").length,
    deployed: items.filter(i => getStatusCategory(i) === "deployed").length,
    expiring: items.filter(i => getStatusCategory(i) === "expiring").length,
    release: items.filter(i => getStatusCategory(i) === "release").length,
  };

  const filters: { key: StatusFilter; dot: string; label: string }[] = [
    { key: "all",      dot: "bg-muted-foreground/50",       label: "All" },
    { key: "built",    dot: "bg-[#FFE64C]",                 label: "Built" },
    { key: "deployed", dot: "bg-[#FFB24C]",                 label: "Dev Deployed" },
    { key: "expiring", dot: "bg-[#F16C6C] animate-pulse",   label: "Expiring" },
    { key: "release",  dot: "bg-[#00C986]",                 label: "Release" },
  ];

  return (
    <div className="flex flex-col gap-2 px-4 py-3 rounded-xl bg-muted/30 border border-border/50">
      <div className="flex items-center gap-2">
        <Filter size={11} className="text-muted-foreground/60" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 select-none">
          Filter by Status
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {filters.map(({ key, dot, label }, idx) => (
          <React.Fragment key={key}>
            {idx > 0 && (
              <span className="text-muted-foreground/30 text-xs select-none">|</span>
            )}
            <StatusFilterButton
              active={statusFilter === key}
              dot={dot}
              label={label}
              count={key === "all" ? counts.all : counts[key]}
              onClick={() => onFilterChange(key)}
            />
          </React.Fragment>
        ))}
        {/* Legend sub-labels */}
        <div className="flex-1" />
        <div className="hidden md:flex items-center gap-3 text-[10px] text-muted-foreground/50">
          <span>Built=ready · Dev≤{devTtlDays}d TTL · Expiring≤7d · Release=persistent</span>
        </div>
      </div>
    </div>
  );
}

function InfoTile({ label, value, sub, valueCls = "", icon }: {
  label: string; value: string; sub?: string; valueCls?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5 bg-muted/30 border border-border/50 rounded-xl p-3">
      {icon && <div className="mt-0.5 text-muted-foreground/60 shrink-0">{icon}</div>}
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-0.5">{label}</p>
        <p className={`text-sm font-semibold truncate ${valueCls || "text-foreground"}`}>{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground/70 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function StatBig({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className={`text-4xl font-black ${color} tabular-nums leading-none`}>{value.toLocaleString()}</span>
      <span className="text-xs text-muted-foreground/70 font-medium">{label}</span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Marketplace() {
  const { token, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── Core state ─────────────────────────────────────────────────────────────
  const [items, setItems] = useState<MarketplaceItem[]>([]);
  const [config, setConfig] = useState<MarketplaceConfig>({ max_agents_per_user: 5, max_mcp_per_user: 5, dev_ttl_days: 10 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

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

  // Open a specific item if navigated here via URL param ?itemId=xxx
  useEffect(() => {
    const itemIdParam = searchParams.get("itemId");
    if (itemIdParam && items.length > 0) {
      const targetId = parseInt(itemIdParam, 10);
      const found = items.find(i => i.id === targetId);
      if (found) {
        setDetailItem(found);
        setEditMode(false);
        // Remove the param from URL so refreshing doesn't re-open it
        setSearchParams({}, { replace: true });
      }
    }
  }, [searchParams, items, setSearchParams]);

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
        toast.success(`${isRedeploy ? "Upgraded" : "Deployed"} to ${deployEnv.toUpperCase()} — ${selectedChart}@${selectedVersion}`);
        setIsDeployOpen(false);
        setDetailItem(null);
      } else {
        const e = await r.json();
        toast.error(e.detail || "Deploy failed.");
      }
    } catch { toast.error("Network error."); }
    finally { setDeployLoading(false); }
  }, [deployItem, deployEnv, selectedChart, selectedVersion, isRedeploy, authHeaders]);

  const handleExtendTTL = useCallback(async (item: MarketplaceItem) => {
    try {
      const r = await fetch(`/api/marketplace/items/${item.id}/extend-ttl`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) {
        const d = await r.json();
        setItems(prev => prev.map(i => i.id === item.id ? d.item : i));
        toast.success(`TTL extended — ${item.ttl_days ?? "default"} more days added.`);
        setDetailItem(null);
      } else {
        const e = await r.json();
        toast.error(e.detail || "Extend TTL failed.");
      }
    } catch { toast.error("Network error."); }
  }, [token]);

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
  const filterBySearch = useCallback((arr: MarketplaceItem[]) =>
    q ? arr.filter(i => i.name.toLowerCase().includes(q) || i.description.toLowerCase().includes(q)
      || i.owner_name?.toLowerCase().includes(q) || i.chart_name?.toLowerCase().includes(q)) : arr,
    [q]);

  const filterByStatus = useCallback((arr: MarketplaceItem[]) =>
    statusFilter === "all" ? arr : arr.filter(i => getStatusCategory(i) === statusFilter),
    [statusFilter]);

  const agents     = useMemo(() => filterByStatus(filterBySearch(items.filter(i => i.item_type === "agent"))),      [items, filterBySearch, filterByStatus]);
  const mcpServers = useMemo(() => filterByStatus(filterBySearch(items.filter(i => i.item_type === "mcp_server"))), [items, filterBySearch, filterByStatus]);

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

      {/* Hero Header */}
      <motion.div
        className="relative overflow-hidden rounded-2xl border border-border/30 p-6 glass"
        style={{ background: "hsl(var(--surface) / 0.8)" }}
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center shadow-lg shrink-0">
                <Store className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-black gradient-text tracking-tight leading-none">AI Marketplace</h1>
                <p className="text-xs text-muted-foreground mt-0.5">Internal App Store for AI Agents &amp; MCP Servers</p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed max-w-lg mt-3">
              Publish once, deploy anywhere.
              Connect Agents and MCP Servers to OpenWebUI, your IDE, or any tool.
            </p>
          </div>
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="lg" onClick={() => setIsCreateOpen(true)}
                  className="shrink-0 gap-2 bg-gradient-primary text-white border-0 shadow-lg shadow-primary/20 hover:opacity-90 transition-all font-bold">
                  <Plus size={17} /> Publish Agent / MCP Server
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left" className="text-xs max-w-[200px] text-center">
                Publish a new AI Agent or MCP Server to the marketplace
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Background ambient orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <motion.div
            className="absolute -right-12 -top-12 w-48 h-48 bg-secondary/8 rounded-full blur-3xl"
            animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 6, repeat: Infinity }}
          />
          <motion.div
            className="absolute left-1/3 -bottom-8 w-36 h-36 bg-primary/8 rounded-full blur-2xl"
            animate={{ scale: [1.1, 1, 1.1], opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 5, repeat: Infinity, delay: 1 }}
          />
        </div>
      </motion.div>

      {/* Status Legend / Filter */}
      <StatusLegend
        devTtlDays={config.dev_ttl_days}
        items={items}
        statusFilter={statusFilter}
        onFilterChange={setStatusFilter}
      />

      {/* Tabs */}
      <ThemedTabs defaultValue="agents" className="flex-1 flex flex-col" onValueChange={handleTabChange}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <ThemedTabsList className="grid grid-cols-3 sm:w-auto sm:min-w-[380px]">
            <ThemedTabsTrigger value="agents" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Zap size={13} /> Agents
              <span className="ml-1 text-[10px] font-black bg-white/10 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "agent").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="mcp-servers" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Blocks size={13} /> MCP Servers
              <span className="ml-1 text-[10px] font-black bg-white/10 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "mcp_server").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="skills" className="py-2.5 gap-1.5 text-sm font-semibold">
              <Sparkles size={13} /> Skills
            </ThemedTabsTrigger>
          </ThemedTabsList>
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <Input
              className="pl-8 h-9 text-sm border border-border/60 ring-1 ring-border/20 focus:border-primary/50 focus:ring-primary/20 bg-white/[0.03]"
              placeholder="Search by name, owner, chart…"
              value={search} onChange={e => setSearch(e.target.value)}
            />
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
                <div className="px-7 pt-5 pb-4 border-b border-border/50">
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
                          <span className="flex items-center gap-1 text-[#00C986] text-[10px] font-bold">
                            <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${st.pulse ? "animate-pulse" : ""}`} /> RUNNING
                          </span>
                        )}
                        {item.deployment_status === "DEPLOYED" && item.environment === "release" && (
                          <span className="flex items-center gap-1 text-[#00C986] text-[10px] font-bold">
                            <Sparkles size={9} /> Persistent · No expiry
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
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-1.5">Description</p>
                    {editMode
                      ? <Textarea value={editDesc} onChange={e => setEditDesc(e.target.value)}
                          className="min-h-[80px] resize-none" />
                      : <p className="text-sm text-muted-foreground bg-muted/30 border border-border/50 rounded-xl p-4 leading-relaxed">{item.description}</p>}
                  </div>

                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-1.5">How to Use</p>
                    {editMode
                      ? <Textarea value={editHowTo} onChange={e => setEditHowTo(e.target.value)}
                          className="min-h-[72px] resize-none"
                          placeholder="Example prompts, prerequisites…" />
                      : item.how_to_use
                        ? <p className="text-sm text-muted-foreground bg-primary/5 border border-primary/20 rounded-xl p-4 leading-relaxed">{item.how_to_use}</p>
                        : <p className="text-sm text-muted-foreground/50 italic">Not provided.</p>}
                  </div>

                  {editMode && (
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-1.5">Repo URL</p>
                      <Input value={editRepo} onChange={e => setEditRepo(e.target.value)}
                        placeholder="https://bitbucket.company.internal/…" />
                    </div>
                  )}

                  {!editMode && (
                    <div className="grid grid-cols-2 gap-2.5">
                      <InfoTile label="Chart" icon={<PackageSearch size={14} />}
                        value={item.chart_name ?? "Not deployed yet"}
                        sub={item.chart_version ? `version ${item.chart_version}` : undefined} />
                      <InfoTile label="TTL / Persistence" icon={<Clock size={14} />}
                        value={item.environment === "release" ? "Persistent (no TTL)" : `Dev · ${item.ttl_days ?? config.dev_ttl_days}d TTL`}
                        valueCls={item.ttl_remaining_days !== null && item.ttl_remaining_days <= 7 ? "text-[#F16C6C]" : ""}
                        sub={item.environment === "release"
                          ? "Release deployments never expire"
                          : item.ttl_remaining_days !== null
                            ? `${item.ttl_remaining_days} days remaining`
                            : undefined} />
                      {item.bitbucket_repo && (
                        <div className="flex items-start gap-2.5 bg-muted/30 border border-border/50 rounded-xl p-3">
                          <Github size={14} className="mt-0.5 text-muted-foreground/60 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-0.5">Repository</p>
                            <a href={item.bitbucket_repo} target="_blank" rel="noreferrer"
                              className="text-sm text-primary hover:underline truncate block">View Source ↗</a>
                          </div>
                        </div>
                      )}
                      {item.url_to_connect && (
                        <div className="flex items-start gap-2.5 bg-muted/30 border border-border/50 rounded-xl p-3">
                          <ExternalLink size={14} className="mt-0.5 text-muted-foreground/60 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-0.5">Connection URL</p>
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
                    <div className="flex gap-10 pt-4 border-t border-border/40">
                      <StatBig value={item.usage_count} label="Total Calls" color="text-primary" />
                      <StatBig value={item.unique_users} label="Unique Users" color="text-[#00C986]" />
                      {(item.tools_exposed?.length ?? 0) > 0 && (
                        <StatBig value={item.tools_exposed.length} label="Tools" color="text-secondary" />
                      )}
                    </div>
                  )}
                </div>

                {/* Footer actions */}
                <div className="px-7 py-4 border-t border-border/40 flex flex-col sm:flex-row items-center justify-between gap-3 bg-muted/20">
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
                            className="gap-1.5 border-[#FFB24C]/40 text-[#935900] dark:text-[#FFB24C] hover:bg-[#FFB24C] hover:text-white hover:border-[#FFB24C]"
                            onClick={() => { setDetailItem(null); openDeploy(item, false, "dev"); }}>
                            <Cloud size={13} /> Deploy Dev
                          </Button>
                          <Button size="sm" variant="outline"
                            className="gap-1.5 border-[#00C986]/40 text-[#007a52] dark:text-[#00C986] hover:bg-[#00C986] hover:text-white hover:border-[#00C986]"
                            onClick={() => { setDetailItem(null); openDeploy(item, false, "release"); }}>
                            <Rocket size={13} /> Deploy Release
                          </Button>
                        </>)}
                        {canManage && item.deployment_status === "DEPLOYED" && (<>
                          <Button size="sm" variant="outline"
                            className="gap-1.5 border-[#FFB24C]/40 text-[#935900] dark:text-[#FFB24C] hover:bg-[#FFB24C] hover:text-white hover:border-[#FFB24C]"
                            onClick={() => { setDetailItem(null); openDeploy(item, true, item.environment as "dev" | "release"); }}>
                            <RefreshCw size={13} /> Upgrade
                          </Button>
                          {item.environment === "dev" && (
                            <Button size="sm" variant="outline"
                              className="gap-1.5 border-[#55C5E2]/40 text-[#1a7a96] dark:text-[#55C5E2] hover:bg-[#55C5E2] hover:text-white hover:border-[#55C5E2]"
                              onClick={() => handleExtendTTL(item)}>
                              <Clock size={13} /> Extend Life
                            </Button>
                          )}
                        </>)}
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
            <DialogDescription>
              This action cannot be undone. The following will happen:
            </DialogDescription>
          </DialogHeader>
          <ul className="list-disc pl-5 space-y-1.5 text-sm text-muted-foreground">
            <li>
              The item will be <strong className="text-foreground">permanently removed</strong> from the Marketplace database.
            </li>
            {deleteTarget?.deployment_status === "DEPLOYED" && (
              <li>
                The <strong className="text-foreground">{deleteTarget.environment.toUpperCase()}</strong> deployment will be <strong className="text-foreground">undeployed</strong>.
              </li>
            )}
            <li>
              All usage history for this entity will be deleted.
            </li>
          </ul>
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
              {isRedeploy ? <RefreshCw size={17} className="text-[#FFB24C]" /> : <Rocket size={17} className="text-primary" />}
              {isRedeploy ? "Upgrade" : "Deploy"} — {deployItem?.name}
            </DialogTitle>
            <DialogDescription>Select environment, chart, and version from your Artifactory registry.</DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-1">
            {/* Environment */}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-2">Environment</p>
              <div className="grid grid-cols-2 gap-2">
                {(["dev", "release"] as const).map(env => (
                  <button key={env} type="button" onClick={() => handleDeployEnvChange(env)}
                    className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                      deployEnv === env
                        ? env === "dev"
                          ? "border-[#FFB24C] bg-[#FFB24C]/10 text-[#935900] dark:bg-[#FFB24C]/15 dark:text-[#FFB24C]"
                          : "border-[#00C986] bg-[#00C986]/10 text-[#007a52] dark:bg-[#00C986]/15 dark:text-[#00C986]"
                        : "border-border text-muted-foreground/70 hover:border-border/80 hover:bg-muted/30"
                    }`}>
                    {env === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
                    {env === "dev" ? "Dev" : "Release"}
                  </button>
                ))}
              </div>
              {deployEnv === "dev" && (
                <p className="text-xs text-[#935900] dark:text-[#FFB24C] mt-2 flex items-center gap-1.5">
                  <Clock size={10} /> Auto-expires after {config.dev_ttl_days} days
                </p>
              )}
              {deployEnv === "release" && (
                <p className="text-xs text-[#007a52] dark:text-[#00C986] mt-2 flex items-center gap-1.5">
                  <Sparkles size={10} /> Release deployments are persistent and never expire automatically
                </p>
              )}
            </div>

            {/* Chart picker */}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-2">
                Chart from Artifactory ({deployEnv === "dev" ? "my-helm-dev-local" : "my-helm-release-local"})
              </p>
              <div className="relative mb-2">
                <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60" />
                <Input className="pl-7 h-8 text-sm"
                  placeholder="Filter charts…" value={chartFilter} onChange={e => setChartFilter(e.target.value)} />
              </div>
              <div className="border border-border/60 rounded-xl overflow-hidden max-h-44 overflow-y-auto bg-muted/20">
                {chartsLoading
                  ? <p className="text-center text-muted-foreground/60 text-xs py-8 animate-pulse">Loading charts…</p>
                  : filteredCharts.length === 0
                    ? <p className="text-center text-muted-foreground/60 text-xs py-8">No charts found</p>
                    : filteredCharts.map(chart => (
                      <button key={chart} type="button" onClick={() => handleChartSelect(chart)}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2.5 transition-colors ${
                          selectedChart === chart ? "bg-primary/15 text-primary font-semibold" : "hover:bg-muted/50 text-foreground/80"
                        }`}>
                        <PackageSearch size={12} className="text-muted-foreground/60 shrink-0" />
                        <span className="font-mono truncate">{chart}</span>
                        {selectedChart === chart && <span className="ml-auto text-primary text-xs">✓</span>}
                      </button>
                    ))}
              </div>
            </div>

            {/* Versions */}
            {selectedChart && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 mb-2">
                  Version — <span className="text-primary normal-case font-semibold">{selectedChart}</span>
                </p>
                <div className="relative mb-2">
                  <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60" />
                  <Input className="pl-7 h-8 text-sm"
                    placeholder="Filter versions…" value={versionFilter} onChange={e => setVersionFilter(e.target.value)} />
                </div>
                {versionsLoading
                  ? <p className="text-xs text-muted-foreground/60 animate-pulse">Loading versions…</p>
                  : filteredVersions.length === 0
                    ? <p className="text-xs text-muted-foreground/60">No versions found</p>
                    : <div className="flex flex-wrap gap-2">
                        {filteredVersions.map(v => (
                          <button key={v} type="button" onClick={() => setSelectedVersion(v)}
                            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold transition-all ${
                              selectedVersion === v ? "border-primary bg-primary/15 text-primary" : "border-border/60 text-foreground/70 hover:border-border"
                            }`}>{v}
                          </button>
                        ))}
                      </div>}
              </div>
            )}

            {/* Summary */}
            {selectedChart && selectedVersion && (
              <div className={`flex items-start gap-3 p-4 rounded-xl border bg-muted/50 text-sm`}
                style={{ borderColor: deployEnv === "dev" ? "rgba(255,178,76,0.5)" : "rgba(0,201,134,0.5)" }}>
                <div className={`mt-0.5 shrink-0 p-1.5 rounded-lg ${
                  deployEnv === "dev" ? "bg-[#FFB24C]/20 text-[#935900] dark:text-[#FFB24C]" : "bg-[#00C986]/20 text-[#007a52] dark:text-[#00C986]"
                }`}>
                  {deployEnv === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
                </div>
                <div className="leading-relaxed text-foreground">
                  <span className="font-semibold">{isRedeploy ? "Upgrading" : "Deploying"}</span>{" "}
                  <code className="text-xs font-mono px-1.5 py-0.5 rounded bg-foreground/10 border border-border/60 text-foreground">
                    {selectedChart}@{selectedVersion}
                  </code>{" "}
                  to{" "}
                  <span className={`font-bold ${deployEnv === "dev" ? "text-[#935900] dark:text-[#FFB24C]" : "text-[#007a52] dark:text-[#00C986]"}`}>
                    {deployEnv.toUpperCase()}
                  </span>.
                  {deployEnv === "dev" && (
                    <span className="text-xs block mt-1 text-muted-foreground">
                      Auto-expires in {config.dev_ttl_days} days.
                    </span>
                  )}
                  {deployEnv === "release" && (
                    <span className="text-xs block mt-1 text-[#007a52] dark:text-[#00C986]">
                      Persistent deployment — will not expire automatically.
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsDeployOpen(false)}>Cancel</Button>
            <Button disabled={!selectedChart || !selectedVersion || deployLoading} onClick={handleDeploy}
              className={`gap-1.5 font-bold ${deployEnv === "dev" ? "bg-[#FFB24C] hover:opacity-90 text-white" : "bg-[#00C986] hover:opacity-90 text-white"}`}>
              {deployEnv === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
              {deployLoading ? "Working…" : isRedeploy ? "Upgrade" : "Deploy"}
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
              <p className="text-xs text-muted-foreground font-mono bg-muted/40 border border-border/50 rounded-lg px-3 py-2 truncate">
                {callItem.url_to_connect}
              </p>
            ) : (
              <div className="flex items-center gap-2 text-sm text-[#935900] dark:text-[#FFB24C] bg-[#FFB24C]/10 border border-[#FFB24C]/30 rounded-lg px-3 py-2">
                <AlertTriangle size={14} /> No connection URL — redeploy to assign one.
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Prompt</Label>
              <Textarea
                className="min-h-[100px] resize-none font-mono text-sm"
                placeholder={`Send a message to ${callItem?.name}…`}
                value={callPrompt}
                onChange={e => setCallPrompt(e.target.value)}
              />
            </div>

            {callResponse !== null && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-[#007a52] dark:text-[#00C986]/80 mb-1.5">Response</p>
                <pre className="text-xs text-foreground bg-muted/50 border border-border/50 rounded-xl p-4 overflow-auto max-h-60 whitespace-pre-wrap font-mono leading-relaxed">
                  {callResponse}
                </pre>
              </div>
            )}
            {callError && (
              <div className="flex items-start gap-2 text-sm text-[#c03232] dark:text-[#F16C6C] bg-[#F16C6C]/10 border border-[#F16C6C]/30 rounded-xl p-3">
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
              <Sparkles size={19} className="text-primary" /> Publish New Agent / MCP Server
            </DialogTitle>
            <DialogDescription>
              Register an Agent or MCP Server. It will immediately be <strong>BUILT</strong> and ready to deploy.
            </DialogDescription>
          </DialogHeader>

          {/* Prerequisites notice */}
          <div className="mt-4 rounded-xl border border-[#FFB24C]/30 bg-[#FFB24C]/5 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-[#FFB24C]/20 flex items-center justify-center shrink-0">
                <Info size={13} className="text-[#FFB24C]" />
              </div>
              <p className="text-sm font-bold text-[#935900] dark:text-[#FFB24C]">Prerequisites — This Release Only</p>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              In this release, repository provisioning and pipeline setup are <strong>manual</strong>. Before you can
              start writing code, please open a Jira ticket to <strong>DevOps</strong> requesting the following:
            </p>
            <ol className="text-xs text-muted-foreground space-y-1.5 pl-1">
              <li className="flex items-start gap-2">
                <span className="w-4 h-4 rounded-full bg-[#FFB24C]/20 text-[#935900] dark:text-[#FFB24C] text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">1</span>
                <span>
                  <strong>Fork the templates repository</strong> for your Agent or MCP Server — DevOps will create the repo and return the Bitbucket URL.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-4 h-4 rounded-full bg-[#FFB24C]/20 text-[#935900] dark:text-[#FFB24C] text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">2</span>
                <span>
                  <strong>Create a multibranch pipeline in Jenkins</strong> for the new repo — DevOps will return the Jenkins job URL.
                </span>
              </li>
            </ol>
            <div className="rounded-lg bg-[#FFB24C]/10 border border-[#FFB24C]/20 px-3 py-2 space-y-1">
              <p className="text-[11px] font-semibold text-[#935900] dark:text-[#FFB24C]">After DevOps responds:</p>
              <ul className="text-[11px] text-muted-foreground space-y-0.5 list-disc list-inside">
                <li>Enter the <strong>Bitbucket repo URL</strong> in the field below and start developing.</li>
                <li>In the repository, replace every occurrence of <code className="bg-muted/60 px-1 rounded text-[#935900] dark:text-[#FFB24C] font-mono">__appname__</code> with your Agent / MCP name.</li>
                <li>Use the Jenkins URL to monitor builds and deployments.</li>
              </ul>
            </div>
            <p className="text-[10px] text-muted-foreground/50 italic">
              This step will be automated in the next release.
            </p>
          </div>

          <form onSubmit={handleCreate} className="mt-3 space-y-5">
            {/* Icon upload */}
            <div className="flex items-start gap-5 p-4 rounded-2xl border border-border/50 bg-muted/20">
              <div onClick={() => iconInputRef.current?.click()}
                className="w-20 h-20 rounded-2xl border-2 border-dashed border-border/60 bg-muted/30 flex items-center justify-center cursor-pointer hover:border-primary/60 hover:bg-primary/5 transition-all shrink-0 overflow-hidden group">
                {createIcon
                  ? <img src={createIcon} alt="preview" className="w-full h-full object-cover" />
                  : <div className="flex flex-col items-center gap-1 text-muted-foreground/40 group-hover:text-muted-foreground/70 transition-colors">
                      <UploadCloud size={20} /><span className="text-[9px] font-medium">Icon</span>
                    </div>}
              </div>
              <input ref={iconInputRef} type="file" accept="image/*" className="hidden" onChange={handleIconFile} />
              <div className="flex-1">
                <p className="text-sm font-semibold mb-1 text-foreground">Entity Icon</p>
                <p className="text-xs text-muted-foreground/60 mb-3">PNG / JPG / SVG · max 1 MB · stored in database</p>
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
                <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                  Type <span className="text-destructive">*</span>
                </Label>
                <div className="grid grid-cols-2 gap-2">
                  {(["agent", "mcp_server"] as const).map(t => (
                    <button key={t} type="button" onClick={() => setCreateType(t)}
                      className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                        createType === t ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground/70 hover:border-border/80 hover:bg-muted/30"
                      }`}>
                      {t === "agent" ? <Zap size={13} /> : <Blocks size={13} />}
                      {t === "agent" ? "Agent" : "MCP"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input id="cn" required placeholder="e.g. Jira Integration MCP"
                  value={createName} onChange={e => setCreateName(e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cd" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea id="cd" required className="min-h-[80px] resize-none"
                placeholder="What does this entity do? When should someone use it?"
                value={createDesc} onChange={e => setCreateDesc(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="cr" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Bitbucket Repo URL</Label>
              <Input id="cr" placeholder="https://bitbucket.company.internal/…"
                value={createRepo} onChange={e => setCreateRepo(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ch" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">How to Use</Label>
              <Textarea id="ch" className="min-h-[72px] resize-none"
                placeholder="Example prompts, prerequisites, example inputs…"
                value={createHowTo} onChange={e => setCreateHowTo(e.target.value)} />
            </div>

            <DialogFooter className="pt-4 border-t border-border/40 gap-2">
              <Button type="button" variant="outline" onClick={() => { setIsCreateOpen(false); resetCreate(); }}>Cancel</Button>
              <Button type="submit" disabled={createLoading || !createName.trim() || !createDesc.trim()}
                className="gap-1.5 bg-gradient-primary text-primary-foreground font-bold px-6">
                <Plus size={14} />{createLoading ? "Publishing…" : "Publish Agent / MCP Server"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
