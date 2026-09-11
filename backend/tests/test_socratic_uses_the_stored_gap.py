"""The Socratic surface should use the diagnosis the analyser already made.

Review derived `fundamental_violated` from exactly two board facts --
`pieces_now_undefended` and `missed_tactic_kind` -- and fell to the generic
variant for everything else. Across 8,405 stored Socratic cards:

    generic variants                       7,230   86.0%
    mistake_hanging                          423    5.0%
    blunder_hanging_with_capture             412    4.9%
    blunder_threat_fork                      142    1.7%
    blunder_threat_mate                      116    1.4%
    blunder_hanging_with_mate                 81    1.0%
    blunder_threat_capture                     1    0.0%

Eleven of the nineteen variants never fired at all. Meanwhile every analysed
move already carries a `cognitive_gap`, and of those 7,230 generic cards:

    king_safety         1,546  21.4%   variants exist, never fired
    piece_safety        1,083  15.0%
    missed_tactic         923  12.8%
    endgame_technique     770  10.7%
    opening_knowledge     764  10.6%
    tactical_oversight    433   6.0%
    <no gap stored>     1,711  23.7%

The mapping is deliberately partial. `opening_knowledge` is not mapped to
`development`, because that variant claims "you moved a developed piece
instead of bringing a new one out" and leaving known theory does not
establish that. `endgame_technique`, `pawn_structure`, `piece_activity` and
`time_pressure` have no honest variant at all. A wrong name is worse than no
name -- services/concept_attribution.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import (
    GAP_TO_FUNDAMENTAL,
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# A quiet losing move that leaves nothing hanging: neither board fact fires, so
# this is exactly the 86% case where the stored gap is the only diagnosis
# available. h3 in the Italian, called a 200cp error.
QUIET_MISTAKE_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1"


def _decide(cognitive_gap, played_san="h3", cp_loss=200):
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=QUIET_MISTAKE_FEN,
            played_san=played_san,
            mover_is_user=True,
            mover_is_white=True,
            user_color="white",
            full_move_number=4,
            move_history_san=["e4", "e5", "Bc4", "Nc6"],
            best_move_san="O-O",
            eval_before_cp=20,
            eval_after_cp=20 - cp_loss,
            cp_loss=cp_loss,
            user_rating=1200,
            cognitive_gap=cognitive_gap,
            pv_after_played=[],
            pv_after_best=[],
            allow_fresh_engine_verification=False,
        ),
        CrossMoveState(),
    )


def test_the_mapping_only_claims_what_a_variant_can_honestly_say():
    assert GAP_TO_FUNDAMENTAL == {
        "piece_safety": "hanging_pieces",
        "missed_tactic": "calculate",
        "tactical_oversight": "calculate",
        "calculation_depth": "calculate",
        "king_safety": "king_safety",
    }
    # The ones left out are left out on purpose, and each has a reason in the
    # module comment. Adding one here without a variant that says something
    # the gap establishes is the failure this test exists to catch.
    for gap in ("opening_knowledge", "endgame_technique", "pawn_structure",
                "piece_activity", "time_pressure"):
        assert gap not in GAP_TO_FUNDAMENTAL, (
            f"{gap!r} has no variant that says something it establishes"
        )


@pytest.mark.parametrize("gap,expected", [
    ("king_safety", "Your king"),
    ("missed_tactic", "calculate"),
    ("tactical_oversight", "calculate"),
    ("calculation_depth", "calculate"),
])
def test_a_stored_gap_reaches_the_right_variant(gap, expected):
    decision = _decide(gap)
    extras = decision.socratic_extras
    assert extras is not None, f"{gap} produced no Socratic coaching at all"
    assert expected.lower() in extras.narrative.lower(), (
        f"{gap} should have selected the matching variant, got: "
        f"{extras.narrative!r}"
    )
    assert extras.question.strip().endswith("?")


def test_an_unmapped_gap_stays_generic_rather_than_guessing():
    for gap in ("endgame_technique", "opening_knowledge", "pawn_structure"):
        extras = _decide(gap).socratic_extras
        assert extras is not None
        assert "mistake" in extras.narrative.lower(), (
            f"{gap} should fall to the generic variant, not invent a "
            f"diagnosis: {extras.narrative!r}"
        )


def test_no_gap_behaves_exactly_as_before():
    without = _decide(None).socratic_extras
    assert without is not None
    assert "mistake" in without.narrative.lower()


def test_a_board_proved_fact_still_outranks_the_stored_label():
    # A piece hanging after the move is checked against THIS position; the gap
    # is a stored classification of it. When they disagree the board wins.
    # Nxe5 leaves the knight on e5 undefended, so the hanging-piece variant
    # speaks even though the stored gap says king_safety.
    extras = _decide("king_safety", played_san="Nxe5").socratic_extras
    assert extras is not None
    assert "e5" in extras.narrative, extras.narrative
    assert "king" not in extras.narrative.lower()


def test_the_narrative_never_speaks_about_the_player_in_the_third_person():
    # The evidence strings were inherited from smart_coaching as notes written
    # ABOUT the student, and R18 narratives embedded them. Only the variants
    # that did not use them ever fired, so "Your king position got weaker.
    # Student's king is in danger" was latent until the gap wiring made those
    # variants fire.
    for gap in ("king_safety", "missed_tactic", "calculation_depth", None):
        extras = _decide(gap).socratic_extras
        assert extras is not None
        for field in (extras.narrative, extras.plan, extras.question, extras.hint):
            assert "student" not in field.lower(), field
            assert "{" not in field and "}" not in field, field
