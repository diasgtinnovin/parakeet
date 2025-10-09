import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EngagementSimulationService:
    """
    Service to simulate human-like email engagement behavior
    - Opens emails after realistic delays with high but not 100% probability
    - Decides whether to reply (default ~60%)
    - Generates replies after realistic delays
    """
    
    def __init__(self):
        # Configuration for engagement simulation
        self.open_delay_range = (30, 600)  # 30 seconds to 10 minutes
        # Most emails are opened, but not all
        self.open_probability_range = (0.75, 0.85)  # 85%-95% chance
        # Replies should be around 60%
        self.reply_probability_range = (0.5, 0.6) 
        self.reply_delay_range = (300, 1800)  # 5-30 minutes after opening
        
    def calculate_open_delay(self) -> int:
        """
        Calculate realistic delay before opening an email (in seconds)
        Uses non-linear distribution to simulate human behavior
        """
        min_delay, max_delay = self.open_delay_range
        
        # Use beta distribution for more realistic timing
        # Most emails opened quickly, some delayed longer
        random_factor = random.betavariate(2, 5)  # Skewed towards quicker opens
        delay = int(min_delay + (max_delay - min_delay) * random_factor)
        
        logger.debug(f"Calculated open delay: {delay} seconds ({delay//60}m {delay%60}s)")
        return delay
    
    def should_reply(self) -> bool:
        """
        Decide whether to reply to an email
        Returns True with configured probability (~60%)
        """
        min_prob, max_prob = self.reply_probability_range
        reply_probability = random.uniform(min_prob, max_prob)
        will_reply = random.random() < reply_probability
        
        logger.debug(f"Reply decision: {will_reply} (probability: {reply_probability:.2%})")
        return will_reply

    def should_open(self) -> bool:
        """
        Decide whether to open an email.
        High probability but not guaranteed (85%-95%).
        """
        min_prob, max_prob = self.open_probability_range
        open_probability = random.uniform(min_prob, max_prob)
        will_open = random.random() < open_probability
        logger.debug(f"Open decision: {will_open} (probability: {open_probability:.2%})")
        return will_open
    
    def calculate_reply_delay(self) -> int:
        """
        Calculate realistic delay before sending a reply (in seconds)
        Simulates thinking/typing time
        """
        min_delay, max_delay = self.reply_delay_range
        
        # Use beta distribution for more realistic timing
        # Most replies sent relatively quickly, some take longer
        random_factor = random.betavariate(2, 3)
        delay = int(min_delay + (max_delay - min_delay) * random_factor)
        
        logger.debug(f"Calculated reply delay: {delay} seconds ({delay//60}m {delay%60}s)")
        return delay
    
    def should_process_email(self, email_received_time: datetime) -> bool:
        """
        Determine if email is ready to be processed (opened)
        Returns True if enough time has passed since receipt
        """
        if not email_received_time:
            return True  # Process if no timestamp available
        
        # Calculate minimum delay
        min_delay_seconds = self.open_delay_range[0]
        time_since_received = (datetime.utcnow() - email_received_time).total_seconds()
        
        is_ready = time_since_received >= min_delay_seconds
        logger.debug(f"Email ready to process: {is_ready} (received {time_since_received}s ago)")
        return is_ready
    
    def get_engagement_stats(self) -> dict:
        """Return current engagement configuration"""
        return {
            'open_delay_range_seconds': self.open_delay_range,
            'open_delay_range_human': f"{self.open_delay_range[0]//60}-{self.open_delay_range[1]//60} minutes",
            'reply_probability_range': f"{self.reply_probability_range[0]:.0%}-{self.reply_probability_range[1]:.0%}",
            'reply_delay_range_seconds': self.reply_delay_range,
            'reply_delay_range_human': f"{self.reply_delay_range[0]//60}-{self.reply_delay_range[1]//60} minutes"
        }
