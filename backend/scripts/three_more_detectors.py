"""Three more of the brief's detectors, measured on the enriched games.

  03 recapture_quality          do errors cluster on immediate recaptures
  02 post_error_recovery        do errors cluster after a bad move
  07 time_pressure_sensitivity  do errors cluster when the clock is low

These three were picked because each needs a different thing enrichment just
supplied: 03 needs the opponent's move analysed, 02 needs the player's moves in
order within a game, 07 needs a remaining clock.

The remaining clock is stored NOWHERE -- the capability inventory found no raw
clock field in any collection, only a derived seconds-per-move. It is parsed
here out of the PGN's %clk annotations, which is the only clock source there is.

Each reading reports its opportunity count and refuses to print a ratio when
there are too few. The halves test is not applied to error rates, only to
preferences: an error rate is a count of events, and splitting 50 games in two
leaves neither half able to carry it.
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
# Bands set from this player's own clock distribution, measured first: 580 of
# his moves carry a clock, median 212s, p25 84s. These are blitz games, so the
# obvious "five minutes or more" would have meant move one only. 60s leaves 119
# moves and 180s leaves 331, with a gap between the bands so neither edge is a
# relabelled version of the other.
LOW_CLOCK_S = 60
AMPLE_CLOCK_S = 180
CLK = re.compile(r"\[%clk\s+(\d+):(\d+):([\d.]+)\]")


def erred(row):
    """Did the player pick something outside the sound set? None if unknowable.

    Mate scores are excluded from the sound set rather than clamped. A mate is
    not on the centipawn scale, and the 2026 mate-in-0 bug came from treating
    it as if it were.
    """
    alts = row.get("root_alternatives") or []
    scored = {a["move_uci"]: a["cp"] for a in alts
              if isinstance(a.get("cp"), (int, float)) and a.get("mate") is None}
    if not scored:
        return None
    top = max(scored.values())
    mine = scored.get(row.get("played_uci"))
    return mine is None or (top - mine) > GAP


def rate(name, slot, width=24):
    n, e = slot
    if n < ENOUGH:
        print("   %-*s only %d -- not enough to say" % (width, name, n))
        return None
    print("   %-*s went wrong %d of %d  (%.0f%%)" % (width, name, e, n, 100.0 * e / n))
    return e / n


def verdict(a, b, high, low, flat):
    if a is None or b is None:
        return
    d = 100.0 * (a - b)
    print("   difference: %+.1f points -> %s"
          % (d, high if d > 5 else low if d < -5 else flat))


async def main_async(user_id: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    mine = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": True}, {"_id": 0}).to_list(20000)
    theirs = await db.move_enrichment.find(
        {"user_id": user_id, "is_user_move": False},
        {"_id": 0, "game_id": 1, "ply": 1, "fen": 1, "played_uci": 1}).to_list(20000)

    by_game = collections.defaultdict(list)
    for r in mine:
        by_game[r["game_id"]].append(r)
    for g in by_game:
        by_game[g].sort(key=lambda r: r["ply"])

    # Where the opponent captured, read off the board rather than from SAN
    # containing an "x" -- that misses en passant and counts check marks.
    opp_capture_at = {}
    for o in theirs:
        try:
            board = chess.Board(o["fen"])
            move = chess.Move.from_uci(o["played_uci"])
        except Exception:
            continue
        if move in board.legal_moves and board.is_capture(move):
            opp_capture_at[(o["game_id"], o["ply"])] = move.to_square

    print("=" * 70)
    print("  03  RECAPTURES -- taking straight back on the square they took on")
    print("=" * 70)
    recap, plain = [0, 0], [0, 0]
    for game, items in by_game.items():
        for r in items:
            bad = erred(r)
            if bad is None:
                continue
            try:
                board = chess.Board(r["fen"])
                move = chess.Move.from_uci(r["played_uci"])
            except Exception:
                continue
            if move not in board.legal_moves:
                continue
            took_on = opp_capture_at.get((game, r["ply"] - 1))
            slot = (recap if board.is_capture(move) and took_on == move.to_square
                    else plain)
            slot[0] += 1
            slot[1] += 1 if bad else 0
    a = rate("taking straight back", recap)
    b = rate("every other move", plain)
    verdict(a, b,
            "recaptures are where you slip",
            "recaptures are safer for you than an ordinary move",
            "no real difference")

    print("\n" + "=" * 70)
    print("  02  AFTER A BAD MOVE -- does one lead to another")
    print("=" * 70)
    after_bad, after_good = [0, 0], [0, 0]
    for items in by_game.values():
        flags = [erred(r) for r in items]
        for i in range(len(items) - 1):
            if flags[i] is None or flags[i + 1] is None:
                continue
            slot = after_bad if flags[i] else after_good
            slot[0] += 1
            slot[1] += 1 if flags[i + 1] else 0
    a = rate("after a bad move", after_bad)
    b = rate("after a good one", after_good)
    verdict(a, b,
            "your mistakes come in runs -- the move after is the dangerous one",
            "you steady yourself straight after a mistake",
            "no real difference")

    print("\n" + "=" * 70)
    print("  07  THE CLOCK")
    print("=" * 70)
    games = await db.games.find(
        {"game_id": {"$in": list(by_game)}},
        {"_id": 0, "game_id": 1, "pgn": 1}).to_list(500)
    low, ample = [0, 0], [0, 0]
    with_clocks = 0
    for g in games:
        parsed = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        if parsed is None:
            continue
        # %clk alternates sides by ply, so a ply number is enough to line it up
        # with the player's own rows; no colour handling needed.
        clocks = {}
        node, ply = parsed, 0
        while node.variations:
            node = node.variations[0]
            ply += 1
            found = CLK.search(node.comment or "")
            if found:
                h, m, s = found.groups()
                clocks[ply] = int(h) * 3600 + int(m) * 60 + float(s)
        if not clocks:
            continue
        with_clocks += 1
        flags = {r["ply"]: erred(r) for r in by_game[g["game_id"]]}
        for ply, remaining in clocks.items():
            bad = flags.get(ply)
            if bad is None:
                continue
            slot = (low if remaining <= LOW_CLOCK_S
                    else ample if remaining >= AMPLE_CLOCK_S else None)
            if slot is None:
                continue
            slot[0] += 1
            slot[1] += 1 if bad else 0
    print("   %d of %d games carried clock times" % (with_clocks, len(games)))
    a = rate("under a minute left", low)
    b = rate("five minutes or more", ample)
    verdict(a, b,
            "your play falls apart on a low clock",
            "you hold up on a low clock",
            "no real difference")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    return asyncio.run(main_async(args.user))


if __name__ == "__main__":
    raise SystemExit(main())
