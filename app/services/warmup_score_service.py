"""
Warmup Score Calculation Service

Implements the comprehensive warmup score algorithm with the following components:
- Open Rate Score (40% weight)
- Reply Rate Score (30% weight)
- Phase Progress Score (20% weight)
- Spam Penalty Score (10% weight)

Total Warmup Score = (Open Rate Score × 30%) + 
                     (Reply Rate Score × 20%) + 
                     (Phase Progress Score × 40%) + 
                     (Spam Penalty × 10%)
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class WarmupScoreCalculator:
    """Calculate comprehensive warmup scores for email accounts"""
    
    # Phase definitions
    PHASE_1 = (1, 7, 0.10, 50)      # Days 1-7, 10% target, 50 base score
    PHASE_2 = (8, 14, 0.25, 65)     # Days 8-14, 25% target, 65 base score
    PHASE_3 = (15, 21, 0.50, 80)    # Days 15-21, 50% target, 80 base score
    PHASE_4 = (22, 28, 0.75, 90)    # Days 22-28, 75% target, 90 base score
    PHASE_5 = (29, 999, 1.00, 100)  # Days 29+, 100% target, 100 base score
    
    PHASES = [PHASE_1, PHASE_2, PHASE_3, PHASE_4, PHASE_5]
    
    def __init__(self, db_session):
        """
        Initialize the calculator with database session
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def calculate_open_rate_score(self, open_rate: float) -> float:
        """
        Calculate Open Rate Score component (40% weight)
        
        Conversion to Points:
        - If Open Rate ≥ 60%  →  Score = 100
        - If Open Rate ≥ 40%  →  Score = 80
        - If Open Rate ≥ 20%  →  Score = 60
        - If Open Rate < 20%  →  Score = (Open Rate / 20) × 60
        
        Args:
            open_rate: Open rate percentage (0-100)
            
        Returns:
            Score out of 100
        """
        if open_rate >= 60:
            return 100.0
        elif open_rate >= 40:
            return 80.0
        elif open_rate >= 20:
            return 60.0
        else:
            return (open_rate / 20) * 60
    
    def calculate_reply_rate_score(self, reply_rate: float) -> float:
        """
        Calculate Reply Rate Score component (30% weight)
        
        Conversion to Points:
        - If Reply Rate ≥ 25%  →  Score = 100
        - If Reply Rate ≥ 15%  →  Score = 85
        - If Reply Rate ≥ 5%   →  Score = 70
        - If Reply Rate < 5%   →  Score = (Reply Rate / 5) × 70
        
        Args:
            reply_rate: Reply rate percentage (0-100)
            
        Returns:
            Score out of 100
        """
        if reply_rate >= 25:
            return 100.0
        elif reply_rate >= 15:
            return 85.0
        elif reply_rate >= 5:
            return 70.0
        else:
            return (reply_rate / 5) * 70
    
    def get_phase_info(self, warmup_day: int) -> Tuple[int, float, int]:
        """
        Get phase information for a given warmup day
        
        Args:
            warmup_day: Current warmup day
            
        Returns:
            Tuple of (phase_number, target_percentage, base_score)
        """
        for idx, (start_day, end_day, target_pct, base_score) in enumerate(self.PHASES, 1):
            if start_day <= warmup_day <= end_day:
                return (idx, target_pct, base_score)
        
        # Default to phase 5 if beyond all phases
        return (5, 1.0, 100)
    
    def calculate_phase_progress_score(self, warmup_day: int, warmup_target: int, 
                                       actual_daily_emails: int) -> float:
        """
        Calculate Phase Progress Score component (20% weight)
        
        Base score by phase:
        - Phase 1 (Days 1-7):   10% target  →  Score = 50
        - Phase 2 (Days 8-14):  25% target  →  Score = 65
        - Phase 3 (Days 15-21): 50% target  →  Score = 80
        - Phase 4 (Days 22-28): 75% target  →  Score = 90
        - Phase 5 (Days 29+):   100% target →  Score = 100
        
        Plus consistency bonus:
        - If (Actual Daily Emails / Target for Phase) ≥ 0.9  →  Add +10 points
        - If (Actual Daily Emails / Target for Phase) < 0.5  →  Subtract -15 points
        
        Args:
            warmup_day: Current warmup day
            warmup_target: Target emails per day at full warmup
            actual_daily_emails: Actual emails being sent daily
            
        Returns:
            Score out of 100
        """
        if warmup_day <= 0:
            return 0.0
        
        phase_num, target_pct, base_score = self.get_phase_info(warmup_day)
        
        # Calculate target for this phase
        phase_target = warmup_target * target_pct
        
        # Calculate consistency ratio
        if phase_target > 0:
            consistency_ratio = actual_daily_emails / phase_target
        else:
            consistency_ratio = 0
        
        # Apply consistency bonus/penalty
        score = float(base_score)
        if consistency_ratio >= 0.9:
            score += 10  # Bonus for meeting target
        elif consistency_ratio < 0.5:
            score -= 15  # Penalty for falling behind
        
        # Ensure score stays within bounds
        return max(0.0, min(100.0, score))
    
    def calculate_spam_penalty_score(self, total_emails: int, spam_count: int, 
                                     recovered_count: int) -> float:
        """
        Calculate Spam Penalty Score component (10% weight, inverted)
        
        Spam Rate = (Emails in Spam / Total Emails Sent) × 100
        
        Spam Score Calculation:
        - If Spam Rate ≤ 2%   →  Score = 100 (Excellent)
        - If Spam Rate ≤ 5%   →  Score = 85  (Good)
        - If Spam Rate ≤ 10%  →  Score = 60  (Concerning)
        - If Spam Rate > 10%  →  Score = Max(0, 100 - (Spam Rate × 8))
        
        Recovery Bonus:
        - If recovery rate ≥ 80%  →  Add +10 to Spam Score
        - If recovery rate < 50%  →  Subtract -10 from Spam Score
        
        Args:
            total_emails: Total emails sent
            spam_count: Number of emails that landed in spam
            recovered_count: Number of spam emails recovered
            
        Returns:
            Score out of 100
        """
        if total_emails == 0:
            return 100.0  # No emails sent yet, perfect score
        
        # Calculate spam rate
        spam_rate = (spam_count / total_emails) * 100
        
        # Calculate base spam score
        if spam_rate <= 2:
            base_score = 100.0
        elif spam_rate <= 5:
            base_score = 85.0
        elif spam_rate <= 10:
            base_score = 60.0
        else:
            base_score = max(0.0, 100 - (spam_rate * 8))
        
        # Calculate recovery rate and apply bonus/penalty
        if spam_count > 0:
            recovery_rate = (recovered_count / spam_count) * 100
            
            if recovery_rate >= 80:
                base_score += 10
            elif recovery_rate < 50:
                base_score -= 10
        
        # Ensure score stays within bounds
        return max(0.0, min(100.0, base_score))
    
    def calculate_warmup_score(self, account_id: int) -> Dict:
        """
        Calculate comprehensive warmup score for an account
        
        Args:
            account_id: Account ID to calculate score for
            
        Returns:
            Dictionary containing:
            - total_score: Final warmup score (0-100)
            - grade: Letter grade (A+, A, B, C, D, F)
            - status_message: User-friendly status message
            - components: Breakdown of score components
            - recommendations: List of improvement recommendations
        """
        from app.models.account import Account
        from app.models.email import Email
        from app.models.spam_email import SpamEmail
        
        # Get account
        account = Account.query.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Get email statistics
        total_emails = Email.query.filter_by(account_id=account_id).count()
        opened_emails = Email.query.filter_by(account_id=account_id, is_opened=True).count()
        replied_emails = Email.query.filter_by(account_id=account_id, is_replied=True).count()
        
        # Calculate rates
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        reply_rate = (replied_emails / total_emails * 100) if total_emails > 0 else 0
        
        # Get spam statistics
        spam_emails = SpamEmail.query.filter_by(sender_account_id=account_id).all()
        spam_count = len(spam_emails)
        recovered_count = sum(1 for spam in spam_emails if spam.status == 'recovered')
        
        # Get daily email count (average of last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_emails = Email.query.filter(
            Email.account_id == account_id,
            Email.sent_at >= seven_days_ago
        ).count()
        actual_daily_emails = recent_emails / 7 if recent_emails > 0 else account.daily_limit
        
        # Calculate component scores
        open_rate_score = self.calculate_open_rate_score(open_rate)
        reply_rate_score = self.calculate_reply_rate_score(reply_rate)
        phase_progress_score = self.calculate_phase_progress_score(
            account.warmup_day,
            account.warmup_target,
            actual_daily_emails
        )
        spam_penalty_score = self.calculate_spam_penalty_score(
            total_emails,
            spam_count,
            recovered_count
        )
        
        # Calculate total score with weights
        total_score = (
            (open_rate_score * 0.30) +
            (reply_rate_score * 0.20) +
            (phase_progress_score * 0.40) +
            (spam_penalty_score * 0.10)
        )
        
        # Round to 1 decimal place
        total_score = round(total_score, 1)
        
        # Determine grade and status
        grade, status_message = self._get_grade_and_status(
            total_score, 
            account.warmup_day,
            open_rate,
            reply_rate,
            spam_count
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            open_rate,
            reply_rate,
            phase_progress_score,
            spam_count,
            total_emails,
            account.warmup_day
        )
        
        return {
            'total_score': total_score,
            'grade': grade,
            'status_message': status_message,
            'components': {
                'open_rate': {
                    'value': round(open_rate, 1),
                    'score': round(open_rate_score, 1),
                    'contribution': round(open_rate_score * 0.30, 1),
                    'weight': 30
                },
                'reply_rate': {
                    'value': round(reply_rate, 1),
                    'score': round(reply_rate_score, 1),
                    'contribution': round(reply_rate_score * 0.20, 1),
                    'weight': 20
                },
                'phase_progress': {
                    'day': account.warmup_day,
                    'phase': self.get_phase_info(account.warmup_day)[0],
                    'score': round(phase_progress_score, 1),
                    'contribution': round(phase_progress_score * 0.40, 1),
                    'weight': 40
                },
                'spam_penalty': {
                    'spam_count': spam_count,
                    'recovered_count': recovered_count,
                    'spam_rate': round((spam_count / total_emails * 100) if total_emails > 0 else 0, 1),
                    'score': round(spam_penalty_score, 1),
                    'contribution': round(spam_penalty_score * 0.10, 1),
                    'weight': 10
                }
            },

            'statistics': {
                'total_emails': total_emails,
                'opened_emails': opened_emails,
                'replied_emails': replied_emails,
                'spam_count': spam_count,
                'recovered_count': recovered_count
            },
            'recommendations': recommendations
        }
    
    def _get_grade_and_status(self, score: float, warmup_day: int, 
                             open_rate: float, reply_rate: float, 
                             spam_count: int) -> Tuple[str, str]:
        """
        Get grade and user-friendly status message based on score
        
        Args:
            score: Total warmup score
            warmup_day: Current warmup day
            open_rate: Open rate percentage
            reply_rate: Reply rate percentagelready displays engagement rates from account configuration
            spam_count: Number of spam emails
            
        Returns:
            Tuple of (grade, status_message)
        """
        if score >= 90:
            grade = "A+"
            messages = [
                "🚀 Ready for takeoff! Your email reputation is excellent!",
                "🎯 Perfect warmup! Time to scale up your campaigns!",
                "⭐ Outstanding performance! You're cleared for full volume!",
                "🏆 Elite status achieved! Your emails are highly trusted!",
            ]
            # Pick message based on warmup day
            if warmup_day >= 29:
                status = messages[1]  # Completed warmup
            else:
                status = messages[0]
        
        elif score >= 80:
            grade = "A"
            messages = [
                "📈 Almost ready to takeoff! Keep up the excellent work!",
                "✨ Great progress! Your emails are gaining strong trust!",
                "🎪 Very good warmup! Just a bit more to reach peak performance!",
                "💪 Strong deliverability! You're on the right track!",
            ]
            status = messages[0] if warmup_day >= 21 else messages[1]
        
        elif score >= 70:
            grade = "B"
            messages = [
                "🌤️ Good progress! Some fine-tuning needed for optimal results.",
                "📊 Solid warmup! Focus on engagement to reach the next level.",
                "🔧 Doing well! A few adjustments will get you to excellent status.",
                "⚡ Building momentum! Keep improving engagement rates.",
            ]
            if open_rate < 40:
                status = messages[1]
            else:
                status = messages[0]
        
        elif score >= 60:
            grade = "C"
            messages = [
                "⚠️ Fair progress. Need to improve engagement and reduce spam.",
                "🔍 Acceptable but needs attention. Review your email strategy.",
                "📉 Moderate warmup. Focus on quality over quantity.",
                "🛠️ Needs work. Consider adjusting content and timing.",
            ]
            if spam_count > 5:
                status = messages[0]
            else:
                status = messages[1]
        
        elif score >= 50:
            grade = "D"
            messages = [
                "🚨 Poor performance. Urgent adjustments needed!",
                "⛔ Low score. Review and fix deliverability issues immediately.",
                "💔 Struggling warmup. Consider pausing and reassessing strategy.",
                "🔴 Critical attention needed. Your reputation is at risk.",
            ]
            status = messages[0] if spam_count > 10 else messages[1]
        
        else:
            grade = "F"
            messages = [
                "🛑 CRITICAL: Pause immediately! Major deliverability issues detected!",
                "❌ STOP: Your email reputation is severely damaged. Urgent action required!",
                "⚠️ ALERT: High spam rate. Do NOT send more emails until resolved!",
                "🚫 DANGER: Account health critical. Seek expert help immediately!",
            ]
            if spam_count > 20:
                status = messages[2]
            else:
                status = messages[0]
        
        return grade, status
    
    def _generate_recommendations(self, open_rate: float, reply_rate: float,
                                 phase_score: float, spam_count: int,
                                 total_emails: int, warmup_day: int) -> list:
        """
        Generate personalized recommendations for improvement
        
        Args:
            open_rate: Open rate percentage
            reply_rate: Reply rate percentage
            phase_score: Phase progress score
            spam_count: Number of spam emails
            total_emails: Total emails sent
            warmup_day: Current warmup day
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Open rate recommendations
        if open_rate < 40:
            recommendations.append("📧 Improve subject lines - current open rate is below optimal")
            recommendations.append("🕐 Try adjusting send times to match recipient activity")
        elif open_rate < 60:
            recommendations.append("✍️ Test different subject line styles to boost opens")
        
        # Reply rate recommendations
        if reply_rate < 15:
            recommendations.append("💬 Make emails more conversational to encourage replies")
            recommendations.append("❓ Include clear call-to-action or questions in emails")
        elif reply_rate < 25:
            recommendations.append("🎯 Personalize content more to increase engagement")
        
        # Phase progress recommendations
        if phase_score < 70:
            recommendations.append("📅 Stay consistent with daily sending volume")
            recommendations.append("⚖️ Ensure you're meeting your phase target daily")
        
        # Spam recommendations
        spam_rate = (spam_count / total_emails * 100) if total_emails > 0 else 0
        if spam_rate > 5:
            recommendations.append("🚨 URGENT: Reduce spam rate by improving email authentication (SPF, DKIM, DMARC)")
            recommendations.append("🔍 Review email content - avoid spam trigger words")
            recommendations.append("👥 Ensure you're only sending to engaged recipients")
        elif spam_rate > 2:
            recommendations.append("⚠️ Monitor spam rate closely and adjust content if needed")
        
        # Warmup day recommendations
        if warmup_day < 7:
            recommendations.append("🌱 Early stage: Focus on quality engagement over quantity")
        elif warmup_day < 14:
            recommendations.append("📈 Building trust: Maintain consistent sending patterns")
        elif warmup_day >= 29 and len(recommendations) == 0:
            recommendations.append("🎉 Warmup complete! Ready to scale to full volume")
        
        # If no issues, add positive reinforcement
        if len(recommendations) == 0:
            recommendations.append("✅ Everything looks great! Keep up the excellent work!")
            recommendations.append("🎯 Continue maintaining current strategy for best results")
        
        return recommendations


def calculate_and_update_warmup_score(account_id: int, db_session) -> Dict:
    """
    Calculate warmup score and update the account record
    
    Args:
        account_id: Account ID to calculate score for
        db_session: SQLAlchemy database session
        
    Returns:
        Dictionary containing score details
    """
    try:
        calculator = WarmupScoreCalculator(db_session)
        score_data = calculator.calculate_warmup_score(account_id)
        
        # Update account with new score
        from app.models.account import Account
        account = Account.query.get(account_id)
        if account:
            account.warmup_score = int(score_data['total_score'])
            db_session.commit()
            logger.info(f"Updated warmup score for account {account_id}: {score_data['total_score']}")
        
        return score_data
    
    except Exception as e:
        logger.error(f"Error calculating warmup score for account {account_id}: {e}")
        db_session.rollback()
        raise

