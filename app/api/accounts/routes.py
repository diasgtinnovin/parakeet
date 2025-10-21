from flask import request, jsonify
from app import db
from app.models.account import Account
from app.services.gmail_service import GmailService
from . import accounts_bp
import logging

logger = logging.getLogger(__name__)

@accounts_bp.route('/add', methods=['POST'])
def add_account():
    """Add a new email account for warmup"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'provider', 'oauth_token']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate optional rate fields (if provided)
        open_rate = data.get('open_rate', 0.80)  # Default 80%
        reply_rate = data.get('reply_rate', 0.55)  # Default 55%
        
        # Validate rates are between 0 and 1
        if not (0 <= open_rate <= 1):
            return jsonify({'error': 'open_rate must be between 0 and 1 (e.g., 0.80 for 80%)'}), 400
        if not (0 <= reply_rate <= 1):
            return jsonify({'error': 'reply_rate must be between 0 and 1 (e.g., 0.55 for 55%)'}), 400
        
        # Check if account already exists
        existing_account = Account.query.filter_by(email=data['email']).first()
        if existing_account:
            return jsonify({'error': 'Account already exists'}), 409
        
        # Test Gmail connection
        gmail_service = GmailService()
        success, _ = gmail_service.authenticate_with_token(data['oauth_token'])
        if not success:
            return jsonify({'error': 'Invalid OAuth token or connection failed'}), 400
        
        # Create new account
        account = Account(
            email=data['email'],
            provider=data['provider'],
            daily_limit=data.get('daily_limit', 5),
            warmup_score=0,
            open_rate=open_rate,
            reply_rate=reply_rate
        )
        
        # Set OAuth token data
        account.set_oauth_token_data(data['oauth_token'])
        
        db.session.add(account)
        db.session.commit()
        
        return jsonify({
            'message': 'Account added successfully',
            'account_id': account.id,
            'email': account.email,
            'open_rate': f"{open_rate:.0%}",
            'reply_rate': f"{reply_rate:.0%}"
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@accounts_bp.route('/list', methods=['GET'])
def list_accounts():
    """List all warmup accounts"""
    try:
        accounts = Account.query.filter_by(is_active=True).all()
        
        account_list = []
        for account in accounts:
            account_list.append({
                'id': account.id,
                'email': account.email,
                'provider': account.provider,
                'daily_limit': account.daily_limit,
                'warmup_score': account.warmup_score,
                'open_rate': f"{account.open_rate:.0%}",
                'reply_rate': f"{account.reply_rate:.0%}",
                'created_at': account.created_at.isoformat()
            })
        
        return jsonify({'accounts': account_list}), 200
        
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@accounts_bp.route('/<int:account_id>/pause', methods=['POST'])
def pause_account(account_id):
    """Pause warmup for an account"""
    try:
        account = Account.query.get_or_404(account_id)
        account.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Account paused successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error pausing account: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@accounts_bp.route('/<int:account_id>/resume', methods=['POST'])
def resume_account(account_id):
    """Resume warmup for an account"""
    try:
        account = Account.query.get_or_404(account_id)
        account.is_active = True
        db.session.commit()
        
        return jsonify({'message': 'Account resumed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error resuming account: {e}")
        return jsonify({'error': 'Internal server error'}), 500
