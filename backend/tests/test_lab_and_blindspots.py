"""
Test Lab and Blind Spots API Endpoints

Tests:
- /api/lab/{gameId} - Lab data with turning_point
- /api/blind-spots - User blind spots

Testing key fields:
- turning_point: move_uci, best_move_uci, category, missed_idea, how_to_spot
- biggest_blunder: move_uci, best_move_uci 
- blind_spots: category, count, patterns, severity
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test game ID with known data
TEST_GAME_ID = "cb946acd-7871-4d38-a704-6c3ccbe968c5"


class TestLabEndpoint:
    """Tests for /api/lab/{gameId} endpoint"""
    
    def test_lab_endpoint_returns_200(self):
        """Lab endpoint should return 200 for valid game"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Lab endpoint returns 200")
    
    def test_lab_returns_turning_point(self):
        """Lab should return turning_point with required fields"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        assert response.status_code == 200
        
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist in response"
        print(f"PASS: turning_point exists with move_number={tp.get('move_number')}")
    
    def test_turning_point_has_move_uci(self):
        """Turning point should have move_uci field for arrow display"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "move_uci" in tp, "turning_point should have move_uci field"
        assert tp["move_uci"], f"move_uci should not be empty, got: {tp.get('move_uci')}"
        print(f"PASS: turning_point.move_uci = {tp['move_uci']}")
    
    def test_turning_point_has_best_move_uci(self):
        """Turning point should have best_move_uci field for arrow display"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "best_move_uci" in tp, "turning_point should have best_move_uci field"
        assert tp["best_move_uci"], f"best_move_uci should not be empty, got: {tp.get('best_move_uci')}"
        print(f"PASS: turning_point.best_move_uci = {tp['best_move_uci']}")
    
    def test_turning_point_has_category(self):
        """Turning point should have category for pattern tracking"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "category" in tp, "turning_point should have category field"
        assert tp["category"], f"category should not be empty"
        print(f"PASS: turning_point.category = {tp['category']}")
    
    def test_turning_point_has_category_label(self):
        """Turning point should have category_label for display"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "category_label" in tp, "turning_point should have category_label field"
        print(f"PASS: turning_point.category_label = {tp.get('category_label')}")
    
    def test_turning_point_has_missed_idea(self):
        """Turning point should have missed_idea explanation"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "missed_idea" in tp, "turning_point should have missed_idea field"
        print(f"PASS: turning_point.missed_idea exists")
    
    def test_turning_point_has_how_to_spot(self):
        """Turning point should have how_to_spot array"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        tp = data.get("turning_point")
        
        assert tp is not None, "turning_point should exist"
        assert "how_to_spot" in tp, "turning_point should have how_to_spot field"
        how_to_spot = tp.get("how_to_spot", [])
        assert isinstance(how_to_spot, list), "how_to_spot should be a list"
        print(f"PASS: turning_point.how_to_spot has {len(how_to_spot)} items")
    
    def test_lab_returns_biggest_blunder(self):
        """Lab should return biggest_blunder with UCI moves"""
        response = requests.get(f"{BASE_URL}/api/lab/{TEST_GAME_ID}")
        data = response.json()
        
        bb = data.get("biggest_blunder")
        assert bb is not None, "biggest_blunder should exist"
        
        assert "move_uci" in bb, "biggest_blunder should have move_uci"
        assert "best_move_uci" in bb, "biggest_blunder should have best_move_uci"
        
        print(f"PASS: biggest_blunder move_uci={bb.get('move_uci')}, best_move_uci={bb.get('best_move_uci')}")


class TestBlindSpotsEndpoint:
    """Tests for /api/blind-spots endpoint"""
    
    def test_blind_spots_returns_200(self):
        """Blind spots endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Blind spots endpoint returns 200")
    
    def test_blind_spots_returns_array(self):
        """Should return blind_spots array"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        assert "blind_spots" in data, "Response should have blind_spots field"
        assert isinstance(data["blind_spots"], list), "blind_spots should be a list"
        print(f"PASS: blind_spots array has {len(data['blind_spots'])} items")
    
    def test_blind_spot_has_category(self):
        """Each blind spot should have category"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        spots = data.get("blind_spots", [])
        if spots:
            spot = spots[0]
            assert "category" in spot, "Blind spot should have category"
            assert "label" in spot, "Blind spot should have label"
            print(f"PASS: First blind spot category={spot['category']}, label={spot['label']}")
        else:
            print("SKIP: No blind spots in response")
    
    def test_blind_spot_has_count(self):
        """Each blind spot should have count"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        spots = data.get("blind_spots", [])
        if spots:
            spot = spots[0]
            assert "count" in spot, "Blind spot should have count"
            assert isinstance(spot["count"], int), "count should be an integer"
            print(f"PASS: First blind spot count={spot['count']}")
        else:
            print("SKIP: No blind spots in response")
    
    def test_blind_spot_has_patterns(self):
        """Each blind spot should have patterns array"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        spots = data.get("blind_spots", [])
        if spots:
            spot = spots[0]
            assert "patterns" in spot, "Blind spot should have patterns"
            assert isinstance(spot["patterns"], list), "patterns should be a list"
            print(f"PASS: First blind spot has {len(spot['patterns'])} patterns")
        else:
            print("SKIP: No blind spots in response")
    
    def test_blind_spot_has_severity(self):
        """Each blind spot should have severity"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        spots = data.get("blind_spots", [])
        if spots:
            spot = spots[0]
            assert "severity" in spot, "Blind spot should have severity"
            assert spot["severity"] in ["high", "medium", "low"], f"Invalid severity: {spot['severity']}"
            print(f"PASS: First blind spot severity={spot['severity']}")
        else:
            print("SKIP: No blind spots in response")
    
    def test_blind_spots_has_totals(self):
        """Response should have total_games_analyzed and games_with_turning_points"""
        response = requests.get(f"{BASE_URL}/api/blind-spots")
        data = response.json()
        
        assert "total_games_analyzed" in data, "Should have total_games_analyzed"
        assert "games_with_turning_points" in data, "Should have games_with_turning_points"
        print(f"PASS: total_games={data['total_games_analyzed']}, with_turning_points={data['games_with_turning_points']}")


class TestExplainMistakeEndpoint:
    """Tests for /api/explain-mistake endpoint (used by Biggest Blunder explain)"""
    
    def test_explain_mistake_endpoint_exists(self):
        """Explain mistake POST endpoint should work"""
        payload = {
            "fen_before": "3r1bkr/2pq2pp/8/2p1N1p1/2Q1R3/8/PPP3PP/R5K1 b - - 4 21",
            "move": "Qf7",
            "best_move": "Qd5",
            "cp_loss": 9509,
            "user_color": "black",
            "move_number": 21
        }
        
        response = requests.post(
            f"{BASE_URL}/api/explain-mistake",
            json=payload
        )
        
        # Should return 200 (may return explanation or fallback)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASS: explain-mistake returns 200")
    
    def test_explain_mistake_returns_explanation(self):
        """Explain mistake should return explanation field"""
        payload = {
            "fen_before": "3r1bkr/2pq2pp/8/2p1N1p1/2Q1R3/8/PPP3PP/R5K1 b - - 4 21",
            "move": "Qf7",
            "best_move": "Qd5",
            "cp_loss": 500,
            "user_color": "black",
            "move_number": 21
        }
        
        response = requests.post(
            f"{BASE_URL}/api/explain-mistake",
            json=payload
        )
        
        data = response.json()
        assert "explanation" in data or "mistake_type" in data, "Response should have explanation or mistake_type"
        print(f"PASS: explain-mistake returns data structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
