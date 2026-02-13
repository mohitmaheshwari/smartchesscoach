"""
Test Coaching Loop System - GM Coach Style Plan → Play → Audit → Adjust (GOLD FEATURE)

Tests for:
1. GET /api/round-preparation - Returns PlanCard with plan_id, training_block, cards[] (5 domains)
2. GET /api/plan-audit - Returns audited PlanCard with audit_summary and filled audit for each card
3. PlanCard Schema - Same structure for preparation and audit
4. Domain Card Structure - domain, priority, goal, rules, success_criteria, audit
5. Audit Structure - status (executed/partial/missed/n/a), data_points[], evidence[], coach_note

Evidence links should have: move number, delta, note
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
        return api_client
    pytest.skip("Dev login not available")


class TestRoundPreparationEndpoint:
    """Tests for GET /api/round-preparation - Next Game Plan"""
    
    def test_round_preparation_returns_200(self, auth_session):
        """Test that round-preparation endpoint returns 200 status"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/round-preparation returned 200")
    
    def test_round_preparation_has_plan_id(self, auth_session):
        """Test that response has plan_id field"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        assert "plan_id" in data, "Missing 'plan_id' field"
        assert isinstance(data["plan_id"], str), "plan_id should be a string"
        assert len(data["plan_id"]) > 0, "plan_id should not be empty"
        print(f"✓ plan_id present: {data['plan_id'][:20]}...")
    
    def test_round_preparation_has_training_block(self, auth_session):
        """Test that response has training_block field with name and intensity"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        assert "training_block" in data, "Missing 'training_block' field"
        
        tb = data["training_block"]
        assert "name" in tb, "training_block missing 'name'"
        assert "intensity" in tb, "training_block missing 'intensity'"
        assert isinstance(tb["intensity"], int), "intensity should be integer"
        assert 1 <= tb["intensity"] <= 3, "intensity should be 1-3"
        
        print(f"✓ training_block: {tb['name']}, intensity {tb['intensity']}/3")
    
    def test_round_preparation_has_5_domain_cards(self, auth_session):
        """Test that response has cards[] array with 5 domains"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        assert "cards" in data, "Missing 'cards' field"
        assert isinstance(data["cards"], list), "cards should be an array"
        assert len(data["cards"]) == 5, f"Expected 5 domain cards, got {len(data['cards'])}"
        
        # Check all 5 domains are present
        domains = [card["domain"] for card in data["cards"]]
        expected_domains = {"opening", "middlegame", "tactics", "endgame", "time"}
        assert set(domains) == expected_domains, f"Missing domains: {expected_domains - set(domains)}"
        
        print(f"✓ All 5 domain cards present: {domains}")
    
    def test_round_preparation_card_structure(self, auth_session):
        """Test each card has: domain, priority, goal, rules, success_criteria, audit (empty)"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        cards = data.get("cards", [])
        
        for card in cards:
            # Required fields
            assert "domain" in card, f"Card missing 'domain'"
            assert "priority" in card, f"Card missing 'priority' for {card.get('domain')}"
            assert "goal" in card, f"Card missing 'goal' for {card.get('domain')}"
            assert "rules" in card, f"Card missing 'rules' for {card.get('domain')}"
            assert "success_criteria" in card, f"Card missing 'success_criteria' for {card.get('domain')}"
            assert "audit" in card, f"Card missing 'audit' for {card.get('domain')}"
            
            # Validate priority values
            valid_priorities = {"primary", "secondary", "baseline"}
            assert card["priority"] in valid_priorities, \
                f"Invalid priority '{card['priority']}' for {card['domain']}"
            
            # Validate rules is a list
            assert isinstance(card["rules"], list), f"rules should be a list for {card['domain']}"
            
            # Audit should be empty for preparation
            audit = card["audit"]
            assert audit.get("status") is None, f"audit.status should be None for preparation"
            
            print(f"  ✓ {card['domain']}: {card['priority']}, goal: '{card['goal'][:40]}...'")
        
        print(f"✓ All cards have correct structure")
    
    def test_round_preparation_primary_domain_has_more_rules(self, auth_session):
        """Test that primary domain has up to 4 rules, secondary up to 2, baseline 1"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        cards = data.get("cards", [])
        
        for card in cards:
            rules_count = len(card.get("rules", []))
            priority = card["priority"]
            
            if priority == "primary":
                assert rules_count <= 4, f"Primary domain should have <= 4 rules, got {rules_count}"
                print(f"  ✓ Primary '{card['domain']}' has {rules_count} rules")
            elif priority == "secondary":
                assert rules_count <= 2, f"Secondary domain should have <= 2 rules, got {rules_count}"
                print(f"  ✓ Secondary '{card['domain']}' has {rules_count} rules")
            else:  # baseline
                assert rules_count <= 1, f"Baseline domain should have <= 1 rule, got {rules_count}"
                print(f"  ✓ Baseline '{card['domain']}' has {rules_count} rules")
        
        print(f"✓ Rule counts appropriate for priority levels")


class TestPlanAuditNewSchema:
    """Tests for GET /api/plan-audit with new PlanCard schema"""
    
    def test_plan_audit_returns_200(self, auth_session):
        """Test that plan-audit endpoint returns 200 status"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/plan-audit returned 200")
    
    def test_plan_audit_has_audit_summary(self, auth_session):
        """Test that audited plan has audit_summary field"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data"):
            pytest.skip("No audit data available")
        
        # Check for audit_summary or summary (support both schemas)
        has_summary = "audit_summary" in data or "summary" in data
        assert has_summary, "Missing audit_summary or summary field"
        
        summary = data.get("audit_summary") or data.get("summary", {})
        
        # Check for score info
        if "score" in summary:
            assert "/" in str(summary["score"]), "score should be in X/Y format"
            print(f"✓ audit_summary.score: {summary['score']}")
        elif "execution_score" in summary:
            assert "/" in str(summary["execution_score"]), "execution_score should be in X/Y format"
            print(f"✓ summary.execution_score: {summary['execution_score']}")
        
        # Check for game_result
        if "game_result" in summary:
            valid_results = {"win", "loss", "draw"}
            assert summary["game_result"] in valid_results, \
                f"Invalid game_result: {summary['game_result']}"
            print(f"✓ game_result: {summary['game_result']}")
    
    def test_plan_audit_card_audit_status(self, auth_session):
        """Test each card audit has status: executed/partial/missed/n/a"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data"):
            pytest.skip("No audit data available")
        
        cards = data.get("cards", [])
        if not cards:
            pytest.skip("No cards in response")
        
        valid_statuses = {"executed", "partial", "missed", "n/a", None}
        
        for card in cards:
            audit = card.get("audit", {})
            status = audit.get("status")
            assert status in valid_statuses, f"Invalid audit status '{status}' for {card['domain']}"
            print(f"  ✓ {card['domain']} audit status: {status}")
        
        print(f"✓ All card audit statuses are valid")
    
    def test_plan_audit_card_audit_fields(self, auth_session):
        """Test each card audit has data_points[], evidence[], coach_note"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data"):
            pytest.skip("No audit data available")
        
        cards = data.get("cards", [])
        if not cards:
            pytest.skip("No cards in response")
        
        for card in cards:
            audit = card.get("audit", {})
            
            # data_points should be list
            assert "data_points" in audit, f"Missing data_points for {card['domain']}"
            assert isinstance(audit["data_points"], list), "data_points should be list"
            
            # evidence should be list
            assert "evidence" in audit, f"Missing evidence for {card['domain']}"
            assert isinstance(audit["evidence"], list), "evidence should be list"
            
            # coach_note can be string or null
            assert "coach_note" in audit, f"Missing coach_note for {card['domain']}"
            
            data_points_count = len(audit["data_points"])
            evidence_count = len(audit["evidence"])
            print(f"  ✓ {card['domain']}: {data_points_count} data_points, {evidence_count} evidence")
        
        print(f"✓ All cards have audit structure with data_points, evidence, coach_note")
    
    def test_plan_audit_evidence_structure(self, auth_session):
        """Test evidence links have: move number, delta, note"""
        response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        assert response.status_code == 200
        
        data = response.json()
        if not data.get("has_data"):
            pytest.skip("No audit data available")
        
        cards = data.get("cards", [])
        if not cards:
            pytest.skip("No cards in response")
        
        evidence_found = False
        for card in cards:
            audit = card.get("audit", {})
            evidence_list = audit.get("evidence", [])
            
            for ev in evidence_list:
                evidence_found = True
                # Required: move (number)
                assert "move" in ev, f"Evidence missing 'move' field"
                assert isinstance(ev["move"], int), "move should be integer"
                
                # Optional but expected: delta, note
                if "delta" in ev and ev["delta"] is not None:
                    assert isinstance(ev["delta"], (int, float)), "delta should be number"
                
                print(f"  ✓ Evidence: Move {ev['move']}, delta: {ev.get('delta')}, note: '{ev.get('note', '')[:30]}'")
        
        if evidence_found:
            print(f"✓ Evidence structures are valid")
        else:
            print(f"✓ No evidence in this audit (may be a clean game)")


class TestCoachingLoopAuditGame:
    """Tests for POST /api/coaching-loop/audit-game/{game_id}"""
    
    def test_audit_game_endpoint_exists(self, auth_session):
        """Test that audit-game endpoint exists and requires game_id"""
        # Try with invalid game ID
        response = auth_session.post(f"{BASE_URL}/api/coaching-loop/audit-game/invalid_game_123")
        # Should return 404 (game not found) not 405 (method not allowed)
        assert response.status_code != 405, "audit-game endpoint should exist"
        print(f"✓ POST /api/coaching-loop/audit-game/{'{game_id}'} endpoint exists")


class TestCoachingLoopRegeneratePlan:
    """Tests for POST /api/coaching-loop/regenerate-plan"""
    
    def test_regenerate_plan_returns_new_plan(self, auth_session):
        """Test that regenerate-plan returns a fresh plan"""
        response = auth_session.post(f"{BASE_URL}/api/coaching-loop/regenerate-plan")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "plan_id" in data, "Response missing plan_id"
        assert "cards" in data, "Response missing cards"
        assert len(data.get("cards", [])) == 5, "Should have 5 domain cards"
        
        print(f"✓ regenerate-plan returned new plan: {data['plan_id'][:20]}...")


class TestCoachingLoopProfile:
    """Tests for GET /api/coaching-loop/profile"""
    
    def test_coaching_profile_endpoint(self, auth_session):
        """Test that coaching profile endpoint returns all inputs"""
        response = auth_session.get(f"{BASE_URL}/api/coaching-loop/profile")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check for profile components
        expected_fields = ["rating_band", "fundamentals", "behavior_patterns", "opening_stability"]
        for field in expected_fields:
            assert field in data, f"Profile missing '{field}' field"
        
        print(f"✓ coaching-loop/profile returns all profile data:")
        print(f"  - rating_band: {data.get('rating_band')}")
        print(f"  - fundamentals: {list(data.get('fundamentals', {}).keys())}")
        print(f"  - behavior_patterns: {data.get('behavior_patterns', {}).get('patterns', [])[:2]}")


class TestCoachingLoopConsistency:
    """Test consistency between round-preparation and plan-audit"""
    
    def test_same_schema_between_prep_and_audit(self, auth_session):
        """Test that round-preparation and plan-audit use same card schema"""
        prep_response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        audit_response = auth_session.get(f"{BASE_URL}/api/plan-audit")
        
        assert prep_response.status_code == 200
        assert audit_response.status_code == 200
        
        prep_data = prep_response.json()
        audit_data = audit_response.json()
        
        # Both should have cards array
        assert "cards" in prep_data, "round-preparation missing cards"
        
        # Compare card structure (if audit has data)
        if audit_data.get("has_data") and "cards" in audit_data:
            prep_card = prep_data["cards"][0]
            audit_card = audit_data["cards"][0]
            
            # Same required fields
            common_fields = {"domain", "priority", "goal", "rules", "success_criteria", "audit"}
            prep_fields = set(prep_card.keys())
            audit_fields = set(audit_card.keys())
            
            for field in common_fields:
                assert field in prep_fields, f"prep card missing {field}"
                assert field in audit_fields, f"audit card missing {field}"
            
            print(f"✓ Same schema used: {common_fields}")
        else:
            print(f"✓ Schema validated (audit has no data yet)")


class TestPlanCardSchema:
    """Validate the PlanCard schema (shared by prep and audit)"""
    
    def test_plancard_required_fields(self, auth_session):
        """Test PlanCard has: plan_id, user_id, generated_at, rating_band, training_block, cards"""
        response = auth_session.get(f"{BASE_URL}/api/round-preparation")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required PlanCard fields
        required = ["plan_id", "user_id", "generated_at", "rating_band", "training_block", "cards"]
        for field in required:
            assert field in data, f"PlanCard missing '{field}'"
        
        print(f"✓ PlanCard has all required fields")
        print(f"  - plan_id: {data['plan_id'][:20]}...")
        print(f"  - rating_band: {data['rating_band']}")
        print(f"  - training_block: {data['training_block']['name']}")
        print(f"  - cards count: {len(data['cards'])}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
