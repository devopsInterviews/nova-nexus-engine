import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { FileText, ArrowRight, Save, Eye } from "lucide-react";

export function DescribeColumnsTab() {
  const columns = [
    { 
      name: "user_id", 
      type: "INTEGER", 
      nullable: false, 
      description: "",
      aiSuggestion: "Primary key identifier for user records"
    },
    { 
      name: "email", 
      type: "VARCHAR(255)", 
      nullable: false, 
      description: "User's email address",
      aiSuggestion: "Unique email address for user authentication and communication"
    },
    { 
      name: "created_at", 
      type: "TIMESTAMP", 
      nullable: false, 
      description: "",
      aiSuggestion: "Timestamp when the user account was created"
    },
    { 
      name: "last_login", 
      type: "TIMESTAMP", 
      nullable: true, 
      description: "",
      aiSuggestion: "Most recent login timestamp, null if user never logged in"
    },
    { 
      name: "subscription_tier", 
      type: "ENUM", 
      nullable: true, 
      description: "User subscription level",
      aiSuggestion: "User's current subscription plan (free, premium, enterprise)"
    },
    { 
      name: "profile_data", 
      type: "JSON", 
      nullable: true, 
      description: "",
      aiSuggestion: "Flexible JSON storage for user profile information and preferences"
    },
  ];

  const typeColors = {
    "INTEGER": "bg-primary/10 text-primary border-primary/20",
    "VARCHAR(255)": "bg-secondary/10 text-secondary border-secondary/20",
    "TIMESTAMP": "bg-accent/10 text-accent border-accent/20",
    "ENUM": "bg-warning/10 text-warning border-warning/20",
    "JSON": "bg-destructive/10 text-destructive border-destructive/20",
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
              Describe Columns → Confluence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Database</label>
                <Select>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Select database" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="production">Production DB</SelectItem>
                    <SelectItem value="staging">Staging DB</SelectItem>
                    <SelectItem value="analytics">Analytics DB</SelectItem>
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
                <Select>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Select table" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="users">users</SelectItem>
                    <SelectItem value="orders">orders</SelectItem>
                    <SelectItem value="products">products</SelectItem>
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
                {columns.map((column, index) => (
                  <motion.div
                    key={column.name}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 + index * 0.1 }}
                    className="p-4 rounded-lg bg-surface-elevated/50 border border-border/50 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <code className="font-mono font-medium text-primary">{column.name}</code>
                        <Badge variant="outline" className={typeColors[column.type as keyof typeof typeColors]}>
                          {column.type}
                        </Badge>
                        {!column.nullable && (
                          <Badge variant="outline" className="bg-warning/10 text-warning border-warning/20 text-xs">
                            NOT NULL
                          </Badge>
                        )}
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Textarea
                        placeholder={column.aiSuggestion}
                        value={column.description}
                        className="bg-surface text-sm resize-none"
                        rows={2}
                      />
                      
                      {column.aiSuggestion && !column.description && (
                        <Button size="sm" variant="outline" className="text-xs">
                          <span className="mr-1">🤖</span>
                          Use AI Suggestion
                        </Button>
                      )}
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
                <Input placeholder="DATA-DOCS" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Page Title</label>
                <Input placeholder="Database Schema Documentation" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Update Mode</label>
                <Select>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Append to existing" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="append">Append to existing</SelectItem>
                    <SelectItem value="replace">Replace section</SelectItem>
                    <SelectItem value="new">Create new page</SelectItem>
                  </SelectContent>
                </Select>
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
                <Button className="bg-gradient-primary flex-1">
                  <Save className="w-4 h-4 mr-2" />
                  Save Descriptions
                </Button>
                <Button variant="outline" className="flex-1">
                  <ArrowRight className="w-4 h-4 mr-2" />
                  Update Confluence
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}