# Quick Start Guide - New Scheduling System

## What Changed?

The email warmup system now uses **proactive scheduling** instead of reactive checking:

- ✅ **Schedules generated daily** at midnight for each timezone
- ✅ **Human-like distribution**: 60% peak, 30% normal, 10% low activity
- ✅ **Timezone support**: Each account has its own business hours
- ✅ **Weekend skipping**: Automatically skips Saturday and Sunday
- ✅ **Efficient**: Only sends when emails are actually scheduled

## Quick Setup (5 Steps)

### Step 1: Run the Migration

```bash
source venv/bin/activate
python scripts/create_schedule_migration.py
```

This adds:
- `timezone` column to `account` table (default: 'Asia/Kolkata')
- New `email_schedule` table to store schedules

### Step 2: Test the System

```bash
python scripts/test_new_scheduling.py
```

This validates:
- Schedule generation logic
- Timezone handling
- Weekend skipping
- Business hours detection

### Step 3: Restart Celery

```bash
# Stop old processes
pkill -f celery

# Start new workers
celery -A celery_beat_schedule worker --loglevel=info &
celery -A celery_beat_schedule beat --loglevel=info &
```

### Step 4: Monitor Schedules

```bash
# Check account status
python scripts/check_accounts.py

# Watch logs
tail -f celery.log | grep -E "(schedule|send)"
```

### Step 5: Verify Email Sending

Wait for schedules to be generated (happens at midnight) or manually trigger:

```bash
celery -A celery_beat_schedule call app.tasks.email_tasks.generate_daily_schedules_task
```

## Activity Distribution

| Time Period | Hours | % of Emails |
|------------|-------|-------------|
| Peak Morning | 9-11 AM | 30% |
| Normal | 11-12 PM | 15% |
| Lunch (Low) | 12-2 PM | 10% |
| Peak Afternoon | 2-4 PM | 30% |
| Normal Evening | 4-6 PM | 15% |

## New Tasks Overview

| Task | Schedule | Purpose |
|------|----------|---------|
| `generate_daily_schedules_task` | Hourly | Generate schedules at midnight |
| `send_scheduled_emails_task` | Every 2 min | Send due emails |
| `check_replies_task` | Every 5 min | Check for replies |
| `advance_warmup_day_task` | Daily 00:05 | Advance warmup day |
| `warmup_status_report_task` | Every 6 hours | Status reports |
| `cleanup_old_schedules_task` | Daily 02:00 | Clean up old data |

## Timezone Management

### Supported Timezones

Use any IANA timezone name:
- `Asia/Kolkata` (India)
- `America/New_York` (US East)
- `Europe/London` (UK)
- `Asia/Singapore` (Singapore)
- etc.

### Change Account Timezone

```python
from app import create_app, db
from app.models.account import Account

app = create_app()
with app.app_context():
    account = Account.query.filter_by(email='your@email.com').first()
    account.timezone = 'America/New_York'
    db.session.commit()
```

## Troubleshooting

### No schedules generated?

**Check:**
1. Is it midnight in the account's timezone?
2. Is today a weekday?
3. Is the account active and warmup type?

**Fix:**
```bash
# Manually trigger
celery -A celery_beat_schedule call app.tasks.email_tasks.generate_daily_schedules_task
```

### Emails not sending?

**Check:**
1. Are there pending schedules?
2. Is it business hours?
3. Is today a weekday?

**Fix:**
```python
from app import create_app
from app.models.email_schedule import EmailSchedule

app = create_app()
with app.app_context():
    pending = EmailSchedule.query.filter_by(status='pending').count()
    print(f"Pending: {pending}")
```

### View today's schedule

```python
from app import create_app
from app.models.email_schedule import EmailSchedule
from datetime import date

app = create_app()
with app.app_context():
    schedules = EmailSchedule.query.filter_by(schedule_date=date.today()).all()
    for s in schedules:
        print(f"{s.account.email}: {s.scheduled_time} ({s.activity_period}) - {s.status}")
```

## Key Files Changed

1. **`app/models/email_schedule.py`** - NEW: Schedule storage model
2. **`app/models/account.py`** - UPDATED: Added timezone field
3. **`app/services/human_timing_service.py`** - REWRITTEN: New schedule generation
4. **`app/tasks/email_tasks.py`** - REWRITTEN: Proactive scheduling
5. **`celery_beat_schedule.py`** - UPDATED: New task schedules

## Migration Rollback (If Needed)

If you need to rollback:

```bash
# Stop Celery
pkill -f celery

# Restore old files from git
git checkout app/tasks/email_tasks.py
git checkout app/services/human_timing_service.py
git checkout celery_beat_schedule.py

# Drop new table (optional)
psql -d your_database -c "DROP TABLE email_schedule;"

# Restart Celery
celery -A celery_beat_schedule worker --loglevel=info &
celery -A celery_beat_schedule beat --loglevel=info &
```

## Expected Behavior

### Day 1 (Initial Setup)
- Run migration ✓
- Existing accounts have timezone='Asia/Kolkata' ✓
- No schedules exist yet

### Day 2 (First Midnight)
- At 00:01, schedules generated for all accounts
- Each account gets N schedules (N = daily_limit)
- Distribution: 60% peak, 30% normal, 10% low

### Day 2 (Business Hours)
- Every 2 minutes, system checks for due emails
- Emails sent at scheduled times (±2 min window)
- Status updated: pending → sent
- Email records created as before

### Day 3+ (Ongoing)
- New schedules generated at midnight
- Old schedules (>7 days) cleaned up
- Warmup day advances at 00:05
- Status reports every 6 hours

## Performance Notes

- **Database**: Indexes on scheduled_time, schedule_date, status
- **Cleanup**: Old schedules auto-deleted after 7 days
- **Efficiency**: No wasted checks outside business hours
- **Scalability**: Easily handles 100+ accounts across timezones

## Benefits

1. ✅ More realistic human behavior
2. ✅ Predictable send times
3. ✅ Better timezone support
4. ✅ Weekend handling
5. ✅ Observable schedules
6. ✅ Lower CPU usage
7. ✅ Easier debugging

## Next Steps After Setup

1. Monitor logs for 24 hours
2. Verify schedules are being generated
3. Check email sending during business hours
4. Review warmup status reports
5. Adjust timezones if needed

## Support Commands

```bash
# Check accounts
python scripts/check_accounts.py

# Test scheduling
python scripts/test_new_scheduling.py

# View logs
tail -f celery.log

# Check database
psql -d your_database -c "SELECT * FROM email_schedule WHERE schedule_date = CURRENT_DATE;"
```

## Documentation

- **Full Documentation**: `NEW_SCHEDULING_SYSTEM.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Database Schema**: `docs/DATABASE_SCHEMA.md`

---

**Questions?** Check the logs first, then review `NEW_SCHEDULING_SYSTEM.md`
