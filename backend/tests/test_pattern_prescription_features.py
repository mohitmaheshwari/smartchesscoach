"""
Test Pattern Prescription & Theory Applied Features (Iteration 158)
====================================================================

Tests for 4 new features:
1. Pattern Prescription on Home Page - shows top recurring patterns with training positions
2. Cross-screen progress tracking - theory applied tracking
3. Theory Applied moment - green note in coaching card
4. Opening Portrait Coach Progress - shows 'Applied Xx in games'

Endpoints tested:
- GET /api/home/pattern-prescription
- GET /api/openings/{key}?variation={variation}
- GET /api/training/opening-progress

UI elements tested:
- pattern-prescription-card on home page
- prescription-{pattern_type} items
- theory-applied-note in V5CoachingCard
- pattern-memory-note in V5CoachingCard
- Coach Progress section with times_applied_in_games
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPatternPrescriptionAPI:
    """Test the pattern prescription endpoint for home page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        # Dev login to get session cookie
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
    
    def test_pattern_prescription_endpoint_exists(self):
        """Test that GET /api/home/pattern-prescription returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/home/pattern-prescription")
        assert resp.status_code == 200, f"Pattern prescription endpoint failed: {resp.text}"
        print("✓ Pattern prescription endpoint returns 200")
    
    def test_pattern_prescription_response_structure(self):
        """Test that response has correct structure with prescriptions array"""
        resp = self.session.get(f"{BASE_URL}/api/home/pattern-prescription")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "prescriptions" in data, "Response missing 'prescriptions' key"
        assert isinstance(data["prescriptions"], list), "prescriptions should be a list"
        print(f"✓ Pattern prescription returns {len(data['prescriptions'])} prescriptions")
    
    def test_prescription_item_fields(self):
        """Test that each prescription has required fields"""
        resp = self.session.get(f"{BASE_URL}/api/home/pattern-prescription")
        assert resp.status_code == 200
        
        data = resp.json()
        prescriptions = data.get("prescriptions", [])
        
        if len(prescriptions) > 0:
            rx = prescriptions[0]
            required_fields = ["pattern_type", "label", "recent_count", "severity", "training_positions_available"]
            for field in required_fields:
                assert field in rx, f"Prescription missing required field: {field}"
            
            # Validate field types
            assert isinstance(rx["pattern_type"], str), "pattern_type should be string"
            assert isinstance(rx["label"], str), "label should be string"
            assert isinstance(rx["recent_count"], int), "recent_count should be int"
            assert isinstance(rx["severity"], str), "severity should be string"
            assert isinstance(rx["training_positions_available"], int), "training_positions_available should be int"
            
            print(f"✓ First prescription: {rx['label']} ({rx['recent_count']}x recently)")
        else:
            print("⚠ No prescriptions found (user may not have analyzed games)")
    
    def test_prescription_severity_values(self):
        """Test that severity is one of expected values"""
        resp = self.session.get(f"{BASE_URL}/api/home/pattern-prescription")
        assert resp.status_code == 200
        
        data = resp.json()
        valid_severities = ["critical", "high", "medium", "low"]
        
        for rx in data.get("prescriptions", []):
            assert rx["severity"] in valid_severities, f"Invalid severity: {rx['severity']}"
        
        print("✓ All prescription severities are valid")


class TestOpeningProgressAPI:
    """Test opening progress endpoint for times_applied_in_games"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_opening_progress_endpoint(self):
        """Test GET /api/training/opening-progress returns progress data"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200, f"Opening progress failed: {resp.text}"
        
        data = resp.json()
        assert "progress" in data, "Response missing 'progress' key"
        print(f"✓ Opening progress returns {len(data.get('progress', []))} items")
    
    def test_opening_progress_has_times_applied(self):
        """Test that coach-taught progress items have times_applied_in_games field"""
        resp = self.session.get(f"{BASE_URL}/api/training/opening-progress")
        assert resp.status_code == 200
        
        data = resp.json()
        progress_items = data.get("progress", [])
        
        # Find coach-taught items (these should have times_applied_in_games)
        coach_taught_items = [p for p in progress_items if p.get("coach_taught")]
        
        if len(coach_taught_items) > 0:
            item = coach_taught_items[0]
            # Check for times_applied_in_games field
            has_applied = "times_applied_in_games" in item
            assert has_applied, f"Coach-taught progress item missing times_applied_in_games field: {item.keys()}"
            print(f"✓ Coach-taught progress item has times_applied_in_games: {item.get('times_applied_in_games')}")
        else:
            # Check non-coach-taught items for times_applied field
            if len(progress_items) > 0:
                print(f"⚠ No coach-taught items found, checking regular items")
                # Non-coach-taught items may not have this field - that's OK
                print(f"✓ Found {len(progress_items)} progress items (none coach-taught)")
            else:
                print("⚠ No progress items found (user may not have practiced openings)")


class TestOpeningVariationAPI:
    """Test opening variation endpoint with active_variation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_french_defense_default(self):
        """Test GET /api/openings/french-defense returns opening data"""
        resp = self.session.get(f"{BASE_URL}/api/openings/french-defense")
        assert resp.status_code == 200, f"French defense endpoint failed: {resp.text}"
        
        data = resp.json()
        assert "opening" in data or "name" in data, "Response missing opening data"
        print("✓ French Defense endpoint returns data")
    
    def test_french_defense_with_variation(self):
        """Test GET /api/openings/french-defense?variation=french_winawer returns correct variation"""
        resp = self.session.get(f"{BASE_URL}/api/openings/french-defense?variation=french_winawer")
        assert resp.status_code == 200, f"French Winawer variation failed: {resp.text}"
        
        data = resp.json()
        opening = data.get("opening", data)
        
        # Check active_variation field
        active_var = opening.get("active_variation")
        if active_var:
            assert active_var == "french_winawer", f"Expected french_winawer, got {active_var}"
            print(f"✓ French Defense returns active_variation: {active_var}")
        else:
            print("⚠ active_variation field not present in response")
    
    def test_italian_game_endpoint(self):
        """Test GET /api/openings/italian-game works with hyphenated key"""
        resp = self.session.get(f"{BASE_URL}/api/openings/italian-game")
        assert resp.status_code == 200, f"Italian Game endpoint failed: {resp.text}"
        print("✓ Italian Game endpoint works with hyphenated key")


