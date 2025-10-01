from app.celery_app import celery
from app import db
from app.models.account import Account
from app.models.email import Email
from app.services.gmail_service import GmailService
from app.services.ai_service import AIService
from app.services.human_timing_service import HumanTimingService
import os
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@celery.task
def send_warmup_emails_task():
    """Send warmup emails from warmup accounts to pool accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        session = None
        try:
            # Create a new session for this task
            session = db.session
            # Get warmup accounts (accounts being warmed up)
            warmup_accounts = Account.query.filter_by(
                is_active=True, 
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                logger.warning("No active warmup accounts found")
                return "No warmup accounts to process"
            
            # Get pool accounts (recipients)
            pool_accounts = Account.query.filter_by(
                is_active=True, 
                account_type='pool'
            ).all()
            
            if not pool_accounts:
                logger.warning("No pool accounts found for warmup recipients")
                return "No pool accounts available"
            
            pool_emails = [acc.email for acc in pool_accounts]
            logger.info(f"Found {len(warmup_accounts)} warmup account(s) and {len(pool_emails)} pool account(s)")
            
            # Initialize human timing service
            timing_service = HumanTimingService()
            
            for account in warmup_accounts:
                # Update daily limit based on warmup progress
                old_limit, new_limit = account.update_daily_limit()
                if old_limit and new_limit and old_limit != new_limit:
                    logger.info(f"Daily limit updated for {account.email}: {old_limit} → {new_limit} emails/day ({account.get_warmup_phase()})")
                    session.commit()
                
                # Check if account has reached daily limit
                today_emails = Email.query.filter(
                    Email.account_id == account.id,
                    Email.sent_at >= db.func.date(db.func.now())
                ).count()
                
                current_limit = account.calculate_daily_limit()
                if today_emails >= current_limit:
                    logger.info(f"Daily limit reached for {account.email} ({today_emails}/{current_limit}) - {account.get_warmup_phase()}")
                    continue
                
                # Check if we should send now based on human timing patterns
                last_email = Email.query.filter_by(account_id=account.id).order_by(Email.sent_at.desc()).first()
                last_sent = last_email.sent_at if last_email else None
                
                should_send, timing_reason = timing_service.should_send_now(last_sent, min_interval_minutes=5)
                if not should_send:
                    logger.debug(f"Skipping send for {account.email}: {timing_reason}")
                    continue
                
                logger.info(f"Sending email for {account.email}: {timing_reason}")
                
                # Select a random pool email as recipient
                import random
                recipient_email = random.choice(pool_emails)
                
                # Generate AI content (with toggle)
                use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
                ai_service = AIService(os.getenv('OPENAI_API_KEY'), use_ai=use_ai)
                content_data = ai_service.generate_email_content()
                
                # Generate tracking pixel ID
                tracking_pixel_id = str(uuid.uuid4())
                
                # Send email via Gmail
                gmail_service = GmailService()
                oauth_token_data = account.get_oauth_token_data()
                if not oauth_token_data or not gmail_service.authenticate_with_token(oauth_token_data):
                    logger.error(f"Gmail authentication failed for account {account.email}")
                    continue
                
                message_id = gmail_service.send_email(
                    recipient_email,
                    content_data['subject'],
                    content_data['content'],
                    tracking_pixel_id
                )
                
                if message_id:
                    # Save email record
                    email_record = Email(
                        account_id=account.id,
                        to_address=recipient_email,
                        subject=content_data['subject'],
                        content=content_data['content'],
                        tracking_pixel_id=tracking_pixel_id
                    )
                    
                    session.add(email_record)
                    session.commit()
                    
                    logger.info(f"Warmup email sent from {account.email} to {recipient_email} ({today_emails + 1}/{current_limit}) - {account.get_warmup_phase()}")
                    
                    # Add human-like delay after sending (only if more emails to send)
                    if today_emails + 1 < current_limit:
                        delay_seconds = timing_service.calculate_send_delay(base_interval_minutes=10)
                        delay_description = timing_service.get_human_delay_description(delay_seconds)
                        logger.info(f"Next email for {account.email} in {delay_description}")
                        
                        # Note: We don't actually sleep here as this would block the worker
                        # The delay is handled by the scheduling logic
            
            return "Warmup emails sent successfully"
            
        except Exception as e:
            logger.error(f"Error in send_warmup_emails_task: {e}")
            if session:
                session.rollback()
            return f"Error: {str(e)}"
        finally:
            # Ensure session is properly closed
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")

@celery.task
def check_replies_task():
    """Check for replies and update engagement metrics for warmup accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        session = None
        try:
            # Create a new session for this task
            session = db.session
            # Only check replies for warmup accounts
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
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
                    
                    session.commit()
                    logger.info(f"Updated {reply_count} replies for account {account.email}")
            
            return "Replies checked successfully"
            
        except Exception as e:
            logger.error(f"Error in check_replies_task: {e}")
            if session:
                session.rollback()
            return f"Error: {str(e)}"
        finally:
            # Ensure session is properly closed
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")

