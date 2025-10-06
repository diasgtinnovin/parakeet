# Email Warmup POC - Database Schema

## Table of Contents
1. [Overview](#overview)
2. [Tables](#tables)
3. [Relationships](#relationships)
4. [Indexes](#indexes)
5. [Sample Queries](#sample-queries)
6. [Migration History](#migration-history)

---

## Overview

The database uses **PostgreSQL** with **SQLAlchemy ORM** for object-relational mapping. The schema consists of two main tables that track email accounts and sent emails with engagement metrics.

### Database Configuration

```python
# Connection string format
DATABASE_URL = "postgresql://user:password@localhost:5432/email_warmup"

# Connection pooling settings
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,           # Base pool connections
    'max_overflow': 20,        # Additional connections beyond pool_size
    'pool_timeout': 30,        # Seconds to wait for connection
    'pool_recycle': 3600,      # Recycle connections after 1 hour
    'pool_pre_ping': True,     # Validate connections before use
}
```

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      Account                             │
├─────────────────────────────────────────────────────────┤
│ PK  id                    INTEGER                        │
│     email                 VARCHAR(255)  UNIQUE NOT NULL  │
│     provider              VARCHAR(50)   NOT NULL         │
│     oauth_token           TEXT          NOT NULL         │
│     refresh_token         TEXT          NULL             │
│     token_expires_at      TIMESTAMP     NULL             │
│     is_active             BOOLEAN       DEFAULT TRUE     │
│     daily_limit           INTEGER       DEFAULT 5        │
│     warmup_score          INTEGER       DEFAULT 0        │
│     account_type          VARCHAR(20)   DEFAULT 'pool'   │
│     warmup_target         INTEGER       DEFAULT 50       │
│     warmup_day            INTEGER       DEFAULT 0        │
│     created_at            TIMESTAMP     DEFAULT NOW()    │
│     updated_at            TIMESTAMP     DEFAULT NOW()    │
└─────────────────────────────────────────────────────────┘
                                │
                                │ 1:N
                                │
                                ▼
┌─────────────────────────────────────────────────────────┐
│                       Email                              │
├─────────────────────────────────────────────────────────┤
│ PK  id                    INTEGER                        │
│ FK  account_id            INTEGER       NOT NULL         │
│     to_address            VARCHAR(255)  NOT NULL         │
│     subject               VARCHAR(500)  NOT NULL         │
│     content               TEXT          NOT NULL         │
│     tracking_pixel_id     VARCHAR(100)  UNIQUE NOT NULL  │
│     is_opened             BOOLEAN       DEFAULT FALSE    │
│     is_replied            BOOLEAN       DEFAULT FALSE    │
│     sent_at               TIMESTAMP     DEFAULT NOW()    │
│     opened_at             TIMESTAMP     NULL             │
│     replied_at            TIMESTAMP     NULL             │
└─────────────────────────────────────────────────────────┘
```

---

## Tables

### 1. Account Table

**Purpose**: Stores email account information, OAuth credentials, and warmup configuration.

**Schema Definition**:

```sql
CREATE TABLE account (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(255) UNIQUE NOT NULL,
    provider            VARCHAR(50) NOT NULL,
    oauth_token         TEXT NOT NULL,
    refresh_token       TEXT,
    token_expires_at    TIMESTAMP,
    is_active           BOOLEAN DEFAULT TRUE,
    daily_limit         INTEGER DEFAULT 5,
    warmup_score        INTEGER DEFAULT 0,
    account_type        VARCHAR(20) DEFAULT 'pool',
    warmup_target       INTEGER DEFAULT 50,
    warmup_day          INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Column Details**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key, auto-increment |
| `email` | VARCHAR(255) | NO | - | Email address (unique) |
| `provider` | VARCHAR(50) | NO | - | Email provider ('gmail', 'outlook') |
| `oauth_token` | TEXT | NO | - | JSON string with OAuth credentials |
| `refresh_token` | TEXT | YES | NULL | OAuth refresh token (encrypted) |
| `token_expires_at` | TIMESTAMP | YES | NULL | Token expiration timestamp |
| `is_active` | BOOLEAN | NO | TRUE | Whether account is actively sending |
| `daily_limit` | INTEGER | NO | 5 | Current daily email sending limit |
| `warmup_score` | INTEGER | NO | 0 | Warmup effectiveness score (0-100) |
| `account_type` | VARCHAR(20) | NO | 'pool' | 'warmup' or 'pool' |
| `warmup_target` | INTEGER | NO | 50 | Target emails/day at full warmup |
| `warmup_day` | INTEGER | NO | 0 | Current day in warmup schedule |
| `created_at` | TIMESTAMP | NO | NOW() | Account creation timestamp |
| `updated_at` | TIMESTAMP | NO | NOW() | Last update timestamp |

**OAuth Token Structure** (stored as JSON in `oauth_token` column):
```json
{
  "token": "ya29.a0Ae4lvC...",
  "refresh_token": "1//0eH...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789.apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "scopes": [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
  ]
}
```

**Account Types**:
- **`warmup`**: Account being warmed up (sender)
  - Sends emails to pool accounts
  - Tracks warmup progress via `warmup_day`
  - Daily limit increases with warmup phases
  
- **`pool`**: Recipient account
  - Receives warmup emails
  - Helps build sender reputation
  - May reply to emails (engagement simulation)

**Warmup Phases** (calculated from `warmup_day`):

| Phase | Days | Daily Limit | % of Target |
|-------|------|-------------|-------------|
| Phase 1 | 1-7 | max(5, target × 0.1) | 10% |
| Phase 2 | 8-14 | max(10, target × 0.25) | 25% |
| Phase 3 | 15-21 | max(15, target × 0.5) | 50% |
| Phase 4 | 22-28 | max(20, target × 0.75) | 75% |
| Phase 5 | 29+ | target | 100% |

**Sample Records**:

```sql
-- Warmup account
INSERT INTO account (email, provider, oauth_token, account_type, warmup_target, warmup_day, daily_limit)
VALUES (
    'warmup@example.com',
    'gmail',
    '{"token":"ya29...","refresh_token":"1//0e..."}',
    'warmup',
    50,
    10,
    12
);

-- Pool account
INSERT INTO account (email, provider, oauth_token, account_type)
VALUES (
    'pool1@example.com',
    'gmail',
    '{"token":"ya29...","refresh_token":"1//0e..."}',
    'pool'
);
```

---

### 2. Email Table

**Purpose**: Tracks sent warmup emails with engagement metrics (opens, replies).

**Schema Definition**:

```sql
CREATE TABLE email (
    id                  SERIAL PRIMARY KEY,
    account_id          INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    to_address          VARCHAR(255) NOT NULL,
    subject             VARCHAR(500) NOT NULL,
    content             TEXT NOT NULL,
    tracking_pixel_id   VARCHAR(100) UNIQUE NOT NULL,
    is_opened           BOOLEAN DEFAULT FALSE,
    is_replied          BOOLEAN DEFAULT FALSE,
    sent_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opened_at           TIMESTAMP,
    replied_at          TIMESTAMP
);
```

**Column Details**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | AUTO | Primary key, auto-increment |
| `account_id` | INTEGER | NO | - | Foreign key to account.id |
| `to_address` | VARCHAR(255) | NO | - | Recipient email address |
| `subject` | VARCHAR(500) | NO | - | Email subject line |
| `content` | TEXT | NO | - | Email body content |
| `tracking_pixel_id` | VARCHAR(100) | NO | - | Unique UUID for tracking pixel |
| `is_opened` | BOOLEAN | NO | FALSE | Whether email was opened |
| `is_replied` | BOOLEAN | NO | FALSE | Whether email received reply |
| `sent_at` | TIMESTAMP | NO | NOW() | Email sent timestamp |
| `opened_at` | TIMESTAMP | YES | NULL | Email opened timestamp |
| `replied_at` | TIMESTAMP | YES | NULL | Reply received timestamp |

**Tracking Pixel Flow**:

1. Email sent with embedded pixel:
   ```html
   <img src="http://localhost:5000/track/open/{tracking_pixel_id}" 
        width="1" height="1" style="display:none;">
   ```

2. Recipient opens email → Image loads → Endpoint hit

3. Database update:
   ```sql
   UPDATE email 
   SET is_opened = TRUE, opened_at = CURRENT_TIMESTAMP 
   WHERE tracking_pixel_id = '{id}' AND is_opened = FALSE;
   ```

**Sample Records**:

```sql
-- Sent email (not yet opened/replied)
INSERT INTO email (account_id, to_address, subject, content, tracking_pixel_id)
VALUES (
    1,
    'pool1@example.com',
    'Hey there!',
    'Hey friend! Hope you''re doing awesome. Talk soon!',
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
);

-- Opened email
INSERT INTO email (account_id, to_address, subject, content, tracking_pixel_id, is_opened, opened_at)
VALUES (
    1,
    'pool2@example.com',
    'Just saying hi',
    'Hi there! Hope all is well. Take care!',
    'b2c3d4e5-f6g7-8901-bcde-f12345678901',
    TRUE,
    '2025-10-01 10:35:22'
);

-- Opened and replied
INSERT INTO email (account_id, to_address, subject, content, tracking_pixel_id, is_opened, is_replied, opened_at, replied_at)
VALUES (
    1,
    'pool1@example.com',
    'Hope you''re well',
    'Hello! How have you been? Best wishes!',
    'c3d4e5f6-g7h8-9012-cdef-123456789012',
    TRUE,
    TRUE,
    '2025-10-01 11:20:15',
    '2025-10-01 11:45:30'
);
```

---

## Relationships

### One-to-Many: Account → Email

**Relationship Type**: One account can have many emails

**Foreign Key**: `email.account_id` references `account.id`

**SQLAlchemy Definition**:
```python
# In Account model
emails = db.relationship('Email', backref='account', lazy=True)

# In Email model
account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
```

**Usage Examples**:

```python
# Get all emails for an account
account = Account.query.get(1)
emails = account.emails  # Returns list of Email objects

# Get account from email
email = Email.query.get(42)
account = email.account  # Returns Account object
```

**Cascade Behavior**:
- `ON DELETE CASCADE`: If account is deleted, all associated emails are deleted

**SQL Join Example**:
```sql
-- Get all emails with account information
SELECT 
    e.id, e.subject, e.to_address, e.sent_at,
    a.email AS from_address, a.account_type
FROM email e
JOIN account a ON e.account_id = a.id
WHERE a.account_type = 'warmup'
ORDER BY e.sent_at DESC;
```

---

## Indexes

### Automatic Indexes

**Primary Keys** (automatically indexed):
- `account.id`
- `email.id`

**Unique Constraints** (automatically indexed):
- `account.email`
- `email.tracking_pixel_id`

### Recommended Indexes

**For Performance Optimization**:

```sql
-- Speed up foreign key joins
CREATE INDEX idx_email_account_id ON email(account_id);

-- Speed up daily email count queries
CREATE INDEX idx_email_sent_at ON email(sent_at);

-- Speed up engagement queries
CREATE INDEX idx_email_opened ON email(is_opened);
CREATE INDEX idx_email_replied ON email(is_replied);

-- Speed up account type filtering
CREATE INDEX idx_account_type ON account(account_type);

-- Speed up active account queries
CREATE INDEX idx_account_active ON account(is_active);

-- Composite index for common query pattern
CREATE INDEX idx_email_account_sent ON email(account_id, sent_at);
```

---

## Sample Queries

### Account Queries

**1. Get all warmup accounts**:
```sql
SELECT id, email, warmup_day, daily_limit, warmup_score
FROM account
WHERE account_type = 'warmup' AND is_active = TRUE;
```

**2. Get all pool accounts**:
```sql
SELECT id, email
FROM account
WHERE account_type = 'pool' AND is_active = TRUE;
```

**3. Calculate warmup phase**:
```sql
SELECT 
    email,
    warmup_day,
    CASE 
        WHEN warmup_day <= 7 THEN 'Phase 1: Initial warmup'
        WHEN warmup_day <= 14 THEN 'Phase 2: Building trust'
        WHEN warmup_day <= 21 THEN 'Phase 3: Increasing volume'
        WHEN warmup_day <= 28 THEN 'Phase 4: Near target'
        ELSE 'Phase 5: Full warmup'
    END AS warmup_phase,
    daily_limit,
    warmup_target
FROM account
WHERE account_type = 'warmup';
```

**4. Get account with OAuth token**:
```sql
SELECT id, email, oauth_token::json AS token_data
FROM account
WHERE email = 'warmup@example.com';
```

---

### Email Queries

**1. Count today's emails for account**:
```sql
SELECT COUNT(*) AS today_count
FROM email
WHERE account_id = 1 
  AND sent_at >= CURRENT_DATE;
```

**2. Get recent sent emails**:
```sql
SELECT id, to_address, subject, sent_at, is_opened, is_replied
FROM email
WHERE account_id = 1
ORDER BY sent_at DESC
LIMIT 10;
```

**3. Get last sent email**:
```sql
SELECT *
FROM email
WHERE account_id = 1
ORDER BY sent_at DESC
LIMIT 1;
```

**4. Find emails by tracking pixel**:
```sql
SELECT id, subject, to_address, is_opened, opened_at
FROM email
WHERE tracking_pixel_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
```

**5. Get unreplied emails from today**:
```sql
SELECT id, to_address, subject, sent_at
FROM email
WHERE account_id = 1
  AND is_replied = FALSE
  AND sent_at >= CURRENT_DATE
ORDER BY sent_at DESC;
```

---

### Analytics Queries

**1. Calculate open and reply rates**:
```sql
SELECT 
    a.id,
    a.email,
    COUNT(e.id) AS total_emails,
    SUM(CASE WHEN e.is_opened THEN 1 ELSE 0 END) AS opened_emails,
    SUM(CASE WHEN e.is_replied THEN 1 ELSE 0 END) AS replied_emails,
    ROUND(100.0 * SUM(CASE WHEN e.is_opened THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0), 2) AS open_rate,
    ROUND(100.0 * SUM(CASE WHEN e.is_replied THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0), 2) AS reply_rate
FROM account a
LEFT JOIN email e ON a.id = e.account_id
WHERE a.account_type = 'warmup'
GROUP BY a.id, a.email;
```

**2. Calculate warmup score**:
```sql
WITH email_stats AS (
    SELECT 
        account_id,
        COUNT(*) AS total,
        SUM(CASE WHEN is_opened THEN 1 ELSE 0 END) AS opened,
        SUM(CASE WHEN is_replied THEN 1 ELSE 0 END) AS replied
    FROM email
    GROUP BY account_id
)
SELECT 
    a.email,
    LEAST(100, 
        CAST((
            (100.0 * es.opened / NULLIF(es.total, 0) * 0.6) +
            (100.0 * es.replied / NULLIF(es.total, 0) * 0.4)
        ) * 2 AS INTEGER)
    ) AS warmup_score
FROM account a
JOIN email_stats es ON a.id = es.account_id
WHERE a.account_type = 'warmup';
```

**3. Get overall system stats**:
```sql
SELECT 
    COUNT(DISTINCT a.id) AS total_accounts,
    COUNT(e.id) AS total_emails,
    SUM(CASE WHEN e.is_opened THEN 1 ELSE 0 END) AS total_opened,
    SUM(CASE WHEN e.is_replied THEN 1 ELSE 0 END) AS total_replied,
    ROUND(100.0 * SUM(CASE WHEN e.is_opened THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0), 2) AS overall_open_rate,
    ROUND(100.0 * SUM(CASE WHEN e.is_replied THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0), 2) AS overall_reply_rate
FROM account a
LEFT JOIN email e ON a.id = e.account_id
WHERE a.is_active = TRUE;
```

**4. Daily email volume by account**:
```sql
SELECT 
    a.email,
    DATE(e.sent_at) AS date,
    COUNT(e.id) AS emails_sent,
    a.daily_limit
FROM account a
JOIN email e ON a.id = e.account_id
WHERE a.account_type = 'warmup'
GROUP BY a.email, DATE(e.sent_at), a.daily_limit
ORDER BY DATE(e.sent_at) DESC, a.email;
```

**5. Hourly email distribution**:
```sql
SELECT 
    EXTRACT(HOUR FROM sent_at) AS hour,
    COUNT(*) AS email_count
FROM email
WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM sent_at)
ORDER BY hour;
```

---

### Advanced Queries

**1. Find accounts approaching daily limit**:
```sql
WITH today_counts AS (
    SELECT account_id, COUNT(*) AS sent_today
    FROM email
    WHERE sent_at >= CURRENT_DATE
    GROUP BY account_id
)
SELECT 
    a.email,
    tc.sent_today,
    a.daily_limit,
    a.daily_limit - tc.sent_today AS remaining
FROM account a
JOIN today_counts tc ON a.id = tc.account_id
WHERE a.account_type = 'warmup'
  AND tc.sent_today >= a.daily_limit * 0.8  -- 80% of limit
ORDER BY remaining;
```

**2. Engagement timeline for account**:
```sql
SELECT 
    DATE(sent_at) AS date,
    COUNT(*) AS sent,
    SUM(CASE WHEN is_opened THEN 1 ELSE 0 END) AS opened,
    SUM(CASE WHEN is_replied THEN 1 ELSE 0 END) AS replied,
    ROUND(100.0 * SUM(CASE WHEN is_opened THEN 1 ELSE 0 END) / COUNT(*), 2) AS open_rate,
    ROUND(100.0 * SUM(CASE WHEN is_replied THEN 1 ELSE 0 END) / COUNT(*), 2) AS reply_rate
FROM email
WHERE account_id = 1
GROUP BY DATE(sent_at)
ORDER BY date DESC;
```

**3. Find stale accounts (no emails in 24 hours)**:
```sql
WITH last_sent AS (
    SELECT account_id, MAX(sent_at) AS last_email
    FROM email
    GROUP BY account_id
)
SELECT 
    a.email,
    a.account_type,
    ls.last_email,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ls.last_email)) / 3600 AS hours_since_last
FROM account a
LEFT JOIN last_sent ls ON a.id = ls.account_id
WHERE a.is_active = TRUE
  AND (ls.last_email IS NULL OR ls.last_email < CURRENT_TIMESTAMP - INTERVAL '24 hours')
ORDER BY hours_since_last DESC NULLS FIRST;
```

**4. Warmup progress report**:
```sql
SELECT 
    a.email,
    a.warmup_day,
    a.daily_limit,
    a.warmup_target,
    CASE 
        WHEN a.warmup_day <= 7 THEN 'Phase 1'
        WHEN a.warmup_day <= 14 THEN 'Phase 2'
        WHEN a.warmup_day <= 21 THEN 'Phase 3'
        WHEN a.warmup_day <= 28 THEN 'Phase 4'
        ELSE 'Phase 5'
    END AS phase,
    ROUND(100.0 * a.daily_limit / a.warmup_target, 2) AS progress_percentage,
    COUNT(e.id) AS total_sent,
    AVG(CASE WHEN e.is_opened THEN 1 ELSE 0 END) * 100 AS avg_open_rate
FROM account a
LEFT JOIN email e ON a.id = e.account_id
WHERE a.account_type = 'warmup'
GROUP BY a.id, a.email, a.warmup_day, a.daily_limit, a.warmup_target;
```

---

## Migration History

### Initial Schema (v1)

```sql
-- Account table
CREATE TABLE account (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    oauth_token TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    daily_limit INTEGER DEFAULT 5,
    warmup_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email table
CREATE TABLE email (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES account(id),
    to_address VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    tracking_pixel_id VARCHAR(100) UNIQUE NOT NULL,
    is_opened BOOLEAN DEFAULT FALSE,
    is_replied BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opened_at TIMESTAMP,
    replied_at TIMESTAMP
);
```

### Warmup Configuration Migration (v2)

**Added warmup fields to Account**:
```sql
ALTER TABLE account ADD COLUMN account_type VARCHAR(20) DEFAULT 'pool';
ALTER TABLE account ADD COLUMN warmup_target INTEGER DEFAULT 50;
ALTER TABLE account ADD COLUMN warmup_day INTEGER DEFAULT 0;
```

**Migration Script**:
```bash
flask db migrate -m "Add warmup configuration fields"
flask db upgrade
```

### OAuth Enhancement Migration (v3)

**Added OAuth refresh tokens**:
```sql
ALTER TABLE account ADD COLUMN refresh_token TEXT;
ALTER TABLE account ADD COLUMN token_expires_at TIMESTAMP;
```

---

## Data Maintenance

### Cleanup Old Emails

```sql
-- Archive emails older than 90 days
CREATE TABLE email_archive AS
SELECT * FROM email 
WHERE sent_at < CURRENT_DATE - INTERVAL '90 days';

-- Delete archived emails
DELETE FROM email 
WHERE sent_at < CURRENT_DATE - INTERVAL '90 days';
```

### Update Warmup Scores

```sql
-- Recalculate warmup scores for all accounts
UPDATE account SET warmup_score = (
    SELECT LEAST(100, 
        CAST((
            (100.0 * SUM(CASE WHEN e.is_opened THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0) * 0.6) +
            (100.0 * SUM(CASE WHEN e.is_replied THEN 1 ELSE 0 END) / NULLIF(COUNT(e.id), 0) * 0.4)
        ) * 2 AS INTEGER)
    )
    FROM email e
    WHERE e.account_id = account.id
)
WHERE account_type = 'warmup';
```

---

For API usage, see [API_REFERENCE.md](API_REFERENCE.md).  
For workflow details, see [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md).  
For technical implementation, see [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md).
