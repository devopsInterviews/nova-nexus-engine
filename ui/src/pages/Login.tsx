import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Eye, EyeOff } from 'lucide-react';
import { motion, useAnimation } from 'framer-motion';
import RobotFace from './RobotFace'; // Assuming RobotFace component is in the same directory

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isPasswordHidden, setIsPasswordHidden] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const idleTimer = useRef<NodeJS.Timeout | null>(null);
  const controls = useAnimation();

  const handleLogin = async () => {
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (response.ok) {
        localStorage.setItem('token', data.token);
        navigate('/');
      } else {
        setError(data.message || 'Login failed');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    }
  };

  const resetIdleTimer = () => {
    if (idleTimer.current) {
      clearTimeout(idleTimer.current);
    }
    controls.start({
      x: 0,
      y: 0,
      transition: { type: 'spring', stiffness: 200, damping: 20 },
    });
    idleTimer.current = setTimeout(() => {
      controls.start({
        x: [0, Math.random() * 20 - 10, 0],
        y: [0, Math.random() * 20 - 10, 0],
        transition: {
          duration: 15,
          repeat: Infinity,
          repeatType: 'mirror',
        },
      });
    }, 15000);
  };

  useEffect(() => {
    resetIdleTimer();
    window.addEventListener('mousemove', resetIdleTimer);
    window.addEventListener('keydown', resetIdleTimer);
    return () => {
      if (idleTimer.current) {
        clearTimeout(idleTimer.current);
      }
      window.removeEventListener('mousemove', resetIdleTimer);
      window.removeEventListener('keydown', resetIdleTimer);
    };
  }, []);

  return (
    <div className="relative flex items-center justify-center h-screen bg-gray-900 overflow-hidden">
      <div className="absolute inset-0 z-0">
        {/* Your light moving background component here */}
      </div>
      <motion.div animate={controls}>
        <Card className="w-[400px] z-10 bg-gray-800 text-white border-gray-700">
          <CardHeader>
            <CardTitle className="text-center text-2xl">
              <RobotFace passwordLength={password.length} isPasswordHidden={isPasswordHidden} />
              Login
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div className="space-y-2 relative">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type={isPasswordHidden ? 'password' : 'text'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="bg-gray-700 border-gray-600 text-white"
                />
                <button
                  onClick={() => setIsPasswordHidden(!isPasswordHidden)}
                  className="absolute right-2 top-9 text-gray-400"
                >
                  {isPasswordHidden ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
              {error && <p className="text-red-500 text-sm">{error}</p>}
              <Button onClick={handleLogin} className="w-full bg-blue-600 hover:bg-blue-700">
                Login
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

const RobotFace: React.FC<{ passwordLength: number; isPasswordHidden: boolean }> = ({ passwordLength, isPasswordHidden }) => {
    const eyeAngle = Math.min(passwordLength * 5, 45);
  
    return (
      <div className="w-24 h-24 mx-auto mb-4 bg-gray-700 rounded-full flex items-center justify-center relative">
        <div className="flex space-x-4">
          <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center" style={{ transform: `translateX(${-eyeAngle / 4}px)` }}>
            <div className="w-3 h-3 bg-black rounded-full" style={{ transform: `translateX(${eyeAngle / 8}px)` }}></div>
          </div>
          <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center" style={{ transform: `translateX(${eyeAngle / 4}px)` }}>
            <div className="w-3 h-3 bg-black rounded-full" style={{ transform: `translateX(${eyeAngle / 8}px)` }}></div>
          </div>
        </div>
        {isPasswordHidden && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-8 bg-gray-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">Shhh!</span>
          </div>
        )}
      </div>
    );
  };
  

export default LoginPage;
