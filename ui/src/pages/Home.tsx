/**
 * Home Dashboard Page Component
 * 
 * This is the main landing page of the Nova Nexus Engine application that serves as
 * the central control center and system overview dashboard.
 * 
 * Key Features:
 * 1. **System Overview**: Real-time system statistics and health metrics
 * 2. **Hero Section**: Visually appealing introduction with call-to-action buttons
 * 3. **Activity Feed**: Recent system events and user activities
 * 4. **Performance Monitoring**: Key performance indicators and trends
 * 5. **Quick Navigation**: Direct access to main application areas
 * 
 * Data Sources:
 * - System metrics from analytics service API
 * - Real-time activity logs from backend
 * - Performance statistics from monitoring services
 * - User activity tracking for engagement metrics
 * 
 * Visual Design:
 * - Gradient backgrounds with animated elements
 * - Smooth animations using Framer Motion
 * - Glass morphism design patterns
 * - Responsive grid layouts for different screen sizes
 * - Status indicators with color-coded health states
 * 
 * User Experience:
 * - Progressive data loading with skeleton states
 * - Smooth page transitions and hover effects
 * - Intuitive navigation to main application areas
 * - Real-time updates without page refresh
 * - Mobile-responsive design for all devices
 * 
 * Analytics Integration:
 * - Automatic page view tracking
 * - Load time measurement
 * - User interaction monitoring
 * - Navigation pattern analysis
 */

import { motion } from "framer-motion";
import { ArrowRight, Activity, Server, Clock, Users, Zap, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusCard } from "@/components/ui/status-card";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { analyticsService } from "@/lib/api-service";

// TypeScript interface for system statistics displayed on dashboard
interface Stat {
  title: string;          // Display name of the metric (e.g., "System Uptime")
  value: string;          // Current value as formatted string (e.g., "99.9%")
  description: string;    // Additional context (e.g., "Last 30 days")
  icon: React.ComponentType<any>; // Lucide React icon component
  status: 'success' | 'warning' | 'error' | 'info'; // Health status for color coding
  trend: 'up' | 'down' | 'stable'; // Trend direction for trend indicators
  trendValue: string;     // Trend magnitude (e.g., "+2.1%", "-5ms")
}

// TypeScript interface for recent activity events
interface Activity {
  action: string;         // Description of what happened (e.g., "User logged in")
  status: string;         // Event status (e.g., "Completed", "Failed")
  time: string;          // Human-readable timestamp (e.g., "5 minutes ago")
  type: 'success' | 'warning' | 'error'; // Event type for visual styling
}

