"""Repair the cognitive_gap labels the mate gate was shipped to fix.

The gate (`9378f797`, 2026-09-18) only runs when a game is analysed. Every
analysis already in the database still carries whatever the old code wrote, and
the old code assigned `tactical_oversight` to every missed mate and had no rule
at all for a mate the player walked into.

It also repairs the gate's own first mistake. `mate_info` is WHITE-relative
(`stockfish_service` returns `score.white()`), and the version shipped this
morning ignored that. Measured over 8,863 fires, it was wrong on 738 (8.3%):
a black player mating in 17 was told he had walked into mate, and a white
player who ESCAPED a mate was told he had let a forced win go. So this joins
every analysis back to its game's colour and re-derives in the player's frame.

That matters past tidiness. These labels feed the picker, active focus,
mastery, Progress and every validation run, and `tactical_oversight` (5,984
moves) is the bucket measured at 0.0% agreement with the precedence spec. We
have been measuring the product against labels we know are wrong.

Deliberately NOT a re-analysis. Stockfish is not re-run: `mate_info` is
already stored on 99.4% of mate swings, and the only field that changes is the
one the gate decides. A re-analysis would rewrite fields nobody asked to
change.

The rule itself is imported, never restated -- see
`analysis_interpreter.mate_gate_label`. A second copy here would be correct the
day it was written and wrong the first time the rule moved.

Usage (dry run prints the plan and writes nothing):

    docker exec chess-coach-backend python scripts/backfill_mate_gate_labels.py
    docker exec chess-coach-backend python scripts/backfill_mate_gate_labels.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from analysis_interpreter import mate_gate_label  # noqa: E402


async def main(apply: bool, recompute: bool) -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "test_database")]

    changes = Counter()
    users: set = set()
    touched_docs = 0
    scanned_moves = 0
    examples = []

    # `mate_info` is WHITE-relative (stockfish_service returns `score.white()`).
    # The gate needs the player's own frame, so every analysis has to be joined
    # back to its game's colour. Skipping this is not a rounding error: the
    # colour-blind version of this rule was wrong on 738 of 8,863 fires.
    colours = {}
    async for game in db.games.find({}, {"_id": 0, "game_id": 1, "user_color": 1}):
        colours[game.get("game_id")] = (game.get("user_color") or "white").lower()
    print(f"resolved colour for {len(colours)} games")

    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.mate_info": {"$exists": True}},
        {"_id": 1, "game_id": 1, "user_id": 1,
         "stockfish_analysis.move_evaluations": 1},
    )
    unknown_colour = 0
    async for doc in cursor:
        moves = (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []
        doc_changed = False
        game_id = doc.get("game_id")
        if game_id not in colours:
            # No game row means no colour, and guessing white is exactly the
            # bug this backfill exists to repair. Skip and report.
            unknown_colour += 1
            continue
        colour = colours[game_id]
        for index, move in enumerate(moves):
            # Opponent moves carry no engine truth of their own; the gate has
            # never applied to them and must not start here.
            if move.get("is_opponent_move"):
                continue
            scanned_moves += 1
            want = mate_gate_label(move.get("mate_info"), colour)
            if not want:
                continue
            had = move.get("cognitive_gap")
            if had == want:
                continue
            changes[f"{had} -> {want}"] += 1
            users.add(doc.get("user_id"))
            doc_changed = True
            if len(examples) < 8:
                examples.append(
                    f"    {game_id} move#{move.get('move_number')} {colour:5s} "
                    f"{had} -> {want}  mate_info={move.get('mate_info')}")
            if apply:
                # Positional write: only the one field the gate decides.
                await db.game_analyses.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        f"stockfish_analysis.move_evaluations.{index}."
                        f"cognitive_gap": want,
                        f"stockfish_analysis.move_evaluations.{index}."
                        f"cognitive_gap_source": "mate_gate_backfill_2026_09_18",
                    }},
                )
        if doc_changed:
            touched_docs += 1

    total = sum(changes.values())
    print(f"scanned {scanned_moves} user moves carrying mate_info")
    if unknown_colour:
        print(f"SKIPPED {unknown_colour} analyses with no game row (colour unknown)")
    print(f"{'APPLIED' if apply else 'WOULD CHANGE'}: {total} labels "
          f"in {touched_docs} analyses across {len(users)} users")
    for transition, count in changes.most_common():
        print(f"  {transition:44s} {count}")
    print("\nexamples:")
    for line in examples:
        print(line)

    if not apply:
        print("\nDRY RUN — nothing written. Re-run with --apply.")
        return

    if not recompute:
        print("\nLabels written. Pattern decay NOT refreshed (--no-recompute).")
        return

    # A label nobody re-reads changes nothing a player sees. Pattern decay is
    # the derived cache keyed off these labels. Active focus needs no pass of
    # its own -- focus_resolver.get_active_focus recomputes against a fresh
    # aggregate on every read.
    print(f"\nrefreshing pattern decay for {len(users)} users...")
    ok = failed = 0
    for user_id in users:
        if not user_id:
            continue
        try:
            from services.pattern_decay_service import (
                refresh_user_pattern_decay,
            )
            await refresh_user_pattern_decay(db, user_id)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  {user_id}: {type(exc).__name__}: {exc}")
    print(f"refreshed {ok} users, {failed} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write the labels (default is a dry run)")
    parser.add_argument("--no-recompute", action="store_true",
                        help="skip the pattern-decay refresh after writing")
    args = parser.parse_args()
    asyncio.run(main(args.apply, not args.no_recompute))
