"""
Tests for Positional Coaching RAG Layer

Tests:
- /api/knowledge-base/structures - Returns list of pawn structures
- /api/knowledge-base/imbalances - Returns strategic imbalances
- /api/positional-insight/{structure_id} - Returns deep dive for a structure
- /api/lab/{game_id} - Includes positional_insight when strategic data exists
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is required")

# Expected pawn structures from knowledge base
EXPECTED_STRUCTURE_IDS = [
    "iqp",
    "hanging_pawns", 
    "doubled_pawns",
    "kingside_majority",
    "queenside_majority",
    "carlsbad",
    "french_advance",
    "sicilian_open",
    "symmetrical",
    "closed_center"
]

# Expected strategic imbalances from knowledge base
EXPECTED_IMBALANCE_IDS = [
    "good_bishop",
    "bishop_pair",
    "knight_outpost",
    "weak_squares",
    "space_advantage",
    "development_lead",
    "open_file",
    "two_weaknesses",
    "king_activity",
    "material_imbalance"
]


@pytest.fixture(scope="module")
def session():
    """Create authenticated session using dev login"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Dev login
    resp = s.get(f"{BASE_URL}/api/auth/dev-login")
    assert resp.status_code == 200, f"Dev login failed: {resp.text}"
    
    return s


class TestKnowledgeBaseStructures:
    """Tests for /api/knowledge-base/structures endpoint"""
    
    def test_get_structures_returns_200(self, session):
        """API returns 200 status"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/structures")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_get_structures_returns_list(self, session):
        """API returns structures list"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/structures")
        data = resp.json()
        
        assert "structures" in data, "Response missing 'structures' key"
        assert isinstance(data["structures"], list), "Structures should be a list"
        assert len(data["structures"]) >= 10, f"Expected at least 10 structures, got {len(data['structures'])}"
    
    def test_structures_have_required_fields(self, session):
        """Each structure has structure_id, name, key_point"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/structures")
        structures = resp.json()["structures"]
        
        for struct in structures:
            assert "structure_id" in struct, f"Structure missing structure_id: {struct}"
            assert "name" in struct, f"Structure missing name: {struct}"
            assert "key_point" in struct, f"Structure missing key_point: {struct}"
    
    def test_all_expected_structures_present(self, session):
        """All 10 expected pawn structures are present"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/structures")
        structures = resp.json()["structures"]
        
        returned_ids = {s["structure_id"] for s in structures}
        for expected_id in EXPECTED_STRUCTURE_IDS:
            assert expected_id in returned_ids, f"Missing expected structure: {expected_id}"


