#!/usr/bin/env python3
"""
Migration script to add sender_open_rate and sender_reply_rate fields to Email table
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def add_sender_engagement_fields():
    """Add sender_open_rate and sender_reply_rate columns to email table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='email' 
                AND column_name IN ('sender_open_rate', 'sender_reply_rate')
            """)
            
            result = db.session.execute(check_query)
            existing_columns = [row[0] for row in result]
            
            if 'sender_open_rate' in existing_columns and 'sender_reply_rate' in existing_columns:
                print("✓ Columns already exist. No migration needed.")
                return
            
            print("Adding sender_open_rate and sender_reply_rate columns to email table...")
            
            # Add sender_open_rate column
            if 'sender_open_rate' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE email 
                    ADD COLUMN sender_open_rate FLOAT
                """))
                print("✓ Added sender_open_rate column")
            else:
                print("✓ sender_open_rate column already exists")
            
            # Add sender_reply_rate column
            if 'sender_reply_rate' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE email 
                    ADD COLUMN sender_reply_rate FLOAT
                """))
                print("✓ Added sender_reply_rate column")
            else:
                print("✓ sender_reply_rate column already exists")
            
            # Commit the changes
            db.session.commit()
            print("\n✅ Migration completed successfully!")
            
            # Optionally, update existing records with default values from their account
            print("\nUpdating existing email records with sender account's engagement rates...")
            update_query = text("""
                UPDATE email 
                SET 
                    sender_open_rate = account.open_rate,
                    sender_reply_rate = account.reply_rate
                FROM account
                WHERE email.account_id = account.id
                AND email.sender_open_rate IS NULL
            """)
            result = db.session.execute(update_query)
            db.session.commit()
            print(f"✓ Updated {result.rowcount} existing email records")
            
            print("\n🎉 All done! The Email table now tracks sender engagement strategy.")
            
        except Exception as e:
            print(f"\n❌ Error during migration: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    add_sender_engagement_fields()

