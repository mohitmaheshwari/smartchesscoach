"""
Test suite for Reflect Pre-filtering Feature

Tests that:
1. GET /api/reflect/pending - Only returns games with qualifying moments (no "Great Game!" candidates)
2. GET /api/reflect/pending/count - Count matches actual available games
3. GET /api/reflect/game/{game_id}/moments - Returns filtered moments correctly
4. /api/explain-mistake - Still correctly detects mate in 1 (Move 21 Qf3)

The pre-filtering ensures users don't see "Great Game!" screens for games without actual mistakes.
"""

import pytest
import requests
import os

# Get BASE_URL from environment - MUST be the public URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://chess-training-hub-1.preview.emergentagent.com"


class TestReflectPrefiltering:
    """Test the pre-filtering logic for reflect/pending endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login"""
        self.session = requests.Session()
        login_res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_res.status_code == 200, f"Dev login failed: {login_res.text}"
        self.user_data = login_res.json()
    
    def test_pending_returns_only_games_with_moments(self):
        """
        CRITICAL TEST: Every game in pending list should have actual qualifying moments.
        This is the core fix - games without qualifying moments should NOT appear.
        """
        # Get pending games
        res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        games = res.json().get("games", [])
        print(f"Found {len(games)} pending games")
        
        # For each game in pending list, verify it has qualifying moments
        games_without_moments = []
        for game in games:
            game_id = game.get("game_id")
            
            # Get moments for this game
            moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
            assert moments_res.status_code == 200, f"Failed to get moments for {game_id}"
            
            moments = moments_res.json().get("moments", [])
            
            if len(moments) == 0:
                games_without_moments.append({
                    "game_id": game_id,
                    "blunders": game.get("blunders", 0),
                    "mistakes": game.get("mistakes", 0)
                })
            else:
                print(f"  ✓ Game {game_id[:8]}... has {len(moments)} qualifying moments")
        
        # Assert no games without moments
        if games_without_moments:
            print(f"\n❌ Found {len(games_without_moments)} games WITHOUT qualifying moments:")
            for g in games_without_moments:
                print(f"   - {g['game_id'][:8]}... (blunders={g['blunders']}, mistakes={g['mistakes']})")
        
        assert len(games_without_moments) == 0, \
            f"Pre-filtering failed: {len(games_without_moments)} games in pending list have no qualifying moments"
        
        print(f"\n✓ All {len(games)} pending games have qualifying moments - pre-filtering works!")
    
    def test_pending_count_matches_games_list(self):
        """
        The count endpoint should return a count that matches actual available games.
        Since both use the same pre-filtering logic, they should be consistent.
        """
        # Get count
        count_res = self.session.get(f"{BASE_URL}/api/reflect/pending/count")
        assert count_res.status_code == 200, f"Count endpoint failed: {count_res.text}"
        count = count_res.json().get("count", -1)
        
        # Get games list
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        assert games_res.status_code == 200, f"Pending endpoint failed: {games_res.text}"
        games = games_res.json().get("games", [])
        
        # Count should match or be greater (count may include more games before limit)
        # The pending endpoint returns up to 5 games, count looks at up to 20
        print(f"Count: {count}, Games returned: {len(games)}")
        
        # If count <= 5, it should match exactly
        if count <= 5:
            assert count == len(games), \
                f"Count ({count}) should match games returned ({len(games)}) when count <= 5"
        else:
            # If count > 5, games should be exactly 5 (the limit)
            assert len(games) == 5, \
                f"Games returned should be 5 (the limit) when count ({count}) > 5"
        
        print(f"✓ Count ({count}) is consistent with games list ({len(games)})")
    
    def test_moments_filtering_rules(self):
        """
        Verify that moments are filtered according to the rules:
        1. Skip opening phase (moves 1-8) unless major blunder (>200 cp)
        2. Only include blunders and mistakes (not inaccuracies)
        3. Require minimum centipawn loss (>50 cp for middlegame)
        4. Skip already-reflected moments
        """
        # Get a game with moments
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        games = games_res.json().get("games", [])
        
        if len(games) == 0:
            pytest.skip("No games available for moments test")
            return
        
        game = games[0]
        game_id = game.get("game_id")
        
        moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        moments = moments_res.json().get("moments", [])
        
        if len(moments) == 0:
            pytest.skip("No moments in first game")
            return
        
        print(f"Checking moments for game {game_id[:8]}...")
        
        for moment in moments:
            move_num = moment.get("move_number", 0)
            cp_loss = moment.get("cp_loss", 0)
            moment_type = moment.get("type", "")
            
            # Verify filtering rules
            # Rule 1: Opening phase filtering
            if move_num <= 8:
                assert cp_loss >= 200, \
                    f"Opening move {move_num} should have cp_loss >= 200, got {cp_loss}"
            else:
                assert cp_loss >= 50, \
                    f"Middlegame move {move_num} should have cp_loss >= 50, got {cp_loss}"
            
            # Rule 2: Only blunders and mistakes
            assert moment_type in ["blunder", "mistake"], \
                f"Moment type should be blunder/mistake, got: {moment_type}"
            
            # Rule 3: Not already reflected
            assert not moment.get("already_reflected", False), \
                "Moment should not be already reflected"
            
            print(f"  ✓ Move {move_num}: {moment_type}, cp_loss={cp_loss}")
        
        print(f"✓ All {len(moments)} moments pass filtering rules")
    
    def test_no_great_game_for_pending_games(self):
        """
        CRITICAL: Games in the pending list should NEVER result in "Great Game!" screen.
        Each game should have at least one qualifying moment.
        """
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        games = games_res.json().get("games", [])
        
        print(f"Checking {len(games)} games for 'Great Game!' prevention...")
        
        great_game_candidates = []
        for game in games:
            game_id = game.get("game_id")
            
            moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
            moments = moments_res.json().get("moments", [])
            
            if len(moments) == 0:
                great_game_candidates.append(game_id)
        
        assert len(great_game_candidates) == 0, \
            f"Found {len(great_game_candidates)} games that would show 'Great Game!': {great_game_candidates}"
        
        print(f"✓ All {len(games)} games have qualifying moments - no 'Great Game!' screens!")


