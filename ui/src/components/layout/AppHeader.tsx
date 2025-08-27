import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/context/auth-context";
import { useEffect, useState } from 'react';
import { Moon, Sun } from "lucide-react";

export function AppHeader() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  const handleProfile = () => {
    // For now, just show an alert since we don't have routing
    alert('Profile functionality coming soon!');
  };

  const handleSettings = () => {
    // Navigate to settings page
    window.location.href = '/settings';
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user) return 'U';
    if (user.full_name) {
      const names = user.full_name.split(' ');
      return names.length > 1 
        ? `${names[0][0]}${names[1][0]}`.toUpperCase()
        : names[0][0].toUpperCase();
    }
    return user.username.substring(0, 2).toUpperCase();
  };

  const [themeMode, setThemeMode] = useState<'light'|'dark'>(() => {
    const saved = localStorage.getItem('theme');
    return (saved === 'dark' || saved === 'light') ? saved : 'light';
  });

  useEffect(() => {
    const applyTheme = (theme: 'light' | 'dark') => {
      const root = document.documentElement;
      root.classList.remove('light', 'dark');
      root.classList.add(theme);
      localStorage.setItem('theme', theme);
    };

    applyTheme(themeMode);
  }, [themeMode]);

  const toggleTheme = () => {
    setThemeMode(prev => prev === 'light' ? 'dark' : 'light');
  };

  return (
    <header className="h-16 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 sticky top-0 z-50 shadow-sm">
      <div className="flex items-center justify-between h-full px-6">
        {/* Left Section */}
        <div className="flex items-center gap-4">
          <SidebarTrigger />
          
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
              PRODUCTION
            </span>
            
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
              v2.1.0
            </span>
          </div>
        </div>

        {/* Center - Search */}
        <div className="flex-1 max-w-md mx-8">
          <div className="relative">
            <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500">🔍</span>
            <Input
              placeholder="Search across all systems..."
              className="pl-10 dark:bg-gray-800 dark:border-gray-600 dark:text-white dark:placeholder-gray-400"
            />
          </div>
        </div>

        {/* Right Section */}
        <div className="flex items-center gap-3">
          {/* Theme Toggle */}
          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme" className="dark:text-gray-200 dark:hover:bg-gray-800">
            {themeMode === 'light' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
          </Button>
          
          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-8 w-8 rounded-full dark:hover:bg-gray-800">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-blue-600 text-white font-semibold">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            
            <DropdownMenuContent 
              className="w-56 dark:bg-gray-800 dark:border-gray-700" 
              align="end"
            >
              <div className="flex items-center justify-start gap-2 p-2">
                <div className="flex flex-col space-y-1 leading-none">
                  <p className="font-medium text-sm dark:text-white">
                    {user?.full_name || user?.username || 'User'}
                  </p>
                  <p className="w-[200px] truncate text-xs text-gray-500 dark:text-gray-400">
                    {user?.email || 'No email'}
                  </p>
                  {user?.is_admin && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">
                      Admin
                    </span>
                  )}
                </div>
              </div>
              
              <DropdownMenuSeparator className="dark:bg-gray-700" />
              
              <DropdownMenuItem className="cursor-pointer dark:text-gray-200 dark:hover:bg-gray-700" onClick={handleProfile}>
                👤 Profile
              </DropdownMenuItem>
              
              <DropdownMenuItem className="cursor-pointer dark:text-gray-200 dark:hover:bg-gray-700" onClick={handleSettings}>
                ⚙️ Settings
              </DropdownMenuItem>
              
              <DropdownMenuSeparator className="dark:bg-gray-700" />
              
              <DropdownMenuItem className="cursor-pointer text-red-600 dark:text-red-400 dark:hover:bg-gray-700" onClick={handleLogout}>
                🚪 Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}