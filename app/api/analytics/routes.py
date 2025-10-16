from flask import request, jsonify, render_template_string
from app import db
from app.models.account import Account
from app.models.email import Email
from app.models.email_schedule import EmailSchedule
from . import analytics_bp
from sqlalchemy import func, case
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@analytics_bp.route('/account/<int:account_id>', methods=['GET'])
def get_account_analytics(account_id):
    """Get analytics for a specific account with comprehensive warmup score"""
    try:
        from app.services.warmup_score_service import calculate_and_update_warmup_score
        
        account = Account.query.get_or_404(account_id)
        
        # Get email statistics
        total_emails = Email.query.filter_by(account_id=account_id).count()
        opened_emails = Email.query.filter_by(account_id=account_id, is_opened=True).count()
        replied_emails = Email.query.filter_by(account_id=account_id, is_replied=True).count()
        
        # Calculate rates
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        reply_rate = (replied_emails / total_emails * 100) if total_emails > 0 else 0
        
        # Calculate comprehensive warmup score
        try:
            score_data = calculate_and_update_warmup_score(account_id, db.session)
            warmup_score = score_data['total_score']
            warmup_grade = score_data['grade']
            warmup_status = score_data['status_message']
        except Exception as score_error:
            logger.warning(f"Error calculating warmup score, using fallback: {score_error}")
            # Fallback to stored score if calculation fails
            warmup_score = account.warmup_score
            warmup_grade = "N/A"
            warmup_status = "Score calculation pending"
        
        return jsonify({
            'account_id': account_id,
            'email': account.email,
            'total_emails': total_emails,
            'opened_emails': opened_emails,
            'replied_emails': replied_emails,
            'open_rate': round(open_rate, 2),
            'reply_rate': round(reply_rate, 2),
            'warmup_score': warmup_score,
            'warmup_grade': warmup_grade,
            'warmup_status': warmup_status,
            'daily_limit': account.daily_limit,
            'is_active': account.is_active
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@analytics_bp.route('/overview', methods=['GET'])
def get_overview_analytics():
    """Get overview analytics for all accounts"""
    try:
        # Get total statistics
        total_accounts = Account.query.filter_by(is_active=True).count()
        total_emails = Email.query.count()
        total_opened = Email.query.filter_by(is_opened=True).count()
        total_replied = Email.query.filter_by(is_replied=True).count()
        
        # Calculate overall rates
        overall_open_rate = (total_opened / total_emails * 100) if total_emails > 0 else 0
        overall_reply_rate = (total_replied / total_emails * 100) if total_emails > 0 else 0
        
        return jsonify({
            'total_accounts': total_accounts,
            'total_emails': total_emails,
            'total_opened': total_opened,
            'total_replied': total_replied,
            'overall_open_rate': round(overall_open_rate, 2),
            'overall_reply_rate': round(overall_reply_rate, 2)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting overview analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================
# NEW: COMPREHENSIVE DASHBOARD DATA
# ============================================

# Add this route to the analytics blueprint

@analytics_bp.route('/account/<int:account_id>/warmup-score', methods=['GET'])
def get_detailed_warmup_score(account_id):
    """Get detailed warmup score breakdown for an account"""
    try:
        from app.services.warmup_score_service import WarmupScoreCalculator
        
        account = Account.query.get_or_404(account_id)
        
        # Calculate comprehensive warmup score
        calculator = WarmupScoreCalculator(db.session)
        score_data = calculator.calculate_warmup_score(account_id)
        
        return jsonify({
            'success': True,
            'data': score_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting detailed warmup score: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analytics_bp.route('/spam-stats', methods=['GET'])
def get_spam_stats():
    """Get spam detection and recovery statistics"""
    try:
        from app.models.spam_email import SpamEmail
        
        # Check if SpamEmail table exists by trying a simple query
        try:
            # Overall statistics
            total_spam = SpamEmail.query.count()
            recovered = SpamEmail.query.filter_by(status='recovered').count()
            failed = SpamEmail.query.filter_by(status='failed').count()
            pending = SpamEmail.query.filter_by(status='detected').count()
        except Exception as db_error:
            # Table might not exist, return empty data
            logger.warning(f"SpamEmail table might not exist: {db_error}")
            return jsonify({
                'success': True,
                'data': {
                    'summary': {
                        'total_spam': 0,
                        'recovered': 0,
                        'failed': 0,
                        'pending': 0,
                        'recovery_rate': 0
                    },
                    'by_sender': [],
                    'by_pool_account': [],
                    'recent_spam': []
                }
            }), 200
        
        # Recent spam (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_spam = SpamEmail.query.filter(
            SpamEmail.detected_at >= week_ago
        ).all()
        
        # Recovery rate
        recovery_rate = (recovered / total_spam * 100) if total_spam > 0 else 0
        
        # Spam by account
        spam_by_sender = db.session.query(
            Account.email,
            Account.id,
            func.count(SpamEmail.id).label('spam_count'),
            func.coalesce(
                func.sum(
                    case(
                        (SpamEmail.status == 'recovered', 1),
                        else_=0
                    )
                ), 
                0
            ).label('recovered_count')
        ).join(
            SpamEmail, SpamEmail.sender_account_id == Account.id
        ).group_by(Account.id, Account.email).all()
        
        spam_by_pool = db.session.query(
            Account.email,
            Account.id,
            func.count(SpamEmail.id).label('spam_count')
        ).join(
            SpamEmail, SpamEmail.pool_account_id == Account.id
        ).group_by(Account.id, Account.email).all()
        
        # Recent spam details
        recent_spam_details = [{
            'id': spam.id,
            'subject': spam.subject or '(No Subject)',
            'from': spam.from_address,
            'to': spam.to_address,
            'detected_at': spam.detected_at.isoformat() if spam.detected_at else None,
            'recovered_at': spam.recovered_at.isoformat() if spam.recovered_at else None,
            'status': spam.status,
            'recovery_attempts': spam.recovery_attempts or 0
        } for spam in recent_spam[:20]]  # Limit to 20 most recent
        
        return jsonify({
            'success': True,
            'data': {
                'summary': {
                    'total_spam': total_spam,
                    'recovered': recovered,
                    'failed': failed,
                    'pending': pending,
                    'recovery_rate': round(recovery_rate, 2)
                },
                'by_sender': [{
                    'email': email,
                    'account_id': acc_id,
                    'spam_count': spam_count or 0,
                    'recovered_count': recovered_count or 0,
                    'recovery_rate': round((recovered_count / spam_count * 100) if spam_count > 0 and recovered_count else 0, 2)
                } for email, acc_id, spam_count, recovered_count in spam_by_sender],
                'by_pool_account': [{
                    'email': email,
                    'account_id': acc_id,
                    'spam_count': spam_count or 0
                } for email, acc_id, spam_count in spam_by_pool],
                'recent_spam': recent_spam_details
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in spam-stats endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/dashboard/data', methods=['GET'])
def get_dashboard_data():
    """Get complete dashboard data including warmup and pool accounts"""
    try:
        # ===== WARMUP ACCOUNTS =====
        warmup_accounts = Account.query.filter_by(
            is_active=True,
            account_type='warmup'
        ).all()
        
        warmup_data = []
        for account in warmup_accounts:
            # Sent emails statistics
            total_sent = Email.query.filter_by(account_id=account.id).count()
            opened = Email.query.filter_by(account_id=account.id, is_opened=True).count()
            replied = Email.query.filter_by(account_id=account.id, is_replied=True).count()
            
            # Today's statistics
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_sent = Email.query.filter(
                Email.account_id == account.id,
                Email.sent_at >= today_start
            ).count()
            
            # Pending schedules for today
            today_pending = EmailSchedule.query.filter(
                EmailSchedule.account_id == account.id,
                EmailSchedule.schedule_date == datetime.utcnow().date(),
                EmailSchedule.status == 'pending'
            ).count()
            
            # Calculate rates
            open_rate = (opened / total_sent * 100) if total_sent > 0 else 0
            reply_rate = (replied / total_sent * 100) if total_sent > 0 else 0
            
            # Calculate comprehensive warmup score with status message
            warmup_score = account.warmup_score
            warmup_grade = "N/A"
            warmup_status = "Score calculation pending"
            try:
                from app.services.warmup_score_service import WarmupScoreCalculator
                calculator = WarmupScoreCalculator(db.session)
                score_data = calculator.calculate_warmup_score(account.id)
                warmup_score = score_data['total_score']
                warmup_grade = score_data['grade']
                warmup_status = score_data['status_message']
            except Exception as score_error:
                logger.warning(f"Error calculating warmup score for {account.email}: {score_error}")
            
            warmup_data.append({
                'id': account.id,
                'email': account.email,
                'warmup_day': account.warmup_day,
                'warmup_phase': account.get_warmup_phase(),
                'daily_limit': account.daily_limit,
                'warmup_target': account.warmup_target,
                'timezone': account.timezone,
                'today_sent': today_sent,
                'today_pending': today_pending,
                'total_sent': total_sent,
                'total_opened': opened,
                'total_replied': replied,
                'open_rate': round(open_rate, 1),
                'reply_rate': round(reply_rate, 1),
                'warmup_score': warmup_score,
                'warmup_grade': warmup_grade,
                'warmup_status': warmup_status,
                'progress_percentage': round((account.daily_limit / account.warmup_target * 100), 1) if account.warmup_target > 0 else 0
            })
        
        # ===== POOL ACCOUNTS =====
        pool_accounts = Account.query.filter_by(
            is_active=True,
            account_type='pool'
        ).all()
        
        pool_data = []
        for account in pool_accounts:
            # Received emails (emails sent TO this pool account)
            total_received = Email.query.filter_by(to_address=account.email).count()
            received_opened = Email.query.filter_by(to_address=account.email, is_opened=True).count()
            received_replied = Email.query.filter_by(to_address=account.email, is_replied=True).count()
            
            # Today's received
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_received = Email.query.filter(
                Email.to_address == account.email,
                Email.sent_at >= today_start
            ).count()
            
            # Engagement rates
            open_rate = (received_opened / total_received * 100) if total_received > 0 else 0
            reply_rate = (received_replied / total_received * 100) if total_received > 0 else 0
            
            pool_data.append({
                'id': account.id,
                'email': account.email,
                'timezone': account.timezone,
                'today_received': today_received,
                'total_received': total_received,
                'total_opened': received_opened,
                'total_replied': received_replied,
                'open_rate': round(open_rate, 1),
                'reply_rate': round(reply_rate, 1),
            })
        
        # ===== OVERALL STATISTICS =====
        total_emails_sent = Email.query.count()
        total_opened = Email.query.filter_by(is_opened=True).count()
        total_replied = Email.query.filter_by(is_replied=True).count()
        
        overall_open_rate = (total_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0
        overall_reply_rate = (total_replied / total_emails_sent * 100) if total_emails_sent > 0 else 0
        
        # Today's statistics
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sent = Email.query.filter(Email.sent_at >= today_start).count()
        today_opened = Email.query.filter(
            Email.sent_at >= today_start,
            Email.is_opened == True
        ).count()
        today_replied = Email.query.filter(
            Email.sent_at >= today_start,
            Email.is_replied == True
        ).count()
        
        # Pending schedules
        total_pending = EmailSchedule.query.filter(
            EmailSchedule.schedule_date == datetime.utcnow().date(),
            EmailSchedule.status == 'pending'
        ).count()
        
        return jsonify({
            'overall': {
                'total_warmup_accounts': len(warmup_data),
                'total_pool_accounts': len(pool_data),
                'total_emails_sent': total_emails_sent,
                'total_opened': total_opened,
                'total_replied': total_replied,
                'overall_open_rate': round(overall_open_rate, 1),
                'overall_reply_rate': round(overall_reply_rate, 1),
                'today_sent': today_sent,
                'today_opened': today_opened,
                'today_replied': today_replied,
                'today_pending': total_pending
            },
            'warmup_accounts': warmup_data,
            'pool_accounts': pool_data,
            'last_updated': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# NEW: HTML DASHBOARD VIEW
# ============================================

"""
Enhanced Analytics Dashboard with Integrated Spam Statistics
Add this to your analytics/routes.py to replace the existing dashboard route
"""

@analytics_bp.route('/dashboard', methods=['GET'])
@analytics_bp.route('/', methods=['GET'])
def analytics_dashboard():
    """Render enhanced HTML dashboard with spam monitoring"""
    
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Email Warmup Analytics Dashboard</title>
  <style>
    :root {
      --bg: #f8fdf9;
      --card: #ffffff;
      --text: #1e3a28;
      --muted: #6b8270;
      --subtle: #95a599;
      --primary: #4ade80;
      --primary-dark: #22c55e;
      --primary-light: #d1fae5;
      --primary-50: #f0fdf4;
      --accent: #86efac;
      --success: #10b981;
      --warning: #fbbf24;
      --danger: #ef4444;
      --shadow: 0 4px 20px rgba(34, 197, 94, 0.08);
      --shadow-hover: 0 8px 30px rgba(34, 197, 94, 0.15);
      --radius: 16px;
      --radius-sm: 12px;
      --radius-lg: 20px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; }

    body {
      font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
      color: var(--text);
      background: linear-gradient(135deg, #f0fdf4 0%, #f8fdf9 50%, #ecfdf5 100%);
      padding: 32px;
      letter-spacing: -0.01em;
      line-height: 1.6;
    }

    .container { 
      max-width: 1400px; 
      margin: 0 auto; 
    }

    /* Header */
    .header {
      background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%);
      backdrop-filter: blur(12px);
      border: 2px solid #d1fae5;
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow);
      padding: 32px 36px;
      margin-bottom: 28px;
      transition: all 0.3s ease;
    }

    .header:hover {
      box-shadow: var(--shadow-hover);
      transform: translateY(-2px);
    }

    .header h1 {
      font-size: 32px;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex; 
      align-items: center; 
      gap: 12px;
      color: var(--text);
    }

    .header p { 
      color: var(--muted); 
      margin-top: 8px; 
      font-size: 16px; 
    }

    .header-actions { 
      margin-top: 20px; 
      display: flex; 
      align-items: center; 
      gap: 12px; 
      flex-wrap: wrap; 
    }

    .button {
      appearance: none; 
      border: 0; 
      cursor: pointer;
      padding: 12px 20px; 
      font-weight: 600; 
      font-size: 14px;
      border-radius: var(--radius-sm); 
      transition: all 0.25s ease;
      display: inline-flex; 
      align-items: center; 
      gap: 8px;
      box-shadow: 0 2px 8px rgba(34, 197, 94, 0.2);
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
      color: white;
      font-family: inherit;
    }

    .button:hover { 
      transform: translateY(-2px); 
      box-shadow: 0 6px 20px rgba(34, 197, 94, 0.35); 
    }

    .button:active { 
      transform: translateY(0); 
    }

    .subtle { 
      background: linear-gradient(135deg, #f0fdf4 0%, #d1fae5 100%);
      color: var(--text); 
      box-shadow: 0 2px 8px rgba(34, 197, 94, 0.1);
    }

    .subtle:hover { 
      background: linear-gradient(135deg, #d1fae5 0%, #bbf7d0 100%);
      box-shadow: 0 4px 12px rgba(34, 197, 94, 0.2);
    }

    .last-updated { 
      color: var(--subtle); 
      font-size: 13px; 
      padding: 8px 12px;
      background: var(--primary-50);
      border-radius: 8px;
    }

    /* Stats Grid */
    .stats-grid {
      display: grid; 
      gap: 20px; 
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      margin-bottom: 28px;
    }

    .stat-card {
      background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%);
      border: 2px solid #d1fae5;
      border-radius: var(--radius);
      padding: 24px;
      box-shadow: var(--shadow);
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
    }

    .stat-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, var(--primary), var(--accent));
      opacity: 0;
      transition: opacity 0.3s ease;
    }

    .stat-card:hover {
      transform: translateY(-4px); 
      box-shadow: var(--shadow-hover);
      border-color: var(--primary);
    }

    .stat-card:hover::before {
      opacity: 1;
    }

    .stat-label { 
      color: var(--muted); 
      font-size: 12px; 
      text-transform: uppercase; 
      font-weight: 700; 
      letter-spacing: 0.1em; 
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .stat-value { 
      font-size: 36px; 
      font-weight: 800; 
      margin-top: 12px; 
      letter-spacing: -0.02em;
      color: var(--text);
    }

    .stat-subtext { 
      margin-top: 8px; 
      color: var(--subtle); 
      font-size: 13px; 
    }

    /* Section Title */
    .section-title {
      background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%);
      border: 2px solid #d1fae5;
      border-radius: var(--radius);
      padding: 18px 24px;
      box-shadow: var(--shadow);
      margin: 16px 0 12px;
      display: flex; 
      align-items: center; 
      justify-content: space-between; 
      gap: 12px;
    }

    .section-title h2 { 
      font-size: 20px; 
      display: flex; 
      align-items: center; 
      gap: 10px;
      color: var(--text);
      font-weight: 700;
    }

    .badge {
      font-size: 12px; 
      font-weight: 700; 
      padding: 8px 14px; 
      border-radius: 999px; 
      border: 2px solid transparent;
      transition: all 0.2s ease;
    }

    .badge-warmup { 
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
      color: #92400e; 
      border-color: #fcd34d; 
    }

    .badge-pool { 
      background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
      color: #1e40af; 
      border-color: #93c5fd; 
    }

    .badge-spam { 
      background: linear-gradient(135deg, #fecaca 0%, #fca5a5 100%);
      color: #991b1b; 
      border-color: #f87171; 
    }

    .badge-success { 
      background: linear-gradient(135deg, var(--primary-light) 0%, var(--accent) 100%);
      color: #065f46; 
      border-color: var(--primary); 
    }

    /* Tabs */
    .tabs {
      display: flex; 
      gap: 12px; 
      margin-bottom: 16px;
      background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%);
      padding: 12px;
      border-radius: var(--radius);
      border: 2px solid #d1fae5;
      box-shadow: var(--shadow);
    }

    .tab {
      flex: 1;
      padding: 14px 24px;
      border: 0;
      background: transparent;
      color: var(--muted);
      font-weight: 600;
      font-size: 15px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.25s ease;
      font-family: inherit;
    }

    .tab:hover { 
      background: var(--primary-50);
      color: var(--text); 
    }

    .tab.active {
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
      color: white;
      box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    /* Tables */
    .table-container {
      background: white;
      border: 2px solid #d1fae5;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    table { width: 100%; border-collapse: collapse; }

    thead th {
      position: sticky; 
      top: 0; 
      z-index: 1;
      background: linear-gradient(135deg, #f0fdf4 0%, #d1fae5 100%);
      color: var(--text);
      text-transform: uppercase; 
      font-size: 11px; 
      letter-spacing: 0.08em;
      padding: 16px 20px; 
      border-bottom: 2px solid #bbf7d0;
      text-align: left;
      font-weight: 700;
    }

    tbody td { 
      padding: 20px; 
      border-bottom: 1px solid #f0fdf4;
      font-size: 14px; 
    }

    tbody tr {
      transition: all 0.2s ease;
    }

    tbody tr:hover { 
      background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
    }

    tbody tr:last-child td { border-bottom: none; }

    .email-strong { 
      font-weight: 700; 
      letter-spacing: -0.01em;
      color: var(--text);
    }

    .muted { 
      color: var(--muted); 
      font-size: 12px; 
    }

    /* Progress Bar */
    .progress {
      display: flex; 
      flex-direction: column; 
      gap: 8px; 
      min-width: 220px;
    }

    .progress-bar { 
      width: 100%; 
      height: 10px; 
      background: #f0fdf4;
      border: 1px solid #d1fae5;
      border-radius: 999px; 
      overflow: hidden; 
    }

    .progress-fill { 
      height: 100%; 
      background: linear-gradient(90deg, var(--primary) 0%, var(--success) 100%);
      border-radius: 999px; 
      transition: width 0.4s ease;
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
    }

    /* Metrics */
    .metric { 
      display: inline-flex; 
      align-items: center; 
      gap: 6px; 
      padding: 8px 12px; 
      border-radius: var(--radius-sm);
      font-weight: 700; 
      font-size: 12px; 
      border: 2px solid;
      transition: all 0.2s ease;
    }

    .metric:hover {
      transform: translateY(-1px);
    }

    .metric-good { 
      background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
      color: #065f46;
      border-color: var(--primary);
    }

    .metric-medium { 
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
      color: #78350f;
      border-color: #fcd34d;
    }

    .metric-low { 
      background: linear-gradient(135deg, #fecaca 0%, #fca5a5 100%);
      color: #7f1d1d;
      border-color: #f87171;
    }

    /* Score */
    .score { 
      font-size: 28px; 
      font-weight: 800; 
      letter-spacing: -0.02em; 
    }

    /* Status Badge */
    .status-badge {
      display: inline-flex; 
      align-items: center; 
      gap: 6px;
      padding: 8px 14px; 
      border-radius: 999px;
      font-size: 12px; 
      font-weight: 700;
      border: 2px solid;
      transition: all 0.2s ease;
    }

    .status-badge:hover {
      transform: scale(1.05);
    }

    .status-recovered { 
      background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
      color: #065f46; 
      border-color: var(--primary); 
    }

    .status-detected { 
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
      color: #78350f; 
      border-color: #fcd34d; 
    }

    .status-failed { 
      background: linear-gradient(135deg, #fecaca 0%, #fca5a5 100%);
      color: #991b1b; 
      border-color: #f87171; 
    }

    /* Alert Box */
    .alert {
      padding: 20px 24px;
      border-radius: var(--radius);
      border: 2px solid;
      margin-bottom: 20px;
      display: flex;
      align-items: flex-start;
      gap: 14px;
      box-shadow: var(--shadow);
    }

    .alert-warning {
      background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
      border-color: #fcd34d;
      color: #78350f;
    }

    .alert-info {
      background: linear-gradient(135deg, #f0fdf4 0%, #d1fae5 100%);
      border-color: var(--primary);
      color: #065f46;
    }

    .alert-icon { font-size: 24px; }
    .alert-content { flex: 1; }
    .alert-title { font-weight: 700; margin-bottom: 6px; font-size: 15px; }

    /* Loading & Error States */
    .loading { 
      text-align: center; 
      color: var(--muted); 
      padding: 60px 0; 
    }

    .spinner { 
      width: 56px; 
      height: 56px; 
      border: 4px solid #d1fae5;
      border-top-color: var(--primary);
      border-radius: 999px; 
      animation: spin 1s linear infinite; 
      margin: 0 auto; 
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    .error { 
      background: linear-gradient(135deg, #fecaca 0%, #fca5a5 100%);
      color: #7f1d1d; 
      border: 2px solid #f87171;
      border-radius: var(--radius);
      padding: 18px 22px; 
      margin: 16px 0;
      box-shadow: var(--shadow);
    }

    .empty-state { 
      text-align: center; 
      padding: 60px 20px; 
      color: var(--muted); 
    }

    .empty-state-icon { 
      font-size: 64px; 
      margin-bottom: 12px; 
    }

    /* Utility */
    .row { 
      display: flex; 
      align-items: center; 
      justify-content: space-between; 
      gap: 12px; 
    }

    .col { 
      display: flex; 
      flex-direction: column; 
      gap: 6px; 
    }

    /* Spam specific styles */
    .spam-highlight { 
      background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
      border-left: 4px solid var(--danger); 
    }

    .recovery-timeline {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
    }

    .recovery-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
    }

    /* Animations */
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .stat-card, .section-title, .tabs, .table-container {
      animation: fadeIn 0.5s ease-out;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <h1>📧 Email Warmup Analytics</h1>
      <p>Real-time monitoring of warmup campaigns, pool accounts, and spam detection</p>
      <div class="header-actions">
        <button class="button" onclick="loadDashboard()" id="refresh-btn">
          <span id="refresh-icon">🔄</span>
          Refresh All Data
        </button>
        <button class="button subtle" onclick="toggleAutoRefresh()">
          <span id="auto-refresh-icon">⏸️</span>
          <span id="auto-refresh-text">Pause Auto-Refresh</span>
        </button>
        <span class="last-updated" id="last-updated"></span>
      </div>
    </div>

    <!-- Loading State -->
    <div id="loading" class="loading">
      <div class="spinner"></div>
      <p style="margin-top:16px; font-weight: 600;">Loading dashboard data…</p>
    </div>

    <!-- Error -->
    <div id="error" class="error" style="display:none"></div>

    <!-- Content -->
    <div id="dashboard-content" style="display:none">
      <!-- Overall Stats -->
      <div class="stats-grid" id="overall-stats"></div>

      <!-- Tabs Navigation -->
      <div class="tabs">
        <button class="tab active" onclick="switchTab('warmup')">
          🔥 Warmup Accounts
        </button>
        <button class="tab" onclick="switchTab('pool')">
          💧 Pool Accounts
        </button>
        <button class="tab" onclick="switchTab('spam')">
          🚨 Spam Monitoring
        </button>
      </div>

      <!-- Warmup Tab -->
      <div id="tab-warmup" class="tab-content active">
        <div class="section-title">
          <h2><span>🔥</span> Warmup Accounts</h2>
          <span class="badge badge-warmup" id="warmup-count">0 accounts</span>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Email Account</th>
                <th>Warmup Status</th>
                <th>Progress</th>
                <th>Today</th>
                <th>Engagement</th>
                <th>Score & Grade</th>
              </tr>
            </thead>
            <tbody id="warmup-table"></tbody>
          </table>
        </div>
      </div>

      <!-- Pool Tab -->
      <div id="tab-pool" class="tab-content">
        <div class="section-title">
          <h2><span>💧</span> Pool Accounts</h2>
          <span class="badge badge-pool" id="pool-count">0 accounts</span>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Email Account</th>
                <th>Timezone</th>
                <th>Today Received</th>
                <th>Total Received</th>
                <th>Opened</th>
                <th>Replied</th>
                <th>Engagement Rate</th>
              </tr>
            </thead>
            <tbody id="pool-table"></tbody>
          </table>
        </div>
      </div>

      <!-- Spam Tab -->
      <div id="tab-spam" class="tab-content">
        <div class="section-title">
          <h2><span>🚨</span> Spam Monitoring</h2>
          <span class="badge badge-spam" id="spam-total-count">0 detected</span>
        </div>

        <!-- Spam Alert -->
        <div id="spam-alert" style="display:none"></div>

        <!-- Spam Stats Grid -->
        <div class="stats-grid" id="spam-stats"></div>

        <!-- Spam by Sender -->
        <div class="section-title" style="margin-top: 24px;">
          <h3 style="font-size: 18px;">📤 Spam by Sender Account</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Sender Email</th>
                <th>Total in Spam</th>
                <th>Recovered</th>
                <th>Failed</th>
                <th>Recovery Rate</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="spam-by-sender-table"></tbody>
          </table>
        </div>

        <!-- Recent Spam Detections -->
        <div class="section-title" style="margin-top: 24px;">
          <h3 style="font-size: 18px;">📋 Recent Spam Detections (Last 20)</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Subject</th>
                <th>From → To</th>
                <th>Detected</th>
                <th>Recovery Time</th>
                <th>Attempts</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="recent-spam-table"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    let autoRefreshEnabled = true;
    let autoRefreshInterval;

    async function loadDashboard() {
      const loading = document.getElementById('loading');
      const error = document.getElementById('error');
      const content = document.getElementById('dashboard-content');
      const refreshIcon = document.getElementById('refresh-icon');

      loading.style.display = 'block';
      error.style.display = 'none';
      refreshIcon.textContent = '⏳';

      try {
        const dashRes = await fetch('/api/analytics/dashboard/data');
        if (!dashRes.ok) throw new Error('Failed to fetch dashboard data');
        const dashData = await dashRes.json();

        const spamRes = await fetch('/api/analytics/spam-stats');
        const spamData = await spamRes.json();

        renderOverallStats(dashData.overall, spamData.success ? spamData.data : null);
        renderWarmupAccounts(dashData.warmup_accounts);
        renderPoolAccounts(dashData.pool_accounts);
        
        if (spamData.success) {
          renderSpamStats(spamData.data);
        }

        const lastUpdated = new Date(dashData.last_updated);
        document.getElementById('last-updated').textContent = `Last updated: ${lastUpdated.toLocaleTimeString()}`;

        loading.style.display = 'none';
        content.style.display = 'block';
        refreshIcon.textContent = '🔄';
      } catch (e) {
        error.textContent = `Error: ${e.message}. Please check if the server is running.`;
        error.style.display = 'block';
        loading.style.display = 'none';
        refreshIcon.textContent = '❌';
      }
    }

    function switchTab(tab) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      event.target.classList.add('active');

      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.getElementById(`tab-${tab}`).classList.add('active');
    }

    function toggleAutoRefresh() {
      autoRefreshEnabled = !autoRefreshEnabled;
      const icon = document.getElementById('auto-refresh-icon');
      const text = document.getElementById('auto-refresh-text');
      
      if (autoRefreshEnabled) {
        icon.textContent = '⏸️';
        text.textContent = 'Pause Auto-Refresh';
        startAutoRefresh();
      } else {
        icon.textContent = '▶️';
        text.textContent = 'Resume Auto-Refresh';
        if (autoRefreshInterval) {
          clearInterval(autoRefreshInterval);
        }
      }
    }

    function startAutoRefresh() {
      if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
      }
      autoRefreshInterval = setInterval(() => {
        if (autoRefreshEnabled) {
          loadDashboard();
        }
      }, 30000);
    }

    function statCard(label, value, subtext, icon = '') {
      return `
        <div class="stat-card">
          <div class="stat-label">${icon} ${label}</div>
          <div class="stat-value">${value}</div>
          <div class="stat-subtext">${subtext}</div>
        </div>
      `;
    }

    function renderOverallStats(stats, spamData) {
      const c = document.getElementById('overall-stats');
      let cards = [
        statCard('Warmup Accounts', stats.total_warmup_accounts, 'Active campaigns', '🔥'),
        statCard('Pool Accounts', stats.total_pool_accounts, 'Recipient pool', '💧'),
        statCard('Emails Sent', stats.total_emails_sent, `Today: ${stats.today_sent} · Pending: ${stats.today_pending}`, '📧'),
        statCard('Open Rate', `${stats.overall_open_rate}%`, `${stats.total_opened} opened`, '📖'),
        statCard('Reply Rate', `${stats.overall_reply_rate}%`, `${stats.total_replied} replies`, '💬'),
      ];

      if (spamData && spamData.summary) {
        const recoveryRate = spamData.summary.recovery_rate || 0;
        cards.push(
          statCard('Spam Detected', spamData.summary.total_spam, 
            `${spamData.summary.recovered} recovered · ${spamData.summary.pending} pending`, '🚨')
        );
      }

      c.innerHTML = cards.join('');
    }

    function renderWarmupAccounts(accounts) {
      const tbody = document.getElementById('warmup-table');
      const badge = document.getElementById('warmup-count');
      badge.textContent = `${accounts.length} accounts`;

      if (!accounts.length) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="empty-state">
              <div class="empty-state-icon">📭</div>
              <div style="font-weight: 600; font-size: 16px; margin-bottom: 4px;">No warmup accounts yet</div>
              <div class="muted">Add accounts via OAuth to start warming up</div>
            </td>
          </tr>`;
        return;
      }

      tbody.innerHTML = accounts.map(acc => `
        <tr>
          <td>
            <div class="col">
              <span class="email-strong">${acc.email}</span>
              <span class="muted">${acc.warmup_phase}</span>
            </div>
          </td>
          <td>
            <div class="col" style="max-width: 320px;">
              <div style="font-weight:600; color:${getScoreColor(acc.warmup_score)}; font-size:14px; line-height:1.5;">
                ${acc.warmup_status || 'Calculating warmup status...'}
              </div>
              <span class="muted" style="margin-top:4px;">Day ${acc.warmup_day} • Total: ${acc.total_sent} emails</span>
            </div>
          </td>
          <td>
            <div class="progress">
              <div class="row">
                <span class="muted">Target</span>
                <span style="font-weight:700">${acc.daily_limit}/${acc.warmup_target}</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" style="width:${acc.progress_percentage}%"></div>
              </div>
              <span class="muted">${acc.progress_percentage}% of target</span>
            </div>
          </td>
          <td>
            <div class="col">
              <span style="font-size:20px; font-weight:800">${acc.today_sent}</span>
              <span class="muted">${acc.today_pending} pending</span>
            </div>
          </td>
          <td>
            <div class="col" style="gap:8px">
              <span class="metric ${getMetricClass(acc.open_rate)}">📖 ${acc.open_rate}%</span>
              <span class="metric ${getMetricClass(acc.reply_rate)}">💬 ${acc.reply_rate}%</span>
            </div>
          </td>
          <td>
            <div class="col" style="align-items:center;">
              <div class="score" style="color:${getScoreColor(acc.warmup_score)}">${acc.warmup_score}</div>
              <div class="badge" style="background:${getGradeBadgeColor(acc.warmup_grade)}; margin-top:8px; font-size:13px; border-color: ${getGradeBorderColor(acc.warmup_grade)};">
                ${acc.warmup_grade || 'N/A'}
              </div>
            </div>
          </td>
        </tr>
      `).join('');
    }

    function renderPoolAccounts(accounts) {
      const tbody = document.getElementById('pool-table');
      const badge = document.getElementById('pool-count');
      badge.textContent = `${accounts.length} accounts`;

      if (!accounts.length) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="empty-state">
              <div class="empty-state-icon">💧</div>
              <div style="font-weight: 600; font-size: 16px; margin-bottom: 4px;">No pool accounts yet</div>
              <div class="muted">Add pool accounts to receive warmup emails</div>
            </td>
          </tr>`;
        return;
      }

      tbody.innerHTML = accounts.map(acc => `
        <tr>
          <td><span class="email-strong">${acc.email}</span></td>
          <td><span class="muted">${acc.timezone}</span></td>
          <td><span style="font-size:20px; font-weight:800">${acc.today_received}</span></td>
          <td><span style="font-size:20px; font-weight:800">${acc.total_received}</span></td>
          <td><span class="metric ${getMetricClass(acc.open_rate)}">${acc.total_opened} (${acc.open_rate}%)</span></td>
          <td><span class="metric ${getMetricClass(acc.reply_rate)}">${acc.total_replied} (${acc.reply_rate}%)</span></td>
          <td><div style="font-weight:700">📖 ${acc.open_rate}% · 💬 ${acc.reply_rate}%</div></td>
        </tr>
      `).join('');
    }

    function renderSpamStats(data) {
      const summary = data.summary;
      const bySender = data.by_sender || [];
      const recentSpam = data.recent_spam || [];

      document.getElementById('spam-total-count').textContent = `${summary.total_spam} detected`;

      const alertDiv = document.getElementById('spam-alert');
      if (summary.total_spam > 0 && summary.recovery_rate < 80) {
        alertDiv.innerHTML = `
          <div class="alert alert-warning">
            <span class="alert-icon">⚠️</span>
            <div class="alert-content">
              <div class="alert-title">Spam Detection Alert</div>
              <div>Recovery rate is ${summary.recovery_rate}%. ${summary.pending} emails pending recovery. Consider reviewing your warmup strategy.</div>
            </div>
          </div>
        `;
        alertDiv.style.display = 'block';
      } else if (summary.total_spam === 0) {
        alertDiv.innerHTML = `
          <div class="alert alert-info">
            <span class="alert-icon">✅</span>
            <div class="alert-content">
              <div class="alert-title">No Spam Detected</div>
              <div>Great news! No warmup emails have landed in spam folders.</div>
            </div>
          </div>
        `;
        alertDiv.style.display = 'block';
      } else {
        alertDiv.style.display = 'none';
      }

      const statsDiv = document.getElementById('spam-stats');
      statsDiv.innerHTML = [
        statCard('Total Detected', summary.total_spam, 'In spam folders', '🚨'),
        statCard('Successfully Recovered', summary.recovered, `${summary.recovery_rate}% success rate`, '✅'),
        statCard('Pending Recovery', summary.pending, 'Awaiting action', '⏳'),
        statCard('Failed Recovery', summary.failed, 'Needs attention', '❌'),
      ].join('');

      const senderTbody = document.getElementById('spam-by-sender-table');
      if (bySender.length === 0) {
        senderTbody.innerHTML = `
          <tr>
            <td colspan="6" class="empty-state">
              <div class="empty-state-icon">✅</div>
              <div style="font-weight: 600; font-size: 16px; margin-bottom: 4px;">No spam detected from any sender</div>
            </td>
          </tr>`;
      } else {
        senderTbody.innerHTML = bySender.map(sender => {
          const recoveryRate = sender.recovery_rate || 0;
          const statusClass = recoveryRate >= 80 ? 'status-recovered' : recoveryRate >= 50 ? 'status-detected' : 'status-failed';
          const statusText = recoveryRate >= 80 ? '✅ Good' : recoveryRate >= 50 ? '⚠️ Fair' : '❌ Poor';
          
          return `
            <tr ${sender.spam_count > 5 ? 'class="spam-highlight"' : ''}>
              <td><span class="email-strong">${sender.email}</span></td>
              <td><span style="font-size:20px; font-weight:800">${sender.spam_count}</span></td>
              <td><span style="font-size:18px; font-weight:700; color: var(--success)">${sender.recovered_count}</span></td>
              <td><span style="font-size:18px; font-weight:700; color: var(--danger)">${sender.spam_count - sender.recovered_count}</span></td>
              <td>
                <div class="progress-bar" style="width: 140px;">
                  <div class="progress-fill" style="width:${recoveryRate}%; background: ${recoveryRate >= 80 ? 'linear-gradient(90deg, var(--success), var(--primary))' : recoveryRate >= 50 ? 'linear-gradient(90deg, var(--warning), #fbbf24)' : 'linear-gradient(90deg, var(--danger), #dc2626)'}"></div>
                </div>
                <span class="muted" style="margin-top: 6px; display: block; font-weight: 600;">${recoveryRate}%</span>
              </td>
              <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            </tr>
          `;
        }).join('');
      }

      const recentTbody = document.getElementById('recent-spam-table');
      if (recentSpam.length === 0) {
        recentTbody.innerHTML = `
          <tr>
            <td colspan="6" class="empty-state">
              <div class="empty-state-icon">📭</div>
              <div style="font-weight: 600; font-size: 16px; margin-bottom: 4px;">No recent spam detections</div>
            </td>
          </tr>`;
      } else {
        recentTbody.innerHTML = recentSpam.map(spam => {
          const detectedDate = new Date(spam.detected_at);
          const recoveredDate = spam.recovered_at ? new Date(spam.recovered_at) : null;
          
          let recoveryTime = 'N/A';
          if (recoveredDate) {
            const diffMs = recoveredDate - detectedDate;
            const diffMins = Math.floor(diffMs / 60000);
            if (diffMins < 60) {
              recoveryTime = `${diffMins}m`;
            } else {
              const hours = Math.floor(diffMins / 60);
              const mins = diffMins % 60;
              recoveryTime = `${hours}h ${mins}m`;
            }
          }

          const statusMap = {
            'recovered': { class: 'status-recovered', text: '✅ Recovered' },
            'detected': { class: 'status-detected', text: '⏳ Pending' },
            'failed': { class: 'status-failed', text: '❌ Failed' }
          };
          const status = statusMap[spam.status] || statusMap.detected;

          return `
            <tr>
              <td>
                <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600;">
                  ${spam.subject || '(No Subject)'}
                </div>
              </td>
              <td>
                <div class="col">
                  <span class="muted">From:</span>
                  <span style="font-size: 12px; font-weight: 600;">${spam.from}</span>
                  <span class="muted" style="margin-top: 4px;">To:</span>
                  <span style="font-size: 12px; font-weight: 600;">${spam.to}</span>
                </div>
              </td>
              <td>
                <div class="muted" style="font-weight: 500;">${detectedDate.toLocaleString()}</div>
              </td>
              <td>
                <span style="font-weight: 700; font-size: 15px; color: ${recoveredDate ? 'var(--success)' : 'var(--muted)'}">
                  ${recoveryTime}
                </span>
              </td>
              <td>
                <span class="metric ${spam.recovery_attempts > 3 ? 'metric-low' : 'metric-medium'}">
                  ${spam.recovery_attempts} ${spam.recovery_attempts === 1 ? 'attempt' : 'attempts'}
                </span>
              </td>
              <td>
                <span class="status-badge ${status.class}">${status.text}</span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    function getMetricClass(v) {
      if (v >= 50) return 'metric-good';
      if (v >= 25) return 'metric-medium';
      return 'metric-low';
    }

    function getScoreColor(s) {
      if (s >= 80) return '#16a34a';
      if (s >= 70) return '#059669';
      if (s >= 60) return '#d97706';
      if (s >= 50) return '#dc2626';
      return '#991b1b';
    }

    function getGradeBadgeColor(grade) {
      if (!grade || grade === 'N/A') return 'linear-gradient(135deg, #f1f5f9, #e2e8f0)';
      if (grade === 'A+' || grade === 'A') return 'linear-gradient(135deg, #d1fae5, #a7f3d0)';
      if (grade === 'B') return 'linear-gradient(135deg, #fef3c7, #fde68a)';
      if (grade === 'C') return 'linear-gradient(135deg, #fed7aa, #fdba74)';
      if (grade === 'D') return 'linear-gradient(135deg, #fecaca, #fca5a5)';
      return 'linear-gradient(135deg, #fee2e2, #fecaca)';
    }

    function getGradeBorderColor(grade) {
      if (!grade || grade === 'N/A') return '#cbd5e1';
      if (grade === 'A+' || grade === 'A') return '#4ade80';
      if (grade === 'B') return '#fcd34d';
      if (grade === 'C') return '#fb923c';
      if (grade === 'D') return '#f87171';
      return '#ef4444';
    }

    loadDashboard();
    startAutoRefresh();
  </script>
</body>
</html>
    """
    
    return render_template_string(html_template)