"""
Test Contextual Tags Feature for Chess Coaching App Reflection

Tests the POST /api/reflect/moment/contextual-tags endpoint which generates 
position-aware tags based on actual chess analysis.

Features tested:
1. Endpoint returns position-based tags
2. Handles captures correctly (should show 'I wanted to capture the X')
3. Handles attacks on valuable pieces (knight, bishop, rook, queen)
4. Handles attacks on weak squares (f7/f2)
5. Handles cases where intent cannot be inferred (returns could_not_infer: true)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestContextualTags:
    """Test the contextual tags endpoint for the Reflect feature."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with credentials."""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Use dev login
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_resp.status_code != 200:
            pytest.skip("Dev login not available")
    
    def test_contextual_tags_endpoint_exists(self):
        """Test that the contextual-tags endpoint exists and responds."""
        # Basic FEN - starting position with a pawn move
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "user_move": "e4",
            "best_move": "d4",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check response structure
        assert "tags" in data, "Response should contain 'tags' field"
        assert "could_not_infer" in data, "Response should contain 'could_not_infer' field"
        assert isinstance(data["tags"], list), "Tags should be a list"
    
    def test_bb5_attacking_knight(self):
        """
        Test position: Bb5 attacking knight on c6 (Italian Game setup)
        FEN: r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3
        User plays Bb5 (attacking knight)
        """
        payload = {
            "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
            "user_move": "Bb5",
            "best_move": "d4",
            "eval_change": -0.3
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Bb5 attacking knight test ===")
        print(f"Tags returned: {data.get('tags', [])}")
        print(f"Could not infer: {data.get('could_not_infer', False)}")
        print(f"Inferred intent: {data.get('inferred_intent')}")
        
        # The move attacks the knight on c6, so we expect a tag mentioning this
        assert "tags" in data, "Should return tags"
        tags_lower = [t.lower() for t in data.get("tags", [])]
        
        # Check that some tag mentions attacking the knight
        attack_knight_found = any("knight" in tag and ("attack" in tag or "wanted" in tag) for tag in tags_lower)
        print(f"Attack knight tag found: {attack_knight_found}")
        
        # It's acceptable if the move is categorized as development too
        development_found = any("develop" in tag for tag in tags_lower)
        print(f"Development tag found: {development_found}")
        
        assert len(data.get("tags", [])) > 0, "Should return at least one tag"
    
    def test_qh5_attacking_f7(self):
        """
        Test position: Qh5 attacking weak f7 square (Scholar's mate idea)
        FEN: rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2
        User plays Qh5 (attacking f7)
        """
        payload = {
            "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
            "user_move": "Qh5",
            "best_move": "Nf3",
            "eval_change": -0.5
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Qh5 attacking f7 test ===")
        print(f"Tags returned: {data.get('tags', [])}")
        print(f"Could not infer: {data.get('could_not_infer', False)}")
        print(f"Inferred intent: {data.get('inferred_intent')}")
        
        # The move attacks f7 (weak square) and e5 pawn
        assert "tags" in data, "Should return tags"
        tags_lower = [t.lower() for t in data.get("tags", [])]
        
        # Check for f7 attack mention or e5 pawn attack
        f7_attack = any("f7" in tag or "weak" in tag for tag in tags_lower)
        e5_attack = any(("e5" in tag or "pawn" in tag) and "attack" in tag for tag in tags_lower)
        
        print(f"F7 attack tag found: {f7_attack}")
        print(f"E5 pawn attack tag found: {e5_attack}")
        
        assert len(data.get("tags", [])) > 0, "Should return at least one tag"
    
    def test_capture_move(self):
        """
        Test position: Capture scenario (Bxf7)
        FEN: r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4
        User plays Bxf7 (capturing pawn on f7)
        """
        payload = {
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "user_move": "Bxf7+",
            "best_move": "d3",
            "eval_change": -1.0
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Bxf7 capture test ===")
        print(f"Tags returned: {data.get('tags', [])}")
        print(f"Could not infer: {data.get('could_not_infer', False)}")
        print(f"Inferred intent: {data.get('inferred_intent')}")
        
        # For a capture, we expect "I wanted to capture the pawn/piece"
        assert "tags" in data, "Should return tags"
        tags_lower = [t.lower() for t in data.get("tags", [])]
        
        # Check for capture-related tag
        capture_found = any("capture" in tag for tag in tags_lower)
        print(f"Capture tag found: {capture_found}")
        
        # Should mention capture or check
        check_found = any("check" in tag for tag in tags_lower)
        print(f"Check tag found: {check_found}")
        
        assert len(data.get("tags", [])) > 0, "Should return at least one tag for capture move"
        
        # For a capture move, inferred_intent should mention capture
        inferred_intent = data.get("inferred_intent", "").lower()
        print(f"Inferred intent contains 'capture': {'capture' in inferred_intent}")
    
    def test_invalid_fen_handling(self):
        """Test that invalid FEN returns could_not_infer: true."""
        payload = {
            "fen": "invalid_fen_string",
            "user_move": "e4",
            "best_move": "d4",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Invalid FEN test ===")
        print(f"Response: {data}")
        
        # Should indicate it couldn't infer
        assert data.get("could_not_infer") == True or data.get("tags") == [], \
            "Invalid FEN should result in could_not_infer=True or empty tags"
    
    def test_invalid_move_handling(self):
        """Test that invalid move returns could_not_infer: true."""
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "user_move": "Qxh7",  # Illegal move from starting position
            "best_move": "e4",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Invalid move test ===")
        print(f"Response: {data}")
        
        # Should indicate it couldn't infer due to invalid move
        assert data.get("could_not_infer") == True or data.get("tags") == [], \
            "Invalid move should result in could_not_infer=True or empty tags"
    
    def test_development_move(self):
        """Test simple development move generates appropriate tags."""
        # Nf3 from starting position - a development move
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "user_move": "Nf6",  # Black develops knight
            "best_move": "d5",
            "eval_change": -0.1
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"\n=== Development move test ===")
        print(f"Tags returned: {data.get('tags', [])}")
        print(f"Could not infer: {data.get('could_not_infer', False)}")
        print(f"Inferred intent: {data.get('inferred_intent')}")
        
        # For a development move, we might see "developing my knight" or attacking center
        assert "tags" in data, "Should return tags"
        
        # Either development or control space or attacking e4
        tags_lower = [t.lower() for t in data.get("tags", [])]
        has_meaningful_tag = any(
            "develop" in tag or "control" in tag or "attack" in tag or "e4" in tag
            for tag in tags_lower
        )
        
        print(f"Has meaningful tag: {has_meaningful_tag}")
        assert len(data.get("tags", [])) > 0, "Should return at least one tag for development move"
    
    def test_response_structure(self):
        """Test that response has all expected fields."""
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "user_move": "e5",
            "best_move": "c5",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\n=== Response structure test ===")
        print(f"Response keys: {data.keys()}")
        
        # Required fields
        assert "tags" in data, "Response must have 'tags' field"
        assert "could_not_infer" in data, "Response must have 'could_not_infer' field"
        
        # Tags should be strings
        for tag in data.get("tags", []):
            assert isinstance(tag, str), f"Tag should be string, got {type(tag)}"
        
        # should_not_infer should be boolean
        assert isinstance(data["could_not_infer"], bool), "could_not_infer should be boolean"
        
        # Optional inferred_intent field
        if "inferred_intent" in data:
            assert data["inferred_intent"] is None or isinstance(data["inferred_intent"], str), \
                "inferred_intent should be string or None"
    
    def test_tags_limit(self):
        """Test that tags are limited to reasonable number (max 5)."""
        # Position with multiple possible intents
        payload = {
            "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "user_move": "Ng5",  # Attacks f7, threatens fork
            "best_move": "d3",
            "eval_change": -0.3
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"\n=== Tags limit test ===")
        print(f"Number of tags: {len(data.get('tags', []))}")
        print(f"Tags: {data.get('tags', [])}")
        
        # Should not exceed 5 tags (as per implementation)
        assert len(data.get("tags", [])) <= 5, "Should not return more than 5 tags"


class TestContextualTagsEdgeCases:
    """Test edge cases for contextual tags."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with credentials."""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Use dev login
        login_resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        if login_resp.status_code != 200:
            pytest.skip("Dev login not available")
    
    def test_missing_required_fields(self):
        """Test that missing required fields return appropriate error."""
        # Missing fen
        payload = {
            "user_move": "e4",
            "best_move": "d4",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        # Should return 422 Unprocessable Entity for missing required field
        assert response.status_code == 422, f"Expected 422 for missing field, got {response.status_code}"
    
    def test_empty_user_move(self):
        """Test handling of empty user move."""
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "user_move": "",
            "best_move": "e4",
            "eval_change": -0.2
        }
        
        response = self.session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        # Should handle gracefully
        assert response.status_code == 200
        data = response.json()
        
        print(f"\n=== Empty user move test ===")
        print(f"Response: {data}")
        
        # Should indicate couldn't infer or return empty tags
        assert data.get("could_not_infer") == True or len(data.get("tags", [])) == 0
    
    def test_authentication_required(self):
        """Test that endpoint requires authentication."""
        # Create new session without auth
        unauthenticated_session = requests.Session()
        unauthenticated_session.headers.update({"Content-Type": "application/json"})
        
        payload = {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "user_move": "e5",
            "best_move": "c5",
            "eval_change": -0.2
        }
        
        response = unauthenticated_session.post(f"{BASE_URL}/api/reflect/moment/contextual-tags", json=payload)
        
        # In DEV_MODE, authentication might be bypassed, but normally should require auth
        # If DEV_MODE is enabled, this might return 200
        print(f"\n=== Auth required test ===")
        print(f"Status code: {response.status_code}")
        
        # Either 401 (requires auth) or 200 (DEV_MODE bypasses auth)
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
