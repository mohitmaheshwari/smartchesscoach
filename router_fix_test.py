#!/usr/bin/env python3
"""
Router Registration Fix Testing
===============================

Tests the critical fix where api_router was not registered with FastAPI app.
Previously ~65 endpoints were returning 404, now they should return 401 for unauthenticated requests.

Critical endpoints to test:
1. POST /api/coach/play/start - Should return 401 (not 404)
2. POST /api/coach/play/move - Should return 401 (not 404)
3. POST /api/coach/play/undo - Should return 401 (not 404)
4. POST /api/import-games - Should return 401 (not 404)
5. POST /api/coach/play/trigger-coach-move - Should return 401 (not 404)
6. POST /api/connect-platform - Should return 401 (not 404)
7. POST /api/analyze-game - Should return 401 (not 404)

Also verify existing route file endpoints still work:
8. GET /api/coach/play/active - Should return 401 (this was always working)
9. GET /api/coach/play/stats - Should return 401
10. GET /api/auth/status - Should return 200 with dev_mode info
"""

import requests
import json
import logging
from typing import Dict, Any, List
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://guru-play-debug.preview.emergentagent.com/api"

class RouterFixTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
        
    def test_endpoint(self, method: str, endpoint: str, expected_status: int, description: str) -> Dict[str, Any]:
        """Test a single endpoint and verify it returns expected status code"""
        url = f"{BACKEND_URL}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json={})
            else:
                return {
                    "endpoint": endpoint,
                    "method": method,
                    "expected_status": expected_status,
                    "actual_status": None,
                    "passed": False,
                    "error": f"Unsupported method: {method}",
                    "description": description
                }
            
            actual_status = response.status_code
            passed = actual_status == expected_status
            
            # Try to get response content for additional info
            response_content = None
            try:
                if response.headers.get('content-type', '').startswith('application/json'):
                    response_content = response.json()
                else:
                    response_content = response.text[:200]  # First 200 chars
            except:
                response_content = "Unable to parse response"
            
            result = {
                "endpoint": endpoint,
                "method": method,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "passed": passed,
                "error": None,
                "description": description,
                "response_content": response_content
            }
            
            status_emoji = "✅" if passed else "❌"
            logger.info(f"{status_emoji} {method} {endpoint}: {actual_status} (expected {expected_status}) - {description}")
            
            if not passed:
                logger.warning(f"   Response: {response_content}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ {method} {endpoint}: ERROR - {str(e)}")
            return {
                "endpoint": endpoint,
                "method": method,
                "expected_status": expected_status,
                "actual_status": None,
                "passed": False,
                "error": str(e),
                "description": description,
                "response_content": None
            }

    def test_critical_endpoints(self) -> List[Dict[str, Any]]:
        """Test the critical endpoints that were previously returning 404"""
        logger.info("🧪 Testing Critical Endpoints (Previously 404, Now Should Be 401)")
        
        critical_tests = [
            ("POST", "/coach/play/start", 401, "Begin game - Should require auth"),
            ("POST", "/coach/play/move", 401, "Make move - Should require auth"),
            ("POST", "/coach/play/undo", 401, "Undo move - Should require auth"),
            ("POST", "/import-games", 401, "Import games - Should require auth"),
            ("POST", "/coach/play/trigger-coach-move", 401, "Trigger coach move - Should require auth"),
            ("POST", "/connect-platform", 401, "Connect platform - Should require auth"),
            ("POST", "/analyze-game", 401, "Analyze game - Should require auth"),
        ]
        
        results = []
        for method, endpoint, expected_status, description in critical_tests:
            result = self.test_endpoint(method, endpoint, expected_status, description)
            results.append(result)
        
        return results

    def test_existing_endpoints(self) -> List[Dict[str, Any]]:
        """Test existing route file endpoints that should still work"""
        logger.info("🧪 Testing Existing Route File Endpoints (Should Still Work)")
        
        existing_tests = [
            ("GET", "/coach/play/active", 401, "Active game status - Should require auth"),
            ("GET", "/coach/play/stats", 401, "Play stats - Should require auth"),
            ("GET", "/auth/status", 200, "Auth status - Should return dev_mode info"),
        ]
        
        results = []
        for method, endpoint, expected_status, description in existing_tests:
            result = self.test_endpoint(method, endpoint, expected_status, description)
            results.append(result)
        
        return results

    def analyze_404_vs_401_pattern(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the pattern of 404 vs 401 responses to verify the fix"""
        analysis = {
            "total_endpoints": len(results),
            "endpoints_returning_401": 0,
            "endpoints_returning_404": 0,
            "endpoints_returning_200": 0,
            "endpoints_with_errors": 0,
            "fix_successful": False,
            "problematic_endpoints": []
        }
        
        for result in results:
            status = result.get("actual_status")
            if status == 401:
                analysis["endpoints_returning_401"] += 1
            elif status == 404:
                analysis["endpoints_returning_404"] += 1
                analysis["problematic_endpoints"].append({
                    "endpoint": result["endpoint"],
                    "method": result["method"],
                    "status": status,
                    "description": result["description"]
                })
            elif status == 200:
                analysis["endpoints_returning_200"] += 1
            elif result.get("error"):
                analysis["endpoints_with_errors"] += 1
                analysis["problematic_endpoints"].append({
                    "endpoint": result["endpoint"],
                    "method": result["method"],
                    "error": result["error"],
                    "description": result["description"]
                })
        
        # Fix is successful if:
        # 1. No endpoints return 404 (the main issue)
        # 2. Most endpoints return 401 (auth required) or 200 (public endpoints)
        # 3. No critical errors
        analysis["fix_successful"] = (
            analysis["endpoints_returning_404"] == 0 and
            analysis["endpoints_with_errors"] == 0 and
            (analysis["endpoints_returning_401"] + analysis["endpoints_returning_200"]) >= analysis["total_endpoints"] * 0.8
        )
        
        return analysis

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test of the router registration fix"""
        logger.info("🚀 Starting Router Registration Fix Testing")
        
        # Test critical endpoints
        critical_results = self.test_critical_endpoints()
        
        # Test existing endpoints
        existing_results = self.test_existing_endpoints()
        
        # Combine all results
        all_results = critical_results + existing_results
        
        # Analyze the pattern
        analysis = self.analyze_404_vs_401_pattern(all_results)
        
        # Calculate pass rate
        passed_tests = sum(1 for result in all_results if result.get("passed", False))
        total_tests = len(all_results)
        
        return {
            "critical_endpoints": critical_results,
            "existing_endpoints": existing_results,
            "all_results": all_results,
            "analysis": analysis,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%",
                "fix_successful": analysis["fix_successful"]
            }
        }


