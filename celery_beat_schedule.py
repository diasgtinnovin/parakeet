#!/usr/bin/env python3
"""
Celery Beat Schedule Configuration
Run this to start the scheduled tasks
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
    send_warmup_emails_task, 
    check_replies_task, 
    advance_warmup_day_task,
    warmup_status_report_task,
    generate_daily_schedule_task
)

# Configure Celery
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    include=['app.tasks.email_tasks'],  # Include the tasks module
)

# Schedule tasks with ramping support
celery.conf.beat_schedule = {
    # Check for warmup emails every 3 minutes (human timing logic decides when to actually send)
    'send-warmup-emails': {
        'task': 'app.tasks.email_tasks.send_warmup_emails_task',
        'schedule': crontab(minute='*/3'),  # Every 3 minutes (more frequent checks)
    },
    
    # Check for replies every minute
    'check-replies': {
        'task': 'app.tasks.email_tasks.check_replies_task',
        'schedule': crontab(minute='*/5'),  # Every minute
    },
    
    # Advance warmup day once daily at 00:01 (1 minute past midnight)
    'advance-warmup-day': {
        'task': 'app.tasks.email_tasks.advance_warmup_day_task',
        'schedule': crontab(hour=0, minute=1),  # Daily at 00:01
    },
    
    # Generate status report every 6 hours
    'warmup-status-report': {
        'task': 'app.tasks.email_tasks.warmup_status_report_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    
    # Generate daily schedule at 8:30 AM each day
    'generate-daily-schedule': {
        'task': 'app.tasks.email_tasks.generate_daily_schedule_task',
        'schedule': crontab(hour=8, minute=30),  # Daily at 8:30 AM
    },
}


if __name__ == '__main__':
    celery.start()