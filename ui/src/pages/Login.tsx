import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LoginScreen } from '@/components/auth/LoginScreen';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();

  const handleLogin = async (username: string, password: string) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        localStorage.setItem('auth_token', data.access_token);
        localStorage.setItem('auth_user', JSON.stringify(data.user));
        navigate('/', { replace: true });
      } else {
        throw new Error(data.detail || 'Login failed');
      }
    } catch (err) {
      throw err; // Let LoginScreen handle the error display
    }
  };

  return (
    <LoginScreen
      onLogin={handleLogin}
      loading={false}
      error={null}
    />
  );
};

export default LoginPage;
