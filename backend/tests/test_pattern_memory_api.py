"""
Test Pattern Memory API Endpoints
=================================

Tests for the Pattern Memory feature that aggregates recurring cognitive gaps/mistakes:
- GET /api/coach/patterns/summary - returns aggregated patterns with total_count, recent_count, severity
- GET /api/coach/patterns/top?limit=3 - returns top 3 worst patterns for dashboard
- GET /api/coach/patterns/for-mistake/{cognitive_gap} - returns pattern data with confrontation_message
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://move-intent-engine.preview.emergentagent.com')


class TestPatternMemoryAPI:
    """Tests for Pattern Memory endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth cookie"""
        self.session = requests.Session()
        self.session.cookies.set('session_token', 'test')
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def test_patterns_summary_endpoint_returns_200(self):
        """Test GET /api/coach/patterns/summary returns 200 with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/summary")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "patterns" in data, "Response should contain 'patterns' field"
        assert "total_games_analyzed" in data, "Response should contain 'total_games_analyzed' field"
        assert "worst_pattern" in data, "Response should contain 'worst_pattern' field"
        
        # Verify patterns is a list
        assert isinstance(data["patterns"], list), "patterns should be a list"
        
        print(f"SUCCESS: patterns/summary returned {len(data['patterns'])} patterns, {data['total_games_analyzed']} games analyzed")
    
    def test_patterns_summary_pattern_structure(self):
        """Test that each pattern in summary has required fields"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["patterns"]) > 0:
            pattern = data["patterns"][0]
            
            # Required fields for each pattern
            required_fields = [
                "pattern_type",
                "label",
                "total_count",
                "recent_count",
                "recent_games",
                "severity"
            ]
            
            for field in required_fields:
                assert field in pattern, f"Pattern should contain '{field}' field"
            
            # Verify severity is one of expected values
            valid_severities = ["critical", "high", "medium", "low"]
            assert pattern["severity"] in valid_severities, f"Severity should be one of {valid_severities}"
            
            # Verify counts are integers
            assert isinstance(pattern["total_count"], int), "total_count should be an integer"
            assert isinstance(pattern["recent_count"], int), "recent_count should be an integer"
            
            print(f"SUCCESS: Pattern structure verified - {pattern['label']} ({pattern['severity']})")
        else:
            print("INFO: No patterns found (user may not have enough game data)")
    
    def test_patterns_top_endpoint_returns_200(self):
        """Test GET /api/coach/patterns/top returns 200 with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/top?limit=3")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "patterns" in data, "Response should contain 'patterns' field"
        assert isinstance(data["patterns"], list), "patterns should be a list"
        
        # Verify limit is respected
        assert len(data["patterns"]) <= 3, f"Should return at most 3 patterns, got {len(data['patterns'])}"
        
        print(f"SUCCESS: patterns/top returned {len(data['patterns'])} patterns")
    
    def test_patterns_top_with_different_limits(self):
        """Test GET /api/coach/patterns/top with different limit values"""
        for limit in [1, 3, 5]:
            response = self.session.get(f"{BASE_URL}/api/coach/patterns/top?limit={limit}")
            
            assert response.status_code == 200, f"Expected 200 for limit={limit}, got {response.status_code}"
            
            data = response.json()
            assert len(data["patterns"]) <= limit, f"Should return at most {limit} patterns"
        
        print("SUCCESS: patterns/top respects different limit values")
    
    def test_patterns_for_mistake_endpoint_returns_200(self):
        """Test GET /api/coach/patterns/for-mistake/{cognitive_gap} returns 200"""
        # Test with common cognitive gap types
        cognitive_gaps = ["ignore_threat", "tactical_miss", "hanging_piece", "short_calculation"]
        
        for gap in cognitive_gaps:
            response = self.session.get(f"{BASE_URL}/api/coach/patterns/for-mistake/{gap}")
            
            assert response.status_code == 200, f"Expected 200 for {gap}, got {response.status_code}: {response.text}"
            
            data = response.json()
            
            # Response should have 'pattern' field (can be null if no data)
            assert "pattern" in data, f"Response should contain 'pattern' field for {gap}"
            
            print(f"SUCCESS: patterns/for-mistake/{gap} returned 200")
    
    def test_patterns_for_mistake_confrontation_message(self):
        """Test that pattern for mistake includes confrontation_message when data exists"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/for-mistake/ignore_threat")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["pattern"] is not None:
            pattern = data["pattern"]
            
            # Should have confrontation_message
            assert "confrontation_message" in pattern, "Pattern should contain 'confrontation_message'"
            
            # Confrontation message should be a non-empty string
            assert isinstance(pattern["confrontation_message"], str), "confrontation_message should be a string"
            assert len(pattern["confrontation_message"]) > 0, "confrontation_message should not be empty"
            
            # Should contain count information
            assert "times" in pattern["confrontation_message"].lower(), "Message should mention 'times'"
            
            print(f"SUCCESS: Confrontation message: {pattern['confrontation_message'][:100]}...")
        else:
            print("INFO: No pattern data found for ignore_threat (user may not have this pattern)")
    
    def test_patterns_for_mistake_with_url_encoded_gap(self):
        """Test patterns/for-mistake with URL-encoded cognitive gap"""
        # Test with spaces and special characters
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/for-mistake/tactical%20oversight")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "pattern" in data
        
        print("SUCCESS: URL-encoded cognitive gap handled correctly")


class TestPatternMemoryDataIntegrity:
    """Tests for Pattern Memory data integrity and aggregation logic"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth cookie"""
        self.session = requests.Session()
        self.session.cookies.set('session_token', 'test')
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def test_patterns_sorted_by_severity(self):
        """Test that patterns are sorted by recent_count (urgency) then total_count"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        patterns = data["patterns"]
        
        if len(patterns) >= 2:
            # Verify sorting: recent_count should be descending
            for i in range(len(patterns) - 1):
                current = patterns[i]
                next_pattern = patterns[i + 1]
                
                # Primary sort: recent_count descending
                # Secondary sort: total_count descending
                is_sorted = (
                    current["recent_count"] > next_pattern["recent_count"] or
                    (current["recent_count"] == next_pattern["recent_count"] and 
                     current["total_count"] >= next_pattern["total_count"])
                )
                
                assert is_sorted, f"Patterns should be sorted by recent_count, then total_count"
            
            print("SUCCESS: Patterns are correctly sorted by severity")
        else:
            print("INFO: Not enough patterns to verify sorting")
    
    def test_recent_games_count_is_20(self):
        """Test that recent_games is set to 20 (last 20 games)"""
        response = self.session.get(f"{BASE_URL}/api/coach/patterns/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        for pattern in data["patterns"]:
            assert pattern["recent_games"] == 20, f"recent_games should be 20, got {pattern['recent_games']}"
        
        print("SUCCESS: recent_games is correctly set to 20")
    
    def test_top_patterns_match_summary(self):
        """Test that top patterns are a subset of summary patterns"""
        summary_response = self.session.get(f"{BASE_URL}/api/coach/patterns/summary")
        top_response = self.session.get(f"{BASE_URL}/api/coach/patterns/top?limit=3")
        
        assert summary_response.status_code == 200
        assert top_response.status_code == 200
        
        summary_data = summary_response.json()
        top_data = top_response.json()
        
        # Top patterns should be the first N from summary
        summary_types = [p["pattern_type"] for p in summary_data["patterns"][:3]]
        top_types = [p["pattern_type"] for p in top_data["patterns"]]
        
        assert top_types == summary_types[:len(top_types)], "Top patterns should match first N from summary"
        
        print("SUCCESS: Top patterns match summary patterns")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
