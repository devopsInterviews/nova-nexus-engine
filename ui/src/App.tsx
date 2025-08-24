import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import Home from "./pages/Home";
import DevOps from "./pages/DevOps";
import BI from "./pages/BI";
import Analytics from "./pages/Analytics";
import Tests from "./pages/Tests";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import { ConnectionProvider } from "@/context/connection-context";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ConnectionProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<Home />} />
              <Route path="devops/*" element={<DevOps />} />
              <Route path="bi/*" element={<BI />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="tests" element={<Tests />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </ConnectionProvider>
  </QueryClientProvider>
);

export default App;
