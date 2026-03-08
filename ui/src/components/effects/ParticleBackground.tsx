import { motion } from "framer-motion";

// Lightweight ambient background — opacity-only animations so the browser can
// handle them entirely on the compositor thread with no CPU repaints.
// Previously this component ran 80+ framer-motion nodes animating scale/rotate/blur
// plus a mousemove listener that re-rendered all of them on every cursor pixel,
// which reliably crashed the Chrome GPU process under normal use.

const ORBS: Array<{
  className: string;
  duration: number;
  delay: number;
  from: number;
  to: number;
}> = [
  { className: "absolute top-1/4  left-1/4  w-96 h-96 bg-primary/8   rounded-full blur-3xl", duration: 8,  delay: 0, from: 0.2, to: 0.45 },
  { className: "absolute top-3/4  right-1/4 w-80 h-80 bg-secondary/8 rounded-full blur-3xl", duration: 10, delay: 2, from: 0.15, to: 0.4 },
  { className: "absolute top-1/2  right-1/3 w-64 h-64 bg-accent/8    rounded-full blur-3xl", duration: 12, delay: 4, from: 0.1,  to: 0.35 },
  { className: "absolute bottom-1/4 left-1/3 w-72 h-72 bg-primary/6  rounded-full blur-3xl", duration: 9,  delay: 1, from: 0.1,  to: 0.3  },
];

export function ParticleBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {ORBS.map((orb, i) => (
        <motion.div
          key={i}
          className={orb.className}
          animate={{ opacity: [orb.from, orb.to, orb.from] }}
          transition={{ duration: orb.duration, delay: orb.delay, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}
