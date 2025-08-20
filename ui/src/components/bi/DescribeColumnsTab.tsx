import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { FileText, ArrowRight, Save, Eye, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useConnectionContext } from "@/connection-context";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";

export function DescribeColumnsTab() {
  const { currentConnection } = useConnectionContext();
  const { toast } = useToast();
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [space, setSpace] = useState("AAA");
  const [title, setTitle] = useState("Demo - database keys description");
  const [limit, setLimit] = useState<number>(2000);
  const [loadingTables, setLoadingTables] = useState(false);
  const [saving, setSaving] = useState(false);
  const [descriptions, setDescriptions] = useState<Array<{column: string; description: string}>>([]);

  const disabled = !currentConnection;

  useEffect(() => {
    const loadTables = async () => {
      if (!currentConnection) return;
      setLoadingTables(true);
      const res = await dbService.listTables(currentConnection);
      if (res.status === 'success' && res.data) {
        setTables(res.data);
        if (res.data.length > 0) setSelectedTable(res.data[0]);
      } else {
        toast({ variant: 'destructive', title: 'Error', description: res.error || 'Failed to load tables' });
      }
      setLoadingTables(false);
    };
    loadTables();
  }, [currentConnection]);

  const onUpdateConfluence = async () => {
    if (!currentConnection || !selectedTable) {
      toast({ variant: 'destructive', title: 'Missing info', description: 'Select a table and ensure connection is set' });
      return;
    }
    setSaving(true);
    const payload = {
      ...currentConnection,
      table: selectedTable,
      limit,
      space,
      title,
    } as any;
    const res = await dbService.describeColumns(payload);
    if (res.status === 'success' && res.data) {
      const rows = (res.data as any).descriptions || [];
      setDescriptions(rows);
      toast({ title: 'Confluence Updated', description: `Described ${rows.length} columns for ${selectedTable}` });
    } else {
      toast({ variant: 'destructive', title: 'Error', description: res.error || 'Failed to describe/update' });
    }
    setSaving(false);
  };

  const typeColors = {
    "INTEGER": "bg-primary/10 text-primary border-primary/20",
    "VARCHAR(255)": "bg-secondary/10 text-secondary border-secondary/20",
    "TIMESTAMP": "bg-accent/10 text-accent border-accent/20",
    "ENUM": "bg-warning/10 text-warning border-warning/20",
    "JSON": "bg-destructive/10 text-destructive border-destructive/20",
  } as const;

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
              Describe Columns → Confluence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Database</label>
                <Select value={currentConnection?.database || undefined} disabled>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Select database" />
                  </SelectTrigger>
                  <SelectContent>
                    {currentConnection?.database && (
                      <SelectItem value={currentConnection.database}>{currentConnection.database}</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Schema</label>
                <Select>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Select schema" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">public</SelectItem>
                    <SelectItem value="auth">auth</SelectItem>
                    <SelectItem value="analytics">analytics</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Table</label>
                <Select value={selectedTable} onValueChange={setSelectedTable} disabled={disabled || loadingTables}>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder={loadingTables ? "Loading tables..." : "Select table"} />
                  </SelectTrigger>
                  <SelectContent>
                    {tables.map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Two-Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Pane - Columns Table */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card className="glass border-border/50 h-[600px] flex flex-col">
            <CardHeader>
              <CardTitle>Column Descriptions</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto">
              <div className="space-y-4">
                {descriptions.length === 0 && (
                  <div className="text-sm text-muted-foreground">No descriptions loaded yet. Choose a table and click Update Confluence.</div>
                )}
                {descriptions.map((column, index) => (
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
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Textarea
                        placeholder="Description"
                        value={(column as any).description || ""}
                        className="bg-surface text-sm resize-none"
                        rows={2}
                        readOnly
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Right Pane - Confluence Update */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="space-y-6"
        >
          {/* Confluence Configuration */}
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle>Confluence Update</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Confluence Space</label>
                <Input placeholder="AAA" className="bg-surface-elevated" value={space} onChange={(e)=>setSpace(e.target.value)} />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Page Title</label>
                <Input placeholder="Demo - database keys description" className="bg-surface-elevated" value={title} onChange={(e)=>setTitle(e.target.value)} />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Sample Size Limit</label>
                <Input type="number" className="bg-surface-elevated" value={limit} onChange={(e)=>setLimit(parseInt(e.target.value || '0')||0)} />
              </div>
            </CardContent>
          </Card>

          {/* Preview */}
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                Confluence Preview
                <Button size="sm" variant="outline">
                  <Eye className="w-4 h-4 mr-2" />
                  Preview
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-surface-elevated rounded-lg p-4 border border-border/50 h-[300px] overflow-auto text-sm">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-primary">Users Table</h3>
                  
                  <div className="space-y-3">
                    <div className="border-l-4 border-primary pl-3">
                      <h4 className="font-medium">user_id (INTEGER, NOT NULL)</h4>
                      <p className="text-muted-foreground">Primary key identifier for user records</p>
                    </div>
                    
                    <div className="border-l-4 border-secondary pl-3">
                      <h4 className="font-medium">email (VARCHAR(255), NOT NULL)</h4>
                      <p className="text-muted-foreground">User's email address</p>
                    </div>
                    
                    <div className="border-l-4 border-accent pl-3">
                      <h4 className="font-medium">created_at (TIMESTAMP, NOT NULL)</h4>
                      <p className="text-muted-foreground">Timestamp when the user account was created</p>
                    </div>
                    
                    <div className="text-center text-muted-foreground text-xs">
                      ... and 3 more columns
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <Card className="glass border-border/50">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  disabled={disabled || saving || !selectedTable}
                  onClick={onUpdateConfluence}
                >
                  {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ArrowRight className="w-4 h-4 mr-2" />}
                  {saving ? 'Updating…' : 'Describe & Update Confluence'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}