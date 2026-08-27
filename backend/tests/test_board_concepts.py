"""Tests for the named board-concept detectors.

Every position here is hand-constructed so the chess answer is checkable by eye,
and each carries the reasoning in a comment. These detectors exist to replace
generic buckets with real names, so a wrong name is worse than no name: the
tests lean hard on the NEGATIVE cases (concept absent, concept ambiguous).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess  # noqa: E402

from services.board_concepts import (  # noqa: E402
    _passed_pawns,
    _steps_to_promote,
    back_rank_weakness,
    detect_all,
    opposition,
    pawn_race,
    rule_of_the_square,
    trapped_pieces,
)

failures = []


def check(name, cond):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}")
        failures.append(name)


print("board_concepts")

# ── passed pawns ─────────────────────────────────────────────────────────────
# White pawn e5, black pawns a7/b7 only: e5 is passed.
b = chess.Board("4k3/pp6/8/4P3/8/8/8/4K3 w - - 0 1")
check("passed pawn found", [chess.square_name(s) for s in _passed_pawns(b, chess.WHITE)] == ["e5"])
# Black pawn on d6 stops it being passed (adjacent file, ahead of the pawn).
b2 = chess.Board("4k3/pp6/3p4/4P3/8/8/8/4K3 w - - 0 1")
check("blocked by adjacent pawn is not passed", _passed_pawns(b2, chess.WHITE) == [])

check("steps counts the double step", _steps_to_promote(chess.E2, chess.WHITE) == 5)
check("steps from mid-board", _steps_to_promote(chess.E5, chess.WHITE) == 3)
check("steps for black", _steps_to_promote(chess.E4, chess.BLACK) == 3)

# ── rule of the square ───────────────────────────────────────────────────────
# White pawn h5, black king a8 — miles away, cannot catch it.
far = chess.Board("k7/8/8/7P/8/8/8/4K3 w - - 0 1")
r = rule_of_the_square(far)
check("uncatchable pawn detected", r is not None and r["pawn_square"] == "h5")
check("names the promotion square", r is not None and r["promotion_square"] == "h8")
check("reports the king cannot catch", r is not None and r["king_catches"] is False)

# Same pawn, king on g7 — comfortably inside the square.
near = chess.Board("8/6k1/8/7P/8/8/8/4K3 w - - 0 1")
check("catchable pawn is NOT reported", rule_of_the_square(near) is None)

# A piece standing IN FRONT of the pawn (h6, not h4 - white pawns go up):
# the rule does not apply to a pawn that cannot run.
blocked = chess.Board("k7/8/7n/7P/8/8/8/4K3 w - - 0 1")
check("blocked path is not a rule-of-square case", rule_of_the_square(blocked) is None)

# ── opposition ───────────────────────────────────────────────────────────────
# Kings e4 and e6, one square between, White to move -> BLACK holds it.
opp = chess.Board("8/8/4k3/8/4K3/8/8/8 w - - 0 1")
o = opposition(opp)
check("direct opposition detected", o is not None and o["kind"] == "file")
check("side not to move holds it", o is not None and o["held_by"] == "black")

# Same position with Black to move -> WHITE holds it.
opp_b = chess.Board("8/8/4k3/8/4K3/8/8/8 b - - 0 1")
o2 = opposition(opp_b)
check("opposition flips with the turn", o2 is not None and o2["held_by"] == "white")

# Kings adjacent-but-offset: not opposition.
off = chess.Board("8/8/5k2/8/4K3/8/8/8 w - - 0 1")
check("non-aligned kings are not opposition", opposition(off) is None)

# Diagonal opposition: kings c4 and e6.
diag = chess.Board("8/8/4k3/8/2K5/8/8/8 w - - 0 1")
d = opposition(diag)
check("diagonal opposition detected", d is not None and d["kind"] == "diagonal")

# ── pawn race ────────────────────────────────────────────────────────────────
# White h-pawn and black a-pawn, both kings too far to catch either.
# (Kings must also stay off the promotion files, or they block the path.)
race = chess.Board("8/7P/4k3/8/8/3K4/p7/8 w - - 0 1")
pr = pawn_race(race)
check("race detected with both sides passed", pr is not None)
if pr:
    check("race names both pawns", pr["white_pawn"] == "h7" and pr["black_pawn"] == "a2")
    check("race picks a leader", pr["leader"] in ("white", "black", "level"))

# Only one side has a passer -> not a race.
solo = chess.Board("8/7P/8/8/8/8/8/K6k w - - 0 1")
check("one passer is not a race", pawn_race(solo) is None)

# ── back rank ────────────────────────────────────────────────────────────────
# White king g1 boxed in by f2/g2/h2, black rook on a1 bearing down.
br_pos = chess.Board("6k1/8/8/8/8/8/5PPP/r5K1 w - - 0 1")
br = back_rank_weakness(br_pos, chess.WHITE)
check("back rank weakness detected", br is not None)
if br:
    check("counts the blocking pawns", br["pawns_blocking"] == 3)
    check("marks it exploitable", br["exploitable"] is True)

# Give the king luft with h3: no longer a back-rank case.
luft = chess.Board("6k1/8/8/8/8/7P/5PP1/r5K1 w - - 0 1")
check("luft removes the weakness", back_rank_weakness(luft, chess.WHITE) is None)

# King boxed in but no heavy piece anywhere: weakness exists, not exploitable.
quiet = chess.Board("6k1/8/8/8/8/8/5PPP/6K1 w - - 0 1")
q = back_rank_weakness(quiet, chess.WHITE)
check("unexploitable weakness is reported but flagged", q is not None and q["exploitable"] is False)

# ── trapped piece ────────────────────────────────────────────────────────────
# Black knight a8, attacked by the rook on h8. Both its squares (b6, c7) sit on
# the a5 bishop's diagonal, so it has nowhere to go. Classic trapped knight.
trap = chess.Board("n6R/8/8/B3k3/8/8/8/4K3 b - - 0 1")
tp = trapped_pieces(trap, chess.BLACK)
check("trapped knight found", any(t["square"] == "a8" for t in tp))
if tp:
    check("names the piece", tp[0]["piece"] == "knight")
    check("reports what it costs", tp[0]["cost_cp"] >= 300)

# Same knight, same covered squares - but nothing is attacking it. Restricted is
# not trapped, and calling it trapped would be a false name.
safe = chess.Board("n7/8/8/B3k3/8/8/8/4K3 b - - 0 1")
check("unattacked piece is not trapped", trapped_pieces(safe, chess.BLACK) == [])

# ── detect_all ───────────────────────────────────────────────────────────────
allc = detect_all(far)
check("detect_all surfaces rule_of_square", "rule_of_square" in allc)
check("detect_all never throws on the start position", isinstance(detect_all(chess.Board()), dict))
check("start position has no concepts", detect_all(chess.Board()) == {})

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all board_concepts tests passed")
