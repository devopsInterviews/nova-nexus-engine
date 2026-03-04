import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/auth-context";
import { useEffect, useState } from "react";
import { Moon, Sun, Shield, User, Mail, Calendar, LogIn, Tag } from "lucide-react";
import { appConfigService } from "@/lib/api-service";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function AppHeader() {
  const { user, logout } = useAuth();
  const [appConfig, setAppConfig] = useState({ environment: "Production", version: "1.0.0" });
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    appConfigService.getConfig().then(res => {
      if (res.status === "success" && res.data) {
        setAppConfig({ environment: res.data.environment, version: res.data.version });
      }
    }).catch(() => {});
  }, []);

  const handleLogout = () => {
    logout();
    window.location.href = "/login";
  };

  const handleSettings = () => {
    window.location.href = "/settings";
  };

  const getUserInitials = () => {
    if (!user) return "U";
    if (user.full_name) {
      const names = user.full_name.split(" ");
      return names.length > 1
        ? `${names[0][0]}${names[1][0]}`.toUpperCase()
        : names[0][0].toUpperCase();
    }
    return user.username.substring(0, 2).toUpperCase();
  };

  const [themeMode, setThemeMode] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("theme");
    return saved === "dark" || saved === "light" ? saved : "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(themeMode);
    localStorage.setItem("theme", themeMode);
  }, [themeMode]);

  const toggleTheme = () => setThemeMode(prev => (prev === "light" ? "dark" : "light"));

  return (
    <>
      <header className="h-16 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 sticky top-0 z-50 shadow-sm">
        <div className="flex items-center justify-between h-full px-6">
          {/* Left — sidebar trigger + env badges */}
          <div className="flex items-center gap-4">
            <SidebarTrigger />
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                {appConfig.environment.toUpperCase()}
              </span>
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
                v{appConfig.version}
              </span>
            </div>
          </div>

          {/* Center — search */}
          <div className="flex-1 max-w-md mx-8">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500">🔍</span>
              <Input
                placeholder="Search across all systems..."
                className="pl-10 dark:bg-gray-800 dark:border-gray-600 dark:text-white dark:placeholder-gray-400"
              />
            </div>
          </div>

          {/* Right — theme toggle + user menu */}
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="dark:text-gray-200 dark:hover:bg-gray-800"
            >
              {themeMode === "light" ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full dark:hover:bg-gray-800">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-blue-600 text-white font-semibold text-sm">
                      {getUserInitials()}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>

              <DropdownMenuContent className="w-56 dark:bg-gray-800 dark:border-gray-700" align="end">
                <div className="flex items-center gap-2 p-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-blue-600 text-white font-semibold text-sm">
                      {getUserInitials()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col leading-none">
                    <p className="font-medium text-sm dark:text-white truncate max-w-[140px]">
                      {user?.full_name || user?.username || "User"}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[140px]">
                      {user?.email || "No email"}
                    </p>
                  </div>
                </div>

                <DropdownMenuSeparator className="dark:bg-gray-700" />

                <DropdownMenuItem
                  className="cursor-pointer dark:text-gray-200 dark:hover:bg-gray-700"
                  onClick={() => setProfileOpen(true)}
                >
                  👤 Profile
                </DropdownMenuItem>

                <DropdownMenuItem
                  className="cursor-pointer dark:text-gray-200 dark:hover:bg-gray-700"
                  onClick={handleSettings}
                >
                  ⚙️ Settings
                </DropdownMenuItem>

                <DropdownMenuSeparator className="dark:bg-gray-700" />

                <DropdownMenuItem
                  className="cursor-pointer text-red-600 dark:text-red-400 dark:hover:bg-gray-700"
                  onClick={handleLogout}
                >
                  🚪 Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* ── Profile Dialog ─────────────────────────────────────────────── */}
      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="sm:max-w-md dark:bg-gray-900 dark:border-gray-700">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <User className="w-5 h-5 text-primary" />
              My Profile
            </DialogTitle>
          </DialogHeader>

          {user && (
            <div className="space-y-5 pt-1">
              {/* Avatar + name row */}
              <div className="flex items-center gap-4">
                <Avatar className="h-16 w-16">
                  <AvatarFallback className="bg-blue-600 text-white text-xl font-bold">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-xl font-bold text-foreground leading-tight">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-sm text-muted-foreground">@{user.username}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {user.is_admin && (
                      <Badge className="bg-red-500/10 text-red-500 border-red-500/30 flex items-center gap-1">
                        <Shield className="w-3 h-3" /> Admin
                      </Badge>
                    )}
                    <Badge
                      variant="outline"
                      className="capitalize text-xs"
                    >
                      {user.auth_provider || "local"}
                    </Badge>
                  </div>
                </div>
              </div>

              {/* Detail rows */}
              <div className="space-y-3 rounded-xl border border-border/40 p-4 bg-surface/50">
                <ProfileRow icon={Mail} label="Email" value={user.email || "—"} />
                <ProfileRow icon={Calendar} label="Member since" value={formatDate(user.created_at)} />
                <ProfileRow icon={LogIn} label="Last login" value={formatDate(user.last_login)} />
                <ProfileRow icon={LogIn} label="Total logins" value={String(user.login_count ?? 0)} />
                {user.allowed_tabs && user.allowed_tabs.length > 0 && (
                  <div className="flex items-start gap-3 pt-1">
                    <Tag className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-muted-foreground mb-1.5">Access</p>
                      <div className="flex flex-wrap gap-1.5">
                        {user.allowed_tabs.map(tab => (
                          <Badge key={tab} variant="outline" className="text-xs">
                            {tab}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function ProfileRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
      <div className="flex items-center justify-between w-full gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-sm font-medium text-foreground text-right">{value}</span>
      </div>
    </div>
  );
}
