#!/usr/bin/env python3
"""Is the derived why better than the caption that ships today?

This is the gate in docs/offline_resolver_captions_scope.md. The plan is
to substitute a derived sentence ONLY on mistake cards that fell to a
fallback tier -- the ones where the system had nothing and spoke anyway.
Before any of that renders, the pairs have to be looked at.

It prints, in order:
  1. which caption rule renders on user mistakes, and the fallback share
  2. for a sample of fallback cards, today's caption next to the derived
     sentence, with the mechanism that produced it

"It ought to be better" is how caption regressions ship here, so this
prints pairs rather than a score. Read them.

Usage (inside the backend container, where Mongo and Stockfish are):
    python scripts/caption_vs_derived.py --sample 120
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import sys

import chess
import chess.engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.why_on_demand import (  # noqa: E402
    CANDIDATE_COUNT,
    CANDIDATE_DEPTH,
    explain,
)

STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

# A card is "fallback" when its rule_name says the pipeline reached for a
# floor rather than an explanation. Kept as substrings because the stored
# name carries a chain ("R_FALLBACK->R_PROMOTED_basic_mistake->HELD").
FALLBACK_MARKS = ("R_PROMOTED_basic_mistake", "R16_board_state_fallback",
                  "R_TIER", "R_FALLBACK")


def is_fallback(rule: str) -> bool:
    return any(mark in (rule or "") for mark in FALLBACK_MARKS)


async def rule_mix(db, games: int = 600):
    """Which rule renders on user mistakes. No engine needed."""
    rules: collections.Counter = collections.Counter()
    cards = seen = 0
    async for a in db.game_analyses.find(
            {"decryption_v5_data.0": {"$exists": True}},
            {"_id": 0, "decryption_v5_data": 1}).limit(games):
        seen += 1
        for d in a.get("decryption_v5_data") or []:
            if not d.get("is_user_move"):
                continue
            if d.get("severity") not in ("blunder", "mistake"):
                continue
            cards += 1
            rules[d.get("rule_name") or "(none)"] += 1
    fb = sum(n for k, n in rules.items() if is_fallback(k))
    print(f"games {seen}   user mistake/blunder cards {cards}\n")
    print("%-50s %6s %7s" % ("rule_name", "cards", "share"))
    for k, n in rules.most_common(12):
        mark = "  <- fallback" if is_fallback(k) else ""
        print("%-50s %6d %6.1f%%%s" % (k[:50], n, 100.0 * n / max(cards, 1), mark))
    print("\nFALLBACK TOTAL: %d of %d (%.1f%%)" % (fb, cards, 100.0*fb/max(cards, 1)))
    return cards, fb


def candidates_for(eng, board, limit):
    infos = eng.analyse(board, limit, multipv=CANDIDATE_COUNT)
    if isinstance(infos, dict):
        infos = [infos]
    out = []
    for info in infos:
        pv = info.get("pv") or []
        if not pv:
            continue
        walker, line = board.copy(stack=False), []
        for mv in pv[:12]:
            try:
                line.append(walker.san(mv))
                walker.push(mv)
            except (ValueError, AssertionError, KeyError):
                break
        if not line:
            continue
        score = info.get("score")
        out.append({
            "move_san": line[0],
            "line_san": line,
            "eval_cp": score.pov(board.turn).score(mate_score=100000)
            if score else None,
        })
    return out


async def side_by_side(db, sample: int):
    eng = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    # Threads=1 is not a speed setting: multi-threaded Stockfish returns a
    # different line each run, so the same card would compare differently.
    eng.configure({"Threads": 1, "Hash": 128})
    limit = chess.engine.Limit(depth=CANDIDATE_DEPTH)

    pairs, n = [], 0
    async for a in db.game_analyses.find(
            {"decryption_v5_data.0": {"$exists": True},
             "stockfish_analysis.move_evaluations.0": {"$exists": True}},
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1,
             "stockfish_analysis.move_evaluations": 1}).limit(1200):
        evals = {(e.get("move_number"), e.get("move")): e
                 for e in (a.get("stockfish_analysis") or {}).get(
                     "move_evaluations") or []
                 if not e.get("is_opponent_move")}
        for d in a.get("decryption_v5_data") or []:
            if not d.get("is_user_move"):
                continue
            if d.get("severity") not in ("blunder", "mistake"):
                continue
            if not is_fallback(d.get("rule_name") or ""):
                continue
            ev = evals.get((d.get("move_number"), d.get("move_san")))
            if not ev or not ev.get("fen_before"):
                continue
            try:
                board = chess.Board(ev["fen_before"])
            except ValueError:
                continue
            n += 1
            result = explain(
                ev["fen_before"], ev.get("move"),
                ev.get("pv_after_played") or [],
                candidates_for(eng, board, limit),
                cp_loss=ev.get("cp_loss"),
            )
            pairs.append({
                "game": a.get("game_id"),
                "move": ev.get("move"),
                "cp": ev.get("cp_loss"),
                "rule": d.get("rule_name"),
                "now": (d.get("narrative") or d.get("caption") or "").strip(),
                "derived": (result or {}).get("text"),
                "mech": (result or {}).get("mechanism"),
            })
            if n % 20 == 0:
                print(f"  ...{n}", flush=True)
            if n >= sample:
                break
        if n >= sample:
            break
    eng.quit()

    out = "/tmp/caption_vs_derived.json"
    with open(out, "w") as fh:
        json.dump(pairs, fh, indent=1)
    assert os.path.exists(out), "pairs not written"

    got = [p for p in pairs if p["derived"]]
    print(f"\nwrote {out}")
    print(f"fallback cards sampled : {len(pairs)}")
    print(f"derived an answer      : {len(got)} "
          f"({100.0*len(got)/max(len(pairs),1):.0f}%)")
    print(f"stayed silent          : {len(pairs)-len(got)}  "
          f"(these keep today's caption, so no regression is possible)")
    print("mechanisms:", dict(collections.Counter(p["mech"] for p in got)))

    print("\n" + "=" * 76)
    print("  TODAY'S CAPTION  vs  THE DERIVED SENTENCE")
    print("=" * 76)
    for p in got[:25]:
        print(f"\n{p['move']}  ({p['cp']}cp)")
        print(f"   now     : {p['now'][:160]}")
        print(f"   derived : {p['derived']}")
    return pairs


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=120)
    ap.add_argument("--games", type=int, default=600)
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    print("=" * 76)
    print("  1. WHICH RULE RENDERS ON USER MISTAKES")
    print("=" * 76)
    await rule_mix(db, args.games)

    print("\n" + "=" * 76)
    print("  2. THE PAIRS")
    print("=" * 76)
    await side_by_side(db, args.sample)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
