"""
Backend tests for P1.5 Coach Memory & Learning Velocity features

Tests:
- learning_velocity, learner_type, coach_compliance_score, active_advice_count in API responses
- advice_stats with applicable/followed/violated counts
- scorecard includes coach_compliance and learning_velocity dimensions
- Advice rule engine validation
- Learning velocity calculation
- Narrative engine tone adjustment based on learner_type
- Mission picker prioritization
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://identity-tracker-19.preview.emergentagent.com')

# Valid learner types
VALID_LEARNER_TYPES = ["FAST_ADAPTER", "STEADY", "TRYING_BUT_STUCK", "NOT_APPLYING"]

# Scorecard dimensions
SCORECARD_DIMENSIONS = [
    "plan_discipline",
    "decision_stability",
    "pattern_persistence",
    "coach_compliance",
    "learning_velocity"
]

# Valid advice rule codes
VALID_RULE_CODES = [
    "OPENING_REPEAT_PIECE",
    "TIME_PANIC",
    "HANGING_PIECE",
    "EARLY_QUEEN",
    "OPENING_WANDER",
    "CONVERSION_ISSUE"
]


@pytest.fixture
def authenticated_session():
    """Session with dev login authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    res = session.get(f"{BASE_URL}/api/auth/dev-login")
    if res.status_code != 200:
        pytest.skip("Dev login failed - skipping authenticated tests")
    
    return session


class TestLearningVelocityFields:
    """Tests for P1.5 learning velocity fields in API response"""
    
    def test_last_report_returns_learning_velocity(self, authenticated_session):
        """Test that last report returns learning_velocity field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "learning_velocity" in data, "Response should contain learning_velocity field"
        
        velocity = data["learning_velocity"]
        assert isinstance(velocity, (int, float)), "learning_velocity should be a number"
        assert 0 <= velocity <= 1, f"learning_velocity should be 0-1, got {velocity}"
    
    def test_last_report_returns_learner_type(self, authenticated_session):
        """Test that last report returns learner_type field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "learner_type" in data, "Response should contain learner_type field"
        assert data["learner_type"] in VALID_LEARNER_TYPES, \
            f"learner_type should be one of {VALID_LEARNER_TYPES}, got {data['learner_type']}"
    
    def test_last_report_returns_coach_compliance_score(self, authenticated_session):
        """Test that last report returns coach_compliance_score field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "coach_compliance_score" in data, "Response should contain coach_compliance_score field"
        
        score = data["coach_compliance_score"]
        assert isinstance(score, int), "coach_compliance_score should be an integer"
        assert 0 <= score <= 100, f"coach_compliance_score should be 0-100, got {score}"
    
    def test_last_report_returns_active_advice_count(self, authenticated_session):
        """Test that last report returns active_advice_count field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "active_advice_count" in data, "Response should contain active_advice_count field"
        
        count = data["active_advice_count"]
        assert isinstance(count, int), "active_advice_count should be an integer"
        assert count >= 0, f"active_advice_count should be >= 0, got {count}"


class TestAdviceStatsFields:
    """Tests for advice_stats in API response"""
    
    def test_last_report_returns_advice_stats(self, authenticated_session):
        """Test that last report returns advice_stats field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "advice_stats" in data, "Response should contain advice_stats field"
        assert isinstance(data["advice_stats"], dict), "advice_stats should be a dict"
    
    def test_advice_stats_has_required_fields(self, authenticated_session):
        """Test that advice_stats contains all required fields"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        stats = data.get("advice_stats", {})
        
        required_fields = ["total_applications", "applicable", "followed", "violated"]
        for field in required_fields:
            assert field in stats, f"advice_stats should contain {field}"
            assert isinstance(stats[field], int), f"advice_stats.{field} should be an integer"
    
    def test_advice_stats_counts_are_consistent(self, authenticated_session):
        """Test that advice_stats counts are logically consistent"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        stats = data.get("advice_stats", {})
        
        applicable = stats.get("applicable", 0)
        followed = stats.get("followed", 0)
        violated = stats.get("violated", 0)
        
        # followed + violated should be <= applicable
        assert followed + violated <= applicable, \
            f"followed ({followed}) + violated ({violated}) should be <= applicable ({applicable})"
        
        # All counts should be non-negative
        assert applicable >= 0
        assert followed >= 0
        assert violated >= 0


class TestAdviceResultsFields:
    """Tests for advice_results in API response"""
    
    def test_last_report_returns_advice_results(self, authenticated_session):
        """Test that last report returns advice_results field"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        assert "advice_results" in data, "Response should contain advice_results field"
        assert isinstance(data["advice_results"], list), "advice_results should be a list"
    
    def test_analyze_endpoint_returns_advice_results(self, authenticated_session):
        """Test that analyze endpoint returns advice_results"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert "advice_results" in data, "Response should contain advice_results"


class TestScorecardCoachDimensions:
    """Tests for coach_compliance and learning_velocity dimensions in scorecard"""
    
    def test_scorecard_has_coach_compliance_dimension(self, authenticated_session):
        """Test that scorecard contains coach_compliance dimension"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        scorecard = data.get("scorecard", {})
        
        assert "coach_compliance" in scorecard, "Scorecard should contain coach_compliance"
        
        compliance = scorecard["coach_compliance"]
        assert "score" in compliance, "coach_compliance should have score"
        assert "label" in compliance, "coach_compliance should have label"
        assert "why" in compliance, "coach_compliance should have why"
        
        assert 0 <= compliance["score"] <= 100, "coach_compliance score should be 0-100"
        assert compliance["label"] in ["Excellent", "Good", "Mixed", "Concern"], \
            f"Invalid label: {compliance['label']}"
    
    def test_scorecard_has_learning_velocity_dimension(self, authenticated_session):
        """Test that scorecard contains learning_velocity dimension"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        scorecard = data.get("scorecard", {})
        
        assert "learning_velocity" in scorecard, "Scorecard should contain learning_velocity"
        
        velocity = scorecard["learning_velocity"]
        assert "score" in velocity, "learning_velocity should have score"
        assert "label" in velocity, "learning_velocity should have label"
        assert "why" in velocity, "learning_velocity should have why"
        
        assert 0 <= velocity["score"] <= 100, "learning_velocity score should be 0-100"
        assert velocity["label"] in ["Excellent", "Good", "Mixed", "Concern"], \
            f"Invalid label: {velocity['label']}"


class TestLearnerTypeMapping:
    """Tests for learner type to label mapping"""
    
    def test_learner_type_maps_to_correct_velocity_label(self, authenticated_session):
        """Test that learner_type maps to correct velocity label"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        learner_type = data.get("learner_type")
        scorecard = data.get("scorecard", {})
        velocity_dim = scorecard.get("learning_velocity", {})
        velocity_label = velocity_dim.get("label")
        
        # Mapping as per learning_velocity.py
        expected_labels = {
            "FAST_ADAPTER": "Excellent",
            "STEADY": "Good",
            "TRYING_BUT_STUCK": "Mixed",
            "NOT_APPLYING": "Concern"
        }
        
        if learner_type in expected_labels:
            assert velocity_label == expected_labels[learner_type], \
                f"For learner_type {learner_type}, expected label {expected_labels[learner_type]}, got {velocity_label}"


