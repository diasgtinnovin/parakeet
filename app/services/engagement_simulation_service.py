import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EngagementSimulationService:
    """
    Service to simulate human-like email engagement behavior
    - Opens emails after realistic delays with target-based probability
    - Decides whether to reply with target-based probability
    - Generates replies after realistic delays
    """
    
    def __init__(self, open_rate=None, reply_rate=None):
        """
        Initialize with optional custom rates
        
        Args:
            open_rate: Float between 0-1 (e.g., 0.80 for 80%). If None, uses default range.
            reply_rate: Float between 0-1 (e.g., 0.55 for 55%). If None, uses default range.
        """
        # Configuration for engagement simulation
        self.open_delay_range = (30, 600)  # 30 seconds to 10 minutes
        self.reply_delay_range = (300, 1800)  # 5-30 minutes after opening
        
        # Store custom rates or use defaults
        self.custom_open_rate = open_rate
        self.custom_reply_rate = reply_rate
        
        # Default ranges (used when no custom rate is provided)
        self.default_open_probability_range = (0.75, 0.85)  # 75%-85% chance
        self.default_reply_probability_range = (0.5, 0.6)   # 50%-60% chance
        
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
        Uses custom rate if provided, otherwise uses default range
        """
        if self.custom_reply_rate is not None:
            # Use custom rate with small random variation (±5%)
            variation = random.uniform(-0.05, 0.05)
            reply_probability = max(0, min(1, self.custom_reply_rate + variation))
        else:
            # Use default range
            min_prob, max_prob = self.default_reply_probability_range
            reply_probability = random.uniform(min_prob, max_prob)
        
        will_reply = random.random() < reply_probability
        
        logger.debug(f"Reply decision: {will_reply} (probability: {reply_probability:.2%})")
        return will_reply

    def should_open_target_based(self, sender_account_id: int, db_session) -> bool:
        """
        Decide whether to open an email based on TARGET RATE maintenance.
        This ensures the actual open rate matches the user-specified rate exactly.
        
        Args:
            sender_account_id: The warmup account ID that sent this email
            db_session: Database session for queries
            
        Returns:
            True if email should be opened, False if it should be skipped
        """
        from app.models.email import Email
        
        # Get target open rate for this sender
        target_open_rate = self.custom_open_rate if self.custom_open_rate is not None else 0.80
        
        # Count total emails sent by this sender (that have been processed)
        total_sent = db_session.query(Email).filter(
            Email.account_id == sender_account_id,
            Email.is_processed == True
        ).count()
        
        # Count how many were opened
        total_opened = db_session.query(Email).filter(
            Email.account_id == sender_account_id,
            Email.is_processed == True,
            Email.is_opened == True
        ).count()
        
        # Calculate current open rate
        if total_sent == 0:
            # First email - use random decision based on target rate
            current_open_rate = 0.0
        else:
            current_open_rate = total_opened / total_sent
        
        logger.debug(
            f"Open rate check - Target: {target_open_rate:.2%}, "
            f"Current: {current_open_rate:.2%} ({total_opened}/{total_sent})"
        )
        
        # Decision logic based on current vs target rate
        if total_sent == 0:
            # First email - random decision based on target rate
            should_open = random.random() < target_open_rate
            logger.info(
                f"First email for account {sender_account_id} - "
                f"Random decision: {'OPEN' if should_open else 'SKIP'}"
            )
            return should_open
        
        # If current rate is significantly below target, ALWAYS open
        if current_open_rate < (target_open_rate - 0.05):
            logger.info(
                f"Current rate ({current_open_rate:.2%}) < Target ({target_open_rate:.2%}) - "
                f"OPENING to increase rate"
            )
            return True
        
        # If current rate is significantly above target, NEVER open
        if current_open_rate > (target_open_rate + 0.05):
            logger.info(
                f"Current rate ({current_open_rate:.2%}) > Target ({target_open_rate:.2%}) - "
                f"SKIPPING to decrease rate"
            )
            return False
        
        # If rate is close to target (within ±5%), use probability to maintain
        # Calculate what probability will keep us at target
        # If we need to move towards target, adjust probability
        if current_open_rate < target_open_rate:
            # Slightly below target - increase open probability
            open_probability = min(1.0, target_open_rate + 0.1)
        elif current_open_rate > target_open_rate:
            # Slightly above target - decrease open probability
            open_probability = max(0.0, target_open_rate - 0.1)
        else:
            # At target - use target rate
            open_probability = target_open_rate
        
        should_open = random.random() < open_probability
        
        logger.info(
            f"Rate maintenance mode - Target: {target_open_rate:.2%}, "
            f"Current: {current_open_rate:.2%}, "
            f"Probability: {open_probability:.2%}, "
            f"Decision: {'OPEN' if should_open else 'SKIP'}"
        )
        
        return should_open

    def should_open(self) -> bool:
        """
        Decide whether to open an email (OLD PROBABILISTIC METHOD - DEPRECATED).
        Uses custom rate if provided, otherwise uses default range.
        
        WARNING: This method is deprecated. Use should_open_target_based() instead
        for accurate rate maintenance.
        """
        if self.custom_open_rate is not None:
            # Use custom rate with small random variation (±5%)
            variation = random.uniform(-0.05, 0.05)
            open_probability = max(0, min(1, self.custom_open_rate + variation))
        else:
            # Use default range
            min_prob, max_prob = self.default_open_probability_range
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
    
    def should_mark_important(self) -> bool:
        """
        Decide whether to mark an opened email as important
        Uses a probability range of 15%-25%
        """
        important_probability_range = (0.15, 0.25)
        min_prob, max_prob = important_probability_range
        important_probability = random.uniform(min_prob, max_prob)
        
        will_mark_important = random.random() < important_probability
        
        logger.debug(f"Important decision: {will_mark_important} (probability: {important_probability:.2%})")
        return will_mark_important
    
    def calculate_important_delay(self) -> int:
        """
        Calculate delay before marking email as important (in seconds)
        Random delay between 45 and 100 seconds
        """
        min_delay = 45
        max_delay = 100
        
        # Use uniform distribution for the delay
        delay = random.randint(min_delay, max_delay)
        
        logger.debug(f"Calculated important delay: {delay} seconds")
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
        stats = {
            'open_delay_range_seconds': self.open_delay_range,
            'open_delay_range_human': f"{self.open_delay_range[0]//60}-{self.open_delay_range[1]//60} minutes",
            'reply_delay_range_seconds': self.reply_delay_range,
            'reply_delay_range_human': f"{self.reply_delay_range[0]//60}-{self.reply_delay_range[1]//60} minutes"
        }
        
        if self.custom_open_rate is not None:
            stats['open_rate'] = f"{self.custom_open_rate:.0%} (custom)"
        else:
            stats['open_probability_range'] = f"{self.default_open_probability_range[0]:.0%}-{self.default_open_probability_range[1]:.0%} (default)"
            
        if self.custom_reply_rate is not None:
            stats['reply_rate'] = f"{self.custom_reply_rate:.0%} (custom)"
        else:
            stats['reply_probability_range'] = f"{self.default_reply_probability_range[0]:.0%}-{self.default_reply_probability_range[1]:.0%} (default)"
        
        return stats
