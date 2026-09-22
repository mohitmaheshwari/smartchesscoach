"""Precompute what each detector claims, so the review page can just read it.

Mohit, 2026-09-21: "why is there a scan, the positions we have already
identified ... should be added as a separate collection for that category."

He is right. /admin/detector-review was re-deriving every claim on every page
load: walk up to 20,000 analyses, run the proof builders on every mistake
move, stop once 20 unruled cards are found. For a detector that fires on 1.8%
of games that means grinding through about a thousand games before it can show
anything, and nginx gives up at sixty seconds. Three 504s in today's access
log -- discovered_attack twice and fork once -- which is why the page told him
there was nothing left to review while twenty cards were waiting.

Claims are a function of (corpus, detector). Neither changes while someone is
reading a card, so deriving them live is work repeated for no reason.

    python scripts/build_detector_claims.py --detector discovered_attack
    python scripts/build_detector_claims.py --all
    python scripts/build_detector_claims.py --all --limit 4000

Writes `detector_claims`, keyed on claim_key so a re-run is idempotent. Each
row records `built_at` and `builder_fingerprint` -- a hash of the detector's
own source -- so a stale claim set is visible rather than silently served
after a detector changes. That mattered today: discovered_attack's payoff rule
and the discovery gate both changed, and the claim set moved under both.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient

COLLECTION = "detector_claims"


def _fingerprint(detector: str) -> str:
    """A hash of the code that produces this detector's claims.

    Not a version number someone has to remember to bump -- the source itself.
    """
    from routes import admin_detector_review as adr

    parts = [detector]
    producer = adr._producers().get(detector)
    for obj in (producer, getattr(producer, "__wrapped__", None)):
        if obj is None:
            continue
        try:
            parts.append(inspect.getsource(obj))
        except (OSError, TypeError):
            pass
    # The shared proof builders matter as much as the producer wrapper. A
    # producer that names its own proof module (the 2026-09-22 detectors do,
    # via `_new_proof`) gets that module hashed too -- otherwise a change to
    # e.g. interference_puzzle_proof left every stored claim looking freshly
    # built, which defeats the whole point of recording a fingerprint.
    mod_names = ["services.fork_puzzle_proof",
                 "services.discovered_attack_puzzle_proof",
                 "services.aligned_tactic_puzzle_proof",
                 "services.played_hangs_detector",
                 "services.mate_lesson"]
    tagged = getattr(producer, "_proof_module", None)
    if tagged and tagged not in mod_names:
        mod_names.append(tagged)
    for mod_name in mod_names:
        try:
            mod = __import__(mod_name, fromlist=["*"])
            parts.append(inspect.getsource(mod))
        except Exception:  # noqa: BLE001
            pass
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()[:16]


async def build(db, detector: str, limit: int) -> dict:
    from routes import admin_detector_review as adr

    adr.set_db(db)
    fingerprint = _fingerprint(detector)

    # _fires_for stops at `limit` claims; ask for far more than a page so the
    # collection is a real index rather than one screenful.
    claims = await adr._fires_for(detector, set(), limit)

    written = 0
    now = datetime.now(timezone.utc)
    for claim in claims:
        await db[COLLECTION].update_one(
            {"claim_key": claim["claim_key"]},
            {"$set": {
                "claim_key": claim["claim_key"],
                "detector": detector,
                "game_id": claim.get("game_id"),
                "claim": claim.get("claim"),
                "evidence": claim.get("evidence"),
                "game": claim.get("game"),
                "built_at": now,
                "builder_fingerprint": fingerprint,
            }},
            upsert=True)
        written += 1

    # Anything built by an older fingerprint is stale: the detector has
    # changed since, so the claim may no longer be one.
    stale = await db[COLLECTION].count_documents(
        {"detector": detector, "builder_fingerprint": {"$ne": fingerprint}})
    return {"detector": detector, "written": written,
            "fingerprint": fingerprint, "stale_rows": stale}


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=2000,
                        help="max claims to store per detector")
    parser.add_argument("--purge-stale", action="store_true",
                        help="delete rows built by an older fingerprint")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    from routes import admin_detector_review as adr
    names = ([args.detector] if args.detector
             else sorted(adr._producers()) if args.all else [])
    if not names:
        parser.error("pass --detector NAME or --all")

    await db[COLLECTION].create_index("claim_key", unique=True)
    await db[COLLECTION].create_index([("detector", 1), ("built_at", -1)])

    for name in names:
        try:
            result = await build(db, name, args.limit)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:26s} FAILED {type(exc).__name__}: {exc}")
            continue
        if args.purge_stale and result["stale_rows"]:
            await db[COLLECTION].delete_many(
                {"detector": name,
                 "builder_fingerprint": {"$ne": result["fingerprint"]}})
        print(f"{name:26s} stored {result['written']:5d}  "
              f"fingerprint {result['fingerprint']}  "
              f"stale {result['stale_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
