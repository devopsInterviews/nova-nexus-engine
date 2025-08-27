import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/context/auth-context';

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
  type: 'password' | 'delete' | null;
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
  const [actionLoading, setActionLoading] = useState(false);
  const { user: currentUser } = useAuth();

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await fetchApi('/api/users');
      
      if (response.status === 'success' && response.data) {
        setUsers(response.data.users);
        setError('');
      } else {
        setError(response.error || 'Failed to fetch users');
      }
    } catch (err) {
      setError('An error occurred while fetching users.');
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

  const openDialog = (type: 'password' | 'delete', user: User) => {
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
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span>User Management</span>
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-800">
              {users.length} total
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
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-mono">{user.id}</TableCell>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>{user.email}</TableCell>
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
                  <TableCell>{user.login_count}</TableCell>
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
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

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
    </div>
  );
};

export default UsersPage;
