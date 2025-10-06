#!/usr/bin/env python3
"""
Manually generate schedules for testing
Useful for testing without waiting for midnight
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.account import Account
from app.models.email_schedule import EmailSchedule
from app.tasks.email_tasks import generate_schedule_for_account
from datetime import datetime, date
import pytz

def manual_generate_schedules(target_date=None, account_email=None):
    """
    Manually generate schedules for testing
    
    Args:
        target_date: Date to generate for (defaults to today)
        account_email: Specific account email (None = all accounts)
    """
    app = create_app()
    
    with app.app_context():
        # Get target date
        if target_date is None:
            target_date = date.today()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        print(f"{'='*80}")
        print(f"  Manual Schedule Generation for {target_date}")
        print(f"{'='*80}\n")
        
        # Get accounts
        query = Account.query.filter_by(is_active=True, account_type='warmup')
        if account_email:
            query = query.filter_by(email=account_email)
        
        accounts = query.all()
        
        if not accounts:
            print("❌ No matching warmup accounts found")
            if account_email:
                print(f"   Looking for: {account_email}")
            return
        
        print(f"Found {len(accounts)} warmup account(s)\n")
        
        total_created = 0
        
        for account in accounts:
            print(f"📧 {account.email}")
            print(f"   Timezone: {account.timezone or 'Asia/Kolkata'}")
            print(f"   Phase: {account.get_warmup_phase()}")
            print(f"   Daily Limit: {account.calculate_daily_limit()} emails")
            
            # Check for existing schedules
            existing = EmailSchedule.query.filter(
                EmailSchedule.account_id == account.id,
                EmailSchedule.schedule_date == target_date
            ).all()
            
            if existing:
                print(f"   ⚠️  Found {len(existing)} existing schedules for {target_date}")
                
                # Ask if should delete and regenerate
                response = input(f"   Delete and regenerate? (y/N): ")
                if response.lower() == 'y':
                    for schedule in existing:
                        db.session.delete(schedule)
                    db.session.commit()
                    print(f"   ✓ Deleted {len(existing)} existing schedules")
                else:
                    print(f"   Skipping...")
                    print()
                    continue
            
            # Generate new schedule
            try:
                count = generate_schedule_for_account(account, target_date)
                
                if count > 0:
                    print(f"   ✓ Generated {count} schedule entries")
                    total_created += count
                    
                    # Show sample schedules
                    new_schedules = EmailSchedule.query.filter(
                        EmailSchedule.account_id == account.id,
                        EmailSchedule.schedule_date == target_date
                    ).order_by(EmailSchedule.scheduled_time).all()
                    
                    # Show first 5
                    tz = pytz.timezone(account.timezone or 'Asia/Kolkata')
                    print(f"   Sample times:")
                    for i, s in enumerate(new_schedules[:5], 1):
                        local_time = s.scheduled_time.replace(tzinfo=pytz.utc).astimezone(tz)
                        print(f"     {i}. {local_time.strftime('%H:%M:%S')} ({s.activity_period})")
                    
                    if len(new_schedules) > 5:
                        print(f"     ... and {len(new_schedules) - 5} more")
                    
                    # Show distribution
                    peak = sum(1 for s in new_schedules if s.activity_period == 'peak')
                    normal = sum(1 for s in new_schedules if s.activity_period == 'normal')
                    low = sum(1 for s in new_schedules if s.activity_period == 'low')
                    
                    print(f"   Distribution: Peak={peak}, Normal={normal}, Low={low}")
                else:
                    print(f"   ⚠️  No schedules generated (might be weekend or zero limit)")
            
            except Exception as e:
                print(f"   ❌ Error: {e}")
            
            print()
        
        print(f"{'='*80}")
        print(f"✓ Total schedules created: {total_created}")
        print(f"{'='*80}\n")
        
        if total_created > 0:
            print("Next steps:")
            print("  1. Check schedules in database")
            print("  2. Monitor Celery logs for email sending")
            print("  3. Verify emails are sent at scheduled times")
            print("\nUseful commands:")
            print("  python scripts/check_accounts.py")
            print("  tail -f celery.log | grep -E '(schedule|send)'")

def show_existing_schedules(account_email=None, target_date=None):
    """Show existing schedules"""
    app = create_app()
    
    with app.app_context():
        if target_date is None:
            target_date = date.today()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        print(f"{'='*80}")
        print(f"  Schedules for {target_date}")
        print(f"{'='*80}\n")
        
        query = EmailSchedule.query.join(Account).filter(
            EmailSchedule.schedule_date == target_date
        )
        
        if account_email:
            query = query.filter(Account.email == account_email)
        
        schedules = query.order_by(Account.email, EmailSchedule.scheduled_time).all()
        
        if not schedules:
            print("No schedules found")
            return
        
        current_account = None
        for schedule in schedules:
            if current_account != schedule.account.email:
                if current_account is not None:
                    print()
                current_account = schedule.account.email
                print(f"📧 {schedule.account.email} ({schedule.account.timezone})")
            
            tz = pytz.timezone(schedule.account.timezone or 'Asia/Kolkata')
            local_time = schedule.scheduled_time.replace(tzinfo=pytz.utc).astimezone(tz)
            
            status_emoji = {
                'pending': '⏳',
                'sent': '✓',
                'failed': '❌',
                'skipped': '⊘'
            }.get(schedule.status, '?')
            
            print(f"   {status_emoji} {local_time.strftime('%H:%M:%S')} "
                  f"({schedule.activity_period:6s}) - {schedule.status}")
        
        print(f"\n{'='*80}")
        print(f"Total: {len(schedules)} schedules")
        
        # Statistics
        by_status = {}
        for s in schedules:
            by_status[s.status] = by_status.get(s.status, 0) + 1
        
        print("\nBy status:")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Manually generate or view email schedules')
    parser.add_argument('--action', choices=['generate', 'view'], default='generate',
                       help='Action to perform')
    parser.add_argument('--email', type=str, help='Specific account email')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.action == 'generate':
        manual_generate_schedules(args.date, args.email)
    else:
        show_existing_schedules(args.email, args.date)
