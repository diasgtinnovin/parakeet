# Email Warmup System - Project Overview

## What is This Project?

This is an **automated email warmup system** designed to gradually build and maintain email sender reputation. Email warmup is the process of slowly increasing sending volume from a new email account to establish trust with email service providers (ESPs) like Gmail, preventing emails from landing in spam folders.

The system simulates natural email behavior by sending emails between accounts, opening them, replying, and marking them as important - all with human-like timing patterns to appear authentic to email providers.

## Core Architecture

### Tech Stack
- **Backend**: Flask (Python web framework)
- **Database**: PostgreSQL (data storage)
- **Task Queue**: Celery with Redis (scheduled background tasks)
- **Email Service**: Gmail API (OAuth2 authentication)
- **AI**: OpenAI GPT-4 (optional, for content generation)

### Account Types
1. **Warmup Accounts**: Accounts being warmed up (senders)
   - Gradually increase daily email volume over 5 phases (28+ days)
   - Each has configurable target volume and engagement rates
   
2. **Pool Accounts**: Recipient accounts that simulate engagement
   - Open emails from warmup accounts
   - Send replies to create conversation threads
   - Mark emails as important

## How It Works

### 1. Warmup Phases (Progressive Volume Increase)

The system implements a 5-phase warmup strategy:

| Phase | Days | Target Volume | Purpose |
|-------|------|---------------|---------|
| Phase 1 | 1-7 | 10% of target | Initial trust building |
| Phase 2 | 8-14 | 25% of target | Establishing patterns |
| Phase 3 | 15-21 | 50% of target | Increasing volume |
| Phase 4 | 22-28 | 75% of target | Near full capacity |
| Phase 5 | 29+ | 100% of target | Full warmup achieved |

### 2. Email Scheduling System

**Daily Schedule Generation**:
- Runs at midnight for each timezone
- Distributes emails across business hours (9 AM - 6 PM)
- Activity periods: 60% peak hours, 30% normal hours, 10% low hours
- Skips weekends automatically
- Adds human-like randomization (±15 minutes)

**Email Sending**:
- Executes every 2 minutes to check for due emails
- Respects business hours and timezone settings
- Adds random delays between sends (1-5 seconds)
- Includes "green-bulb" keyword for tracking purposes

### 3. Content Generation (Hybrid AI + Templates)

The system offers flexible content generation:

**Four Generation Methods**:
1. **Pure Template** (30%): Fill placeholders with random values
2. **Template + AI Fill** (40%): AI generates placeholder content
3. **AI Addon** (20%): Template base + AI-generated additions
4. **AI Seeded** (10%): Fully AI-generated conversational emails

