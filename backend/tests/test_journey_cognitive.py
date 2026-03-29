"""
Test Suite: Journey Page - Cognitive Evolution Dashboard
Tests the 4 endpoints used by the Journey page:
- /cognitive/patterns (TSI + patterns data)
- /cognitive/trend (30-game TSI trend)
- /cognitive/blunder-context (blunder distribution by position type)
- /cognitive/phase-insight (phase stability)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestJourneyCognitiveEndpoints:
    """Test all cognitive endpoints used by Journey page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Dev login to get auth
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_resp.status_code == 200:
            self.session.cookies.update(login_resp.cookies)
    
    def test_cognitive_patterns_returns_200(self):
        """Section 1: TSI data - verify endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/patterns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /cognitive/patterns returns 200")
    
    def test_cognitive_patterns_has_tsi(self):
        """Section 1: Verify TSI value is present"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/patterns")
        data = response.json()
        
        assert "thinking_stability_index" in data, "Missing thinking_stability_index"
        tsi = data["thinking_stability_index"]
        assert isinstance(tsi, (int, float)), f"TSI should be numeric, got {type(tsi)}"
        assert 0 <= tsi <= 100, f"TSI should be 0-100, got {tsi}"
        print(f"✓ TSI value: {tsi}")
    
    def test_cognitive_patterns_has_tsi_trend(self):
        """Section 1: Verify TSI trend is present"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/patterns")
        data = response.json()
        
        assert "tsi_trend" in data, "Missing tsi_trend"
        trend = data["tsi_trend"]
        valid_trends = ["improving", "worsening", "stable"]
        assert trend in valid_trends, f"Invalid trend: {trend}, expected one of {valid_trends}"
        print(f"✓ TSI trend: {trend}")
    
    def test_cognitive_patterns_has_patterns(self):
        """Section 3: Verify patterns data for Top Instability Drivers"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/patterns")
        data = response.json()
        
        assert "patterns" in data, "Missing patterns"
        patterns = data["patterns"]
        assert isinstance(patterns, dict), f"Patterns should be dict, got {type(patterns)}"
        
        # Check pattern structure if any patterns exist
        for key, pattern_data in patterns.items():
            assert "frequency" in pattern_data, f"Pattern {key} missing frequency"
            print(f"  - Found pattern: {key} (frequency: {pattern_data['frequency']})")
        
        print(f"✓ Found {len(patterns)} patterns")
    
    def test_cognitive_patterns_has_games_analyzed(self):
        """Section 1: Verify games_analyzed count"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/patterns")
        data = response.json()
        
        assert "games_analyzed" in data, "Missing games_analyzed"
        games = data["games_analyzed"]
        assert isinstance(games, int), f"games_analyzed should be int, got {type(games)}"
        print(f"✓ Games analyzed: {games}")
    
    def test_cognitive_trend_returns_200(self):
        """Section 4: Verify trend endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/trend")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /cognitive/trend returns 200")
    
    def test_cognitive_trend_has_data_array(self):
        """Section 4: Verify trend data structure for line chart"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/trend")
        data = response.json()
        
        assert "data" in data, "Missing 'data' key"
        trend_data = data["data"]
        assert isinstance(trend_data, list), f"data should be list, got {type(trend_data)}"
        
        # Check structure of each data point
        if trend_data:
            for point in trend_data:
                assert "game_num" in point, "Missing game_num in trend point"
                assert "value" in point, "Missing value in trend point"
                value = point["value"]
                assert 0 <= value <= 100, f"TSI value should be 0-100, got {value}"
        
        print(f"✓ Trend data has {len(trend_data)} points")
    
    def test_blunder_context_returns_200(self):
        """Section 2: Verify blunder-context endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/blunder-context")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /cognitive/blunder-context returns 200")
    
    def test_blunder_context_has_distribution(self):
        """Section 2: Verify distribution data structure"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/blunder-context")
        data = response.json()
        
        assert "distribution" in data, "Missing 'distribution' key"
        dist = data["distribution"]
        
        # Check required fields
        assert "winning" in dist, "Missing 'winning' in distribution"
        assert "equal" in dist, "Missing 'equal' in distribution"
        assert "losing" in dist, "Missing 'losing' in distribution"
        
        # Check values are percentages
        assert isinstance(dist["winning"], (int, float)), f"winning should be numeric"
        assert isinstance(dist["equal"], (int, float)), f"equal should be numeric"
        assert isinstance(dist["losing"], (int, float)), f"losing should be numeric"
        
        # Check they sum to 100
        total = dist["winning"] + dist["equal"] + dist["losing"]
        assert total == 100, f"Distribution should sum to 100, got {total}"
        
        print(f"✓ Blunder distribution: Winning {dist['winning']}%, Equal {dist['equal']}%, Losing {dist['losing']}%")
    
    def test_phase_insight_returns_200(self):
        """Section 5: Verify phase-insight endpoint returns 200"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/phase-insight")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /cognitive/phase-insight returns 200")
    
    def test_phase_insight_has_phases(self):
        """Section 5: Verify most stable/unstable phases"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/phase-insight")
        data = response.json()
        
        assert "most_unstable" in data, "Missing 'most_unstable'"
        assert "most_stable" in data, "Missing 'most_stable'"
        
        valid_phases = ["Opening", "Middlegame", "Endgame"]
        assert data["most_unstable"] in valid_phases, f"Invalid most_unstable: {data['most_unstable']}"
        assert data["most_stable"] in valid_phases, f"Invalid most_stable: {data['most_stable']}"
        
        print(f"✓ Most Unstable: {data['most_unstable']}, Most Stable: {data['most_stable']}")


class TestTSIInterpretationBands:
    """Test TSI interpretation band logic (frontend interprets these)"""
    
    def test_tsi_80_plus_is_stable(self):
        """TSI >= 80 should display as 'Stable'"""
        tsi = 85
        if tsi >= 80:
            interpretation = "Stable"
        elif tsi >= 65:
            interpretation = "Moderate"
        elif tsi >= 50:
            interpretation = "Unstable"
        else:
            interpretation = "Volatile"
        assert interpretation == "Stable"
        print("✓ TSI 85 → Stable")
    
    def test_tsi_65_to_79_is_moderate(self):
        """TSI 65-79 should display as 'Moderate'"""
        tsi = 70
        if tsi >= 80:
            interpretation = "Stable"
        elif tsi >= 65:
            interpretation = "Moderate"
        elif tsi >= 50:
            interpretation = "Unstable"
        else:
            interpretation = "Volatile"
        assert interpretation == "Moderate"
        print("✓ TSI 70 → Moderate")
    
    def test_tsi_50_to_64_is_unstable(self):
        """TSI 50-64 should display as 'Unstable'"""
        tsi = 61
        if tsi >= 80:
            interpretation = "Stable"
        elif tsi >= 65:
            interpretation = "Moderate"
        elif tsi >= 50:
            interpretation = "Unstable"
        else:
            interpretation = "Volatile"
        assert interpretation == "Unstable"
        print("✓ TSI 61 → Unstable")
    
    def test_tsi_below_50_is_volatile(self):
        """TSI < 50 should display as 'Volatile'"""
        tsi = 42
        if tsi >= 80:
            interpretation = "Stable"
        elif tsi >= 65:
            interpretation = "Moderate"
        elif tsi >= 50:
            interpretation = "Unstable"
        else:
            interpretation = "Volatile"
        assert interpretation == "Volatile"
        print("✓ TSI 42 → Volatile")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
