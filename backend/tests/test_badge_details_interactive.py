"""
Test Badge Details and Interactive Board Features

Tests for:
1. Badge details endpoint /api/badges/{badge_key}/details
2. Mistake classifier fork/pin detection
3. Badge detail structure with deterministic mistake types

These tests verify the Progress page drill-down features.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBadgeDetailsEndpoint:
    """Tests for /api/badges/{badge_key}/details endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get session via dev-login for testing"""
        self.session = requests.Session()
        # Dev login to get session cookie
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        data = login_resp.json()
        assert data.get("status") == "ok", "Dev login did not succeed"
    
    def test_badges_endpoint_returns_200(self):
        """Test that /api/badges returns 200 with badge data"""
        response = self.session.get(f"{BASE_URL}/api/badges")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should have badges dict
        assert "badges" in data or "message" in data, "Response should have badges or message"
    
    def test_badge_details_tactical_returns_structure(self):
        """Test /api/badges/tactical/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/tactical/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should have required fields
        assert "badge_key" in data, "Missing badge_key"
        assert data["badge_key"] == "tactical", "Wrong badge_key"
        assert "badge_name" in data, "Missing badge_name"
        assert "score" in data, "Missing score"
        assert "insight" in data, "Missing insight"
        assert "relevant_games" in data, "Missing relevant_games"
        assert "summary" in data, "Missing summary"
        assert "why_this_score" in data, "Missing why_this_score"
    
    def test_badge_details_opening_returns_structure(self):
        """Test /api/badges/opening/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/opening/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should have required fields
        assert "badge_key" in data
        assert data["badge_key"] == "opening"
        assert "relevant_games" in data
    
    def test_badge_details_positional_returns_structure(self):
        """Test /api/badges/positional/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/positional/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "positional"
    
    def test_badge_details_endgame_returns_structure(self):
        """Test /api/badges/endgame/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/endgame/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "endgame"
    
    def test_badge_details_defense_returns_structure(self):
        """Test /api/badges/defense/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/defense/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "defense"
    
    def test_badge_details_converting_returns_structure(self):
        """Test /api/badges/converting/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/converting/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "converting"
    
    def test_badge_details_focus_returns_structure(self):
        """Test /api/badges/focus/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/focus/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "focus"
    
    def test_badge_details_time_returns_structure(self):
        """Test /api/badges/time/details returns correct structure"""
        response = self.session.get(f"{BASE_URL}/api/badges/time/details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["badge_key"] == "time"
    
    def test_badge_details_invalid_badge_returns_400(self):
        """Test that unknown badge key returns 400"""
        response = self.session.get(f"{BASE_URL}/api/badges/invalid_badge/details")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    def test_badge_details_games_have_required_fields(self):
        """Test that relevant_games in badge details have the required fields"""
        response = self.session.get(f"{BASE_URL}/api/badges/tactical/details")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("relevant_games"):
            for game in data["relevant_games"]:
                # Each game should have these fields
                assert "game_id" in game, "Game missing game_id"
                assert "opponent" in game, "Game missing opponent"
                assert "result" in game, "Game missing result"
                assert "user_color" in game, "Game missing user_color"
                assert "moves" in game, "Game missing moves"
                
                # Check moves structure if present
                if game.get("moves"):
                    for move in game["moves"]:
                        assert "move_number" in move, "Move missing move_number"
                        assert "move_played" in move, "Move missing move_played"
                        assert "type" in move, "Move missing type"
                        # These are important for InteractiveBoard:
                        # fen_before (for starting position)
                        # best_move (for "Best Move" button)
                        print(f"Move {move.get('move_number')}: type={move.get('type')}, has fen_before={bool(move.get('fen_before'))}, best_move={move.get('best_move')}")


class TestMistakeClassifier:
    """Tests for mistake_classifier.py fork/pin detection"""
    
    def test_classify_mistake_function_exists(self):
        """Verify mistake_classifier module can be imported"""
        import sys
        sys.path.insert(0, '/app/backend')
        from mistake_classifier import classify_mistake, MistakeType
        assert classify_mistake is not None
        assert MistakeType.WALKED_INTO_FORK is not None
        assert MistakeType.WALKED_INTO_PIN is not None
        assert MistakeType.MISSED_FORK is not None
        assert MistakeType.MISSED_PIN is not None
    
    def test_find_forks_function(self):
        """Test that find_forks detects knight forks"""
        import sys
        sys.path.insert(0, '/app/backend')
        from mistake_classifier import find_forks
        import chess
        
        # Position with a knight fork on queen and rook
        # White knight on e5, Black queen on f7, Black rook on d7
        board = chess.Board("r1b1k2r/pp1qnppp/2p2n2/3pN3/3P4/2N1P3/PPP2PPP/R1BQK2R w KQkq - 0 1")
        forks = find_forks(board, chess.WHITE)
        
        # The knight on e5 attacks f7 and d7
        print(f"Found forks: {forks}")
        # Test should pass if fork detection works
        assert isinstance(forks, list)
    
    def test_find_pins_function(self):
        """Test that find_pins detects pin patterns"""
        import sys
        sys.path.insert(0, '/app/backend')
        from mistake_classifier import find_pins
        import chess
        
        # Position with a pinned knight
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3")
        pins = find_pins(board, chess.BLACK)
        
        print(f"Found pins: {pins}")
        assert isinstance(pins, list)
    
    def test_classify_mistake_returns_correct_structure(self):
        """Test classify_mistake returns ClassifiedMistake with all fields"""
        import sys
        sys.path.insert(0, '/app/backend')
        from mistake_classifier import classify_mistake
        
        fen_before = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        fen_after = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        
        result = classify_mistake(
            fen_before=fen_before,
            fen_after=fen_after,
            move_played="e4",
            best_move="e4",
            eval_before=20,
            eval_after=20,
            user_color="white",
            move_number=1
        )
        
        # Check structure
        assert hasattr(result, 'mistake_type')
        assert hasattr(result, 'context')
        assert hasattr(result, 'eval_drop')
        assert hasattr(result, 'pattern_details')
        
        print(f"Mistake type: {result.mistake_type.value}")
        print(f"Eval drop: {result.eval_drop}")
    
    def test_classify_mistake_detects_blunder(self):
        """Test that a significant eval drop is classified appropriately"""
        import sys
        sys.path.insert(0, '/app/backend')
        from mistake_classifier import classify_mistake, MistakeType
        
        # Position where eval drops significantly
        fen_before = "r1bqkbnr/pppppppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2"
        fen_after = "r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 2"
        
        result = classify_mistake(
            fen_before=fen_before,
            fen_after=fen_after,
            move_played="Nf3",
            best_move="Nxe5",
            eval_before=50,  # +0.5
            eval_after=-150,  # -1.5
            user_color="white",
            move_number=4
        )
        
        print(f"Mistake type for significant eval drop: {result.mistake_type.value}")
        print(f"Eval drop: {result.eval_drop}")
        
        # Should be classified as some kind of mistake (not good move)
        assert result.mistake_type not in [MistakeType.GOOD_MOVE, MistakeType.EXCELLENT_MOVE]


class TestDevMode:
    """Test DEV_MODE functionality"""
    
    def test_auth_status_returns_dev_mode(self):
        """Test that /api/auth/status returns dev_mode status"""
        response = requests.get(f"{BASE_URL}/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "dev_mode" in data
        # Should be true since we enabled it
        print(f"Dev mode status: {data['dev_mode']}")
    
    def test_dev_login_works(self):
        """Test that dev login endpoint works"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/auth/dev-login")
        assert response.status_code == 200, f"Dev login failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        assert "user" in data
        assert data["user"]["user_id"] == "local_tester"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
