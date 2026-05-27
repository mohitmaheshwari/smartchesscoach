"""CI GUARD: prove no LLM fires in the move-coaching code paths.

Mohit 2026-05-27: "no LLM in coaching, review included." This test
converts that directive from "trust Claude's reading" into a
machine-checked invariant. It installs sys.settrace and runs the
move-coaching entry points for BOTH surfaces (review caption + PWC
move coaching), then asserts that `llm_service.call_llm` never
executed.

`call_llm` is the single chokepoint for ALL LLM text in the backend
(verified exhaustively 2026-05-27: 20 invocation sites, all routing
through llm_service.call_llm, including the injected call_llm_func
variants which call the same function). So "call_llm never ran" ==
"no LLM produced any text in this path".

Synthetic inputs only — no DB/network — so it runs anywhere in CI.

If this test fails, someone reintroduced an LLM call into a coaching
path. Fix the path, don't weaken the test.
"""
from __future__ import annotations

import os
import sys

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import chess  # noqa: E402

_BACKEND_MARKER = os.sep + "backend" + os.sep


class _LLMTracer:
    """Records whether llm_service.call_llm executed during the traced
    region, plus the set of backend functions seen (for diagnostics)."""

    def __init__(self) -> None:
        self.llm_fired = False
        self.llm_callers: list = []
        self.seen: set = set()

    def _trace(self, frame, event, arg):
        if event != "call":
            return None
        co = frame.f_code
        fn = co.co_filename
        if _BACKEND_MARKER not in fn or ".venv" in fn or "__pycache__" in fn:
            return None
        rel = fn.split(_BACKEND_MARKER, 1)[-1].replace(os.sep, "/")
        name = co.co_name
        self.seen.add((rel, name))
        if name == "call_llm" and rel.endswith("llm_service.py"):
            self.llm_fired = True
            # Capture the caller for a useful failure message.
            back = frame.f_back
            if back is not None:
                bco = back.f_code
                self.llm_callers.append(
                    f"{bco.co_filename.split(_BACKEND_MARKER,1)[-1]}::{bco.co_name}"
                )
        return None

    def __enter__(self):
        sys.settrace(self._trace)
        return self

    def __exit__(self, *exc):
        sys.settrace(None)
        return False


def _synthetic_move_inputs(**overrides):
    from services.caption_pipeline import MoveInputs
    defaults = dict(
        fen_before="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1",
        played_san="Nxe5",
        mover_is_user=True,
        mover_is_white=True,
        user_color="white",
        full_move_number=4,
        move_history_san=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
        best_move_san="d3",
        cp_loss=200,
        eval_before_cp=20,
        eval_after_cp=-180,
    )
    defaults.update(overrides)
    return MoveInputs(**defaults)


class TestNoLLMInCoaching:
    """The core invariant: move-coaching paths fire zero call_llm."""

    def test_central_layer_user_mistake_no_llm(self):
        from services.caption_pipeline import build_move_teaching_decision, CrossMoveState
        with _LLMTracer() as t:
            build_move_teaching_decision(_synthetic_move_inputs(), CrossMoveState())
        assert not t.llm_fired, (
            f"LLM fired in central-layer user-mistake path. Callers: {t.llm_callers}"
        )

    def test_central_layer_opponent_move_no_llm(self):
        from services.caption_pipeline import build_move_teaching_decision, CrossMoveState
        with _LLMTracer() as t:
            build_move_teaching_decision(
                _synthetic_move_inputs(mover_is_user=False, user_color="black"),
                CrossMoveState(),
            )
        assert not t.llm_fired, (
            f"LLM fired in central-layer opponent-move path. Callers: {t.llm_callers}"
        )

    @pytest.mark.asyncio
    async def test_pwc_generate_move_coaching_no_llm(self):
        from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
        board = chess.Board(
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1"
        )
        mv = board.parse_san("Nxe5")
        with _LLMTracer() as t:
            await generate_move_coaching(
                board_before=board, move=mv, best_move_san="d3",
                pv_after_played=[], pv_after_best=[], cp_loss=200,
                phase="middlegame", is_user_move=True,
                context=CoachingContext.LIVE_AFTER_USER, user_color="white",
            )
        assert not t.llm_fired, (
            f"LLM fired in PWC generate_move_coaching. Callers: {t.llm_callers}"
        )

    def test_pwc_live_entry_points_no_llm(self):
        from services.live_v5_teaching import (
            socratic_feedback_for_live_move,
            coach_move_narration_for_live_move,
        )
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1"
        with _LLMTracer() as t:
            socratic_feedback_for_live_move(
                fen_before=fen, played_san="Nxe5", user_color="white",
                severity="blunder", fundamental_violated="hanging_pieces",
                coach_intent=None, phase="middlegame", cp_loss=200, user_rating=1200,
            )
            coach_move_narration_for_live_move(
                fen_before=fen, played_san="Nxe5", user_color="white",
                move_history_san=[], full_move_number=4,
                v2_context={"v2": True, "teaching_goal": "threat_awareness"},
            )
        assert not t.llm_fired, (
            f"LLM fired in PWC live entry points. Callers: {t.llm_callers}"
        )

    def test_v5_narrator_is_deterministic(self):
        """The review narrative fallback must not call the LLM."""
        import asyncio
        from services.v5_llm_narrator import generate_concise_narrative
        with _LLMTracer() as t:
            asyncio.get_event_loop().run_until_complete(
                generate_concise_narrative(
                    move_san="Nxe5",
                    plan_data={"current_problem": "leaves the knight hanging",
                               "better_approach": "d3"},
                    phase="middlegame", severity="blunder", is_user_move=True,
                )
            )
        assert not t.llm_fired, (
            f"LLM fired in v5_llm_narrator. Callers: {t.llm_callers}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
