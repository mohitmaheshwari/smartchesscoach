"""
sub_variation_check.py — guard that the curriculum move tree still resolves the
named sub-variations the 600-1500 audience actually hits.

Sibling to opening_sync_check.py. The 2026-06-10 audit (71a7cfd0) deepened the
Sicilian / Caro-Kann trees with the anti-lines the main `setup_order` can't see
(Alapin 2.c3, Smith-Morra 2.d4, Bowdler 2.Bc4, Caro-Kann Advance 3.e5) — those
are the OPPONENT's choice, not the learner's setup. `match_sub_variation` walks
the authored tree and labels the sub-line directly from the moves so the
progress page can show "Alapin", not just "Sicilian".

This check asserts each known line resolves to a sensible sub-variation name and
that shallow / off-book lines stay silent (no false sub-line). Reads only the
canonical curriculum JSON; writes nothing.

Exit 0 = all expected lines resolve, 1 = a regression (a line stopped matching
or a too-shallow line started claiming a sub-variation).

Usage:  python -m scripts.sub_variation_check       (from backend/, or in-container)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.opening_lookup import match_sub_variation  # noqa: E402

# (label, full SAN move list, substring the resolved sub-variation must contain).
# These are the exact move orders real games in these lines run through.
EXPECT_MATCH = [
    ("Sicilian Alapin (2.c3)",   ["e4", "c5", "c3", "d5", "exd5"],                     "Alapin"),
    ("Sicilian Smith-Morra",     ["e4", "c5", "d4", "cxd4", "c3"],                     "Smith-Morra"),
    ("Sicilian Bowdler (2.Bc4)", ["e4", "c5", "Bc4", "e6"],                            "Bowdler"),
    ("Open Sicilian / Najdorf",  ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4",
                                  "Nf6", "Nc3", "a6"],                                 "Open Sicilian"),
    ("Caro-Kann Advance (3.e5)", ["e4", "c6", "d4", "d5", "e5"],                       "Advance"),
    ("Caro-Kann Exchange",       ["e4", "c6", "d4", "d5", "exd5", "cxd5"],             "Exchange"),
    ("Caro-Kann Classical",      ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4",
                                  "Bf5"],                                              "Classical"),
    ("Italian main line",        ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3",
                                  "Nf6", "d4"],                                        "Italian"),
]

# Lines that must NOT claim a sub-variation (too shallow to be sure).
EXPECT_SILENT = [
    ("bare 1.e4 c5",  ["e4", "c5"]),
    ("bare 1.e4 c6",  ["e4", "c6"]),
    ("bare 1.e4",     ["e4"]),
]


def run() -> int:
    failures = []

    print("=== sub-variations that MUST resolve ===")
    for label, moves, needle in EXPECT_MATCH:
        sub = match_sub_variation(moves)
        name = sub["name"] if sub else None
        ok = bool(sub) and needle.lower() in (name or "").lower()
        flag = "OK " if ok else "FAIL"
        depth = sub["depth"] if sub else 0
        print(f"  [{flag}] {label:28s} -> {name!r} (depth {depth})")
        if not ok:
            failures.append(f"{label}: expected a name containing {needle!r}, got {name!r}")

    print("\n=== shallow / off-book lines that MUST stay silent ===")
    for label, moves in EXPECT_SILENT:
        sub = match_sub_variation(moves)
        ok = sub is None
        flag = "OK " if ok else "FAIL"
        print(f"  [{flag}] {label:28s} -> {sub}")
        if not ok:
            failures.append(f"{label}: expected None (too shallow), got {sub}")

    if failures:
        print("\n=== REGRESSIONS ===")
        for f in failures:
            print("  -", f)
        print(f"\nFAIL: {len(failures)} sub-variation regression(s).")
        return 1

    print("\nPASS: all expected sub-variations resolve; shallow lines silent.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
