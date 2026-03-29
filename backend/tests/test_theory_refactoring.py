"""
Test Theory Refactoring - Chess Theory Knowledge Base
=====================================================

Tests the refactored theory knowledge base that was split from a single 
chess_theory.json into 4 files in /data/theory/:
- opening_mistakes.json (28 patterns)
- endgame_principles.json (17 patterns)
- tactical_patterns.json (17 patterns)
- positional_rules.json (20 rules)

Tests:
1. Theory stats endpoint - should return 82 total patterns
2. Opening patterns endpoint - should return 28 patterns
3. Endgame patterns endpoint - should return 17 patterns
4. Tactical patterns endpoint - should return 17 patterns
5. Positional rules endpoint (NEW) - should return 20 rules
6. Theory reload endpoint - should reload and return updated stats
7. Explain-mistake endpoint - Italian d5 theory match
8. Explain-mistake endpoint - French attack chain theory match
9. Explain-mistake endpoint - non-theory position fallback
10. Ask-move endpoint - illegal move error handling
11. Ask-move endpoint - legal move Stockfish analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestTheoryStatsEndpoint:
    """Test GET /api/coach/theory/stats - should return 82 total patterns across 4 categories"""
    
    def test_theory_stats_returns_correct_counts(self):
        """Verify theory stats returns expected pattern counts"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "stats" in data, "Response should contain 'stats' key"
        assert "status" in data, "Response should contain 'status' key"
        assert data["status"] == "ok", f"Status should be 'ok', got {data['status']}"
        
        stats = data["stats"]
        assert "opening_patterns" in stats, "Stats should contain 'opening_patterns'"
        assert "endgame_patterns" in stats, "Stats should contain 'endgame_patterns'"
        assert "tactical_patterns" in stats, "Stats should contain 'tactical_patterns'"
        assert "positional_rules" in stats, "Stats should contain 'positional_rules'"
        assert "total" in stats, "Stats should contain 'total'"
        
        # Verify expected counts
        assert stats["opening_patterns"] == 28, f"Expected 28 opening patterns, got {stats['opening_patterns']}"
        assert stats["endgame_patterns"] == 17, f"Expected 17 endgame patterns, got {stats['endgame_patterns']}"
        assert stats["tactical_patterns"] == 17, f"Expected 17 tactical patterns, got {stats['tactical_patterns']}"
        assert stats["positional_rules"] == 20, f"Expected 20 positional rules, got {stats['positional_rules']}"
        assert stats["total"] == 82, f"Expected 82 total patterns, got {stats['total']}"


class TestOpeningPatternsEndpoint:
    """Test GET /api/coach/theory/openings - should return 28 opening patterns"""
    
    def test_opening_patterns_returns_28_patterns(self):
        """Verify opening patterns endpoint returns 28 patterns"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/openings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "patterns" in data, "Response should contain 'patterns' key"
        assert "count" in data, "Response should contain 'count' key"
        
        assert data["count"] == 28, f"Expected 28 opening patterns, got {data['count']}"
        assert len(data["patterns"]) == 28, f"Expected 28 patterns in list, got {len(data['patterns'])}"
        
        # Verify pattern structure
        if data["patterns"]:
            pattern = data["patterns"][0]
            assert "id" in pattern, "Pattern should have 'id' field"
    
    def test_opening_patterns_contains_italian_d5(self):
        """Verify Italian d5 pattern exists in opening patterns"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/openings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Find the Italian d5 pattern
        italian_d5 = None
        for pattern in data["patterns"]:
            if pattern.get("id") == "italian_two_knights_d5":
                italian_d5 = pattern
                break
        
        assert italian_d5 is not None, "Italian Two Knights d5 pattern should exist"
        assert italian_d5.get("bad_move") == "d5", "Bad move should be d5"
        assert italian_d5.get("good_move") == "d6", "Good move should be d6"


class TestEndgamePatternsEndpoint:
    """Test GET /api/coach/theory/endgames - should return 17 endgame patterns"""
    
    def test_endgame_patterns_returns_17_patterns(self):
        """Verify endgame patterns endpoint returns 17 patterns"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/endgames")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "patterns" in data, "Response should contain 'patterns' key"
        assert "count" in data, "Response should contain 'count' key"
        
        assert data["count"] == 17, f"Expected 17 endgame patterns, got {data['count']}"
        assert len(data["patterns"]) == 17, f"Expected 17 patterns in list, got {len(data['patterns'])}"
    
    def test_endgame_patterns_contains_lucena(self):
        """Verify Lucena position pattern exists"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/endgames")
        
        assert response.status_code == 200
        data = response.json()
        
        lucena = None
        for pattern in data["patterns"]:
            if pattern.get("id") == "lucena_position":
                lucena = pattern
                break
        
        assert lucena is not None, "Lucena position pattern should exist"
        assert "key_rule" in lucena, "Lucena should have key_rule"


