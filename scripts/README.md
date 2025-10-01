# Scripts Directory

This directory contains utility scripts for managing the email warmup service.

## Setup Scripts

### `setup_warmup_config.py`
**Purpose**: Interactive script to configure warmup and pool accounts

**Usage**:
```bash
python scripts/setup_warmup_config.py
```

**What it does**:
1. Lists all accounts in the database
2. Lets you select which account to warmup
3. Configures warmup target (emails/day at full warmup)
4. Sets remaining accounts as pool (recipients)
5. Calculates initial daily limit (10% of target)

**When to run**:
- After adding accounts via OAuth flow
- When you want to change which account is being warmed
- When reconfiguring warmup strategy

---

### `create_migration.py`
**Purpose**: Create and apply database migration for warmup configuration fields

**Usage**:
```bash
python scripts/create_migration.py
```

**What it does**:
1. Initializes Flask-Migrate if needed
2. Creates migration for new Account model fields
3. Applies the migration to the database

**When to run**:
- Once, after first deployment
- When Account model schema changes

**Note**: Only run this if you haven't already migrated the database.

---

## Monitoring Scripts

### `check_accounts.py`
**Purpose**: Display current warmup configuration status

**Usage**:
```bash
python scripts/check_accounts.py
```

**What it shows**:
- Total accounts in database
- Warmup accounts (with full config details)
- Pool accounts (recipients)
- Unconfigured accounts (if any)
- Configuration warnings and recommendations

**When to run**:
- After running `setup_warmup_config.py`
- To verify current configuration
- To troubleshoot email sending issues

---

## OAuth Scripts

### `get_oauth_tokens.py`
**Purpose**: Obtain OAuth tokens for email accounts

**Usage**:
```bash
python scripts/get_oauth_tokens.py
```

**What it does**:
- Starts OAuth flow for Gmail/Outlook
- Obtains access and refresh tokens
- Can be used to add accounts to database

---

### `add_oauth_tokens.py`
**Purpose**: Add OAuth tokens to database for an account

**Usage**:
```bash
python scripts/add_oauth_tokens.py
```

**What it does**:
- Adds account with OAuth tokens to database
- Alternative to web-based OAuth flow

---

## Workflow

### Initial Setup (First Time)

```bash
# 1. Add accounts via OAuth (repeat for each account)
python scripts/get_oauth_tokens.py
# OR use web interface: http://localhost:5000/api/oauth/authorize

# 2. Run migration to add warmup fields
python scripts/create_migration.py

# 3. Configure warmup and pool accounts
python scripts/setup_warmup_config.py

# 4. Verify configuration
python scripts/check_accounts.py
```

### Regular Operations

```bash
# Check current status
python scripts/check_accounts.py

# Reconfigure warmup if needed
python scripts/setup_warmup_config.py
```

### Adding More Accounts

```bash
# 1. Add new account via OAuth
python scripts/get_oauth_tokens.py

# 2. Reconfigure to include new account in pool
python scripts/setup_warmup_config.py

# 3. Verify
python scripts/check_accounts.py
```

## Example Output

### `check_accounts.py`
```
================================================================================
                        WARMUP CONFIGURATION STATUS
================================================================================

Total accounts: 7
Warmup accounts: 1
Pool accounts: 6

--------------------------------------------------------------------------------

                              WARMUP ACCOUNTS
--------------------------------------------------------------------------------

📧 sender@example.com
   Type: warmup
   Provider: gmail
   Active: ✓
   Daily Limit: 5 emails/day
   Warmup Target: 50 emails/day
   Warmup Day: 1
   Warmup Score: 0/100
   Created: 2025-09-30 10:23

                        POOL ACCOUNTS (Recipients)
--------------------------------------------------------------------------------

1. recipient1@example.com
   Provider: gmail
   Active: ✓

2. recipient2@example.com
   Provider: gmail
   Active: ✓

...

================================================================================

✓ Configuration looks good!
  • 1 warmup account(s)
  • 6 pool account(s)

Next: Ensure Celery Beat is running to start warmup.
```

## Troubleshooting

### Script fails with "No module named 'flask'"
**Solution**: Activate virtual environment first
```bash
source venv/bin/activate
python scripts/<script_name>.py
```

### Script fails with "RuntimeError: SQLALCHEMY_DATABASE_URI must be set"
**Solution**: Ensure `.env` file exists with `DATABASE_URL` set
```bash
echo "DATABASE_URL=postgresql://user:pass@localhost/dbname" > .env
```

### No accounts found
**Solution**: Add accounts via OAuth flow first
```bash
python scripts/get_oauth_tokens.py
# OR use web interface
```

### Migration already exists
**Solution**: Skip `create_migration.py` and run setup directly
```bash
python scripts/setup_warmup_config.py
```