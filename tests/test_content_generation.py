#!/usr/bin/env python3
"""
Test Content Generation

This script tests the AI service content generation with all 4 methods:
1. Pure Template
2. Template + AI Fill
3. Template + AI Addon
4. AI Seeded

Run: python tests/test_content_generation.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from app.services.ai_service import AIService
import json

# Load environment variables
load_dotenv()

def test_content_generation():
    """Test all content generation methods"""
    
    print("=" * 80)
    print("EMAIL CONTENT GENERATION TEST")
    print("=" * 80)
    print()
    
    # Initialize AI service
    use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
    api_key = os.getenv('OPENAI_API_KEY')
    
    print(f"🔧 Configuration:")
    print(f"   USE_OPENAI: {use_ai}")
    print(f"   API_KEY: {'✓ Provided' if api_key and api_key != 'your-openai-api-key' else '✗ Not provided'}")
    print()
    
    ai_service = AIService(api_key=api_key, use_ai=use_ai)
    
    # Get AI status
    status = ai_service.get_ai_status()
    print(f"📊 AI Service Status:")
    print(f"   AI Available: {status['ai_available']}")
    print(f"   Templates Loaded: {status['templates_loaded']}")
    print(f"   Placeholder Categories: {status['placeholder_categories']}")
    print(f"   AI Prompts Loaded: {status['ai_prompts_loaded']}")
    print()
    
    # Get generation ratios
    ratios = ai_service.get_generation_stats()
    print(f"📈 Generation Ratios:")
    for method, ratio in ratios.items():
        print(f"   {method}: {ratio * 100:.1f}%")
    print()
    
    print("=" * 80)
    print("GENERATING TEST EMAILS")
    print("=" * 80)
    print()
    
    # Generate 20 test emails to see distribution
    results = {
        'pure_template': [],
        'template_ai_fill': [],
        'ai_addon': [],
        'ai_seeded': [],
        'pure_template_fallback': [],
        'fallback': []
    }
    
    print("📧 Generating 20 test emails...")
    print()
    
    for i in range(20):
        content = ai_service.generate_email_content()
        generation_type = content.get('generation_type', 'unknown')
        results[generation_type].append(content)
        
        # Print first few of each type
        if len(results[generation_type]) <= 2:
            print(f"─" * 80)
            print(f"Email #{i+1} - Type: {generation_type}")
            print(f"─" * 80)
            print(f"Subject: {content['subject']}")
            print(f"Content: {content['content']}")
            print()
    
    # Summary
    print("=" * 80)
    print("GENERATION DISTRIBUTION")
    print("=" * 80)
    print()
    
    total = sum(len(v) for v in results.values())
    for method, emails in results.items():
        count = len(emails)
        percentage = (count / total * 100) if total > 0 else 0
        print(f"   {method}: {count} emails ({percentage:.1f}%)")
    
    print()
    print("=" * 80)
    print("CONTENT QUALITY CHECKS")
    print("=" * 80)
    print()
    
    all_emails = [email for emails in results.values() for email in emails]
    
    # Check for variety
    subjects = [e['subject'] for e in all_emails]
    unique_subjects = len(set(subjects))
    print(f"✓ Subject variety: {unique_subjects}/{len(subjects)} unique ({unique_subjects/len(subjects)*100:.1f}%)")
    
    contents = [e['content'] for e in all_emails]
    unique_contents = len(set(contents))
    print(f"✓ Content variety: {unique_contents}/{len(contents)} unique ({unique_contents/len(contents)*100:.1f}%)")
    
    # Check for spam patterns
    spam_indicators = ['FREE', 'URGENT', 'CLICK HERE', 'BUY NOW', '!!!', '$$$']
    spam_found = 0
    for email in all_emails:
        text = (email['subject'] + ' ' + email['content']).upper()
        if any(indicator in text for indicator in spam_indicators):
            spam_found += 1
    
    print(f"✓ Spam patterns: {spam_found}/{len(all_emails)} flagged ({spam_found/len(all_emails)*100:.1f}%)")
    
    # Check average length
    avg_subject_len = sum(len(s) for s in subjects) / len(subjects)
    avg_content_len = sum(len(c) for c in contents) / len(contents)
    print(f"✓ Average subject length: {avg_subject_len:.1f} characters")
    print(f"✓ Average content length: {avg_content_len:.1f} characters")
    
    # Check for humanization features
    contractions = sum(1 for e in all_emails if any(c in e['content'] for c in ["'m", "'re", "'s", "'t", "'ll"]))
    print(f"✓ Contractions used: {contractions}/{len(all_emails)} emails ({contractions/len(all_emails)*100:.1f}%)")
    
    print()
    print("=" * 80)
    print("SAMPLE EMAILS FROM EACH TYPE")
    print("=" * 80)
    print()
    
    for method, emails in results.items():
        if emails:
            print(f"\n📝 {method.upper().replace('_', ' ')}")
            print(f"─" * 80)
            email = emails[0]
            print(f"Subject: {email['subject']}")
            print(f"Content: {email['content']}")
    
    print()
    print("=" * 80)
    print("TEST COMPLETED SUCCESSFULLY ✓")
    print("=" * 80)
    
    return results


def test_specific_generation_method(method='pure_template', count=5):
    """Test a specific generation method multiple times"""
    
    print()
    print("=" * 80)
    print(f"TESTING SPECIFIC METHOD: {method.upper()}")
    print("=" * 80)
    print()
    
    use_ai = os.getenv('USE_OPENAI', 'false').lower() == 'true'
    api_key = os.getenv('OPENAI_API_KEY')
    ai_service = AIService(api_key=api_key, use_ai=use_ai)
    
    # Temporarily set ratios to test specific method
    if method == 'pure_template':
        ai_service.generation_ratios = {'pure_template': 1.0, 'template_ai_fill': 0.0, 'ai_addon': 0.0, 'ai_seeded': 0.0}
    elif method == 'template_ai_fill' and ai_service.ai_available:
        ai_service.generation_ratios = {'pure_template': 0.0, 'template_ai_fill': 1.0, 'ai_addon': 0.0, 'ai_seeded': 0.0}
    elif method == 'ai_addon' and ai_service.ai_available:
        ai_service.generation_ratios = {'pure_template': 0.0, 'template_ai_fill': 0.0, 'ai_addon': 1.0, 'ai_seeded': 0.0}
    elif method == 'ai_seeded' and ai_service.ai_available:
        ai_service.generation_ratios = {'pure_template': 0.0, 'template_ai_fill': 0.0, 'ai_addon': 0.0, 'ai_seeded': 1.0}
    
    for i in range(count):
        print(f"\n📧 Email #{i+1}")
        print(f"─" * 80)
        content = ai_service.generate_email_content()
        print(f"Type: {content.get('generation_type', 'unknown')}")
        print(f"Subject: {content['subject']}")
        print(f"Content: {content['content']}")
    
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test email content generation')
    parser.add_argument('--method', type=str, choices=['pure_template', 'template_ai_fill', 'ai_addon', 'ai_seeded'],
                       help='Test specific generation method')
    parser.add_argument('--count', type=int, default=5, help='Number of emails to generate for specific method')
    
    args = parser.parse_args()
    
    if args.method:
        test_specific_generation_method(args.method, args.count)
    else:
        test_content_generation()
