"""
Test Suite for Discipline Check Feature
- GET /api/discipline-check endpoint
- Decision stability calculation
- Opening compliance check
- Blunder context analysis
- Verdict generation with grades
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDisciplineCheckEndpoint:
    """Tests for GET /api/discipline-check endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for all tests"""
        self.session = requests.Session()
        
        # Dev login first
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.text}"
        
        # Store cookies
        self.cookies = login_resp.cookies
        yield
    
    def test_discipline_check_returns_200(self):
        """Test endpoint returns 200 OK"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_discipline_check_response_structure_with_data(self):
        """Test response has correct structure when user has games"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check has_data field
        assert "has_data" in data, "Response must have 'has_data' field"
        
        if data["has_data"]:
            # Required fields when has_data is True
            assert "game_id" in data, "Must have game_id"
            assert "opponent" in data, "Must have opponent"
            assert "result" in data, "Must have result (win/loss/draw)"
            assert "user_color" in data, "Must have user_color"
            assert "metrics" in data, "Must have metrics object"
            assert "verdict" in data, "Must have verdict object"
    
    def test_metrics_structure(self):
        """Test metrics object has all required fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if data.get("has_data"):
            metrics = data["metrics"]
            
            # Required metric fields
            assert "accuracy" in metrics, "Metrics must have accuracy"
            assert "blunders" in metrics, "Metrics must have blunders"
            assert "mistakes" in metrics, "Metrics must have mistakes"
            assert "decision_stability" in metrics, "Metrics must have decision_stability"
            assert "opening_compliance" in metrics, "Metrics must have opening_compliance"
            assert "blunder_context" in metrics, "Metrics must have blunder_context"
            assert "winning_position" in metrics, "Metrics must have winning_position"
    
    def test_decision_stability_structure(self):
        """Test decision_stability has correct fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            stability = data["metrics"]["decision_stability"]
            
            # Score can be null or 0-100
            assert "score" in stability, "Must have score"
            assert "sample_size" in stability, "Must have sample_size"
            assert "collapses" in stability, "Must have collapses"
            
            if stability["score"] is not None:
                assert 0 <= stability["score"] <= 100, f"Score must be 0-100, got {stability['score']}"
    
    def test_opening_compliance_structure(self):
        """Test opening_compliance has correct fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            opening = data["metrics"]["opening_compliance"]
            
            assert "complied" in opening, "Must have complied"
            assert "played" in opening, "Must have played opening name"
            assert "verdict" in opening, "Must have verdict"
            
            # Verdict must be one of the expected values
            assert opening["verdict"] in ["FOLLOWED", "IGNORED", "NEUTRAL"], \
                f"Verdict must be FOLLOWED/IGNORED/NEUTRAL, got {opening['verdict']}"
    
    def test_blunder_context_structure(self):
        """Test blunder_context has correct fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            blunder_ctx = data["metrics"]["blunder_context"]
            
            assert "when_winning" in blunder_ctx, "Must have when_winning"
            assert "when_equal" in blunder_ctx, "Must have when_equal"
            assert "when_losing" in blunder_ctx, "Must have when_losing"
            assert "total_blunders" in blunder_ctx, "Must have total_blunders"
            assert "primary_trigger" in blunder_ctx, "Must have primary_trigger"
            
            # Primary trigger validation
            assert blunder_ctx["primary_trigger"] in ["winning", "losing", "equal", "none"], \
                f"Invalid primary_trigger: {blunder_ctx['primary_trigger']}"
    
    def test_verdict_structure(self):
        """Test verdict has correct fields and valid grade"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            verdict = data["verdict"]
            
            assert "headline" in verdict, "Verdict must have headline"
            assert "grade" in verdict, "Verdict must have grade"
            assert "tone" in verdict, "Verdict must have tone"
            assert "issues" in verdict, "Verdict must have issues list"
            assert "positives" in verdict, "Verdict must have positives list"
            
            # Grade must be valid letter
            assert verdict["grade"] in ["A", "B", "C", "D", "F"], \
                f"Grade must be A/B/C/D/F, got {verdict['grade']}"
            
            # Tone validation
            assert verdict["tone"] in ["positive", "neutral", "critical"], \
                f"Tone must be positive/neutral/critical, got {verdict['tone']}"
    
    def test_verdict_grade_tone_consistency(self):
        """Test that grade and tone are consistent"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            verdict = data["verdict"]
            grade = verdict["grade"]
            tone = verdict["tone"]
            
            # A/B grades should be positive, D/F should be critical
            if grade in ["A", "B"]:
                assert tone == "positive", f"Grade {grade} should have positive tone, got {tone}"
            elif grade in ["D", "F"]:
                assert tone == "critical", f"Grade {grade} should have critical tone, got {tone}"
    
    def test_no_data_response(self):
        """Test response when user has no games"""
        # This test checks the structure when has_data is false
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if not data.get("has_data"):
            assert "reason" in data, "Must have reason when no data"
            assert data["reason"] in ["no_games", "no_analysis"], \
                f"Invalid reason: {data['reason']}"
    
    def test_accuracy_in_valid_range(self):
        """Test accuracy is a valid percentage"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            accuracy = data["metrics"]["accuracy"]
            assert isinstance(accuracy, (int, float)), "Accuracy must be a number"
            assert 0 <= accuracy <= 100, f"Accuracy must be 0-100, got {accuracy}"
    
    def test_issues_and_positives_are_lists(self):
        """Test issues and positives are lists of strings"""
        resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        data = resp.json()
        
        if data.get("has_data"):
            issues = data["verdict"]["issues"]
            positives = data["verdict"]["positives"]
            
            assert isinstance(issues, list), "Issues must be a list"
            assert isinstance(positives, list), "Positives must be a list"
            
            for issue in issues:
                assert isinstance(issue, str), f"Each issue must be string, got {type(issue)}"
            
            for pos in positives:
                assert isinstance(pos, str), f"Each positive must be string, got {type(pos)}"


class TestDisciplineCheckServiceFunctions:
    """Test the individual service functions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session"""
        self.session = requests.Session()
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_resp.status_code == 200
        self.cookies = login_resp.cookies
    
    def test_game_id_matches_last_analyzed(self):
        """Test that discipline check uses the most recent analyzed game"""
        # Get discipline check
        disc_resp = self.session.get(
            f"{BASE_URL}/api/discipline-check",
            cookies=self.cookies
        )
        
        if disc_resp.status_code == 200 and disc_resp.json().get("has_data"):
            disc_data = disc_resp.json()
            game_id = disc_data.get("game_id")
            
            # Get games list
            games_resp = self.session.get(
                f"{BASE_URL}/api/games/analyzed",
                cookies=self.cookies
            )
            
            if games_resp.status_code == 200:
                games = games_resp.json().get("games", [])
                if games:
                    # The first game should be the most recent
                    most_recent = games[0].get("game_id")
                    assert game_id == most_recent, \
                        f"Discipline check game_id ({game_id}) should match most recent analyzed ({most_recent})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
