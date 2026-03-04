import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, Store, Search, Database, BookOpen,
  MessageSquare, ExternalLink, Lock,
  LogIn, Eye, Zap, Activity, Terminal,
  Cpu, Layers, Bot,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { analyticsService, appConfigService } from "@/lib/api-service";
import { useAuth } from "@/context/auth-context";

// ─── Types ──────────────────────────────────────────────────────────────────

interface AppConfig {
  environment: string;
  version: string;
  confluence_url: string;
  openwebui_url: string;
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
  icon: React.ComponentType<{ className?: string }>;
  tab: string;
  route: string;
  gradient: string;
  borderColor: string;
  preview: React.ReactNode;
}

// ─── Helper ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// ─── Miniature feature previews ──────────────────────────────────────────────

function MarketplacePreview() {
  const items = [
    { name: "code-review-agent", kind: "Agent", color: "bg-violet-500/20 text-violet-300" },
    { name: "jenkins-mcp", kind: "MCP Server", color: "bg-blue-500/20 text-blue-300" },
    { name: "sql-analyst", kind: "Agent", color: "bg-emerald-500/20 text-emerald-300" },
  ];
  return (
    <div className="space-y-2 p-3">
      {items.map((item) => (
        <div key={item.name} className="flex items-center justify-between rounded-md bg-white/5 px-3 py-2">
          <div className="flex items-center gap-2">
            <Bot className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs text-foreground font-mono">{item.name}</span>
          </div>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${item.color}`}>{item.kind}</span>
        </div>
      ))}
      <div className="mt-2 flex gap-2">
        <div className="h-6 flex-1 rounded bg-violet-500/30 flex items-center justify-center">
          <span className="text-[10px] text-violet-200 font-medium">+ Deploy Agent</span>
        </div>
        <div className="h-6 flex-1 rounded bg-blue-500/30 flex items-center justify-center">
          <span className="text-[10px] text-blue-200 font-medium">+ New MCP</span>
        </div>
      </div>
    </div>
  );
}

function ResearchPreview() {
  return (
    <div className="p-3 space-y-2">
      <div className="rounded-md bg-white/5 px-3 py-2 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        <span className="text-xs font-mono text-cyan-300">firmware_v2.bin</span>
        <span className="ml-auto text-[10px] text-muted-foreground">Analyzing…</span>
      </div>
      <div className="rounded-md bg-black/30 px-3 py-2 text-[10px] font-mono text-green-400 leading-relaxed">
        <span className="text-muted-foreground">LLM&gt;</span> Found 3 suspicious<br />
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;function patterns in<br />
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;sub_0x4012A0…
      </div>
      <div className="flex items-center gap-1">
        <Cpu className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] text-muted-foreground">IDA Pro connected via MCP</span>
      </div>
    </div>
  );
}

function BIPreview() {
  return (
    <div className="p-3 space-y-2">
      <div className="rounded-md bg-black/30 px-3 py-2 text-[10px] font-mono text-yellow-300">
        <span className="text-muted-foreground">You:</span> Show top 5 revenue regions<br />
        <span className="text-emerald-400">SQL:</span> SELECT region, SUM(…)…
      </div>
      <div className="rounded-md bg-white/5 px-3 py-2">
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>Region</span><span>Revenue</span>
        </div>
        {[["North", "$4.2M"], ["South", "$3.1M"], ["West", "$2.8M"]].map(([r, v]) => (
          <div key={r} className="flex justify-between text-[10px]">
            <span className="text-foreground">{r}</span>
            <span className="text-emerald-400 font-medium">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Feature Teaser Card ──────────────────────────────────────────────────────

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
      className={`relative rounded-2xl border ${feature.borderColor} overflow-hidden cursor-pointer`}
      style={{ background: "hsl(var(--surface) / 0.8)" }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
      onClick={() => hasAccess && onNavigate(feature.route)}
    >
      {/* Gradient top stripe */}
      <div className={`h-1 w-full bg-gradient-to-r ${feature.gradient}`} />

      <div className="p-6">
        {/* Icon + title row */}
        <div className="flex items-start justify-between mb-3">
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center shadow-lg`}>
            <feature.icon className="w-5 h-5 text-white" />
          </div>
        </div>

        <p className="text-xs text-muted-foreground mb-1">{feature.tagline}</p>
        <h3 className="text-lg font-bold text-foreground mb-2">{feature.title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>

        {/* CTA */}
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
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3">
              <Lock className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <p className="text-sm font-medium text-amber-600 dark:text-amber-400 leading-snug">
                You don't have access yet.{" "}
                <span className="font-semibold">Contact DevOps</span> to request permission.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Floating preview panel — dark overlay so content is always readable in both themes */}
      <AnimatePresence>
        {hovered && (
          <motion.div
            className="absolute inset-x-0 bottom-0 rounded-b-2xl overflow-hidden"
            style={{ background: "rgba(10, 10, 20, 0.88)" }}
            initial={{ y: "100%", opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: "100%", opacity: 0 }}
            transition={{ type: "spring", stiffness: 400, damping: 35 }}
          >
            <div className="px-3 pt-2 border-t border-white/10">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Preview</p>
            </div>
            {feature.preview}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Stat Badge ───────────────────────────────────────────────────────────────

function StatBadge({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string | number }) {
  return (
    <motion.div
      className="flex flex-col items-center gap-1 p-4 rounded-xl glass border border-border/40 bg-surface/60"
      whileHover={{ scale: 1.03 }}
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
      title: "Binary Research",
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
    success: "bg-success/10 text-success border-success/20",
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
              Welcome, {user?.full_name || user?.username}!
            </h1>
            <p className="text-lg text-muted-foreground mb-2 max-w-3xl mx-auto">
              Where <span className="text-foreground font-semibold">intelligence meets infrastructure.</span>{" "}
              A living AI ecosystem that evolves with your team — connecting models, tools, data,
              and workflows into a single, continuously expanding platform.
            </p>
            <p className="text-sm text-muted-foreground max-w-2xl mx-auto">
              Every team contributes. Every integration amplifies. Explore what's possible below.
            </p>
          </motion.div>
        </div>

        {/* Animated background orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <motion.div
            className="absolute top-1/4 left-1/4 w-40 h-40 bg-primary/15 rounded-full blur-3xl"
            animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 5, repeat: Infinity }}
          />
          <motion.div
            className="absolute bottom-1/4 right-1/4 w-32 h-32 bg-secondary/15 rounded-full blur-3xl"
            animate={{ scale: [1.2, 1, 1.2], opacity: [0.4, 0.2, 0.4] }}
            transition={{ duration: 4, repeat: Infinity, delay: 1.5 }}
          />
          <motion.div
            className="absolute top-1/2 right-1/3 w-20 h-20 bg-accent/10 rounded-full blur-2xl"
            animate={{ scale: [1, 1.5, 1], opacity: [0.2, 0.4, 0.2] }}
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
