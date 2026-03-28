"""
Thinking Score API Tests
========================

Tests for the Thinking Score feature that tracks how well players apply thinking habits.
All scores are calculated from REAL game analysis data.

Endpoints tested:
- GET /api/thinking-score - Overall thinking score and progress
- POST /api/thinking-score/calculate/{game_id} - Calculate score for a game
- GET /api/thinking-score/history - Score history across games
- GET /api/thinking-score/recommendations - Personalized recommendations
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestThinkingScoreAPI:
    """Test suite for Thinking Score API endpoints."""
    
    def test_get_thinking_score_returns_valid_structure(self):
        """GET /api/thinking-score returns expected response structure."""
        response = requests.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200
        
        data = response.json()
        
        # Must have has_data field
        assert "has_data" in data
        
        if data["has_data"]:
            # When data exists, verify all required fields
            assert "overall_score" in data
            assert "overall_trend" in data
            assert "habit_progress" in data
            assert "games_analyzed" in data
            assert "recommendations" in data
            assert "explanation" in data
            
            # Score should be 0-100
            assert 0 <= data["overall_score"] <= 100
            
            # Trend should be valid
            assert data["overall_trend"] in ["improving", "declining", "stable"]
            
            # games_analyzed should be positive
            assert data["games_analyzed"] >= 0
    
    def test_thinking_score_habit_progress_structure(self):
        """Verify habit_progress contains all 5 thinking habits."""
        response = requests.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data"):
            habit_progress = data.get("habit_progress", {})
            
            # All 5 habits should be present
            expected_habits = [
                "threat_awareness",
                "tactical_vision",
                "move_verification",
                "king_safety",
                "patience"
            ]
            
            for habit in expected_habits:
                assert habit in habit_progress, f"Missing habit: {habit}"
                
                habit_data = habit_progress[habit]
                # Each habit should have current_score
                assert "current_score" in habit_data
                assert 0 <= habit_data["current_score"] <= 100
                
                # Should have trend
                assert "trend" in habit_data
    
    def test_thinking_score_recommendations(self):
        """Verify recommendations are returned when data exists."""
        response = requests.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data"):
            recommendations = data.get("recommendations", [])
            
            # Should have recommendations (max 2)
            assert isinstance(recommendations, list)
            
            for rec in recommendations:
                # Each recommendation should have required fields
                assert "habit" in rec
                assert "habit_label" in rec
                assert "score" in rec
                assert "priority" in rec
                assert "recommendation" in rec
                assert "checklist_item" in rec
                assert "icon" in rec
                
                # Priority should be valid
                assert rec["priority"] in ["high", "medium", "low"]


class TestCalculateGameThinkingScore:
    """Test suite for calculating thinking scores for individual games."""
    
    def test_calculate_game_score_valid_game(self):
        """POST /api/thinking-score/calculate/{game_id} calculates score for valid game."""
        # Get a game to test with
        games_response = requests.get(f"{BASE_URL}/api/games?limit=1")
        if games_response.status_code != 200 or not games_response.json():
            pytest.skip("No games available for testing")
        
        game_id = games_response.json()[0].get("game_id")
        
        response = requests.post(f"{BASE_URL}/api/thinking-score/calculate/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return score structure
        assert "overall_score" in data
        assert "habit_scores" in data
        assert "total_moves" in data
        assert "game_id" in data
        assert "calculated_at" in data
        
        # Verify overall score is valid
        assert 0 <= data["overall_score"] <= 100
        
        # Verify habit_scores structure
        habit_scores = data["habit_scores"]
        for habit in ["threat_awareness", "tactical_vision", "move_verification", "king_safety", "patience"]:
            assert habit in habit_scores
            assert "score" in habit_scores[habit]
            assert "mistakes" in habit_scores[habit]
            assert "opportunities" in habit_scores[habit]
    
    def test_calculate_game_score_nonexistent_game(self):
        """POST /api/thinking-score/calculate/{game_id} handles nonexistent game."""
        response = requests.post(f"{BASE_URL}/api/thinking-score/calculate/nonexistent-game-id-12345")
        assert response.status_code == 200
        
        data = response.json()
        # Should return error or empty result
        assert "error" in data or data.get("overall_score") is None
    
    def test_calculate_score_uses_real_data(self):
        """Verify score calculation is based on real mistake analysis, not random."""
        # Get a game
        games_response = requests.get(f"{BASE_URL}/api/games?limit=1")
        if games_response.status_code != 200 or not games_response.json():
            pytest.skip("No games available for testing")
        
        game_id = games_response.json()[0].get("game_id")
        
        # Calculate score twice - should get same result
        response1 = requests.post(f"{BASE_URL}/api/thinking-score/calculate/{game_id}")
        response2 = requests.post(f"{BASE_URL}/api/thinking-score/calculate/{game_id}")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Scores should be identical (deterministic calculation)
        assert data1["overall_score"] == data2["overall_score"]
        assert data1["habit_scores"]["threat_awareness"]["score"] == data2["habit_scores"]["threat_awareness"]["score"]


class TestThinkingScoreHistory:
    """Test suite for thinking score history endpoint."""
    
    def test_get_history_returns_list(self):
        """GET /api/thinking-score/history returns score history."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/history?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "scores" in data
        assert "count" in data
        assert isinstance(data["scores"], list)
        assert data["count"] == len(data["scores"])
    
    def test_history_limit_parameter(self):
        """History endpoint respects limit parameter."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/history?limit=3")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["scores"]) <= 3
    
    def test_history_score_structure(self):
        """Each history entry has complete score data."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/history?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        
        if data["scores"]:
            entry = data["scores"][0]
            
            # Should have required fields
            assert "overall_score" in entry
            assert "habit_scores" in entry
            assert "game_id" in entry
            assert "calculated_at" in entry


