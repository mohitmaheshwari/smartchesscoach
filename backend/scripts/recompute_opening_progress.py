"""
recompute_opening_progress.py — backfill opening "games played" from real games.

Fixes the gap where adding an opening to the skill-tree doesn't retroactively
credit past games (Mohit 2026-06-09: 2 faithful English games existed but English
showed "Not started"). Re-detects each of the user's analyzed games via the SINGLE
curriculum detector + confidence gate, counts games per opening, and sets each
opening skill's `seen` count in coach_memory so the progress page reflects reality.

Run this after adding any opening (until per-opening counts are derived live).

DRY-RUN by default (read-only — computes + prints what it WOULD set). Pass
write=True to actually update coach_memory.

Usage (dry-run):
  docker exec -i chess-coach-backend python -c "import asyncio,sys; sys.path.insert(0,'/app/backend'); \
    from scripts.recompute_opening_progress import recompute; asyncio.run(recompute('user_xxx'))"
"""
import io
import os
import sys
from collections import Counter

sys.path.insert(0, "/app/backend")

import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

_MIN_CONFIDENCE_DEPTH = 3  # must match the live persist gate in coach_play.py


def _first_moves(pgn: str, n: int = 12):
    if not isinstance(pgn, str) or not pgn.strip():
        return []
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        board = game.board()
        out = []
        for mv in game.mainline_moves():
            out.append(board.san(mv))
            board.push(mv)
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


async def recompute(user_id: str, write: bool = False):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)[
        os.environ.get("DB_NAME", "chess_coach")
    ]
    await db.command("ping")
    from routes.coach_play import _detect_opening_from_moves
    import json
    # content_ref -> skill_id, read straight from the skill tree (reliable: the
    # skill id is the dict KEY, content_ref is a field).
    _st = json.load(open("/app/backend/data/coaching/skill_tree.json", encoding="utf-8"))
    valid = {
        v["content_ref"]: k
        for k, v in _st.get("skills", {}).items()
        if isinstance(v, dict) and v.get("kind") == "opening" and v.get("content_ref")
    }

    counts = Counter()          # content_ref -> games
    gated = Counter()           # content_ref -> shallow/transposed (excluded)
    scanned = 0
    async for g in db.games.find(
        {"user_id": user_id}, {"_id": 0, "pgn": 1, "moves": 1, "user_color": 1, "game_id": 1}
    ):
        moves = _first_moves(g.get("pgn") or g.get("moves") or "")
        if len(moves) < 3:
            continue
        scanned += 1
        key, depth = _detect_opening_from_moves(moves, (g.get("user_color") or "white"))
        if not key:
            continue
        if depth >= _MIN_CONFIDENCE_DEPTH:
            counts[key] += 1
        else:
            gated[key] += 1

    print(f"scanned {scanned} games for {user_id}")
    print(f"\n=== recomputed games-per-opening (confident, depth >= {_MIN_CONFIDENCE_DEPTH}) ===")
    for ref, c in counts.most_common():
        sid = valid.get(ref, f"(untracked:{ref})")
        print(f"  {ref}: {c} games  -> skill {sid}")
    if gated:
        print(f"\n  excluded (shallow/transposed, < depth {_MIN_CONFIDENCE_DEPTH}):")
        for ref, c in gated.most_common():
            print(f"    {ref}: {c}")

    if not write:
        print("\n[DRY-RUN] no changes written. Pass write=True to apply.")
        return dict(counts)

    # ── WRITE: set each opening skill's `seen` to the true count ──────────
    # Uses the codebase's own serializer (_memory_to_doc) + the standard
    # coach_memory upsert (the same persistence as update_memory_after_game).
    # skills is a LIST of SkillProgress; find-or-create, then idempotently SET
    # seen to the recomputed count (max() never inflates on re-run).
    from datetime import datetime, timezone
    from services.coach_memory import get_or_create_memory, _memory_to_doc, SkillProgress
    memory = await get_or_create_memory(db, user_id)
    applied = 0
    for ref, c in counts.items():
        sid = valid.get(ref)
        if not sid:
            continue
        skill = next((s for s in memory.learning.skills
                      if s.skill_id == sid and s.skill_type == "opening"), None)
        if skill is None:
            skill = SkillProgress(
                skill_id=sid, skill_type="opening",
                first_seen=datetime.now(timezone.utc).isoformat(),
            )
            memory.learning.skills.append(skill)
        skill.seen = max(skill.seen, c)
        applied += 1
    await db.coach_memory.update_one(
        {"user_id": user_id}, {"$set": _memory_to_doc(memory)}, upsert=True
    )
    print(f"\n[WRITE] set seen on {applied} opening skills in coach_memory for {user_id}")
    return dict(counts)
