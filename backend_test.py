import requests
import sys
import json
from datetime import datetime

class ChessCoachAPITester:
    def __init__(self, base_url="https://rated-training-hub.preview.emergentagent.com"):
        self.base_url = base_url
        self.session_token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('http') else endpoint
        
        default_headers = {'Content-Type': 'application/json'}
        if self.session_token:
            default_headers['Authorization'] = f'Bearer {self.session_token}'
        
        if headers:
            default_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=30)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json() if response.text else {}
                    self.log_test(name, True)
                    return True, response_data
                except:
                    self.log_test(name, True, "No JSON response")
                    return True, {}
            else:
                try:
                    error_data = response.json() if response.text else {"error": "No response body"}
                    self.log_test(name, False, f"Expected {expected_status}, got {response.status_code}. Response: {error_data}")
                except:
                    self.log_test(name, False, f"Expected {expected_status}, got {response.status_code}. Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log_test(name, False, f"Request failed: {str(e)}")
            return False, {}

    def test_basic_endpoints(self):
        """Test basic API endpoints"""
        print("\n" + "="*50)
        print("TESTING BASIC ENDPOINTS")
        print("="*50)
        
        # Test root endpoint
        self.run_test("API Root", "GET", "", 200)
        
        # Test health endpoint
        self.run_test("Health Check", "GET", "health", 200)

    def create_test_session(self):
        """Create a test session for authenticated endpoints"""
        print("\n" + "="*50)
        print("CREATING TEST SESSION")
        print("="*50)
        
        # Create a test user session directly in the database simulation
        # Since we can't easily test OAuth flow, we'll create a mock session
        test_session_data = {
            "session_id": f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
        # Try to create session (this will likely fail without proper OAuth, but let's test the endpoint)
        success, response = self.run_test(
            "Create Session", 
            "POST", 
            "auth/session", 
            200,  # We expect this might fail, but let's see
            data=test_session_data
        )
        
        if success and 'user_id' in response:
            self.user_id = response.get('user_id')
            print(f"   Created test user: {self.user_id}")
            return True
        else:
            print("   ⚠️  Session creation failed - will test unauthenticated endpoints only")
            return False

    def test_unauthenticated_endpoints(self):
        """Test endpoints that should work without authentication"""
        print("\n" + "="*50)
        print("TESTING UNAUTHENTICATED ENDPOINTS")
        print("="*50)
        
        # Test auth/me without session (should fail)
        self.run_test("Get User (No Auth)", "GET", "auth/me", 401)

    def test_game_import_endpoints(self):
        """Test game import functionality"""
        print("\n" + "="*50)
        print("TESTING GAME IMPORT ENDPOINTS")
        print("="*50)
        
        if not self.session_token:
            print("⚠️  Skipping authenticated tests - no session token")
            return
        
        # Test Chess.com import with known username
        chess_com_data = {
            "platform": "chess.com",
            "username": "hikaru"
        }
        
        success, response = self.run_test(
            "Import Chess.com Games", 
            "POST", 
            "import-games", 
            200,
            data=chess_com_data
        )
        
        if success:
            print(f"   Imported: {response.get('imported', 0)} games")
        
        # Test Lichess import with known username
        lichess_data = {
            "platform": "lichess", 
            "username": "DrNykterstein"
        }
        
        success, response = self.run_test(
            "Import Lichess Games",
            "POST",
            "import-games", 
            200,
            data=lichess_data
        )
        
        if success:
            print(f"   Imported: {response.get('imported', 0)} games")

    def test_game_endpoints(self):
        """Test game-related endpoints"""
        print("\n" + "="*50)
        print("TESTING GAME ENDPOINTS")
        print("="*50)
        
        if not self.session_token:
            print("⚠️  Skipping authenticated tests - no session token")
            return
        
        # Get games list
        success, games_response = self.run_test("Get Games List", "GET", "games", 200)
        
        if success and games_response and len(games_response) > 0:
            # Test getting a specific game
            first_game = games_response[0]
            game_id = first_game.get('game_id')
            
            if game_id:
                self.run_test(
                    "Get Specific Game", 
                    "GET", 
                    f"games/{game_id}", 
                    200
                )
                
                # Test game analysis
                analysis_data = {"game_id": game_id}
                self.run_test(
                    "Analyze Game", 
                    "POST", 
                    "analyze-game", 
                    200,
                    data=analysis_data
                )
        else:
            print("   ⚠️  No games found - skipping game-specific tests")

    def test_dashboard_endpoints(self):
        """Test dashboard and stats endpoints"""
        print("\n" + "="*50)
        print("TESTING DASHBOARD ENDPOINTS")
        print("="*50)
        
        if not self.session_token:
            print("⚠️  Skipping authenticated tests - no session token")
            return
        
        # Test dashboard stats
        self.run_test("Dashboard Stats", "GET", "dashboard-stats", 200)
        
        # Test patterns/weaknesses
        self.run_test("Get Patterns", "GET", "patterns", 200)
        
        # Test training recommendations
        self.run_test("Training Recommendations", "GET", "training-recommendations", 200)

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n" + "="*50)
        print("TESTING AUTH ENDPOINTS")
        print("="*50)
        
        if self.session_token:
            # Test getting current user
            self.run_test("Get Current User", "GET", "auth/me", 200)
            
            # Test logout
            self.run_test("Logout", "POST", "auth/logout", 200)

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Chess Coach API Tests")
        print(f"Testing against: {self.base_url}")
        
        # Basic tests (no auth required)
        self.test_basic_endpoints()
        self.test_unauthenticated_endpoints()
        
        # Try to create test session
        session_created = self.create_test_session()
        
        if session_created:
            # Authenticated tests
            self.test_auth_endpoints()
            self.test_game_import_endpoints()
            self.test_game_endpoints()
            self.test_dashboard_endpoints()
        
        # Print final results
        self.print_summary()
        
        return self.tests_passed == self.tests_run

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%" if self.tests_run > 0 else "0%")
        
        # Show failed tests
        failed_tests = [t for t in self.test_results if not t['success']]
        if failed_tests:
            print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"   • {test['test']}: {test['details']}")
        
        print("\n" + "="*60)

def main():
    """Main test runner"""
    tester = ChessCoachAPITester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n💥 Test runner crashed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())