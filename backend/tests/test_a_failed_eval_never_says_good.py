"""If we did not evaluate the move, we must not call it a good one.

Profiled on the live server with per-stage timing inside evaluate_pending_move:

    a_session       =   1-2 ms
    b_weaknesses    =  15-31 ms
    c_focus         =  63-269 ms
    d_prelude_done  =  65-272 ms      <- every DB read, together
    e_engine_only   = 907-1410 ms     <- the engine alone blows the 1000ms budget

So the endpoint's budget is spent entirely in Stockfish, not in the database.
`fast_eval` has its own 800ms budget inside that, and when it fired it
returned `move_quality: "good"` with `depth: 0`:

  - `_timeout_result` said "good" outright;
  - the internal bail passed `eval_before` as `eval_after`, making cp_loss 0,
    which `_classify_quality` also calls "good".

`CoachPlay.jsx` paints `moveQuality` onto the board as an instant label. So a
move the engine never finished searching got a tick -- and on a loaded box
that included moves that hung a piece. The one thing we knew was that we knew
nothing, and we reported the opposite.

Callers already had the right signal (`eval_is_valid = depth > 0`) and used it
to fall back to the hung_piece / missed_threat heuristics. That behaviour is
deliberately unchanged here; what changes is that nothing claims a verdict it
does not have.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.fast_eval_service import (
    UNKNOWN_QUALITY,
    _build_result,
    _timeout_result,
)
import chess


def test_a_timed_out_search_reports_unknown_not_good():
    result = _timeout_result(cached_eval=0.4)
    assert result["move_quality"] == UNKNOWN_QUALITY
    assert result["move_quality"] != "good"
    # depth stays the machine-readable signal every caller already tests.
    assert result["depth"] == 0


def test_depth_zero_can_never_carry_a_quality():
    """cp_loss 0 at depth 0 means "compared a position with itself"."""
    result = _build_result(0.3, 0.3, "", chess.WHITE, 0, 0, 900.0)
    assert result["move_quality"] == UNKNOWN_QUALITY


def test_a_real_search_still_classifies_normally():
    """The honest path must be untouched."""
    good = _build_result(0.3, 0.25, "Nf3", chess.WHITE, 12, 80000, 210.0)
    assert good["move_quality"] == "good"

    blunder = _build_result(0.3, -4.0, "Nf3", chess.WHITE, 12, 80000, 260.0)
    assert blunder["move_quality"] == "blunder"
    assert blunder["cp_loss"] >= 300


def test_the_client_is_told_what_the_engine_said_not_the_working_value():
    """The endpoint normalises unknown->good internally, on purpose.

    Every downstream branch keeps the behaviour it had -- the heuristic
    fallbacks are what speak when the engine could not. But the value sent
    back to the browser must be the honest one, because that is what gets
    painted on the board.
    """
    src = io.open(BACKEND / "routes" / "coach_play.py", encoding="utf-8").read()
    body = src[src.index("async def evaluate_pending_move"):]
    body = body[:body.index("\nasync def ", 10)]

    assert 'reported_quality = eval_result.get("move_quality", "good")' in body
    assert '"moveQuality": move_quality,' not in body, (
        "responses must carry reported_quality, not the normalised working value"
    )
    assert body.count('"moveQuality": reported_quality') >= 2, (
        "both the silent path and the full path answer the client"
    )


def test_the_internal_normalisation_is_still_there():
    """Removing it would change which branch every unknown move takes."""
    src = io.open(BACKEND / "routes" / "coach_play.py", encoding="utf-8").read()
    body = src[src.index("async def evaluate_pending_move"):]
    body = body[:body.index("\nasync def ", 10)]
    assert 'if move_quality in ("mistake", "blunder", "unknown"):' in body
    assert "eval_is_valid" in body


def test_the_budgets_leave_the_engine_room_to_finish():
    """The endpoint must not give up before the browser would.

    Measured: DB prelude 65-272ms, engine 907-1410ms, two passes together
    ~1480ms. The old budgets (800 inside fast_eval, 1000 at the endpoint) were
    both below that, so the degraded path was the normal path on any move
    worth analysing. The client races at EVAL_TIMEOUT_MS = 3000, so there was
    a full second of headroom going unused.
    """
    fes = io.open(BACKEND / "services" / "fast_eval_service.py",
                  encoding="utf-8").read()
    endpoint = io.open(BACKEND / "routes" / "coach_play.py",
                       encoding="utf-8").read()
    flow = BACKEND.parent / "frontend" / "src" / "coachFlow" / "useCoachFlow.js"

    inner = int(re.search(r"HARD_TIMEOUT_MS = (\d+)", fes).group(1))
    outer = int(re.search(r"if elapsed_eval > (\d+):", endpoint).group(1))

    assert inner >= 1400, f"fast_eval bails before its two passes finish ({inner}ms)"
    assert outer > inner, (
        f"the endpoint ({outer}ms) must outlast fast_eval ({inner}ms), or the "
        "inner search can never complete"
    )
    if flow.exists():
        client = int(re.search(
            r"EVAL_TIMEOUT_MS = (\d+)",
            io.open(flow, encoding="utf-8").read()).group(1))
        assert outer <= client, (
            f"the endpoint ({outer}ms) must answer before the browser stops "
            f"waiting ({client}ms)"
        )


def test_the_board_label_is_skipped_when_we_do_not_know():
    # The deployed backend image ships without the frontend tree, so this
    # asserts only where the source is actually present (dev + CI).
    page_path = BACKEND.parent / "frontend" / "src" / "pages" / "CoachPlay.jsx"
    if not page_path.exists():
        pytest.skip("frontend source not present in this image")
    page = io.open(page_path, encoding="utf-8").read()
    assert 'moveQuality !== "unknown"' in page, (
        "an unevaluated move must not get an instant label"
    )
    assert 'quality !== "unknown"' in page, (
        "nor should an unfinished search count as 'not a bad move'"
    )
