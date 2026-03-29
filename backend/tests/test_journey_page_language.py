"""
Test Journey Page Language Rewrite
- Tests /api/cognitive/journey endpoint with plain Indian-English labels
- Verifies micro/macro sections have correct structure and directives
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestJourneyPageLanguageRewrite:
    """Test Journey page /api/cognitive/journey endpoint with new plain language labels"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with dev login"""
        self.session = requests.Session()
        # Dev login to get session cookie
        response = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert response.status_code == 200, f"Dev login failed: {response.text}"
    
    def test_journey_endpoint_returns_200(self):
        """Test that /api/cognitive/journey returns 200"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_journey_is_activated_with_enough_games(self):
        """Test that journey is activated when user has 10+ games"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        # User has 100+ games so should be activated
        assert data.get("activated") == True, "Journey should be activated with 100+ games"
        assert data.get("games_analyzed", 0) >= 10, "Should have at least 10 games analyzed"
    
    def test_micro_section_has_headline(self):
        """Test micro section contains headline"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        assert "micro" in data, "Response should have 'micro' section"
        micro = data["micro"]
        assert "headline" in micro, "Micro section should have 'headline'"
        assert isinstance(micro["headline"], str), "Headline should be a string"
        assert len(micro["headline"]) > 0, "Headline should not be empty"
    
    def test_micro_section_has_3_rows(self):
        """Test micro section has exactly 3 rows"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        rows = micro.get("rows", [])
        assert len(rows) == 3, f"Micro should have exactly 3 rows, got {len(rows)}"
    
    def test_micro_row_labels_are_plain_language(self):
        """Test micro section row labels use plain Indian-English ('How steady?', 'When winning?', 'Main issue')"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        rows = micro.get("rows", [])
        
        expected_labels = ["How steady?", "When winning?", "Main issue"]
        actual_labels = [row.get("label") for row in rows]
        
        for expected in expected_labels:
            assert expected in actual_labels, f"Expected label '{expected}' not found in {actual_labels}"
    
    def test_micro_row1_stability_has_plain_values(self):
        """Test first row uses plain stability labels (Playing steady, Hit and miss, Too many slips, All over the place)"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        row1 = micro.get("rows", [])[0]
        
        valid_labels = ["Playing steady", "Hit and miss", "Too many slips", "All over the place"]
        
        assert row1.get("previous") in valid_labels, f"Previous stability '{row1.get('previous')}' not in valid labels"
        assert row1.get("recent") in valid_labels, f"Recent stability '{row1.get('recent')}' not in valid labels"
    
    def test_micro_row2_risk_has_plain_values(self):
        """Test second row uses plain risk labels (Finishing games well, Sometimes losing grip when winning, Throwing away winning positions)"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        row2 = micro.get("rows", [])[1]
        
        valid_labels = ["Finishing games well", "Sometimes losing grip when winning", "Throwing away winning positions"]
        
        assert row2.get("previous") in valid_labels, f"Previous risk '{row2.get('previous')}' not in valid labels"
        assert row2.get("recent") in valid_labels, f"Recent risk '{row2.get('recent')}' not in valid labels"
    
    def test_micro_row3_main_issue_has_value_and_note(self):
        """Test third row has 'value' and 'note' fields"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        row3 = micro.get("rows", [])[2]
        
        assert "value" in row3, "Third row should have 'value' field"
        assert "note" in row3, "Third row should have 'note' field"
    
    def test_micro_has_directive(self):
        """Test micro section has 'directive' field with action guidance"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        directive = micro.get("directive")
        
        assert directive is not None, "Micro should have 'directive' field"
        assert isinstance(directive, str), "Directive should be a string"
        assert len(directive) > 10, "Directive should have meaningful content"
        # Directive should mention 'Next 5 games' pattern
        assert "Next 5 games" in directive or "next" in directive.lower(), f"Directive should contain action guidance: {directive}"
    
    def test_macro_section_has_4_rows(self):
        """Test macro section has exactly 4 rows"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        macro = data.get("macro")
        if macro is None:
            pytest.skip("Macro section requires 30+ games")
        
        rows = macro.get("rows", [])
        assert len(rows) == 4, f"Macro should have exactly 4 rows, got {len(rows)}"
    
    def test_macro_row_labels_are_correct(self):
        """Test macro section row labels ('Overall', 'Main weakness', 'Weakest phase', 'vs Others')"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        macro = data.get("macro")
        if macro is None:
            pytest.skip("Macro section requires 30+ games")
        
        rows = macro.get("rows", [])
        expected_labels = ["Overall", "Main weakness", "Weakest phase", "vs Others"]
        actual_labels = [row.get("label") for row in rows]
        
        for expected in expected_labels:
            assert expected in actual_labels, f"Expected label '{expected}' not found in {actual_labels}"
    
    def test_macro_has_directive(self):
        """Test macro section has 'directive' field for weekly focus"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        macro = data.get("macro")
        if macro is None:
            pytest.skip("Macro section requires 30+ games")
        
        directive = macro.get("directive")
        assert directive is not None, "Macro should have 'directive' field"
        assert isinstance(directive, str), "Directive should be a string"
        assert len(directive) > 10, "Directive should have meaningful content"
    
    def test_evidence_section_has_2_game_links(self):
        """Test evidence section has exactly 2 game links"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        evidence = data.get("evidence", [])
        assert len(evidence) == 2, f"Evidence should have exactly 2 items, got {len(evidence)}"
        
        for item in evidence:
            assert "type" in item, "Evidence item should have 'type'"
            assert "label" in item, "Evidence item should have 'label'"
            assert "description" in item, "Evidence item should have 'description'"
    
    def test_metrics_available_when_toggled(self):
        """Test that metrics data is included in response"""
        response = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = response.json()
        
        micro = data.get("micro", {})
        metrics = micro.get("metrics", {})
        
        # Verify numeric metrics are present
        assert "tsi_previous" in metrics, "Should have tsi_previous metric"
        assert "tsi_recent" in metrics, "Should have tsi_recent metric"
        assert "tsi_delta" in metrics, "Should have tsi_delta metric"
        assert "context_previous" in metrics, "Should have context_previous metric"
        assert "context_recent" in metrics, "Should have context_recent metric"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
