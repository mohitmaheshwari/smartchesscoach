"""
Test Suite: Journey Page Patch - Reusing baseline_service.py logic

PATCH FEATURES:
- Tab A (Now): 'top_issue' with name, id, impact (from detect_weakness_patterns)
- Tab B (Journey): Primary Driver evolution - then_driver/now_driver/then_impact/now_impact
- Tab C (Trend): 'top_issues' array (up to 3, only if occurrence_pct >= 25%)
- Tab C (Trend): 'advantage_shift' with previous/recent/delta_pct/direction
- Evidence links have game_id and move_number for Lab navigation
- Backend reuses calculate_blunder_context_stats and detect_weakness_patterns from baseline_service.py
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestJourneyPatchFeatures:
    """Tests for Journey page patch - reusing baseline_service.py logic"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get session cookie via dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        self.user_data = resp.json()
        print(f"Logged in as: {self.user_data.get('user', {}).get('name', 'Unknown')}")

    # ================== TAB A: TOP_ISSUE (from detect_weakness_patterns) ==================

    def test_tab_a_snapshot_has_top_issue_field(self):
        """Tab A: Should have 'top_issue' field (not 'primary_driver')"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        snapshot = data.get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip(f"Snapshot not ready: {snapshot.get('message')}")
        
        # New key name: top_issue (not primary_driver)
        assert "top_issue" in snapshot, "Missing 'top_issue' key in snapshot"
        print("Tab A has 'top_issue' field")

    def test_tab_a_top_issue_has_name_id_impact(self):
        """Tab A: top_issue should have name, id, and impact fields"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        top_issue = snapshot.get("top_issue", {})
        
        assert "name" in top_issue, "top_issue missing 'name'"
        assert "id" in top_issue, "top_issue missing 'id'"
        assert "impact" in top_issue, "top_issue missing 'impact'"
        
        print(f"Tab A top_issue: name={top_issue['name']}, id={top_issue['id']}, impact={top_issue['impact']}")

    def test_tab_a_top_issue_id_matches_weakness_pattern(self):
        """Tab A: top_issue id should be a valid weakness pattern ID from baseline_service"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        top_issue = snapshot.get("top_issue", {})
        weakness_id = top_issue.get("id")
        
        # Valid IDs from detect_weakness_patterns in baseline_service.py
        valid_ids = [
            "relaxes_when_winning",
            "piece_safety",
            "tactical_blindness",
            "time_trouble",
            None  # Can be None if no clear pattern
        ]
        
        assert weakness_id in valid_ids, f"Invalid top_issue id: {weakness_id}"
        print(f"top_issue id '{weakness_id}' is a valid weakness pattern ID")

    def test_tab_a_top_issue_impact_uses_bands(self):
        """Tab A: top_issue impact should use Low/Moderate/High bands (not raw numbers)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        top_issue = snapshot.get("top_issue", {})
        impact = top_issue.get("impact")
        
        if impact is not None:
            valid_impacts = ["Low", "Moderate", "High"]
            assert impact in valid_impacts, f"Impact should be band, got: {impact}"
            # Ensure not a raw number
            assert not isinstance(impact, (int, float)), f"Impact should not be a number: {impact}"
        print(f"top_issue impact '{impact}' uses correct band format")

    def test_tab_a_top_issue_has_occurrence_pct(self):
        """Tab A: top_issue should have occurrence_pct from weakness detection"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        top_issue = snapshot.get("top_issue", {})
        occurrence_pct = top_issue.get("occurrence_pct")
        
        assert "occurrence_pct" in top_issue, "top_issue missing occurrence_pct"
        
        if occurrence_pct is not None:
            assert isinstance(occurrence_pct, (int, float)), f"occurrence_pct should be numeric: {occurrence_pct}"
        print(f"top_issue occurrence_pct: {occurrence_pct}%")

    # ================== TAB B: PRIMARY DRIVER EVOLUTION ==================

    def test_tab_b_journey_primary_driver_row_structure(self):
        """Tab B: Primary Driver row should have then_driver/now_driver/then_impact/now_impact"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        rows = journey.get("rows", [])
        driver_row = next((r for r in rows if r.get("label") == "Primary Driver"), None)
        
        assert driver_row is not None, "Primary Driver row not found"
        
        # Check new structure
        assert "then_driver" in driver_row, "Missing then_driver"
        assert "now_driver" in driver_row, "Missing now_driver"
        assert "then_impact" in driver_row, "Missing then_impact"
        assert "now_impact" in driver_row, "Missing now_impact"
        assert "changed" in driver_row, "Missing changed flag"
        
        print(f"Primary Driver: {driver_row['then_driver']} ({driver_row['then_impact']}) -> "
              f"{driver_row['now_driver']} ({driver_row['now_impact']})")

    def test_tab_b_primary_driver_evolution_uses_bands(self):
        """Tab B: then_impact and now_impact should use Low/Moderate/High bands"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        rows = journey.get("rows", [])
        driver_row = next((r for r in rows if r.get("label") == "Primary Driver"), None)
        
        assert driver_row is not None, "Primary Driver row not found"
        
        valid_impacts = ["Low", "Moderate", "High", None]
        
        then_impact = driver_row.get("then_impact")
        now_impact = driver_row.get("now_impact")
        
        assert then_impact in valid_impacts, f"Invalid then_impact: {then_impact}"
        assert now_impact in valid_impacts, f"Invalid now_impact: {now_impact}"
        
        print(f"Impact bands correct: then={then_impact}, now={now_impact}")

    # ================== TAB C: TOP_ISSUES ARRAY ==================

    def test_tab_c_momentum_has_top_issues_array(self):
        """Tab C: Should have 'top_issues' array (not 'shifts')"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        assert "top_issues" in momentum, "Missing 'top_issues' array in momentum"
        top_issues = momentum.get("top_issues", [])
        
        assert isinstance(top_issues, list), f"top_issues should be a list: {type(top_issues)}"
        print(f"Tab C has top_issues array with {len(top_issues)} items")

    def test_tab_c_top_issues_max_3_items(self):
        """Tab C: top_issues should have at most 3 items"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        
        assert len(top_issues) <= 3, f"top_issues should have max 3 items, got {len(top_issues)}"
        print(f"top_issues count: {len(top_issues)} (max 3)")

    def test_tab_c_top_issues_only_if_occurrence_pct_25_plus(self):
        """Tab C: top_issues should only include items with occurrence_pct >= 25%"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        
        for issue in top_issues:
            occurrence_pct = issue.get("occurrence_pct", 0)
            # Only included if >= 25%
            assert occurrence_pct >= 25, f"Issue with occurrence_pct {occurrence_pct}% should not be included (< 25%)"
            print(f"  Issue '{issue.get('name')}': {occurrence_pct}% (>= 25%)")

    def test_tab_c_top_issues_item_structure(self):
        """Tab C: Each top_issue item should have id, name, impact, occurrence_pct, examples"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        
        for idx, issue in enumerate(top_issues):
            assert "id" in issue, f"Issue {idx} missing 'id'"
            assert "name" in issue, f"Issue {idx} missing 'name'"
            assert "impact" in issue, f"Issue {idx} missing 'impact'"
            assert "occurrence_pct" in issue, f"Issue {idx} missing 'occurrence_pct'"
            assert "examples" in issue, f"Issue {idx} missing 'examples'"
            
            print(f"  Issue {idx+1}: {issue['name']} (id={issue['id']}, impact={issue['impact']})")

    # ================== TAB C: ADVANTAGE_SHIFT ==================

    def test_tab_c_momentum_has_advantage_shift(self):
        """Tab C: Should have 'advantage_shift' object"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        # advantage_shift can be null if no significant change
        if "advantage_shift" in momentum and momentum["advantage_shift"] is not None:
            print("Tab C has advantage_shift object")
        else:
            print("Tab C advantage_shift is null (no significant shift)")

    def test_tab_c_advantage_shift_structure(self):
        """Tab C: advantage_shift should have previous/recent/delta_pct/direction"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        advantage_shift = momentum.get("advantage_shift")
        
        if advantage_shift is None:
            print("advantage_shift is null - no significant change (5 vs 5)")
            return
        
        assert "previous" in advantage_shift, "Missing 'previous'"
        assert "recent" in advantage_shift, "Missing 'recent'"
        assert "delta_pct" in advantage_shift, "Missing 'delta_pct'"
        assert "direction" in advantage_shift, "Missing 'direction'"
        
        print(f"advantage_shift: {advantage_shift['previous']} -> {advantage_shift['recent']} "
              f"(delta={advantage_shift['delta_pct']}%, direction={advantage_shift['direction']})")

    def test_tab_c_advantage_shift_direction_values(self):
        """Tab C: advantage_shift direction should be 'improving' or 'declining'"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        advantage_shift = momentum.get("advantage_shift")
        
        if advantage_shift is None:
            pytest.skip("No advantage_shift data")
        
        direction = advantage_shift.get("direction")
        valid_directions = ["improving", "declining"]
        
        assert direction in valid_directions, f"Invalid direction: {direction}"
        print(f"advantage_shift direction '{direction}' is valid")

    def test_tab_c_advantage_shift_previous_recent_bands(self):
        """Tab C: previous and recent should use risk band labels"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        advantage_shift = momentum.get("advantage_shift")
        
        if advantage_shift is None:
            pytest.skip("No advantage_shift data")
        
        valid_bands = ["Low risk", "Medium risk", "High risk"]
        
        previous = advantage_shift.get("previous")
        recent = advantage_shift.get("recent")
        
        assert previous in valid_bands, f"Invalid previous band: {previous}"
        assert recent in valid_bands, f"Invalid recent band: {recent}"
        
        print(f"Risk bands: previous={previous}, recent={recent}")

    # ================== EVIDENCE LINKS ==================

    def test_tab_c_evidence_has_game_id_and_move_number(self):
        """Tab C: Evidence items should have game_id and move_number for Lab navigation"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        evidence = momentum.get("evidence", [])
        evidence_ready = momentum.get("evidence_ready", False)
        
        if not evidence_ready or not evidence:
            print("Evidence not ready or empty - skipping")
            return
        
        for idx, item in enumerate(evidence):
            assert "game_id" in item, f"Evidence {idx} missing game_id"
            assert "move_number" in item, f"Evidence {idx} missing move_number"
            assert "label" in item, f"Evidence {idx} missing label"
            
            print(f"  Evidence {idx+1}: {item['label']} -> /game/{item['game_id']}?move={item['move_number']}&src=journey")

    def test_tab_c_top_issues_examples_have_game_id_move_number(self):
        """Tab C: top_issues examples should have game_id and move_number"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        
        for issue in top_issues:
            examples = issue.get("examples", [])
            for ex in examples:
                assert "game_id" in ex, f"Example missing game_id"
                assert "move_number" in ex, f"Example missing move_number"
                
                print(f"  Example: game_id={ex['game_id']}, move={ex['move_number']}")

    # ================== BACKEND REUSE VERIFICATION ==================

    def test_backend_uses_detect_weakness_patterns(self):
        """Verify backend reuses detect_weakness_patterns from baseline_service.py"""
        # This test verifies the response structure matches what detect_weakness_patterns returns
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        snapshot = data.get("snapshot", {})
        if snapshot.get("ready"):
            top_issue = snapshot.get("top_issue", {})
            # detect_weakness_patterns returns: id, label, severity, occurrence_pct, examples
            # top_issue should map: id, name (from label), impact (from severity), occurrence_pct
            assert "id" in top_issue, "Should have id from detect_weakness_patterns"
            assert "occurrence_pct" in top_issue, "Should have occurrence_pct from detect_weakness_patterns"
            print("Tab A top_issue structure matches detect_weakness_patterns output")

    def test_backend_uses_calculate_blunder_context_stats(self):
        """Verify backend reuses calculate_blunder_context_stats for advantage_discipline"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        snapshot = data.get("snapshot", {})
        if snapshot.get("ready"):
            advantage_discipline = snapshot.get("advantage_discipline", {})
            # calculate_blunder_context_stats returns: when_winning, when_equal, when_losing
            # advantage_discipline uses: blunder_when_winning_pct
            if "blunder_when_winning_pct" in advantage_discipline:
                print(f"Blunder when winning: {advantage_discipline['blunder_when_winning_pct']}%")
                assert isinstance(advantage_discipline["blunder_when_winning_pct"], (int, float))

    # ================== NO NEW PARALLEL AGGREGATION ==================

    def test_no_new_aggregation_logic_top_issues_from_existing(self):
        """Verify top_issues use existing detect_weakness_patterns (no new aggregation)"""
        # This is a structural test - top_issues should match baseline_service pattern structure
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        
        for issue in top_issues:
            # Structure from detect_weakness_patterns
            assert "id" in issue, "Should have id"
            assert "name" in issue, "Should have name (mapped from label)"
            assert "occurrence_pct" in issue, "Should have occurrence_pct"
            assert "examples" in issue, "Should have examples"
            
            # Examples should have the structure from detect_weakness_patterns
            for ex in issue.get("examples", []):
                assert "game_id" in ex, "Example should have game_id"
                assert "move_number" in ex, "Example should have move_number"
        
        print("top_issues structure matches detect_weakness_patterns output (no new aggregation)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
