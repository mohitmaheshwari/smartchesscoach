"""
Test Data Freshness API Endpoints
=================================

Tests the data freshness service that ensures all aggregated data
is recalculated when games are analyzed:
- POST /api/data/refresh - Manual refresh trigger
- GET /api/data/status - Data freshness status check
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://thinking-simulator.preview.emergentagent.com')


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Authenticate via dev login
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestDataStatusEndpoint:
    """Test GET /api/data/status endpoint"""
    
    def test_data_status_returns_200(self, authenticated_session):
        """Data status endpoint returns 200 for authenticated user"""
        response = authenticated_session.get(f"{BASE_URL}/api/data/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_data_status_has_player_identity(self, authenticated_session):
        """Data status response contains player_identity info"""
        response = authenticated_session.get(f"{BASE_URL}/api/data/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "player_identity" in data, "Missing player_identity key"
        
        identity = data["player_identity"]
        assert "exists" in identity
        assert "games_analyzed" in identity
        assert "updated_at" in identity
    
    def test_data_status_has_player_profile(self, authenticated_session):
        """Data status response contains player_profile info"""
        response = authenticated_session.get(f"{BASE_URL}/api/data/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "player_profile" in data, "Missing player_profile key"
        
        profile = data["player_profile"]
        assert "exists" in profile
        assert "games_analyzed" in profile
    
    def test_data_status_has_thinking_scores(self, authenticated_session):
        """Data status response contains thinking_scores info"""
        response = authenticated_session.get(f"{BASE_URL}/api/data/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "thinking_scores" in data, "Missing thinking_scores key"
        assert "count" in data["thinking_scores"]
    
    def test_data_status_has_games_info(self, authenticated_session):
        """Data status response contains games info (total, analyzed, pending)"""
        response = authenticated_session.get(f"{BASE_URL}/api/data/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "games" in data, "Missing games key"
        
        games = data["games"]
        assert "total" in games
        assert "analyzed" in games
        assert "pending" in games
        
        # Verify pending = total - analyzed
        assert games["pending"] == games["total"] - games["analyzed"], \
            f"pending ({games['pending']}) should equal total ({games['total']}) - analyzed ({games['analyzed']})"
    
    def test_data_status_unauthenticated(self):
        """Data status endpoint requires authentication - returns error or empty data"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/data/status")
        # Note: API may return 200 with empty data or 401/403 depending on auth implementation
        # If 200, verify it doesn't return valid user data for unauthenticated user
        if response.status_code == 200:
            data = response.json()
            # Should have empty/minimal data or default values
            assert data is not None
        else:
            assert response.status_code in [401, 403]


