import React from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import Home from "./pages/Home";
import DevOps from "./pages/DevOps";
import BI from "./pages/BI";
import Analytics from "./pages/Analytics";
import Tests from "./pages/Tests";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import { LoginScreen } from "./components/auth/LoginScreen";
import Users from "./pages/Users";
import { ConnectionProvider } from "@/context/connection-context";
import { AuthProvider, useAuth } from "@/context/auth-context";

const queryClient = new QueryClient();

const PrivateRoute = ({ children }: { children: React.ReactElement }) => {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
};

const LoginWrapper = () => {
  const { login, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (username: string, password: string) => {
    try {
      clearError(); // Clear any previous errors
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      // Error is handled by the auth context
      console.error('Login failed:', err);
    }
  };

  return (
    <LoginScreen
      onLogin={handleLogin}
      loading={isLoading}
      error={error}
    />
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <ConnectionProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginWrapper />} />
              <Route 
                path="/" 
                element={
                  <PrivateRoute>
                    <AppLayout />
                  </PrivateRoute>
                }
              >
                <Route index element={<Home />} />
                <Route path="devops/*" element={<DevOps />} />
                <Route path="bi/*" element={<BI />} />
                <Route path="analytics" element={<Analytics />} />
                <Route path="tests" element={<Tests />} />
                <Route path="settings" element={<Settings />} />
                <Route path="users" element={<Users />} />
              </Route>
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ConnectionProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
