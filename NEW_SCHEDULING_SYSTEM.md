# New Email Scheduling System Documentation

## Overview

The email warmup system has been completely redesigned to use **proactive schedule generation** instead of reactive checking. This creates more natural, human-like email sending patterns that are harder to detect.

## Key Changes

### 1. Architecture Shift: Reactive → Proactive

**Old System (Reactive):**
- Celery task runs every 15 minutes
- Checks each account: "Should I send now?"
- Makes random decisions in real-time
- Inefficient and unpredictable

**New System (Proactive):**
- Daily schedules generated at midnight for each timezone
- Schedules stored in database
- Worker checks for due emails every 2 minutes
- Predictable, efficient, and more human-like

### 2. Human-Like Activity Patterns

Emails are distributed across three activity periods:

| Period | Time Ranges | % of Daily Emails | Description |
|--------|-------------|------------------|-------------|
| **Peak** | 9-11 AM, 2-4 PM | 60% | High activity hours |
| **Normal** | 11-12 PM, 4-6 PM | 30% | Regular activity |
| **Low** | 12-2 PM | 10% | Lunch time |

### 3. Timezone Support

- Each account has its own timezone (e.g., 'Asia/Kolkata', 'America/New_York')
- Business hours calculated per timezone
- Schedules generated at midnight in each timezone
- Default timezone: 'Asia/Kolkata' for existing accounts

### 4. Weekend Handling

- Weekends are automatically skipped
- No emails sent on Saturday or Sunday
- Schedules only generated for weekdays

## Database Schema Changes

### New Table: `email_schedule`

```sql
CREATE TABLE email_schedule (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES account(id),
    scheduled_time TIMESTAMP NOT NULL,
    schedule_date DATE NOT NULL,
    activity_period VARCHAR(20) NOT NULL,  -- 'peak', 'normal', 'low'
    status VARCHAR(20) DEFAULT 'pending',   -- 'pending', 'sent', 'failed', 'skipped'
    sent_at TIMESTAMP,
    email_id INTEGER REFERENCES email(id),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scheduled_time ON email_schedule(scheduled_time);
CREATE INDEX idx_schedule_date ON email_schedule(schedule_date);
CREATE INDEX idx_status ON email_schedule(status);
```

### Updated Table: `account`

```sql
ALTER TABLE account ADD COLUMN timezone VARCHAR(50) DEFAULT 'Asia/Kolkata';
```

## New Task Schedule

| Task | Frequency | Purpose |
|------|-----------|---------|
| `generate_daily_schedules_task` | Every hour | Generate schedules at midnight in each timezone |
| `send_scheduled_emails_task` | Every 2 minutes | Send emails that are due now |
| `check_replies_task` | Every 5 minutes | Check for and record replies |
| `advance_warmup_day_task` | Daily at 00:05 | Advance warmup day counter |
| `warmup_status_report_task` | Every 6 hours | Generate status reports |
| `cleanup_old_schedules_task` | Daily at 02:00 | Clean up old schedule records |

## How It Works

### 1. Schedule Generation (Midnight)

At midnight in each timezone:

1. **Check if it's midnight** in the account's timezone
2. **Calculate daily limit** based on warmup phase
3. **Skip weekends** automatically
4. **Generate schedule** with proper distribution:
   - 60% during peak hours (9-11 AM, 2-4 PM)
   - 30% during normal hours (11-12 PM, 4-6 PM)
   - 10% during low hours (12-2 PM)
5. **Add randomization** (±3 minutes, ±30 seconds)
6. **Save to database** as `email_schedule` records

### 2. Email Sending (Every 2 Minutes)

Every 2 minutes:

1. **Check each timezone** for active warmup accounts
2. **Skip if outside business hours** or weekend
3. **Query due schedules** (scheduled_time within 2-minute window)
4. **Send each scheduled email**:
   - Generate AI content
   - Authenticate with Gmail
   - Send email
   - Record in `email` table
   - Mark schedule as 'sent'
5. **Handle failures**: Mark as 'failed', increment retry count

### 3. Schedule Flow Example

**Account**: `warmup@example.com`
**Timezone**: `Asia/Kolkata`
**Daily Limit**: 10 emails
**Date**: Monday, Oct 7, 2025

**Generated Schedule:**
```
09:15:23 - Peak period (email 1)
09:47:51 - Peak period (email 2)
10:23:08 - Peak period (email 3)
10:58:34 - Peak period (email 4)
11:34:12 - Normal period (email 5)
11:51:47 - Normal period (email 6)
12:29:53 - Low period (email 7)
14:18:24 - Peak period (email 8)
14:52:39 - Peak period (email 9)
16:41:15 - Normal period (email 10)
```

**Distribution:**
- Peak: 6 emails (60%)
- Normal: 3 emails (30%)
- Low: 1 email (10%)

## Installation & Setup

### Step 1: Install Dependencies

```bash
# Already installed, no new dependencies needed
```

### Step 2: Run Migration

```bash
# Activate virtual environment
source venv/bin/activate

# Run migration script
python scripts/create_schedule_migration.py
```

This will:
- Add `timezone` column to `account` table
- Create `email_schedule` table
- Add necessary indexes

### Step 3: Update Existing Accounts (If Needed)

If you want to change timezones for existing accounts:

```python
from app import create_app, db
from app.models.account import Account

app = create_app()
with app.app_context():
    # Update a specific account
    account = Account.query.filter_by(email='your@email.com').first()
    account.timezone = 'America/New_York'  # or any valid timezone
    db.session.commit()
```

### Step 4: Restart Celery

```bash
# Stop existing Celery workers
pkill -f celery

# Start new workers with updated code
celery -A celery_beat_schedule worker --loglevel=info &
celery -A celery_beat_schedule beat --loglevel=info &
```

