"""The played move's consequence when it arrives LATER than the first reply.

Every other played-move failure predicate in R12_blunder.json reads
`opp_reply_*` — ply 1 of the stored line and nothing else. Measured 2026-09-30
over 12,000 stored lines, 26.8% resolve at ply 1 and a further 36.0% resolve
later (ply 3 alone is 17.5%), invisible to all of them, which is where 80% of
the ALT_WHY_ONLY class came from. See docs/missing_why_diagnosis_2026_09_30.md.

The `line_loss_*` facts walk the engine's own stored line and name the first
capture of one of the MOVER's pieces at ply >= 2, and only when the line ENDS
with the mover down at least a pawn — so an even trade inside the line is never
reported as a loss.

Every position here is a real row from the prod corpus, with the engine's own
stored `pv_after_played`. Pure functions: no DB, no engine call.
"""
from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.caption_facts import extract_facts  # noqa: E402
from services.caption_templates import render_rule  # noqa: E402

# White played b3; Black's f6 hits the e5 pawn and fxe5 wins it at ply 3.
# White ends a pawn down, so the clause is licensed.
LOSES_PAWN_AT_PLY3 = dict(
    fen_before="r1b1k1nr/pp3ppp/1qn1p3/2bpP3/8/5N2/PPP1QPPP/RNB1KB1R w KQkq - 2 7",
    played_san="b3",
    best_move_san="Nbd2",
    cp_loss=121,
    pv_after_played=["f6", "Nc3", "fxe5", "Bb2"],
)

# Black played f5; White's f3 hits the bishop and fxe4 takes it at ply 3.
# Black recaptures a pawn, so the net is still a bishop for a pawn.
LOSES_BISHOP_AT_PLY3 = dict(
    fen_before="r6r/pppk1p2/2n2p2/3p3p/3Pb3/P1Q3PP/1PPN1P2/1K2R3 b - - 1 18",
    played_san="f5",
    best_move_san="Bg6",
    cp_loss=133,
    pv_after_played=["f3", "Rae8", "fxe4", "fxe4"],
)

# Black played Nd4. Bxg4 takes a black bishop at ply 3, but the whole line
# settles dead level (Nxd4 exd4 Bxg4 dxc3), so nothing was lost.
EVEN_TRADE = dict(
    fen_before="r2q1rk1/ppp1bppp/2n2n2/4p3/1PP3b1/P1N2N2/1B1PBPPP/R2QR1K1 b - - 4 11",
    played_san="Nd4",
    best_move_san="e4",
    cp_loss=206,
    pv_after_played=["Nxd4", "exd4", "Bxg4", "dxc3"],
)

# The only capture is at ply 1, which the opp_reply_* predicates already own.
ONLY_PLY_1 = dict(
    fen_before="rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    played_san="Nc3",
    best_move_san="exd5",
    cp_loss=120,
    pv_after_played=["dxe4"],
)


# ─── The facts ──────────────────────────────────────────────────────


def test_names_the_capture_that_arrives_at_ply_3():
    f = extract_facts(mover_is_user=True, **LOSES_PAWN_AT_PLY3)
    assert f["line_loss_san"] == "fxe5"
    assert f["line_loss_piece_type"] == "pawn"
    assert f["line_loss_square"] == "e5"
    assert f["line_loss_ply"] == 3


def test_a_bishop_lost_for_a_pawn_still_counts():
    f = extract_facts(mover_is_user=True, **LOSES_BISHOP_AT_PLY3)
    assert f["line_loss_san"] == "fxe4"
    assert f["line_loss_piece_type"] == "bishop"
    assert f["line_loss_square"] == "e4"


def test_silent_when_the_line_ends_level():
    """The guard that stops a trade being sold as a loss."""
    f = extract_facts(mover_is_user=True, **EVEN_TRADE)
    assert f["line_loss_san"] is None
    assert f["line_loss_piece_type"] is None


def test_silent_when_the_only_capture_is_the_first_reply():
    """Ply 1 belongs to the opp_reply_* predicates; this must not duplicate it."""
    f = extract_facts(mover_is_user=True, **ONLY_PLY_1)
    assert f["line_loss_san"] is None


def test_silent_without_a_stored_line():
    f = extract_facts(
        fen_before=LOSES_PAWN_AT_PLY3["fen_before"],
        played_san="b3", best_move_san="Nbd2", cp_loss=121,
        pv_after_played=[], mover_is_user=True,
    )
    assert f["line_loss_san"] is None


# ─── The possessive in _recommended_move_why ────────────────────────
# Three branches describing the MOVER's own pieces hardcoded "your", so an
# opponent card read "it defends your pawn on b5" about the opponent's pawn:
# 47 of 238 such cards on 2026-09-30.


def _why(mover_is_user):
    return extract_facts(mover_is_user=mover_is_user, **LOSES_BISHOP_AT_PLY3)["best_move_why"]


def test_possessive_is_yours_on_a_user_card():
    assert "your" in (_why(True) or "")


def test_possessive_is_theirs_on_an_opponent_card():
    why = _why(False) or ""
    assert "their" in why
    assert "your" not in why


def test_possessive_goes_neutral_when_the_mover_is_unknown():
    """A neutral phrase is never wrong; a guessed one is wrong half the time."""
    why = _why(None) or ""
    assert "your" not in why
    assert "their" not in why


# ─── End-to-end through R12_blunder.json ────────────────────────────


def _r12(mover_is_user, **overrides):
    f = {
        "mover_is_user": mover_is_user,
        "played_san": "b3",
        "best_move_san": "Nbd2",
        "cp_loss": 121,
        "severity": "mistake" if mover_is_user else "opp_mistake",
        "severity_practical": "mistake",
        "severity_canonical": "mistake",
        "opp_reply_san": "f6",
        "line_loss_san": "fxe5",
        "line_loss_piece_type": "pawn",
        "line_loss_square": "e5",
        "line_loss_ply": 3,
    }
    f.update(overrides)
    return f


def test_user_side_clause_is_deliberately_not_wired():
    """The facts are computed for both sides; only the OPPONENT clause ships.

    The user-side predicate was built, verified at 100% precision over 2,690
    firings — and withdrawn. Full-population rendering showed it also cost 248
    user cards their R12 caption: the card fell through to a promoted tier rule
    with weaker text, 179 of them from ALT_WHY_ONLY to NO_WHY. The fact is set
    on 14.0% of random user cards and on 100% of those 248, so it is the cause,
    not a coincidence — but the mechanism is not understood, and a user-facing
    regression that cannot be explained should not ship on a 10:1 trade.

    This test exists so re-wiring it is a deliberate act: deleting this test is
    the reminder to re-measure the 248 first.
    """
    out = render_rule("R12_blunder", _r12(True)) or ""
    assert "fxe5" not in out


def test_opponent_caption_says_their_piece_not_yours():
    out = render_rule("R12_blunder", _r12(False)) or ""
    assert "fxe5" in out
    assert "their pawn on e5" in out
    assert "your pawn on e5" not in out


def test_no_clause_without_the_facts():
    out = render_rule("R12_blunder", _r12(
        True, line_loss_san=None, line_loss_piece_type=None,
        line_loss_square=None, line_loss_ply=None)) or ""
    assert "fxe5" not in out
