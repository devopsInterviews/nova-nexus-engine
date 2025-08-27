#!/usr/bin/env python3
"""
Database migration script to create new analytics tables.

This script creates the new analytics tables without affecting existing data.
Run this after adding the new models to ensure all tables exist.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from app.database import init_db
from app.models import Base, SystemMetrics, RequestLog, McpServerStatus, PageView, UserActivity
from sqlalchemy import create_engine

def create_analytics_tables():
    """Create analytics tables if they don't exist."""
    try:
        print("Creating analytics tables...")
        
        # Initialize database connection
        init_db()
        
        print("✅ Analytics tables created successfully!")
        print("\nNew tables added:")
        print("- system_metrics: For tracking system performance metrics")
        print("- request_logs: For logging API requests and performance")
        print("- mcp_server_status: For monitoring MCP server health")
        print("- page_views: For tracking page visits")
        print("- user_activities: Enhanced user activity tracking")
        
    except Exception as e:
        print(f"❌ Error creating analytics tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_analytics_tables()