class TestThinkingRecommendations:
    """Test suite for thinking recommendations endpoint."""
    
    def test_get_recommendations_valid_response(self):
        """GET /api/thinking-score/recommendations returns valid structure."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/recommendations")
        assert response.status_code == 200
        
        data = response.json()
        
        # Must indicate whether data is available
        assert "has_data" in data
        assert "recommendations" in data
    
    def test_recommendations_when_no_data(self):
        """Recommendations endpoint provides fallback when no data."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/recommendations")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should always have at least one recommendation
        assert len(data["recommendations"]) >= 1
        
        # First recommendation should be valid
        rec = data["recommendations"][0]
        assert "recommendation" in rec
        assert "checklist_item" in rec
    
    def test_recommendations_sorted_by_weakness(self):
        """Recommendations should prioritize weakest habits."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/recommendations")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data") and len(data["recommendations"]) >= 2:
            # If scores exist, verify recommendations are sorted by score (weakest first)
            scores = [rec.get("score", 100) for rec in data["recommendations"]]
            # Lower scores = weaker habits = higher priority
            assert scores == sorted(scores), "Recommendations should be sorted by score (weakest first)"


class TestThinkingScoreIntegration:
    """Integration tests for the full thinking score flow."""
    
    def test_full_flow_calculate_then_retrieve(self):
        """Test flow: calculate score for game, then retrieve overall score."""
        # Get a game
        games_response = requests.get(f"{BASE_URL}/api/games?limit=1")
        if games_response.status_code != 200 or not games_response.json():
            pytest.skip("No games available for testing")
        
        game_id = games_response.json()[0].get("game_id")
        
        # Calculate score
        calc_response = requests.post(f"{BASE_URL}/api/thinking-score/calculate/{game_id}")
        assert calc_response.status_code == 200
        
        calc_data = calc_response.json()
        calculated_score = calc_data.get("overall_score")
        
        # Retrieve overall thinking score
        score_response = requests.get(f"{BASE_URL}/api/thinking-score")
        assert score_response.status_code == 200
        
        score_data = score_response.json()
        
        # Should now have data
        assert score_data.get("has_data") == True
        
        # The history should include the calculated game
        history_response = requests.get(f"{BASE_URL}/api/thinking-score/history?limit=10")
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        game_ids_in_history = [s.get("game_id") for s in history_data.get("scores", [])]
        assert game_id in game_ids_in_history, "Calculated game should appear in history"
    
    def test_habit_examples_contain_real_move_data(self):
        """Verify habit examples include real move information."""
        # Get a game
        games_response = requests.get(f"{BASE_URL}/api/games?limit=1")
        if games_response.status_code != 200 or not games_response.json():
            pytest.skip("No games available for testing")
        
        game_id = games_response.json()[0].get("game_id")
        
        # Calculate score
        response = requests.post(f"{BASE_URL}/api/thinking-score/calculate/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check for examples in habit scores
        habit_scores = data.get("habit_scores", {})
        
        has_examples = False
        for habit, habit_data in habit_scores.items():
            examples = habit_data.get("examples", [])
            if examples:
                has_examples = True
                for example in examples:
                    # Examples should have move information
                    assert "move_number" in example or "move" in example or "cp_loss" in example
        
        # If there were mistakes, there should be examples
        total_mistakes = sum(h.get("mistakes", 0) for h in habit_scores.values())
        if total_mistakes > 0:
            assert has_examples, "Should have examples when mistakes exist"


class TestThinkingScoreEdgeCases:
    """Edge case tests for thinking score."""
    
    def test_history_with_zero_limit(self):
        """History with limit=0 should return empty list."""
        response = requests.get(f"{BASE_URL}/api/thinking-score/history?limit=0")
        # Could be 200 with empty list or 400 for invalid param
        if response.status_code == 200:
            data = response.json()
            assert data["count"] == 0
    
    def test_score_explanation_varies_with_score(self):
        """Score explanation should reflect score level."""
        response = requests.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("has_data"):
            score = data.get("overall_score", 0)
            explanation = data.get("explanation", "")
            
            # Explanation should exist and be meaningful
            assert len(explanation) > 10
            
            # Explanation should match score level
            if score >= 90:
                assert "excellent" in explanation.lower() or "great" in explanation.lower()
            elif score < 60:
                assert "basics" in explanation.lower() or "focus" in explanation.lower() or "improvement" in explanation.lower()
