from flask import request, jsonify, redirect, session, render_template_string
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app import db
from app.models.account import Account
from . import oauth_bp
import os
import json
import secrets
import logging
from dotenv import load_dotenv

# Allow HTTP for development (IMPORTANT: Only for development!)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logger = logging.getLogger(__name__)

# OAuth 2.0 client configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:5000/api/oauth/callback"]
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

@oauth_bp.route('/login', methods=['POST'])
def oauth_login():
    """Initiate Google OAuth flow with engagement rate configuration"""
    try:
        # Get configuration from form
        data = request.form
        open_rate = float(data.get('open_rate', 80)) / 100  # Convert percentage to decimal
        reply_rate = float(data.get('reply_rate', 55)) / 100  # Convert percentage to decimal
        account_type = data.get('account_type', 'pool')
        daily_limit = int(data.get('daily_limit', 5))
        
        # Validate rates
        if not (0 <= open_rate <= 1):
            return jsonify({'error': 'Open rate must be between 0 and 100'}), 400
        if not (0 <= reply_rate <= 1):
            return jsonify({'error': 'Reply rate must be between 0 and 100'}), 400
        
        # Store configuration in session for use in callback
        session['account_config'] = {
            'open_rate': open_rate,
            'reply_rate': reply_rate,
            'account_type': account_type,
            'daily_limit': daily_limit
        }
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri="http://localhost:5000/api/oauth/callback"
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # ensure refresh_token is returned on reconnect
        )
        
        session['oauth_state'] = state
        return redirect(authorization_url)
        
    except ValueError as e:
        return jsonify({'error': 'Invalid rate values. Please enter numbers between 0 and 100.'}), 400
    except Exception as e:
        logger.error(f"OAuth login error: {e}")
        return jsonify({'error': f'Failed to initiate OAuth: {str(e)}'}), 500

