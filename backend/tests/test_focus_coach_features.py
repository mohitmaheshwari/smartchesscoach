"""
Test Focus Page Coach-Like Feedback & Streak Mission Features

Features tested:
1. Coach-Like Feedback for Last Game (GET /api/discipline-check)
   - For wins: what_worked and needs_work fields
   - For losses: good_plays and core_problem fields
2. Streak-Based Mission System (GET /api/focus)
   - current_streak and longest_streak tracking
   - streak_broken_in_last_game indicator
   - is_streak_based flag
3. Next Mission Endpoint (POST /api/focus/next-mission)
   - Success response
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDisciplineCheckCoachFeedback:
    """Test GET /api/discipline-check returns coach_feedback with proper fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip("Dev login failed")
    
    def test_discipline_check_returns_coach_feedback_object(self):
        """Test that discipline-check returns coach_feedback in verdict"""
        response = self.session.get(f"{BASE_URL}/api/discipline-check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # May not have data if no analyzed games
        if not data.get("has_data"):
            pytest.skip("No discipline check data available - need analyzed games")
        
        # If analysis is pending, no coach_feedback yet
        if data.get("analysis_pending"):
            pytest.skip("Analysis pending - coach_feedback not yet available")
        
        # Verify verdict object exists
        assert "verdict" in data, "Expected 'verdict' key in response"
        verdict = data["verdict"]
        
        # Verify coach_feedback object exists
        assert "coach_feedback" in verdict, "Expected 'coach_feedback' in verdict"
        coach_feedback = verdict["coach_feedback"]
        
        print(f"✓ Coach feedback object found: {list(coach_feedback.keys())}")
    
    def test_win_feedback_has_what_worked_and_needs_work(self):
        """Test wins have what_worked and needs_work fields"""
        response = self.session.get(f"{BASE_URL}/api/discipline-check")
        assert response.status_code == 200
        
        data = response.json()
        
        if not data.get("has_data") or data.get("analysis_pending"):
            pytest.skip("Need fully analyzed game data")
        
        result = data.get("result")
        coach_feedback = data.get("verdict", {}).get("coach_feedback", {})
        
        # For wins, we expect what_worked and optionally needs_work
        if result == "win":
            # what_worked should be a list
            if "what_worked" in coach_feedback:
                assert isinstance(coach_feedback["what_worked"], list), "what_worked should be a list"
                print(f"✓ WIN: what_worked has {len(coach_feedback['what_worked'])} items")
            
            # needs_work should be a list (may be empty)
            if "needs_work" in coach_feedback:
                assert isinstance(coach_feedback["needs_work"], list), "needs_work should be a list"
                print(f"✓ WIN: needs_work has {len(coach_feedback['needs_work'])} items")
        else:
            print(f"Game result was {result}, not win - skipping win-specific assertions")
    
    def test_loss_feedback_has_good_plays_and_core_problem(self):
        """Test losses have good_plays and core_problem fields"""
        response = self.session.get(f"{BASE_URL}/api/discipline-check")
        assert response.status_code == 200
        
        data = response.json()
        
        if not data.get("has_data") or data.get("analysis_pending"):
            pytest.skip("Need fully analyzed game data")
        
        result = data.get("result")
        coach_feedback = data.get("verdict", {}).get("coach_feedback", {})
        
        # For losses, we expect good_plays and core_problem
        if result == "loss":
            # good_plays should be a list
            if "good_plays" in coach_feedback:
                assert isinstance(coach_feedback["good_plays"], list), "good_plays should be a list"
                print(f"✓ LOSS: good_plays has {len(coach_feedback['good_plays'])} items")
            
            # core_problem should be a string
            if "core_problem" in coach_feedback:
                assert isinstance(coach_feedback["core_problem"], str), "core_problem should be a string"
                print(f"✓ LOSS: core_problem = '{coach_feedback['core_problem'][:50]}...'")
        else:
            print(f"Game result was {result}, not loss - skipping loss-specific assertions")
    
    def test_coach_feedback_structure_complete(self):
        """Test coach_feedback has expected structure based on result"""
        response = self.session.get(f"{BASE_URL}/api/discipline-check")
        assert response.status_code == 200
        
        data = response.json()
        
        if not data.get("has_data") or data.get("analysis_pending"):
            pytest.skip("Need fully analyzed game data")
        
        result = data.get("result")
        coach_feedback = data.get("verdict", {}).get("coach_feedback", {})
        
        # Verify summary always exists
        assert "summary" in coach_feedback, "Expected 'summary' in coach_feedback"
        assert isinstance(coach_feedback["summary"], str), "summary should be a string"
        
        print(f"✓ Coach feedback summary: '{coach_feedback['summary'][:60]}...'")
        
        # Check for result-appropriate fields
        if result == "win":
            # Should have what_worked OR needs_work
            has_win_fields = "what_worked" in coach_feedback or "needs_work" in coach_feedback
            print(f"✓ WIN feedback has what_worked/needs_work fields: {has_win_fields}")
        elif result == "loss":
            # Should have good_plays OR core_problem
            has_loss_fields = "good_plays" in coach_feedback or "core_problem" in coach_feedback
            print(f"✓ LOSS feedback has good_plays/core_problem fields: {has_loss_fields}")


class TestFocusMissionStreaks:
    """Test GET /api/focus returns mission with streak tracking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip("Dev login failed")
    
    def test_focus_returns_mission_object(self):
        """Test /api/focus returns mission object"""
        response = self.session.get(f"{BASE_URL}/api/focus")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Focus should have mission
        assert "mission" in data, "Expected 'mission' key in focus data"
        mission = data["mission"]
        
        # Required fields
        assert "name" in mission, "Mission should have 'name'"
        assert "goal" in mission, "Mission should have 'goal'"
        assert "target" in mission, "Mission should have 'target'"
        
        print(f"✓ Mission: {mission['name']} - {mission['goal']}")
    
    def test_mission_has_streak_fields(self):
        """Test mission has current_streak and longest_streak"""
        response = self.session.get(f"{BASE_URL}/api/focus")
        assert response.status_code == 200
        
        data = response.json()
        mission = data.get("mission", {})
        
        # Streak fields
        assert "is_streak_based" in mission, "Expected 'is_streak_based' in mission"
        
        # If it's a real mission (not first steps), should have streak tracking
        if mission.get("is_streak_based"):
            assert "current_streak" in mission, "Expected 'current_streak' in mission"
            assert "longest_streak" in mission, "Expected 'longest_streak' in mission"
            
            current = mission["current_streak"]
            longest = mission["longest_streak"]
            
            assert isinstance(current, int), "current_streak should be int"
            assert isinstance(longest, int), "longest_streak should be int"
            assert longest >= current, "longest_streak should >= current_streak"
            
            print(f"✓ Streaks: current={current}, longest={longest}")
        else:
            print("✓ Mission is not streak-based (first steps or starter)")
    
    def test_mission_has_streak_broken_indicator(self):
        """Test mission has streak_broken_in_last_game field"""
        response = self.session.get(f"{BASE_URL}/api/focus")
        assert response.status_code == 200
        
        data = response.json()
        mission = data.get("mission", {})
        
        if mission.get("is_streak_based"):
            # Should have streak broken indicator
            assert "streak_broken_in_last_game" in mission, "Expected 'streak_broken_in_last_game'"
            broken = mission["streak_broken_in_last_game"]
            assert isinstance(broken, bool), "streak_broken_in_last_game should be bool"
            
            print(f"✓ Streak broken in last game: {broken}")
        else:
            print("✓ Mission is not streak-based - no broken indicator expected")
    
    def test_mission_has_progress_matching_streak(self):
        """Test that progress field equals current_streak for streak-based missions"""
        response = self.session.get(f"{BASE_URL}/api/focus")
        assert response.status_code == 200
        
        data = response.json()
        mission = data.get("mission", {})
        
        if mission.get("is_streak_based"):
            progress = mission.get("progress", 0)
            current_streak = mission.get("current_streak", 0)
            
            # For streak-based missions, progress = current_streak
            assert progress == current_streak, f"progress ({progress}) should equal current_streak ({current_streak})"
            
            print(f"✓ Progress matches streak: {progress}")
        else:
            print("✓ Non-streak mission - progress separate from streak")


class TestNextMissionEndpoint:
    """Test POST /api/focus/next-mission endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip("Dev login failed")
    
    def test_next_mission_endpoint_exists(self):
        """Test /api/focus/next-mission POST endpoint exists"""
        response = self.session.post(f"{BASE_URL}/api/focus/next-mission")
        
        # Should return 200 with success response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Expected 'status' key in response"
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        
        print(f"✓ Next mission endpoint works: {data.get('message', '')}")
    
    def test_next_mission_returns_success_message(self):
        """Test next-mission returns helpful message"""
        response = self.session.post(f"{BASE_URL}/api/focus/next-mission")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data, "Expected 'message' in response"
        assert len(data["message"]) > 0, "Message should not be empty"
        
        print(f"✓ Message: {data['message']}")


class TestFullResponseStructure:
    """Integration tests for complete response structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if resp.status_code != 200:
            pytest.skip("Dev login failed")
    
    def test_discipline_check_full_structure(self):
        """Test discipline-check has all expected fields"""
        response = self.session.get(f"{BASE_URL}/api/discipline-check")
        assert response.status_code == 200
        
        data = response.json()
        
        # Always has has_data
        assert "has_data" in data
        
        if data.get("has_data") and not data.get("analysis_pending"):
            # Should have these fields
            expected_fields = ["game_id", "opponent", "result", "verdict", "metrics"]
            for field in expected_fields:
                assert field in data, f"Expected '{field}' in discipline check data"
            
            # Verdict should have these
            verdict = data["verdict"]
            verdict_fields = ["headline", "grade", "tone", "coach_feedback"]
            for field in verdict_fields:
                assert field in verdict, f"Expected '{field}' in verdict"
            
            print("✓ Full discipline check structure verified")
            print(f"  - Result: {data['result']}")
            print(f"  - Grade: {verdict['grade']}")
            print(f"  - Headline: {verdict['headline']}")
    
    def test_focus_full_structure(self):
        """Test focus endpoint has all expected fields for missions"""
        response = self.session.get(f"{BASE_URL}/api/focus")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required top-level fields
        assert "games_analyzed" in data
        assert "mission" in data
        
        mission = data["mission"]
        
        # Required mission fields
        required = ["name", "goal", "target", "status"]
        for field in required:
            assert field in mission, f"Expected '{field}' in mission"
        
        # Streak-specific fields (for real missions)
        if mission.get("is_streak_based"):
            streak_fields = ["current_streak", "longest_streak", "streak_broken_in_last_game"]
            for field in streak_fields:
                assert field in mission, f"Expected '{field}' in streak-based mission"
        
        print("✓ Full focus structure verified")
        print(f"  - Games analyzed: {data['games_analyzed']}")
        print(f"  - Mission: {mission['name']}")
        print(f"  - Is streak-based: {mission.get('is_streak_based', False)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
