import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Eye, Info, LayoutDashboard, Search, UsersRound } from 'lucide-react';
import { useAuth } from '@/context/auth-context';
import { useConnectionContext } from '@/context/connection-context';
import { analyticsService } from '@/lib/api-service';
import { PermissionsManager } from '@/components/admin/PermissionsManager';
import TableDataPreview from '@/components/admin/TableDataPreview';
import { navigationItems } from '@/components/layout/AppSidebar';

interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
  auth_provider?: string;
  created_at?: string;
  last_login?: string;
  login_count: number;
  preferences: Record<string, any>;
}

interface UserDialogState {
  open: boolean;
  type: 'password' | 'delete' | 'create' | 'viewTable' | null;
  user: User | null;
}

// Custom fetchApi function for this component
const fetchApi = async (endpoint: string, options: RequestInit = {}) => {
  try {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${endpoint}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      return { status: 'error', error: data.message || `HTTP error! status: ${response.status}` };
    }
    
    return { status: 'success', data };
  } catch (error) {
    return { status: 'error', error: error instanceof Error ? error.message : 'Network error' };
  }
};

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState<UserDialogState>({ open: false, type: null, user: null });
  const [newPassword, setNewPassword] = useState('');
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '', full_name: '' });
  const [actionLoading, setActionLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const { user: currentUser } = useAuth();
  const { currentConnection } = useConnectionContext();

  // Active session tracking: user IDs with a live, non-expired JWT
  const [activeSessionUserIds, setActiveSessionUserIds] = useState<Set<number>>(new Set());

  // Database tables state
  const [tables, setTables] = useState<string[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  // Internal DB only (BI toggle removed per requirements)

  // Groups tab state
  interface Group { id: number; name: string; }
  interface TabPermissions { [tab: string]: { users: number[]; groups: number[] }; }
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupPermissions, setGroupPermissions] = useState<TabPermissions>({});
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupsError, setGroupsError] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [groupSearch, setGroupSearch] = useState('');
  const [groupsFetched, setGroupsFetched] = useState(false);

  const getTabDisplayName = (title: string) =>
    navigationItems.find(n => n.title === title)?.displayLabel ?? title;

  const fetchGroupsData = async () => {
    if (groupsFetched) return;
    setGroupsLoading(true);
    setGroupsError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const headers = { Authorization: `Bearer ${token}` };
      const [gRes, pRes] = await Promise.all([
        fetch('/api/sso/groups', { headers }),
        fetch('/api/permissions', { headers }),
      ]);
      const gData = gRes.ok ? await gRes.json() : { groups: [] };
      const pData = pRes.ok ? await pRes.json() : { status: 'error', data: {} };
      setGroups(gData.groups || []);
      setGroupPermissions(pData.status === 'success' ? pData.data : {});
      setGroupsFetched(true);
    } catch {
      setGroupsError('Failed to load groups data.');
    } finally {
      setGroupsLoading(false);
    }
  };

  // Tabs granted to a given group
  const tabsForGroup = (groupId: number): string[] =>
    Object.entries(groupPermissions)
      .filter(([, perms]) => perms.groups?.includes(groupId))
      .map(([tab]) => tab)
      .sort();

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await fetchApi('/api/users');
      
      if (response.status === 'success' && response.data) {
        // Unwrap possible nesting: {status:'success', data:{users:[...]}}
        const raw = response.data as any;
        const usersArray = Array.isArray(raw) ? raw : Array.isArray(raw.users) ? raw.users : Array.isArray(raw.data?.users) ? raw.data.users : [];
        if (!usersArray.length) {
          console.warn('Unexpected users data format:', raw);
        }
        setUsers(usersArray);
        setError('');
      } else {
        setError(response.error || 'Failed to fetch users');
        setUsers([]);
      }
    } catch (err) {
      setError('An error occurred while fetching users.');
      setUsers([]);
      console.error('Fetch users error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveSessionIds = async () => {
    try {
      const res = await analyticsService.getActiveSessionUserIds();
      if (res.status === 'success' && res.data) {
        setActiveSessionUserIds(new Set(res.data.user_ids));
      }
    } catch {
      // Non-critical — silently ignore; the Online indicator just won't show
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchActiveSessionIds();
    // Refresh active sessions every 60 seconds
    const interval = setInterval(fetchActiveSessionIds, 60000);
    return () => clearInterval(interval);
  }, []);

  const handlePasswordChange = async () => {
    if (!dialog.user || !newPassword.trim()) return;

    try {
      setActionLoading(true);
      const response = await fetchApi(`/api/users/${dialog.user.id}/password`, {
        method: 'PUT',
        body: JSON.stringify({ new_password: newPassword }),
      });

      if (response.status === 'success') {
        setDialog({ open: false, type: null, user: null });
        setNewPassword('');
        // Optionally refresh users list
        await fetchUsers();
      } else {
        setError(response.error || 'Failed to change password');
      }
    } catch (err) {
      setError('An error occurred while changing password.');
      console.error('Password change error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!dialog.user) return;

    try {
      setActionLoading(true);
      const response = await fetchApi(`/api/users/${dialog.user.id}`, {
        method: 'DELETE',
      });

      if (response.status === 'success') {
        setDialog({ open: false, type: null, user: null });
        // Remove user from local state
        setUsers(users.filter(u => u.id !== dialog.user!.id));
      } else {
        setError(response.error || 'Failed to delete user');
      }
    } catch (err) {
      setError('An error occurred while deleting user.');
      console.error('Delete user error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUser.username || !newUser.password) return;
    try {
      setActionLoading(true);
      const response = await fetchApi('/api/users', {
        method: 'POST',
        body: JSON.stringify(newUser),
      });
      if (response.status === 'success') {
        setDialog({ open: false, type: null, user: null });
        setNewUser({ username: '', email: '', password: '', full_name: '' });
        await fetchUsers();
      } else {
        setError(response.error || 'Failed to create user');
      }
    } catch (err) {
      setError('An error occurred while creating user.');
    } finally {
      setActionLoading(false);
    }
  };

  // Function to fetch database tables
  const fetchTables = async () => {
    try {
      setTablesLoading(true);
      setTablesError(null);
      const resp = await fetchApi('/api/internal/list-tables');
      if (resp.status === 'success' && resp.data) {
        const raw = resp.data as any;
        setTables(Array.isArray(raw) ? raw : raw.tables || raw.data || []);
      } else {
        setTablesError(resp.error || 'Failed to fetch internal tables');
      }
    } catch (err) {
      setTablesError('An error occurred while fetching tables.');
      console.error('Fetch tables error:', err);
    } finally {
      setTablesLoading(false);
    }
  };

  const openDialog = (type: UserDialogState['type'], user: User | null) => {
    setDialog({ open: true, type, user });
    setError('');
  };

  const closeDialog = () => {
    setDialog({ open: false, type: null, user: null });
    setNewPassword('');
    setError('');
  };

  if (loading) {
    return (
      <div className="p-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              <span className="ml-2">Loading users...</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-2xl font-bold gradient-text">Administration</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage users, permissions, and system data.</p>
      </div>
      <Tabs defaultValue="users" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="users" className="data-[state=active]:bg-gradient-primary data-[state=active]:text-white">User Management</TabsTrigger>
          <TabsTrigger value="permissions" className="data-[state=active]:bg-gradient-primary data-[state=active]:text-white">Permissions</TabsTrigger>
          <TabsTrigger value="groups" className="data-[state=active]:bg-gradient-primary data-[state=active]:text-white" onClick={fetchGroupsData}>Groups</TabsTrigger>
          <TabsTrigger value="tables" className="data-[state=active]:bg-gradient-primary data-[state=active]:text-white">Database Tables</TabsTrigger>
        </TabsList>
        
        <TabsContent value="users">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span>User Management</span>
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-800">
                  {users?.length || 0} total
                </span>
              </CardTitle>
            </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <span>⚠️</span>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          
          <div className="flex justify-between mb-4">
            <Input
              placeholder="Filter users..."
              className="max-w-xs h-8"
              value={filter}
              onChange={(e)=>setFilter(e.target.value)}
            />
            <Button size="sm" onClick={() => openDialog('create', null)}>➕ Create User</Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Full Name</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Session</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Login Count</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users && users.length > 0 ? users
                .filter(u => !filter || u.username.toLowerCase().includes(filter.toLowerCase()) || (u.email||'').toLowerCase().includes(filter.toLowerCase()))
                .map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-mono">{user.id}</TableCell>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>{user.email || '-'}</TableCell>
                  <TableCell>{user.full_name || '-'}</TableCell>
                  <TableCell>
                    {/* Account enabled/disabled flag — not the same as "currently online" */}
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                      {user.is_active ? 'Enabled' : 'Disabled'}
                    </span>
                  </TableCell>
                  <TableCell>
                    {/* Real-time session indicator: green = has a live JWT, gray = no active token */}
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs cursor-default ${activeSessionUserIds.has(user.id) ? 'bg-[#00C986]/10 text-[#007a52] dark:text-[#00C986]' : 'bg-muted/60 text-muted-foreground'}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${activeSessionUserIds.has(user.id) ? 'bg-[#00C986] animate-pulse' : 'bg-muted-foreground/40'}`} />
                            {activeSessionUserIds.has(user.id) ? 'Online' : 'Offline'}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs max-w-[200px] text-center">
                          {activeSessionUserIds.has(user.id)
                            ? 'User has an active, non-expired login session right now.'
                            : 'No active session — user is not currently logged in.'}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </TableCell>
                  <TableCell>
                    {/* Account type: SSO (via LDAP/Authentik) vs System (local account) */}
                    <TooltipProvider delayDuration={200}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs cursor-default ${
                            user.auth_provider === 'sso'
                              ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300'
                              : 'bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300'
                          }`}>
                            {user.auth_provider === 'sso' ? 'SSO' : 'System'}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs max-w-[200px] text-center">
                          {user.auth_provider === 'sso'
                            ? 'SSO user — authenticated via Authentik/LDAP'
                            : 'System user — local account managed in this portal'}
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${user.is_admin ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}>
                      {user.is_admin ? 'Admin' : 'User'}
                    </span>
                  </TableCell>
                  <TableCell>
                    {user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}
                  </TableCell>
                  <TableCell>{user.login_count || 0}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {user.auth_provider !== 'sso' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDialog('password', user)}
                          className="h-8 px-2"
                          title="Change password"
                        >
                          🔑 Change Password
                        </Button>
                      )}
                      {!user.is_admin && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDialog('delete', user)}
                          className="h-8 px-2 text-red-600 hover:text-red-700"
                        >
                          🗑️ Delete
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-8">
                    {loading ? 'Loading users...' : 'No users found'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      </TabsContent>

      <TabsContent value="permissions">
        <PermissionsManager />
      </TabsContent>

      <TabsContent value="groups">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UsersRound className="w-5 h-5 text-indigo-400" />
              <span>Groups</span>
              {groups.length > 0 && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-800 dark:bg-indigo-500/20 dark:text-indigo-300">
                  {groups.length} total
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Read-only notice */}
            <div className="flex items-start gap-3 rounded-lg border border-border/50 bg-muted/30 px-4 py-3 mb-5">
              <Info className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
              <p className="text-sm text-muted-foreground leading-relaxed">
                This view is <strong className="text-foreground/80">read-only</strong>. It shows which portal tabs each SSO group has been granted access to.
                To add or remove permissions, go to the <strong className="text-foreground/80">Permissions</strong> tab.
              </p>
            </div>

            {groupsError && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{groupsError}</AlertDescription>
              </Alert>
            )}

            {groupsLoading ? (
              <div className="flex items-center justify-center p-10">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                <span className="ml-3 text-muted-foreground">Loading groups…</span>
              </div>
            ) : groups.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground text-sm border border-dashed rounded-lg">
                No SSO groups found. Groups are synced from your identity provider (Authentik / LDAP).
              </div>
            ) : (
              <>
                <div className="relative max-w-xs mb-4">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Filter groups…"
                    className="pl-9 h-9"
                    value={groupSearch}
                    onChange={e => setGroupSearch(e.target.value)}
                  />
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Group Name</TableHead>
                      <TableHead>Tabs Granted</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {groups
                      .filter(g => !groupSearch || g.name.toLowerCase().includes(groupSearch.toLowerCase()))
                      .map(group => {
                        const count = tabsForGroup(group.id).length;
                        return (
                          <TableRow key={group.id}>
                            <TableCell className="font-medium flex items-center gap-2">
                              <UsersRound className="w-4 h-4 text-indigo-400 shrink-0" />
                              {group.name}
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary" className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20">
                                {count} {count === 1 ? 'tab' : 'tabs'}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-8 gap-1.5"
                                onClick={() => setSelectedGroup(group)}
                              >
                                <Eye className="w-3.5 h-3.5" />
                                View Tabs
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                  </TableBody>
                </Table>
              </>
            )}
          </CardContent>
        </Card>

        {/* Group tab-access dialog */}
        <Dialog open={!!selectedGroup} onOpenChange={open => !open && setSelectedGroup(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <UsersRound className="w-5 h-5 text-indigo-400" />
                {selectedGroup?.name}
              </DialogTitle>
              <DialogDescription>
                Portal tabs this group has been granted access to.
              </DialogDescription>
            </DialogHeader>

            {/* Read-only banner inside dialog */}
            <div className="flex items-start gap-2.5 rounded-lg border border-border/50 bg-muted/30 px-3 py-2.5 text-sm text-muted-foreground">
              <Info className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                Read-only view. To change permissions, use the <strong className="text-foreground/80">Permissions</strong> tab.
              </span>
            </div>

            <div className="mt-2">
              {selectedGroup && tabsForGroup(selectedGroup.id).length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground border border-dashed rounded-lg">
                  No tabs have been granted to this group yet.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {selectedGroup && tabsForGroup(selectedGroup.id).map(tab => (
                    <div
                      key={tab}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-border/50 bg-surface/30"
                    >
                      <LayoutDashboard className="w-4 h-4 text-muted-foreground shrink-0" />
                      <span className="text-sm font-medium">{getTabDisplayName(tab)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setSelectedGroup(null)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </TabsContent>

      <TabsContent value="tables">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span>Internal Database Tables</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <Button onClick={fetchTables} disabled={tablesLoading}>
                  {tablesLoading ? 'Loading...' : 'Refresh Tables'}
                </Button>
                {tables.length > 0 && (
                  <span className="text-sm text-muted-foreground">
                    {tables.length} tables found
                  </span>
                )}
              </div>

              {tablesError && (
                <Alert variant="destructive">
                  <AlertDescription>{tablesError}</AlertDescription>
                </Alert>
              )}

              {tablesLoading ? (
                <div className="flex items-center justify-center p-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  <span className="ml-2">Loading tables...</span>
                </div>
              ) : tables.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Table Name</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tables.map((table, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium cursor-pointer" onClick={() => openDialog('viewTable', { id: 0, username: table, email: '', is_active: true, is_admin: false, login_count: 0, preferences: {} })}>{table}</TableCell>
                        <TableCell>
                          <Button variant="outline" size="sm" onClick={() => openDialog('viewTable', { id: 0, username: table, email: '', is_active: true, is_admin: false, login_count: 0, preferences: {} })}>
                            View Data
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : !tablesLoading && (
                <div className="text-center py-8 text-muted-foreground">
                  No tables found. Click "Refresh Tables" to load tables from the internal database.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </TabsContent>
      </Tabs>

      {/* Create User Dialog */}
      <Dialog open={dialog.open && dialog.type === 'create'} onOpenChange={closeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Username</Label>
              <Input value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label>Email</Label>
              <Input value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label>Full Name</Label>
              <Input value={newUser.full_name} onChange={e => setNewUser({ ...newUser, full_name: e.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label>Password</Label>
              <Input type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>Cancel</Button>
            <Button onClick={handleCreateUser} disabled={!newUser.username || !newUser.password || (newUser.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(newUser.email)) || actionLoading}>{actionLoading ? 'Creating...' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Password Change Dialog */}
      <Dialog open={dialog.open && dialog.type === 'password'} onOpenChange={closeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>
              Change password for user: <strong>{dialog.user?.username}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button 
              onClick={handlePasswordChange}
              disabled={!newPassword.trim() || actionLoading}
            >
              {actionLoading ? 'Changing...' : 'Change Password'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

  {/* Delete User Dialog */}
      <Dialog open={dialog.open && dialog.type === 'delete'} onOpenChange={closeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete user <strong>{dialog.user?.username}</strong>? 
              This action cannot be undone and will remove all associated data.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={handleDeleteUser}
              disabled={actionLoading}
            >
              {actionLoading ? 'Deleting...' : 'Delete User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Table Data Dialog */}
    <Dialog open={dialog.open && dialog.type === 'viewTable'} onOpenChange={closeDialog}>
        <DialogContent className="max-w-[95vw] w-[95vw] h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Table: {dialog.user?.username}</DialogTitle>
            <DialogDescription>Internal table preview with pagination (100 rows per page).</DialogDescription>
          </DialogHeader>
      <div className="flex-1 min-h-0 overflow-auto">
        <TableDataPreview 
          tableName={dialog.user?.username || ''} 
          connectionActive={!!currentConnection} 
          internalMode={true}
          internalShowAll={false}
          pageSize={100}
          maxHeightClass=""
        />
      </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersPage;
