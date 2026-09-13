#!/usr/bin/env python3
"""Measure frozen deterministic fact coverage on the one-time holdout.

The fact projection and match rules are imported from the development scorer.
This wrapper owns only immutable holdout identity checks and report metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.measure_whole_game_teaching_fact_coverage import measure


BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_packet_v1.json"
)
DEFAULT_WORKSHEET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_worksheet_v1.json"
)
EXPECTED_PACKET_SHA256 = (
    "ee694af72dc95a7c0ea6807023c0fc1e98e37cfe8726eb452d941bddef0695f9"
)
EXPECTED_WORKSHEET_SHA256 = (
    "adefb7104e7c48639f1f7c50064a3a3d14c71c4c2e5c11af6f09dc7927ca6a17"
)
EXPECTED_MEMBERSHIP_SHA256 = (
    "87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b"
)


def _load_bound(path: Path, expected_sha256: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"frozen holdout hash mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_report(packet_path: Path, worksheet_path: Path) -> Dict[str, Any]:
    packet = _load_bound(packet_path, EXPECTED_PACKET_SHA256)
    worksheet = _load_bound(worksheet_path, EXPECTED_WORKSHEET_SHA256)
    if packet.get("sample") != "holdout":
        raise ValueError("coverage input is not the frozen holdout")
    if packet.get("membership_sha256") != EXPECTED_MEMBERSHIP_SHA256:
        raise ValueError("holdout membership changed")
    report = measure(packet, worksheet)
    report["source"] = {
        "packet_sha256": EXPECTED_PACKET_SHA256,
        "worksheet_sha256": EXPECTED_WORKSHEET_SHA256,
        "membership_sha256": EXPECTED_MEMBERSHIP_SHA256,
        "games": 42,
        "holdout_opened": True,
        "one_time_evaluation": True,
        "frozen_adjudicator_source_commit": (
            "76a411306b0066b4e585f6f23f2d0df8a7306e7e"
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--worksheet", type=Path, default=DEFAULT_WORKSHEET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.packet, args.worksheet)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
