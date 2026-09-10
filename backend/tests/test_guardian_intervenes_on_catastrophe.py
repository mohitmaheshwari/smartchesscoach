"""The guardian must actually stop the blunder it says it can see.

From the real game on 2026-09-10, at the move that lost the queen:

    risk_level       = high
    risk_type        = material_loss
    message          = "Bad trade! Losing queen for pawn."
    should_intervene = False        <-- it saw it and said nothing

Two independent faults produced that. The engine never ran (fixed in
test_pre_move_guardian_engine_wiring.py), and even with the engine running the
severity ceiling made intervention impossible: material_loss graded at most
HIGH, while _decide_intervention fires only on CRITICAL. So queen-for-a-pawn
(net -8) scored identically to knight-for-a-pawn (net -2), and no material loss
could ever be blocked -- although the policy docstring names "losing a queen for
nothing" as exactly what it exists to block.

The philosophy is deliberately preserved: minor-piece mistakes still fall
through to the Socratic system, which teaches after the fact.
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from coach_play.pre_move_guardian import PreMoveGuardian, RiskLevel  # noqa: E402

# The exact position from that game, White to move, before Qxe6+ hung the queen.
QUEEN_BLUNDER_FEN = "rnbqkbnr/ppp2ppp/4p3/8/P7/5p2/1PPPQPPP/RNB1KB1R w KQkq - 0 5"


def _verdict(fen, san, color="white", before=None, after=None):
    return PreMoveGuardian(3).evaluate_move(
        fen=fen, move_san=san, user_color=color,
        stockfish_eval_before=before, stockfish_eval_after=after,
    ).to_dict()


def test_hanging_the_queen_is_blocked():
    """The regression, pinned to the real position that lost a real queen."""
    v = _verdict(QUEEN_BLUNDER_FEN, "Qxe6+")
    assert v["risk_type"] == "material_loss"
    assert v["risk_level"] == RiskLevel.CRITICAL.value, (
        f"queen-for-a-pawn graded {v['risk_level']}; a catastrophic material "
        "loss must reach CRITICAL or _decide_intervention can never fire"
    )
    assert v["should_intervene"] is True, (
        "the guardian identified 'Bad trade! Losing queen for pawn' and still "
        "let it through"
    )


def test_a_minor_piece_mistake_still_teaches_instead_of_blocking():
    """Deliberate: the Socratic system owns the small stuff. Don't over-block."""
    # 1.e4 e5 2.Nf3 Nc6 3.Bc4 -- Bxf7+ drops a bishop for a pawn (net -2).
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    v = _verdict(fen, "Bxf7+")
    assert v["risk_level"] != RiskLevel.CRITICAL.value, (
        "a bishop-for-pawn trade is a teaching moment, not a catastrophe; "
        "blocking it would make the coach nag"
    )
    assert v["should_intervene"] is False


def test_a_normal_developing_move_is_never_flagged():
    v = _verdict("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e4")
    assert v["should_intervene"] is False
    assert v["risk_level"] == RiskLevel.NONE.value


def test_intervention_budget_is_still_respected():
    """Three interventions per game; a spent budget stays silent."""
    spent = PreMoveGuardian(0).evaluate_move(
        fen=QUEEN_BLUNDER_FEN, move_san="Qxe6+", user_color="white",
    ).to_dict()
    assert spent["should_intervene"] is False, (
        "budget exhaustion must still win, or the guardian becomes the nag "
        "this whole change is trying to remove"
    )


def test_an_intervention_always_offers_a_better_move():
    """Stopping a player without an alternative is worse than staying quiet.

    The sidebar renders guardianIntervention.alternative_moves and nothing
    else -- it never reads analysis.best_move. _suggest_alternatives covers
    only HANGING_PIECE and IGNORE_THREAT, so the live queen blunder produced
    should_intervene=True with alternative_moves=[] while the engine had Qe3
    in hand. The route now backfills from the engine's best move.
    """
    import ast
    import io as _io

    source = _io.open(BACKEND / "routes" / "coach_play.py", encoding="utf-8").read()
    assert 'result["alternative_moves"] = [best_move_san]' in source, (
        "an intervention with an empty alternative_moves shows the player a "
        "red stop sign and no way forward"
    )
    ast.parse(source)
