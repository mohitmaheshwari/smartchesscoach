"""
Backend API Tests for AI Chess Coach - Journey Dashboard Feature
Tests: Journey API endpoints, Auth flow, and basic API health
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasicEndpoints:
    """Test basic API health and root endpoints"""
    
    def test_api_health(self):
        """Test /api/health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("SUCCESS: /api/health returns healthy status")
    
    def test_api_root(self):
        """Test /api/ root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Chess Coach API"
        print("SUCCESS: /api/ returns correct message")


class TestAuthEndpoints:
    """Test authentication endpoints - unauthenticated flows"""
    
    def test_auth_me_requires_authentication(self):
        """Test /api/auth/me returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not authenticated"
        print("SUCCESS: /api/auth/me correctly returns 401 for unauthenticated requests")
    
    def test_auth_session_requires_session_id(self):
        """Test /api/auth/session requires session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "session_id" in data["detail"].lower()
        print("SUCCESS: /api/auth/session correctly requires session_id")
    
    def test_auth_logout_works_without_session(self):
        """Test /api/auth/logout works even without active session"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("SUCCESS: /api/auth/logout works correctly")


class TestJourneyEndpoints:
    """Test Journey Dashboard API endpoints - unauthenticated flows"""
    
    def test_journey_requires_authentication(self):
        """Test GET /api/journey returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/journey")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not authenticated"
        print("SUCCESS: /api/journey correctly returns 401 for unauthenticated requests")
    
    def test_journey_linked_accounts_requires_authentication(self):
        """Test GET /api/journey/linked-accounts returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/journey/linked-accounts")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not authenticated"
        print("SUCCESS: /api/journey/linked-accounts correctly returns 401 for unauthenticated requests")
    
    def test_journey_link_account_requires_authentication(self):
        """Test POST /api/journey/link-account returns 401 without session"""
        response = requests.post(
            f"{BASE_URL}/api/journey/link-account",
            json={"platform": "chess.com", "username": "testuser"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not authenticated"
        print("SUCCESS: /api/journey/link-account correctly returns 401 for unauthenticated requests")
    
    def test_journey_sync_now_requires_authentication(self):
        """Test POST /api/journey/sync-now returns 401 without session"""
        response = requests.post(f"{BASE_URL}/api/journey/sync-now")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not authenticated"
        print("SUCCESS: /api/journey/sync-now correctly returns 401 for unauthenticated requests")


class TestProtectedEndpoints:
    """Test other protected endpoints require authentication"""
    
    def test_games_requires_authentication(self):
        """Test GET /api/games returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/games")
        assert response.status_code == 401
        print("SUCCESS: /api/games correctly returns 401")
    
    def test_patterns_requires_authentication(self):
        """Test GET /api/patterns returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        assert response.status_code == 401
        print("SUCCESS: /api/patterns correctly returns 401")
    
    def test_profile_requires_authentication(self):
        """Test GET /api/profile returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/profile")
        assert response.status_code == 401
        print("SUCCESS: /api/profile correctly returns 401")
    
    def test_dashboard_stats_requires_authentication(self):
        """Test GET /api/dashboard-stats returns 401 without session"""
        response = requests.get(f"{BASE_URL}/api/dashboard-stats")
        assert response.status_code == 401
        print("SUCCESS: /api/dashboard-stats correctly returns 401")
    
    def test_import_games_requires_authentication(self):
        """Test POST /api/import-games returns 401 without session"""
        response = requests.post(
            f"{BASE_URL}/api/import-games",
            json={"platform": "chess.com", "username": "testuser"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        print("SUCCESS: /api/import-games correctly returns 401")
    
    def test_connect_platform_requires_authentication(self):
        """Test POST /api/connect-platform returns 401 without session"""
        response = requests.post(
            f"{BASE_URL}/api/connect-platform",
            json={"platform": "chess.com", "username": "testuser"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
        print("SUCCESS: /api/connect-platform correctly returns 401")


class TestWeaknessCategoriesEndpoint:
    """Test weakness categories endpoint - public endpoint"""
    
    def test_weakness_categories_is_public(self):
        """Test GET /api/weakness-categories is accessible without auth"""
        response = requests.get(f"{BASE_URL}/api/weakness-categories")
        # This endpoint might be public or protected
        if response.status_code == 200:
            data = response.json()
            assert "categories" in data
            print(f"SUCCESS: /api/weakness-categories returns categories: {len(data['categories'])} categories found")
        elif response.status_code == 401:
            print("INFO: /api/weakness-categories requires authentication")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
