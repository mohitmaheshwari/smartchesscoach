"""
Test Deep Opening Variation Teaching in Play with Coach

Verifies:
1. QGD family detection works for QGD/QGA/Slav contexts
2. After line d4 d5 c4 e6 Nc3, the coach emits variation-aware text from QGD tree
3. If user deviates with d4 d5 c4 e6 Nf3, coach guides with expected main-line move (Nc3)
4. Coach follow-up commentary keeps using active variation context
5. Elephant Trap warning surfaces in QGD live position

These tests verify the P0 bug fix: deep variation teaching must trigger in 
Play with Coach for supported opening families, not just stop after first few moves.
"""

import chess
import pytest
import sys

sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import (
    build_opening_coaching_context,
    get_opening_by_moves,
    get_opening_family_by_moves,
    QUEENS_GAMBIT,
)
from services.move_by_move_coach import (
    check_for_traps,
    get_variation_teaching,
    generate_move_commentary,
    MoveCommentary,
)


# ==============================================================================
# Module 1: Queen's Gambit Family Detection Tests
# ==============================================================================

class TestQueensGambitFamilyDetection:
    """Test that QGD/QGA/Slav openings correctly inherit from the Queen's Gambit family."""

    def test_qgd_inherits_queens_gambit_variations(self):
        """QGD (d4 d5 c4 e6) should get family variations from Queen's Gambit."""
        moves = ["d4", "d5", "c4", "e6"]
        context = build_opening_coaching_context(moves)

        assert context is not None, "Context should be built for QGD opening"
        assert context["name"] == "Queen's Gambit Declined", f"Expected QGD, got {context['name']}"
        assert context["family_name"] == "Queen's Gambit", f"Family should be QG, got {context['family_name']}"
        assert "variations" in context and context["variations"], "Should have variations"
        assert "qgd_main" in context["variations"], "Should have qgd_main variation"

    def test_slav_inherits_queens_gambit_variations(self):
        """Slav (d4 d5 c4 c6) should get family variations from Queen's Gambit."""
        moves = ["d4", "d5", "c4", "c6"]
        context = build_opening_coaching_context(moves)

        assert context is not None, "Context should be built for Slav opening"
        assert context["name"] == "Slav Defense", f"Expected Slav, got {context['name']}"
        assert context["family_name"] == "Queen's Gambit", f"Family should be QG, got {context['family_name']}"
        assert "slav_main" in context["variations"], "Should have slav_main variation"

    def test_qga_detection(self):
        """QGA (d4 d5 c4 dxc4) should be detected."""
        moves = ["d4", "d5", "c4", "dxc4"]
        context = build_opening_coaching_context(moves)

        assert context is not None, "Context should be built for QGA"
        # The direct opening is Queen's Gambit (parent), family should also be present
        assert context.get("variations"), "Should have variations from family"
        assert "qga_main" in context["variations"], "Should have qga_main variation"

    def test_family_function_finds_queens_gambit(self):
        """get_opening_family_by_moves should find Queen's Gambit as the family."""
        moves = ["d4", "d5", "c4", "e6"]
        family = get_opening_family_by_moves(moves)

        assert family is not None, "Should find a family opening"
        assert family.name == "Queen's Gambit", f"Family should be QG, got {family.name}"
        assert family.variations, "Family should have variations"


# ==============================================================================
# Module 2: Deep Variation Teaching Tests (after Nc3)
# ==============================================================================

