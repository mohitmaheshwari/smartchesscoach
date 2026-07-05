"""
Regression lock for the simple_hang SEE upgrade (2026-07-05).

_piece_is_hanging_after_move was raised from a raw attacker>defender COUNT
to a proper Static Exchange Evaluation. The count version over-fired ~1/3 of
the time on the live corpus (only 66% of simple_hang events were real hangs
under strict SEE). These tests lock the corrected behaviour — especially the
count-vs-SEE divergence that was the root cause.

Run:  python -m pytest tests/test_piece_safety_hang_see.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.move_observation_deriver import _piece_is_hanging_after_move as hangs


def _count_says_hang(fen: str, uci: str) -> bool:
    """The OLD logic: destination attackers strictly > defenders (no values).
    Kept here only to prove the divergence the SEE fix resolves."""
    import chess
    board = chess.Board(fen)
    mv = chess.Move.from_uci(uci)
    board.push(mv)
    dest = mv.to_square
    opp = board.turn
    return len(list(board.attackers(opp, dest))) > len(list(board.attackers(not opp, dest)))


def test_real_free_hang_is_true():
    # Bxg3 lands the bishop where the h2 pawn recaptures — a real ~2-pawn loss.
    fen = "rn1qk2r/pp3p2/2p1p3/3pPn2/3P1B1b/2P2N2/PP2Q1PP/RN3RK1 b kq - 4 16"
    assert hangs(fen, "h4g3") is True


def test_safe_developing_move_is_false():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    assert hangs(fen, "g1f3") is False


def test_count_overfires_but_see_says_safe():
    """THE root-cause case. d4-d5 pushes a pawn onto d5: defended once (c4),
    'attacked' twice (Qa5, Nf6) — so the COUNT rule (attackers 2 > defenders 1)
    screams hang. SEE knows better: the cheapest attacker (the knight, 300) wins
    only a pawn (100) and is recaptured by cxd5, so no one takes. The push hangs
    nothing."""
    fen = "4k3/8/5n2/q7/2PP4/8/8/6K1 w - - 0 1"
    assert _count_says_hang(fen, "d4d5") is True     # old logic: false positive
    assert hangs(fen, "d4d5") is False               # SEE: correct — not a hang


def test_illegal_or_bad_input_returns_none():
    assert hangs("", "e2e4") is None
    assert hangs("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e5") is None  # illegal


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