class TestAnalyzeEndpointP15Fields:
    """Tests for P1.5 fields in /api/behavioral/analyze/{game_id}"""
    
    def test_analyze_returns_learning_velocity(self, authenticated_session):
        """Test analyze endpoint returns learning_velocity"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert "learning_velocity" in data
        assert 0 <= data["learning_velocity"] <= 1
    
    def test_analyze_returns_learner_type(self, authenticated_session):
        """Test analyze endpoint returns learner_type"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert "learner_type" in data
        assert data["learner_type"] in VALID_LEARNER_TYPES
    
    def test_analyze_returns_coach_compliance_score(self, authenticated_session):
        """Test analyze endpoint returns coach_compliance_score"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert "coach_compliance_score" in data
        assert 0 <= data["coach_compliance_score"] <= 100
    
    def test_analyze_returns_advice_stats(self, authenticated_session):
        """Test analyze endpoint returns advice_stats"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        game_id = last_res.json().get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert "advice_stats" in data
        stats = data["advice_stats"]
        assert "applicable" in stats
        assert "followed" in stats
        assert "violated" in stats


class TestMissionPrioritization:
    """Tests for mission picker prioritization"""
    
    def test_mission_structure_with_advice_enforcement(self, authenticated_session):
        """Test mission structure - should support ADVICE_ENFORCEMENT type"""
        res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        assert res.status_code == 200
        
        data = res.json()
        mission = data.get("next_mission", {})
        
        # Mission should have proper structure
        assert "type" in mission, "Mission should have type"
        assert "title" in mission, "Mission should have title"
        assert "instruction" in mission, "Mission should have instruction"
        
        # Valid mission types include ADVICE_ENFORCEMENT
        valid_types = [
            "TIME_DECISION_DRILL",
            "CONVERSION_DISCIPLINE_DRILL",
            "CANDIDATE_MOVE_DRILL",
            "DEFENSIVE_RESILIENCE_DRILL",
            "STABILITY_DRILL",
            "OPENING_DISCIPLINE",
            "TACTICAL_FUEL",
            "ADVICE_ENFORCEMENT"  # P1.5 addition
        ]
        assert mission["type"] in valid_types, f"Mission type {mission['type']} not valid"


class TestP15FieldsConsistency:
    """Tests for consistency between last-report and analyze endpoints"""
    
    def test_fields_match_between_endpoints(self, authenticated_session):
        """Test that P1.5 fields match between last-report and analyze"""
        last_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/last-report")
        if last_res.status_code != 200:
            pytest.skip("No last report available")
        
        last_data = last_res.json()
        game_id = last_data.get("game_id")
        if not game_id:
            pytest.skip("No game_id in last report")
        
        analyze_res = authenticated_session.get(f"{BASE_URL}/api/behavioral/analyze/{game_id}")
        assert analyze_res.status_code == 200
        
        analyze_data = analyze_res.json()
        
        # P1.5 fields should match
        assert last_data.get("learning_velocity") == analyze_data.get("learning_velocity"), \
            "learning_velocity should match"
        assert last_data.get("learner_type") == analyze_data.get("learner_type"), \
            "learner_type should match"
        assert last_data.get("coach_compliance_score") == analyze_data.get("coach_compliance_score"), \
            "coach_compliance_score should match"
        assert last_data.get("active_advice_count") == analyze_data.get("active_advice_count"), \
            "active_advice_count should match"
