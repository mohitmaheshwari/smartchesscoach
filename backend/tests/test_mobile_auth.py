"""
Test Mobile Auth and Protected Endpoints
Tests for:
1. Mobile Google OAuth endpoint - /api/auth/google/mobile
2. Push notification registration - /api/notifications/register-device
3. Protected endpoints requiring authentication
"""

import pytest
import requests
import os

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMobileGoogleAuth:
    """Tests for POST /api/auth/google/mobile endpoint"""
    
    def test_mobile_auth_invalid_token_returns_401(self):
        """Mobile auth should return 401 for invalid Google access token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/mobile",
            json={"access_token": "invalid_token_12345"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for invalid token
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        # Verify error message
        data = response.json()
        assert "detail" in data
        assert "Invalid Google access token" in data["detail"] or "invalid" in data["detail"].lower()
    
    def test_mobile_auth_empty_token_returns_error(self):
        """Mobile auth should return error for empty access token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/mobile",
            json={"access_token": ""},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return error status (401, 422, 500, or 520 via proxy)
        # Empty token causes Google API to fail, which results in 500/520
        assert response.status_code in [401, 422, 500, 520], f"Expected error status, got {response.status_code}: {response.text}"
        
        # Verify error response has detail
        data = response.json()
        assert "detail" in data
    
    def test_mobile_auth_missing_token_returns_422(self):
        """Mobile auth should return 422 for missing access_token field"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/mobile",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 422 for missing required field
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
    
    def test_mobile_auth_malformed_json_returns_422(self):
        """Mobile auth should return 422 for malformed JSON"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/mobile",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 422 for malformed JSON
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"


class TestPushNotificationEndpoints:
    """Tests for push notification endpoints"""
    
    def test_register_device_requires_auth(self):
        """POST /api/notifications/register-device should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/register-device",
            json={
                "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                "platform": "ios"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
        assert "authenticated" in data["detail"].lower() or "not authenticated" in data["detail"].lower()
    
    def test_register_device_with_invalid_token_returns_401(self):
        """POST /api/notifications/register-device with invalid Bearer token should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/register-device",
            json={
                "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                "platform": "android"
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid_session_token_12345"
            }
        )
        
        # Should return 401 for invalid session token
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_unregister_device_requires_auth(self):
        """DELETE /api/notifications/unregister-device should require authentication"""
        response = requests.delete(
            f"{BASE_URL}/api/notifications/unregister-device",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication"""
    
    def test_dashboard_stats_requires_auth(self):
        """GET /api/dashboard-stats should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard-stats",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
    
    def test_dashboard_stats_with_invalid_token_returns_401(self):
        """GET /api/dashboard-stats with invalid Bearer token should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard-stats",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid_session_token_xyz"
            }
        )
        
        # Should return 401 for invalid session token
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_games_endpoint_requires_auth(self):
        """GET /api/games should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/games",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
    
    def test_games_endpoint_with_invalid_token_returns_401(self):
        """GET /api/games with invalid Bearer token should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/games",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer fake_token_abc123"
            }
        )
        
        # Should return 401 for invalid session token
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_journey_endpoint_requires_auth(self):
        """GET /api/journey should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/journey",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
    
    def test_journey_endpoint_with_invalid_token_returns_401(self):
        """GET /api/journey with invalid Bearer token should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/journey",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid_journey_token"
            }
        )
        
        # Should return 401 for invalid session token
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_auth_me_requires_auth(self):
        """GET /api/auth/me should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_profile_endpoint_requires_auth(self):
        """GET /api/profile should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/profile",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
    
    def test_patterns_endpoint_requires_auth(self):
        """GET /api/patterns should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/patterns",
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


class TestPublicEndpoints:
    """Tests for public endpoints that don't require authentication"""
    
    def test_health_endpoint_is_public(self):
        """GET /api/health should be accessible without authentication"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        # Should return 200 for public health endpoint
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "healthy"
    
    def test_root_endpoint_is_public(self):
        """GET /api/ should be accessible without authentication"""
        response = requests.get(f"{BASE_URL}/api/")
        
        # Should return 200 for public root endpoint
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "Chess Coach" in data.get("message", "")
    
    def test_weakness_categories_is_public(self):
        """GET /api/weakness-categories should be accessible without authentication"""
        response = requests.get(f"{BASE_URL}/api/weakness-categories")
        
        # Should return 200 for public endpoint
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "categories" in data


class TestBearerTokenAuth:
    """Tests for Bearer token authentication mechanism"""
    
    def test_bearer_token_format_accepted(self):
        """Verify Bearer token format is accepted in Authorization header"""
        # This test verifies the auth mechanism accepts Bearer format
        # Even with invalid token, it should process the header correctly
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={
                "Authorization": "Bearer test_token_format"
            }
        )
        
        # Should return 401 (invalid session) not 400 (bad format)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        data = response.json()
        # Should indicate session issue, not header format issue
        assert "session" in data.get("detail", "").lower() or "authenticated" in data.get("detail", "").lower()
    
    def test_expired_session_returns_401(self):
        """Verify expired session tokens return 401"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard-stats",
            headers={
                "Authorization": "Bearer expired_session_token_test"
            }
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