@celery.task
def advance_warmup_day_task():
    """Advance warmup day for all warmup accounts (run once daily)"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        session = None
        try:
            # Create a new session for this task
            session = db.session
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                logger.info("No warmup accounts found for daily advancement")
                return "No warmup accounts to advance"
            
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
                    
                    session.commit()
                else:
                    logger.debug(f"Warmup day already advanced today for {account.email}")
            
            return f"Warmup day advanced for {len(warmup_accounts)} account(s)"
            
        except Exception as e:
            logger.error(f"Error in advance_warmup_day_task: {e}")
            if session:
                session.rollback()
            return f"Error: {str(e)}"
        finally:
            # Ensure session is properly closed
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")

@celery.task
def warmup_status_report_task():
    """Generate warmup status report for all accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        session = None
        try:
            # Create a new session for this task
            session = db.session
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                return "No warmup accounts found"
            
            report = []
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
                
                # Calculate progress percentage
                current_limit = account.calculate_daily_limit()
                progress = (current_limit / account.warmup_target) * 100 if account.warmup_target > 0 else 0
                
                status = {
                    'email': account.email,
                    'phase': account.get_warmup_phase(),
                    'day': account.warmup_day,
                    'today_sent': today_emails,
                    'daily_limit': current_limit,
                    'target': account.warmup_target,
                    'progress': f"{progress:.1f}%",
                    'total_sent': total_emails,
                    'warmup_score': account.warmup_score
                }
                report.append(status)
                
                logger.info(f"📊 {account.email}: {status['phase']} | "
                          f"Today: {today_emails}/{current_limit} | "
                          f"Progress: {progress:.1f}% | "
                          f"Total sent: {total_emails}")
            
            return f"Status report generated for {len(report)} warmup account(s)"
            
        except Exception as e:
            logger.error(f"Error in warmup_status_report_task: {e}")
            if session:
                session.rollback()
            return f"Error: {str(e)}"
        finally:
            # Ensure session is properly closed
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")

@celery.task
def generate_daily_schedule_task():
    """Generate and log daily sending schedule for warmup accounts"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        session = None
        try:
            # Create a new session for this task
            session = db.session
            warmup_accounts = Account.query.filter_by(
                is_active=True,
                account_type='warmup'
            ).all()
            
            if not warmup_accounts:
                return "No warmup accounts found"
            
            timing_service = HumanTimingService()
            
            for account in warmup_accounts:
                current_limit = account.calculate_daily_limit()
                
                # Generate today's schedule
                schedule = timing_service.get_daily_send_schedule(current_limit)
                
                logger.info(f"📅 Daily schedule for {account.email} ({account.get_warmup_phase()}):")
                logger.info(f"   Target: {current_limit} emails between 9 AM - 6 PM")
                
                for i, send_time in enumerate(schedule, 1):
                    activity_weight = timing_service.get_activity_weight(send_time)
                    period = "Peak" if activity_weight >= 0.8 else "Normal" if activity_weight >= 0.6 else "Low"
                    logger.info(f"   {i:2d}. {send_time.strftime('%H:%M')} ({period} activity)")
                
                logger.info("")
            
            return f"Daily schedule generated for {len(warmup_accounts)} account(s)"
            
        except Exception as e:
            logger.error(f"Error in generate_daily_schedule_task: {e}")
            if session:
                session.rollback()
            return f"Error: {str(e)}"
        finally:
            # Ensure session is properly closed
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")

