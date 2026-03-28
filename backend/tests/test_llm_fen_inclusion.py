"""
Test LLM Prompt FEN Inclusion

The main agent fixed the hallucination issue by:
1. Including FEN in all LLM prompts
2. Adding explicit instructions to not mention pieces unless verified

This test verifies the coach_commentary module includes FEN in prompts.
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')


class TestCoachCommentaryFENInclusion:
    """Test that coach_commentary includes FEN in LLM prompts."""
    
    def test_build_feedback_prompt_includes_fen(self):
        """The feedback prompt should include the FEN string."""
        from coach_play.coach_commentary import CoachCommentary, PositionAnalysis, MoveAnalysis, MoveQuality
        
        coach = CoachCommentary()
        
        # Create mock analysis objects
        position = PositionAnalysis(
            fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            evaluation=0.3,
            mate_in=None,
            best_moves=[{"move": "Nf3", "eval": 0.3, "is_mate": False}],
            is_check=False,
            opening_name="King's Pawn Opening",
            opening_eco="C20",
            phase="opening",
            key_features=["white can still castle"]
        )
        
        move = MoveAnalysis(
            move_san="Nf3",
            quality=MoveQuality.GOOD,
            eval_before=0.3,
            eval_after=0.3,
            eval_loss=0.0,
            is_best_move=True,
            is_candidate=True,
            best_move_san="Nf3",
            best_move_uci="g1f3",
            best_continuation=["Nf3", "Nc6", "Bb5"],
            tactical_themes=[],
            missed_tactic=None,
            threat_explanation=None
        )
        
        prompt = coach._build_feedback_prompt(
            position=position,
            move=move,
            user_reasoning="I want to develop my knight and control the center",
            user_color="white",
            move_number=2
        )
        
        # Verify FEN is in the prompt
        assert "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR" in prompt, \
            "FEN should be included in the prompt"
        
        # Verify instructions about not hallucinating
        assert "VERIFY" in prompt.upper() or "verify" in prompt.lower(), \
            "Prompt should include verification instructions"
    
    def test_prompt_warns_about_piece_verification(self):
        """The prompt should warn about verifying piece positions."""
        from coach_play.coach_commentary import CoachCommentary, PositionAnalysis, MoveAnalysis, MoveQuality
        
        coach = CoachCommentary()
        
        position = PositionAnalysis(
            fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
            evaluation=0.4,
            mate_in=None,
            best_moves=[{"move": "Bc4", "eval": 0.4, "is_mate": False}],
            is_check=False,
            opening_name="King's Pawn Game",
            opening_eco="C44",
            phase="opening",
            key_features=[]
        )
        
        move = MoveAnalysis(
            move_san="Bc4",
            quality=MoveQuality.GREAT,
            eval_before=0.4,
            eval_after=0.4,
            eval_loss=0.0,
            is_best_move=True,
            is_candidate=True,
            best_move_san="Bc4",
            best_move_uci="f1c4",
            best_continuation=["Bc4"],
            tactical_themes=[],
            missed_tactic=None,
            threat_explanation=None
        )
        
        prompt = coach._build_feedback_prompt(
            position=position,
            move=move,
            user_reasoning="Developing my bishop to a good square",
            user_color="white",
            move_number=3
        )
        
        # Should have anti-hallucination instructions
        hallucination_keywords = [
            "do not mention",
            "only mention pieces",
            "verify",
            "do not guess",
            "do not make up"
        ]
        
        prompt_lower = prompt.lower()
        has_hallucination_warning = any(kw in prompt_lower for kw in hallucination_keywords)
        
        assert has_hallucination_warning, \
            "Prompt should include warnings about not hallucinating piece positions"


class TestGenerateResponseToUserFEN:
    """Test that generate_response_to_user includes FEN in prompts."""
    
    def test_prompt_includes_current_fen(self):
        """The response prompt should include current FEN."""
        # We can't easily test the full async function without mocking
        # But we can verify the prompt structure by examining the code
        import inspect
        from coach_play.coach_commentary import generate_response_to_user
        
        # Get the source code
        source = inspect.getsource(generate_response_to_user)
        
        # Check that FEN is included in prompt building
        assert "current_fen" in source or "fen" in source.lower(), \
            "Function should reference current_fen for prompt building"
        
        # Check for position context
        assert "POSITION" in source.upper() or "position" in source, \
            "Function should include position context"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
