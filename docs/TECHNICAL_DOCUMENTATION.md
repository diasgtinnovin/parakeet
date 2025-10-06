# Email Warmup POC - Technical Documentation

## Table of Contents
1. [Core Components](#core-components)
2. [Services Deep Dive](#services-deep-dive)
3. [Database Models](#database-models)
4. [Celery Tasks](#celery-tasks)
5. [API Blueprints](#api-blueprints)
6. [Configuration System](#configuration-system)
7. [Code Flow Examples](#code-flow-examples)

---

## Core Components

### 1. Flask Application Factory (`app/__init__.py`)

**Purpose**: Creates and configures the Flask application instance.

```python
def create_app():
    app = Flask(__name__)
    
    # Database configuration with connection pooling
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,           # Base pool size
        'max_overflow': 20,        # Additional connections
        'pool_timeout': 30,        # Wait timeout for connection
        'pool_recycle': 3600,      # Recycle after 1 hour
        'pool_pre_ping': True,     # Validate before use
    }
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(accounts_bp, url_prefix='/api/accounts')
    app.register_blueprint(emails_bp, url_prefix='/api/emails')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(oauth_bp, url_prefix='/api/oauth')
```

**Key Features**:
- Connection pooling for database efficiency
- Blueprint registration for modular routing
- CORS enabled for cross-origin requests
- Celery integration for async tasks

---

## Services Deep Dive

### 1. AI Service (`app/services/ai_service.py`)

**Purpose**: Generates human-like email content using hybrid approach.

#### Architecture

```
AIService
├── Initialization
│   ├── Load templates from files
│   ├── Load placeholders
│   ├── Load AI prompts
│   ├── Load configuration
│   └── Initialize OpenAI client (if enabled)
│
├── Generation Methods (4 types)
│   ├── Pure Template (25%)
│   ├── Template + AI Fill (45%)
│   ├── Template + AI Addon (25%)
│   └── AI Seeded (5%)
│
└── Content Enhancement
    ├── Humanization (contractions, filler words)
    ├── Timing context (morning/afternoon/evening)
    ├── Emotional touches (emojis, expressions)
    ├── Intentional imperfections (rare)
    └── Spam validation
```

#### Key Methods

**`__init__(api_key=None, use_ai=True)`**
- Initializes the service with API key validation
- Loads all templates, placeholders, prompts, and config
- Sets up generation ratios based on AI availability

```python
if self.ai_available:
    self.generation_ratios = {
        'pure_template': 0.25,
        'template_ai_fill': 0.45,
        'ai_addon': 0.25,
        'ai_seeded': 0.05
    }
else:
    # Fallback to 100% templates if AI unavailable
    self.generation_ratios = {'pure_template': 1.0, ...}
```

**`generate_email_content(email_type='general')`**
- Main entry point for content generation
- Selects generation method based on ratios
- Validates content for spam patterns
- Returns: `{'subject': str, 'content': str, 'generation_type': str, 'template_type': str}`

**`_generate_pure_template_content()`**
- Selects random template from category
- Fills placeholders with random values
- No AI involvement

**`_fill_template_placeholders(template, use_ai=False)`**
- Replaces `{placeholder}` with actual values
- Can use AI to generate contextual values
- Falls back to random selection if AI fails

**`_generate_ai_addon(base_content)`**
- Takes template-based content
- AI generates 1-2 additional sentences
- Adds natural variation to templates

**`_generate_ai_seeded_content(theme)`**
- Fully AI-generated email
- Uses enhanced themes for human-like content
- Applies post-processing humanization

**`_humanize_content(content)`**
- Adds contractions (I'm, you're, it's)
- Inserts filler words (anyway, by the way)
- Adds emotional touches (emojis, lol)
- Intentional imperfections (5% rate)

**`_validate_content(content)`**
- Checks for spam patterns (FREE, URGENT, CLICK HERE)
- Detects excessive word repetition
- Prevents promotional language
- Returns: `bool` (True if clean)

#### Template System

**Email Templates Format**: `TYPE|SUBJECT|CONTENT`
```
general|Hey there!|{greeting} {casual_phrase} Hope you're doing well! {closing}
follow_up|Following up|{greeting} Just wanted to follow up. {closing}
```

**Placeholder Format**: `TYPE:VALUE`
```
greeting:Hey there!
greeting:Hi!
casual_phrase:Hope all is well.
closing:Take care!
```

**AI Prompts Format**: `TYPE|PROMPT`
```
ai_seeded|Write a short, casual email (2-3 sentences) with this theme: {theme}...
```

**Configuration Format**: `SETTING:VALUE`
```
pure_template_ratio:0.25
ai_temperature:0.9
enable_contractions:true
```

---

### 2. Gmail Service (`app/services/gmail_service.py`)

**Purpose**: Handles Gmail API interactions for sending and checking emails.

#### Key Methods

**`authenticate_with_token(token_data)`**
- Authenticates using OAuth token
- Refreshes token if expired
- Builds Gmail API service client
- Returns: `bool` (success/failure)

```python
creds = Credentials.from_authorized_user_info(token_data, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
self.service = build('gmail', 'v1', credentials=creds)
```

**`send_email(to_address, subject, content, tracking_pixel_id)`**
- Creates MIME multipart message
- Embeds tracking pixel in HTML
- Sends via Gmail API
- Returns: `message_id` or `None`

```python
html_content = f"""
{content}
<img src="http://localhost:5000/track/open/{tracking_pixel_id}" 
     width="1" height="1" style="display:none;">
"""
```

**`check_replies(account_email)`**
- Searches for unread messages
- Query: `to:{account_email} is:unread`
- Returns: `int` (count of replies)

#### Gmail API Scopes
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',      # Send emails
    'https://www.googleapis.com/auth/gmail.readonly'   # Read emails
]
```

---

### 3. Human Timing Service (`app/services/human_timing_service.py`)

**Purpose**: Generates human-like email sending patterns to avoid detection.

#### Configuration
```python
business_hours = {
    'start': 9,      # 9 AM
    'end': 18,       # 6 PM
    'lunch_start': 12,
    'lunch_end': 14,
}

peak_periods = [(9, 11), (14, 16)]  # Morning & afternoon peaks
low_periods = [(12, 14), (17, 18)]  # Lunch & end of day
```

#### Key Methods

**`is_business_hours(dt=None)`**
- Checks if time is within business hours (9 AM - 6 PM)
- Excludes weekends (Saturday/Sunday)
- Handles timezone conversions
- Returns: `bool`

**`get_activity_weight(dt=None)`**
- Returns probability multiplier for sending (0.0 - 1.0)
- Weekend: 0.1 (very low)
- Outside business hours: 0.2 (low)
- Peak periods (9-11 AM, 2-4 PM): 1.0 (high)
- Low periods (lunch, end of day): 0.4 (reduced)
- Normal business hours: 0.7 (moderate)

**`calculate_send_delay(base_interval_minutes=10)`**
- Calculates human-like delay in seconds
- Applies activity-based variation:
  - Peak hours: 50%-120% of base (more frequent)
  - Normal hours: 80%-150% of base
  - Low activity: 120%-200% of base
  - Very low: 200%-400% of base
- Adds random jitter (±30 seconds)
- Minimum delay: 30 seconds

**`should_send_now(last_sent, min_interval_minutes, daily_limit, emails_sent_today)`**
- **Core decision-making function** for email sending
- Returns: `(bool, str)` - (should_send, reason)

Logic Flow:
```
1. Check business hours → Outside? Return False
2. Check minimum interval → Too soon? Return False
3. Calculate day progress (0.0 - 1.0)
4. Calculate expected emails by now (non-linear curve)
5. Determine if behind/on-track/ahead of schedule
6. Base probability:
   - Way ahead: 5%
   - On track: 15%
   - Slightly behind: 25%
   - Significantly behind: 40%
7. Apply activity weight multiplier
8. Apply time-since-last-sent factor:
   - Recent (<15 min): 0.3x (reduce clustering)
   - Medium (15-45 min): 1.0x
   - Longer (45-120 min): 1.3x
   - Very long (>120 min): 1.6x
9. Add randomness (±20%)
10. Make probabilistic decision
```

**`_calculate_expected_emails_by_now(day_progress, daily_limit)`**
- **Non-linear distribution** throughout the day
- First 1/3 (9 AM - 12 PM): 40% of daily emails
- Lunch period (12 PM - 2 PM): 10% of daily emails
- Afternoon peak (2 PM - 5 PM): 40% of daily emails
- End of day (5 PM - 6 PM): 10% of daily emails
- Adds ±15% randomness to avoid predictability

**`get_daily_send_schedule(daily_limit, start_date=None)`**
- Generates complete daily schedule
- Distributes emails across business hours
- Skips lunch hour with 70% probability
- Returns: `List[datetime]`

**Example Output**:
```
Daily schedule for user@example.com (Phase 1: Initial warmup):
   Target: 5 emails between 9 AM - 6 PM
   1.  09:23 (Peak activity)
   2.  10:47 (Peak activity)
   3.  14:15 (Peak activity)
   4.  15:38 (Peak activity)
   5.  17:22 (Low activity)
```

---

## Database Models

### 1. Account Model (`app/models/account.py`)

**Purpose**: Represents email accounts (both warmup and pool accounts).

#### Schema
```python
class Account(db.Model):
    # Identity
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'gmail', 'outlook'
    
    # OAuth credentials
    oauth_token = db.Column(db.Text, nullable=False)  # JSON string
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Account settings
    is_active = db.Column(db.Boolean, default=True)
    daily_limit = db.Column(db.Integer, default=5)
    warmup_score = db.Column(db.Integer, default=0)
    
    # Warmup configuration
    account_type = db.Column(db.String(20), default='pool')  # 'warmup' or 'pool'
    warmup_target = db.Column(db.Integer, default=50)  # Target emails/day at full warmup
    warmup_day = db.Column(db.Integer, default=0)  # Current day (0 = not started)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    emails = db.relationship('Email', backref='account', lazy=True)
```

#### Key Methods

**`get_oauth_token_data()`**
- Parses JSON oauth_token field
- Returns: `dict` or `None`

**`set_oauth_token_data(token_data)`**
- Serializes dict to JSON
- Stores in oauth_token field

**`calculate_daily_limit()`**
- **Warmup ramping algorithm**
- Returns appropriate limit based on warmup_day

```python
# Phase 1: Days 1-7 → 10% of target (min 5)
if day <= 7:
    return max(5, int(target * 0.1))

# Phase 2: Days 8-14 → 25% of target (min 10)
elif day <= 14:
    return max(10, int(target * 0.25))

# Phase 3: Days 15-21 → 50% of target (min 15)
elif day <= 21:
    return max(15, int(target * 0.5))

# Phase 4: Days 22-28 → 75% of target (min 20)
elif day <= 28:
    return max(20, int(target * 0.75))

# Phase 5: Days 29+ → 100% of target
else:
    return target
```

**`get_warmup_phase()`**
- Returns human-readable phase description
- Examples:
  - "Phase 1: Initial warmup (Day 3/7)"
  - "Phase 3: Increasing volume (Day 18/21)"
  - "Phase 5: Full warmup (Day 35)"

**`update_daily_limit()`**
- Recalculates and updates daily_limit
- Returns: `(old_limit, new_limit)` or `(None, None)`

---

### 2. Email Model (`app/models/email.py`)

**Purpose**: Represents sent warmup emails with tracking data.

#### Schema
```python
class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    
    # Email content
    to_address = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Tracking
    tracking_pixel_id = db.Column(db.String(100), unique=True, nullable=False)
    is_opened = db.Column(db.Boolean, default=False)
    is_replied = db.Column(db.Boolean, default=False)
    
    # Timestamps
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    opened_at = db.Column(db.DateTime, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
```

#### Tracking Flow
```
Email Sent → tracking_pixel_id generated (UUID)
           ↓
Email Opened → Pixel image requested
             ↓
             /track/open/{tracking_pixel_id} endpoint hit
             ↓
             is_opened = True, opened_at = now
             
Email Replied → IMAP check finds reply
              ↓
              is_replied = True, replied_at = now
```

---

## Celery Tasks

### Configuration (`celery_beat_schedule.py`)

**Celery Setup**:
```python
celery = Celery('email_warmup_service')
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL'),  # Redis
    result_backend=os.getenv('CELERY_RESULT_BACKEND'),  # Redis
    timezone='Asia/Kolkata',
    enable_utc=True,
)
```

**Beat Schedule**:
```python
beat_schedule = {
    'send-warmup-emails': {
        'task': 'app.tasks.email_tasks.send_warmup_emails_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'check-replies': {
        'task': 'app.tasks.email_tasks.check_replies_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'advance-warmup-day': {
        'task': 'app.tasks.email_tasks.advance_warmup_day_task',
        'schedule': crontab(hour=0, minute=1),  # Daily at 00:01
    },
    'warmup-status-report': {
        'task': 'app.tasks.email_tasks.warmup_status_report_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'generate-daily-schedule': {
        'task': 'app.tasks.email_tasks.generate_daily_schedule_task',
        'schedule': crontab(hour=8, minute=30),  # Daily at 8:30 AM
    },
}
```

### Task Implementations (`app/tasks/email_tasks.py`)

#### 1. `send_warmup_emails_task()`

**Purpose**: Main task that sends warmup emails.

**Flow**:
```
1. Get all warmup accounts (account_type='warmup', is_active=True)
2. Get all pool accounts (account_type='pool', is_active=True)
3. For each warmup account:
   a. Update daily limit based on warmup progress
   b. Check if daily limit reached
   c. Get last sent email timestamp
   d. Ask HumanTimingService: should_send_now()?
   e. If yes:
      - Select random pool account as recipient
      - Generate AI content
      - Generate tracking pixel ID
      - Authenticate with Gmail
      - Send email
      - Save Email record to database
      - Log progress
4. Return summary
```

**Code Snippet**:
```python
# Check if we should send based on human timing
should_send, timing_reason = timing_service.should_send_now(
    last_sent=last_sent, 
    min_interval_minutes=5,
    daily_limit=current_limit,
    emails_sent_today=today_emails
)

if not should_send:
    logger.debug(f"Skipping send for {account.email}: {timing_reason}")
    continue

logger.info(f"Sending email for {account.email}: {timing_reason}")
```

#### 2. `check_replies_task()`

**Purpose**: Checks for email replies and updates engagement metrics.

**Flow**:
```
1. Get all warmup accounts
2. For each account:
   a. Authenticate with Gmail
   b. Check for unread replies
   c. Update Email records (is_replied=True, replied_at=now)
   d. Commit to database
3. Return summary
```

#### 3. `advance_warmup_day_task()`

**Purpose**: Advances warmup day counter once daily (runs at midnight).

**Flow**:
```
1. Get all warmup accounts
2. For each account:
   a. Check if last update was yesterday or earlier
   b. Increment warmup_day by 1
   c. Recalculate daily_limit based on new day
   d. Log phase transitions (days 8, 15, 22, 29)
   e. Update database
3. Return summary
```

**Example Log**:
```
Advanced warmup for user@example.com: Day 7 → 8
  Phase: Phase 1: Initial warmup (Day 7/7) → Phase 2: Building trust (Day 8/14)
  Daily limit: 5 → 12 emails/day
🎉 user@example.com entered new warmup phase: Phase 2: Building trust (Day 8/14)
```

#### 4. `warmup_status_report_task()`

**Purpose**: Generates status report for monitoring (every 6 hours).

**Output**:
```
📊 user@example.com: Phase 2: Building trust (Day 10/14) | 
    Today: 8/12 | Progress: 24.0% | Total sent: 67
```

#### 5. `generate_daily_schedule_task()`

**Purpose**: Generates and logs daily sending schedule (8:30 AM).

**Output**:
```
📅 Daily schedule for user@example.com (Phase 2: Building trust (Day 10/14)):
   Target: 12 emails between 9 AM - 6 PM
   1.  09:15 (Peak activity)
   2.  09:48 (Peak activity)
   ...
   12. 17:35 (Low activity)
```

---

## API Blueprints

### 1. OAuth Routes (`app/api/oauth/routes.py`)

#### `GET /api/oauth/signin`
- HTML sign-in page with "Sign in with Google" button

#### `GET /api/oauth/login`
- Initiates Google OAuth flow
- Redirects to Google consent screen
- Stores OAuth state in session

#### `GET /api/oauth/callback`
- Handles OAuth callback from Google
- Exchanges authorization code for tokens
- Gets user email from Gmail API
- Creates or updates Account record
- Returns success HTML page

**Flow**:
```
User → /signin → Click button → /login → Google OAuth → /callback → Account created
```

---

### 2. Accounts Routes (`app/api/accounts/routes.py`)

#### `POST /api/accounts/add`
**Purpose**: Manually add account with OAuth token.

**Request**:
```json
{
  "email": "user@example.com",
  "provider": "gmail",
  "oauth_token": {...},
  "daily_limit": 5
}
```

**Response**:
```json
{
  "message": "Account added successfully",
  "account_id": 1,
  "email": "user@example.com"
}
```

#### `GET /api/accounts/list`
**Purpose**: List all active accounts.

**Response**:
```json
{
  "accounts": [
    {
      "id": 1,
      "email": "user@example.com",
      "provider": "gmail",
      "daily_limit": 5,
      "warmup_score": 42,
      "created_at": "2025-10-01T10:30:00"
    }
  ]
}
```

#### `POST /api/accounts/<id>/pause`
**Purpose**: Pause warmup for account (sets is_active=False).

#### `POST /api/accounts/<id>/resume`
**Purpose**: Resume warmup for account (sets is_active=True).

---

### 3. Analytics Routes (`app/api/analytics/routes.py`)

#### `GET /api/analytics/account/<id>`
**Purpose**: Get detailed analytics for specific account.

**Response**:
```json
{
  "account_id": 1,
  "email": "user@example.com",
  "total_emails": 67,
  "opened_emails": 42,
  "replied_emails": 15,
  "open_rate": 62.69,
  "reply_rate": 22.39,
  "warmup_score": 48,
  "daily_limit": 12,
  "is_active": true
}
```

**Warmup Score Calculation**:
```python
warmup_score = min(100, int((open_rate * 0.6 + reply_rate * 0.4) * 2))
# 60% weight on opens, 40% on replies, scaled to 0-100
```

#### `GET /api/analytics/overview`
**Purpose**: Get system-wide analytics.

**Response**:
```json
{
  "total_accounts": 5,
  "total_emails": 342,
  "total_opened": 215,
  "total_replied": 87,
  "overall_open_rate": 62.87,
  "overall_reply_rate": 25.44
}
```

---

### 4. Emails Routes (`app/api/emails/routes.py`)

#### `GET /track/open/<tracking_pixel_id>`
**Purpose**: Track email opens via invisible 1x1 pixel.

**Flow**:
```
Email opened → HTML loads → <img src="/track/open/{id}"> requested
            ↓
Find Email by tracking_pixel_id
            ↓
Set is_opened=True, opened_at=now
            ↓
Return 1x1 transparent PNG
```

**Response**: Binary PNG image (1x1 transparent pixel)

---

## Configuration System

### Environment Variables (`.env`)

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/email_warmup

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI
USE_OPENAI=true
OPENAI_API_KEY=sk-...

# Flask
SECRET_KEY=your-secret-key-change-in-production
```

### Template Configuration Files

**`generation_config.txt`**:
```
pure_template_ratio:0.25
template_ai_fill_ratio:0.45
ai_addon_ratio:0.25
ai_seeded_ratio:0.05

ai_temperature:0.9
max_content_tokens:120
enable_contractions:true
imperfection_rate:0.05
```

---

## Code Flow Examples

### Complete Email Sending Flow

```
1. Celery Beat triggers send_warmup_emails_task (every 15 min)
                    ↓
2. Task queries warmup accounts from database
                    ↓
3. For warmup account A (warmup_day=10, target=50):
   a. calculate_daily_limit() → 12 emails/day (Phase 2: 25%)
   b. Query today's sent emails → 7 sent
   c. Get last email timestamp → 10:47 AM
   d. Current time → 11:15 AM (28 min since last)
                    ↓
4. HumanTimingService.should_send_now():
   a. Business hours? → Yes (11:15 AM)
   b. Minimum interval (5 min)? → Yes (28 min passed)
   c. Day progress → 0.25 (25% through business day)
   d. Expected emails by now → 3 (40% of 12 * 0.25 day progress)
   e. Emails behind → -4 (sent 7, expected 3 = ahead)
   f. Base probability → 0.05 (way ahead)
   g. Activity weight → 1.0 (peak period 9-11 AM)
   h. Time-since-last factor → 1.0 (28 min = medium gap)
   i. Final probability → 0.05 * 1.5 * 1.0 * 1.1 (random) = 0.08
   j. Decision → random() = 0.15 > 0.08 → DON'T SEND
   k. Return (False, "Ahead of schedule, waiting")
                    ↓
5. Task skips sending, logs reason, moves to next check
```

### Account Warmup Lifecycle

```
Day 0: OAuth signin → Account created
       account_type='warmup', warmup_day=0, warmup_target=50
                    ↓
Day 1: advance_warmup_day_task runs at 00:01
       warmup_day=0 → 1
       calculate_daily_limit() → 5 (10% of 50)
                    ↓
Day 1-7: Send 5 emails/day with human timing
         Opens tracked, replies detected
         Warmup score calculated
                    ↓
Day 8: Phase transition!
       warmup_day=7 → 8
       calculate_daily_limit() → 12 (25% of 50)
       Log: "🎉 Entered Phase 2: Building trust"
                    ↓
Day 8-14: Send 12 emails/day
                    ↓
Day 15: Phase 3 → 25 emails/day (50%)
Day 22: Phase 4 → 37 emails/day (75%)
Day 29: Phase 5 → 50 emails/day (100% target)
                    ↓
Day 29+: Maintain 50 emails/day, full warmup achieved
```

---

This technical documentation provides a deep understanding of the codebase implementation. For API usage, see [API_REFERENCE.md](API_REFERENCE.md). For workflow explanations, see [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md).
