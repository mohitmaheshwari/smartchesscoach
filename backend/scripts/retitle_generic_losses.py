"""Re-title, ONCE, the losses whose title says only "big mistakes punished".

Headlines are one model call per game, ever (Mohit, 2026-10-23: "once LLM is
used, don't make another call"). This is the single exception he approved on
2026-10-28 ("go ahead", on re-titling the generic ones once). It is not a
second path for the product: services/game_headline.py still never calls the
model for a game that has a headline.

Why: 1,468 losses were titled "Your big mistakes were punished" while their
tags held a checkmate, a lost queen or a lost rook (2026-10-27). Headline v3
puts that cause into the facts. This gives the v3 facts to the games titled
before v3 -- only losses whose old title is a generic one AND for which the
rules can now name a cause.

Each game is marked `retitled_once` whatever happens, except a call that never
reached the model, so a restart only does what is left and no game is ever
re-titled twice. A refused new title keeps the old one; the old title is kept
in `previous_title` either way.

  docker exec -i chess-coach-backend python -m scripts.retitle_generic_losses            # count only
  docker exec -i chess-coach-backend python -m scripts.retitle_generic_losses --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import re
import sys
import time
from datetime import datetime, timezone

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from services.game_headline import (  # noqa: E402
    COLLECTION, HEADLINE_VERSION, facts_key, headline_facts, what_decided_a_loss, write_headline,
)
from services.game_story import story_for_game  # noqa: E402

GENERIC = re.compile(r"punished|slipped", re.I)
_OBS_FIELDS = {"_id": 0, "subtype": 1, "missed_pattern": 1, "phase": 1,
               "found_best_in_critical": 1, "punished_opponent_blunder": 1, "responded_to_threat": 1}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    headlines = db[COLLECTION]

    old = [h async for h in headlines.find(
        {"llm_used": True, "version": {"$ne": HEADLINE_VERSION}, "retitled_once": {"$ne": True}},
        {"_id": 0, "game_id": 1, "title": 1}) if GENERIC.search(h.get("title") or "")]
    print(f"generic titles written before {HEADLINE_VERSION}: {len(old)}", flush=True)

    counts: collections.Counter = collections.Counter()
    todo = []
    for start in range(0, len(old), 200):
        chunk = [h["game_id"] for h in old[start:start + 200]]
        obs = collections.defaultdict(list)
        async for o in db.move_observations.find({"game_id": {"$in": chunk}}, {**_OBS_FIELDS, "game_id": 1}):
            obs[o.pop("game_id")].append(o)
        tags = {t["game_id"]: t.get("tags") or [] async for t in db.game_tag_index.find(
            {"game_id": {"$in": chunk}}, {"_id": 0, "game_id": 1, "tags": 1})}
        async for a in db.game_analyses.find(
                {"game_id": {"$in": chunk}},
                {"_id": 0, "game_id": 1, "game_story.ledger.events": 1, "game_story.ledger.outcome": 1}):
            story = {**(a.get("game_story") or {}), "tags": {"ids": tags.get(a["game_id"], [])}}
            if (story.get("ledger") or {}).get("outcome") != "loss":
                counts["not a loss"] += 1
            elif not what_decided_a_loss(story, obs[a["game_id"]]):
                counts["no cause to name"] += 1
            else:
                todo.append(a["game_id"])
    if args.limit:
        todo = todo[:args.limit]
    print(f"losses the rules can now name a cause for: {len(todo)}   skipped: {dict(counts)}", flush=True)
    if not args.apply:
        return 0

    done: collections.Counter = collections.Counter()
    gate = asyncio.Semaphore(max(1, args.concurrency))
    start_at = time.time()

    async def one(game_id: str):
        async with gate:
            saved = await headlines.find_one({"game_id": game_id}, {"_id": 0})
            if not saved or saved.get("retitled_once"):
                done["already done"] += 1
                return
            game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
            story = await story_for_game(db, game, persist=False) if game else None
            if not story or not story.get("plan"):
                done["no story"] += 1
                return
            observations = await db.move_observations.find({"game_id": game_id}, _OBS_FIELDS).to_list(None)
            facts = headline_facts(story, game, observations)
            written = await write_headline(facts, (story.get("ledger") or {}).get("outcome"))
            if written.get("reason") in ("llm_error", "disabled"):
                done["model unreachable (retry later)"] += 1
                return
            update = {"retitled_once": True, "retitled_at": datetime.now(timezone.utc),
                      "previous_title": saved.get("title"), "previous_teaching": saved.get("teaching"),
                      "previous_version": saved.get("version")}
            if written.get("ok"):
                update.update(title=written["title"], teaching=written["teaching"], source="llm",
                              model=written["model"], version=HEADLINE_VERSION, facts_key=facts_key(facts))
                done["re-titled"] += 1
            else:
                update["retitle_refused"] = written.get("reason")
                done["refused, old title kept"] += 1
            await headlines.update_one({"game_id": game_id}, {"$set": update})
            n = sum(done.values())
            if n % 250 == 0:
                print(f"  {n}/{len(todo)}  {n / max(1e-6, time.time() - start_at):.1f}/s  {dict(done)}", flush=True)

    await asyncio.gather(*(one(g) for g in todo))
    print("=== done ===")
    for key, value in done.most_common():
        print(f"  {key:<34} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
