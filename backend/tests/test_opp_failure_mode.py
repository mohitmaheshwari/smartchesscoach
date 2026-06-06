"""Regression tests for the opp-side failure-mode predicate framework.

Shipped 2026-06-06 (commit 700fb473) as the permanent fix for
"opponent's move is a mistake but doesn't say WHY". These tests anchor:

  - opp_failure_missed_capture fires when the opponent had a capture
    available (engine best_move) and played something else. Canonical
    case fb_4899b11157fa: 9.Qe2 hangs d4, opp plays 9...Nbd7 missing
    9...Qxd4 (free pawn).
  - opp_failure_missed_mate fires when the opp's best-move PV forces mate.
  - The facts do NOT fire on user moves (mover_is_user=True) or when the
    opp actually played the best move (no missed opportunity).
  - The R12_blunder.json end-to-end render produces the combined
    "Opponent's X is a mistake — they had Y, grabbing your Z ... " caption.

Pure-function pytest; no DB, no engine calls (engine truth is passed in
as best_move_san / pv_after_best, mirroring how the V5 service feeds it).
"""
from __future__ import annotations

import os
import sys

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_facts import extract_facts  # noqa: E402
from services.caption_templates import render_rule  # noqa: E402


# The canonical case: after 9.Qe2 (White/user) hangs d4, Black/opp plays
# 9...Nbd7 missing 9...Qxd4. FEN is the position with Black to move.
NBD7_FEN = "rnbq1rk1/pp3pbp/2p1pnp1/4N3/2BP1B2/2N5/PPP1QPPP/R3K2R b KQ - 1 9"


# ─── Fact extraction ────────────────────────────────────────────────


def test_missed_capture_fires_on_nbd7():
    facts = extract_facts(
        fen_before=NBD7_FEN,
        played_san="Nbd7",
        best_move_san="Qxd4",      # engine truth, depth 20
        cp_loss=166,
        pv_after_best=["Qxd4"],
        mover_is_user=False,
    )
    assert facts["opp_failure_missed_capture"] is True
    assert facts["opp_missed_capture_san"] == "Qxd4"
    assert facts["opp_missed_capture_piece"] == "pawn"
    assert facts["opp_missed_capture_square"] == "d4"


def test_missed_capture_silent_on_user_move():
    # Same position/move but flagged as the USER's move — opp_failure_*
    # must NOT fire (these are opponent-only facts).
    facts = extract_facts(
        fen_before=NBD7_FEN,
        played_san="Nbd7",
        best_move_san="Qxd4",
        cp_loss=166,
        pv_after_best=["Qxd4"],
        mover_is_user=True,
    )
    assert facts["opp_failure_missed_capture"] is False
    assert facts["opp_missed_capture_san"] is None


def test_missed_capture_silent_when_best_was_played():
    # Opp PLAYED the best move (Qxd4) — no missed opportunity, no fire.
    facts = extract_facts(
        fen_before=NBD7_FEN,
        played_san="Qxd4",
        best_move_san="Qxd4",
        cp_loss=0,
        mover_is_user=False,
    )
    assert facts["opp_failure_missed_capture"] is False


def test_missed_capture_silent_when_best_is_not_a_capture():
    # Best move is a quiet developing move, not a capture → no missed
    # capture. (O-O is legal for Black here? No — use a quiet move that
    # is legal in the position: ...a6.)
    facts = extract_facts(
        fen_before=NBD7_FEN,
        played_san="Nbd7",
        best_move_san="a6",       # quiet, non-capture
        cp_loss=80,
        mover_is_user=False,
    )
    assert facts["opp_failure_missed_capture"] is False


def test_missed_mate_fires_when_pv_forces_mate():
    facts = extract_facts(
        fen_before=NBD7_FEN,
        played_san="Nbd7",
        best_move_san="Qxd4",
        cp_loss=166,
        pv_after_best=["Qxd4", "Nf3", "Qd1#"],   # mate in the PV
        mover_is_user=False,
    )
    assert facts["opp_failure_missed_mate"] is True
    assert facts["opp_missed_mate_san"] == "Qxd4"


# ─── End-to-end render through R12_blunder.json ─────────────────────


def _r12_facts(**overrides):
    base = {
        "mover_is_user": False,
        "played_san": "Nbd7",
        "cp_loss": 166,
        "severity": "mistake",
        "opp_failure_missed_capture": True,
        "opp_missed_capture_san": "Qxd4",
        "opp_missed_capture_piece": "pawn",
        "opp_missed_capture_square": "d4",
        "opp_failure_missed_mate": False,
        "opp_missed_mate_san": None,
    }
    base.update(overrides)
    return base


def test_render_combines_failure_and_user_response():
    # With a user-response why ("Play O-O") present, the caption should
    # combine the opp-failure clause and the response.
    out = render_rule("R12_blunder", _r12_facts(
        user_best_reply_san="O-O", opp_has_concrete_why=True,
    ))
    assert out is not None
    assert "Nbd7 is a mistake" in out
    assert "Qxd4" in out
    assert "d4" in out
    assert "Play O-O" in out


def test_render_failure_only_when_no_user_response():
    out = render_rule("R12_blunder", _r12_facts(
        user_best_reply_san=None, opp_has_concrete_why=False,
    ))
    assert out is not None
    assert "Nbd7 is a mistake" in out
    assert "Qxd4" in out
    # No user-response tail
    assert "Play" not in out


def test_render_uses_em_dash_not_period_before_failure():
    # The failure clause should be joined with an em-dash, not a period,
    # so it reads "is a mistake — they had Qxd4 ..." (the v110 voice).
    out = render_rule("R12_blunder", _r12_facts(
        user_best_reply_san="O-O", opp_has_concrete_why=True,
    ))
    assert "—" in out  # em-dash present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
