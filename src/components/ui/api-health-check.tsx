import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle, Loader2 } from "lucide-react";
import { dbService } from "@/lib/api-service";

export default function ApiHealthCheck() {
  const [apiStatus, setApiStatus] = useState<'idle' | 'checking' | 'healthy' | 'error'>('idle');
  const [statusDetails, setStatusDetails] = useState<any>(null);
  const [errorDetails, setErrorDetails] = useState<string>("");
  
  const checkApiHealth = async () => {
    setApiStatus('checking');
    try {
      const response = await dbService.checkApiHealth();
      console.log("API Health check response:", response);
      
      if (response.status === 'success' && response.data) {
        setApiStatus('healthy');
        setStatusDetails(response.data);
        setErrorDetails("");
      } else {
        setApiStatus('error');
        setErrorDetails(response.error || "Unknown error occurred");
        setStatusDetails(null);
      }
    } catch (error) {
      console.error("API health check failed:", error);
      setApiStatus('error');
      setErrorDetails(error instanceof Error ? error.message : "Failed to connect to API");
      setStatusDetails(null);
    }
  };
  
  useEffect(() => {
    // Check API health on component mount
    checkApiHealth();
  }, []);
  
  return (
    <Card className="mb-6">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          API Connection Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {apiStatus === 'checking' && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Checking API connection...</span>
              </div>
            )}
            
            {apiStatus === 'healthy' && (
              <div className="flex items-center gap-2 text-success">
                <CheckCircle className="w-5 h-5" />
                <span>API is operational</span>
                {statusDetails && (
                  <span className="text-xs text-muted-foreground ml-2">
                    ({statusDetails.service})
                  </span>
                )}
              </div>
            )}
            
            {apiStatus === 'error' && (
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="w-5 h-5" />
                <span>{errorDetails || "Unable to connect to API"}</span>
              </div>
            )}
          </div>
          
          <Button 
            variant="outline" 
            size="sm"
            onClick={checkApiHealth}
            disabled={apiStatus === 'checking'}
          >
            {apiStatus === 'checking' ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <></>
            )}
            Check Again
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
