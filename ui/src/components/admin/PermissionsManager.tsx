import React, { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Search, Save, Shield, ShieldCheck, Crown, Users, UsersRound, Plus, Trash2, Eye, LayoutDashboard, Filter } from "lucide-react";
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
  is_admin?: boolean;
}

interface Group {
  id: number;
  name: string;
}

export function PermissionsManager() {
  const [permissions, setPermissions] = useState<Permissions>({});
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Tab filter
  const [tabFilter, setTabFilter] = useState("");

  // Tab access dialog state
  const [selectedTab, setSelectedTab] = useState<string | null>(null);
  const [dialogMode, setDialogMode] = useState<'view' | 'add'>('view');
  const [searchQuery, setSearchQuery] = useState("");

  // Admin role dialog state
  const [adminDialogOpen, setAdminDialogOpen] = useState(false);
  const [adminDialogMode, setAdminDialogMode] = useState<'view' | 'add'>('view');
  const [adminSearchQuery, setAdminSearchQuery] = useState("");
  const [adminSaving, setAdminSaving] = useState(false);

  // Admin groups state (groups that have admin access)
  const [adminGroupIds, setAdminGroupIds] = useState<number[]>([]);

  const TABS = navigationItems.map(item => item.title);
  const getTabDisplayName = (title: string) => navigationItems.find(n => n.title === title)?.displayLabel ?? title;

  // Non-admin users eligible for tab permission grants
  const users = useMemo(() => allUsers.filter(u => !u.is_admin), [allUsers]);
  // Users that have been granted admin role (excluding the built-in admin account)
  const adminUsers = useMemo(() => allUsers.filter(u => u.is_admin), [allUsers]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const [pRes, uRes, gRes, agRes] = await Promise.all([
        fetch('/api/permissions', { headers }),
        fetch('/api/users', { headers }),
        fetch('/api/sso/groups', { headers }).catch(() => null),
        fetch('/api/admin-groups', { headers }).catch(() => null),
      ]);

      const pData = await pRes.json();
      const uData = await uRes.json();
      let gData = { groups: [] };
      if (gRes && gRes.ok) {
        gData = await gRes.json();
      }
      if (agRes && agRes.ok) {
        const ct = agRes.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const agData = await agRes.json();
          setAdminGroupIds(agData.group_ids || []);
        }
      }

      const initialPermissions: Permissions = {};
      TABS.forEach(tab => {
        initialPermissions[tab] = pData.status === 'success' && pData.data[tab]
          ? pData.data[tab]
          : { users: [], groups: [] };
      });

      setPermissions(initialPermissions);

      if (uData.status === 'success' && uData.data && uData.data.users) {
        // Store all users except the built-in admin account
        setAllUsers(uData.data.users.filter((u: User) => u.username !== 'admin'));
      }
      setGroups(gData.groups || []);

    } catch (err) {
      console.error("Failed to fetch permissions data:", err);
      toast.error("Failed to load permissions data");
    } finally {
      setLoading(false);
    }
  };

  const savePermissions = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
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

  // --- Tab permission handlers ---

  const handleAddUser = (userId: number) => {
    if (!selectedTab) return;
    setPermissions(prev => {
      const next = { ...prev };
      if (!next[selectedTab].users.includes(userId)) {
        next[selectedTab].users = [...next[selectedTab].users, userId];
      }
      return next;
    });
  };

  const handleRemoveUser = (userId: number) => {
    if (!selectedTab) return;
    setPermissions(prev => {
      const next = { ...prev };
      next[selectedTab].users = next[selectedTab].users.filter(id => id !== userId);
      return next;
    });
  };

  const handleAddGroup = (groupId: number) => {
    if (!selectedTab) return;
    setPermissions(prev => {
      const next = { ...prev };
      if (!next[selectedTab].groups.includes(groupId)) {
        next[selectedTab].groups = [...next[selectedTab].groups, groupId];
      }
      return next;
    });
  };

  const handleRemoveGroup = (groupId: number) => {
    if (!selectedTab) return;
    setPermissions(prev => {
      const next = { ...prev };
      next[selectedTab].groups = next[selectedTab].groups.filter(id => id !== groupId);
      return next;
    });
  };

  const openDialog = (tab: string, mode: 'view' | 'add') => {
    setSelectedTab(tab);
    setDialogMode(mode);
    setSearchQuery("");
  };

  const closeDialog = () => {
    setSelectedTab(null);
    setSearchQuery("");
  };

  // --- Admin role handlers ---

  const handleGrantAdmin = async (userId: number) => {
    setAdminSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`/api/users/${userId}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ is_admin: true })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to grant admin role");
      }
      // Promote user locally and strip their explicit tab permissions (admins don't need them)
      setAllUsers(prev => prev.map(u => u.id === userId ? { ...u, is_admin: true } : u));
      setPermissions(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(tab => {
          next[tab] = { ...next[tab], users: next[tab].users.filter(id => id !== userId) };
        });
        return next;
      });
      toast.success("Admin role granted successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to grant admin role");
    } finally {
      setAdminSaving(false);
    }
  };

  const handleRevokeAdmin = async (userId: number) => {
    setAdminSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`/api/users/${userId}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ is_admin: false })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to revoke admin role");
      }
      setAllUsers(prev => prev.map(u => u.id === userId ? { ...u, is_admin: false } : u));
      toast.success("Admin role revoked successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke admin role");
    } finally {
      setAdminSaving(false);
    }
  };

  // --- Admin group handlers ---

  const handleGrantAdminGroup = async (groupId: number) => {
    setAdminSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/admin-groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ group_id: groupId })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to grant admin to group");
      }
      setAdminGroupIds(prev => [...prev, groupId]);
      toast.success("Admin access granted to group");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to grant admin to group");
    } finally {
      setAdminSaving(false);
    }
  };

  const handleRevokeAdminGroup = async (groupId: number) => {
    setAdminSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`/api/admin-groups/${groupId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to revoke admin from group");
      }
      setAdminGroupIds(prev => prev.filter(id => id !== groupId));
      toast.success("Admin access revoked from group");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke admin from group");
    } finally {
      setAdminSaving(false);
    }
  };

  // Filter logic for the tab access dialog
  const currentTabPerms = selectedTab ? permissions[selectedTab] : { users: [], groups: [] };

  const authorizedUsers = users.filter(u => currentTabPerms.users.includes(u.id));
  const authorizedGroups = groups.filter(g => currentTabPerms.groups.includes(g.id));

  const unauthorizedUsers = users.filter(u => !currentTabPerms.users.includes(u.id));
  const unauthorizedGroups = groups.filter(g => !currentTabPerms.groups.includes(g.id));

  const filteredAuthUsers = authorizedUsers.filter(u => u.username.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredAuthGroups = authorizedGroups.filter(g => g.name.toLowerCase().includes(searchQuery.toLowerCase()));

  const filteredUnauthUsers = unauthorizedUsers.filter(u => u.username.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredUnauthGroups = unauthorizedGroups.filter(g => g.name.toLowerCase().includes(searchQuery.toLowerCase()));

  // Filter logic for the admin dialog
  const filteredAdminUsers = adminUsers.filter(u => u.username.toLowerCase().includes(adminSearchQuery.toLowerCase()));
  const filteredNonAdminUsers = users.filter(u => u.username.toLowerCase().includes(adminSearchQuery.toLowerCase()));

  // Admin groups filter
  const adminGroups = groups.filter(g => adminGroupIds.includes(g.id));
  const nonAdminGroups = groups.filter(g => !adminGroupIds.includes(g.id));
  const filteredAdminGroups = adminGroups.filter(g => g.name.toLowerCase().includes(adminSearchQuery.toLowerCase()));
  const filteredNonAdminGroups = nonAdminGroups.filter(g => g.name.toLowerCase().includes(adminSearchQuery.toLowerCase()));

  // Tabs filtered by search
  const filteredTabs = TABS.filter(tab => {
    const q = tabFilter.toLowerCase();
    return tab.toLowerCase().includes(q) || getTabDisplayName(tab).toLowerCase().includes(q);
  });

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

  return (
    <div className="space-y-6">
      {/* ── Global Tab Access ── */}
      <div>
        <div className="flex items-center justify-between bg-surface/50 p-4 rounded-xl border border-border/50">
          <div>
            <h3 className="font-semibold flex items-center gap-2 text-lg">
              <Shield className="w-5 h-5 text-primary" />
              Global Tab Access
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Configure which users and groups have access to specific portal functionalities. Admins always have access.
            </p>
          </div>
          <Button
            onClick={savePermissions}
            disabled={saving}
            className="bg-primary hover:bg-primary/90 min-w-[140px] shadow-glow"
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

        {/* Tab filter */}
        <div className="mt-4 mb-2 relative max-w-xs">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter tabs…"
            className="pl-9 h-9 bg-surface/50"
            value={tabFilter}
            onChange={e => setTabFilter(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTabs.length === 0 ? (
            <div className="col-span-3 text-center py-8 text-sm text-muted-foreground border border-dashed rounded-lg">
              No tabs match "{tabFilter}"
            </div>
          ) : filteredTabs.map((tab) => {
            const userCount = permissions[tab]?.users?.length || 0;
            const groupCount = permissions[tab]?.groups?.length || 0;

            return (
              <Card key={tab} className="hover:border-primary/30 transition-all duration-300">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <LayoutDashboard className="w-5 h-5 text-muted-foreground" />
                    {getTabDisplayName(tab)}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-3 mb-6">
                    <Badge variant="secondary" className="flex items-center gap-1.5 py-1.5 px-3 bg-primary/10 text-primary hover:bg-primary/20">
                      <Users className="w-3.5 h-3.5" />
                      {userCount} {userCount === 1 ? 'User' : 'Users'}
                    </Badge>
                    <Badge variant="secondary" className="flex items-center gap-1.5 py-1.5 px-3 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20">
                      <UsersRound className="w-3.5 h-3.5" />
                      {groupCount} {groupCount === 1 ? 'Group' : 'Groups'}
                    </Badge>
                  </div>

                  <div className="flex gap-2 w-full">
                    <Button
                      variant="outline"
                      className="flex-1 border-border/50 hover:bg-surface/50"
                      onClick={() => openDialog(tab, 'view')}
                    >
                      <Eye className="w-4 h-4 mr-2" />
                      View Access
                    </Button>
                    <Button
                      variant="outline"
                      className="flex-1 border-border/50 hover:bg-primary/10 hover:text-primary hover:border-primary/30"
                      onClick={() => openDialog(tab, 'add')}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add Access
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* ── Admin Role Management ── */}
      <div>
        <div className="flex items-center justify-between bg-primary/10 border border-primary/20 p-4 rounded-xl">
          <div>
            <h3 className="font-semibold flex items-center gap-2 text-lg">
              <ShieldCheck className="w-5 h-5 text-primary" />
              Admin Role Management
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Grant or revoke administrator access. Admins bypass all tab restrictions and can perform privileged actions.
            </p>
          </div>
        </div>

        <div className="mt-4 max-w-sm">
          <Card className="border-primary/20 bg-primary/5 hover:border-primary/40 transition-all duration-300">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Crown className="w-5 h-5 text-primary" />
                Administrators
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-3 mb-6">
                <Badge variant="secondary" className="flex items-center gap-1.5 py-1.5 px-3 bg-primary/10 text-primary hover:bg-primary/20">
                  <Users className="w-3.5 h-3.5" />
                  {adminUsers.length} {adminUsers.length === 1 ? 'User' : 'Users'}
                </Badge>
                <Badge variant="secondary" className="flex items-center gap-1.5 py-1.5 px-3 bg-primary/10 text-primary hover:bg-primary/20">
                  <UsersRound className="w-3.5 h-3.5" />
                  {adminGroupIds.length} {adminGroupIds.length === 1 ? 'Group' : 'Groups'}
                </Badge>
              </div>
              <div className="flex gap-2 w-full">
                <Button
                  variant="outline"
                  className="flex-1 border-primary/30 hover:bg-primary/10 hover:border-primary/50"
                  onClick={() => { setAdminDialogOpen(true); setAdminDialogMode('view'); setAdminSearchQuery(''); }}
                >
                  <Eye className="w-4 h-4 mr-2" />
                  View Admins
                </Button>
                <Button
                  variant="outline"
                  className="flex-1 border-primary/30 hover:bg-primary/10 hover:text-primary hover:border-primary/50"
                  onClick={() => { setAdminDialogOpen(true); setAdminDialogMode('add'); setAdminSearchQuery(''); }}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Admin
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Tab Access Dialog ── */}
      <Dialog open={!!selectedTab} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col p-0 overflow-hidden bg-background">
          <div className="p-6 border-b border-border/50 bg-surface/30">
            <DialogTitle className="text-2xl flex items-center gap-2 mb-2">
              <Shield className="w-6 h-6 text-primary" />
              Manage Access: <span className="text-primary">{selectedTab ? getTabDisplayName(selectedTab) : ""}</span>
            </DialogTitle>
            <DialogDescription>
              {dialogMode === 'view'
                ? 'View and remove currently authorized users and groups.'
                : 'Search and add new users or groups to this tab.'}
            </DialogDescription>
          </div>

          <div className="flex border-b border-border/50">
            <button
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${dialogMode === 'view' ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:bg-surface/50'}`}
              onClick={() => { setDialogMode('view'); setSearchQuery(""); }}
            >
              Current Access
            </button>
            <button
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${dialogMode === 'add' ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:bg-surface/50'}`}
              onClick={() => { setDialogMode('add'); setSearchQuery(""); }}
            >
              Add New Access
            </button>
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            <div className="relative mb-6">
              <Search className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
              <Input
                placeholder="Search users or groups..."
                className="pl-10 h-10 bg-surface/50"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Users Column */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold mb-4 text-foreground/80 pb-2 border-b">
                  <Users className="w-4 h-4 text-primary" />
                  Users
                </h4>
                <div className="space-y-2">
                  {dialogMode === 'view' ? (
                    filteredAuthUsers.length > 0 ? (
                      filteredAuthUsers.map(u => (
                        <div key={u.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <span className="font-medium">{u.username}</span>
                          <Button variant="ghost" size="sm" onClick={() => handleRemoveUser(u.id)} className="h-8 px-2 text-destructive hover:text-destructive/90 hover:bg-destructive/10">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No users found</div>
                    )
                  ) : (
                    filteredUnauthUsers.length > 0 ? (
                      filteredUnauthUsers.map(u => (
                        <div key={u.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <span className="font-medium">{u.username}</span>
                          <Button variant="outline" size="sm" onClick={() => handleAddUser(u.id)} className="h-8 px-3 text-primary border-primary/30 hover:bg-primary/10">
                            <Plus className="w-4 h-4 mr-1" /> Add
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No users available to add</div>
                    )
                  )}
                </div>
              </div>

              {/* Groups Column */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold mb-4 text-foreground/80 pb-2 border-b">
                  <UsersRound className="w-4 h-4 text-indigo-400" />
                  Groups
                </h4>
                <div className="space-y-2">
                  {dialogMode === 'view' ? (
                    filteredAuthGroups.length > 0 ? (
                      filteredAuthGroups.map(g => (
                        <div key={g.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <span className="font-medium">{g.name}</span>
                          <Button variant="ghost" size="sm" onClick={() => handleRemoveGroup(g.id)} className="h-8 px-2 text-destructive hover:text-destructive/90 hover:bg-destructive/10">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No groups found</div>
                    )
                  ) : (
                    filteredUnauthGroups.length > 0 ? (
                      filteredUnauthGroups.map(g => (
                        <div key={g.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <span className="font-medium">{g.name}</span>
                          <Button variant="outline" size="sm" onClick={() => handleAddGroup(g.id)} className="h-8 px-3 text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/10">
                            <Plus className="w-4 h-4 mr-1" /> Add
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No groups available to add</div>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="p-4 border-t border-border/50 bg-surface/30">
            <Button variant="outline" onClick={closeDialog}>Close</Button>
            <Button onClick={() => { closeDialog(); savePermissions(); }}>Save All Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Admin Role Dialog ── */}
      <Dialog open={adminDialogOpen} onOpenChange={(open) => !open && setAdminDialogOpen(false)}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col p-0 overflow-hidden bg-background">
          <div className="p-6 border-b border-primary/20 bg-primary/5">
            <DialogTitle className="text-2xl flex items-center gap-2 mb-2">
              <ShieldCheck className="w-6 h-6 text-primary" />
              Admin Role Management
            </DialogTitle>
            <DialogDescription>
              {adminDialogMode === 'view'
                ? 'View and revoke administrator access from users and groups.'
                : 'Grant administrator access to users and groups.'}
            </DialogDescription>
          </div>

          <div className="flex border-b border-border/50">
            <button
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${adminDialogMode === 'view' ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:bg-surface/50'}`}
              onClick={() => { setAdminDialogMode('view'); setAdminSearchQuery(''); }}
            >
              Current Admins
            </button>
            <button
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${adminDialogMode === 'add' ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:bg-surface/50'}`}
              onClick={() => { setAdminDialogMode('add'); setAdminSearchQuery(''); }}
            >
              Add Admin Access
            </button>
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            <div className="relative mb-6">
              <Search className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
              <Input
                placeholder="Search users or groups..."
                className="pl-10 h-10 bg-surface/50"
                value={adminSearchQuery}
                onChange={(e) => setAdminSearchQuery(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Users Column */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold mb-4 text-foreground/80 pb-2 border-b">
                  <Users className="w-4 h-4 text-primary" />
                  Users
                </h4>
                <div className="space-y-2">
                  {adminDialogMode === 'view' ? (
                    filteredAdminUsers.length > 0 ? (
                      filteredAdminUsers.map(u => (
                        <div key={u.id} className="flex items-center justify-between p-3 rounded-lg border border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-primary" />
                            <span className="font-medium">{u.username}</span>
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => handleRevokeAdmin(u.id)} disabled={adminSaving}
                            className="h-8 px-2 text-destructive hover:text-destructive/90 hover:bg-destructive/10">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No admin users</div>
                    )
                  ) : (
                    filteredNonAdminUsers.length > 0 ? (
                      filteredNonAdminUsers.map(u => (
                        <div key={u.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <span className="font-medium">{u.username}</span>
                          <Button variant="outline" size="sm" onClick={() => handleGrantAdmin(u.id)} disabled={adminSaving}
                            className="h-8 px-3 text-primary border-primary/30 hover:bg-primary/10 hover:border-primary/50">
                            <Plus className="w-4 h-4 mr-1" /> Add
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No users available to promote</div>
                    )
                  )}
                </div>
              </div>

              {/* Groups Column */}
              <div>
                <h4 className="flex items-center gap-2 font-semibold mb-4 text-foreground/80 pb-2 border-b">
                  <UsersRound className="w-4 h-4 text-primary" />
                  Groups
                </h4>
                <div className="space-y-2">
                  {groups.length === 0 ? (
                    <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No SSO groups available</div>
                  ) : adminDialogMode === 'view' ? (
                    filteredAdminGroups.length > 0 ? (
                      filteredAdminGroups.map(g => (
                        <div key={g.id} className="flex items-center justify-between p-3 rounded-lg border border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-primary" />
                            <span className="font-medium">{g.name}</span>
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => handleRevokeAdminGroup(g.id)} disabled={adminSaving}
                            className="h-8 px-2 text-destructive hover:text-destructive/90 hover:bg-destructive/10">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">No admin groups</div>
                    )
                  ) : (
                    filteredNonAdminGroups.length > 0 ? (
                      filteredNonAdminGroups.map(g => (
                        <div key={g.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-surface/30 hover:bg-surface/50 transition-colors">
                          <div className="flex items-center gap-2">
                            <UsersRound className="w-4 h-4 text-muted-foreground" />
                            <span className="font-medium">{g.name}</span>
                          </div>
                          <Button variant="outline" size="sm" onClick={() => handleGrantAdminGroup(g.id)} disabled={adminSaving}
                            className="h-8 px-3 text-primary border-primary/30 hover:bg-primary/10 hover:border-primary/50">
                            <Plus className="w-4 h-4 mr-1" /> Add
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-6 text-sm text-muted-foreground border border-dashed rounded-lg">All groups already have admin access</div>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="p-4 border-t border-border/50 bg-surface/30">
            <Button variant="outline" onClick={() => setAdminDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