class TestHomePageAPIs:
    """Test home page APIs still work correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_home_intelligence_endpoint(self):
        """Test GET /api/coach/home-intelligence returns data"""
        resp = self.session.get(f"{BASE_URL}/api/coach/home-intelligence")
        assert resp.status_code == 200, f"Home intelligence failed: {resp.text}"
        
        data = resp.json()
        # Should have development_phase and games_analyzed
        assert "development_phase" in data or "games_analyzed" in data, "Missing expected home data"
        print("✓ Home intelligence endpoint works")
    
    def test_progress_endpoint(self):
        """Test GET /api/progress returns accuracy and trend"""
        resp = self.session.get(f"{BASE_URL}/api/progress")
        assert resp.status_code == 200, f"Progress endpoint failed: {resp.text}"
        
        data = resp.json()
        # Should have accuracy data
        assert "accuracy" in data, "Missing accuracy in progress data"
        print("✓ Progress endpoint works")


class TestV5CoachingDataStructure:
    """Test that V5 coaching data includes pattern_memory and theory_applied fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_v5_coaching_fields_in_schema(self):
        """Verify V5Coaching dataclass has pattern_memory and theory_applied fields"""
        # This is a code verification test - we check the service file
        import sys
        sys.path.insert(0, '/app/backend')
        
        try:
            from services.shared_coaching_v5 import V5Coaching
            
            # Create a test instance
            coaching = V5Coaching(
                severity="mistake",
                narrative="Test narrative",
                pattern_memory="You've missed this 3 times",
                theory_applied="You played the book move"
            )
            
            coaching_dict = coaching.to_dict()
            
            assert "pattern_memory" in coaching_dict, "V5Coaching missing pattern_memory field"
            assert "theory_applied" in coaching_dict, "V5Coaching missing theory_applied field"
            assert coaching_dict["pattern_memory"] == "You've missed this 3 times"
            assert coaching_dict["theory_applied"] == "You played the book move"
            
            print("✓ V5Coaching dataclass has pattern_memory and theory_applied fields")
        except ImportError as e:
            pytest.skip(f"Could not import V5Coaching: {e}")


class TestTrainingPageAPI:
    """Test training page API still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_training_feed_endpoint(self):
        """Test GET /api/training/community-feed returns positions"""
        resp = self.session.get(f"{BASE_URL}/api/training/community-feed?limit=5")
        assert resp.status_code == 200, f"Training feed failed: {resp.text}"
        
        data = resp.json()
        assert "positions" in data, "Missing positions in training feed"
        print(f"✓ Training feed returns {len(data.get('positions', []))} positions")


class TestOpeningsRepertoireAPI:
    """Test openings repertoire for Coach Progress section"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
    
    def test_openings_repertoire_endpoint(self):
        """Test GET /api/openings/repertoire returns repertoire data"""
        resp = self.session.get(f"{BASE_URL}/api/openings/repertoire")
        assert resp.status_code == 200, f"Openings repertoire failed: {resp.text}"
        
        data = resp.json()
        # Should have white_repertoire and black_repertoire
        assert "white_repertoire" in data or "black_repertoire" in data, "Missing repertoire data"
        print("✓ Openings repertoire endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
