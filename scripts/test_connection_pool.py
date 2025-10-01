#!/usr/bin/env python3
"""Test script for database connection pooling"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.account import Account

def test_connection_pool():
    print(f"\n{'='*80}")
    print(f"{'DATABASE CONNECTION POOL TEST':^80}")
    print(f"{'='*80}\n")
    
    app = create_app()
    
    # Display connection pool configuration
    print("Connection Pool Configuration:")
    print(f"  Pool Size: {app.config['SQLALCHEMY_ENGINE_OPTIONS']['pool_size']}")
    print(f"  Max Overflow: {app.config['SQLALCHEMY_ENGINE_OPTIONS']['max_overflow']}")
    print(f"  Pool Timeout: {app.config['SQLALCHEMY_ENGINE_OPTIONS']['pool_timeout']}s")
    print(f"  Pool Recycle: {app.config['SQLALCHEMY_ENGINE_OPTIONS']['pool_recycle']}s")
    print(f"  Pool Pre-ping: {app.config['SQLALCHEMY_ENGINE_OPTIONS']['pool_pre_ping']}")
    print()
    
    def simulate_task(task_id):
        """Simulate a Celery task that uses database connections"""
        with app.app_context():
            session = None
            try:
                session = db.session
                start_time = time.time()
                
                # Simulate database operations
                accounts = Account.query.filter_by(is_active=True).all()
                account_count = len(accounts)
                
                # Simulate some processing time
                time.sleep(0.1)
                
                end_time = time.time()
                duration = end_time - start_time
                
                return {
                    'task_id': task_id,
                    'account_count': account_count,
                    'duration': duration,
                    'success': True
                }
                
            except Exception as e:
                return {
                    'task_id': task_id,
                    'error': str(e),
                    'success': False
                }
            finally:
                if session:
                    try:
                        session.close()
                    except Exception as e:
                        print(f"Warning: Error closing session for task {task_id}: {e}")
    
    # Test with multiple concurrent connections
    print("Testing concurrent database connections...")
    print(f"Simulating {30} concurrent tasks (like Celery workers)")
    print()
    
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=30) as executor:
        # Submit tasks
        futures = [executor.submit(simulate_task, i) for i in range(30)]
        
        # Collect results
        for future in as_completed(futures):
            try:
                result = future.result(timeout=10)
                results.append(result)
                
                if result['success']:
                    print(f"✅ Task {result['task_id']:2d}: {result['account_count']} accounts, {result['duration']:.3f}s")
                else:
                    print(f"❌ Task {result['task_id']:2d}: ERROR - {result['error']}")
                    
            except Exception as e:
                print(f"❌ Task failed with exception: {e}")
                results.append({'success': False, 'error': str(e)})
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Summary
    successful_tasks = sum(1 for r in results if r['success'])
    failed_tasks = len(results) - successful_tasks
    
    print(f"\n{'-'*80}")
    print(f"{'TEST RESULTS':^80}")
    print(f"{'-'*80}")
    print(f"Total Tasks: {len(results)}")
    print(f"Successful: {successful_tasks}")
    print(f"Failed: {failed_tasks}")
    print(f"Success Rate: {(successful_tasks/len(results)*100):.1f}%")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Average Task Duration: {sum(r.get('duration', 0) for r in results if r['success'])/max(successful_tasks, 1):.3f}s")
    
    if failed_tasks == 0:
        print(f"\n🎉 ALL TESTS PASSED! Connection pooling is working correctly.")
        print(f"The system can handle {successful_tasks} concurrent database operations.")
    else:
        print(f"\n⚠️  {failed_tasks} tasks failed. Check connection pool settings.")
        
        # Show first few errors
        errors = [r['error'] for r in results if not r['success']][:3]
        if errors:
            print("\nFirst few errors:")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
    
    print(f"\n{'='*80}\n")

def test_pool_exhaustion():
    """Test what happens when pool is exhausted"""
    print(f"{'POOL EXHAUSTION TEST':^80}")
    print(f"{'-'*80}")
    
    app = create_app()
    pool_size = app.config['SQLALCHEMY_ENGINE_OPTIONS']['pool_size']
    max_overflow = app.config['SQLALCHEMY_ENGINE_OPTIONS']['max_overflow']
    max_connections = pool_size + max_overflow
    
    print(f"Testing with {max_connections + 5} connections (should exceed pool limit)")
    print(f"Pool size: {pool_size}, Max overflow: {max_overflow}, Total: {max_connections}")
    print()
    
    def hold_connection(task_id, hold_time=2):
        """Hold a database connection for a specified time"""
        with app.app_context():
            session = None
            try:
                session = db.session
                start_time = time.time()
                
                # Hold the connection
                accounts = Account.query.filter_by(is_active=True).first()
                time.sleep(hold_time)
                
                end_time = time.time()
                return {
                    'task_id': task_id,
                    'duration': end_time - start_time,
                    'success': True
                }
                
            except Exception as e:
                return {
                    'task_id': task_id,
                    'error': str(e),
                    'success': False
                }
            finally:
                if session:
                    try:
                        session.close()
                    except Exception as e:
                        print(f"Warning: Error closing session for task {task_id}: {e}")
    
    # Test pool exhaustion
    with ThreadPoolExecutor(max_workers=max_connections + 5) as executor:
        futures = [executor.submit(hold_connection, i, 1) for i in range(max_connections + 5)]
        
        results = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=15)
                results.append(result)
                
                if result['success']:
                    print(f"✅ Task {result['task_id']:2d}: Completed in {result['duration']:.2f}s")
                else:
                    print(f"❌ Task {result['task_id']:2d}: {result['error']}")
                    
            except Exception as e:
                print(f"❌ Task timeout or error: {e}")
                results.append({'success': False, 'error': str(e)})
    
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    print(f"\nPool exhaustion test results:")
    print(f"  Successful: {successful}/{len(results)}")
    print(f"  Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print(f"  ✅ Pool limits are working (some connections were rejected/timed out)")
    else:
        print(f"  ⚠️  All connections succeeded (pool might be too large or not limiting)")

if __name__ == "__main__":
    try:
        test_connection_pool()
        print()
        test_pool_exhaustion()
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()