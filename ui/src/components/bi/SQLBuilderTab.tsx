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
import { ConnectionStatusCard } from "./ConnectionStatusCard";

interface QueryResult {
  sql_query?: string;
  rows: Record<string, any>[];
  executionTime?: number;
  rowCount?: number;
}

export function SQLBuilderTab() {
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();
  
  // Form state
  const [userPrompt, setUserPrompt] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("AAA");
  const [confluenceTitle, setConfluenceTitle] = useState("Demo - database keys description");
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showVisualize, setShowVisualize] = useState(false);

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
      
      console.log("🔄 Starting analytics query...");
      
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

      console.log("📥 Analytics query response received");
      const executionTime = Date.now() - startTime;

      if (response.status === 'success' && response.data) {
        const rows = response.data.rows || [];
        const sql_query = response.data.sql;
        
        setResult({
          rows,
          sql_query,
          executionTime,
          rowCount: rows.length
        });
        
        toast({
          title: "Query Executed Successfully",
          description: `Retrieved ${rows.length} rows in ${executionTime}ms${sql_query ? ' with SQL' : ' (no SQL)'}`
        });
      } else {
        console.error("❌ Query failed:", response);
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

  // Handle Copy SQL Query
  const handleCopySQL = () => {
    if (!result?.sql_query) return;
    
    navigator.clipboard.writeText(result.sql_query);
    toast({
      title: "SQL Copied",
      description: "SQL query copied to clipboard"
    });
  };

  // Handle Copy Results to Clipboard
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
      title: "Results Copied",
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
      {/* Connection Status */}
      <ConnectionStatusCard />

      {/* Query Builder */}
      <Card className="glass border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code2 className="w-5 h-5 text-primary" />
            AI-Powered SQL Generator & Executor
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Confluence Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Confluence Space
                {!confluenceSpace.trim() && <span className="text-red-500 ml-1">*</span>}
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
              <label className="text-sm font-medium">
                Confluence Title
                {!confluenceTitle.trim() && <span className="text-red-500 ml-1">*</span>}
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
            <label className="text-sm font-medium">
              Natural Language Query
              {!userPrompt.trim() && <span className="text-red-500 ml-1">*</span>}
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
          {/* Generated SQL Query Display */}
          {result.sql_query ? (
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  Generated SQL Query
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={handleCopySQL}>
                      <Copy className="w-4 h-4 mr-2" />
                      Copy SQL
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-surface-elevated rounded-lg p-4 border border-border/50">
                  <pre className="text-sm font-mono text-foreground overflow-x-auto whitespace-pre-wrap">
                    {result.sql_query}
                  </pre>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="glass border-border/50 border-orange-500/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-orange-600">
                  <AlertCircle className="w-5 h-5" />
                  SQL Query Not Available
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-orange-50/50 rounded-lg p-4 border border-orange-200/50">
                  <p className="text-sm text-orange-700">
                    The SQL query could not be extracted from the AI response. 
                    This might happen if the AI returned results in a different format.
                    Check the browser console for detailed response information.
                  </p>
                  <details className="mt-2">
                    <summary className="text-xs text-orange-600 cursor-pointer">Debug Information</summary>
                    <pre className="text-xs mt-2 text-orange-800 bg-orange-100/50 p-2 rounded">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </details>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Query Stats */}
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                Query Results
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleCopyResults}>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Results
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleDownloadCSV}>
                    <Download className="w-4 h-4 mr-2" />
                    Export CSV
                  </Button>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => setShowVisualize(!showVisualize)}
                    disabled={!result?.rows?.length}
                  >
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

          {/* Visualization Panel */}
          {showVisualize && result.rows.length > 0 && (
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle>Data Visualization</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Chart Type Selection */}
                  <div className="flex gap-2 mb-4">
                    <Button size="sm" variant="outline" className="bg-primary/10">Bar Chart</Button>
                    <Button size="sm" variant="outline">Line Chart</Button>
                    <Button size="sm" variant="outline">Pie Chart</Button>
                    <Button size="sm" variant="outline">Table Heatmap</Button>
                  </div>
                  
                  {/* Simple Bar Chart Visualization */}
                  <div className="bg-surface-elevated rounded-lg p-4 border border-border/50">
                    <div className="grid grid-cols-1 gap-2">
                      {result.rows.slice(0, 10).map((row, index) => {
                        const firstNumericKey = Object.keys(row).find(key => typeof row[key] === 'number');
                        const firstStringKey = Object.keys(row).find(key => typeof row[key] === 'string');
                        const maxValue = Math.max(...result.rows.map(r => typeof r[firstNumericKey || ''] === 'number' ? r[firstNumericKey || ''] : 0));
                        const value = firstNumericKey ? row[firstNumericKey] : 0;
                        const label = firstStringKey ? String(row[firstStringKey]).slice(0, 20) : `Row ${index + 1}`;
                        const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
                        
                        return (
                          <div key={index} className="flex items-center gap-2 py-1">
                            <div className="w-24 text-xs text-right truncate">{label}</div>
                            <div className="flex-1 bg-muted rounded-full h-4 relative">
                              <div 
                                className="bg-primary rounded-full h-full transition-all duration-500"
                                style={{ width: `${percentage}%` }}
                              />
                              <span className="absolute inset-0 flex items-center justify-center text-xs font-mono">
                                {typeof value === 'number' ? value.toLocaleString() : value}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {result.rows.length > 10 && (
                      <p className="text-xs text-muted-foreground mt-2 text-center">
                        Showing top 10 rows for visualization
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}