class TestExplainMistakeMateDetection:
    """Test that /api/explain-mistake still correctly detects mate in 1"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login"""
        self.session = requests.Session()
        login_res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_res.status_code == 200, f"Dev login failed: {login_res.text}"
    
    def test_explain_mistake_detects_mate_in_1_qf3(self):
        """
        Test the specific case from iteration 56:
        Move 21 Qf3 allows Qxh2# (mate in 1)
        FEN: 5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21
        """
        payload = {
            "fen_before": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21",
            "move": "Qf3",
            "best_move": "Rf1",  # Or any move that doesn't allow mate
            "cp_loss": 900,  # High loss because it's a mate blunder
            "user_color": "white",
            "move_number": 21
        }
        
        res = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        
        # Verify response structure
        assert "mistake_type" in data, f"Response missing 'mistake_type': {data}"
        assert "explanation" in data, f"Response missing 'explanation': {data}"
        
        # Check that mate in 1 is detected
        print(f"Mistake type: {data.get('mistake_type')}")
        print(f"Severity: {data.get('severity')}")
        print(f"Details: {data.get('details', {})}")
        print(f"Explanation: {data.get('explanation', '')[:200]}...")
        
        # Should detect this as allowing mate in 1
        assert data.get("mistake_type") == "allowed_mate_in_1", \
            f"Expected 'allowed_mate_in_1', got: {data.get('mistake_type')}"
        
        assert data.get("severity") == "decisive", \
            f"Expected 'decisive' severity, got: {data.get('severity')}"
        
        # Verify mating move is in details
        details = data.get("details", {})
        mating_move = details.get("mating_move", "")
        
        # The mating move should be Qxh2# or similar
        assert "Qxh2" in mating_move or "h2" in mating_move, \
            f"Expected mating move Qxh2#, got: {mating_move}"
        
        print(f"\n✓ Mate in 1 (Qf3 allows Qxh2#) correctly detected!")
    
    def test_explain_mistake_returns_thinking_habit_for_mate(self):
        """Verify that thinking_habit is provided for mate-allowing moves"""
        payload = {
            "fen_before": "5r1k/1pp3pp/p7/8/2B2qn1/3Pb3/PP4PP/R2QR2K w - - 1 21",
            "move": "Qf3",
            "best_move": "Rf1",
            "cp_loss": 900,
            "user_color": "white",
            "move_number": 21
        }
        
        res = self.session.post(f"{BASE_URL}/api/explain-mistake", json=payload)
        assert res.status_code == 200
        
        data = res.json()
        
        # Should have a thinking habit for such a critical mistake
        thinking_habit = data.get("thinking_habit")
        assert thinking_habit is not None, "Expected thinking_habit for mate-allowing move"
        assert len(thinking_habit) > 10, f"Thinking habit too short: {thinking_habit}"
        
        print(f"✓ Thinking habit provided: {thinking_habit}")