## Supported Timezones

Use standard IANA timezone names:

**Common Business Timezones:**
- `Asia/Kolkata` (IST - India)
- `America/New_York` (EST/EDT - US East)
- `America/Los_Angeles` (PST/PDT - US West)
- `Europe/London` (GMT/BST - UK)
- `Europe/Paris` (CET/CEST - Central Europe)
- `Asia/Tokyo` (JST - Japan)
- `Australia/Sydney` (AEST/AEDT - Australia)
- `Asia/Singapore` (SGT - Singapore)
- `Asia/Dubai` (GST - UAE)

[Full list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

## Monitoring & Debugging

### Check Generated Schedules

```python
from app import create_app, db
from app.models.email_schedule import EmailSchedule
from datetime import date

app = create_app()
with app.app_context():
    today = date.today()
    schedules = EmailSchedule.query.filter_by(schedule_date=today).all()
    
    for s in schedules:
        print(f"{s.account.email}: {s.scheduled_time} ({s.activity_period}) - {s.status}")
```

### View Account Status

```bash
python scripts/check_accounts.py
```

### Monitor Logs

```bash
# Watch Celery logs for schedule generation and sending
tail -f celery.log | grep -E "(schedule|send|email)"
```

### Check Schedule Statistics

The system logs detailed statistics when generating schedules:

```
Generated schedule for warmup@example.com (Phase 2: Building trust):
  10 emails - Peak: 6, Normal: 3, Low: 1
  First send: 09:15:23, Last send: 16:41:15
  Avg interval: 43.2 min (range: 18.5 - 87.3 min)
```

## API Endpoints (For Future Integration)

You can add these endpoints to view/manage schedules:

```python
# app/api/schedules/routes.py (to be created)

@bp.route('/api/schedules/<int:account_id>', methods=['GET'])
def get_account_schedules(account_id):
    """Get today's schedule for an account"""
    # Return pending/sent schedules for today

@bp.route('/api/schedules/<int:account_id>/regenerate', methods=['POST'])
def regenerate_schedule(account_id):
    """Regenerate schedule for an account"""
    # Clear pending schedules and regenerate
```

## Troubleshooting

### Issue: No schedules being generated

**Check:**
1. Are accounts active? (`is_active=True`)
2. Are they warmup type? (`account_type='warmup'`)
3. Is it midnight in their timezone?
4. Is today a weekday?
5. Check logs for errors

**Solution:**
```bash
# Manually trigger schedule generation
celery -A celery_beat_schedule call app.tasks.email_tasks.generate_daily_schedules_task
```

### Issue: Emails not being sent

**Check:**
1. Are schedules marked as 'pending'?
2. Is it business hours in the account's timezone?
3. Is it a weekday?
4. Are there pool accounts available?
5. Check Gmail authentication

**Solution:**
```python
# Check pending schedules
from app.models.email_schedule import EmailSchedule
pending = EmailSchedule.query.filter_by(status='pending').count()
print(f"Pending schedules: {pending}")
```

### Issue: Wrong timezone behavior

**Check:**
1. Verify timezone string is correct
2. Check server time vs. account timezone
3. Look for DST transitions

**Solution:**
```python
from app.models.account import Account
account = Account.query.filter_by(email='your@email.com').first()
print(f"Timezone: {account.timezone}")

# Update if needed
account.timezone = 'Asia/Kolkata'
db.session.commit()
```

## Performance Considerations

### Database Indexes

The system uses indexes on:
- `email_schedule.scheduled_time` - Fast lookup of due emails
- `email_schedule.schedule_date` - Date-based queries
- `email_schedule.status` - Filter by status

### Schedule Cleanup

Old schedules (>7 days) are automatically cleaned up daily at 2 AM to prevent table bloat.

### Query Optimization

The `send_scheduled_emails_task` uses efficient queries:
- Groups by timezone first
- Checks business hours before querying
- Uses 2-minute window for due emails
- Includes 5-minute grace period for missed emails

## Benefits of New System

1. **More Human-Like**: Pre-planned schedules mimic real human behavior
2. **Predictable**: Know exactly when emails will be sent
3. **Efficient**: No wasted checks outside business hours
4. **Scalable**: Easy to add more accounts/timezones
5. **Observable**: Clear database records of all schedules
6. **Flexible**: Easy to adjust distribution percentages
7. **Reliable**: Failed sends can be tracked and retried
8. **Global**: Full timezone support for worldwide warmup

## Future Enhancements

Potential improvements to consider:

1. **Dynamic Rescheduling**: Automatically reschedule failed sends
2. **Holiday Calendar**: Skip regional holidays
3. **Account-Specific Patterns**: Custom activity patterns per account
4. **ML-Based Timing**: Learn optimal send times from engagement data
5. **A/B Testing**: Test different distribution patterns
6. **Priority Queue**: Prioritize accounts that are behind schedule
7. **Rate Limiting**: Add per-hour limits for extra safety
8. **Schedule Preview**: API to preview tomorrow's schedule

## Migration Checklist

- [x] Create EmailSchedule model
- [x] Add timezone column to Account model
- [x] Rewrite HumanTimingService
- [x] Rewrite email_tasks.py
- [x] Update celery_beat_schedule.py
- [x] Create migration script
- [ ] Run migration on database
- [ ] Test with existing accounts
- [ ] Monitor first day of schedules
- [ ] Verify timezone behavior
- [ ] Check weekend skipping
- [ ] Validate activity distribution

## Support

For issues or questions:
1. Check logs: `tail -f celery.log`
2. Run diagnostic: `python scripts/check_accounts.py`
3. Review this documentation
4. Check EmailSchedule table directly

---

**Last Updated**: October 6, 2025
**Version**: 2.0 (Proactive Scheduling System)
