import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Initialize theme on app start - default to light mode
const initializeTheme = () => {
  const savedTheme = localStorage.getItem('theme');
  
  if (savedTheme === 'dark') {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
  } else if (savedTheme === 'auto') {
    // Use system preference for auto mode
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (systemPrefersDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.add('light');
      document.documentElement.classList.remove('dark');
    }
  } else {
    // Default to light mode
    document.documentElement.classList.add('light');
    document.documentElement.classList.remove('dark');
    
    // Set light as default if no theme was saved
    if (!savedTheme) {
      localStorage.setItem('theme', 'light');
    }
  }
};

// Initialize theme before rendering
initializeTheme();

createRoot(document.getElementById("root")!).render(<App />);
