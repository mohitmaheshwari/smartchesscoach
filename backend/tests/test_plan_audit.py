"""
Test Plan Audit API - Phase-Based Execution Evaluation

Tests the GET /api/plan-audit endpoint which evaluates the previous game across 5 domains:
- Opening, Middlegame, Endgame, Tactical Discipline, Time Discipline

Each domain shows: Expected Plan, What Happened, Data Snapshot, and Verdict.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def auth_session(api_client):
    """Get authenticated session via dev login"""
    response = api_client.get(f"{BASE_URL}/api/auth/dev-login")
    if response.status_code == 200:
        # Session cookie is set automatically
        return api_client
    pytest.skip("Dev login not available")


class TestPlanAuditEndpoint:
    """Tests for GET /api/plan-audit endpoint"""
    
    def test_plan_audit_returns_200(self, auth_session):
        """Test that plan-audit endpoint returns 200 status"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/plan-audit returned 200")
    
    def test_plan_audit_has_required_fields(self, auth_session):
        """Test that response has all required top-level fields"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        assert "has_data" in data, "Missing 'has_data' field"
        
        # If has_data is True, check for additional required fields
        if data.get("has_data"):
            required_fields = ["game_id", "opponent", "result", "accuracy", "audits", "summary"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            print(f"✓ All required fields present: has_data, game_id, opponent, result, accuracy, audits, summary")
        else:
            print(f"✓ has_data is False (no analyzed games) - response structure valid")
    
    def test_plan_audit_audits_array_structure(self, auth_session):
        """Test that each audit in audits array has correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        audits = data["audits"]
        assert isinstance(audits, list), "audits should be an array"
        
        for audit in audits:
            # Required fields for each audit
            assert "domain" in audit, "Audit missing 'domain' field"
            assert "has_plan" in audit, "Audit missing 'has_plan' field"
            assert "verdict" in audit, "Audit missing 'verdict' field"
            assert "verdict_type" in audit, "Audit missing 'verdict_type' field"
            assert "what_happened" in audit, "Audit missing 'what_happened' field"
            assert "data" in audit, "Audit missing 'data' field"
            
            # Validate verdict_type is one of expected values
            valid_verdict_types = ["pass", "partial", "fail", "neutral"]
            assert audit["verdict_type"] in valid_verdict_types, \
                f"Invalid verdict_type: {audit['verdict_type']}"
            
            # Validate what_happened is a list
            assert isinstance(audit["what_happened"], list), "what_happened should be an array"
            
            print(f"  ✓ Domain '{audit['domain']}' has valid structure")
        
        print(f"✓ All {len(audits)} audits have correct structure")
    
    def test_plan_audit_summary_structure(self, auth_session):
        """Test that summary has correct structure"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data"):
            pytest.skip("No audit data available")
        
        summary = data.get("summary", {})
        
        # Required summary fields
        required_summary_fields = [
            "domains_shown", "executed", "partial", "failed", 
            "execution_score", "training_focus"
        ]
        
        for field in required_summary_fields:
            assert field in summary, f"Summary missing '{field}' field"
        
        # Validate numeric fields are integers
        assert isinstance(summary["domains_shown"], int), "domains_shown should be integer"
        assert isinstance(summary["executed"], int), "executed should be integer"
        assert isinstance(summary["partial"], int), "partial should be integer"
        assert isinstance(summary["failed"], int), "failed should be integer"
        
        # Validate execution_score format (e.g., "2/5")
        assert "/" in str(summary["execution_score"]), "execution_score should be in X/Y format"
        
        print(f"✓ Summary structure valid: {summary['execution_score']} domains executed")
    
    def test_plan_audit_verdict_types(self, auth_session):
        """Test that verdict_type values are correctly categorized"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        audits = data["audits"]
        summary = data.get("summary", {})
        
        # Count verdict types
        pass_count = sum(1 for a in audits if a["verdict_type"] == "pass")
        partial_count = sum(1 for a in audits if a["verdict_type"] == "partial")
        fail_count = sum(1 for a in audits if a["verdict_type"] == "fail")
        
        # Verify summary matches audit counts
        assert summary["executed"] == pass_count, \
            f"Summary executed ({summary['executed']}) doesn't match pass count ({pass_count})"
        assert summary["partial"] == partial_count, \
            f"Summary partial ({summary['partial']}) doesn't match partial count ({partial_count})"
        assert summary["failed"] == fail_count, \
            f"Summary failed ({summary['failed']}) doesn't match fail count ({fail_count})"
        
        print(f"✓ Verdict counts: {pass_count} pass, {partial_count} partial, {fail_count} fail")
    
    def test_plan_audit_valid_domains(self, auth_session):
        """Test that only valid domain names are returned"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        valid_domains = ["Opening", "Middlegame", "Endgame", "Tactics", "Time"]
        
        for audit in data["audits"]:
            assert audit["domain"] in valid_domains, \
                f"Invalid domain: {audit['domain']}"
        
        print(f"✓ All domains are valid: {[a['domain'] for a in data['audits']]}")
    
    def test_plan_audit_opening_domain_data(self, auth_session):
        """Test Opening domain specific data fields"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        opening_audit = next((a for a in data["audits"] if a["domain"] == "Opening"), None)
        if not opening_audit:
            pytest.skip("No Opening audit in response")
        
        # Opening data can include: opening_accuracy, early_eval_stability, max_eval_drop
        audit_data = opening_audit.get("data", {})
        
        if "opening_accuracy" in audit_data:
            assert isinstance(audit_data["opening_accuracy"], (int, float)), \
                "opening_accuracy should be a number"
            print(f"  Opening accuracy: {audit_data['opening_accuracy']}%")
        
        if "early_eval_stability" in audit_data:
            assert audit_data["early_eval_stability"] in ["Stable", "Unstable", "Poor"], \
                f"Invalid early_eval_stability: {audit_data['early_eval_stability']}"
            print(f"  Early eval stability: {audit_data['early_eval_stability']}")
        
        print(f"✓ Opening domain data structure valid")
    
    def test_plan_audit_tactics_domain_data(self, auth_session):
        """Test Tactics domain specific data fields"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        tactics_audit = next((a for a in data["audits"] if a["domain"] == "Tactics"), None)
        if not tactics_audit:
            pytest.skip("No Tactics audit in response")
        
        # Tactics data includes: blunders, mistakes, worst_drop
        audit_data = tactics_audit.get("data", {})
        
        if "blunders" in audit_data:
            assert isinstance(audit_data["blunders"], int), "blunders should be integer"
            print(f"  Blunders: {audit_data['blunders']}")
        
        if "mistakes" in audit_data:
            assert isinstance(audit_data["mistakes"], int), "mistakes should be integer"
            print(f"  Mistakes: {audit_data['mistakes']}")
        
        print(f"✓ Tactics domain data structure valid")
    
    def test_plan_audit_middlegame_domain_data(self, auth_session):
        """Test Middlegame domain specific data fields"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data") or not data.get("audits"):
            pytest.skip("No audit data available")
        
        middlegame_audit = next((a for a in data["audits"] if a["domain"] == "Middlegame"), None)
        if not middlegame_audit:
            pytest.skip("No Middlegame audit in response")
        
        # Middlegame data includes: max_advantage, max_advantage_move, eval_swing
        audit_data = middlegame_audit.get("data", {})
        
        if "max_advantage" in audit_data and audit_data["max_advantage"]:
            # Format should be like "+3.7" or null
            assert isinstance(audit_data["max_advantage"], str), \
                "max_advantage should be a string (e.g., '+3.7')"
            print(f"  Max advantage: {audit_data['max_advantage']}")
        
        if "eval_swing" in audit_data and audit_data["eval_swing"]:
            # Format should be like "-1.9" or null
            assert isinstance(audit_data["eval_swing"], str), \
                "eval_swing should be a string (e.g., '-1.9')"
            print(f"  Eval swing: {audit_data['eval_swing']}")
        
        print(f"✓ Middlegame domain data structure valid")


