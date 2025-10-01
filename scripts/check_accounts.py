#!/usr/bin/env python3
"""Script to check existing accounts in the database"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.account import Account

def check_accounts():
    app = create_app()
    
    with app.app_context():
        accounts = Account.query.all()
        warmup_accounts = [acc for acc in accounts if hasattr(acc, 'account_type') and acc.account_type == 'warmup']
        pool_accounts = [acc for acc in accounts if hasattr(acc, 'account_type') and acc.account_type == 'pool']
        
        print(f"\n{'='*80}")
        print(f"{'WARMUP CONFIGURATION STATUS':^80}")
        print(f"{'='*80}\n")
        print(f"Total accounts: {len(accounts)}")
        print(f"Warmup accounts: {len(warmup_accounts)}")
        print(f"Pool accounts: {len(pool_accounts)}")
        print(f"\n{'-'*80}\n")
        
        if warmup_accounts:
            print(f"{'WARMUP ACCOUNTS':^80}")
            print(f"{'-'*80}\n")
            for account in warmup_accounts:
                current_limit = account.calculate_daily_limit()
                progress = (current_limit / account.warmup_target) * 100 if account.warmup_target > 0 else 0
                
                print(f"📧 {account.email}")
                print(f"   Type: {account.account_type}")
                print(f"   Provider: {account.provider}")
                print(f"   Active: {'✓' if account.is_active else '✗'}")
                print(f"   Current Phase: {account.get_warmup_phase()}")
                print(f"   Daily Limit: {current_limit} emails/day (Target: {account.warmup_target})")
                print(f"   Progress: {progress:.1f}% of target volume")
                print(f"   Warmup Score: {account.warmup_score}/100")
                print(f"   Created: {account.created_at.strftime('%Y-%m-%d %H:%M')}")
                
                # Show ramping schedule
                print(f"   📈 Ramping Schedule:")
                phases = [
                    (7, "10%", "Initial warmup"),
                    (14, "25%", "Building trust"), 
                    (21, "50%", "Increasing volume"),
                    (28, "75%", "Near target"),
                    (35, "100%", "Full warmup")
                ]
                
                for day, percent, desc in phases:
                    if account.warmup_day <= day:
                        status = "🔄 Current" if account.warmup_day <= day and (day == 7 or account.warmup_day > day - 7) else "⏳ Upcoming"
                        limit_at_phase = max(5, int(account.warmup_target * float(percent.strip('%')) / 100))
                        print(f"      Day {day}: {percent} ({limit_at_phase} emails/day) - {desc} {status if account.warmup_day <= day else '✅ Completed'}")
                        if account.warmup_day <= day:
                            break
                print()
        
        if pool_accounts:
            print(f"{'POOL ACCOUNTS (Recipients)':^80}")
            print(f"{'-'*80}\n")
            for i, account in enumerate(pool_accounts, 1):
                print(f"{i}. {account.email}")
                print(f"   Provider: {account.provider}")
                print(f"   Active: {'✓' if account.is_active else '✗'}")
                print()
        
        # Show unconfigured accounts
        unconfigured = [acc for acc in accounts if not hasattr(acc, 'account_type') or not acc.account_type or acc.account_type not in ['warmup', 'pool']]
        if unconfigured:
            print(f"{'UNCONFIGURED ACCOUNTS':^80}")
            print(f"{'-'*80}\n")
            print("⚠️  These accounts need configuration. Run: python scripts/setup_warmup_config.py\n")
            for account in unconfigured:
                print(f"  • {account.email}")
            print()
        
        print(f"{'='*80}\n")
        
        # Summary and recommendations
        if not warmup_accounts:
            print("⚠️  WARNING: No warmup accounts configured!")
            print("   Run: python scripts/setup_warmup_config.py\n")
        elif not pool_accounts:
            print("⚠️  WARNING: No pool accounts! Warmup needs recipients.")
            print("   Add more accounts or reconfigure with: python scripts/setup_warmup_config.py\n")
        elif len(pool_accounts) < 3:
            print("⚠️  RECOMMENDATION: Add more pool accounts for better warmup.")
            print(f"   Current: {len(pool_accounts)} pool accounts")
            print("   Recommended: At least 5-10 pool accounts\n")
        else:
            print("✓ Configuration looks good!")
            print(f"  • {len(warmup_accounts)} warmup account(s)")
            print(f"  • {len(pool_accounts)} pool account(s)")
            print("\nNext: Ensure Celery Beat is running to start warmup.\n")

if __name__ == "__main__":
    check_accounts()