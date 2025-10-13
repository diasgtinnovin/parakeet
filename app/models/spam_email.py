from app import db
from datetime import datetime

class SpamEmail(db.Model):
    """Track emails that were found in spam folder"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference to the original email record
    email_id = db.Column(db.Integer, db.ForeignKey('email.id'), nullable=True)
    
    # Account where spam was found (pool account)
    pool_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    
    # Sender account (warmup account)
    sender_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    
    # Email details
    gmail_message_id = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    from_address = db.Column(db.String(255), nullable=False)
    to_address = db.Column(db.String(255), nullable=False)
    snippet = db.Column(db.Text, nullable=True)
    
    # Spam detection info
    detected_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    recovered_at = db.Column(db.DateTime, nullable=True)
    
    # Status tracking
    status = db.Column(db.String(20), default='detected')  # 'detected', 'recovered', 'failed'
    recovery_attempts = db.Column(db.Integer, default=0)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    email = db.relationship('Email', backref='spam_records', lazy=True)
    pool_account = db.relationship('Account', foreign_keys=[pool_account_id], backref='spam_emails_received')
    sender_account = db.relationship('Account', foreign_keys=[sender_account_id], backref='spam_emails_sent')
    
    def mark_recovered(self):
        """Mark spam email as successfully recovered"""
        self.status = 'recovered'
        self.recovered_at = datetime.utcnow()
    
    def mark_failed(self, error_msg):
        """Mark spam recovery as failed"""
        self.status = 'failed'
        self.error_message = error_msg
        self.last_attempt_at = datetime.utcnow()
    
    def increment_attempts(self):
        """Increment recovery attempts counter"""
        self.recovery_attempts += 1
        self.last_attempt_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<SpamEmail {self.id} from {self.from_address} to {self.to_address}>'