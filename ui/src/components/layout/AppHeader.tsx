import { Button } from "@/components/ui/button";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/auth-context";
import { useEffect, useState } from "react";
import {
  Moon, Sun, Shield, User, Mail, Calendar, LogIn, Tag, Search,
  ChevronLeft, ChevronRight, KeyRound, ExternalLink, Activity, Store, Zap, Eye,
} from "lucide-react";
import { appConfigService, analyticsService } from "@/lib/api-service";
import { GlobalCommandPalette } from "./GlobalCommandPalette";
import { useSidebar } from "@/components/ui/sidebar";
import { useNavigate } from "react-router-dom";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

interface UserStats {
  login_count: number;
  last_login: string | null;
  page_views_30d: number;
  test_runs_total: number;
  marketplace_usage_total: number;
  member_since: string | null;
  recent_activities: Array<{
    action: string;
    type: string;
    time: string;
    status_type: "success" | "warning" | "error";
  }>;
}

export function AppHeader() {
  const { user, logout } = useAuth();
  const { open, toggleSidebar } = useSidebar();
  const navigate = useNavigate();
  const [appConfig, setAppConfig] = useState({ environment: "Production", version: "1.0.0", developer_portal_url: "" });
  const [profileOpen, setProfileOpen] = useState(false);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  useEffect(() => {
    appConfigService.getConfig().then(res => {
      if (res.status === "success" && res.data) {
        setAppConfig({
          environment: res.data.environment,
          version: res.data.version,
          developer_portal_url: res.data.developer_portal_url || "",
        });
      }
    }).catch(() => {});
  }, []);

  // Fetch user stats when profile opens
  useEffect(() => {
    if (!profileOpen || userStats) return;
    setLoadingStats(true);
    analyticsService.getUserStats()
      .then(res => {
        if (res.status === "success" && res.data) setUserStats(res.data);
      })
      .catch(() => {})
      .finally(() => setLoadingStats(false));
  }, [profileOpen]);

  const handleLogout = () => {
    logout();
    window.location.href = "/login";
  };

  const handlePersonalSettings = () => {
    navigate("/settings");
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

  const [paletteOpen, setPaletteOpen] = useState(false);

  const [themeMode, setThemeMode] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("theme");
    return saved === "dark" || saved === "light" ? saved : "light";
  });

  // Apply theme on mount and on change
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(themeMode);
    localStorage.setItem("theme", themeMode);
  }, [themeMode]);

  // Sync theme state when another part of the app changes it (e.g. Settings page)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "theme" && (e.newValue === "light" || e.newValue === "dark")) {
        setThemeMode(e.newValue);
      }
    };
    // Custom event for same-window sync (localStorage events don't fire in same tab)
    const handleThemeChange = (e: Event) => {
      const detail = (e as CustomEvent<"light" | "dark">).detail;
      if (detail === "light" || detail === "dark") {
        setThemeMode(detail);
      }
    };
    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("themechange", handleThemeChange);
    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("themechange", handleThemeChange);
    };
  }, []);

  const toggleTheme = () => {
    const next = themeMode === "light" ? "dark" : "light";
    setThemeMode(next);
    window.dispatchEvent(new CustomEvent("themechange", { detail: next }));
  };

  const statusColors: Record<string, string> = {
    success: "bg-[#00C986]/10 text-[#007a52] border-[#00C986]/30 dark:bg-[#00C986]/15 dark:text-[#00C986] dark:border-[#00C986]/25",
    warning: "bg-[#FFB24C]/10 text-[#935900] border-[#FFB24C]/30 dark:bg-[#FFB24C]/15 dark:text-[#FFB24C] dark:border-[#FFB24C]/25",
    error: "bg-[#F16C6C]/10 text-[#c03232] border-[#F16C6C]/30 dark:bg-[#F16C6C]/15 dark:text-[#F16C6C] dark:border-[#F16C6C]/25",
  };

  return (
    <>
      <header className="h-16 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 sticky top-0 z-50 shadow-sm">
        <div className="flex items-center justify-between h-full px-6">
          {/* Left — sidebar toggle (arrow) */}
          <div className="flex items-center gap-4">
            <TooltipProvider delayDuration={400}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleSidebar}
                    className="h-8 w-8 text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800 focus-visible:ring-0"
                    aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
                  >
                    {open
                      ? <ChevronLeft className="h-5 w-5" />
                      : <ChevronRight className="h-5 w-5" />
                    }
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right" className="text-xs">
                  {open ? "Collapse sidebar" : "Expand sidebar"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Center — command palette trigger */}
          <div className="flex-1 max-w-md mx-8">
            <button
              onClick={() => setPaletteOpen(true)}
              className="w-full flex items-center gap-2 px-3 h-9 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:border-gray-400 dark:hover:border-gray-500 ring-1 ring-transparent hover:ring-gray-200 dark:hover:ring-gray-700 transition-all"
            >
              <Search className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-left">Search across all systems…</span>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-1.5 py-0.5 text-[10px] font-mono text-gray-400 dark:text-gray-500">
                Ctrl K
              </kbd>
            </button>
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
                  onClick={handlePersonalSettings}
                >
                  ⚙️ Personal Settings
                </DropdownMenuItem>

                <DropdownMenuSeparator className="dark:bg-gray-700" />

                <DropdownMenuItem
                  className="cursor-pointer text-[#F16C6C] dark:hover:bg-gray-700"
                  onClick={handleLogout}
                >
                  🚪 Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* ── Command Palette ────────────────────────────────────────────── */}
      <GlobalCommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* ── Profile Dialog ─────────────────────────────────────────────── */}
      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="sm:max-w-lg dark:bg-gray-900 dark:border-gray-700 max-h-[90vh] overflow-y-auto">
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
                  <AvatarFallback className="bg-gradient-primary text-white text-xl font-bold">
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
                      <Badge className="bg-[#F16C6C]/10 text-[#c03232] dark:text-[#F16C6C] border-[#F16C6C]/30 flex items-center gap-1">
                        <Shield className="w-3 h-3" /> Admin
                      </Badge>
                    )}
                    <Badge variant="outline" className="capitalize text-xs">
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

              {/* Quick Links — API Keys & Tokens */}
              {appConfig.developer_portal_url && (
                <div className="rounded-xl border border-border/40 p-4 bg-surface/50 space-y-3">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Developer</p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full justify-start gap-2"
                    onClick={() => window.open(appConfig.developer_portal_url, "_blank", "noopener,noreferrer")}
                  >
                    <KeyRound className="w-4 h-4" />
                    Create API Keys &amp; Token List
                    <ExternalLink className="w-3 h-3 ml-auto opacity-60" />
                  </Button>
                </div>
              )}

              {/* Your Activity Stats */}
              {loadingStats ? (
                <div className="rounded-xl border border-border/40 p-4 bg-surface/50">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Your Activity</p>
                  <div className="grid grid-cols-2 gap-2">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="h-14 rounded-lg bg-surface-elevated/40 animate-pulse" />
                    ))}
                  </div>
                </div>
              ) : userStats && (
                <div className="rounded-xl border border-border/40 p-4 bg-surface/50 space-y-3">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Your Activity</p>
                  <div className="grid grid-cols-2 gap-2">
                    <ActivityStat icon={LogIn} label="Total logins" value={userStats.login_count} />
                    <ActivityStat icon={Eye} label="Pages (30d)" value={userStats.page_views_30d} />
                    <ActivityStat icon={Zap} label="Test runs" value={userStats.test_runs_total} />
                    <ActivityStat icon={Store} label="Marketplace" value={userStats.marketplace_usage_total} />
                  </div>

                  {/* Recent Actions */}
                  {userStats.recent_activities && userStats.recent_activities.length > 0 && (
                    <div className="space-y-2 mt-3">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5" /> Recent Actions
                      </p>
                      <div className="space-y-1.5 max-h-36 overflow-y-auto">
                        {userStats.recent_activities.slice(0, 5).map((activity, index) => (
                          <div
                            key={index}
                            className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-surface-elevated/40 text-xs gap-2"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                activity.status_type === "success" ? "bg-[#00C986]" :
                                activity.status_type === "error" ? "bg-[#F16C6C]" : "bg-[#FFB24C]"
                              }`} />
                              <span className="text-foreground truncate">{activity.action}</span>
                            </div>
                            <Badge
                              variant="outline"
                              className={`text-[10px] shrink-0 ${statusColors[activity.status_type] ?? statusColors.warning}`}
                            >
                              {activity.status_type === "success" ? "Done" : activity.status_type === "error" ? "Failed" : "Running"}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
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

function ActivityStat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 p-3 rounded-lg bg-surface-elevated/40 text-center">
      <Icon className="w-4 h-4 text-primary mb-1" />
      <span className="text-lg font-bold text-foreground">{value}</span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}
