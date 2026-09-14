"""Measure the four locked teaching families on the frozen 100-game set.

Offline only: no database, engine, model, identity, holdout, or production
write. The output is development evidence, never a promotion packet.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.caption_facts import (
    TEACHING_OPPORTUNITY_PROOF_VERSION,
    TEACHING_OPPORTUNITY_QUALITY_IDS,
    build_verified_line_cause,
    build_verified_teaching_opportunities,
)
from services.caption_pipeline import build_teaching_opportunity_comparisons
from services.detector_quality import QualitySurface, is_authorized
from services.game_review_planner import build_teaching_opportunity_shadow_summary


DEFAULT_PACKET = BACKEND / (
    "data/detector_gold/"
    "deterministic_teaching_intelligence_development_packet_v1.json"
)
DEFAULT_REVIEW = BACKEND / (
    "data/detector_gold/"
    "deterministic_teaching_intelligence_codex_complete_game_review_v1.json"
)
DEFAULT_OUTPUT = BACKEND / (
    "data/corpus_snapshots/"
    "deterministic_teaching_opportunity_family_measurement_v3_2026-09-14.json"
)
SCHEMA_VERSION = "deterministic_teaching_opportunity_measurement.v2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source_evidence_fingerprint(row: Mapping[str, Any]) -> str:
    payload = {
        key: row.get(key)
        for key in (
            "fen_before",
            "played_san",
            "best_move_san",
            "pv_after_played",
            "pv_after_best",
            "cp_loss",
            "actor",
            "ply",
        )
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _compact_fact(opportunity) -> Dict[str, Any]:
    """Keep the exact claim identity without repeating its full branch traces."""
    fact = opportunity.contract_dict()
    fact.pop("cause", None)
    return fact


def build_report(
    packet: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    packet_sha256: str,
    review_sha256: str,
) -> Dict[str, Any]:
    games = packet.get("games")
    review_rows = review.get("game_reviews")
    if (
        packet.get("schema_version")
        != "deterministic_teaching_intelligence_evidence.v1"
        or not isinstance(games, list)
        or len(games) != 100
        or not isinstance(review_rows, list)
        or len(review_rows) != 100
        or review.get("source_packet_sha256") != packet_sha256
    ):
        raise ValueError("frozen development evidence binding is invalid")

    reviews_by_game = {
        str(row.get("anonymous_game_key") or ""): row
        for row in review_rows
        if isinstance(row, Mapping)
    }
    if set(reviews_by_game) != {
        str(game.get("anonymous_game_key") or "")
        for game in games
        if isinstance(game, Mapping)
    }:
        raise ValueError("review and packet memberships disagree")

    statuses = Counter()
    raw_family_counts = Counter()
    deduplicated_family_counts = Counter()
    detected_games_by_family = defaultdict(set)
    candidates = []

    for game in games:
        game_key = str(game.get("anonymous_game_key") or "")
        player_key = str(game.get("anonymous_player_key") or "")
        evidence_rows = game.get("stored_engine_evidence") or []
        raw_game_candidates = []
        for row in evidence_rows:
            if not isinstance(row, Mapping):
                statuses["invalid_row"] += 1
                continue
            required = (
                "fen_before",
                "played_san",
                "best_move_san",
                "pv_after_played",
                "pv_after_best",
                "cp_loss",
                "actor",
                "ply",
            )
            if any(row.get(key) in (None, "") for key in required):
                statuses["missing_stored_evidence"] += 1
                continue
            cause = build_verified_line_cause(
                fen_before=str(row["fen_before"]),
                played_san=str(row["played_san"]),
                best_move_san=str(row["best_move_san"]),
                pv_after_played=tuple(row.get("pv_after_played") or ()),
                pv_after_best=tuple(row.get("pv_after_best") or ()),
                cp_loss=int(row.get("cp_loss") or 0),
                include_branch_evidence=True,
            )
            if cause is None:
                statuses["not_proved"] += 1
                continue
            opportunities = build_verified_teaching_opportunities(
                fen_before=str(row["fen_before"]),
                mover_is_user=(str(row.get("actor")) == "player"),
                cause=cause,
            )
            if not opportunities:
                statuses["proved_other_family"] += 1
                continue
            comparisons = build_teaching_opportunity_comparisons(opportunities)
            by_fingerprint = {
                item.opportunity_fingerprint: item for item in comparisons
            }
            for opportunity in opportunities:
                comparison = by_fingerprint.get(opportunity.fingerprint)
                if comparison is None:
                    statuses["render_abstained"] += 1
                    continue
                raw_family_counts[opportunity.family] += 1
                comparison_contract = comparison.contract_dict()
                comparison_contract["source_ply"] = int(row["ply"])
                raw_game_candidates.append({
                    "anonymous_game_key": game_key,
                    "anonymous_player_key": player_key,
                    "rating_band": game.get("rating_band"),
                    "ply": int(row["ply"]),
                    "fen_before": row["fen_before"],
                    "actor": row["actor"],
                    "played_san": row["played_san"],
                    "best_move_san": row["best_move_san"],
                    "cp_loss": int(row["cp_loss"]),
                    "is_critical": bool(row.get("is_critical")),
                    "source_evidence_fingerprint": (
                        _source_evidence_fingerprint(row)
                    ),
                    "fact": _compact_fact(opportunity),
                    "comparison": comparison_contract,
                })

        shadow_summary = build_teaching_opportunity_shadow_summary(
            tuple(item["comparison"] for item in raw_game_candidates)
        )
        accepted_fingerprints = {
            str(item.get("opportunity_fingerprint") or "")
            for item in shadow_summary["candidates"]
        }
        statuses["deduplicated_story"] += shadow_summary["deduplicated_count"]
        for candidate in raw_game_candidates:
            fingerprint = str(candidate["fact"].get("fingerprint") or "")
            if fingerprint not in accepted_fingerprints:
                continue
            family = str(candidate["fact"]["family"])
            statuses["candidate"] += 1
            deduplicated_family_counts[family] += 1
            detected_games_by_family[family].add(game_key)
            candidates.append(candidate)

    required_games_by_family = {
        family: {
            game_key
            for game_key, row in reviews_by_game.items()
            if family in (row.get("required_families") or [])
        }
        for family in TEACHING_OPPORTUNITY_QUALITY_IDS
    }
    development_alignment = {}
    for family in TEACHING_OPPORTUNITY_QUALITY_IDS:
        required = required_games_by_family[family]
        detected = detected_games_by_family[family]
        development_alignment[family] = {
            "review_required_games": len(required),
            "detected_games": len(detected),
            "required_and_detected": len(required & detected),
            "review_required_but_not_detected": sorted(required - detected),
            "detected_outside_review_family": sorted(detected - required),
            "interpretation": "development diagnosis only; not a precision verdict",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "development_shadow_evidence_only",
        "sources": {
            "development_packet_sha256": packet_sha256,
            "complete_game_review_sha256": review_sha256,
            "membership_sha256": packet.get("membership_sha256"),
        },
        "execution_contract": {
            "games": len(games),
            "database_reads": 0,
            "database_writes": 0,
            "engine_runs": 0,
            "model_calls": 0,
            "holdout_opened": False,
            "player_visible_authorizations_changed": False,
            "promotion_packet": False,
        },
        "summary": {
            "proof_version": TEACHING_OPPORTUNITY_PROOF_VERSION,
            "comparison_schema_version": "teaching_opportunity_comparison.v2",
            "shadow_summary_schema_version": (
                "teaching_opportunity_shadow_summary.v2"
            ),
            "positions_seen": sum(
                len(game.get("stored_engine_evidence") or [])
                for game in games
            ),
            "candidate_count": len(candidates),
            "games_with_candidate": len({
                item["anonymous_game_key"] for item in candidates
            }),
            "players_with_candidate": len({
                item["anonymous_player_key"] for item in candidates
            }),
            "status_counts": dict(sorted(statuses.items())),
            "raw_family_counts": {
                family: raw_family_counts[family]
                for family in TEACHING_OPPORTUNITY_QUALITY_IDS
            },
            "deduplicated_family_counts": {
                family: deduplicated_family_counts[family]
                for family in TEACHING_OPPORTUNITY_QUALITY_IDS
            },
            "caption_authorized_family_count": sum(
                int(is_authorized(quality_id, QualitySurface.CAPTION))
                for quality_id in TEACHING_OPPORTUNITY_QUALITY_IDS.values()
            ),
        },
        "development_alignment": development_alignment,
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    packet_path = args.packet.resolve()
    review_path = args.review.resolve()
    report = build_report(
        _load(packet_path),
        _load(review_path),
        packet_sha256=_sha256(packet_path),
        review_sha256=_sha256(review_path),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
