/**
 * AppLayout - Main Application Shell Component
 * 
 * This component provides the core layout structure for the entire MCP Client application.
 * It combines navigation, content area, visual effects, and easter eggs into a cohesive user experience.
 * 
 * Key Features:
 * 1. **Sidebar Navigation**: Collapsible sidebar with route-aware navigation
 * 2. **Main Content Area**: Outlet for React Router page components
 * 3. **Visual Effects**: Cyberpunk-themed background animations
 * 4. **Easter Eggs**: Konami code activation for Matrix effect
 * 5. **Responsive Design**: Adapts to mobile, tablet, and desktop
 * 
 * Layout Structure:
 * ```
 * AppLayout
 * ├── ParticleBackground (ambient visual effect)
 * ├── MatrixRain (Konami code easter egg)
 * ├── SidebarProvider (navigation state management)
 * │   ├── AppSidebar (navigation menu)
 * │   └── Main Content Area
 * │       ├── AppHeader (top bar with user info)
 * │       └── Outlet (route-specific page content)
 * ```
 * 
 * Navigation Integration:
 * - Uses React Router's Outlet for page content
 * - Sidebar provides navigation to all main app sections
 * - Active route highlighting for user orientation
 * - Role-based menu items (admin features)
 * 
 * Visual Design:
 * - Cyberpunk aesthetic with dark theme and neon accents
 * - Animated particle background for ambiance
 * - Smooth transitions between sections
 * - Responsive layout for all screen sizes
 * 
 * Easter Eggs:
 * - Konami Code (↑↑↓↓←→←→BA) activates Matrix rain effect
 * - Console art and messages for developers
 * - Hidden animations and effects
 * 
 * State Management:
 * - Local state for visual effects (Matrix activation)
 * - SidebarProvider manages navigation state
 * - No global state dependencies (self-contained)
 * 
 * Performance:
 * - Lazy loading of visual effects
 * - Optimized re-renders with useEffect dependencies
 * - Minimal impact on route transitions
 */

import { Outlet } from "react-router-dom";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";
import { MatrixRain } from "@/components/effects/MatrixRain";
import { ParticleBackground } from "@/components/effects/ParticleBackground";
import { useEffect, useState } from "react";

export function AppLayout() {
  const [showMatrix, setShowMatrix] = useState(false);
  const [konamiSequence, setKonamiSequence] = useState<string[]>([]);
  
  const targetSequence = [
    'ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
    'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight',
    'KeyB', 'KeyA'
  ];

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const newSequence = [...konamiSequence, event.code].slice(-10);
      setKonamiSequence(newSequence);
      
      if (JSON.stringify(newSequence) === JSON.stringify(targetSequence)) {
        setShowMatrix(true);
        console.log("🎉 Konami Code activated! Matrix mode enabled!");
        setTimeout(() => setShowMatrix(false), 5000);
        setKonamiSequence([]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [konamiSequence]);

  // Easter egg console messages
  useEffect(() => {
    console.log(`
    ███╗   ███╗ ██████╗██████╗     ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  ██████╗ ██╗     
    ████╗ ████║██╔════╝██╔══██╗   ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔═══██╗██║     
    ██╔████╔██║██║     ██████╔╝   ██║     ██║   ██║██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║     
    ██║╚██╔╝██║██║     ██╔═══╝    ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══██╗██║   ██║██║     
    ██║ ╚═╝ ██║╚██████╗██║        ╚██████╗╚██████╔╝██║ ╚████║   ██║   ██║  ██║╚██████╔╝███████╗
    ╚═╝     ╚═╝ ╚═════╝╚═╝         ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    
    🚀 Welcome to the future of AI Portal!
    💡 Try the Konami Code: ↑↑↓↓←→←→BA
    🎨 Built with love and cyberpunk vibes
    `);
    
    console.log("🔮 System Status: ONLINE");
    console.log("🌟 Neural Networks: ACTIVE");
    console.log("⚡ Quantum Processors: OPTIMIZED");
  }, []);

  return (
    <SidebarProvider
      style={{ "--sidebar-width-icon": "4rem" } as React.CSSProperties}
    >
      <div className="min-h-screen flex w-full bg-background">
        <ParticleBackground />
        {showMatrix && <MatrixRain />}
        
        <AppSidebar />
        
        <div className="flex-1 flex flex-col">
          <AppHeader />
          
          <main className="flex-1 p-6 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}