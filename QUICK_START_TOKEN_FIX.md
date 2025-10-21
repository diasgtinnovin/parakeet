# Quick Start: Token Auto-Refresh Fix ⚡

## TL;DR

✅ **Fixed**: OAuth tokens now auto-refresh automatically  
✅ **Working**: 9 accounts already refreshed and operational  
❌ **Action Needed**: 7 accounts need re-authentication (one-time)

---

## Run This Command First

```bash
cd /home/dias/Documents/Projects/email-warmup-poc
source venv/bin/activate
python scripts/fix_expired_tokens.py
```

This will show you which accounts are working and which need re-authentication.

---

## Re-authenticate Invalid Accounts

### The 7 accounts that need re-authentication:
- sarah@usi-tek.com
- brandon@usistek.com
- christopher@usittek.com
- jonathan@usittek.com
- matthew@usittek.com
- eric@usistek.com
- nicholas@usistek.com

### How to fix (2 minutes per account):

```bash
# 1. Start Flask app
cd /home/dias/Documents/Projects/email-warmup-poc
source venv/bin/activate
python app.py
```

Then in browser:
1. Go to: http://localhost:5000
2. Fill form → Click "Add Account via Google OAuth"
3. Sign in → Grant permissions
4. Done! (Repeat for other accounts)

---

## What Changed

**Before**: Tokens expired → Tasks failed repeatedly → Manual restart required

**After**: Tokens expired → System auto-refreshes → Tasks continue → Token saved to DB

---

## Verify It's Working

Watch Celery logs for:
```
✅ "Successfully refreshed expired credentials"
✅ "Updated OAuth token for account ..."
```

Instead of:
```
❌ "Failed to refresh credentials: invalid_grant"
❌ "Gmail authentication failed"
```

---

## Files Changed

- `app/services/gmail_service.py` - Returns refreshed tokens
- `app/tasks/email_tasks.py` - Saves refreshed tokens to DB
- `app/api/accounts/routes.py` - Updated OAuth flow
- `scripts/fix_expired_tokens.py` - NEW diagnostic tool

---

## Need Help?

**Full docs**: `OAUTH_TOKEN_MANAGEMENT.md`  
**Summary**: `TOKEN_REFRESH_FIX_SUMMARY.md`  
**Diagnostics**: `python scripts/fix_expired_tokens.py`

---

## Monthly Maintenance (Optional)

```bash
# Check token health
python scripts/fix_expired_tokens.py

# Re-authenticate any failing accounts via OAuth flow
# (Usually zero after initial fix)
```

---

## That's It! 🎉

Your email warmup system now handles token refresh automatically.
Just re-authenticate those 7 accounts and you're all set.