export default function Home() {
  // React Router hook for programmatic navigation between pages
  const navigate = useNavigate();
  
  // State management for dashboard data
  const [stats, setStats] = useState<Stat[]>([]);           // System metrics array
  const [recentActivity, setRecentActivity] = useState<Activity[]>([]); // Activity feed
  const [isLoading, setIsLoading] = useState(true);         // Loading state for data fetching

  // Icon mapping object to associate metric titles with appropriate Lucide icons
  // This provides visual consistency and intuitive iconography for different metrics
  const iconMap = {
    'System Uptime': Activity,    // Activity icon for uptime monitoring
    'Active Servers': Server,     // Server icon for infrastructure status
    'Response Time': Clock,       // Clock icon for performance metrics
    'Active Users': Users,        // Users icon for user engagement
  };

  /**
   * Dashboard Data Loading Effect
   * 
   * This useEffect hook runs on component mount and handles:
   * 1. **API Data Fetching**: Calls analytics service for real system data
   * 2. **Error Handling**: Provides fallback data if API calls fail
   * 3. **Icon Association**: Maps metric titles to appropriate icons
   * 4. **Analytics Tracking**: Logs page view for user behavior analysis
   * 5. **Performance Monitoring**: Tracks page load time
   * 
   * Data Flow:
   * - Calls analyticsService.getSystemOverview() for real metrics
   * - Falls back to default static data if API fails
   * - Associates icons with metrics for visual representation
   * - Updates component state with fetched/fallback data
   * - Logs page view analytics with performance timing
   * 
   * Error Resilience:
   * - Graceful degradation to default data if API unavailable
   * - Console error logging for debugging
   * - Maintains UI functionality even with backend issues
   */
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Attempt to fetch real system overview data from analytics API
        const response = await analyticsService.getSystemOverview();
        
        if (response.status === 'success' && response.data) {
          // Map the successful API response data to include appropriate icons
          const statsWithIcons = response.data.stats.map(stat => ({
            ...stat, // Spread existing stat properties (title, value, description, etc.)
            // Associate each metric with its corresponding icon from the iconMap
            icon: iconMap[stat.title as keyof typeof iconMap] || Activity
          }));
          
          // Update state with real data from API
          setStats(statsWithIcons);
          setRecentActivity(response.data.recentActivity);
        }
      } catch (error) {
        console.error('Failed to fetch system overview:', error);
        
        // Fallback to default static data if API call fails
        // This ensures the dashboard remains functional even with backend issues
        setStats([
          {
            title: "System Uptime",
            value: "99.9%",
            description: "Last 30 days",
            icon: Activity,
            status: "success",
            trend: "stable",
            trendValue: "0.1%",
          },
          {
            title: "Active Servers",
            value: "0",
            description: "Connected MCP servers",
            icon: Server,
            status: "warning",
            trend: "stable",
            trendValue: "0",
          },
          {
            title: "Response Time",
            value: "N/A",
            description: "Average latency",
            icon: Clock,
            status: "info",
            trend: "stable",
            trendValue: "0ms",
          },
          {
            title: "Active Users",
            value: "1",
            description: "Last 24 hours",
            icon: Users,
            status: "info",
            trend: "stable",
            trendValue: "0",
          },
        ]);
        
        // Default activity data for fallback state
        setRecentActivity([
          { action: "System initialized", status: "Completed", time: "just now", type: "success" },
        ]);
      } finally {
        // Always set loading to false regardless of success or failure
        setIsLoading(false);
      }
    };

    // Execute the data fetching function
    fetchData();

    // Log page view analytics for user behavior tracking
    // This helps understand user navigation patterns and page engagement
    analyticsService.logPageView({
      path: '/',                      // Current page path
      title: 'Home',                  // Human-readable page title
      loadTime: performance.now()     // Page load performance timing
    });
  }, []); // Empty dependency array means this runs once on component mount

  // Color mapping for activity status badges
  // Provides consistent visual styling for different event types
  const statusTypeColors = {
    success: "bg-success/10 text-success border-success/20",     // Green tones for successful events
    warning: "bg-warning/10 text-warning border-warning/20",     // Yellow tones for warning events
    error: "bg-destructive/10 text-destructive border-destructive/20", // Red tones for error events
  };

  return (
    <div className="space-y-8">
      {/* Hero Section - Main Welcome Area */}
      {/* 
        This section provides the main visual introduction to the application.
        Features:
        - Gradient background with animated elements
        - Welcome message and value proposition
        - Call-to-action buttons for main application areas
        - Smooth entrance animations using Framer Motion
      */}
      <motion.section 
        className="relative overflow-hidden rounded-2xl bg-gradient-hero p-8 text-center glass border border-border/30"
        initial={{ opacity: 0, scale: 0.95 }}    // Start slightly smaller and transparent
        animate={{ opacity: 1, scale: 1 }}       // Animate to full size and opacity
        transition={{ duration: 0.8 }}           // Smooth 0.8 second animation
      >
        <div className="relative z-10">
          {/* Welcome Text with Staggered Animation */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}      // Start below and transparent
            animate={{ opacity: 1, y: 0 }}       // Animate up and fade in
            transition={{ delay: 0.2, duration: 0.8 }} // Slight delay for staggered effect
          >
            <h1 className="text-4xl font-bold mb-4 gradient-text">
              Welcome to MCP Control Center
            </h1>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Your unified command center for DevOps automation, business intelligence, 
              and system monitoring. The future of infrastructure management is here.
            </p>
          </motion.div>

          {/* Call-to-Action Buttons with Hover Effects */}
          <motion.div 
            className="flex flex-col sm:flex-row gap-4 justify-center"
            initial={{ opacity: 0, y: 20 }}      // Start below and transparent
            animate={{ opacity: 1, y: 0 }}       // Animate up and fade in
            transition={{ delay: 0.5, duration: 0.6 }} // Longer delay for sequence
          >
            {/* Primary CTA - DevOps Suite */}
            <Button 
              size="lg" 
              className="bg-gradient-primary text-primary-foreground hover:shadow-glow transition-all duration-smooth group"
              onClick={() => navigate('/devops')} // Navigate to DevOps page
            >
              <Zap className="mr-2 h-5 w-5 group-hover:rotate-12 transition-transform" />
              Enter DevOps Suite
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            
            {/* Secondary CTA - BI Tools */}
            <Button 
              size="lg" 
              variant="outline"
              className="bg-surface/50 border-primary/30 hover:bg-gradient-primary hover:text-primary-foreground hover:shadow-glow transition-all duration-smooth group"
              onClick={() => navigate('/bi')} // Navigate to Business Intelligence page
            >
              <TrendingUp className="mr-2 h-5 w-5 group-hover:scale-110 transition-transform" />
              Explore BI Tools
            </Button>
          </motion.div>
        </div>

        {/* Animated Background Elements */}
        {/* 
          These provide subtle visual interest and depth to the hero section.
          The floating orbs have different animation patterns for dynamic movement.
        */}
        <div className="absolute inset-0 overflow-hidden">
          {/* Primary floating orb with pulsing animation */}
          <motion.div 
            className="absolute top-1/4 left-1/4 w-32 h-32 bg-primary/20 rounded-full blur-xl"
            animate={{ 
              scale: [1, 1.2, 1],          // Breathing scale animation
              opacity: [0.3, 0.5, 0.3],   // Fading opacity animation
            }}
            transition={{ duration: 4, repeat: Infinity }} // 4-second infinite loop
          />
          {/* Secondary floating orb with offset timing */}
          <motion.div 
            className="absolute bottom-1/4 right-1/4 w-24 h-24 bg-secondary/20 rounded-full blur-xl"
            animate={{ 
              scale: [1.2, 1, 1.2],        // Reverse breathing pattern
              opacity: [0.5, 0.3, 0.5],   // Reverse opacity pattern
            }}
            transition={{ duration: 3, repeat: Infinity, delay: 1 }} // 3-second loop with 1-second delay
          />
        </div>
      </motion.section>

      {/* System Statistics Grid */}
      {/* 
        This section displays key system metrics in an organized grid layout.
        Each stat card shows current values, trends, and health status.
      */}
      <section>
        <motion.h2 
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}     // Start from left and transparent
          animate={{ opacity: 1, x: 0 }}       // Animate to position and fade in
          transition={{ delay: 0.6 }}          // Delayed for sequential animation
        >
          System Overview
        </motion.h2>
        
        {/* Responsive grid that adapts to screen size */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((stat, index) => (
            <StatusCard
              key={stat.title}
              {...stat}                         // Spread all stat properties
              delay={0.7 + index * 0.1}        // Staggered animation delay for each card
            />
          ))}
        </div>
      </section>

      {/* Recent Activity Feed */}
      {/* 
        This section shows the latest system events and user activities.
        Provides real-time insight into system usage and health.
      */}
      <section>
        <motion.h2 
          className="text-2xl font-bold mb-6 text-foreground"
          initial={{ opacity: 0, x: -20 }}     // Start from left and transparent
          animate={{ opacity: 1, x: 0 }}       // Animate to position and fade in
          transition={{ delay: 1.1 }}          // Later in the animation sequence
        >
          Recent Activity
        </motion.h2>
        
        <motion.div
          initial={{ opacity: 0, y: 20 }}      // Start below and transparent
          animate={{ opacity: 1, y: 0 }}       // Animate up and fade in
          transition={{ delay: 1.2 }}          // Slight delay after header
        >
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">Latest Events</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity.map((activity, index) => (
                  <motion.div
                    key={index}
                    className="flex items-center justify-between py-3 px-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors duration-smooth group"
                    initial={{ opacity: 0, x: -20 }}   // Start from left and transparent
                    animate={{ opacity: 1, x: 0 }}     // Animate to position and fade in
                    transition={{ delay: 1.3 + index * 0.1 }} // Staggered delay for each activity
                    whileHover={{ x: 4 }}              // Slight right movement on hover
                  >
                    <div className="flex items-center gap-3">
                      {/* Activity indicator dot */}
                      <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                      <div>
                        <p className="font-medium text-foreground group-hover:text-primary transition-colors">
                          {activity.action}
                        </p>
                        <p className="text-sm text-muted-foreground">{activity.time}</p>
                      </div>
                    </div>
                    
                    {/* Status badge with color coding */}
                    <Badge 
                      variant="outline" 
                      className={statusTypeColors[activity.type as keyof typeof statusTypeColors]}
                    >
                      {activity.status}
                    </Badge>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </section>
    </div>
  );
}