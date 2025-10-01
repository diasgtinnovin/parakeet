import random
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional
import pytz
import logging

logger = logging.getLogger(__name__)

class HumanTimingService:
    """Service to generate human-like email sending patterns"""
    
    def __init__(self, timezone='Asia/Kolkata'):
        self.timezone = pytz.timezone(timezone)
        
        # Business hours configuration (24-hour format)
        self.business_hours = {
            'start': 9,   # 9 AM
            'end': 18,    # 6 PM
            'lunch_start': 12,  # 12 PM
            'lunch_end': 14,    # 2 PM
        }
        
        # Peak activity periods (higher probability of sending)
        self.peak_periods = [
            (9, 11),   # Morning peak: 9-11 AM
            (14, 16),  # Afternoon peak: 2-4 PM
        ]
        
        # Low activity periods (lower probability)
        self.low_periods = [
            (12, 14),  # Lunch time: 12-2 PM
            (17, 18),  # End of day: 5-6 PM
        ]
    
    def is_business_hours(self, dt: datetime = None) -> bool:
        """Check if given time is within business hours"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        # Convert to local timezone if needed
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        elif dt.tzinfo != self.timezone:
            dt = dt.astimezone(self.timezone)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        hour = dt.hour
        return self.business_hours['start'] <= hour < self.business_hours['end']
    
    def get_activity_weight(self, dt: datetime = None) -> float:
        """Get activity weight for given time (higher = more likely to send)"""
        if dt is None:
            dt = datetime.now(self.timezone)
        
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        elif dt.tzinfo != self.timezone:
            dt = dt.astimezone(self.timezone)
        
        hour = dt.hour
        
        # Weekend - very low activity
        if dt.weekday() >= 5:
            return 0.1
        
        # Outside business hours - very low activity
        if not self.is_business_hours(dt):
            return 0.2
        
        # Peak periods - high activity
        for start, end in self.peak_periods:
            if start <= hour < end:
                return 1.0
        
        # Low periods - reduced activity
        for start, end in self.low_periods:
            if start <= hour < end:
                return 0.4
        
        # Normal business hours
        return 0.7
    
    def calculate_send_delay(self, base_interval_minutes: int = 10) -> int:
        """Calculate human-like delay in seconds before sending next email"""
        now = datetime.now(self.timezone)
        activity_weight = self.get_activity_weight(now)
        
        # Base delay with human variation
        base_delay = base_interval_minutes * 60  # Convert to seconds
        
        # Add randomness based on activity level
        if activity_weight >= 0.8:  # Peak hours - more frequent
            variation = random.uniform(0.5, 1.2)  # 50% to 120% of base
        elif activity_weight >= 0.6:  # Normal hours
            variation = random.uniform(0.8, 1.5)  # 80% to 150% of base
        elif activity_weight >= 0.3:  # Low activity
            variation = random.uniform(1.2, 2.0)  # 120% to 200% of base
        else:  # Very low activity (weekends, after hours)
            variation = random.uniform(2.0, 4.0)  # 200% to 400% of base
        
        delay = int(base_delay * variation)
        
        # Add small random jitter (±30 seconds)
        jitter = random.randint(-30, 30)
        delay += jitter
        
        # Ensure minimum delay of 30 seconds
        delay = max(30, delay)
        
        logger.debug(f"Calculated send delay: {delay}s (activity_weight: {activity_weight:.2f})")
        return delay
    
    def get_next_send_time(self, base_interval_minutes: int = 10) -> datetime:
        """Get the next optimal time to send an email"""
        now = datetime.now(self.timezone)
        delay_seconds = self.calculate_send_delay(base_interval_minutes)
        next_time = now + timedelta(seconds=delay_seconds)
        
        # If next time falls outside business hours, adjust to next business day
        if not self.is_business_hours(next_time):
            next_time = self._adjust_to_business_hours(next_time)
        
        return next_time
    
    def _adjust_to_business_hours(self, dt: datetime) -> datetime:
        """Adjust datetime to fall within business hours"""
        # If it's weekend, move to next Monday
        while dt.weekday() >= 5:
            dt += timedelta(days=1)
        
        # If it's too early, move to business start
        if dt.hour < self.business_hours['start']:
            dt = dt.replace(hour=self.business_hours['start'], minute=0, second=0)
            # Add some randomness to start time (0-30 minutes)
            dt += timedelta(minutes=random.randint(0, 30))
        
        # If it's too late, move to next business day
        elif dt.hour >= self.business_hours['end']:
            dt += timedelta(days=1)
            dt = dt.replace(hour=self.business_hours['start'], minute=0, second=0)
            # Add some randomness to start time (0-30 minutes)
            dt += timedelta(minutes=random.randint(0, 30))
        
        return dt
    
    def should_send_now(self, last_sent: Optional[datetime] = None, 
                       min_interval_minutes: int = 5) -> Tuple[bool, str]:
        """
        Determine if we should send an email now based on human patterns
        
        Returns:
            Tuple[bool, str]: (should_send, reason)
        """
        now = datetime.now(self.timezone)
        
        # Check if we're in business hours
        if not self.is_business_hours(now):
            return False, "Outside business hours"
        
        # Check minimum interval since last send
        if last_sent:
            if last_sent.tzinfo is None:
                last_sent = self.timezone.localize(last_sent)
            elif last_sent.tzinfo != self.timezone:
                last_sent = last_sent.astimezone(self.timezone)
            
            time_since_last = (now - last_sent).total_seconds() / 60  # minutes
            if time_since_last < min_interval_minutes:
                return False, f"Too soon (last sent {time_since_last:.1f} min ago)"
        
        # Get activity weight and make probabilistic decision
        activity_weight = self.get_activity_weight(now)
        
        # Generate random probability
        send_probability = random.random()
        
        # Adjust threshold based on activity weight
        threshold = 0.3 + (activity_weight * 0.4)  # 0.3 to 0.7 range
        
        should_send = send_probability < threshold
        
        if should_send:
            return True, f"Good time to send (activity: {activity_weight:.2f})"
        else:
            return False, f"Waiting for better timing (activity: {activity_weight:.2f})"
    
    def get_daily_send_schedule(self, daily_limit: int, 
                               start_date: datetime = None) -> list:
        """
        Generate a realistic daily schedule for sending emails
        
        Returns:
            List of datetime objects representing send times
        """
        if start_date is None:
            start_date = datetime.now(self.timezone).replace(hour=9, minute=0, second=0, microsecond=0)
        
        if not self.is_business_hours(start_date):
            start_date = self._adjust_to_business_hours(start_date)
        
        schedule = []
        current_time = start_date
        
        # Calculate rough interval between emails
        business_hours_duration = (self.business_hours['end'] - self.business_hours['start']) * 60  # minutes
        base_interval = business_hours_duration / daily_limit if daily_limit > 0 else 60
        
        for i in range(daily_limit):
            # Add some randomness to the interval
            interval_variation = random.uniform(0.7, 1.3)
            interval_minutes = base_interval * interval_variation
            
            # Add the interval
            current_time += timedelta(minutes=interval_minutes)
            
            # Ensure we're still in business hours
            if current_time.hour >= self.business_hours['end']:
                break
            
            # Skip lunch hour with some probability
            if (self.business_hours['lunch_start'] <= current_time.hour < self.business_hours['lunch_end'] 
                and random.random() < 0.7):  # 70% chance to skip lunch hour
                current_time = current_time.replace(hour=self.business_hours['lunch_end'], minute=0)
                current_time += timedelta(minutes=random.randint(0, 30))
            
            schedule.append(current_time)
        
        return schedule
    
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