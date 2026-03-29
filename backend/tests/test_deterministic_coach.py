"""
Test Suite: Deterministic Adaptive Coach - GM-Style Coaching System

Tests the Gold Feature coaching loop:
- Round Preparation (next game plan with 5-level intensity)
- Plan Audit (last game evaluation with evidence)
- Coaching Profile (fundamentals, patterns, domain history)
- Regenerate Plan (force new plan)

Rating bands tested: 1000-1400 (beginner_high)
User context: 1200-rated player with 25 games, piece_safety (76%) and advantage_collapse (52%) weaknesses
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRoundPreparationEndpoint:
    """Tests for GET /api/round-preparation - Next Game Plan"""
    
    def test_round_preparation_returns_200(self):
        """Round Preparation endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/round-preparation returns 200")
    
    def test_round_preparation_has_cards(self):
        """Round Preparation should have 5 domain cards"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        assert "cards" in data, "Response should have 'cards' field"
        assert len(data["cards"]) == 5, f"Should have 5 domain cards, got {len(data['cards'])}"
        
        # Verify all 5 domains present
        domains = [card["domain"] for card in data["cards"]]
        expected_domains = ["opening", "middlegame", "tactics", "endgame", "time"]
        for domain in expected_domains:
            assert domain in domains, f"Missing domain: {domain}"
        
        print(f"✓ Round Preparation has all 5 domain cards: {domains}")
    
    def test_round_preparation_has_rating_band(self):
        """Round Preparation should include rating band info"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        # Check rating band fields
        assert "rating_band" in data, "Should have rating_band field"
        assert "rating_label" in data, "Should have rating_label field"
        
        # Rating band should be one of the valid bands
        valid_bands = ["beginner_low", "beginner_high", "intermediate", "advanced"]
        assert data["rating_band"] in valid_bands, f"Invalid rating band: {data['rating_band']}"
        
        print(f"✓ Rating band: {data['rating_band']} ({data['rating_label']})")
    
    def test_round_preparation_training_block(self):
        """Round Preparation should have training block with intensity"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        assert "training_block" in data, "Should have training_block field"
        block = data["training_block"]
        
        # Training block should have required fields
        assert "name" in block, "Training block should have name"
        assert "intensity" in block, "Training block should have intensity"
        assert "intensity_name" in block, "Training block should have intensity_name"
        
        # Intensity should be 1-5
        intensity = block["intensity"]
        assert 1 <= intensity <= 5, f"Intensity should be 1-5, got {intensity}"
        
        # Intensity names should match
        intensity_names = {1: "Light", 2: "Normal", 3: "Focused", 4: "Intense", 5: "Critical"}
        expected_name = intensity_names.get(intensity)
        assert block["intensity_name"] == expected_name, f"Intensity name mismatch: {block['intensity_name']} vs {expected_name}"
        
        print(f"✓ Training block: {block['name']} at intensity {intensity}/5 ({block['intensity_name']})")
    
    def test_domain_card_structure(self):
        """Each domain card should have proper structure with escalation info"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        for card in data["cards"]:
            # Required fields
            assert "domain" in card, "Card should have domain"
            assert "priority" in card, "Card should have priority"
            assert "goal" in card, "Card should have goal"
            assert "rules" in card, "Card should have rules"
            assert "intensity" in card, "Card should have intensity"
            assert "intensity_name" in card, "Card should have intensity_name"
            assert "escalation" in card, "Card should have escalation"
            
            # Escalation structure
            esc = card["escalation"]
            assert "is_escalated" in esc, "Escalation should have is_escalated"
            assert "consecutive_misses" in esc, "Escalation should have consecutive_misses"
            assert "consecutive_executions" in esc, "Escalation should have consecutive_executions"
            
            # Intensity should be 1-5
            assert 1 <= card["intensity"] <= 5, f"Domain {card['domain']} intensity out of range"
            
            print(f"  ✓ {card['domain']}: priority={card['priority']}, L{card['intensity']}, escalated={esc['is_escalated']}")
        
        print("✓ All domain cards have proper structure with L1-5 levels and escalation")
    
    def test_domain_card_goals_non_empty(self):
        """Each domain should have non-empty goal text"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        for card in data["cards"]:
            assert len(card["goal"]) > 10, f"Domain {card['domain']} should have meaningful goal"
        
        print("✓ All domains have meaningful goal text")
    
    def test_focus_items_structure(self):
        """Focus items should have proper structure with pattern info"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        if "focus_items" in data and len(data["focus_items"]) > 0:
            for item in data["focus_items"]:
                assert "pattern" in item, "Focus item should have pattern"
                assert "pattern_name" in item, "Focus item should have pattern_name"
                if "move_number" in item:
                    assert isinstance(item["move_number"], int), "move_number should be integer"
                if "cp_lost" in item:
                    assert isinstance(item["cp_lost"], (int, float)), "cp_lost should be numeric"
            print(f"✓ Focus items present: {len(data['focus_items'])} critical patterns")
        else:
            print("✓ No focus items (expected if no recent critical patterns)")