class TestTacticalPatternsEndpoint:
    """Test GET /api/coach/theory/tactical - should return 17 tactical patterns"""
    
    def test_tactical_patterns_returns_17_patterns(self):
        """Verify tactical patterns endpoint returns 17 patterns"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/tactical")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "patterns" in data, "Response should contain 'patterns' key"
        assert "count" in data, "Response should contain 'count' key"
        
        assert data["count"] == 17, f"Expected 17 tactical patterns, got {data['count']}"
        assert len(data["patterns"]) == 17, f"Expected 17 patterns in list, got {len(data['patterns'])}"
    
    def test_tactical_patterns_contains_knight_fork(self):
        """Verify knight fork pattern exists"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/tactical")
        
        assert response.status_code == 200
        data = response.json()
        
        knight_fork = None
        for pattern in data["patterns"]:
            if pattern.get("id") == "knight_fork":
                knight_fork = pattern
                break
        
        assert knight_fork is not None, "Knight fork pattern should exist"
        assert knight_fork.get("pattern_type") == "fork", "Pattern type should be 'fork'"


class TestPositionalRulesEndpoint:
    """Test GET /api/coach/theory/rules - NEW endpoint, should return 20 positional rules"""
    
    def test_positional_rules_returns_20_rules(self):
        """Verify positional rules endpoint returns 20 rules"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/rules")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "rules" in data, "Response should contain 'rules' key"
        assert "count" in data, "Response should contain 'count' key"
        
        assert data["count"] == 20, f"Expected 20 positional rules, got {data['count']}"
        assert len(data["rules"]) == 20, f"Expected 20 rules in list, got {len(data['rules'])}"
    
    def test_positional_rules_structure(self):
        """Verify positional rules have correct structure"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/rules")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that rules have expected fields
        if data["rules"]:
            rule = data["rules"][0]
            assert "id" in rule, "Rule should have 'id' field"
            assert "rule" in rule, "Rule should have 'rule' field"
            assert "short" in rule, "Rule should have 'short' field"
            assert "severity" in rule, "Rule should have 'severity' field"
    
    def test_positional_rules_contains_loses_pawn(self):
        """Verify loses_pawn rule exists"""
        response = requests.get(f"{BASE_URL}/api/coach/theory/rules")
        
        assert response.status_code == 200
        data = response.json()
        
        loses_pawn = None
        for rule in data["rules"]:
            if rule.get("id") == "loses_pawn":
                loses_pawn = rule
                break
        
        assert loses_pawn is not None, "loses_pawn rule should exist"
        assert loses_pawn.get("severity") == "minor", "loses_pawn severity should be 'minor'"


class TestTheoryReloadEndpoint:
    """Test POST /api/coach/theory/reload - should reload and return updated stats"""
    
    def test_theory_reload_returns_stats(self):
        """Verify theory reload endpoint works and returns stats"""
        response = requests.post(f"{BASE_URL}/api/coach/theory/reload")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Response should contain 'status' key"
        assert "stats" in data, "Response should contain 'stats' key"
        
        assert data["status"] == "reloaded", f"Status should be 'reloaded', got {data['status']}"
        
        stats = data["stats"]
        assert stats["total"] == 82, f"Expected 82 total patterns after reload, got {stats['total']}"


