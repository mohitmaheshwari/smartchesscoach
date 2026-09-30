"""Self-test for the structural why-classifier.

The classifier itself moved into `services/caption_why_heuristics.py` on
2026-09-30, so that module is genuinely the one definition of "does this
caption have a why" rather than nominally so — it used to say that while the
better classifier sat here, unimported by anything, and the review queue used
the weaker keyword scan in the same file.

This file keeps only the case table, which is a real test of the relocated
function. Run it directly, or via tests/test_caption_why_class_cases.py.
"""
from __future__ import annotations

from services.caption_why_heuristics import (  # noqa: F401  (re-exported)
    ALT_BOUNDARY_RE,
    CONSEQUENCE_RE,
    PRINCIPLE_RE,
    SAN_RE,
    classify_caption_why,
)

# (caption, played_san, best_san, expected_class)
CASES = [
    ("You played Qf6; Nxd3+ was stronger — it trades his bishop.",
     "Qf6", "Nxd3+", "ALT_WHY_ONLY"),
    ("Qd7 is a mistake — it drops the pawn after Bxe5. Qxc4 was better — it wins a pawn.",
     "Qd7", "Qxc4", "PLAYED_WHY"),
    ("Bf6 is a mistake. f5 was better.",
     "Bf6", "f5", "NO_WHY"),
    ("Kf1 loses to Qxd3+. Ke2 was better.",
     "Kf1", "Ke2", "PLAYED_WHY"),
    ("Nd4 is a mistake. e4 was better — it attacks the knight on f3.",
     "Nd4", "e4", "ALT_WHY_ONLY"),
    ("Bxf7+ leaves your bishop undefended — opponent recaptures on f7. "
     "Be3 was better — it develops a piece.",
     "Bxf7+", "Be3", "PLAYED_WHY"),
    ("Nxe5 is a mistake. dxe5 was better. Look for the move that creates two threats.",
     "Nxe5", "dxe5", "NO_WHY"),
    # Regression guards for the two cases the keyword scan gets wrong. Both are
    # real captions pulled from the corpus on 2026-09-30.
    ("Kf1 runs into Qxd3+, and the line costs you material; instead Ke2 was "
     "stronger whereas Kf1 hands material away. Before any quiet move, check "
     "that it doesn't run into a tactic that loses a piece.",
     "Kf1", "Ke2", "PLAYED_WHY"),
    ("Ke8 allows mate next move. Before moving, calculate every enemy check "
     "to the end.",
     "Ke8", "Kc7", "PLAYED_WHY"),
    # A universal principle is not a why (Mohit, 2026-09-30).
    ("Opponent's Qxf2 is a serious mistake.",
     "Qxf2", "Kxf2", "NO_WHY"),
]


def run() -> int:
    ok = 0
    for cap, played, best, want in CASES:
        got = classify_caption_why(cap, played, best)["why_class"]
        if got == want:
            ok += 1
        print("%s want=%-13s got=%-13s %s"
              % ("ok " if got == want else "FAIL", want, got, cap[:70]))
    print("%d/%d" % (ok, len(CASES)))
    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(run())
