#!/usr/bin/env python3
"""
Test script for the warmup score calculation system

Usage:
    python scripts/test_warmup_score.py [account_id]
    
If no account_id is provided, calculates scores for all warmup accounts.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.account import Account
from app.services.warmup_score_service import WarmupScoreCalculator, calculate_and_update_warmup_score


def test_single_account(account_id):
    """Test warmup score calculation for a single account"""
    print(f"\n{'='*80}")
    print(f"Testing Warmup Score Calculation for Account ID: {account_id}")
    print(f"{'='*80}\n")
    
    try:
        account = Account.query.get(account_id)
        if not account:
            print(f"❌ Error: Account {account_id} not found")
            return False
        
        print(f"📧 Account: {account.email}")
        print(f"🔄 Type: {account.account_type}")
        print(f"📅 Warmup Day: {account.warmup_day}")
        print(f"🎯 Phase: {account.get_warmup_phase()}")
        print(f"📊 Current stored score: {account.warmup_score}\n")
        
        # Calculate new score
        calculator = WarmupScoreCalculator(db.session)
        score_data = calculator.calculate_warmup_score(account_id)
        
        # Display results
        print(f"{'─'*80}")
        print(f"📊 WARMUP SCORE RESULTS")
        print(f"{'─'*80}\n")
        
        print(f"🎯 Total Score: {score_data['total_score']:.1f}/100")
        print(f"🏆 Grade: {score_data['grade']}")
        print(f"💬 Status: {score_data['status_message']}\n")
        
        print(f"{'─'*80}")
        print(f"📈 COMPONENT BREAKDOWN")
        print(f"{'─'*80}\n")
        
        # Open Rate
        open_comp = score_data['components']['open_rate']
        print(f"📖 Open Rate Component (40% weight):")
        print(f"   • Actual Rate: {open_comp['value']:.1f}%")
        print(f"   • Component Score: {open_comp['score']:.1f}/100")
        print(f"   • Contribution: {open_comp['contribution']:.1f} points\n")
        
        # Reply Rate
        reply_comp = score_data['components']['reply_rate']
        print(f"💬 Reply Rate Component (30% weight):")
        print(f"   • Actual Rate: {reply_comp['value']:.1f}%")
        print(f"   • Component Score: {reply_comp['score']:.1f}/100")
        print(f"   • Contribution: {reply_comp['contribution']:.1f} points\n")
        
        # Phase Progress
        phase_comp = score_data['components']['phase_progress']
        print(f"📅 Phase Progress Component (20% weight):")
        print(f"   • Current Day: {phase_comp['day']}")
        print(f"   • Phase: {phase_comp['phase']}")
        print(f"   • Component Score: {phase_comp['score']:.1f}/100")
        print(f"   • Contribution: {phase_comp['contribution']:.1f} points\n")
        
        # Spam Penalty
        spam_comp = score_data['components']['spam_penalty']
        print(f"🚨 Spam Penalty Component (10% weight):")
        print(f"   • Spam Count: {spam_comp['spam_count']}")
        print(f"   • Recovered: {spam_comp['recovered_count']}")
        print(f"   • Spam Rate: {spam_comp['spam_rate']:.1f}%")
        print(f"   • Component Score: {spam_comp['score']:.1f}/100")
        print(f"   • Contribution: {spam_comp['contribution']:.1f} points\n")
        
        # Statistics
        stats = score_data['statistics']
        print(f"{'─'*80}")
        print(f"📊 STATISTICS")
        print(f"{'─'*80}\n")
        print(f"   • Total Emails Sent: {stats['total_emails']}")
        print(f"   • Opened: {stats['opened_emails']}")
        print(f"   • Replied: {stats['replied_emails']}")
        print(f"   • In Spam: {stats['spam_count']}")
        print(f"   • Recovered: {stats['recovered_count']}\n")
        
        # Recommendations
        if score_data['recommendations']:
            print(f"{'─'*80}")
            print(f"💡 RECOMMENDATIONS")
            print(f"{'─'*80}\n")
            for rec in score_data['recommendations']:
                print(f"   {rec}")
            print()
        
        print(f"{'='*80}\n")
        print(f"✅ Test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error calculating warmup score: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_warmup_accounts():
    """Test warmup score calculation for all warmup accounts"""
    print(f"\n{'='*80}")
    print(f"Testing Warmup Score Calculation for All Warmup Accounts")
    print(f"{'='*80}\n")
    
    warmup_accounts = Account.query.filter_by(
        is_active=True,
        account_type='warmup'
    ).all()
    
    if not warmup_accounts:
        print("❌ No warmup accounts found")
        return False
    
    print(f"Found {len(warmup_accounts)} warmup account(s)\n")
    
    results = []
    for account in warmup_accounts:
        try:
            score_data = calculate_and_update_warmup_score(account.id, db.session)
            results.append({
                'email': account.email,
                'score': score_data['total_score'],
                'grade': score_data['grade'],
                'status': score_data['status_message'],
                'success': True
            })
            print(f"✅ {account.email}: Score = {score_data['total_score']:.1f} ({score_data['grade']})")
        except Exception as e:
            results.append({
                'email': account.email,
                'error': str(e),
                'success': False
            })
            print(f"❌ {account.email}: Error - {e}")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}\n")
    
    success_count = sum(1 for r in results if r['success'])
    error_count = len(results) - success_count
    
    print(f"Total accounts: {len(results)}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Errors: {error_count}\n")
    
    if success_count > 0:
        print("Successful calculations:")
        print(f"{'─'*80}")
        for result in results:
            if result['success']:
                print(f"  {result['email']:<40} Score: {result['score']:>5.1f} Grade: {result['grade']:>3}")
        print()
    
    return error_count == 0


def main():
    """Main test function"""
    app = create_app()
    
    with app.app_context():
        if len(sys.argv) > 1:
            # Test specific account
            try:
                account_id = int(sys.argv[1])
                success = test_single_account(account_id)
            except ValueError:
                print("❌ Error: Account ID must be an integer")
                print("Usage: python scripts/test_warmup_score.py [account_id]")
                return 1
        else:
            # Test all warmup accounts
            success = test_all_warmup_accounts()
        
        return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

