#!/usr/bin/env python3
"""
Create migration for new EmailSchedule table and timezone column
Run this once to update the database schema
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from flask_migrate import init, migrate, upgrade

def create_migration():
    app = create_app()
    
    with app.app_context():
        # Initialize migrations if not already done
        if not os.path.exists('migrations'):
            print("Initializing migrations...")
            init()
        
        # Create migration
        print("Creating migration for EmailSchedule table and timezone column...")
        print("\nChanges to be applied:")
        print("  1. Add 'timezone' column to 'account' table (default: 'Asia/Kolkata')")
        print("  2. Create 'email_schedule' table with:")
        print("     - id, account_id, scheduled_time, schedule_date")
        print("     - activity_period, status, sent_at, email_id")
        print("     - retry_count, last_error, created_at, updated_at")
        print("  3. Add foreign key relationships")
        print("  4. Add indexes for performance")
        
        migrate(message="add_email_schedule_table_and_timezone")
        
        # Apply migration
        print("\nApplying migration...")
        upgrade()
        
        print("\n✓ Migration completed successfully!")
        print("\nNext steps:")
        print("  1. Verify the schema: Check that email_schedule table exists")
        print("  2. Run check_accounts.py to see current configuration")
        print("  3. Start Celery workers and beat scheduler")
        print("  4. Monitor logs for schedule generation")

if __name__ == "__main__":
    create_migration()
