from flask import request, jsonify
from app import db
from app.models.account import Account
from app.models.email import Email
from . import analytics_bp
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@analytics_bp.route('/account/<int:account_id>', methods=['GET'])
def get_account_analytics(account_id):
    """Get analytics for a specific account"""
    try:
        account = Account.query.get_or_404(account_id)
        
        # Get email statistics
        total_emails = Email.query.filter_by(account_id=account_id).count()
        opened_emails = Email.query.filter_by(account_id=account_id, is_opened=True).count()
        replied_emails = Email.query.filter_by(account_id=account_id, is_replied=True).count()
        
        # Calculate rates
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        reply_rate = (replied_emails / total_emails * 100) if total_emails > 0 else 0
        
        # Calculate warmup score (simplified)
        warmup_score = min(100, int((open_rate * 0.6 + reply_rate * 0.4) * 2))
        
        # Update account warmup score
        account.warmup_score = warmup_score
        db.session.commit()
        
        return jsonify({
            'account_id': account_id,
            'email': account.email,
            'total_emails': total_emails,
            'opened_emails': opened_emails,
            'replied_emails': replied_emails,
            'open_rate': round(open_rate, 2),
            'reply_rate': round(reply_rate, 2),
            'warmup_score': warmup_score,
            'daily_limit': account.daily_limit,
            'is_active': account.is_active
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@analytics_bp.route('/overview', methods=['GET'])
def get_overview_analytics():
    """Get overview analytics for all accounts"""
    try:
        # Get total statistics
        total_accounts = Account.query.filter_by(is_active=True).count()
        total_emails = Email.query.count()
        total_opened = Email.query.filter_by(is_opened=True).count()
        total_replied = Email.query.filter_by(is_replied=True).count()
        
        # Calculate overall rates
        overall_open_rate = (total_opened / total_emails * 100) if total_emails > 0 else 0
        overall_reply_rate = (total_replied / total_emails * 100) if total_emails > 0 else 0
        
        return jsonify({
            'total_accounts': total_accounts,
            'total_emails': total_emails,
            'total_opened': total_opened,
            'total_replied': total_replied,
            'overall_open_rate': round(overall_open_rate, 2),
            'overall_reply_rate': round(overall_reply_rate, 2)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting overview analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500
