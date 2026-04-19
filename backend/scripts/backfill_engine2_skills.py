"""
Backfill Engine 2 skill attempts from the user's last N analyzed games.

Why: the recorder (record_engine2_skills_from_game) only started running
today. Historical games didn't populate SkillProgress, so Engine 2's
"Learn next" card shows seen=0 for every tier-1 skill.

This script replays the last N games through the recorder so the stats
reflect actual play history. Then pick_next_skill returns a meaningful
suggestion instead of the always-ready tier-1 default.

Usage:
    python scripts/backfill_engine2_skills.py <user_id> [--limit 25] [--reset]

  --limit N   how many recent analyzed games to backfill (default 25)
  --reset     wipe learning.skills before backfilling (start clean)

Defaults to dev_user_local when no user_id given.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _extract_tactical_patterns(move_evaluations, user_color: str):
    """Run classify_mistake over user moves with meaningful cp_loss.
    Returns list of tactical_pattern strings for this game."""
    from mistake_classifier import classify_mistake

    patterns = []
    for mv in move_evaluations:
        if not mv.get("is_user_move"):
            continue
        cp_loss = mv.get("cp_loss", 0) or 0
        # Only classify meaningful moves — includes positive events too
        if cp_loss < 30:
            continue
        try:
            classified = classify_mistake(
                fen_before=mv.get("fen_before", ""),
                fen_after=mv.get("fen_after", ""),
                move_played=mv.get("move_san") or mv.get("move_uci", ""),
                best_move=mv.get("best_move_san") or mv.get("engine_best_move", ""),
                eval_before=mv.get("score_before", 0),
                eval_after=mv.get("score_after", 0),
                user_color=user_color,
                move_number=mv.get("move_number", 1),
            )
            if classified and classified.mistake_type:
                patterns.append(classified.mistake_type.value)
        except Exception:
            continue
    return patterns


async def backfill(user_id: str, limit: int, reset: bool):
    from services.coach_memory import (
        get_or_create_memory, record_engine2_skills_from_game, _memory_to_doc
    )
    from services.engine2_skill_builder import pick_next_skill

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\nBackfilling Engine 2 for: {user_id}")
    print(f"DB: {DB_NAME}  |  limit: {limit}  |  reset: {reset}\n")

    # Load memory
    memory = await get_or_create_memory(db, user_id)

    if reset:
        memory.learning.skills = []
        memory.learning.concepts_mastered = []
        # Keep openings_learned / traps_learned / endgames_learned —
        # those have their own recording pipelines.
        print("[reset] Cleared learning.skills + learning.concepts_mastered")

    # Load user rating (best available)
    user_rating = memory.performance.best_performance_rating or 1000

    # Pull a larger window so we can filter out short / abandoned games
    # and still land on N usable ones.
    candidates = await db.games.find(
        {"user_id": user_id, "is_analyzed": True}
    ).sort("imported_at", -1).limit(limit * 4).to_list(limit * 4)

    MIN_MOVES = 20  # half-moves; <20 = too short to draw skill signal
    BAD_TERMINATIONS = {"abandonment", "abandoned", "aborted", "unknown", ""}

    usable = []
    rejected_short = 0
    rejected_abandoned = 0
    rejected_noanalysis = 0

    for game in candidates:
        if len(usable) >= limit:
            break
        termination = (game.get("termination") or "").lower()
        if termination in BAD_TERMINATIONS:
            rejected_abandoned += 1
            continue

        analysis = await db.game_analyses.find_one({"game_id": game.get("game_id")})
        if not analysis:
            rejected_noanalysis += 1
            continue

        move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        if len(move_evals) < MIN_MOVES:
            rejected_short += 1
            continue

        usable.append((game, analysis))

    # Chronological order (oldest first) so graduation fires in the right sequence
    usable.reverse()

    print(f"Scanned {len(candidates)} recent games, kept {len(usable)}")
    print(f"  rejected: {rejected_short} too short  |  "
          f"{rejected_abandoned} abandoned/aborted  |  "
          f"{rejected_noanalysis} no analysis\n")

    recorded_count = 0
    skipped = 0

    for idx, (game, analysis) in enumerate(usable, 1):
        game_id = game.get("game_id")
        user_color = (game.get("user_color") or "white").lower()

        sf = analysis.get("stockfish_analysis", {})
        move_evaluations = sf.get("move_evaluations", [])
        if not move_evaluations:
            skipped += 1
            continue

        # Extract the game-level signals
        blunders = sf.get("blunders", 0) or 0
        accuracy = sf.get("accuracy", 0) or 0

        raw_result = (game.get("result") or "").lower()
        if raw_result == "1-0":
            game_result = "win" if user_color == "white" else "loss"
        elif raw_result == "0-1":
            game_result = "win" if user_color == "black" else "loss"
        elif raw_result in ("w", "l", "d", "win", "loss", "draw", "1/2-1/2"):
            game_result = {"w": "win", "l": "loss", "d": "draw"}.get(raw_result, raw_result)
        else:
            game_result = "draw"

        # was_winning: any point the user had +150cp advantage
        was_winning = False
        for mv in move_evaluations:
            score = mv.get("score_before", 0) or 0
            # score_before is centipawns from white's perspective
            if user_color == "white" and score > 150:
                was_winning = True
                break
            if user_color == "black" and score < -150:
                was_winning = True
                break

        endgame_reached = len(move_evaluations) > 80

        # Re-classify the mistake types for this game
        mistake_types = _extract_tactical_patterns(move_evaluations, user_color)

        # Record into Engine 2
        added = record_engine2_skills_from_game(
            memory=memory,
            user_rating=user_rating,
            mistake_types=mistake_types,
            blunders=blunders,
            accuracy=accuracy,
            game_result=game_result,
            was_winning=was_winning,
            endgame_reached=endgame_reached,
        )
        recorded_count += 1

        term = (game.get("termination") or "?")[:10]
        print(f"  [{idx:>2}/{len(usable)}] {game_id[:16]}  "
              f"{game_result:<4}  {term:<10} acc={accuracy:>3.0f}  bl={blunders}  "
              f"evts={len(mistake_types):>2}  rec={len(added)}")

    # Save memory
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": _memory_to_doc(memory)},
        upsert=True,
    )

    # Show the result
    print(f"\n{'='*60}")
    print(f"Replayed {recorded_count} games  |  skipped {skipped}")
    print(f"\nSkill progress after backfill:")
    print(f"{'-'*60}")
    print(f"{'Skill':<28} {'Seen':>5} {'Corr':>5} {'Wrong':>5}  {'Last 5':<12}  Learned")
    for s in sorted(memory.learning.skills, key=lambda x: -x.seen):
        outcomes = " ".join("✓" if o == "correct" else "✗" if o == "wrong" else "·"
                            for o in (s.outcomes or [])[-5:])
        learned = "YES" if s.learned_at else "—"
        print(f"  {s.skill_id:<26} {s.seen:>5} {s.correct:>5} {s.wrong:>5}  {outcomes:<12}  {learned}")

    print(f"\nLearned list (concepts_mastered): {memory.learning.concepts_mastered or '(empty)'}")

    # Show what Engine 2 would pick now
    print(f"\n{'='*60}")
    next_skill = pick_next_skill(memory, user_rating)
    if next_skill:
        print(f"Engine 2 next pick:  {next_skill['label']}")
        print(f"  skill_id:  {next_skill['skill_id']}")
        print(f"  reason:    {next_skill['reason']}")
        print(f"  stats:     seen={next_skill['stats']['seen']} "
              f"correct={next_skill['stats']['correct']} "
              f"failed={next_skill['stats']['failed']} "
              f"score={next_skill['stats']['score']}")
    else:
        print("Engine 2 has nothing ready to teach right now.")

    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", nargs="?", default="dev_user_local",
                        help="User ID to backfill (default: dev_user_local)")
    parser.add_argument("--limit", type=int, default=25,
                        help="Number of recent analyzed games to replay (default 25)")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe learning.skills + concepts_mastered before backfilling")
    args = parser.parse_args()

    asyncio.run(backfill(args.user_id, args.limit, args.reset))


if __name__ == "__main__":
    main()
