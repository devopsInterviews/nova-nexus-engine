import { motion } from "framer-motion";
import {
  ArrowRight, Store, Search, Database, BookOpen,
  MessageSquare, ExternalLink, Lock,
  LogIn, Eye, Zap, Activity, Terminal,
  Cpu, Layers, Bot, KeyRound,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { analyticsService, appConfigService } from "@/lib/api-service";
import { useAuth } from "@/context/auth-context";

// ─── Types ──────────────────────────────────────────────────────────────────

interface AppConfig {
  environment: string;
  version: string;
  confluence_url: string;
  openwebui_url: string;
  developer_portal_url: string;
}

interface UserStats {
  login_count: number;
  last_login: string | null;
  page_views_30d: number;
  test_runs_total: number;
  marketplace_usage_total: number;
  member_since: string | null;
  recent_activities: Array<{
    action: string;
    type: string;
    time: string;
    status_type: "success" | "warning" | "error";
  }>;
}

interface FeatureCard {
  id: string;
  title: string;
  tagline: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  tab: string;
  route: string;
  gradient: string;
  borderColor: string;
  preview: ReactNode;
}

// ─── Helper ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// ─── Miniature feature previews (theme-aware: work in both light & dark) ─────

const rowCls = "flex items-center justify-between rounded-md border border-border/40 bg-muted/50 px-3 py-1.5";

function MarketplacePreview() {
  const items = [
    { name: "code-review-agent", kind: "Agent", accent: "text-violet-500 bg-violet-500/10 border-violet-500/20" },
    { name: "jenkins-mcp", kind: "MCP Server", accent: "text-blue-500 bg-blue-500/10 border-blue-500/20" },
    { name: "sql-analyst", kind: "Agent", accent: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20" },
  ];
  return (
    <div className="space-y-1.5">
      {items.map((item) => (
        <div key={item.name} className={rowCls}>
          <div className="flex items-center gap-2">
            <Bot className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs font-mono text-foreground">{item.name}</span>
          </div>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${item.accent}`}>{item.kind}</span>
        </div>
      ))}
      <div className="flex gap-2 pt-1">
        <div className="h-6 flex-1 rounded border border-violet-500/30 bg-violet-500/10 flex items-center justify-center">
          <span className="text-[10px] text-violet-600 dark:text-violet-400 font-medium">+ Deploy Agent</span>
        </div>
        <div className="h-6 flex-1 rounded border border-blue-500/30 bg-blue-500/10 flex items-center justify-center">
          <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium">+ New MCP</span>
        </div>
      </div>
    </div>
  );
}

function ResearchPreview() {
  return (
    <div className="space-y-1.5">
      <div className={rowCls}>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
          <span className="text-xs font-mono text-foreground">firmware_v2.bin</span>
        </div>
        <span className="text-[10px] text-muted-foreground">Analyzing…</span>
      </div>
      <div className="rounded-md border border-border/40 bg-muted/50 px-3 py-2 text-[10px] font-mono leading-relaxed">
        <span className="text-muted-foreground">LLM›</span>{" "}
        <span className="text-foreground">Found 3 suspicious</span><br />
        <span className="pl-6 text-foreground">function patterns in</span><br />
        <span className="pl-6 text-cyan-600 dark:text-cyan-400">sub_0x4012A0…</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Cpu className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] text-muted-foreground">IDA Pro connected via MCP</span>
      </div>
    </div>
  );
}

function BIPreview() {
  const rows = [["North", "$4.2M"], ["South", "$3.1M"], ["West", "$2.8M"]];
  return (
    <div className="space-y-1.5">
      <div className="rounded-md border border-border/40 bg-muted/50 px-3 py-2 text-[10px] font-mono leading-relaxed">
        <span className="text-muted-foreground">You: </span>
        <span className="text-foreground">Show top 5 revenue regions</span><br />
        <span className="text-emerald-600 dark:text-emerald-400">SQL: </span>
        <span className="text-foreground">SELECT region, SUM(…)…</span>
      </div>
      <div className={rowCls}>
        <span className="text-[10px] text-muted-foreground font-medium">Region</span>
        <span className="text-[10px] text-muted-foreground font-medium">Revenue</span>
      </div>
      {rows.map(([r, v]) => (
        <div key={r} className={rowCls}>
          <span className="text-xs text-foreground">{r}</span>
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">{v}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Feature Teaser Card ──────────────────────────────────────────────────────
// Uses a cross-fade technique: main content fades out, preview fades in.
// This avoids any dark-overlay clipping issues in light mode.

function FeatureTeaserCard({
  feature,
  hasAccess,
  onNavigate,
}: {
  feature: FeatureCard;
  hasAccess: boolean;
  onNavigate: (route: string) => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      className={`relative rounded-2xl border ${feature.borderColor} cursor-pointer`}
      style={{ background: "hsl(var(--surface) / 0.8)" }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
      onClick={() => hasAccess && onNavigate(feature.route)}
    >
      {/* Gradient top stripe */}
      <div className={`h-1 w-full bg-gradient-to-r ${feature.gradient} rounded-t-2xl`} />

      {/* Fixed-height inner area so both panels share the same space */}
      <div className="relative p-6" style={{ minHeight: 260 }}>

        {/* ── Main content panel ── */}
        <motion.div
          animate={{ opacity: hovered ? 0 : 1, y: hovered ? -6 : 0 }}
          transition={{ duration: 0.18 }}
          style={{ pointerEvents: hovered ? "none" : "auto" }}
        >
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center shadow-lg mb-3`}>
            <feature.icon className="w-5 h-5 text-white" />
          </div>
          <p className="text-xs text-muted-foreground mb-1">{feature.tagline}</p>
          <h3 className="text-lg font-bold text-foreground mb-2">{feature.title}</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>

          <div className="mt-4">
            {hasAccess ? (
              <Button
                size="sm"
                className={`bg-gradient-to-r ${feature.gradient} text-white border-0 hover:opacity-90 transition-opacity group`}
                onClick={(e) => { e.stopPropagation(); onNavigate(feature.route); }}
              >
                Go to {feature.title}
                <ArrowRight className="ml-1 w-3 h-3 group-hover:translate-x-1 transition-transform" />
              </Button>
            ) : (
              <div className="flex items-start gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3">
                <Lock className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <p className="text-sm font-medium text-amber-600 dark:text-amber-400 leading-snug">
                  You don't have access yet.{" "}
                  <span className="font-semibold">Contact DevOps</span> to request permission.
                </p>
              </div>
            )}
          </div>
        </motion.div>

        {/* ── Preview panel (cross-fades in on hover) ── */}
        <motion.div
          className="absolute inset-0 p-6"
          animate={{ opacity: hovered ? 1 : 0, y: hovered ? 0 : 6 }}
          initial={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.18 }}
          style={{ pointerEvents: hovered ? "auto" : "none" }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Preview
          </p>
          {feature.preview}
        </motion.div>
      </div>
    </motion.div>
  );
}

// ─── Stat Badge ───────────────────────────────────────────────────────────────

function StatBadge({ icon: Icon, label, value }: { icon: ComponentType<{ className?: string }>; label: string; value: string | number }) {
  return (
    <motion.div
      className="flex flex-col items-center gap-1 p-4 rounded-xl border border-border/40 bg-surface/80"
      whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
    >
      <Icon className="w-5 h-5 text-primary" />
      <span className="text-2xl font-bold text-foreground">{value}</span>
      <span className="text-xs text-muted-foreground text-center">{label}</span>
    </motion.div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);

  useEffect(() => {
    appConfigService.getConfig().then(res => {
      if (res.status === "success" && res.data) setAppConfig(res.data);
    }).catch(() => {});

    analyticsService.getUserStats().then(res => {
      if (res.status === "success" && res.data) setUserStats(res.data);
    }).catch(() => {}).finally(() => setIsLoadingStats(false));

    analyticsService.logPageView({ path: "/", title: "Home", loadTime: performance.now() });
  }, []);

  const hasAccess = (tab: string) =>
    user?.is_admin || (user?.allowed_tabs?.includes(tab) ?? false);

  const features: FeatureCard[] = [
    {
      id: "marketplace",
      title: "AI Marketplace",
      tagline: "Want to integrate AI into your systems?",
      description:
        "Build and deploy custom AI Agents and MCP Servers. Connect them to OpenWebUI, your IDE, or any tool — and automate complex workflows in minutes.",
      icon: Store,
      tab: "Marketplace",
      route: "/marketplace",
      gradient: "from-violet-500 to-purple-600",
      borderColor: "border-violet-500/20",
      preview: <MarketplacePreview />,
    },
    {
      id: "research",
      title: "Binary File Research",
      tagline: "Want to use LLM to research binary files?",
      description:
        "Connect your IDA Pro workstation to the AI Portal and ask the LLM anything about your binaries. Reverse-engineering meets generative AI.",
      icon: Search,
      tab: "Research",
      route: "/research",
      gradient: "from-cyan-500 to-blue-600",
      borderColor: "border-cyan-500/20",
      preview: <ResearchPreview />,
    },
    {
      id: "bi",
      title: "Business Intelligence",
      tagline: "Want business intelligence from your databases?",
      description:
        "Ask questions in plain language and get AI-generated SQL, results, and insights directly from your production or analytics databases.",
      icon: Database,
      tab: "BI",
      route: "/bi",
      gradient: "from-emerald-500 to-green-600",
      borderColor: "border-emerald-500/20",
      preview: <BIPreview />,
    },
  ];

  const statusColors: Record<string, string> = {
    success: "bg-green-100 text-green-800 border-green-300 dark:bg-success/10 dark:text-success dark:border-success/20",
    warning: "bg-warning/10 text-warning border-warning/20",
    error: "bg-destructive/10 text-destructive border-destructive/20",
  };

  return (
    <div className="space-y-10 pb-8">

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <motion.section
        className="relative overflow-hidden rounded-2xl bg-gradient-hero p-8 text-center glass border border-border/30"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7 }}
      >
        <div className="relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.7 }}
          >
            <h1 className="text-4xl font-bold mb-3 gradient-text">
              Welcome, {user?.full_name?.split(' ')[0] || user?.username}!
            </h1>
            <p className="text-lg font-semibold text-foreground mb-1">
              Your AI platform for intelligent workflows and connected systems.
            </p>
            <p className="text-sm text-muted-foreground max-w-2xl mx-auto">
              Connecting models, tools, data, and teams — all in one place.
            </p>
          </motion.div>
        </div>

        {/* Animated background orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <motion.div
            className="absolute top-1/4 left-1/4 w-40 h-40 bg-primary/15 rounded-full blur-3xl"
            animate={{ opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 5, repeat: Infinity }}
          />
          <motion.div
            className="absolute bottom-1/4 right-1/4 w-32 h-32 bg-secondary/15 rounded-full blur-3xl"
            animate={{ opacity: [0.4, 0.2, 0.4] }}
            transition={{ duration: 4, repeat: Infinity, delay: 1.5 }}
          />
          <motion.div
            className="absolute top-1/2 right-1/3 w-20 h-20 bg-accent/10 rounded-full blur-2xl"
            animate={{ opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 3.5, repeat: Infinity, delay: 0.7 }}
          />
        </div>
      </motion.section>

      {/* ── Feature Teasers ──────────────────────────────────────────────── */}
      <section>
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="mb-6"
        >
          <h2 className="text-2xl font-bold text-foreground">What can you do here?</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Hover over a card to peek inside. Click to open — or request access if you don't have it yet.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={feature.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 + i * 0.1 }}
            >
              <FeatureTeaserCard
                feature={feature}
                hasAccess={hasAccess(feature.tab)}
                onNavigate={navigate}
              />
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── Get Started + AI Tools ────────────────────────────────────────── */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Documentation */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <Card className="glass border-border/50 h-full">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center">
                  <BookOpen className="w-4 h-4 text-white" />
                </div>
                Don't know where to start?
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Visit the company documentation to find guides, tutorials, and API references
                for everything the AI Portal has to offer.
              </p>
              <Button
                className="w-full bg-gradient-to-r from-orange-400 to-pink-500 text-white border-0 hover:opacity-90 group"
                onClick={() => {
                  const url = appConfig?.confluence_url;
                  if (url) window.open(url, "_blank", "noopener,noreferrer");
                }}
                disabled={!appConfig?.confluence_url}
              >
                <BookOpen className="mr-2 w-4 h-4" />
                Open Documentation
                <ExternalLink className="ml-2 w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </Button>

              <div className="border-t border-border/30 pt-4 space-y-3">
                <p className="text-sm text-muted-foreground">
                  To use Agents and MCP Servers you need an <strong className="text-foreground/80">LLM API key</strong> and
                  an <strong className="text-foreground/80">upstream token</strong>. Generate them in the developer portal
                  and configure them in your client or agent settings.
                </p>
                <Button
                  className="w-full bg-gradient-to-r from-violet-500/20 to-purple-600/20 hover:from-violet-500/30 hover:to-purple-600/30 text-violet-300 hover:text-violet-200 border border-violet-500/30 hover:border-violet-500/60 transition-all group"
                  onClick={() => {
                    const url = appConfig?.developer_portal_url;
                    if (url) window.open(url, "_blank", "noopener,noreferrer");
                  }}
                  disabled={!appConfig?.developer_portal_url}
                >
                  <KeyRound className="mr-2 w-4 h-4" />
                  Create API Keys &amp; Tokens
                  <ExternalLink className="ml-2 w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Chat with AI + IDE Tools */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <Card className="glass border-border/50 h-full">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-indigo-500 flex items-center justify-center">
                  <MessageSquare className="w-4 h-4 text-white" />
                </div>
                Chat &amp; Code with AI
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* OpenWebUI */}
              <div>
                <p className="text-sm text-muted-foreground mb-2">
                  Want to chat with our latest models? Connect your Agents and MCP Servers to OpenWebUI
                  for a full conversational AI experience.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-sky-500/30 hover:bg-sky-500/10 hover:text-sky-300 group"
                  onClick={() => {
                    const url = appConfig?.openwebui_url;
                    if (url) window.open(url, "_blank", "noopener,noreferrer");
                  }}
                  disabled={!appConfig?.openwebui_url}
                >
                  <MessageSquare className="mr-2 w-4 h-4 text-sky-400" />
                  Open OpenWebUI
                  <ExternalLink className="ml-auto w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                </Button>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-border/40" />
                <span className="text-xs text-muted-foreground">or work from your IDE</span>
                <div className="flex-1 h-px bg-border/40" />
              </div>

              {/* IDE Tools */}
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="border-indigo-500/30 hover:bg-indigo-500/10 hover:text-indigo-300 group"
                  onClick={() => window.open("https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev", "_blank", "noopener,noreferrer")}
                >
                  <Terminal className="mr-1.5 w-3.5 h-3.5 text-indigo-400" />
                  Download Cline
                  <ExternalLink className="ml-auto w-2.5 h-2.5 opacity-60" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-violet-500/30 hover:bg-violet-500/10 hover:text-violet-300 group"
                  onClick={() => window.open("https://opencode.ai", "_blank", "noopener,noreferrer")}
                >
                  <Layers className="mr-1.5 w-3.5 h-3.5 text-violet-400" />
                  Download OpenCode
                  <ExternalLink className="ml-auto w-2.5 h-2.5 opacity-60" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </section>

      {/* ── Your Activity ─────────────────────────────────────────────────── */}
      <section>
        <motion.h2
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.8 }}
        >
          Your Activity
        </motion.h2>

        {/* Stats row */}
        <motion.div
          className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
        >
          <StatBadge
            icon={LogIn}
            label="Total logins"
            value={isLoadingStats ? "…" : userStats?.login_count ?? 0}
          />
          <StatBadge
            icon={Eye}
            label="Pages visited (30d)"
            value={isLoadingStats ? "…" : userStats?.page_views_30d ?? 0}
          />
          <StatBadge
            icon={Zap}
            label="Test runs"
            value={isLoadingStats ? "…" : userStats?.test_runs_total ?? 0}
          />
          <StatBadge
            icon={Store}
            label="Marketplace actions"
            value={isLoadingStats ? "…" : userStats?.marketplace_usage_total ?? 0}
          />
        </motion.div>

        {/* Recent activity feed */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0 }}
        >
          <Card className="glass border-border/50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary" />
                  Recent Actions
                </CardTitle>
                {userStats?.last_login && (
                  <span className="text-xs text-muted-foreground">
                    Last login: {formatDate(userStats.last_login)}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {isLoadingStats ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-10 rounded-lg bg-surface-elevated/40 animate-pulse" />
                  ))}
                </div>
              ) : !userStats?.recent_activities?.length ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p>No recent activity yet.</p>
                  <p className="text-xs mt-1">Start exploring the portal — your actions will appear here.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {userStats.recent_activities.map((activity, index) => (
                    <motion.div
                      key={index}
                      className="flex items-center justify-between py-2.5 px-4 rounded-lg bg-surface-elevated/40 hover:bg-surface-elevated transition-colors group"
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 1.05 + index * 0.06 }}
                      whileHover={{ x: 3 }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                        <div>
                          <p className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                            {activity.action}
                          </p>
                          <p className="text-xs text-muted-foreground capitalize">{activity.type} · {activity.time}</p>
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-xs ${statusColors[activity.status_type] ?? statusColors.warning}`}
                      >
                        {activity.status_type === "success" ? "Completed" : activity.status_type === "error" ? "Failed" : "Running"}
                      </Badge>
                    </motion.div>
                  ))}
                </div>
              )}

              {userStats?.member_since && (
                <p className="text-xs text-muted-foreground mt-4 text-center">
                  Member since {formatDate(userStats.member_since)}
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </section>
    </div>
  );
}
