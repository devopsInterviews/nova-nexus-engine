import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Brain, ArrowRight, Lightbulb, Send, Loader2, AlertCircle } from "lucide-react";
import { useState } from "react";
import { useConnectionContext } from "@/context/connection-context";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";
import { ConnectionStatusCard } from "./ConnectionStatusCard";

export function ColumnSuggestionsTab() {
  const [prompt, setPrompt] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("AAA");
  const [confluenceTitle, setConfluenceTitle] = useState("Demo - database keys description");
  const [isLoading, setIsLoading] = useState(false);
  const [suggestedColumns, setSuggestedColumns] = useState<Array<{name: string, type: string, description: string}>>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({name: "", type: "", description: ""});
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();

  const typeColors = {
    // Integers
    "INTEGER": "bg-blue-500/15 text-blue-600 border-blue-400/30",
    "BIGINT": "bg-blue-600/15 text-blue-700 border-blue-500/30", 
    "SMALLINT": "bg-blue-400/15 text-blue-500 border-blue-300/30",
    "INT": "bg-blue-500/15 text-blue-600 border-blue-400/30",
    
    // Strings
    "VARCHAR(255)": "bg-green-500/15 text-green-600 border-green-400/30",
    "VARCHAR": "bg-green-500/15 text-green-600 border-green-400/30",
    "TEXT": "bg-green-600/15 text-green-700 border-green-500/30",
    "CHAR": "bg-green-400/15 text-green-500 border-green-300/30",
    "STRING": "bg-green-500/15 text-green-600 border-green-400/30",
    
    // Dates
    "TIMESTAMP": "bg-purple-500/15 text-purple-600 border-purple-400/30",
    "DATETIME": "bg-purple-600/15 text-purple-700 border-purple-500/30",
    "DATE": "bg-purple-400/15 text-purple-500 border-purple-300/30",
    "TIME": "bg-purple-300/15 text-purple-400 border-purple-200/30",
    
    // Boolean
    "BOOLEAN": "bg-orange-500/15 text-orange-600 border-orange-400/30",
    "BOOL": "bg-orange-500/15 text-orange-600 border-orange-400/30",
    
    // Numbers
    "DECIMAL": "bg-yellow-500/15 text-yellow-600 border-yellow-400/30",
    "NUMERIC": "bg-yellow-600/15 text-yellow-700 border-yellow-500/30",
    "FLOAT": "bg-yellow-400/15 text-yellow-500 border-yellow-300/30",
    "DOUBLE": "bg-yellow-700/15 text-yellow-800 border-yellow-600/30",
    "REAL": "bg-yellow-300/15 text-yellow-400 border-yellow-200/30",
    "NUMBER": "bg-yellow-500/15 text-yellow-600 border-yellow-400/30",
    
    // Special
    "ENUM": "bg-red-500/15 text-red-600 border-red-400/30",
    "SET": "bg-red-400/15 text-red-500 border-red-300/30",
    "JSON": "bg-indigo-500/15 text-indigo-600 border-indigo-400/30",
    "JSONB": "bg-indigo-600/15 text-indigo-700 border-indigo-500/30",
    "UUID": "bg-pink-500/15 text-pink-600 border-pink-400/30",
    "BINARY": "bg-gray-500/15 text-gray-600 border-gray-400/30",
    "BLOB": "bg-gray-600/15 text-gray-700 border-gray-500/30",
  };

  // Get color for type (case insensitive with fallback)
  const getTypeColor = (type: string): string => {
    const upperType = type.toUpperCase();
    
    // Direct match
    if (typeColors[upperType as keyof typeof typeColors]) {
      return typeColors[upperType as keyof typeof typeColors];
    }
    
    // Try base type (remove size specifiers like VARCHAR(255) -> VARCHAR)
    const baseType = upperType.replace(/\(\d+\)/, '');
    if (typeColors[baseType as keyof typeof typeColors]) {
      return typeColors[baseType as keyof typeof typeColors];
    }
    
    // Fallback
    return "bg-gray-400/15 text-gray-600 border-gray-400/30";
  };

  // Parse column suggestion - handles both objects from API and string formats
  const parseColumnSuggestion = (suggestion: any) => {
    if (typeof suggestion === 'object' && suggestion.name) {
      // Already parsed object from API
      let type = (suggestion.data_type || suggestion.type || "TEXT").toString();
      
      // Clean up the type - extract the actual database type
      // Handle cases like "VARCHAR(255)", "INTEGER", "TEXT", etc.
      const typeMatch = type.match(/^([A-Z]+(?:\(\d+\))?)/i);
      if (typeMatch) {
        type = typeMatch[1].toUpperCase();
      } else {
        // If no match, take the first word and uppercase it
        type = type.split(/\s+/)[0].toUpperCase();
      }
      
      return {
        name: suggestion.name || "",
        type: type,
        description: suggestion.description || ""
      };
    }
    
    if (typeof suggestion === 'string') {
      // Parse string format "tablename.keyname - description - type"
      const parts = suggestion.split(' - ');
      
      if (parts.length >= 3) {
        // We have all three parts: name, description, type
        const name = parts[0].trim();
        const description = parts[1].trim();
        let type = parts[2].trim();
        
        // Clean up the type - take only the first word/type declaration
        // Handle cases like "VARCHAR(255)" or "INTEGER" or "TEXT etc"
        const typeMatch = type.match(/^([A-Z]+(?:\(\d+\))?)/i);
        if (typeMatch) {
          type = typeMatch[1].toUpperCase();
        } else {
          // If no match, take the first word and uppercase it
          type = type.split(/\s+/)[0].toUpperCase();
        }
        
        return {
          name: name,
          description: description,
          type: type
        };
      } else if (parts.length === 2) {
        // Only name and description, default type to TEXT
        return {
          name: parts[0].trim(),
          description: parts[1].trim(),
          type: "TEXT"
        };
      } else {
        // Only name provided
        return {
          name: suggestion.trim(),
          description: "",
          type: "TEXT"
        };
      }
    }
    
    return {
      name: String(suggestion),
      description: "",
      type: "TEXT"
    };
  };

  // Generate column suggestions
  const generateSuggestions = async () => {
    if (!currentConnection) {
      toast({
        variant: "destructive",
        title: "No Connection",
        description: "Please connect to a database first in the 'Connect to DB' tab"
      });
      return;
    }

    if (!prompt.trim()) {
      toast({
        variant: "destructive",
        title: "Empty Prompt",
        description: "Please enter a description of your table requirements"
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

    setIsLoading(true);

    try {
      const response = await dbService.suggestColumns({
        ...currentConnection,
        user_prompt: prompt,
        confluenceSpace: confluenceSpace,
        confluenceTitle: confluenceTitle
      });

      console.log("🔍 Column suggestions API response:", response);

      if (response.status === 'success' && response.data && (response.data as any).suggested_columns) {
        console.log("📋 Raw suggested columns:", (response.data as any).suggested_columns);
        
        // Parse the columns using the new parser function
        const columns = (response.data as any).suggested_columns.map((column: any) => {
          const parsed = parseColumnSuggestion(column);
          console.log("🔧 Parsed column:", {
            original: column,
            parsed: parsed,
            originalType: typeof column,
            parsedType: parsed.type,
            typeColor: getTypeColor(parsed.type)
          });
          return parsed;
        });

        console.log("✅ Final parsed columns:", columns);
        setSuggestedColumns(columns);

        toast({
          title: "Success",
          description: `Generated ${columns.length} column suggestions`
        });
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: response.error || "Failed to generate column suggestions"
        });
      }
    } catch (error) {
      console.error("Error generating suggestions:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "An unexpected error occurred"
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Handle edit column
  const handleEditColumn = (index: number) => {
    setEditingIndex(index);
    setEditForm(suggestedColumns[index]);
  };

  // Handle save edit
  const handleSaveEdit = () => {
    if (editingIndex !== null) {
      const updated = [...suggestedColumns];
      updated[editingIndex] = editForm;
      setSuggestedColumns(updated);
      setEditingIndex(null);
      setEditForm({name: "", type: "", description: ""});
      toast({
        title: "Column Updated",
        description: "Column suggestion has been updated"
      });
    }
  };

  // Handle cancel edit
  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditForm({name: "", type: "", description: ""});
  };

  // Handle delete column
  const handleDeleteColumn = (index: number) => {
    const updated = suggestedColumns.filter((_, i) => i !== index);
    setSuggestedColumns(updated);
    toast({
      title: "Column Removed",
      description: "Column suggestion has been removed"
    });
  };

  const clearPrompt = () => {
    setPrompt("");
    setConfluenceSpace("AAA");
    setConfluenceTitle("Demo - database keys description");
    setSuggestedColumns([]);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Connection Status Card */}
      <ConnectionStatusCard />

      {/* AI Prompt Interface */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              AI Column Suggestions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                <label className="text-sm font-medium">Confluence Title</label>
                <Input 
                  placeholder="Demo - database keys description"
                  className="bg-surface-elevated"
                  value={confluenceTitle}
                  onChange={(e) => setConfluenceTitle(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Describe your table requirements</label>
              <Textarea 
                placeholder="I need a user table for an e-commerce application that stores customer information, login history, and subscription details..."
                className="bg-surface-elevated min-h-[120px]"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={isLoading}
              />
            </div>
            
            <div className="flex gap-3">
              <Button 
                className="bg-gradient-primary flex items-center gap-2"
                onClick={generateSuggestions}
                disabled={isLoading || !prompt.trim() || !confluenceSpace.trim() || !confluenceTitle.trim() || !currentConnection}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Lightbulb className="w-4 h-4" />
                )}
                {isLoading ? "Generating..." : "Generate Suggestions"}
              </Button>
              <Button 
                variant="outline"
                onClick={clearPrompt}
                disabled={isLoading || (!prompt.trim() && !confluenceSpace.trim() && !confluenceTitle.trim() && suggestedColumns.length === 0)}
              >
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Generated Suggestions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Generated Column Suggestions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {suggestedColumns.map((column, index) => (
                <motion.div
                  key={`${column.name}-${index}`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + index * 0.1 }}
                  className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                >
                  {editingIndex === index ? (
                    // Edit mode
                    <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
                      <Input
                        value={editForm.name}
                        onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                        placeholder="Column name"
                        className="bg-surface-elevated text-sm"
                      />
                      <Input
                        value={editForm.description}
                        onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                        placeholder="Description"
                        className="bg-surface-elevated text-sm"
                      />
                      <Input
                        value={editForm.type}
                        onChange={(e) => setEditForm({...editForm, type: e.target.value})}
                        placeholder="Type"
                        className="bg-surface-elevated text-sm"
                      />
                    </div>
                  ) : (
                    // Display mode
                    <div className="flex items-center gap-4 flex-1">
                      <div className="w-3 h-3 bg-primary rounded-full animate-pulse" />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <code className="font-mono font-medium text-primary">{column.name}</code>
                          <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getTypeColor(column.type)}`}>
                            {column.type}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{column.description}</p>
                      </div>
                    </div>
                  )}
                  
                  <div className="flex items-center gap-2">
                    {editingIndex === index ? (
                      <>
                        <Button size="sm" variant="ghost" onClick={handleSaveEdit}>
                          Save
                        </Button>
                        <Button size="sm" variant="ghost" onClick={handleCancelEdit}>
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => handleEditColumn(index)}>
                          Edit
                        </Button>
                        <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => handleDeleteColumn(index)}>
                          Remove
                        </Button>
                      </>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Action Buttons */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
      >
        <Card className="glass border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium mb-1">Ready to build your table?</h3>
                <p className="text-sm text-muted-foreground">
                  Send these suggestions to the SQL Builder to generate CREATE TABLE statements
                </p>
              </div>
              
              <Button className="bg-gradient-primary flex items-center gap-2">
                <Send className="w-4 h-4" />
                Send to SQL Builder
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Additional AI Features */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>AI Enhancement Options</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg glass border-border/50 text-center">
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl">🔗</span>
                </div>
                <h4 className="font-medium mb-2">Suggest Relationships</h4>
                <p className="text-sm text-muted-foreground">
                  AI will analyze and suggest foreign key relationships
                </p>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50 text-center">
                <div className="w-12 h-12 bg-secondary/10 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl">📊</span>
                </div>
                <h4 className="font-medium mb-2">Optimize Indexes</h4>
                <p className="text-sm text-muted-foreground">
                  Get recommendations for optimal database indexes
                </p>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50 text-center">
                <div className="w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-xl">🛡️</span>
                </div>
                <h4 className="font-medium mb-2">Security Analysis</h4>
                <p className="text-sm text-muted-foreground">
                  AI-powered security and compliance recommendations
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}