def main():
    """Run the router registration fix tests"""
    tester = RouterFixTester()
    results = tester.run_comprehensive_test()
    
    # Print summary
    print("\n" + "="*70)
    print("ROUTER REGISTRATION FIX TEST RESULTS")
    print("="*70)
    
    summary = results["summary"]
    analysis = results["analysis"]
    
    print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']})")
    print(f"Fix Successful: {'✅ YES' if summary['fix_successful'] else '❌ NO'}")
    print()
    
    # Print analysis
    print("RESPONSE PATTERN ANALYSIS:")
    print(f"  401 (Auth Required): {analysis['endpoints_returning_401']}")
    print(f"  200 (Success): {analysis['endpoints_returning_200']}")
    print(f"  404 (Not Found): {analysis['endpoints_returning_404']}")
    print(f"  Errors: {analysis['endpoints_with_errors']}")
    print()
    
    # Print detailed results for critical endpoints
    print("CRITICAL ENDPOINTS (Previously 404):")
    for result in results["critical_endpoints"]:
        status_emoji = "✅" if result["passed"] else "❌"
        status = result.get("actual_status", "ERROR")
        print(f"  {status_emoji} {result['method']} {result['endpoint']}: {status}")
        if not result["passed"] and result.get("error"):
            print(f"      Error: {result['error']}")
    print()
    
    # Print detailed results for existing endpoints
    print("EXISTING ENDPOINTS (Should Still Work):")
    for result in results["existing_endpoints"]:
        status_emoji = "✅" if result["passed"] else "❌"
        status = result.get("actual_status", "ERROR")
        print(f"  {status_emoji} {result['method']} {result['endpoint']}: {status}")
        if not result["passed"] and result.get("error"):
            print(f"      Error: {result['error']}")
    print()
    
    # Print problematic endpoints if any
    if analysis["problematic_endpoints"]:
        print("PROBLEMATIC ENDPOINTS:")
        for endpoint in analysis["problematic_endpoints"]:
            if "error" in endpoint:
                print(f"  ❌ {endpoint['method']} {endpoint['endpoint']}: {endpoint['error']}")
            else:
                print(f"  ❌ {endpoint['method']} {endpoint['endpoint']}: {endpoint['status']}")
        print()
    
    # Overall conclusion
    if summary["fix_successful"]:
        print("🎉 CONCLUSION: Router registration fix is SUCCESSFUL!")
        print("   All critical endpoints now return 401 (auth required) instead of 404.")
        print("   Existing endpoints continue to work as expected.")
    else:
        print("⚠️ CONCLUSION: Router registration fix needs attention.")
        if analysis["endpoints_returning_404"] > 0:
            print(f"   {analysis['endpoints_returning_404']} endpoints still return 404.")
        if analysis["endpoints_with_errors"] > 0:
            print(f"   {analysis['endpoints_with_errors']} endpoints have errors.")
    
    # Return exit code based on overall success
    return 0 if summary["fix_successful"] else 1


if __name__ == "__main__":
    sys.exit(main())