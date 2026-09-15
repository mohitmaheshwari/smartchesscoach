"""A coach that goes quiet under collapse is worse than no coach.

First real unified_v1 session (41bd8d36, 27 moves): 14 of 15 coaching
decisions were layer="silent" with text=None, coach_messages 0,
coach_interventions 0. Only move 27 spoke -- after the player had already lost
a rook, a knight, a bishop and another rook. The same player's legacy sessions
produce 22, 27 and 38 messages.

The caption layer was never the problem. `build_verified_caption` returns
verified text on those exact positions. Nothing upstream ever asked for it,
because of one fused condition:

    if quality in {"excellent", "good"} or not eval_valid:
        return _silent_response(quality)

Keeping a clean move quiet is deliberate. Going quiet because the ENGINE
failed is not -- it turns "we could not look" into "there was nothing to see".
`eval_valid` is `depth > 0`, and `fast_eval` returns depth 0 whenever it
exceeds its own 800ms budget. Profiled on this box the engine takes 907-1410ms,
so that fires routinely, and three consecutive calls on one position have
returned depth [0, 10, 10].

Legacy never had this hole: with an invalid eval it falls back to board
heuristics and still speaks.

Two guards here. One on the code path, and one on the CANARY -- the staging
check passed this release because it only ever played e4 and confirmed a reply.
It never played a position where the player is losing, which is exactly where
a coach that goes quiet survives the gate.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import services.unified_pwc_coaching as unified


# 1.e4 e5 2.Qh5 Nc6 3.Qxe5+?? -- the queen grabs a pawn the knight defends and
# is left en prise. Verified against detect_signals_fast, which reports
# hung_piece {'piece': 'queen', 'square': 'e5'}. The first draft of this test
# used plain Qh5, which hangs nothing immediately: the heuristic said None and
# it was right. Testing a "piece is hanging" fallback with a move that hangs
# no piece proves nothing.
HUNG_QUEEN_FEN = "r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3"
HUNG_QUEEN_UCI = "h5e5"

SESSION = {
    "game_mode": "coach",
    "current_fen": HUNG_QUEEN_FEN,
    "user_color": "white",
    "user_rating": 800,
    "move_history": [],
    "evaluations": [],
    "coaching_decisions": [],
}


def _dead_engine(*_a, **_k):
    """What fast_eval returns when it runs out of budget: depth 0."""
    return {
        "eval_before": 0.3, "eval_after": 0.3, "cp_loss": 0,
        "best_move": "", "move_quality": "unknown",
        "depth": 0, "nodes": 0, "elapsed_ms": 999,
    }


def _run(**over):
    kwargs = {
        "session_doc": dict(SESSION),
        "fen_before": HUNG_QUEEN_FEN,
        "uci": HUNG_QUEEN_UCI,
        "user_rating": 800,
    }
    kwargs.update(over)
    return asyncio.run(unified.evaluate_unified_pending(**kwargs))


def test_a_stalled_eval_is_retried_before_giving_up():
    """depth 0 is a race, not a verdict. Ask once more."""
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _dead_engine()
        return {
            "eval_before": 0.3, "eval_after": -4.0, "cp_loss": 430,
            "best_move": "Nf3", "move_quality": "blunder",
            "depth": 10, "nodes": 80000, "elapsed_ms": 260,
        }

    import services.fast_eval_service as fes
    original = fes.fast_eval
    fes.fast_eval = flaky
    try:
        result = _run()
    finally:
        fes.fast_eval = original

    # The retry itself is the behaviour under test. What the recovered eval
    # then produces is the normal caption path's business, tested elsewhere.
    assert calls["n"] == 2, "a depth-0 result must be retried once"
    assert result["moveEvaluation"]["moveQuality"] != "unknown", (
        "after a successful retry the verdict must come from the search"
    )


def test_a_hung_piece_still_gets_named_when_the_engine_never_recovers():
    """The floor. Legacy has it; unified did not, and went mute for 27 moves."""
    import services.fast_eval_service as fes
    original = fes.fast_eval
    fes.fast_eval = _dead_engine
    try:
        result = _run()
    finally:
        fes.fast_eval = original

    decision = result["coachingDecision"]
    assert decision["layer"] != "silent", (
        "a piece hanging in plain sight must not be silent just because the "
        "engine stalled"
    )
    assert decision.get("text"), decision
    assert decision.get("degradedEval") is True, (
        "the response must admit it reasoned without a search"
    )
    # It must not pretend to a verdict it does not have.
    assert result["moveEvaluation"]["moveQuality"] == "unknown"


def test_a_quiet_move_is_still_quiet():
    """The deliberate half of that condition must survive the fix."""
    import services.fast_eval_service as fes
    original = fes.fast_eval
    fes.fast_eval = lambda *a, **k: {
        "eval_before": 0.3, "eval_after": 0.28, "cp_loss": 2,
        "best_move": "Nf3", "move_quality": "good",
        "depth": 12, "nodes": 80000, "elapsed_ms": 180,
    }
    try:
        result = _run(uci="g1f3")
    finally:
        fes.fast_eval = original
    assert result["coachingDecision"]["layer"] == "silent"


def test_the_degraded_path_stays_silent_when_it_has_nothing_certain():
    """Guessing is not the fix for silence.

    With no hung piece and no missed threat, an unevaluated move gets no
    invented advice -- only the two signals legacy also trusts without a
    search earn a word.
    """
    quiet_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    session = dict(SESSION, current_fen=quiet_fen)

    import services.fast_eval_service as fes
    original = fes.fast_eval
    fes.fast_eval = _dead_engine
    try:
        result = _run(session_doc=session, fen_before=quiet_fen, uci="e2e4")
    finally:
        fes.fast_eval = original
    assert result["coachingDecision"]["layer"] == "silent"


def test_the_coach_never_tells_you_your_own_king_is_in_check_after_your_move():
    """`is_check()` asks about the SIDE TO MOVE, which is the opponent.

    `_get_move_detail` returned "Your king is now in check." whenever
    board_after.is_check() was true -- which is exactly when the player has
    just GIVEN check. It can never mean their own king, because moving into
    check is illegal, so the line was wrong every single time it fired.

    Caught on the canary position: Qxe5+ is a 596cp blunder, and the coaching
    read "This move costs you significantly. Your king is now in check."
    """
    from routes.coach_play import _get_move_detail

    board = chess.Board(
        "r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3")
    after = board.copy()
    after.push(chess.Move.from_uci("h5e5"))   # Qxe5+ -- BLACK is now in check

    assert after.is_check(), "fixture must actually give check"
    assert after.turn == chess.BLACK, "the opponent is the one in check"

    detail = _get_move_detail(board, after, "white", 596)
    assert "your king" not in (detail or "").lower(), (
        f"the player's king is not in check; got {detail!r}"
    )
    # It should have fallen through to the real reason: the queen is en prise.
    assert "queen" in (detail or "").lower() or detail == "", detail


# --- the canary that let this reach production ------------------------------

CANARY = BACKEND / "scripts" / "pwc_staging_canary.py"


@pytest.mark.skipif(not CANARY.exists(), reason="canary script not in this tree")
def test_the_canary_plays_a_losing_game_not_just_an_opening_move():
    """It played e4, saw a reply, and reported PASS.

    A coach that says nothing when the player is collapsing passes that check
    perfectly. The canary has to reach a position where the player is losing
    and assert that a blunder produces a visible layer.
    """
    src = io.open(CANARY, encoding="utf-8").read()
    assert "blunder" in src.lower(), "the canary must make a losing move"
    assert "silent" in src.lower(), (
        "the canary must assert the coach did NOT stay silent"
    )
