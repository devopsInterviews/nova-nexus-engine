import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, User, Lock, Zap, AlertCircle, CheckCircle, Bot, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ParticleBackground } from '@/components/effects/ParticleBackground';

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
      case 'left': return 'translate(-10px, 0)';
      case 'right': return 'translate(10px, 0)';
      default: return 'translate(0, 0)';
    }
  };

  const getEyeHeight = () => {
    if (eyesClosedForPassword) return '3px';
    if (isBlinking) return '5px';
    return '28px';
  };

  const getEyeWidth = () => {
    if (eyesClosedForPassword) return '50px';
    if (isBlinking) return '28px';
    return '28px';
  };

  return (
    <div className="relative w-20 h-20 bg-gradient-to-b from-slate-700 to-slate-800 rounded-full border-2 border-slate-600 overflow-hidden shadow-lg">
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
            <div className="absolute top-1 left-1 w-3 h-3 bg-white rounded-full opacity-80" />
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
  type: string; // actual input type passed (can be text when revealing password)
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  icon: React.ReactNode;
  onFocus: () => void;
  onBlur: () => void;
  showPassword?: boolean;
  onTogglePassword?: () => void;
  disabled?: boolean;
  isPasswordField?: boolean; // persist eye button presence
}

const FloatingInput: React.FC<FloatingInputProps> = ({
  id,
  type,
  placeholder,
  value,
  onChange,
  icon,
  onFocus,
  onBlur,
  showPassword,
  onTogglePassword,
  disabled = false,
  isPasswordField = false
}) => {
  return (
    <motion.div className="relative group">
      <div className="relative">
        <div className="absolute left-4 top-1/2 transform -translate-y-1/2 text-muted-foreground z-10">
          {icon}
        </div>
        <Input
          id={id}
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          disabled={disabled}
          className="pl-12 pr-14 h-14 text-lg glass border-border/50 focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all duration-300 relative z-0"
          autoComplete={type === 'password' ? 'current-password' : 'username'}
        />
  {isPasswordField && onTogglePassword && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-2 top-1/2 transform -translate-y-1/2 h-12 w-12 p-0 hover:bg-surface-elevated z-10"
            onClick={onTogglePassword}
          >
            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
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
  const [activeField, setActiveField] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  
  const blinkTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Handle robot eye tracking based on password cursor position
  const updateEyeDirection = () => {
    if (activeField === 'password' && password.length > 0) {
      // Eyes follow the last character position
      const cursorPosition = password.length;
      const maxLength = 20; // Assume reasonable max length for calculation
      
      if (cursorPosition <= maxLength * 0.3) {
        setEyeDirection('left');
      } else if (cursorPosition >= maxLength * 0.7) {
        setEyeDirection('right');
      } else {
        setEyeDirection('center');
      }
    } else {
      setEyeDirection('center');
    }
  };

  // Effect for password cursor tracking
  useEffect(() => {
    updateEyeDirection();
  }, [password, activeField]);

  // Random blinking effect
  useEffect(() => {
    const startBlinking = () => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 150);
      
      blinkTimer.current = setTimeout(startBlinking, Math.random() * 4000 + 2000);
    };

    blinkTimer.current = setTimeout(startBlinking, Math.random() * 2000 + 1000);

    return () => {
      if (blinkTimer.current) {
        clearTimeout(blinkTimer.current);
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;

    try {
      await onLogin(username, password);
      setShowSuccess(true);
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  const handleFieldFocus = (field: string) => {
    setActiveField(field);
  };

  const handleFieldBlur = () => {
    setActiveField(null);
  };

  const eyesClosedForPassword = activeField === 'password' && !showPassword && password.length > 0; // unchanged logic reaffirmed

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-background via-surface to-surface-elevated">
      {/* Background Effects */}
      <ParticleBackground />
      
      {/* About Button - Top Left */}
      <motion.div
        className="absolute top-4 left-4 z-20"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.5 }}
      >
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground transition-colors glass border border-border/30 backdrop-blur-sm"
          onClick={() => setShowAbout(true)}
        >
          About
        </Button>
      </motion.div>

      {/* About Modal */}
      <AnimatePresence>
        {showAbout && (
          <motion.div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowAbout(false)}
          >
            <motion.div
              className="bg-surface border border-border rounded-xl p-6 max-w-md mx-4 glass backdrop-blur-md"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold gradient-text">MCP Control System </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAbout(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-muted-foreground mb-4">
                A powerful Model Context Protocol management interface designed for the future of AI interactions.
              </p>
              <p className="text-sm text-muted-foreground">
                Built with modern web technologies and cyberpunk aesthetics.
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Login Card */}
      <motion.div
        initial={{ opacity: 0, y: 50, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="w-full max-w-2xl z-10"
      >
        <Card className="glass border-border/50 shadow-2xl">
          <CardHeader className="text-center pb-8 pt-8">
            {/* Robot Head */}
            <motion.div
              className="mx-auto mb-8 relative"
            >
              {/* Robot Head Container */}
              <div className="relative w-48 h-40 bg-gradient-to-b from-slate-600 to-slate-800 rounded-3xl border-2 border-slate-500 shadow-xl">
                {/* Head top decoration */}
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 w-12 h-6 bg-gradient-to-b from-primary to-primary/80 rounded-t-lg border border-primary/30" />
                
                {/* MCP Logo/Badge */}
                <div className="absolute -top-2 right-3 w-8 h-8 bg-gradient-to-br from-accent to-primary rounded-full flex items-center justify-center border border-accent/50">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                
                {/* Eyes */}
                <div className="absolute top-6 left-1/2 transform -translate-x-1/2 flex space-x-6">
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
                  className="absolute bottom-4 left-1/2 transform -translate-x-1/2"
                  animate={loading ? {
                    scaleX: [1, 1.2, 1],
                    scaleY: [1, 0.8, 1]
                  } : {}}
                  transition={{ duration: 1, repeat: loading ? Infinity : 0 }}
                >
                  <div className="w-16 h-4 bg-gradient-to-r from-slate-800 to-slate-900 rounded-full border border-slate-600" />
                  {loading && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-primary/30 to-accent/30 rounded-full"
                      animate={{ opacity: [0.3, 0.8, 0.3] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  )}
                </motion.div>
                
                {/* Side panels */}
                <div className="absolute left-1 top-1/2 transform -translate-y-1/2 w-3 h-12 bg-gradient-to-b from-slate-700 to-slate-900 rounded-l-lg" />
                <div className="absolute right-1 top-1/2 transform -translate-y-1/2 w-3 h-12 bg-gradient-to-b from-slate-700 to-slate-900 rounded-r-lg" />
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
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <Alert className="border-green-500/50 bg-green-500/10">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <AlertDescription className="text-green-700 dark:text-green-300">
                      Login successful! Redirecting to dashboard...
                    </AlertDescription>
                  </Alert>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error Message */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <Alert variant="destructive" className="glass border-red-500/50">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      {error}
                    </AlertDescription>
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
                onFocus={() => handleFieldFocus('password')}
                onBlur={handleFieldBlur}
                showPassword={showPassword}
                onTogglePassword={() => setShowPassword(!showPassword)}
                disabled={loading}
                isPasswordField
              />

              <motion.div>
                <Button
                  type="submit"
                  className="w-full h-14 text-lg bg-gradient-primary hover:opacity-90 text-primary-foreground font-semibold shadow-glow transition-all duration-300 disabled:opacity-50"
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
                    "Login"
                  )}
                </Button>
              </motion.div>

              {/* Contact Information */}
              <motion.div
                className="text-center text-sm text-muted-foreground mt-4"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.2 }}
              >
                <p>If you want access to the system please contact the DevOps team.</p>
              </motion.div>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};
