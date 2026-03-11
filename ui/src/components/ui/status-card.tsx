import React from "react";
import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "./card";
import { Badge } from "./badge";

interface StatusCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon: LucideIcon;
  status?: "success" | "warning" | "error" | "info";
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  /** When true, "down" trend is shown as good (green) and "up" as bad (red). Useful for metrics like error rate. */
  invertTrendColor?: boolean;
  className?: string;
  delay?: number;
}

const statusColors = {
  success: "text-success border-success/30 bg-success/10 dark:border-success/20 dark:bg-success/5",
  warning: "text-warning border-warning/30 bg-warning/10",
  error: "text-destructive border-destructive/30 bg-destructive/10",
  info: "text-primary border-primary/30 bg-primary/10",
};

export function StatusCard({
  title,
  value,
  description,
  icon: Icon,
  status = "info",
  trend,
  trendValue,
  invertTrendColor = false,
  className,
  delay = 0,
}: StatusCardProps) {
  const trendColors = {
    up: invertTrendColor ? "text-destructive" : "text-success",
    down: invertTrendColor ? "text-success" : "text-destructive",
    stable: "text-muted-foreground",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
    >
      <Card className={cn(
        "glass border-border/50 transition-all duration-smooth",
        className
      )}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {title}
          </CardTitle>
          
          <motion.div
            className={cn(
              "p-2 rounded-lg border transition-all duration-smooth",
              statusColors[status]
            )}
            whileHover={{ scale: 1.1, rotate: 5 }}
          >
            <Icon className="h-4 w-4" />
          </motion.div>
        </CardHeader>
        
        <CardContent>
          <div className="flex items-baseline justify-between">
            <motion.div 
              className="text-2xl font-bold text-foreground"
              initial={{ scale: 0.5 }}
              animate={{ scale: 1 }}
              transition={{ delay: delay + 0.2, type: "spring", stiffness: 200 }}
            >
              {value}
            </motion.div>
            
            {trend && trendValue && (
              <Badge variant="outline" className={cn(
                "text-xs border-none",
                trendColors[trend]
              )}>
                {trend === "up" && "↗"} 
                {trend === "down" && "↘"} 
                {trend === "stable" && "→"} 
                {trendValue}
              </Badge>
            )}
          </div>
          
          {description && (
            <p className="text-xs text-muted-foreground mt-1">
              {description}
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}