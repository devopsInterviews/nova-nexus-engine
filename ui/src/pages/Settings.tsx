import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Settings2, Palette, Keyboard, Info, Moon, Sun, Monitor } from "lucide-react";
import { useState, useEffect } from "react";

export default function Settings() {
  const [theme, setTheme] = useState<'light' | 'dark' | 'auto'>("light");
  const [density, setDensity] = useState("comfortable");
  const [animations, setAnimations] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [autoSave, setAutoSave] = useState(true);

  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | 'auto' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  // Apply theme changes
  const handleThemeChange = (newTheme: 'light' | 'dark' | 'auto') => {
    setTheme(newTheme);
    
    if (newTheme === 'auto') {
      // Use system preference
      const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const actualTheme = systemPrefersDark ? 'dark' : 'light';
      document.documentElement.classList.remove('light', 'dark');
      document.documentElement.classList.add(actualTheme);
      localStorage.setItem('theme', 'auto');
    } else {
      // Use selected theme
      document.documentElement.classList.remove('light', 'dark');
      document.documentElement.classList.add(newTheme);
      localStorage.setItem('theme', newTheme);
    }
  };

  const themeOptions = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "auto", label: "Auto", icon: Monitor },
  ] as const;

  const densityOptions = [
    { value: "compact", label: "Compact" },
    { value: "comfortable", label: "Comfortable" },
    { value: "spacious", label: "Spacious" },
  ];

  const shortcuts = [
    { keys: ["Ctrl", "K"], description: "Open command palette" },
    { keys: ["Ctrl", "Shift", "P"], description: "Open quick actions" },
    { keys: ["Ctrl", "/"], description: "Toggle sidebar" },
    { keys: ["Ctrl", "Enter"], description: "Execute query" },
    { keys: ["Esc"], description: "Close modal/dialog" },
  ];

  return (
    <motion.div 
      className="space-y-6 max-w-4xl"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h1 className="text-3xl font-bold gradient-text mb-2">Settings</h1>
        <p className="text-muted-foreground">
          Customize your MCP Control Center experience
        </p>
      </motion.div>

      {/* Theme Settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="w-5 h-5 text-primary" />
              Appearance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <label className="text-sm font-medium">Theme</label>
              <div className="grid grid-cols-3 gap-3">
                {themeOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <motion.button
                      key={option.value}
                      className={`p-4 rounded-lg border transition-all duration-smooth ${
                        theme === option.value
                          ? "border-primary bg-primary/10 shadow-glow"
                          : "border-border bg-surface-elevated hover:border-primary/50"
                      }`}
                      onClick={() => handleThemeChange(option.value)}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <Icon className={`w-6 h-6 mx-auto mb-2 ${
                        theme === option.value ? "text-primary" : "text-muted-foreground"
                      }`} />
                      <span className="text-sm font-medium">{option.label}</span>
                    </motion.button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-3">
              <label className="text-sm font-medium">Density</label>
              <div className="grid grid-cols-3 gap-3">
                {densityOptions.map((option) => (
                  <Button
                    key={option.value}
                    variant={density === option.value ? "default" : "outline"}
                    className={density === option.value ? "bg-gradient-primary" : ""}
                    onClick={() => setDensity(option.value)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Enable animations</p>
                  <p className="text-sm text-muted-foreground">
                    Smooth transitions and micro-interactions
                  </p>
                </div>
                <Switch checked={animations} onCheckedChange={setAnimations} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Push notifications</p>
                  <p className="text-sm text-muted-foreground">
                    Receive alerts for system events
                  </p>
                </div>
                <Switch checked={notifications} onCheckedChange={setNotifications} />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Auto-save preferences</p>
                  <p className="text-sm text-muted-foreground">
                    Automatically save configuration changes
                  </p>
                </div>
                <Switch checked={autoSave} onCheckedChange={setAutoSave} />
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Keyboard Shortcuts */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Keyboard className="w-5 h-5 text-primary" />
              Keyboard Shortcuts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {shortcuts.map((shortcut, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 + index * 0.1 }}
                  className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors"
                >
                  <span className="text-sm">{shortcut.description}</span>
                  <div className="flex gap-1">
                    {shortcut.keys.map((key, keyIndex) => (
                      <Badge
                        key={keyIndex}
                        variant="outline"
                        className="bg-surface text-xs font-mono"
                      >
                        {key}
                      </Badge>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* About */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="w-5 h-5 text-primary" />
              About
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-1">Version</h4>
                  <p className="text-2xl font-bold text-primary">2.1.0</p>
                  <p className="text-sm text-muted-foreground">Quantum Release</p>
                </div>
                
                <div className="text-center p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-1">Build</h4>
                  <p className="text-2xl font-bold text-secondary">#4729</p>
                  <p className="text-sm text-muted-foreground">Production</p>
                </div>
                
                <div className="text-center p-4 rounded-lg glass border-border/50">
                  <h4 className="font-medium mb-1">Updated</h4>
                  <p className="text-2xl font-bold text-accent">Jan 15</p>
                  <p className="text-sm text-muted-foreground">2024</p>
                </div>
              </div>

              <div className="p-4 rounded-lg glass border-primary/20 bg-primary/5">
                <h4 className="font-medium mb-2 text-primary">🚀 What's New in v2.1.0</h4>
                <ul className="text-sm space-y-1 text-muted-foreground">
                  <li>• Enhanced AI-powered column suggestions</li>
                  <li>• Real-time collaboration features</li>
                  <li>• Advanced query optimization</li>
                  <li>• Improved security monitoring</li>
                  <li>• New cyberpunk UI theme</li>
                </ul>
              </div>

              <div className="text-center">
                <p className="text-sm text-muted-foreground mb-3">
                  Built with ❤️ by the MCP Team
                </p>
                <div className="flex justify-center gap-2">
                  <Button variant="outline" size="sm">
                    Release Notes
                  </Button>
                  <Button variant="outline" size="sm">
                    Documentation
                  </Button>
                  <Button variant="outline" size="sm">
                    Support
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}