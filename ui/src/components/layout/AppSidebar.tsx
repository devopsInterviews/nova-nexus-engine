import { NavLink, useLocation } from "react-router-dom";
import { 
  Home, 
  Activity, 
  Database,
  Cpu,
  Zap,
  CheckSquare,
  Users,
  Search,
  Store,
  Shield
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useAuth } from "@/context/auth-context";
import { useEffect, useState } from "react";
import { appConfigService } from "@/lib/api-service";

export type NavigationItem = {
  title: string;      // Internal key (used for tab permission checks)
  displayLabel?: string; // Optional display label shown in the UI
  url: string;
  icon: any;
  adminOnly?: boolean;
};

export const navigationItems: NavigationItem[] = [
  {
    title: "Home",
    url: "/",
    icon: Home,
  },
  {
    title: "DevOps",
    url: "/devops",
    icon: Cpu,
  },
  {
    title: "BI",
    url: "/bi",
    icon: Database,
  },
  {
    title: "Analytics",
    url: "/analytics", 
    icon: Activity,
  },
  {
    title: "Tests",
    url: "/tests",
    icon: CheckSquare,
  },
  {
    title: "Research",
    url: "/research",
    icon: Search,
  },
  {
    title: "Marketplace",
    url: "/marketplace",
    icon: Store,
  },
  {
    title: "Users",
    displayLabel: "Administration",
    url: "/users",
    icon: Users,
  },
  // Settings intentionally excluded — accessible via the profile menu only
];

// ─── COMPANY LOGO ────────────────────────────────────────────────────────────
// To use your own logo: place your image file in ui/public/ (e.g. logo.png)
// then change COMPANY_LOGO_SRC below to "/logo.png" (or whatever filename).
// Set it to null to keep the built-in SVG placeholder.
const COMPANY_LOGO_SRC: string | null = `${import.meta.env.BASE_URL}logo.png`;

function CompanyLogo({ size = 32 }: { size?: number }) {
  if (COMPANY_LOGO_SRC) {
    return (
      <img
        src={COMPANY_LOGO_SRC}
        alt="Company Logo"
        width={size}
        height={size}
        style={{ width: size, height: size, objectFit: "contain", borderRadius: 6 }}
      />
    );
  }

  // SVG placeholder — shown until COMPANY_LOGO_SRC is set
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Company Logo"
    >
      <rect width="32" height="32" rx="8" fill="url(#logoGrad)" />
      <path
        d="M8 22V10l6 8 6-8v12"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="16" r="3" fill="white" opacity="0.85" />
      <defs>
        <linearGradient id="logoGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function AppSidebar() {
  const { open } = useSidebar();
  const location = useLocation();
  const { user } = useAuth();
  const [appConfig, setAppConfig] = useState({ environment: "Production", version: "1.0.0" });

  useEffect(() => {
    appConfigService.getConfig().then(res => {
      if (res.status === "success" && res.data) {
        setAppConfig({ environment: res.data.environment, version: res.data.version });
      }
    }).catch(() => {});
  }, []);

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <Sidebar
      collapsible="icon"
      className="border-r-0 bg-surface/80 glass transition-all duration-smooth"
    >
      <SidebarContent className={cn("flex flex-col h-full", open ? "p-4" : "p-2")}>
        {/* Logo */}
        <div className={cn("flex items-center gap-3 mb-8", open ? "px-2" : "justify-center px-0")}>
          <motion.div 
            className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center shrink-0"
            whileHover={{ scale: 1.1, rotate: 5 }}
            transition={{ type: "spring", stiffness: 400, damping: 10 }}
          >
            <Zap className="w-5 h-5 text-primary-foreground" />
          </motion.div>
          
          {open && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
            >
              <h1 className="text-xl font-bold gradient-text">AI Portal</h1>
            </motion.div>
          )}
        </div>

        <SidebarGroup className="flex-1">
          {/* Navigation label removed intentionally */}
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {navigationItems
                .filter((item) => {
                  if (user?.is_admin) return true;
                  if (item.adminOnly) return false;
                  if (user?.allowed_tabs && !user.allowed_tabs.includes(item.title)) return false;
                  return true;
                })
                .map((item, index) => {
                  const label = item.displayLabel || item.title;
                  const active = isActive(item.url);

                  return (
                    <SidebarMenuItem key={item.title}>
                      <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        {open ? (
                          <SidebarMenuButton asChild>
                            <NavLink
                              to={item.url}
                              className={cn(
                                "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-smooth group relative",
                                "hover:bg-surface-elevated",
                                active && "bg-gradient-primary text-primary-foreground"
                              )}
                            >
                              <item.icon className={cn(
                                "w-5 h-5 transition-all duration-smooth shrink-0",
                                active ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
                              )} />
                              <span className={cn(
                                "font-medium transition-all duration-smooth",
                                active ? "text-primary-foreground" : "text-foreground"
                              )}>
                                {label}
                              </span>
                            </NavLink>
                          </SidebarMenuButton>
                        ) : (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <SidebarMenuButton asChild>
                                <NavLink
                                  to={item.url}
                                  className={cn(
                                    "flex items-center justify-center p-2 rounded-lg transition-all duration-smooth group",
                                    "hover:bg-surface-elevated",
                                    active && "bg-gradient-primary text-primary-foreground"
                                  )}
                                >
                                  <item.icon className={cn(
                                    "w-5 h-5 transition-all duration-smooth",
                                    active ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
                                  )} />
                                </NavLink>
                              </SidebarMenuButton>
                            </TooltipTrigger>
                            <TooltipContent side="right" className="text-xs font-medium">
                              {label}
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </motion.div>
                    </SidebarMenuItem>
                  );
                })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Company Logo + Environment/Version — replaces System Online */}
        <motion.div
          className={cn(
            "mt-auto rounded-xl border border-border/40 bg-surface/50",
            open ? "p-4" : "p-2 flex justify-center"
          )}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          {open ? (
            <div className="flex flex-col items-center gap-1.5 text-center">
              <CompanyLogo size={120} />
              <p className="text-xs font-semibold text-foreground/80 leading-tight">AI Portal</p>
              <p className="text-[10px] text-muted-foreground/60">
                {appConfig.environment.toUpperCase()} · v{appConfig.version}
              </p>
            </div>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="cursor-default">
                  <CompanyLogo size={84} />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" className="text-xs">
                AI Portal · {appConfig.environment} · v{appConfig.version}
              </TooltipContent>
            </Tooltip>
          )}
        </motion.div>
      </SidebarContent>
    </Sidebar>
  );
}
