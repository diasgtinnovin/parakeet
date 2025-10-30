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
import time

logger = logging.getLogger(__name__)


def authenticate_and_update_token(gmail_service, account):
    """
    Authenticate with Gmail and update token in database if refreshed
    
    Args:
        gmail_service: GmailService instance
        account: Account model instance
        
    Returns:
        bool: True if authentication successful, False otherwise
    """
    oauth_token_data = account.get_oauth_token_data()
    
    if not oauth_token_data:
        logger.warning(f"No OAuth token data for account {account.email}")
        return False
    
    success, updated_token_data = gmail_service.authenticate_with_token(oauth_token_data)
    
    if not success:
        logger.warning(f"Gmail authentication failed for account {account.email}")
        return False
    
    # If token was refreshed, save it to database
    if updated_token_data:
        account.set_oauth_token_data(updated_token_data)
        db.session.commit()
        logger.info(f"Updated OAuth token for account {account.email}")
    
    return True


@celery.task
def generate_daily_schedules_task():
    """
    Generate daily email schedules for all warmup accounts
    Runs at midnight for each timezone
    """
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
            
            # Generate schedules for each timezone
            for tz_name, accounts in accounts_by_timezone.items():
                logger.info(f"Generating schedules for {len(accounts)} account(s) in timezone: {tz_name}")
                
                try:
                    tz = pytz.timezone(tz_name)
                    now_in_tz = datetime.now(tz)
                    
                    # Check if schedules already exist for today
                    # If not, generate them regardless of time (for flexibility)
                    target_date = now_in_tz.date()
                    
                    # Check if we already have schedules for today
                    existing_schedules = EmailSchedule.query.join(Account).filter(
                        EmailSchedule.schedule_date == target_date,
                        Account.timezone == tz_name,
                        Account.is_active == True,
                        Account.account_type == 'warmup'
                    ).count()
                    
                    if existing_schedules > 0:
                        logger.info(f"Schedules already exist for {target_date} in {tz_name}, skipping generation")
                        continue
                    
                    # Target date is already set above
                    
                    for account in accounts:
                        schedules_created = generate_schedule_for_account(account, target_date)
                        total_schedules_created += schedules_created
                
                except Exception as e:
                    logger.error(f"Error generating schedules for timezone {tz_name}: {e}")
                    continue
            
            logger.info(f"Daily schedule generation complete: {total_schedules_created} schedules created")
            return f"Generated {total_schedules_created} schedules for {len(warmup_accounts)} accounts"
    except Exception as e:
        logger.error(f"Error in generate_daily_schedules_task: {e}")
        return f"Error: {str(e)}"
    finally:
        db.session.remove()


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
            # Convert to UTC and remove timezone info to store as naive datetime
            utc_time = scheduled_time.astimezone(pytz.utc)
            naive_utc_time = utc_time.replace(tzinfo=None)
            
            email_schedule = EmailSchedule(
                account_id=account.id,
                scheduled_time=naive_utc_time,  # Store as naive UTC datetime
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
def simulate_engagement_task():
    """
    Simulate engagement for pool accounts (open emails and send replies)
    This task runs periodically to process unread emails in pool accounts
    Uses TARGET-BASED approach to maintain exact user-specified open rates
    """
    from app.services.engagement_simulation_service import EngagementSimulationService
    try:
            ai_service = AIService(os.getenv('OPENAI_API_KEY'), use_ai=os.getenv('USE_OPENAI', 'false').lower() == 'true')
            
            # Get all active pool accounts
            pool_accounts = Account.query.filter_by(
                is_active=True,
                account_type='pool'
            ).all()
            
            if not pool_accounts:
                logger.info("No pool accounts found for engagement simulation")
                return "No pool accounts available"
            
            total_opened = 0
            total_skipped = 0
            total_replied = 0
            
            for pool_account in pool_accounts:
                logger.info(f"Processing pool account: {pool_account.email}")
                
                try:
                    # Authenticate with Gmail
                    gmail_service = GmailService()
                    
                    if not authenticate_and_update_token(gmail_service, pool_account):
                        logger.warning(f"Gmail authentication failed for pool account {pool_account.email}")
                        continue
                    
                    # Get unread emails from warmup accounts
                    warmup_emails = Account.query.filter_by(
                        is_active=True,
                        account_type='warmup'
                    ).all()
                    
                    if not warmup_emails:
                        continue
                    
                    warmup_email_addresses = [acc.email for acc in warmup_emails]
                    
                    # Get unread emails
                    unread_messages = gmail_service.get_unread_emails(max_results=20)
                    
                    # Filter messages from warmup accounts
                    relevant_messages = [
                        msg for msg in unread_messages
                        if any(warmup_email in msg['from'] for warmup_email in warmup_email_addresses)
                    ]
                    
                    logger.info(f"Pool account {pool_account.email}: Found {len(relevant_messages)} unread emails from warmup accounts")
                    
                    for message in relevant_messages:
                        try:
                            # Find the corresponding email record
                            sender_email = message['from'].split('<')[-1].strip('>')
                            email_record = Email.query.filter_by(
                                to_address=pool_account.email,
                                is_opened=False,
                                is_processed=False  # Only get unprocessed emails
                            ).filter(
                                Email.subject == message['subject']
                            ).first()
                            
                            if not email_record:
                                logger.debug(f"No matching unprocessed email record found for message {message['id']}")
                                # Mark as read in Gmail to avoid reprocessing
                                gmail_service.mark_as_read(message['id'])
                                continue
                            
                            # Get the sender account to access their configuration
                            sender_account = Account.query.get(email_record.account_id)
                            if not sender_account:
                                logger.error(f"Sender account not found for email {email_record.id}")
                                continue
                            
                            # Create engagement service using SENDER'S rates (from warmup account)
                            engagement_service = EngagementSimulationService(
                                open_rate=email_record.sender_open_rate,
                                reply_rate=email_record.sender_reply_rate
                            )
                            
                            # Check if enough time has passed since email was received
                            if not engagement_service.should_process_email(email_record.sent_at):
                                logger.debug(f"Email {email_record.id} not ready to process yet")
                                continue
                            
                            # ============================================================
                            # TARGET-BASED OPEN DECISION
                            # This checks current open rate vs target and decides accordingly
                            # ============================================================
                            should_open = engagement_service.should_open_target_based(
                                sender_account_id=sender_account.id,
                                db_session=db.session
                            )
                            
                            if not should_open:
                                # CRITICAL: Mark as processed and read in Gmail so we don't re-evaluate
                                logger.info(
                                    f"\033[93m⊗ Skipping email {email_record.id} based on target rate "
                                    f"(sender: {sender_account.email}, target: {email_record.sender_open_rate:.0%})\033[0m"
                                )
                                
                                # Mark as read in Gmail (so it doesn't appear as unread next time)
                                gmail_service.mark_as_read(message['id'])
                                
                                # Mark as processed in database (but NOT opened)
                                email_record.is_processed = True
                                email_record.processed_at = datetime.utcnow()
                                email_record.is_opened = False  # Explicitly mark as not opened
                                email_record.gmail_message_id = message['message_id']
                                db.session.commit()
                                total_skipped += 1
                                continue
                            
                            # ============================================================
                            # OPEN THE EMAIL
                            # ============================================================
                            # Mark email as read via Gmail API
                            if gmail_service.mark_as_read(message['id']):
                                email_record.is_opened = True
                                email_record.opened_at = datetime.utcnow()
                                email_record.is_processed = True
                                email_record.processed_at = datetime.utcnow()
                                email_record.gmail_message_id = message['message_id']
                                db.session.commit()
                                total_opened += 1
                                
                                logger.info(
                                    f"\033[92m✓ Opened email {email_record.id} "
                                    f"(sender: {sender_account.email}, target: {email_record.sender_open_rate:.0%})\033[0m"
                                )
                                
                                # Decide whether to mark as important
                                if engagement_service.should_mark_important():
                                    # Calculate delay before marking as important (45-100 seconds)
                                    important_delay = engagement_service.calculate_important_delay()
                                    logger.info(f"Will mark email {email_record.id} as important after {important_delay} seconds")
                                    
                                    # Wait for the delay
                                    time.sleep(important_delay)
                                    
                                    # Verify email is still opened before marking as important
                                    if gmail_service.is_email_opened(message['id']):
                                        if gmail_service.mark_as_important(message['id']):
                                            logger.info(f"\033[94m✓ Marked email {email_record.id} as important\033[0m")
                                        else:
                                            logger.warning(f"Failed to mark email {email_record.id} as important")
                                    else:
                                        logger.debug(f"Email {email_record.id} is not opened, skipping important marking")
                                
                                # Decide whether to reply based on SENDER'S reply rate strategy
                                if engagement_service.should_reply():
                                    # Wait realistic delay before replying (simulated)
                                    # In production, this could be a separate scheduled task
                                    
                                    # Generate AI reply
                                    reply_content_data = ai_service.generate_email_content(email_type='reply')
                                    reply_content = reply_content_data['content']
                                    
                                    # Send reply (without tracking pixel)
                                    reply_message_id = gmail_service.send_reply(
                                        to_address=sender_email,
                                        subject=message['subject'],
                                        content=reply_content,
                                        in_reply_to_id=message['message_id']
                                    )
                                    
                                    if reply_message_id:
                                        email_record.is_replied = True
                                        email_record.replied_at = datetime.utcnow()
                                        email_record.in_reply_to = message['message_id']
                                        db.session.commit()
                                        total_replied += 1
                                        logger.info(
                                            f"\033[93m✓ Sent reply for email {email_record.id} "
                                            f"(reply rate: {email_record.sender_reply_rate:.0%})\033[0m"
                                        )
                            else:
                                logger.warning(f"Failed to mark email {email_record.id} as read in Gmail")
                            
                        except Exception as e:
                            logger.error(f"Error processing message {message['id']}: {e}")
                            db.session.rollback()
                            continue
                
                except Exception as e:
                    logger.error(f"Error processing pool account {pool_account.email}: {e}")
                    db.session.rollback()
                    continue
            
            result_msg = (
                f"Engagement simulation completed: "
                f"{total_opened} emails opened, "
                f"{total_skipped} emails skipped, "
                f"{total_replied} replies sent"
            )
            logger.info(result_msg)
            return result_msg
    except Exception as e:
        logger.error(f"Error in simulate_engagement_task: {e}")
        db.session.rollback()
        return f"Error: {str(e)}"
    finally:
        db.session.remove()

@celery.task
def send_scheduled_emails_task():
    """
    Send emails that are scheduled for now
    Runs frequently (every 1-2 minutes) to check for due emails
    """
    random_delay = random.uniform(0, 60)
    time.sleep(random_delay)

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
                            time.sleep(random.uniform(1, 5))

                
                except Exception as e:
                    logger.error(f"Error processing timezone {tz_name}: {e}")
                    continue
            
            if emails_sent > 0:
                logger.info(f"Sent {emails_sent} scheduled email(s)")
            
            return f"Sent {emails_sent} emails"
    except Exception as e:
        logger.error(f"Error in send_scheduled_emails_task: {e}")
        return f"Error: {str(e)}"
    finally:
        db.session.remove()


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
        
        # Generate tracking pixel ID (keep for database record but don't use in email)
        tracking_pixel_id = str(uuid.uuid4())
        
        # Authenticate and send via Gmail
        gmail_service = GmailService()
        
        if not authenticate_and_update_token(gmail_service, account):
            logger.error(f"Gmail authentication failed for account {account.email}")
            schedule.mark_failed("Gmail authentication failed")
            db.session.commit()
            return False
        
        # Send email WITHOUT tracking pixel
        message_id = gmail_service.send_email(
            recipient_email,
            content_data['subject'],
            content_data['content'],
            tracking_pixel_id=None  # No tracking pixel
        )
        
        if not message_id:
            logger.error(f"Failed to send email from {account.email}")
            schedule.mark_failed("Gmail send failed")
            db.session.commit()
            return False
        
        # Save email record with sender's engagement strategy
        email_record = Email(
            account_id=account.id,
            to_address=recipient_email,
            subject=content_data['subject'],
            content=content_data['content'],
            tracking_pixel_id=tracking_pixel_id,
            sender_open_rate=account.open_rate,  # Store sender's open rate strategy
            sender_reply_rate=account.reply_rate  # Store sender's reply rate strategy
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
        
        # Print the sent log in green color for better visibility
        logger.info(
            "\033[92m✓ Sent scheduled email from %s to %s (%d/%d) - %s [%s period]\033[0m",
            account.email,
            recipient_email,
            today_emails,
            account.calculate_daily_limit(),
            account.get_warmup_phase(),
            schedule.activity_period
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending scheduled email (schedule_id={schedule.id}): {e}")
        schedule.mark_failed(str(e))
        db.session.commit()
        return False


@celery.task
def check_replies_task():
    """Check for replies and update engagement metrics for warmup accounts"""
    try:
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            total_replies = 0

            # Build list of pool account emails once
            pool_accounts = Account.query.filter_by(
                is_active=True,
                account_type='pool'
            ).all()
            pool_emails = [acc.email for acc in pool_accounts]

            for account in warmup_accounts:
                gmail_service = GmailService()
                
                if not authenticate_and_update_token(gmail_service, account):
                    continue
                
                # Fetch unread messages from any pool sender to this warmup inbox
                messages = gmail_service.get_unread_emails_from_any(pool_emails, max_results=50)
                updated = 0

                def normalize_subject(subj: str) -> str:
                    s = subj or ''
                    while s.strip().lower().startswith('re:'):
                        s = s.strip()[3:].lstrip()
                    return s

                for msg in messages:
                    try:
                        from_header = msg.get('from', '')
                        from_addr = from_header.split('<')[-1].strip('>') if '<' in from_header else from_header
                        reply_subject = normalize_subject(msg.get('subject', ''))

                        candidate = Email.query.filter(
                            Email.account_id == account.id,
                            Email.to_address == from_addr,
                            Email.is_replied == False
                        ).order_by(Email.sent_at.desc()).first()

                        if candidate and normalize_subject(candidate.subject) == reply_subject:
                            candidate.is_replied = True
                            candidate.replied_at = db.func.now()
                            db.session.flush()
                            try:
                                gmail_service.mark_as_read(msg['id'])
                            except Exception:
                                pass
                            updated += 1
                    except Exception as e:
                        logger.error(f"Error matching reply for account {account.email}: {e}")
                        db.session.rollback()
                        continue

                if updated:
                    db.session.commit()
                    total_replies += updated
                    logger.info(f"Updated {updated} replies for account {account.email}")
            
            return f"Checked replies: {total_replies} new replies found"
    except Exception as e:
        logger.error(f"Error in check_replies_task: {e}")
        db.session.rollback()
        return f"Error: {str(e)}"
    finally:
        db.session.remove()


@celery.task
def advance_warmup_day_task():
    """Advance warmup day for all warmup accounts (run once daily at midnight)"""
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
    finally:
        db.session.remove()


@celery.task
def warmup_status_report_task():
    """Generate warmup status report for all accounts"""
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
    finally:
        db.session.remove()


@celery.task
def calculate_warmup_scores_task():
    """
    Calculate and update warmup scores for all warmup accounts
    Runs every 6 hours to keep scores fresh
    """
    try:
        from app.services.warmup_score_service import calculate_and_update_warmup_score
        
        warmup_accounts = Account.query.filter_by(
            is_active=True,
            account_type='warmup'
        ).all()
        
        if not warmup_accounts:
            logger.info("No warmup accounts to calculate scores for")
            return "No warmup accounts found"
        
        success_count = 0
        error_count = 0
        
        for account in warmup_accounts:
            try:
                score_data = calculate_and_update_warmup_score(account.id, db.session)
                logger.info(
                    f"✅ Account {account.email}: Score = {score_data['total_score']} "
                    f"({score_data['grade']}) - {score_data['status_message']}"
                )
                success_count += 1
            except Exception as e:
                logger.error(f"❌ Error calculating score for {account.email}: {e}")
                error_count += 1
        
        result_msg = (
            f"Warmup scores calculated: {success_count} successful, {error_count} errors. "
            f"Total accounts: {len(warmup_accounts)}"
        )
        logger.info(result_msg)
        return result_msg
        
    except Exception as e:
        logger.error(f"Error in calculate_warmup_scores_task: {e}")
        return f"Error: {str(e)}"
    finally:
        db.session.remove()


@celery.task
def cleanup_old_schedules_task():
    """Clean up old completed/failed schedules (older than 7 days)"""
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
    finally:
        db.session.remove()

# Add after line 680 (before the Celery Beat Schedule section)

@celery.task
def check_spam_folder_task():
    """
    Check spam folders of pool accounts for emails from warmup accounts
    Recovers them and marks as not spam
    Runs every 6 hours
    """
    try:
        from app.models.spam_email import SpamEmail
        
        # Get all active pool accounts
        pool_accounts = Account.query.filter_by(
            is_active=True,
            account_type='pool'
        ).all()
        
        if not pool_accounts:
            logger.info("No pool accounts found for spam checking")
            return "No pool accounts available"
        
        # Get all warmup account email addresses
        warmup_accounts = Account.query.filter_by(
            is_active=True,
            account_type='warmup'
        ).all()
        
        if not warmup_accounts:
            logger.info("No warmup accounts found for spam checking")
            return "No warmup accounts to check"
        
        warmup_email_addresses = [acc.email for acc in warmup_accounts]
        warmup_email_map = {acc.email: acc.id for acc in warmup_accounts}
        
        total_spam_found = 0
        total_recovered = 0
        total_failed = 0
        
        for pool_account in pool_accounts:
            try:
                # Authenticate with Gmail
                gmail_service = GmailService()
                
                if not authenticate_and_update_token(gmail_service, pool_account):
                    logger.warning(f"Gmail authentication failed for pool account {pool_account.email}")
                    continue
                
                # Get spam emails from warmup accounts
                spam_messages = gmail_service.get_spam_emails(
                    sender_emails=warmup_email_addresses,
                    max_results=100
                )
                
                if not spam_messages:
                    logger.debug(f"No spam found in {pool_account.email} from warmup accounts")
                    continue
                
                logger.info(f"Found {len(spam_messages)} spam email(s) in {pool_account.email} from warmup accounts")
                total_spam_found += len(spam_messages)
                
                for spam_msg in spam_messages:
                    try:
                        # Extract sender email
                        from_header = spam_msg.get('from', '')
                        from_addr = from_header.split('<')[-1].strip('>') if '<' in from_header else from_header
                        
                        to_header = spam_msg.get('to', '')
                        to_addr = to_header.split('<')[-1].strip('>') if '<' in to_header else to_header
                        
                        # Verify sender is a warmup account
                        sender_account_id = warmup_email_map.get(from_addr)
                        if not sender_account_id:
                            logger.debug(f"Skipping spam message from unknown sender: {from_addr}")
                            continue
                        
                        # Check if already tracked
                        existing_spam = SpamEmail.query.filter_by(
                            gmail_message_id=spam_msg['message_id'],
                            pool_account_id=pool_account.id
                        ).first()
                        
                        if existing_spam and existing_spam.status == 'recovered':
                            logger.debug(f"Spam already recovered: {spam_msg['message_id']}")
                            continue
                        
                        # Try to find the original email record
                        email_record = Email.query.filter_by(
                            account_id=sender_account_id,
                            to_address=pool_account.email,
                            subject=spam_msg['subject']
                        ).order_by(Email.sent_at.desc()).first()
                        
                        # Mark as not spam in Gmail
                        if gmail_service.mark_not_spam(spam_msg['id']):
                            # Create or update spam record
                            if existing_spam:
                                spam_record = existing_spam
                                spam_record.increment_attempts()
                            else:
                                spam_record = SpamEmail(
                                    email_id=email_record.id if email_record else None,
                                    pool_account_id=pool_account.id,
                                    sender_account_id=sender_account_id,
                                    gmail_message_id=spam_msg['message_id'],
                                    subject=spam_msg['subject'],
                                    from_address=from_addr,
                                    to_address=to_addr,
                                    snippet=spam_msg.get('snippet', '')
                                )
                                db.session.add(spam_record)
                            
                            spam_record.mark_recovered()
                            db.session.commit()
                            
                            total_recovered += 1
                            logger.info(f"✓ Recovered spam email: {spam_msg['subject'][:50]} "
                                       f"from {from_addr} to {pool_account.email}")
                            
                            # Small delay between operations
                            time.sleep(random.uniform(1, 3))
                            
                        else:
                            # Mark as failed
                            if existing_spam:
                                spam_record = existing_spam
                                spam_record.increment_attempts()
                            else:
                                spam_record = SpamEmail(
                                    email_id=email_record.id if email_record else None,
                                    pool_account_id=pool_account.id,
                                    sender_account_id=sender_account_id,
                                    gmail_message_id=spam_msg['message_id'],
                                    subject=spam_msg['subject'],
                                    from_address=from_addr,
                                    to_address=to_addr,
                                    snippet=spam_msg.get('snippet', '')
                                )
                                db.session.add(spam_record)
                            
                            spam_record.mark_failed("Failed to mark as not spam")
                            db.session.commit()
                            
                            total_failed += 1
                            logger.error(f"✗ Failed to recover spam email: {spam_msg['subject'][:50]}")
                    
                    except Exception as e:
                        logger.error(f"Error processing spam message {spam_msg.get('id')}: {e}")
                        db.session.rollback()
                        continue
            
            except Exception as e:
                logger.error(f"Error checking spam for pool account {pool_account.email}: {e}")
                db.session.rollback()
                continue
        
        result_msg = (f"Spam check completed: {total_spam_found} found, "
                     f"{total_recovered} recovered, {total_failed} failed")
        logger.info(result_msg)
        return result_msg
        
    except Exception as e:
        logger.error(f"Error in check_spam_folder_task: {e}")
        db.session.rollback()
        return f"Error: {str(e)}"
    finally:
        db.session.remove()


@celery.task
def spam_report_task():
    """Generate spam detection report"""
    try:
        from app.models.spam_email import SpamEmail
        
        # Get spam statistics
        total_spam = SpamEmail.query.count()
        recovered = SpamEmail.query.filter_by(status='recovered').count()
        failed = SpamEmail.query.filter_by(status='failed').count()
        pending = SpamEmail.query.filter_by(status='detected').count()
        
        # Get recent spam (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_spam = SpamEmail.query.filter(
            SpamEmail.detected_at >= yesterday
        ).count()
        
        # Get spam by sender
        spam_by_sender = db.session.query(
            Account.email,
            db.func.count(SpamEmail.id).label('spam_count')
        ).join(
            SpamEmail, SpamEmail.sender_account_id == Account.id
        ).group_by(Account.email).all()
        
        logger.info(f"📊 Spam Detection Report:")
        logger.info(f"   Total tracked: {total_spam}")
        logger.info(f"   Recovered: {recovered}")
        logger.info(f"   Failed: {failed}")
        logger.info(f"   Pending: {pending}")
        logger.info(f"   Last 24h: {recent_spam}")
        
        if spam_by_sender:
            logger.info(f"   Spam by sender:")
            for email, count in spam_by_sender:
                logger.info(f"     - {email}: {count} spam emails")
        
        return f"Spam report: {total_spam} total, {recovered} recovered, {failed} failed"
        
    except Exception as e:
        logger.error(f"Error in spam_report_task: {e}")
        return f"Error: {str(e)}"
    finally:
        db.session.remove()

# Celery Beat Schedule
celery.conf.beat_schedule = {
    # Generate daily schedules - runs every hour to catch midnight in different timezones
    'generate-daily-schedules': {
        'task': 'app.tasks.email_tasks.generate_daily_schedules_task',
        'schedule': crontab(minute=1, hour='*/1'),  # Every hour at minute 1
    },
    
    # Send scheduled emails - runs every 2 minutes during business hours
    'send-scheduled-emails': {
        'task': 'app.tasks.email_tasks.send_scheduled_emails_task',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
    
    # Check for replies
    'check-replies': {
        'task': 'app.tasks.email_tasks.check_replies_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    # Simulate engagement (open emails and send replies) - runs every 3 minutes
    'simulate-engagement': {
        'task': 'app.tasks.email_tasks.simulate_engagement_task',
        'schedule': crontab(minute='*/3'),  # Every 3 minutes
    },
    # Advance warmup day once daily
    'advance-warmup-day': {
        'task': 'app.tasks.email_tasks.advance_warmup_day_task',
        'schedule': crontab(hour=0, minute=5),  # At 00:05 daily
    },
    
    # Calculate warmup scores every 6 hours
    'calculate-warmup-scores': {
        'task': 'app.tasks.email_tasks.calculate_warmup_scores_task',
        'schedule': crontab(minute=0, hour='*/6'), 
    },
    
    # Generate status report
    'warmup-status-report': {
        'task': 'app.tasks.email_tasks.warmup_status_report_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    
      # Check spam folders every 6 hours
    'check-spam-folders': {
        'task': 'app.tasks.email_tasks.check_spam_folder_task',
        # 'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'schedule': crontab(minute='*/1'),  # Every 3 minutes

        # 'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    
    # Generate spam report daily
    'spam-detection-report': {
        'task': 'app.tasks.email_tasks.spam_report_task',
        'schedule': crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    
    # Cleanup old schedules
    'cleanup-old-schedules': {
        'task': 'app.tasks.email_tasks.cleanup_old_schedules_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
