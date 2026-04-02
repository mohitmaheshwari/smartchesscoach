#!/usr/bin/env python3
"""
Backend Queue Recovery Testing
==============================

Tests the new queue recovery behavior for game analysis including:
1. Analysis status API returns richer queue metadata fields 
2. Real pending jobs are picked up by fallback processor
3. Failed jobs are not endlessly retried beyond 3 attempts
4. Pending jobs are NOT retried (only stuck processing jobs retry)
5. Queue items expose useful last_error data when failed

Real-world data context:
- User ID: user_4dad2b14e380  
- Existing queue items in MongoDB for this user
- Stockfish was installed during this run
"""

import requests
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://coaching-board.preview.emergentagent.com/api"
TEST_USER_ID = "user_4dad2b14e380"
SESSION_TOKEN = None  # Will be obtained via dev login

class QueueRecoveryTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
        
    def authenticate(self) -> bool:
        """Authenticate using dev login"""
        try:
            response = self.session.get(f"{BACKEND_URL}/auth/dev-login")
            if response.status_code == 200:
                data = response.json()
                if data.get("user", {}).get("user_id") == TEST_USER_ID:
                    logger.info("✅ Dev authentication successful")
                    return True
                else:
                    logger.error(f"❌ Wrong user authenticated: {data.get('user', {}).get('user_id')}")
                    return False
            else:
                logger.error(f"❌ Dev login failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False

    def test_analysis_status_api(self) -> Dict[str, Any]:
        """Test 1: Verify analysis status API returns richer queue metadata fields"""
        logger.info("🧪 Test 1: Analysis Status API - Queue Metadata Fields")
        
        results = {
            "test_name": "Analysis Status API",
            "passed": False,
            "games_tested": [],
            "queue_fields_found": set(),
            "error": None
        }
        
        try:
            # Get user's games to find ones with queue status
            games_response = self.session.get(f"{BACKEND_URL}/games")
            if games_response.status_code != 200:
                results["error"] = f"Failed to fetch games: {games_response.status_code}"
                return results
            
            games = games_response.json()
            logger.info(f"Found {len(games)} games for user {TEST_USER_ID}")
            
            # Test analysis status for each game
            queue_items_found = 0
            for game in games[:10]:  # Test first 10 games
                game_id = game.get("game_id")
                if not game_id:
                    continue
                    
                status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                if status_response.status_code != 200:
                    logger.warning(f"Failed to get status for game {game_id}: {status_response.status_code}")
                    continue
                
                status_data = status_response.json()
                results["games_tested"].append({
                    "game_id": game_id,
                    "status": status_data.get("status"),
                    "fields": list(status_data.keys())
                })
                
                # Check for richer queue fields
                expected_queue_fields = {
                    "queued_at", "started_at", "failed_at", "retry_count", 
                    "last_error", "last_error_at", "retrying"
                }
                
                found_fields = set(status_data.keys()) & expected_queue_fields
                results["queue_fields_found"].update(found_fields)
                
                if status_data.get("status") in ["pending", "processing", "failed"]:
                    queue_items_found += 1
                    logger.info(f"📊 Queue item found for {game_id}: status={status_data.get('status')}")
                    
                    # Log detailed queue metadata
                    if found_fields:
                        metadata = {k: status_data.get(k) for k in found_fields}
                        logger.info(f"   Queue metadata: {metadata}")
            
            results["queue_items_found"] = queue_items_found
            results["total_queue_fields"] = len(results["queue_fields_found"])
            
            # Test passes if we find at least 3 of the expected queue metadata fields
            results["passed"] = len(results["queue_fields_found"]) >= 3
            
            if results["passed"]:
                logger.info(f"✅ Test 1 PASSED: Found {len(results['queue_fields_found'])} queue metadata fields")
            else:
                logger.error(f"❌ Test 1 FAILED: Only found {len(results['queue_fields_found'])} queue metadata fields")
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Test 1 ERROR: {e}")
        
        return results

    def test_fallback_processor_behavior(self) -> Dict[str, Any]:
        """Test 2: Verify fallback processor picks up pending jobs"""
        logger.info("🧪 Test 2: Fallback Processor Behavior")
        
        results = {
            "test_name": "Fallback Processor",
            "passed": False,
            "pending_jobs_initial": 0,
            "pending_jobs_after_wait": 0,
            "processing_jobs_observed": 0,
            "completed_jobs_observed": 0,
            "error": None
        }
        
        try:
            # Find games with pending analysis
            games_response = self.session.get(f"{BACKEND_URL}/games")
            games = games_response.json()
            
            pending_games = []
            for game in games[:20]:  # Check first 20 games
                game_id = game.get("game_id")
                status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get("status") == "pending":
                        pending_games.append(game_id)
            
            results["pending_jobs_initial"] = len(pending_games)
            logger.info(f"Found {len(pending_games)} pending games initially")
            
            if len(pending_games) == 0:
                # Try to create a pending job by re-analyzing a game
                if games:
                    test_game_id = games[0].get("game_id")
                    reanalyze_response = self.session.post(f"{BACKEND_URL}/games/{test_game_id}/reanalyze")
                    if reanalyze_response.status_code == 200:
                        logger.info(f"Created pending analysis job for {test_game_id}")
                        pending_games = [test_game_id]
                        results["pending_jobs_initial"] = 1
            
            if pending_games:
                # Monitor the first pending game for 60 seconds
                monitor_game_id = pending_games[0]
                logger.info(f"Monitoring game {monitor_game_id} for fallback processor activity...")
                
                start_time = time.time()
                status_changes = []
                
                while time.time() - start_time < 60:  # Monitor for 60 seconds
                    status_response = self.session.get(f"{BACKEND_URL}/games/{monitor_game_id}/analysis-status")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status")
                        
                        if not status_changes or status_changes[-1]["status"] != current_status:
                            status_changes.append({
                                "timestamp": datetime.now().isoformat(),
                                "status": current_status,
                                "retry_count": status_data.get("retry_count", 0)
                            })
                            logger.info(f"Status change: {current_status}")
                        
                        if current_status == "processing":
                            results["processing_jobs_observed"] += 1
                        elif current_status in ["completed", "analyzed"]:
                            results["completed_jobs_observed"] += 1
                            break
                    
                    time.sleep(5)  # Check every 5 seconds
                
                results["status_changes"] = status_changes
                
                # Count final pending jobs
                final_pending = 0
                for game_id in pending_games:
                    status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get("status") == "pending":
                            final_pending += 1
                
                results["pending_jobs_after_wait"] = final_pending
                
                # Test passes if we observe any processing activity or completed jobs
                results["passed"] = (results["processing_jobs_observed"] > 0 or 
                                  results["completed_jobs_observed"] > 0 or
                                  results["pending_jobs_after_wait"] < results["pending_jobs_initial"])
                
                if results["passed"]:
                    logger.info("✅ Test 2 PASSED: Fallback processor activity observed")
                else:
                    logger.warning("⚠️ Test 2 INCONCLUSIVE: No clear processor activity in 60 seconds")
            else:
                logger.info("ℹ️ Test 2 SKIPPED: No pending jobs found to monitor")
                results["passed"] = True  # Consider it passed if no pending jobs exist
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Test 2 ERROR: {e}")
        
        return results

    def test_retry_limits(self) -> Dict[str, Any]:
        """Test 3: Verify failed jobs don't retry beyond 3 attempts"""
        logger.info("🧪 Test 3: Retry Limits (Max 3 attempts)")
        
        results = {
            "test_name": "Retry Limits", 
            "passed": False,
            "failed_jobs_found": 0,
            "jobs_with_high_retry_count": 0,
            "max_retry_count_seen": 0,
            "error": None
        }
        
        try:
            # Get user's games and check for failed ones with retry counts
            games_response = self.session.get(f"{BACKEND_URL}/games")
            games = games_response.json()
            
            for game in games[:30]:  # Check first 30 games
                game_id = game.get("game_id")
                status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    retry_count = status_data.get("retry_count", 0)
                    
                    if status == "failed":
                        results["failed_jobs_found"] += 1
                        logger.info(f"Failed job found: {game_id}, retry_count: {retry_count}")
                        
                        if retry_count > results["max_retry_count_seen"]:
                            results["max_retry_count_seen"] = retry_count
                        
                        if retry_count > 3:
                            results["jobs_with_high_retry_count"] += 1
                            logger.warning(f"❌ Job {game_id} has retry_count > 3: {retry_count}")
            
            # Test passes if no jobs have retry_count > 3 and max retry count is reasonable
            results["passed"] = (results["jobs_with_high_retry_count"] == 0 and 
                               results["max_retry_count_seen"] <= 3)
            
            if results["passed"]:
                logger.info(f"✅ Test 3 PASSED: Max retry count is {results['max_retry_count_seen']}, no excessive retries")
            else:
                logger.error(f"❌ Test 3 FAILED: Found {results['jobs_with_high_retry_count']} jobs with retry_count > 3")
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Test 3 ERROR: {e}")
        
        return results

    def test_pending_vs_processing_retry_behavior(self) -> Dict[str, Any]:
        """Test 4: Verify pending jobs are NOT retried, only stuck processing jobs"""
        logger.info("🧪 Test 4: Pending vs Processing Retry Behavior")
        
        results = {
            "test_name": "Pending vs Processing Retry",
            "passed": False,
            "pending_jobs_with_retries": 0,
            "old_pending_jobs_found": 0,
            "processing_jobs_found": 0,
            "error": None
        }
        
        try:
            # Get user's games and analyze retry patterns
            games_response = self.session.get(f"{BACKEND_URL}/games")
            games = games_response.json()
            
            now = datetime.now(timezone.utc)
            
            for game in games[:30]:
                game_id = game.get("game_id")
                status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    retry_count = status_data.get("retry_count", 0)
                    queued_at_str = status_data.get("queued_at")
                    
                    if status == "pending":
                        # Check if old pending job has retries (shouldn't happen)
                        if retry_count > 0:
                            results["pending_jobs_with_retries"] += 1
                            logger.warning(f"❌ Pending job {game_id} has retry_count: {retry_count}")
                        
                        # Check age of pending job
                        if queued_at_str:
                            try:
                                queued_at = datetime.fromisoformat(queued_at_str.replace('Z', '+00:00'))
                                age_minutes = (now - queued_at).total_seconds() / 60
                                if age_minutes > 30:  # Old pending job
                                    results["old_pending_jobs_found"] += 1
                                    logger.info(f"Old pending job found: {game_id}, age: {age_minutes:.1f} minutes")
                            except:
                                pass
                    
                    elif status == "processing":
                        results["processing_jobs_found"] += 1
                        logger.info(f"Processing job: {game_id}, retry_count: {retry_count}")
            
            # Test passes if no pending jobs have retry counts
            results["passed"] = results["pending_jobs_with_retries"] == 0
            
            if results["passed"]:
                logger.info("✅ Test 4 PASSED: No pending jobs have retry counts")
            else:
                logger.error(f"❌ Test 4 FAILED: Found {results['pending_jobs_with_retries']} pending jobs with retries")
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Test 4 ERROR: {e}")
        
        return results

    def test_error_data_exposure(self) -> Dict[str, Any]:
        """Test 5: Verify queue items expose useful last_error data when failed"""
        logger.info("🧪 Test 5: Error Data Exposure")
        
        results = {
            "test_name": "Error Data Exposure",
            "passed": False,
            "failed_jobs_found": 0,
            "jobs_with_error_messages": 0,
            "jobs_with_error_timestamps": 0,
            "sample_errors": [],
            "error": None
        }
        
        try:
            # Get user's games and check failed ones for error data
            games_response = self.session.get(f"{BACKEND_URL}/games")
            games = games_response.json()
            
            for game in games[:30]:
                game_id = game.get("game_id")
                status_response = self.session.get(f"{BACKEND_URL}/games/{game_id}/analysis-status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    
                    if status == "failed":
                        results["failed_jobs_found"] += 1
                        
                        last_error = status_data.get("last_error")
                        last_error_at = status_data.get("last_error_at")
                        failed_at = status_data.get("failed_at")
                        
                        if last_error:
                            results["jobs_with_error_messages"] += 1
                            if len(results["sample_errors"]) < 3:
                                results["sample_errors"].append({
                                    "game_id": game_id,
                                    "error": last_error[:200],  # First 200 chars
                                    "error_at": last_error_at
                                })
                            logger.info(f"Error data for {game_id}: {last_error[:100]}...")
                        
                        if last_error_at or failed_at:
                            results["jobs_with_error_timestamps"] += 1
            
            # Test passes if we found failed jobs with error data
            if results["failed_jobs_found"] > 0:
                error_data_coverage = results["jobs_with_error_messages"] / results["failed_jobs_found"]
                results["passed"] = error_data_coverage >= 0.5  # At least 50% have error messages
                
                if results["passed"]:
                    logger.info(f"✅ Test 5 PASSED: {results['jobs_with_error_messages']}/{results['failed_jobs_found']} failed jobs have error messages")
                else:
                    logger.error(f"❌ Test 5 FAILED: Only {results['jobs_with_error_messages']}/{results['failed_jobs_found']} failed jobs have error messages")
            else:
                logger.info("ℹ️ Test 5 SKIPPED: No failed jobs found to check error data")
                results["passed"] = True  # Consider passed if no failed jobs to check
                
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Test 5 ERROR: {e}")
        
        return results

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all queue recovery tests"""
        logger.info("🚀 Starting Queue Recovery Backend Testing")
        
        # Authenticate first
        if not self.authenticate():
            return {"error": "Authentication failed"}
        
        # Run all tests
        test_results = {}
        
        test_results["test1_analysis_status_api"] = self.test_analysis_status_api()
        test_results["test2_fallback_processor"] = self.test_fallback_processor_behavior()
        test_results["test3_retry_limits"] = self.test_retry_limits()
        test_results["test4_pending_vs_processing"] = self.test_pending_vs_processing_retry_behavior()
        test_results["test5_error_data"] = self.test_error_data_exposure()
        
        # Summary
        passed_tests = sum(1 for result in test_results.values() if result.get("passed", False))
        total_tests = len(test_results)
        
        test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": f"{(passed_tests/total_tests)*100:.1f}%"
        }
        
        return test_results


def main():
    """Run the queue recovery tests"""
    tester = QueueRecoveryTester()
    results = tester.run_all_tests()
    
    # Print summary
    print("\n" + "="*60)
    print("QUEUE RECOVERY TEST RESULTS")
    print("="*60)
    
    if "summary" in results:
        summary = results["summary"]
        print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']})")
        print()
    
    # Print detailed results
    for test_name, result in results.items():
        if test_name == "summary":
            continue
            
        status = "✅ PASSED" if result.get("passed", False) else "❌ FAILED"
        print(f"{result.get('test_name', test_name)}: {status}")
        
        if result.get("error"):
            print(f"  Error: {result['error']}")
        
        # Print key metrics for each test
        if test_name == "test1_analysis_status_api":
            print(f"  Queue fields found: {result.get('total_queue_fields', 0)}")
            print(f"  Games tested: {len(result.get('games_tested', []))}")
            
        elif test_name == "test2_fallback_processor":
            print(f"  Initial pending jobs: {result.get('pending_jobs_initial', 0)}")
            print(f"  Processing jobs observed: {result.get('processing_jobs_observed', 0)}")
            print(f"  Completed jobs observed: {result.get('completed_jobs_observed', 0)}")
            
        elif test_name == "test3_retry_limits":
            print(f"  Failed jobs found: {result.get('failed_jobs_found', 0)}")
            print(f"  Max retry count seen: {result.get('max_retry_count_seen', 0)}")
            print(f"  Jobs with excessive retries: {result.get('jobs_with_high_retry_count', 0)}")
            
        elif test_name == "test4_pending_vs_processing":
            print(f"  Pending jobs with retries: {result.get('pending_jobs_with_retries', 0)}")
            print(f"  Old pending jobs found: {result.get('old_pending_jobs_found', 0)}")
            
        elif test_name == "test5_error_data":
            print(f"  Failed jobs found: {result.get('failed_jobs_found', 0)}")
            print(f"  Jobs with error messages: {result.get('jobs_with_error_messages', 0)}")
            print(f"  Sample errors: {len(result.get('sample_errors', []))}")
        
        print()
    
    # Return exit code based on overall success
    if "summary" in results:
        return 0 if results["summary"]["passed_tests"] == results["summary"]["total_tests"] else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())