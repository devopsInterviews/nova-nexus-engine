import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusCard } from "@/components/ui/status-card";
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp, Users, Activity, Server, Zap, Eye } from "lucide-react";
import { useEffect, useState } from "react";
import { analyticsService } from "@/lib/api-service";

interface Metric {
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<any>;
  status: 'success' | 'warning' | 'error' | 'info';
  trend: 'up' | 'down' | 'stable';
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

export default function Analytics() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [topPages, setTopPages] = useState<TopPage[]>([]);
  const [errorsByType, setErrorsByType] = useState<ErrorType[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Icon mapping
  const iconMap = {
    'Total Requests': Activity,
    'Active Sessions': Users,
    'Response Time': Zap,
    'Error Rate': Server,
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch all analytics data concurrently
        const [metricsResponse, topPagesResponse, errorsResponse] = await Promise.all([
          analyticsService.getKeyMetrics(),
          analyticsService.getTopPages(5, 24),
          analyticsService.getErrorAnalysis(24),
        ]);

        // Set metrics data
        if (metricsResponse.status === 'success' && metricsResponse.data) {
          const metricsWithIcons = metricsResponse.data.metrics.map(metric => ({
            ...metric,
            icon: iconMap[metric.title as keyof typeof iconMap] || Activity
          }));
          setMetrics(metricsWithIcons);
        }

        // Set top pages data
        if (topPagesResponse.status === 'success' && topPagesResponse.data) {
          setTopPages(topPagesResponse.data.topPages);
        }

        // Set errors data
        if (errorsResponse.status === 'success' && errorsResponse.data) {
          setErrorsByType(errorsResponse.data.errorsByType);
        }

      } catch (error) {
        console.error('Failed to fetch analytics data:', error);
        // Set fallback data
        setMetrics([
          {
            title: "Total Requests",
            value: "0",
            description: "Last 24 hours",
            icon: Activity,
            status: "info",
            trend: "stable",
            trendValue: "0%",
          },
          {
            title: "Active Sessions",
            value: "1",
            description: "Current active users",
            icon: Users,
            status: "info",
            trend: "stable",
            trendValue: "0%",
          },
          {
            title: "Response Time",
            value: "N/A",
            description: "95th percentile",
            icon: Zap,
            status: "info",
            trend: "stable",
            trendValue: "0ms",
          },
          {
            title: "Error Rate",
            value: "0.00%",
            description: "Last hour",
            icon: Server,
            status: "success",
            trend: "stable",
            trendValue: "0.00%",
          },
        ]);
        setTopPages([
          { path: "/", views: "1", change: "+100%" },
        ]);
        setErrorsByType([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();

    // Log page view
    analyticsService.logPageView({
      path: '/analytics',
      title: 'Analytics Dashboard',
      loadTime: performance.now()
    });

    // Set up auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div 
      className="space-y-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h1 className="text-3xl font-bold gradient-text mb-2">Analytics Dashboard</h1>
        <p className="text-muted-foreground">
          Real-time monitoring and insights across all systems
        </p>
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
          {metrics.map((metric, index) => (
            <StatusCard
              key={metric.title}
              {...metric}
              delay={0.5 + index * 0.1}
            />
          ))}
        </div>
      </section>

      {/* Charts and Data */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Pages */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.9 }}
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-primary" />
                Top Pages
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {topPages.map((page, index) => (
                  <motion.div
                    key={page.path}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.0 + index * 0.1 }}
                    className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                  >
                    <div>
                      <code className="font-mono text-primary group-hover:text-primary-glow transition-colors">
                        {page.path}
                      </code>
                      <p className="text-sm text-muted-foreground">{page.views} views</p>
                    </div>
                    <Badge 
                      variant="outline" 
                      className={page.change.startsWith('+') 
                        ? "bg-success/10 text-success border-success/20" 
                        : "bg-destructive/10 text-destructive border-destructive/20"
                      }
                    >
                      {page.change}
                    </Badge>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Error Analysis */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 1.1 }}
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-primary" />
                Error Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {errorsByType.map((error, index) => (
                  <motion.div
                    key={error.type}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.2 + index * 0.1 }}
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
                        transition={{ delay: 1.3 + index * 0.1, duration: 0.8 }}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Traffic Chart Placeholder */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.5 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Traffic Over Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] bg-surface-elevated rounded-lg p-6 flex items-center justify-center border border-border/50">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <TrendingUp className="w-8 h-8 text-primary animate-pulse" />
                </div>
                <div>
                  <h3 className="text-lg font-medium">Real-time Analytics Chart</h3>
                  <p className="text-muted-foreground">
                    Interactive charts and visualizations would appear here
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}