class TestPlanAuditEndpoint:
    """Tests for GET /api/plan-audit - Last Game Evaluation"""
    
    def test_plan_audit_returns_200(self):
        """Plan Audit endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/plan-audit returns 200")
    
    def test_plan_audit_structure(self):
        """Plan Audit should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        data = response.json()
        
        # Check if audit has data
        if data.get("has_data") == False:
            print("✓ Plan Audit: No active plan to audit (expected for new users)")
            return
        
        # If we have data, verify structure
        if "cards" in data:
            assert "audit_summary" in data, "Should have audit_summary"
            assert "is_audited" in data, "Should have is_audited flag"
            print(f"✓ Plan Audit has audited data with {len(data['cards'])} domain cards")
    
    def test_plan_audit_summary_structure(self):
        """Audit summary should have execution score and game info"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        data = response.json()
        
        if data.get("has_data") == False:
            print("✓ No audit data available (skipping summary test)")
            return
        
        if "audit_summary" in data:
            summary = data["audit_summary"]
            
            # Check score format
            if "score" in summary:
                score = summary["score"]
                assert "/" in score, f"Score should be in X/Y format, got {score}"
                print(f"✓ Audit score: {score}")
            
            # Check game result
            if "game_result" in summary:
                valid_results = ["win", "loss", "draw"]
                assert summary["game_result"] in valid_results, f"Invalid game result: {summary['game_result']}"
                print(f"  Game result: {summary['game_result']}")
            
            # Check opponent info
            if "opponent_name" in summary:
                print(f"  Opponent: {summary['opponent_name']}")
    
    def test_audit_card_status_values(self):
        """Audit cards should have valid status: executed/partial/missed/n/a"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        data = response.json()
        
        if data.get("has_data") == False or "cards" not in data:
            print("✓ No audit cards to test (skipping)")
            return
        
        valid_statuses = ["executed", "partial", "missed", "n/a", None]
        
        for card in data["cards"]:
            if "audit" in card:
                status = card["audit"].get("status")
                assert status in valid_statuses, f"Invalid status for {card['domain']}: {status}"
                if status and status != "n/a":
                    print(f"  {card['domain']}: {status}")
        
        print("✓ All audit statuses are valid")
    
    def test_audit_evidence_links(self):
        """Audit evidence should link to specific game moves"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        data = response.json()
        
        if data.get("has_data") == False or "cards" not in data:
            print("✓ No audit evidence to test (skipping)")
            return
        
        evidence_count = 0
        for card in data["cards"]:
            if "audit" in card and card["audit"].get("evidence"):
                for ev in card["audit"]["evidence"]:
                    assert "move" in ev, "Evidence should have move number"
                    assert isinstance(ev["move"], int), "Move should be integer"
                    evidence_count += 1
        
        print(f"✓ Found {evidence_count} evidence links to game moves")
    
    def test_audit_coach_notes(self):
        """Audit should have coach notes for applicable domains"""
        response = requests.get(f"{BASE_URL}/api/plan-audit", cookies={"session_token": "test"})
        data = response.json()
        
        if data.get("has_data") == False or "cards" not in data:
            print("✓ No audit coach notes to test (skipping)")
            return
        
        notes_count = 0
        for card in data["cards"]:
            if "audit" in card and card["audit"].get("coach_note"):
                notes_count += 1
                print(f"  {card['domain']}: {card['audit']['coach_note'][:50]}...")
        
        print(f"✓ Found {notes_count} coach notes in audit")


class TestCoachingProfileEndpoint:
    """Tests for GET /api/coaching-loop/profile - Full Coaching Profile"""
    
    def test_coaching_profile_returns_200(self):
        """Coaching Profile endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/coaching-loop/profile", cookies={"session_token": "test"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/coaching-loop/profile returns 200")
    
    def test_coaching_profile_fundamentals(self):
        """Profile should include fundamentals scores (0-100) for each domain"""
        response = requests.get(f"{BASE_URL}/api/coaching-loop/profile", cookies={"session_token": "test"})
        data = response.json()
        
        assert "fundamentals" in data, "Profile should have fundamentals"
        fund = data["fundamentals"]
        
        # Check all domain scores exist
        domains = ["opening", "middlegame", "tactics", "endgame", "time"]
        for domain in domains:
            if domain in fund:
                score = fund[domain]
                assert 0 <= score <= 100, f"{domain} score should be 0-100, got {score}"
                print(f"  {domain}: {score}")
        
        # Check sample size
        if "sample_size" in fund:
            print(f"  Sample size: {fund['sample_size']} games")
        
        print("✓ Fundamentals profile has all domain scores")
    
    def test_coaching_profile_weakness_patterns(self):
        """Profile should include weakness patterns with evidence"""
        response = requests.get(f"{BASE_URL}/api/coaching-loop/profile", cookies={"session_token": "test"})
        data = response.json()
        
        assert "weakness_patterns" in data, "Profile should have weakness_patterns"
        patterns = data["weakness_patterns"]
        
        # Check structure
        if "patterns" in patterns:
            for p in patterns["patterns"]:
                assert "pattern" in p, "Pattern should have name"
                assert "severity" in p, "Pattern should have severity"
                if "rate" in p:
                    print(f"  {p['pattern']}: {p['severity']} ({p.get('frequency', 'N/A')})")
        
        # Check primary/secondary weakness
        if "primary_weakness" in patterns:
            print(f"  Primary weakness: {patterns['primary_weakness']}")
        if "secondary_weakness" in patterns:
            print(f"  Secondary weakness: {patterns['secondary_weakness']}")
        
        print("✓ Weakness patterns present in profile")
    
    def test_coaching_profile_domain_history(self):
        """Profile should include domain history with consecutive misses/executions"""
        response = requests.get(f"{BASE_URL}/api/coaching-loop/profile", cookies={"session_token": "test"})
        data = response.json()
        
        assert "domain_history" in data, "Profile should have domain_history"
        history = data["domain_history"]
        
        # Check all domains
        domains = ["opening", "middlegame", "tactics", "endgame", "time"]
        for domain in domains:
            if domain in history:
                dh = history[domain]
                assert "consecutive_misses" in dh, f"{domain} should have consecutive_misses"
                assert "consecutive_executions" in dh, f"{domain} should have consecutive_executions"
                
                misses = dh["consecutive_misses"]
                execs = dh["consecutive_executions"]
                if misses > 0 or execs > 0:
                    print(f"  {domain}: {misses} misses, {execs} executions")
        
        print("✓ Domain history tracks consecutive misses/executions")
    
    def test_coaching_profile_rating_band(self):
        """Profile should include rating band with correct label"""
        response = requests.get(f"{BASE_URL}/api/coaching-loop/profile", cookies={"session_token": "test"})
        data = response.json()
        
        assert "rating_band" in data, "Profile should have rating_band"
        band = data["rating_band"]
        
        # Check band structure
        assert "name" in band, "Rating band should have name"
        assert "label" in band, "Rating band should have label"
        
        # Valid band names and labels
        valid_labels = ["600-1000", "1000-1400", "1400-1800", "1800+"]
        assert band["label"] in valid_labels, f"Invalid rating band label: {band['label']}"
        
        print(f"✓ Rating band: {band['name']} ({band['label']})")


