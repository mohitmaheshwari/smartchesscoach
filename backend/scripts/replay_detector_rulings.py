"""Count how many of a detector's stored rulings are on claims it STILL makes.

Why this exists
---------------
A promotion packet's headline number is "N reviewed fires, P% precision". Both
are wrong if they count rulings made on claims the code has since withdrawn.
That is not hypothetical: on 2026-09-19 `discovered_attack` was promoted on a
packet assembled at 52 rulings, and replaying them showed 3 were on claims two
new gates had just removed. The real count was 49 against a bar of 50, and the
grade was reverted the same day.

So before any grade changes in `services/detector_quality.py`, run this. It
replays every ruling through the producer that `/admin/detector-review` serves
today and reports:

  * reviewed fires on claims the code still makes   (the count that counts)
  * precision over decided fires (true vs false), with a Wilson 95% lower bound
  * which false / unsure rulings are still live, so they can be read

A ruling on a claim the detector no longer makes cannot be wrong, and is not
counted either way. `unsure` counts toward the reviewed total and is excluded
from the precision denominator -- the same convention the 2026-08-27 threshold
lock uses.

This script decides nothing. It prints evidence; a human changes the grade.

Usage
-----
    python scripts/replay_detector_rulings.py discovered_attack
    python scripts/replay_detector_rulings.py principle_tac_hanging_piece -v

Reads `detector_claim_rulings` and `game_analyses`. Writes nothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

RULINGS = "detector_claim_rulings"
MOVE_FIELDS = (
    "fen_before", "fen_after", "move", "best_move", "eval_before",
    "eval_after", "cp_loss", "pv_after_played", "pv_after_best",
    "move_number", "is_opponent_move",
)

# Caption-grade bars, from docs/detector_quality_threshold_lock_2026_08_27.md.
BAR_REVIEWED = 50
BAR_PRECISION_LB = 85.0


def wilson_lower(hits: int, total: int, z: float = 1.96) -> float:
    """Wilson score interval, lower bound, as a percentage."""
    if total <= 0:
        return 0.0
    p = hits / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2.0 * total)
    radius = z * ((p * (1.0 - p) / total + z * z / (4.0 * total * total)) ** 0.5)
    return 100.0 * (centre - radius) / denom


def replay(detector: str, verbose: bool = False) -> int:
    from routes.admin_detector_review import _producers

    producers = _producers()
    produce = producers.get(detector)
    if produce is None:
        print(f"unknown detector {detector!r}. Known queues:")
        for key in sorted(producers):
            print("   ", key)
        return 2

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    rulings = list(db[RULINGS].find({"detector": detector}, {"_id": 0}))
    if not rulings:
        print(f"{detector}: no rulings stored. Nothing to replay.")
        return 1

    game_ids = sorted({str(r.get("claim_key", "")).split(":")[1]
                       for r in rulings
                       if len(str(r.get("claim_key", "")).split(":")) > 2})

    analyses = {}
    for doc in db["game_analyses"].find(
        {"game_id": {"$in": game_ids}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        moves = (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []
        analyses[doc["game_id"]] = [
            {k: m.get(k) for k in MOVE_FIELDS} for m in moves
        ]

    live, dead = Counter(), Counter()
    missing = errors = 0
    still_live_doubts = []
    days = Counter()

    for ruling in rulings:
        days[str(ruling.get("ruled_at"))[:10]] += 1
        parts = str(ruling.get("claim_key", "")).split(":")
        if len(parts) < 3:
            missing += 1
            continue
        moves = analyses.get(parts[1])
        if not moves:
            missing += 1
            continue
        move = next(
            (m for m in moves if str(m.get("move_number")) == str(parts[2])),
            None,
        )
        if move is None:
            missing += 1
            continue
        try:
            out = produce(
                move, None,
                {"stockfish_analysis": {"move_evaluations": moves}},
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            if verbose:
                print(f"  ERROR {ruling['claim_key']}: {type(exc).__name__}: {exc}")
            continue

        verdict = str(ruling.get("verdict"))
        if out:
            live[verdict] += 1
            if verdict != "true":
                still_live_doubts.append(
                    (verdict, ruling["claim_key"], str(out[0]),
                     str(ruling.get("note") or ""))
                )
        else:
            dead[verdict] += 1

    reviewed = sum(live.values())
    true_n, false_n = live["true"], live["false"]
    decided = true_n + false_n
    precision = (100.0 * true_n / decided) if decided else 0.0
    lower = wilson_lower(true_n, decided)

    print(f"detector                 : {detector}")
    print(f"stored rulings           : {len(rulings)}")
    if verbose:
        for day in sorted(days):
            print(f"    {day}  {days[day]}")
    print(f"  analysis unavailable   : {missing}   (not counted)")
    print(f"  producer errors        : {errors}")
    print(f"  claims since withdrawn : {sum(dead.values())}   (not counted) {dict(dead)}")
    print()
    print(f"REVIEWED FIRES (code still makes the claim) : {reviewed}   bar {BAR_REVIEWED}"
          f"   {'PASS' if reviewed >= BAR_REVIEWED else 'SHORT'}")
    print(f"    true {true_n} | false {false_n} | unsure {live['unsure']}")
    if decided:
        print(f"PRECISION over decided fires               : {true_n}/{decided}"
              f" = {precision:.1f}%")
        print(f"WILSON 95% LOWER BOUND                     : {lower:.1f}%"
              f"   bar {BAR_PRECISION_LB}"
              f"   {'PASS' if lower >= BAR_PRECISION_LB else 'SHORT'}")
    else:
        print("PRECISION                                  : no decided fires")

    if still_live_doubts:
        print()
        print("false / unsure rulings on claims still served:")
        for verdict, key, claim, note in still_live_doubts:
            print(f"  [{verdict}] {key}")
            print(f"        claim: {claim[:150]}")
            if note:
                print(f"        note : {note[:150]}")

    print()
    print("This script changes no grade. detector_quality.py is edited by hand.")
    client.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("detector", help="queue id, e.g. discovered_attack")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="per-day ruling counts and producer errors")
    args = parser.parse_args()
    return replay(args.detector, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
