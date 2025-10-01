#!/usr/bin/env python3
"""
Setup script to configure warmup and pool accounts
This script helps configure one account as the warmup account and others as pool accounts
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.account import Account

def setup_warmup_config():
    app = create_app()
    
    with app.app_context():
        # Get all accounts
        accounts = Account.query.all()
        
        if not accounts:
            print("\n❌ No accounts found in database!")
            print("Please add accounts first using the OAuth flow.")
            return
        
        print(f"\n{'='*70}")
        print(f"{'WARMUP ACCOUNT CONFIGURATION':^70}")
        print(f"{'='*70}\n")
        
        print(f"Found {len(accounts)} account(s) in database:\n")
        
        for i, account in enumerate(accounts, 1):
            print(f"{i}. {account.email}")
            print(f"   Current Type: {account.account_type if account.account_type else 'Not set'}")
            print(f"   Provider: {account.provider}")
            print(f"   Active: {account.is_active}")
            print()
        
        # Interactive selection
        print(f"\n{'Strategy':^70}")
        print(f"{'-'*70}")
        print("We need to designate:")
        print("  • 1 account as 'warmup' (the account being warmed up)")
        print("  • Remaining accounts as 'pool' (recipients for warmup emails)")
        print(f"{'-'*70}\n")
        
        if len(accounts) < 2:
            print("⚠️  Warning: You need at least 2 accounts for effective warmup!")
            print("   - 1 warmup account (sender)")
            print("   - At least 1 pool account (recipient)")
            print("\nCurrent setup will work but is not optimal for warmup.\n")
        
        # Ask user to select warmup account
        while True:
            try:
                choice = input(f"Enter the number of the account to warmup (1-{len(accounts)}): ").strip()
                choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(accounts):
                    warmup_account = accounts[choice_idx]
                    break
                else:
                    print(f"❌ Invalid choice. Please enter a number between 1 and {len(accounts)}")
            except ValueError:
                print("❌ Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\n\n❌ Setup cancelled by user.")
                return
        
        # Ask for warmup target
        print(f"\n{'Warmup Configuration':^70}")
        print(f"{'-'*70}")
        default_target = 50
        target_input = input(f"Target emails per day at full warmup (default: {default_target}): ").strip()
        
        try:
            warmup_target = int(target_input) if target_input else default_target
        except ValueError:
            print(f"⚠️  Invalid input, using default: {default_target}")
            warmup_target = default_target
        
        # Calculate initial daily limit (10% of target, minimum 5)
        initial_daily_limit = max(5, int(warmup_target * 0.1))
        
        print(f"\nWarmup will start with {initial_daily_limit} emails/day")
        print(f"and gradually ramp up to {warmup_target} emails/day")
        
        # Confirm
        print(f"\n{'='*70}")
        print(f"{'CONFIGURATION SUMMARY':^70}")
        print(f"{'='*70}\n")
        print(f"Warmup Account: {warmup_account.email}")
        print(f"  • Type: warmup")
        print(f"  • Initial daily limit: {initial_daily_limit} emails/day")
        print(f"  • Target: {warmup_target} emails/day")
        print(f"  • Warmup day: 1 (starting)")
        print()
        
        pool_accounts = [acc for acc in accounts if acc.id != warmup_account.id]
        if pool_accounts:
            print(f"Pool Accounts ({len(pool_accounts)}):")
            for acc in pool_accounts:
                print(f"  • {acc.email}")
        else:
            print("⚠️  No pool accounts (warmup will have no recipients!)")
        
        print(f"\n{'='*70}\n")
        
        confirm = input("Proceed with this configuration? (yes/no): ").strip().lower()
        
        if confirm not in ['yes', 'y']:
            print("\n❌ Setup cancelled.")
            return
        
        # Apply configuration
        print("\n⏳ Applying configuration...")
        
        # Configure warmup account
        warmup_account.account_type = 'warmup'
        warmup_account.warmup_target = warmup_target
        warmup_account.warmup_day = 1  # Start at day 1
        warmup_account.daily_limit = initial_daily_limit
        warmup_account.is_active = True
        
        # Configure pool accounts
        for acc in pool_accounts:
            acc.account_type = 'pool'
            acc.warmup_target = 0  # Pool accounts don't need targets
            acc.warmup_day = 0  # Not in warmup
            acc.is_active = True  # Keep active for receiving emails
        
        db.session.commit()
        
        print("\n✓ Configuration applied successfully!\n")
        print(f"{'='*70}")
        print(f"{'NEXT STEPS':^70}")
        print(f"{'='*70}\n")
        print("1. The warmup account will now send emails to the pool accounts")
        print("2. Emails will be sent according to the Celery Beat schedule")
        print("3. The daily limit will automatically increase as warmup progresses:")
        print("   • Days 1-7: 10% of target (gradual start)")
        print("   • Days 8-14: 25% of target (building trust)")
        print("   • Days 15-21: 50% of target (increasing volume)")
        print("   • Days 22-28: 75% of target (near target)")
        print("   • Days 29+: 100% of target (full warmup)")
        print("4. Warmup day advances automatically at midnight each day")
        print("5. Monitor progress using: python scripts/check_accounts.py")
        print(f"\n{'='*70}\n")

if __name__ == "__main__":
    setup_warmup_config()