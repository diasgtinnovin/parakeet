#!/usr/bin/env python3
"""
Master Test Runner

Run all tests for the email warmup functionality in sequence.
This provides a complete validation of all components.

Run: python3 run_all_tests.py
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def print_header(text):
    """Print a nice header"""
    print("\n")
    print("=" * 80)
    print(f"  {text}")
    print("=" * 80)
    print()

def print_section(text):
    """Print a section divider"""
    print("\n")
    print("-" * 80)
    print(f"  {text}")
    print("-" * 80)
    print()

def run_test(test_name, test_function):
    """Run a single test and handle errors"""
    print_section(f"Running: {test_name}")
    try:
        test_function()
        print(f"\n✓ {test_name} PASSED")
        return True
    except Exception as e:
        print(f"\n✗ {test_name} FAILED")
        print(f"Error: {e}")
        return False

def main():
    """Run all tests in sequence"""
    
    print_header("EMAIL WARMUP POC - COMPLETE TEST SUITE")
    
    print("This will run all tests to validate:")
    print("  1. Content generation (AI + templates)")
    print("  2. Human timing logic")
    print("  3. Warmup simulation (30-day cycle)")
    print("  4. Integration tests (end-to-end)")
    print()
    
    input("Press Enter to start testing...")
    
    results = []
    
    # Test 1: Content Generation
    print_header("TEST 1: CONTENT GENERATION")
    try:
        from tests.test_content_generation import test_content_generation
        results.append(run_test("Content Generation", test_content_generation))
    except Exception as e:
        print(f"✗ Failed to load content generation test: {e}")
        results.append(False)
    
    # Test 2: Human Timing - Business Hours
    print_header("TEST 2: HUMAN TIMING - BUSINESS HOURS")
    try:
        from tests.test_human_timing import test_business_hours
        results.append(run_test("Business Hours Detection", test_business_hours))
    except Exception as e:
        print(f"✗ Failed to load business hours test: {e}")
        results.append(False)
    
    # Test 3: Human Timing - Activity Weights
    print_header("TEST 3: HUMAN TIMING - ACTIVITY WEIGHTS")
    try:
        from tests.test_human_timing import test_activity_weights
        results.append(run_test("Activity Weights", test_activity_weights))
    except Exception as e:
        print(f"✗ Failed to load activity weights test: {e}")
        results.append(False)
    
    # Test 4: Human Timing - Send Decisions
    print_header("TEST 4: HUMAN TIMING - SEND DECISIONS")
    try:
        from tests.test_human_timing import test_send_decisions
        results.append(run_test("Send Decisions", test_send_decisions))
    except Exception as e:
        print(f"✗ Failed to load send decisions test: {e}")
        results.append(False)
    
    # Test 5: Human Timing - Daily Schedule
    print_header("TEST 5: HUMAN TIMING - DAILY SCHEDULE")
    try:
        from tests.test_human_timing import test_daily_schedule
        results.append(run_test("Daily Schedule Generation", test_daily_schedule))
    except Exception as e:
        print(f"✗ Failed to load daily schedule test: {e}")
        results.append(False)
    
    # Test 6: Human Timing - Simulate Full Day
    print_header("TEST 6: HUMAN TIMING - FULL DAY SIMULATION")
    try:
        from tests.test_human_timing import test_multiple_send_decisions
        results.append(run_test("Full Day Simulation", test_multiple_send_decisions))
    except Exception as e:
        print(f"✗ Failed to load full day simulation test: {e}")
        results.append(False)
    
    # Test 7: Warmup Simulation - Quick (7 days)
    print_header("TEST 7: WARMUP SIMULATION - PHASE 1 (7 DAYS)")
    try:
        from tests.test_warmup_simulation import WarmupSimulator
        def run_quick_sim():
            sim = WarmupSimulator(warmup_target=50)
            sim.run_simulation(num_days=7, verbose=False)
        results.append(run_test("7-Day Warmup Simulation", run_quick_sim))
    except Exception as e:
        print(f"✗ Failed to load warmup simulation test: {e}")
        results.append(False)
    
    # Test 8: Warmup Simulation - Full (30 days)
    print_header("TEST 8: WARMUP SIMULATION - FULL CYCLE (30 DAYS)")
    try:
        from tests.test_warmup_simulation import WarmupSimulator
        def run_full_sim():
            sim = WarmupSimulator(warmup_target=50)
            sim.run_simulation(num_days=30, verbose=False)
        results.append(run_test("30-Day Warmup Simulation", run_full_sim))
    except Exception as e:
        print(f"✗ Failed to load full warmup simulation test: {e}")
        results.append(False)
    
    # Test 9: Integration - Complete Email Flow
    print_header("TEST 9: INTEGRATION - COMPLETE EMAIL FLOW")
    try:
        from tests.test_integration import test_complete_email_flow
        results.append(run_test("Complete Email Flow", test_complete_email_flow))
    except Exception as e:
        print(f"✗ Failed to load email flow integration test: {e}")
        results.append(False)
    
    # Test 10: Integration - Full Day
    print_header("TEST 10: INTEGRATION - FULL DAY")
    try:
        from tests.test_integration import test_full_day_simulation
        results.append(run_test("Full Day Integration", test_full_day_simulation))
    except Exception as e:
        print(f"✗ Failed to load full day integration test: {e}")
        results.append(False)
    
    # Test 11: Integration - Multi-Day
    print_header("TEST 11: INTEGRATION - MULTI-DAY (7 DAYS)")
    try:
        from tests.test_integration import test_multi_day_simulation
        results.append(run_test("Multi-Day Integration", test_multi_day_simulation))
    except Exception as e:
        print(f"✗ Failed to load multi-day integration test: {e}")
        results.append(False)
    
    # Final Summary
    print_header("TEST SUITE SUMMARY")
    
    passed = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")
    print(f"Success Rate: {passed/total*100:.1f}%")
    print()
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! 🎉")
        print()
        print("Your email warmup system is working perfectly:")
        print("  ✓ Content generation is varied and natural")
        print("  ✓ Human timing logic is working correctly")
        print("  ✓ Warmup progression follows expected phases")
        print("  ✓ All components integrate successfully")
        print()
        print("You're ready to run the warmup service!")
    else:
        print("⚠️  SOME TESTS FAILED")
        print()
        print("Please review the failed tests above and:")
        print("  1. Check your .env configuration")
        print("  2. Verify all dependencies are installed")
        print("  3. Review the specific error messages")
        print()
        print("Common issues:")
        print("  - Missing or invalid OPENAI_API_KEY (will fall back to templates)")
        print("  - Missing template files in app/templates/")
        print("  - Timezone configuration issues")
    
    print()
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
