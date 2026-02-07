"""
Test Coach Light Stats, Last Game Summary, and Game Termination Features
Tests the coach mode dashboard light stats, termination reason display, and opponent extraction
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user with existing games and analyses
TEST_EMAIL = "bhutramohit@gmail.com"
TEST_GAME_ID = "23b95148-52f9-4c38-b540-54236c123442"


@pytest.fixture(scope="module")
def session_token():
    """Get session token via demo login"""
    response = requests.post(
        f"{BASE_URL}/api/auth/demo-login",
        json={"email": TEST_EMAIL}
    )
    assert response.status_code == 200, f"Demo login failed: {response.text}"
    data = response.json()
    assert "session_token" in data, "No session_token in response"
    return data["session_token"]


@pytest.fixture
def auth_headers(session_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {session_token}"}


class TestLightStats:
    """Light Stats verification - 3 stats with trends"""

    def test_coach_today_returns_light_stats(self, auth_headers):
        """Verify /api/coach/today returns light_stats array"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "light_stats" in data, "light_stats not in response"
        assert "has_data" in data, "has_data not in response"

    def test_light_stats_has_three_items(self, auth_headers):
        """Verify light_stats contains exactly 3 stats"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        light_stats = data.get("light_stats", [])
        assert len(light_stats) == 3, f"Expected 3 stats, got {len(light_stats)}: {light_stats}"

    def test_blunders_per_game_stat(self, auth_headers):
        """Verify Blunders/game stat exists with correct format"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        light_stats = data.get("light_stats", [])
        blunder_stat = next((s for s in light_stats if "Blunders" in s.get("label", "")), None)
        
        assert blunder_stat is not None, "Blunders/game stat not found"
        assert "value" in blunder_stat, "Blunders stat missing value"
        assert "trend" in blunder_stat, "Blunders stat missing trend"
        assert blunder_stat["trend"] in ["up", "down", "stable"], f"Invalid trend: {blunder_stat['trend']}"

    def test_rating_30d_stat(self, auth_headers):
        """Verify Rating (30d) stat exists with correct format"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        light_stats = data.get("light_stats", [])
        rating_stat = next((s for s in light_stats if "Rating" in s.get("label", "")), None)
        
        assert rating_stat is not None, "Rating (30d) stat not found"
        assert "value" in rating_stat, "Rating stat missing value"
        assert "trend" in rating_stat, "Rating stat missing trend"
        # Value should be a number (rating)
        assert rating_stat["value"].isdigit(), f"Rating value should be numeric: {rating_stat['value']}"

    def test_reflection_success_stat(self, auth_headers):
        """Verify Reflection success stat exists with correct format"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        light_stats = data.get("light_stats", [])
        reflection_stat = next((s for s in light_stats if "Reflection" in s.get("label", "")), None)
        
        assert reflection_stat is not None, "Reflection success stat not found"
        assert "value" in reflection_stat, "Reflection stat missing value"
        assert "trend" in reflection_stat, "Reflection stat missing trend"
        # Value should be in format X/Y
        assert "/" in reflection_stat["value"], f"Reflection value should be X/Y format: {reflection_stat['value']}"


class TestLastGameSummary:
    """Last Game Summary verification - opponent name and termination"""

    def test_last_game_exists(self, auth_headers):
        """Verify last_game is present in coach/today"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        assert "last_game" in data, "last_game not in response"
        assert data["last_game"] is not None, "last_game is null"

    def test_last_game_has_opponent(self, auth_headers):
        """Verify last_game includes opponent name"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        last_game = data.get("last_game", {})
        assert "opponent" in last_game, "opponent not in last_game"
        assert last_game["opponent"], "opponent is empty"
        assert last_game["opponent"] != "Opponent", f"Opponent not extracted from PGN: {last_game['opponent']}"

    def test_last_game_has_termination(self, auth_headers):
        """Verify last_game includes termination reason (e.g., 'lost on time')"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        last_game = data.get("last_game", {})
        assert "termination" in last_game, "termination not in last_game"
        # Termination should be human readable like "lost on time", "resigned", etc.
        termination = last_game.get("termination", "")
        assert termination, "termination is empty"
        print(f"Termination: {termination}")

    def test_last_game_has_result(self, auth_headers):
        """Verify last_game includes result (Won/Lost/Draw)"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        last_game = data.get("last_game", {})
        assert "result" in last_game, "result not in last_game"
        assert last_game["result"] in ["Won", "Lost", "Draw"], f"Invalid result: {last_game['result']}"

    def test_last_game_has_stats(self, auth_headers):
        """Verify last_game includes stats (blunders, mistakes)"""
        response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        data = response.json()
        
        last_game = data.get("last_game", {})
        assert "stats" in last_game, "stats not in last_game"
        
        stats = last_game.get("stats", {})
        assert "blunders" in stats, "blunders not in stats"
        assert "mistakes" in stats, "mistakes not in stats"


