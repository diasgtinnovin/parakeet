# Email Warmup POC - Project Overview

## Table of Contents
1. [Introduction](#introduction)
2. [Project Purpose](#project-purpose)
3. [Key Features](#key-features)
4. [Architecture Overview](#architecture-overview)
5. [Technology Stack](#technology-stack)
6. [Project Structure](#project-structure)

---

## Introduction

The **Email Warmup Service** is a standalone platform designed to improve email deliverability by automating the warmup process for email accounts. It gradually builds sender reputation by sending controlled, human-like emails to a pool of recipient addresses, simulating realistic engagement patterns (opens, replies), and tracking metrics to ensure optimal email deliverability.

## Project Purpose

### Why Email Warmup?
- **New Email Accounts**: Fresh email accounts have no sender reputation, leading to emails landing in spam
- **Sender Reputation**: Email providers (Gmail, Outlook) track sender behavior to determine trustworthiness
- **Gradual Volume Increase**: Sending too many emails too quickly from a new account triggers spam filters
- **Engagement Metrics**: High open rates and reply rates build positive sender reputation

### What This Service Does
1. **Accepts OAuth tokens** from external platforms for email accounts
2. **Sends controlled volumes** of emails to warmup pool addresses
3. **Simulates human behavior** with natural timing patterns and varied content
4. **Tracks engagement** via tracking pixels (opens) and IMAP polling (replies)
5. **Gradually increases** email volume based on warmup progress
6. **Provides analytics** to monitor warmup effectiveness

## Key Features

### 1. **Account Management**
- **Warmup Accounts**: Email accounts being warmed up (sender accounts)
- **Pool Accounts**: Recipient accounts that receive warmup emails
- **OAuth Integration**: Secure token-based authentication for Gmail
- **Multi-account Support**: Manage multiple warmup and pool accounts

### 2. **Intelligent Email Sending**
- **Hybrid Content Generation**: Combines templates with AI for natural variation
  - Pure Template (25%): Structured templates with random placeholders
  - Template + AI Fill (45%): AI generates natural placeholder values
  - Template + AI Addon (25%): AI adds sentences to templates
  - AI Seeded (5%): Fully AI-generated content
- **Human Timing Patterns**: Variable send times mimicking real human behavior
- **Business Hours Compliance**: Sends during 9 AM - 6 PM business hours
- **Natural Delays**: Random intervals between emails to avoid patterns

### 3. **Warmup Ramping Strategy**
Progressive volume increase over 5 phases:
- **Phase 1 (Days 1-7)**: 10% of target (minimum 5 emails/day)
- **Phase 2 (Days 8-14)**: 25% of target
- **Phase 3 (Days 15-21)**: 50% of target
- **Phase 4 (Days 22-28)**: 75% of target
- **Phase 5 (Days 29+)**: 100% of target

### 4. **Engagement Tracking**
- **Tracking Pixels**: Invisible 1x1 images to detect email opens
- **Reply Detection**: IMAP polling to check for replies
- **Warmup Score**: Calculated from open rate (60%) + reply rate (40%)
- **Daily Limits**: Enforces volume limits per account

### 5. **Analytics & Monitoring**
- **Real-time Metrics**: Emails sent, opened, replied
- **Open/Reply Rates**: Percentage calculations for engagement
- **Warmup Progress**: Current phase, day, and target progress
- **Status Reports**: Periodic reports on all accounts

### 6. **Automated Scheduling**
- **Celery Beat**: Scheduled task execution
- **Email Sending**: Every 15 minutes (human timing decides actual send)
- **Reply Checking**: Every 5 minutes
- **Daily Advancement**: Advances warmup day at midnight
- **Status Reports**: Every 6 hours
- **Daily Schedules**: Generated at 8:30 AM each day

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     External Platform (Parakeet)                 │
│                  (Handles user authentication)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ OAuth Tokens
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Email Warmup Service (Flask)                   │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │   OAuth API  │ Accounts API │  Emails API  │Analytics API │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Business Logic                         │   │
│  │  ┌─────────────┬──────────────┬────────────────────────┐ │   │
│  │  │ AI Service  │Gmail Service │Human Timing Service    │ │   │
│  │  └─────────────┴──────────────┴────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Database Models                          │   │
│  │  ┌──────────────────────┬─────────────────────────────┐  │   │
│  │  │  Account Model       │    Email Model              │  │   │
│  │  │  - id, email         │    - id, subject, content   │  │   │
│  │  │  - oauth_token       │    - is_opened, is_replied  │  │   │
│  │  │  - account_type      │    - tracking_pixel_id      │  │   │
│  │  │  - warmup_day        │    - account_id (FK)        │  │   │
│  │  │  - daily_limit       │                             │  │   │
│  │  └──────────────────────┴─────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬───────────────────────────────────┬─┘
                            │                                   │
                            ▼                                   ▼
                  ┌──────────────────┐              ┌──────────────────┐
                  │   PostgreSQL     │              │   Celery Beat    │
                  │   Database       │              │   (Redis Broker) │
                  │                  │              │                  │
                  │ - Accounts       │              │ - Email Tasks    │
                  │ - Emails         │              │ - Reply Checks   │
                  │ - Metrics        │              │ - Daily Advance  │
                  └──────────────────┘              │ - Status Reports │
                                                    └──────────────────┘
                                                             │
                                                             ▼
                                                    ┌──────────────────┐
                                                    │  Gmail API       │
                                                    │  - Send Emails   │
                                                    │  - Check Replies │
                                                    └──────────────────┘
```

## Technology Stack

### Backend Framework
- **Flask 2.3.3**: Lightweight Python web framework
- **Flask-SQLAlchemy 3.0.5**: ORM for database operations
- **Flask-Migrate 4.0.5**: Database migrations
- **Flask-CORS 4.0.0**: Cross-origin resource sharing

### Database
- **PostgreSQL**: Primary relational database
- **SQLAlchemy Engine Options**:
  - Connection pooling (10 base + 20 overflow)
  - Pool timeout: 30s
  - Connection recycling: 1 hour
  - Pre-ping validation

### Task Queue
- **Celery 5.3.4**: Distributed task queue
- **Redis 5.0.1**: Message broker and result backend
- **Celery Beat**: Scheduled task execution

### Email Services
- **Google OAuth 2.0**: Authentication
- **Gmail API**: Email sending and receiving
- **google-auth 2.23.4**: OAuth authentication library
- **google-api-python-client 2.110.0**: Gmail API client

### AI & Content Generation
- **OpenAI API**: GPT-4o-mini for content generation
- **openai 1.30.0**: Python client library
- **Template System**: Hybrid approach with 4 generation methods

### Other Dependencies
- **python-dotenv 1.0.0**: Environment variable management
- **pytz 2024.1**: Timezone handling
- **requests 2.31.0**: HTTP library
- **httpx 0.25.0**: Async HTTP client

### Testing
- **pytest 7.4.3**: Testing framework
- **pytest-flask 1.3.0**: Flask testing utilities

## Project Structure

```
email-warmup-poc/
├── app/                                    # Main application package
│   ├── __init__.py                         # Flask app factory
│   ├── celery_app.py                       # Celery configuration
│   │
│   ├── api/                                # API endpoints (Blueprints)
│   │   ├── accounts/                       # Account management
│   │   │   ├── __init__.py
│   │   │   └── routes.py                   # Add, list, pause, resume accounts
│   │   │
│   │   ├── analytics/                      # Analytics endpoints
│   │   │   ├── __init__.py
│   │   │   └── routes.py                   # Account & overview analytics
│   │   │
│   │   ├── emails/                         # Email tracking
│   │   │   ├── __init__.py
│   │   │   └── routes.py                   # Tracking pixel endpoint
│   │   │
│   │   └── oauth/                          # OAuth authentication
│   │       ├── __init__.py
│   │       └── routes.py                   # Google OAuth flow
│   │
│   ├── models/                             # Database models
│   │   ├── __init__.py
│   │   ├── account.py                      # Account model with warmup logic
│   │   └── email.py                        # Email model with tracking
│   │
│   ├── services/                           # Business logic services
│   │   ├── __init__.py
│   │   ├── ai_service.py                   # Hybrid content generation (676 lines)
│   │   ├── gmail_service.py                # Gmail API integration
│   │   └── human_timing_service.py         # Human-like timing patterns (351 lines)
│   │
│   ├── tasks/                              # Celery background tasks
│   │   ├── __init__.py
│   │   └── email_tasks.py                  # Send, check replies, advance day, reports
│   │
│   └── templates/                          # Email content templates
│       ├── email_templates.txt             # 46 templates across 8 categories
│       ├── placeholders.txt                # 155 placeholder values
│       ├── ai_prompts.txt                  # 5 AI prompt templates
│       └── generation_config.txt           # Generation ratios & settings
│
├── scripts/                                # Utility scripts
│   ├── check_accounts.py                   # Verify account configuration
│   ├── create_migration.py                 # Database migration helper
│   ├── setup_warmup_config.py              # Interactive warmup setup
│   ├── test_connection_pool.py             # Test database connections
│   ├── test_human_timing.py                # Test timing service
│   └── README.md                           # Script documentation
│
├── migrations/                             # Database migrations
│   └── versions/                           # Migration version files
│
├── instance/                               # Instance-specific files (SQLite, etc.)
│
├── docs/                                   # Documentation (this file)
│   ├── PROJECT_OVERVIEW.md                 # This file
│   ├── TECHNICAL_DOCUMENTATION.md          # Technical deep dive
│   ├── API_REFERENCE.md                    # API endpoints
│   ├── WORKFLOW_GUIDE.md                   # How everything works together
│   └── DATABASE_SCHEMA.md                  # Database structure
│
├── app.py                                  # Flask application entry point
├── celery_beat_schedule.py                # Celery Beat scheduler
├── requirements.txt                        # Python dependencies
├── .env                                    # Environment variables (not in git)
│
├── Email Warmup Service Architecture.txt   # Original architecture document
├── WARMUP_IMPLEMENTATION_GUIDE.md          # Warmup strategy guide
└── TEMPLATE_SYSTEM_README.md               # Template system documentation
```

## Key Concepts

### Account Types
1. **Warmup Account**: The account being warmed up (sends emails)
2. **Pool Account**: Recipient accounts (receive warmup emails)

### Warmup Lifecycle
```
Day 0: Account added → OAuth authenticated → Set as warmup account
Day 1-7: Phase 1 → Send 5-10 emails/day (10% of target)
Day 8-14: Phase 2 → Send 10-12 emails/day (25% of target)
Day 15-21: Phase 3 → Send 15-25 emails/day (50% of target)
Day 22-28: Phase 4 → Send 20-37 emails/day (75% of target)
Day 29+: Phase 5 → Send full target (100%, e.g., 50 emails/day)
```

### Email Content Flow
```
Template Selection → Placeholder Filling → AI Enhancement → Validation → Send
                                    ↓
                          (25% pure, 45% AI fill, 25% addon, 5% full AI)
```

### Human Timing Logic
```
Check Time → Business Hours? → Calculate Activity Weight → Determine Send Probability
                                                                    ↓
                                                    Decision: Send Now or Wait
```

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Redis server
- Google Cloud Project with Gmail API enabled
- OpenAI API key (optional, for AI features)

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/email_warmup

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI (optional)
USE_OPENAI=true
OPENAI_API_KEY=your-api-key

# Flask
SECRET_KEY=your-secret-key
```

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
flask db upgrade

# Start services
# Terminal 1: Flask app
python app.py

# Terminal 2: Celery worker
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Celery Beat scheduler
python celery_beat_schedule.py
```

### Basic Usage
```bash
# Add account via OAuth
curl http://localhost:5000/api/oauth/signin

# Check accounts
python scripts/check_accounts.py

# Setup warmup configuration
python scripts/setup_warmup_config.py

# Monitor analytics
curl http://localhost:5000/api/analytics/overview
```

## Next Steps

For detailed information, see:
- **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)**: Deep dive into code implementation
- **[API_REFERENCE.md](API_REFERENCE.md)**: Complete API endpoint documentation
- **[WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)**: How components work together
- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)**: Database structure and relationships
