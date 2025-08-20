import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { Database, Plus, Trash2, TestTube, Eye, EyeOff, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { dbService } from "@/lib/api-service";
import { useToast } from "@/components/ui/use-toast";
import { useConnectionContext } from "@/connection-context";
import ApiHealthCheck from "@/components/ui/api-health-check";

export function ConnectDBTab() {
  const [selectedDb, setSelectedDb] = useState<string>("postgres");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [connectionMessage, setConnectionMessage] = useState("");
  const [apiHealthStatus, setApiHealthStatus] = useState<'checking' | 'healthy' | 'unhealthy' | null>(null);
  const [apiHealthMessage, setApiHealthMessage] = useState("");
  const { toast } = useToast();
  const { savedConnections, refreshConnections, setCurrentConnection } = useConnectionContext();
  
  // Check API health on component mount
  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        setApiHealthStatus('checking');
        const response = await dbService.checkApiHealth();
        if (response.status === 'success' && response.data && response.data.status === 'ok') {
          setApiHealthStatus('healthy');
          setApiHealthMessage("API is operational");
          console.log("API Health Check: Healthy", response.data);
        } else {
          setApiHealthStatus('unhealthy');
          setApiHealthMessage(response.error || "API service is unavailable");
          console.error("API Health Check: Unhealthy", response.error);
        }
      } catch (error) {
        setApiHealthStatus('unhealthy');
        setApiHealthMessage("Failed to connect to API");
        console.error("API Health Check: Error", error);
      }
    };
    
    checkApiHealth();
  }, []);
  
  // Form state
  const [formData, setFormData] = useState({
    host: "localhost",
    port: "5432",
    database: "",
    user: "",
    password: "",
    name: "",
  });
  
  const dbDefaults = {
    mssql: { port: "1433", icon: "🏢" },
    postgres: { port: "5432", icon: "🐘" },
    mysql: { port: "3306", icon: "🐬" },
    mongodb: { port: "27017", icon: "🍃" },
    oracle: { port: "1521", icon: "🔶" },
    redis: { port: "6379", icon: "🔴" },
  };

  // Update port when database type changes
  const handleDbTypeChange = (type: string) => {
    setSelectedDb(type);
    if (dbDefaults[type as keyof typeof dbDefaults]) {
      setFormData({
        ...formData,
        port: dbDefaults[type as keyof typeof dbDefaults].port
      });
    }
  };

  // Handle input changes
  const handleInputChange = (field: string, value: string) => {
    setFormData({
      ...formData,
      [field]: value
    });
  };

  // Test connection
  const testConnection = async () => {
    setConnectionStatus('testing');
    setIsLoading(true);
    
    try {
      const response = await dbService.testConnection({
        host: formData.host,
        port: parseInt(formData.port),
        database: formData.database,
        user: formData.user,
        password: formData.password,
        database_type: selectedDb
      });
      
      if (response.status === 'success' && response.data) {
        if (response.data.success) {
          setConnectionStatus('success');
          setConnectionMessage(response.data.message);
          toast({
            title: "Connection Successful",
            description: response.data.message,
          });
        } else {
          setConnectionStatus('error');
          setConnectionMessage(response.data.message);
          toast({
            variant: "destructive",
            title: "Connection Failed",
            description: response.data.message,
          });
        }
      } else {
        setConnectionStatus('error');
        setConnectionMessage(response.error || "Unknown error");
        toast({
          variant: "destructive",
          title: "Error",
          description: response.error || "Failed to test connection",
        });
      }
    } catch (error) {
      console.error("Error testing connection:", error);
      setConnectionStatus('error');
      setConnectionMessage("An unexpected error occurred");
      toast({
        variant: "destructive",
        title: "Error",
        description: "An unexpected error occurred while testing the connection",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Save connection
  const saveConnection = async () => {
    if (!formData.name) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please provide a name for this connection",
      });
      return;
    }
    
    setIsLoading(true);
    
    try {
      const response = await dbService.saveConnection({
        host: formData.host,
        port: parseInt(formData.port),
        database: formData.database,
        user: formData.user,
        password: formData.password,
        database_type: selectedDb,
        name: formData.name
      });
      
      if (response.status === 'success' && response.data) {
        toast({
          title: "Connection Saved",
          description: `Connection "${formData.name}" has been saved successfully`,
        });
        
        // Refresh the connections list
        await refreshConnections();
        
        // Reset form
        setFormData({
          ...formData,
          name: ""
        });
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: response.error || "Failed to save connection",
        });
      }
    } catch (error) {
      console.error("Error saving connection:", error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "An unexpected error occurred while saving the connection",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Connect to a saved connection
  const connectToSaved = (connection: any) => {
    setCurrentConnection({
      host: connection.host,
      port: connection.port,
      database: connection.database,
      user: connection.user,
      password: connection.password,
      database_type: connection.database_type,
      name: connection.name
    });
    
    toast({
      title: "Connection Selected",
      description: `Connected to "${connection.name}"`,
    });
  };
  
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
      {/* API Health Check */}
      <ApiHealthCheck />
      
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
                <label className="text-sm font-medium">Connection Name</label>
                <Input 
                  placeholder="My Database Connection" 
                  className="bg-surface-elevated"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Database Type</label>
                <Select value={selectedDb} onValueChange={handleDbTypeChange}>
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
                <Input 
                  placeholder="localhost" 
                  className="bg-surface-elevated"
                  value={formData.host}
                  onChange={(e) => handleInputChange('host', e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Port</label>
                <Input 
                  placeholder={selectedDb ? dbDefaults[selectedDb as keyof typeof dbDefaults]?.port : "5432"}
                  className="bg-surface-elevated"
                  value={formData.port}
                  onChange={(e) => handleInputChange('port', e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Database Name</label>
                <Input 
                  placeholder="mydb" 
                  className="bg-surface-elevated"
                  value={formData.database}
                  onChange={(e) => handleInputChange('database', e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Username</label>
                <Input 
                  placeholder="username" 
                  className="bg-surface-elevated"
                  value={formData.user}
                  onChange={(e) => handleInputChange('user', e.target.value)}
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <div className="relative">
                  <Input 
                    type={showPassword ? "text" : "password"}
                    placeholder="password" 
                    className="bg-surface-elevated pr-10"
                    value={formData.password}
                    onChange={(e) => handleInputChange('password', e.target.value)}
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
              <Button 
                variant="outline" 
                className="flex items-center gap-2"
                onClick={testConnection}
                disabled={isLoading || !formData.host || !formData.database || !formData.user || !formData.password}
              >
                {isLoading && connectionStatus === 'testing' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <TestTube className="w-4 h-4" />
                )}
                Test Connection
              </Button>
              <Button 
                className="bg-gradient-primary flex items-center gap-2"
                onClick={saveConnection}
                disabled={isLoading || connectionStatus !== 'success' || !formData.name}
              >
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
            <CardTitle>Connection Status</CardTitle>
          </CardHeader>
          <CardContent>
            {/* API Health Status */}
            {apiHealthStatus && (
              <div className={`mb-4 px-4 py-2 rounded-md flex items-center gap-2 ${
                apiHealthStatus === 'healthy' ? 'bg-success/10 text-success border border-success/20' : 
                apiHealthStatus === 'unhealthy' ? 'bg-destructive/10 text-destructive border border-destructive/20' : 
                'bg-muted/30 text-muted-foreground border border-muted/20'
              }`}>
                {apiHealthStatus === 'checking' && <Loader2 className="w-4 h-4 animate-spin" />}
                {apiHealthStatus === 'healthy' && <CheckCircle className="w-4 h-4" />}
                {apiHealthStatus === 'unhealthy' && <AlertCircle className="w-4 h-4" />}
                <span className="text-sm font-medium">
                  API Status: {apiHealthStatus === 'checking' ? 'Checking API...' : 
                              apiHealthStatus === 'healthy' ? apiHealthMessage : 
                              apiHealthMessage}
                </span>
              </div>
            )}
            
            <div className="bg-surface-elevated rounded-lg p-6 border border-border/50">
              {connectionStatus === 'idle' ? (
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                    <Database className="w-8 h-8 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium">Ready to Connect</h3>
                  <p className="text-muted-foreground">
                    Configure your database connection above and test it
                  </p>
                </div>
              ) : connectionStatus === 'testing' ? (
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto">
                    <Loader2 className="w-8 h-8 text-warning animate-spin" />
                  </div>
                  <h3 className="text-lg font-medium">Testing Connection...</h3>
                  <p className="text-muted-foreground">
                    Attempting to connect to your database
                  </p>
                </div>
              ) : connectionStatus === 'success' ? (
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto">
                    <CheckCircle className="w-8 h-8 text-success" />
                  </div>
                  <h3 className="text-lg font-medium">Connection Successful!</h3>
                  <p className="text-success">
                    {connectionMessage}
                  </p>
                  <div className="pt-2">
                    <p className="text-muted-foreground">
                      You can now save this connection or continue working with it
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center space-y-3">
                  <div className="w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center mx-auto">
                    <AlertCircle className="w-8 h-8 text-destructive" />
                  </div>
                  <h3 className="text-lg font-medium">Connection Failed</h3>
                  <p className="text-destructive">
                    {connectionMessage}
                  </p>
                  <div className="pt-2">
                    <p className="text-muted-foreground">
                      Please check your connection details and try again
                    </p>
                  </div>
                </div>
              )}
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
            <CardTitle>Saved Connections</CardTitle>
          </CardHeader>
          <CardContent>
            {savedConnections.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No saved connections yet. Create and save a connection to see it here.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {savedConnections.map((connection, index) => (
                  <motion.div
                    key={connection.id || index}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.7 + index * 0.1 }}
                    className="p-4 rounded-lg glass border-border/50 hover:shadow-glow transition-all duration-smooth group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="text-xl">
                          {dbDefaults[connection.database_type as keyof typeof dbDefaults]?.icon || '📊'}
                        </span>
                        <div>
                          <h4 className="font-medium group-hover:text-primary transition-colors">
                            {connection.name}
                          </h4>
                          <p className="text-sm text-muted-foreground">
                            {connection.host}:{connection.port}/{connection.database}
                          </p>
                        </div>
                      </div>
                      
                      <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                        saved
                      </Badge>
                    </div>
                    
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        variant="outline" 
                        className="flex-1"
                        onClick={() => connectToSaved(connection)}
                      >
                        Connect
                      </Button>
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
