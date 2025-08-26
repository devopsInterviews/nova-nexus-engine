import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, User, Lock, Zap, AlertCircle, CheckCircle, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ParticleBackground } from '@/components/effects/ParticleBackground';
import { MatrixRain } from '@/components/effects/MatrixRain';

interface RobotEyeProps {
  isWatching: boolean;
  isBlinking: boolean;
  eyesClosedForPassword: boolean;
  direction: 'left' | 'center' | 'right';
}

const RobotEye: React.FC<RobotEyeProps> = ({ isWatching, isBlinking, eyesClosedForPassword, direction }) => {
  const getEyePosition = () => {
    if (eyesClosedForPassword || isBlinking) return 'translate(0, 0)';
    
    switch (direction) {
      case 'left': return 'translate(-8px, 0)';
      case 'right': return 'translate(8px, 0)';
      default: return 'translate(0, 0)';
    }
  };

  const getEyeHeight = () => {
    if (eyesClosedForPassword) return '2px';
    if (isBlinking) return '4px';
    return '24px';
  };

  const getEyeWidth = () => {
    if (eyesClosedForPassword) return '40px';
    if (isBlinking) return '24px';
    return '24px';
  };

  return (
    <div className="relative w-16 h-16 bg-gradient-to-b from-slate-700 to-slate-800 rounded-full border-2 border-slate-600 overflow-hidden shadow-lg">
      {/* Eye outer ring */}
      <div className="absolute inset-2 bg-gradient-to-b from-blue-400 to-blue-600 rounded-full">
        {/* Eye pupil */}
        <motion.div
          className="absolute top-1/2 left-1/2 bg-gradient-to-b from-slate-900 to-black rounded-full"
          style={{
            transform: 'translate(-50%, -50%)',
            height: getEyeHeight(),
            width: getEyeWidth()
          }}
          animate={{
            transform: `translate(-50%, -50%) ${getEyePosition()}`
          }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {/* Eye glint */}
          {!eyesClosedForPassword && !isBlinking && (
            <div className="absolute top-1 left-1 w-2 h-2 bg-white rounded-full opacity-80" />
          )}
        </motion.div>
      </div>
      
      {/* Eyelid for blinking */}
      <motion.div
        className="absolute inset-0 bg-gradient-to-b from-slate-700 to-slate-800 origin-top"
        initial={{ scaleY: 0 }}
        animate={{ scaleY: isBlinking ? 1 : 0 }}
        transition={{ duration: 0.1 }}
      />
      
      {/* Eye glow effect when active */}
      {isWatching && !isBlinking && (
        <motion.div
          className="absolute -inset-1 bg-primary/20 rounded-full blur-sm"
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}
    </div>
  );
};

interface FloatingInputProps {
  id: string;
  type: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  icon: React.ReactNode;
  isFloating: boolean;
  onFocus: () => void;
  onBlur: () => void;
  showPassword?: boolean;
  onTogglePassword?: () => void;
  disabled?: boolean;
}

const FloatingInput: React.FC<FloatingInputProps> = ({
  id,
  type,
  placeholder,
  value,
  onChange,
  icon,
  isFloating,
  onFocus,
  onBlur,
  showPassword,
  onTogglePassword,
  disabled = false
}) => {
  const baseRotation = Math.random() * 360;
  const floatDistance = 20 + Math.random() * 40;
  
  return (
    <motion.div
      className="relative group"
      animate={isFloating ? {
        x: [0, floatDistance, -floatDistance, 0],
        y: [0, -floatDistance, floatDistance, 0],
        rotate: [baseRotation, baseRotation + 10, baseRotation - 10, baseRotation],
      } : {
        x: 0,
        y: 0,
        rotate: 0
      }}
      transition={{
        duration: 8,
        repeat: isFloating ? Infinity : 0,
        ease: "easeInOut"
      }}
    >
      <Label htmlFor={id} className="text-sm font-medium text-foreground mb-2 block">
        {placeholder}
      </Label>
      <div className="relative">
        <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground z-10">
          {icon}
        </div>
        <Input
          id={id}
          type={type}
          placeholder={`Enter ${placeholder.toLowerCase()}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          disabled={disabled}
          className="pl-10 pr-12 h-12 glass border-border/50 focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all duration-300 relative z-0"
          autoComplete={type === 'password' ? 'current-password' : 'username'}
        />
        {type === 'password' && onTogglePassword && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-1 top-1/2 transform -translate-y-1/2 h-10 w-10 p-0 hover:bg-surface-elevated z-10"
            onClick={onTogglePassword}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        )}
      </div>
    </motion.div>
  );
};

interface LoginScreenProps {
  onLogin: (username: string, password: string) => Promise<void>;
  loading?: boolean;
  error?: string | null;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin, loading = false, error = null }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isBlinking, setIsBlinking] = useState(false);
  const [eyeDirection, setEyeDirection] = useState<'left' | 'center' | 'right'>('center');
  const [isFloating, setIsFloating] = useState(false);
  const [activeField, setActiveField] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  
  const inactivityTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const blinkTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Handle inactivity floating animation
  const resetInactivityTimer = () => {
    if (inactivityTimer.current) {
      clearTimeout(inactivityTimer.current);
    }
    
    setIsFloating(false);
    
    inactivityTimer.current = setTimeout(() => {
      setIsFloating(true);
    }, 15000); // 15 seconds of inactivity
  };

  // Handle robot eye movement based on active field
  useEffect(() => {
    if (activeField === 'password' && password.length > 0 && !showPassword) {
      // Robot looks away when password is being typed and hidden
      setEyeDirection('right');
      return;
    }
    
    if (activeField === 'username') {
      setEyeDirection('left');
    } else if (activeField === 'password') {
      setEyeDirection('right');
    } else {
      setEyeDirection('center');
    }
  }, [activeField, password.length, showPassword]);

  // Random blinking animation
  useEffect(() => {
    const startBlinking = () => {
      const blinkInterval = 2000 + Math.random() * 3000; // 2-5 seconds
      blinkTimer.current = setTimeout(() => {
        setIsBlinking(true);
        setTimeout(() => {
          setIsBlinking(false);
          startBlinking();
        }, 150); // Blink duration
      }, blinkInterval);
    };

    startBlinking();

    return () => {
      if (blinkTimer.current) {
        clearTimeout(blinkTimer.current);
      }
    };
  }, []);

  // Track user activity
  useEffect(() => {
    resetInactivityTimer();

    const handleActivity = () => {
      resetInactivityTimer();
    };

    const handleMouseMove = () => handleActivity();
    const handleKeyPress = () => handleActivity();
    const handleClick = () => handleActivity();

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('keypress', handleKeyPress);
    document.addEventListener('click', handleClick);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('keypress', handleKeyPress);
      document.removeEventListener('click', handleClick);
      if (inactivityTimer.current) {
        clearTimeout(inactivityTimer.current);
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim() || loading) return;

    try {
      await onLogin(username.trim(), password);
      setShowSuccess(true);
    } catch (error) {
      // Error handling is done by parent component
    }
  };

  const handleFieldFocus = (field: string) => {
    setActiveField(field);
    resetInactivityTimer();
  };

  const handleFieldBlur = () => {
    setActiveField(null);
    resetInactivityTimer();
  };

  const eyesClosedForPassword = activeField === 'password' && !showPassword && password.length > 0;

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-background via-surface to-surface-elevated">
      {/* Background Effects */}
      <ParticleBackground />
      
      {/* Matrix Rain Easter Egg */}
      <AnimatePresence>
        {isFloating && <MatrixRain />}
      </AnimatePresence>
      
      {/* Main Login Card */}
      <motion.div
        initial={{ opacity: 0, y: 50, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="w-full max-w-md z-10"
      >
        <Card className="glass border-border/50 shadow-2xl">
          <CardHeader className="text-center pb-8">
            {/* Robot Head */}
            <motion.div
              className="mx-auto mb-6 relative"
              animate={isFloating ? {
                rotate: [0, 5, -5, 0],
                scale: [1, 1.05, 0.95, 1]
              } : {}}
              transition={{ duration: 6, repeat: isFloating ? Infinity : 0 }}
            >
              {/* Robot Head Container */}
              <div className="relative w-32 h-28 bg-gradient-to-b from-slate-600 to-slate-800 rounded-3xl border-2 border-slate-500 shadow-lg">
                {/* Head top decoration */}
                <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 w-8 h-4 bg-gradient-to-b from-primary to-primary/80 rounded-t-lg border border-primary/30" />
                
                {/* MCP Logo/Badge */}
                <div className="absolute -top-1 right-2 w-6 h-6 bg-gradient-to-br from-accent to-primary rounded-full flex items-center justify-center border border-accent/50">
                  <Bot className="w-3 h-3 text-white" />
                </div>
                
                {/* Eyes */}
                <div className="absolute top-4 left-1/2 transform -translate-x-1/2 flex space-x-4">
                  <RobotEye
                    isWatching={activeField !== null}
                    isBlinking={isBlinking}
                    eyesClosedForPassword={eyesClosedForPassword}
                    direction={eyeDirection}
                  />
                  <RobotEye
                    isWatching={activeField !== null}
                    isBlinking={isBlinking}
                    eyesClosedForPassword={eyesClosedForPassword}
                    direction={eyeDirection}
                  />
                </div>
                
                {/* Mouth */}
                <motion.div
                  className="absolute bottom-3 left-1/2 transform -translate-x-1/2"
                  animate={loading ? {
                    scaleX: [1, 1.2, 1],
                    scaleY: [1, 0.8, 1]
                  } : {}}
                  transition={{ duration: 1, repeat: loading ? Infinity : 0 }}
                >
                  <div className="w-12 h-3 bg-gradient-to-r from-slate-800 to-slate-900 rounded-full border border-slate-600" />
                  {loading && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-primary/30 to-accent/30 rounded-full"
                      animate={{ opacity: [0.3, 0.8, 0.3] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  )}
                </motion.div>
                
                {/* Side panels */}
                <div className="absolute left-1 top-1/2 transform -translate-y-1/2 w-2 h-8 bg-gradient-to-b from-slate-700 to-slate-900 rounded-l-lg" />
                <div className="absolute right-1 top-1/2 transform -translate-y-1/2 w-2 h-8 bg-gradient-to-b from-slate-700 to-slate-900 rounded-r-lg" />
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
            >
              <CardTitle className="text-3xl font-bold gradient-text mb-2 flex items-center justify-center gap-2">
                <Zap className="w-8 h-8 text-primary" />
                MCP Control
              </CardTitle>
              <CardDescription className="text-muted-foreground">
                Welcome to the future of Model Context Protocol
              </CardDescription>
            </motion.div>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Success Message */}
            <AnimatePresence>
              {showSuccess && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                >
                  <Alert className="border-success/50 bg-success/10">
                    <CheckCircle className="h-4 w-4 text-success" />
                    <AlertDescription className="text-success">
                      Login successful! Initializing neural networks...
                    </AlertDescription>
                  </Alert>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error Message */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                >
                  <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-6">
              <FloatingInput
                id="username"
                type="text"
                placeholder="Username"
                value={username}
                onChange={setUsername}
                icon={<User className="h-4 w-4" />}
                isFloating={isFloating}
                onFocus={() => handleFieldFocus('username')}
                onBlur={handleFieldBlur}
                disabled={loading}
              />

              <FloatingInput
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Password"
                value={password}
                onChange={setPassword}
                icon={<Lock className="h-4 w-4" />}
                isFloating={isFloating}
                onFocus={() => handleFieldFocus('password')}
                onBlur={handleFieldBlur}
                showPassword={showPassword}
                onTogglePassword={() => setShowPassword(!showPassword)}
                disabled={loading}
              />

              <motion.div
                animate={isFloating ? {
                  x: [0, 10, -10, 0],
                  y: [0, -15, 15, 0],
                  rotate: [0, 2, -2, 0]
                } : {}}
                transition={{ duration: 10, repeat: isFloating ? Infinity : 0 }}
              >
                <Button
                  type="submit"
                  className="w-full h-12 bg-gradient-primary hover:opacity-90 text-primary-foreground font-semibold shadow-glow transition-all duration-300 disabled:opacity-50"
                  disabled={loading || !username.trim() || !password.trim()}
                >
                  {loading ? (
                    <motion.div
                      className="flex items-center gap-2"
                      animate={{ opacity: [0.5, 1, 0.5] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    >
                      <motion.div
                        className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      />
                      Authenticating...
                    </motion.div>
                  ) : (
                    "Access Neural Network"
                  )}
                </Button>
              </motion.div>
            </form>

            {/* Footer */}
            <motion.div
              className="text-center text-sm text-muted-foreground"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
            >
              Default credentials: admin / admin
            </motion.div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Floating Elements Hint */}
      <AnimatePresence>
        {isFloating && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="absolute bottom-8 left-1/2 transform -translate-x-1/2 text-center text-sm text-muted-foreground bg-surface/80 backdrop-blur-sm rounded-lg px-4 py-2 border border-border/50"
          >
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              🎮 Easter egg activated! Move your mouse to return to normal
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
