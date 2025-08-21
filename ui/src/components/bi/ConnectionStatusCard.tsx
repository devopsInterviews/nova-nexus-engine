import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { MoreVertical, Database, Wifi } from "lucide-react";
import { useConnectionContext } from "@/context/connection-context";
import { useToast } from "@/components/ui/use-toast";

interface ConnectionStatusCardProps {
  className?: string;
}

export function ConnectionStatusCard({ className = "" }: ConnectionStatusCardProps) {
  const { currentConnection, savedConnections, setCurrentConnection } = useConnectionContext();
  const { toast } = useToast();

  const handleSwitchConnection = (connection: any) => {
    setCurrentConnection(connection);
    toast({
      title: "Connection Switched",
      description: `Now connected to ${connection.name || connection.host}`
    });
  };

  if (!currentConnection) {
    return (
      <Card className={`glass border-border/50 border-destructive/20 ${className}`}>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-destructive animate-pulse"></div>
              <div>
                <h4 className="font-semibold text-destructive">No Database Connection</h4>
                <p className="text-sm text-muted-foreground">
                  Please connect to a database first
                </p>
              </div>
            </div>
            <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20">
              Disconnected
            </Badge>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`glass border-border/50 ${className}`}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-success animate-pulse"></div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-primary" />
                <h4 className="font-semibold">Connected to Database</h4>
              </div>
              <p className="text-sm text-muted-foreground">
                {currentConnection.host}:{currentConnection.port}/{currentConnection.database}
                {currentConnection.name && ` (${currentConnection.name})`}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-success/10 text-success border-success/20">
              <Wifi className="w-3 h-3 mr-1" />
              Connected
            </Badge>
            
            {/* Connection Switch Menu */}
            {savedConnections.length > 1 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <div className="px-2 py-1.5 text-sm font-semibold">Switch Connection</div>
                  {savedConnections
                    .filter(conn => conn.id !== currentConnection.id)
                    .map((connection) => (
                      <DropdownMenuItem
                        key={connection.id}
                        onClick={() => handleSwitchConnection(connection)}
                        className="cursor-pointer"
                      >
                        <Database className="w-4 h-4 mr-2" />
                        <div className="flex-1">
                          <div className="font-medium">
                            {connection.name || `${connection.host}:${connection.port}`}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {connection.database} ({connection.database_type})
                          </div>
                        </div>
                      </DropdownMenuItem>
                    ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
