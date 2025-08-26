import { useEffect, useState } from "react";

interface MatrixChar {
  id: number;
  char: string;
  x: number;
  y: number;
  speed: number;
  opacity: number;
  trail: string[];
}

export function MatrixRain() {
  const [chars, setChars] = useState<MatrixChar[]>([]);

  useEffect(() => {
    const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*(){}[]<>MCP";
    const columns = Math.floor(window.innerWidth / 20);
    const rows = Math.floor(window.innerHeight / 20);
    
    const initialChars: MatrixChar[] = [];
    
    for (let i = 0; i < columns; i++) {
      for (let j = 0; j < 3; j++) { // 3 streams per column
        const trailLength = 8 + Math.floor(Math.random() * 12);
        const trail = Array.from({ length: trailLength }, () => 
          characters[Math.floor(Math.random() * characters.length)]
        );
        
        initialChars.push({
          id: i * 3 + j,
          char: characters[Math.floor(Math.random() * characters.length)],
          x: i * 20,
          y: Math.random() * -window.innerHeight,
          speed: 2 + Math.random() * 4,
          opacity: 0.3 + Math.random() * 0.7,
          trail: trail,
        });
      }
    }
    
    setChars(initialChars);

    const interval = setInterval(() => {
      setChars(prev => prev.map(char => {
        const newY = char.y + char.speed;
        const resetY = newY > window.innerHeight ? Math.random() * -200 : newY;
        
        return {
          ...char,
          y: resetY,
          char: characters[Math.floor(Math.random() * characters.length)],
          opacity: 0.3 + Math.random() * 0.7,
          trail: char.trail.map(() => characters[Math.floor(Math.random() * characters.length)]),
        };
      }));
    }, 100);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="matrix-rain">
      {chars.map((char) => (
        <div key={char.id}>
          {/* Main character */}
          <div
            className="matrix-char text-success font-bold"
            style={{
              position: 'absolute',
              left: `${char.x}px`,
              top: `${char.y}px`,
              opacity: char.opacity,
              fontSize: '16px',
              textShadow: '0 0 10px currentColor',
            }}
          >
            {char.char}
          </div>
          
          {/* Trail */}
          {char.trail.map((trailChar, index) => (
            <div
              key={`${char.id}-trail-${index}`}
              className="matrix-char text-success"
              style={{
                position: 'absolute',
                left: `${char.x}px`,
                top: `${char.y - (index + 1) * 20}px`,
                opacity: Math.max(0, char.opacity - (index + 1) * 0.1),
                fontSize: '14px',
                textShadow: '0 0 5px currentColor',
              }}
            >
              {trailChar}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}