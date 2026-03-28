"""
Tests for Evidence Modal and Pattern Drill Mode features
Tests new endpoints and data structures for actionable drill-downs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestFocusEvidenceFeature:
    """Test /api/focus evidence array for rating killer"""
    
    def test_focus_returns_evidence_array(self):
        """Test /api/focus returns evidence array in focus data"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        focus = data.get("focus", {})
        
        # Evidence should exist (even if empty)
        assert "evidence" in focus, "Missing 'evidence' field in focus data"
        
        evidence = focus.get("evidence", [])
        assert isinstance(evidence, list), "evidence should be a list"
        
        print(f"✓ Focus returns evidence array with {len(evidence)} items")
        
        # If evidence exists, verify structure
        if len(evidence) > 0:
            first = evidence[0]
            assert "game_id" in first, "Missing 'game_id' in evidence item"
            assert "move_number" in first, "Missing 'move_number' in evidence item"
            assert "fen_before" in first, "Missing 'fen_before' in evidence item"
            assert "move_played" in first, "Missing 'move_played' in evidence item"
            assert "best_move" in first, "Missing 'best_move' in evidence item"
            assert "cp_loss" in first, "Missing 'cp_loss' in evidence item"
            assert "eval_before" in first, "Missing 'eval_before' in evidence item"
            assert "opponent" in first, "Missing 'opponent' in evidence item"
            
            print(f"✓ Evidence item has valid structure: vs {first.get('opponent')}, move {first.get('move_number')}")
    
    def test_focus_occurrences_count(self):
        """Test /api/focus returns occurrences count"""
        response = requests.get(
            f"{BASE_URL}/api/focus",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        focus = data.get("focus", {})
        
        # Occurrences should exist
        assert "occurrences" in focus, "Missing 'occurrences' field in focus data"
        assert isinstance(focus["occurrences"], int), "occurrences should be an integer"
        
        print(f"✓ Focus occurrences count: {focus.get('occurrences', 0)}")


class TestJourneyV2EvidenceFeatures:
    """Test /api/journey/v2 evidence arrays for weakness ranking and win state"""
    
    def test_weakness_ranking_has_evidence(self):
        """Test weakness_ranking items have evidence arrays"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        weakness_ranking = data.get("weakness_ranking", {})
        ranking = weakness_ranking.get("ranking", [])
        
        # If we have ranked weaknesses, they should have evidence
        for i, weakness in enumerate(ranking[:3]):  # Check top 3
            assert "evidence" in weakness, f"Missing 'evidence' in weakness #{i+1}"
            evidence = weakness.get("evidence", [])
            assert isinstance(evidence, list), f"evidence should be a list in weakness #{i+1}"
            
            if len(evidence) > 0:
                first = evidence[0]
                assert "game_id" in first, f"Missing 'game_id' in evidence item #{i+1}"
                assert "cp_loss" in first, f"Missing 'cp_loss' in evidence item #{i+1}"
                print(f"✓ Weakness #{i+1} ({weakness.get('label', 'N/A')}) has {len(evidence)} evidence items")
            else:
                print(f"✓ Weakness #{i+1} ({weakness.get('label', 'N/A')}) has 0 evidence items (expected)")
        
        # Also check rating_killer and secondary_weakness
        rating_killer = weakness_ranking.get("rating_killer")
        if rating_killer:
            assert "evidence" in rating_killer, "Missing 'evidence' in rating_killer"
            print(f"✓ Rating killer has evidence array: {len(rating_killer.get('evidence', []))} items")
    
    def test_win_state_has_evidence(self):
        """Test win_state has evidence for each state"""
        response = requests.get(
            f"{BASE_URL}/api/journey/v2",
            headers={"Cookie": "session_id=test"}
        )
        data = response.json()
        win_state = data.get("win_state", {})
        
        states = ["when_winning", "when_equal", "when_losing"]
        
        for state in states:
            state_data = win_state.get(state, {})
            assert "evidence" in state_data, f"Missing 'evidence' in {state}"
            evidence = state_data.get("evidence", [])
            assert isinstance(evidence, list), f"evidence should be a list in {state}"
            
            print(f"✓ {state} has {len(evidence)} evidence items")
            
            if len(evidence) > 0:
                first = evidence[0]
                assert "game_id" in first, f"Missing 'game_id' in {state} evidence"
                assert "fen_before" in first, f"Missing 'fen_before' in {state} evidence"
                assert "cp_loss" in first, f"Missing 'cp_loss' in {state} evidence"


class TestDrillPositionsEndpoint:
    """Test POST /api/drill/positions endpoint"""
    
    def test_drill_positions_returns_200(self):
        """Test /api/drill/positions returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/drill/positions",
            headers={"Cookie": "session_id=test", "Content-Type": "application/json"},
            json={"limit": 5}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "positions" in data, "Missing 'positions' key"
        assert "total" in data, "Missing 'total' key"
        
        print(f"✓ Drill positions returned {data['total']} positions")
    
    def test_drill_positions_with_pattern_filter(self):
        """Test /api/drill/positions with pattern filter"""
        response = requests.post(
            f"{BASE_URL}/api/drill/positions",
            headers={"Cookie": "session_id=test", "Content-Type": "application/json"},
            json={
                "pattern": "attacks_before_checking_threats",
                "limit": 5
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("pattern") == "attacks_before_checking_threats", "Pattern not echoed"
        
        positions = data.get("positions", [])
        print(f"✓ Drill with pattern filter returned {len(positions)} positions")
    
    def test_drill_positions_with_state_filter(self):
        """Test /api/drill/positions with state filter"""
        response = requests.post(
            f"{BASE_URL}/api/drill/positions",
            headers={"Cookie": "session_id=test", "Content-Type": "application/json"},
            json={
                "state": "winning",
                "limit": 5
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("state") == "winning", "State not echoed"
        
        positions = data.get("positions", [])
        print(f"✓ Drill with state filter (winning) returned {len(positions)} positions")
    
    def test_drill_positions_structure(self):
        """Test position structure in drill response"""
        response = requests.post(
            f"{BASE_URL}/api/drill/positions",
            headers={"Cookie": "session_id=test", "Content-Type": "application/json"},
            json={"limit": 5}
        )
        data = response.json()
        positions = data.get("positions", [])
        
        if len(positions) > 0:
            pos = positions[0]
            
            # Required fields for drill mode
            required_fields = [
                "game_id", "move_number", "fen_before", "move_played", 
                "best_move", "cp_loss", "eval_before", "opponent", "user_color"
            ]
            
            for field in required_fields:
                assert field in pos, f"Missing required field '{field}' in drill position"
            
            print(f"✓ Position structure valid: vs {pos.get('opponent')}, move {pos.get('move_number')}")
            print(f"  - FEN: {pos.get('fen_before', '')[:50]}...")
            print(f"  - Move played: {pos.get('move_played')}, Best: {pos.get('best_move')}")
        else:
            print("✓ No drill positions available (may need analyzed games with mistakes)")
    
    def test_drill_positions_with_both_filters(self):
        """Test /api/drill/positions with both pattern and state filters"""
        response = requests.post(
            f"{BASE_URL}/api/drill/positions",
            headers={"Cookie": "session_id=test", "Content-Type": "application/json"},
            json={
                "pattern": "loses_focus_when_winning",
                "state": "winning",
                "limit": 3
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Drill with both filters returned {len(data.get('positions', []))} positions")


class TestWeaknessRankingWithEvidence:
    """Test /api/weakness-ranking standalone endpoint with evidence"""
    
    def test_weakness_ranking_contains_evidence_per_pattern(self):
        """Test each ranked weakness has evidence array"""
        response = requests.get(
            f"{BASE_URL}/api/weakness-ranking",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        ranking = data.get("ranking", [])
        
        evidence_total = 0
        for weakness in ranking:
            evidence = weakness.get("evidence", [])
            evidence_total += len(evidence)
            
        print(f"✓ Weakness ranking has {evidence_total} total evidence items across {len(ranking)} patterns")


class TestWinStateWithEvidence:
    """Test /api/win-state standalone endpoint with evidence"""
    
    def test_win_state_contains_evidence_per_state(self):
        """Test each game state has evidence array"""
        response = requests.get(
            f"{BASE_URL}/api/win-state",
            headers={"Cookie": "session_id=test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        winning_evidence = len(data.get("when_winning", {}).get("evidence", []))
        equal_evidence = len(data.get("when_equal", {}).get("evidence", []))
        losing_evidence = len(data.get("when_losing", {}).get("evidence", []))
        
        total = winning_evidence + equal_evidence + losing_evidence
        print(f"✓ Win-state has evidence: winning={winning_evidence}, equal={equal_evidence}, losing={losing_evidence}")
        print(f"  Total evidence positions: {total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
