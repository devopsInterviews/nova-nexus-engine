import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { analyticsService } from '@/lib/api-service';

/**
 * PageViewTracker component that automatically logs page views
 * when the user navigates to different routes.
 */
export const PageViewTracker = () => {
  const location = useLocation();

  useEffect(() => {
    const logPageView = async () => {
      try {
        // Get page title based on pathname
        const getPageTitle = (pathname: string): string => {
          const routes: Record<string, string> = {
            '/': 'Home',
            '/bi': 'Business Intelligence',
            '/analytics': 'Analytics',
            '/devops': 'DevOps',
            '/tests': 'Tests',
            '/settings': 'Settings',
            '/users': 'Users',
            '/login': 'Login'
          };
          
          return routes[pathname] || pathname.replace('/', '').replace(/^\w/, c => c.toUpperCase());
        };

        // Don't track login page or API calls
        if (location.pathname === '/login' || location.pathname.startsWith('/api/')) {
          return;
        }

        // Log the page view
        await analyticsService.logPageView({
          path: location.pathname,
          title: getPageTitle(location.pathname),
          loadTime: Math.round(performance.now()) // Simple load time approximation
        });

        console.debug('Page view logged:', {
          path: location.pathname,
          title: getPageTitle(location.pathname)
        });

      } catch (error) {
        console.warn('Failed to log page view:', error);
        // Don't throw - page view tracking shouldn't break the app
      }
    };

    // Only log for actual page routes (not fragments or search params changes)
    if (location.pathname && location.pathname !== '/login') {
      // Small delay to ensure page is loaded
      setTimeout(logPageView, 100);
    }
  }, [location.pathname]); // Only trigger on pathname changes

  return null; // This component doesn't render anything
};
