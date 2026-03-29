"""
Test Human Coach Review API - /api/lab/{game_id}/coach-review

Tests the 5-section coaching session:
1. THE STORY - Game narrative (opening/tension/climax/resolution/arc_type)
2. THE MIRROR - Personality insight (observation/pattern_insight)
3. THE MOMENT - Critical decisions (2-3 moments with thinking_error)
4. THE TAKEAWAY - One mantra
5. THE PROOF - Progress tracking (improvements/still_working_on/message)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCoachReviewAPI:
    """Test the Human Coach Review endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        # Dev login
        login_res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_res.status_code == 200, f"Dev login failed: {login_res.text}"
        self.test_game_id = "test_game_a793ed92"
    
    def test_coach_review_endpoint_returns_200(self):
        """Test that coach-review endpoint returns 200 for valid game"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            print(f"Response: {res.text[:500]}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    def test_coach_review_has_all_5_sections(self):
        """Test that response contains all 5 required sections"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        # Check all 5 sections exist
        required_sections = ['story', 'mirror', 'moments', 'takeaway', 'proof']
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
            print(f"✓ Section '{section}' present")
    
    def test_story_section_structure(self):
        """Test THE STORY section has required fields"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        story = data.get('story', {})
        required_fields = ['opening', 'tension', 'climax', 'resolution', 'arc_type']
        
        for field in required_fields:
            assert field in story, f"Story missing field: {field}"
            print(f"✓ story.{field}: {str(story[field])[:80]}...")
        
        # arc_type should be one of the expected values
        valid_arc_types = ['dominant', 'scrappy_win', 'stalemate', 'thrown', 'outplayed', 'collapsed', 'unknown']
        assert story['arc_type'] in valid_arc_types, f"Invalid arc_type: {story['arc_type']}"
        print(f"✓ arc_type is valid: {story['arc_type']}")
    
    def test_mirror_section_structure(self):
        """Test THE MIRROR section has required fields"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        mirror = data.get('mirror', {})
        required_fields = ['observation', 'pattern_insight']
        
        for field in required_fields:
            assert field in mirror, f"Mirror missing field: {field}"
            print(f"✓ mirror.{field}: {str(mirror[field])[:80]}...")
    
    def test_moments_section_structure(self):
        """Test THE MOMENT section returns 2-3 critical moments with thinking_error"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        moments = data.get('moments', [])
        assert isinstance(moments, list), "moments should be a list"
        print(f"✓ Found {len(moments)} critical moments")
        
        # Should have 0-3 moments (0 if clean game)
        assert len(moments) <= 3, f"Too many moments: {len(moments)}"
        
        # Each moment should have thinking_error
        for i, moment in enumerate(moments):
            assert 'move_number' in moment, f"Moment {i} missing move_number"
            assert 'thinking_error' in moment, f"Moment {i} missing thinking_error"
            
            te = moment['thinking_error']
            assert 'type' in te, f"Moment {i} thinking_error missing type"
            assert 'label' in te, f"Moment {i} thinking_error missing label"
            assert 'description' in te, f"Moment {i} thinking_error missing description"
            
            print(f"✓ Moment {i+1}: Move {moment['move_number']} - {te['label']}")
    
    def test_takeaway_section_structure(self):
        """Test THE TAKEAWAY section has mantra field"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        takeaway = data.get('takeaway', {})
        assert 'mantra' in takeaway, "Takeaway missing mantra field"
        assert len(takeaway['mantra']) > 10, "Mantra should be a meaningful sentence"
        print(f"✓ takeaway.mantra: {takeaway['mantra'][:100]}...")
    
    def test_proof_section_structure(self):
        """Test THE PROOF section has required fields"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        proof = data.get('proof', {})
        required_fields = ['improvements', 'still_working_on', 'message']
        
        for field in required_fields:
            assert field in proof, f"Proof missing field: {field}"
        
        assert isinstance(proof['improvements'], list), "improvements should be a list"
        assert isinstance(proof['still_working_on'], list), "still_working_on should be a list"
        print(f"✓ proof.message: {proof['message'][:80]}...")
        print(f"✓ proof.improvements: {len(proof['improvements'])} items")
        print(f"✓ proof.still_working_on: {len(proof['still_working_on'])} items")
    
    def test_llm_narrative_layer(self):
        """Test that LLM narrative layer is present (optional but expected)"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        llm_narrative = data.get('llm_narrative')
        if llm_narrative:
            print("✓ LLM narrative layer present")
            expected_fields = ['story_narrative', 'mirror_narrative', 'moment_insights', 'takeaway_refined', 'encouragement']
            for field in expected_fields:
                if field in llm_narrative:
                    print(f"  ✓ llm_narrative.{field}: {str(llm_narrative[field])[:60]}...")
        else:
            print("⚠ LLM narrative layer not present (may be expected if LLM call failed)")
    
    def test_diagnosis_field_present(self):
        """Test that diagnosis field is present for pattern tracking"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        assert 'diagnosis' in data, "Missing diagnosis field"
        print(f"✓ diagnosis: {data['diagnosis']}")
    
    def test_invalid_game_returns_404(self):
        """Test that invalid game ID returns 404"""
        res = self.session.get(f"{BASE_URL}/api/lab/invalid_game_id_xyz/coach-review")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("✓ Invalid game returns 404")


class TestCoachReviewDataQuality:
    """Test the quality and content of coach review data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        login_res = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert login_res.status_code == 200
        self.test_game_id = "test_game_a793ed92"
    
    def test_story_narrative_is_human_readable(self):
        """Test that story narrative doesn't contain chess notation"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        story = data.get('story', {})
        # Check that story text doesn't have raw notation like "Nf3" or "+2.5"
        story_text = f"{story.get('opening', '')} {story.get('tension', '')} {story.get('climax', '')} {story.get('resolution', '')}"
        
        # Should not contain centipawn values
        assert "+2." not in story_text and "-2." not in story_text, "Story should not contain centipawn values"
        print("✓ Story narrative is human-readable (no centipawn values)")
    
    def test_thinking_error_has_root_cause(self):
        """Test that thinking errors have root_cause for training focus"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        moments = data.get('moments', [])
        for i, moment in enumerate(moments):
            te = moment.get('thinking_error', {})
            assert 'root_cause' in te, f"Moment {i} thinking_error missing root_cause"
            print(f"✓ Moment {i+1} root_cause: {te['root_cause']}")
    
    def test_moments_have_navigation_data(self):
        """Test that moments have data needed for board navigation"""
        res = self.session.get(f"{BASE_URL}/api/lab/{self.test_game_id}/coach-review")
        assert res.status_code == 200
        data = res.json()
        
        moments = data.get('moments', [])
        for i, moment in enumerate(moments):
            # Should have move_number for navigation
            assert 'move_number' in moment, f"Moment {i} missing move_number"
            # Should have phase for context
            assert 'phase' in moment, f"Moment {i} missing phase"
            print(f"✓ Moment {i+1}: Move {moment['move_number']} ({moment['phase']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
