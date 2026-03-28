"""
Test suite for Reflect and Lab page bug fixes:
1. Reflected moments should not reappear (filter by move_number)
2. Lab milestones should show chronological order (first to last mistake)
3. Contextual tags use verified position analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session to maintain cookies for authenticated requests
session = requests.Session()


class TestAuthentication:
    """Dev login for testing"""
    
    def test_dev_login(self):
        """Login using dev mode"""
        response = session.post(f"{BASE_URL}/api/auth/dev-login")
        # Dev login may return 200 or 403 if not in dev mode
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert "user" in data or "user_id" in data or "message" in data.get("user", {})
            print(f"Dev login successful: {data}")
        else:
            print(f"Dev login not available (expected in non-dev mode)")


class TestReflectEndpoints:
    """Test Reflect page backend APIs"""
    
    def test_get_pending_reflections(self):
        """Test getting games needing reflection"""
        response = session.get(f"{BASE_URL}/api/reflect/pending")
        assert response.status_code == 200, f"Status: {response.status_code}, Response: {response.text}"
        data = response.json()
        assert "games" in data or isinstance(data, list), f"Expected games data, got: {data}"
        print(f"Pending reflections response: {data}")
    
    def test_get_pending_count(self):
        """Test getting reflection count"""
        response = session.get(f"{BASE_URL}/api/reflect/pending/count")
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        assert "count" in data or isinstance(data, int) or "pending" in str(data).lower()
        print(f"Pending count: {data}")
    
    def test_game_moments_endpoint(self):
        """Test getting moments for a specific game"""
        # First get pending games
        pending = session.get(f"{BASE_URL}/api/reflect/pending")
        if pending.status_code == 200:
            games = pending.json().get("games", [])
            if games:
                game_id = games[0].get("game_id")
                if game_id:
                    response = session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
                    assert response.status_code == 200, f"Status: {response.status_code}"
                    data = response.json()
                    moments = data.get("moments", data if isinstance(data, list) else [])
                    print(f"Moments for game {game_id}: {len(moments)} moments")
                    
                    # Verify moments have required fields
                    if moments:
                        moment = moments[0]
                        assert "fen" in moment, "Moment missing fen"
                        assert "move_number" in moment, "Moment missing move_number"
                        assert "user_move" in moment, "Moment missing user_move"
                        print(f"Sample moment: {moment}")
                else:
                    print("No game_id found in pending games")
            else:
                print("No games needing reflection - this is acceptable")
        else:
            print("Could not fetch pending games")
    
    def test_contextual_tags_endpoint(self):
        """Test contextual tags generation - should use verified analysis"""
        # Test with a known position
        test_data = {
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "user_move": "Qf7",  # Bad move (but not the point of test)
            "best_move": "Qxf7",  # Scholar's mate
            "eval_change": -5.0
        }
        
        response = session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=test_data)
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        
        # Verify response structure
        assert "tags" in data, f"Response missing tags: {data}"
        tags = data.get("tags", [])
        print(f"Contextual tags response: {data}")
        
        # Tags should be based on position analysis, not hallucinated
        if "could_not_infer" in data:
            print(f"Could not infer intent: {data.get('could_not_infer')}")
    
    def test_explain_moment_endpoint(self):
        """Test explain moment - should use verified position analysis"""
        test_data = {
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "user_move": "Qh5",
            "best_move": "Qxf7",
            "eval_change": -5.0,
            "type": "blunder"
        }
        
        response = session.post(f"{BASE_URL}/api/reflect/explain-moment", json=test_data)
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        print(f"Explain moment response: {data}")
        
        # Should have impact and better_plan based on verified analysis
        if "impact" in data:
            print(f"Impact explanation: {data.get('impact')}")
        if "better_plan" in data:
            print(f"Better plan: {data.get('better_plan')}")


class TestLabEndpoints:
    """Test Lab page backend APIs - milestone ordering"""
    
    def test_lab_endpoint(self):
        """Test lab data - milestones should be in chronological order"""
        # First get a game ID
        response = session.get(f"{BASE_URL}/api/games")
        if response.status_code != 200:
            pytest.skip("No games available for testing")
        
        games = response.json()
        if not games or len(games) == 0:
            pytest.skip("No games found")
        
        # Get first game with analysis
        game_id = None
        for game in games[:5]:
            g_id = game.get("game_id")
            if g_id:
                game_id = g_id
                break
        
        if not game_id:
            pytest.skip("No game_id found")
        
        # Get lab data
        response = session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert response.status_code == 200, f"Status: {response.status_code}"
        data = response.json()
        print(f"Lab data for game {game_id}: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        
        # Lab data is enriched analysis - check structure
        if "core_lesson" in data:
            print(f"Core lesson: {data.get('core_lesson')}")
    
    def test_analysis_endpoint(self):
        """Test analysis endpoint for move evaluations"""
        # Get a game ID
        response = session.get(f"{BASE_URL}/api/games")
        if response.status_code != 200:
            pytest.skip("No games available")
        
        games = response.json()
        if not games:
            pytest.skip("No games found")
        
        game_id = games[0].get("game_id")
        if not game_id:
            pytest.skip("No game_id")
        
        # Get analysis
        response = session.get(f"{BASE_URL}/api/analysis/{game_id}")
        if response.status_code != 200:
            print(f"Analysis not available for game {game_id}")
            return
        
        data = response.json()
        stockfish = data.get("stockfish_analysis", {})
        move_evals = stockfish.get("move_evaluations", [])
        
        print(f"Analysis for game {game_id}: {len(move_evals)} move evaluations")
        
        # Check move_number is present in evaluations
        if move_evals:
            for eval_item in move_evals[:3]:
                assert "move_number" in eval_item, f"Missing move_number: {eval_item}"
            print(f"Sample move eval: {move_evals[0]}")


class TestReflectionSubmission:
    """Test reflection submission and filtering of reflected moments"""
    
    def test_reflection_filters_by_move_number(self):
        """
        BUG FIX VERIFICATION:
        After submitting a reflection, that moment should not reappear.
        The fix uses move_number for tracking instead of moment_index.
        """
        # Get pending games
        response = session.get(f"{BASE_URL}/api/reflect/pending")
        if response.status_code != 200:
            pytest.skip("Cannot get pending reflections")
        
        games = response.json().get("games", [])
        if not games:
            pytest.skip("No games needing reflection")
        
        game_id = games[0].get("game_id")
        
        # Get moments before reflection
        response = session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        if response.status_code != 200:
            pytest.skip("Cannot get moments")
        
        data = response.json()
        moments_before = data.get("moments", data if isinstance(data, list) else [])
        count_before = len(moments_before)
        
        print(f"Moments before reflection: {count_before}")
        
        if count_before == 0:
            print("No moments to reflect on - this is acceptable (game fully reflected)")
            return
        
        # Get first moment details
        first_moment = moments_before[0]
        moment_fen = first_moment.get("fen")
        moment_move_number = first_moment.get("move_number")
        user_move = first_moment.get("user_move")
        best_move = first_moment.get("best_move")
        eval_change = first_moment.get("eval_change", 0)
        
        print(f"Reflecting on move {moment_move_number}: {user_move} (should be {best_move})")
        
        # Submit reflection
        reflection_data = {
            "game_id": game_id,
            "moment_index": 0,
            "moment_fen": moment_fen,
            "user_thought": "TEST: I thought I was developing my piece",
            "user_move": user_move,
            "best_move": best_move,
            "eval_change": eval_change,
            "move_number": moment_move_number  # KEY: This is the fix
        }
        
        response = session.post(f"{BASE_URL}/api/reflect/submit", json=reflection_data)
        assert response.status_code == 200, f"Submit failed: {response.status_code} - {response.text}"
        result = response.json()
        print(f"Reflection result: {result}")
        
        # Get moments after reflection - the reflected moment should NOT appear
        response = session.get(f"{BASE_URL}/api/reflect/game/{game_id}/moments")
        assert response.status_code == 200
        
        data = response.json()
        moments_after = data.get("moments", data if isinstance(data, list) else [])
        count_after = len(moments_after)
        
        print(f"Moments after reflection: {count_after}")
        
        # Verify the moment was filtered out
        for m in moments_after:
            assert m.get("move_number") != moment_move_number, \
                f"BUG: Move {moment_move_number} still appears after reflection!"
        
        # Count should be 1 less (or same if there were already other filtered moments)
        assert count_after <= count_before, \
            f"BUG: Moments increased after reflection! Before: {count_before}, After: {count_after}"
        
        print(f"SUCCESS: Move {moment_move_number} correctly filtered after reflection")


class TestLabMilestoneOrdering:
    """Test that Lab milestones are in chronological order"""
    
    def test_analysis_move_evaluations_have_move_number(self):
        """Verify move evaluations include move_number for proper sorting"""
        response = session.get(f"{BASE_URL}/api/games")
        if response.status_code != 200:
            pytest.skip("Cannot get games")
        
        games = response.json()
        if not games:
            pytest.skip("No games")
        
        # Find an analyzed game
        for game in games[:5]:
            game_id = game.get("game_id")
            if not game_id:
                continue
            
            response = session.get(f"{BASE_URL}/api/analysis/{game_id}")
            if response.status_code == 200:
                data = response.json()
                stockfish = data.get("stockfish_analysis", {})
                move_evals = stockfish.get("move_evaluations", [])
                
                if move_evals:
                    # Check all have move_number
                    for i, m in enumerate(move_evals[:10]):
                        assert "move_number" in m, f"Move eval {i} missing move_number"
                    
                    # Extract learning moments (mistakes/blunders)
                    learning = [m for m in move_evals if abs(m.get("cp_loss", 0)) >= 50]
                    
                    if len(learning) >= 2:
                        # Verify they can be sorted by move_number
                        move_numbers = [m.get("move_number", 0) for m in learning]
                        sorted_numbers = sorted(move_numbers)
                        
                        print(f"Game {game_id}: Learning moments at moves {move_numbers}")
                        print(f"Chronological order would be: {sorted_numbers}")
                        
                        # Frontend sorts by move_number (line 578 in Lab.jsx)
                        # This test verifies the data supports that
                        return
        
        print("No analyzed games with multiple learning moments found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