class TestRegeneratePlanEndpoint:
    """Tests for POST /api/coaching-loop/regenerate-plan"""
    
    def test_regenerate_plan_returns_200(self):
        """Regenerate Plan endpoint should return 200"""
        response = requests.post(f"{BASE_URL}/api/coaching-loop/regenerate-plan", cookies={"session_token": "test"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ POST /api/coaching-loop/regenerate-plan returns 200")
    
    def test_regenerate_plan_returns_new_plan(self):
        """Regenerate should return a full new plan structure"""
        response = requests.post(f"{BASE_URL}/api/coaching-loop/regenerate-plan", cookies={"session_token": "test"})
        data = response.json()
        
        # Should have plan structure
        assert "cards" in data, "Should return plan with cards"
        assert len(data["cards"]) == 5, "Should have 5 domain cards"
        assert "plan_id" in data, "Should have plan_id"
        assert "is_active" in data, "Should have is_active flag"
        
        print(f"✓ Regenerated plan: {data['plan_id']}, active={data['is_active']}")
    
    def test_regenerate_plan_is_active(self):
        """Regenerated plan should be marked as active"""
        response = requests.post(f"{BASE_URL}/api/coaching-loop/regenerate-plan", cookies={"session_token": "test"})
        data = response.json()
        
        assert data.get("is_active") == True, "Regenerated plan should be active"
        assert data.get("is_audited") == False, "Regenerated plan should not be audited yet"
        
        print("✓ Regenerated plan is active and not yet audited")


class TestIntensityLevels:
    """Tests specifically for 5-level intensity system"""
    
    def test_intensity_l1_light(self):
        """Level 1 (Light) should have 4 rules per domain"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        for card in data["cards"]:
            if card["intensity"] == 1:
                assert card["intensity_name"] == "Light", "L1 should be 'Light'"
                # Light can have up to 4 rules
                assert len(card["rules"]) <= 4, f"L1 should have ≤4 rules, got {len(card['rules'])}"
                print(f"✓ L1 {card['domain']}: {len(card['rules'])} rules")
        
        print("✓ L1 (Light) intensity configured correctly")
    
    def test_intensity_names_match_levels(self):
        """Intensity names should match levels (1=Light, 2=Normal, etc.)"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        level_names = {
            1: "Light",
            2: "Normal",
            3: "Focused",
            4: "Intense",
            5: "Critical"
        }
        
        for card in data["cards"]:
            expected_name = level_names.get(card["intensity"])
            assert card["intensity_name"] == expected_name, \
                f"{card['domain']} L{card['intensity']} should be '{expected_name}', got '{card['intensity_name']}'"
        
        print("✓ All intensity names match levels correctly")
    
    def test_escalated_domains_higher_intensity(self):
        """Escalated domains (consecutive misses >= 2) should have higher intensity"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        for card in data["cards"]:
            esc = card["escalation"]
            if esc["consecutive_misses"] >= 2:
                # Escalated domains should be intensity >= 3
                assert card["intensity"] >= 3 or esc["is_escalated"], \
                    f"Escalated {card['domain']} should have higher intensity"
                print(f"✓ {card['domain']} escalated with {esc['consecutive_misses']} misses → L{card['intensity']}")


class TestEscalationWarnings:
    """Tests for escalation warnings for intensity >= 4"""
    
    def test_escalation_flag_on_consecutive_misses(self):
        """is_escalated should be true when consecutive_misses >= 2"""
        response = requests.get(f"{BASE_URL}/api/round-preparation", cookies={"session_token": "test"})
        data = response.json()
        
        for card in data["cards"]:
            esc = card["escalation"]
            misses = esc["consecutive_misses"]
            
            if misses >= 2:
                assert esc["is_escalated"] == True, \
                    f"{card['domain']} with {misses} misses should be escalated"
        
        print("✓ Escalation flags set correctly based on consecutive misses")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