class TestKnowledgeBaseImbalances:
    """Tests for /api/knowledge-base/imbalances endpoint"""
    
    def test_get_imbalances_returns_200(self, session):
        """API returns 200 status"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/imbalances")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_get_imbalances_returns_list(self, session):
        """API returns imbalances list"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/imbalances")
        data = resp.json()
        
        assert "imbalances" in data, "Response missing 'imbalances' key"
        assert isinstance(data["imbalances"], list), "Imbalances should be a list"
        assert len(data["imbalances"]) >= 10, f"Expected at least 10 imbalances, got {len(data['imbalances'])}"
    
    def test_imbalances_have_required_fields(self, session):
        """Each imbalance has concept_id, name, key_point"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/imbalances")
        imbalances = resp.json()["imbalances"]
        
        for imb in imbalances:
            assert "concept_id" in imb, f"Imbalance missing concept_id: {imb}"
            assert "name" in imb, f"Imbalance missing name: {imb}"
            assert "key_point" in imb, f"Imbalance missing key_point: {imb}"
    
    def test_all_expected_imbalances_present(self, session):
        """All 10 expected strategic imbalances are present"""
        resp = session.get(f"{BASE_URL}/api/knowledge-base/imbalances")
        imbalances = resp.json()["imbalances"]
        
        returned_ids = {i["concept_id"] for i in imbalances}
        for expected_id in EXPECTED_IMBALANCE_IDS:
            assert expected_id in returned_ids, f"Missing expected imbalance: {expected_id}"


class TestPositionalInsightDeepDive:
    """Tests for /api/positional-insight/{structure_id} endpoint"""
    
    def test_deep_dive_iqp_returns_200(self, session):
        """IQP deep dive returns 200"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/iqp")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    def test_deep_dive_iqp_has_required_fields(self, session):
        """IQP deep dive has all required fields"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/iqp")
        data = resp.json()
        
        required_fields = [
            "structure_id", "name", "trigger_conditions",
            "with_structure", "against_structure", "amateur_errors",
            "key_squares"
        ]
        
        for field in required_fields:
            assert field in data, f"Deep dive missing required field: {field}"
    
    def test_deep_dive_iqp_structure_has_plans(self, session):
        """IQP with_structure and against_structure have plans"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/iqp")
        data = resp.json()
        
        with_structure = data.get("with_structure", {})
        against_structure = data.get("against_structure", {})
        
        assert "plans" in with_structure, "with_structure missing plans"
        assert "plans" in against_structure, "against_structure missing plans"
        assert len(with_structure["plans"]) > 0, "with_structure plans should not be empty"
        assert len(against_structure["plans"]) > 0, "against_structure plans should not be empty"
    
    def test_deep_dive_invalid_structure_returns_404(self, session):
        """Invalid structure_id returns 404"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/invalid_nonexistent_structure")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    
    def test_deep_dive_hanging_pawns(self, session):
        """Hanging pawns deep dive works"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/hanging_pawns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["structure_id"] == "hanging_pawns"
        assert "Hanging" in data["name"]
    
    def test_deep_dive_french_advance(self, session):
        """French advance structure deep dive works"""
        resp = session.get(f"{BASE_URL}/api/positional-insight/french_advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["structure_id"] == "french_advance"
        assert "French" in data["name"]


class TestLabDataIncludesPositionalInsight:
    """Tests that /api/lab/{game_id} includes positional_insight when applicable"""
    
    def test_lab_endpoint_returns_positional_insight_field(self, session):
        """Lab endpoint response includes positional_insight field"""
        # First get a game that's been analyzed
        games_resp = session.get(f"{BASE_URL}/api/games")
        if games_resp.status_code != 200:
            pytest.skip("No games available")
        
        games = games_resp.json()
        analyzed_games = [g for g in games if g.get("is_analyzed")]
        
        if not analyzed_games:
            pytest.skip("No analyzed games available")
        
        game_id = analyzed_games[0]["game_id"]
        
        resp = session.get(f"{BASE_URL}/api/lab/{game_id}")
        assert resp.status_code == 200, f"Lab endpoint failed: {resp.text}"
        
        data = resp.json()
        # positional_insight field should be present (can be null if no strategy detected)
        assert "positional_insight" in data, "Lab data missing positional_insight field"
    
    def test_lab_data_structure(self, session):
        """Lab data has expected structure including core_lesson, strategic_analysis"""
        games_resp = session.get(f"{BASE_URL}/api/games")
        if games_resp.status_code != 200:
            pytest.skip("No games available")
        
        games = games_resp.json()
        analyzed_games = [g for g in games if g.get("is_analyzed")]
        
        if not analyzed_games:
            pytest.skip("No analyzed games available")
        
        game_id = analyzed_games[0]["game_id"]
        
        resp = session.get(f"{BASE_URL}/api/lab/{game_id}")
        data = resp.json()
        
        # Core fields should be present
        assert "core_lesson" in data, "Lab data missing core_lesson"
        assert "strategic_analysis" in data, "Lab data missing strategic_analysis"
        assert "positional_insight" in data, "Lab data missing positional_insight"


class TestPositionalInsightContent:
    """Tests for positional insight content when it exists"""
    
    def test_positional_insight_structure_when_present(self, session):
        """When positional_insight has data, it has expected structure"""
        games_resp = session.get(f"{BASE_URL}/api/games")
        if games_resp.status_code != 200:
            pytest.skip("No games available")
        
        games = games_resp.json()
        analyzed_games = [g for g in games if g.get("is_analyzed")]
        
        # Try to find a game with positional insight
        positional_insight_found = None
        for game in analyzed_games[:10]:  # Check up to 10 games
            resp = session.get(f"{BASE_URL}/api/lab/{game['game_id']}")
            if resp.status_code == 200:
                data = resp.json()
                pi = data.get("positional_insight")
                if pi and pi.get("has_insight"):
                    positional_insight_found = pi
                    break
        
        if not positional_insight_found:
            pytest.skip("No games with positional insight found")
        
        # Verify structure
        assert positional_insight_found.get("has_insight") == True
        
        # May have structure_insight or theme_insights
        has_structure = positional_insight_found.get("structure_insight") is not None
        has_themes = len(positional_insight_found.get("theme_insights", [])) > 0
        
        assert has_structure or has_themes, "Positional insight should have structure_insight or theme_insights"
    
    def test_structure_insight_fields_when_present(self, session):
        """structure_insight has expected fields when present"""
        games_resp = session.get(f"{BASE_URL}/api/games")
        if games_resp.status_code != 200:
            pytest.skip("No games available")
        
        games = games_resp.json()
        analyzed_games = [g for g in games if g.get("is_analyzed")]
        
        # Try to find a game with structure_insight
        structure_insight = None
        for game in analyzed_games[:10]:
            resp = session.get(f"{BASE_URL}/api/lab/{game['game_id']}")
            if resp.status_code == 200:
                data = resp.json()
                pi = data.get("positional_insight")
                if pi and pi.get("structure_insight"):
                    structure_insight = pi["structure_insight"]
                    break
        
        if not structure_insight:
            pytest.skip("No games with structure_insight found")
        
        # Verify expected fields
        expected_fields = ["structure_name", "summary", "your_plans"]
        for field in expected_fields:
            assert field in structure_insight, f"structure_insight missing {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
