import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Initialize theme on app start - default to light mode
const initializeTheme = () => {
  const savedTheme = localStorage.getItem('theme');
  
  if (savedTheme === 'dark') {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
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
