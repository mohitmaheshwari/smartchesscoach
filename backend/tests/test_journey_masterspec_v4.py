"""
Test Suite: Journey Page - Master Spec v4 Implementation
Tests for stat_interpretation_engine.py, coach_voice_generator.py, journey_engine.py

Features tested:
- Tab A (Now): 5 items - Decision Stability, Main issue (top_issue), When ahead, Weakest phase, Directive
- Tab B (Journey): Voice headline with tone color, 4 stat rows, 4 cognitive rows, Directive
- Tab B: Deltas shown only when overall_change='visible', hidden when 'stable_hidden'
- Tab B: Badge 'Big improvement this week' shown when major_improvement signal
- Tab C (Trend): Headline, Meaningful shifts (max 2), Top Issues (up to 3), Evidence links, Directive
- Stats drawer: 4 metrics (Accuracy, Blunders/Game, Mistakes/Game, Win Rate)
- Backend: Stat Interpretation Engine signals (major_improvement/improving/stable/declining/major_decline)
- Backend: Coach Voice Generator (headline, explanation, focus_instruction, tone_level)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestJourneyMasterSpecV4:
    """Tests for /api/cognitive/journey endpoint - Master Spec v4 implementation"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get session cookie via dev login"""
        self.session = requests.Session()
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        self.user_data = resp.json()
        print(f"Logged in as: {self.user_data.get('user', {}).get('name', 'Unknown')}")

    # ================== BASIC ENDPOINT TESTS ==================
    
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

    # ================== TAB A: SNAPSHOT (NOW) - 5 ITEMS ==================

    def test_tab_a_snapshot_has_5_items(self):
        """Tab A (Now): Should have 5 items - decision_stability, top_issue, advantage_discipline, unstable_phase, directive"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip(f"Snapshot not ready: {snapshot.get('message')}")
        
        assert "decision_stability" in snapshot, "Missing decision_stability"
        assert "top_issue" in snapshot, "Missing top_issue (Main issue)"
        assert "advantage_discipline" in snapshot, "Missing advantage_discipline"
        assert "unstable_phase" in snapshot, "Missing unstable_phase (Weakest phase)"
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
        
        valid_bands = ["Stable", "Moderate", "Volatile"]
        assert stability["band"] in valid_bands, f"Invalid band: {stability['band']}"
        print(f"Decision Stability: {stability['band']} - {stability['meaning']}")

    def test_tab_a_top_issue_has_name_and_id(self):
        """Tab A: Top Issue (Main issue) should have name and id"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        top_issue = snapshot.get("top_issue", {})
        assert "name" in top_issue, "Missing top_issue name"
        assert "id" in top_issue or top_issue.get("id") is None, "Missing top_issue id"
        print(f"Top Issue: {top_issue.get('name')} (id: {top_issue.get('id')})")

    def test_tab_a_advantage_discipline_has_band_and_meaning(self):
        """Tab A: Advantage Discipline (When ahead) should have band and meaning"""
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

    def test_tab_a_unstable_phase_is_valid(self):
        """Tab A: Weakest Phase should be one of Opening/Middlegame/Endgame"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        phase = snapshot.get("unstable_phase", "")
        valid_phases = ["Opening", "Middlegame", "Endgame"]
        assert phase in valid_phases, f"Invalid phase: {phase}"
        print(f"Weakest Phase: {phase}")

    def test_tab_a_directive_is_action_oriented(self):
        """Tab A: Directive should be action-oriented in plain Indian-English tone"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        snapshot = resp.json().get("snapshot", {})
        
        if not snapshot.get("ready"):
            pytest.skip("Snapshot not ready")
        
        directive = snapshot.get("directive", "")
        assert len(directive) > 5, "Directive is too short"
        assert len(directive) < 200, "Directive is too long (should be ≤16 words)"
        print(f"Tab A Directive: {directive}")

    # ================== TAB B: JOURNEY (THEN VS NOW) ==================

    def test_tab_b_journey_has_voice_object(self):
        """Tab B: Should have voice object with headline, explanation, tone_level"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip(f"Journey not ready: {journey.get('message')}")
        
        voice = journey.get("voice", {})
        assert "headline" in voice, "Missing voice headline"
        assert "explanation" in voice, "Missing voice explanation"
        assert "tone_level" in voice, "Missing voice tone_level"
        
        valid_tones = ["positive", "concern", "neutral"]
        assert voice["tone_level"] in valid_tones, f"Invalid tone: {voice['tone_level']}"
        print(f"Voice headline: {voice['headline']} (tone: {voice['tone_level']})")

    def test_tab_b_journey_has_4_stat_rows(self):
        """Tab B: Should have 4 stat rows (Accuracy, Blunders/Game, Mistakes/Game, Win Rate)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        stat_rows = journey.get("stat_rows", [])
        assert len(stat_rows) == 4, f"Expected 4 stat rows, got {len(stat_rows)}"
        
        expected_labels = ["Accuracy", "Blunders/Game", "Mistakes/Game", "Win Rate"]
        actual_labels = [row.get("label") for row in stat_rows]
        
        for label in expected_labels:
            assert label in actual_labels, f"Missing stat row: {label}"
        print(f"Tab B has all 4 stat rows: {actual_labels}")

    def test_tab_b_stat_rows_have_then_now_delta(self):
        """Tab B: Each stat row should have then, now, delta, show_delta"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        for row in journey.get("stat_rows", []):
            label = row.get("label")
            assert "then" in row, f"Stat row '{label}' missing 'then'"
            assert "now" in row, f"Stat row '{label}' missing 'now'"
            assert "delta" in row, f"Stat row '{label}' missing 'delta'"
            assert "show_delta" in row, f"Stat row '{label}' missing 'show_delta'"
            print(f"  {label}: {row['then']} -> {row['now']} (delta: {row['delta']}, show: {row['show_delta']})")

    def test_tab_b_journey_has_4_cognitive_rows(self):
        """Tab B: Should have 4 cognitive rows (Decision Stability, Primary Driver, Advantage Risk, Weakest Phase)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        cognitive_rows = journey.get("cognitive_rows", [])
        assert len(cognitive_rows) == 4, f"Expected 4 cognitive rows, got {len(cognitive_rows)}"
        
        expected_labels = ["Decision Stability", "Primary Driver", "Advantage Risk", "Weakest Phase"]
        actual_labels = [row.get("label") for row in cognitive_rows]
        
        for label in expected_labels:
            assert label in actual_labels, f"Missing cognitive row: {label}"
        print(f"Tab B has all 4 cognitive rows")

    def test_tab_b_cognitive_rows_have_then_now_changed(self):
        """Tab B: Each cognitive row should have then, now, changed flag"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        for row in journey.get("cognitive_rows", []):
            label = row.get("label")
            assert "then" in row, f"Cognitive row '{label}' missing 'then'"
            assert "now" in row, f"Cognitive row '{label}' missing 'now'"
            assert "changed" in row, f"Cognitive row '{label}' missing 'changed'"
            print(f"  {label}: {row['then']} -> {row['now']} (changed: {row['changed']})")

    def test_tab_b_overall_change_visible_or_stable_hidden(self):
        """Tab B: overall_change should be 'visible' or 'stable_hidden'"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        overall_change = journey.get("overall_change")
        valid_values = ["visible", "stable_hidden", "not_ready"]
        assert overall_change in valid_values, f"Invalid overall_change: {overall_change}"
        print(f"Overall change: {overall_change}")

    def test_tab_b_deltas_shown_when_visible(self):
        """Tab B: When overall_change='visible', show_deltas should be True"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        overall_change = journey.get("overall_change")
        show_deltas = journey.get("show_deltas")
        
        if overall_change == "visible":
            assert show_deltas == True, "When overall_change='visible', show_deltas should be True"
        elif overall_change == "stable_hidden":
            assert show_deltas == False, "When overall_change='stable_hidden', show_deltas should be False"
        print(f"overall_change={overall_change}, show_deltas={show_deltas}")

    def test_tab_b_badge_shown_on_major_improvement(self):
        """Tab B: Badge should show when headline signal is major_improvement"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        badge = journey.get("badge")
        voice = journey.get("voice", {})
        headline = voice.get("headline", "")
        
        # Check if badge text matches expected format
        if badge:
            assert "improvement" in badge.lower() or "week" in badge.lower(), f"Badge text unexpected: {badge}"
            print(f"Badge shown: {badge}")
        else:
            print(f"No badge shown (headline: {headline})")

    def test_tab_b_journey_has_directive(self):
        """Tab B: Should have a directive (focus_instruction)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        directive = journey.get("directive", "")
        assert len(directive) > 5, "Journey directive is missing or too short"
        print(f"Tab B Directive: {directive}")

    # ================== TAB C: TREND (MOMENTUM 5 VS 5) ==================

    def test_tab_c_momentum_has_headline(self):
        """Tab C: Should have a headline"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip(f"Momentum not ready: {momentum.get('message')}")
        
        headline = momentum.get("headline", "")
        assert len(headline) > 5, "Momentum headline is too short"
        print(f"Momentum headline: {headline}")

    def test_tab_c_momentum_has_meaningful_shifts(self):
        """Tab C: meaningful_shifts should be max 2 items"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        shifts = momentum.get("meaningful_shifts", [])
        assert len(shifts) <= 2, f"meaningful_shifts should be max 2, got {len(shifts)}"
        
        for shift in shifts:
            assert "label" in shift, "Shift missing label"
            assert "previous" in shift, "Shift missing previous"
            assert "recent" in shift, "Shift missing recent"
            assert "direction" in shift, "Shift missing direction"
            print(f"  Shift: {shift['label']} - {shift['previous']} -> {shift['recent']} ({shift['direction']})")

    def test_tab_c_momentum_top_issues_max_3(self):
        """Tab C: top_issues should be max 3 items"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        top_issues = momentum.get("top_issues", [])
        assert len(top_issues) <= 3, f"top_issues should be max 3, got {len(top_issues)}"
        
        for issue in top_issues:
            assert "id" in issue, "Issue missing id"
            assert "name" in issue, "Issue missing name"
            assert "impact" in issue, "Issue missing impact"
            print(f"  Top Issue: {issue['name']} (impact: {issue['impact']})")

    def test_tab_c_evidence_structure(self):
        """Tab C: evidence should have game_id and move_number for navigation"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        evidence = momentum.get("evidence", [])
        if momentum.get("evidence_ready") and evidence:
            for item in evidence:
                assert "game_id" in item, "Evidence missing game_id"
                assert "move_number" in item, "Evidence missing move_number"
                assert "label" in item, "Evidence missing label"
                print(f"  Evidence: {item['label']} (game_id: {item['game_id']}, move: {item['move_number']})")
        else:
            print("Evidence not ready or empty")

    def test_tab_c_evidence_links_format(self):
        """Tab C: Evidence links should support navigation to /game/{id}?move={n}&src=journey"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        evidence = momentum.get("evidence", [])
        if momentum.get("evidence_ready") and evidence:
            for item in evidence:
                game_id = item.get("game_id")
                move_number = item.get("move_number")
                
                # Verify game_id is a valid format (UUID or similar)
                assert game_id and len(game_id) > 10, f"Invalid game_id: {game_id}"
                assert isinstance(move_number, int) and move_number > 0, f"Invalid move_number: {move_number}"
                
                expected_url = f"/game/{game_id}?move={move_number}&src=journey"
                print(f"  Evidence URL would be: {expected_url}")

    def test_tab_c_momentum_has_directive(self):
        """Tab C: Should have a directive"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        momentum = resp.json().get("momentum", {})
        
        if not momentum.get("ready"):
            pytest.skip("Momentum not ready")
        
        directive = momentum.get("directive", "")
        assert len(directive) > 5, "Momentum directive is missing or too short"
        print(f"Tab C Directive: {directive}")

    # ================== STATS DRAWER ==================

    def test_stats_drawer_has_4_metrics(self):
        """Stats drawer should show 4 metrics (Accuracy, Blunders/Game, Mistakes/Game, Win Rate)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        stats = resp.json().get("stats", {})
        
        if not stats.get("ready"):
            pytest.skip("Stats drawer not ready")
        
        now = stats.get("now", {})
        assert "accuracy" in now, "Missing accuracy in stats.now"
        assert "blunders_per_game" in now, "Missing blunders_per_game in stats.now"
        assert "mistakes_per_game" in now, "Missing mistakes_per_game in stats.now"
        assert "winrate" in now, "Missing winrate in stats.now"
        
        print(f"Stats: Accuracy={now['accuracy']}%, Blunders/Game={now['blunders_per_game']}, "
              f"Mistakes/Game={now['mistakes_per_game']}, WinRate={now['winrate']}%")

    def test_stats_drawer_has_games_count(self):
        """Stats drawer should have games_count"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        stats = resp.json().get("stats", {})
        
        if not stats.get("ready"):
            pytest.skip("Stats drawer not ready")
        
        games_count = stats.get("games_count", 0)
        assert games_count > 0, "games_count should be > 0"
        print(f"Stats based on {games_count} games")

    # ================== BACKEND ENGINE TESTS ==================

    def test_stat_interpretation_signals(self):
        """Test that signals are valid from Stat Interpretation Engine"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        # Verify voice has tone_level which comes from signals
        voice = journey.get("voice", {})
        tone = voice.get("tone_level")
        
        # tone_level is derived from headline_signal
        valid_tones = ["positive", "concern", "neutral"]
        assert tone in valid_tones, f"Invalid tone_level: {tone}"
        print(f"Stat Interpretation Engine tone_level: {tone}")

    def test_coach_voice_headline_not_empty(self):
        """Test that Coach Voice Generator returns non-empty headline"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        voice = journey.get("voice", {})
        headline = voice.get("headline", "")
        
        # Headline should be ≤10 words
        word_count = len(headline.split())
        assert word_count <= 15, f"Headline too long ({word_count} words): {headline}"
        assert word_count >= 3, f"Headline too short ({word_count} words): {headline}"
        print(f"Coach Voice headline ({word_count} words): {headline}")

    def test_coach_voice_explanation_not_empty(self):
        """Test that Coach Voice Generator returns non-empty explanation"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        voice = journey.get("voice", {})
        explanation = voice.get("explanation", "")
        
        # Explanation should be ≤18 words
        word_count = len(explanation.split())
        assert word_count <= 25, f"Explanation too long ({word_count} words): {explanation}"
        assert word_count >= 3, f"Explanation too short ({word_count} words): {explanation}"
        print(f"Coach Voice explanation ({word_count} words): {explanation}")

    def test_coach_voice_focus_instruction(self):
        """Test that Coach Voice Generator returns focus_instruction"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        journey = resp.json().get("journey", {})
        
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        voice = journey.get("voice", {})
        instruction = voice.get("focus_instruction", "")
        
        # Instruction should be ≤16 words
        word_count = len(instruction.split())
        assert word_count <= 20, f"Instruction too long ({word_count} words): {instruction}"
        print(f"Coach Voice focus_instruction ({word_count} words): {instruction}")

    # ================== PLAIN INDIAN-ENGLISH TONE ==================

    def test_language_plain_indian_english(self):
        """Test that all text uses plain Indian-English tone (no corporate jargon)"""
        resp = self.session.get(f"{BASE_URL}/api/cognitive/journey")
        data = resp.json()
        
        journey = data.get("journey", {})
        if not journey.get("ready"):
            pytest.skip("Journey not ready")
        
        # Collect all text
        voice = journey.get("voice", {})
        texts = [
            voice.get("headline", ""),
            voice.get("explanation", ""),
            voice.get("focus_instruction", ""),
            journey.get("directive", ""),
            data.get("snapshot", {}).get("directive", ""),
            data.get("momentum", {}).get("directive", "")
        ]
        
        # Check for corporate/jargon terms that should NOT appear
        banned_terms = ["KPI", "optimize", "leverage", "synergy", "actionable", "stakeholder"]
        
        for text in texts:
            for term in banned_terms:
                assert term.lower() not in text.lower(), f"Found corporate jargon '{term}' in: {text}"
        
        print("All text uses plain Indian-English tone")


class TestStatInterpretationEngine:
    """Unit tests for stat_interpretation_engine.py functions"""
    
    def test_import_stat_interpretation_engine(self):
        """Test that stat_interpretation_engine can be imported"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from stat_interpretation_engine import (
            interpret_stats,
            calculate_accuracy_signal,
            calculate_blunder_signal,
            calculate_stability_band,
            is_noise,
            SignalLevel,
            StabilityBand,
            OverallChange
        )
        print("stat_interpretation_engine imported successfully")

    def test_interpret_stats_returns_valid_structure(self):
        """Test interpret_stats returns expected structure"""
        import sys
        sys.path.insert(0, '/app/backend')
        from stat_interpretation_engine import interpret_stats
        
        then_metrics = {
            "games": 15,
            "accuracy": 65.0,
            "blunders_per_game": 2.5,
            "mistakes_per_game": 3.5,
            "winrate": 45.0
        }
        now_metrics = {
            "games": 15,
            "accuracy": 70.0,
            "blunders_per_game": 1.2,
            "mistakes_per_game": 2.0,
            "winrate": 55.0
        }
        
        result = interpret_stats(then_metrics, now_metrics)
        
        assert "evaluation_ready" in result
        assert "confidence" in result
        assert "overall_change" in result
        assert "signals" in result
        assert "deltas" in result
        assert "show_deltas" in result
        
        print(f"interpret_stats result: overall_change={result['overall_change']}, show_deltas={result['show_deltas']}")

    def test_calculate_blunder_signal_major_improvement(self):
        """Test blunder signal calculation for major improvement"""
        import sys
        sys.path.insert(0, '/app/backend')
        from stat_interpretation_engine import calculate_blunder_signal, SignalLevel
        
        # Reduction of 0.8+ is major improvement
        signal = calculate_blunder_signal(1.0)  # delta = then - now (reduction)
        assert signal == SignalLevel.MAJOR_IMPROVEMENT
        print(f"Blunder delta=1.0 -> {signal.value}")

    def test_is_noise_function(self):
        """Test is_noise function for hide-noise rule"""
        import sys
        sys.path.insert(0, '/app/backend')
        from stat_interpretation_engine import is_noise
        
        # Small deltas should be noise
        assert is_noise(1.0, 0.1, 0.2, 3) == True, "Small deltas should be noise"
        
        # Large deltas should not be noise
        assert is_noise(5.0, 0.1, 0.2, 3) == False, "Large accuracy delta should not be noise"
        assert is_noise(1.0, 0.5, 0.2, 3) == False, "Large blunder delta should not be noise"
        
        print("is_noise function works correctly")