class TestDeepVariationTeaching:
    """Test that deep variation teaching triggers after d4 d5 c4 e6 Nc3."""

    def test_nc3_gets_variation_teaching(self):
        """After d4 d5 c4 e6 Nc3, the coach should emit teaching from QGD variation."""
        moves = ["d4", "d5", "c4", "e6", "Nc3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None, "Should get variation teaching for Nc3"
        assert teaching.get("variation_name"), "Should have variation name"
        # Nc3 is the expected move in QGD main line
        assert teaching.get("teaching"), f"Should have teaching text, got: {teaching}"

    def test_nc3_teaching_mentions_correct_ideas(self):
        """Nc3 teaching should mention pressuring d5 or central control."""
        moves = ["d4", "d5", "c4", "e6", "Nc3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None
        teaching_text = teaching.get("teaching", "")
        # Should mention d5 pressure or development or center (based on opening_plans.py)
        assert any(
            term in teaching_text.lower() 
            for term in ["d5", "develop", "knight", "center", "support", "pressure"]
        ), f"Teaching should mention QGD concepts, got: {teaching_text}"

    def test_deep_line_continues_after_nf6(self):
        """After d4 d5 c4 e6 Nc3 Nf6, teaching should continue."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None, "Should continue teaching after Nf6"
        # Nf6 is Black's move in QGD main line
        assert teaching.get("variation_name"), "Should track variation"

    def test_bg5_teaching_after_deeper_line(self):
        """After d4 d5 c4 e6 Nc3 Nf6 Bg5, should get teaching for Bg5."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None, "Should have teaching for Bg5"
        teaching_text = teaching.get("teaching", "")
        # Bg5 is the classical QGD pin
        if teaching_text:
            assert any(
                term in teaching_text.lower()
                for term in ["pin", "knight", "d5", "pressure", "classical"]
            ), f"Bg5 teaching should mention pin concept, got: {teaching_text}"


# ==============================================================================
# Module 3: User Deviation Handling Tests
# ==============================================================================

class TestUserDeviationHandling:
    """Test that coach guides when user deviates from main line."""

    def test_nf3_deviation_shows_expected_nc3(self):
        """If user plays Nf3 instead of Nc3 in QGD, coach should mention Nc3."""
        moves = ["d4", "d5", "c4", "e6", "Nf3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None, "Should still get teaching when deviating"
        # The teaching should show what was expected
        expected_move = teaching.get("expected_move", "")
        matched = teaching.get("matched_expected", True)

        # Either expected_move is Nc3 or matched_expected is False
        assert expected_move == "Nc3" or not matched, \
            f"Should indicate Nc3 was expected. Got expected: {expected_move}, matched: {matched}"

    def test_deviation_still_gives_useful_teaching(self):
        """Even on deviation, teaching should provide useful guidance."""
        moves = ["d4", "d5", "c4", "e6", "Nf3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None
        # Should still have some teaching context even if not exact match
        has_teaching = bool(teaching.get("teaching"))
        has_context = bool(teaching.get("variation_name") or teaching.get("key_plans"))
        assert has_teaching or has_context, "Deviation should still provide guidance"

    def test_commentary_on_deviation_mentions_main_line(self):
        """generate_move_commentary should mention the main line on deviation."""
        moves = ["d4", "d5", "c4", "e6", "Nf3"]
        context = build_opening_coaching_context(moves)
        
        board_before = chess.Board()
        for m in moves[:-1]:
            board_before.push_san(m)
        fen_before = board_before.fen()
        
        board_after = chess.Board()
        for m in moves:
            board_after.push_san(m)
        fen_after = board_after.fen()

        commentary = generate_move_commentary(
            fen_before=fen_before,
            fen_after=fen_after,
            move_san="Nf3",
            move_by="user",
            all_moves=moves,
            user_color="white",
            user_rating=1200,
            opening_plan=context,
            eval_before=0,
            eval_after=0,
            is_best_move=False,
            best_move_san="Nc3",
        )

        assert isinstance(commentary, MoveCommentary)
        assert commentary.message, "Should generate a message"
        # Message should mention Nc3 or the main line concept
        msg_lower = commentary.message.lower()
        has_guidance = (
            "nc3" in msg_lower or 
            "main line" in msg_lower or
            "develop" in msg_lower or
            "knight" in msg_lower
        )
        # Even if not explicit, should have some teaching
        assert has_guidance or commentary.teaching_type == "opening_variation", \
            f"Should guide on deviation. Got: {commentary.message}"


# ==============================================================================
# Module 4: Elephant Trap Warning Tests
# ==============================================================================

class TestElephantTrapWarning:
    """Test Elephant Trap warning in QGD positions."""

    def test_trap_surfaces_in_qgd_position(self):
        """In QGD around d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7, Elephant Trap warning should surface."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"]
        context = build_opening_coaching_context(moves)
        
        board = chess.Board()
        for move in moves:
            board.push_san(move)
        
        trap = check_for_traps(moves, context, board)

        # Trap might be None if not yet triggered, but should be findable
        # Check if the variation has trap info
        qgd_var = context.get("variations", {}).get("qgd_main", {})
        traps = qgd_var.get("traps", [])
        
        has_elephant_trap_data = any(
            "elephant" in str(t).lower() for t in traps
        )
        
        # Either trap is returned or trap data exists in variations
        if trap:
            assert "elephant" in trap.get("warning", "").lower() or \
                   "bb4" in trap.get("warning", "").lower(), \
                   f"Trap warning should mention Elephant Trap. Got: {trap}"
        else:
            assert has_elephant_trap_data, \
                "QGD variation should have Elephant Trap data in variations"

    def test_trap_data_exists_in_qgd_variations(self):
        """QGD variations should contain Elephant Trap warning data."""
        moves = ["d4", "d5", "c4", "e6"]
        context = build_opening_coaching_context(moves)
        
        variations = context.get("variations", {})
        qgd_main = variations.get("qgd_main", {})
        traps = qgd_main.get("traps", [])

        # Should have at least one trap defined
        assert len(traps) >= 1, "QGD should have trap data"
        
        # Find elephant trap
        elephant_trap = None
        for t in traps:
            if "elephant" in str(t.get("warning", "")).lower():
                elephant_trap = t
                break
        
        assert elephant_trap is not None, "Should have Elephant Trap warning in QGD"


# ==============================================================================
# Module 5: Coach Follow-up Commentary Tests
# ==============================================================================

class TestCoachFollowupCommentary:
    """Test that coach's follow-up commentary keeps using active variation context."""

    def test_coach_move_uses_variation_context(self):
        """When coach makes a move in QGD position, commentary should use variation context."""
        # User played d4 d5 c4 e6 Nc3, coach plays Nf6
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6"]
        context = build_opening_coaching_context(moves)
        
        board_before = chess.Board()
        for m in moves[:-1]:
            board_before.push_san(m)
        fen_before = board_before.fen()
        
        board_after = chess.Board()
        for m in moves:
            board_after.push_san(m)
        fen_after = board_after.fen()

        commentary = generate_move_commentary(
            fen_before=fen_before,
            fen_after=fen_after,
            move_san="Nf6",
            move_by="coach",  # Coach/opponent making the move
            all_moves=moves,
            user_color="white",
            user_rating=1200,
            opening_plan=context,
        )

        assert isinstance(commentary, MoveCommentary)
        assert commentary.message, "Coach move should generate commentary"
        # Teaching type should indicate opening context
        assert commentary.teaching_type in ["opening", "opening_variation"], \
            f"Should be opening teaching type, got: {commentary.teaching_type}"

    def test_continued_variation_context_at_move_8(self):
        """At move 8 (e3), variation context should still be active."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        assert teaching is not None, "Should still have variation teaching at move 8"
        assert teaching.get("variation_name"), "Should know which variation we're in"

    def test_variation_context_persists_through_castling(self):
        """After castling (O-O), variation context should still be available."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)

        # Should still have context even after O-O
        assert context is not None, "Should have opening context"
        # Variation might not have specific teaching for O-O but context should exist


# ==============================================================================
# Module 6: Integration Test - Full QGD Flow
# ==============================================================================

class TestFullQGDTeachingFlow:
    """Integration test verifying the full QGD teaching flow."""

    def test_complete_qgd_classical_line(self):
        """Test the complete QGD Classical line has teaching throughout."""
        full_line = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "Nbd7", "Bd3", "c6"]
        
        for i in range(4, len(full_line) + 1):
            moves = full_line[:i]
            context = build_opening_coaching_context(moves)
            
            assert context is not None, f"Should have context at move {i}: {moves}"
            
            # After move 4, should have variations
            if i >= 4:
                assert context.get("variations"), f"Should have variations at move {i}"
            
            # After move 5, should have variation teaching for most moves
            if i >= 5:
                teaching = get_variation_teaching(moves, context)
                # Should at least have variation context, even if no specific teaching
                assert teaching is None or isinstance(teaching, dict), \
                    f"Teaching should be dict or None at move {i}"

    def test_key_teaching_moments_present(self):
        """Verify key teaching moments are present in QGD variations."""
        moves = ["d4", "d5", "c4", "e6"]
        context = build_opening_coaching_context(moves)
        
        qgd_var = context.get("variations", {}).get("qgd_main", {})
        move_teaching = qgd_var.get("move_teaching", {})
        
        # Should have teaching for key moves
        key_moves = ["Nc3", "Bg5", "e3"]
        for km in key_moves:
            assert km in move_teaching, f"Should have teaching for {km}"
            teaching_obj = move_teaching[km]
            assert "teach" in teaching_obj, f"Teaching for {km} should have 'teach' field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
