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
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Email Warmup — Sign In</title>
    <style>
        :root {
        --main: #2baf43;
        --main-light: #eaf8ec;
        --bg: #f9fbf9;
        --card: #ffffff;
        --text: #2f2f2f;
        --muted: #6c6c6c;
        --border: #d8e6da;
        --radius: 14px;
        font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
        }

        * { box-sizing: border-box; }
        body { margin: 0; background: var(--bg); color: var(--text); -webkit-font-smoothing: antialiased; }

        .wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 36px; }
        .card { width: 100%; max-width: 900px; background: var(--card); border-radius: var(--radius); box-shadow: 0 12px 40px rgba(0,0,0,0.06); border: 1px solid var(--border); overflow: hidden; }

        .grid { display: grid; grid-template-columns: 420px 1fr; }
        @media (max-width:880px) { .grid { grid-template-columns: 1fr; } }

        .hero { padding: 36px 30px; background: linear-gradient(180deg, var(--main-light), #ffffff); border-right: 1px solid var(--border); }
        .brand { display: flex; align-items: center; gap: 12px; }
        .logo { width: 56px; height: 56px; border-radius: 12px; background: var(--main-light); display: flex; align-items: center; justify-content: center; border: 1px solid var(--border); font-weight: 700; color: var(--main); font-size: 18px; }
        h1 { margin: 12px 0 6px; font-size: 20px; color: var(--text); }
        p.lead { margin: 0; color: var(--muted); font-size: 13px; }

        .features { margin-top: 20px; }
        .features li { margin: 8px 0; color: var(--muted); font-size: 13px; }

        .content { padding: 30px; }
        .section { margin-bottom: 20px; }
        .title { font-size: 13px; color: var(--muted); margin-bottom: 10px; font-weight: 600; }

        .panel { background: #fff; border: 1px solid var(--border); padding: 14px; border-radius: 10px; }

        .account-type { display: flex; gap: 12px; }
        .account-type button { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: #fff; cursor: pointer; font-size: 14px; color: var(--text); transition: all .2s; }
        .account-type button.selected { border-color: var(--main); background: var(--main-light); box-shadow: 0 4px 12px rgba(43,175,67,0.1); }

        input[type=number] { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); font-size: 14px; background: #fff; color: var(--text); }

        input[type=range] { -webkit-appearance: none; width: 100%; height: 10px; border-radius: 8px; background: var(--main-light); }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: var(--main); cursor: pointer; }

        .slider-value { min-width: 64px; text-align: center; font-weight: 700; color: var(--text); }

        .google-btn { width: 100%; display: flex; align-items: center; justify-content: center; padding: 14px 20px; border-radius: 10px; border: none; background: var(--main); color: #fff; font-weight: 600; cursor: pointer; font-size: 16px; transition: all 0.2s; }
        .google-btn:hover { background: #25973b; }
        .graph { margin-top: 20px; background: var(--main-light); height: 120px; border-radius: 10px; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; color: var(--main); font-weight: bold; font-size: 14px; }   
        .note { margin-top: 12px; font-size: 13px; color: var(--muted); text-align: center; }
        footer.small { padding: 14px 28px; border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); text-align: center; }
    </style>
    </head>
    <body>
    <div class="wrap">
        <div class="card">
        <div class="grid">
            <aside class="hero">
            <div class="brand">
                <div class="logo">EW</div>
                <div>
                <h1>Welcome to Email Warmup</h1>
                <p class="lead">Improve your deliverability through gradual, intelligent email warmup.</p>
                </div>
            </div>
            <div class="graph">
            <svg viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
              <defs>
                <linearGradient id="g1" x1="0" x2="1">
                  <stop offset="0" stop-color="#eaf8ec"/>
                  <stop offset="1" stop-color="#ffffff"/>
                </linearGradient>
              </defs>
              <rect width="600" height="200" fill="url(#g1)" />
              <g fill="none" stroke="#e6d2c3" stroke-width="2">
                <path d="M40 150 q80 -100 160 -40 q80 60 160 -10 q80 -70 200 -10"/>
              </g>
            </svg>
          </div>
            <div class="features">
                <ul>
                <li>• Automated and adaptive warmup process</li>
                <li>• Custom open & reply behavior settings</li>
                <li>• Real-time analytics and insights</li>
                </ul>
            </div>
            </aside>

            <section class="content">
            <form action="/api/oauth/login" method="POST">
                <div class="section">
                <div class="title">Account Type</div>
                <div class="panel">
                    <div class="account-type">
                    <button type="button" id="type_warmup" onclick="selectAccountType('warmup')">Warmup</button>
                    <button type="button" id="type_pool" class="selected" onclick="selectAccountType('pool')">Pool</button>
                    </div>
                    <input type="hidden" id="account_type" name="account_type" value="pool">
                    <p class="note">Use both warmup and pool accounts for best engagement results.</p>
                </div>
                </div>

                <div class="section">
                <div class="title">Daily Limit</div>
                <div class="panel">
                    <label for="daily_limit">Emails per day</label>
                    <input type="number" id="daily_limit" name="daily_limit" value="5" min="1" max="100">
                    <p class="note">Start small and let the system scale safely as reputation builds.</p>
                </div>
                </div>

                <div class="section">
                <div class="title">Engagement Configuration</div>
                <div class="panel">
                    <label>Email Open Rate (<span id="open_rate_display">80%</span>)</label>
                    <input type="range" id="open_rate_slider" min="50" max="95" value="80" step="5" oninput="updateSliderValue('open_rate_slider','open_rate_display')">
                    <input type="hidden" id="open_rate_slider_value" name="open_rate" value="80">

                    <label style="margin-top:15px">Reply Rate (<span id="reply_rate_display">55%</span>)</label>
                    <input type="range" id="reply_rate_slider" min="30" max="80" value="55" step="5" oninput="updateSliderValue('reply_rate_slider','reply_rate_display')">
                    <input type="hidden" id="reply_rate_slider_value" name="reply_rate" value="55">

                    <p class="note">Recommended: Open 75–85%, Reply 50–60% for natural engagement.</p>
                </div>
                </div>

                <button class="google-btn" type="submit">Continue with Google</button>
                <p class="note">Connect once and let automation handle your email warmup journey.</p>
            </form>
            </section>
        </div>
        <footer class="small">By continuing you agree to our <a href="#">Terms</a> and <a href="#">Privacy</a>.</footer>
        </div>
    </div>

    <script>
        function updateSliderValue(sliderId, displayId) {
        var slider = document.getElementById(sliderId);
        var display = document.getElementById(displayId);
        display.textContent = slider.value + '%';
        if (sliderId === 'open_rate_slider') document.getElementById('open_rate_slider_value').value = slider.value;
        if (sliderId === 'reply_rate_slider') document.getElementById('reply_rate_slider_value').value = slider.value;
        }

        function selectAccountType(type) {
        document.querySelectorAll('.account-type button').forEach(b => b.classList.remove('selected'));
        var el = document.getElementById('type_' + type);
        if (el) el.classList.add('selected');
        document.getElementById('account_type').value = type;
        }

        document.addEventListener('DOMContentLoaded', function() {
        updateSliderValue('open_rate_slider','open_rate_display');
        updateSliderValue('reply_rate_slider','reply_rate_display');
        selectAccountType('pool');
        });
    </script>
    </body>
    </html>

    """
    return html
