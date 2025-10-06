from app import db
from datetime import datetime
import json

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'gmail', 'outlook'
    oauth_token = db.Column(db.Text, nullable=False)  # JSON string
    refresh_token = db.Column(db.Text, nullable=True)  # Encrypted
    token_expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    daily_limit = db.Column(db.Integer, default=5)
    warmup_score = db.Column(db.Integer, default=0)
    
    # Warmup configuration fields
    account_type = db.Column(db.String(20), default='pool')  # 'warmup' or 'pool'
    warmup_target = db.Column(db.Integer, default=50)  # Target emails per day at full warmup
    warmup_day = db.Column(db.Integer, default=0)  # Current day in warmup schedule (0 = not started)
    timezone = db.Column(db.String(50), default='Asia/Kolkata')  # Account timezone for business hours
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    emails = db.relationship('Email', backref='account', lazy=True)
    
    def get_oauth_token_data(self):
        """Get OAuth token data as dictionary"""
        try:
            return json.loads(self.oauth_token)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def set_oauth_token_data(self, token_data):
        """Set OAuth token data from dictionary"""
        self.oauth_token = json.dumps(token_data)
    
    def calculate_daily_limit(self):
        """Calculate daily email limit based on warmup progress"""
        if self.account_type != 'warmup' or self.warmup_day <= 0:
            return self.daily_limit
        
        # Warmup ramping strategy
        target = self.warmup_target
        day = self.warmup_day
        
        # Phase 1: Days 1-7 (Week 1) - Start slow at 10% of target
        if day <= 7:
            return max(5, int(target * 0.1))
        
        # Phase 2: Days 8-14 (Week 2) - Increase to 25% of target
        elif day <= 14:
            return max(10, int(target * 0.25))
        
        # Phase 3: Days 15-21 (Week 3) - Increase to 50% of target
        elif day <= 21:
            return max(15, int(target * 0.5))
        
        # Phase 4: Days 22-28 (Week 4) - Increase to 75% of target
        elif day <= 28:
            return max(20, int(target * 0.75))
        
        # Phase 5: Days 29+ (Month+) - Reach 100% of target
        else:
            return target
    
    def get_warmup_phase(self):
        """Get current warmup phase description"""
        if self.account_type != 'warmup' or self.warmup_day <= 0:
            return "Not in warmup"
        
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
    
    def update_daily_limit(self):
        """Update daily limit based on current warmup progress"""
        if self.account_type == 'warmup':
            new_limit = self.calculate_daily_limit()
            if new_limit != self.daily_limit:
                old_limit = self.daily_limit
                self.daily_limit = new_limit
                return old_limit, new_limit
        return None, None
    
    def __repr__(self):
        return f'<Account {self.email}>'
