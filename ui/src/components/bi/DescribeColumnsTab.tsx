import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { FileText, ArrowRight, Save, Eye, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { useConnectionContext } from "@/context/connection-context";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";

export function DescribeColumnsTab() {
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [columns, setColumns] = useState<Array<{column: string; description: string; data_type: string}>>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [loadingColumns, setLoadingColumns] = useState(false);

  const typeColors = {
    "INTEGER": "bg-primary/10 text-primary border-primary/20",
    "VARCHAR": "bg-secondary/10 text-secondary border-secondary/20",
    "VARCHAR(255)": "bg-secondary/10 text-secondary border-secondary/20",
    "TIMESTAMP": "bg-accent/10 text-accent border-accent/20",
    "ENUM": "bg-warning/10 text-warning border-warning/20",
    "JSON": "bg-destructive/10 text-destructive border-destructive/20",
    "TEXT": "bg-warning/10 text-warning border-warning/20",
  };

  // Load tables when connection changes
  useEffect(() => {
    const loadTables = async () => {
      if (!currentConnection) {
        setTables([]);
        setSelectedTable("");
        setColumns([]);
        return;
      }

      setLoadingTables(true);
      try {
        const response = await dbService.listTables(currentConnection);
        if (response.status === 'success' && Array.isArray(response.data)) {
          setTables(response.data as string[]);
          if (response.data.length > 0) {
            setSelectedTable(response.data[0]);
          }
        } else {
          toast({
            variant: "destructive",
            title: "Error",
            description: response.error || "Failed to load tables"
          });
        }
      } catch (error) {
        console.error("Error loading tables:", error);
        toast({
          variant: "destructive",
          title: "Error",
          description: "An unexpected error occurred while loading tables"
        });
      } finally {
        setLoadingTables(false);
      }
    };

    loadTables();
  }, [currentConnection, toast]);

  // Load columns when table selection changes
  const loadColumns = async () => {
    if (!currentConnection || !selectedTable) {
      setColumns([]);
      return;
    }

    setLoadingColumns(true);
    try {
      const response = await dbService.describeColumns({
        ...currentConnection,
        table: selectedTable,
        limit: 100
      });
      
      if (response.status === 'success' && response.data) {
        setColumns(response.data as any);
        toast({
          title: "Success",
          description: `Loaded ${(response.data as any[]).length} columns for table ${selectedTable}`
        });
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: response.error || "Failed to load column descriptions"
        });
      }
    } catch (error) {
      console.error("Error loading columns:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "An unexpected error occurred while loading column descriptions"
      });
    } finally {
      setLoadingColumns(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Table Selection */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              Describe Columns
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Current Connection</label>
                <Input 
                  value={currentConnection ? `${currentConnection.name} (${currentConnection.database})` : "No connection"}
                  disabled 
                  className="bg-surface-elevated"
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Table</label>
                <Select
                  value={selectedTable}
                  onValueChange={setSelectedTable}
                  disabled={!currentConnection || loadingTables || tables.length === 0}
                >
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder={loadingTables ? "Loading tables..." : "Select table"} />
                  </SelectTrigger>
                  <SelectContent>
                    {tables.map((table) => (
                      <SelectItem key={table} value={table}>
                        {table}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Actions</label>
                <Button 
                  onClick={loadColumns}
                  disabled={!currentConnection || !selectedTable || loadingColumns}
                  className="w-full"
                >
                  {loadingColumns ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <FileText className="w-4 h-4 mr-2" />
                  )}
                  {loadingColumns ? "Loading..." : "Describe Columns"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Columns Display */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Column Descriptions</CardTitle>
          </CardHeader>
          <CardContent>
            {columns.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {!currentConnection ? "No database connection available" :
                 !selectedTable ? "Select a table to view its columns" :
                 "Click 'Describe Columns' to load column information"}
              </div>
            ) : (
              <div className="space-y-4">
                {columns.map((column, index) => (
                  <motion.div
                    key={column.column}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 + index * 0.1 }}
                    className="p-4 rounded-lg bg-surface-elevated/50 border border-border/50 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <code className="font-mono font-medium text-primary">{column.column}</code>
                        {column.data_type && (
                          <Badge variant="outline" className={typeColors[column.data_type as keyof typeof typeColors] || "bg-muted/20 text-muted-foreground border-border"}>
                            {column.data_type}
                          </Badge>
                        )}
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Textarea
                        value={column.description || ""}
                        placeholder="No description available"
                        className="bg-surface text-sm resize-none"
                        rows={2}
                        readOnly
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}