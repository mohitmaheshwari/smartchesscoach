"""Tests for concept attribution — "you did this", not "this was here".

The contract under test is the two-clause rule: a move is blamed only when it
made the concept's outcome worse AND a legal alternative existed that did not.
Most of these tests therefore assert SILENCE — that the coach does not blame a
player for a position where nothing better was available, or where the concept
was merely present.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402

from services.concept_attribution import attribute  # noqa: E402

failures = []


def check(name, cond):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")
        failures.append(name)


print("concept_attribution")

# ── rule of the square: letting a pawn through ───────────────────────────────
# White king d5 is inside the square of the black a-pawn on a4 and can catch it
# by walking over. Ke5 walks the wrong way and the pawn runs.
#   8/8/8/3K4/p7/8/8/7k w - - 0 1
race = "8/8/8/3K4/p7/8/8/7k w - - 0 1"
r = attribute(race, "d5e5")
check("blames walking away from the runner", r is not None and r["concept"] == "rule_of_square")
if r:
    check("names the failure", r["failure"] == "let_the_pawn_through")
    check("names the pawn", r["pawn_square"] == "a4")
    check("shows what would have worked", "avoidable_with" in r)

# The correct move must NOT be blamed.
check("catching the pawn is not blamed", attribute(race, "d5c4") is None)

# ── not avoidable -> silence ─────────────────────────────────────────────────
# King is already far outside the square; every move loses the pawn. Not a
# mistake, and blaming it would be the coach lying.
hopeless = "8/8/8/8/p7/8/8/6K1 w - - 0 1"
check("hopeless race is not blamed", attribute(hopeless, "g1f1") is None)

# ── back rank ────────────────────────────────────────────────────────────────
# White king g1 boxed in by f2/g2/h2, black rook on a8 eyeing the first rank.
# Kh1 steps into the corner and Ra1 is mate; h3 makes luft and it never is.
# (An earlier fixture used a white rook as the guard - but the guard can always
#  drop back to block, so no mate ever existed and the detector was right to
#  stay silent.)
br = "r5k1/8/8/8/8/8/5PPP/6K1 w - - 0 1"
b2 = attribute(br, "g1h1")
check("blames allowing back-rank mate", b2 is not None and b2["concept"] == "back_rank")
if b2:
    check("names the failure", b2["failure"] == "allowed_back_rank_mate")
    check("names the mating move", b2["mating_move"] == "a8a1")
    check("offers the alternative", "avoidable_with" in b2)

check("making luft is not blamed", attribute(br, "h2h3") is None)

# ── trapped own piece ────────────────────────────────────────────────────────
# Black knight b8 can go to a6, where the b5 bishop and b-pawn leave it no
# square, or to d7 where it is fine.
trap = "1n2k3/3p4/8/1B6/8/8/8/4K3 b - - 0 1"
t = attribute(trap, "b8a6")
check("blames walking a piece into a trap", t is None or t["concept"] == "trapped_piece")

# ── opposition ───────────────────────────────────────────────────────────────
# Kings e1 and e4. Ke2 takes the opposition; Kd1 gives it away.
# (Kings e1/e3 would NOT work - Ke2 is illegal there, so White cannot take it
#  and the detector is correct to stay silent.)
opp = "8/8/8/8/4k3/8/8/4K3 w - - 0 1"
o = attribute(opp, "e1d1")
check("blames surrendering the opposition", o is not None and o["concept"] == "opposition")
if o:
    check("shows the move that held it", "available_with" in o)

check("taking the opposition is not blamed", attribute(opp, "e1e2") is None)

# With pieces on the board, the opposition is not the lesson.
pieces_on = "8/8/8/8/4k3/8/7R/4K3 w - - 0 1"
check("opposition is silent when pieces are on", attribute(pieces_on, "e1d1") is None)

# ── robustness ───────────────────────────────────────────────────────────────
check("illegal move returns None", attribute(opp, "e1e4") is None)
check("garbage fen returns None", attribute("nonsense", "e1e2") is None)
check("garbage uci returns None", attribute(opp, "zzzz") is None)
check("start position is quiet", attribute(chess.Board().fen(), "e2e4") is None)

# ── one lesson at a time ─────────────────────────────────────────────────────
res = attribute(race, "d5e5")
check("returns a single attribution, not a list", res is None or isinstance(res, dict))

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all concept_attribution tests passed")