class TestExplainMistakeTheoryMatch:
    """Test POST /api/coach/explain-mistake - theory matching functionality"""
    
    def test_italian_d5_theory_match(self):
        """
        Test Italian d5 theory pattern matching
        FEN: r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq
        bad_move: d5, good_move: d6
        Should return theory_match: true
        """
        payload = {
            "fen_before": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4",
            "played_move": "d5",
            "played_move_uci": "d7d5",
            "best_move": "d6",
            "best_move_uci": "d7d6",
            "eval_before": 0,
            "eval_after": -100,
            "move_number": 4,
            "pv_after_played": ["exd5", "Nxd5"],
            "pv_after_best": ["O-O"],
            "user_color": "black"
        }
        
        response = requests.post(f"{BASE_URL}/api/coach/explain-mistake", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "theory_match" in data, "Response should contain 'theory_match' key"
        assert data["theory_match"] == True, f"Expected theory_match=True for Italian d5, got {data.get('theory_match')}"
        assert "headline" in data, "Response should contain 'headline'"
        assert "explanation" in data, "Response should contain 'explanation'"
        assert "rule" in data, "Response should contain 'rule'"
        assert data.get("category") == "opening", f"Category should be 'opening', got {data.get('category')}"
    
    def test_french_attack_chain_theory_match(self):
        """
        Test French attack chain pattern matching
        FEN: rnbqkbnr/ppp2ppp/4p3/3pP3/3P4/8/PPP2PPP/RNBQKBNR b KQkq
        bad_move: f6, good_move: c5
        Should return theory_match: true
        """
        payload = {
            "fen_before": "rnbqkbnr/ppp2ppp/4p3/3pP3/3P4/8/PPP2PPP/RNBQKBNR b KQkq - 0 3",
            "played_move": "f6",
            "played_move_uci": "f7f6",
            "best_move": "c5",
            "best_move_uci": "c7c5",
            "eval_before": 0,
            "eval_after": -150,
            "move_number": 3,
            "pv_after_played": ["exf6", "Nxf6"],
            "pv_after_best": ["c3", "Nc6"],
            "user_color": "black"
        }
        
        response = requests.post(f"{BASE_URL}/api/coach/explain-mistake", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "theory_match" in data, "Response should contain 'theory_match' key"
        assert data["theory_match"] == True, f"Expected theory_match=True for French attack chain, got {data.get('theory_match')}"
        assert data.get("category") == "opening", f"Category should be 'opening', got {data.get('category')}"
    
    def test_non_theory_position_fallback(self):
        """
        Test non-theory position falls back to PV parsing with golden rules
        Use a random middlegame position that won't match any theory pattern
        """
        payload = {
            "fen_before": "r1bq1rk1/ppp2ppp/2n2n2/3pp3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w - - 0 7",
            "played_move": "Bg5",
            "played_move_uci": "c4g5",
            "best_move": "exd5",
            "best_move_uci": "e4d5",
            "eval_before": 50,
            "eval_after": -100,
            "move_number": 7,
            "pv_after_played": ["h6", "Bh4", "g5"],
            "pv_after_best": ["Nxd5", "Nxd5"],
            "user_color": "white"
        }
        
        response = requests.post(f"{BASE_URL}/api/coach/explain-mistake", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Non-theory positions should NOT have theory_match=True
        # They should fall back to PV parsing
        assert "headline" in data, "Response should contain 'headline'"
        assert "explanation" in data, "Response should contain 'explanation'"
        assert "rule" in data, "Response should contain 'rule'"
        # theory_match should be False or not present for non-theory positions
        if "theory_match" in data:
            assert data["theory_match"] == False, "Non-theory position should have theory_match=False"


class TestAskMoveEndpoint:
    """Test POST /api/coach/ask-move - move Q&A functionality"""
    
    def test_illegal_move_shows_helpful_error(self):
        """Test that illegal move returns helpful error with legal alternatives"""
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "question": "why Ke3?",  # Illegal move - king can't move to e3 from starting position
            "played_move": "Ke3",
            "depth": 18
        }
        
        response = requests.post(f"{BASE_URL}/api/coach/ask-move", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return an error or indication that the move is illegal
        # The response should be helpful, not just crash
        assert "error" in data or "illegal" in str(data).lower() or "legal" in str(data).lower(), \
            f"Response should indicate illegal move or provide legal alternatives: {data}"
    
    def test_legal_move_returns_stockfish_analysis(self):
        """Test that legal move returns Stockfish analysis"""
        # The ask-move endpoint expects a comparison question format like "Why X and not Y?"
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "question": "Why e4 and not d4?",  # Correct format for comparison
            "played_move": None,
            "depth": 18
        }
        
        response = requests.post(f"{BASE_URL}/api/coach/ask-move", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return analysis with comparison data
        # The endpoint parses the question to extract moves for comparison
        assert "error" not in data or "Could not understand" not in str(data.get("error", "")), \
            f"Legal move comparison should not return parse error: {data}"


class TestTheoryServiceIntegration:
    """Integration tests for the theory service loading from /data/theory/"""
    
    def test_all_endpoints_return_consistent_counts(self):
        """Verify all endpoints return consistent counts that sum to total"""
        # Get stats
        stats_response = requests.get(f"{BASE_URL}/api/coach/theory/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()["stats"]
        
        # Get individual counts
        openings_response = requests.get(f"{BASE_URL}/api/coach/theory/openings")
        endgames_response = requests.get(f"{BASE_URL}/api/coach/theory/endgames")
        tactical_response = requests.get(f"{BASE_URL}/api/coach/theory/tactical")
        rules_response = requests.get(f"{BASE_URL}/api/coach/theory/rules")
        
        assert openings_response.status_code == 200
        assert endgames_response.status_code == 200
        assert tactical_response.status_code == 200
        assert rules_response.status_code == 200
        
        openings_count = openings_response.json()["count"]
        endgames_count = endgames_response.json()["count"]
        tactical_count = tactical_response.json()["count"]
        rules_count = rules_response.json()["count"]
        
        # Verify consistency
        assert stats["opening_patterns"] == openings_count, "Opening patterns count mismatch"
        assert stats["endgame_patterns"] == endgames_count, "Endgame patterns count mismatch"
        assert stats["tactical_patterns"] == tactical_count, "Tactical patterns count mismatch"
        assert stats["positional_rules"] == rules_count, "Positional rules count mismatch"
        
        # Verify total
        calculated_total = openings_count + endgames_count + tactical_count + rules_count
        assert stats["total"] == calculated_total, f"Total mismatch: {stats['total']} != {calculated_total}"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
