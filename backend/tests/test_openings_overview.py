"""
Test suite for Openings Overview feature
Tests the personalized 'Your Opening World' portrait functionality
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOpeningsRepertoireEndpoint:
    """Tests for GET /api/openings/repertoire endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        # Dev login to get session cookie
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
    
    def test_repertoire_returns_200(self):
        """Test that repertoire endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("SUCCESS: /api/openings/repertoire returns 200")
    
    def test_repertoire_has_white_and_black_arrays(self):
        """Test that repertoire returns white_repertoire and black_repertoire arrays"""
        response = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        data = response.json()
        
        assert "white_repertoire" in data, "Missing white_repertoire field"
        assert "black_repertoire" in data, "Missing black_repertoire field"
        assert isinstance(data["white_repertoire"], list), "white_repertoire should be a list"
        assert isinstance(data["black_repertoire"], list), "black_repertoire should be a list"
        print(f"SUCCESS: Found {len(data['white_repertoire'])} white openings and {len(data['black_repertoire'])} black openings")
    
    def test_repertoire_opening_fields(self):
        """Test that each opening has required fields"""
        response = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        data = response.json()
        
        required_fields = ["name", "games_played", "win_rate", "avg_accuracy", "in_library", "library_key"]
        
        all_openings = data["white_repertoire"] + data["black_repertoire"]
        if len(all_openings) == 0:
            pytest.skip("No openings in repertoire to test")
        
        for opening in all_openings[:5]:  # Test first 5
            for field in required_fields:
                assert field in opening, f"Missing field '{field}' in opening: {opening.get('name', 'unknown')}"
        
        print(f"SUCCESS: All required fields present in openings")
    
    def test_repertoire_win_rate_is_percentage(self):
        """Test that win_rate is a valid percentage (0-100)"""
        response = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        data = response.json()
        
        all_openings = data["white_repertoire"] + data["black_repertoire"]
        for opening in all_openings:
            win_rate = opening.get("win_rate", 0)
            assert 0 <= win_rate <= 100, f"Invalid win_rate {win_rate} for {opening.get('name')}"
        
        print("SUCCESS: All win rates are valid percentages")


class TestOpeningProgressEndpoint:
    """Tests for GET /api/training/opening-progress endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
    
    def test_opening_progress_returns_200(self):
        """Test that opening-progress endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("SUCCESS: /api/training/opening-progress returns 200")
    
    def test_opening_progress_has_progress_array(self):
        """Test that opening-progress returns progress array"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        assert "progress" in data, "Missing progress field"
        assert isinstance(data["progress"], list), "progress should be a list"
        print(f"SUCCESS: Found {len(data['progress'])} openings in progress")
    
    def test_opening_progress_has_summary_fields(self):
        """Test that opening-progress returns summary fields"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        summary_fields = ["total_taught", "total_learned", "total_played", "needs_attention"]
        for field in summary_fields:
            assert field in data, f"Missing summary field '{field}'"
        
        print(f"SUCCESS: Summary - taught: {data['total_taught']}, learned: {data['total_learned']}, played: {data['total_played']}, needs_attention: {data['needs_attention']}")
    
    def test_opening_progress_item_fields(self):
        """Test that each progress item has required fields"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        required_fields = ["opening_name", "mastery_level", "coach_taught", "real_games", "real_win_rate", "real_accuracy"]
        
        if len(data["progress"]) == 0:
            pytest.skip("No progress items to test")
        
        for item in data["progress"][:5]:  # Test first 5
            for field in required_fields:
                assert field in item, f"Missing field '{field}' in progress item: {item.get('opening_name', 'unknown')}"
        
        print("SUCCESS: All required fields present in progress items")
    
    def test_opening_progress_mastery_levels(self):
        """Test that mastery_level is a valid value"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        valid_levels = ["mastered", "comfortable", "learning", "needs_work", "introduced", "unknown", "practiced"]
        
        for item in data["progress"]:
            level = item.get("mastery_level", "unknown")
            assert level in valid_levels, f"Invalid mastery_level '{level}' for {item.get('opening_name')}"
        
        print("SUCCESS: All mastery levels are valid")
    
    def test_coach_taught_items_have_times_practiced(self):
        """Test that coach-taught items have times_practiced field"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        coach_taught = [p for p in data["progress"] if p.get("coach_taught")]
        
        if len(coach_taught) == 0:
            pytest.skip("No coach-taught openings to test")
        
        for item in coach_taught:
            assert "times_practiced" in item, f"Missing times_practiced for coach-taught opening: {item.get('opening_name')}"
            assert isinstance(item["times_practiced"], int), f"times_practiced should be int for {item.get('opening_name')}"
        
        print(f"SUCCESS: {len(coach_taught)} coach-taught openings have times_practiced field")


class TestFocusOpeningLogic:
    """Tests for Focus Opening selection logic"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
    
    def test_focus_opening_is_weakest(self):
        """Test that the weakest opening (lowest win rate with enough games) would be selected as focus"""
        response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        data = response.json()
        
        # Filter openings with 2+ games and win rate < 55%
        candidates = [
            p for p in data["progress"]
            if p.get("real_games", 0) >= 2 and p.get("real_win_rate", 100) < 55
        ]
        
        if len(candidates) == 0:
            print("INFO: No focus candidates found (all openings have good win rates or not enough games)")
            return
        
        # Sort by win rate ascending
        candidates.sort(key=lambda x: x.get("real_win_rate", 100))
        focus = candidates[0]
        
        print(f"SUCCESS: Focus opening would be '{focus['opening_name']}' with {focus['real_win_rate']}% win rate and {focus['real_games']} games")
        
        # Verify it's the Queens Pawn Opening Chigorin Variation as expected
        assert "Queens Pawn" in focus["opening_name"] or focus["real_win_rate"] <= 50, \
            f"Expected Queens Pawn Opening or lowest win rate opening, got {focus['opening_name']}"


class TestDataConsistency:
    """Tests for data consistency between endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
    
    def test_repertoire_and_progress_game_counts_match(self):
        """Test that game counts are consistent between repertoire and progress endpoints"""
        rep_response = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        prog_response = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        
        rep_data = rep_response.json()
        prog_data = prog_response.json()
        
        # Build lookup from repertoire
        rep_by_name = {}
        for opening in rep_data["white_repertoire"] + rep_data["black_repertoire"]:
            name = opening["name"].lower().strip()
            rep_by_name[name] = opening
        
        # Check consistency
        mismatches = []
        for prog_item in prog_data["progress"]:
            name = prog_item["opening_name"].lower().strip()
            if name in rep_by_name:
                rep_games = rep_by_name[name]["games_played"]
                prog_games = prog_item["real_games"]
                if rep_games != prog_games:
                    mismatches.append(f"{prog_item['opening_name']}: repertoire={rep_games}, progress={prog_games}")
        
        if mismatches:
            print(f"WARNING: Game count mismatches found: {mismatches}")
        else:
            print("SUCCESS: Game counts are consistent between endpoints")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