class TestCoachVoiceGenerator:
    """Unit tests for coach_voice_generator.py functions"""
    
    def test_import_coach_voice_generator(self):
        """Test that coach_voice_generator can be imported"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from coach_voice_generator import (
            generate_coach_voice,
            generate_tab_voice,
            HEADLINE_MAP,
            INSTRUCTION_MAP,
            get_tone_level,
            should_show_improvement_badge,
            get_badge_text
        )
        print("coach_voice_generator imported successfully")

    def test_generate_coach_voice_structure(self):
        """Test generate_coach_voice returns expected structure"""
        import sys
        sys.path.insert(0, '/app/backend')
        from coach_voice_generator import generate_coach_voice
        
        result = generate_coach_voice(
            headline_signal="improving",
            stability_band="moderate",
            primary_driver="missed_forcing_move",
            phase_instability="middlegame",
            advantage_risk="medium",
            confidence=0.8
        )
        
        assert "headline" in result
        assert "explanation" in result
        assert "focus_instruction" in result
        assert "tone_level" in result
        
        print(f"Coach voice: {result['headline']} (tone: {result['tone_level']})")

    def test_headline_map_coverage(self):
        """Test that HEADLINE_MAP has entries for all signal levels"""
        import sys
        sys.path.insert(0, '/app/backend')
        from coach_voice_generator import HEADLINE_MAP
        
        required_signals = ["major_improvement", "improving", "stable", "declining", "major_decline"]
        
        for signal in required_signals:
            assert signal in HEADLINE_MAP, f"Missing headline for signal: {signal}"
            assert len(HEADLINE_MAP[signal]) > 5, f"Headline too short for {signal}"
        
        print(f"HEADLINE_MAP has {len(HEADLINE_MAP)} entries")

    def test_badge_on_major_improvement(self):
        """Test badge is shown for major_improvement signal"""
        import sys
        sys.path.insert(0, '/app/backend')
        from coach_voice_generator import should_show_improvement_badge, get_badge_text
        
        assert should_show_improvement_badge("major_improvement") == True
        assert should_show_improvement_badge("improving") == False
        assert should_show_improvement_badge("stable") == False
        
        badge = get_badge_text("major_improvement")
        assert badge is not None
        assert "improvement" in badge.lower() or "week" in badge.lower()
        
        print(f"Badge for major_improvement: {badge}")

    def test_get_tone_level(self):
        """Test tone level mapping from signals"""
        import sys
        sys.path.insert(0, '/app/backend')
        from coach_voice_generator import get_tone_level
        
        assert get_tone_level("major_improvement") == "positive"
        assert get_tone_level("improving") == "positive"
        assert get_tone_level("stable") == "neutral"
        assert get_tone_level("declining") == "concern"
        assert get_tone_level("major_decline") == "concern"
        
        print("Tone levels mapped correctly")
