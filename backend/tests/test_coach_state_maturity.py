"""
Test Coach State and Behavioral Maturity Services

Tests:
1. CoachState persistence and retrieval
2. GameCoachSummary generation
3. Behavioral maturity level calculation
4. Coach tone adaptation based on maturity
5. Analytics event logging
6. Deep session flow
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test archetypes (seeded users)
TEST_USERS = {
    "novice": {
        "user_id": "test_novice_nina",
        "expected_maturity": "Novice",
        "expected_tone": "ExplainMore"
    },
    "steady": {
        "user_id": "test_steady_sam",
        "expected_maturity": "Developing",
        "expected_tone": "Balanced"
    },
    "disciplined": {
        "user_id": "test_disciplined_dana",
        "expected_maturity": "Disciplined",
        "expected_tone": "ChallengeMore"
    }
}


class TestCoachStateAPI:
    """Test CoachState persistence and retrieval"""
    
    def test_get_coach_state_dev_user(self):
        """Test getting coach state for dev user"""
        res = requests.get(
            f"{BASE_URL}/api/coach/state",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get coach state: {res.text}"
        
        data = res.json()
        assert "user_id" in data, "Missing user_id in response"
        assert "active_theme" in data, "Missing active_theme"
        assert "behavioral_maturity_level" in data, "Missing behavioral_maturity_level"
        assert "coach_tone_mode" in data, "Missing coach_tone_mode"
        assert "micro_rules" in data, "Missing micro_rules"
        
        # Verify maturity level is valid
        valid_levels = ["Novice", "Developing", "Disciplined", "Advanced"]
        assert data["behavioral_maturity_level"] in valid_levels, f"Invalid maturity level: {data['behavioral_maturity_level']}"
        
        # Verify tone mode is valid
        valid_tones = ["ExplainMore", "Balanced", "ChallengeMore"]
        assert data["coach_tone_mode"] in valid_tones, f"Invalid tone mode: {data['coach_tone_mode']}"
    
    def test_coach_state_has_theme_and_rules(self):
        """Test that coach state contains theme and micro rules"""
        res = requests.get(
            f"{BASE_URL}/api/coach/state",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200
        
        data = res.json()
        
        # Check theme
        valid_themes = [
            "CalculationDepth", "ThreatVerification", "ConversionDiscipline",
            "PieceSafety", "TimeManagement", "OpeningRepertoire",
            "EndgameTechnique", "PositionalPatience"
        ]
        assert data["active_theme"] in valid_themes, f"Invalid theme: {data['active_theme']}"
        
        # Check micro rules exist and are list
        assert isinstance(data["micro_rules"], list), "micro_rules should be a list"
        assert len(data["micro_rules"]) >= 1, "Should have at least one micro rule"


class TestBehavioralMaturityAPI:
    """Test behavioral maturity calculation and tone adaptation"""
    
    def test_get_maturity_level(self):
        """Test getting behavioral maturity for dev user"""
        res = requests.get(
            f"{BASE_URL}/api/coach/maturity",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get maturity: {res.text}"
        
        data = res.json()
        assert "maturity_level" in data, "Missing maturity_level"
        assert "tone_config" in data, "Missing tone_config"
        assert "metrics" in data, "Missing metrics"
        assert "description" in data, "Missing description"
        
        # Verify tone_config structure
        tone = data["tone_config"]
        assert "emotion_intensity" in tone, "Missing emotion_intensity"
        assert "max_lines" in tone, "Missing max_lines"
        assert "use_questions" in tone, "Missing use_questions"
        assert "explanation_depth" in tone, "Missing explanation_depth"
        assert "challenge_level" in tone, "Missing challenge_level"
    
    def test_maturity_metrics_structure(self):
        """Test that maturity metrics have expected fields"""
        res = requests.get(
            f"{BASE_URL}/api/coach/maturity",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200
        
        data = res.json()
        metrics = data["metrics"]
        
        expected_fields = [
            "theme_improvement_delta",
            "repeated_issue_frequency",
            "cpr_stability",
            "deep_session_completion_rate",
            "drill_completion_rate",
            "games_analyzed",
            "correct_reflection_rate"
        ]
        
        for field in expected_fields:
            assert field in metrics, f"Missing metric field: {field}"
    
    def test_update_maturity(self):
        """Test updating behavioral maturity"""
        res = requests.post(
            f"{BASE_URL}/api/coach/maturity/update",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to update maturity: {res.text}"
        
        data = res.json()
        assert "maturity_level" in data, "Missing maturity_level in response"
        assert "tone_mode" in data, "Missing tone_mode in response"
        assert "transitioned" in data, "Missing transitioned flag"
    
    def test_adapt_message(self):
        """Test message adaptation based on maturity"""
        params = {
            "issue_type": "threat_scan_failure",
            "emotion": "You missed their threat.",
            "explanation": "Check forcing moves first."
        }
        
        res = requests.get(
            f"{BASE_URL}/api/coach/maturity/adapt-message",
            params=params,
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to adapt message: {res.text}"
        
        data = res.json()
        assert "maturity_level" in data, "Missing maturity_level"
        assert "adapted_message" in data, "Missing adapted_message"
        
        adapted = data["adapted_message"]
        assert "emotion" in adapted or "explanation" in adapted or "cta" in adapted, "Adapted message should have content"


class TestThemeStats:
    """Test theme stats endpoint"""
    
    def test_get_theme_stats(self):
        """Test getting theme stats"""
        res = requests.get(
            f"{BASE_URL}/api/coach/theme-stats",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get theme stats: {res.text}"
        
        data = res.json()
        # If user has a theme, validate structure
        if data.get("has_theme"):
            assert "theme_display" in data, "Missing theme_display"
            assert "micro_rules" in data, "Missing micro_rules"
            assert "games_on_theme" in data, "Missing games_on_theme"
            assert "days_on_theme" in data, "Missing days_on_theme"


class TestCoachAnalytics:
    """Test analytics event logging"""
    
    def test_get_analytics_summary(self):
        """Test getting analytics summary"""
        res = requests.get(
            f"{BASE_URL}/api/coach/analytics/summary",
            params={"days": 30},
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get analytics: {res.text}"
        
        data = res.json()
        assert "period_days" in data, "Missing period_days"
        assert "event_counts" in data, "Missing event_counts"
        assert "total_events" in data, "Missing total_events"
    
    def test_get_theme_switches(self):
        """Test getting theme switch history"""
        res = requests.get(
            f"{BASE_URL}/api/coach/analytics/theme-history",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get theme switches: {res.text}"
        
        data = res.json()
        # API returns object with 'history' key
        assert "history" in data or isinstance(data, list), "Response should have history"
    
    def test_get_maturity_progression(self):
        """Test getting maturity progression history"""
        res = requests.get(
            f"{BASE_URL}/api/coach/analytics/maturity-progression",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to get maturity progression: {res.text}"
        
        data = res.json()
        # API returns object with 'progression' key
        assert "progression" in data or isinstance(data, list), "Response should have progression"


class TestDeepSession:
    """Test deep coaching session flow"""
    
    def test_check_deep_session_trigger(self):
        """Test checking if deep session should be triggered"""
        res = requests.get(
            f"{BASE_URL}/api/coach/deep-session/check",
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to check trigger: {res.text}"
        
        data = res.json()
        assert "should_trigger" in data, "Missing should_trigger"
        # Can have reason or message
    
    def test_start_deep_session(self):
        """Test starting a deep session"""
        res = requests.post(
            f"{BASE_URL}/api/coach/deep-session/start",
            json={"trigger": "manual"},
            cookies={"dev_login": "true"}
        )
        assert res.status_code == 200, f"Failed to start session: {res.text}"
        
        data = res.json()
        assert "session_id" in data, "Missing session_id"
        assert "current_step" in data, "Missing current_step"
        assert "content" in data, "Missing content"
        
        # Verify initial step is 1
        assert data["current_step"] == 1, f"Expected step 1, got {data['current_step']}"
        
        return data["session_id"]
    
    def test_deep_session_complete_flow(self):
        """Test completing a full deep session flow"""
        # Start session
        start_res = requests.post(
            f"{BASE_URL}/api/coach/deep-session/start",
            json={"trigger": "manual"},
            cookies={"dev_login": "true"}
        )
        assert start_res.status_code == 200, f"Failed to start: {start_res.text}"
        session_id = start_res.json()["session_id"]
        
        # Advance to step 2
        advance_res = requests.post(
            f"{BASE_URL}/api/coach/deep-session/{session_id}/advance",
            cookies={"dev_login": "true"}
        )
        assert advance_res.status_code == 200, f"Failed to advance: {advance_res.text}"
        assert advance_res.json()["current_step"] == 2
        
        # Submit reflection at step 2
        reflect_res = requests.post(
            f"{BASE_URL}/api/coach/deep-session/{session_id}/reflection",
            json={"answer": "momentum"},
            cookies={"dev_login": "true"}
        )
        assert reflect_res.status_code == 200, f"Failed to submit reflection: {reflect_res.text}"
        assert reflect_res.json()["current_step"] == 3
        
        # Advance through remaining steps
        for expected_step in [4, 5, 6]:
            adv_res = requests.post(
                f"{BASE_URL}/api/coach/deep-session/{session_id}/advance",
                cookies={"dev_login": "true"}
            )
            assert adv_res.status_code == 200, f"Failed to advance to step {expected_step}: {adv_res.text}"
            assert adv_res.json()["current_step"] == expected_step
        
        # Complete session
        complete_res = requests.post(
            f"{BASE_URL}/api/coach/deep-session/{session_id}/complete",
            cookies={"dev_login": "true"}
        )
        assert complete_res.status_code == 200, f"Failed to complete: {complete_res.text}"
        
        data = complete_res.json()
        assert data.get("completed") == True, "Session should be marked completed"
    
    def test_improvement_check_after_session(self):
        """Test checking improvement after deep session"""
        # This endpoint may return 404 if no completed sessions exist
        res = requests.get(
            f"{BASE_URL}/api/coach/deep-session/improvement-check",
            cookies={"dev_login": "true"}
        )
        # Accept 200 or 404 (no sessions exist yet)
        assert res.status_code in [200, 404], f"Unexpected status: {res.status_code}, {res.text}"
        # If 200, response may or may not have improvement message


class TestGameCoachSummary:
    """Test game coach summary generation"""
    
    def test_get_latest_game_summary(self):
        """Test getting latest game coach summary"""
        res = requests.get(
            f"{BASE_URL}/api/coach/latest-summary",
            cookies={"dev_login": "true"}
        )
        # May return 404 if no summaries exist
        if res.status_code == 200:
            data = res.json()
            if data.get("has_summary"):
                assert "game_id" in data, "Missing game_id"
                assert "primary_issue" in data, "Missing primary_issue"
                assert "emotion_mirror_line" in data, "Missing emotion_mirror_line"
                assert "coach_explain_line" in data, "Missing coach_explain_line"


class TestSeededUserMaturity:
    """Test maturity levels for seeded test users"""
    
    def test_novice_nina_maturity(self):
        """Test that Novice Nina has correct maturity level"""
        # Check directly in DB since we can't easily switch users via API
        # This tests the seed data was created correctly
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        nina = db.coach_states.find_one({"user_id": "test_novice_nina"})
        assert nina is not None, "Novice Nina coach state not found"
        assert nina["behavioral_maturity_level"] == "Novice", f"Expected Novice, got {nina['behavioral_maturity_level']}"
        assert nina["coach_tone_mode"] == "ExplainMore", f"Expected ExplainMore, got {nina['coach_tone_mode']}"
    
    def test_steady_sam_maturity(self):
        """Test that Steady Sam has correct maturity level"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        sam = db.coach_states.find_one({"user_id": "test_steady_sam"})
        assert sam is not None, "Steady Sam coach state not found"
        assert sam["behavioral_maturity_level"] == "Developing", f"Expected Developing, got {sam['behavioral_maturity_level']}"
        assert sam["coach_tone_mode"] == "Balanced", f"Expected Balanced, got {sam['coach_tone_mode']}"
    
    def test_disciplined_dana_maturity(self):
        """Test that Disciplined Dana has correct maturity level"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        dana = db.coach_states.find_one({"user_id": "test_disciplined_dana"})
        assert dana is not None, "Disciplined Dana coach state not found"
        assert dana["behavioral_maturity_level"] == "Disciplined", f"Expected Disciplined, got {dana['behavioral_maturity_level']}"
        assert dana["coach_tone_mode"] == "ChallengeMore", f"Expected ChallengeMore, got {dana['coach_tone_mode']}"
    
    def test_seeded_games_exist(self):
        """Test that seeded games exist for test users"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        # Check Nina's games
        nina_games = db.games.count_documents({"user_id": "test_novice_nina"})
        assert nina_games >= 15, f"Expected at least 15 games for Nina, got {nina_games}"
        
        # Check Sam's games
        sam_games = db.games.count_documents({"user_id": "test_steady_sam"})
        assert sam_games >= 20, f"Expected at least 20 games for Sam, got {sam_games}"
        
        # Check Dana's games
        dana_games = db.games.count_documents({"user_id": "test_disciplined_dana"})
        assert dana_games >= 25, f"Expected at least 25 games for Dana, got {dana_games}"
    
    def test_seeded_coach_summaries_exist(self):
        """Test that game coach summaries exist for test users"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        for user_id in ["test_novice_nina", "test_steady_sam", "test_disciplined_dana"]:
            summaries = db.game_coach_summaries.count_documents({"user_id": user_id})
            assert summaries > 0, f"Expected game coach summaries for {user_id}, got {summaries}"


class TestAnalysisWorkerNotStuck:
    """Test that analysis worker doesn't get stuck"""
    
    def test_analysis_queue_not_stuck(self):
        """Test that no jobs are stuck in processing state for too long"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from datetime import datetime, timezone, timedelta
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        # Check for jobs stuck in processing for > 5 minutes
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        stuck_jobs = db.analysis_queue.count_documents({
            "status": "processing",
            "started_at": {"$lt": five_min_ago}
        })
        
        assert stuck_jobs == 0, f"Found {stuck_jobs} stuck jobs in analysis queue"
    
    def test_analysis_queue_pending_reasonable(self):
        """Test that pending queue isn't too large"""
        import sys
        sys.path.insert(0, '/app/backend')
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        client = MongoClient(os.environ.get('MONGO_URL'))
        db = client[os.environ.get('DB_NAME', 'test_database')]
        
        pending_count = db.analysis_queue.count_documents({"status": "pending"})
        processing_count = db.analysis_queue.count_documents({"status": "processing"})
        
        # Not a strict test - just logging
        print(f"Analysis queue: {pending_count} pending, {processing_count} processing")
        
        # Fail if queue is unreasonably large (>100 pending)
        assert pending_count < 100, f"Too many pending jobs: {pending_count}"
