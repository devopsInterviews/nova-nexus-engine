import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { motion } from "framer-motion";
import { RefreshCw, Play, CheckCircle, Clock, AlertCircle, BookOpen, Loader2, Database } from "lucide-react";
import { useState } from "react";
import { useConnectionContext } from "@/context/connection-context";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";
import { ConnectionStatusCard } from "./ConnectionStatusCard";

interface SyncResult {
  table: string;
  newColumns: Array<{ column: string; description: string }>;
  error: string | null;
}

interface ProgressData {
  status: string;
  stage: string;
  current_table: string | null;
  current_table_index: number;
  total_tables: number;
  progress_percentage: number;
  stage_details: string;
  tables_processed: Array<{
    table: string;
    newColumns: Array<{ column: string; description: string }>;
    error: string | null;
    stage: string;
  }>;
  tables_pending: string[];
  summary: {
    total_tables: number;
    successful_tables: number;
    failed_tables: number;
    total_synced_columns: number;
  };
  results?: Array<{
    table: string;
    newColumns: Array<{ column: string; description: string }>;
    error: string | null;
  }>;
  start_time?: number;
  end_time?: number;
  duration?: number;
}

export function SyncTablesTab() {
  const [confluenceSpace, setConfluenceSpace] = useState("AAA");
  const [confluenceTitle, setConfluenceTitle] = useState("Demo - database keys description");
  const [limit, setLimit] = useState(10);
  const [isLoading, setIsLoading] = useState(false);
  const [syncResults, setSyncResults] = useState<SyncResult[]>([]);
  const [progressData, setProgressData] = useState<ProgressData | null>(null);
  const [overallProgress, setOverallProgress] = useState(0);
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();

  const handleSyncTables = async () => {
    if (!currentConnection) {
      toast({
        variant: "destructive",
        title: "No Connection",
        description: "Please connect to a database first in the 'Connect to DB' tab"
      });
      return;
    }

    if (!confluenceSpace.trim() || !confluenceTitle.trim()) {
      toast({
        variant: "destructive",
        title: "Missing Configuration",
        description: "Please provide both Confluence space and title"
      });
      return;
    }

    if (limit < 1 || limit > 1000) {
      toast({
        variant: "destructive",
        title: "Invalid Limit",
        description: "Limit must be between 1 and 1000"
      });
      return;
    }

    console.log("🚀 Starting enhanced table sync process with progress tracking", {
      connection: {
        host: currentConnection.host,
        database: currentConnection.database,
        database_type: currentConnection.database_type
      },
      confluenceSpace,
      confluenceTitle,
      limit
    });

    setIsLoading(true);
    setSyncResults([]);
    setProgressData(null);
    setOverallProgress(5);

    try {
      const connectionData = {
        ...currentConnection,
        space: confluenceSpace,
        title: confluenceTitle,
        limit: limit
      };

      console.log("� Starting streaming sync request", connectionData);

      // Use the streaming API for real-time progress updates
      const result = await dbService.syncAllTablesWithProgressStream(
        connectionData,
        (progressData) => {
          console.log("� Real-time progress update:", progressData);
          
          // Update progress data immediately as we receive it
          setProgressData(progressData);
          setOverallProgress(progressData.progress_percentage || 0);
          
          // If we have final results, set them
          if (progressData.results) {
            setSyncResults(progressData.results);
          }
          
          // Show completion toast only when fully completed
          if (progressData.status === 'completed') {
            const summary = progressData.summary;
            toast({
              title: "Sync Completed",
              description: `Synced ${summary.successful_tables}/${summary.total_tables} tables with ${summary.total_synced_columns} new columns${progressData.duration ? ` in ${progressData.duration.toFixed(1)}s` : ''}`
            });
          }
        }
      );

      console.log("📊 Streaming sync completed with result:", result);

      if (result.status === 'error') {
        console.error("❌ Streaming sync failed", result.error);
        toast({
          variant: "destructive",
          title: "Sync Failed",
          description: result.error || "Failed to sync tables"
        });
      }
    } catch (error) {
      console.error("💥 Streaming sync error", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "An unexpected error occurred during sync"
      });
    } finally {
      console.log("🏁 Sync process finished, clearing loading state");
      setIsLoading(false);
    }
  };

  const statusIcons = {
    completed: CheckCircle,
    failed: AlertCircle,
    success: CheckCircle,
  };

  const statusColors = {
    completed: "bg-success/10 text-success border-success/20",
    success: "bg-success/10 text-success border-success/20",
    failed: "bg-destructive/10 text-destructive border-destructive/20",
  };

  const getTableStatus = (result: SyncResult) => {
    if (result.error) return "failed";
    return result.newColumns.length > 0 ? "success" : "completed";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Connection Status */}
      <ConnectionStatusCard />

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
              Sync Tables to Confluence
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Confluence Space</label>
                <Input 
                  placeholder="AAA"
                  className="bg-surface-elevated"
                  value={confluenceSpace}
                  onChange={(e) => setConfluenceSpace(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Page Name</label>
                <Input 
                  placeholder="Demo - database keys description"
                  className="bg-surface-elevated"
                  value={confluenceTitle}
                  onChange={(e) => setConfluenceTitle(e.target.value)}
                  disabled={isLoading}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Row Limit</label>
                <Input 
                  type="number"
                  placeholder="10"
                  className="bg-surface-elevated"
                  value={limit}
                  onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                  disabled={isLoading}
                  min={1}
                  max={1000}
                />
                <p className="text-xs text-muted-foreground">
                  Number of rows AI will read per column for context
                </p>
              </div>
            </div>
            
            <div className="flex gap-3">
              <Button 
                className="bg-gradient-primary flex items-center gap-2"
                onClick={handleSyncTables}
                disabled={isLoading || !currentConnection || !confluenceSpace.trim() || !confluenceTitle.trim()}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {isLoading ? "Syncing..." : "Start Sync"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Enhanced Sync Progress with Detailed Information */}
      {(isLoading || progressData || syncResults.length > 0) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Sync Progress</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-6">
                  {/* Current Status */}
                  <div className="text-center">
                    <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                      <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                    </div>
                    <h3 className="text-lg font-medium">Syncing Tables...</h3>
                    <p className="text-muted-foreground">
                      {progressData?.stage_details || "Reading database schema and syncing with Confluence"}
                    </p>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Overall Progress</span>
                      <span>{progressData?.progress_percentage || overallProgress}%</span>
                    </div>
                    <Progress value={progressData?.progress_percentage || overallProgress} className="h-3" />
                  </div>

                  {/* Current Table Info - only show if we have progress data */}
                  {progressData?.current_table && (
                    <div className="bg-surface-elevated/50 rounded-lg p-4 border border-border/50">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">Current Table</h4>
                        <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                          {progressData.current_table_index}/{progressData.total_tables}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-primary" />
                        <code className="font-mono text-primary">{progressData.current_table}</code>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Stage: {progressData.stage.replace(/_/g, ' ')}
                      </p>
                    </div>
                  )}

                  {/* Tables Summary - only show if we have progress data */}
                  {progressData && (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div className="text-center p-3 rounded-lg glass border-border/50">
                        <div className="text-xl font-bold text-primary">
                          {progressData.total_tables || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Total Tables</div>
                      </div>
                      <div className="text-center p-3 rounded-lg glass border-border/50">
                        <div className="text-xl font-bold text-success">
                          {progressData.summary?.successful_tables || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Processed</div>
                      </div>
                      <div className="text-center p-3 rounded-lg glass border-border/50">
                        <div className="text-xl font-bold text-warning">
                          {progressData.tables_pending?.length || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">Pending</div>
                      </div>
                      <div className="text-center p-3 rounded-lg glass border-border/50">
                        <div className="text-xl font-bold text-accent">
                          {progressData.summary?.total_synced_columns || 0}
                        </div>
                        <div className="text-xs text-muted-foreground">New Columns</div>
                      </div>
                    </div>
                  )}

                  {/* Recently Processed Tables - only show if we have data */}
                  {progressData?.tables_processed && progressData.tables_processed.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-medium">Recently Processed</h4>
                      <div className="space-y-2 max-h-32 overflow-y-auto">
                        {progressData.tables_processed.slice(-3).map((table, index) => (
                          <div key={index} className="flex items-center justify-between p-2 rounded bg-surface/50 border border-border/30">
                            <div className="flex items-center gap-2">
                              <CheckCircle className="w-4 h-4 text-success" />
                              <code className="text-sm font-mono">{table.table}</code>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {table.newColumns.length} columns
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : progressData && progressData.status === 'completed' ? (
                <div className="space-y-4">
                  {/* Completion Status */}
                  <div className="text-center">
                    <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
                      <CheckCircle className="w-8 h-8 text-success" />
                    </div>
                    <h3 className="text-lg font-medium">Sync Completed!</h3>
                    <p className="text-muted-foreground">
                      {progressData.stage_details}
                    </p>
                  </div>

                  {/* Final Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Overall Progress</span>
                      <span>100%</span>
                    </div>
                    <Progress value={100} className="h-3" />
                  </div>

                  {/* Final Summary */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 rounded-lg glass border-border/50">
                      <div className="text-2xl font-bold text-primary">
                        {progressData.summary.total_tables}
                      </div>
                      <div className="text-sm text-muted-foreground">Total Tables</div>
                    </div>
                    <div className="text-center p-4 rounded-lg glass border-border/50">
                      <div className="text-2xl font-bold text-success">
                        {progressData.summary.successful_tables}
                      </div>
                      <div className="text-sm text-muted-foreground">Successful</div>
                    </div>
                    <div className="text-center p-4 rounded-lg glass border-border/50">
                      <div className="text-2xl font-bold text-destructive">
                        {progressData.summary.failed_tables}
                      </div>
                      <div className="text-sm text-muted-foreground">Failed</div>
                    </div>
                    <div className="text-center p-4 rounded-lg glass border-border/50">
                      <div className="text-2xl font-bold text-accent">
                        {progressData.summary.total_synced_columns}
                      </div>
                      <div className="text-sm text-muted-foreground">New Columns</div>
                    </div>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Table Sync Results */}
      {(syncResults.length > 0 || (progressData && progressData.results)) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Detailed Sync Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {(progressData?.results || syncResults).map((result, index) => {
                  const status = getTableStatus(result);
                  const StatusIcon = statusIcons[status as keyof typeof statusIcons];
                  
                  return (
                    <motion.div
                      key={result.table}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.7 + index * 0.1 }}
                      className="p-4 rounded-lg bg-surface-elevated/50 border border-border/50 hover:bg-surface-elevated transition-colors group"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-4">
                          <div className={`p-2 rounded-lg border ${statusColors[status as keyof typeof statusColors]}`}>
                            <StatusIcon className="w-4 h-4" />
                          </div>
                          <div>
                            <h4 className="font-medium group-hover:text-primary transition-colors flex items-center gap-2">
                              <Database className="w-4 h-4" />
                              {result.table}
                            </h4>
                            <p className="text-sm text-muted-foreground">
                              {result.error 
                                ? `Error: ${result.error}`
                                : result.newColumns.length > 0
                                  ? `${result.newColumns.length} new columns synced`
                                  : "No new columns to sync"
                              }
                            </p>
                          </div>
                        </div>
                        
                        <Badge variant="outline" className={statusColors[status as keyof typeof statusColors]}>
                          {status === "success" ? "Updated" : status === "failed" ? "Failed" : "Up to date"}
                        </Badge>
                      </div>
                      
                      {result.newColumns.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <h5 className="text-sm font-medium">New Columns:</h5>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {result.newColumns.map((column, colIndex) => (
                              <div 
                                key={colIndex}
                                className="p-2 rounded bg-surface/50 border border-border/30"
                              >
                                <code className="text-xs font-mono text-primary">
                                  {column.column}
                                </code>
                                {column.description && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {column.description}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </motion.div>
  );
}