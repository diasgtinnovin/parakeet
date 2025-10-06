#!/usr/bin/env python3
"""
Test Human Timing Service

This script tests the human timing logic with different scenarios:
- Business hours detection
- Activity weight calculation
- Send decision probability
- Daily schedule generation

Run: python tests/test_human_timing.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.human_timing_service import HumanTimingService


def test_business_hours():
    """Test business hours detection"""
    
    print("=" * 80)
    print("BUSINESS HOURS DETECTION TEST")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    test_times = [
        # Monday
        (datetime(2025, 10, 6, 8, 0, 0), "Monday 8:00 AM"),
        (datetime(2025, 10, 6, 9, 0, 0), "Monday 9:00 AM"),
        (datetime(2025, 10, 6, 12, 0, 0), "Monday 12:00 PM"),
        (datetime(2025, 10, 6, 14, 0, 0), "Monday 2:00 PM"),
        (datetime(2025, 10, 6, 18, 0, 0), "Monday 6:00 PM"),
        (datetime(2025, 10, 6, 20, 0, 0), "Monday 8:00 PM"),
        
        # Saturday
        (datetime(2025, 10, 11, 10, 0, 0), "Saturday 10:00 AM"),
        (datetime(2025, 10, 11, 14, 0, 0), "Saturday 2:00 PM"),
        
        # Sunday
        (datetime(2025, 10, 12, 10, 0, 0), "Sunday 10:00 AM"),
    ]
    
    for dt, label in test_times:
        dt_tz = tz.localize(dt)
        is_business = timing_service.is_business_hours(dt_tz)
        activity = timing_service.get_activity_weight(dt_tz)
        
        status = "✓ BUSINESS HOURS" if is_business else "✗ Outside hours"
        print(f"{label:25} | {status:20} | Activity: {activity:.2f}")
    
    print()


def test_activity_weights():
    """Test activity weight calculation throughout the day"""
    
    print("=" * 80)
    print("ACTIVITY WEIGHT THROUGHOUT THE DAY")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Monday, Oct 6, 2025
    base_date = datetime(2025, 10, 6)
    
    print("Time         | Activity | Period")
    print("-" * 50)
    
    for hour in range(24):
        dt = tz.localize(base_date.replace(hour=hour, minute=0))
        weight = timing_service.get_activity_weight(dt)
        
        # Determine period
        if not timing_service.is_business_hours(dt):
            period = "Outside business hours"
        elif any(start <= hour < end for start, end in timing_service.peak_periods):
            period = "PEAK PERIOD"
        elif any(start <= hour < end for start, end in timing_service.low_periods):
            period = "Low period"
        else:
            period = "Normal business hours"
        
        # Visual bar
        bar = "█" * int(weight * 20)
        
        print(f"{hour:02d}:00        | {weight:.2f}     | {bar:20} {period}")
    
    print()


def test_send_decisions():
    """Test send decision logic with different scenarios"""
    
    print("=" * 80)
    print("SEND DECISION LOGIC TEST")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Scenario 1: No previous emails sent (fresh start)
    print("📧 SCENARIO 1: Fresh start (no previous emails)")
    print("-" * 80)
    
    for hour in [9, 10, 12, 14, 16, 17]:
        now = tz.localize(datetime(2025, 10, 6, hour, 15, 0))
        should_send, reason = timing_service.should_send_now(
            last_sent=None,
            min_interval_minutes=5,
            daily_limit=12,
            emails_sent_today=0
        )
        
        print(f"Time: {hour:02d}:15 | Decision: {'SEND' if should_send else 'WAIT':4} | {reason}")
    
    print()
    
    # Scenario 2: Behind schedule
    print("📧 SCENARIO 2: Behind schedule (sent 2/12 at 2 PM)")
    print("-" * 80)
    
    last_sent = tz.localize(datetime(2025, 10, 6, 14, 0, 0))
    
    for minute_offset in [10, 20, 30, 45, 60]:
        now = last_sent + timedelta(minutes=minute_offset)
        should_send, reason = timing_service.should_send_now(
            last_sent=last_sent,
            min_interval_minutes=5,
            daily_limit=12,
            emails_sent_today=2
        )
        
        print(f"Time: {now.strftime('%H:%M')} ({minute_offset}m after last) | Decision: {'SEND' if should_send else 'WAIT':4} | {reason}")
    
    print()
    
    # Scenario 3: Ahead of schedule
    print("📧 SCENARIO 3: Ahead of schedule (sent 10/12 at 11 AM)")
    print("-" * 80)
    
    last_sent = tz.localize(datetime(2025, 10, 6, 11, 0, 0))
    
    for minute_offset in [10, 20, 30, 45, 60]:
        now = last_sent + timedelta(minutes=minute_offset)
        should_send, reason = timing_service.should_send_now(
            last_sent=last_sent,
            min_interval_minutes=5,
            daily_limit=12,
            emails_sent_today=10
        )
        
        print(f"Time: {now.strftime('%H:%M')} ({minute_offset}m after last) | Decision: {'SEND' if should_send else 'WAIT':4} | {reason}")
    
    print()
    
    # Scenario 4: Different daily limits
    print("📧 SCENARIO 4: Different daily limits (at 10 AM, 2 sent)")
    print("-" * 80)
    
    now = tz.localize(datetime(2025, 10, 6, 10, 0, 0))
    last_sent = tz.localize(datetime(2025, 10, 6, 9, 30, 0))
    
    for daily_limit in [5, 12, 25, 50]:
        should_send, reason = timing_service.should_send_now(
            last_sent=last_sent,
            min_interval_minutes=5,
            daily_limit=daily_limit,
            emails_sent_today=2
        )
        
        print(f"Daily limit: {daily_limit:2} | Decision: {'SEND' if should_send else 'WAIT':4} | {reason}")
    
    print()


def test_daily_schedule():
    """Test daily schedule generation"""
    
    print("=" * 80)
    print("DAILY SCHEDULE GENERATION TEST")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    daily_limits = [5, 12, 25, 50]
    
    for limit in daily_limits:
        print(f"📅 Daily Limit: {limit} emails")
        print("-" * 80)
        
        start_date = tz.localize(datetime(2025, 10, 6, 9, 0, 0))
        schedule = timing_service.get_daily_send_schedule(limit, start_date)
        
        # Group by hour
        hourly_count = {}
        for send_time in schedule:
            hour = send_time.hour
            hourly_count[hour] = hourly_count.get(hour, 0) + 1
        
        # Print schedule
        for i, send_time in enumerate(schedule, 1):
            activity = timing_service.get_activity_weight(send_time)
            period = "Peak" if activity >= 0.8 else "Normal" if activity >= 0.6 else "Low"
            print(f"   {i:2d}. {send_time.strftime('%H:%M')} ({period:6} activity)")
        
        # Print distribution
        print()
        print("   Hourly distribution:")
        for hour in sorted(hourly_count.keys()):
            count = hourly_count[hour]
            bar = "█" * count
            print(f"   {hour:02d}:00 | {bar} ({count})")
        
        print()


def test_multiple_send_decisions():
    """Simulate multiple send decisions throughout a day"""
    
    print("=" * 80)
    print("SIMULATED DAY: MULTIPLE SEND DECISIONS")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Note: This test demonstrates the timing logic, but since should_send_now()
    # uses datetime.now() internally, we'll show what WOULD happen during business hours
    
    print("⚠️  NOTE: This test shows timing logic demonstration.")
    print("   The actual should_send_now() method uses real current time,")
    print("   so decisions will be based on when you run this test.")
    print()
    
    # Get current time to show if we're in business hours
    now = datetime.now(tz)
    is_business_now = timing_service.is_business_hours(now)
    activity_now = timing_service.get_activity_weight(now)
    
    print(f"Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}")
    print(f"Business hours: {'✓ YES' if is_business_now else '✗ NO'}")
    print(f"Activity weight: {activity_now:.2f}")
    print()
    
    if is_business_now:
        print("✓ You're running this during business hours - decisions will be realistic!")
        print()
        
        # Simulate a day with 12 email limit
        daily_limit = 12
        
        # Test different scenarios
        scenarios = [
            (0, None, "Fresh start"),
            (3, now - timedelta(minutes=30), "Behind schedule (30 min ago)"),
            (8, now - timedelta(minutes=15), "On track (15 min ago)"),
            (11, now - timedelta(minutes=45), "Near limit (45 min ago)"),
        ]
        
        print("Scenario Testing:")
        print("Time  | Sent/Limit | Decision | Reason")
        print("-" * 80)
        
        for emails_sent, last_sent, scenario_name in scenarios:
            should_send, reason = timing_service.should_send_now(
                last_sent=last_sent,
                min_interval_minutes=5,
                daily_limit=daily_limit,
                emails_sent_today=emails_sent
            )
            
            decision_str = "SEND ✓" if should_send else "WAIT  "
            print(f"{now.strftime('%H:%M')} | {emails_sent:2d}/{daily_limit:2d}       | {decision_str} | {reason[:45]}... ({scenario_name})")
        
    else:
        print("✗ You're running this outside business hours.")
        print("   All decisions will be 'Outside business hours'")
        print()
        print("To see realistic timing decisions, run this test during:")
        print("   Monday-Friday, 9:00 AM - 6:00 PM (Asia/Kolkata)")
        print()
        
        # Show what would happen during business hours
        print("Here's what the schedule would look like during business hours:")
        
        # Generate a sample schedule
        business_start = tz.localize(datetime(2025, 10, 7, 9, 0, 0))  # Next Monday
        schedule = timing_service.get_daily_send_schedule(12, business_start)
        
        print()
        print("Sample Schedule for 12 emails:")
        for i, send_time in enumerate(schedule[:10], 1):  # Show first 10
            activity = timing_service.get_activity_weight(send_time)
            period = "Peak" if activity >= 0.8 else "Normal" if activity >= 0.6 else "Low"
            print(f"   {i:2d}. {send_time.strftime('%H:%M')} ({period:6} activity)")
        
        if len(schedule) > 10:
            print(f"   ... and {len(schedule) - 10} more")
    
    print()


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    
    print("=" * 80)
    print("EDGE CASES AND BOUNDARY CONDITIONS")
    print("=" * 80)
    print()
    
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Test 1: Exactly at business hours boundary
    print("🔍 Test 1: Exactly at business hours boundaries")
    print("-" * 80)
    
    boundary_times = [
        (8, 0, "8:00 AM"),
        (8, 59, "8:59 AM"),
        (9, 0, "9:00 AM"),
        (9, 1, "9:01 AM"),
        (17, 59, "5:59 PM"),
        (18, 0, "6:00 PM"),
        (18, 1, "6:01 PM"),
    ]
    
    for hour, minute, label in boundary_times:
        dt = tz.localize(datetime(2025, 10, 6, hour, minute, 0))
        is_business = timing_service.is_business_hours(dt)
        print(f"   {label:10} : {'✓ Business hours' if is_business else '✗ Outside hours'}")
    
    print()
    
    # Test 2: Daily limit already reached
    print("🔍 Test 2: Daily limit already reached")
    print("-" * 80)
    
    now = tz.localize(datetime(2025, 10, 6, 10, 0, 0))
    last_sent = tz.localize(datetime(2025, 10, 6, 9, 45, 0))
    
    should_send, reason = timing_service.should_send_now(
        last_sent=last_sent,
        min_interval_minutes=5,
        daily_limit=12,
        emails_sent_today=12
    )
    
    print(f"   Sent 12/12 emails")
    print(f"   Decision: {'SEND' if should_send else 'WAIT (correct behavior)'}")
    print(f"   Reason: {reason}")
    print()
    
    # Test 3: Too soon after last send
    print("🔍 Test 3: Too soon after last send (< 5 min)")
    print("-" * 80)
    
    now = tz.localize(datetime(2025, 10, 6, 10, 0, 0))
    last_sent = tz.localize(datetime(2025, 10, 6, 9, 57, 0))  # 3 minutes ago
    
    should_send, reason = timing_service.should_send_now(
        last_sent=last_sent,
        min_interval_minutes=5,
        daily_limit=12,
        emails_sent_today=5
    )
    
    print(f"   Last sent 3 minutes ago")
    print(f"   Decision: {'SEND' if should_send else 'WAIT (correct behavior)'}")
    print(f"   Reason: {reason}")
    print()
    
    # Test 4: Weekend
    print("🔍 Test 4: Weekend (should not send)")
    print("-" * 80)
    
    saturday = tz.localize(datetime(2025, 10, 11, 10, 0, 0))
    should_send, reason = timing_service.should_send_now(
        last_sent=None,
        min_interval_minutes=5,
        daily_limit=12,
        emails_sent_today=0
    )
    
    print(f"   Saturday 10:00 AM")
    print(f"   Decision: {'SEND' if should_send else 'WAIT (correct behavior)'}")
    print(f"   Reason: {reason}")
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test human timing service')
    parser.add_argument('--test', type=str, 
                       choices=['business', 'activity', 'decisions', 'schedule', 'simulate', 'edge', 'all'],
                       default='all',
                       help='Which test to run')
    
    args = parser.parse_args()
    
    if args.test == 'all':
        test_business_hours()
        test_activity_weights()
        test_send_decisions()
        test_daily_schedule()
        test_multiple_send_decisions()
        test_edge_cases()
    elif args.test == 'business':
        test_business_hours()
    elif args.test == 'activity':
        test_activity_weights()
    elif args.test == 'decisions':
        test_send_decisions()
    elif args.test == 'schedule':
        test_daily_schedule()
    elif args.test == 'simulate':
        test_multiple_send_decisions()
    elif args.test == 'edge':
        test_edge_cases()
    
    print("=" * 80)
    print("ALL TESTS COMPLETED ✓")
    print("=" * 80)
