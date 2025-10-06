#!/usr/bin/env python3
"""
Warmup Simulation Test

This script simulates a complete 30-day warmup cycle WITHOUT waiting:
- Simulates daily progression
- Tests warmup phase transitions
- Tests daily limit calculations
- Simulates email sending throughout each day
- Provides complete analytics

Run: python tests/test_warmup_simulation.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.services.human_timing_service import HumanTimingService
from app.services.ai_service import AIService

# Load environment variables
load_dotenv()


class WarmupSimulator:
    """Simulates a complete warmup cycle"""
    
    def __init__(self, warmup_target=50, timezone='Asia/Kolkata'):
        self.warmup_target = warmup_target
        self.warmup_day = 0
        self.daily_limit = 0
        self.timing_service = HumanTimingService(timezone=timezone)
        self.tz = pytz.timezone(timezone)
        
        # Statistics
        self.total_emails_sent = 0
        self.daily_stats = []
        self.phase_transitions = []
        
    def calculate_daily_limit(self):
        """Calculate daily limit based on warmup day (same logic as Account model)"""
        if self.warmup_day <= 0:
            return 0
        
        target = self.warmup_target
        day = self.warmup_day
        
        # Phase 1: Days 1-7 → 10% of target (min 5)
        if day <= 7:
            return max(5, int(target * 0.1))
        
        # Phase 2: Days 8-14 → 25% of target (min 10)
        elif day <= 14:
            return max(10, int(target * 0.25))
        
        # Phase 3: Days 15-21 → 50% of target (min 15)
        elif day <= 21:
            return max(15, int(target * 0.5))
        
        # Phase 4: Days 22-28 → 75% of target (min 20)
        elif day <= 28:
            return max(20, int(target * 0.75))
        
        # Phase 5: Days 29+ → 100% of target
        else:
            return target
    
    def get_warmup_phase(self):
        """Get current warmup phase"""
        if self.warmup_day <= 0:
            return "Not started"
        
        day = self.warmup_day
        if day <= 7:
            return f"Phase 1: Initial warmup (Day {day}/7)"
        elif day <= 14:
            return f"Phase 2: Building trust (Day {day}/14)"
        elif day <= 21:
            return f"Phase 3: Increasing volume (Day {day}/21)"
        elif day <= 28:
            return f"Phase 4: Near target (Day {day}/28)"
        else:
            return f"Phase 5: Full warmup (Day {day})"
    
    def simulate_day(self, date):
        """Simulate email sending for one day"""
        emails_sent = 0
        last_sent = None
        send_times = []
        check_attempts = 0
        
        # Start at 9 AM
        current_time = self.tz.localize(datetime.combine(date, datetime.min.time().replace(hour=9)))
        end_time = self.tz.localize(datetime.combine(date, datetime.min.time().replace(hour=18)))
        
        # Check every 15 minutes
        check_interval = timedelta(minutes=15)
        
        while current_time <= end_time and emails_sent < self.daily_limit:
            check_attempts += 1
            
            should_send, reason = self.timing_service.should_send_now(
                last_sent=last_sent,
                min_interval_minutes=5,
                daily_limit=self.daily_limit,
                emails_sent_today=emails_sent
            )
            
            if should_send:
                emails_sent += 1
                last_sent = current_time
                send_times.append(current_time)
            
            current_time += check_interval
        
        return {
            'emails_sent': emails_sent,
            'send_times': send_times,
            'check_attempts': check_attempts,
            'completion_rate': (emails_sent / self.daily_limit * 100) if self.daily_limit > 0 else 0
        }
    
    def advance_day(self):
        """Advance to next day"""
        old_day = self.warmup_day
        old_phase = self.get_warmup_phase()
        old_limit = self.daily_limit
        
        self.warmup_day += 1
        self.daily_limit = self.calculate_daily_limit()
        
        new_phase = self.get_warmup_phase()
        
        # Check for phase transition
        if old_day > 0 and self.warmup_day in [8, 15, 22, 29]:
            self.phase_transitions.append({
                'day': self.warmup_day,
                'from_phase': old_phase,
                'to_phase': new_phase,
                'from_limit': old_limit,
                'to_limit': self.daily_limit
            })
        
        return old_limit, self.daily_limit
    
    def run_simulation(self, num_days=30, verbose=False):
        """Run complete warmup simulation"""
        
        print("=" * 80)
        print("WARMUP SIMULATION STARTING")
        print("=" * 80)
        print()
        print(f"Configuration:")
        print(f"   Warmup target: {self.warmup_target} emails/day")
        print(f"   Simulation days: {num_days}")
        print(f"   Timezone: {self.tz}")
        print()
        
        start_date = datetime(2025, 10, 6)  # Monday
        
        for day_num in range(1, num_days + 1):
            # Advance warmup day
            old_limit, new_limit = self.advance_day()
            
            # Simulate the day
            date = start_date + timedelta(days=day_num - 1)
            
            if verbose or day_num == 1 or day_num % 7 == 0 or day_num == num_days:
                print(f"📅 Day {day_num} - {date.strftime('%A, %B %d')}")
                print(f"   Phase: {self.get_warmup_phase()}")
                print(f"   Daily limit: {self.daily_limit}")
            
            # Skip weekends
            if date.weekday() >= 5:
                if verbose:
                    print(f"   ⏭️  Skipped (weekend)")
                    print()
                continue
            
            # Simulate sending
            day_result = self.simulate_day(date)
            
            self.total_emails_sent += day_result['emails_sent']
            self.daily_stats.append({
                'day': day_num,
                'date': date,
                'phase': self.get_warmup_phase(),
                'daily_limit': self.daily_limit,
                'emails_sent': day_result['emails_sent'],
                'completion_rate': day_result['completion_rate'],
                'send_times': day_result['send_times'],
                'check_attempts': day_result['check_attempts']
            })
            
            if verbose or day_num == 1 or day_num % 7 == 0 or day_num == num_days:
                print(f"   Emails sent: {day_result['emails_sent']}/{self.daily_limit} ({day_result['completion_rate']:.1f}%)")
                print(f"   Check attempts: {day_result['check_attempts']}")
                
                if day_result['send_times'] and len(day_result['send_times']) <= 10:
                    print(f"   Send times: {', '.join(t.strftime('%H:%M') for t in day_result['send_times'])}")
                
                print()
        
        return self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive simulation report"""
        
        print("=" * 80)
        print("SIMULATION COMPLETE - COMPREHENSIVE REPORT")
        print("=" * 80)
        print()
        
        # Overall stats
        print("📊 OVERALL STATISTICS")
        print("-" * 80)
        print(f"   Total days simulated: {len(self.daily_stats)}")
        print(f"   Final warmup day: {self.warmup_day}")
        print(f"   Final phase: {self.get_warmup_phase()}")
        print(f"   Final daily limit: {self.daily_limit}/{self.warmup_target} ({self.daily_limit/self.warmup_target*100:.1f}%)")
        print(f"   Total emails sent: {self.total_emails_sent}")
        print()
        
        # Phase transitions
        if self.phase_transitions:
            print("🎯 PHASE TRANSITIONS")
            print("-" * 80)
            for transition in self.phase_transitions:
                print(f"   Day {transition['day']}:")
                print(f"      {transition['from_phase']} → {transition['to_phase']}")
                print(f"      Daily limit: {transition['from_limit']} → {transition['to_limit']} emails")
                print()
        
        # Phase-by-phase breakdown
        print("📈 PHASE-BY-PHASE BREAKDOWN")
        print("-" * 80)
        
        phases = {
            'Phase 1': [s for s in self.daily_stats if s['day'] <= 7],
            'Phase 2': [s for s in self.daily_stats if 8 <= s['day'] <= 14],
            'Phase 3': [s for s in self.daily_stats if 15 <= s['day'] <= 21],
            'Phase 4': [s for s in self.daily_stats if 22 <= s['day'] <= 28],
            'Phase 5': [s for s in self.daily_stats if s['day'] >= 29]
        }
        
        for phase_name, stats in phases.items():
            if stats:
                total_sent = sum(s['emails_sent'] for s in stats)
                total_limit = sum(s['daily_limit'] for s in stats)
                avg_completion = sum(s['completion_rate'] for s in stats) / len(stats)
                
                print(f"   {phase_name}:")
                print(f"      Days: {stats[0]['day']} - {stats[-1]['day']}")
                print(f"      Total sent: {total_sent}/{total_limit} ({total_sent/total_limit*100:.1f}%)")
                print(f"      Avg completion rate: {avg_completion:.1f}%")
                print(f"      Avg emails/day: {total_sent/len(stats):.1f}")
                print()
        
        # Weekly summary
        print("📅 WEEKLY SUMMARY")
        print("-" * 80)
        
        weeks = defaultdict(list)
        for stat in self.daily_stats:
            week_num = (stat['day'] - 1) // 7 + 1
            weeks[week_num].append(stat)
        
        for week_num, stats in sorted(weeks.items()):
            total_sent = sum(s['emails_sent'] for s in stats)
            total_limit = sum(s['daily_limit'] for s in stats)
            avg_limit = sum(s['daily_limit'] for s in stats) / len(stats)
            
            print(f"   Week {week_num} (Days {stats[0]['day']}-{stats[-1]['day']}):")
            print(f"      Total sent: {total_sent}/{total_limit} emails")
            print(f"      Average daily limit: {avg_limit:.1f}")
            print(f"      Days: {', '.join(str(s['day']) for s in stats)}")
            print()
        
        # Daily completion rates
        print("✓ DAILY COMPLETION RATES")
        print("-" * 80)
        
        completion_ranges = {
            '100%': [s for s in self.daily_stats if s['completion_rate'] == 100],
            '90-99%': [s for s in self.daily_stats if 90 <= s['completion_rate'] < 100],
            '80-89%': [s for s in self.daily_stats if 80 <= s['completion_rate'] < 90],
            '70-79%': [s for s in self.daily_stats if 70 <= s['completion_rate'] < 80],
            '<70%': [s for s in self.daily_stats if s['completion_rate'] < 70]
        }
        
        for range_name, stats in completion_ranges.items():
            if stats:
                percentage = len(stats) / len(self.daily_stats) * 100
                print(f"   {range_name:10} : {len(stats):2} days ({percentage:5.1f}%)")
        
        print()
        
        # Sample send times from different phases
        print("⏰ SAMPLE SEND TIMES (Phase 1 vs Phase 5)")
        print("-" * 80)
        
        phase1_day = next((s for s in self.daily_stats if s['day'] <= 7), None)
        phase5_day = next((s for s in self.daily_stats if s['day'] >= 29), None)
        
        if phase1_day:
            print(f"   Phase 1 (Day {phase1_day['day']}) - {phase1_day['emails_sent']} emails:")
            for i, time in enumerate(phase1_day['send_times'][:10], 1):
                print(f"      {i:2d}. {time.strftime('%H:%M')}")
            print()
        
        if phase5_day:
            print(f"   Phase 5 (Day {phase5_day['day']}) - {phase5_day['emails_sent']} emails:")
            for i, time in enumerate(phase5_day['send_times'][:10], 1):
                print(f"      {i:2d}. {time.strftime('%H:%M')}")
            if len(phase5_day['send_times']) > 10:
                print(f"      ... and {len(phase5_day['send_times']) - 10} more")
            print()
        
        # Success metrics
        print("🎉 SUCCESS METRICS")
        print("-" * 80)
        
        total_possible = sum(s['daily_limit'] for s in self.daily_stats)
        overall_completion = (self.total_emails_sent / total_possible * 100) if total_possible > 0 else 0
        
        print(f"   ✓ Reached Phase 5: {'Yes ✓' if self.warmup_day >= 29 else 'No'}")
        print(f"   ✓ Reached target limit: {'Yes ✓' if self.daily_limit >= self.warmup_target else f'No ({self.daily_limit}/{self.warmup_target})'}")
        print(f"   ✓ Overall completion rate: {overall_completion:.1f}%")
        print(f"   ✓ Total emails sent: {self.total_emails_sent}")
        print(f"   ✓ Phase transitions: {len(self.phase_transitions)}")
        print()
        
        return {
            'total_emails': self.total_emails_sent,
            'completion_rate': overall_completion,
            'phase_transitions': self.phase_transitions,
            'daily_stats': self.daily_stats
        }


