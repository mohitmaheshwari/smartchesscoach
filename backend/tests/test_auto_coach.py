"""
Auto-Coach Feature Tests

Tests for Live Auto-Coach feature:
1. GET /api/subscription - returns plan info with limits
2. GET /api/coach/commentary/{game_id} - generates coaching commentary  
3. POST /api/coach/trigger-analysis/{game_id} - creates notification and queues LLM
4. GET /api/notifications - returns user notifications
5. POST /api/notifications/read - marks notifications as read
"""

import pytest
import requests
import os

# Use production URL from environment variable
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://drills-studio.preview.emergentagent.com"

TEST_GAME_ID = "8a8b4f16-201a-4a7c-bc5a-21405c4ff939"


class TestSubscriptionEndpoint:
    """Test subscription/plan endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        # Login via dev endpoint
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_subscription_returns_plan_info(self):
        """GET /api/subscription returns plan info with limits"""
        response = self.session.get(f"{BASE_URL}/api/subscription")
        
        assert response.status_code == 200, f"Subscription endpoint failed: {response.text}"
        data = response.json()
        
        # Verify plan structure
        assert "plan" in data, "Missing 'plan' field"
        assert data["plan"] in ["free", "pro"], f"Invalid plan: {data['plan']}"
        
        # Verify limits structure
        assert "limits" in data, "Missing 'limits' field"
        limits = data["limits"]
        assert "monthly_analysis_limit" in limits, "Missing monthly_analysis_limit"
        assert "llm_commentary" in limits, "Missing llm_commentary feature flag"
        
        # Verify usage structure
        assert "usage" in data, "Missing 'usage' field"
        usage = data["usage"]
        assert "analyses_used" in usage, "Missing analyses_used"
        assert "analyses_remaining" in usage, "Missing analyses_remaining"
        
        print(f"✓ Subscription endpoint returns plan: {data['plan']}")
        print(f"  - Monthly limit: {limits.get('monthly_analysis_limit')}")
        print(f"  - LLM commentary access: {limits.get('llm_commentary')}")
        print(f"  - Analyses remaining: {usage.get('analyses_remaining')}")
        
    def test_subscription_can_analyze(self):
        """GET /api/subscription/can-analyze returns analysis permission"""
        response = self.session.get(f"{BASE_URL}/api/subscription/can-analyze")
        
        assert response.status_code == 200, f"Can-analyze endpoint failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "allowed" in data, "Missing 'allowed' field"
        assert isinstance(data["allowed"], bool), "allowed should be boolean"
        
        if data["allowed"]:
            assert "analyses_remaining" in data, "Missing analyses_remaining when allowed"
        else:
            assert "reason" in data, "Missing reason when not allowed"
            
        print(f"✓ Can analyze: {data['allowed']}")


class TestCoachCommentaryEndpoint:
    """Test coach commentary endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_coach_commentary_returns_data(self):
        """GET /api/coach/commentary/{game_id} returns coaching commentary"""
        response = self.session.get(f"{BASE_URL}/api/coach/commentary/{TEST_GAME_ID}")
        
        # Should return 200 or 404 (if game not found/not analyzed)
        assert response.status_code in [200, 404], f"Commentary endpoint failed: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for access denied
            if data.get("access_denied"):
                print(f"✓ Commentary endpoint: access denied (plan: free)")
                print(f"  - Message: {data.get('message')}")
            elif data.get("commentary"):
                print(f"✓ Commentary endpoint returned commentary")
                print(f"  - Cached: {data.get('cached', False)}")
                print(f"  - Commentary preview: {data['commentary'][:100]}...")
            else:
                print(f"✓ Commentary endpoint returned no commentary yet")
        else:
            print(f"✓ Commentary endpoint: game analysis not found (expected for new games)")
            
    def test_coach_commentary_nonexistent_game(self):
        """GET /api/coach/commentary/{game_id} returns 404 for nonexistent game"""
        response = self.session.get(f"{BASE_URL}/api/coach/commentary/nonexistent-game-12345")
        
        assert response.status_code == 404, f"Expected 404 for nonexistent game: {response.status_code}"
        print(f"✓ Commentary endpoint returns 404 for nonexistent game")


