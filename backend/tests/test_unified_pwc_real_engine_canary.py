"""Opt-in LOCAL engine -> canonical caption -> decision canary.

Run with RUN_PWC_ENGINE_CANARY=1 and STOCKFISH_PATH set to a local executable.
Synthetic games only: no DB, HTTP, production records or model calls.
"""
import os
from concurrent.futures import ThreadPoolExecutor

import chess
import pytest

from services import fast_eval_service as fast
from services.unified_pwc_coaching import evaluate_unified_pending

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PWC_ENGINE_CANARY") != "1",
    reason="Requires explicit local-engine canary opt-in",
)


def test_concurrent_real_searches_are_verified_or_explicitly_unavailable():
    engine = fast._get_engine()
    board = chess.Board()
    for san in "e4 e5 Qh5 Nc6".split():
        board.push_san(san)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: fast.fast_eval(board.fen(), "h5e5"), range(4)))
        assert any(result["depth"] > 0 for result in results)
        for result in results:
            if result["depth"] > 0:
                assert result["move_quality"] == "blunder", result
                assert result["search_evidence"]["fen_before"] == board.fen()
            else:
                assert result["move_quality"] == "unknown"
                assert result.get("failure_reason")
    finally:
        engine.quit()
        fast._warm_engine = None


@pytest.mark.asyncio
@pytest.mark.parametrize("sequence,color,decisive", [
    ("f3 e5 g4 Qh4#", "white", "g4"),
    ("e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#", "black", "Nf6"),
    ("e4 e5 Qh5 Nc6 Qxe5+ Nxe5", "white", "Qxe5+"),
])
async def test_losing_sequence_gets_verified_coaching(sequence, color, decisive):
    engine = fast._get_engine()  # Warmup is explicit; this is not a cold-start latency test.
    board = chess.Board()
    history, decisions = [], []
    reached = False
    try:
        for san in sequence.split():
            move = board.parse_san(san)
            if board.turn == (color == "white"):
                result = await evaluate_unified_pending(
                    session_doc={
                        "game_mode": "coach", "current_fen": board.fen(),
                        "user_color": color, "move_history": history,
                        "coaching_decisions": decisions,
                    },
                    fen_before=board.fen(), uci=move.uci(), user_rating=1200,
                )
                decision = result["coachingDecision"]
                decisions.append(decision)
                if san == decisive:
                    reached = True
                    assert result["_engineEvidence"]["eval_valid"], result
                    assert result["moveEvaluation"]["moveQuality"] == "blunder", result
                    assert decision["layer"] == "critical_interrupt", result
                    assert decision["text"], result
                    assert decision["proof"]["caption_verified"], result
            history.append({"move": san})
            board.push(move)
        assert reached
        if sequence.endswith("#"):
            assert board.is_checkmate()
    finally:
        engine.quit()
        fast._warm_engine = None
