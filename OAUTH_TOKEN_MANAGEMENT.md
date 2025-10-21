# OAuth Token Management & Auto-Refresh

## Overview

This email warmup system now includes **automatic OAuth token refresh** functionality. When access tokens expire, the system automatically refreshes them using the refresh token and saves the new credentials to the database.

## How It Works

### Token Lifecycle

1. **Initial Authentication**: When you add an account via OAuth, you receive:
   - `access_token`: Short-lived token (expires in ~1 hour)
   - `refresh_token`: Long-lived token (used to get new access tokens)
   - `token_uri`: Google's token endpoint
   - `client_id` & `client_secret`: OAuth app credentials

2. **Automatic Refresh**: During task execution:
   - System checks if access token is expired
   - If expired, uses `refresh_token` to request new `access_token`
   - New token is automatically saved to database
   - Task continues without interruption

3. **Token Storage**: All token data is stored in the `Account.oauth_token` field as JSON

### Code Implementation

#### GmailService.authenticate_with_token()

The core authentication method now returns a tuple:

```python
success, updated_token_data = gmail_service.authenticate_with_token(token_data)

# Returns:
# (True, None)              - Authentication success, no refresh needed
# (True, updated_token)     - Authentication success, token was refreshed
# (False, None)             - Authentication failed
```

#### Helper Function: authenticate_and_update_token()

A convenience function that handles authentication and database updates:

```python
from app.tasks.email_tasks import authenticate_and_update_token

gmail_service = GmailService()
if authenticate_and_update_token(gmail_service, account):
    # Token is valid and updated if needed
    # Proceed with Gmail operations
else:
    # Authentication failed - account needs re-authentication
    logger.error(f"Failed to authenticate {account.email}")
```

## Common Token Issues

### 1. "Token has been expired or revoked"

**Cause**: The refresh token itself is invalid. This happens when:
- User changed their Google account password
- User revoked access via Google Account settings
- OAuth app is in testing mode (7-day token limit)
- Suspicious activity detected by Google
- Refresh token not used for 6 months

**Solution**: Re-authenticate the account via OAuth flow

### 2. Missing client_id or client_secret

**Cause**: Token data doesn't include OAuth app credentials

**Solution**: System automatically backfills from environment variables:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_URI`

Ensure these are set in your `.env` file.

### 3. Missing Required Scopes

**Cause**: Token doesn't have all required Gmail scopes

**Required Scopes**:
```python
[
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]
```

**Solution**: Re-authenticate to grant all scopes

## Monitoring Token Health

### Check Token Status

Run the diagnostic script to test all accounts:

```bash
python scripts/fix_expired_tokens.py
```

This will:
- Test each account's OAuth token
- Automatically refresh tokens if possible
- Report which accounts need re-authentication
- Provide instructions for fixing invalid tokens

### Example Output

```
OAuth Token Health Check
============================================================

Testing chottuuumottuu@gmail.com (warmup)... ✅ Token is valid
Testing jibinbkp02@gmail.com (pool)... ✅ Token refreshed successfully
Testing sarah@usi-tek.com (pool)... ❌ Authentication failed

============================================================
Summary
============================================================
✅ Valid tokens: 1
🔄 Refreshed tokens: 1
❌ Invalid tokens: 1

============================================================
Accounts Requiring Re-authentication
============================================================

📧 sarah@usi-tek.com (pool)
   Account ID: 27
```

## Re-authenticating Accounts

### Via Web Interface

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Navigate to: `http://localhost:5000`

3. Fill in the form:
   - **Open Rate**: 80% (recommended)
   - **Reply Rate**: 55% (recommended)
   - **Account Type**: Select `warmup` or `pool`
   - **Daily Limit**: 50 (or your target)

4. Click "Add Account via Google OAuth"

5. Sign in with the Gmail account

6. Grant all requested permissions

7. If the account already exists, the token will be updated automatically

### Important Notes

