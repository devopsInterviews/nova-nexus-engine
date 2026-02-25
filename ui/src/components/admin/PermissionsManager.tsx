import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Search, Save, CheckSquare, Square, Shield } from "lucide-react";
import { navigationItems } from "@/components/layout/AppSidebar";

interface PermissionData {
  users: number[];
  groups: number[];
}

interface Permissions {
  [tab: string]: PermissionData;
}

interface User {
  id: number;
  username: string;
}

interface Group {
  id: number;
  name: string;
}

export function PermissionsManager() {
  const [permissions, setPermissions] = useState<Permissions>({});
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const TABS = navigationItems.map(item => item.title);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const headers = { 'Authorization': `Bearer ${token}` };

      // Fetch permissions
      const pRes = await fetch('/api/permissions', { headers });
      const pData = await pRes.json();
      
      const initialPermissions: Permissions = {};
      // Initialize all tabs
      TABS.forEach(tab => {
        initialPermissions[tab] = pData.status === 'success' && pData.data[tab] 
          ? pData.data[tab] 
          : { users: [], groups: [] };
      });
      setPermissions(initialPermissions);

      // Fetch users
      const uRes = await fetch('/api/users', { headers });
      const uData = await uRes.json();
      if (uData.status === 'success' && uData.data && uData.data.users) {
        setUsers(uData.data.users);
      }

      // Fetch groups
      try {
        const gRes = await fetch('/api/sso/groups', { headers });
        if (gRes.ok) {
            const gData = await gRes.json();
            setGroups(gData.groups || []);
        }
      } catch (e) {
          console.warn("Could not fetch groups", e);
      }
      
    } catch (err) {
      console.error("Failed to fetch permissions data:", err);
      toast.error("Failed to load permissions data");
    } finally {
      setLoading(false);
    }
  };

  const handleUserToggle = (tab: string, userId: number) => {
    setPermissions(prev => {
      const next = { ...prev };
      if (!next[tab]) next[tab] = { users: [], groups: [] };
      
      if (next[tab].users.includes(userId)) {
        next[tab].users = next[tab].users.filter(id => id !== userId);
      } else {
        next[tab].users = [...next[tab].users, userId];
      }
      return next;
    });
  };

  const handleGroupToggle = (tab: string, groupId: number) => {
    setPermissions(prev => {
      const next = { ...prev };
      if (!next[tab]) next[tab] = { users: [], groups: [] };
      
      if (next[tab].groups.includes(groupId)) {
        next[tab].groups = next[tab].groups.filter(id => id !== groupId);
      } else {
        next[tab].groups = [...next[tab].groups, groupId];
      }
      return next;
    });
  };

  const savePermissions = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      
      // Convert to array format expected by backend
      const payload = {
        permissions: Object.keys(permissions).map(tab => ({
          tab_name: tab,
          user_ids: permissions[tab].users,
          group_ids: permissions[tab].groups
        }))
      };

      const res = await fetch('/api/permissions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to save permissions");
      }
      toast.success("Permissions saved successfully!");
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : "Failed to save permissions");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="glass border-0">
        <CardContent className="p-8 flex items-center justify-center">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            <span className="text-muted-foreground">Loading permissions...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const filteredUsers = users.filter(u => 
    u.username !== 'admin' && 
    u.username.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  const filteredGroups = groups.filter(g => 
    g.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Card className="glass border-0 shadow-lg">
      <CardHeader className="pb-4 border-b border-border/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-2xl flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              Tab Permissions Matrix
            </CardTitle>
            <CardDescription className="mt-1.5">
              Assign which users and groups can access specific tabs in the application.
            </CardDescription>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search users & groups..."
                className="pl-9 h-10 bg-surface/50 border-border/50 focus-visible:ring-primary/30"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Button 
              onClick={savePermissions} 
              disabled={saving}
              className="bg-primary hover:bg-primary/90 text-primary-foreground min-w-[140px]"
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  Saving...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Save className="w-4 h-4" />
                  Save Changes
                </span>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="text-xs uppercase bg-surface/80 border-b border-border/50 text-muted-foreground sticky top-0 z-10">
              <tr>
                <th className="px-6 py-4 font-semibold w-[15%] min-w-[120px]">Tab Module</th>
                <th className="px-6 py-4 font-semibold w-[42.5%] min-w-[300px] border-l border-border/30">Allowed Users</th>
                <th className="px-6 py-4 font-semibold w-[42.5%] min-w-[300px] border-l border-border/30">Allowed Groups</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {TABS.map((tab) => (
                <tr key={tab} className="bg-transparent hover:bg-surface/30 transition-colors">
                  <td className="px-6 py-5 font-medium text-foreground align-top">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-primary/60" />
                      {tab}
                    </div>
                  </td>
                  
                  <td className="px-6 py-5 align-top border-l border-border/30">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {filteredUsers.length > 0 ? (
                        filteredUsers.map(user => {
                          const isChecked = permissions[tab]?.users?.includes(user.id) || false;
                          return (
                            <div 
                              key={`user-${user.id}`} 
                              onClick={() => handleUserToggle(tab, user.id)}
                              className={`flex items-center gap-2.5 p-2 rounded-md cursor-pointer transition-all duration-200 border ${
                                isChecked 
                                  ? 'bg-primary/10 border-primary/20 text-foreground shadow-sm' 
                                  : 'bg-surface/30 border-transparent text-muted-foreground hover:bg-surface/60 hover:text-foreground'
                              }`}
                            >
                              <div className="flex-shrink-0">
                                {isChecked ? (
                                  <CheckSquare className="w-4 h-4 text-primary" />
                                ) : (
                                  <Square className="w-4 h-4 opacity-50" />
                                )}
                              </div>
                              <span className="truncate text-sm select-none" title={user.username}>
                                {user.username}
                              </span>
                            </div>
                          );
                        })
                      ) : (
                        <div className="col-span-full text-muted-foreground text-xs italic">
                          No users found matching search.
                        </div>
                      )}
                    </div>
                  </td>
                  
                  <td className="px-6 py-5 align-top border-l border-border/30 bg-surface/10">
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                      {filteredGroups.length > 0 ? (
                        filteredGroups.map(group => {
                          const isChecked = permissions[tab]?.groups?.includes(group.id) || false;
                          return (
                            <div 
                              key={`group-${group.id}`} 
                              onClick={() => handleGroupToggle(tab, group.id)}
                              className={`flex items-center gap-2.5 p-2 rounded-md cursor-pointer transition-all duration-200 border ${
                                isChecked 
                                  ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400 shadow-sm' 
                                  : 'bg-surface/30 border-transparent text-muted-foreground hover:bg-surface/60 hover:text-foreground'
                              }`}
                            >
                              <div className="flex-shrink-0">
                                {isChecked ? (
                                  <CheckSquare className="w-4 h-4 text-indigo-400" />
                                ) : (
                                  <Square className="w-4 h-4 opacity-50" />
                                )}
                              </div>
                              <span className="truncate text-sm select-none font-medium" title={group.name}>
                                {group.name}
                              </span>
                            </div>
                          );
                        })
                      ) : (
                        <div className="col-span-full text-muted-foreground text-xs italic">
                          No groups found matching search.
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}