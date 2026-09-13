#!/usr/bin/env python3
"""Apply the frozen development adjudicator to the one-time holdout.

This module deliberately owns no chess predicates. It imports the exact
adjudicate_game function frozen before the holdout was opened and only
checks the holdout packet's precommitted identity and shape.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adjudicate_whole_game_teaching_development import (
    EXPECTED_PACKET_SCHEMA,
    SCHEMA_VERSION,
    adjudicate_game,
)


EXPECTED_PACKET_SHA256 = (
    "ee694af72dc95a7c0ea6807023c0fc1e98e37cfe8726eb452d941bddef0695f9"
)
EXPECTED_MEMBERSHIP_SHA256 = (
    "87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b"
)
EXPECTED_GAMES = 42
FROZEN_SOURCE_COMMIT = "76a411306b0066b4e585f6f23f2d0df8a7306e7e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_holdout_worksheet(
    packet: Mapping[str, Any],
    *,
    packet_sha256: str,
) -> Dict[str, Any]:
    if packet_sha256 != EXPECTED_PACKET_SHA256:
        raise ValueError("holdout packet hash mismatch")
    if packet.get("schema_version") != EXPECTED_PACKET_SCHEMA:
        raise ValueError("unexpected packet schema")
    if packet.get("membership_sha256") != EXPECTED_MEMBERSHIP_SHA256:
        raise ValueError("holdout membership changed")
    if packet.get("sample") != "holdout" or packet.get("blinded") is not True:
        raise ValueError("only the blinded holdout packet may be adjudicated")
    games = packet.get("games")
    if not isinstance(games, list) or len(games) != EXPECTED_GAMES:
        raise ValueError("holdout packet must contain exactly 42 games")

    rows = [adjudicate_game(game) for game in games]
    keys = [row["anonymous_game_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate anonymous game")
    moments = [moment for row in rows for moment in row["moments"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_kind": "one_time_unseen_holdout",
        "status": "codex_manual_review_required",
        "source": {
            "packet_schema_version": packet["schema_version"],
            "packet_sha256": packet_sha256,
            "membership_sha256": packet["membership_sha256"],
            "games": EXPECTED_GAMES,
            "frozen_adjudicator_source_commit": FROZEN_SOURCE_COMMIT,
        },
        "method": (
            "The exact detector-blind adjudicate_game function frozen on the "
            "development corpus was applied without changed predicates, "
            "thresholds, ranking, or exceptions. No engine, model, detector "
            "label, product caption, or source identity was used."
        ),
        "summary": {
            "games": len(rows),
            "games_with_proved_story": sum(
                not row["no_provable_central_story"] for row in rows
            ),
            "proved_moments": len(moments),
            "cause_family": dict(sorted(Counter(
                moment["cause_family"] for moment in moments
            ).items())),
            "critical_false_claims": sum(
                bool(moment["critical_false_claim"]) for moment in moments
            ),
        },
        "games": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    actual_sha256 = _sha256(args.packet)
    packet = json.loads(args.packet.read_text(encoding="utf-8-sig"))
    worksheet = build_holdout_worksheet(
        packet,
        packet_sha256=actual_sha256,
    )
    text = json.dumps(worksheet, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
