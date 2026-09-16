"""The worse the move, the more sure the coach must be to speak.

Measured on the live server before this fix, each case in a fresh session so
nothing was suppressed as a repeat:

    159cp  mistake  advisory  "Stop. Your bishop on e6 is undefended."
    581cp  blunder  silent    -- nothing --
    479cp  blunder  silent    -- nothing --

A player who hung a piece got silence; a player who drifted a pawn and a half
got coached. Two independent causes, both in `evaluate_pending_move`:

1. The >=400cp branch set `layer` and `severity` and nothing else, then fell
   straight past the block that builds the sentence. The single worst class of
   move was the one class with no words.

2. The 1000ms hard timeout returned `layer: silent` and discarded the
   decision. The EVALUATION had already finished -- the same response still
   carried moveQuality=blunder and cpLoss=581 -- so what was thrown away was
   the cheap half. And because harder positions take longer to search, the
   budget was blown precisely on the moves that most needed a word.

After the fix, same probe:

    205cp  mistake  advisory            "Stop. You are losing your bishop."
    501cp  blunder  advisory            "This turns a good position into a bad one..."
    522cp  blunder  critical_interrupt  "Stop. You are losing your bishop."
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SRC = BACKEND / "routes" / "coach_play.py"


def _source() -> str:
    return io.open(SRC, encoding="utf-8").read()


def _evaluate_pending_body() -> str:
    src = _source()
    start = src.index("async def evaluate_pending_move")
    end = src.index("\nasync def ", start + 10)
    return src[start:end]


def test_severity_decides_the_layer_not_whether_there_are_words():
    """The >=400cp case must share the template block, not bypass it."""
    body = _evaluate_pending_body()
    assert 'if move_quality == "blunder" and cp_loss_val >= 400:\n            layer = "critical_interrupt"\n            severity = "high"\n        elif' not in body, (
        "the catastrophic-blunder branch must not skip text generation"
    )
    # The severity split has to sit INSIDE the mistake/blunder branch so both
    # arms reach pick_template below.
    outer = body.index('if move_quality in ("mistake", "blunder"):')
    inner = body.index('cp_loss_val >= 400', outer)
    template = body.index('text = tmpl.get("text")', outer)
    assert outer < inner < template, (
        "both severities must fall through to the shared template block"
    )


def test_a_catastrophic_blunder_still_picks_a_template():
    body = _evaluate_pending_body()
    segment = body[body.index('if move_quality in ("mistake", "blunder"):'):]
    segment = segment[:segment.index("# ─── ADVISORY")]
    assert "pick_template" in segment
    assert 'text = tmpl.get("text") or "This move needs another look."' in segment, (
        "there must be a floor so this branch cannot end up wordless"
    )


def test_the_timeout_does_not_discard_a_finished_evaluation():
    """A completed analysis must still produce a sentence."""
    body = _evaluate_pending_body()
    start = body.index("Hard timeout at")
    segment = body[start:start + 4000]
    assert "_to_quality" in segment and "pick_template" in segment, (
        "on timeout, a move already classified mistake/blunder must still be "
        "given words -- choosing a template costs microseconds"
    )
    assert 'in ("mistake", "blunder")' in segment
    # And only when the engine actually returned something.
    assert 'eval_result.get("depth", 0) > 0' in segment, (
        "never coach from an empty evaluation"
    )


def test_the_timeout_path_speaks_at_a_layer_the_client_renders():
    """critical_interrupt is invisible on the auto-commit path.

    `requires_hold` is hard-coded False, so the client auto-commits and only
    renders a strip for layers it knows about. A timeout decision that used
    the critical layer would look right in the payload and show nothing.
    """
    body = _evaluate_pending_body()
    start = body.index("Hard timeout at")
    segment = body[start:start + 4000]
    assert '"layer": "advisory"' in segment


def test_the_hold_is_still_disabled_so_nobody_re_enables_it_by_accident():
    """The hold path froze games once. This is not the fix for silence."""
    body = _evaluate_pending_body()
    assert "requires_hold = False" in body, (
        "re-enabling the hold needs the commit affordance rebuilt first -- see "
        "the comment above it; silence was fixed without touching this"
    )


def test_the_degraded_path_survives_any_budget_change():
    """Written as "the budget is unchanged", which then changed.

    The original point was that raising the budget must not be used INSTEAD of
    making the timeout speak -- a longer wait for everyone, papering over one
    branch. That still holds. But the budget was later raised deliberately, on
    a measurement rather than a hunch: the engine needs ~1480ms on an idle box
    while the client waits 3000ms, so 1000ms was giving up a full second
    before the browser would have.

    So this asserts the thing that actually matters and does not go stale the
    moment a number is tuned: whatever the budget, the timeout path must still
    pick a template for a mistake or a blunder rather than returning silent.
    The exact values are asserted once, with their ordering, in
    test_a_failed_eval_never_says_good.py.
    """
    body = _evaluate_pending_body()
    start = body.index("Hard timeout at")
    segment = body[start:start + 4000]
    assert "pick_template" in segment, (
        "a raised budget must not replace the timeout coaching -- if the "
        "engine still runs out, the move must still get words"
    )
    assert 'in ("mistake", "blunder")' in segment
