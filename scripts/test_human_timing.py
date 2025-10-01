#!/usr/bin/env python3
"""Test script for human timing functionality"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.human_timing_service import HumanTimingService

def test_human_timing():
    print(f"\n{'='*80}")
    print(f"{'HUMAN TIMING SERVICE TEST':^80}")
    print(f"{'='*80}\n")
    
    timing_service = HumanTimingService()
    
    # Test current time
    now = datetime.now(timing_service.timezone)
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Is business hours: {timing_service.is_business_hours(now)}")
    print(f"Activity weight: {timing_service.get_activity_weight(now):.2f}")
    
    # Test should_send_now
    should_send, reason = timing_service.should_send_now()
    print(f"Should send now: {should_send} - {reason}")
    
    # Test delay calculation
    delay = timing_service.calculate_send_delay(base_interval_minutes=10)
    delay_desc = timing_service.get_human_delay_description(delay)
    print(f"Calculated delay: {delay_desc}")
    
    print(f"\n{'-'*80}")
    print(f"{'DAILY SCHEDULE PREVIEW':^80}")
    print(f"{'-'*80}\n")
    
    # Generate sample schedule for different daily limits
    for daily_limit in [5, 10, 25, 50]:
        print(f"Schedule for {daily_limit} emails/day:")
        schedule = timing_service.get_daily_send_schedule(daily_limit)
        
        for i, send_time in enumerate(schedule[:8], 1):  # Show first 8 times
            activity_weight = timing_service.get_activity_weight(send_time)
            period = "Peak" if activity_weight >= 0.8 else "Normal" if activity_weight >= 0.6 else "Low"
            print(f"  {i:2d}. {send_time.strftime('%H:%M')} ({period} activity)")
        
        if len(schedule) > 8:
            print(f"  ... and {len(schedule) - 8} more times")
        print()
    
    print(f"{'-'*80}")
    print(f"{'ACTIVITY PATTERNS THROUGHOUT THE DAY':^80}")
    print(f"{'-'*80}\n")
    
    # Show activity patterns for different hours
    base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print("Hour | Activity | Period")
    print("-----|----------|--------")
    
    for hour in range(24):
        test_time = base_date.replace(hour=hour)
        activity = timing_service.get_activity_weight(test_time)
        
        if activity >= 0.8:
            period = "Peak"
        elif activity >= 0.6:
            period = "Normal"
        elif activity >= 0.3:
            period = "Low"
        else:
            period = "Very Low"
        
        print(f"{hour:2d}:00 | {activity:8.2f} | {period}")
    
    print(f"\n{'-'*80}")
    print(f"{'BUSINESS HOURS CONFIGURATION':^80}")
    print(f"{'-'*80}\n")
    
    print(f"Business hours: {timing_service.business_hours['start']}:00 - {timing_service.business_hours['end']}:00")
    print(f"Lunch break: {timing_service.business_hours['lunch_start']}:00 - {timing_service.business_hours['lunch_end']}:00")
    print(f"Timezone: {timing_service.timezone}")
    
    print("\nPeak periods:")
    for start, end in timing_service.peak_periods:
        print(f"  {start}:00 - {end}:00")
    
    print("\nLow activity periods:")
    for start, end in timing_service.low_periods:
        print(f"  {start}:00 - {end}:00")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    test_human_timing()