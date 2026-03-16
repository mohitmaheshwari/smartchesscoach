"""
Test Pattern Context API - Specific contextual insights

Tests the new Pattern Context feature that provides SPECIFIC insights:
- Rating context (vs higher/lower rated opponents)
- Opening context (which openings trigger mistakes)
- Time control context (blitz vs rapid patterns)
- Player history
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://coaching-moments.preview.emergentagent.com').rstrip('/')


class TestLabPatternContextAPI:
    """Tests for /api/lab/{game_id} pattern_context response"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        
    def get_analyzed_game_id(self):
        """Get a game_id that has been analyzed"""
        # Get dashboard stats to find games
        stats_resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        if stats_resp.status_code != 200:
            return None
        
        games = stats_resp.json().get("recent_games", [])
        
        # Try to find a game that's analyzed
        for game in games:
            game_id = game.get("game_id")
            if game_id:
                # Check if it has analysis
                analysis_resp = self.session.get(f"{BASE_URL}/api/analysis/{game_id}")
                if analysis_resp.status_code == 200:
                    return game_id
        
        return None
    
    def test_lab_endpoint_returns_pattern_context(self):
        """Test that /api/lab/{game_id} returns pattern_context field"""
        game_id = self.get_analyzed_game_id()
        if not game_id:
            pytest.skip("No analyzed game found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200, f"Lab API failed: {resp.text}"
        
        data = resp.json()
        
        # Verify pattern_context exists
        assert "pattern_context" in data, "Missing pattern_context in lab response"
        
        pattern_context = data["pattern_context"]
        assert pattern_context is not None, "pattern_context should not be None"
        
    def test_pattern_context_has_summary_section(self):
        """Test that pattern_context has summary with coach_summary and patterns"""
        game_id = self.get_analyzed_game_id()
        if not game_id:
            pytest.skip("No analyzed game found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200
        
        pattern_context = resp.json().get("pattern_context", {})
        
        # Verify summary structure
        assert "summary" in pattern_context, "Missing summary in pattern_context"
        
        summary = pattern_context["summary"]
        
        # Summary should have coach_summary
        assert "coach_summary" in summary, "Missing coach_summary in pattern_context.summary"
        
        # Summary should have recurring_patterns list
        assert "recurring_patterns" in summary, "Missing recurring_patterns in pattern_context.summary"
        assert isinstance(summary["recurring_patterns"], list), "recurring_patterns should be a list"
        
    def test_pattern_context_has_global_insights(self):
        """Test that pattern_context has global_insights with time/opening/rating vulnerable"""
        game_id = self.get_analyzed_game_id()
        if not game_id:
            pytest.skip("No analyzed game found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200
        
        pattern_context = resp.json().get("pattern_context", {})
        
        # Verify global_insights structure
        assert "global_insights" in pattern_context, "Missing global_insights in pattern_context"
        
        global_insights = pattern_context["global_insights"]
        
        # These fields should exist (may be null if insufficient data)
        assert "rating_vulnerable" in global_insights, "Missing rating_vulnerable in global_insights"
        assert "time_vulnerable" in global_insights, "Missing time_vulnerable in global_insights"
        assert "opening_triggers" in global_insights, "Missing opening_triggers in global_insights"
        
        # opening_triggers should be a list
        assert isinstance(global_insights["opening_triggers"], list), "opening_triggers should be a list"
        
    def test_recurring_patterns_have_specific_insights(self):
        """Test that recurring patterns include specific_insights (rating/opening/time)"""
        game_id = self.get_analyzed_game_id()
        if not game_id:
            pytest.skip("No analyzed game found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200
        
        pattern_context = resp.json().get("pattern_context", {})
        recurring_patterns = pattern_context.get("summary", {}).get("recurring_patterns", [])
        
        # If we have recurring patterns, verify their structure
        for pattern in recurring_patterns:
            # Each pattern should have label
            assert "label" in pattern, "Missing label in recurring pattern"
            
            # Each pattern should have trend
            assert "trend" in pattern, "Missing trend in recurring pattern"
            
            # Each pattern should have specific_insights dict
            assert "specific_insights" in pattern, "Missing specific_insights in recurring pattern"
            assert isinstance(pattern["specific_insights"], dict), "specific_insights should be a dict"
            
            # Each pattern should have action recommendation
            assert "action" in pattern, "Missing action in recurring pattern"
            
        print(f"Verified {len(recurring_patterns)} recurring patterns have correct structure")
        
    def test_pattern_context_history_section(self):
        """Test that pattern_context has history section"""
        game_id = self.get_analyzed_game_id()
        if not game_id:
            pytest.skip("No analyzed game found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200
        
        pattern_context = resp.json().get("pattern_context", {})
        
        # Verify history structure
        assert "history" in pattern_context, "Missing history in pattern_context"
        
        history = pattern_context["history"]
        
        # History should have these fields
        assert "most_recurring" in history, "Missing most_recurring in history"
        assert "improving_patterns" in history, "Missing improving_patterns in history"
        assert "fixed_patterns" in history, "Missing fixed_patterns in history"
        
        # improving_patterns and fixed_patterns should be lists
        assert isinstance(history["improving_patterns"], list), "improving_patterns should be a list"
        assert isinstance(history["fixed_patterns"], list), "fixed_patterns should be a list"


class TestMistakeContextAPI:
    """Tests for /api/lab/{game_id}/mistake/{move_number}/context endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        
    def get_game_with_mistake(self):
        """Get a game_id and move_number with a mistake"""
        # Get dashboard stats to find games
        stats_resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        if stats_resp.status_code != 200:
            return None, None
        
        games = stats_resp.json().get("recent_games", [])
        
        # Try to find a game with mistakes
        for game in games:
            game_id = game.get("game_id")
            if game_id:
                analysis_resp = self.session.get(f"{BASE_URL}/api/analysis/{game_id}")
                if analysis_resp.status_code == 200:
                    analysis = analysis_resp.json()
                    evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
                    
                    # Find a mistake or blunder
                    for e in evals:
                        if e.get("evaluation") in ["blunder", "mistake"]:
                            return game_id, e.get("move_number")
        
        return None, None
    
    def test_mistake_context_endpoint_exists(self):
        """Test that /api/lab/{game_id}/mistake/{move_number}/context exists"""
        game_id, move_number = self.get_game_with_mistake()
        if not game_id or not move_number:
            pytest.skip("No game with mistakes found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}/mistake/{move_number}/context")
        assert resp.status_code == 200, f"Mistake context API failed: {resp.text}"
        
        data = resp.json()
        assert "mistake" in data or "context" in data, "Missing mistake or context in response"
        
    def test_mistake_context_returns_specific_insights(self):
        """Test that mistake context returns specific_insights"""
        game_id, move_number = self.get_game_with_mistake()
        if not game_id or not move_number:
            pytest.skip("No game with mistakes found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}/mistake/{move_number}/context")
        assert resp.status_code == 200
        
        data = resp.json()
        context = data.get("context", {})
        
        # If we have context, check for specific_insights structure
        if context and context.get("is_recurring"):
            assert "specific_insights" in context, "Missing specific_insights for recurring pattern"
            
            specific_insights = context["specific_insights"]
            
            # specific_insights is a dict with optional keys
            assert isinstance(specific_insights, dict), "specific_insights should be a dict"
            
            # Log what insights we have
            available_insights = [k for k in specific_insights.keys() if specific_insights[k]]
            print(f"Available insights: {available_insights}")
            
    def test_mistake_context_returns_action_recommendation(self):
        """Test that mistake context includes action_recommendation"""
        game_id, move_number = self.get_game_with_mistake()
        if not game_id or not move_number:
            pytest.skip("No game with mistakes found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}/mistake/{move_number}/context")
        assert resp.status_code == 200
        
        data = resp.json()
        context = data.get("context", {})
        
        # action_recommendation should exist (may be null for non-recurring)
        if context:
            assert "action_recommendation" in context, "Missing action_recommendation in context"
            
    def test_mistake_context_returns_recurrence_info(self):
        """Test that mistake context includes recurrence tracking info"""
        game_id, move_number = self.get_game_with_mistake()
        if not game_id or not move_number:
            pytest.skip("No game with mistakes found")
        
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}/mistake/{move_number}/context")
        assert resp.status_code == 200
        
        data = resp.json()
        context = data.get("context", {})
        
        if context:
            # Recurrence fields
            assert "is_recurring" in context, "Missing is_recurring"
            assert "recurrence_count" in context, "Missing recurrence_count"
            assert "trend" in context, "Missing trend"
            assert "other_games" in context, "Missing other_games"
            
            assert isinstance(context["is_recurring"], bool), "is_recurring should be bool"
            assert isinstance(context["recurrence_count"], int), "recurrence_count should be int"
            assert isinstance(context["other_games"], list), "other_games should be list"
            
    def test_nonexistent_mistake_returns_no_context(self):
        """Test that requesting a non-mistake move number returns no context"""
        game_id, _ = self.get_game_with_mistake()
        if not game_id:
            pytest.skip("No game found")
        
        # Use move number 999 which likely doesn't exist
        resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}/mistake/999/context")
        assert resp.status_code == 200
        
        data = resp.json()
        # Should return empty context or message
        assert data.get("context") is None or data.get("message") is not None


class TestPatternContextDataQuality:
    """Tests verifying the pattern context data is SPECIFIC, not vague"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        
    def test_coach_summary_is_not_generic(self):
        """Test that coach_summary contains specific details, not generic phrases"""
        # Get dashboard stats
        stats_resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        if stats_resp.status_code != 200:
            pytest.skip("Could not get dashboard stats")
        
        games = stats_resp.json().get("recent_games", [])
        
        for game in games[:5]:
            game_id = game.get("game_id")
            if not game_id:
                continue
                
            resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
            if resp.status_code != 200:
                continue
            
            coach_summary = resp.json().get("pattern_context", {}).get("summary", {}).get("coach_summary", "")
            
            if coach_summary:
                # Coach summary should NOT be just vague labels
                vague_phrases = ["positional", "tactical awareness", "calculation"]
                is_vague = all(phrase in coach_summary.lower() for phrase in vague_phrases) and len(coach_summary) < 50
                
                assert not is_vague, f"Coach summary is too vague: {coach_summary}"
                
                # Good coach summary should mention specific things
                print(f"Coach summary: {coach_summary[:100]}...")
                break  # One good test is enough
                
    def test_opening_triggers_are_specific_openings(self):
        """Test that opening_triggers contain specific opening names"""
        stats_resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        if stats_resp.status_code != 200:
            pytest.skip("Could not get dashboard stats")
        
        games = stats_resp.json().get("recent_games", [])
        
        for game in games[:5]:
            game_id = game.get("game_id")
            if not game_id:
                continue
                
            resp = self.session.get(f"{BASE_URL}/api/lab/{game_id}")
            if resp.status_code != 200:
                continue
            
            opening_triggers = resp.json().get("pattern_context", {}).get("global_insights", {}).get("opening_triggers", [])
            
            if opening_triggers:
                # Each opening trigger should be a specific opening name
                for opening in opening_triggers:
                    assert isinstance(opening, str), "Opening trigger should be string"
                    assert len(opening) > 2, f"Opening trigger too short: {opening}"
                    # Should not be just "positional" or generic labels
                    assert opening.lower() not in ["positional", "tactical", "general"], f"Opening trigger is too vague: {opening}"
                    
                print(f"Opening triggers: {opening_triggers}")
                break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
