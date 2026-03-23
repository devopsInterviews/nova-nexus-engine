import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Palette, Info, Moon, Sun, BookOpen, ExternalLink } from "lucide-react";
import { useState, useEffect } from "react";
import { appConfigService } from "@/lib/api-service";

export default function Settings() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [appConfig, setAppConfig] = useState<{
    version: string;
    environment: string;
    confluence_url: string;
  }>({ version: "1.0.0", environment: "Production", confluence_url: "" });

  useEffect(() => {
    const saved = localStorage.getItem("theme") as "light" | "dark" | null;
    if (saved === "light" || saved === "dark") setTheme(saved);
  }, []);

  useEffect(() => {
    appConfigService.getConfig().then(res => {
      if (res.status === "success" && res.data) {
        setAppConfig({
          version: res.data.version,
          environment: res.data.environment,
          confluence_url: res.data.confluence_url,
        });
      }
    }).catch(() => {});
  }, []);

  const handleThemeChange = (newTheme: "light" | "dark") => {
    setTheme(newTheme);
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(newTheme);
    localStorage.setItem("theme", newTheme);
    // Notify AppHeader (and any other listeners in the same window) immediately
    window.dispatchEvent(new CustomEvent("themechange", { detail: newTheme }));
  };

  return (
    <motion.div
      className="space-y-6 max-w-2xl"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h1 className="text-3xl font-bold gradient-text mb-1">Personal Settings</h1>
        <p className="text-muted-foreground">Manage your personal CorteX preferences</p>
      </motion.div>

      {/* ── Appearance ──────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="w-5 h-5 text-primary" />
              Appearance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">Choose the interface theme.</p>
            <div className="grid grid-cols-2 gap-3 max-w-xs">
              {(["light", "dark"] as const).map((t) => {
                const Icon = t === "light" ? Sun : Moon;
                const active = theme === t;
                const label = t === "light" ? "Off" : "On";
                return (
                  <motion.button
                    key={t}
                    onClick={() => handleThemeChange(t)}
                    className={`flex flex-col items-center gap-2 p-5 rounded-xl border transition-all duration-200 ${
                      active
                        ? "border-primary bg-primary/10 shadow-glow"
                        : "border-border bg-surface-elevated hover:border-primary/50"
                    }`}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    <Icon className={`w-6 h-6 ${active ? "text-primary" : "text-muted-foreground"}`} />
                    <span className={`text-sm font-medium ${active ? "text-primary" : ""}`}>{label}</span>
                  </motion.button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── About ───────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card className="glass border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="w-5 h-5 text-primary" />
              About
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Info grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl p-4 glass border border-border/40 text-center">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Version</p>
                <p className="text-2xl font-bold text-primary">v{appConfig.version}</p>
              </div>
              <div className="rounded-xl p-4 glass border border-border/40 text-center">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Environment</p>
                <p className="text-2xl font-bold text-foreground">{appConfig.environment}</p>
              </div>
            </div>

            {/* Built by line */}
            <p className="text-sm text-muted-foreground text-center">
              CorteX — built with ❤️ by the DevOps Team
            </p>

            {/* Documentation */}
            <Button
              className="w-full bg-gradient-to-r from-orange-400 to-pink-500 text-white border-0 hover:opacity-90 group"
              onClick={() => {
                if (appConfig.confluence_url) {
                  window.open(appConfig.confluence_url, "_blank", "noopener,noreferrer");
                }
              }}
              disabled={!appConfig.confluence_url}
            >
              <BookOpen className="mr-2 w-4 h-4" />
              Documentation
              <ExternalLink className="ml-2 w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
