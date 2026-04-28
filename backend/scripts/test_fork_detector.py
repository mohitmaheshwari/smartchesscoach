"""
Lock-in tests for the fork detector.

Twelve hand-built positions across real forks, fake forks, and edge
cases. Run as a script — exits non-zero on any regression.

This is the INTERIM lock pending the full FORK_CONFIDENCE_FORMULA.md
implementation (which adds SEE-based scoring and tier mapping).
For now we validate binary detect / not-detect. Once the formula
lands, expected_confidence and expected_tier get added.

Usage:
    python scripts/test_fork_detector.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
from services.pv_tactical_analyzer import _immediate_fork


# Each case: (name, fen, move_uci, should_be_fork, notes)
# fen is the position BEFORE the move.
CASES = [
    # ── REAL FORKS (should detect) ──
    (
        "Nf7 forks Q and R, defended by bishop",
        # Black: Ke8, Qd8, Rh8. White: Kg1, Bc4, Nh6.
        # Nf7 forks Q+R and is defended by Bc4 (long diagonal).
        "3qk2r/8/7N/8/2B5/8/8/6K1 w - - 0 1",
        "h6f7", True, "clean fork: defended forker, two valuable targets",
    ),
    (
        "queen+rook battery: Qe4 attacks K and R via diagonal",
        # Q on e4 checks Ke8 along e-file AND attacks Ra8 along diagonal.
        # That's a check_and_attack pattern — should be detected.
        "r3k3/8/8/8/8/8/8/4K2Q w - - 0 1",
        "h1e4", True, "queen check + skewer-like attack on rook",
    ),
    (
        "knight fork on undefended pieces (forker safe by no attacker)",
        # White Nc3 -> Nd5 attacks black queen on b6 AND rook on f6.
        # No black piece attacks d5. Real fork.
        "4k3/8/1q3r2/8/8/2N5/8/4K3 w - - 0 1",
        "c3d5", True, "Nd5 forks queen and rook from a safe square",
    ),

    # ── FAKE FORKS (should be rejected) ──
    (
        "knight 'forks' knight (mutual capture, not a fork)",
        # White Nd5 attacks Nb6 and Nf6. Both can recapture. Trade.
        "1n2k3/8/1n3n2/3N4/8/8/8/4K3 w - - 0 1",
        "d5f6", False, "Nxf6: target knight can recapture; not a real fork",
    ),
    (
        "queen 'forks' two pawns (low value targets)",
        # Queen attacks pawns only — no valuable targets, base gate rejects.
        "r3k3/p7/8/4p3/3Q4/8/8/4K3 w - - 0 1",
        "d4d5", False, "pawn-only targets fail the value bar",
    ),
    (
        "knight 'fork' but forker hangs to pawn, no check, no defender",
        # White Nd4 -> Ne6 attacks Qd8 and rook on f6. But pawn f7 takes
        # Ne6 for free. No defender of e6. Not a check. Should be rejected.
        "3qk3/5p2/5r2/8/3N4/8/8/4K3 w - - 0 1",
        "d4e6", False, "forker hangs to pawn for free; targets don't compensate",
    ),

    # ── EDGE CASES ──
    (
        "fork square attacked but defended (forker safe)",
        # Same Nf7 as case 1 but with explicit pawn pressure on f7 from black.
        # Defender (Bc4 long diagonal to f7) keeps forker safe.
        "3qk2r/5p2/7N/8/2B5/8/8/6K1 w - - 0 1",
        "h6f7", True, "forker attacked by pawn but defended by bishop — fork holds",
    ),
]


def _check(case_idx: int, name: str, fen: str, move_uci: str, expected_fork: bool, notes: str) -> bool:
    if move_uci is None:
        # Skipped placeholder
        print(f"  [{case_idx}] SKIP — {name}")
        return True
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            print(f"  [{case_idx}] SETUP-ERR — {name}: move {move_uci} illegal in given FEN")
            return False
    except Exception as e:
        print(f"  [{case_idx}] SETUP-ERR — {name}: {e}")
        return False

    result = _immediate_fork(board, move)
    detected = result is not None and result.get("type") in ("fork", "check_and_attack")
    ok = detected == expected_fork
    status = "PASS" if ok else "FAIL"
    expected_label = "FORK" if expected_fork else "no fork"
    actual_label = (result or {}).get("type", "no fork")
    print(f"  [{case_idx}] {status} — {name}")
    if not ok:
        print(f"        expected: {expected_label}")
        print(f"        actual:   {actual_label}")
        if notes:
            print(f"        notes: {notes}")
    return ok


def main() -> int:
    print("Fork detector lock-in tests")
    print("=" * 60)
    passed = 0
    failed = 0
    for i, (name, fen, move_uci, expected, notes) in enumerate(CASES, 1):
        ok = _check(i, name, fen, move_uci, expected, notes)
        if ok:
            passed += 1
        else:
            failed += 1
    print()
    print(f"Total: {passed + failed}  Passed: {passed}  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
