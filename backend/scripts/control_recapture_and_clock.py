"""Controls for two of the three readings in three_more_detectors.py.

Both headline numbers have an obvious alternative explanation and neither is
reportable until that explanation is tested.

RECAPTURE (-31 points, 17% against 48%). A recapture is usually the obvious
move, and often the only sound one. A low error rate there may be a fact about
recapture POSITIONS being easy, which is true for every player, rather than
anything about this player. Control: count the sound options in each group, and
re-run restricted to positions where at least two moves were sound, so the
"there was nothing else to play" cases are removed from both sides.

CLOCK (+12 points, 53% against 41%). A low clock arrives late and often in a
worse position, and this player's error rate already measured 48% when lost and
54% when behind against 40% when level. The clock effect may be the position
effect wearing a watch. Control: re-run inside each evaluation state, so the
comparison only ever holds the state fixed.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import io
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess  # noqa: E402
import chess.pgn  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

GAP = 30
ENOUGH = 25
LOW_CLOCK_S = 60
AMPLE_CLOCK_S = 180
CLK = re.compile(r"\[%clk\s+(\d+):(\d+):([\d.]+)\]")


def read(row):
    """(erred, number of sound moves, best cp) -- or None if unknowable."""
    alts = row.get("root_alternatives") or []
    scored = {a["move_uci"]: a["cp"] for a in alts
              if isinstance(a.get("cp"), (int, float)) and a.get("mate") is None}
    if not scored:
        return None
    top = max(scored.values())
    sound = sum(1 for cp in scored.values() if top - cp <= GAP)
    mine = scored.get(row.get("played_uci"))
    return (mine is None or (top - mine) > GAP), sound, top


def state_of(cp):
    if cp >= 200:
        return "winning"
    if cp <= -300:
        return "lost"
    if cp <= -100:
        return "behind"
    return "level"


def show(label, slot, width=22):
    n, e = slot
    if n < ENOUGH:
        print("   %-*s only %d -- not enough to say" % (width, label, n))
        return None
    print("   %-*s %3d of %4d went wrong  (%.0f%%)" % (width, label, e, n, 100.0 * e / n))
    return e / n


async def main_async(user_id: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    mine = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": True}, {"_id": 0}).to_list(20000)
    theirs = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": False},
        {"_id": 0, "game_id": 1, "ply": 1, "fen": 1, "played_uci": 1}).to_list(20000)

    opp_capture_at = {}
    for o in theirs:
        try:
            b = chess.Board(o["fen"])
            m = chess.Move.from_uci(o["played_uci"])
        except Exception:
            continue
        if m in b.legal_moves and b.is_capture(m):
            opp_capture_at[(o["game_id"], o["ply"])] = m.to_square

    # ── control A: is the recapture gap just easy positions ────────────
    print("=" * 70)
    print("  CONTROL A -- are recaptures easy, or is he good at them")
    print("=" * 70)
    groups = {"recapture": [0, 0], "other": [0, 0]}
    choice = {"recapture": [0, 0], "other": [0, 0]}   # [positions, sound-move total]
    restricted = {"recapture": [0, 0], "other": [0, 0]}
    forced = {"recapture": 0, "other": 0}
    for r in mine:
        got = read(r)
        if got is None:
            continue
        bad, sound, _ = got
        try:
            b = chess.Board(r["fen"])
            m = chess.Move.from_uci(r["played_uci"])
        except Exception:
            continue
        if m not in b.legal_moves:
            continue
        took = opp_capture_at.get((r["game_id"], r["ply"] - 1))
        key = ("recapture" if b.is_capture(m) and took is not None
               and took == m.to_square else "other")
        groups[key][0] += 1
        groups[key][1] += 1 if bad else 0
        choice[key][0] += 1
        choice[key][1] += sound
        if sound == 1:
            forced[key] += 1
        else:
            restricted[key][0] += 1
            restricted[key][1] += 1 if bad else 0

    for key in ("recapture", "other"):
        n, tot = choice[key]
        print("   %-10s positions=%-5d sound moves on average %.2f,  only one sound move in %d (%.0f%%)"
              % (key, n, tot / max(n, 1), forced[key], 100.0 * forced[key] / max(n, 1)))
    print("\n   all positions")
    a = show("recapture", groups["recapture"])
    b = show("other", groups["other"])
    print("   with the one-sound-move positions removed from both sides")
    ra = show("recapture", restricted["recapture"])
    rb = show("other", restricted["other"])
    if None not in (a, b, ra, rb):
        print("\n   gap before control: %+.1f points" % (100 * (a - b)))
        print("   gap after  control: %+.1f points" % (100 * (ra - rb)))

    # ── control B: does the clock effect survive inside a state ────────
    print("\n" + "=" * 70)
    print("  CONTROL B -- clock, or the position the clock arrives in")
    print("=" * 70)
    by_game = collections.defaultdict(dict)
    for r in mine:
        got = read(r)
        if got is not None:
            by_game[r["game_id"]][r["ply"]] = got
    games = await db.games.find(
        {"game_id": {"$in": list(by_game)}},
        {"_id": 0, "game_id": 1, "pgn": 1}).to_list(500)
    cells = collections.defaultdict(lambda: [0, 0])
    states_seen = collections.Counter()
    for g in games:
        parsed = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        if parsed is None:
            continue
        node, ply = parsed, 0
        while node.variations:
            node = node.variations[0]
            ply += 1
            found = CLK.search(node.comment or "")
            if not found:
                continue
            h, m, s = found.groups()
            remaining = int(h) * 3600 + int(m) * 60 + float(s)
            got = by_game[g["game_id"]].get(ply)
            if got is None:
                continue
            bad, _, top = got
            band = ("low" if remaining <= LOW_CLOCK_S
                    else "ample" if remaining >= AMPLE_CLOCK_S else None)
            if band is None:
                continue
            st = state_of(top)
            states_seen[st] += 1
            cells[(st, band)][0] += 1
            cells[(st, band)][1] += 1 if bad else 0
    for st in ("winning", "level", "behind", "lost"):
        lo = show("%s, low clock" % st, cells[(st, "low")], 26)
        am = show("%s, ample clock" % st, cells[(st, "ample")], 26)
        if lo is not None and am is not None:
            print("      -> %+.1f points inside this state" % (100 * (lo - am)))
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    return asyncio.run(main_async(args.user))


if __name__ == "__main__":
    raise SystemExit(main())
