import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/context/auth-context';
import { useConnectionContext } from '@/context/connection-context';
import { dbService } from '@/lib/api-service';
import TableDataPreview from '@/components/admin/TableDataPreview';

interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_admin: boolean;
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

  // Database tables state
  const [tables, setTables] = useState<string[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  // Internal DB only (BI toggle removed per requirements)

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

  useEffect(() => {
    fetchUsers();
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
      <Tabs defaultValue="users" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="users">User Management</TabsTrigger>
          <TabsTrigger value="tables">Database Tables</TabsTrigger>
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
            {currentUser?.is_admin && (
              <Button size="sm" onClick={() => openDialog('create', null)}>➕ Create User</Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Full Name</TableHead>
                <TableHead>Status</TableHead>
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
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
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
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openDialog('password', user)}
                        className="h-8 px-2"
                      >
                        🔑 Change
                      </Button>
                      {!user.is_admin && currentUser?.is_admin && (
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
                  <TableCell colSpan={9} className="text-center py-8">
                    {loading ? 'Loading users...' : 'No users found'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
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
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Table: {dialog.user?.username}</DialogTitle>
            <DialogDescription>First rows of the selected table.</DialogDescription>
          </DialogHeader>
      {/* Table rows preview with pagination */}
  <TableDataPreview tableName={dialog.user?.username || ''} connectionActive={!!currentConnection} internalMode={true} />
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersPage;
