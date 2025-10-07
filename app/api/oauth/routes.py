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
    'https://www.googleapis.com/auth/gmail.modify'
]

@oauth_bp.route('/login')
def oauth_login():
    """Initiate Google OAuth flow"""
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

@oauth_bp.route('/callback')
def oauth_callback():
    """Handle OAuth callback and create account"""
    try:
        state = session.get('oauth_state')
        if not state:
            return jsonify({'error': 'Invalid OAuth state'}), 400
        
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
            db.session.commit()
            
            message = f"Account {email_address} updated successfully"
            account_id = existing_account.id
        else:
            # Create new account
            account = Account(
                email=email_address,
                provider='gmail',
                daily_limit=5,
                warmup_score=0
            )
            account.set_oauth_token_data(token_data)
            
            db.session.add(account)
            db.session.commit()
            
            message = f"Account {email_address} added successfully"
            account_id = account.id
        
        # Success page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Success!</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                .container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .success {{ background: #d4edda; padding: 15px; border-radius: 5px; color: #155724; margin: 20px 0; }}
                .info {{ background: #d1ecf1; padding: 15px; border-radius: 5px; color: #0c5460; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 Success!</h1>
                <div class="success">
                    <h3>✅ {message}</h3>
                    <p><strong>Account ID:</strong> {account_id}</p>
                    <p><strong>Email:</strong> {email_address}</p>
                </div>
                <div class="info">
                    <h4>🚀 What's Next:</h4>
                    <ul>
                        <li>Your account is now active in the warmup service</li>
                        <li>Emails will be sent automatically every 2 minutes</li>
                        <li>Check the analytics at <a href="/api/analytics/account/{account_id}">/api/analytics/account/{account_id}</a></li>
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
    """Simple sign in page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Warmup - Sign In</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background-color: #f5f5f5; }
            .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
            .google-btn { background-color: #4285f4; color: white; padding: 12px 24px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; text-decoration: none; display: inline-block; margin: 20px 0; }
            .google-btn:hover { background-color: #357ae8; }
            .info { background: #e8f4ff; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: left; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Email Warmup Service</h1>
            <h2>Add Gmail Account</h2>
            
            <div class="info">
                <h3>Quick Setup:</h3>
                <ul>
                    <li>✅ Sign in with your Gmail account</li>
                    <li>✅ Automatically adds account to warmup service</li>
                    <li>✅ Starts sending warmup emails immediately</li>
                    <li>✅ No manual token copying needed!</li>
                </ul>
            </div>
            
            <a href="/api/oauth/login" class="google-btn">
                🔐 Sign in with Google
            </a>
            
            <p><small>This will securely authenticate your Gmail account</small></p>
        </div>
    </body>
    </html>
    """
    return html
