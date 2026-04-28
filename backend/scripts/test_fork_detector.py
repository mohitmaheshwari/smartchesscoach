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
from services.pattern_confidence.fork import evaluate_fork


# Each case: (name, fen, move_uci, should_be_fork, expected_tier, notes)
# expected_tier: "HIGH" / "MEDIUM" / "LOW" / None (don't check tier)
# fen is the position BEFORE the move.
CASES = [
    # ── REAL FORKS (should detect) ──
    (
        "Nf7 forks Q and R, defended by bishop",
        "3qk2r/8/7N/8/2B5/8/8/6K1 w - - 0 1",
        "h6f7", True, "HIGH", "clean fork: defended forker, two valuable targets",
    ),
    (
        "queen+rook battery: Qe4 attacks K and R via diagonal",
        "r3k3/8/8/8/8/8/8/4K2Q w - - 0 1",
        "h1e4", True, None, "queen check + skewer-like attack on rook",
    ),
    (
        "knight fork on undefended pieces (forker safe by no attacker)",
        "4k3/8/1q3r2/8/8/2N5/8/4K3 w - - 0 1",
        "c3d5", True, "HIGH", "Nd5 forks queen and rook from a safe square",
    ),

    # ── FAKE FORKS (should be rejected) ──
    (
        "knight 'forks' knight (mutual capture, not a fork)",
        "1n2k3/8/1n3n2/3N4/8/8/8/4K3 w - - 0 1",
        "d5f6", False, "LOW", "Nxf6 leaves no valid fork shape from f6",
    ),
    (
        "queen 'forks' two pawns (low value targets)",
        "r3k3/p7/8/4p3/3Q4/8/8/4K3 w - - 0 1",
        "d4d5", False, "LOW", "pawn-only targets fail the value bar",
    ),
    (
        "knight 'fork' but forker hangs to pawn, no check, no defender",
        "3qk3/5p2/5r2/8/3N4/8/8/4K3 w - - 0 1",
        "d4e6", False, "LOW", "forker hangs to pawn for free; targets don't compensate",
    ),

    # ── EDGE CASES ──
    (
        "fork square attacked but defended (forker safe)",
        "3qk2r/5p2/7N/8/2B5/8/8/6K1 w - - 0 1",
        "h6f7", True, "HIGH", "forker attacked by pawn but defended by bishop",
    ),
]


def _check(case_idx: int, name: str, fen: str, move_uci: str,
           expected_fork: bool, expected_tier, notes: str) -> bool:
    if move_uci is None:
        print(f"  [{case_idx}] SKIP — {name}")
        return True
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            print(f"  [{case_idx}] SETUP-ERR — {name}: move {move_uci} illegal")
            return False
    except Exception as e:
        print(f"  [{case_idx}] SETUP-ERR — {name}: {e}")
        return False

    # Layer 1: binary detector (existing, unchanged)
    binary = _immediate_fork(board, move)
    binary_detected = binary is not None and binary.get("type") in (
        "fork", "check_and_attack"
    )
    binary_ok = binary_detected == expected_fork

    # Layer 2: confidence-aware scorer (new)
    score = evaluate_fork(board, move)
    scored_detected = bool(score.get("detected"))
    scored_tier_ok = (expected_tier is None) or (score.get("tier") == expected_tier)

    # The binary detector and the scorer should agree on detected/not.
    detected_agree = binary_detected == scored_detected
    detect_ok = scored_detected == expected_fork

    ok = binary_ok and detect_ok and scored_tier_ok and detected_agree

    status = "PASS" if ok else "FAIL"
    print(f"  [{case_idx}] {status} — {name}")
    print(f"        binary: detected={binary_detected}  expected={expected_fork}")
    print(f"        scored: detected={scored_detected}  tier={score.get('tier')}  "
          f"conf={score.get('confidence')}  expected_tier={expected_tier}")
    if score.get("reason"):
        print(f"        reason: {score['reason']}")
    if not ok:
        print(f"        notes:  {notes}")
    return ok


def main() -> int:
    print("Fork detector lock-in tests")
    print("=" * 60)
    passed = 0
    failed = 0
    for i, (name, fen, move_uci, expected, expected_tier, notes) in enumerate(CASES, 1):
        ok = _check(i, name, fen, move_uci, expected, expected_tier, notes)
        if ok:
            passed += 1
        else:
            failed += 1
    print()
    print(f"Total: {passed + failed}  Passed: {passed}  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
