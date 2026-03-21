"""
Test EnforcementCheckboxModal (Level 3) and Improvement Proof features

GAP 1: EnforcementCheckboxModal - Level 3 enforcement
- Requires checkbox acknowledgment
- 400ms delay after checkbox before button enables
- Cannot be dismissed without acknowledgment

GAP 2: Improvement proof in post-game
- _enhance_postgame_messaging includes improvement comparison
- improvement object has this_game, last_game, text, verdict fields
"""

import pytest
import os

# Import the streak service functions
import sys
sys.path.insert(0, '/app/backend')

from services.mistake_streak_service import (
    _enhance_postgame_messaging,
    get_postgame_streak_result,
    FOCUS_MISTAKE_TYPES
)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestImprovementProof:
    """Test improvement comparison in post-game messaging (GAP 2)"""
    
    def test_enhance_postgame_messaging_with_improvement(self):
        """Test that _enhance_postgame_messaging adds improvement data"""
        # Setup: postgame result for broken streak
        postgame_result = {
            "result": "broken",
            "headline": "❌ Streak Broken",
            "message": "You repeated your core mistake.",
            "streak": 0,
            "best": 5,
            "previous_streak": 3,
            "tone": "warning"
        }
        
        # Game summary with mistake count
        game_summary = {
            "game_id": "test_game_1",
            "focus_mistake_occurred": True,
            "mistake_count": 4,
            "total_moves": 30,
            "is_valid_for_streak": True
        }
        
        # Last 5 games with previous game having 6 mistakes
        last_5_games = [
            {"game_id": "old_1", "mistake_count": 5, "is_valid": True},
            {"game_id": "old_2", "mistake_count": 6, "is_valid": True},  # Last game
            {"game_id": "current", "mistake_count": 4, "is_valid": True}  # Current game
        ]
        
        # Call the function
        result = _enhance_postgame_messaging(
            postgame_result,
            game_summary,
            "THREAT_VERIFICATION",
            last_5_games=last_5_games
        )
        
        # Verify improvement object exists
        assert "improvement" in result, "improvement object should be in result"
        improvement = result["improvement"]
        
        # Verify improvement fields
        assert "this_game" in improvement, "improvement should have this_game"
        assert "last_game" in improvement, "improvement should have last_game"
        assert "text" in improvement, "improvement should have text"
        assert "verdict" in improvement, "improvement should have verdict"
        
        # Verify values
        assert improvement["this_game"] == 4, f"this_game should be 4, got {improvement['this_game']}"
        assert improvement["last_game"] == 6, f"last_game should be 6, got {improvement['last_game']}"
        assert improvement["verdict"] == "improving", f"verdict should be 'improving' since 4 < 6, got {improvement['verdict']}"
        
        # Verify text format: "You missed X threats (last: Y)"
        assert "4" in improvement["text"], "text should contain this game's count"
        assert "6" in improvement["text"], "text should contain last game's count"
        print(f"✅ Improvement text: {improvement['text']}")
    
    def test_improvement_verdict_slipping(self):
        """Test verdict is 'slipping' when mistakes increased"""
        postgame_result = {
            "result": "broken",
            "headline": "❌ Streak Broken",
            "message": "Test",
            "streak": 0,
            "best": 5,
            "tone": "warning"
        }
        
        game_summary = {
            "mistake_count": 6,
            "is_valid_for_streak": True
        }
        
        # Last game had 4 mistakes, this game has 6 (slipping)
        last_5_games = [
            {"game_id": "old_1", "mistake_count": 4, "is_valid": True},  # Last game
            {"game_id": "current", "mistake_count": 6, "is_valid": True}  # Current
        ]
        
        result = _enhance_postgame_messaging(
            postgame_result,
            game_summary,
            "THREAT_VERIFICATION",
            last_5_games=last_5_games
        )
        
        assert result["improvement"]["verdict"] == "slipping", f"Expected 'slipping', got {result['improvement']['verdict']}"
        print(f"✅ Slipping verdict: {result['improvement']['text']}")
    
    def test_improvement_verdict_same(self):
        """Test verdict is 'same' when mistakes unchanged"""
        postgame_result = {
            "result": "broken",
            "headline": "❌ Streak Broken",
            "message": "Test",
            "streak": 0,
            "best": 5,
            "tone": "warning"
        }
        
        game_summary = {
            "mistake_count": 4,
            "is_valid_for_streak": True
        }
        
        # Same mistake count
        last_5_games = [
            {"game_id": "old_1", "mistake_count": 4, "is_valid": True},  # Last game
            {"game_id": "current", "mistake_count": 4, "is_valid": True}  # Current
        ]
        
        result = _enhance_postgame_messaging(
            postgame_result,
            game_summary,
            "THREAT_VERIFICATION",
            last_5_games=last_5_games
        )
        
        assert result["improvement"]["verdict"] == "same", f"Expected 'same', got {result['improvement']['verdict']}"
        print(f"✅ Same verdict: {result['improvement']['text']}")
    
    def test_improvement_message_for_broken_streak(self):
        """Test improvement_message is added for broken streaks"""
        postgame_result = {
            "result": "broken",
            "headline": "❌ Streak Broken",
            "message": "Test",
            "streak": 0,
            "best": 5,
            "tone": "warning"
        }
        
        game_summary = {
            "mistake_count": 6,
            "is_valid_for_streak": True
        }
        
        # Slipping case
        last_5_games = [
            {"game_id": "old_1", "mistake_count": 4, "is_valid": True},
            {"game_id": "current", "mistake_count": 6, "is_valid": True}
        ]
        
        result = _enhance_postgame_messaging(
            postgame_result,
            game_summary,
            "THREAT_VERIFICATION",
            last_5_games=last_5_games
        )
        
        # Should have improvement_message for slipping
        assert "improvement_message" in result, "Should have improvement_message for slipping"
        print(f"✅ Improvement message: {result['improvement_message']}")
    
    def test_improvement_for_continued_streak(self):
        """Test improvement data for continued streak"""
        postgame_result = {
            "result": "continued",
            "headline": "✅ Streak: 3 Games",
            "message": "Clean game!",
            "streak": 3,
            "best": 5,
            "tone": "success"
        }
        
        game_summary = {
            "mistake_count": 0,  # Clean game
            "is_valid_for_streak": True
        }
        
        # Last game had 2 mistakes
        last_5_games = [
            {"game_id": "old_1", "mistake_count": 2, "is_valid": True},
            {"game_id": "current", "mistake_count": 0, "is_valid": True}
        ]
        
        result = _enhance_postgame_messaging(
            postgame_result,
            game_summary,
            "THREAT_VERIFICATION",
            last_5_games=last_5_games
        )
        
        # Should have improvement data
        assert "improvement" in result
        assert result["improvement"]["this_game"] == 0
        assert result["improvement"]["last_game"] == 2
        assert result["improvement"]["verdict"] == "improving"
        print(f"✅ Continued streak improvement: {result['improvement']['text']}")


