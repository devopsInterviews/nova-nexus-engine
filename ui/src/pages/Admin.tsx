/**
 * Admin Dashboard Page
 * 
 * General-purpose administrative interface for system-wide management.
 * Provides a centralized control panel for various administrative tasks.
 * 
 * Current Tabs:
 * - Research: View and manage all users' IDA MCP servers (view details, upgrade, delete)
 * - Users: User management capabilities (coming soon)
 * - System: System-wide configuration and settings (coming soon)
 * 
 * Access Control: Only visible and accessible to users with is_admin=true.
 * Future expansion: Can include analytics, logs, billing, etc.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Shield, Search, Users as UsersIcon, Settings as SettingsIcon } from "lucide-react";
import { AdminMcpServers } from "@/components/admin/AdminMcpServers";

export default function Admin() {
  const [activeTab, setActiveTab] = useState("research");

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-center gap-3"
      >
        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Panel</h1>
          <p className="text-muted-foreground">
            System administration and management
          </p>
        </div>
      </motion.div>

      {/* Admin Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <Card className="glass border-0">
          <CardContent className="p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-3 mb-6">
                <TabsTrigger value="research" className="flex items-center gap-2">
                  <Search className="w-4 h-4" />
                  <span className="hidden sm:inline">Research / MCP</span>
                  <span className="sm:hidden">MCP</span>
                </TabsTrigger>
                <TabsTrigger value="users" className="flex items-center gap-2" disabled>
                  <UsersIcon className="w-4 h-4" />
                  <span className="hidden sm:inline">Users</span>
                  <span className="sm:hidden">Users</span>
                </TabsTrigger>
                <TabsTrigger value="system" className="flex items-center gap-2" disabled>
                  <SettingsIcon className="w-4 h-4" />
                  <span className="hidden sm:inline">System</span>
                  <span className="sm:hidden">System</span>
                </TabsTrigger>
              </TabsList>

              {/* Research Tab - MCP Server Management */}
              <TabsContent value="research" className="space-y-4">
                <AdminMcpServers />
              </TabsContent>

              {/* Users Tab - Coming Soon */}
              <TabsContent value="users" className="space-y-4">
                <div className="text-center py-12 text-muted-foreground">
                  <UsersIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>User management coming soon...</p>
                </div>
              </TabsContent>

              {/* System Tab - Coming Soon */}
              <TabsContent value="system" className="space-y-4">
                <div className="text-center py-12 text-muted-foreground">
                  <SettingsIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>System settings coming soon...</p>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
