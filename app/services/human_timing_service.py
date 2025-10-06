import random
from datetime import datetime, timedelta, time
from typing import List, Tuple
import pytz
import logging

logger = logging.getLogger(__name__)

class HumanTimingService:
    """
    Service to generate human-like email sending schedules
    Focuses on proactive schedule generation rather than reactive checking
    """
    
    def __init__(self, timezone='Asia/Kolkata'):
        self.timezone = pytz.timezone(timezone)
        
        # Business hours configuration (24-hour format)
        self.business_hours = {
            'start': 9,   # 9 AM
            'end': 18,    # 6 PM
        }
        
        # Activity periods with time ranges and email distribution
        self.activity_periods = {
            'peak': {
                'ranges': [(9, 11), (14, 16)],  # 9-11 AM, 2-4 PM
                'weight': 0.60,  # 60% of daily emails
                'description': 'Peak activity hours'
            },
            'normal': {
                'ranges': [(11, 12), (16, 18)],  # 11-12 PM, 4-6 PM
                'weight': 0.30,  # 30% of daily emails
                'description': 'Normal activity hours'
            },
            'low': {
                'ranges': [(12, 14)],  # 12-2 PM (lunch)
                'weight': 0.10,  # 10% of daily emails
                'description': 'Low activity hours (lunch)'
            }
        }
    
    def is_business_hours(self, dt: datetime = None) -> bool:
        """Check if given time is within business hours"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        # Convert to local timezone if needed
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        elif dt.tzinfo != self.timezone:
            dt = dt.astimezone(self.timezone)
        
        # Skip weekends (Monday=0, Sunday=6)
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        hour = dt.hour
        return self.business_hours['start'] <= hour < self.business_hours['end']
    
    def is_weekend(self, dt: datetime = None) -> bool:
        """Check if given date is a weekend"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        elif dt.tzinfo != self.timezone:
            dt = dt.astimezone(self.timezone)
        
        return dt.weekday() >= 5
    
    def get_activity_period(self, dt: datetime) -> str:
        """Determine which activity period a given time falls into"""
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        elif dt.tzinfo != self.timezone:
            dt = dt.astimezone(self.timezone)
        
        hour = dt.hour
        
        for period_name, period_info in self.activity_periods.items():
            for start, end in period_info['ranges']:
                if start <= hour < end:
                    return period_name
        
        return 'outside'
    
    def generate_daily_schedule(self, daily_limit: int, target_date: datetime = None) -> List[Tuple[datetime, str]]:
        """
        Generate a complete daily schedule for sending emails
        
        Args:
            daily_limit: Number of emails to send today
            target_date: Date to generate schedule for (defaults to today)
        
        Returns:
            List of tuples: (scheduled_datetime, activity_period)
        """
        if target_date is None:
            target_date = datetime.now(self.timezone)
        
        # Ensure timezone awareness
        if target_date.tzinfo is None:
            target_date = self.timezone.localize(target_date)
        elif target_date.tzinfo != self.timezone:
            target_date = target_date.astimezone(self.timezone)
        
        # Skip weekends
        if self.is_weekend(target_date):
            logger.info(f"Skipping schedule generation for weekend: {target_date.date()}")
            return []
        
        # Set to business day start
        target_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        schedule = []
        
        # Calculate emails per period based on weights
        peak_count = int(daily_limit * self.activity_periods['peak']['weight'])
        normal_count = int(daily_limit * self.activity_periods['normal']['weight'])
        low_count = daily_limit - peak_count - normal_count  # Remaining goes to low
        
        logger.info(f"Generating schedule for {daily_limit} emails: Peak={peak_count}, Normal={normal_count}, Low={low_count}")
        
        # Generate times for each period
        schedule.extend(self._generate_period_times('peak', peak_count, target_date))
        schedule.extend(self._generate_period_times('normal', normal_count, target_date))
        schedule.extend(self._generate_period_times('low', low_count, target_date))
        
        # Sort by time
        schedule.sort(key=lambda x: x[0])
        
        # Add randomization to avoid patterns - shuffle slightly
        schedule = self._add_temporal_randomness(schedule)
        
        logger.info(f"Generated {len(schedule)} scheduled send times for {target_date.date()}")
        
        return schedule
    
    def _generate_period_times(self, period: str, count: int, base_date: datetime) -> List[Tuple[datetime, str]]:
        """Generate random send times within a specific activity period"""
        if count <= 0:
            return []
        
        period_info = self.activity_periods.get(period)
        if not period_info:
            return []
        
        times = []
        
        # Get all time ranges for this period
        all_ranges = period_info['ranges']
        
        # Calculate total minutes available in this period
        total_minutes = sum((end - start) * 60 for start, end in all_ranges)
        
        # Generate random times
        for _ in range(count):
            # Pick a random range
            time_range = random.choice(all_ranges)
            start_hour, end_hour = time_range
            
            # Generate random time within this range
            start_minute = start_hour * 60
            end_minute = end_hour * 60
            random_minute = random.randint(start_minute, end_minute - 1)
            
            hour = random_minute // 60
            minute = random_minute % 60
            
            # Add some second-level randomness
            second = random.randint(0, 59)
            
            scheduled_time = base_date.replace(hour=hour, minute=minute, second=second)
            times.append((scheduled_time, period))
        
        return times
    
    def _add_temporal_randomness(self, schedule: List[Tuple[datetime, str]]) -> List[Tuple[datetime, str]]:
        """
        Add slight temporal randomness to avoid perfectly even distribution
        Humans don't send emails at perfectly random intervals - there are micro-patterns
        """
        if len(schedule) <= 1:
            return schedule
        
        randomized = []
        
        for i, (scheduled_time, period) in enumerate(schedule):
            # Add small random offset (±3 minutes)
            offset_minutes = random.randint(-3, 3)
            offset_seconds = random.randint(-30, 30)
            
            new_time = scheduled_time + timedelta(minutes=offset_minutes, seconds=offset_seconds)
            
            # Ensure it stays within business hours
            if new_time.hour < self.business_hours['start']:
                new_time = new_time.replace(hour=self.business_hours['start'], minute=0)
            elif new_time.hour >= self.business_hours['end']:
                new_time = new_time.replace(hour=self.business_hours['end'] - 1, minute=59)
            
            randomized.append((new_time, period))
        
        # Re-sort after randomization
        randomized.sort(key=lambda x: x[0])
        
        return randomized
    
    def get_next_business_day(self, from_date: datetime = None) -> datetime:
        """Get the next business day (skip weekends)"""
        if from_date is None:
            from_date = datetime.now(self.timezone)
        
        if from_date.tzinfo is None:
            from_date = self.timezone.localize(from_date)
        
        next_day = from_date + timedelta(days=1)
        
        # Skip weekends
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        
        # Set to start of business day
        next_day = next_day.replace(hour=self.business_hours['start'], minute=0, second=0, microsecond=0)
        
        return next_day
    
    def calculate_schedule_stats(self, schedule: List[Tuple[datetime, str]]) -> dict:
        """Calculate statistics about a schedule"""
        if not schedule:
            return {
                'total': 0,
                'peak': 0,
                'normal': 0,
                'low': 0
            }
        
        stats = {
            'total': len(schedule),
            'peak': sum(1 for _, period in schedule if period == 'peak'),
            'normal': sum(1 for _, period in schedule if period == 'normal'),
            'low': sum(1 for _, period in schedule if period == 'low'),
            'first_send': schedule[0][0].strftime('%H:%M:%S'),
            'last_send': schedule[-1][0].strftime('%H:%M:%S'),
        }
        
        # Calculate intervals
        if len(schedule) > 1:
            intervals = []
            for i in range(1, len(schedule)):
                diff = (schedule[i][0] - schedule[i-1][0]).total_seconds() / 60
                intervals.append(diff)
            
            stats['avg_interval_minutes'] = sum(intervals) / len(intervals)
            stats['min_interval_minutes'] = min(intervals)
            stats['max_interval_minutes'] = max(intervals)
        
        return stats
    
    def get_human_delay_description(self, delay_seconds: int) -> str:
        """Get human-readable description of delay"""
        minutes = delay_seconds // 60
        seconds = delay_seconds % 60
        
        if minutes == 0:
            return f"{seconds} seconds"
        elif seconds == 0:
            return f"{minutes} minutes"
        else:
            return f"{minutes}m {seconds}s"
