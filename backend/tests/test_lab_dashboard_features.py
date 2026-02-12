"""
Test Lab Page and Dashboard Enhancements
- Dashboard: opponent names, ratings, filter functionality
- Lab page: game data with player names/ratings
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardFeatures:
    """Tests for Dashboard opponent names, ratings, and filter"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        # Dev login
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        
    def test_dashboard_stats_returns_opponent_data(self):
        """Test that dashboard-stats returns white_player, black_player, white_rating, black_rating"""
        resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert resp.status_code == 200, f"Dashboard stats failed: {resp.text}"
        
        data = resp.json()
        
        # Verify structure
        assert "recent_games" in data, "Missing recent_games in response"
        assert "total_games" in data, "Missing total_games"
        assert "profile_summary" in data, "Missing profile_summary"
        
        # Check recent games have player data
        recent_games = data["recent_games"]
        assert len(recent_games) > 0, "No recent games found"
        
        for game in recent_games:
            assert "white_player" in game, f"Missing white_player in game {game.get('game_id')}"
            assert "black_player" in game, f"Missing black_player in game {game.get('game_id')}"
            # Ratings may not always be present but fields should exist if PGN has them
            if game.get("white_rating"):
                assert isinstance(game["white_rating"], int), "white_rating should be int"
            if game.get("black_rating"):
                assert isinstance(game["black_rating"], int), "black_rating should be int"
    
    def test_dashboard_stats_profile_has_elo(self):
        """Test that profile_summary includes estimated_elo for filter functionality"""
        resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert resp.status_code == 200
        
        data = resp.json()
        profile = data.get("profile_summary", {})
        
        # Profile should have estimated_elo for filtering stronger/weaker opponents
        assert "estimated_elo" in profile, "Missing estimated_elo in profile_summary"
        assert isinstance(profile["estimated_elo"], (int, float)), "estimated_elo should be numeric"
    
    def test_dashboard_opponent_display_format(self):
        """Test that opponent data is in correct format for display"""
        resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert resp.status_code == 200
        
        data = resp.json()
        recent_games = data.get("recent_games", [])
        
        # Verify we can derive opponent info
        for game in recent_games[:3]:
            user_color = game.get("user_color")
            assert user_color in ["white", "black"], f"Invalid user_color: {user_color}"
            
            # Opponent is the other player
            if user_color == "white":
                opponent = game.get("black_player")
                opponent_rating = game.get("black_rating")
            else:
                opponent = game.get("white_player")
                opponent_rating = game.get("white_rating")
            
            assert opponent is not None, "Could not derive opponent name"
            print(f"Game: vs {opponent} ({opponent_rating})")


class TestLabPageAPI:
    """Tests for Lab page game data API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
        
    def test_game_endpoint_returns_player_names(self):
        """Test that /games/{game_id} returns player names and ratings"""
        # Get a game ID first
        stats = self.session.get(f"{BASE_URL}/api/dashboard-stats").json()
        games = stats.get("recent_games", [])
        assert len(games) > 0, "No games to test"
        
        game_id = games[0]["game_id"]
        
        # Get specific game
        resp = self.session.get(f"{BASE_URL}/api/games/{game_id}")
        assert resp.status_code == 200, f"Failed to get game: {resp.text}"
        
        game = resp.json()
        
        # Verify player data
        assert "white_player" in game, "Missing white_player"
        assert "black_player" in game, "Missing black_player"
        assert "user_color" in game, "Missing user_color"
        assert "result" in game, "Missing result"
        
        # Ratings extracted from PGN
        if game.get("white_rating"):
            assert isinstance(game["white_rating"], int)
        if game.get("black_rating"):
            assert isinstance(game["black_rating"], int)
    
    def test_lab_specific_game_f17df20c(self):
        """Test the specific game mentioned in the task: f17df20c-8ecb-4bfb-8600-c9f6512a6b12"""
        game_id = "f17df20c-8ecb-4bfb-8600-c9f6512a6b12"
        
        resp = self.session.get(f"{BASE_URL}/api/games/{game_id}")
        assert resp.status_code == 200, f"Failed to get test game: {resp.text}"
        
        game = resp.json()
        
        # Verify expected values per task
        assert game.get("white_player") == "SamoRendlev", f"Expected SamoRendlev, got {game.get('white_player')}"
        assert game.get("user_color") == "black", f"Expected black, got {game.get('user_color')}"
        assert game.get("white_rating") == 1303, f"Expected 1303, got {game.get('white_rating')}"
        assert game.get("is_analyzed") == True, "Game should be analyzed"
        
        # Result should be 0-1 (user won as black)
        assert game.get("result") == "0-1", f"Expected 0-1, got {game.get('result')}"
        
    def test_analysis_endpoint_exists(self):
        """Test that analysis endpoint returns data for analyzed games"""
        game_id = "f17df20c-8ecb-4bfb-8600-c9f6512a6b12"
        
        resp = self.session.get(f"{BASE_URL}/api/analysis/{game_id}")
        assert resp.status_code == 200, f"Analysis endpoint failed: {resp.text}"
        
        analysis = resp.json()
        
        # Should have stockfish analysis with accuracy
        assert "stockfish_analysis" in analysis or "accuracy" in analysis, "Missing analysis data"


class TestFilterFunctionality:
    """Tests verifying filter data is available"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_games_have_ratings_for_filtering(self):
        """Test that games have rating data needed for stronger/equal/weaker filter"""
        resp = self.session.get(f"{BASE_URL}/api/dashboard-stats")
        assert resp.status_code == 200
        
        data = resp.json()
        user_rating = data.get("profile_summary", {}).get("estimated_elo", 1200)
        games = data.get("recent_games", [])
        
        games_with_opponent_rating = 0
        for game in games:
            user_color = game.get("user_color")
            opponent_rating = game.get("black_rating") if user_color == "white" else game.get("white_rating")
            
            if opponent_rating:
                games_with_opponent_rating += 1
                # Calculate rating diff
                diff = opponent_rating - user_rating
                
                # This is what frontend uses for filtering
                if diff > 50:
                    category = "stronger"
                elif diff < -50:
                    category = "weaker"
                else:
                    category = "equal"
                
                print(f"Game vs rating {opponent_rating}: user {user_rating}, diff={diff}, category={category}")
        
        # Most games should have ratings
        assert games_with_opponent_rating > 0, "No games have opponent ratings for filtering"
        print(f"{games_with_opponent_rating}/{len(games)} games have opponent ratings")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