def run_quick_simulation():
    """Run a quick 7-day simulation"""
    print("Running Quick 7-Day Simulation (Phase 1 only)")
    print()
    
    simulator = WarmupSimulator(warmup_target=50)
    simulator.run_simulation(num_days=7, verbose=True)


def run_full_simulation():
    """Run complete 30-day simulation"""
    print("Running Full 30-Day Simulation")
    print()
    
    simulator = WarmupSimulator(warmup_target=50)
    simulator.run_simulation(num_days=30, verbose=False)


def run_custom_simulation(days, target):
    """Run custom simulation"""
    print(f"Running Custom Simulation: {days} days, target {target} emails/day")
    print()
    
    simulator = WarmupSimulator(warmup_target=target)
    simulator.run_simulation(num_days=days, verbose=True)


def compare_targets():
    """Compare different warmup targets"""
    print("=" * 80)
    print("COMPARING DIFFERENT WARMUP TARGETS")
    print("=" * 80)
    print()
    
    targets = [20, 50, 100]
    
    for target in targets:
        print(f"\n{'='*80}")
        print(f"Target: {target} emails/day")
        print(f"{'='*80}\n")
        
        simulator = WarmupSimulator(warmup_target=target)
        result = simulator.run_simulation(num_days=30, verbose=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simulate email warmup cycle')
    parser.add_argument('--mode', type=str, 
                       choices=['quick', 'full', 'custom', 'compare'],
                       default='full',
                       help='Simulation mode')
    parser.add_argument('--days', type=int, default=30, help='Number of days for custom simulation')
    parser.add_argument('--target', type=int, default=50, help='Target emails/day for custom simulation')
    
    args = parser.parse_args()
    
    if args.mode == 'quick':
        run_quick_simulation()
    elif args.mode == 'full':
        run_full_simulation()
    elif args.mode == 'custom':
        run_custom_simulation(args.days, args.target)
    elif args.mode == 'compare':
        compare_targets()
    
    print()
    print("=" * 80)
    print("SIMULATION COMPLETED SUCCESSFULLY ✓")
    print("=" * 80)