class TestMomentsQuality:
    """Test the quality and consistency of returned moments"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and login"""
        self.session = requests.Session()
        login_res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_res.status_code == 200
    
    def test_moments_have_required_fields(self):
        """Each moment should have all required fields for reflection"""
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        games = games_res.json().get("games", [])
        
        if len(games) == 0:
            pytest.skip("No games available")
            return
        
        game_id = games[0].get("game_id")
        moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        moments = moments_res.json().get("moments", [])
        
        if len(moments) == 0:
            pytest.skip("No moments in first game")
            return
        
        required_fields = [
            "moment_index", "move_number", "type", "fen",
            "user_move", "best_move", "cp_loss"
        ]
        
        for moment in moments:
            for field in required_fields:
                assert field in moment, f"Moment missing field '{field}': {moment}"
            
            # Validate types
            assert isinstance(moment["moment_index"], int)
            assert isinstance(moment["move_number"], int)
            assert isinstance(moment["fen"], str)
            assert len(moment["fen"]) > 20  # Basic FEN check
        
        print(f"✓ All {len(moments)} moments have required fields")
    
    def test_moments_are_sorted_by_severity(self):
        """Moments should be sorted by cp_loss (most severe first)"""
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        games = games_res.json().get("games", [])
        
        if len(games) == 0:
            pytest.skip("No games available")
            return
        
        game_id = games[0].get("game_id")
        moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        moments = moments_res.json().get("moments", [])
        
        if len(moments) <= 1:
            pytest.skip("Not enough moments to test sorting")
            return
        
        # Check that cp_loss is in descending order
        cp_losses = [m.get("cp_loss", 0) for m in moments]
        print(f"CP losses: {cp_losses}")
        
        for i in range(len(cp_losses) - 1):
            assert cp_losses[i] >= cp_losses[i+1], \
                f"Moments not sorted by severity: {cp_losses[i]} < {cp_losses[i+1]}"
        
        print(f"✓ Moments are sorted by severity (cp_loss)")
    
    def test_max_6_moments_per_game(self):
        """Moments should be limited to top 6 per game"""
        games_res = self.session.get(f"{BASE_URL}/api/reflect/pending")
        games = games_res.json().get("games", [])
        
        for game in games:
            game_id = game.get("game_id")
            moments_res = self.session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
            moments = moments_res.json().get("moments", [])
            
            assert len(moments) <= 6, \
                f"Game {game_id} has {len(moments)} moments, expected max 6"
        
        print(f"✓ All games have at most 6 moments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
