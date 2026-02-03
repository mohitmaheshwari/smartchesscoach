"""
Journey Dashboard API Tests
Tests for:
- GET /api/journey - Journey dashboard data (requires auth)
- GET /api/journey/linked-accounts - Linked accounts (requires auth)
- POST /api/journey/link-account - Link Chess.com/Lichess accounts (requires auth)
- POST /api/journey/sync-now - Manual game sync (requires auth)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasic:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint returns healthy status")
    
    def test_root_endpoint(self):
        """Test /api/ returns Chess Coach API message"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Chess Coach API"
        print("✓ Root endpoint returns correct message")


class TestJourneyEndpointsAuth:
    """Test Journey endpoints require authentication"""
    
    def test_journey_requires_auth(self):
        """GET /api/journey returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/journey")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "authenticated" in data["detail"].lower() or "not authenticated" in data["detail"].lower()
        print("✓ GET /api/journey returns 401 for unauthenticated requests")
    
    def test_linked_accounts_requires_auth(self):
        """GET /api/journey/linked-accounts returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/journey/linked-accounts")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print("✓ GET /api/journey/linked-accounts returns 401 for unauthenticated requests")
    
    def test_link_account_requires_auth(self):
        """POST /api/journey/link-account returns 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/journey/link-account",
            json={"platform": "chess.com", "username": "testuser"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print("✓ POST /api/journey/link-account returns 401 for unauthenticated requests")
    
    def test_sync_now_requires_auth(self):
        """POST /api/journey/sync-now returns 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/journey/sync-now")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print("✓ POST /api/journey/sync-now returns 401 for unauthenticated requests")


class TestOtherProtectedEndpoints:
    """Test other protected endpoints for auth"""
    
    def test_games_requires_auth(self):
        """GET /api/games returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 401
        print("✓ GET /api/games returns 401")
    
    def test_patterns_requires_auth(self):
        """GET /api/patterns returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        assert response.status_code == 401
        print("✓ GET /api/patterns returns 401")
    
    def test_profile_requires_auth(self):
        """GET /api/profile returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/profile")
        assert response.status_code == 401
        print("✓ GET /api/profile returns 401")
    
    def test_dashboard_stats_requires_auth(self):
        """GET /api/dashboard-stats returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 401
        print("✓ GET /api/dashboard-stats returns 401")


class TestPublicEndpoints:
    """Test public endpoints that don't require auth"""
    
    def test_weakness_categories_public(self):
        """GET /api/weakness-categories is public"""
        response = requests.get(f"{BASE_URL}/api/weakness-categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        print(f"✓ GET /api/weakness-categories returns {len(data['categories'])} categories")


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_auth_me_requires_session(self):
        """GET /api/auth/me returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ GET /api/auth/me returns 401 without session")
    
    def test_auth_session_requires_session_id(self):
        """POST /api/auth/session requires session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={}
        )
        assert response.status_code == 400
        data = response.json()
        assert "session_id" in data.get("detail", "").lower()
        print("✓ POST /api/auth/session requires session_id parameter")
    
    def test_auth_logout_works(self):
        """POST /api/auth/logout works without session"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ POST /api/auth/logout works correctly")


class TestLinkAccountValidation:
    """Test link-account endpoint validation (would work with auth)"""
    
    def test_link_account_invalid_platform_format(self):
        """POST /api/journey/link-account validates platform"""
        # This will return 401 first, but we're testing the endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/journey/link-account",
            json={"platform": "invalid_platform", "username": "testuser"}
        )
        # Should return 401 (auth required) before validation
        assert response.status_code == 401
        print("✓ POST /api/journey/link-account endpoint exists and requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
