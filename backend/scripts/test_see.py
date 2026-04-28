"""
Lock-in tests for SEE.

Hand-built positions covering the exchange types the fork formula
relies on. Each case names what's on the target square and the
expected SEE outcome.

Usage:
    python scripts/test_see.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess

from services.pattern_confidence.see import (
    static_exchange_eval, forced_exchange_eval,
)


# Each case: (name, fen, target_sq, attacker_color,
#             expected_standard, expected_forced, notes)
# expected_standard — standard SEE with full back-prop clamp
# expected_forced  — forced-exchange variant (no step-0 clamp)
CASES = [
    # ── Free piece — no defenders ──
    (
        "free pawn capture (no defenders)",
        "4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1",
        chess.D5, chess.WHITE, 100, 100,
        "exd5 wins a pawn for free",
    ),
    (
        "free knight capture (no defenders)",
        "4k3/8/8/3n4/8/2N5/8/4K3 w - - 0 1",
        chess.D5, chess.WHITE, 300, 300,
        "Nxd5 wins a knight for free",
    ),

    # ── Even trade — defender of equal value ──
    (
        "knight for knight: defended by knight",
        "4k3/8/5n2/3n4/8/2N5/8/4K3 w - - 0 1",
        chess.D5, chess.WHITE, 0, 0,
        "Nxd5 Nxd5 — even trade in both interpretations",
    ),

    # ── Bad trade — attacker more valuable ──
    # KEY DIFFERENCE between standard and forced:
    #   Standard says "black wouldn't take — outcome is 0"
    #   Forced says "if black is committed to take, outcome is -800"
    (
        "queen takes pawn defended by knight",
        "3qk3/8/8/3P4/8/2N5/8/4K3 b - - 0 1",
        chess.D5, chess.BLACK, 0, -800,
        "standard=0 (black refuses); forced=-800 (committed Qxd5 Nxd5)",
    ),

    # ── Good trade — pawn takes knight defended by pawn ──
    (
        "pawn takes knight defended by pawn",
        "4k3/8/4p3/3n4/4P3/8/8/4K3 w - - 0 1",
        chess.D5, chess.WHITE, 200, 200,
        "exd5 exd5 — white wins minor for pawn (+200)",
    ),

    # ── Empty square ──
    (
        "empty target square",
        "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
        chess.D4, chess.WHITE, 0, 0,
        "no piece on target = no exchange",
    ),

    # ── Multiple attackers and defenders ──
    (
        "rook-supported pawn capture",
        "4k3/8/4p3/3n4/4P3/8/8/3RK3 w - - 0 1",
        chess.D5, chess.WHITE, 300, 300,
        "exd5 exd5 Rxd5 — white nets a knight",
    ),
]


def main() -> int:
    print("SEE lock-in tests (standard + forced)")
    print("=" * 60)
    passed = 0
    failed = 0
    for i, (name, fen, sq, color, exp_std, exp_forced, notes) in enumerate(CASES, 1):
        try:
            board = chess.Board(fen)
            std = static_exchange_eval(board, sq, color)
            forced = forced_exchange_eval(board, sq, color)
        except Exception as e:
            print(f"  [{i}] ERROR — {name}: {e}")
            failed += 1
            continue
        std_ok = std == exp_std
        forced_ok = forced == exp_forced
        ok = std_ok and forced_ok
        status = "PASS" if ok else "FAIL"
        print(f"  [{i}] {status} — {name}")
        print(f"        standard: got {std:>5d}  expected {exp_std:>5d}  {'OK' if std_ok else 'FAIL'}")
        print(f"        forced:   got {forced:>5d}  expected {exp_forced:>5d}  {'OK' if forced_ok else 'FAIL'}")
        if not ok:
            print(f"        notes:    {notes}")
            failed += 1
        else:
            passed += 1
    print()
    print(f"Total: {passed + failed}  Passed: {passed}  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
