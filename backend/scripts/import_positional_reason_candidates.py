#!/usr/bin/env python3
"""Load local positional candidates for admin review without resolving them."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pymongo import MongoClient, ReplaceOne


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    meta = source["meta"]
    records = source["records"]
    client = MongoClient(os.environ["MONGO_URL"])
    database = client[os.environ.get("DB_NAME", "test_database")]
    collection = database.positional_reason_generated_candidates
    collection.create_index("position_fingerprint", unique=True, name="generated_positional_position")

    operations = []
    for record in records:
        final = record["final"]
        document = {
            "schema_version": meta["schema_version"],
            "position_fingerprint": record["position_fingerprint"],
            "candidate_id": record["candidate_id"],
            "fen": record["fen"],
            "game_id": record.get("game_id"),
            "move_number": record.get("move_number"),
            "side_to_move": record.get("side_to_move"),
            "bucket": record.get("bucket"),
            "played_san": record.get("played_san"),
            "played_uci": record.get("played_uci"),
            "best_san": record.get("best_san"),
            "best_uci": record.get("best_uci"),
            "disposition": record["disposition"],
            "concept_label": final.get("concept_label"),
            "canonical_concept_id": final.get("canonical_concept_id"),
            "better_move_fact": final.get("better_move_fact"),
            "played_move_fact": final.get("played_move_fact"),
            "contrast": final.get("contrast"),
            "transferable_lesson": final.get("transferable_lesson"),
            "caption": final.get("caption"),
            "reason_category": final.get("category"),
            "claim_proof": final.get("claim_proof") or [],
            "verification": record["verification"],
            "exclusion_scores": record.get("exclusion_scores"),
            "generated_at": record["generated_at"],
            "generation_meta": meta,
            "caption_eligible": False,
            "tracker_eligible": False,
            "review_status": "candidate",
        }
        operations.append(
            ReplaceOne(
                {"position_fingerprint": document["position_fingerprint"]},
                document,
                upsert=True,
            )
        )
    result = collection.bulk_write(operations, ordered=False) if operations else None
    print(
        json.dumps(
            {
                "candidates": len(records),
                "caption_targets": sum(record["disposition"] == "eligible_positional" for record in records),
                "verified_caption_targets": sum(
                    record["disposition"] == "eligible_positional"
                    and record["verification"]["status"] == "pass"
                    for record in records
                ),
                "matched": result.matched_count if result else 0,
                "upserted": len(result.upserted_ids) if result else 0,
            }
        )
    )


if __name__ == "__main__":
    main()