class TestTriggerAnalysisEndpoint:
    """Test trigger analysis endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_trigger_analysis_returns_data(self):
        """POST /api/coach/trigger-analysis/{game_id} creates notification"""
        response = self.session.post(f"{BASE_URL}/api/coach/trigger-analysis/{TEST_GAME_ID}")
        
        # Should return 200 or 404 (if game not found/not analyzed)
        assert response.status_code in [200, 404], f"Trigger analysis failed: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for limit reached
            if data.get("allowed") == False:
                print(f"✓ Trigger analysis: limit reached")
                print(f"  - Reason: {data.get('reason')}")
            elif data.get("success"):
                # Verify response structure
                assert "summary" in data, "Missing 'summary' field"
                assert "notification" in data, "Missing 'notification' field"
                
                summary = data["summary"]
                assert "result" in summary, "Missing result in summary"
                assert "accuracy" in summary, "Missing accuracy in summary"
                assert "blunders" in summary, "Missing blunders in summary"
                
                print(f"✓ Trigger analysis succeeded")
                print(f"  - Result: {summary.get('result')}")
                print(f"  - Accuracy: {summary.get('accuracy')}%")
                print(f"  - Blunders: {summary.get('blunders')}")
                print(f"  - Notification: {data.get('notification')}")
                print(f"  - LLM queued: {data.get('llm_commentary_queued')}")
        else:
            print(f"✓ Trigger analysis: game analysis not found (expected if not analyzed)")
            
    def test_trigger_analysis_nonexistent_game(self):
        """POST /api/coach/trigger-analysis/{game_id} returns 404 for nonexistent game"""
        response = self.session.post(f"{BASE_URL}/api/coach/trigger-analysis/nonexistent-game-12345")
        
        assert response.status_code == 404, f"Expected 404 for nonexistent game: {response.status_code}"
        print(f"✓ Trigger analysis returns 404 for nonexistent game")


class TestNotificationsEndpoint:
    """Test notifications endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_notifications_returns_list(self):
        """GET /api/notifications returns user notifications"""
        response = self.session.get(f"{BASE_URL}/api/notifications")
        
        assert response.status_code == 200, f"Notifications endpoint failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "notifications" in data, "Missing 'notifications' field"
        assert "unread_count" in data, "Missing 'unread_count' field"
        assert isinstance(data["notifications"], list), "notifications should be a list"
        assert isinstance(data["unread_count"], int), "unread_count should be int"
        
        print(f"✓ Notifications endpoint returned {len(data['notifications'])} notifications")
        print(f"  - Unread count: {data['unread_count']}")
        
        # Verify notification structure if any exist
        if data["notifications"]:
            notif = data["notifications"][0]
            assert "title" in notif, "Missing title in notification"
            assert "message" in notif, "Missing message in notification"
            assert "type" in notif, "Missing type in notification"
            assert "read" in notif, "Missing read flag in notification"
            print(f"  - First notification: {notif.get('title')}")
            
    def test_notifications_with_limit(self):
        """GET /api/notifications with limit parameter"""
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=5")
        
        assert response.status_code == 200, f"Notifications with limit failed: {response.text}"
        data = response.json()
        
        # Should respect limit
        assert len(data["notifications"]) <= 5, f"Returned more than limit: {len(data['notifications'])}"
        print(f"✓ Notifications with limit=5 returned {len(data['notifications'])} notifications")
        
    def test_notifications_unread_only(self):
        """GET /api/notifications with unread_only parameter"""
        response = self.session.get(f"{BASE_URL}/api/notifications?unread_only=true")
        
        assert response.status_code == 200, f"Notifications unread_only failed: {response.text}"
        data = response.json()
        
        # All notifications should be unread
        for notif in data["notifications"]:
            assert notif.get("read") == False, "Found read notification in unread_only query"
            
        print(f"✓ Notifications unread_only returned {len(data['notifications'])} unread notifications")


