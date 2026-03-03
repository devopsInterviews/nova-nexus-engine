/**
 * Marketplace — centralised hub for AI Agents and MCP Servers.
 *
 * ─── Critical architecture note ──────────────────────────────────────────────
 * ALL sub-components (ItemCard, EntityIcon, etc.) are defined OUTSIDE this
 * component function so they are stable React component identities.  Modals are
 * inlined as JSX inside the return, NOT as nested function components.
 * This prevents the "form re-renders on every keystroke" bug caused by defining
 * components inside the render scope.
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
  Calendar,
  ChevronRight,
  Circle,
  Clock,
  Cloud,
  Copy,
  ExternalLink,
  Github,
  PackageSearch,
  Plus,
  RefreshCw,
  Rocket,
  Search,
  Sparkles,
  Tag,
  Trash2,
  UploadCloud,
  Users,
  Zap,
} from "lucide-react";

// ─── Feature flag — set to false once backend is wired end-to-end ─────────────
const USE_MOCK_DATA = true;

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

// ─── Frontend mock data (delete when backend is fully wired) ──────────────────

const _AVT = "https://api.dicebear.com/7.x/bottts/svg";
const NOW_ISO = new Date().toISOString();
const daysAgo = (d: number) =>
  new Date(Date.now() - d * 86_400_000).toISOString();

const MOCK_ITEMS: MarketplaceItem[] = [
  {
    id: 1001, name: "Data Analysis Agent",
    description: "Analyzes complex datasets and returns natural language summaries with statistical insights, trend detection, and anomaly flagging. Powered by pandas + LLM.",
    item_type: "agent", owner_id: 1, owner_name: "alice",
    icon: `${_AVT}?seed=DataAgent&backgroundColor=b6e3f4`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/AI/repos/data-agent",
    how_to_use: "Ask: 'summarize the latest sales data' or 'find anomalies in the weekly report'. Works with SQL queries and CSV uploads.",
    url_to_connect: "http://data-agent.release.svc.cluster.local",
    tools_exposed: [], deployment_status: "DEPLOYED", version: "2.1.0",
    environment: "release", chart_name: "data-analysis-agent", chart_version: "2.1.0",
    ttl_days: null, ttl_remaining_days: null, deployed_at: daysAgo(30),
    created_at: daysAgo(60), usage_count: 142, unique_users: 23,
  },
  {
    id: 1002, name: "Jira Integration MCP",
    description: "Exposes tools to create, update, search, and comment on Jira issues from any LLM session. Supports JQL queries, sprint management, and epic linking.",
    item_type: "mcp_server", owner_id: 1, owner_name: "alice",
    icon: `${_AVT}?seed=JiraMCP&backgroundColor=c0aede`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/MCP/repos/jira-mcp",
    how_to_use: "Enable in the Research tab. Then say 'create a P1 bug' or 'show my open tickets'. Tools: create_ticket, update_ticket, search_tickets.",
    url_to_connect: "http://jira-mcp.mcp-gateway.company.internal",
    tools_exposed: [{ name: "create_ticket" }, { name: "update_ticket" }, { name: "search_tickets" }, { name: "add_comment" }],
    deployment_status: "DEPLOYED", version: "2.0.1", environment: "release",
    chart_name: "jira-integration-mcp", chart_version: "2.0.1",
    ttl_days: null, ttl_remaining_days: null, deployed_at: daysAgo(45),
    created_at: daysAgo(90), usage_count: 381, unique_users: 47,
  },
  {
    id: 1003, name: "K8s Ops Agent",
    description: "Your AI SRE. Monitors Kubernetes cluster health, surfaces failing pods, suggests remediation, and can apply Helm rollbacks on command.",
    item_type: "agent", owner_id: 2, owner_name: "bob",
    icon: `${_AVT}?seed=K8sAgent&backgroundColor=d1f4cc`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/OPS/repos/k8s-agent",
    how_to_use: "Ask 'check the prod cluster', 'list failing pods in ns payments', or 'roll back payments to v1.3'.",
    url_to_connect: "http://k8s-agent.dev.svc.cluster.local",
    tools_exposed: [], deployment_status: "DEPLOYED", version: "0.9.4",
    environment: "dev", chart_name: "k8s-ops-agent", chart_version: "0.9.4",
    // 8 days elapsed on 10-day TTL → 2 days remaining = RED warning
    ttl_days: 10, ttl_remaining_days: 2, deployed_at: daysAgo(8),
    created_at: daysAgo(20), usage_count: 67, unique_users: 8,
  },
  {
    id: 1004, name: "GitHub Actions MCP",
    description: "Trigger workflows, inspect run logs, download artifacts, and manage GitHub Actions pipelines entirely from natural language prompts.",
    item_type: "mcp_server", owner_id: 2, owner_name: "bob",
    icon: `${_AVT}?seed=GithubMCP&backgroundColor=ffd5dc`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/MCP/repos/gh-actions-mcp",
    how_to_use: "Say 'trigger the nightly build for repo X' or 'show last 5 failed CI runs for the backend'. Tools: trigger_workflow, list_runs, get_run_logs.",
    url_to_connect: null,
    tools_exposed: [{ name: "trigger_workflow" }, { name: "list_runs" }, { name: "get_run_logs" }],
    deployment_status: "BUILT", version: "1.0.0", environment: "dev",
    chart_name: null, chart_version: null,
    ttl_days: 10, ttl_remaining_days: null, deployed_at: null,
    created_at: daysAgo(5), usage_count: 0, unique_users: 0,
  },
  {
    id: 1005, name: "Vault Secrets MCP",
    description: "Securely fetches secrets from HashiCorp Vault and injects them into your AI workflows. No more hardcoded credentials in prompts.",
    item_type: "mcp_server", owner_id: 1, owner_name: "alice",
    icon: `${_AVT}?seed=VaultMCP&backgroundColor=fffdd0`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/MCP/repos/vault-mcp",
    how_to_use: "Ask 'get the DB password for prod' or 'rotate the API keys for service X'. Requires Vault policy approved by your team lead.",
    url_to_connect: "http://vault-mcp.dev.svc.cluster.local",
    tools_exposed: [{ name: "get_secret" }, { name: "rotate_secret" }],
    deployment_status: "DEPLOYED", version: "1.3.0", environment: "dev",
    chart_name: "vault-secrets-mcp", chart_version: "1.3.0",
    // 6 days elapsed → 4 days remaining = ORANGE warning
    ttl_days: 10, ttl_remaining_days: 4, deployed_at: daysAgo(6),
    created_at: daysAgo(14), usage_count: 29, unique_users: 5,
  },
  {
    id: 1006, name: "Slack Notifier Agent",
    description: "Sends intelligent notifications, daily summaries, and real-time alerts to Slack channels based on events across your connected systems.",
    item_type: "agent", owner_id: 3, owner_name: "carol",
    icon: `${_AVT}?seed=SlackAgent&backgroundColor=e0c3fc`,
    bitbucket_repo: "https://bitbucket.company.internal/projects/AI/repos/slack-agent",
    how_to_use: "Ask 'send a daily standup to #engineering' or 'alert #on-call about the DB spike'. Configure channel in the settings.",
    url_to_connect: null,
    tools_exposed: [], deployment_status: "BUILT", version: "1.1.0",
    environment: "dev", chart_name: null, chart_version: null,
    ttl_days: 10, ttl_remaining_days: null, deployed_at: null,
    created_at: daysAgo(3), usage_count: 0, unique_users: 0,
  },
];

const MOCK_CHARTS: Record<string, string[]> = {
  dev: [
    "data-analysis-agent", "k8s-ops-agent", "github-actions-mcp",
    "vault-secrets-mcp", "slack-notifier-agent", "reporting-agent",
    "incident-responder-mcp", "confluence-mcp",
  ],
  release: [
    "data-analysis-agent", "jira-integration-mcp", "vault-secrets-mcp",
    "reporting-agent", "confluence-mcp",
  ],
};

const MOCK_CHART_VERSIONS: Record<string, string[]> = {
  "data-analysis-agent":  ["2.1.0", "2.0.0", "1.5.2", "1.4.0", "1.0.0"],
  "jira-integration-mcp": ["2.0.1", "2.0.0", "1.8.3", "1.5.0"],
  "k8s-ops-agent":        ["0.9.4", "0.9.0", "0.8.2", "0.7.0"],
  "github-actions-mcp":   ["1.0.0", "0.9.1"],
  "vault-secrets-mcp":    ["1.3.0", "1.2.1", "1.0.0"],
  "slack-notifier-agent": ["1.1.0", "1.0.0"],
  "reporting-agent":      ["3.0.0", "2.5.1", "2.0.0"],
  "incident-responder-mcp": ["1.0.0"],
  "confluence-mcp":       ["1.2.0", "1.1.0", "1.0.0"],
};

// ─── Status/style helpers (pure — no React hooks) ─────────────────────────────

function getItemStyle(item: MarketplaceItem) {
  const nearExpiry = item.ttl_remaining_days !== null && item.ttl_remaining_days <= 3;
  const midExpiry  = item.ttl_remaining_days !== null && item.ttl_remaining_days <= 7 && item.ttl_remaining_days > 3;

  if (item.deployment_status === "DEPLOYED") {
    if (item.environment === "release") {
      return {
        topBar:      "bg-emerald-500",
        glow:        "shadow-emerald-500/10",
        ring:        "border-emerald-500/30 hover:border-emerald-400/60",
        cardBg:      "from-emerald-950/10",
        badgeCls:    "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
        label:       "Deployed · Release",
        dotCls:      "bg-emerald-500",
        dotPulse:    true,
      };
    }
    if (nearExpiry) {
      return {
        topBar:   "bg-red-500",
        glow:     "shadow-red-500/20",
        ring:     "border-red-500/50 hover:border-red-400/80",
        cardBg:   "from-red-950/20",
        badgeCls: "bg-red-500/15 text-red-400 border-red-500/30",
        label:    "Expiring Soon!",
        dotCls:   "bg-red-500 animate-pulse",
        dotPulse: true,
      };
    }
    if (midExpiry) {
      return {
        topBar:   "bg-orange-500",
        glow:     "shadow-orange-500/15",
        ring:     "border-orange-500/40 hover:border-orange-400/70",
        cardBg:   "from-orange-950/15",
        badgeCls: "bg-orange-500/15 text-orange-400 border-orange-500/30",
        label:    "Deployed · Dev",
        dotCls:   "bg-orange-400",
        dotPulse: false,
      };
    }
    return {
      topBar:   "bg-violet-500",
      glow:     "shadow-violet-500/10",
      ring:     "border-violet-500/30 hover:border-violet-400/60",
      cardBg:   "from-violet-950/10",
      badgeCls: "bg-violet-500/15 text-violet-400 border-violet-500/30",
      label:    "Deployed · Dev",
      dotCls:   "bg-violet-500",
      dotPulse: true,
    };
  }

  // BUILT
  return {
    topBar:   "bg-amber-500",
    glow:     "shadow-amber-500/10",
    ring:     "border-amber-500/25 hover:border-amber-400/50",
    cardBg:   "from-amber-950/10",
    badgeCls: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    label:    "Built",
    dotCls:   "bg-amber-400",
    dotPulse: false,
  };
}

function getTtlBadgeCls(remaining: number | null): string {
  if (remaining === null) return "";
  if (remaining <= 3) return "bg-red-500/15 text-red-400 border-red-500/30";
  if (remaining <= 7) return "bg-orange-500/15 text-orange-400 border-orange-500/30";
  return "bg-violet-500/15 text-violet-400 border-violet-500/30";
}

// ─── Reusable sub-components (defined OUTSIDE Marketplace) ────────────────────

const EntityIcon = memo(function EntityIcon({
  icon,
  item_type,
  size = "md",
}: {
  icon: string | null;
  item_type: string;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const dim = { sm: "w-10 h-10", md: "w-14 h-14", lg: "w-16 h-16", xl: "w-20 h-20" }[size];
  const iconSz = { sm: 16, md: 24, lg: 28, xl: 32 }[size];

  if (icon) {
    return (
      <img
        src={icon}
        alt="icon"
        className={`${dim} rounded-2xl object-cover border border-white/10 shrink-0`}
      />
    );
  }
  return (
    <div
      className={`${dim} rounded-2xl shrink-0 flex items-center justify-center border border-primary/20
        bg-gradient-to-br from-primary/20 to-secondary/20`}
    >
      {item_type === "agent" ? (
        <Zap size={iconSz} className="text-primary/90" />
      ) : (
        <Blocks size={iconSz} className="text-secondary/90" />
      )}
    </div>
  );
});

const ItemCard = memo(function ItemCard({
  item,
  onClick,
}: {
  item: MarketplaceItem;
  onClick: () => void;
}) {
  const st = getItemStyle(item);
  const nearExpiry = item.ttl_remaining_days !== null && item.ttl_remaining_days <= 3;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      className={`
        group relative cursor-pointer rounded-2xl overflow-hidden flex flex-col
        bg-gradient-to-b ${st.cardBg} to-surface/60 backdrop-blur-sm
        border-2 ${st.ring}
        transition-all duration-200 ease-out
        hover:scale-[1.02] hover:shadow-2xl ${st.glow}
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary
      `}
    >
      {/* Status top bar */}
      <div className={`absolute top-0 inset-x-0 h-1 ${st.topBar} z-10`} />

      {/* Near-expiry alert strip */}
      {nearExpiry && (
        <div className="absolute top-1 inset-x-0 flex items-center justify-center gap-1 text-[10px] font-bold text-red-300 bg-red-950/60 py-0.5 z-10">
          <AlertTriangle size={10} /> AUTO-DELETING IN {item.ttl_remaining_days}d
        </div>
      )}

      <div className={`p-4 ${nearExpiry ? "pt-7" : "pt-5"} flex-1 flex flex-col gap-3`}>
        {/* Header row */}
        <div className="flex items-start gap-3">
          <EntityIcon icon={item.icon} item_type={item.item_type} size="md" />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-base leading-snug truncate group-hover:text-primary transition-colors">
              {item.name}
            </p>
            <p className="text-xs text-muted-foreground/80 mt-0.5 truncate">
              by <span className="text-foreground/60 font-medium">{item.owner_name}</span>
            </p>
            <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-muted/50 border border-border/40 px-1.5 py-0.5 rounded-md text-muted-foreground">
                <Tag size={8} /> v{item.version}
              </span>
              <span
                className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border ${
                  item.environment === "release"
                    ? "bg-blue-500/10 text-blue-400 border-blue-500/25"
                    : "bg-orange-500/10 text-orange-400 border-orange-500/25"
                }`}
              >
                {item.environment.toUpperCase()}
              </span>
            </div>
          </div>
          {/* Live dot */}
          {item.deployment_status === "DEPLOYED" && (
            <div className="shrink-0 pt-1">
              <span
                className={`block w-2.5 h-2.5 rounded-full ${st.dotCls} ${st.dotPulse ? "animate-pulse" : ""}`}
                title="Live"
              />
            </div>
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-muted-foreground/80 line-clamp-3 leading-relaxed flex-1">
          {item.description}
        </p>

        {/* TTL badge */}
        {item.deployment_status === "DEPLOYED" && item.environment === "dev" && item.ttl_remaining_days !== null && (
          <div className={`self-start inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-1 rounded-lg border ${getTtlBadgeCls(item.ttl_remaining_days)}`}>
            <Clock size={11} />
            {item.ttl_remaining_days === 0 ? "Expiring today!" : `${item.ttl_remaining_days}d remaining`}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-white/5 bg-black/10 px-4 py-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-3 text-xs text-muted-foreground/70">
          <span className="flex items-center gap-1" title="Total calls">
            <Activity size={11} className="text-primary/50" />
            <span className="font-bold text-foreground/60">{item.usage_count}</span>
          </span>
          <span className="flex items-center gap-1" title="Unique users">
            <Users size={11} className="text-emerald-500/50" />
            <span className="font-bold text-foreground/60">{item.unique_users}</span>
          </span>
        </div>
        <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${st.badgeCls}`}>
          <Circle size={5} className="fill-current" />
          {st.label}
        </span>
      </div>
    </div>
  );
});

