import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';
import { DbConnection, ConnectionContext as ConnectionContextType, dbService } from '@/lib/api-service';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/context/auth-context';

// Create the context
const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

// Provider component
export const ConnectionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentConnection, setCurrentConnection] = useState<DbConnection | null>(null);
  const [savedConnections, setSavedConnections] = useState<DbConnection[]>([]);
  const { toast } = useToast();
  const { user, token, initializing } = useAuth();

  // Function to refresh the connection list
  const refreshConnections = async () => {
    // Only attempt to load connections if user is authenticated
    if (!user || !token) {
      console.log('ConnectionContext: Skipping connection load - user not authenticated');
      setSavedConnections([]); // Clear connections if not authenticated
      return;
    }

    try {
      console.log('ConnectionContext: Loading saved connections for user:', user.username);
      const response = await dbService.getSavedConnections();
      if (response.status === 'success' && response.data) {
        // Normalize database_type casing and ensure required fields present
        const normalized = response.data.map(c => ({
          ...c,
          database_type: String((c as any).database_type || (c as any).db_type || '').toLowerCase(),
          host: (c as any).host || (c as any).db_host,
          port: (c as any).port || (c as any).db_port,
          user: (c as any).user || (c as any).db_user,
          password: (c as any).password || (c as any).db_password || '***',
          database: (c as any).database || (c as any).db_name,
          name: (c as any).name || (c as any).connection_name,
        }));
        setSavedConnections(normalized as any);
        console.log(`ConnectionContext: Loaded ${normalized.length} connections`);
      }
    } catch (error) {
      console.error('Failed to refresh connections:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to load saved connections."
      });
    }
  };

  // Load saved connections when user authentication is ready
  useEffect(() => {
    if (!initializing) {
      // Authentication is complete, now we can try to load connections
      console.log('ConnectionContext: Authentication ready, loading connections...');
      refreshConnections();
    }
  }, [user, token, initializing]); // React to changes in authentication state

  return (
    <ConnectionContext.Provider
      value={{
        currentConnection,
        setCurrentConnection,
        savedConnections,
        setSavedConnections,
        refreshConnections
      }}
    >
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook for using the connection context
export const useConnectionContext = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnectionContext must be used within a ConnectionProvider');
  }
  return context;
};