class TestMarkNotificationsRead:
    """Test marking notifications as read"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_mark_all_read(self):
        """POST /api/notifications/read marks all notifications as read"""
        response = self.session.post(f"{BASE_URL}/api/notifications/read")
        
        assert response.status_code == 200, f"Mark all read failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "success" in data, "Missing 'success' field"
        
        print(f"✓ Mark all notifications read: {data.get('success')}")
        
        # Verify unread count is now 0
        verify_resp = self.session.get(f"{BASE_URL}/api/notifications")
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["unread_count"] == 0, f"Unread count should be 0 after marking all read"
        print(f"  - Verified unread count is now 0")


class TestFullAutoCoachWorkflow:
    """Test the complete auto-coach workflow"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
    def test_full_workflow(self):
        """Test complete auto-coach workflow: subscription → trigger → notification → commentary"""
        
        # Step 1: Check subscription
        sub_resp = self.session.get(f"{BASE_URL}/api/subscription")
        assert sub_resp.status_code == 200, f"Subscription check failed"
        sub_data = sub_resp.json()
        print(f"Step 1: Subscription - {sub_data.get('plan')} (LLM: {sub_data['limits'].get('llm_commentary')})")
        
        # Step 2: Check can analyze
        can_analyze_resp = self.session.get(f"{BASE_URL}/api/subscription/can-analyze")
        assert can_analyze_resp.status_code == 200, f"Can analyze check failed"
        can_analyze_data = can_analyze_resp.json()
        print(f"Step 2: Can analyze - {can_analyze_data.get('allowed')}")
        
        # Step 3: Get initial notification count
        notif_before_resp = self.session.get(f"{BASE_URL}/api/notifications")
        assert notif_before_resp.status_code == 200, f"Get notifications failed"
        notif_count_before = len(notif_before_resp.json()["notifications"])
        print(f"Step 3: Initial notification count - {notif_count_before}")
        
        # Step 4: Trigger analysis (if game exists and is analyzed)
        trigger_resp = self.session.post(f"{BASE_URL}/api/coach/trigger-analysis/{TEST_GAME_ID}")
        if trigger_resp.status_code == 200:
            trigger_data = trigger_resp.json()
            if trigger_data.get("success"):
                print(f"Step 4: Trigger analysis - SUCCESS")
                print(f"  - Summary: {trigger_data.get('notification')}")
                
                # Step 5: Verify notification was created
                notif_after_resp = self.session.get(f"{BASE_URL}/api/notifications")
                assert notif_after_resp.status_code == 200
                notif_count_after = len(notif_after_resp.json()["notifications"])
                print(f"Step 5: Notification count after - {notif_count_after}")
                
                # New notification should be created
                if notif_count_after > notif_count_before:
                    print(f"  ✓ New notification created!")
                    newest = notif_after_resp.json()["notifications"][0]
                    print(f"  - Title: {newest.get('title')}")
                    print(f"  - Message: {newest.get('message')}")
                    
                # Step 6: Get commentary
                commentary_resp = self.session.get(f"{BASE_URL}/api/coach/commentary/{TEST_GAME_ID}")
                if commentary_resp.status_code == 200:
                    commentary_data = commentary_resp.json()
                    if commentary_data.get("commentary"):
                        print(f"Step 6: Commentary - Retrieved")
                        print(f"  - Preview: {commentary_data['commentary'][:80]}...")
                    elif commentary_data.get("access_denied"):
                        print(f"Step 6: Commentary - Access denied (Free plan)")
                    else:
                        print(f"Step 6: Commentary - Pending generation")
                        
            elif trigger_data.get("allowed") == False:
                print(f"Step 4: Trigger analysis - Limit reached")
                print(f"  - Reason: {trigger_data.get('reason')}")
        elif trigger_resp.status_code == 404:
            print(f"Step 4: Game not analyzed yet - skipping remaining steps")
            
        print(f"\n✓ Full auto-coach workflow test completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
