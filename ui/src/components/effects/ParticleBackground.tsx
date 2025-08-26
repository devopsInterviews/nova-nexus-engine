import { useEffect, useState } from "react";
import { motion } from "framer-motion";

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
  color: string;
}

export function ParticleBackground() {
  const [particles, setParticles] = useState<Particle[]>([]);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    const generateParticles = () => {
      const newParticles: Particle[] = [];
      const colors = ['primary', 'secondary', 'accent'];
      
      for (let i = 0; i < 80; i++) {
        newParticles.push({
          id: i,
          x: Math.random() * 100,
          y: Math.random() * 100,
          size: Math.random() * 8 + 2,
          duration: Math.random() * 30 + 20,
          delay: Math.random() * 10,
          color: colors[Math.floor(Math.random() * colors.length)],
        });
      }
      setParticles(newParticles);
    };

    generateParticles();
  }, []);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Interactive particles that follow mouse */}
      {particles.slice(0, 20).map((particle) => (
        <motion.div
          key={`mouse-${particle.id}`}
          className={`absolute rounded-full bg-${particle.color}/30 blur-sm`}
          style={{
            left: mousePosition.x - particle.size / 2,
            top: mousePosition.y - particle.size / 2,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
          }}
          animate={{
            x: [0, Math.sin(particle.id) * 30, 0],
            y: [0, Math.cos(particle.id) * 30, 0],
            opacity: [0.1, 0.6, 0.1],
            scale: [0.5, 1.5, 0.5],
          }}
          transition={{
            duration: 3,
            delay: particle.delay / 10,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}

      {/* Regular floating particles */}
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className={`absolute rounded-full bg-${particle.color}/25 blur-sm`}
          style={{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
          }}
          animate={{
            y: [0, -60, 0],
            x: [0, Math.sin(particle.id) * 40, 0],
            opacity: [0.1, 0.9, 0.1],
            scale: [1, 2, 1],
            rotate: [0, 360, 0],
          }}
          transition={{
            duration: particle.duration,
            delay: particle.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
      
      {/* Enhanced glow effects with pulsing */}
      <motion.div 
        className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" 
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.7, 0.3]
        }}
        transition={{ duration: 8, repeat: Infinity }}
      />
      <motion.div 
        className="absolute top-3/4 right-1/4 w-80 h-80 bg-secondary/10 rounded-full blur-3xl"
        animate={{
          scale: [1.2, 1, 1.2],
          opacity: [0.2, 0.6, 0.2]
        }}
        transition={{ duration: 6, delay: 2, repeat: Infinity }}
      />
      <motion.div 
        className="absolute top-1/2 right-1/3 w-64 h-64 bg-accent/10 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.4, 0.8, 0.4]
        }}
        transition={{ duration: 10, delay: 4, repeat: Infinity }}
      />
      <motion.div 
        className="absolute bottom-1/4 left-1/3 w-72 h-72 bg-primary/8 rounded-full blur-3xl"
        animate={{
          scale: [1.1, 1, 1.1],
          opacity: [0.2, 0.5, 0.2]
        }}
        transition={{ duration: 12, delay: 1, repeat: Infinity }}
      />
      
      {/* Moving light streams with more complexity */}
      <motion.div
        className="absolute inset-0 opacity-40"
        animate={{
          background: [
            'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(var(--primary) / 0.4), transparent 50%)',
            'radial-gradient(ellipse 80% 50% at 80% 100%, hsl(var(--secondary) / 0.4), transparent 50%)',
            'radial-gradient(ellipse 80% 50% at 20% 100%, hsl(var(--accent) / 0.4), transparent 50%)',
            'radial-gradient(ellipse 80% 50% at 50% 50%, hsl(var(--primary) / 0.4), transparent 50%)',
            'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(var(--primary) / 0.4), transparent 50%)',
          ]
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "linear"
        }}
      />

      {/* Lightning effect */}
      <motion.div
        className="absolute inset-0"
        animate={{
          opacity: [0, 0, 0, 0.8, 0, 0, 0, 0.6, 0],
        }}
        transition={{
          duration: 15,
          repeat: Infinity,
          times: [0, 0.1, 0.2, 0.21, 0.22, 0.4, 0.6, 0.61, 1]
        }}
      >
        <div className="absolute top-0 left-1/4 w-1 h-full bg-gradient-to-b from-primary/80 via-accent/60 to-transparent blur-sm" />
        <div className="absolute top-0 right-1/3 w-1 h-full bg-gradient-to-b from-secondary/80 via-primary/60 to-transparent blur-sm" />
      </motion.div>
    </div>
  );
}