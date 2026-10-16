"""The engine's verdict is never softened. The EXPLANATION is what gives way.

REVERSED 2026-10-12. This file used to assert the opposite: that a verdict with
no why-clause attached should be downgraded to "is playable" below 250cp. The
intent was "a mistake verdict must be earned", which sounds right and is not.

Measured over all 838 of Mohit's analysed games: 660 of 4,018 moves at 100cp+
(16.4%) were rendered "is playable" -- real mistakes, described to him as fine.
One of them was "Qb4 is playable -- you moved your queen away from defending
c2", where the caption carries its own evidence and the keyword test simply
missed it. His Rf3 card read "Rf3 is playable" on a 210cp loss for which
Stockfish had already handed us the full refutation, Qe2 Rf1 Rhd8 Rd3 Rxd3.

Mohit: "how can we get the chess wrong, we are completely backed by stockfish
there is no way we can go wrong at all." We never did get the chess wrong. The
engine's number was right in our data every time; this rule overruled it
whenever OUR rules failed to find words, which reports our ignorance to the
player as a fact about the position.

The trust order was inverted and is now explicit: the engine's verdict is the
most certain thing we own and the explanation is the least, so when evidence is
missing the explanation goes and the verdict stays.
"""
import sys

sys.path.insert(0, "/app/backend")

from services.caption_pipeline import _soften_verdict_without_evidence as soften

CASES = [
    # (caption, mover_is_user, cp_loss, expect)
    # --- KEPT, and these three are the reversal. All are 100-111cp, which is
    # the canonical mistake band in services/severity.py. The engine called
    # them mistakes and they are mistakes; the captions are merely thin. A
    # thin explanation is a reason to say less, never a reason to tell the
    # player the move was fine. ---
    ("Bf6 is a mistake. f5 was better. When defending in the middlegame, "
     "fix your worst piece first.", True, 100, "keep"),
    ("Qd7 is a mistake. Opponent has developed 4 pieces; you've developed 1 piece.",
     True, 111, "keep"),
    ("Qf5+ is a mistake. Your queen on f5 is out alone.", True, 103, "keep"),

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
# --- kept: prose captions that DO explain, in words the keyword list
    # cannot see. These were wrongly softened when the rule shipped. ---
    ("Nxf7 is a mistake - you moved your knight away from defending e4. "
     "Bxf7+ was better - it sacrifices your bishop to break open the pawn shield "
     "in front of their king. The attack that follows is worth more than the pawn "
     "you lose. Nxf7 took without the check, so the opponent has time to organise.",
     True, 178, "keep"),
    ("Nxd5 is a mistake, but the light-squared bishop is currently white's worst "
     "piece because the pawn structure blocks its activity. The knight, on the "
     "other hand, controls important central squares and can be rerouted easily. "
     "A better choice is to recapture with the bishop.", True, 39, "keep"),
    ("Your knight on e3 is pinned to your king by the rook on e8. O-O-O is a "
     "mistake. Qb5+ was better - it gives check, forcing your opponent to respond. "
     "Between two reasonable moves, pick the one your opponent has less time to "
     "deal with.", True, 142, "keep"),
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
