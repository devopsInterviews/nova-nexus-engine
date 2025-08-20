import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { motion } from "framer-motion";
import { Play, Square, RefreshCw, Terminal, Clock, CheckCircle, XCircle, AlertCircle } from "lucide-react";

export function JenkinsTab() {
  const jobs = [
    { name: "frontend-build", status: "success", duration: "2m 34s", progress: 100 },
    { name: "backend-deploy", status: "running", duration: "1m 12s", progress: 67 },
    { name: "test-automation", status: "failed", duration: "45s", progress: 100 },
    { name: "security-scan", status: "pending", duration: "-", progress: 0 },
  ];

  const statusIcons = {
    success: CheckCircle,
    running: RefreshCw,
    failed: XCircle,
    pending: Clock,
  };

  const statusColors = {
    success: "text-success border-success/20 bg-success/5",
    running: "text-warning border-warning/20 bg-warning/5 animate-pulse",
    failed: "text-destructive border-destructive/20 bg-destructive/5",
    pending: "text-muted-foreground border-border bg-muted/20",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <ThemedTabs defaultValue="console" className="w-full">
        <ThemedTabsList className="grid w-full grid-cols-4">
          <ThemedTabsTrigger value="console">Job Console</ThemedTabsTrigger>
          <ThemedTabsTrigger value="timewindow">Time Window</ThemedTabsTrigger>
          <ThemedTabsTrigger value="downstream">Downstream Tree</ThemedTabsTrigger>
          <ThemedTabsTrigger value="analysis">AI Analysis</ThemedTabsTrigger>
        </ThemedTabsList>

        <ThemedTabsContent value="console">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Job Control Panel */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-primary" />
                    Job Control
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Job Name</label>
                    <Input placeholder="Enter job name..." className="bg-surface-elevated" />
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Branch</label>
                    <Input placeholder="main" className="bg-surface-elevated" />
                  </div>
                  
                  <div className="flex gap-2">
                    <Button size="sm" className="bg-gradient-primary">
                      <Play className="w-4 h-4 mr-2" />
                      Build
                    </Button>
                    <Button size="sm" variant="outline">
                      <Square className="w-4 h-4 mr-2" />
                      Stop
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Console Output */}
            <div className="lg:col-span-2">
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 }}
              >
                <Card className="glass border-border/50 h-[400px]">
                  <CardHeader>
                    <CardTitle>Console Output</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="bg-surface-elevated rounded-lg p-4 h-full overflow-auto font-mono text-sm">
                      <div className="space-y-1 text-muted-foreground">
                        <div className="text-success">[INFO] Starting build process...</div>
                        <div>[DEBUG] Checking out repository</div>
                        <div>[DEBUG] Installing dependencies</div>
                        <div className="text-primary">[INFO] Running tests</div>
                        <div className="text-success">✓ All tests passed</div>
                        <div>[DEBUG] Building application</div>
                        <div className="text-warning">[WARN] Large bundle size detected</div>
                        <div className="text-success">[INFO] Build completed successfully</div>
                        <div className="text-primary animate-pulse">▶ Deploying to staging...</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>
          </div>

          {/* Active Jobs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="mt-6"
          >
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle>Active Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {jobs.map((job, index) => {
                    const StatusIcon = statusIcons[job.status as keyof typeof statusIcons];
                    return (
                      <motion.div
                        key={job.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.7 + index * 0.1 }}
                        className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                      >
                        <div className="flex items-center gap-4">
                          <div className={`p-2 rounded-lg border ${statusColors[job.status as keyof typeof statusColors]}`}>
                            <StatusIcon className="w-4 h-4" />
                          </div>
                          <div>
                            <h4 className="font-medium group-hover:text-primary transition-colors">{job.name}</h4>
                            <p className="text-sm text-muted-foreground">Duration: {job.duration}</p>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-4">
                          {job.progress > 0 && (
                            <div className="w-32">
                              <Progress value={job.progress} className="h-2" />
                            </div>
                          )}
                          <Badge variant="outline" className={statusColors[job.status as keyof typeof statusColors]}>
                            {job.status}
                          </Badge>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </ThemedTabsContent>

        <ThemedTabsContent value="timewindow">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Build Time Window Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Start Time</label>
                  <Input type="datetime-local" className="bg-surface-elevated" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">End Time</label>
                  <Input type="datetime-local" className="bg-surface-elevated" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Job Filter</label>
                  <Input placeholder="All jobs" className="bg-surface-elevated" />
                </div>
              </div>
              
              <div className="h-[300px] bg-surface-elevated rounded-lg p-6 flex items-center justify-center border border-border/50">
                <div className="text-center space-y-2">
                  <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground">Select time window to view build analytics</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>

        <ThemedTabsContent value="downstream">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Downstream Dependency Tree</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] bg-surface-elevated rounded-lg p-6 flex items-center justify-center border border-border/50">
                <div className="text-center space-y-2">
                  <div className="text-primary text-2xl">🌳</div>
                  <p className="text-muted-foreground">Dependency tree visualization</p>
                  <p className="text-sm text-muted-foreground">Interactive job dependency mapping coming soon</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>

        <ThemedTabsContent value="analysis">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>AI-Powered Job Analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">Analysis Query</label>
                <Textarea 
                  placeholder="Analyze build failures in the last 7 days..."
                  className="bg-surface-elevated"
                  rows={3}
                />
              </div>
              
              <Button className="bg-gradient-primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                Generate Analysis
              </Button>
              
              <div className="bg-surface-elevated rounded-lg p-6 border border-border/50">
                <h4 className="font-medium mb-3 text-primary">Analysis Results</h4>
                <div className="space-y-3 text-muted-foreground">
                  <p>• Build success rate: 87% (last 7 days)</p>
                  <p>• Most common failure: Test timeout in integration suite</p>
                  <p>• Peak build times: 9-11 AM, 2-4 PM</p>
                  <p>• Recommendation: Increase test timeout and optimize database queries</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>
      </ThemedTabs>
    </motion.div>
  );
}