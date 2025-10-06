from app.celery_app import celery
from app import db
from app.models.account import Account
from app.models.email import Email
from app.models.email_schedule import EmailSchedule
from app.services.gmail_service import GmailService
from app.services.ai_service import AIService
from app.services.human_timing_service import HumanTimingService
import os
import uuid
import logging
from datetime import datetime, timedelta, date
from celery.schedules import crontab
import pytz
import random

logger = logging.getLogger(__name__)


@celery.task
def generate_daily_schedules_task():
    """
    Generate daily email schedules for all warmup accounts
    Runs at midnight for each timezone
    NEW: Creates individual Celery tasks for each scheduled email
    """
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            # Get all unique timezones from warmup accounts
            warmup_accounts = Account.query.filter_by(
                is_active=True, 
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                logger.info("No active warmup accounts found for schedule generation")
                return "No warmup accounts to schedule"
            
            # Group accounts by timezone
            accounts_by_timezone = {}
            for account in warmup_accounts:
                tz = account.timezone or 'Asia/Kolkata'
                if tz not in accounts_by_timezone:
                    accounts_by_timezone[tz] = []
                accounts_by_timezone[tz].append(account)
            
            total_schedules_created = 0
            total_tasks_scheduled = 0
            
            # Generate schedules for each timezone
            for tz_name, accounts in accounts_by_timezone.items():
                logger.info(f"Generating schedules for {len(accounts)} account(s) in timezone: {tz_name}")
                
                try:
                    tz = pytz.timezone(tz_name)
                    now_in_tz = datetime.now(tz)
                    
                    # Check if it's actually midnight (±30 minutes) in this timezone
                    hour = now_in_tz.hour
                    if not (0 <= hour <= 1 or hour == 23):
                        logger.info(f"Not midnight in {tz_name} (current hour: {hour}), skipping")
                        continue
                    
                    # Get the target date (today in that timezone)
                    target_date = now_in_tz.date()
                    
                    for account in accounts:
                        schedules_created = generate_schedule_for_account(account, target_date)
                        total_schedules_created += schedules_created
                        
                        # NEW: Create individual Celery tasks for each scheduled email
                        if schedules_created > 0:
                            tasks_created = schedule_individual_email_tasks(account, target_date)
                            total_tasks_scheduled += tasks_created
                
                except Exception as e:
                    logger.error(f"Error generating schedules for timezone {tz_name}: {e}")
                    continue
            
            logger.info(f"Daily schedule generation complete: {total_schedules_created} schedules created, {total_tasks_scheduled} Celery tasks scheduled")
            
            # Schedule rescheduling checks throughout the day
            schedule_rescheduling_checks()
            
            return f"Generated {total_schedules_created} schedules and {total_tasks_scheduled} tasks for {len(warmup_accounts)} accounts"
            
        except Exception as e:
            logger.error(f"Error in generate_daily_schedules_task: {e}")
            return f"Error: {str(e)}"


def schedule_individual_email_tasks(account: Account, target_date: date) -> int:
    """
    Create individual Celery tasks for each scheduled email
    NEW FEATURE: Dynamic task scheduling at exact times
    """
    try:
        # Get today's schedules for this account
        schedules = EmailSchedule.query.filter(
            EmailSchedule.account_id == account.id,
            EmailSchedule.schedule_date == target_date,
            EmailSchedule.status == 'pending'
        ).all()
        
        tasks_created = 0
        
        for schedule in schedules:
            # Schedule Celery task for exact time
            try:
                send_single_email_task.apply_async(
                    args=[schedule.id],
                    eta=schedule.scheduled_time  # Exact time!
                )
                tasks_created += 1
                logger.debug(f"Scheduled email task for {account.email} at {schedule.scheduled_time}")
                
            except Exception as e:
                logger.error(f"Failed to schedule task for schedule {schedule.id}: {e}")
        
        logger.info(f"Created {tasks_created} individual email tasks for {account.email}")
        return tasks_created
        
    except Exception as e:
        logger.error(f"Error scheduling individual tasks for {account.email}: {e}")
        return 0


def schedule_rescheduling_checks():
    """
    Schedule periodic rescheduling checks throughout the day
    NEW FEATURE: Smart rescheduling monitoring
    """
    try:
        # Schedule rescheduling checks at key times during business hours
        check_times = [10, 12, 14, 16]  # 10 AM, 12 PM, 2 PM, 4 PM
        
        for hour in check_times:
            # Calculate when to run (today at specified hour)
            now = datetime.now(pytz.utc)
            check_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # If time has passed today, schedule for tomorrow
            if check_time <= now:
                check_time += timedelta(days=1)
            
            reschedule_failed_emails_task.apply_async(eta=check_time)
            logger.debug(f"Scheduled rescheduling check at {check_time}")
            
    except Exception as e:
        logger.error(f"Error scheduling rescheduling checks: {e}")


def generate_schedule_for_account(account: Account, target_date: date) -> int:
    """
    Generate schedule for a single account for the target date
    
    Returns:
        Number of schedules created
    """
    try:
        # Check if schedule already exists for this date
        existing_schedules = EmailSchedule.query.filter(
            EmailSchedule.account_id == account.id,
            EmailSchedule.schedule_date == target_date
        ).count()
        
        if existing_schedules > 0:
            logger.info(f"Schedule already exists for {account.email} on {target_date}")
            return 0
        
        # Calculate daily limit for this account
        daily_limit = account.calculate_daily_limit()
        
        if daily_limit <= 0:
            logger.info(f"Daily limit is 0 for {account.email}, skipping schedule generation")
            return 0
        
        # Initialize timing service with account's timezone
        timing_service = HumanTimingService(timezone=account.timezone or 'Asia/Kolkata')
        
        # Get timezone object
        tz = pytz.timezone(account.timezone or 'Asia/Kolkata')
        target_datetime = tz.localize(datetime.combine(target_date, datetime.min.time()))
        
        # Skip weekends
        if timing_service.is_weekend(target_datetime):
            logger.info(f"Skipping weekend date {target_date} for {account.email}")
            return 0
        
        # Generate the schedule
        schedule = timing_service.generate_daily_schedule(daily_limit, target_datetime)
        
        if not schedule:
            logger.warning(f"No schedule generated for {account.email} on {target_date}")
            return 0
        
        # Save schedules to database
        schedules_created = 0
        for scheduled_time, activity_period in schedule:
            email_schedule = EmailSchedule(
                account_id=account.id,
                scheduled_time=scheduled_time.astimezone(pytz.utc),  # Store in UTC
                schedule_date=target_date,
                activity_period=activity_period,
                status='pending'
            )
            db.session.add(email_schedule)
            schedules_created += 1
        
        db.session.commit()
        
        # Log statistics
        stats = timing_service.calculate_schedule_stats(schedule)
        logger.info(f"Created schedule for {account.email} ({account.get_warmup_phase()}): "
                   f"{stats['total']} emails - Peak: {stats['peak']}, Normal: {stats['normal']}, Low: {stats['low']}")
        logger.info(f"  First send: {stats['first_send']}, Last send: {stats['last_send']}")
        if 'avg_interval_minutes' in stats:
            logger.info(f"  Avg interval: {stats['avg_interval_minutes']:.1f} min "
                       f"(range: {stats['min_interval_minutes']:.1f} - {stats['max_interval_minutes']:.1f} min)")
        
        return schedules_created
        
    except Exception as e:
        logger.error(f"Error generating schedule for account {account.email}: {e}")
        db.session.rollback()
        return 0


@celery.task
def send_single_email_task(schedule_id):
    """
    Send a single scheduled email at its exact time
    NEW FEATURE: Replaces periodic checking with precise scheduling
    """
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            # Get the schedule
            schedule = EmailSchedule.query.get(schedule_id)
            if not schedule:
                logger.error(f"Schedule {schedule_id} not found")
                return f"Schedule {schedule_id} not found"
            
            # Check if already processed
            if schedule.status != 'pending':
                logger.info(f"Schedule {schedule_id} already processed (status: {schedule.status})")
                return f"Schedule already processed"
            
            # Check if account is still active
            account = schedule.account
            if not account or not account.is_active or account.account_type != 'warmup':
                schedule.mark_skipped("Account not active or not warmup type")
                db.session.commit()
                return "Account not active"
            
            # Send the email
            success = send_scheduled_email(schedule)
            
            if success:
                logger.info(f"✓ Successfully sent scheduled email for {account.email}")
                return "Email sent successfully"
            else:
                logger.warning(f"⚠️ Failed to send scheduled email for {account.email}")
                # Failed email will be handled by rescheduling task
                return "Email send failed"
                
        except Exception as e:
            logger.error(f"Error in send_single_email_task({schedule_id}): {e}")
            return f"Error: {str(e)}"


@celery.task
def reschedule_failed_emails_task():
    """
    Smart rescheduling of failed/missed emails
    NEW FEATURE: Analyzes current progress and redistributes remaining emails
    """
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("🔄 Starting smart email rescheduling analysis...")
            
            # Get all active warmup accounts
            warmup_accounts = Account.query.filter_by(
                is_active=True, 
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                return "No warmup accounts found"
            
            total_rescheduled = 0
            
            for account in warmup_accounts:
                rescheduled = reschedule_account_emails(account)
                total_rescheduled += rescheduled
            
            logger.info(f"✅ Rescheduling complete: {total_rescheduled} emails rescheduled across {len(warmup_accounts)} accounts")
            return f"Rescheduled {total_rescheduled} emails"
            
        except Exception as e:
            logger.error(f"Error in reschedule_failed_emails_task: {e}")
            return f"Error: {str(e)}"


def reschedule_account_emails(account: Account) -> int:
    """
    Reschedule emails for a single account based on current progress
    YOUR REQUIREMENT: Check current time, expected vs actual emails sent, reschedule if needed
    """
    try:
        today = datetime.utcnow().date()
        tz = pytz.timezone(account.timezone or 'Asia/Kolkata')
        now_in_tz = datetime.now(tz)
        
        # Skip if outside business hours or weekend
        timing_service = HumanTimingService(timezone=account.timezone or 'Asia/Kolkata')
        if not timing_service.is_business_hours(now_in_tz) or timing_service.is_weekend(now_in_tz):
            return 0
        
        # Get today's schedule data
        all_schedules = EmailSchedule.query.filter(
            EmailSchedule.account_id == account.id,
            EmailSchedule.schedule_date == today
        ).all()
        
        if not all_schedules:
            return 0
        
        # Analyze current progress
        total_scheduled = len(all_schedules)
        sent_count = sum(1 for s in all_schedules if s.status == 'sent')
        failed_count = sum(1 for s in all_schedules if s.status == 'failed')
        pending_count = sum(1 for s in all_schedules if s.status == 'pending')
        
        # Calculate expected progress based on time
        business_start = now_in_tz.replace(hour=9, minute=0, second=0, microsecond=0)
        business_end = now_in_tz.replace(hour=18, minute=0, second=0, microsecond=0)
        
        if now_in_tz < business_start:
            expected_progress = 0.0
        elif now_in_tz >= business_end:
            expected_progress = 1.0
        else:
            elapsed_minutes = (now_in_tz - business_start).total_seconds() / 60
            total_business_minutes = (business_end - business_start).total_seconds() / 60
            expected_progress = elapsed_minutes / total_business_minutes
        
        expected_sent = int(total_scheduled * expected_progress)
        actual_sent = sent_count
        
        # Determine if rescheduling is needed
        behind_schedule = expected_sent - actual_sent
        
        logger.info(f"📊 {account.email} progress analysis:")
        logger.info(f"   Expected by now: {expected_sent}/{total_scheduled} ({expected_progress:.1%})")
        logger.info(f"   Actually sent: {actual_sent}/{total_scheduled}")
        logger.info(f"   Behind schedule: {behind_schedule} emails")
        logger.info(f"   Failed: {failed_count}, Pending: {pending_count}")
        
        # Only reschedule if significantly behind (more than 2 emails)
        if behind_schedule <= 2 and failed_count == 0:
            return 0
        
        # Get failed and overdue pending schedules
        current_utc = datetime.utcnow()
        schedules_to_reschedule = []
        
        for schedule in all_schedules:
            if schedule.status == 'failed':
                schedules_to_reschedule.append(schedule)
            elif (schedule.status == 'pending' and 
                  schedule.scheduled_time < current_utc - timedelta(minutes=10)):  # 10 min grace period
                schedules_to_reschedule.append(schedule)
        
        if not schedules_to_reschedule:
            return 0
        
        # Calculate remaining business hours today
        remaining_hours = max(0, (business_end - now_in_tz).total_seconds() / 3600)
        
        if remaining_hours < 0.5:  # Less than 30 minutes left
            logger.info(f"Too little time remaining ({remaining_hours:.1f}h) for rescheduling")
            return 0
        
        # Generate new schedule times for failed/overdue emails
        new_times = generate_rescheduled_times(
            count=len(schedules_to_reschedule),
            start_time=now_in_tz + timedelta(minutes=5),  # Start in 5 minutes
            end_time=business_end - timedelta(minutes=30),  # End 30 min before close
            timing_service=timing_service
        )
        
        if len(new_times) != len(schedules_to_reschedule):
            logger.warning(f"Could only generate {len(new_times)} new times for {len(schedules_to_reschedule)} emails")
        
        # Reschedule the emails
        rescheduled_count = 0
        
        for i, schedule in enumerate(schedules_to_reschedule[:len(new_times)]):
            new_time_utc = new_times[i].astimezone(pytz.utc)
            
            # Update schedule
            schedule.scheduled_time = new_time_utc
            schedule.status = 'pending'
            schedule.retry_count += 1
            schedule.last_error = f"Rescheduled at {datetime.utcnow()}"
            
            # Create new Celery task
            try:
                send_single_email_task.apply_async(
                    args=[schedule.id],
                    eta=new_time_utc
                )
                rescheduled_count += 1
                logger.info(f"   ↻ Rescheduled email to {new_times[i].strftime('%H:%M:%S')}")
                
            except Exception as e:
                logger.error(f"Failed to reschedule task for schedule {schedule.id}: {e}")
        
        db.session.commit()
        
        if rescheduled_count > 0:
            logger.info(f"✅ Rescheduled {rescheduled_count} emails for {account.email}")
        
        return rescheduled_count
        
    except Exception as e:
        logger.error(f"Error rescheduling emails for {account.email}: {e}")
        db.session.rollback()
        return 0


def generate_rescheduled_times(count: int, start_time: datetime, end_time: datetime, 
                             timing_service: HumanTimingService) -> list:
    """
    Generate new random times for rescheduled emails
    Maintains human-like distribution even for rescheduled emails
    """
    if count <= 0 or start_time >= end_time:
        return []
    
    times = []
    available_minutes = (end_time - start_time).total_seconds() / 60
    
    if available_minutes < count * 2:  # Need at least 2 minutes between emails
        # Too little time, spread evenly
        interval = available_minutes / count
        for i in range(count):
            time_offset = timedelta(minutes=i * interval + random.uniform(0, interval * 0.5))
            times.append(start_time + time_offset)
    else:
        # Enough time, use random distribution
        for _ in range(count):
            # Random time within available window
            random_minutes = random.uniform(0, available_minutes)
            new_time = start_time + timedelta(minutes=random_minutes)
            
            # Ensure it's still within business hours
            if timing_service.is_business_hours(new_time):
                times.append(new_time)
    
    # Sort times and ensure minimum 1-minute gaps
    times.sort()
    adjusted_times = []
    last_time = None
    
    for time in times:
        if last_time and (time - last_time).total_seconds() < 60:
            time = last_time + timedelta(minutes=1)
        adjusted_times.append(time)
        last_time = time
    
    return adjusted_times


@celery.task
def send_scheduled_emails_task():
    """
    Send emails that are scheduled for now
    Runs frequently (every 1-2 minutes) to check for due emails
    """
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            # Get all unique timezones
            timezones = db.session.query(Account.timezone).filter(
                Account.is_active == True,
                Account.account_type == 'warmup'
            ).distinct().all()
            
            if not timezones:
                return "No active warmup accounts"
            
            emails_sent = 0
            
            for (tz_name,) in timezones:
                if not tz_name:
                    tz_name = 'Asia/Kolkata'
                
                try:
                    tz = pytz.timezone(tz_name)
                    now_in_tz = datetime.now(tz)
                    
                    # Skip if outside business hours or weekend
                    timing_service = HumanTimingService(timezone=tz_name)
                    if not timing_service.is_business_hours(now_in_tz):
                    continue
                
                    # Get due schedules for this timezone
                    # Look for schedules within the next 2 minutes
                    now_utc = datetime.utcnow()
                    window_end = now_utc + timedelta(minutes=2)
                    
                    due_schedules = EmailSchedule.query.join(Account).filter(
                        EmailSchedule.status == 'pending',
                        EmailSchedule.scheduled_time <= window_end,
                        EmailSchedule.scheduled_time >= now_utc - timedelta(minutes=5),  # Grace period for missed
                        Account.timezone == tz_name,
                        Account.is_active == True,
                        Account.account_type == 'warmup'
                    ).all()
                    
                    logger.info(f"Found {len(due_schedules)} due schedules in {tz_name}")
                    
                    for schedule in due_schedules:
                        if send_scheduled_email(schedule):
                            emails_sent += 1
                
                except Exception as e:
                    logger.error(f"Error processing timezone {tz_name}: {e}")
                    continue
                
            if emails_sent > 0:
                logger.info(f"Sent {emails_sent} scheduled email(s)")
            
            return f"Sent {emails_sent} emails"
            
        except Exception as e:
            logger.error(f"Error in send_scheduled_emails_task: {e}")
            return f"Error: {str(e)}"


def send_scheduled_email(schedule: EmailSchedule) -> bool:
    """
    Send a single scheduled email
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        account = schedule.account
        
        # Double-check account is active
        if not account.is_active or account.account_type != 'warmup':
            schedule.mark_skipped("Account not active or not warmup type")
            db.session.commit()
            return False
        
        # Get pool accounts for recipients
        pool_accounts = Account.query.filter_by(
            is_active=True,
            account_type='pool'
        ).all()
        
        if not pool_accounts:
            logger.error("No pool accounts available for recipients")
            schedule.mark_failed("No pool accounts available")
            db.session.commit()
            return False
        
        # Select random recipient
                import random
        recipient_email = random.choice([acc.email for acc in pool_accounts])
                
        # Generate email content
                use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
                ai_service = AIService(os.getenv('OPENAI_API_KEY'), use_ai=use_ai)
                content_data = ai_service.generate_email_content()
                
                # Generate tracking pixel ID
                tracking_pixel_id = str(uuid.uuid4())
                
        # Authenticate and send via Gmail
                gmail_service = GmailService()
                oauth_token_data = account.get_oauth_token_data()
        
                if not oauth_token_data or not gmail_service.authenticate_with_token(oauth_token_data):
                    logger.error(f"Gmail authentication failed for account {account.email}")
            schedule.mark_failed("Gmail authentication failed")
            db.session.commit()
            return False
                
                message_id = gmail_service.send_email(
                    recipient_email,
                    content_data['subject'],
                    content_data['content'],
                    tracking_pixel_id
                )
                
        if not message_id:
            logger.error(f"Failed to send email from {account.email}")
            schedule.mark_failed("Gmail send failed")
            db.session.commit()
            return False
        
                    # Save email record
                    email_record = Email(
                        account_id=account.id,
                        to_address=recipient_email,
                        subject=content_data['subject'],
                        content=content_data['content'],
                        tracking_pixel_id=tracking_pixel_id
                    )
        db.session.add(email_record)
        db.session.flush()  # Get the email ID
        
        # Mark schedule as sent
        schedule.mark_sent(email_record.id)
        db.session.commit()
        
        # Get today's count
        today_emails = Email.query.filter(
            Email.account_id == account.id,
            Email.sent_at >= db.func.date(db.func.now())
        ).count()
        
        logger.info(f"✓ Sent scheduled email from {account.email} to {recipient_email} "
                   f"({today_emails}/{account.calculate_daily_limit()}) - {account.get_warmup_phase()} "
                   f"[{schedule.activity_period} period]")
        
        return True
            
        except Exception as e:
        logger.error(f"Error sending scheduled email (schedule_id={schedule.id}): {e}")
        schedule.mark_failed(str(e))
        db.session.commit()
        return False


@celery.task
def check_replies_task():
    """Check for replies and update engagement metrics for warmup accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            total_replies = 0
            
            for account in warmup_accounts:
                gmail_service = GmailService()
                oauth_token_data = account.get_oauth_token_data()
                
                if not oauth_token_data or not gmail_service.authenticate_with_token(oauth_token_data):
                    continue
                
                # Check for replies
                reply_count = gmail_service.check_replies(account.email)
                
                if reply_count > 0:
                    # Update recent emails as replied
                    recent_emails = Email.query.filter(
                        Email.account_id == account.id,
                        Email.is_replied == False,
                        Email.sent_at >= db.func.date(db.func.now())
                    ).limit(reply_count).all()
                    
                    for email in recent_emails:
                        email.is_replied = True
                        email.replied_at = db.func.now()
                    
                    db.session.commit()
                    total_replies += reply_count
                    logger.info(f"Updated {reply_count} replies for account {account.email}")
            
            return f"Checked replies: {total_replies} new replies found"
            
        except Exception as e:
            logger.error(f"Error in check_replies_task: {e}")
            db.session.rollback()
            return f"Error: {str(e)}"


@celery.task
def advance_warmup_day_task():
    """Advance warmup day for all warmup accounts (run once daily at midnight)"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                logger.info("No warmup accounts found for daily advancement")
                return "No warmup accounts to advance"
            
            accounts_advanced = 0
            
            for account in warmup_accounts:
                # Check if we should advance the warmup day
                # Only advance once per day (check if last update was yesterday or earlier)
                if account.updated_at.date() < datetime.utcnow().date():
                    old_day = account.warmup_day
                    old_phase = account.get_warmup_phase()
                    old_limit = account.daily_limit
                    
                    # Advance warmup day
                    account.warmup_day += 1
                    account.updated_at = datetime.utcnow()
                    
                    # Update daily limit based on new warmup day
                    new_limit = account.calculate_daily_limit()
                    account.daily_limit = new_limit
                    
                    new_phase = account.get_warmup_phase()
                    
                    logger.info(f"Advanced warmup for {account.email}: Day {old_day} → {account.warmup_day}")
                    logger.info(f"  Phase: {old_phase} → {new_phase}")
                    logger.info(f"  Daily limit: {old_limit} → {new_limit} emails/day")
                    
                    # Check for phase transitions
                    if account.warmup_day in [8, 15, 22, 29]:
                        logger.info(f"🎉 {account.email} entered new warmup phase: {new_phase}")
                    
                    accounts_advanced += 1
                else:
                    logger.debug(f"Warmup day already advanced today for {account.email}")
            
            db.session.commit()
            
            return f"Warmup day advanced for {accounts_advanced} account(s)"
            
        except Exception as e:
            logger.error(f"Error in advance_warmup_day_task: {e}")
            db.session.rollback()
            return f"Error: {str(e)}"


@celery.task
def warmup_status_report_task():
    """Generate warmup status report for all accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                return "No warmup accounts found"
            
            for account in warmup_accounts:
                # Get today's email count
                today_emails = Email.query.filter(
                    Email.account_id == account.id,
                    Email.sent_at >= db.func.date(db.func.now())
                ).count()
                
                # Get total email count
                total_emails = Email.query.filter(
                    Email.account_id == account.id
                ).count()
                
                # Get pending schedules for today
                today_date = datetime.utcnow().date()
                pending_schedules = EmailSchedule.query.filter(
                    EmailSchedule.account_id == account.id,
                    EmailSchedule.schedule_date == today_date,
                    EmailSchedule.status == 'pending'
                ).count()
                
                # Calculate progress percentage
                current_limit = account.calculate_daily_limit()
                progress = (current_limit / account.warmup_target) * 100 if account.warmup_target > 0 else 0
                
                logger.info(f"📊 {account.email} ({account.timezone}): {account.get_warmup_phase()}")
                logger.info(f"   Today: {today_emails}/{current_limit} sent, {pending_schedules} pending")
                logger.info(f"   Progress: {progress:.1f}% of target ({current_limit}/{account.warmup_target})")
                logger.info(f"   Total sent: {total_emails} emails")
            
            return f"Status report generated for {len(warmup_accounts)} warmup account(s)"
            
        except Exception as e:
            logger.error(f"Error in warmup_status_report_task: {e}")
            return f"Error: {str(e)}"


@celery.task
def cleanup_old_schedules_task():
    """Clean up old completed/failed schedules (older than 7 days)"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        try:
            cutoff_date = datetime.utcnow().date() - timedelta(days=7)
            
            deleted = EmailSchedule.query.filter(
                EmailSchedule.schedule_date < cutoff_date,
                EmailSchedule.status.in_(['sent', 'failed', 'skipped'])
            ).delete()
            
            db.session.commit()
            
            logger.info(f"Cleaned up {deleted} old schedule entries")
            return f"Cleaned up {deleted} old schedules"
            
        except Exception as e:
            logger.error(f"Error in cleanup_old_schedules_task: {e}")
            db.session.rollback()
            return f"Error: {str(e)}"


# Celery Beat Schedule - ENHANCED VERSION
celery.conf.beat_schedule = {
    # Generate daily schedules - runs every hour to catch midnight in different timezones
    # NEW: Also creates individual Celery tasks for each scheduled email
    'generate-daily-schedules': {
        'task': 'app.tasks.email_tasks.generate_daily_schedules_task',
        'schedule': crontab(minute=1, hour='*/1'),  # Every hour at minute 1
    },
    
    # REMOVED: send-scheduled-emails (replaced by individual tasks)
    # NEW: Individual email tasks are created with exact ETA times
    
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
    
    # NEW: Smart rescheduling - no fixed schedule, triggered by generate_daily_schedules_task
    # Rescheduling tasks are created dynamically at 10 AM, 12 PM, 2 PM, 4 PM
}
