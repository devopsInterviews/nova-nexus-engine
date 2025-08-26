#!/usr/bin/env python3
"""
Test script to check database configuration and connection.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    print("🔍 Database Configuration Check")
    print("=" * 50)
    
    # Check environment variables
    print("Environment Variables:")
    print(f"  DATABASE_HOST: {os.getenv('DATABASE_HOST', 'localhost')}")
    print(f"  DATABASE_PORT: {os.getenv('DATABASE_PORT', '5432')}")
    print(f"  DATABASE_NAME: {os.getenv('DATABASE_NAME', 'mcp_client')}")
    print(f"  DATABASE_USER: {os.getenv('DATABASE_USER', 'mcp_user')}")
    password = os.getenv('DATABASE_PASSWORD')
    print(f"  DATABASE_PASSWORD: {'***' if password else 'Not set'}")
    print(f"  DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")
    
    print("\n🔌 Testing Database Connection...")
    try:
        from app.database import check_database_connection, get_database_info
        
        # Test connection
        if check_database_connection():
            print("✅ Database connection successful!")
            
            # Get database info
            db_info = get_database_info()
            print(f"\nDatabase Info:")
            print(f"  Status: {db_info['status']}")
            print(f"  Database: {db_info.get('database', 'Unknown')}")
            print(f"  Version: {db_info.get('version', 'Unknown')}")
            
        else:
            print("❌ Database connection failed!")
            
    except Exception as e:
        print(f"❌ Error testing database: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
