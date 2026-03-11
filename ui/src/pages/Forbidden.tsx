import React from "react";
import { useLocation, Navigate } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

const Forbidden = () => {
  const location = useLocation();

  React.useEffect(() => {
    console.error(
      "403 Error: User attempted to access unauthorized route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center p-4">
      <div className="text-center space-y-6 max-w-md">
        <div className="flex justify-center">
          <div className="p-4 bg-[#F16C6C]/10 rounded-full">
            <ShieldAlert className="w-16 h-16 text-[#F16C6C]" />
          </div>
        </div>
        
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Access Denied</h1>
          <p className="text-muted-foreground">
            You don't have permission to view this page. If you believe this is a mistake, please contact your administrator.
          </p>
        </div>

        <div className="pt-4">
          <Button asChild className="w-full sm:w-auto">
            <a href="/">Return to Dashboard</a>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Forbidden;
