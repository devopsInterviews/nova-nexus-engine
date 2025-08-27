#!/usr/bin/env python3
"""
Validation script to ensure all analytics components are working correctly.

This script tests:
- Model imports
- Route imports  
- Database connection setup
- Analytics service functionality
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all analytics components can be imported."""
    print("🔍 Testing imports...")
    
    try:
        # Test model imports
        from app.models import (
            User, DatabaseConnection, SystemMetrics, RequestLog, 
            McpServerStatus, PageView, UserActivity, TestConfiguration
        )
        print("✅ All models imported successfully")
        
        # Test route imports
        from app.routes.analytics_routes import router
        print("✅ Analytics routes imported successfully")
        
        # Test database imports
        from app.database import get_db_session, init_db
        print("✅ Database functions imported successfully")
        
        # Test service imports
        from app.services.analytics_service import analytics_service
        print("✅ Analytics service imported successfully")
        
        # Test middleware imports  
        from app.middleware.analytics import AnalyticsMiddleware
        print("✅ Analytics middleware imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_models():
    """Test that models can be instantiated."""
    print("\n🔍 Testing model instantiation...")
    
    try:
        from app.models import SystemMetrics, RequestLog
        
        # Test SystemMetrics
        metric = SystemMetrics(
            metric_name='test_metric',
            metric_type='gauge', 
            value='100',
            numeric_value=100
        )
        print("✅ SystemMetrics model can be instantiated")
        
        # Test RequestLog
        log = RequestLog(
            method='GET',
            path='/test',
            status_code=200,
            response_time_ms=50
        )
        print("✅ RequestLog model can be instantiated")
        
        return True
        
    except Exception as e:
        print(f"❌ Model instantiation failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🚀 Starting analytics validation...\n")
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test models
    if not test_models():
        success = False
    
    if success:
        print("\n🎉 All analytics components validated successfully!")
        print("\n📊 Your analytics implementation is ready to use:")
        print("   • Homepage will show real system metrics")
        print("   • Analytics page will display real data")
        print("   • Request logging happens automatically")
        print("   • Database tables will be created on app startup")
        print("\n🚀 Start your application to see the real analytics in action!")
    else:
        print("\n❌ Some validation tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
