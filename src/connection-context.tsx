import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';
import { DbConnection, ConnectionContext as ConnectionContextType, dbService } from '@/lib/api-service';
import { useToast } from '@/components/ui/use-toast';

// Create the context
const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

// Provider component
export const ConnectionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentConnection, setCurrentConnection] = useState<DbConnection | null>(null);
  const [savedConnections, setSavedConnections] = useState<DbConnection[]>([]);
  const { toast } = useToast();

  // Function to refresh the connection list
  const refreshConnections = async () => {
    try {
      const response = await dbService.getSavedConnections();
      if (response.status === 'success' && response.data) {
        setSavedConnections(response.data);
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

  // Load saved connections on component mount
  useEffect(() => {
    refreshConnections();
  }, []);

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
