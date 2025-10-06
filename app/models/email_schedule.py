from app import db
from datetime import datetime
import pytz

class EmailSchedule(db.Model):
    """
    Stores scheduled email send times for each warmup account
    Generated daily at midnight for the next business day
    """
    __tablename__ = 'email_schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False, index=True)
    
    # Schedule metadata
    schedule_date = db.Column(db.Date, nullable=False, index=True)  # Date this schedule is for
    activity_period = db.Column(db.String(20), nullable=False)  # 'peak', 'normal', 'low'
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'failed', 'skipped'
    sent_at = db.Column(db.DateTime, nullable=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email.id'), nullable=True)  # Reference to sent email
    
    # Retry tracking
    retry_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account', backref='email_schedules')
    email = db.relationship('Email', backref='schedule', uselist=False)
    
    def __repr__(self):
        return f'<EmailSchedule account_id={self.account_id} scheduled_time={self.scheduled_time} status={self.status}>'
    
    def is_due(self, timezone='UTC'):
        """Check if this scheduled email is due to be sent"""
        if self.status != 'pending':
            return False
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        scheduled = self.scheduled_time
        
        # Add timezone info if not present
        if scheduled.tzinfo is None:
            scheduled = pytz.utc.localize(scheduled).astimezone(tz)
        else:
            scheduled = scheduled.astimezone(tz)
        
        # Consider it due if within 2 minutes of scheduled time
        time_diff = (now - scheduled).total_seconds()
        return 0 <= time_diff <= 120  # 0 to 2 minutes window
    
    def mark_sent(self, email_id):
        """Mark this schedule as successfully sent"""
        self.status = 'sent'
        self.sent_at = datetime.utcnow()
        self.email_id = email_id
    
    def mark_failed(self, error_message):
        """Mark this schedule as failed"""
        self.status = 'failed'
        self.retry_count += 1
        self.last_error = error_message
    
    def mark_skipped(self, reason):
        """Mark this schedule as skipped"""
        self.status = 'skipped'
        self.last_error = reason
