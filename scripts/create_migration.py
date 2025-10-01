#!/usr/bin/env python3
"""Create migration for warmup configuration fields"""

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
        print("Creating migration for warmup configuration fields...")
        migrate(message="add_warmup_configuration_fields")
        
        # Apply migration
        print("Applying migration...")
        upgrade()
        
        print("\n✓ Migration completed successfully!")

if __name__ == "__main__":
    create_migration()