**Human-like Features**:
- Natural contractions (I'm, you're, can't)
- Occasional typos (5% rate)
- Filler words (anyway, by the way, actually)
- Time-based context (morning greetings, afternoon check-ins)
- Emotional touches (emojis: 😊, lol, haha)

### 4. Engagement Simulation

**Pool accounts automatically simulate human behavior**:

**Opening Emails**:
- Delay: 30 seconds to 10 minutes (beta distribution for realism)
- Rate: 75-85% (configurable per warmup account)
- Marks as read via Gmail API

**Marking Important**:
- 15-25% of opened emails
- Delay: 45-100 seconds after opening

**Sending Replies**:
- Rate: 50-60% of opened emails (configurable)
- Delay: 5-30 minutes after opening
- AI-generated reply content
- Proper email threading (In-Reply-To headers)

**Reply Detection**:
- Warmup accounts check for incoming replies every 5 minutes
- Matches by subject line and sender
- Updates engagement metrics

### 5. Spam Detection & Recovery

**Automatic Spam Folder Monitoring**:
- Checks pool account spam folders every 6 hours
- Identifies warmup emails that landed in spam
- Automatically marks them as "Not Spam"
- Moves them back to inbox
- Tracks spam statistics for scoring

### 6. Warmup Score Calculation

**Comprehensive scoring system** (0-100 points):

**Components**:
1. **Open Rate Score** (30% weight)
   - ≥60% open rate → 100 points
   - ≥40% → 80 points
   - ≥20% → 60 points

2. **Reply Rate Score** (20% weight)
   - ≥25% reply rate → 100 points
   - ≥15% → 85 points
   - ≥5% → 70 points

3. **Phase Progress Score** (40% weight)
   - Base score by phase (50-100)
   - +10 bonus for meeting targets
   - -15 penalty for falling behind

4. **Spam Penalty** (10% weight)
   - ≤2% spam rate → 100 points
   - ≤5% → 85 points
   - ≤10% → 60 points
   - +10 bonus for 80%+ recovery rate

**Grading System**:
- **A+** (90-100): Ready for full volume campaigns
- **A** (80-89): Excellent progress
- **B** (70-79): Good, needs fine-tuning
- **C** (60-69): Fair, needs attention
- **D** (50-59): Poor, urgent adjustments needed
- **F** (<50): Critical, pause immediately

## Key Services

### GmailService (`gmail_service.py`)
- OAuth2 authentication with automatic token refresh
- Send emails (with proper MIME formatting)
- Send threaded replies
- Fetch unread emails (filtered by sender)
- Mark emails as read/important/not spam
- Check spam folders

### AIService (`ai_service.py`)
- OpenAI GPT-4 integration with fallback templates
- Multiple generation strategies for variety
- Spam pattern validation
- Human-like content post-processing
- Configurable generation ratios

### HumanTimingService (`human_timing_service.py`)
- Business hours detection
- Weekend skipping
- Timezone-aware scheduling
- Activity period distribution (peak/normal/low)
- Randomized intervals for natural patterns

### EngagementSimulationService (`engagement_simulation_service.py`)
- Configurable open/reply rates per warmup account
- Realistic delay calculations (beta distribution)
- Important marking probability
- Human-like timing patterns

### WarmupScoreService (`warmup_score_service.py`)
- Multi-component scoring algorithm
- Personalized recommendations
- Grade assignment with status messages
- Component breakdown for analytics

## Database Models

### Account
- OAuth credentials (encrypted)
- Account type (warmup/pool)
- Warmup configuration (day, phase, target)
- Engagement rates (open_rate, reply_rate)
- Timezone settings
- Warmup score

### Email
- Sender/recipient information
- Subject and content
- Engagement tracking (opened_at, replied_at)
- Gmail message IDs for threading
- Sender's engagement strategy (for pool accounts)

### EmailSchedule
- Pre-calculated send times
- Activity period classification
- Status tracking (pending/sent/failed)
- Retry logic with error logging

### SpamEmail
- Spam detection tracking
- Recovery attempts
- Status (detected/recovered/failed)
- Sender/receiver details

## Celery Task Schedule

**Core Tasks**:
- `generate_daily_schedules_task`: Every hour (catches midnight in all timezones)
- `send_scheduled_emails_task`: Every 2 minutes
- `simulate_engagement_task`: Every 3 minutes
- `check_replies_task`: Every 5 minutes
- `check_spam_folder_task`: Every 6 hours
- `advance_warmup_day_task`: Daily at 00:05 UTC
- `calculate_warmup_scores_task`: Every 6 hours
- `warmup_status_report_task`: Every 6 hours
- `cleanup_old_schedules_task`: Daily at 02:00 UTC

## API Endpoints

### Accounts (`/api/accounts`)
- GET `/`: List all accounts
- POST `/`: Create new account
- GET `/<id>`: Get account details
- PUT `/<id>`: Update account
- POST `/<id>/pause`: Pause warmup
- POST `/<id>/resume`: Resume warmup

### OAuth (`/api/oauth`)
- GET `/google/authorize`: Start OAuth flow
- GET `/google/callback`: Handle OAuth callback

### Analytics (`/api/analytics`)
- GET `/account/<id>`: Account-specific analytics
- GET `/account/<id>/warmup-score`: Detailed score breakdown
- GET `/overview`: System-wide statistics
- GET `/dashboard`: Comprehensive dashboard data

### Emails (`/api/emails`)
- GET `/`: List emails with filters
- GET `/<id>`: Get email details
- POST `/test-send`: Send test email

## Configuration

**Environment Variables**:
```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
GOOGLE_CLIENT_ID=<oauth-client-id>
GOOGLE_CLIENT_SECRET=<oauth-secret>
OPENAI_API_KEY=<openai-key>
USE_OPENAI=true  # Enable AI content generation
```

## Typical Workflow

1. **Setup**: Add warmup and pool accounts via OAuth
2. **Configure**: Set warmup target, timezone, engagement rates
3. **Start**: System generates daily schedules automatically
4. **Monitor**: Check warmup scores, analytics dashboard
5. **Recover**: Automatic spam recovery runs in background
6. **Scale**: After 28+ days and good score, ready for production use

## Success Metrics

- **Warmup Score**: Target A+ (90+) for production readiness
- **Open Rate**: 60%+ indicates good subject lines and timing
- **Reply Rate**: 25%+ shows high engagement
- **Spam Rate**: <2% optimal, <5% acceptable
- **Phase Progress**: Meeting daily targets consistently

---

**Status**: Proof of Concept
**Last Updated**: October 2025

