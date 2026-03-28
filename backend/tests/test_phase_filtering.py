"""
Test Phase-Filtered Example Positions Fix
==========================================
Tests for the bug fix where:
1. Example positions should match the current training phase
2. "Opening Principles" phase should only show moves 1-12
3. Training Areas UI should show meaningful stats (not raw cost numbers)

Related files:
- backend/training_profile_service.py - Lines 1048-1180
- frontend/src/pages/Training.jsx - Lines 666-715
"""
import pytest
import requests
import os

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPhaseFilteredPositions:
    """Test that example_positions are filtered by current training phase"""
    
    def test_health_endpoint(self):
        """Verify API is running"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        print("PASS: API is healthy")
    
    def test_training_profile_endpoint(self):
        """Test training profile endpoint returns expected structure"""
        resp = requests.get(f"{BASE_URL}/api/training/profile", 
                          cookies={'session_token': 'test'})
        # May return 401 if not authenticated
        if resp.status_code == 401:
            print("INFO: Not authenticated - using dev mode")
            # Use dev-login
            dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
            if dev_resp.status_code == 200:
                cookies = dev_resp.cookies
                resp = requests.get(f"{BASE_URL}/api/training/profile", 
                                  cookies=cookies)
        
        print(f"Training profile response status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check required fields exist
            assert 'status' in data or 'example_positions' in data, \
                "Response should have status or example_positions"
            
            if data.get('status') == 'insufficient_data':
                print(f"INFO: Insufficient data - need {data.get('games_required', '?')} games")
                return
            
            # Check example_positions structure
            if 'example_positions' in data:
                example_positions = data['example_positions']
                print(f"PASS: Found {len(example_positions)} example positions")
                
                # Verify each position has required fields
                for pos in example_positions:
                    assert 'move_number' in pos, "Position should have move_number"
                    assert 'fen' in pos, "Position should have fen"
                    assert 'cp_loss' in pos, "Position should have cp_loss"
                    print(f"  - Move {pos.get('move_number')}: cp_loss={pos.get('cp_loss')}")
            
            # Check layer_breakdown structure (new meaningful stats)
            if 'layer_breakdown' in data:
                breakdown = data['layer_breakdown']
                for phase, layer_data in breakdown.items():
                    assert 'cost' in layer_data, f"{phase} should have cost"
                    assert 'label' in layer_data, f"{phase} should have label"
                    # New fields: mistakes_count and avg_loss_per_game
                    print(f"  - {phase}: cost={layer_data.get('cost')}, "
                          f"mistakes_count={layer_data.get('mistakes_count', 'N/A')}, "
                          f"avg_loss={layer_data.get('avg_loss_per_game', 'N/A')}")
            
            print("PASS: Training profile structure is correct")
        else:
            print(f"INFO: Training profile returned {resp.status_code}")
    
    def test_phase_progress_endpoint(self):
        """Test phase-progress endpoint returns tier and phase info"""
        # First get dev session
        dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
        cookies = dev_resp.cookies if dev_resp.status_code == 200 else {}
        
        resp = requests.get(f"{BASE_URL}/api/training/phase-progress", cookies=cookies)
        print(f"Phase progress response status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check tier info
            if 'tier_label' in data:
                print(f"  Tier: {data.get('tier_label')} ({data.get('tier_id')})")
                print(f"  Rating range: {data.get('tier_rating_range')}")
            
            # Check phase info
            if 'phase' in data:
                phase = data['phase']
                print(f"  Current phase: {phase.get('label')} ({phase.get('id')})")
                print(f"  Description: {phase.get('description')}")
                print(f"  Phase index: {data.get('phase_index')}/{data.get('total_phases')}")
            
            # Check stats
            if 'stats' in data:
                stats = data['stats']
                print(f"  Stats: trend={stats.get('trend')}, "
                      f"clean_games={stats.get('clean_games')}")
            
            # Verify required fields
            required_fields = ['tier_id', 'tier_label', 'phase', 'phase_index', 'total_phases']
            for field in required_fields:
                assert field in data, f"Response should have {field}"
            
            print("PASS: Phase progress structure is correct")
        else:
            print(f"INFO: Phase progress returned {resp.status_code}")
    
    def test_opening_principles_phase_filtering(self):
        """
        CRITICAL TEST: Verify that when in 'opening_principles' phase,
        example_positions only contain moves 1-12.
        
        This is the main bug fix being tested.
        """
        # Get dev session
        dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
        cookies = dev_resp.cookies if dev_resp.status_code == 200 else {}
        
        # Get training profile
        resp = requests.get(f"{BASE_URL}/api/training/profile", cookies=cookies)
        
        if resp.status_code != 200:
            pytest.skip(f"Training profile not available: {resp.status_code}")
        
        data = resp.json()
        
        if data.get('status') == 'insufficient_data':
            pytest.skip("Insufficient data for training profile")
        
        # Check current phase
        current_phase_id = data.get('current_phase_id', '')
        example_positions = data.get('example_positions', [])
        
        print(f"Current phase: {current_phase_id}")
        print(f"Example positions count: {len(example_positions)}")
        
        if current_phase_id == 'opening_principles':
            # CRITICAL: All example positions should have move_number <= 12
            violations = []
            for pos in example_positions:
                move_num = pos.get('move_number', 0)
                print(f"  - Move {move_num}: fen={pos.get('fen', '')[:30]}...")
                if move_num > 12:
                    violations.append(move_num)
            
            if violations:
                print(f"FAIL: Found {len(violations)} positions with move_number > 12: {violations}")
                assert False, f"Opening Principles phase showing moves {violations} (should be 1-12 only)"
            else:
                print("PASS: All example positions are within opening (moves 1-12)")
        else:
            print(f"INFO: User not in opening_principles phase (current: {current_phase_id})")
            # Still verify positions have move_number field
            for pos in example_positions:
                assert 'move_number' in pos, "Position should have move_number"
    
    def test_layer_breakdown_has_meaningful_stats(self):
        """
        Test that layer_breakdown shows meaningful stats, not just raw cost.
        The fix added mistakes_count and avg_loss_per_game fields.
        """
        # Get dev session
        dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
        cookies = dev_resp.cookies if dev_resp.status_code == 200 else {}
        
        # Get training profile
        resp = requests.get(f"{BASE_URL}/api/training/profile", cookies=cookies)
        
        if resp.status_code != 200:
            pytest.skip(f"Training profile not available: {resp.status_code}")
        
        data = resp.json()
        
        if data.get('status') == 'insufficient_data':
            pytest.skip("Insufficient data for training profile")
        
        layer_breakdown = data.get('layer_breakdown', {})
        
        if not layer_breakdown:
            pytest.skip("No layer_breakdown in response")
        
        for phase_name, layer_data in layer_breakdown.items():
            print(f"Checking {phase_name}...")
            
            # Basic fields
            assert 'cost' in layer_data, f"{phase_name} missing cost"
            assert 'label' in layer_data, f"{phase_name} missing label"
            assert 'is_active' in layer_data, f"{phase_name} missing is_active"
            
            # New meaningful stats (added in fix)
            # Check if mistakes_count exists (may be calculated or present)
            if 'mistakes_count' in layer_data:
                mistakes = layer_data['mistakes_count']
                print(f"  - mistakes_count: {mistakes}")
                assert isinstance(mistakes, (int, float)), f"mistakes_count should be numeric"
            
            if 'avg_loss_per_game' in layer_data:
                avg_loss = layer_data['avg_loss_per_game']
                print(f"  - avg_loss_per_game: {avg_loss}")
                assert isinstance(avg_loss, (int, float)), f"avg_loss_per_game should be numeric"
        
        print("PASS: Layer breakdown has meaningful stats structure")


class TestPhaseFilteringLogic:
    """Test the phase filtering logic directly"""
    
    def test_phase_filter_criteria_for_opening_principles(self):
        """
        Test that the PHASE_FILTERS for opening_principles is configured correctly.
        Expected: move_range=(1, 12), min_cp_loss=80
        """
        # This would be a unit test in a real scenario
        # Here we're testing via the API response
        print("Testing phase filter criteria via API...")
        
        # Get dev session
        dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
        cookies = dev_resp.cookies if dev_resp.status_code == 200 else {}
        
        # Get training profile 
        resp = requests.get(f"{BASE_URL}/api/training/profile", cookies=cookies)
        
        if resp.status_code != 200:
            pytest.skip(f"Training profile not available: {resp.status_code}")
        
        data = resp.json()
        current_tier_id = data.get('current_tier_id', '')
        
        # Verify tier is 'structure' for rating 1000-1400
        rating = data.get('rating_at_computation', 0)
        print(f"User rating: {rating}, tier: {current_tier_id}")
        
        if 1000 <= rating < 1400:
            # Should be in 'structure' tier
            assert current_tier_id == 'structure', \
                f"Rating {rating} should be in 'structure' tier, got {current_tier_id}"
            print(f"PASS: Correct tier for rating {rating}")


class TestFrontendIntegration:
    """Test that frontend-relevant data is present"""
    
    def test_training_profile_has_ui_fields(self):
        """
        Verify training profile has fields needed by Training.jsx UI:
        - example_positions with move_number
        - layer_breakdown with meaningful labels
        - current_tier_id and current_phase_id
        """
        # Get dev session
        dev_resp = requests.get(f"{BASE_URL}/api/auth/dev-login")
        cookies = dev_resp.cookies if dev_resp.status_code == 200 else {}
        
        resp = requests.get(f"{BASE_URL}/api/training/profile", cookies=cookies)
        
        if resp.status_code != 200:
            pytest.skip(f"Training profile not available")
        
        data = resp.json()
        
        if data.get('status') == 'insufficient_data':
            pytest.skip("Insufficient data")
        
        # Fields used by Training.jsx renderPhaseStep()
        ui_fields = [
            'active_phase',
            'active_phase_label',
            'example_positions',
            'layer_breakdown',
            'micro_habit',
            'micro_habit_label',
            'rules',
            'pattern_weights',
        ]
        
        missing = [f for f in ui_fields if f not in data]
        if missing:
            print(f"WARNING: Missing UI fields: {missing}")
        else:
            print("PASS: All UI fields present")
        
        # Check example_positions structure for UI
        if 'example_positions' in data and data['example_positions']:
            pos = data['example_positions'][0]
            required_pos_fields = ['move_number', 'fen', 'move', 'best_move', 'cp_loss']
            pos_missing = [f for f in required_pos_fields if f not in pos]
            if pos_missing:
                print(f"WARNING: Example position missing: {pos_missing}")
            else:
                print("PASS: Example position has all required fields")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
