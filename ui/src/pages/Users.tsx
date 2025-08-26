import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

interface User {
  id: number;
  username: string;
  creation_date: string;
  last_login: string;
  login_count: number;
}

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          setError('No token found');
          return;
        }
        const response = await fetch('/api/users', {
          headers: {
            'x-access-token': token,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setUsers(data.users);
        } else {
          const data = await response.json();
          setError(data.message || 'Failed to fetch users');
        }
      } catch (err) {
        setError('An error occurred while fetching users.');
      }
    };

    fetchUsers();
  }, []);

  return (
    <div className="p-4">
      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="text-red-500">{error}</p>}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Creation Date</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Login Count</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.id}</TableCell>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>{new Date(user.creation_date).toLocaleString()}</TableCell>
                  <TableCell>{user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</TableCell>
                  <TableCell>{user.login_count}</TableCell>
                  <TableCell>
                    {user.username === 'admin' ? <Badge>Admin</Badge> : <Badge variant="secondary">User</Badge>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

export default UsersPage;
