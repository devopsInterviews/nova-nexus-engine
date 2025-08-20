import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { motion } from "framer-motion";
import { RefreshCw, Play, CheckCircle, Clock, AlertCircle, BookOpen } from "lucide-react";

export function SyncTablesTab() {
  const tables = [
    { 
      name: "users", 
      status: "completed", 
      progress: 100, 
      lastSync: "2 hours ago",
      changes: 3
    },
    { 
      name: "orders", 
      status: "syncing", 
      progress: 67, 
      lastSync: "In progress",
      changes: 12
    },
    { 
      name: "products", 
      status: "pending", 
      progress: 0, 
      lastSync: "Never",
      changes: 45
    },
    { 
      name: "inventory", 
      status: "failed", 
      progress: 34, 
      lastSync: "1 day ago",
      changes: 8
    },
    { 
      name: "analytics_events", 
      status: "completed", 
      progress: 100, 
      lastSync: "30 min ago",
      changes: 156
    },
  ];

  const statusIcons = {
    completed: CheckCircle,
    syncing: RefreshCw,
    pending: Clock,
    failed: AlertCircle,
  };

  const statusColors = {
    completed: "bg-success/10 text-success border-success/20",
    syncing: "bg-primary/10 text-primary border-primary/20 animate-pulse",
    pending: "bg-muted/20 text-muted-foreground border-border",
    failed: "bg-destructive/10 text-destructive border-destructive/20",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Confluence Configuration */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary" />
              Sync All Tables (Delta) → Confluence
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Confluence Space</label>
                <Input placeholder="DATA-SCHEMA" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Page Name</label>
                <Input placeholder="Database Schema Documentation" className="bg-surface-elevated" />
              </div>
            </div>
            
            <div className="flex gap-3">
              <Button className="bg-gradient-primary flex items-center gap-2">
                <Play className="w-4 h-4" />
                Start Delta Sync
              </Button>
              <Button variant="outline">
                <RefreshCw className="w-4 h-4 mr-2" />
                Force Full Sync
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Sync Progress Overview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Sync Progress Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="text-center p-4 rounded-lg glass border-border/50">
                <div className="text-2xl font-bold text-success">2</div>
                <div className="text-sm text-muted-foreground">Completed</div>
              </div>
              <div className="text-center p-4 rounded-lg glass border-border/50">
                <div className="text-2xl font-bold text-primary">1</div>
                <div className="text-sm text-muted-foreground">In Progress</div>
              </div>
              <div className="text-center p-4 rounded-lg glass border-border/50">
                <div className="text-2xl font-bold text-muted-foreground">1</div>
                <div className="text-sm text-muted-foreground">Pending</div>
              </div>
              <div className="text-center p-4 rounded-lg glass border-border/50">
                <div className="text-2xl font-bold text-destructive">1</div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Overall Progress</span>
                <span>67%</span>
              </div>
              <Progress value={67} className="h-3" />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Table Sync Status */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Table Sync Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {tables.map((table, index) => {
                const StatusIcon = statusIcons[table.status as keyof typeof statusIcons];
                return (
                  <motion.div
                    key={table.name}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + index * 0.1 }}
                    className="p-4 rounded-lg bg-surface-elevated/50 border border-border/50 hover:bg-surface-elevated transition-colors group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-4">
                        <div className={`p-2 rounded-lg border ${statusColors[table.status as keyof typeof statusColors]}`}>
                          <StatusIcon className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="font-medium group-hover:text-primary transition-colors">
                            {table.name}
                          </h4>
                          <p className="text-sm text-muted-foreground">
                            Last sync: {table.lastSync} • {table.changes} changes detected
                          </p>
                        </div>
                      </div>
                      
                      <Badge variant="outline" className={statusColors[table.status as keyof typeof statusColors]}>
                        {table.status}
                      </Badge>
                    </div>
                    
                    {table.progress > 0 && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>Progress</span>
                          <span>{table.progress}%</span>
                        </div>
                        <Progress value={table.progress} className="h-2" />
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Sync Configuration */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Sync Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-primary">Auto Sync</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  Automatically sync changes every 6 hours
                </p>
                <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                  Enabled
                </Badge>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-secondary">Delta Mode</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  Only sync changed tables and columns
                </p>
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                  Active
                </Badge>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-accent">Backup</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  Create backup before each sync
                </p>
                <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                  Enabled
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}