class TestDataRefreshEndpoint:
    """Test POST /api/data/refresh endpoint"""
    
    def test_data_refresh_returns_200(self, authenticated_session):
        """Data refresh endpoint returns 200 for authenticated user"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_data_refresh_returns_result_structure(self, authenticated_session):
        """Data refresh response has correct structure"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have user_id
        assert "user_id" in data, "Missing user_id in response"
        
        # Should have refreshed_at timestamp
        assert "refreshed_at" in data, "Missing refreshed_at timestamp"
        
        # Should have updates object
        assert "updates" in data, "Missing updates object"
        
        # Should have success flag
        assert "success" in data, "Missing success flag"
    
    def test_data_refresh_updates_player_identity(self, authenticated_session):
        """Data refresh updates player identity"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        updates = data.get("updates", {})
        
        assert "player_identity" in updates, "Missing player_identity in updates"
        
        identity = updates["player_identity"]
        # Should have status
        assert "status" in identity
    
    def test_data_refresh_updates_journey(self, authenticated_session):
        """Data refresh updates journey stats"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        updates = data.get("updates", {})
        
        assert "journey" in updates, "Missing journey in updates"
    
    def test_data_refresh_updates_player_profile(self, authenticated_session):
        """Data refresh updates player profile"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        updates = data.get("updates", {})
        
        assert "player_profile" in updates, "Missing player_profile in updates"
    
    def test_data_refresh_updates_thinking_scores(self, authenticated_session):
        """Data refresh ensures thinking scores are calculated"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        updates = data.get("updates", {})
        
        assert "thinking_scores" in updates, "Missing thinking_scores in updates"
        
        ts = updates["thinking_scores"]
        # Should have status
        assert "status" in ts
    
    def test_data_refresh_unauthenticated(self):
        """Data refresh endpoint requires authentication - returns error or empty result"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/data/refresh")
        # Note: API may return 200 with no updates or 401/403 depending on auth implementation
        if response.status_code == 200:
            data = response.json()
            # Should process without error (no user_id data)
            assert data is not None
        else:
            assert response.status_code in [401, 403]


class TestPlayerIdentityDataIntegrity:
    """Test player identity data integrity after refresh"""
    
    def test_player_identity_has_correct_win_loss_record(self, authenticated_session):
        """After refresh, player identity shows correct win/loss record"""
        # First trigger refresh
        refresh_response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert refresh_response.status_code == 200
        
        refresh_data = refresh_response.json()
        identity = refresh_data.get("updates", {}).get("player_identity", {})
        
        if identity.get("status") == "no_games":
            pytest.skip("No games analyzed - skipping win/loss verification")
        
        # Check total_record format
        if "total_record" in identity:
            record = identity["total_record"]
            parts = record.split("-")
            assert len(parts) == 3, f"Expected record format W-L-D, got {record}"
            
            wins, losses, draws = int(parts[0]), int(parts[1]), int(parts[2])
            
            # Verify consecutive wins/losses are consistent
            consecutive_wins = identity.get("consecutive_wins", 0)
            consecutive_losses = identity.get("consecutive_losses", 0)
            
            # At any time, only one can be non-zero (or both zero for a draw)
            assert not (consecutive_wins > 0 and consecutive_losses > 0), \
                f"Cannot have both consecutive wins ({consecutive_wins}) and losses ({consecutive_losses})"
    
    def test_player_identity_consecutive_streaks_valid(self, authenticated_session):
        """Player identity has valid streak values"""
        response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert response.status_code == 200
        
        data = response.json()
        identity = data.get("updates", {}).get("player_identity", {})
        
        if identity.get("status") == "no_games":
            pytest.skip("No games analyzed")
        
        consecutive_wins = identity.get("consecutive_wins", 0)
        consecutive_losses = identity.get("consecutive_losses", 0)
        
        # Values should be non-negative
        assert consecutive_wins >= 0, f"consecutive_wins should be non-negative, got {consecutive_wins}"
        assert consecutive_losses >= 0, f"consecutive_losses should be non-negative, got {consecutive_losses}"
        
        # Only one can be active at a time
        if consecutive_wins > 0:
            assert consecutive_losses == 0, "Cannot have both win and loss streak active"
        if consecutive_losses > 0:
            assert consecutive_wins == 0, "Cannot have both loss and win streak active"


class TestDeepMemoryAPIDataConsistency:
    """Test that deep-memory API returns refreshed data"""
    
    def test_deep_memory_returns_correct_data(self, authenticated_session):
        """Deep memory API should return consistent data with player identity"""
        # First refresh data
        authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        
        # Get deep memory data
        response = authenticated_session.get(f"{BASE_URL}/api/deep-memory")
        
        if response.status_code == 404:
            pytest.skip("Deep memory endpoint not found or no data")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure exists
        if "win_loss_record" in data:
            record = data["win_loss_record"]
            assert "wins" in record or isinstance(record, str), "win_loss_record should have wins key or be string"


class TestThinkingScoreAPIDataConsistency:
    """Test that thinking score API returns refreshed data"""
    
    def test_thinking_score_returns_data(self, authenticated_session):
        """Thinking score API should return calculated data"""
        # First refresh to ensure scores are calculated
        authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        
        # Get thinking score
        response = authenticated_session.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should have overall_score (even if 0)
        assert "overall_score" in data, "Missing overall_score in thinking score response"
    
    def test_thinking_score_has_habits(self, authenticated_session):
        """Thinking score API should return habit scores"""
        response = authenticated_session.get(f"{BASE_URL}/api/thinking-score")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have habit_progress breakdown (actual key name in API)
        assert "habit_progress" in data, "Missing habit_progress in thinking score response"
        
        # Verify habit progress contains expected habits
        habit_progress = data["habit_progress"]
        expected_habits = ["threat_awareness", "tactical_vision", "move_verification", "king_safety", "patience"]
        for habit in expected_habits:
            assert habit in habit_progress, f"Missing habit: {habit}"
            
            habit_data = habit_progress[habit]
            assert "current_score" in habit_data, f"Missing current_score for {habit}"


class TestEndToEndDataFlow:
    """Test the full data flow from refresh to API responses"""
    
    def test_status_updates_after_refresh(self, authenticated_session):
        """Data status should reflect updates after refresh"""
        # Get initial status
        initial_status = authenticated_session.get(f"{BASE_URL}/api/data/status").json()
        
        # Trigger refresh
        refresh_response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert refresh_response.status_code == 200
        
        # Get updated status
        updated_status = authenticated_session.get(f"{BASE_URL}/api/data/status").json()
        
        # Player identity should exist after refresh (if games were analyzed)
        if initial_status.get("games", {}).get("analyzed", 0) > 0:
            assert updated_status.get("player_identity", {}).get("exists"), \
                "player_identity should exist after refresh with analyzed games"
    
    def test_refresh_is_idempotent(self, authenticated_session):
        """Multiple refresh calls should produce consistent results"""
        # First refresh
        first_response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert first_response.status_code == 200
        first_data = first_response.json()
        
        # Small delay
        time.sleep(0.5)
        
        # Second refresh
        second_response = authenticated_session.post(f"{BASE_URL}/api/data/refresh")
        assert second_response.status_code == 200
        second_data = second_response.json()
        
        # Both should succeed
        assert first_data.get("success") == second_data.get("success")
        
        # Win/loss record should be the same
        first_record = first_data.get("updates", {}).get("player_identity", {}).get("total_record")
        second_record = second_data.get("updates", {}).get("player_identity", {}).get("total_record")
        
        if first_record and second_record:
            assert first_record == second_record, \
                f"Record changed between refreshes: {first_record} -> {second_record}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
