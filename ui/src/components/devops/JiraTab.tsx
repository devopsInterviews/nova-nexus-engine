import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { motion } from "framer-motion";
import { Search, FileText, ExternalLink, AlertCircle, CheckCircle, Clock } from "lucide-react";

export function JiraTab() {
  const recentTickets = [
    { 
      id: "PROJ-123", 
      title: "Database performance optimization", 
      status: "In Progress", 
      priority: "High",
      assignee: "john.doe",
      created: "2 days ago"
    },
    { 
      id: "PROJ-124", 
      title: "User authentication bug fix", 
      status: "Done", 
      priority: "Critical",
      assignee: "jane.smith",
      created: "3 days ago"
    },
    { 
      id: "PROJ-125", 
      title: "API rate limiting implementation", 
      status: "To Do", 
      priority: "Medium",
      assignee: "mike.wilson",
      created: "1 day ago"
    },
  ];

  const statusColors = {
    "To Do": "bg-muted/20 text-muted-foreground border-border",
    "In Progress": "bg-warning/10 text-warning border-warning/20",
    "Done": "bg-success/10 text-success border-success/20",
    "Blocked": "bg-destructive/10 text-destructive border-destructive/20",
  };

  const priorityColors = {
    "Low": "bg-muted/20 text-muted-foreground border-border",
    "Medium": "bg-primary/10 text-primary border-primary/20",
    "High": "bg-warning/10 text-warning border-warning/20",
    "Critical": "bg-destructive/10 text-destructive border-destructive/20",
  };

  const statusIcons = {
    "To Do": Clock,
    "In Progress": AlertCircle,
    "Done": CheckCircle,
    "Blocked": AlertCircle,
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Ticket Investigation */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="w-5 h-5 text-primary" />
              Investigate by Ticket
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-4">
              <div className="flex-1 space-y-2">
                <label className="text-sm font-medium">Ticket ID or URL</label>
                <Input 
                  placeholder="PROJ-123 or https://jira.company.com/browse/PROJ-123"
                  className="bg-surface-elevated"
                />
              </div>
              <div className="flex items-end">
                <Button className="bg-gradient-primary">
                  <Search className="w-4 h-4 mr-2" />
                  Investigate
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Investigation Results */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              Investigation Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Ticket Summary */}
            <div className="p-4 rounded-lg bg-surface-elevated/50 border border-border/50">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-primary">PROJ-123</h3>
                  <h4 className="font-medium text-foreground">Database performance optimization</h4>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={statusColors["In Progress"]}>
                    In Progress
                  </Badge>
                  <Badge variant="outline" className={priorityColors["High"]}>
                    High Priority
                  </Badge>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Assignee:</span>
                  <p className="font-medium">John Doe</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Reporter:</span>
                  <p className="font-medium">Jane Smith</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Created:</span>
                  <p className="font-medium">2 days ago</p>
                </div>
              </div>
            </div>

            {/* AI Analysis */}
            <div className="p-4 rounded-lg glass border border-primary/20 bg-primary/5">
              <h4 className="font-medium mb-3 text-primary flex items-center gap-2">
                🤖 AI Analysis & Insights
              </h4>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="font-medium text-foreground">Related Issues:</span>
                  <p className="text-muted-foreground mt-1">
                    Found 3 similar performance issues in the last 6 months. Common pattern: 
                    database queries without proper indexing.
                  </p>
                </div>
                <div>
                  <span className="font-medium text-foreground">Suggested Solution:</span>
                  <p className="text-muted-foreground mt-1">
                    1. Add composite index on user_id and created_at columns
                    <br />
                    2. Implement query result caching for frequent reads
                    <br />
                    3. Consider database connection pooling optimization
                  </p>
                </div>
                <div>
                  <span className="font-medium text-foreground">Impact Assessment:</span>
                  <p className="text-muted-foreground mt-1">
                    High - affects 85% of user queries, average response time 2.3s
                  </p>
                </div>
              </div>
            </div>

            {/* Linked Issues */}
            <div>
              <h4 className="font-medium mb-3">Linked Issues & Dependencies</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors">
                  <div className="flex items-center gap-3">
                    <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="font-medium">PROJ-118 - Database migration scripts</p>
                      <p className="text-sm text-muted-foreground">Blocks this issue</p>
                    </div>
                  </div>
                  <Badge variant="outline" className={statusColors["Done"]}>
                    Done
                  </Badge>
                </div>
                
                <div className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors">
                  <div className="flex items-center gap-3">
                    <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="font-medium">PROJ-126 - Performance monitoring dashboard</p>
                      <p className="text-sm text-muted-foreground">Related to this issue</p>
                    </div>
                  </div>
                  <Badge variant="outline" className={statusColors["To Do"]}>
                    To Do
                  </Badge>
                </div>
              </div>
            </div>

            {/* Comment Section */}
            <div>
              <h4 className="font-medium mb-3">Add Investigation Notes</h4>
              <Textarea 
                placeholder="Add your investigation findings, analysis, or recommendations..."
                className="bg-surface-elevated"
                rows={4}
              />
              <Button className="mt-3 bg-gradient-primary">
                Add Comment to Ticket
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Recent Tickets */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Recent Tickets</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentTickets.map((ticket, index) => {
                const StatusIcon = statusIcons[ticket.status as keyof typeof statusIcons];
                return (
                  <motion.div
                    key={ticket.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + index * 0.1 }}
                    className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group cursor-pointer"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg border ${statusColors[ticket.status as keyof typeof statusColors]}`}>
                        <StatusIcon className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-primary">{ticket.id}</span>
                          <span className="text-muted-foreground">•</span>
                          <span className="font-medium group-hover:text-primary transition-colors">{ticket.title}</span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Assigned to {ticket.assignee} • Created {ticket.created}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className={priorityColors[ticket.priority as keyof typeof priorityColors]}>
                        {ticket.priority}
                      </Badge>
                      <Badge variant="outline" className={statusColors[ticket.status as keyof typeof statusColors]}>
                        {ticket.status}
                      </Badge>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}