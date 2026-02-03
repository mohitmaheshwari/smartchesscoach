"""
Test Rating Trajectory and Training Endpoints

Tests for:
1. GET /api/rating/trajectory - Rating prediction with projections
2. GET /api/training/time-management - Time management analysis
3. GET /api/training/fast-thinking - Calculation analysis
4. GET /api/training/puzzles - Personalized puzzles
5. POST /api/training/puzzles/{index}/solve - Record puzzle attempts
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRatingTrajectoryAuth:
    """Test authentication requirements for rating/trajectory endpoint"""
    
    def test_rating_trajectory_requires_auth(self):
        """GET /api/rating/trajectory should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/rating/trajectory")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/rating/trajectory requires authentication (returns 401)")
    
    def test_rating_trajectory_invalid_token(self):
        """GET /api/rating/trajectory should return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/rating/trajectory",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/rating/trajectory returns 401 for invalid Bearer token")


class TestTimeManagementAuth:
    """Test authentication requirements for time-management endpoint"""
    
    def test_time_management_requires_auth(self):
        """GET /api/training/time-management should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/training/time-management")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/time-management requires authentication (returns 401)")
    
    def test_time_management_invalid_token(self):
        """GET /api/training/time-management should return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/training/time-management",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/time-management returns 401 for invalid Bearer token")


class TestFastThinkingAuth:
    """Test authentication requirements for fast-thinking endpoint"""
    
    def test_fast_thinking_requires_auth(self):
        """GET /api/training/fast-thinking should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/training/fast-thinking")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/fast-thinking requires authentication (returns 401)")
    
    def test_fast_thinking_invalid_token(self):
        """GET /api/training/fast-thinking should return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/training/fast-thinking",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/fast-thinking returns 401 for invalid Bearer token")


class TestPuzzlesAuth:
    """Test authentication requirements for puzzles endpoints"""
    
    def test_puzzles_requires_auth(self):
        """GET /api/training/puzzles should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/training/puzzles")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/puzzles requires authentication (returns 401)")
    
    def test_puzzles_invalid_token(self):
        """GET /api/training/puzzles should return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/training/puzzles",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training/puzzles returns 401 for invalid Bearer token")
    
    def test_puzzle_solve_requires_auth(self):
        """POST /api/training/puzzles/{index}/solve should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/training/puzzles/0/solve",
            params={"solution": "Nf3", "time_taken_seconds": 30}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/training/puzzles/{index}/solve requires authentication (returns 401)")
    
    def test_puzzle_solve_invalid_token(self):
        """POST /api/training/puzzles/{index}/solve should return 401 with invalid token"""
        response = requests.post(
            f"{BASE_URL}/api/training/puzzles/0/solve",
            params={"solution": "Nf3", "time_taken_seconds": 30},
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/training/puzzles/{index}/solve returns 401 for invalid Bearer token")


class TestTrainingRecommendationsAuth:
    """Test authentication requirements for training-recommendations endpoint"""
    
    def test_training_recommendations_requires_auth(self):
        """GET /api/training-recommendations should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/training-recommendations")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/training-recommendations requires authentication (returns 401)")


class TestHealthEndpoint:
    """Verify health endpoint is still accessible"""
    
    def test_health_endpoint_accessible(self):
        """GET /api/health should be publicly accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy status, got {data}"
        print("✓ GET /api/health is publicly accessible (returns 200)")


class TestRatingServiceFunctions:
    """Test rating service functions via API (requires auth for full test)"""
    
    def test_api_endpoint_exists(self):
        """Verify rating/trajectory endpoint exists (returns 401, not 404)"""
        response = requests.get(f"{BASE_URL}/api/rating/trajectory")
        # Should return 401 (auth required), not 404 (not found)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/rating/trajectory endpoint exists (returns 401, not 404)")
    
    def test_time_management_endpoint_exists(self):
        """Verify training/time-management endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/training/time-management")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/training/time-management endpoint exists (returns 401, not 404)")
    
    def test_fast_thinking_endpoint_exists(self):
        """Verify training/fast-thinking endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/training/fast-thinking")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/training/fast-thinking endpoint exists (returns 401, not 404)")
    
    def test_puzzles_endpoint_exists(self):
        """Verify training/puzzles endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/training/puzzles")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/training/puzzles endpoint exists (returns 401, not 404)")
    
    def test_puzzle_solve_endpoint_exists(self):
        """Verify training/puzzles/{index}/solve endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/training/puzzles/0/solve",
            params={"solution": "e4", "time_taken_seconds": 10}
        )
        # Should return 401 (auth required), not 404 (not found)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/training/puzzles/{index}/solve endpoint exists (returns 401, not 404)")


class TestPuzzlesQueryParams:
    """Test puzzles endpoint query parameters"""
    
    def test_puzzles_count_param_accepted(self):
        """Verify count query parameter is accepted (even without auth)"""
        response = requests.get(f"{BASE_URL}/api/training/puzzles?count=10")
        # Should return 401 (auth required), not 422 (validation error)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/training/puzzles accepts count query parameter")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
