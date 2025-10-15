from app import db
from datetime import datetime

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    to_address = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    tracking_pixel_id = db.Column(db.String(100), unique=True, nullable=False)
    
    # Engagement tracking
    is_opened = db.Column(db.Boolean, default=False)
    is_replied = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
    
    # Sender's engagement strategy - used by pool accounts to decide open/reply behavior
    # These rates come from the warmup account (sender) configuration
    sender_open_rate = db.Column(db.Float, nullable=True)  # Sender's open rate strategy (0-1)
    sender_reply_rate = db.Column(db.Float, nullable=True)  # Sender's reply rate strategy (0-1)
    
    # Gmail message IDs for proper threading
    gmail_message_id = db.Column(db.String(255), nullable=True)  # Gmail's message ID
    in_reply_to = db.Column(db.String(255), nullable=True)  # For threading replies
    
    def __repr__(self):
        return f'<Email {self.id} to {self.to_address}>'