class TestGameTermination:
    """Game Analysis Page termination display verification"""

    def test_game_endpoint_returns_termination_text(self, auth_headers):
        """Verify /api/games/{game_id} returns termination_text field"""
        response = requests.get(f"{BASE_URL}/api/games/{TEST_GAME_ID}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "termination_text" in data, "termination_text not in game response"

    def test_game_termination_text_is_human_readable(self, auth_headers):
        """Verify termination_text is a human readable string"""
        response = requests.get(f"{BASE_URL}/api/games/{TEST_GAME_ID}", headers=auth_headers)
        data = response.json()
        
        termination_text = data.get("termination_text", "")
        assert termination_text, "termination_text is empty"
        # Should be something like "You won", "You lost on time", etc.
        assert any(word in termination_text.lower() for word in ["won", "lost", "draw", "resigned", "time"]), \
            f"termination_text doesn't look human readable: {termination_text}"

    def test_game_has_player_names(self, auth_headers):
        """Verify game endpoint returns correct player names"""
        response = requests.get(f"{BASE_URL}/api/games/{TEST_GAME_ID}", headers=auth_headers)
        data = response.json()
        
        assert "white_player" in data, "white_player not in response"
        assert "black_player" in data, "black_player not in response"
        assert data["white_player"] != "White", "white_player not extracted from PGN"
        assert data["black_player"] != "Black", "black_player not extracted from PGN"


class TestCoachEndSession:
    """Coach end-session opponent extraction verification"""

    def test_end_session_returns_opponent(self, auth_headers):
        """Verify /api/coach/end-session extracts opponent from PGN"""
        # First start a session
        start_response = requests.post(
            f"{BASE_URL}/api/coach/start-session",
            headers=auth_headers,
            json={"platform": "chess.com"}
        )
        assert start_response.status_code == 200
        
        # Then end it to get opponent extraction
        end_response = requests.post(
            f"{BASE_URL}/api/coach/end-session",
            headers=auth_headers
        )
        assert end_response.status_code == 200
        
        data = end_response.json()
        # Should have opponent field (extracted from PGN)
        if data.get("status") in ["already_analyzed", "analyzing"]:
            assert "opponent" in data, "opponent not in end-session response"
            assert data["opponent"] != "Opponent", f"Opponent not extracted from PGN: {data['opponent']}"
            print(f"Opponent extracted: {data['opponent']}")

    def test_end_session_returns_feedback(self, auth_headers):
        """Verify /api/coach/end-session returns feedback"""
        # Start session
        requests.post(
            f"{BASE_URL}/api/coach/start-session",
            headers=auth_headers,
            json={"platform": "chess.com"}
        )
        
        # End session
        end_response = requests.post(
            f"{BASE_URL}/api/coach/end-session",
            headers=auth_headers
        )
        data = end_response.json()
        
        if data.get("status") == "already_analyzed":
            assert "feedback" in data, "feedback not in response for already analyzed game"
            feedback = data.get("feedback", {})
            assert "type" in feedback, "feedback missing type"
            assert "message" in feedback, "feedback missing message"


class TestIntegration:
    """Integration tests for the full flow"""

    def test_full_coach_flow(self, auth_headers):
        """Test the complete coach mode flow"""
        # 1. Get coach/today data
        today_response = requests.get(f"{BASE_URL}/api/coach/today", headers=auth_headers)
        assert today_response.status_code == 200
        today_data = today_response.json()
        
        # 2. Verify light stats
        assert len(today_data.get("light_stats", [])) == 3
        
        # 3. Verify last game has termination
        last_game = today_data.get("last_game", {})
        if last_game:
            assert last_game.get("opponent")
            assert last_game.get("termination")
        
        # 4. Get game details and verify termination_text
        if last_game and last_game.get("game_id"):
            game_response = requests.get(
                f"{BASE_URL}/api/games/{last_game['game_id']}",
                headers=auth_headers
            )
            if game_response.status_code == 200:
                game_data = game_response.json()
                assert "termination_text" in game_data
                print(f"Game termination_text: {game_data.get('termination_text')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
