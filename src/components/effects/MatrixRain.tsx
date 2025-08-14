import { useEffect, useState } from "react";

interface MatrixChar {
  id: number;
  char: string;
  x: number;
  speed: number;
  opacity: number;
}

export function MatrixRain() {
  const [chars, setChars] = useState<MatrixChar[]>([]);

  useEffect(() => {
    const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()";
    const columns = Math.floor(window.innerWidth / 20);
    
    const initialChars: MatrixChar[] = [];
    
    for (let i = 0; i < columns * 20; i++) {
      initialChars.push({
        id: i,
        char: characters[Math.floor(Math.random() * characters.length)],
        x: (i % columns) * 20,
        speed: Math.random() * 5 + 1,
        opacity: Math.random(),
      });
    }
    
    setChars(initialChars);

    const interval = setInterval(() => {
      setChars(prev => prev.map(char => ({
        ...char,
        char: characters[Math.floor(Math.random() * characters.length)],
        opacity: Math.random(),
      })));
    }, 100);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="matrix-rain">
      {chars.map((char) => (
        <div
          key={char.id}
          className="matrix-char"
          style={{
            left: `${char.x}px`,
            animationDuration: `${3 / char.speed}s`,
            opacity: char.opacity,
            fontSize: '14px',
          }}
        >
          {char.char}
        </div>
      ))}
    </div>
  );
}