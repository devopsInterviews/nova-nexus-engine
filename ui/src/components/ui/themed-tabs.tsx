import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const ThemedTabs = TabsPrimitive.Root;

const ThemedTabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex h-12 items-center justify-center rounded-lg bg-surface p-1 text-muted-foreground border border-border/50 glass",
      className
    )}
    {...props}
  />
));
ThemedTabsList.displayName = TabsPrimitive.List.displayName;

const ThemedTabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger> & {
    layoutId?: string;
  }
>(({ className, layoutId = "activeTab", ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex items-center justify-center whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm hover:text-foreground hover:bg-surface-elevated/50",
      className
    )}
    {...props}
  >
    {props.children}
    <motion.div
      className="absolute inset-0 bg-gradient-primary rounded-md -z-10"
      initial={false}
      animate={{
        opacity: props["data-state"] === "active" ? 1 : 0,
      }}
      transition={{
        type: "spring",
        stiffness: 500,
        damping: 30,
      }}
    />
  </TabsPrimitive.Trigger>
));
ThemedTabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const ThemedTabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-6 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      className
    )}
    {...props}
  >
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
    >
      {props.children}
    </motion.div>
  </TabsPrimitive.Content>
));
ThemedTabsContent.displayName = TabsPrimitive.Content.displayName;

export { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent };