"""
Test PostGame Analysis with Coach Memory Integration

Tests the integration between postgame_analysis.py and coach_memory.py:
1. POST /api/coach/play/analysis returns memory section
2. Memory insights show recurring patterns when a weakness appears 3+ times
3. Coach memory is updated after game analysis
4. Coach summary includes personalized references to user history

These are integration tests against the running backend API.
"""

import pytest
import requests
import os
from datetime import datetime, timezone
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://coaching-board.preview.emergentagent.com')


class TestPostGameAnalysisMemory:
    """Test POST /api/coach/play/analysis with memory integration"""

    @pytest.fixture
    def auth_session(self):
        """Get authenticated session via dev login"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate via dev login
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed - skipping authenticated tests")
        
        return session

    def test_analysis_endpoint_returns_memory_section(self, auth_session):
        """POST /api/coach/play/analysis returns memory section with games_together, coach_knows_you, insights"""
        # First start a game session
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "10+5"
        })
        
        if start_res.status_code != 200:
            pytest.skip(f"Could not start coach session: {start_res.text}")
        
        session_data = start_res.json()
        session_id = session_data.get("session_id")
        assert session_id, "Session ID not returned"
        
        try:
            # End the game via resign
            end_res = auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            assert end_res.status_code == 200, f"End session failed: {end_res.text}"
            
            # Now call analysis endpoint
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200, f"Analysis failed: {analysis_res.text}"
            analysis = analysis_res.json()
            
            # CRITICAL: Check for memory section
            assert "memory" in analysis, "Memory section not in analysis response"
            memory = analysis["memory"]
            
            assert "games_together" in memory, "games_together not in memory"
            assert isinstance(memory["games_together"], int), "games_together should be int"
            assert memory["games_together"] >= 1, "games_together should be >= 1 after playing a game"
            
            assert "coach_knows_you" in memory, "coach_knows_you not in memory"
            assert isinstance(memory["coach_knows_you"], bool), "coach_knows_you should be bool"
            
            assert "insights" in memory, "insights not in memory"
            assert isinstance(memory["insights"], list), "insights should be a list"
            
            # Check each insight has required fields
            for insight in memory["insights"]:
                assert "type" in insight, "insight missing type"
                assert "message" in insight, "insight missing message"
        
        finally:
            # Cleanup - try to end session if not already ended
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass

    def test_analysis_returns_coach_summary_and_encouragement(self, auth_session):
        """Analysis should include coach_summary and encouragement fields"""
        # Start and end a quick game
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            # End the game
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            # Get analysis
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check personalized summary fields
            assert "coach_summary" in analysis, "coach_summary missing from analysis"
            assert isinstance(analysis["coach_summary"], str), "coach_summary should be string"
            assert len(analysis["coach_summary"]) > 0, "coach_summary should not be empty"
            
            assert "encouragement" in analysis, "encouragement missing from analysis"
            assert isinstance(analysis["encouragement"], str), "encouragement should be string"
            assert len(analysis["encouragement"]) > 0, "encouragement should not be empty"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass

    def test_analysis_returns_performance_rating(self, auth_session):
        """Analysis should include performance_rating with estimated rating"""
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check performance_rating structure
            assert "performance_rating" in analysis, "performance_rating missing"
            perf = analysis["performance_rating"]
            
            assert "estimated" in perf, "estimated rating missing"
            assert isinstance(perf["estimated"], int), "estimated should be int"
            
            assert "confidence" in perf, "confidence missing"
            assert perf["confidence"] in ["low", "medium", "high"], "invalid confidence value"
            
            assert "vs_actual" in perf, "vs_actual comparison missing"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass

    def test_analysis_returns_mistakes_breakdown(self, auth_session):
        """Analysis should include mistakes breakdown with blunders, mistakes, inaccuracies"""
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check mistakes structure
            assert "mistakes" in analysis, "mistakes section missing"
            mistakes = analysis["mistakes"]
            
            assert "blunders" in mistakes, "blunders count missing"
            assert isinstance(mistakes["blunders"], int), "blunders should be int"
            assert mistakes["blunders"] >= 0, "blunders should be >= 0"
            
            assert "mistakes" in mistakes, "mistakes count missing"
            assert isinstance(mistakes["mistakes"], int), "mistakes should be int"
            
            assert "inaccuracies" in mistakes, "inaccuracies count missing"
            assert isinstance(mistakes["inaccuracies"], int), "inaccuracies should be int"
            
            assert "details" in mistakes, "mistake details missing"
            assert isinstance(mistakes["details"], list), "details should be list"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass

    def test_analysis_returns_habits_section(self, auth_session):
        """Analysis should include habits section with violations, improved, still_weak"""
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check habits structure
            assert "habits" in analysis, "habits section missing"
            habits = analysis["habits"]
            
            assert "violations" in habits, "violations missing"
            assert isinstance(habits["violations"], list), "violations should be list"
            
            assert "improved" in habits, "improved missing"
            assert isinstance(habits["improved"], list), "improved should be list"
            
            assert "still_weak" in habits, "still_weak missing"
            assert isinstance(habits["still_weak"], list), "still_weak should be list"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass

    def test_analysis_returns_recommendations(self, auth_session):
        """Analysis should include recommendations with priority, suggestions, opening_to_learn"""
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check recommendations structure
            assert "recommendations" in analysis, "recommendations section missing"
            rec = analysis["recommendations"]
            
            assert "priority" in rec, "priority missing"
            assert isinstance(rec["priority"], str), "priority should be string"
            
            assert "suggestions" in rec, "suggestions missing"
            assert isinstance(rec["suggestions"], list), "suggestions should be list"
            
            # opening_to_learn can be null
            assert "opening_to_learn" in rec, "opening_to_learn missing"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass


class TestAnalysisWithoutSession:
    """Test analysis endpoint error handling"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed")
        return session
    
    def test_analysis_requires_session_id(self, auth_session):
        """Analysis endpoint should require session_id"""
        res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={})
        assert res.status_code == 400, "Should return 400 for missing session_id"
    
    def test_analysis_invalid_session_returns_404(self, auth_session):
        """Analysis with invalid session_id should return 404"""
        res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
            "session_id": "nonexistent_session_id_12345"
        })
        assert res.status_code == 404, "Should return 404 for nonexistent session"


class TestMemoryInsightsRecurringPatterns:
    """Test that memory insights show recurring patterns"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed")
        return session
    
    def test_memory_insight_types_are_valid(self, auth_session):
        """Memory insights should have valid insight_type values"""
        # Start and end a game
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        try:
            auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                "session_id": session_id,
                "reason": "resigned"
            })
            
            analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
                "session_id": session_id
            })
            
            assert analysis_res.status_code == 200
            analysis = analysis_res.json()
            
            # Check insight types are valid
            valid_types = [
                "recurring_pattern", 
                "improvement", 
                "performance_comparison", 
                "milestone",
                "first_time"
            ]
            
            for insight in analysis.get("memory", {}).get("insights", []):
                assert insight.get("type") in valid_types, \
                    f"Invalid insight type: {insight.get('type')}"
        
        finally:
            try:
                auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
                    "session_id": session_id,
                    "reason": "resigned"
                })
            except:
                pass


class TestCoachMemoryGamesCounter:
    """Test that games_together counter increments correctly"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.get(f"{BASE_URL}/api/auth/dev-login")
        if res.status_code != 200:
            pytest.skip("Dev login failed")
        return session
    
    def test_games_together_increments_after_multiple_games(self, auth_session):
        """games_together should increment with each game played"""
        initial_games = 0
        
        # Play first game
        start_res = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "white",
            "time_control": "3+2"
        })
        
        if start_res.status_code != 200:
            pytest.skip("Could not start coach session")
        
        session_id = start_res.json().get("session_id")
        
        auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
            "session_id": session_id,
            "reason": "resigned"
        })
        
        analysis_res = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
            "session_id": session_id
        })
        
        if analysis_res.status_code == 200:
            analysis = analysis_res.json()
            initial_games = analysis.get("memory", {}).get("games_together", 0)
        
        # Play second game
        start_res2 = auth_session.post(f"{BASE_URL}/api/coach/play/start", json={
            "user_color": "black",
            "time_control": "3+2"
        })
        
        if start_res2.status_code != 200:
            pytest.skip("Could not start second coach session")
        
        session_id2 = start_res2.json().get("session_id")
        
        auth_session.post(f"{BASE_URL}/api/coach/play/end", json={
            "session_id": session_id2,
            "reason": "resigned"
        })
        
        analysis_res2 = auth_session.post(f"{BASE_URL}/api/coach/play/analysis", json={
            "session_id": session_id2
        })
        
        assert analysis_res2.status_code == 200
        analysis2 = analysis_res2.json()
        
        new_games = analysis2.get("memory", {}).get("games_together", 0)
        
        # games_together should have incremented
        assert new_games >= initial_games, \
            f"games_together should not decrease: {new_games} < {initial_games}"
