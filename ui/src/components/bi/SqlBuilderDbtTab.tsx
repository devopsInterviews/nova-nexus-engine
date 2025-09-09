import React, { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Upload, FileJson, X, CheckCircle2, AlertCircle, FileText } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { dbService } from "@/lib/api-service";

interface DbtFile {
  name: string;
  content: string;
  size: number;
  type: string;
}

export function SqlBuilderDbtTab() {
  const { toast } = useToast();
  
  // State management
  const [selectedFile, setSelectedFile] = useState<DbtFile | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // Try to parse and validate dbt model structure
  const validateDbtContent = (content: string): { isValid: boolean; summary: string } => {
    try {
      const parsed = JSON.parse(content);
      
      // Check for common dbt file structures
      if (parsed.model || parsed.models) {
        return { 
          isValid: true, 
          summary: `dbt models file with ${Object.keys(parsed.models || parsed.model || {}).length} models` 
        };
      } else if (parsed.sources) {
        return { 
          isValid: true, 
          summary: `dbt sources file with ${Object.keys(parsed.sources).length} sources` 
        };
      } else if (parsed.version && parsed.nodes) {
        return { 
          isValid: true, 
          summary: `dbt manifest file (version ${parsed.version}) with ${Object.keys(parsed.nodes).length} nodes` 
        };
      } else if (Array.isArray(parsed)) {
        return { 
          isValid: true, 
          summary: `JSON array with ${parsed.length} items` 
        };
      } else {
        return { 
          isValid: true, 
          summary: `Generic JSON object with ${Object.keys(parsed).length} top-level keys` 
        };
      }
    } catch {
      return { isValid: false, summary: 'Invalid JSON format' };
    }
  };

  return (
    <div className="space-y-6">
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
                  <Alert variant={validation.isValid ? "default" : "destructive"}>
                    {validation.isValid ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <AlertCircle className="h-4 w-4" />
                    )}
                    <AlertDescription>
                      <strong>{validation.isValid ? 'Valid JSON:' : 'Invalid:'}</strong> {validation.summary}
                    </AlertDescription>
                  </Alert>
                );
              })()}
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

      {/* File Content Preview */}
      {selectedFile && (
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              File Content Preview
              <span className="text-sm font-normal text-muted-foreground">
                {selectedFile.content.split('\n').length} lines
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-96 w-full rounded-md border border-border/50">
              <pre className="p-4 text-sm font-mono text-foreground whitespace-pre-wrap">
                {selectedFile.content}
              </pre>
            </ScrollArea>
            
            {/* File Actions */}
            <div className="flex gap-2 mt-4">
              <Button
                variant="outline"
                onClick={() => navigator.clipboard.writeText(selectedFile.content)}
              >
                Copy Content
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  const blob = new Blob([selectedFile.content], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = selectedFile.name;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }}
              >
                Download File
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
