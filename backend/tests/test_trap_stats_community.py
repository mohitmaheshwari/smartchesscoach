"""
Test Trap Statistics Tracking and Community Learning Features

Tests:
1. Trap Statistics - Record attempt API
2. Trap Statistics - Get user stats API
3. Trap Statistics - Get recommendations API
4. Community Learning - Share puzzle API
5. Community Learning - Get puzzles API
6. Community Learning - Attempt puzzle API
7. Community Learning - Get stats API
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "test_session_356539ff12b1"

@pytest.fixture
def auth_headers():
    """Authenticated session headers."""
    return {
        "Content-Type": "application/json",
        "Cookie": f"session_token={SESSION_TOKEN}"
    }


class TestTrapStatisticsAPI:
    """Test Trap Statistics Tracking APIs"""
    
    def test_record_trap_attempt_success(self, auth_headers):
        """Test recording a successful trap attempt"""
        response = requests.post(
            f"{BASE_URL}/api/training/tricks/record-attempt",
            headers=auth_headers,
            json={
                "trap_key": "scholars_mate",
                "mode": "execution",
                "success": True,
                "details": {"test": True}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "recorded" in data
        assert data["recorded"] == True
        print(f"✅ Record attempt - Success: {data}")
    
    def test_record_trap_attempt_failure(self, auth_headers):
        """Test recording a failed trap attempt"""
        response = requests.post(
            f"{BASE_URL}/api/training/tricks/record-attempt",
            headers=auth_headers,
            json={
                "trap_key": "legal_trap",
                "mode": "avoidance",
                "success": False,
                "details": {"move": "Bxf7"}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["recorded"] == True
        print(f"✅ Record attempt - Failure recorded: {data}")
    
    def test_record_trap_attempt_recognition_mode(self, auth_headers):
        """Test recording a recognition mode attempt"""
        response = requests.post(
            f"{BASE_URL}/api/training/tricks/record-attempt",
            headers=auth_headers,
            json={
                "trap_key": "fried_liver",
                "mode": "recognition",
                "success": True,
                "details": {"score": "perfect"}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["recorded"] == True
        print(f"✅ Record recognition attempt: {data}")
    
    def test_record_attempt_invalid_mode(self, auth_headers):
        """Test that invalid mode returns error"""
        response = requests.post(
            f"{BASE_URL}/api/training/tricks/record-attempt",
            headers=auth_headers,
            json={
                "trap_key": "scholars_mate",
                "mode": "invalid_mode",
                "success": True
            }
        )
        assert response.status_code == 400, f"Expected 400 for invalid mode, got {response.status_code}"
        print(f"✅ Invalid mode rejected correctly")
    
    def test_record_attempt_missing_fields(self, auth_headers):
        """Test that missing fields return error"""
        response = requests.post(
            f"{BASE_URL}/api/training/tricks/record-attempt",
            headers=auth_headers,
            json={
                "trap_key": "scholars_mate"
                # Missing mode and success
            }
        )
        assert response.status_code == 400, f"Expected 400 for missing fields, got {response.status_code}"
        print(f"✅ Missing fields rejected correctly")
    
    def test_get_user_trap_stats(self, auth_headers):
        """Test getting user's trap statistics"""
        response = requests.get(
            f"{BASE_URL}/api/training/tricks/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total_attempts" in data, "Missing total_attempts in response"
        assert "total_successes" in data, "Missing total_successes in response"
        assert "success_rate" in data, "Missing success_rate in response"
        assert "traps" in data, "Missing traps in response"
        
        print(f"✅ Get user stats: {data['total_attempts']} attempts, {data['success_rate']}% success rate")
        print(f"   Traps tracked: {len(data['traps'])} trap stats")
        
        # Verify we have some stats from our recording attempts
        assert isinstance(data["total_attempts"], int)
        assert isinstance(data["success_rate"], (int, float))
    
    def test_get_trap_recommendations(self, auth_headers):
        """Test getting trap recommendations"""
        response = requests.get(
            f"{BASE_URL}/api/training/tricks/recommendations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "recommendations" in data, "Missing recommendations in response"
        recommendations = data["recommendations"]
        assert isinstance(recommendations, list), "Recommendations should be a list"
        
        print(f"✅ Get recommendations: {len(recommendations)} traps recommended")
        
        # Verify recommendation structure if any exist
        if len(recommendations) > 0:
            rec = recommendations[0]
            assert "trap_key" in rec, "Missing trap_key in recommendation"
            assert "name" in rec, "Missing name in recommendation"
            assert "reason" in rec, "Missing reason in recommendation"
            assert "priority" in rec, "Missing priority in recommendation"
            print(f"   First recommendation: {rec['name']} - {rec['reason']}")


class TestCommunityLearningAPI:
    """Test Community Learning APIs"""
    
    def test_get_community_puzzles(self, auth_headers):
        """Test getting community puzzles list"""
        response = requests.get(
            f"{BASE_URL}/api/community/puzzles",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "puzzles" in data, "Missing puzzles in response"
        assert "total" in data, "Missing total count in response"
        assert isinstance(data["puzzles"], list), "Puzzles should be a list"
        
        print(f"✅ Get community puzzles: {data['total']} total, {len(data['puzzles'])} returned")
        
        # Verify puzzle structure if any exist
        if len(data["puzzles"]) > 0:
            puzzle = data["puzzles"][0]
            assert "puzzle_id" in puzzle, "Missing puzzle_id"
            assert "fen" in puzzle, "Missing fen"
            assert "best_move_san" in puzzle, "Missing best_move_san"
            assert "difficulty" in puzzle, "Missing difficulty"
            print(f"   First puzzle: {puzzle['puzzle_id']} - {puzzle['difficulty']} difficulty")
    
    def test_get_community_puzzles_with_filters(self, auth_headers):
        """Test filtering community puzzles"""
        response = requests.get(
            f"{BASE_URL}/api/community/puzzles?difficulty=intermediate&sort_by=newest",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "puzzles" in data
        print(f"✅ Get filtered puzzles: {len(data['puzzles'])} intermediate puzzles")
    
    def test_get_community_stats(self, auth_headers):
        """Test getting community statistics"""
        response = requests.get(
            f"{BASE_URL}/api/community/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "total_puzzles" in data, "Missing total_puzzles"
        assert "total_attempts" in data, "Missing total_attempts"
        assert "overall_solve_rate" in data, "Missing overall_solve_rate"
        
        print(f"✅ Get community stats: {data['total_puzzles']} puzzles, {data['total_attempts']} attempts, {data['overall_solve_rate']}% solve rate")
    
    def test_share_puzzle(self, auth_headers):
        """Test sharing a new puzzle"""
        unique_fen = f"r1bqkbnr/pppp1ppp/2n5/4p3/{uuid.uuid4().hex[:8]}/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        response = requests.post(
            f"{BASE_URL}/api/community/puzzles/share",
            headers=auth_headers,
            json={
                "fen": unique_fen,
                "best_move_san": "Nf3",
                "issue_type": "development",
                "difficulty": "beginner",
                "theme": "tactical",
                "description": "Test puzzle"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data or "puzzle_id" in data, "Missing success indicator in response"
        print(f"✅ Share puzzle: {data}")
        
        return data.get("puzzle_id")
    
    def test_share_puzzle_missing_fields(self, auth_headers):
        """Test sharing puzzle with missing required fields"""
        response = requests.post(
            f"{BASE_URL}/api/community/puzzles/share",
            headers=auth_headers,
            json={
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                # Missing best_move_san and issue_type
            }
        )
        assert response.status_code == 400, f"Expected 400 for missing fields, got {response.status_code}"
        print(f"✅ Missing fields rejected correctly")
    
    def test_attempt_community_puzzle(self, auth_headers):
        """Test attempting to solve a community puzzle"""
        # First get puzzles to find one to attempt
        get_response = requests.get(
            f"{BASE_URL}/api/community/puzzles",
            headers=auth_headers
        )
        
        if get_response.status_code == 200:
            data = get_response.json()
            if len(data["puzzles"]) > 0:
                puzzle = data["puzzles"][0]
                puzzle_id = puzzle["puzzle_id"]
                correct_move = puzzle["best_move_san"]
                
                # Test with correct answer
                response = requests.post(
                    f"{BASE_URL}/api/community/puzzles/{puzzle_id}/attempt",
                    headers=auth_headers,
                    json={"user_move": correct_move}
                )
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
                result = response.json()
                
                assert "correct" in result, "Missing correct indicator"
                assert "message" in result, "Missing message"
                print(f"✅ Attempt puzzle {puzzle_id}: correct={result['correct']}, {result['message']}")
            else:
                print("⚠️ No puzzles to attempt - skipping attempt test")
                pytest.skip("No community puzzles available")
        else:
            pytest.skip("Could not fetch puzzles")
    
    def test_attempt_puzzle_wrong_answer(self, auth_headers):
        """Test attempting puzzle with wrong answer"""
        # Get puzzles
        get_response = requests.get(
            f"{BASE_URL}/api/community/puzzles",
            headers=auth_headers
        )
        
        if get_response.status_code == 200:
            data = get_response.json()
            if len(data["puzzles"]) > 0:
                puzzle = data["puzzles"][0]
                puzzle_id = puzzle["puzzle_id"]
                
                # Test with wrong answer
                response = requests.post(
                    f"{BASE_URL}/api/community/puzzles/{puzzle_id}/attempt",
                    headers=auth_headers,
                    json={"user_move": "a3"}  # Usually wrong move
                )
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
                result = response.json()
                
                assert "correct" in result
                assert "expected_move" in result, "Should show expected move on wrong answer"
                print(f"✅ Wrong answer handled: expected={result['expected_move']}")
            else:
                pytest.skip("No community puzzles available")
        else:
            pytest.skip("Could not fetch puzzles")
    
    def test_attempt_invalid_puzzle_id(self, auth_headers):
        """Test attempting non-existent puzzle"""
        response = requests.post(
            f"{BASE_URL}/api/community/puzzles/invalid_id_123/attempt",
            headers=auth_headers,
            json={"user_move": "e4"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid ID, got {response.status_code}"
        print(f"✅ Invalid puzzle ID rejected correctly")
    
    def test_rate_puzzle_valid_rating(self, auth_headers):
        """Test rating a community puzzle"""
        # Get puzzles
        get_response = requests.get(
            f"{BASE_URL}/api/community/puzzles",
            headers=auth_headers
        )
        
        if get_response.status_code == 200:
            data = get_response.json()
            if len(data["puzzles"]) > 0:
                puzzle_id = data["puzzles"][0]["puzzle_id"]
                
                # Test rating
                response = requests.post(
                    f"{BASE_URL}/api/community/puzzles/{puzzle_id}/rate",
                    headers=auth_headers,
                    json={"rating": 4}
                )
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
                result = response.json()
                
                assert "success" in result or "avg_rating" in result
                print(f"✅ Rate puzzle: {result}")
            else:
                pytest.skip("No community puzzles available")
        else:
            pytest.skip("Could not fetch puzzles")
    
    def test_rate_puzzle_invalid_rating(self, auth_headers):
        """Test rating with invalid value"""
        get_response = requests.get(
            f"{BASE_URL}/api/community/puzzles",
            headers=auth_headers
        )
        
        if get_response.status_code == 200:
            data = get_response.json()
            if len(data["puzzles"]) > 0:
                puzzle_id = data["puzzles"][0]["puzzle_id"]
                
                # Test invalid rating
                response = requests.post(
                    f"{BASE_URL}/api/community/puzzles/{puzzle_id}/rate",
                    headers=auth_headers,
                    json={"rating": 10}  # Invalid - should be 1-5
                )
                assert response.status_code == 400, f"Expected 400 for invalid rating, got {response.status_code}"
                print(f"✅ Invalid rating rejected correctly")
            else:
                pytest.skip("No community puzzles available")
        else:
            pytest.skip("Could not fetch puzzles")


class TestTrapStatsUIData:
    """Test data returned for UI display"""
    
    def test_stats_has_weakest_and_strongest(self, auth_headers):
        """Test that stats include weakest and strongest traps for UI"""
        response = requests.get(
            f"{BASE_URL}/api/training/tricks/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # These fields are expected by the UI
        assert "weakest_traps" in data, "Missing weakest_traps for 'Areas to Improve' section"
        assert "strongest_traps" in data, "Missing strongest_traps for 'Your Strengths' section"
        assert "recent_activity" in data, "Missing recent_activity for 'Recent Activity' section"
        
        print(f"✅ Stats has UI fields: weakest_traps={len(data['weakest_traps'])}, strongest_traps={len(data['strongest_traps'])}, recent={len(data['recent_activity'])}")
    
    def test_recommendations_have_priority(self, auth_headers):
        """Test that recommendations include priority for UI badges"""
        response = requests.get(
            f"{BASE_URL}/api/training/tricks/recommendations",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data["recommendations"]) > 0:
            rec = data["recommendations"][0]
            assert "priority" in rec, "Missing priority field for UI badge"
            assert rec["priority"] in ["high", "medium", "low"], f"Invalid priority: {rec['priority']}"
            print(f"✅ Recommendations have priority field: {rec['priority']}")
        else:
            print("⚠️ No recommendations to test priority")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
