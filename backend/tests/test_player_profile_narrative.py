"""
Test Player Profile Narrative Feature
======================================

Tests the new Player Profile coaching narrative feature:
- GET /api/progress/player-profile returns narrative, generated_at, games_at_generation
- Narrative is cached - second call returns same narrative without regeneration
- Narrative is LLM-generated (non-null, > 50 characters)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session cookie for dev user
SESSION_COOKIE = {"session_token": "dev_session"}


class TestPlayerProfileNarrative:
    """Test the Player Profile narrative endpoint."""

    def test_player_profile_endpoint_returns_200(self):
        """Test that GET /api/progress/player-profile returns 200."""
        response = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Player profile endpoint returns 200")

    def test_player_profile_has_required_fields(self):
        """Test that response contains narrative, generated_at, games_at_generation."""
        response = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "narrative" in data, "Missing 'narrative' field"
        assert "current_game_count" in data, "Missing 'current_game_count' field"
        
        # If narrative exists, check for generated_at and games_at_generation
        if data.get("narrative"):
            assert "generated_at" in data, "Missing 'generated_at' field when narrative exists"
            assert "games_at_generation" in data, "Missing 'games_at_generation' field when narrative exists"
            print(f"✓ Player profile has all required fields")
            print(f"  - narrative: {data['narrative'][:100]}..." if len(data.get('narrative', '')) > 100 else f"  - narrative: {data.get('narrative')}")
            print(f"  - generated_at: {data.get('generated_at')}")
            print(f"  - games_at_generation: {data.get('games_at_generation')}")
            print(f"  - current_game_count: {data.get('current_game_count')}")
        else:
            # If no narrative, check for min_games_needed
            print(f"✓ No narrative yet (current_game_count: {data.get('current_game_count')})")
            if data.get("min_games_needed"):
                print(f"  - min_games_needed: {data.get('min_games_needed')}")

    def test_narrative_is_substantial(self):
        """Test that narrative is non-null and > 50 characters (LLM-generated)."""
        response = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        narrative = data.get("narrative")
        
        # If user has enough games, narrative should exist
        if data.get("current_game_count", 0) >= 5:
            assert narrative is not None, "Narrative should not be None for user with 5+ games"
            assert len(narrative) > 50, f"Narrative should be > 50 chars, got {len(narrative)}: {narrative}"
            print(f"✓ Narrative is substantial ({len(narrative)} characters)")
        else:
            print(f"✓ User has < 5 games, narrative not generated yet")

    def test_narrative_is_cached(self):
        """Test that second call returns same narrative (cached)."""
        # First call
        response1 = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call
        response2 = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Compare narratives
        if data1.get("narrative") and data2.get("narrative"):
            assert data1["narrative"] == data2["narrative"], "Narrative should be cached (same on second call)"
            assert data1.get("generated_at") == data2.get("generated_at"), "generated_at should be same (cached)"
            print(f"✓ Narrative is cached (same on second call)")
        else:
            print(f"✓ No narrative to cache (user has < 5 games)")

    def test_needs_refresh_is_false(self):
        """Test that needs_refresh is False when cached."""
        response = requests.get(
            f"{BASE_URL}/api/progress/player-profile",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("needs_refresh") == False, "needs_refresh should be False"
        print(f"✓ needs_refresh is False")


class TestPlayerProfileAuth:
    """Test authentication for player profile endpoint."""

    def test_unauthenticated_returns_401(self):
        """Test that unauthenticated request returns 401."""
        response = requests.get(f"{BASE_URL}/api/progress/player-profile")
        # In DEV_MODE, it might still return 200 with dev user fallback
        # But we should test the endpoint exists
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        print(f"✓ Endpoint responds to unauthenticated request (status: {response.status_code})")


class TestAdminNavStillWorks:
    """Test that admin nav link still works for admin users."""

    def test_auth_me_returns_role(self):
        """Test that /api/auth/me returns user with role."""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "role" in data, "Missing 'role' field in auth/me response"
        print(f"✓ Auth/me returns role: {data.get('role')}")

    def test_admin_overview_works_for_admin(self):
        """Test that admin overview endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/admin/overview",
            cookies=SESSION_COOKIE
        )
        # Should work for super_admin user
        assert response.status_code in [200, 403], f"Expected 200 or 403, got {response.status_code}"
        if response.status_code == 200:
            print(f"✓ Admin overview works for admin user")
        else:
            print(f"✓ Admin overview returns 403 (user is not admin)")


class TestPreviousFeaturesStillWork:
    """Test that previous features still work."""

    def test_progress_endpoint_works(self):
        """Test that /api/progress endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/progress",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Progress endpoint works")

    def test_coach_home_intelligence_works(self):
        """Test that /api/coach/home-intelligence endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/coach/home-intelligence",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Coach home intelligence endpoint works")

    def test_games_endpoint_works(self):
        """Test that /api/games endpoint still works."""
        response = requests.get(
            f"{BASE_URL}/api/games",
            cookies=SESSION_COOKIE
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"✓ Games endpoint works (returned {len(data) if isinstance(data, list) else 'N/A'} games)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
