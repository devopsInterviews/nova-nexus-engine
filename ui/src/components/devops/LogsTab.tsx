import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { Search, Filter, Download, Eye, Server, FileText } from "lucide-react";

export function LogsTab() {
  const logFiles = [
    { name: "app.log", size: "2.3 MB", modified: "2 min ago", level: "INFO" },
    { name: "error.log", size: "156 KB", modified: "5 min ago", level: "ERROR" },
    { name: "access.log", size: "45.2 MB", modified: "1 min ago", level: "DEBUG" },
    { name: "system.log", size: "8.7 MB", modified: "3 min ago", level: "WARN" },
  ];

  const containers = [
    { name: "frontend-app", status: "running", logs: "1.2k", memory: "256MB" },
    { name: "backend-api", status: "running", logs: "3.4k", memory: "512MB" },
    { name: "database", status: "running", logs: "890", memory: "1GB" },
    { name: "redis-cache", status: "stopped", logs: "245", memory: "128MB" },
  ];

  const logLevelColors = {
    INFO: "bg-primary/10 text-primary border-primary/20",
    ERROR: "bg-destructive/10 text-destructive border-destructive/20",
    WARN: "bg-warning/10 text-warning border-warning/20",
    DEBUG: "bg-muted/20 text-muted-foreground border-border",
  };

  const statusColors = {
    running: "bg-success/10 text-success border-success/20",
    stopped: "bg-destructive/10 text-destructive border-destructive/20",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <ThemedTabs defaultValue="files" className="w-full">
        <ThemedTabsList className="grid w-full grid-cols-4">
          <ThemedTabsTrigger value="files">Find Log Files</ThemedTabsTrigger>
          <ThemedTabsTrigger value="paths">Logs by Path</ThemedTabsTrigger>
          <ThemedTabsTrigger value="containers">Containers</ThemedTabsTrigger>
          <ThemedTabsTrigger value="viewer">Log Viewer</ThemedTabsTrigger>
        </ThemedTabsList>

        <ThemedTabsContent value="files">
          <div className="space-y-6">
            {/* Search Filters */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Search className="w-5 h-5 text-primary" />
                    Log File Search
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">File Pattern</label>
                      <Input placeholder="*.log" className="bg-surface-elevated" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Time Range</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="Last 24h" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1h">Last hour</SelectItem>
                          <SelectItem value="24h">Last 24 hours</SelectItem>
                          <SelectItem value="7d">Last 7 days</SelectItem>
                          <SelectItem value="30d">Last 30 days</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Log Level</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="All levels" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All levels</SelectItem>
                          <SelectItem value="error">ERROR</SelectItem>
                          <SelectItem value="warn">WARN</SelectItem>
                          <SelectItem value="info">INFO</SelectItem>
                          <SelectItem value="debug">DEBUG</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-end">
                      <Button className="bg-gradient-primary w-full">
                        <Filter className="w-4 h-4 mr-2" />
                        Search
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Results */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle>Found Log Files</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {logFiles.map((file, index) => (
                      <motion.div
                        key={file.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.5 + index * 0.1 }}
                        className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                      >
                        <div className="flex items-center gap-4">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                          <div>
                            <h4 className="font-medium group-hover:text-primary transition-colors">{file.name}</h4>
                            <p className="text-sm text-muted-foreground">{file.size} • Modified {file.modified}</p>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-3">
                          <Badge variant="outline" className={logLevelColors[file.level as keyof typeof logLevelColors]}>
                            {file.level}
                          </Badge>
                          <div className="flex gap-2">
                            <Button size="sm" variant="ghost">
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button size="sm" variant="ghost">
                              <Download className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </ThemedTabsContent>

        <ThemedTabsContent value="paths">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Browse by Path</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <Input placeholder="/var/log/" className="bg-surface-elevated" />
                  <Button className="bg-gradient-primary">Browse</Button>
                </div>
                
                <div className="bg-surface-elevated rounded-lg p-6 border border-border/50 h-[300px] overflow-auto font-mono text-sm">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 hover:bg-primary/10 p-1 rounded cursor-pointer">
                      <span className="text-primary">📁</span> /var/log/nginx/
                    </div>
                    <div className="flex items-center gap-2 hover:bg-primary/10 p-1 rounded cursor-pointer">
                      <span className="text-primary">📁</span> /var/log/mysql/
                    </div>
                    <div className="flex items-center gap-2 hover:bg-primary/10 p-1 rounded cursor-pointer">
                      <span className="text-muted-foreground">📄</span> access.log
                    </div>
                    <div className="flex items-center gap-2 hover:bg-primary/10 p-1 rounded cursor-pointer">
                      <span className="text-muted-foreground">📄</span> error.log
                    </div>
                    <div className="flex items-center gap-2 hover:bg-primary/10 p-1 rounded cursor-pointer">
                      <span className="text-muted-foreground">📄</span> system.log
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>

        <ThemedTabsContent value="containers">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="w-5 h-5 text-primary" />
                Container Logs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {containers.map((container, index) => (
                  <motion.div
                    key={container.name}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.2 + index * 0.1 }}
                    className="p-4 rounded-lg glass border-border/50 hover:shadow-glow transition-all duration-smooth group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-medium group-hover:text-primary transition-colors">{container.name}</h4>
                      <Badge variant="outline" className={statusColors[container.status as keyof typeof statusColors]}>
                        {container.status}
                      </Badge>
                    </div>
                    
                    <div className="space-y-2 text-sm text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Log entries:</span>
                        <span className="text-foreground">{container.logs}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Memory:</span>
                        <span className="text-foreground">{container.memory}</span>
                      </div>
                    </div>
                    
                    <Button size="sm" className="w-full mt-3 bg-gradient-primary">
                      <Eye className="w-4 h-4 mr-2" />
                      View Logs
                    </Button>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>

        <ThemedTabsContent value="viewer">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Live Log Viewer</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-surface-elevated rounded-lg p-4 h-[400px] overflow-auto font-mono text-sm border border-border/50">
                <div className="space-y-1">
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">2024-01-15 14:23:45</span>
                    <span className="text-primary">[INFO]</span>
                    <span>Application started successfully</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">2024-01-15 14:23:46</span>
                    <span className="text-success">[DEBUG]</span>
                    <span>Database connection established</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">2024-01-15 14:23:47</span>
                    <span className="text-warning">[WARN]</span>
                    <span>High memory usage detected: 85%</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">2024-01-15 14:23:48</span>
                    <span className="text-destructive">[ERROR]</span>
                    <span>Failed to connect to external API</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">2024-01-15 14:23:49</span>
                    <span className="text-primary">[INFO]</span>
                    <span>Retrying connection in 5 seconds...</span>
                  </div>
                  <div className="flex gap-2 animate-pulse">
                    <span className="text-muted-foreground">2024-01-15 14:23:50</span>
                    <span className="text-success">[INFO]</span>
                    <span>▶ Live streaming...</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>
      </ThemedTabs>
    </motion.div>
  );
}