#!/usr/bin/env python3
"""
Test script for the new scheduling system
Validates schedule generation, distribution, and timing logic
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
from app.services.human_timing_service import HumanTimingService
from app.tasks.email_tasks import generate_schedule_for_account
from datetime import datetime, date, timedelta
import pytz

def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")

def test_timing_service():
    """Test HumanTimingService schedule generation"""
    print_header("Testing HumanTimingService")
    
    # Test with different timezones
    timezones = ['Asia/Kolkata', 'America/New_York', 'Europe/London']
    
    for tz_name in timezones:
        print(f"\n📍 Testing timezone: {tz_name}")
        timing_service = HumanTimingService(timezone=tz_name)
        
        # Generate a test schedule
        tz = pytz.timezone(tz_name)
        today = datetime.now(tz).replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Skip if weekend
        if timing_service.is_weekend(today):
            print(f"   ⚠️  Today is a weekend in {tz_name}, skipping test")
            continue
        
        # Generate schedule for 15 emails
        daily_limit = 15
        schedule = timing_service.generate_daily_schedule(daily_limit, today)
        
        if not schedule:
            print(f"   ❌ No schedule generated!")
            continue
        
        # Calculate statistics
        stats = timing_service.calculate_schedule_stats(schedule)
        
        print(f"   ✓ Generated {stats['total']} scheduled times")
        print(f"   Distribution: Peak={stats['peak']}, Normal={stats['normal']}, Low={stats['low']}")
        print(f"   First send: {stats['first_send']}, Last send: {stats['last_send']}")
        
        if 'avg_interval_minutes' in stats:
            print(f"   Avg interval: {stats['avg_interval_minutes']:.1f} min "
                  f"(range: {stats['min_interval_minutes']:.1f} - {stats['max_interval_minutes']:.1f})")
        
        # Check distribution percentages
        peak_pct = (stats['peak'] / stats['total']) * 100
        normal_pct = (stats['normal'] / stats['total']) * 100
        low_pct = (stats['low'] / stats['total']) * 100
        
        print(f"   Percentages: Peak={peak_pct:.0f}%, Normal={normal_pct:.0f}%, Low={low_pct:.0f}%")
        
        # Validate distribution (should be close to 60/30/10)
        if 55 <= peak_pct <= 65 and 25 <= normal_pct <= 35:
            print(f"   ✓ Distribution is within expected range")
        else:
            print(f"   ⚠️  Distribution is outside expected range (target: 60/30/10)")
        
        # Show sample schedule
        print(f"\n   Sample schedule times:")
        for i, (scheduled_time, period) in enumerate(schedule[:5], 1):
            print(f"     {i}. {scheduled_time.strftime('%H:%M:%S')} ({period})")
        if len(schedule) > 5:
            print(f"     ... ({len(schedule) - 5} more)")

def test_schedule_generation_for_accounts():
    """Test schedule generation for actual accounts"""
    print_header("Testing Schedule Generation for Accounts")
    
    app = create_app()
    
    with app.app_context():
        # Get warmup accounts
        warmup_accounts = Account.query.filter_by(
            is_active=True,
            account_type='warmup'
        ).all()
        
        if not warmup_accounts:
            print("⚠️  No warmup accounts found in database")
            print("   Add accounts and configure warmup using:")
            print("   python scripts/setup_warmup_config.py")
            return
        
        print(f"Found {len(warmup_accounts)} warmup account(s)\n")
        
        for account in warmup_accounts:
            print(f"\n📧 Account: {account.email}")
            print(f"   Timezone: {account.timezone or 'Asia/Kolkata'}")
            print(f"   Warmup Phase: {account.get_warmup_phase()}")
            print(f"   Daily Limit: {account.calculate_daily_limit()} emails")
            
            # Get today's date
            tz = pytz.timezone(account.timezone or 'Asia/Kolkata')
            today = datetime.now(tz).date()
            
            # Check for existing schedule
            existing_count = EmailSchedule.query.filter(
                EmailSchedule.account_id == account.id,
                EmailSchedule.schedule_date == today
            ).count()
            
            if existing_count > 0:
                print(f"   ℹ️  Schedule already exists for today ({existing_count} entries)")
                
                # Show schedule details
                schedules = EmailSchedule.query.filter(
                    EmailSchedule.account_id == account.id,
                    EmailSchedule.schedule_date == today
                ).order_by(EmailSchedule.scheduled_time).all()
                
                pending = sum(1 for s in schedules if s.status == 'pending')
                sent = sum(1 for s in schedules if s.status == 'sent')
                failed = sum(1 for s in schedules if s.status == 'failed')
                
                print(f"   Status: Pending={pending}, Sent={sent}, Failed={failed}")
                
                # Show next few pending
                next_pending = [s for s in schedules if s.status == 'pending'][:3]
                if next_pending:
                    print(f"   Next pending sends:")
                    for s in next_pending:
                        local_time = s.scheduled_time.replace(tzinfo=pytz.utc).astimezone(tz)
                        print(f"     • {local_time.strftime('%H:%M:%S')} ({s.activity_period})")
            else:
                print(f"   ℹ️  No schedule for today, generating test schedule...")
                
                # Generate schedule
                try:
                    count = generate_schedule_for_account(account, today)
                    if count > 0:
                        print(f"   ✓ Generated {count} schedule entries")
                    else:
                        print(f"   ⚠️  No schedules generated (might be weekend)")
                except Exception as e:
                    print(f"   ❌ Error generating schedule: {e}")

def test_weekend_handling():
    """Test that weekends are properly skipped"""
    print_header("Testing Weekend Handling")
    
    timing_service = HumanTimingService()
    
    # Test a known Saturday and Sunday
    tz = pytz.timezone('Asia/Kolkata')
    
    # Find next Saturday
    today = datetime.now(tz)
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7
    
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    
    print(f"Testing with:")
    print(f"  Saturday: {saturday.strftime('%Y-%m-%d (%A)')}")
    print(f"  Sunday: {sunday.strftime('%Y-%m-%d (%A)')}")
    
    # Test weekend detection
    is_sat_weekend = timing_service.is_weekend(saturday)
    is_sun_weekend = timing_service.is_weekend(sunday)
    
    print(f"\nWeekend detection:")
    print(f"  Saturday is weekend: {is_sat_weekend} {'✓' if is_sat_weekend else '❌'}")
    print(f"  Sunday is weekend: {is_sun_weekend} {'✓' if is_sun_weekend else '❌'}")
    
    # Test schedule generation
    sat_schedule = timing_service.generate_daily_schedule(10, saturday)
    sun_schedule = timing_service.generate_daily_schedule(10, sunday)
    
    print(f"\nSchedule generation:")
    print(f"  Saturday schedule: {len(sat_schedule)} emails {'✓' if len(sat_schedule) == 0 else '❌'}")
    print(f"  Sunday schedule: {len(sun_schedule)} emails {'✓' if len(sun_schedule) == 0 else '❌'}")
    
    if len(sat_schedule) == 0 and len(sun_schedule) == 0:
        print(f"\n✓ Weekend handling works correctly!")
    else:
        print(f"\n❌ Weekend handling has issues!")

def test_business_hours():
    """Test business hours detection"""
    print_header("Testing Business Hours Detection")
    
    timing_service = HumanTimingService()
    tz = pytz.timezone('Asia/Kolkata')
    
    # Test different hours
    test_times = [
        (8, 0, False, "Before business hours"),
        (9, 0, True, "Start of business hours"),
        (12, 30, True, "During lunch (still business hours)"),
        (17, 59, True, "End of business hours"),
        (18, 0, False, "After business hours"),
        (22, 0, False, "Evening"),
    ]
    
    today = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    
    # Make sure it's a weekday
    while today.weekday() >= 5:
        today += timedelta(days=1)
    
    print(f"Testing with weekday: {today.strftime('%Y-%m-%d (%A)')}\n")
    
    all_correct = True
    for hour, minute, expected, description in test_times:
        test_time = today.replace(hour=hour, minute=minute)
        result = timing_service.is_business_hours(test_time)
        status = '✓' if result == expected else '❌'
        
        print(f"  {test_time.strftime('%H:%M')} - {description}: {result} {status}")
        
        if result != expected:
            all_correct = False
    
    if all_correct:
        print(f"\n✓ Business hours detection works correctly!")
    else:
        print(f"\n❌ Business hours detection has issues!")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("  NEW SCHEDULING SYSTEM - VALIDATION TESTS")
    print("="*80)
    
    try:
        test_timing_service()
        test_weekend_handling()
        test_business_hours()
        test_schedule_generation_for_accounts()
        
        print_header("Test Summary")
        print("✓ All tests completed!")
        print("\nNext steps:")
        print("  1. Review the test results above")
        print("  2. Run: python scripts/create_schedule_migration.py")
        print("  3. Start Celery workers and beat scheduler")
        print("  4. Monitor logs for schedule generation")
        print("  5. Use: python scripts/check_accounts.py to monitor status")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
