/**
 * GlobalCommandPalette
 *
 * A keyboard-driven command palette that searches across:
 *   - Navigation pages (filtered by the user's tab access)
 *   - Marketplace items (Agents & MCP Servers)
 *   - Users (admin only)
 *
 * Opens on Ctrl+K or when the user clicks the header search bar.
 * Navigates to the selected result and closes automatically.
 */

import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/auth-context";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import {
  Home,
  Database,
  Activity,
  CheckSquare,
  Search,
  Store,
  Users,
  Settings,
  Cpu,
  Bot,
  Server,
  User,
} from "lucide-react";
import { navigationItems } from "./AppSidebar";

// ─── Minimal fetch helper (auth token from localStorage) ─────────────────────

async function authFetch(path: string) {
  const token = localStorage.getItem("auth_token");
  const base =
    (import.meta as any).env?.VITE_API_BASE_URL ||
    window.location.origin.replace(/:\d+$/, ":8000");
  const res = await fetch(`${base}${path}`, {
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─── Icon map for navigation items ───────────────────────────────────────────

const NAV_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Home, DevOps: Cpu, BI: Database, Analytics: Activity,
  Tests: CheckSquare, Research: Search, Marketplace: Store,
  Users, Settings,
};

// Display labels for navigation items (maps internal title → display label)
const NAV_LABELS: Record<string, string> = {
  Users: "Administration",
};

// ─── Types ────────────────────────────────────────────────────────────────────

interface MarketplaceItem {
  id: number;
  name: string;
  description: string;
  item_type: "agent" | "mcp_server";
}

interface PortalUser {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_admin: boolean;
}

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GlobalCommandPalette({ open, onOpenChange }: Props) {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [marketplaceItems, setMarketplaceItems] = useState<MarketplaceItem[]>([]);
  const [users, setUsers] = useState<PortalUser[]>([]);
  const [loadingMarketplace, setLoadingMarketplace] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Lazy-load marketplace items and users once the palette opens for the first time.
  useEffect(() => {
    if (!open) return;

    if (marketplaceItems.length === 0 && !loadingMarketplace) {
      setLoadingMarketplace(true);
      authFetch("/api/marketplace/items")
        .then((data) => {
          const items: MarketplaceItem[] = Array.isArray(data)
            ? data
            : data.items ?? [];
          setMarketplaceItems(items);
        })
        .catch(() => {})
        .finally(() => setLoadingMarketplace(false));
    }

    if (user?.is_admin && users.length === 0 && !loadingUsers) {
      setLoadingUsers(true);
      authFetch("/api/users")
        .then((data) => {
          const raw = Array.isArray(data) ? data : data.users ?? data.data?.users ?? [];
          setUsers(raw);
        })
        .catch(() => {})
        .finally(() => setLoadingUsers(false));
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onOpenChange]);

  const go = useCallback(
    (url: string) => {
      onOpenChange(false);
      navigate(url);
    },
    [navigate, onOpenChange]
  );

  // Pages accessible to this user (same logic as AppSidebar)
  const allowedNavItems = navigationItems.filter((item) => {
    if (user?.is_admin) return true;
    if (item.adminOnly) return false;
    if (user?.allowed_tabs && !user.allowed_tabs.includes(item.title)) return false;
    return true;
  });

  const agents = marketplaceItems.filter((i) => i.item_type === "agent");
  const mcpServers = marketplaceItems.filter((i) => i.item_type === "mcp_server");

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search pages, agents, MCP servers, users…" />

      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        {/* ── Navigation ─────────────────────────────────────────────────── */}
        <CommandGroup heading="Navigation">
          {allowedNavItems.map((item) => {
            const Icon = NAV_ICONS[item.title] ?? Home;
            const label = NAV_LABELS[item.title] ?? item.title;
            return (
              <CommandItem
                key={item.url}
                value={`${item.title} ${label}`}
                onSelect={() => go(item.url)}
                className="cursor-pointer"
              >
                <Icon className="mr-2 h-4 w-4 text-muted-foreground" />
                <span>{label}</span>
                {item.url === "/" ? (
                  <CommandShortcut>Home</CommandShortcut>
                ) : null}
              </CommandItem>
            );
          })}
        </CommandGroup>

        {/* ── Marketplace — Agents ────────────────────────────────────────── */}
        {(agents.length > 0 || loadingMarketplace) && (
          <>
            <CommandSeparator />
            <CommandGroup heading={loadingMarketplace ? "AI Agents (loading…)" : "AI Agents"}>
              {agents.map((item) => (
                <CommandItem
                  key={`agent-${item.id}`}
                  value={`agent ${item.name} ${item.description}`}
                  onSelect={() => go(`/marketplace?itemId=${item.id}`)}
                  className="cursor-pointer"
                >
                  <Bot className="mr-2 h-4 w-4 text-secondary shrink-0" />
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{item.name}</span>
                    {item.description && (
                      <span className="text-xs text-muted-foreground truncate">
                        {item.description}
                      </span>
                    )}
                  </div>
                  <CommandShortcut className="text-secondary shrink-0">Agent</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {/* ── Marketplace — MCP Servers ───────────────────────────────────── */}
        {(mcpServers.length > 0 || loadingMarketplace) && (
          <>
            <CommandSeparator />
            <CommandGroup heading={loadingMarketplace ? "MCP Servers (loading…)" : "MCP Servers"}>
              {mcpServers.map((item) => (
                <CommandItem
                  key={`mcp-${item.id}`}
                  value={`mcp server ${item.name} ${item.description}`}
                  onSelect={() => go(`/marketplace?itemId=${item.id}`)}
                  className="cursor-pointer"
                >
                  <Server className="mr-2 h-4 w-4 text-blue-500 shrink-0" />
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{item.name}</span>
                    {item.description && (
                      <span className="text-xs text-muted-foreground truncate">
                        {item.description}
                      </span>
                    )}
                  </div>
                  <CommandShortcut className="text-blue-400 shrink-0">MCP</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {/* ── Users / Administration (admin only) ────────────────────────── */}
        {user?.is_admin && (users.length > 0 || loadingUsers) && (
          <>
            <CommandSeparator />
            <CommandGroup heading={loadingUsers ? "Administration (loading…)" : "Administration"}>
              {users.map((u) => (
                <CommandItem
                  key={`user-${u.id}`}
                  value={`user ${u.username} ${u.email} ${u.full_name ?? ""}`}
                  onSelect={() => go("/users")}
                  className="cursor-pointer"
                >
                  <User className="mr-2 h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{u.full_name || u.username}</span>
                    <span className="text-xs text-muted-foreground truncate">
                      @{u.username} · {u.email || "no email"}
                    </span>
                  </div>
                  {u.is_admin && (
                    <CommandShortcut className="text-[#F16C6C] shrink-0">Admin</CommandShortcut>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
