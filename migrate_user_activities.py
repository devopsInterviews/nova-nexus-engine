#!/usr/bin/env python3
"""
Migration script to make user_id nullable in user_activities table.
Run this once to update the database schema.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def migrate_user_activities():
    """Make user_id column nullable in user_activities table."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        return False
    
    print(f"Connecting to database...")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("Making user_id column nullable in user_activities table...")
                
                # Make user_id nullable
                conn.execute(text("""
                    ALTER TABLE user_activities 
                    ALTER COLUMN user_id DROP NOT NULL;
                """))
                
                print("✓ Successfully updated user_activities table")
                
                # Commit transaction
                trans.commit()
                return True
                
            except Exception as e:
                print(f"✗ Error during migration: {e}")
                trans.rollback()
                return False
                
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return False

if __name__ == "__main__":
    print("Starting user_activities migration...")
    success = migrate_user_activities()
    
    if success:
        print("\n✓ Migration completed successfully!")
        print("The user_activities table now allows NULL user_id values for anonymous tracking.")
    else:
        print("\n✗ Migration failed!")
        print("Please check the error messages above and try again.")
    
    sys.exit(0 if success else 1)
