import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusCard } from "@/components/ui/status-card";
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp, Users, Activity, Server, Zap, Eye, PieChart, ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import { analyticsService } from "@/lib/api-service";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Metric {
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  status: "success" | "warning" | "error" | "info";
  trend: "up" | "down" | "stable";
  trendValue: string;
}

interface TopPage {
  path: string;
  views: string;
  change: string;
}

interface ErrorType {
  type: string;
  count: number;
  percentage: number;
}

interface TrafficPoint {
  hour: string;
  label: string;
  total: number;
  success: number;
  errors: number;
}

interface ActivityBreakdownItem {
  type: string;
  count: number;
}

// ─── Custom Tooltip for traffic chart ────────────────────────────────────────

function TrafficTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-background/95 p-3 shadow-lg text-xs">
      <p className="font-semibold text-foreground mb-1">{payload[0]?.payload?.label ?? label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <span className="font-medium">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

// ─── Activity type metadata ───────────────────────────────────────────────────

interface ActivityMeta {
  label: string;
  description: string;
  color: string;
}

const ACTIVITY_META: Record<string, ActivityMeta> = {
  auth:            { label: "Authentication",       description: "Login, logout, token refresh",              color: "#414FA2" },
  database:        { label: "Database (BI)",         description: "SQL queries and DB connections via BI tab", color: "#00C986" },
  mcp:             { label: "MCP / AI Tools",        description: "AI agent calls and MCP tool invocations",   color: "#55C5E2" },
  analytics:       { label: "Analytics",             description: "Dashboard and metric page views",           color: "#FFBE0A" },
  bi:              { label: "Business Intelligence", description: "BI queries and natural-language analysis",  color: "#9D4FDE" },
  testing:         { label: "Testing",               description: "Test runs and saved test configurations",   color: "#FB5606" },
  user_management: { label: "User Management",       description: "Admin operations on users and permissions", color: "#F72586" },
  marketplace:     { label: "Marketplace",           description: "Agent and MCP server deployments",         color: "#06D6A0" },
};

function activityMeta(type: string): ActivityMeta {
  return ACTIVITY_META[type] ?? { label: type, description: "Other system activity", color: "#9CA4B0" };
}

// ─── KPI metric descriptions (frontend overrides) ─────────────────────────────
// These are shown below each KPI value in the StatusCard to explain what the metric represents.
const METRIC_DESCRIPTIONS: Record<string, string> = {
  "Total Requests":   "All HTTP requests handled by the backend in the last 24 h, including API calls, page loads, and health checks.",
  "Active Sessions":  "Users currently authenticated with a valid session or JWT token — a proxy for real-time concurrency.",
  "Response Time":    "Median server-side latency across all API endpoints. High values indicate backend slowness or DB bottlenecks.",
  "Error Rate":       "Percentage of requests that returned a 4xx or 5xx status. Values above 1 % warrant investigation.",
};

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Analytics() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [topPages, setTopPages] = useState<TopPage[]>([]);
  const [errorsByType, setErrorsByType] = useState<ErrorType[]>([]);
  const [traffic, setTraffic] = useState<TrafficPoint[]>([]);
  const [activityBreakdown, setActivityBreakdown] = useState<ActivityBreakdownItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  // Which KPI card has its description expanded
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null);

  const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
    "Total Requests": Activity,
    "Active Sessions": Users,
    "Response Time": Zap,
    "Error Rate": Server,
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [metricsRes, topPagesRes, errorsRes, trafficRes, breakdownRes] = await Promise.all([
          analyticsService.getKeyMetrics(),
          analyticsService.getTopPages(5, 24),
          analyticsService.getErrorAnalysis(24),
          analyticsService.getTrafficOverTime(24),
          analyticsService.getUserActivityBreakdown(24),
        ]);

        if (metricsRes.status === "success" && metricsRes.data) {
          setMetrics(
            metricsRes.data.metrics.map((m) => ({
              ...m,
              icon: iconMap[m.title] ?? Activity,
              // Enrich with a more detailed description if we have one
              description: METRIC_DESCRIPTIONS[m.title] ?? m.description,
            }))
          );
        }

        if (topPagesRes.status === "success" && topPagesRes.data) {
          setTopPages(topPagesRes.data.topPages);
        }

        if (errorsRes.status === "success" && errorsRes.data) {
          setErrorsByType(errorsRes.data.errorsByType);
        }

        if (trafficRes.status === "success" && trafficRes.data) {
          setTraffic(trafficRes.data.traffic);
        }

        if (breakdownRes.status === "success" && breakdownRes.data) {
          setActivityBreakdown(breakdownRes.data.breakdown);
        }
      } catch (error) {
        console.error("Failed to fetch analytics data:", error);
        // Keep existing state — next auto-refresh may succeed
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    analyticsService.logPageView({ path: "/analytics", title: "Analytics Dashboard", loadTime: performance.now() });

    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const hasActivity = activityBreakdown.length > 0;

  // Enrich breakdown with friendly labels so the chart and tooltip are human-readable
  const enrichedBreakdown = activityBreakdown.map((item) => ({
    ...item,
    ...activityMeta(item.type),
  }));

  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <h1 className="text-3xl font-bold gradient-text mb-2">Analytics Dashboard</h1>
        <p className="text-muted-foreground">Real-time monitoring and insights across all systems</p>
      </motion.div>

      {/* Key Metrics */}
      <section>
        <motion.h2
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
        >
          Key Metrics
        </motion.h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {metrics.map((metric, index) => {
            const isExpanded = expandedMetric === metric.title;
            return (
              <div key={metric.title} className="flex flex-col gap-0">
                <StatusCard
                  {...metric}
                  description={undefined}
                  delay={0.5 + index * 0.1}
                  invertTrendColor={metric.title === "Error Rate" || metric.title === "Response Time"}
                />
                {metric.description && (
                  <button
                    onClick={() => setExpandedMetric(isExpanded ? null : metric.title)}
                    className="flex items-center gap-1 px-3 pb-1 text-[11px] text-muted-foreground/60 hover:text-muted-foreground transition-colors self-start"
                  >
                    <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`} />
                    {isExpanded ? "Hide" : "What does this measure?"}
                  </button>
                )}
                {isExpanded && metric.description && (
                  <motion.p
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-xs text-muted-foreground px-3 pb-3 leading-relaxed border border-t-0 border-border/40 rounded-b-lg bg-surface/30 -mt-1 pt-2"
                  >
                    {metric.description}
                  </motion.p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Traffic Over Time */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9 }}>
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Traffic Over Time
              <span className="text-xs font-normal text-muted-foreground ml-auto">Last 24 hours</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-[260px] flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={traffic} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#55C5E2" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#55C5E2" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradSuccess" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00C986" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#00C986" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradErrors" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#F16C6C" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#F16C6C" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.3)" />
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                    axisLine={false}
                    interval={Math.floor(traffic.length / 8)}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<TrafficTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area
                    type="monotone"
                    dataKey="total"
                    name="Total"
                    stroke="#55C5E2"
                    strokeWidth={2}
                    fill="url(#gradTotal)"
                  />
                  <Area
                    type="monotone"
                    dataKey="success"
                    name="Success"
                    stroke="#00C986"
                    strokeWidth={1.5}
                    fill="url(#gradSuccess)"
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    name="Errors"
                    stroke="#F16C6C"
                    strokeWidth={1.5}
                    fill="url(#gradErrors)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
            {!isLoading && traffic.every((p) => p.total === 0) && (
              <p className="text-xs text-muted-foreground text-center mt-2">
                No requests logged in the last 24 hours — data will appear here as traffic arrives.
              </p>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Charts and Data */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Pages */}
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.0 }}>
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-primary" />
                Top Pages
              </CardTitle>
            </CardHeader>
            <CardContent>
              {topPages.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No page view data yet.</p>
              ) : (
                <div className="space-y-4">
                  {topPages.map((page, index) => (
                    <motion.div
                      key={page.path}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 1.05 + index * 0.1 }}
                      className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50"
                    >
                      <div>
                        <code className="font-mono text-primary group-hover:text-primary-glow transition-colors text-sm">
                          {page.path}
                        </code>
                        <p className="text-xs text-muted-foreground">{page.views} views</p>
                      </div>
                      <Badge
                        variant="outline"
                        className={
                          page.change.startsWith("+")
                            ? "bg-success/10 text-success border-success/20"
                            : "bg-destructive/10 text-destructive border-destructive/20"
                        }
                      >
                        {page.change}
                      </Badge>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Error Analysis */}
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.1 }}>
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-primary" />
                Error Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              {errorsByType.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground gap-2">
                  <BarChart3 className="w-8 h-8 opacity-25" />
                  <p className="text-sm">No errors in the last 24 hours.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {errorsByType.map((error, index) => (
                    <motion.div
                      key={error.type}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 1.15 + index * 0.1 }}
                      className="space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{error.type}</span>
                        <span className="text-sm text-muted-foreground">{error.count}</span>
                      </div>
                      <div className="w-full bg-muted/30 rounded-full h-2">
                        <motion.div
                          className="bg-gradient-primary h-2 rounded-full"
                          initial={{ width: 0 }}
                          animate={{ width: `${error.percentage}%` }}
                          transition={{ delay: 1.25 + index * 0.1, duration: 0.8 }}
                        />
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* User Activity Breakdown */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.3 }}>
        <Card className="glass border-border/50">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-primary" />
                  Feature Usage Breakdown
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  How many user actions were recorded per portal feature in the last 24 hours.
                  Each bar shows the total number of tracked events (API calls, queries, logins, etc.)
                  for that feature area.
                </p>
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap ml-4 mt-1">Last 24 hours</span>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-[240px] flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : !hasActivity ? (
              <div className="h-[240px] flex flex-col items-center justify-center text-muted-foreground gap-3">
                <Activity className="w-10 h-10 opacity-25" />
                <p className="text-sm">No user activity recorded in the last 24 hours.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(220, enrichedBreakdown.length * 42)}>
                <BarChart
                  data={enrichedBreakdown}
                  layout="vertical"
                  margin={{ top: 4, right: 48, left: 8, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border) / 0.3)" />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                    label={{ value: "Actions", position: "insideBottom", offset: -2, fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                    axisLine={false}
                    width={140}
                  />
                  <Tooltip
                    cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0];
                      const meta = activityMeta(d.payload.type);
                      return (
                        <div className="rounded-lg border border-border/60 bg-background/95 p-3 shadow-lg text-xs max-w-[200px]">
                          <p className="font-semibold text-foreground">{meta.label}</p>
                          <p className="text-muted-foreground mt-0.5 mb-1.5">{meta.description}</p>
                          <p style={{ color: meta.color }}>
                            Actions logged: <span className="font-semibold">{d.value}</span>
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="count" name="Actions" radius={[0, 4, 4, 0]}>
                    {enrichedBreakdown.map((entry) => (
                      <Cell key={entry.type} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
