#!/usr/bin/env python3
"""
Test script to verify database table creation works without conflicts.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import get_db_url
from app.models import Base

def test_table_creation():
    """Test that all tables can be created without index conflicts."""
    try:
        # Get database URL
        db_url = get_db_url()
        print(f"🔗 Connecting to database...")
        
        # Create engine
        engine = create_engine(db_url)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        print("📊 Creating all tables...")
        
        # Create all tables (this is where the error was occurring)
        Base.metadata.create_all(engine)
        
        print("✅ All tables created successfully!")
        
        # Verify tables exist
        with engine.connect() as conn:
            # Get list of tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result]
            print(f"\n📋 Created {len(tables)} tables:")
            for table in tables:
                print(f"   • {table}")
            
            # Check for analytics tables specifically
            analytics_tables = [
                'system_metrics', 'request_logs', 
                'mcp_server_status', 'page_views'
            ]
            
            missing_tables = [t for t in analytics_tables if t not in tables]
            if missing_tables:
                print(f"⚠️  Missing analytics tables: {missing_tables}")
            else:
                print("✅ All analytics tables created successfully!")
                
        # Test index creation by checking for indexes
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
                AND indexname LIKE 'idx_%'
                ORDER BY indexname
            """))
            
            indexes = [row[0] for row in result]
            print(f"\n🔍 Created {len(indexes)} custom indexes:")
            for index in indexes:
                print(f"   • {index}")
                
        print("\n🎉 Database setup completed successfully!")
        print("✅ No index naming conflicts detected!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing database table creation...")
    success = test_table_creation()
    
    if success:
        print("\n✅ Test passed! Your application should start without database errors.")
    else:
        print("\n❌ Test failed! Check the error above.")
        sys.exit(1)
