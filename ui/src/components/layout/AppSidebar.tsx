import { NavLink, useLocation } from "react-router-dom";
import { 
  Home, 
  Settings, 
  Activity, 
  Database,
  Cpu,
  Zap,
  CheckSquare,
  Users
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const navigationItems = [
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
    title: "Settings",
    url: "/settings",
    icon: Settings,
  },
  {
    title: "Users",
    url: "/users",
    icon: Users,
  },
];

export function AppSidebar() {
  const { open } = useSidebar();
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <Sidebar className={cn(
      "border-r-0 bg-surface/80 glass transition-all duration-smooth",
      !open ? "w-16" : "w-64"
    )}>
      <SidebarContent className="p-4">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <motion.div 
            className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center"
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
              <h1 className="text-xl font-bold gradient-text">MCP Control</h1>
            </motion.div>
          )}
        </div>

        <SidebarGroup>
          <SidebarGroupLabel className="text-muted-foreground text-xs uppercase tracking-wider mb-4">
            Navigation
          </SidebarGroupLabel>
          
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {navigationItems.map((item, index) => (
                <SidebarMenuItem key={item.title}>
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <SidebarMenuButton asChild>
                      <NavLink
                        to={item.url}
                        className={cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-smooth group relative",
                          "hover:bg-surface-elevated hover:shadow-glow",
                          isActive(item.url) && [
                            "bg-gradient-primary text-primary-foreground shadow-glow",
                            "before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1",
                            "before:bg-accent before:rounded-r-full"
                          ]
                        )}
                      >
                        <item.icon className={cn(
                          "w-5 h-5 transition-all duration-smooth",
                          isActive(item.url) ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
                        )} />
                        
                        {open && (
                          <span className={cn(
                            "font-medium transition-all duration-smooth",
                            isActive(item.url) ? "text-primary-foreground" : "text-foreground"
                          )}>
                            {item.title}
                          </span>
                        )}
                        
                        {isActive(item.url) && (
                          <motion.div
                            className="absolute right-2 w-2 h-2 bg-accent rounded-full animate-pulse-glow"
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                          />
                        )}
                      </NavLink>
                    </SidebarMenuButton>
                  </motion.div>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Status Indicator */}
        {open && (
          <motion.div 
            className="mt-auto p-3 rounded-lg glass border border-success/20 bg-success/5"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
              <div>
                <p className="text-sm font-medium text-success">System Online</p>
                <p className="text-xs text-muted-foreground">All services running</p>
              </div>
            </div>
          </motion.div>
        )}
      </SidebarContent>
    </Sidebar>
  );
}