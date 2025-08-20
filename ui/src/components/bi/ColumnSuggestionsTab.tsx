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

export function ColumnSuggestionsTab() {
  const [prompt, setPrompt] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("AAA");
  const [confluenceTitle, setConfluenceTitle] = useState("Demo - database keys description");
  const [isLoading, setIsLoading] = useState(false);
  const [suggestedColumns, setSuggestedColumns] = useState<Array<{name: string, type: string, description: string}>>([]);
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();

  const typeColors = {
    "INTEGER": "bg-primary/10 text-primary border-primary/20",
    "VARCHAR(255)": "bg-secondary/10 text-secondary border-secondary/20",
    "TIMESTAMP": "bg-accent/10 text-accent border-accent/20",
    "BOOLEAN": "bg-success/10 text-success border-success/20",
    "TEXT": "bg-warning/10 text-warning border-warning/20",
    "ENUM": "bg-destructive/10 text-destructive border-destructive/20",
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
        title: "Missing Confluence Info",
        description: "Please provide both Confluence Space and Title"
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

      if (response.status === 'success' && response.data && (response.data as any).suggested_columns) {
        // Use the properly formatted columns from the API
        const columns = (response.data as any).suggested_columns.map((column: any) => {
          return {
            name: column.name || "",
            type: column.data_type || "TEXT",
            description: column.description || ""
          };
        });

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
                  key={column.name}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + index * 0.1 }}
                  className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className="w-3 h-3 bg-primary rounded-full animate-pulse" />
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <code className="font-mono font-medium text-primary">{column.name}</code>
                        <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${typeColors[column.type as keyof typeof typeColors] || "bg-muted/20 text-muted-foreground border-border"}`}>
                          {column.type}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">{column.description}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button size="sm" variant="ghost">
                      Edit
                    </Button>
                    <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive">
                      Remove
                    </Button>
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