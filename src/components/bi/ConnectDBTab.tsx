import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { Database, Plus, Trash2, TestTube, Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export function ConnectDBTab() {
  const [selectedDb, setSelectedDb] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  
  const dbDefaults = {
    mssql: { port: "1433", icon: "🏢" },
    postgres: { port: "5432", icon: "🐘" },
    mysql: { port: "3306", icon: "🐬" },
    mongodb: { port: "27017", icon: "🍃" },
    oracle: { port: "1521", icon: "🔶" },
    redis: { port: "6379", icon: "🔴" },
  };

  const savedConnections = [
    { name: "Production DB", type: "postgres", host: "prod-db.company.com", status: "connected" },
    { name: "Analytics DB", type: "mssql", host: "analytics.company.com", status: "connected" },
    { name: "Cache Layer", type: "redis", host: "cache.company.com", status: "disconnected" },
    { name: "Document Store", type: "mongodb", host: "docs.company.com", status: "connected" },
  ];

  const statusColors = {
    connected: "bg-success/10 text-success border-success/20",
    disconnected: "bg-destructive/10 text-destructive border-destructive/20",
    connecting: "bg-warning/10 text-warning border-warning/20 animate-pulse",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      {/* Connection Form */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              New Database Connection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Database Type</label>
                <Select value={selectedDb} onValueChange={setSelectedDb}>
                  <SelectTrigger className="bg-surface-elevated">
                    <SelectValue placeholder="Select database type" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(dbDefaults).map(([key, db]) => (
                      <SelectItem key={key} value={key}>
                        <div className="flex items-center gap-2">
                          <span>{db.icon}</span>
                          <span className="capitalize">{key}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Host/IP Address</label>
                <Input placeholder="localhost" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Port</label>
                <Input 
                  placeholder={selectedDb ? dbDefaults[selectedDb as keyof typeof dbDefaults]?.port : "5432"}
                  className="bg-surface-elevated"
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Database Name</label>
                <Input placeholder="mydb" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Username</label>
                <Input placeholder="username" className="bg-surface-elevated" />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <div className="relative">
                  <Input 
                    type={showPassword ? "text" : "password"}
                    placeholder="password" 
                    className="bg-surface-elevated pr-10" 
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Eye className="h-4 w-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
            
            <div className="flex gap-3">
              <Button variant="outline" className="flex items-center gap-2">
                <TestTube className="w-4 h-4" />
                Test Connection
              </Button>
              <Button className="bg-gradient-primary flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Save Connection
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Connection Results Preview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Connection Results Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-surface-elevated rounded-lg p-6 border border-border/50">
              <div className="text-center space-y-3">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <Database className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-lg font-medium">Ready to Connect</h3>
                <p className="text-muted-foreground">
                  Configure your database connection above to see schema preview and table information
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Saved Connections */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle>Saved Profiles</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {savedConnections.map((connection, index) => (
                <motion.div
                  key={connection.name}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.7 + index * 0.1 }}
                  className="p-4 rounded-lg glass border-border/50 hover:shadow-glow transition-all duration-smooth group"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-xl">
                        {dbDefaults[connection.type as keyof typeof dbDefaults]?.icon}
                      </span>
                      <div>
                        <h4 className="font-medium group-hover:text-primary transition-colors">
                          {connection.name}
                        </h4>
                        <p className="text-sm text-muted-foreground">{connection.host}</p>
                      </div>
                    </div>
                    
                    <Badge variant="outline" className={statusColors[connection.status as keyof typeof statusColors]}>
                      {connection.status}
                    </Badge>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1">
                      Connect
                    </Button>
                    <Button size="sm" variant="ghost">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}