class TestEnforcementLevelCheckbox:
    """Test EnforcementLevel.CHECKBOX_REQUIRED (Level 3) - GAP 1"""
    
    def test_enforcement_level_checkbox_required_exists(self):
        """Verify CHECKBOX_REQUIRED level exists in EnforcementLevel enum"""
        from coach_play.pre_move_guardian import EnforcementLevel
        
        assert hasattr(EnforcementLevel, 'CHECKBOX_REQUIRED'), "EnforcementLevel should have CHECKBOX_REQUIRED"
        assert EnforcementLevel.CHECKBOX_REQUIRED.value == 3, "CHECKBOX_REQUIRED should be level 3"
        print("✅ EnforcementLevel.CHECKBOX_REQUIRED exists at level 3")
    
    def test_enforcement_result_has_requires_checkbox(self):
        """Verify EnforcementResult has requires_checkbox field"""
        from coach_play.pre_move_guardian import EnforcementResult, EnforcementLevel, RiskType
        
        # Create an enforcement result with checkbox required
        result = EnforcementResult(
            level=EnforcementLevel.CHECKBOX_REQUIRED,
            should_block=False,
            requires_checkbox=True,
            message="Test message",
            explanation="Test explanation",
            repeat_count=3,
            risk_type=RiskType.IGNORE_THREAT
        )
        
        assert result.requires_checkbox == True, "requires_checkbox should be True"
        
        # Test to_dict includes requires_checkbox
        result_dict = result.to_dict()
        assert "requires_checkbox" in result_dict, "to_dict should include requires_checkbox"
        assert result_dict["requires_checkbox"] == True
        print("✅ EnforcementResult has requires_checkbox field")
    
    def test_enforcement_ladder_returns_checkbox_at_level_3(self):
        """Test EnforcementLadder returns requires_checkbox=True at level 3"""
        from coach_play.pre_move_guardian import EnforcementLadder, RiskType, RiskLevel, GuardianResult, InterventionType
        
        ladder = EnforcementLadder()
        
        # Simulate 3 warnings for same risk type (should trigger level 3)
        risk_type = RiskType.IGNORE_THREAT
        
        # Track 2 previous mistakes
        ladder.track_mistake(risk_type)
        ladder.track_mistake(risk_type)
        
        # Create a mock guardian result using MEDIUM risk level
        # (HIGH risk level adds +1 to level when repeat_count >= 2, which would make it level 4)
        mock_result = GuardianResult(
            should_intervene=True,
            intervention_type=InterventionType.WARN,
            risk_type=risk_type,
            risk_level=RiskLevel.MEDIUM,  # Use MEDIUM to get level 3 exactly
            message="Test message",
            explanation="Test explanation",
            alternative_moves=[],
            details={},
            processing_time_ms=0.0
        )
        
        # Get enforcement for 3rd occurrence using correct method name
        enforcement = ladder.evaluate_enforcement(mock_result)
        
        # Should be level 3 (CHECKBOX_REQUIRED)
        from coach_play.pre_move_guardian import EnforcementLevel
        assert enforcement is not None, "Enforcement should not be None"
        assert enforcement.level == EnforcementLevel.CHECKBOX_REQUIRED, f"Expected CHECKBOX_REQUIRED, got {enforcement.level}"
        assert enforcement.requires_checkbox == True, "requires_checkbox should be True at level 3"
        print(f"✅ EnforcementLadder returns requires_checkbox=True at level 3")
        print(f"   Message: {enforcement.message}")


class TestFocusMistakeTypes:
    """Test focus mistake types are properly defined"""
    
    def test_all_focus_types_have_required_fields(self):
        """Verify all focus types have name, short_name, description, rule"""
        required_fields = ["name", "short_name", "description", "rule"]
        
        for focus_type, info in FOCUS_MISTAKE_TYPES.items():
            for field in required_fields:
                assert field in info, f"{focus_type} missing {field}"
            print(f"✅ {focus_type}: {info['short_name']}")
    
    def test_threat_verification_type(self):
        """Test THREAT_VERIFICATION focus type"""
        threat_type = FOCUS_MISTAKE_TYPES.get("THREAT_VERIFICATION")
        assert threat_type is not None
        assert threat_type["short_name"] == "Threats"
        assert "opponent" in threat_type["rule"].lower() or "threatening" in threat_type["rule"].lower()
        print(f"✅ THREAT_VERIFICATION rule: {threat_type['rule']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