function ColorLegend({ devTtlDays }: { devTtlDays: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 rounded-2xl bg-black/20 border border-white/5 backdrop-blur-sm text-xs">
      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/40">
        Status guide
      </span>
      {[
        { color: "bg-amber-500", label: "Built", desc: "Ready to deploy" },
        { color: "bg-violet-500", label: "Dev Deployed", desc: `Expires in ${devTtlDays}d` },
        { color: "bg-orange-500", label: "Near expiry", desc: "≤7 days left" },
        { color: "bg-red-500 animate-pulse", label: "Critical", desc: "≤3 days — will auto-delete" },
        { color: "bg-emerald-500", label: "Release", desc: "Persistent" },
      ].map(({ color, label, desc }) => (
        <span key={label} className="flex items-center gap-2">
          <span className={`w-4 h-1.5 rounded-full shrink-0 ${color}`} />
          <span className="font-semibold text-foreground/70">{label}</span>
          <span className="text-muted-foreground/50 hidden sm:inline">— {desc}</span>
        </span>
      ))}
    </div>
  );
}

function InfoTile({
  label,
  value,
  sub,
  valueCls = "text-foreground",
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  valueCls?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 bg-white/[0.03] border border-white/5 rounded-xl p-3">
      {icon && <div className="mt-0.5 text-muted-foreground/50 shrink-0">{icon}</div>}
      <div className="min-w-0">
        <p className="text-[11px] text-muted-foreground/60 uppercase tracking-wide font-semibold mb-0.5">{label}</p>
        <p className={`text-sm font-semibold truncate ${valueCls}`}>{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground/50 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function StatBig({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={`text-4xl font-black ${color} tabular-nums`}>{value}</span>
      <span className="text-xs text-muted-foreground/60">{label}</span>
    </div>
  );
}

// ─── Main Page Component ──────────────────────────────────────────────────────

export default function Marketplace() {
  const { token, user } = useAuth();

  const [items, setItems] = useState<MarketplaceItem[]>(USE_MOCK_DATA ? MOCK_ITEMS : []);
  const [config, setConfig] = useState<MarketplaceConfig>({ max_agents_per_user: 5, max_mcp_per_user: 5, dev_ttl_days: 10 });
  const [apiLoading, setApiLoading] = useState(!USE_MOCK_DATA);
  const [search, setSearch] = useState("");

  // ── Detail modal state ─────────────────────────────────────────────────────
  const [detailItem, setDetailItem] = useState<MarketplaceItem | null>(null);

  // ── Deploy / Redeploy modal state ──────────────────────────────────────────
  const [isDeployOpen, setIsDeployOpen] = useState(false);
  const [isRedeploy, setIsRedeploy] = useState(false);
  const [deployItem, setDeployItem] = useState<MarketplaceItem | null>(null);
  const [deployEnv, setDeployEnv] = useState<"dev" | "release">("dev");
  const [availableCharts, setAvailableCharts] = useState<string[]>([]);
  const [chartFilter, setChartFilter] = useState("");
  const [selectedChart, setSelectedChart] = useState("");
  const [chartVersions, setChartVersions] = useState<string[]>([]);
  const [selectedVersion, setSelectedVersion] = useState("latest");
  const [deployLoading, setDeployLoading] = useState(false);

  // ── Create modal state ─────────────────────────────────────────────────────
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createType, setCreateType] = useState("agent");
  const [createIcon, setCreateIcon] = useState("");
  const [createRepo, setCreateRepo] = useState("");
  const [createHowTo, setCreateHowTo] = useState("");
  const iconInputRef = useRef<HTMLInputElement>(null);

  // ── Data fetching ──────────────────────────────────────────────────────────

  const fetchConfig = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/marketplace/config", { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setConfig(await res.json());
    } catch { /* ignore */ }
  }, [token]);

  const fetchItems = useCallback(async () => {
    if (!token) return;
    setApiLoading(true);
    try {
      const res = await fetch("/api/marketplace/items", { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setItems(await res.json());
    } catch { toast.error("Failed to load marketplace items."); }
    finally { setApiLoading(false); }
  }, [token]);

  useEffect(() => {
    if (token && !USE_MOCK_DATA) { fetchConfig(); fetchItems(); }
    else if (token) { fetchConfig(); }
  }, [token, fetchConfig, fetchItems]);

  // ── Chart loading for deploy modal ─────────────────────────────────────────

  const loadCharts = useCallback(async (env: "dev" | "release") => {
    if (USE_MOCK_DATA) {
      setAvailableCharts(MOCK_CHARTS[env] ?? []);
      return;
    }
    try {
      const res = await fetch(`/api/marketplace/charts?environment=${env}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setAvailableCharts(d.charts ?? []); }
    } catch { setAvailableCharts([]); }
  }, [token]);

  const loadVersions = useCallback(async (chartName: string, env: "dev" | "release") => {
    setChartVersions([]);
    setSelectedVersion("latest");
    if (!chartName) return;
    if (USE_MOCK_DATA) {
      const v = MOCK_CHART_VERSIONS[chartName] ?? ["latest", "1.0.0"];
      setChartVersions(v);
      setSelectedVersion(v[0] ?? "latest");
      return;
    }
    try {
      const res = await fetch(
        `/api/marketplace/chart-versions?environment=${env}&chart_name=${encodeURIComponent(chartName)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const d = await res.json();
        setChartVersions(d.versions ?? ["latest"]);
        setSelectedVersion(d.versions?.[0] ?? "latest");
      }
    } catch { setChartVersions(["latest"]); setSelectedVersion("latest"); }
  }, [token]);

  // ── Open deploy modal ──────────────────────────────────────────────────────

  const openDeploy = useCallback((item: MarketplaceItem, redeploy = false, initialEnv: "dev" | "release" = "dev") => {
    setDeployItem(item);
    setIsRedeploy(redeploy);
    setDeployEnv(initialEnv);
    setChartFilter("");
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

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    try {
      if (USE_MOCK_DATA) {
        await new Promise(r => setTimeout(r, 600));
        const newItem: MarketplaceItem = {
          id: Date.now(), name: createName, description: createDesc,
          item_type: createType as "agent" | "mcp_server",
          owner_id: user?.id ?? 1, owner_name: user?.username ?? "me",
          icon: createIcon || null, bitbucket_repo: createRepo || null,
          how_to_use: createHowTo || null, url_to_connect: null, tools_exposed: [],
          deployment_status: "BUILT", version: "1.0.0",
          environment: "dev", chart_name: null, chart_version: null,
          ttl_days: config.dev_ttl_days, ttl_remaining_days: null,
          deployed_at: null, created_at: new Date().toISOString(),
          usage_count: 0, unique_users: 0,
        };
        setItems(prev => [...prev, newItem]);
        toast.success(`${createType === "agent" ? "Agent" : "MCP Server"} registered — ready to deploy!`);
        setIsCreateOpen(false);
        setCreateName(""); setCreateDesc(""); setCreateType("agent");
        setCreateIcon(""); setCreateRepo(""); setCreateHowTo("");
        return;
      }
      const res = await fetch("/api/marketplace/items", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: createName, description: createDesc, item_type: createType,
          icon: createIcon || null, bitbucket_repo: createRepo || null, how_to_use: createHowTo || null,
        }),
      });
      if (res.ok) {
        toast.success("Entity registered — ready to deploy!");
        setIsCreateOpen(false);
        setCreateName(""); setCreateDesc(""); setCreateType("agent");
        setCreateIcon(""); setCreateRepo(""); setCreateHowTo("");
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Failed to create.");
      }
    } catch { toast.error("Network error."); }
    finally { setCreateLoading(false); }
  }, [createName, createDesc, createType, createIcon, createRepo, createHowTo, token, user, config.dev_ttl_days, fetchItems]);

  const handleDeploy = useCallback(async () => {
    if (!deployItem || !selectedChart) return;
    setDeployLoading(true);
    try {
      const endpoint = isRedeploy ? "/api/marketplace/redeploy" : "/api/marketplace/deploy";
      if (USE_MOCK_DATA) {
        await new Promise(r => setTimeout(r, 800));
        const ttlRemaining = deployEnv === "dev" ? config.dev_ttl_days : null;
        setItems(prev => prev.map(i =>
          i.id === deployItem.id
            ? {
                ...i, deployment_status: "DEPLOYED", environment: deployEnv,
                chart_name: selectedChart, chart_version: selectedVersion,
                ttl_days: deployEnv === "dev" ? config.dev_ttl_days : null,
                ttl_remaining_days: ttlRemaining,
                deployed_at: new Date().toISOString(),
              }
            : i
        ));
        toast.success(`${isRedeploy ? "Redeployed" : "Deployed"} ${deployItem.name} to ${deployEnv.toUpperCase()} (${selectedChart}@${selectedVersion})!`);
        setIsDeployOpen(false);
        setDetailItem(null);
        return;
      }
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ item_id: deployItem.id, environment: deployEnv, chart_name: selectedChart, chart_version: selectedVersion }),
      });
      if (res.ok) {
        toast.success(`${isRedeploy ? "Redeployed" : "Deployed"} to ${deployEnv}!`);
        setIsDeployOpen(false);
        setDetailItem(null);
        fetchItems();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Deploy failed.");
      }
    } catch { toast.error("Network error."); }
    finally { setDeployLoading(false); }
  }, [deployItem, deployEnv, selectedChart, selectedVersion, isRedeploy, token, config.dev_ttl_days, fetchItems]);

  const handleClone = useCallback(async (item: MarketplaceItem) => {
    try {
      if (USE_MOCK_DATA) {
        const clone: MarketplaceItem = {
          ...item, id: Date.now(), name: `${item.name} (Fork)`,
          deployment_status: "BUILT", deployed_at: null, ttl_remaining_days: null,
          url_to_connect: null, usage_count: 0, unique_users: 0, created_at: new Date().toISOString(),
        };
        setItems(prev => [...prev, clone]);
        toast.success("Fork created — deploy it independently.");
        setDetailItem(null);
        return;
      }
      const res = await fetch(`/api/marketplace/items/${item.id}/clone`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { toast.success("Fork created!"); setDetailItem(null); fetchItems(); }
      else { const e = await res.json(); toast.error(e.detail || "Clone failed."); }
    } catch { toast.error("Network error."); }
  }, [token, fetchItems]);

  const handleCall = useCallback(async (item: MarketplaceItem) => {
    try {
      if (USE_MOCK_DATA) {
        setItems(prev => prev.map(i => i.id === item.id ? { ...i, usage_count: i.usage_count + 1 } : i));
        toast.success("Call logged!");
        return;
      }
      const res = await fetch("/api/marketplace/usage", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ item_id: item.id, action: "call" }),
      });
      if (res.ok) { toast.success("Call logged!"); fetchItems(); }
    } catch { toast.error("Network error."); }
  }, [token, fetchItems]);

  const handleDelete = useCallback(async (item: MarketplaceItem) => {
    if (!confirm(`Delete "${item.name}"? This cannot be undone.`)) return;
    try {
      if (USE_MOCK_DATA) {
        setItems(prev => prev.filter(i => i.id !== item.id));
        toast.success("Item deleted.");
        setDetailItem(null);
        return;
      }
      const res = await fetch(`/api/marketplace/items/${item.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { toast.success("Deleted."); setDetailItem(null); fetchItems(); }
      else { const e = await res.json(); toast.error(e.detail || "Delete failed."); }
    } catch { toast.error("Network error."); }
  }, [token, fetchItems]);

  const handleIconFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1_048_576) { toast.error("Image must be < 1 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => setCreateIcon(reader.result as string);
    reader.readAsDataURL(file);
  }, []);

  // ── Derived data ───────────────────────────────────────────────────────────

  const q = search.toLowerCase();
  const filterItems = useCallback((arr: MarketplaceItem[]) =>
    q ? arr.filter(i =>
      i.name.toLowerCase().includes(q) ||
      i.description.toLowerCase().includes(q) ||
      i.owner_name?.toLowerCase().includes(q) ||
      i.chart_name?.toLowerCase().includes(q)
    ) : arr, [q]);

  const agents    = useMemo(() => filterItems(items.filter(i => i.item_type === "agent")),      [items, filterItems]);
  const mcpServers = useMemo(() => filterItems(items.filter(i => i.item_type === "mcp_server")), [items, filterItems]);

  const isOwnerOrAdmin = useCallback((item: MarketplaceItem) =>
    user?.is_admin || user?.id === item.owner_id, [user]);

  const filteredCharts = useMemo(() =>
    availableCharts.filter(c => c.toLowerCase().includes(chartFilter.toLowerCase())),
    [availableCharts, chartFilter]);

  // ── Card grid helper ───────────────────────────────────────────────────────

  const renderGrid = (list: MarketplaceItem[], emptyMsg: string, emptyIcon: React.ReactNode) => {
    if (apiLoading) return (
      <div className="flex items-center justify-center h-52">
        <p className="text-muted-foreground animate-pulse text-lg">Loading…</p>
      </div>
    );
    if (list.length === 0) return (
      <div className="flex flex-col items-center justify-center h-52 border-2 border-dashed border-border/20 rounded-2xl">
        <div className="opacity-10 mb-3">{emptyIcon}</div>
        <p className="text-muted-foreground/70">{emptyMsg}</p>
      </div>
    );
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 auto-rows-fr">
        {list.map(item => (
          <ItemCard key={item.id} item={item} onClick={() => setDetailItem(item)} />
        ))}
      </div>
    );
  };

  // ── Detail item (sync from items list when list updates) ───────────────────
  const detailItemSynced = useMemo(
    () => detailItem ? (items.find(i => i.id === detailItem.id) ?? detailItem) : null,
    [detailItem, items]
  );
  const detailSt = detailItemSynced ? getItemStyle(detailItemSynced) : null;

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 p-6 pb-16 min-h-full">

      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black gradient-text tracking-tight mb-2">
            Marketplace
          </h1>
          <p className="text-muted-foreground/80 text-sm max-w-lg leading-relaxed">
            Your team's internal App Store for AI. Publish Agents and MCP Servers once —
            let everyone discover, deploy, and use them without needing tribal knowledge.
          </p>
        </div>
        <Button
          size="lg"
          className="shrink-0 gap-2 bg-gradient-primary text-primary-foreground shadow-lg shadow-primary/20 hover:shadow-primary/30 hover:scale-[1.02] transition-all"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus size={18} /> Publish Entity
        </Button>
      </div>

      {/* ── Color legend ────────────────────────────────────────────────────── */}
      <ColorLegend devTtlDays={config.dev_ttl_days} />

      {/* ── Tabs ─────────────────────────────────────────────────────────────── */}
      <ThemedTabs defaultValue="agents" className="flex-1 flex flex-col">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <ThemedTabsList className="grid grid-cols-3 sm:w-auto sm:min-w-[360px]">
            <ThemedTabsTrigger value="agents" className="py-2.5 gap-1.5 text-sm">
              <Zap size={13} /> Agents
              <span className="ml-1 text-[10px] font-bold bg-white/5 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "agent").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="mcp-servers" className="py-2.5 gap-1.5 text-sm">
              <Blocks size={13} /> MCP Servers
              <span className="ml-1 text-[10px] font-bold bg-white/5 px-1.5 py-0.5 rounded-full">
                {items.filter(i => i.item_type === "mcp_server").length}
              </span>
            </ThemedTabsTrigger>
            <ThemedTabsTrigger value="skills" className="py-2.5 gap-1.5 text-sm">
              <Sparkles size={13} /> Skills
            </ThemedTabsTrigger>
          </ThemedTabsList>

          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/60" />
            <Input
              className="pl-8 h-9 text-sm bg-muted/20 border-white/10"
              placeholder="Filter by name, owner, chart…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-5 flex-1">
          <ThemedTabsContent value="agents">
            {renderGrid(agents, "No agents yet — publish the first one!", <Zap size={56} />)}
          </ThemedTabsContent>
          <ThemedTabsContent value="mcp-servers">
            {renderGrid(mcpServers, "No MCP servers yet — publish one!", <Blocks size={56} />)}
          </ThemedTabsContent>
          <ThemedTabsContent value="skills">
            <div className="flex flex-col items-center justify-center min-h-[420px] border-2 border-dashed border-border/20 rounded-2xl bg-gradient-to-b from-surface/30 to-background">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center mb-5 ring-4 ring-primary/5">
                <Sparkles size={36} className="text-primary/70" />
              </div>
              <h3 className="text-2xl font-black mb-3">Coming Soon</h3>
              <p className="text-muted-foreground/60 text-sm max-w-md text-center leading-relaxed">
                <strong className="text-foreground/50">Skills</strong> will let you compose
                capabilities from multiple Agents and MCP Servers into autonomous multi-step
                pipelines — without writing any glue code.
              </p>
              <div className="flex items-center gap-2 mt-5 text-xs text-primary/50">
                <ChevronRight size={12} /> Stay tuned for the next release
              </div>
            </div>
          </ThemedTabsContent>
        </div>
      </ThemedTabs>

      {/* ════════════════════════════════════════════════════════════════════════
          DETAIL MODAL — inlined as JSX (not a sub-component) to avoid re-mount
          ════════════════════════════════════════════════════════════════════════ */}
      <Dialog open={!!detailItemSynced} onOpenChange={(open) => { if (!open) setDetailItem(null); }}>
        <DialogContent className="sm:max-w-[740px] max-h-[92vh] overflow-y-auto p-0">
          {detailItemSynced && detailSt && (() => {
            const item = detailItemSynced;
            const canManage = isOwnerOrAdmin(item);
            return (
              <>
                <div className={`h-1.5 w-full ${detailSt.topBar}`} />
                <div className="px-7 pt-5 pb-4 border-b border-white/5">
                  <div className="flex items-start gap-4">
                    <EntityIcon icon={item.icon} item_type={item.item_type} size="xl" />
                    <div className="flex-1 min-w-0">
                      <DialogTitle className="text-2xl font-black leading-tight">{item.name}</DialogTitle>
                      <DialogDescription className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                        <span className="text-foreground/60">by <strong>{item.owner_name}</strong></span>
                        <span className="text-border">·</span>
                        <span className={`font-bold px-2 py-0.5 rounded-full border ${detailSt.badgeCls}`}>
                          {detailSt.label}
                        </span>
                        <span className={`font-bold px-2 py-0.5 rounded-full border text-[10px] ${
                          item.environment === "release"
                            ? "bg-blue-500/10 text-blue-400 border-blue-500/25"
                            : "bg-orange-500/10 text-orange-400 border-orange-500/25"
                        }`}>{item.environment.toUpperCase()}</span>
                        {item.deployment_status === "DEPLOYED" && (
                          <span className="flex items-center gap-1 text-emerald-400 text-[10px] font-bold">
                            <span className={`w-1.5 h-1.5 rounded-full ${detailSt.dotCls}`} /> LIVE
                          </span>
                        )}
                      </DialogDescription>
                    </div>
                  </div>
                </div>

                <div className="px-7 py-5 space-y-4">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 mb-2">Description</p>
                    <p className="text-sm text-muted-foreground/80 bg-white/[0.02] border border-white/5 rounded-xl p-4 leading-relaxed">{item.description}</p>
                  </div>

                  {item.how_to_use && (
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/50 mb-2">How to Use</p>
                      <p className="text-sm text-muted-foreground/80 bg-primary/[0.04] border border-primary/15 rounded-xl p-4 leading-relaxed">{item.how_to_use}</p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2.5">
                    <InfoTile
                      label="Chart"
                      value={item.chart_name ?? "not deployed yet"}
                      sub={item.chart_version ? `v${item.chart_version}` : undefined}
                      icon={<PackageSearch size={15} />}
                    />
                    <InfoTile
                      label="Environment"
                      value={item.environment === "release" ? "Release (persistent)" : `Dev (TTL: ${item.ttl_days ?? config.dev_ttl_days}d)`}
                      sub={item.environment === "dev" && item.ttl_remaining_days !== null
                        ? `${item.ttl_remaining_days} days remaining`
                        : undefined}
                      valueCls={item.ttl_remaining_days !== null && item.ttl_remaining_days <= 3 ? "text-red-400" : "text-foreground"}
                      icon={<Clock size={15} />}
                    />
                    {item.bitbucket_repo && (
                      <div className="flex items-start gap-3 bg-white/[0.03] border border-white/5 rounded-xl p-3">
                        <Github size={15} className="mt-0.5 text-muted-foreground/50 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground/50 mb-0.5">Repository</p>
                          <a href={item.bitbucket_repo} target="_blank" rel="noreferrer"
                            className="text-sm text-primary hover:underline truncate block">
                            View Source Code ↗
                          </a>
                        </div>
                      </div>
                    )}
                    {item.url_to_connect && (
                      <div className="flex items-start gap-3 bg-white/[0.03] border border-white/5 rounded-xl p-3">
                        <ExternalLink size={15} className="mt-0.5 text-muted-foreground/50 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground/50 mb-0.5">Connection URL</p>
                          <a href={item.url_to_connect} target="_blank" rel="noreferrer"
                            className="text-sm text-primary hover:underline truncate block">{item.url_to_connect}</a>
                        </div>
                      </div>
                    )}
                    <InfoTile
                      label="Created"
                      value={new Date(item.created_at).toLocaleDateString()}
                      icon={<Calendar size={15} />}
                    />
                    {item.tools_exposed?.length > 0 && (
                      <InfoTile
                        label="Tools Exposed"
                        value={item.tools_exposed.map(t => t.name).join(", ")}
                        icon={<Blocks size={15} />}
                      />
                    )}
                  </div>

                  <div className="flex gap-10 pt-4 border-t border-white/5 px-1">
                    <StatBig value={item.usage_count} label="Total Calls" color="text-primary" />
                    <StatBig value={item.unique_users} label="Unique Users" color="text-emerald-400" />
                    {item.tools_exposed?.length > 0 && (
                      <StatBig value={item.tools_exposed.length} label="Tools" color="text-violet-400" />
                    )}
                  </div>
                </div>

                <div className="px-7 py-4 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-3 bg-black/10">
                  <div>{canManage && (
                    <Button variant="destructive" size="sm" className="gap-1.5" onClick={() => handleDelete(item)}>
                      <Trash2 size={13} /> Delete
                    </Button>
                  )}</div>
                  <div className="flex flex-wrap gap-2 justify-end">
                    {canManage && item.deployment_status === "BUILT" && (<>
                      <Button size="sm" variant="outline"
                        className="gap-1.5 border-violet-500/40 text-violet-400 hover:bg-violet-500 hover:text-white hover:border-violet-500"
                        onClick={() => { setDetailItem(null); openDeploy(item, false); }}>
                        <Cloud size={13} /> Deploy Dev
                      </Button>
                      <Button size="sm" variant="outline"
                        className="gap-1.5 border-emerald-500/40 text-emerald-400 hover:bg-emerald-500 hover:text-white hover:border-emerald-500"
                        onClick={() => { setDetailItem(null); openDeploy(item, false, "release"); }}>
                        <Rocket size={13} /> Deploy Release
                      </Button>
                    </>)}
                    {canManage && item.deployment_status === "DEPLOYED" && (
                      <Button size="sm" variant="outline"
                        className="gap-1.5 border-amber-500/40 text-amber-400 hover:bg-amber-500 hover:text-white hover:border-amber-500"
                        onClick={() => { setDetailItem(null); openDeploy(item, true); }}>
                        <RefreshCw size={13} /> Redeploy
                      </Button>
                    )}
                    {canManage && (item.deployment_status === "BUILT" || item.deployment_status === "DEPLOYED") && (
                      <Button size="sm" variant="outline" className="gap-1.5" onClick={() => handleClone(item)}>
                        <Copy size={13} /> Fork
                      </Button>
                    )}
                    {item.deployment_status === "DEPLOYED" && (
                      <Button size="sm" className="gap-1.5 bg-primary text-primary-foreground" onClick={() => handleCall(item)}>
                        <Zap size={13} /> Run / Call
                      </Button>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>

      {/* ════════════════════════════════════════════════════════════════════════
          DEPLOY / REDEPLOY MODAL
          Step 1: pick environment + filter & select chart from Artifactory
          Step 2: pick version → confirm
          ════════════════════════════════════════════════════════════════════════ */}
      <Dialog open={isDeployOpen} onOpenChange={setIsDeployOpen}>
        <DialogContent className="sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-black">
              {isRedeploy ? <RefreshCw size={18} className="text-amber-400" /> : <Rocket size={18} className="text-violet-400" />}
              {isRedeploy ? "Redeploy" : "Deploy"} — {deployItem?.name}
            </DialogTitle>
            <DialogDescription>
              Select the Helm chart and version from your Artifactory registry.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {/* Environment toggle */}
            <div>
              <Label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 mb-2 block">Environment</Label>
              <div className="grid grid-cols-2 gap-2">
                {(["dev", "release"] as const).map(env => (
                  <button key={env} type="button"
                    onClick={() => handleDeployEnvChange(env)}
                    className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${
                      deployEnv === env
                        ? env === "dev"
                          ? "border-violet-500 bg-violet-500/15 text-violet-400"
                          : "border-emerald-500 bg-emerald-500/15 text-emerald-400"
                        : "border-border/30 text-muted-foreground hover:border-border/60"
                    }`}
                  >
                    {env === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
                    {env.charAt(0).toUpperCase() + env.slice(1)}
                  </button>
                ))}
              </div>
              {deployEnv === "dev" && (
                <p className="text-xs text-violet-400/70 mt-2 flex items-center gap-1.5">
                  <Clock size={11} /> Auto-expires after {config.dev_ttl_days} days
                </p>
              )}
            </div>

            {/* Chart picker */}
            <div>
              <Label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 mb-2 block">
                Select Chart from Artifactory ({deployEnv})
              </Label>
              <div className="relative mb-2">
                <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50" />
                <Input
                  className="pl-8 h-8 text-sm bg-muted/20 border-white/10"
                  placeholder="Filter charts…"
                  value={chartFilter}
                  onChange={e => setChartFilter(e.target.value)}
                />
              </div>
              <div className="border border-white/10 rounded-xl overflow-hidden max-h-40 overflow-y-auto bg-black/20">
                {filteredCharts.length === 0 ? (
                  <p className="text-center text-muted-foreground/50 text-xs py-6">No charts found</p>
                ) : filteredCharts.map(chart => (
                  <button
                    key={chart}
                    type="button"
                    onClick={() => handleChartSelect(chart)}
                    className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-2.5 transition-colors ${
                      selectedChart === chart
                        ? "bg-primary/20 text-primary font-semibold"
                        : "hover:bg-white/5 text-foreground/70"
                    }`}
                  >
                    <PackageSearch size={13} className="shrink-0 text-muted-foreground/50" />
                    <span className="truncate">{chart}</span>
                    {selectedChart === chart && <span className="ml-auto text-[10px] font-bold text-primary">✓</span>}
                  </button>
                ))}
              </div>
            </div>

            {/* Version selector (appears after chart selection) */}
            {selectedChart && (
              <div>
                <Label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground/60 mb-2 block">
                  Chart Version — <span className="text-primary normal-case font-semibold">{selectedChart}</span>
                </Label>
                {chartVersions.length === 0 ? (
                  <p className="text-sm text-muted-foreground/50 animate-pulse">Loading versions…</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {chartVersions.map(v => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => setSelectedVersion(v)}
                        className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                          selectedVersion === v
                            ? "border-primary bg-primary/20 text-primary"
                            : "border-border/30 text-muted-foreground hover:border-border/60"
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Summary */}
            {selectedChart && selectedVersion && (
              <div className={`flex items-start gap-3 p-3 rounded-xl border text-sm ${
                deployEnv === "dev"
                  ? "bg-violet-500/10 border-violet-500/25 text-violet-300"
                  : "bg-emerald-500/10 border-emerald-500/25 text-emerald-300"
              }`}>
                {deployEnv === "dev" ? <Cloud size={15} className="mt-0.5 shrink-0" /> : <Rocket size={15} className="mt-0.5 shrink-0" />}
                <div>
                  <strong>{isRedeploy ? "Redeploying" : "Deploying"}</strong>{" "}
                  <span className="font-mono text-xs bg-black/20 px-1 py-0.5 rounded">{selectedChart}@{selectedVersion}</span>{" "}
                  to <strong>{deployEnv.toUpperCase()}</strong>.
                  {deployEnv === "dev" && <span className="text-[11px] block mt-0.5 opacity-70"> Auto-expires in {config.dev_ttl_days} days.</span>}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsDeployOpen(false)}>Cancel</Button>
            <Button
              disabled={!selectedChart || !selectedVersion || deployLoading}
              onClick={handleDeploy}
              className={deployEnv === "dev"
                ? "bg-violet-600 hover:bg-violet-500 text-white gap-1.5"
                : "bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"}
            >
              {deployEnv === "dev" ? <Cloud size={14} /> : <Rocket size={14} />}
              {deployLoading ? "Working…" : isRedeploy ? "Redeploy" : "Deploy"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ════════════════════════════════════════════════════════════════════════
          CREATE MODAL — each piece of form state is a separate useState so that
          no sub-component is re-created on every keystroke.
          ════════════════════════════════════════════════════════════════════════ */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="sm:max-w-[760px] max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl font-black">
              <Sparkles size={20} className="text-primary" /> Publish New Entity
            </DialogTitle>
            <DialogDescription>
              Register an Agent or MCP Server. It will be immediately <strong>BUILT</strong> and ready to deploy — no separate build step needed.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreate} className="mt-3 space-y-5">
            {/* Icon upload + type selector row */}
            <div className="flex items-start gap-5 p-4 rounded-2xl border border-white/5 bg-white/[0.02]">
              <div
                className="w-24 h-24 rounded-2xl border-2 border-dashed border-white/10 bg-black/20 flex items-center justify-center cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-all shrink-0 overflow-hidden group"
                onClick={() => iconInputRef.current?.click()}
              >
                {createIcon ? (
                  <img src={createIcon} alt="preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="flex flex-col items-center gap-1 text-muted-foreground/30 group-hover:text-muted-foreground/60 transition-colors">
                    <UploadCloud size={22} />
                    <span className="text-[10px] font-medium">Upload icon</span>
                  </div>
                )}
              </div>
              <input ref={iconInputRef} type="file" accept="image/*" className="hidden" onChange={handleIconFile} />
              <div className="flex-1">
                <p className="text-sm font-semibold mb-1 text-foreground/80">Entity Icon</p>
                <p className="text-xs text-muted-foreground/60 mb-3">PNG, JPG or SVG · max 1 MB · stored in database</p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" className="gap-1.5 h-8 text-xs" onClick={() => iconInputRef.current?.click()}>
                    <UploadCloud size={12} /> {createIcon ? "Change" : "Choose"}
                  </Button>
                  {createIcon && (
                    <Button type="button" variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={() => setCreateIcon("")}>Remove</Button>
                  )}
                </div>
              </div>
            </div>

            {/* Type + Name row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">
                  Type <span className="text-destructive">*</span>
                </Label>
                <div className="grid grid-cols-2 gap-2">
                  {(["agent", "mcp_server"] as const).map(type => (
                    <button
                      key={type} type="button"
                      onClick={() => setCreateType(type)}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-sm font-semibold transition-all ${
                        createType === type
                          ? "border-primary bg-primary/15 text-primary"
                          : "border-border/30 text-muted-foreground hover:border-border/60"
                      }`}
                    >
                      {type === "agent" ? <Zap size={14} /> : <Blocks size={14} />}
                      {type === "agent" ? "Agent" : "MCP Server"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="c-name" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="c-name"
                  required
                  placeholder="e.g. Data Analysis Agent"
                  className="bg-muted/20 border-white/10"
                  value={createName}
                  onChange={e => setCreateName(e.target.value)}
                />
              </div>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="c-desc" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="c-desc"
                required
                className="min-h-[88px] bg-muted/20 border-white/10 resize-none"
                placeholder="What does this entity do? When should someone use it?"
                value={createDesc}
                onChange={e => setCreateDesc(e.target.value)}
              />
            </div>

            {/* Repo */}
            <div className="space-y-2">
              <Label htmlFor="c-repo" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">
                Bitbucket Repo URL
              </Label>
              <Input
                id="c-repo"
                placeholder="https://bitbucket.company.internal/projects/…"
                className="bg-muted/20 border-white/10"
                value={createRepo}
                onChange={e => setCreateRepo(e.target.value)}
              />
            </div>

            {/* How to Use */}
            <div className="space-y-2">
              <Label htmlFor="c-usage" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/60">
                How to Use
              </Label>
              <Textarea
                id="c-usage"
                className="min-h-[72px] bg-muted/20 border-white/10 resize-none"
                placeholder="Example prompts, prerequisites, expected inputs…"
                value={createHowTo}
                onChange={e => setCreateHowTo(e.target.value)}
              />
            </div>

            <DialogFooter className="pt-4 border-t border-white/5 gap-2">
              <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
              <Button
                type="submit"
                disabled={createLoading || !createName.trim() || !createDesc.trim()}
                className="gap-1.5 bg-gradient-primary text-primary-foreground px-6 font-bold"
              >
                <Plus size={15} />
                {createLoading ? "Publishing…" : "Publish Entity"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
