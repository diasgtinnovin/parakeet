#!/usr/bin/env python3
"""
Script to identify and help fix accounts with expired or invalid OAuth tokens.

This script:
1. Tests all accounts' OAuth tokens
2. Lists accounts that need re-authentication
3. Provides instructions for fixing them

Run this script if you see "invalid_grant: Token has been expired or revoked" errors.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print("Warning: .env file not found. Make sure environment variables are set.")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.account import Account
from app.services.gmail_service import GmailService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_account_token(account):
    """Test if an account's OAuth token is valid"""
    gmail_service = GmailService()
    success, updated_token = gmail_service.authenticate_with_token(account.get_oauth_token_data())
    
    if not success:
        return False, "Authentication failed"
    
    if updated_token:
        # Token was refreshed successfully
        account.set_oauth_token_data(updated_token)
        db.session.commit()
        return True, "Token refreshed successfully"
    
    return True, "Token is valid"


def main():
    """Main function to check all accounts"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*60)
        print("OAuth Token Health Check")
        print("="*60 + "\n")
        
        all_accounts = Account.query.filter_by(is_active=True).all()
        
        if not all_accounts:
            print("No active accounts found in database.")
            return
        
        valid_accounts = []
        refreshed_accounts = []
        invalid_accounts = []
        
        for account in all_accounts:
            print(f"Testing {account.email} ({account.account_type})...", end=" ")
            
            success, message = test_account_token(account)
            
            if not success:
                print(f"❌ {message}")
                invalid_accounts.append(account)
            elif "refreshed" in message.lower():
                print(f"✅ {message}")
                refreshed_accounts.append(account)
            else:
                print(f"✅ {message}")
                valid_accounts.append(account)
        
        # Summary
        print("\n" + "="*60)
        print("Summary")
        print("="*60)
        print(f"✅ Valid tokens: {len(valid_accounts)}")
        print(f"🔄 Refreshed tokens: {len(refreshed_accounts)}")
        print(f"❌ Invalid tokens: {len(invalid_accounts)}")
        
        if invalid_accounts:
            print("\n" + "="*60)
            print("Accounts Requiring Re-authentication")
            print("="*60)
            
            for account in invalid_accounts:
                print(f"\n📧 {account.email} ({account.account_type})")
                print(f"   Account ID: {account.id}")
            
            print("\n" + "="*60)
            print("How to Fix Invalid Tokens")
            print("="*60)
            print("""
These accounts need to be re-authenticated through the OAuth flow:

1. Go to: http://localhost:5000 (make sure Flask app is running)
2. Fill in the account details:
   - Open Rate: 80% (or your preferred rate)
   - Reply Rate: 55% (or your preferred rate)
   - Account Type: Select 'warmup' or 'pool'
   - Daily Limit: 50 (or your target)
3. Click "Add Account via Google OAuth"
4. Sign in with the Gmail account
5. Grant all requested permissions

The OAuth flow will automatically update the existing account
if the email already exists in the database.

Note: Tokens can expire due to:
- Password changes on the Google account
- Security events (suspicious activity)
- Token not being used for 6 months
- User revoking access via Google Account settings
- OAuth app being in testing mode (tokens expire after 7 days)
""")
        
        if refreshed_accounts:
            print("\n" + "="*60)
            print("Auto-Refreshed Accounts")
            print("="*60)
            print("\nThe following accounts had their tokens automatically refreshed:")
            for account in refreshed_accounts:
                print(f"  ✅ {account.email}")
            print("\nThese accounts are now ready to use!")
        
        print("\n" + "="*60)
        print("Additional Notes")
        print("="*60)
        print("""
✨ The system now automatically refreshes tokens when they expire!

When a token expires, the system will:
1. Detect the expiration
2. Use the refresh_token to get a new access token
3. Save the new token to the database
4. Continue operating normally

This fix ensures tokens are kept up-to-date automatically during
normal operation of the warmup tasks.
""")


if __name__ == '__main__':
    main()