- Re-authentication **does not** create duplicate accounts
- Existing account data (warmup progress, stats) is preserved
- Only the OAuth token is updated

## Best Practices

### 1. OAuth App Configuration

**For Production**: Publish your OAuth app to avoid 7-day token expiration

In Google Cloud Console:
1. Go to OAuth consent screen
2. Change from "Testing" to "In Production"
3. Submit for verification if needed

**For Development**: Use "Testing" mode but re-authenticate frequently

### 2. Environment Variables

Ensure these are set in your `.env`:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
```

### 3. Regular Monitoring

- Run `fix_expired_tokens.py` weekly to catch issues early
- Monitor Celery logs for authentication failures
- Set up alerts for repeated auth failures

### 4. Secure Token Storage

- Never commit `.env` files to version control
- Use encrypted database fields for sensitive data
- Regularly rotate OAuth app credentials

## Troubleshooting

### Tokens Keep Expiring After 7 Days

**Cause**: OAuth app is in "Testing" mode

**Solution**: Publish your OAuth app in Google Cloud Console

### "missing refresh_token" Error

**Cause**: OAuth flow didn't return a refresh token

**Solution**: Ensure OAuth flow includes:
```python
authorization_url, state = flow.authorization_url(
    access_type='offline',      # Required for refresh token
    prompt='consent',           # Force consent screen
    include_granted_scopes='true'
)
```

### Automatic Refresh Not Working

**Cause**: Missing client credentials in token data

**Solution**: Check environment variables are set correctly:
```bash
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET
```

## API Changes

If you're integrating with this system programmatically:

### Old Method (Before Fix)
```python
gmail_service = GmailService()
if gmail_service.authenticate_with_token(token_data):
    # Use gmail_service
```

### New Method (After Fix)
```python
gmail_service = GmailService()
success, updated_token = gmail_service.authenticate_with_token(token_data)

if not success:
    # Handle authentication failure
    return

if updated_token:
    # Save updated token to your storage
    account.set_oauth_token_data(updated_token)
    db.session.commit()

# Use gmail_service
```

### Recommended Method (Celery Tasks)
```python
from app.tasks.email_tasks import authenticate_and_update_token

gmail_service = GmailService()
if not authenticate_and_update_token(gmail_service, account):
    # Handle authentication failure
    return

# Use gmail_service
```

## Logging

The system logs token refresh events:

```
[INFO] Successfully refreshed expired credentials
[INFO] Updated OAuth token for account example@gmail.com
```

Watch for these in Celery logs to monitor token refresh activity.

## Security Considerations

1. **Refresh tokens are sensitive**: Treat them like passwords
2. **Token rotation**: Google may issue new refresh tokens
3. **Revocation**: Users can revoke access at any time
4. **Scope changes**: Adding scopes requires re-authentication
5. **Rate limits**: Google limits token refresh requests

## Summary

✅ **What's Fixed:**
- Automatic token refresh during task execution
- Database persistence of refreshed tokens
- No more repeated "token expired" errors
- Graceful handling of refresh failures

❌ **What Still Requires Manual Action:**
- Invalid or revoked refresh tokens
- OAuth app in testing mode (7-day limit)
- Missing OAuth app credentials
- Scope changes

🔧 **Tools Provided:**
- `fix_expired_tokens.py` - Diagnostic and health check script
- `authenticate_and_update_token()` - Helper function for tasks
- Comprehensive logging and error messages

## Need Help?

If you encounter issues:

1. Run `python scripts/fix_expired_tokens.py` for diagnostics
2. Check Celery logs for detailed error messages
3. Verify `.env` file has all required variables
4. Ensure OAuth app is properly configured in Google Cloud Console
5. Check Google Account activity for revoked access

For persistent issues, review the token data in the database:
```python
python
>>> from app import create_app, db
>>> from app.models.account import Account
>>> app = create_app()
>>> with app.app_context():
...     account = Account.query.filter_by(email='your@email.com').first()
...     print(account.get_oauth_token_data())
```

