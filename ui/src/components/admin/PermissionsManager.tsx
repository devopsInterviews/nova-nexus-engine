import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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
      if (pData.status === 'success') setPermissions(pData.data);

      // Fetch users
      const uRes = await fetch('/api/users', { headers });
      const uData = await uRes.json();
      setUsers(uData);

      // Fetch groups (assuming an endpoint exists or we can just mock for now)
      // Ideally we should have an endpoint for /api/groups
      // For now we'll just leave groups empty if the endpoint doesn't exist
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
      
      if (!res.ok) throw new Error("Failed to save");
      alert("Permissions saved successfully!");
    } catch (err) {
      console.error(err);
      alert("Failed to save permissions");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div>Loading permissions...</div>;

  const tabs = Object.keys(permissions);

  return (
    <Card className="glass border-0">
      <CardHeader>
        <CardTitle>Tab Permissions Matrix</CardTitle>
        <CardDescription>
          Assign which users and groups can see specific tabs in the sidebar.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-surface/50 border-b">
              <tr>
                <th className="px-4 py-3">Tab</th>
                <th className="px-4 py-3">Allowed Users</th>
                {groups.length > 0 && <th className="px-4 py-3">Allowed Groups</th>}
              </tr>
            </thead>
            <tbody>
              {tabs.map(tab => (
                <tr key={tab} className="border-b bg-surface/20 hover:bg-surface/50">
                  <td className="px-4 py-3 font-medium">{tab}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {users.filter(u => u.username !== 'admin').map(user => (
                        <label key={user.id} className="flex items-center space-x-1 cursor-pointer">
                          <input 
                            type="checkbox"
                            checked={permissions[tab]?.users?.includes(user.id) || false}
                            onChange={() => handleUserToggle(tab, user.id)}
                            className="rounded border-gray-300"
                          />
                          <span>{user.username}</span>
                        </label>
                      ))}
                    </div>
                  </td>
                  {groups.length > 0 && (
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {groups.map(group => (
                          <label key={group.id} className="flex items-center space-x-1 cursor-pointer">
                            <input 
                              type="checkbox"
                              checked={permissions[tab]?.groups?.includes(group.id) || false}
                              onChange={() => handleGroupToggle(tab, group.id)}
                              className="rounded border-gray-300"
                            />
                            <span>{group.name}</span>
                          </label>
                        ))}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={savePermissions} disabled={saving}>
            {saving ? "Saving..." : "Save Permissions"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}