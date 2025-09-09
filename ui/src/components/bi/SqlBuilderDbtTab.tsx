import React, { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Upload, FileJson, X, CheckCircle2, AlertCircle, FileText, Eye, EyeOff, Code2, Play, Loader2, Copy, Brain, Zap, ChevronDown, ChevronRight } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { useConnectionContext } from "@/context/connection-context";
import { dbService } from "@/lib/api-service";
import { ConnectionStatusCard } from "./ConnectionStatusCard";

interface DbtFile {
  name: string;
  content: string;
  size: number;
  type: string;
}

interface QueryResult {
  sql_query?: string;
  rows: Record<string, any>[];
  executionTime?: number;
  rowCount?: number;
}

interface IterativeResult {
  status: 'success' | 'error';
  error?: string;
  final_depth?: number;
  tables_used?: string[];
  sql_query?: string;
  results?: Array<Record<string, any>>;
  row_count?: number;
  iteration_count?: number;
  process_log?: Array<{
    depth: number;
    table_count: number;
    tables: string[];
    ai_decision: 'yes' | 'no';
    ai_reasoning: string;
    sql_generated?: string;
    execution_successful?: boolean;
    error_message?: string;
  }>;
}

export function SqlBuilderDbtTab() {
  const { toast } = useToast();
  const { currentConnection } = useConnectionContext();
  
  // File upload state
  const [selectedFile, setSelectedFile] = useState<DbtFile | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJsonContent, setShowJsonContent] = useState(true);

  // SQL query state
  const [userPrompt, setUserPrompt] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("AAA");
  const [confluenceTitle, setConfluenceTitle] = useState("Demo - database keys description");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Iterative analysis state
  const [isIterativeLoading, setIsIterativeLoading] = useState(false);
  const [iterativeResult, setIterativeResult] = useState<IterativeResult | null>(null);
  const [iterativeError, setIterativeError] = useState<string | null>(null);
  const [showProcessLog, setShowProcessLog] = useState(false);

  // Handle file selection via input
  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      processFile(file);
    }
  }, []);

  // Process the uploaded file
  const processFile = useCallback(async (file: File) => {
    setError(null);
    setIsProcessing(true);

    try {
      // Validate file type
      if (!file.name.endsWith('.json') && file.type !== 'application/json') {
        throw new Error('Please select a JSON file (.json)');
      }

      // Validate file size (limit to 10MB)
      if (file.size > 10 * 1024 * 1024) {
        throw new Error('File size must be less than 10MB');
      }

      // Read file content
      const content = await file.text();

      // Validate JSON format
      try {
        JSON.parse(content);
      } catch (jsonError) {
        throw new Error('Invalid JSON format');
      }

      // Create file object
      const dbtFile: DbtFile = {
        name: file.name,
        content: content,
        size: file.size,
        type: file.type || 'application/json'
      };

      setSelectedFile(dbtFile);

      // Call backend API to log the file upload
      await logFileUpload(dbtFile);

      toast({
        title: "File Uploaded Successfully",
        description: `${file.name} has been processed and logged`,
        variant: "default"
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process file';
      setError(errorMessage);
      toast({
        title: "File Upload Failed",
        description: errorMessage,
        variant: "destructive"
      });
    } finally {
      setIsProcessing(false);
    }
  }, [toast]);

  // Log file upload to backend
  const logFileUpload = async (file: DbtFile) => {
    try {
      const response = await dbService.logDbtFileUpload({
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        contentPreview: file.content.substring(0, 500) // First 500 chars for logging
      });

      if (response.status !== 'success') {
        console.warn('Failed to log file upload to backend:', response.error);
      }
    } catch (error) {
      console.warn('Error logging file upload:', error);
      // Don't throw - file upload should still work even if logging fails
    }
  };

  // Handle Generate & Execute SQL
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
    setQueryError(null);
    setResult(null);

    try {
      const startTime = Date.now();
      
      console.log("🔄 Starting analytics query from dbt tab...");
      
      // Call the analytics query API with confluence integration
      const response = await dbService.runAnalyticsQuery({
        ...currentConnection,
        analytics_prompt: userPrompt,
        system_prompt: `You are a BI assistant working with dbt models and database schemas. Given a JSON schema of tables and their columns,
and a user's analytics request, write a valid PostgreSQL query that
joins the relevant tables, filters by the appropriate date range,
and aggregates any measures. Consider dbt model patterns and naming conventions. Return ONLY the SQL statement. No greetings, no extra words.`,
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
      setQueryError(errorMessage);
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

  // Handle Iterative dbt Analysis
  const handleIterativeAnalysis = async () => {
    if (!currentConnection) {
      toast({
        variant: "destructive",
        title: "No Connection",
        description: "Please select a database connection first."
      });
      return;
    }

    if (!selectedFile?.content) {
      toast({
        variant: "destructive",
        title: "No dbt File",
        description: "Please upload a dbt configuration file first."
      });
      return;
    }

    if (!userPrompt.trim()) {
      toast({
        variant: "destructive",
        title: "Missing Prompt",
        description: "Please enter a natural language prompt for your analysis."
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

    setIsIterativeLoading(true);
    setIterativeError(null);
    setIterativeResult(null);

    try {
      const startTime = Date.now();
      
      console.log("🧠 Starting iterative dbt analysis...");
      
      // Call the iterative dbt query API
      const response = await dbService.iterativeDbtQuery({
        ...currentConnection,
        dbt_file_content: selectedFile.content,
        analytics_prompt: userPrompt,
        confluence_space: confluenceSpace,
        confluence_title: confluenceTitle
      });

      console.log("📥 Iterative analysis response received");
      const executionTime = Date.now() - startTime;

      if (response.status === 'success' && response.data) {
        setIterativeResult(response.data);
        
        const final_depth = response.data.final_depth;
        const iteration_count = response.data.iteration_count;
        const row_count = response.data.row_count || 0;
        
        toast({
          title: "Iterative Analysis Complete",
          description: `✅ Successful at depth ${final_depth} after ${iteration_count} iterations (${row_count} rows, ${executionTime}ms)`
        });
      } else {
        console.error("❌ Iterative analysis failed:", response);
        throw new Error(response.error || 'Iterative analysis failed');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setIterativeError(errorMessage);
      toast({
        variant: "destructive",
        title: "Iterative Analysis Failed",
        description: errorMessage
      });
    } finally {
      setIsIterativeLoading(false);
    }
  };

  // Handle Copy Iterative SQL
  const handleCopyIterativeSQL = () => {
    if (!iterativeResult?.sql_query) return;
    
    navigator.clipboard.writeText(iterativeResult.sql_query);
    toast({
      title: "SQL Copied",
      description: "Iterative analysis SQL query copied to clipboard"
    });
  };

  // Handle drag and drop events
  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);

    const files = event.dataTransfer.files;
    if (files.length > 0) {
      processFile(files[0]);
    }
  }, [processFile]);

  // Clear selected file
  const clearFile = useCallback(() => {
    setSelectedFile(null);
    setError(null);
  }, []);

  // Format file size for display
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format JSON content for pretty display
  const formatJsonContent = (content: string): string => {
    try {
      const parsed = JSON.parse(content);
      return JSON.stringify(parsed, null, 2); // 2 spaces for indentation
    } catch {
      return content; // Return original if not valid JSON
    }
  };

  // Detect file format (manifest vs tree vs unknown)
  const detectDbtFileFormat = (content: string): { type: 'manifest' | 'tree' | 'unknown'; details: string; issues?: string[] } => {
    try {
      const parsed = JSON.parse(content);
      const issues: string[] = [];
      
      // Check for manifest.json format (has metadata and nodes)
      if (parsed.metadata && parsed.nodes) {
        // Validate manifest structure
        if (!parsed.metadata.dbt_version) issues.push("Missing dbt_version in metadata");
        if (Object.keys(parsed.nodes).length === 0) issues.push("No nodes found in manifest");
        
        return { 
          type: 'manifest', 
          details: `dbt manifest.json (v${parsed.metadata.dbt_version || 'unknown'}) with ${Object.keys(parsed.nodes).length} nodes`,
          issues: issues.length > 0 ? issues : undefined
        };
      }
      
      // Check for tree format (has relations array)
      if (Array.isArray(parsed.relations)) {
        // Validate tree structure
        if (parsed.relations.length === 0) issues.push("Relations array is empty");
        
        // Check if relations have expected structure (depth, unique_id, identifier, etc.)
        const hasValidStructure = parsed.relations.every((r: any) => 
          typeof r === 'object' && r !== null && 
          (r.hasOwnProperty('depth') || r.hasOwnProperty('unique_id') || r.hasOwnProperty('identifier'))
        );
        
        if (!hasValidStructure) issues.push("Relations don't have expected structure (missing depth, unique_id, or identifier)");
        
        return { 
          type: 'tree', 
          details: `Pre-processed tree format with ${parsed.relations.length} relations`,
          issues: issues.length > 0 ? issues : undefined
        };
      }
      
      // Try to identify why it's not supported
      const reasons: string[] = [];
      
      if (!parsed.metadata && !parsed.relations) {
        reasons.push("Missing both 'metadata' (for manifest) and 'relations' (for tree format)");
      } else if (parsed.metadata && !parsed.nodes) {
        reasons.push("Has 'metadata' but missing 'nodes' (incomplete manifest)");
      } else if (parsed.relations && !Array.isArray(parsed.relations)) {
        reasons.push("Has 'relations' but it's not an array (invalid tree format)");
      } else if (Array.isArray(parsed.relations) && !parsed.tree) {
        reasons.push("Has 'relations' array but missing 'tree' structure (incomplete tree format)");
      }
      
      // Check for other dbt-like structures
      if (parsed.model || parsed.models) {
        reasons.push("Appears to be a dbt models file (not supported - use manifest.json or preprocessed tree format)");
      } else if (parsed.sources) {
        reasons.push("Appears to be a dbt sources file (not supported - use manifest.json or preprocessed tree format)");
      } else if (Array.isArray(parsed)) {
        reasons.push("JSON array format (not supported - expecting object with manifest or tree structure)");
      } else {
        reasons.push("Unknown JSON structure - not a recognizable dbt format");
      }
      
      return { 
        type: 'unknown', 
        details: `Unsupported format: ${reasons.join(', ')}`,
        issues: reasons
      };
    } catch (error) {
      return { 
        type: 'unknown', 
        details: `Invalid JSON format: ${error instanceof Error ? error.message : 'Parse error'}`,
        issues: ['File is not valid JSON']
      };
    }
  };

  // Try to parse and validate dbt model structure
  const validateDbtContent = (content: string): { 
    isValid: boolean; 
    summary: string; 
    format: { type: 'manifest' | 'tree' | 'unknown'; details: string; issues?: string[] };
    isDamaged: boolean;
    damageReason?: string;
  } => {
    const format = detectDbtFileFormat(content);
    
    // Determine if file is damaged/broken
    const isDamaged = format.type === 'unknown' || (format.issues && format.issues.length > 0);
    
    let damageReason: string | undefined;
    if (format.type === 'unknown') {
      damageReason = format.details;
    } else if (format.issues && format.issues.length > 0) {
      damageReason = `File has issues: ${format.issues.join(', ')}`;
    }
    
    const isValid = format.type === 'manifest' || format.type === 'tree';
    
    return { 
      isValid: isValid && !isDamaged,
      summary: format.details,
      format,
      isDamaged,
      damageReason
    };
  };

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <ConnectionStatusCard />

      {/* Header */}
      <Card className="glass border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileJson className="w-5 h-5 text-primary" />
            SQL Builder - dbt Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Upload your dbt JSON configuration files to analyze table structures, models, and dependencies. 
            Supported formats include dbt models, sources, and manifest files.
          </p>
        </CardContent>
      </Card>

      {/* File Upload Area */}
      <Card className="glass border-border/50">
        <CardHeader>
          <CardTitle>Upload dbt Configuration File</CardTitle>
        </CardHeader>
        <CardContent>
          {!selectedFile ? (
            <div
              className={`
                relative border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200
                ${isDragOver 
                  ? 'border-primary bg-primary/5 scale-105' 
                  : 'border-border hover:border-primary/50 hover:bg-primary/2'
                }
                ${isProcessing ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}
              `}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-upload')?.click()}
            >
              <input
                id="file-upload"
                type="file"
                accept=".json,application/json"
                onChange={handleFileSelect}
                className="hidden"
                disabled={isProcessing}
              />
              
              <div className="flex flex-col items-center gap-4">
                <div className={`
                  w-16 h-16 rounded-full flex items-center justify-center transition-all
                  ${isDragOver ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}
                `}>
                  <Upload className="w-8 h-8" />
                </div>
                
                <div className="space-y-2">
                  <h3 className="text-lg font-medium">
                    {isDragOver ? 'Drop your file here' : 'Choose a file or drag it here'}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Supports JSON files up to 10MB
                  </p>
                </div>

                <Button 
                  variant="outline" 
                  className="mt-2"
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Processing...' : 'Browse Files'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* File Info */}
              <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-lg border">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h4 className="font-medium">{selectedFile.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      {formatFileSize(selectedFile.size)} • {selectedFile.type}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFile}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>

              {/* File Validation Status */}
              {(() => {
                const validation = validateDbtContent(selectedFile.content);
                return (
                  <div className="space-y-3">
                    {/* Main validation alert */}
                    <Alert variant={validation.isValid ? "default" : "destructive"}>
                      {validation.isValid ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <AlertCircle className="h-4 w-4" />
                      )}
                      <AlertDescription>
                        <strong>{validation.isValid ? 'Valid dbt File:' : validation.isDamaged ? 'File is Damaged/Broken:' : 'Invalid:'}</strong> {validation.summary}
                      </AlertDescription>
                    </Alert>

                    {/* Detailed damage/error information */}
                    {validation.isDamaged && validation.damageReason && (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                          <div className="space-y-2">
                            <div><strong>Why this file is broken:</strong></div>
                            <div className="text-sm">{validation.damageReason}</div>
                            <div className="text-sm font-medium">
                              <strong>Expected formats:</strong>
                              <ul className="list-disc list-inside mt-1 space-y-1">
                                <li><strong>dbt manifest.json:</strong> Must have 'metadata' and 'nodes' fields with proper structure</li>
                                <li><strong>Pre-processed tree format:</strong> Must have 'relations' array and 'tree' object with depth information</li>
                              </ul>
                            </div>
                          </div>
                        </AlertDescription>
                      </Alert>
                    )}

                    {/* File Format Information - only show for valid files */}
                    {validation.isValid && validation.format && !validation.isDamaged && (
                      <div className={`rounded-lg p-3 border ${
                        validation.format.type === 'manifest' 
                          ? 'bg-blue-50/30 border-blue-200/50' 
                          : validation.format.type === 'tree' 
                          ? 'bg-green-50/30 border-green-200/50' 
                          : 'bg-gray-50/30 border-gray-200/50'
                      }`}>
                        <div className="flex items-center gap-2 mb-2">
                          <div className={`w-2 h-2 rounded-full ${
                            validation.format.type === 'manifest' ? 'bg-blue-500' 
                            : validation.format.type === 'tree' ? 'bg-green-500' 
                            : 'bg-gray-500'
                          }`} />
                          <span className={`text-sm font-medium ${
                            validation.format.type === 'manifest' ? 'text-blue-700' 
                            : validation.format.type === 'tree' ? 'text-green-700' 
                            : 'text-gray-700'
                          }`}>
                            {validation.format.type === 'manifest' ? 'Raw dbt Manifest' 
                             : validation.format.type === 'tree' ? 'Pre-processed Tree Format' 
                             : 'Other Format'}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {validation.format.type === 'manifest' 
                            ? '📋 This raw manifest.json will be automatically converted to tree format for analysis' 
                            : validation.format.type === 'tree' 
                            ? '✅ This file is ready for analysis - no preprocessing needed' 
                            : '⚠️ Format may not be fully supported for iterative analysis'}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* File Content Preview */}
              <div className="space-y-4 border-t border-border/30 pt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-foreground">File Content Preview</h4>
                    <span className="text-sm font-normal text-muted-foreground">
                      {selectedFile.content.split('\n').length} lines
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="show-json"
                      checked={showJsonContent}
                      onCheckedChange={(checked) => setShowJsonContent(checked as boolean)}
                    />
                    <Label 
                      htmlFor="show-json"
                      className="text-sm font-normal cursor-pointer flex items-center gap-1"
                    >
                      {showJsonContent ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                      Show content
                    </Label>
                  </div>
                </div>
                
                {showJsonContent && (
                  (() => {
                    const validation = validateDbtContent(selectedFile.content);
                    let contentToShow = selectedFile.content;
                    let isProcessedContent = false;
                    
                    // For manifest files, show the processed tree format instead of raw manifest
                    if (validation.isValid && validation.format.type === 'manifest') {
                      try {
                        const parsed = JSON.parse(selectedFile.content);
                        // This simulates the preprocessing that happens on the backend
                        // In a real scenario, we'd call the backend, but for preview we'll show what would be processed
                        contentToShow = JSON.stringify({
                          note: "This is a preview of how your manifest.json will be processed for analysis",
                          original_format: "dbt_manifest",
                          will_be_converted_to: "tree_format_with_relations_and_depths",
                          sample_processed_structure: {
                            relations: "Array of tables with depth calculations",
                            tree: "Hierarchical structure for analysis",
                            metadata: "Processing information"
                          },
                          original_nodes_count: Object.keys(parsed.nodes || {}).length,
                          original_sources_count: Object.keys(parsed.sources || {}).length
                        }, null, 2);
                        isProcessedContent = true;
                      } catch (e) {
                        // Fall back to original content if parsing fails
                        contentToShow = selectedFile.content;
                      }
                    }
                    
                    return (
                      <div className="space-y-4">
                        {isProcessedContent && (
                          <div className="bg-blue-50/30 border border-blue-200/50 rounded-lg p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <div className="w-2 h-2 rounded-full bg-blue-500" />
                              <span className="text-sm font-medium text-blue-700">Preview: Processed Tree Format</span>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              This shows how your manifest.json will be converted for analysis. The actual processing will include all relations with proper depth calculations.
                            </p>
                          </div>
                        )}
                        
                        <div className="border border-border/50 rounded-lg">
                          <ScrollArea className="h-96 w-full">
                            <pre className="p-4 text-sm font-mono text-foreground whitespace-pre-wrap overflow-x-auto">
                              {formatJsonContent(contentToShow)}
                            </pre>
                          </ScrollArea>
                        </div>
                        
                        {/* File Actions */}
                        <div className="flex gap-2 flex-wrap">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigator.clipboard.writeText(formatJsonContent(contentToShow))}
                          >
                            Copy {isProcessedContent ? 'Preview' : 'Formatted'} JSON
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigator.clipboard.writeText(selectedFile.content)}
                          >
                            Copy Original
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              const blob = new Blob([formatJsonContent(contentToShow)], { type: 'application/json' });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = selectedFile.name.replace('.json', isProcessedContent ? '_preview.json' : '_formatted.json');
                              document.body.appendChild(a);
                              a.click();
                              document.body.removeChild(a);
                              URL.revokeObjectURL(url);
                            }}
                          >
                            Download {isProcessedContent ? 'Preview' : 'Formatted'}
                          </Button>
                        </div>
                      </div>
                    );
                  })()
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* AI-Powered SQL Builder with dbt Integration */}
      <Card className="glass border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code2 className="w-5 h-5 text-primary" />
            <Brain className="w-5 h-5 text-blue-500" />
            AI-Powered SQL Builder with dbt Integration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Feature Description */}
          <div className="bg-gradient-to-r from-blue-50/20 to-purple-50/20 rounded-lg p-4 border border-blue-200/30">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-blue-100/50 rounded-lg">
                <Brain className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h4 className="font-medium text-blue-900 mb-2">Smart dbt-Aware Analysis</h4>
                <p className="text-sm text-blue-700 leading-relaxed mb-3">
                  This AI-powered feature intelligently analyzes your dbt file structure and builds optimal SQL queries. 
                  When a dbt file is uploaded, it automatically performs iterative depth-based analysis, starting from the most detailed tables 
                  and working toward higher-level aggregations until the AI finds the perfect scope for your query.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-blue-600">
                  <div className="space-y-1">
                    <div><strong>Without dbt file:</strong></div>
                    <div>• Standard AI SQL generation</div>
                    <div>• Uses database schema</div>
                    <div>• Confluence-enhanced context</div>
                  </div>
                  <div className="space-y-1">
                    <div><strong>With dbt file:</strong></div>
                    <div>• Dynamic depth detection</div>
                    <div>• AI iterative evaluation</div>
                    <div>• Optimal table selection</div>
                    <div>• Enhanced query generation</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

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
                disabled={isLoading || isIterativeLoading}
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
                disabled={isLoading || isIterativeLoading}
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
              disabled={isLoading || isIterativeLoading}
            />
          </div>
          
          {/* dbt File Status and Action Buttons */}
          <div className="space-y-4">
            {selectedFile ? (
              <div className="text-sm text-green-600 bg-green-50/50 rounded-lg p-3 border border-green-200/50">
                ✅ <strong>dbt file loaded:</strong> {selectedFile.name} - Will use iterative depth-based analysis ({(() => {
                  const validation = validateDbtContent(selectedFile.content);
                  return validation.summary;
                })()})
              </div>
            ) : (
              <div className="text-sm text-blue-600 bg-blue-50/50 rounded-lg p-3 border border-blue-200/50">
                ℹ️ <strong>No dbt file:</strong> Will use standard AI SQL generation with database schema analysis
              </div>
            )}
            
            <div className="flex gap-3">
              {selectedFile ? (
                (() => {
                  const validation = validateDbtContent(selectedFile.content);
                  const isFileValid = validation.isValid && !validation.isDamaged;
                  
                  return (
                    <Button 
                      className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white flex items-center gap-2"
                      onClick={handleIterativeAnalysis}
                      disabled={isIterativeLoading || isLoading || !currentConnection || !userPrompt.trim() || !confluenceSpace.trim() || !confluenceTitle.trim() || !isFileValid}
                      title={!isFileValid ? "Cannot analyze - file is damaged or in unsupported format" : undefined}
                    >
                      {isIterativeLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Brain className="w-4 h-4" />
                          <Zap className="w-3 h-3" />
                        </>
                      )}
                      {isIterativeLoading ? "Analyzing dbt Structure..." : "Generate SQL with dbt Analysis"}
                    </Button>
                  );
                })()
              ) : (
                <Button 
                  className="bg-gradient-primary flex items-center gap-2"
                  onClick={handleGenerateAndExecute}
                  disabled={isLoading || isIterativeLoading || !currentConnection}
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {isLoading ? "Generating SQL..." : "Generate & Execute SQL"}
                </Button>
              )}
              
              {(isLoading || isIterativeLoading) && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {selectedFile 
                    ? "AI is analyzing dbt depths and building optimal queries..."
                    : "AI is generating SQL from database schema..."
                  }
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Query Error Display */}
      {queryError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{queryError}</AlertDescription>
        </Alert>
      )}

      {/* Iterative Analysis Error Display */}
      {iterativeError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <strong>Iterative Analysis Failed:</strong> {iterativeError}
          </AlertDescription>
        </Alert>
      )}

      {/* Iterative Analysis Results */}
      {iterativeResult && (
        <>
          {/* Success Summary */}
          {iterativeResult.status === 'success' && (
            <Card className="glass border-border/50 bg-gradient-to-br from-green-50/10 to-blue-50/10 border-green-500/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-green-700">
                  <CheckCircle2 className="w-5 h-5" />
                  Iterative Analysis Complete
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                  <div className="bg-green-50/50 rounded-lg p-3 border border-green-200/50">
                    <div className="text-sm text-green-600 font-medium">Final Depth</div>
                    <div className="text-lg font-bold text-green-800">{iterativeResult.final_depth}</div>
                  </div>
                  <div className="bg-blue-50/50 rounded-lg p-3 border border-blue-200/50">
                    <div className="text-sm text-blue-600 font-medium">Iterations</div>
                    <div className="text-lg font-bold text-blue-800">{iterativeResult.iteration_count}</div>
                  </div>
                  <div className="bg-purple-50/50 rounded-lg p-3 border border-purple-200/50">
                    <div className="text-sm text-purple-600 font-medium">Tables Used</div>
                    <div className="text-lg font-bold text-purple-800">{iterativeResult.tables_used?.length || 0}</div>
                  </div>
                  <div className="bg-orange-50/50 rounded-lg p-3 border border-orange-200/50">
                    <div className="text-sm text-orange-600 font-medium">Results</div>
                    <div className="text-lg font-bold text-orange-800">{iterativeResult.row_count || 0} rows</div>
                  </div>
                </div>

                {iterativeResult.tables_used && iterativeResult.tables_used.length > 0 && (
                  <div className="bg-blue-50/30 rounded-lg p-3 border border-blue-200/30">
                    <div className="text-sm text-blue-700 font-medium mb-2">Tables Selected by AI:</div>
                    <div className="flex flex-wrap gap-1">
                      {iterativeResult.tables_used.map((table, index) => (
                        <span 
                          key={index}
                          className="px-2 py-1 bg-blue-100/70 text-blue-800 text-xs rounded-md border border-blue-200/50"
                        >
                          {table}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Process Log */}
          {iterativeResult.process_log && iterativeResult.process_log.length > 0 && (
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle 
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setShowProcessLog(!showProcessLog)}
                >
                  <div className="flex items-center gap-2">
                    AI Decision Process Log
                    <span className="text-sm font-normal text-muted-foreground">
                      ({iterativeResult.process_log.length} iterations)
                    </span>
                  </div>
                  {showProcessLog ? (
                    <ChevronDown className="w-5 h-5" />
                  ) : (
                    <ChevronRight className="w-5 h-5" />
                  )}
                </CardTitle>
              </CardHeader>
              {showProcessLog && (
                <CardContent>
                  <div className="space-y-4">
                    {iterativeResult.process_log.map((logEntry, index) => (
                      <div 
                        key={index}
                        className={`border rounded-lg p-4 ${
                          logEntry.ai_decision === 'yes' 
                            ? 'bg-green-50/30 border-green-200/50' 
                            : 'bg-orange-50/30 border-orange-200/50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 rounded-md text-xs font-medium ${
                              logEntry.ai_decision === 'yes' 
                                ? 'bg-green-100 text-green-800' 
                                : 'bg-orange-100 text-orange-800'
                            }`}>
                              Depth {logEntry.depth}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              {logEntry.table_count} tables
                            </span>
                          </div>
                          <div className={`flex items-center gap-1 text-sm font-medium ${
                            logEntry.ai_decision === 'yes' ? 'text-green-700' : 'text-orange-700'
                          }`}>
                            {logEntry.ai_decision === 'yes' ? '✅ Sufficient' : '❌ Insufficient'}
                          </div>
                        </div>
                        
                        <div className="text-sm text-foreground mb-2">
                          <strong>AI Reasoning:</strong> {logEntry.ai_reasoning}
                        </div>
                        
                        {logEntry.tables && logEntry.tables.length > 0 && (
                          <div className="text-xs text-muted-foreground">
                            <strong>Tables:</strong> {logEntry.tables.join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* Generated SQL Query */}
          {(iterativeResult?.sql_query || result?.sql_query) && (
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {iterativeResult?.sql_query ? "Optimized SQL Query (dbt Analysis)" : "Generated SQL Query"}
                  <div className="flex gap-2">
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={iterativeResult?.sql_query ? handleCopyIterativeSQL : handleCopySQL}
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy SQL
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-surface-elevated rounded-lg p-4 border border-border/50">
                  <pre className="text-sm font-mono text-foreground overflow-x-auto whitespace-pre-wrap">
                    {iterativeResult?.sql_query || result?.sql_query}
                  </pre>
                </div>
              </CardContent>
            </Card>
          )}

          {/* SQL Query Not Available Fallback */}
          {result && !result.sql_query && !iterativeResult?.sql_query && (
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
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Query Results */}
          {(iterativeResult?.results || result?.rows) && (
            <Card className="glass border-border/50">
              <CardHeader>
                <CardTitle>
                  {iterativeResult?.results ? "dbt Analysis Results" : "Query Results"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm mb-4">
                  <span className="text-muted-foreground">
                    Rows: {iterativeResult?.row_count || result?.rowCount || 0}
                  </span>
                  {result?.executionTime && (
                    <span className="text-muted-foreground">
                      Execution time: ~{result.executionTime}ms
                    </span>
                  )}
                  {iterativeResult?.final_depth !== undefined && (
                    <span className="text-muted-foreground">
                      Optimal depth: {iterativeResult.final_depth}
                    </span>
                  )}
                  {iterativeResult?.iteration_count && (
                    <span className="text-muted-foreground">
                      AI iterations: {iterativeResult.iteration_count}
                    </span>
                  )}
                </div>

                {/* Results Table */}
                {(() => {
                  const rows = iterativeResult?.results || result?.rows || [];
                  if (rows.length > 0) {
                    return (
                      <div className="overflow-x-auto border border-border/50 rounded-lg">
                        <table className="w-full text-sm">
                          <thead className="bg-surface-elevated/50">
                            <tr className="border-b border-border">
                              {Object.keys(rows[0]).map((header) => (
                                <th key={header} className="text-left p-3 font-medium">
                                  {header}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {rows.slice(0, 100).map((row, index) => (
                              <tr
                                key={index}
                                className="border-b border-border/50 hover:bg-surface-elevated/30 transition-colors"
                              >
                                {Object.keys(rows[0]).map((header) => (
                                  <td key={header} className="p-3">
                                    {typeof row[header] === 'number' ? (
                                      <span className="font-mono text-primary">
                                        {row[header].toLocaleString()}
                                      </span>
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
                    );
                  } else {
                    return (
                      <div className="text-center py-8 text-muted-foreground">
                        No data returned from the query
                      </div>
                    );
                  }
                })()}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
