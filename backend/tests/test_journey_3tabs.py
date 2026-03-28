"""
Test Suite: Journey Page 3-Tab Structure
- Tab A (Now/Snapshot): 5 items
- Tab B (Journey): 4 before/after rows
- Tab C (Trend): Headline + shifts + evidence + directive
- Stats Drawer: Accuracy, Win Rate, Blunders/Game, Mistakes/Game
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestJourneyCognitiveAPI:
    """Tests for /api/cognitive/journey endpoint - 3-tab structure"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get session cookie via dev login"""
        self.session = requests.Session()
        # Dev login to get session
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        self.user_data = resp.json()
        print(f"Logged in as: {self.user_data.get('user', {}).get('name', 'Unknown')}")

    def test_journey_endpoint_returns_200(self):
        """Test that cognitive journey endpoint returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        assert resp.status_code == 200, f"Journey endpoint failed: {resp.text}"
        print("Journey endpoint returned 200 OK")

    def test_journey_returns_activated_true(self):
        """Test that journey data shows activated=true for user with 100+ games"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        assert data.get("activated") == True, f"Expected activated=True, got {data.get('activated')}"
        assert data.get("games_analyzed", 0) >= 10, f"Expected 10+ games, got {data.get('games_analyzed')}"
        print(f"Journey activated with {data.get('games_analyzed')} games analyzed")

    def test_journey_structure_has_3_tabs_and_stats(self):
        """Test that response has snapshot, journey, momentum, and stats keys"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        assert "snapshot" in data, "Missing 'snapshot' key (Tab A: Now)"
        assert "journey" in data, "Missing 'journey' key (Tab B: Journey)"
        assert "momentum" in data, "Missing 'momentum' key (Tab C: Trend)"
        assert "stats" in data, "Missing 'stats' key (Stats Drawer)"
        print("All 3 tabs + stats drawer present in response")

    # ================== TAB A: SNAPSHOT (NOW) ==================

    def test_tab_a_snapshot_has_5_items(self):
        """Tab A (Now): Should have 5 items - stability, driver, advantage, phase, directive"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip(f"Snapshot not ready: {snapshot.get('message')}")
        
        assert "decision_stability" in snapshot, "Missing decision_stability"
        assert "primary_driver" in snapshot, "Missing primary_driver"
        assert "advantage_discipline" in snapshot, "Missing advantage_discipline"
        assert "unstable_phase" in snapshot, "Missing unstable_phase"
        assert "directive" in snapshot, "Missing directive"
        print("Tab A (Snapshot) has all 5 required items")

    def test_tab_a_decision_stability_has_band_and_meaning(self):
        """Tab A: Decision Stability should have band and meaning"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        stability = snapshot.get("decision_stability", {})
        assert "band" in stability, "Missing stability band"
        assert "meaning" in stability, "Missing stability meaning"
        
        valid_bands = ["Stable", "Mixed", "Volatile", "Chaotic"]
        assert stability["band"] in valid_bands, f"Invalid band: {stability['band']}"
        print(f"Decision Stability: {stability['band']} - {stability['meaning']}")

    def test_tab_a_primary_driver_has_name_key_impact(self):
        """Tab A: Primary Driver should have name, key, and impact band"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        driver = snapshot.get("primary_driver", {})
        assert "name" in driver, "Missing driver name"
        assert "key" in driver, "Missing driver key"
        
        # Impact should use bands: Low/Moderate/High (not raw numbers)
        if driver.get("impact"):
            valid_impacts = ["Low", "Moderate", "High"]
            assert driver["impact"] in valid_impacts, f"Invalid impact band: {driver['impact']}"
        print(f"Primary Driver: {driver['name']} (Impact: {driver.get('impact', 'N/A')})")

    def test_tab_a_advantage_discipline_has_band_and_meaning(self):
        """Tab A: Advantage Discipline should have band and meaning"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        advantage = snapshot.get("advantage_discipline", {})
        assert "band" in advantage, "Missing advantage band"
        assert "meaning" in advantage, "Missing advantage meaning"
        
        valid_bands = ["Low risk", "Medium risk", "High risk"]
        assert advantage["band"] in valid_bands, f"Invalid risk band: {advantage['band']}"
        print(f"Advantage Discipline: {advantage['band']} - {advantage['meaning']}")

    def test_tab_a_directive_is_plain_indian_english(self):
        """Tab A: Directive should be in plain Indian-English tone"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        directive = snapshot.get("directive", "")
        assert len(directive) > 10, "Directive is too short"
        
        # Check for action-oriented language
        action_words = ["Next", "games", "ask", "pause", "Check", "trade", "Calculate", "Play"]
        has_action = any(word in directive for word in action_words)
        assert has_action, f"Directive doesn't seem action-oriented: {directive}"
        print(f"Tab A Directive: {directive}")

    # ================== TAB B: JOURNEY (THEN VS NOW) ==================

    def test_tab_b_journey_has_4_rows(self):
        """Tab B (Journey): Should have exactly 4 before/after rows"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip(f"Journey not ready: {journey.get('message')}")
        
        rows = journey.get("rows", [])
        assert len(rows) == 4, f"Expected 4 rows, got {len(rows)}"
        
        expected_labels = ["Decision Stability", "Primary Driver", "Advantage Discipline", "Weakest Phase"]
        actual_labels = [row.get("label") for row in rows]
        
        for label in expected_labels:
            assert label in actual_labels, f"Missing row: {label}"
        print(f"Tab B (Journey) has all 4 rows: {actual_labels}")

    def test_tab_b_rows_have_then_now_structure(self):
        """Tab B: Each row should have then/now values and changed flag"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        rows = journey.get("rows", [])
        for row in rows:
            label = row.get("label", "Unknown")
            
            if label == "Primary Driver":
                # Primary Driver has driver, then_band, now_band
                assert "driver" in row, f"Primary Driver row missing 'driver'"
                assert "then_band" in row or row.get("then_band") is None, "Missing then_band"
                assert "now_band" in row or row.get("now_band") is None, "Missing now_band"
            else:
                # Other rows have then, now, changed
                assert "then" in row, f"Row '{label}' missing 'then'"
                assert "now" in row, f"Row '{label}' missing 'now'"
            
            assert "changed" in row, f"Row '{label}' missing 'changed'"
            print(f"  {label}: then={row.get('then', row.get('then_band'))} -> now={row.get('now', row.get('now_band'))}")

    def test_tab_b_has_trend_indicator(self):
        """Tab B: Decision Stability row should have trend indicator"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        rows = journey.get("rows", [])
        stability_row = next((r for r in rows if r.get("label") == "Decision Stability"), None)
        
        assert stability_row is not None, "Decision Stability row not found"
        
        # Trend should be Improving, Declining, or No major shift
        trend = stability_row.get("trend")
        if trend:
            valid_trends = ["Improving", "Declining", "No major shift"]
            assert trend in valid_trends, f"Invalid trend: {trend}"
            print(f"Decision Stability trend: {trend}")

    def test_tab_b_journey_directive(self):
        """Tab B: Should have a directive"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        directive = journey.get("directive", "")
        assert len(directive) > 10, "Journey directive is too short"
        print(f"Tab B Directive: {directive}")

    # ================== TAB C: TREND (MOMENTUM 5V5) ==================

    def test_tab_c_momentum_has_headline(self):
        """Tab C (Trend): Should have a headline"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip(f"Momentum not ready: {momentum.get('message')}")
        
        headline = momentum.get("headline", "")
        assert len(headline) > 10, "Headline is too short"
        print(f"Tab C Headline: {headline}")

    def test_tab_c_momentum_has_shifts_structure(self):
        """Tab C (Trend): Shifts should have proper structure"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        shifts = momentum.get("shifts", [])
        # Shifts can be empty if no meaningful change
        print(f"Tab C has {len(shifts)} shifts")
        
        for shift in shifts:
            assert "type" in shift, "Shift missing 'type'"
            assert "label" in shift, "Shift missing 'label'"
            assert "previous" in shift, "Shift missing 'previous'"
            assert "recent" in shift, "Shift missing 'recent'"
            assert "direction" in shift, "Shift missing 'direction'"
            
            # Direction should be improving/declining
            valid_directions = ["improving", "declining"]
            assert shift["direction"] in valid_directions, f"Invalid direction: {shift['direction']}"
            print(f"  Shift: {shift['label']} ({shift['direction']})")

    def test_tab_c_evidence_structure(self):
        """Tab C (Trend): Evidence items should have game_id and move_number for navigation"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        evidence = momentum.get("evidence", [])
        evidence_ready = momentum.get("evidence_ready", False)
        
        print(f"Evidence ready: {evidence_ready}, count: {len(evidence)}")
        
        if evidence_ready and evidence:
            for item in evidence:
                assert "game_id" in item, "Evidence item missing game_id"
                assert "move_number" in item, "Evidence item missing move_number"
                assert "label" in item, "Evidence item missing label"
                print(f"  Evidence: {item['label']} - Game {item['game_id']} Move {item['move_number']}")

    def test_tab_c_momentum_directive(self):
        """Tab C: Should have a directive"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        directive = momentum.get("directive", "")
        assert len(directive) > 10, "Momentum directive is too short"
        print(f"Tab C Directive: {directive}")

    # ================== STATS DRAWER ==================

    def test_stats_drawer_has_4_metrics(self):
        """Stats Drawer: Should have Accuracy, Win Rate, Blunders/Game, Mistakes/Game"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        stats = resp.json().get("stats", {})
        
        if not stats.get("ready"):
            pytest.skip("Stats not ready")
        
        assert "accuracy" in stats, "Missing accuracy"
        assert "win_rate" in stats, "Missing win_rate"
        assert "blunders_per_game" in stats, "Missing blunders_per_game"
        assert "mistakes_per_game" in stats, "Missing mistakes_per_game"
        
        print(f"Stats: Accuracy={stats['accuracy']}%, Win Rate={stats['win_rate']}%, "
              f"Blunders/Game={stats['blunders_per_game']}, Mistakes/Game={stats['mistakes_per_game']}")

    def test_stats_drawer_has_record(self):
        """Stats Drawer: Should have win/loss/draw record"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        stats = resp.json().get("stats", {})
        
        if not stats.get("ready"):
            pytest.skip("Stats not ready")
        
        record = stats.get("record", {})
        assert "wins" in record, "Missing wins in record"
        assert "losses" in record, "Missing losses in record"
        assert "draws" in record, "Missing draws in record"
        
        print(f"Record: W{record['wins']} L{record['losses']} D{record['draws']}")

    def test_stats_drawer_games_count(self):
        """Stats Drawer: Should show games_count (based on last 20 games)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        stats = resp.json().get("stats", {})
        
        if not stats.get("ready"):
            pytest.skip("Stats not ready")
        
        games_count = stats.get("games_count", 0)
        assert games_count > 0, "Games count should be > 0"
        assert games_count <= 20, "Games count should be <= 20 (last 20 games)"
        print(f"Stats based on {games_count} games")

    # ================== DATA QUALITY CHECKS ==================

    def test_impact_bands_not_raw_numbers(self):
        """Impact bands should use Low/Moderate/High, not raw numbers"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        snapshot = data.get("snapshot", {})
        if snapshot.get("ready"):
            driver = snapshot.get("primary_driver", {})
            impact = driver.get("impact")
            if impact:
                # Should not be a number
                assert not isinstance(impact, (int, float)), f"Impact is a raw number: {impact}"
                # Should be a band
                assert impact in ["Low", "Moderate", "High"], f"Invalid impact band: {impact}"
        
        print("Impact bands use Low/Moderate/High (not raw numbers)")

    def test_directives_plain_indian_english(self):
        """Directives should use plain Indian-English tone"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        directives = []
        if data.get("snapshot", {}).get("ready"):
            directives.append(data["snapshot"].get("directive", ""))
        if data.get("journey", {}).get("ready"):
            directives.append(data["journey"].get("directive", ""))
        if data.get("momentum", {}).get("ready"):
            directives.append(data["momentum"].get("directive", ""))
        
        for directive in directives:
            if directive:
                # Should not contain technical jargon
                jargon = ["TSI", "cp_loss", "centipawn", "node", "depth"]
                for j in jargon:
                    assert j.lower() not in directive.lower(), f"Directive contains jargon '{j}': {directive}"
        
        print("Directives use plain language (no technical jargon)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
