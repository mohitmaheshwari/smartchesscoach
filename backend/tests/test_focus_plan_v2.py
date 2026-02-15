"""
Test Focus Plan V2 Features:
1. Example Position cycling - multiple positions with prev/next
2. Last Game Audit - executed/partial/missed status for rules
3. User Thoughts API - save and retrieve thoughts on mistakes
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFocusPlanExamplePositions:
    """Test example_positions array in primary_focus for cycling UI"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get session token from dev login"""
        self.session = requests.Session()
        # Dev login to get cookie
        res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert res.status_code == 200
        yield
    
    def test_focus_plan_has_example_positions_array(self):
        """Verify focus plan returns example_positions as array for cycling"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan")
        assert res.status_code == 200
        
        data = res.json()
        # Check if plan exists
        if data.get("needs_more_games"):
            pytest.skip("Need more games for focus plan")
            
        plan = data.get("plan", {})
        assert "primary_focus" in plan, "Missing primary_focus in plan"
        
        primary_focus = plan["primary_focus"]
        
        # Must have example_positions array
        assert "example_positions" in primary_focus, "Missing example_positions array"
        example_positions = primary_focus["example_positions"]
        assert isinstance(example_positions, list), "example_positions must be a list"
        
        # Should have up to 5 positions
        print(f"Found {len(example_positions)} example positions")
        
        # If there are positions, validate their structure
        if example_positions:
            pos = example_positions[0]
            assert "fen" in pos or pos is None, "Position missing fen"
            if pos and pos.get("fen"):
                assert "move_number" in pos, "Position missing move_number"
                assert "cp_loss" in pos, "Position missing cp_loss"
                print(f"First position: Move {pos.get('move_number')}, cp_loss: {pos.get('cp_loss')}")
    
    def test_focus_plan_has_backwards_compatible_example_position(self):
        """Verify backwards compatibility with single example_position field"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("needs_more_games"):
            pytest.skip("Need more games for focus plan")
            
        plan = data.get("plan", {})
        primary_focus = plan.get("primary_focus", {})
        
        # Should have example_position (single) for backwards compatibility
        # This may be None if no positions
        assert "example_position" in primary_focus, "Missing example_position for backwards compatibility"
        print(f"example_position: {primary_focus.get('example_position')}")


