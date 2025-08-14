import { motion } from "framer-motion";
import { ArrowRight, Activity, Server, Clock, Users, Zap, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusCard } from "@/components/ui/status-card";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";

export default function Home() {
  const navigate = useNavigate();

  const stats = [
    {
      title: "System Uptime",
      value: "99.9%",
      description: "Last 30 days",
      icon: Activity,
      status: "success" as const,
      trend: "stable" as const,
      trendValue: "0.1%",
    },
    {
      title: "Active Servers",
      value: "847",
      description: "Connected MCP servers",
      icon: Server,
      status: "success" as const,
      trend: "up" as const,
      trendValue: "+12",
    },
    {
      title: "Response Time",
      value: "47ms",
      description: "Average latency",
      icon: Clock,
      status: "success" as const,
      trend: "down" as const,
      trendValue: "-3ms",
    },
    {
      title: "Active Users",
      value: "1,234",
      description: "Across all systems",
      icon: Users,
      status: "info" as const,
      trend: "up" as const,
      trendValue: "+89",
    },
  ];

  const recentActivity = [
    { action: "Jenkins Pipeline", status: "Completed", time: "2 min ago", type: "success" },
    { action: "Database Backup", status: "Running", time: "5 min ago", type: "warning" },
    { action: "Log Analysis", status: "Completed", time: "12 min ago", type: "success" },
    { action: "Security Scan", status: "Failed", time: "18 min ago", type: "error" },
    { action: "API Health Check", status: "Completed", time: "25 min ago", type: "success" },
  ];

  const statusTypeColors = {
    success: "bg-success/10 text-success border-success/20",
    warning: "bg-warning/10 text-warning border-warning/20", 
    error: "bg-destructive/10 text-destructive border-destructive/20",
  };

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <motion.section 
        className="relative overflow-hidden rounded-2xl bg-gradient-hero p-8 text-center glass border border-border/30"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8 }}
      >
        <div className="relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.8 }}
          >
            <h1 className="text-4xl font-bold mb-4 gradient-text">
              Welcome to MCP Control Center
            </h1>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Your unified command center for DevOps automation, business intelligence, 
              and system monitoring. The future of infrastructure management is here.
            </p>
          </motion.div>

          <motion.div 
            className="flex flex-col sm:flex-row gap-4 justify-center"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
          >
            <Button 
              size="lg" 
              className="bg-gradient-primary text-primary-foreground hover:shadow-glow transition-all duration-smooth group"
              onClick={() => navigate('/devops')}
            >
              <Zap className="mr-2 h-5 w-5 group-hover:rotate-12 transition-transform" />
              Enter DevOps Suite
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            
            <Button 
              size="lg" 
              variant="outline"
              className="bg-surface/50 border-primary/30 hover:bg-gradient-primary hover:text-primary-foreground hover:shadow-glow transition-all duration-smooth group"
              onClick={() => navigate('/bi')}
            >
              <TrendingUp className="mr-2 h-5 w-5 group-hover:scale-110 transition-transform" />
              Explore BI Tools
            </Button>
          </motion.div>
        </div>

        {/* Animated background elements */}
        <div className="absolute inset-0 overflow-hidden">
          <motion.div 
            className="absolute top-1/4 left-1/4 w-32 h-32 bg-primary/20 rounded-full blur-xl"
            animate={{ 
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{ duration: 4, repeat: Infinity }}
          />
          <motion.div 
            className="absolute bottom-1/4 right-1/4 w-24 h-24 bg-secondary/20 rounded-full blur-xl"
            animate={{ 
              scale: [1.2, 1, 1.2],
              opacity: [0.5, 0.3, 0.5],
            }}
            transition={{ duration: 3, repeat: Infinity, delay: 1 }}
          />
        </div>
      </motion.section>

      {/* Stats Grid */}
      <section>
        <motion.h2 
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
        >
          System Overview
        </motion.h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((stat, index) => (
            <StatusCard
              key={stat.title}
              {...stat}
              delay={0.7 + index * 0.1}
            />
          ))}
        </div>
      </section>

      {/* Recent Activity */}
      <section>
        <motion.h2 
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 1.1 }}
        >
          Recent Activity
        </motion.h2>
        
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.2 }}
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">Latest Events</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity.map((activity, index) => (
                  <motion.div
                    key={index}
                    className="flex items-center justify-between py-3 px-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors duration-smooth group"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 1.3 + index * 0.1 }}
                    whileHover={{ x: 4 }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                      <div>
                        <p className="font-medium text-foreground group-hover:text-primary transition-colors">
                          {activity.action}
                        </p>
                        <p className="text-sm text-muted-foreground">{activity.time}</p>
                      </div>
                    </div>
                    
                    <Badge 
                      variant="outline" 
                      className={statusTypeColors[activity.type as keyof typeof statusTypeColors]}
                    >
                      {activity.status}
                    </Badge>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </section>
    </div>
  );
}