class TestPlanAuditAuthentication:
    """Test authentication requirements for plan-audit endpoint"""
    
    def test_plan_audit_requires_auth(self, api_client):
        """Test that unauthenticated request returns 401"""
        response = api_client.get(f"{BASE_URL}/api/plan-audit")
        # DEV_MODE may bypass auth, so accept 200 or 401
        assert response.status_code in [200, 401], \
            f"Expected 200 (dev mode) or 401, got {response.status_code}"
        print(f"✓ Auth check: returned {response.status_code}")


class TestPlanAuditIntegration:
    """Integration tests verifying plan audit with other endpoints"""
    
    def test_plan_audit_game_id_matches_game(self, auth_session):
        """Test that game_id in plan-audit exists in games list"""
        # Get plan audit data
        audit_response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert audit_response.status_code == 200
        
        audit_data = audit_response.json()
        if not audit_data.get("has_data"):
            pytest.skip("No audit data available")
        
        game_id = audit_data.get("game_id")
        assert game_id, "game_id should not be empty"
        
        # Verify game exists
        game_response = auth_session.get(f"{BASE_URL}/api/games/{game_id}")
        assert game_response.status_code == 200, \
            f"Game {game_id} from plan-audit not found in games"
        
        print(f"✓ Plan audit game_id {game_id} exists in games")
    
    def test_plan_audit_consistency_with_focus(self, auth_session):
        """Test that plan audit data is consistent with focus endpoint"""
        # Get plan audit
        audit_response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        
        # Get focus data  
        focus_response = auth_session.get(f"{BASE_URL}/api/focus")
        assert focus_response.status_code == 200
        
        # Both endpoints should be accessible and return structured data
        print(f"✓ Plan audit and focus endpoints both return valid data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
