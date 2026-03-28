"""
Test Cases for Milestones Feature and Dashboard Polling
Tests:
1. Lab page - Milestones tab with brilliant moves, great decisions, learning moments
2. Dashboard polling - queued_games field in dashboard-stats
3. Explain mistake endpoint - coach-like explanations
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Use dev auth for testing
def get_auth_session():
    """Get authenticated session via dev login"""
    session = requests.Session()
    # Dev login
    session.get(f"{BASE_URL}/api/auth/dev-login")
    return session


class TestDashboardStats:
    """Dashboard stats endpoint tests - verify queued_games field for polling"""
    
    def test_dashboard_stats_returns_queued_games(self):
        """Verify /api/dashboard-stats includes queued_games field"""
        session = get_auth_session()
        response = session.get(f"{BASE_URL}/api/dashboard-stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify required fields for polling feature
        assert "queued_games" in data, "Missing 'queued_games' field for polling"
        assert isinstance(data["queued_games"], int), "queued_games should be integer"
        
        # Verify other stats fields
        assert "total_games" in data
        assert "analyzed_games" in data
        assert "not_analyzed_games" in data
        
        print(f"Dashboard stats: total={data['total_games']}, analyzed={data['analyzed_games']}, queued={data['queued_games']}")
    
    def test_dashboard_stats_includes_game_lists(self):
        """Verify dashboard-stats returns game lists for tabs"""
        session = get_auth_session()
        response = session.get(f"{BASE_URL}/api/dashboard-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify game lists for dashboard tabs
        assert "analyzed_list" in data, "Missing analyzed_list for Analyzed tab"
        assert "in_queue_list" in data, "Missing in_queue_list for In Queue tab"
        assert "not_analyzed_list" in data, "Missing not_analyzed_list for Not Analyzed tab"
        
        # Verify list structure
        if len(data["analyzed_list"]) > 0:
            game = data["analyzed_list"][0]
            assert "game_id" in game
            assert "user_color" in game
            
        print(f"Game lists: analyzed={len(data['analyzed_list'])}, in_queue={len(data['in_queue_list'])}, not_analyzed={len(data['not_analyzed_list'])}")


class TestLabEndpoints:
    """Lab page endpoints - verify analysis data structure"""
    
    @pytest.fixture
    def test_game_id(self):
        """Get a game ID with analysis for testing"""
        return "fedf27ba-ca55-463f-9b3c-5e1815639472"
    
    def test_lab_endpoint_returns_data(self, test_game_id):
        """Verify /api/lab/{game_id} returns analysis data"""
        session = get_auth_session()
        response = session.get(f"{BASE_URL}/api/lab/{test_game_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify core lesson (used for milestones grouping)
        assert "core_lesson" in data
        if data["core_lesson"]:
            assert "lesson" in data["core_lesson"]
            assert "pattern" in data["core_lesson"]
            
        print(f"Lab data has core_lesson: {data.get('core_lesson', {}).get('pattern')}")
    
    def test_analysis_endpoint_returns_move_evaluations(self, test_game_id):
        """Verify /api/analysis/{game_id} returns move evaluations for milestones"""
        session = get_auth_session()
        response = session.get(f"{BASE_URL}/api/analysis/{test_game_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify stockfish analysis with move evaluations (needed for milestones)
        assert "stockfish_analysis" in data
        stockfish = data["stockfish_analysis"]
        
        assert "move_evaluations" in stockfish
        assert isinstance(stockfish["move_evaluations"], list)
        assert len(stockfish["move_evaluations"]) > 0, "No move evaluations found"
        
        # Check evaluation structure for milestone grouping
        first_eval = stockfish["move_evaluations"][0]
        assert "move_number" in first_eval
        assert "move" in first_eval
        assert "cp_loss" in first_eval
        
        print(f"Analysis has {len(stockfish['move_evaluations'])} move evaluations")
        
        # Count types for milestones
        brilliant = sum(1 for m in stockfish["move_evaluations"] if m.get("cp_loss", 999) <= 5)
        learning = sum(1 for m in stockfish["move_evaluations"] if m.get("cp_loss", 0) >= 50)
        print(f"Potential brilliant moves: {brilliant}, learning moments: {learning}")


class TestExplainMistake:
    """Test the explain-mistake endpoint for coach-like feedback"""
    
    def test_explain_mistake_returns_coach_feedback(self):
        """Verify /api/explain-mistake returns coach-style explanation"""
        session = get_auth_session()
        
        # Sample mistake data
        payload = {
            "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "move": "d5",
            "best_move": "c5",
            "cp_loss": 41,
            "user_color": "black",
            "move_number": 1
        }
        
        response = session.post(
            f"{BASE_URL}/api/explain-mistake",
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert "explanation" in data, "Missing explanation field"
        assert "mistake_type" in data, "Missing mistake_type field"
        assert "short_label" in data, "Missing short_label field"
        
        # Verify coach-like feedback elements
        assert len(data["explanation"]) > 20, "Explanation too short for coach feedback"
        
        # Check for thinking habit (coach tip)
        if "thinking_habit" in data and data["thinking_habit"]:
            print(f"Thinking habit tip: {data['thinking_habit']}")
        
        print(f"Explanation type: {data['mistake_type']}, Label: {data['short_label']}")
        print(f"Coach feedback: {data['explanation'][:100]}...")
    
    def test_explain_mistake_handles_blunder(self):
        """Test explanation for a blunder (higher cp_loss)"""
        session = get_auth_session()
        
        # Sample blunder data
        payload = {
            "fen_before": "r2qk2r/p1p3p1/2p1pn2/3p2p1/3P2P1/P1N5/1PP2PP1/R2Q1RK1 b kq - 0 15",
            "move": "Qb8",
            "best_move": "Qd6",
            "cp_loss": 233,
            "user_color": "black",
            "move_number": 15
        }
        
        response = session.post(
            f"{BASE_URL}/api/explain-mistake",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "explanation" in data
        # For blunders, severity should be higher
        severity = data.get("severity", "unknown")
        print(f"Blunder severity: {severity}")


class TestGameReanalyze:
    """Test the reanalyze endpoint for queue functionality"""
    
    @pytest.fixture
    def not_analyzed_game_id(self):
        """Get a not-analyzed game ID"""
        session = get_auth_session()
        response = session.get(f"{BASE_URL}/api/dashboard-stats")
        data = response.json()
        
        if data.get("not_analyzed_list") and len(data["not_analyzed_list"]) > 0:
            return data["not_analyzed_list"][0]["game_id"]
        return None
    
    def test_reanalyze_queues_game(self, not_analyzed_game_id):
        """Verify POST /api/games/{id}/reanalyze queues a game"""
        if not not_analyzed_game_id:
            pytest.skip("No not-analyzed games available for testing")
        
        session = get_auth_session()
        response = session.post(f"{BASE_URL}/api/games/{not_analyzed_game_id}/reanalyze")
        
        # Should succeed or indicate already queued/analyzed
        assert response.status_code in [200, 400, 409], f"Unexpected status: {response.status_code}"
        
        data = response.json()
        print(f"Reanalyze response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
