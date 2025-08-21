import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Code2, Play, Download, Copy, BarChart3, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";
import { useConnectionContext } from "@/context/connection-context";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";

interface QueryResult {
  sql?: string;
  rows: Record<string, any>[];
  executionTime?: number;
  rowCount?: number;
}

export function SQLBuilderTab() {
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();
  
  // Form state
  const [userPrompt, setUserPrompt] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("");
  const [confluenceTitle, setConfluenceTitle] = useState("");
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Handle Generate & Execute
  const handleGenerateAndExecute = async () => {
    if (!currentConnection) {
      toast({
        variant: "destructive",
        title: "No Connection",
        description: "Please select a database connection first."
      });
      return;
    }

    if (!userPrompt.trim()) {
      toast({
        variant: "destructive",
        title: "Missing Prompt",
        description: "Please enter a natural language prompt for your query."
      });
      return;
    }

    if (!confluenceSpace.trim() || !confluenceTitle.trim()) {
      toast({
        variant: "destructive",
        title: "Missing Confluence Details",
        description: "Please provide both Confluence space and title."
      });
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const startTime = Date.now();
      
      // Call the analytics query API with confluence integration
      const response = await dbService.runAnalyticsQuery({
        ...currentConnection,
        analytics_prompt: userPrompt,
        system_prompt: `You are a BI assistant. Given a JSON schema of tables and their columns,
and a user's analytics request, write a valid PostgreSQL query that
joins the relevant tables, filters by the appropriate date range,
and aggregates any measures. Return ONLY the SQL statement. No greetings, no extra words.`,
        confluenceSpace,
        confluenceTitle
      });

      const executionTime = Date.now() - startTime;

      if (response.status === 'success' && response.data) {
        const rows = response.data.rows || [];
        setResult({
          rows,
          executionTime,
          rowCount: rows.length
        });
        
        toast({
          title: "Query Executed Successfully",
          description: `Retrieved ${rows.length} rows in ${executionTime}ms`
        });
      } else {
        throw new Error(response.error || 'Query execution failed');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Query Failed",
        description: errorMessage
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Copy to Clipboard
  const handleCopyResults = () => {
    if (!result?.rows?.length) return;
    
    // Convert to CSV format
    const headers = Object.keys(result.rows[0]);
    const csvContent = [
      headers.join(','),
      ...result.rows.map(row => 
        headers.map(header => {
          const value = row[header];
          // Escape quotes and wrap in quotes if contains comma or quote
          const escaped = String(value).replace(/"/g, '""');
          return escaped.includes(',') || escaped.includes('"') ? `"${escaped}"` : escaped;
        }).join(',')
      )
    ].join('\n');
    
    navigator.clipboard.writeText(csvContent);
    toast({
      title: "Copied to Clipboard",
      description: "Query results copied as CSV format"
    });
  };

  // Handle Download CSV
  const handleDownloadCSV = () => {
    if (!result?.rows?.length) return;
    
    const headers = Object.keys(result.rows[0]);
    const csvContent = [
      headers.join(','),
      ...result.rows.map(row => 
        headers.map(header => {
          const value = row[header];
          const escaped = String(value).replace(/"/g, '""');
          return escaped.includes(',') || escaped.includes('"') ? `"${escaped}"` : escaped;
        }).join(',')
      )
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `query_results_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast({
      title: "Download Started",
      description: "CSV file download has started"
    });
  };

  return (
    <div className="space-y-6">
      {/* Query Builder */}
      <Card className="glass border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code2 className="w-5 h-5 text-primary" />
            AI-Powered SQL Generator & Executor
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connection Status */}
          {currentConnection ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                Connected to <strong>{currentConnection.name || currentConnection.host}</strong> ({currentConnection.database})
              </AlertDescription>
            </Alert>
          ) : (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                No database connection selected. Please go to Connect DB tab first.
              </AlertDescription>
            </Alert>
          )}

          {/* Confluence Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-red-400">
                Confluence Space <span className="text-red-500">*</span>
              </label>
              <Input 
                placeholder="e.g., DATA, ANALYTICS"
                value={confluenceSpace}
                onChange={(e) => setConfluenceSpace(e.target.value)}
                className="bg-surface-elevated"
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-red-400">
                Confluence Title <span className="text-red-500">*</span>
              </label>
              <Input 
                placeholder="e.g., Database Schema Documentation"
                value={confluenceTitle}
                onChange={(e) => setConfluenceTitle(e.target.value)}
                className="bg-surface-elevated"
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Natural Language Prompt */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-red-400">
              Natural Language Query <span className="text-red-500">*</span>
            </label>
            <Textarea 
              placeholder="e.g., Show me the top 10 customers by total order value in the last 6 months, including their contact information and number of orders..."
              className="bg-surface-elevated min-h-[120px]"
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              disabled={isLoading}
            />
          </div>
          
          {/* Action Button */}
          <div className="flex gap-3">
            <Button 
              className="bg-gradient-primary flex items-center gap-2"
              onClick={handleGenerateAndExecute}
              disabled={isLoading || !currentConnection}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {isLoading ? "Generating & Executing..." : "Generate & Execute SQL"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results Display */}
      {result && (
        <>
          {/* Query Stats */}
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                Query Results
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleCopyResults}>
                    <Copy className="w-4 h-4" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleDownloadCSV}>
                    <Download className="w-4 h-4 mr-2" />
                    Export CSV
                  </Button>
                  <Button size="sm" variant="outline" disabled>
                    <BarChart3 className="w-4 h-4 mr-2" />
                    Visualize
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 text-sm mb-4">
                <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                  ✓ Executed Successfully
                </Badge>
                <span className="text-muted-foreground">
                  Rows: {result.rowCount}
                </span>
                <span className="text-muted-foreground">
                  Execution time: ~{result.executionTime}ms
                </span>
              </div>

              {/* Results Table */}
              {result.rows.length > 0 ? (
                <div className="overflow-x-auto border border-border/50 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-elevated/50">
                      <tr className="border-b border-border">
                        {Object.keys(result.rows[0]).map((header) => (
                          <th key={header} className="text-left p-3 font-medium">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.slice(0, 100).map((row, index) => (
                        <tr
                          key={index}
                          className="border-b border-border/50 hover:bg-surface-elevated/30 transition-colors"
                        >
                          {Object.keys(result.rows[0]).map((header) => (
                            <td key={header} className="p-3">
                              {typeof row[header] === 'number' ? (
                                <span className="font-mono text-primary">
                                  {row[header].toLocaleString()}
                                </span>
                              ) : typeof row[header] === 'boolean' ? (
                                <Badge 
                                  variant="outline" 
                                  className={row[header] 
                                    ? "bg-success/10 text-success border-success/20" 
                                    : "bg-muted/20 text-muted-foreground border-border"
                                  }
                                >
                                  {row[header] ? 'true' : 'false'}
                                </Badge>
                              ) : (
                                <span className="text-foreground">
                                  {String(row[header] ?? '')}
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No data returned from the query
                </div>
              )}
              
              {result.rows.length > 100 && (
                <div className="mt-4 text-sm text-muted-foreground text-center">
                  Showing first 100 of {result.rowCount} results
                </div>
              )}
            </CardContent>
          </Card>

          {/* Query Performance Analysis */}
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Query Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-2 text-success">Performance</h4>
                  <p className="text-2xl font-bold text-success">
                    {result.executionTime && result.executionTime < 1000 ? "Excellent" : 
                     result.executionTime && result.executionTime < 5000 ? "Good" : "Slow"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {result.executionTime}ms execution time
                  </p>
                </div>
                
                <div className="p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-2 text-primary">Data Volume</h4>
                  <p className="text-2xl font-bold text-primary">
                    {result.rowCount?.toLocaleString()}
                  </p>
                  <p className="text-sm text-muted-foreground">rows returned</p>
                </div>
                
                <div className="p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-2 text-warning">Columns</h4>
                  <p className="text-2xl font-bold text-warning">
                    {result.rows.length > 0 ? Object.keys(result.rows[0]).length : 0}
                  </p>
                  <p className="text-sm text-muted-foreground">fields selected</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}