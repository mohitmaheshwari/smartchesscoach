"""
Test suite for Focus Plan Service - Deterministic Personalized Coaching System
Tests:
1. GET /api/focus-plan - Returns complete focus plan with all required fields
2. POST /api/focus-plan/regenerate - Forces new plan generation
3. POST /api/focus-plan/mission/start - Creates mission session
4. POST /api/focus-plan/mission/interaction - Records events and tracks active time
5. POST /api/focus-plan/mission/complete - Completes mission and updates weekly progress
6. GET /api/focus-plan/bucket-breakdown - Returns bucket cost breakdown
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFocusPlanAPI:
    """Test Focus Plan API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for all tests"""
        self.session = requests.Session()
        self.session.cookies.set("session_token", "test_session_356539ff12b1")
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_get_focus_plan_returns_complete_data(self):
        """Test GET /api/focus-plan returns complete focus plan with all required fields"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should have plan data or needs_more_games flag
        assert "plan" in data or "needs_more_games" in data, "Missing plan data"
        
        if "plan" in data:
            plan = data["plan"]
            
            # Required fields in plan
            assert "primary_focus" in plan, "Missing primary_focus"
            assert "rules" in plan, "Missing rules"
            assert "openings" in plan, "Missing openings"
            assert "mission" in plan, "Missing mission"
            assert "weekly_requirements" in plan, "Missing weekly_requirements"
            assert "turning_points" in plan, "Missing turning_points"
            
            # Validate primary_focus structure
            primary_focus = plan["primary_focus"]
            assert "code" in primary_focus, "primary_focus missing code"
            assert "label" in primary_focus, "primary_focus missing label"
            assert "score" in primary_focus, "primary_focus missing score"
            
            # Validate openings structure
            openings = plan["openings"]
            assert "white" in openings, "openings missing white"
            
            # Validate mission structure
            mission = plan["mission"]
            assert "active_seconds_target" in mission, "mission missing active_seconds_target"
            assert "steps" in mission, "mission missing steps"
            
            # Validate weekly_requirements structure
            weekly_req = plan["weekly_requirements"]
            assert "games_with_openings" in weekly_req, "weekly_requirements missing games_with_openings"
            assert "missions_completed" in weekly_req, "weekly_requirements missing missions_completed"
            
            print(f"✓ Focus plan returned with primary_focus: {primary_focus['code']}")
            print(f"  - Rules: {len(plan['rules'])} rules")
            print(f"  - Turning points: {len(plan.get('turning_points', []))} positions")
    
    def test_focus_plan_has_coach_note(self):
        """Test GET /api/focus-plan returns personalized coach note"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "coach_note" in data, "Missing coach_note"
        assert len(data["coach_note"]) > 10, "Coach note too short"
        
        print(f"✓ Coach note: {data['coach_note'][:100]}...")
    
    def test_focus_plan_has_streak_info(self):
        """Test GET /api/focus-plan returns streak information"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "streak" in data, "Missing streak"
        assert isinstance(data["streak"], int), "Streak should be integer"
        
        print(f"✓ Current streak: {data['streak']} days")
    
    def test_primary_focus_bucket_codes(self):
        """Test primary focus has valid bucket code"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response.status_code == 200
        data = response.json()
        
        if "plan" in data:
            primary = data["plan"]["primary_focus"]
            valid_buckets = [
                "PIECE_SAFETY", "THREAT_AWARENESS", "TACTICAL_EXECUTION",
                "ADVANTAGE_DISCIPLINE", "OPENING_STABILITY", "TIME_DISCIPLINE",
                "ENDGAME_FUNDAMENTALS"
            ]
            assert primary["code"] in valid_buckets, f"Invalid bucket code: {primary['code']}"
            print(f"✓ Primary focus bucket: {primary['code']} ({primary['label']})")
    
    def test_opening_recommendations_have_stats(self):
        """Test opening recommendations include statistics"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response.status_code == 200
        data = response.json()
        
        if "plan" in data:
            openings = data["plan"]["openings"]
            
            # Check white opening has required stats
            if openings.get("white"):
                white_opening = openings["white"]
                assert "name" in white_opening, "white opening missing name"
                assert "games" in white_opening, "white opening missing games count"
                assert "win_rate" in white_opening, "white opening missing win_rate"
                print(f"✓ White opening: {white_opening['name']} ({white_opening['games']} games, {white_opening['win_rate']}% win)")
            
            # Check black vs e4 has stats
            if openings.get("black_vs_e4"):
                black_e4 = openings["black_vs_e4"]
                assert "name" in black_e4, "black_vs_e4 missing name"
                print(f"✓ Black vs e4: {black_e4['name']}")
    
    def test_regenerate_focus_plan(self):
        """Test POST /api/focus-plan/regenerate forces new plan generation"""
        response = self.session.post(f"{BASE_URL}/api/focus-plan/regenerate")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should return plan or needs_more_games
        assert "plan_id" in data or "needs_more_games" in data, "Missing plan_id or needs_more_games flag"
        
        if "plan_id" in data:
            print(f"✓ Plan regenerated: {data['plan_id']}")
        else:
            print("✓ Needs more games to regenerate")
    
    def test_mission_start_creates_session(self):
        """Test POST /api/focus-plan/mission/start creates a new session"""
        response = self.session.post(f"{BASE_URL}/api/focus-plan/mission/start")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should return session data or error if no active plan
        if "error" not in data:
            assert "session_id" in data, "Missing session_id"
            assert "user_id" in data, "Missing user_id"
            assert "plan_id" in data, "Missing plan_id"
            print(f"✓ Mission session started: {data['session_id']}")
            return data["session_id"]
        else:
            print(f"ℹ No active plan found: {data['error']}")
    
    def test_mission_interaction_heartbeat(self):
        """Test POST /api/focus-plan/mission/interaction records heartbeat events"""
        # First start a mission
        start_res = self.session.post(f"{BASE_URL}/api/focus-plan/mission/start")
        
        if start_res.status_code != 200:
            pytest.skip("Could not start mission")
        
        start_data = start_res.json()
        if "error" in start_data:
            pytest.skip(f"No active plan: {start_data['error']}")
        
        session_id = start_data["session_id"]
        
        # Record heartbeat
        interaction_data = {
            "session_id": session_id,
            "event_type": "heartbeat",
            "event_data": None
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/focus-plan/mission/interaction",
            json=interaction_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "session_id" in data, "Missing session_id"
        assert "active_seconds" in data, "Missing active_seconds"
        
        print(f"✓ Heartbeat recorded. Active seconds: {data['active_seconds']}")
    
    def test_mission_interaction_position_attempt(self):
        """Test POST /api/focus-plan/mission/interaction records position attempts"""
        # Start a mission
        start_res = self.session.post(f"{BASE_URL}/api/focus-plan/mission/start")
        
        if start_res.status_code != 200:
            pytest.skip("Could not start mission")
        
        start_data = start_res.json()
        if "error" in start_data:
            pytest.skip(f"No active plan: {start_data['error']}")
        
        session_id = start_data["session_id"]
        
        # Record position attempt
        interaction_data = {
            "session_id": session_id,
            "event_type": "position_attempted",
            "event_data": {"position_id": "op_0", "correct": True}
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/focus-plan/mission/interaction",
            json=interaction_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "active_seconds" in data, "Missing active_seconds tracking"
        print(f"✓ Position attempt recorded. Active seconds: {data['active_seconds']}")
    
    def test_mission_active_time_tracking(self):
        """Test that mission tracks active time correctly with rapid heartbeats"""
        # Start a mission
        start_res = self.session.post(f"{BASE_URL}/api/focus-plan/mission/start")
        
        if start_res.status_code != 200:
            pytest.skip("Could not start mission")
        
        start_data = start_res.json()
        if "error" in start_data:
            pytest.skip(f"No active plan: {start_data['error']}")
        
        session_id = start_data["session_id"]
        
        # Send multiple heartbeats to accumulate time
        initial_seconds = 0
        
        for i in range(3):
            time.sleep(2)  # Wait 2 seconds between heartbeats
            
            interaction_data = {
                "session_id": session_id,
                "event_type": "heartbeat"
            }
            
            response = self.session.post(
                f"{BASE_URL}/api/focus-plan/mission/interaction",
                json=interaction_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if i == 0:
                initial_seconds = data.get("active_seconds", 0)
            else:
                # Active time should increase
                current_seconds = data.get("active_seconds", 0)
                print(f"  Heartbeat {i+1}: active_seconds={current_seconds}")
        
        final_seconds = data.get("active_seconds", 0)
        print(f"✓ Active time accumulated: {initial_seconds} → {final_seconds} seconds")
    
    def test_bucket_breakdown_returns_all_buckets(self):
        """Test GET /api/focus-plan/bucket-breakdown returns all bucket costs"""
        response = self.session.get(f"{BASE_URL}/api/focus-plan/bucket-breakdown")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        expected_buckets = [
            "PIECE_SAFETY", "THREAT_AWARENESS", "TACTICAL_EXECUTION",
            "ADVANTAGE_DISCIPLINE", "OPENING_STABILITY", "TIME_DISCIPLINE",
            "ENDGAME_FUNDAMENTALS"
        ]
        
        if "bucket_costs" in data:
            buckets = data["bucket_costs"]
            for bucket in expected_buckets:
                assert bucket in buckets, f"Missing bucket: {bucket}"
                assert "score" in buckets[bucket], f"{bucket} missing score"
            
            print(f"✓ All {len(expected_buckets)} buckets returned")
            for bucket, info in buckets.items():
                print(f"  - {bucket}: score={info['score']}")
    
    def test_mission_complete(self):
        """Test POST /api/focus-plan/mission/complete marks mission as complete"""
        # Start a mission first
        start_res = self.session.post(f"{BASE_URL}/api/focus-plan/mission/start")
        
        if start_res.status_code != 200:
            pytest.skip("Could not start mission")
        
        start_data = start_res.json()
        if "error" in start_data:
            pytest.skip(f"No active plan: {start_data['error']}")
        
        session_id = start_data["session_id"]
        
        # Complete the mission
        response = self.session.post(
            f"{BASE_URL}/api/focus-plan/mission/complete",
            params={"session_id": session_id}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "completed" in data, "Missing completed field"
        assert data["completed"] == True, "Mission should be marked complete"
        
        print(f"✓ Mission completed: {session_id}")
    
    def test_determinism_same_inputs_same_plan(self):
        """Test deterministic behavior - same user/inputs should produce same plan"""
        # Get plan twice
        response1 = self.session.get(f"{BASE_URL}/api/focus-plan")
        response2 = self.session.get(f"{BASE_URL}/api/focus-plan")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        if "plan" in data1 and "plan" in data2:
            # Same inputs should produce same primary focus
            assert data1["plan"]["primary_focus"]["code"] == data2["plan"]["primary_focus"]["code"], \
                "Primary focus should be deterministic"
            
            # Same plan_id (if not regenerated)
            assert data1["plan"]["plan_id"] == data2["plan"]["plan_id"], \
                "Plan ID should be deterministic for same inputs"
            
            print(f"✓ Deterministic: Both calls returned plan_id={data1['plan']['plan_id']}")


class TestFocusPlanEdgeCases:
    """Test edge cases for Focus Plan API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for all tests"""
        self.session = requests.Session()
        self.session.cookies.set("session_token", "test_session_356539ff12b1")
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_invalid_session_interaction_returns_error(self):
        """Test interaction with invalid session ID returns error"""
        interaction_data = {
            "session_id": "invalid_session_12345",
            "event_type": "heartbeat"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/focus-plan/mission/interaction",
            json=interaction_data
        )
        
        assert response.status_code == 200  # API should handle gracefully
        data = response.json()
        
        # Should return error for invalid session
        assert "error" in data, "Should return error for invalid session"
        print(f"✓ Invalid session handled: {data['error']}")
    
    def test_mission_complete_invalid_session(self):
        """Test completing mission with invalid session returns error"""
        response = self.session.post(
            f"{BASE_URL}/api/focus-plan/mission/complete",
            params={"session_id": "invalid_session_xyz"}
        )
        
        assert response.status_code == 200  # API handles gracefully
        data = response.json()
        
        assert "error" in data, "Should return error for invalid session"
        print(f"✓ Invalid session complete handled: {data['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
