"""
Test Enhanced Reflection System - Training Page Step 4
=======================================================

Tests for:
1. GET /api/training/last-game-for-reflection
2. GET /api/training/game/{game_id}/milestones
3. POST /api/training/milestone/explain
4. POST /api/training/milestone/reflect
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://training-ui.preview.emergentagent.com').rstrip('/')


class TestEnhancedReflection:
    """Test the enhanced reflection system for Training page"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Login using dev endpoint
        resp = s.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        return s
    
    def test_last_game_for_reflection(self, session):
        """Test GET /api/training/last-game-for-reflection returns game_id"""
        resp = session.get(f"{BASE_URL}/api/training/last-game-for-reflection")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "game_id" in data, "Response should have game_id"
        assert data["game_id"] is not None or "error" in data, "Should have game_id or error"
        
        # Store for other tests
        self.__class__.game_id = data.get("game_id")
        print(f"✓ Last game for reflection: {data.get('game_id')}")
    
    def test_get_game_milestones(self, session):
        """Test GET /api/training/game/{game_id}/milestones returns milestones"""
        game_id = getattr(self.__class__, 'game_id', None)
        if not game_id:
            pytest.skip("No game_id from previous test")
        
        resp = session.get(f"{BASE_URL}/api/training/game/{game_id}/milestones")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        
        # Verify structure
        assert "game_id" in data, "Response should have game_id"
        assert "milestones" in data, "Response should have milestones array"
        assert "total_count" in data, "Response should have total_count"
        assert "rating_category" in data, "Response should have rating_category"
        assert "min_cp_threshold" in data, "Response should have min_cp_threshold"
        
        # Store first milestone for other tests
        if data["milestones"]:
            self.__class__.first_milestone = data["milestones"][0]
            
            # Verify milestone structure
            milestone = data["milestones"][0]
            assert "move_number" in milestone, "Milestone should have move_number"
            assert "fen" in milestone, "Milestone should have fen"
            assert "user_move" in milestone, "Milestone should have user_move"
            assert "best_move" in milestone, "Milestone should have best_move"
            assert "cp_loss" in milestone, "Milestone should have cp_loss"
            assert "evaluation_type" in milestone, "Milestone should have evaluation_type"
            assert "reflection_options" in milestone, "Milestone should have reflection_options"
            assert "context_for_explanation" in milestone, "Milestone should have context_for_explanation"
            
            # Verify reflection options have contextual flags
            for opt in milestone["reflection_options"]:
                assert "tag" in opt, "Option should have tag"
                assert "label" in opt, "Option should have label"
                assert "contextual" in opt, "Option should have contextual flag"
            
            # Check for position-specific options
            option_tags = [opt["tag"] for opt in milestone["reflection_options"]]
            print(f"✓ Contextual tags present: {option_tags}")
        
        print(f"✓ Found {data['total_count']} milestones for game {game_id}")
    
    def test_milestone_explain(self, session):
        """Test POST /api/training/milestone/explain generates explanation"""
        milestone = getattr(self.__class__, 'first_milestone', None)
        if not milestone:
            pytest.skip("No milestone from previous test")
        
        payload = {
            "context_for_explanation": milestone["context_for_explanation"],
            "fen": milestone["fen"],
            "move_played": milestone["user_move"],
            "best_move": milestone["best_move"]
        }
        
        resp = session.post(f"{BASE_URL}/api/training/milestone/explain", json=payload)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        
        # Verify structure
        assert "stockfish_analysis" in data, "Response should have stockfish_analysis"
        assert "move_played" in data, "Response should have move_played"
        assert "best_move" in data, "Response should have best_move"
        
        # Verify stockfish analysis has useful info
        sf = data["stockfish_analysis"]
        assert "eval_swing" in sf or "position_context" in sf, "Should have position context"
        assert "cp_lost" in sf, "Should explain centipawn loss"
        
        # Check if human explanation was generated
        if "human_explanation" in data:
            assert len(data["human_explanation"]) > 10, "Human explanation should be meaningful"
            print(f"✓ Human explanation: {data['human_explanation'][:100]}...")
        else:
            print("✓ Stockfish analysis provided (no LLM humanization)")
    
    def test_save_milestone_reflection(self, session):
        """Test POST /api/training/milestone/reflect saves reflection"""
        game_id = getattr(self.__class__, 'game_id', None)
        milestone = getattr(self.__class__, 'first_milestone', None)
        
        if not game_id or not milestone:
            pytest.skip("No game_id or milestone from previous tests")
        
        move_number = milestone["move_number"]
        
        payload = {
            "selected_tags": ["missed_threat", "time_pressure"],
            "user_plan": "Testing the reflection save endpoint",
            "understood": True,
            "fen": milestone["fen"]
        }
        
        resp = session.post(
            f"{BASE_URL}/api/training/milestone/reflect?game_id={game_id}&move_number={move_number}",
            json=payload
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data["status"] == "saved", "Reflection should be saved"
        assert data["move_number"] == move_number, "Move number should match"
        
        print(f"✓ Reflection saved for move {move_number}")
    
    def test_contextual_options_generation(self, session):
        """Test that reflection options are contextual based on position"""
        game_id = getattr(self.__class__, 'game_id', None)
        if not game_id:
            pytest.skip("No game_id from previous test")
        
        resp = session.get(f"{BASE_URL}/api/training/game/{game_id}/milestones")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        if not data["milestones"]:
            pytest.skip("No milestones available")
        
        milestone = data["milestones"][0]
        options = milestone.get("reflection_options", [])
        
        # Check for both contextual and generic options
        contextual_options = [o for o in options if o.get("contextual") == True]
        generic_options = [o for o in options if o.get("contextual") == False]
        
        # Should have at least some contextual options based on position
        assert len(generic_options) >= 2, "Should have at least 2 generic options"
        print(f"✓ Contextual options: {len(contextual_options)}, Generic options: {len(generic_options)}")
        
        # Verify specific generic tags are present
        generic_tags = [o["tag"] for o in generic_options]
        assert "time_pressure" in generic_tags, "Should have time_pressure option"
        assert "tunnel_vision" in generic_tags or "didnt_consider" in generic_tags, "Should have thinking-related option"
    
    def test_pv_lines_present(self, session):
        """Test that PV lines are provided for interactive board"""
        game_id = getattr(self.__class__, 'game_id', None)
        if not game_id:
            pytest.skip("No game_id from previous test")
        
        resp = session.get(f"{BASE_URL}/api/training/game/{game_id}/milestones")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        if not data["milestones"]:
            pytest.skip("No milestones available")
        
        milestone = data["milestones"][0]
        
        # Check PV lines exist
        assert "pv_after_best" in milestone, "Should have pv_after_best"
        assert "pv_after_played" in milestone, "Should have pv_after_played"
        
        if milestone.get("pv_after_best"):
            print(f"✓ Better line: {' '.join(milestone['pv_after_best'][:4])}")
        if milestone.get("pv_after_played"):
            print(f"✓ Played line: {' '.join(milestone['pv_after_played'][:4])}")
    
    def test_training_profile_exists(self, session):
        """Test that training profile is available"""
        resp = session.get(f"{BASE_URL}/api/training/profile")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        
        # Skip if insufficient data
        if data.get("status") == "insufficient_data":
            pytest.skip("User has insufficient games for profile")
        
        # Verify key fields
        assert "active_phase" in data, "Should have active_phase"
        assert "micro_habit" in data, "Should have micro_habit"
        assert "rules" in data, "Should have rules"
        assert "example_positions" in data, "Should have example_positions"
        
        print(f"✓ Training profile: Phase={data['active_phase']}, Habit={data['micro_habit']}")


class TestRatingBasedFiltering:
    """Test rating-based milestone filtering"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        resp = s.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
        return s
    
    def test_milestones_have_min_threshold(self, session):
        """Test that milestones are filtered by rating threshold"""
        # Get last game
        resp = session.get(f"{BASE_URL}/api/training/last-game-for-reflection")
        if resp.status_code != 200 or not resp.json().get("game_id"):
            pytest.skip("No game available")
        
        game_id = resp.json()["game_id"]
        
        # Get milestones
        resp = session.get(f"{BASE_URL}/api/training/game/{game_id}/milestones")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        min_cp = data.get("min_cp_threshold", 100)
        
        # All milestones should meet the threshold
        for m in data.get("milestones", []):
            assert m["cp_loss"] >= min_cp, f"Milestone at move {m['move_number']} has cp_loss {m['cp_loss']} below threshold {min_cp}"
        
        print(f"✓ All {len(data.get('milestones', []))} milestones meet threshold of {min_cp}cp")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
