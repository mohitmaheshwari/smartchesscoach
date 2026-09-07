"""A mistake verdict must be earned.

R12 already refuses to assert "X is a mistake" on a user move under 250cp with
no why-clause. The fallback paths never got that rule, so 362 captions in one
user's corpus announced a verdict with no reason attached - 70% of them at
cp 100-199. These cases lock the rule in at the composition boundary, where
every path sees it.
"""
import sys

sys.path.insert(0, "/app/backend")

from services.caption_pipeline import _soften_verdict_without_evidence as soften

CASES = [
    # (caption, mover_is_user, cp_loss, expect)
    # --- softened: verdict asserted, nothing backs it up, modest loss ---
    ("Bf6 is a mistake. f5 was better. When defending in the middlegame, "
     "fix your worst piece first.", True, 100, "soften"),
    ("Qd7 is a mistake. Opponent has developed 4 pieces; you've developed 1 piece.",
     True, 111, "soften"),
    ("Qf5+ is a mistake. Your queen on f5 is out alone.", True, 103, "soften"),

    # --- kept: the caption names a consequence, so the verdict is earned ---
    ("Qd7 is a mistake - it drops the pawn after Bxe5. Qxc4 was better.",
     True, 141, "keep"),
    ("Nd4 is a mistake. e4 was better - it attacks the knight on f3.",
     True, 206, "keep"),
    ("O-O allows Nxc6 forking your queen on d8 and rook on b8.", True, 304, "keep"),

    # --- kept: at or above the bar a real blunder is named even unexplained ---
    ("Rh5 is a major blunder. Qd7 was the stronger move here.", True, 900, "keep"),
    ("Bd5 is a serious mistake. Rhe8 was better.", True, 356, "keep"),
    ("Nb6 is a mistake. Nc3 was the stronger move here.", True, 250, "keep"),

    # --- kept: opponent moves are not the player's verdict to soften ---
    ("Bf6 is a mistake. f5 was better.", False, 100, "keep"),

    # --- untouched: no verdict phrase at all ---
    ("You played Bf4; Ne2 was the stronger move here.", True, 150, "keep"),
]


def run():
    failures = []
    for caption, is_user, cp, expect in CASES:
        out = soften(caption, mover_is_user=is_user, cp_loss=cp)
        got = "soften" if out != caption else "keep"
        ok = got == expect
        if not ok:
            failures.append(caption)
        print("%s %-6s cp=%-4s %s" % ("ok  " if ok else "FAIL", got, cp, out[:76]))
    print("\n%d/%d" % (len(CASES) - len(failures), len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
