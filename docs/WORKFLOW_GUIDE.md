# Email Warmup POC - Workflow Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Account Setup Workflow](#account-setup-workflow)
3. [Email Sending Workflow](#email-sending-workflow)
4. [Engagement Tracking Workflow](#engagement-tracking-workflow)
5. [Warmup Progression Workflow](#warmup-progression-workflow)
6. [Daily Operations](#daily-operations)
7. [Monitoring & Analytics](#monitoring--analytics)

---

## System Overview

### High-Level Flow

```
External Platform → OAuth Tokens → Email Warmup Service → Gmail API → Recipients
                                            ↓
                                    PostgreSQL Database
                                            ↓
                                    Celery Tasks (Redis)
                                            ↓
                                    Analytics & Reports
```

### Core Components Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Actions                             │
│  1. Sign in with Google (OAuth)                                 │
│  2. Configure warmup settings                                   │
│  3. Monitor analytics                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask API Layer                             │
│  - OAuth routes: Handle Google authentication                   │
│  - Account routes: Manage accounts (add, pause, resume)         │
│  - Analytics routes: Provide metrics and insights               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer (PostgreSQL)                   │
│  - Account table: Store account info and OAuth tokens           │
│  - Email table: Track sent emails and engagement                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Celery Background Tasks                         │
│  1. Send warmup emails (every 15 min)                           │
│  2. Check replies (every 5 min)                                 │
│  3. Advance warmup day (daily at midnight)                      │
│  4. Generate reports (every 6 hours)                            │
│  5. Create daily schedule (8:30 AM)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Service Layer                                │
│  - AI Service: Generate human-like email content                │
│  - Gmail Service: Send emails and check replies                 │
│  - Human Timing Service: Determine optimal send times           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Account Setup Workflow

### Step 1: OAuth Authentication

**User Journey**:
```
1. User visits http://localhost:5000/api/oauth/signin
2. Clicks "Sign in with Google" button
3. Redirected to Google OAuth consent screen
4. Grants Gmail permissions (send + read)
5. Redirected back to /api/oauth/callback
6. Account automatically created in database
7. Success page displayed with account details
```

**Technical Flow**:
```python
# routes.py - /api/oauth/login
flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
authorization_url, state = flow.authorization_url(access_type='offline')
session['oauth_state'] = state
return redirect(authorization_url)

# routes.py - /api/oauth/callback
flow.fetch_token(authorization_response=request.url)
credentials = flow.credentials

# Get user email from Gmail
service = build('gmail', 'v1', credentials=credentials)
profile = service.users().getProfile(userId='me').execute()
email_address = profile['emailAddress']

# Store tokens in database
token_data = {
    "token": credentials.token,
    "refresh_token": credentials.refresh_token,
    "token_uri": credentials.token_uri,
    "client_id": credentials.client_id,
    "client_secret": credentials.client_secret,
    "scopes": credentials.scopes
}

account = Account(email=email_address, provider='gmail')
account.set_oauth_token_data(token_data)
db.session.add(account)
db.session.commit()
```

**Database State After OAuth**:
```sql
-- New account record created
INSERT INTO account (email, provider, oauth_token, account_type, warmup_day, warmup_target, daily_limit)
VALUES ('user@example.com', 'gmail', '{"token":"ya29...","refresh_token":"1//0e..."}', 'pool', 0, 50, 5);
```

---

### Step 2: Warmup Configuration

**Interactive Setup**:
```bash
$ python scripts/setup_warmup_config.py

Email Warmup Configuration Setup
================================

Found 3 accounts in database:
1. warmup@example.com (pool)
2. pool1@example.com (pool)
3. pool2@example.com (pool)

Which account do you want to warm up? (Enter number): 1
What is your target emails/day at full warmup? (default: 50): 50

Configuration Summary:
- Warmup account: warmup@example.com
- Target: 50 emails/day
- Initial limit: 5 emails/day (10% of target)
- Phase 1 (Days 1-7): 5 emails/day
- Phase 5 (Days 29+): 50 emails/day
- Pool accounts: 2 accounts

Apply this configuration? (yes/no): yes

✅ Configuration applied successfully!
```

**Database Changes**:
```sql
-- Update warmup account
UPDATE account 
SET account_type = 'warmup', 
    warmup_target = 50, 
    warmup_day = 1, 
    daily_limit = 5
WHERE email = 'warmup@example.com';

-- Pool accounts remain unchanged (account_type='pool')
```

---

## Email Sending Workflow

### Complete Send Flow

```
1. Celery Beat triggers send_warmup_emails_task (every 15 minutes)
                            ↓
2. Task execution begins
   - Query warmup accounts (account_type='warmup', is_active=True)
   - Query pool accounts (account_type='pool', is_active=True)
                            ↓
3. For each warmup account:
   a. Update daily limit based on warmup_day
      - warmup_day = 10
      - Phase 2 (days 8-14)
      - daily_limit = 25% of target = 12 emails/day
                            ↓
   b. Check today's email count
      - Query: SELECT COUNT(*) FROM email 
                WHERE account_id=1 AND sent_at >= CURRENT_DATE
      - Result: 7 emails sent today
                            ↓
   c. Daily limit check
      - 7 < 12? YES → Continue
      - 12 >= 12? NO → Skip to next account
                            ↓
   d. Get last sent email
      - Query: SELECT * FROM email WHERE account_id=1 
                ORDER BY sent_at DESC LIMIT 1
      - Result: Last sent at 10:47 AM
      - Current time: 11:15 AM (28 minutes ago)
                            ↓
   e. Human timing decision
      - Call: timing_service.should_send_now(
          last_sent=10:47 AM,
          min_interval_minutes=5,
          daily_limit=12,
          emails_sent_today=7
        )
                            ↓
4. Human Timing Logic (detailed):
   a. Business hours check
      - Current: 11:15 AM on Wednesday
      - Business hours: 9 AM - 6 PM, Monday-Friday
      - Result: ✅ YES
                            ↓
   b. Minimum interval check
      - Time since last: 28 minutes
      - Minimum: 5 minutes
      - Result: ✅ YES (28 > 5)
                            ↓
   c. Calculate day progress
      - Business start: 9:00 AM
      - Business end: 6:00 PM
      - Current: 11:15 AM
      - Progress: (11:15 - 9:00) / (18:00 - 9:00) = 2.25 / 9 = 0.25 (25%)
                            ↓
   d. Calculate expected emails by now
      - Non-linear distribution:
        * Morning peak (9-12): 40% of daily total
        * Lunch (12-2): 10%
        * Afternoon peak (2-5): 40%
        * Evening (5-6): 10%
      - At 25% of day (morning peak): 40% * 0.25 = 10% of total
      - Expected: 12 * 0.10 = 1.2 emails
      - With randomness (±15%): 1.2 * 1.1 = 1.3 emails
                            ↓
   e. Calculate if behind/ahead
      - Sent: 7 emails
      - Expected: 1.3 emails
      - Behind: 1.3 - 7 = -5.7 (way ahead!)
                            ↓
   f. Base probability (based on schedule status)
      - Way ahead (< -2): 5%
      - On track (-2 to 0): 15%
      - Slightly behind (0 to 1): 25%
      - Significantly behind (> 1): 40%
      - Current: Way ahead → 5% base probability
                            ↓
   g. Activity weight multiplier
      - 11:15 AM = Peak period (9-11 AM)
      - Activity weight: 1.0
      - Multiplier: 0.5 + 1.0 = 1.5
                            ↓
   h. Time-since-last factor
      - 28 minutes since last send
      - Ranges:
        * < 15 min: 0.3x (avoid clustering)
        * 15-45 min: 1.0x (normal)
        * 45-120 min: 1.3x (natural gap)
        * > 120 min: 1.6x (catching up)
      - Current: 28 min → 1.0x
                            ↓
   i. Final probability
      - Base: 0.05
      - × Activity: 1.5
      - × Time factor: 1.0
      - × Randomness (±20%): 0.9
      - Final: 0.05 * 1.5 * 1.0 * 0.9 = 0.0675 (6.75%)
                            ↓
   j. Decision
      - Generate random: 0.15 (15%)
      - Compare: 0.15 > 0.0675
      - Result: ❌ DON'T SEND
      - Reason: "Ahead of schedule, waiting (prob: 0.07, activity: 1.0)"
                            ↓
5. Log result and skip
   - Log: "Skipping send for warmup@example.com: Ahead of schedule"
   - Continue to next check in 15 minutes
```

---

### When Send Decision is YES

```
5. Send decision: YES
                            ↓
6. Select recipient
   - Pool accounts: ['pool1@example.com', 'pool2@example.com']
   - Random selection: pool1@example.com
                            ↓
7. Generate email content
   a. Initialize AIService
      - use_ai = True (from env: USE_OPENAI=true)
      - api_key = sk-... (from env)
                            ↓
   b. Generate content
      - Random method selection (45% chance): Template + AI Fill
      - Selected template: "general|Hey there!|{greeting} {casual_phrase} {closing}"
      - AI fills placeholders:
        * {greeting} → "Hey friend!"
        * {casual_phrase} → "Hope you're doing awesome"
        * {closing} → "Talk soon!"
      - Result:
        * Subject: "Hey there!"
        * Content: "Hey friend! Hope you're doing awesome. Talk soon!"
                            ↓
   c. Humanization
      - Add contractions: "you're" (already has)
      - Add filler word (15% chance): No
      - Add emoji (10% chance): No
      - Intentional typo (5% chance): No
      - Final: "Hey friend! Hope you're doing awesome. Talk soon!"
                            ↓
   d. Validation
      - Spam pattern check: ✅ CLEAN
      - Word repetition check: ✅ CLEAN
      - Result: Content approved
                            ↓
8. Generate tracking pixel ID
   - UUID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                            ↓
9. Authenticate with Gmail
   - Get OAuth token from database
   - Create credentials: Credentials.from_authorized_user_info(token_data)
   - Refresh if expired
   - Build service: build('gmail', 'v1', credentials=creds)
                            ↓
10. Send email
    a. Create MIME message
       - To: pool1@example.com
       - Subject: Hey there!
       - Content: Hey friend! Hope you're doing awesome. Talk soon!
       - Tracking pixel: <img src="http://localhost:5000/track/open/a1b2c3d4..." 
                              width="1" height="1" style="display:none;">
                            ↓
    b. Encode and send
       - raw_message = base64.urlsafe_b64encode(message.as_bytes())
       - service.users().messages().send(userId='me', body={'raw': raw_message})
       - Result: message_id = "18b3d4e5f6..."
                            ↓
11. Save to database
    - Create Email record:
      * account_id = 1
      * to_address = pool1@example.com
      * subject = "Hey there!"
      * content = "Hey friend!..."
      * tracking_pixel_id = "a1b2c3d4..."
      * is_opened = False
      * is_replied = False
      * sent_at = NOW()
    - db.session.add(email_record)
    - db.session.commit()
                            ↓
12. Log success
    - "Warmup email sent from warmup@example.com to pool1@example.com (8/12) - Phase 2: Building trust"
                            ↓
13. Calculate next delay (informational only)
    - timing_service.calculate_send_delay(base_interval_minutes=10)
    - Result: 487 seconds (8m 7s)
    - Log: "Next email for warmup@example.com in 8m 7s"
```

---

## Engagement Tracking Workflow

### Email Open Tracking

```
1. Recipient opens email
                            ↓
2. Email client loads HTML
                            ↓
3. Tracking pixel image request
   - URL: http://localhost:5000/track/open/a1b2c3d4-e5f6-7890-abcd-ef1234567890
   - Method: GET
                            ↓
4. Flask route handles request
   - Route: /track/open/<tracking_pixel_id>
   - Handler: track_email_open(tracking_pixel_id)
                            ↓
5. Database lookup
   - Query: SELECT * FROM email WHERE tracking_pixel_id = 'a1b2c3d4...'
   - Result: Email record found (id=42)
                            ↓
6. Update email record (if not already opened)
   - Check: is_opened == False
   - Update: 
     * is_opened = True
     * opened_at = NOW()
   - db.session.commit()
   - Log: "Email 42 opened"
                            ↓
7. Return tracking pixel
   - Content-Type: image/png
   - Body: 1x1 transparent PNG (binary)
   - Status: 200 OK
                            ↓
8. Email client displays pixel (invisible to user)
   - User sees normal email content
   - System tracks the open event
```

---

### Reply Detection Tracking

```
1. Celery Beat triggers check_replies_task (every 5 minutes)
                            ↓
2. Task execution
   - Query warmup accounts (account_type='warmup', is_active=True)
                            ↓
3. For each warmup account:
   a. Authenticate with Gmail
      - Get OAuth token from database
      - Build Gmail service
                            ↓
   b. Search for replies
      - Query: "to:warmup@example.com is:unread"
      - service.users().messages().list(userId='me', q=query)
      - Result: 2 unread messages found
                            ↓
   c. Update email records
      - Query recent sent emails (today, not replied, limit 2)
      - For each email:
        * is_replied = True
        * replied_at = NOW()
      - db.session.commit()
      - Log: "Updated 2 replies for account warmup@example.com"
                            ↓
4. Engagement metrics update (via analytics API)
   - Total emails: 67
   - Opened: 42 (62.69%)
   - Replied: 15 (22.39%)
   - Warmup score: (62.69 * 0.6 + 22.39 * 0.4) * 2 = 48
```

---

## Warmup Progression Workflow

### Daily Advancement

```
1. Celery Beat triggers advance_warmup_day_task (daily at 00:01)
                            ↓
2. Query warmup accounts
   - Filter: account_type='warmup', is_active=True
                            ↓
3. For each warmup account:
   a. Check if already advanced today
      - Compare: account.updated_at.date() < TODAY
      - If already advanced: Skip
                            ↓
   b. Capture current state
      - old_day = 7
      - old_phase = "Phase 1: Initial warmup (Day 7/7)"
      - old_limit = 5
                            ↓
   c. Advance warmup day
      - warmup_day = 7 + 1 = 8
      - updated_at = NOW()
                            ↓
   d. Calculate new daily limit
      - Day 8 → Phase 2 (days 8-14)
      - Limit: 25% of target (50) = 12
      - daily_limit = 12
                            ↓
   e. Get new phase
      - new_phase = "Phase 2: Building trust (Day 8/14)"
                            ↓
   f. Log transition
      - "Advanced warmup for warmup@example.com: Day 7 → 8"
      - "  Phase: Phase 1: Initial warmup (Day 7/7) → Phase 2: Building trust (Day 8/14)"
      - "  Daily limit: 5 → 12 emails/day"
                            ↓
   g. Check for phase milestones
      - Day 8: ✅ New phase!
      - Log: "🎉 warmup@example.com entered new warmup phase: Phase 2: Building trust"
                            ↓
   h. Commit to database
      - db.session.commit()
```

### Warmup Phase Timeline

```
Day 0:  Account added, configured as warmup
        warmup_day = 0, daily_limit = 0
                            ↓
Day 1:  advance_warmup_day_task runs
        warmup_day = 1, daily_limit = 5 (10% of 50)
        Phase 1: Initial warmup
        → Send 5 emails/day
                            ↓
Days 2-7: Continue Phase 1
        → Send 5 emails/day
                            ↓
Day 8:  Phase transition!
        warmup_day = 8, daily_limit = 12 (25% of 50)
        Phase 2: Building trust
        → Send 12 emails/day
                            ↓
Days 9-14: Continue Phase 2
        → Send 12 emails/day
                            ↓
Day 15: Phase transition!
        warmup_day = 15, daily_limit = 25 (50% of 50)
        Phase 3: Increasing volume
        → Send 25 emails/day
                            ↓
Days 16-21: Continue Phase 3
        → Send 25 emails/day
                            ↓
Day 22: Phase transition!
        warmup_day = 22, daily_limit = 37 (75% of 50)
        Phase 4: Near target
        → Send 37 emails/day
                            ↓
Days 23-28: Continue Phase 4
        → Send 37 emails/day
                            ↓
Day 29: Phase transition!
        warmup_day = 29, daily_limit = 50 (100% of 50)
        Phase 5: Full warmup
        → Send 50 emails/day
                            ↓
Days 30+: Maintain full warmup
        → Send 50 emails/day
        → Warmup complete, sender reputation established
```

---

## Daily Operations

### Morning (8:30 AM)

**1. Generate Daily Schedule**
```
Celery Beat → generate_daily_schedule_task
                            ↓
For warmup@example.com (Phase 2, Day 10):
                            ↓
Daily limit: 12 emails
Business hours: 9 AM - 6 PM (9 hours = 540 minutes)
Base interval: 540 / 12 = 45 minutes
                            ↓
Generate schedule with variation:
1.  09:15 (Peak)    - Start of day
2.  09:48 (Peak)    - Morning peak
3.  10:32 (Peak)    - Morning peak
4.  11:07 (Normal)  - Normal hours
5.  [Skip lunch 12-2 PM]
6.  14:12 (Peak)    - Afternoon peak start
7.  14:45 (Peak)    - Afternoon peak
8.  15:23 (Peak)    - Afternoon peak
9.  15:58 (Normal)  - Normal hours
10. 16:35 (Normal)  - Normal hours
11. 17:08 (Low)     - End of day
12. 17:41 (Low)     - End of day
```

---

### Throughout the Day (Every 15 Minutes)

**2. Check and Send Emails**
```
00:00 - send_warmup_emails_task
00:15 - send_warmup_emails_task
00:30 - send_warmup_emails_task
...
23:45 - send_warmup_emails_task

Each execution:
- Checks business hours
- Evaluates timing decision
- Sends if probability check passes
- Updates database
```

---

### Throughout the Day (Every 5 Minutes)

**3. Check Replies**
```
00:00 - check_replies_task
00:05 - check_replies_task
00:10 - check_replies_task
...
23:55 - check_replies_task

Each execution:
- Polls Gmail for unread messages
- Updates email records with replies
- Tracks engagement metrics
```

---

### Every 6 Hours

**4. Status Reports**
```
00:00 - warmup_status_report_task
06:00 - warmup_status_report_task
12:00 - warmup_status_report_task
18:00 - warmup_status_report_task

Output:
📊 warmup@example.com: Phase 2: Building trust (Day 10/14) | 
   Today: 8/12 | Progress: 24.0% | Total sent: 87
```

---

### Midnight (00:01)

**5. Advance Warmup Day**
```
00:01 - advance_warmup_day_task

For each warmup account:
- Increment warmup_day
- Recalculate daily_limit
- Log phase transitions
- Reset daily counters
```

---

## Monitoring & Analytics

### Real-Time Monitoring

**Check Account Status**:
```bash
curl http://localhost:5000/api/analytics/account/1 | jq
```

**Response**:
```json
{
  "account_id": 1,
  "email": "warmup@example.com",
  "total_emails": 87,
  "opened_emails": 58,
  "replied_emails": 21,
  "open_rate": 66.67,
  "reply_rate": 24.14,
  "warmup_score": 50,
  "daily_limit": 12,
  "is_active": true
}
```

---

### System Overview

**Check Overall Stats**:
```bash
curl http://localhost:5000/api/analytics/overview | jq
```

**Response**:
```json
{
  "total_accounts": 3,
  "total_emails": 87,
  "total_opened": 58,
  "total_replied": 21,
  "overall_open_rate": 66.67,
  "overall_reply_rate": 24.14
}
```

---

### Log Monitoring

**Celery Worker Logs**:
```
[2025-10-01 11:15:32] INFO: Skipping send for warmup@example.com: Ahead of schedule
[2025-10-01 11:30:18] INFO: Sending email for warmup@example.com: Slightly behind, good timing
[2025-10-01 11:30:19] INFO: Warmup email sent from warmup@example.com to pool1@example.com (8/12)
[2025-10-01 11:30:19] INFO: Next email for warmup@example.com in 8m 7s
```

**Celery Beat Logs**:
```
[2025-10-01 08:30:00] INFO: 📅 Daily schedule generated for 1 account(s)
[2025-10-01 12:00:00] INFO: 📊 Status report generated for 1 warmup account(s)
[2025-10-01 00:01:00] INFO: Advanced warmup for warmup@example.com: Day 10 → 11
[2025-10-01 00:01:00] INFO:   Phase: Phase 2: Building trust (Day 10/14) → Phase 2: Building trust (Day 11/14)
[2025-10-01 00:01:00] INFO:   Daily limit: 12 → 12 emails/day
```

---

For API details, see [API_REFERENCE.md](API_REFERENCE.md).  
For technical implementation, see [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md).  
For database structure, see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).
