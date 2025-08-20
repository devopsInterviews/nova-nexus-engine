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
    
    🚀 Welcome to the future of MCP Control!
    💡 Try the Konami Code: ↑↑↓↓←→←→BA
    🎨 Built with love and cyberpunk vibes
    `);
    
    console.log("🔮 System Status: ONLINE");
    console.log("🌟 Neural Networks: ACTIVE");
    console.log("⚡ Quantum Processors: OPTIMIZED");
  }, []);

  return (
    <SidebarProvider>
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