@oauth_bp.route('/callback')
def oauth_callback():
    """Handle OAuth callback and create account"""
    try:
        state = session.get('oauth_state')
        if not state:
            return jsonify({'error': 'Invalid OAuth state'}), 400
        
        # Get account configuration from session
        account_config = session.get('account_config', {})
        open_rate = account_config.get('open_rate', 0.80)  # Default 80%
        reply_rate = account_config.get('reply_rate', 0.55)  # Default 55%
        account_type = account_config.get('account_type', 'pool')
        daily_limit = account_config.get('daily_limit', 5)
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=state,
            redirect_uri="http://localhost:5000/api/oauth/callback"
        )
        
        # Get authorization response
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Test Gmail connection and get email
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile['emailAddress']
        
        # Prepare token data
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        
        # Check if account already exists
        existing_account = Account.query.filter_by(email=email_address).first()
        
        if existing_account:
            # Update existing account
            existing_account.set_oauth_token_data(token_data)
            existing_account.is_active = True
            existing_account.open_rate = open_rate
            existing_account.reply_rate = reply_rate
            existing_account.account_type = account_type
            existing_account.daily_limit = daily_limit
            db.session.commit()
            
            message = f"Account {email_address} updated successfully"
            account_id = existing_account.id
        else:
            # Create new account
            account = Account(
                email=email_address,
                provider='gmail',
                daily_limit=daily_limit,
                warmup_score=0,
                account_type=account_type,
                open_rate=open_rate,
                reply_rate=reply_rate
            )
            account.set_oauth_token_data(token_data)
            
            db.session.add(account)
            db.session.commit()
            
            message = f"Account {email_address} added successfully"
            account_id = account.id
        
        # Clear session data
        session.pop('account_config', None)
        session.pop('oauth_state', None)
        
        # Success page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Success!</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; background-color: #f5f5f5; }}
                .container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .success {{ background: #d4edda; padding: 20px; border-radius: 5px; color: #155724; margin: 20px 0; border-left: 5px solid #28a745; }}
                .info {{ background: #d1ecf1; padding: 20px; border-radius: 5px; color: #0c5460; margin: 20px 0; border-left: 5px solid #17a2b8; }}
                .config {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .config-item {{ margin: 8px 0; padding: 5px; border-bottom: 1px solid #e0e0e0; }}
                .config-item:last-child {{ border-bottom: none; }}
                h1 {{ color: #333; margin-bottom: 10px; }}
                h3 {{ margin-top: 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 Success!</h1>
                <div class="success">
                    <h3>✅ {message}</h3>
                    <p><strong>Email:</strong> {email_address}</p>
                    <p><strong>Account ID:</strong> {account_id}</p>
                </div>
                
                <div class="config">
                    <h4>⚙️ Your Configuration:</h4>
                    <div class="config-item"><strong>Account Type:</strong> {account_type.title()}</div>
                    <div class="config-item"><strong>Daily Limit:</strong> {daily_limit} emails</div>
                    <div class="config-item"><strong>Email Open Rate:</strong> {open_rate:.0%}</div>
                    <div class="config-item"><strong>Reply Rate:</strong> {reply_rate:.0%}</div>
                </div>
                
                <div class="info">
                    <h4>🚀 What's Next:</h4>
                    <ul>
                        <li>Your account is now active in the warmup service</li>
                        <li>Emails will be sent/received automatically based on your configuration</li>
                        <li>Check analytics: <a href="/api/analytics/account/{account_id}" target="_blank">View Dashboard</a></li>
                        <li>Monitor warmup score and adjust settings as needed</li>
                        <li>You can close this page</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return jsonify({'error': f'OAuth failed: {str(e)}'}), 500

@oauth_bp.route('/signin')
def signin_page():
    """Enhanced sign in page with engagement rate configuration"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Warmup - Sign In</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                max-width: 700px; 
                margin: 50px auto; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                background: white; 
                padding: 40px; 
                border-radius: 15px; 
                box-shadow: 0 10px 40px rgba(0,0,0,0.2); 
            }
            h1 { 
                color: #333; 
                margin-bottom: 10px; 
                font-size: 32px;
                text-align: center;
            }
            h2 { 
                color: #666; 
                text-align: center; 
                font-weight: normal;
                margin-bottom: 30px;
            }
            .info { 
                background: #e8f4ff; 
                padding: 20px; 
                border-radius: 10px; 
                margin: 20px 0; 
                border-left: 5px solid #4285f4;
            }
            .info h3 { margin-top: 0; color: #1a73e8; }
            .info ul { margin: 10px 0; padding-left: 20px; }
            .info li { margin: 8px 0; color: #333; }
            
            .form-section {
                background: #f8f9fa;
                padding: 25px;
                border-radius: 10px;
                margin: 25px 0;
                border: 1px solid #e0e0e0;
            }
            .form-section h3 {
                margin-top: 0;
                color: #333;
                font-size: 18px;
                margin-bottom: 20px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 600;
                font-size: 14px;
            }
            
            .label-description {
                font-size: 12px;
                color: #666;
                font-weight: normal;
                margin-top: 4px;
                display: block;
            }
            
            input[type="number"],
            select {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                transition: border-color 0.3s;
                box-sizing: border-box;
            }
            
            input[type="number"]:focus,
            select:focus {
                outline: none;
                border-color: #667eea;
            }
            
            .input-group {
                display: flex;
                align-items: center;
            }
            
            .input-group input {
                flex: 1;
            }
            
            .input-suffix {
                margin-left: 10px;
                color: #666;
                font-weight: 600;
            }
            
            .slider-container {
                margin-top: 10px;
            }
            
            input[type="range"] {
                width: 100%;
                height: 8px;
                border-radius: 5px;
                background: #e0e0e0;
                outline: none;
                -webkit-appearance: none;
            }
            
            input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #667eea;
                cursor: pointer;
            }
            
            input[type="range"]::-moz-range-thumb {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #667eea;
                cursor: pointer;
                border: none;
            }
            
            .slider-value {
                text-align: center;
                font-size: 24px;
                font-weight: bold;
                color: #667eea;
                margin-top: 8px;
            }
            
            .google-btn { 
                background: linear-gradient(135deg, #4285f4 0%, #357ae8 100%);
                color: white; 
                padding: 16px 32px; 
                border: none; 
                border-radius: 10px; 
                font-size: 18px; 
                cursor: pointer; 
                width: 100%;
                margin: 20px 0;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(66, 133, 244, 0.3);
                transition: all 0.3s;
            }
            .google-btn:hover { 
                background: linear-gradient(135deg, #357ae8 0%, #2a62c4 100%);
                box-shadow: 0 6px 20px rgba(66, 133, 244, 0.4);
                transform: translateY(-2px);
            }
            
            .help-text {
                background: #fff3cd;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                border-left: 4px solid #ffc107;
                font-size: 13px;
                color: #856404;
            }
            
            .account-type-options {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-top: 10px;
            }
            
            .account-type-option {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                cursor: pointer;
                transition: all 0.3s;
                text-align: center;
            }
            
            .account-type-option:hover {
                border-color: #667eea;
                background: #f8f9ff;
            }
            
            .account-type-option.selected {
                border-color: #667eea;
                background: #f8f9ff;
            }
            
            .account-type-option input[type="radio"] {
                display: none;
            }
            
            .account-type-option .title {
                font-weight: 600;
                color: #333;
                margin-bottom: 5px;
            }
            
            .account-type-option .description {
                font-size: 12px;
                color: #666;
            }
        </style>
        <script>
            function updateSliderValue(sliderId, displayId) {
                const slider = document.getElementById(sliderId);
                const display = document.getElementById(displayId);
                const hiddenInput = document.getElementById(sliderId + '_value');
                
                slider.addEventListener('input', function() {
                    display.textContent = this.value + '%';
                    hiddenInput.value = this.value;
                });
            }
            
            function selectAccountType(type) {
                document.querySelectorAll('.account-type-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                document.getElementById('type_' + type).classList.add('selected');
                document.getElementById('account_type').value = type;
            }
            
            window.onload = function() {
                updateSliderValue('open_rate_slider', 'open_rate_display');
                updateSliderValue('reply_rate_slider', 'reply_rate_display');
                selectAccountType('pool'); // Default selection
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Email Warmup Service</h1>
            <h2>Configure Your Account</h2>
            
            <div class="info">
                <h3>📋 Quick Setup Guide:</h3>
                <ul>
                    <li>✅ Configure your engagement preferences below</li>
                    <li>✅ Sign in with your Gmail account</li>
                    <li>✅ Start warming up your email automatically</li>
                    <li>✅ Track your progress in real-time</li>
                </ul>
            </div>
            
            <form action="/api/oauth/login" method="POST">
                <div class="form-section">
                    <h3>🎯 Account Type</h3>
                    
                    <div class="account-type-options">
                        <div class="account-type-option" id="type_warmup" onclick="selectAccountType('warmup')">
                            <input type="radio" name="account_type_radio" value="warmup">
                            <div class="title">🔥 Warmup Account</div>
                            <div class="description">This account sends warmup emails</div>
                        </div>
                        <div class="account-type-option" id="type_pool" onclick="selectAccountType('pool')">
                            <input type="radio" name="account_type_radio" value="pool" checked>
                            <div class="title">📧 Pool Account</div>
                            <div class="description">This account receives & engages with emails</div>
                        </div>
                    </div>
                    <input type="hidden" id="account_type" name="account_type" value="pool">
                    
                    <div class="help-text">
                        <strong>Note:</strong> You need at least 1 warmup account and 1+ pool accounts for the system to work.
                    </div>
                </div>
                
                <div class="form-section">
                    <h3>📊 Engagement Configuration</h3>
                    
                    <div class="form-group">
                        <label>
                            📬 Email Open Rate
                            <span class="label-description">What percentage of emails should be opened?</span>
                        </label>
                        <div class="slider-container">
                            <input type="range" id="open_rate_slider" min="50" max="95" value="80" step="5">
                            <div class="slider-value" id="open_rate_display">80%</div>
                        </div>
                        <input type="hidden" id="open_rate_slider_value" name="open_rate" value="80">
                    </div>
                    
                    <div class="form-group">
                        <label>
                            💬 Reply Rate
                            <span class="label-description">What percentage of opened emails should get a reply?</span>
                        </label>
                        <div class="slider-container">
                            <input type="range" id="reply_rate_slider" min="30" max="80" value="55" step="5">
                            <div class="slider-value" id="reply_rate_display">55%</div>
                        </div>
                        <input type="hidden" id="reply_rate_slider_value" name="reply_rate" value="55">
                    </div>
                    
                    <div class="help-text">
                        <strong>💡 Recommended:</strong> Open Rate: 75-85%, Reply Rate: 50-60% for natural engagement patterns.
                    </div>
                </div>
                
                <div class="form-section">
                    <h3>⚙️ Volume Settings</h3>
                    
                    <div class="form-group">
                        <label>
                            📨 Daily Email Limit
                            <span class="label-description">Maximum emails per day (for warmup accounts)</span>
                        </label>
                        <div class="input-group">
                            <input type="number" id="daily_limit" name="daily_limit" value="5" min="1" max="100">
                            <span class="input-suffix">emails/day</span>
                        </div>
                    </div>
                    
                    <div class="help-text">
                        <strong>⚠️ Start Low:</strong> Begin with 5-10 emails/day and gradually increase as your warmup score improves.
                    </div>
                </div>
                
                <button type="submit" class="google-btn">
                    🔐 Continue with Google
                </button>
            </form>
            
            <p style="text-align: center; color: #666; font-size: 13px;">
                <small>🔒 This will securely authenticate your Gmail account. Your data is safe.</small>
            </p>
        </div>
    </body>
    </html>
    """
    return html
