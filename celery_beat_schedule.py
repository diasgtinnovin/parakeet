#!/usr/bin/env python3
"""
Celery Beat Schedule Configuration
Run this to start the scheduled tasks

NEW SCHEDULING SYSTEM:
- Daily schedules generated at midnight for each timezone
- Emails sent based on pre-calculated schedules (not reactive checking)
- Peak/Normal/Low activity periods with proper distribution (60/30/10)
- Weekend support (skipped)
"""

from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Celery instance
celery = Celery('email_warmup_service')

# Import tasks to register them
from app.tasks.email_tasks import (
    generate_daily_schedules_task,
    send_scheduled_emails_task,
    check_replies_task,
    advance_warmup_day_task,
    warmup_status_report_task,
    cleanup_old_schedules_task
)

# Configure Celery
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',  # Store times in UTC
    enable_utc=True,
    include=['app.tasks.email_tasks'],
)

# Schedule tasks with new architecture
celery.conf.beat_schedule = {
    # Generate daily schedules - runs every hour to catch midnight in different timezones
    'generate-daily-schedules': {
        'task': 'app.tasks.email_tasks.generate_daily_schedules_task',
        'schedule': crontab(minute=1, hour='*/1'),  # Every hour at minute 1
    },
    
    # Send scheduled emails - runs every 2 minutes
    'send-scheduled-emails': {
        'task': 'app.tasks.email_tasks.send_scheduled_emails_task',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
    
    # Check for replies
    'check-replies': {
        'task': 'app.tasks.email_tasks.check_replies_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    # Advance warmup day once daily
    'advance-warmup-day': {
        'task': 'app.tasks.email_tasks.advance_warmup_day_task',
        'schedule': crontab(hour=0, minute=5),  # At 00:05 daily
    },
    
    # Generate status report
    'warmup-status-report': {
        'task': 'app.tasks.email_tasks.warmup_status_report_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    
    # Cleanup old schedules
    'cleanup-old-schedules': {
        'task': 'app.tasks.email_tasks.cleanup_old_schedules_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}


if __name__ == '__main__':
    celery.start()
