# Email Warmup Implementation Guide

## Overview

This guide explains the warmup system implementation and how to configure your accounts for effective email warmup.

## Warmup Strategy

The warmup system mimics human email behavior to build sender reputation gradually. Here's how it works:

### Account Types

1. **Warmup Accounts** (`account_type='warmup'`)
   - The email account(s) being warmed up
   - Sends emails to pool accounts
   - Gradually increases daily email volume
   - Tracks warmup progress via `warmup_day` field

2. **Pool Accounts** (`account_type='pool'`)
   - Recipient accounts for warmup emails
   - Receive emails from warmup accounts
   - Can reply to emails (simulating engagement)
   - Help build sender reputation

### Warmup Flow

```
Warmup Account → Sends Email → Pool Account(s)
                                      ↓
                                   Opens/Reads
                                      ↓
                                  Replies (optional)
                                      ↓
                            Engagement Metrics Updated
```

## Database Schema Changes

The `Account` model now includes three new fields:

```python
account_type = db.Column(db.String(20), default='pool')      # 'warmup' or 'pool'
warmup_target = db.Column(db.Integer, default=50)            # Target emails/day
warmup_day = db.Column(db.Integer, default=0)                # Current warmup day
```

## Setup Instructions

### Step 1: Add Accounts via OAuth

First, add all your email accounts to the database using the OAuth flow:

```bash
# Use the web interface or API to add accounts
# POST /api/oauth/authorize
# This stores OAuth tokens in the Account table
```

### Step 2: Run Migration

Update the database schema to include warmup configuration fields:

```bash
source venv/bin/activate
python scripts/create_migration.py
```

### Step 3: Configure Warmup and Pool Accounts

Run the interactive setup script:

```bash
python scripts/setup_warmup_config.py
```

This script will:
1. Show all accounts in the database
2. Let you select which account to warmup
3. Configure the warmup target (emails/day at full warmup)
4. Set the remaining accounts as pool accounts
5. Calculate and set the initial daily limit (10% of target, min 5)

### Step 4: Verify Configuration

Check the configuration:

```bash
python scripts/check_accounts.py
```

You should see:
- 1 account with `account_type='warmup'`
- Remaining accounts with `account_type='pool'`

## How It Works

### Email Sending Task

The Celery task `send_warmup_emails_task` runs periodically and:

1. Queries for active warmup accounts
2. Queries for active pool accounts
3. For each warmup account:
   - Checks if daily limit is reached
   - Selects a random pool account as recipient
   - Generates AI-powered email content
   - Sends the email
   - Records the email in the database
   - Logs progress

### Reply Checking Task

The Celery task `check_replies_task` runs periodically and:

1. Queries for active warmup accounts
2. For each warmup account:
   - Checks for new replies via IMAP
   - Updates email records with reply status
   - Updates engagement metrics

### Ramping Strategy (Future Implementation)

The warmup system will gradually increase email volume:

- **Day 1-5**: Start at 10% of target (e.g., 5 emails/day for target of 50)
- **Day 6-15**: Increase to 25% of target (e.g., 12 emails/day)
- **Day 16-30**: Increase to 50% of target (e.g., 25 emails/day)
- **Day 31+**: Reach 100% of target (e.g., 50 emails/day)

The ramp-up is automatic based on the `warmup_day` field.

### Human-like Timing (Future Implementation)

To avoid detection, emails are sent with:
- **Variable intervals**: Not perfectly spaced (e.g., 8:23am, 10:47am, 2:15pm)
- **Random delays**: ±15-30 minutes from scheduled time
- **Natural patterns**: More emails during business hours
- **Day-to-day variation**: Different patterns each day

## Configuration Files

### Account Model (`app/models/account.py`)

Contains the warmup configuration fields:
- `account_type`: Distinguishes warmup from pool accounts
- `warmup_target`: Target daily email volume
- `warmup_day`: Tracks warmup progress
- `daily_limit`: Current daily sending limit

### Email Tasks (`app/tasks/email_tasks.py`)

Contains the logic for:
- Sending warmup emails to pool accounts
- Checking replies and updating metrics
- Respecting daily limits

### Celery Schedule (`celery_beat_schedule.py`)

Defines when tasks run:
- `send-warmup-emails`: Every 10 minutes (configurable)
- `check-replies`: Every minute (configurable)

## Monitoring

### Check Daily Progress

```python
from app.models.email import Email
from app.models.account import Account

# Get warmup account
warmup_account = Account.query.filter_by(account_type='warmup').first()

# Count today's emails
today_emails = Email.query.filter(
    Email.account_id == warmup_account.id,
    Email.sent_at >= db.func.date(db.func.now())
).count()

print(f"Sent: {today_emails}/{warmup_account.daily_limit}")
```

### Analytics API

Use the analytics endpoints to monitor:
- Total emails sent
- Open rate
- Reply rate
- Warmup score
- Daily volume

## Best Practices

1. **Minimum Pool Size**: Use at least 5-10 pool accounts for effective warmup
2. **Gradual Ramp**: Don't skip warmup days or increase limits too quickly
3. **Consistent Sending**: Maintain daily email volume consistency
4. **Monitor Metrics**: Watch open and reply rates closely
5. **Adjust Strategy**: If metrics drop, slow down the ramp-up

## Troubleshooting

### No Emails Being Sent

Check:
1. Is there a warmup account configured? (`account_type='warmup'`)
2. Are there pool accounts? (`account_type='pool'`)
3. Is the warmup account active? (`is_active=True`)
4. Has daily limit been reached?
5. Are OAuth tokens valid?

### Emails Going to Wrong Recipients

Check:
- Pool accounts are properly configured with `account_type='pool'`
- Pool accounts have valid email addresses

### Daily Limit Not Working

Check:
- `daily_limit` field is set correctly
- Task is checking `sent_at >= db.func.date(db.func.now())`
- Timezone is configured correctly in Celery

## Next Steps

After basic setup is working:

1. **Implement Ramping**: Auto-increase daily limits based on `warmup_day`
2. **Add Human Timing**: Randomize sending times within business hours
3. **Reply Automation**: Pool accounts auto-reply to warmup emails
4. **Engagement Tracking**: Track opens via tracking pixels
5. **Warmup Score**: Calculate reputation score based on engagement

## File Structure

```
email-warmup-poc/
├── app/
│   ├── models/
│   │   └── account.py          # Updated with warmup fields
│   └── tasks/
│       └── email_tasks.py      # Updated warmup logic
├── scripts/
│   ├── setup_warmup_config.py  # Interactive setup script
│   ├── create_migration.py     # Database migration
│   └── check_accounts.py       # Verify configuration
└── WARMUP_IMPLEMENTATION_GUIDE.md  # This file
```

## Support

For issues or questions:
1. Check the logs in Celery worker output
2. Verify database configuration
3. Review this guide
4. Check the architecture document