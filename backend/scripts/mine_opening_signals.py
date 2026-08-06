"""mine_opening_signals.py — validation pass for two zero-user-cost signals
mined from games ChessGuru already imports:

1. Trap encounters: did this game's early moves match a known trap's
   setup, and if so, did the user (as victim or springer) walk the
   trap_line or deviate? Uses the existing trap_library.py /
   data/traps.json -- no new content authored here.
2. Opening-phase move timing: seconds spent per move for the user's own
   first ~10 moves, parsed from the PGN's %clk annotations (already
   present in every chess.com/lichess import, currently unused for
   anything except one late-game "critical move" stat).

This is a VALIDATION script, not a backfill -- run against a sample,
print real findings, decide whether the signal is clean enough to be
worth building into the product before writing anything permanent.

Usage:
  docker exec -i chess-coach-backend python3 scripts/mine_opening_signals.py --sample 200
"""
import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient
from services.trap_library import get_all_traps

MOVE_CLK_RE = re.compile(r"(\d+)\.+\s*(\S+)\s*\{[^}]*%clk\s+([0-9:.]+)\]?\s*\}")


def clk_to_seconds(clk: str) -> float:
    parts = clk.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def parse_pgn_moves_with_clock(pgn: str):
    """Returns [(ply_index, san, clock_seconds), ...] in order, ply 0 = White's 1st move."""
    out = []
    for move_num, san, clk in MOVE_CLK_RE.findall(pgn):
        out.append((san, clk_to_seconds(clk)))
    return out


def san_sequence_from_pairs(pairs):
    return [san for san, _ in pairs]


def match_trap(user_sans, user_is_white: bool, traps_by_opening):
    """Check every trap's setup_moves against this game's move list.
    Returns list of {trap_name, role, outcome} for any that apply."""
    hits = []
    for opening_key, traps in traps_by_opening.items():
        for trap in traps:
            setup = trap.get("setup_moves") or []
            if not setup or len(user_sans) < len(setup):
                continue
            if user_sans[: len(setup)] != setup:
                continue
            # Setup reached. Whose move springs the trap? setup_moves
            # alternates W,B,W,B...; the mover of setup[-1] just moved,
            # so the NEXT move (index len(setup)) is the response the
            # trap_line's first entry describes.
            trap_line = trap.get("trap_line") or []
            if not trap_line:
                continue
            expected = [t["move"] for t in trap_line]
            actual_continuation = user_sans[len(setup): len(setup) + len(expected)]
            # len(setup) even -> White just played setup[-1] (0-indexed, len-1 is last mover);
            # ply index len(setup) (0-indexed) is White's move if len(setup) is even.
            responder_is_white = (len(setup) % 2 == 0)
            responder_is_user = (responder_is_white == user_is_white)
            fully_walked = actual_continuation == expected[: len(actual_continuation)] and len(
                actual_continuation
            ) >= min(3, len(expected))
            role = "springer" if not responder_is_user else "victim"
            # If the user IS the responder and walked the trap_line -> user fell for it (if victim)
            # or user executed it correctly (if the trap_line is what wins for the springer's side
            # and the user is on that side -- trap authoring puts trap_line as the VICTIM's moves
            # per traps.json convention, springer's moves are implicit between).
            hits.append({
                "trap_name": trap["name"],
                "opening_key": opening_key,
                "role": role,
                "reached_setup": True,
                "walked_trap_line": fully_walked,
            })
    return hits


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=200)
    args = p.parse_args()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=12000)[
        os.environ.get("DB_NAME", "chess_coach")
    ]
    traps_by_opening = get_all_traps()
    total_traps = sum(len(v) for v in traps_by_opening.values())
    print(f"Loaded {total_traps} traps across {len(traps_by_opening)} openings.\n")

    games = await db.games.find(
        {"pgn": {"$regex": "%clk"}, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "opening": 1, "user_id": 1, "time_control": 1},
    ).sort("imported_at", -1).limit(args.sample).to_list(args.sample)

    print(f"Sampled {len(games)} analyzed games with clock data.\n")

    trap_hit_games = 0
    trap_walked = 0
    opening_time_rows = []
    parse_failures = 0

    for g in games:
        pairs = parse_pgn_moves_with_clock(g["pgn"])
        if len(pairs) < 6:
            parse_failures += 1
            continue
        sans = san_sequence_from_pairs(pairs)
        user_is_white = g.get("user_color") == "white"

        hits = match_trap(sans, user_is_white, traps_by_opening)
        if hits:
            trap_hit_games += 1
            if any(h["walked_trap_line"] for h in hits):
                trap_walked += 1

        # Opening timing: first 10 of the USER's own plies. Must add the
        # increment back in -- a fast player's clock can go UP between
        # their own moves once increment exceeds time spent, and raw
        # deltas without this correction go negative (caught by checking
        # sample output before trusting it -- 5/300 "fastest" games had
        # impossible negative times until this fix).
        tc = g.get("time_control") or ""
        increment = 0.0
        if "+" in tc:
            try:
                increment = float(tc.split("+")[1])
            except (ValueError, IndexError):
                increment = 0.0

        user_ply_start = 0 if user_is_white else 1
        user_pairs = pairs[user_ply_start::2][:10]
        if len(user_pairs) >= 4:
            clocks = [c for _, c in user_pairs]
            deltas = []
            for i in range(1, len(clocks)):
                spent = clocks[i - 1] - clocks[i] + increment
                # Sanity filter: a single move taking >5min or a negative
                # value even after the increment correction means a parse
                # glitch (e.g. mistimed pairing), not real thinking time --
                # drop it rather than let one bad game corrupt the sample.
                if 0 <= spent <= 300:
                    deltas.append(spent)
            if deltas:
                opening_time_rows.append({
                    "game_id": g["game_id"],
                    "opening": g.get("opening"),
                    "avg_opening_move_time_s": round(sum(deltas) / len(deltas), 2),
                    "min_s": round(min(deltas), 2),
                    "max_s": round(max(deltas), 2),
                })

    print("=== TRAP MINING ===")
    print(f"  Games where a known trap's setup was reached: {trap_hit_games}/{len(games)}")
    print(f"  Of those, games where the trap_line was actually walked: {trap_walked}")

    print("\n=== OPENING-PHASE TIMING ===")
    print(f"  Games with usable opening timing data: {len(opening_time_rows)}/{len(games)}")
    print(f"  Parse failures (too few clocked moves): {parse_failures}")
    if opening_time_rows:
        avgs = [r["avg_opening_move_time_s"] for r in opening_time_rows]
        avgs.sort()
        n = len(avgs)
        print(f"  Median avg-opening-move-time across games: {avgs[n // 2]}s")
        print(f"  10th percentile (fast/known): {avgs[int(n * 0.1)]}s")
        print(f"  90th percentile (slow/unsure): {avgs[int(n * 0.9)]}s")
        print("\n  5 fastest games (sample):")
        for r in sorted(opening_time_rows, key=lambda r: r["avg_opening_move_time_s"])[:5]:
            print(f"    {r['opening']}: avg={r['avg_opening_move_time_s']}s  range=[{r['min_s']}, {r['max_s']}]")
        print("\n  5 slowest games (sample):")
        for r in sorted(opening_time_rows, key=lambda r: -r["avg_opening_move_time_s"])[:5]:
            print(f"    {r['opening']}: avg={r['avg_opening_move_time_s']}s  range=[{r['min_s']}, {r['max_s']}]")


asyncio.run(main())
