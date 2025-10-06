#!/usr/bin/env python3
"""
Integration Test - Complete Workflow

This script tests the complete email warmup workflow:
1. Content generation
2. Human timing decision
3. Simulated email sending
4. Full day simulation
5. Multi-day warmup simulation

Run: python tests/test_integration.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.services.ai_service import AIService
from app.services.human_timing_service import HumanTimingService

# Load environment variables
load_dotenv()


def test_complete_email_flow():
    """Test complete flow: content generation → timing decision → email creation"""
    
    print("=" * 80)
    print("INTEGRATION TEST: COMPLETE EMAIL FLOW")
    print("=" * 80)
    print()
    
    # Initialize services
    use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
    api_key = os.getenv('OPENAI_API_KEY')
    
    ai_service = AIService(api_key=api_key, use_ai=use_ai)
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    print("✓ Services initialized")
    print(f"   AI Service: {'Enabled' if ai_service.ai_available else 'Disabled (template-only)'}")
    print(f"   Timing Service: {timing_service.timezone}")
    print()
    
    # Simulate warmup account state
    warmup_day = 10
    warmup_target = 50
    daily_limit = 12  # Phase 2: 25% of target
    emails_sent_today = 3
    
    # Calculate current state
    if warmup_day <= 7:
        phase = f"Phase 1: Initial warmup (Day {warmup_day}/7)"
    elif warmup_day <= 14:
        phase = f"Phase 2: Building trust (Day {warmup_day}/14)"
    elif warmup_day <= 21:
        phase = f"Phase 3: Increasing volume (Day {warmup_day}/21)"
    elif warmup_day <= 28:
        phase = f"Phase 4: Near target (Day {warmup_day}/28)"
    else:
        phase = f"Phase 5: Full warmup (Day {warmup_day})"
    
    print("📊 Warmup Account State:")
    print(f"   Warmup day: {warmup_day}")
    print(f"   Phase: {phase}")
    print(f"   Daily limit: {daily_limit}")
    print(f"   Emails sent today: {emails_sent_today}/{daily_limit}")
    print(f"   Target: {warmup_target} emails/day")
    print()
    
    # Simulate current time (Monday 2 PM)
    current_time = tz.localize(datetime(2025, 10, 6, 14, 15, 0))
    last_sent = tz.localize(datetime(2025, 10, 6, 13, 42, 0))
    
    print(f"⏰ Timing Information:")
    print(f"   Current time: {current_time.strftime('%A, %B %d, %Y at %I:%M %p')}")
    print(f"   Last email sent: {last_sent.strftime('%I:%M %p')} ({(current_time - last_sent).total_seconds() / 60:.0f} minutes ago)")
    print()
    
    # Step 1: Check if we should send
    print("=" * 80)
    print("STEP 1: TIMING DECISION")
    print("=" * 80)
    print()
    
    should_send, reason = timing_service.should_send_now(
        last_sent=last_sent,
        min_interval_minutes=5,
        daily_limit=daily_limit,
        emails_sent_today=emails_sent_today
    )
    
    print(f"Decision: {'✓ SEND EMAIL' if should_send else '✗ WAIT'}")
    print(f"Reason: {reason}")
    print()
    
    if not should_send:
        print("⏭️  Skipping email generation (timing decision was WAIT)")
        print()
        return
    
    # Step 2: Generate email content
    print("=" * 80)
    print("STEP 2: CONTENT GENERATION")
    print("=" * 80)
    print()
    
    content = ai_service.generate_email_content()
    
    print(f"Generation method: {content['generation_type']}")
    print(f"Template type: {content.get('template_type', 'N/A')}")
    print()
    print(f"Subject: {content['subject']}")
    print(f"Content: {content['content']}")
    print()
    
    # Step 3: Create email record (simulated)
    print("=" * 80)
    print("STEP 3: EMAIL RECORD CREATION")
    print("=" * 80)
    print()
    
    # Select recipient (random pool account)
    pool_emails = ['pool1@example.com', 'pool2@example.com', 'pool3@example.com']
    import random
    recipient = random.choice(pool_emails)
    
    # Generate tracking pixel ID
    tracking_pixel_id = str(uuid.uuid4())
    
    email_record = {
        'to_address': recipient,
        'subject': content['subject'],
        'content': content['content'],
        'tracking_pixel_id': tracking_pixel_id,
        'sent_at': current_time.isoformat(),
        'is_opened': False,
        'is_replied': False
    }
    
    print("✓ Email record created:")
    print(f"   To: {email_record['to_address']}")
    print(f"   Subject: {email_record['subject']}")
    print(f"   Tracking ID: {email_record['tracking_pixel_id']}")
    print(f"   Sent at: {current_time.strftime('%I:%M %p')}")
    print()
    
    # Step 4: Update account state
    print("=" * 80)
    print("STEP 4: ACCOUNT STATE UPDATE")
    print("=" * 80)
    print()
    
    emails_sent_today += 1
    
    print(f"✓ Account updated:")
    print(f"   Emails sent today: {emails_sent_today}/{daily_limit}")
    print(f"   Progress: {emails_sent_today/daily_limit*100:.1f}%")
    print(f"   Remaining: {daily_limit - emails_sent_today} emails")
    print()
    
    # Step 5: Calculate next send time (estimate)
    print("=" * 80)
    print("STEP 5: NEXT SEND ESTIMATE")
    print("=" * 80)
    print()
    
    delay_seconds = timing_service.calculate_send_delay(base_interval_minutes=10)
    next_check = current_time + timedelta(seconds=delay_seconds)
    
    print(f"Next check in: {delay_seconds // 60}m {delay_seconds % 60}s")
    print(f"Next check time: {next_check.strftime('%I:%M %p')}")
    print()
    
    print("=" * 80)
    print("✓ COMPLETE FLOW TEST SUCCESSFUL")
    print("=" * 80)
    print()


def test_full_day_simulation():
    """Simulate a complete day of email sending"""
    
    print("=" * 80)
    print("INTEGRATION TEST: FULL DAY SIMULATION")
    print("=" * 80)
    print()
    
    # Initialize services
    use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
    api_key = os.getenv('OPENAI_API_KEY')
    
    ai_service = AIService(api_key=api_key, use_ai=use_ai)
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Account state
    daily_limit = 12
    emails_sent = 0
    last_sent = None
    
    # Start simulation at 9 AM
    current_time = tz.localize(datetime(2025, 10, 6, 9, 0, 0))
    end_time = tz.localize(datetime(2025, 10, 6, 18, 0, 0))
    
    emails = []
    check_count = 0
    
    print(f"📅 Simulating: Monday, October 6, 2025")
    print(f"   Business hours: 9:00 AM - 6:00 PM")
    print(f"   Daily limit: {daily_limit} emails")
    print(f"   Check interval: Every 15 minutes")
    print()
    
    print("Time  | Sent | Decision | Reason")
    print("-" * 80)
    
    while current_time <= end_time and emails_sent < daily_limit:
        check_count += 1
        
        # Check if we should send
        should_send, reason = timing_service.should_send_now(
            last_sent=last_sent,
            min_interval_minutes=5,
            daily_limit=daily_limit,
            emails_sent_today=emails_sent
        )
        
        decision = "SEND ✓" if should_send else "WAIT  "
        short_reason = reason[:45] + "..." if len(reason) > 45 else reason
        
        print(f"{current_time.strftime('%H:%M')} | {emails_sent:2d}/{daily_limit:2d} | {decision} | {short_reason}")
        
        if should_send:
            # Generate content
            content = ai_service.generate_email_content()
            
            # Create email record
            email = {
                'time': current_time,
                'subject': content['subject'],
                'content': content['content'][:50] + "...",
                'generation_type': content['generation_type']
            }
            
            emails.append(email)
            emails_sent += 1
            last_sent = current_time
        
        # Move to next check (15 minutes)
        current_time += timedelta(minutes=15)
    
    print()
    print("=" * 80)
    print("DAY SIMULATION SUMMARY")
    print("=" * 80)
    print()
    
    print(f"📊 Statistics:")
    print(f"   Total checks: {check_count}")
    print(f"   Emails sent: {emails_sent}/{daily_limit} ({emails_sent/daily_limit*100:.1f}%)")
    print(f"   Success rate: {emails_sent/check_count*100:.1f}% of checks resulted in send")
    print()
    
    if emails:
        print(f"📧 Emails Sent ({len(emails)}):")
        print()
        for i, email in enumerate(emails, 1):
            print(f"   {i:2d}. {email['time'].strftime('%H:%M')} - {email['subject']}")
            print(f"       Type: {email['generation_type']}")
        print()
        
        # Calculate intervals
        if len(emails) > 1:
            intervals = [(emails[i]['time'] - emails[i-1]['time']).total_seconds() / 60 
                        for i in range(1, len(emails))]
            print(f"⏱️  Send Intervals:")
            print(f"   Average: {sum(intervals) / len(intervals):.1f} minutes")
            print(f"   Min: {min(intervals):.1f} minutes")
            print(f"   Max: {max(intervals):.1f} minutes")
            print()
    
    print("=" * 80)
    print("✓ FULL DAY SIMULATION SUCCESSFUL")
    print("=" * 80)
    print()


def test_multi_day_simulation():
    """Simulate 7 days of warmup with phase progression"""
    
    print("=" * 80)
    print("INTEGRATION TEST: MULTI-DAY SIMULATION (7 DAYS)")
    print("=" * 80)
    print()
    
    # Initialize services
    use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
    api_key = os.getenv('OPENAI_API_KEY')
    
    ai_service = AIService(api_key=api_key, use_ai=use_ai)
    timing_service = HumanTimingService()
    tz = timing_service.timezone
    
    # Warmup configuration
    warmup_target = 50
    warmup_day = 0
    
    total_emails = 0
    daily_results = []
    
    print(f"Configuration:")
    print(f"   Warmup target: {warmup_target} emails/day")
    print(f"   Simulation: 7 days (Phase 1)")
    print()
    
    for day_num in range(1, 8):
        # Advance warmup day
        warmup_day += 1
        
        # Calculate daily limit (Phase 1: 10% of target, min 5)
        daily_limit = max(5, int(warmup_target * 0.1))
        
        # Simulate the day
        date = datetime(2025, 10, 6) + timedelta(days=day_num - 1)
        
        # Skip weekends
        if date.weekday() >= 5:
            print(f"Day {warmup_day} ({date.strftime('%A')}) - SKIPPED (weekend)")
            continue
        
        print(f"Day {warmup_day} ({date.strftime('%A')})")
        print(f"   Daily limit: {daily_limit}")
        
        # Simulate email sending
        emails_sent = 0
        last_sent = None
        current_time = tz.localize(datetime.combine(date, datetime.min.time().replace(hour=9)))
        end_time = tz.localize(datetime.combine(date, datetime.min.time().replace(hour=18)))
        
        while current_time <= end_time and emails_sent < daily_limit:
            should_send, _ = timing_service.should_send_now(
                last_sent=last_sent,
                min_interval_minutes=5,
                daily_limit=daily_limit,
                emails_sent_today=emails_sent
            )
            
            if should_send:
                emails_sent += 1
                last_sent = current_time
            
            current_time += timedelta(minutes=15)
        
        total_emails += emails_sent
        daily_results.append({
            'day': warmup_day,
            'date': date,
            'limit': daily_limit,
            'sent': emails_sent,
            'completion': emails_sent / daily_limit * 100
        })
        
        print(f"   Sent: {emails_sent}/{daily_limit} ({emails_sent/daily_limit*100:.1f}%)")
        print()
    
    print("=" * 80)
    print("7-DAY SIMULATION SUMMARY")
    print("=" * 80)
    print()
    
    print(f"📊 Overall Statistics:")
    print(f"   Total emails sent: {total_emails}")
    print(f"   Days simulated: {len(daily_results)}")
    print(f"   Average per day: {total_emails / len(daily_results):.1f}")
    print()
    
    print(f"📈 Daily Breakdown:")
    for result in daily_results:
        print(f"   Day {result['day']}: {result['sent']}/{result['limit']} ({result['completion']:.1f}%)")
    
    print()
    print("=" * 80)
    print("✓ MULTI-DAY SIMULATION SUCCESSFUL")
    print("=" * 80)
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Integration tests for email warmup')
    parser.add_argument('--test', type=str, 
                       choices=['flow', 'day', 'multiday', 'all'],
                       default='all',
                       help='Which test to run')
    
    args = parser.parse_args()
    
    if args.test == 'all':
        test_complete_email_flow()
        print("\n\n")
        test_full_day_simulation()
        print("\n\n")
        test_multi_day_simulation()
    elif args.test == 'flow':
        test_complete_email_flow()
    elif args.test == 'day':
        test_full_day_simulation()
    elif args.test == 'multiday':
        test_multi_day_simulation()
    
    print()
    print("=" * 80)
    print("ALL INTEGRATION TESTS COMPLETED ✓")
    print("=" * 80)
