import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Code2, Play, Download, Copy, FileText, BarChart3 } from "lucide-react";
import { useState } from "react";

export function SQLBuilderTab() {
  const [queryType, setQueryType] = useState("select");

  const sampleResults = [
    { id: 1, name: "John Doe", email: "john@example.com", created_at: "2024-01-15", status: "active" },
    { id: 2, name: "Jane Smith", email: "jane@example.com", created_at: "2024-01-12", status: "active" },
    { id: 3, name: "Mike Wilson", email: "mike@example.com", created_at: "2024-01-10", status: "inactive" },
    { id: 4, name: "Sarah Connor", email: "sarah@example.com", created_at: "2024-01-08", status: "active" },
  ];

  const queryTemplates = [
    { type: "select", label: "SELECT Query", example: "SELECT * FROM users WHERE status = 'active'" },
    { type: "insert", label: "INSERT Data", example: "INSERT INTO users (name, email) VALUES ('New User', 'user@example.com')" },
    { type: "update", label: "UPDATE Records", example: "UPDATE users SET status = 'inactive' WHERE last_login < '2023-01-01'" },
    { type: "create", label: "CREATE Table", example: "CREATE TABLE products (id SERIAL PRIMARY KEY, name VARCHAR(255), price DECIMAL(10,2))" },
  ];

  const generatedSQL = `SELECT 
    u.id,
    u.name,
    u.email,
    u.created_at,
    u.status,
    COUNT(o.id) as order_count,
    SUM(o.total_amount) as total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.status = 'active'
    AND u.created_at >= '2024-01-01'
GROUP BY u.id, u.name, u.email, u.created_at, u.status
HAVING COUNT(o.id) > 0
ORDER BY total_spent DESC
LIMIT 100;`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Prompt Editor */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Code2 className="w-5 h-5 text-primary" />
              SQL Builder & Runner
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Quick Templates */}
            <div className="flex flex-wrap gap-2">
              {queryTemplates.map((template) => (
                <Button
                  key={template.type}
                  variant={queryType === template.type ? "default" : "outline"}
                  size="sm"
                  onClick={() => setQueryType(template.type)}
                  className={queryType === template.type ? "bg-gradient-primary" : ""}
                >
                  {template.label}
                </Button>
              ))}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Natural language prompt</label>
              <Textarea 
                placeholder="Find all active users who have made at least one order in 2024, show their total spending..."
                className="bg-surface-elevated min-h-[100px]"
              />
            </div>
            
            <div className="flex gap-3">
              <Button className="bg-gradient-primary flex items-center gap-2">
                <Code2 className="w-4 h-4" />
                Generate SQL
              </Button>
              <Button variant="outline">
                <FileText className="w-4 h-4 mr-2" />
                Load Template
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Generated SQL */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Generated SQL Query
              <div className="flex gap-2">
                <Button size="sm" variant="outline">
                  <Copy className="w-4 h-4" />
                </Button>
                <Button size="sm" variant="outline">
                  <Download className="w-4 h-4" />
                </Button>
                <Button size="sm" className="bg-gradient-primary">
                  <Play className="w-4 h-4 mr-2" />
                  Execute
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-surface-elevated rounded-lg p-4 border border-border/50">
              <pre className="text-sm font-mono text-foreground overflow-x-auto">
                {generatedSQL}
              </pre>
            </div>
            
            <div className="mt-4 flex items-center gap-4 text-sm">
              <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                ✓ Syntax Valid
              </Badge>
              <span className="text-muted-foreground">Estimated rows: ~1,247</span>
              <span className="text-muted-foreground">Execution time: ~0.15s</span>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Results Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Query Results
              <div className="flex gap-2">
                <Button size="sm" variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button size="sm" variant="outline">
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Visualize
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left p-3 font-medium">ID</th>
                    <th className="text-left p-3 font-medium">Name</th>
                    <th className="text-left p-3 font-medium">Email</th>
                    <th className="text-left p-3 font-medium">Created</th>
                    <th className="text-left p-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sampleResults.map((row, index) => (
                    <motion.tr
                      key={row.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.7 + index * 0.1 }}
                      className="border-b border-border/50 hover:bg-surface-elevated/30 transition-colors"
                    >
                      <td className="p-3 font-mono text-primary">{row.id}</td>
                      <td className="p-3">{row.name}</td>
                      <td className="p-3 text-muted-foreground">{row.email}</td>
                      <td className="p-3">{row.created_at}</td>
                      <td className="p-3">
                        <Badge 
                          variant="outline" 
                          className={row.status === 'active' 
                            ? "bg-success/10 text-success border-success/20" 
                            : "bg-muted/20 text-muted-foreground border-border"
                          }
                        >
                          {row.status}
                        </Badge>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>Showing 4 of 1,247 results</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline">Previous</Button>
                <Button size="sm" variant="outline">Next</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Query Analysis */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Query Performance Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-success">Performance</h4>
                <p className="text-2xl font-bold text-success">Excellent</p>
                <p className="text-sm text-muted-foreground">Query optimized for indexes</p>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-primary">Complexity</h4>
                <p className="text-2xl font-bold text-primary">Medium</p>
                <p className="text-sm text-muted-foreground">JOIN with aggregation</p>
              </div>
              
              <div className="p-4 rounded-lg glass border-border/50">
                <h4 className="font-medium mb-2 text-warning">Cost</h4>
                <p className="text-2xl font-bold text-warning">Low</p>
                <p className="text-sm text-muted-foreground">Efficient resource usage</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}