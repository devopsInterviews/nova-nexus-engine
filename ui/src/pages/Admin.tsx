/**
 * Admin Dashboard Page
 * 
 * General-purpose administrative interface for system-wide management.
 * Provides a centralized control panel for various administrative tasks.
 * 
 * Current Sections:
 * - Research - IDA MCP: View and manage all users' IDA MCP servers (view details, upgrade, delete)
 * 
 * Access Control: Only visible and accessible to users with is_admin=true.
 * Future expansion: Users management, system settings, analytics, logs, billing, etc.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield } from "lucide-react";
import { AdminMcpServers } from "@/components/admin/AdminMcpServers";

export default function Admin() {
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

      {/* Research - IDA MCP Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <Card className="glass border-0 mb-6">
          <CardHeader>
            <CardTitle>Research - IDA MCP</CardTitle>
            <CardDescription>
              Manage all users' IDA MCP server deployments
            </CardDescription>
          </CardHeader>
        </Card>
        
        <AdminMcpServers />
      </motion.div>
    </div>
  );
}