class TestLastGameAudit:
    """Test Last Game Audit feature on Focus page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get session token from dev login"""
        self.session = requests.Session()
        res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert res.status_code == 200
        yield
    
    def test_last_game_audit_endpoint_exists(self):
        """Test GET /api/focus-plan/last-game-audit endpoint"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan/last-game-audit")
        assert res.status_code == 200
        data = res.json()
        
        # Should return either has_audit: true/false or error
        if data.get("error"):
            print(f"No audit available: {data.get('error')}")
            return
            
        # Check audit structure
        if data.get("has_audit"):
            assert "game_id" in data, "Missing game_id in audit"
            assert "opponent" in data, "Missing opponent in audit"
            assert "overall_alignment" in data, "Missing overall_alignment"
            assert "rules_audit" in data, "Missing rules_audit"
            
            print(f"Audit for game: {data.get('game_id')}")
            print(f"Opponent: {data.get('opponent')}")
            print(f"Overall alignment: {data.get('overall_alignment')}")
            
            # Validate overall_alignment values
            assert data["overall_alignment"] in ["executed", "partial", "missed"], \
                f"Invalid overall_alignment: {data['overall_alignment']}"
    
    def test_last_game_audit_rules_structure(self):
        """Test rules_audit array structure with status badges"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan/last-game-audit")
        assert res.status_code == 200
        data = res.json()
        
        if not data.get("has_audit"):
            pytest.skip("No audit available")
        
        rules_audit = data.get("rules_audit", [])
        assert isinstance(rules_audit, list), "rules_audit must be a list"
        
        for rule_audit in rules_audit:
            assert "rule" in rule_audit, "Missing rule text"
            assert "status" in rule_audit, "Missing status"
            assert "note" in rule_audit, "Missing note"
            
            # Status must be one of these values
            assert rule_audit["status"] in ["executed", "partial", "missed"], \
                f"Invalid status: {rule_audit['status']}"
            
            print(f"Rule: {rule_audit['rule']}")
            print(f"  Status: {rule_audit['status']} - {rule_audit['note']}")
    
    def test_last_game_audit_violations_structure(self):
        """Test violations array structure for key moments"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan/last-game-audit")
        assert res.status_code == 200
        data = res.json()
        
        if not data.get("has_audit"):
            pytest.skip("No audit available")
        
        violations = data.get("violations", [])
        assert isinstance(violations, list), "violations must be a list"
        
        # If there are violations, check structure
        if violations:
            v = violations[0]
            assert "move_number" in v, "Violation missing move_number"
            assert "fen" in v, "Violation missing fen"
            assert "reason" in v, "Violation missing reason"
            print(f"Found {len(violations)} violations")
            print(f"First violation: Move {v.get('move_number')} - {v.get('reason')}")


class TestUserThoughtsAPI:
    """Test POST/GET /api/games/{game_id}/thought(s) endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get session token from dev login"""
        self.session = requests.Session()
        res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert res.status_code == 200
        yield
    
    def get_valid_game_id(self):
        """Get a valid game_id from user's games"""
        res = self.session.get(f"{BASE_URL}/api/games")
        if res.status_code != 200:
            return None
        games = res.json()
        if games and len(games) > 0:
            return games[0].get("game_id")
        return None
    
    def test_save_user_thought_endpoint_exists(self):
        """Test POST /api/games/{game_id}/thought endpoint"""
        game_id = self.get_valid_game_id()
        if not game_id:
            pytest.skip("No games available for testing")
        
        # Try to save a thought
        thought_data = {
            "move_number": 10,
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "thought_text": "I was thinking about developing my knight",
            "move_played": "Nf6",
            "best_move": "d5",
            "evaluation_type": "inaccuracy",
            "cp_loss": 50
        }
        
        res = self.session.post(
            f"{BASE_URL}/api/games/{game_id}/thought",
            json=thought_data
        )
        assert res.status_code == 200, f"Failed to save thought: {res.text}"
        
        data = res.json()
        assert data.get("success") == True, "Expected success: true"
        assert "thought_id" in data, "Missing thought_id in response"
        print(f"Saved thought with ID: {data.get('thought_id')}")
    
    def test_get_game_thoughts_endpoint_exists(self):
        """Test GET /api/games/{game_id}/thoughts endpoint"""
        game_id = self.get_valid_game_id()
        if not game_id:
            pytest.skip("No games available for testing")
        
        res = self.session.get(f"{BASE_URL}/api/games/{game_id}/thoughts")
        assert res.status_code == 200, f"Failed to get thoughts: {res.text}"
        
        data = res.json()
        assert "game_id" in data, "Missing game_id in response"
        assert "thoughts" in data, "Missing thoughts array"
        assert "count" in data, "Missing count"
        assert data["game_id"] == game_id, "game_id mismatch"
        
        print(f"Found {data.get('count')} thoughts for game {game_id}")
    
    def test_save_and_retrieve_thought_roundtrip(self):
        """Test full roundtrip: save thought then retrieve it"""
        game_id = self.get_valid_game_id()
        if not game_id:
            pytest.skip("No games available for testing")
        
        # Save a unique thought with unique move number
        import uuid
        import random
        unique_text = f"Test thought {uuid.uuid4().hex[:8]}"
        move_num = random.randint(100, 200)  # Use high move number to avoid conflicts
        
        thought_data = {
            "move_number": move_num,
            "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
            "thought_text": unique_text,
            "move_played": "Bc4",
            "best_move": "Bb5",
            "evaluation_type": "mistake",
            "cp_loss": 80
        }
        
        # Save
        save_res = self.session.post(
            f"{BASE_URL}/api/games/{game_id}/thought",
            json=thought_data
        )
        assert save_res.status_code == 200
        
        # Retrieve
        get_res = self.session.get(f"{BASE_URL}/api/games/{game_id}/thoughts")
        assert get_res.status_code == 200
        
        thoughts = get_res.json().get("thoughts", [])
        
        # Find our thought by unique text
        found = None
        for t in thoughts:
            if t.get("thought_text") == unique_text:
                found = t
                break
        
        assert found is not None, f"Could not find saved thought with text: {unique_text}"
        assert found.get("move_number") == move_num
        # Check that evaluation_type is saved correctly (might be updated if move existed)
        assert found.get("thought_text") == unique_text
        print(f"Successfully saved and retrieved thought: {unique_text}")
    
    def test_update_existing_thought(self):
        """Test updating an existing thought for the same move"""
        game_id = self.get_valid_game_id()
        if not game_id:
            pytest.skip("No games available for testing")
        
        move_num = 20  # Use a specific move number
        
        # First save
        thought_data = {
            "move_number": move_num,
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "thought_text": "Original thought"
        }
        
        res1 = self.session.post(
            f"{BASE_URL}/api/games/{game_id}/thought",
            json=thought_data
        )
        assert res1.status_code == 200
        
        # Update same move with new thought
        thought_data["thought_text"] = "Updated thought"
        res2 = self.session.post(
            f"{BASE_URL}/api/games/{game_id}/thought",
            json=thought_data
        )
        assert res2.status_code == 200
        
        data = res2.json()
        assert data.get("message") == "Thought updated", "Expected thought to be updated"
        print("Successfully updated existing thought")
    
    def test_invalid_game_id_returns_404(self):
        """Test that invalid game_id returns 404"""
        res = self.session.post(
            f"{BASE_URL}/api/games/invalid_game_12345/thought",
            json={
                "move_number": 1,
                "fen": "test",
                "thought_text": "test"
            }
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("Correctly returns 404 for invalid game_id")


class TestFocusPlanIntegration:
    """Integration tests for focus plan with audit"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get session token from dev login"""
        self.session = requests.Session()
        res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert res.status_code == 200
        yield
    
    def test_focus_plan_contains_all_required_fields(self):
        """Test that focus plan has all required fields"""
        res = self.session.get(f"{BASE_URL}/api/focus-plan")
        assert res.status_code == 200
        
        data = res.json()
        if data.get("needs_more_games"):
            pytest.skip("Need more games for focus plan")
        
        plan = data.get("plan", {})
        
        # Required fields
        required_fields = [
            "plan_id", "user_id", "primary_focus", "rules",
            "openings", "mission", "weekly_requirements"
        ]
        
        for field in required_fields:
            assert field in plan, f"Missing required field: {field}"
        
        # Primary focus structure
        pf = plan["primary_focus"]
        assert "code" in pf, "primary_focus missing code"
        assert "label" in pf, "primary_focus missing label"
        assert "example_positions" in pf, "primary_focus missing example_positions"
        
        print(f"Plan {plan.get('plan_id')} validated successfully")
        print(f"Primary Focus: {pf.get('code')} - {pf.get('label')}")
        print(f"Example positions count: {len(pf.get('example_positions', []))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
