"""Read-only measurement report for PWC V2 shadow conductor packets.

This script does not choose a winning policy and never writes to MongoDB. Its
job is to establish whether the captured evidence is structurally comparable
and to export disagreement cases for human chess review.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from typing import Any, Iterable, Mapping

from coach_play.v2.shadow_conductor import (
    SHADOW_POLICIES,
    SHADOW_POLICY_VERSION,
    SHADOW_SCHEMA_VERSION,
)


def _rating_band(rating: Any) -> str:
    from services.rating_resolver import get_rating_band

    try:
        return get_rating_band(int(rating or 1200))
    except (TypeError, ValueError):
        return get_rating_band(1200)


def _increment(counter: Counter[str], value: Any) -> None:
    label = str(value or "unknown").strip() or "unknown"
    counter[label] += 1


def summarize_shadow_sessions(
    sessions: Iterable[Mapping[str, Any]],
    *,
    example_limit: int = 25,
) -> dict[str, Any]:
    """Summarize persisted packets without deciding any numeric release gate."""
    session_count = 0
    packet_count = 0
    candidate_count = 0
    rejected_count = 0
    multi_candidate_packets = 0
    disagreement_count = 0
    zero_candidate_packets = 0
    invariant_violations: list[dict[str, Any]] = []
    disagreement_examples: list[dict[str, Any]] = []
    candidate_sources: Counter[str] = Counter()
    candidate_categories: Counter[str] = Counter()
    rejection_reasons: Counter[str] = Counter()
    packets_by_rating_band: Counter[str] = Counter()
    policy_winners: dict[str, Counter[str]] = {
        policy: Counter() for policy in SHADOW_POLICIES
    }
    policy_ties: Counter[str] = Counter()
    adapter_statuses: Counter[str] = Counter()

    for session in sessions:
        session_had_packet = False
        session_id = str(session.get("session_id") or "unknown")
        rating_band = _rating_band(session.get("user_rating"))
        for decision in session.get("coaching_decisions") or []:
            packet = decision.get("pwc_v2_shadow")
            if not isinstance(packet, Mapping):
                continue
            session_had_packet = True
            packet_count += 1
            packets_by_rating_band[rating_band] += 1

            candidates = packet.get("candidates") or []
            rejected = packet.get("rejected") or []
            policies = packet.get("policies") or {}
            candidate_ids = {
                str(candidate.get("candidate_id"))
                for candidate in candidates
                if candidate.get("candidate_id")
            }
            candidate_count += len(candidates)
            rejected_count += len(rejected)
            if len(candidates) == 0:
                zero_candidate_packets += 1
            if len(candidates) > 1:
                multi_candidate_packets += 1

            for candidate in candidates:
                _increment(candidate_sources, candidate.get("source"))
                _increment(candidate_categories, candidate.get("category"))
            for item in rejected:
                for reason in item.get("reasons") or []:
                    _increment(rejection_reasons, reason)
            for observation in packet.get("adapter_observations") or []:
                if not isinstance(observation, Mapping):
                    continue
                adapter = str(observation.get("adapter") or "unknown")
                status = str(observation.get("status") or "unknown")
                _increment(adapter_statuses, f"{adapter}:{status}")

            violations = []
            if packet.get("schema_version") != SHADOW_SCHEMA_VERSION:
                violations.append("schema_version_mismatch")
            if packet.get("policy_version") != SHADOW_POLICY_VERSION:
                violations.append("policy_version_mismatch")
            if packet.get("player_visible") is not False:
                violations.append("player_visible_not_false")
            if packet.get("candidate_count") != len(candidates):
                violations.append("candidate_count_mismatch")
            if packet.get("rejected_count") != len(rejected):
                violations.append("rejected_count_mismatch")
            if set(policies) != set(SHADOW_POLICIES):
                violations.append("policy_set_mismatch")

            winners: dict[str, Any] = {}
            for policy in SHADOW_POLICIES:
                policy_result = policies.get(policy) or {}
                winner_id = policy_result.get("winner_candidate_id")
                tied_ids = policy_result.get("tied_candidate_ids") or []
                winners[policy] = winner_id
                _increment(policy_winners[policy], winner_id or "silence")
                if winner_id is not None and winner_id not in candidate_ids:
                    violations.append(f"unknown_winner:{policy}")
                if any(candidate_id not in candidate_ids for candidate_id in tied_ids):
                    violations.append(f"unknown_tied_candidate:{policy}")
                measured_tie = len(tied_ids) > 1
                if bool(policy_result.get("tie")) != measured_tie:
                    violations.append(f"tie_flag_mismatch:{policy}")
                if measured_tie:
                    policy_ties[policy] += 1

            measured_disagreement = (
                len({winner for winner in winners.values() if winner is not None}) > 1
            )
            if bool(packet.get("disagreement")) != measured_disagreement:
                violations.append("disagreement_flag_mismatch")
            if measured_disagreement:
                disagreement_count += 1
                if len(disagreement_examples) < max(0, example_limit):
                    disagreement_examples.append(
                        {
                            "session_id": session_id,
                            "move_key": decision.get("move_key"),
                            "created_at": packet.get("created_at"),
                            "rating_band": rating_band,
                            "winners": winners,
                            "candidates": candidates,
                        }
                    )
            if violations:
                invariant_violations.append(
                    {
                        "session_id": session_id,
                        "move_key": decision.get("move_key"),
                        "violations": violations,
                    }
                )

        if session_had_packet:
            session_count += 1

    return {
        "report_version": "pwc_v2_shadow_report.v1",
        "measurement_only": True,
        "conductor_choice_authorized": False,
        "sessions": session_count,
        "packets": packet_count,
        "candidates": candidate_count,
        "rejected_candidates": rejected_count,
        "zero_candidate_packets": zero_candidate_packets,
        "multi_candidate_packets": multi_candidate_packets,
        "comparison_possible": (
            multi_candidate_packets > 0 and not invariant_violations
        ),
        "disagreements": disagreement_count,
        "candidate_sources": dict(candidate_sources.most_common()),
        "candidate_categories": dict(candidate_categories.most_common()),
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "adapter_statuses": dict(adapter_statuses.most_common()),
        "packets_by_rating_band": dict(packets_by_rating_band.most_common()),
        "policy_winners": {
            policy: dict(winners.most_common())
            for policy, winners in policy_winners.items()
        },
        "policy_ties": dict(policy_ties.most_common()),
        "invariant_violation_count": len(invariant_violations),
        "invariant_violations": invariant_violations,
        "disagreement_examples": disagreement_examples,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--examples", type=int, default=25)
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise SystemExit("MONGO_URL is required; this report never guesses a database")

    from pymongo import MongoClient

    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10_000)
    query = {"coaching_decisions.pwc_v2_shadow": {"$exists": True}}
    projection = {
        "_id": 0,
        "session_id": 1,
        "user_rating": 1,
        "coaching_decisions.move_key": 1,
        "coaching_decisions.pwc_v2_shadow": 1,
    }
    try:
        cursor = client[db_name].coach_sessions.find(query, projection)
        if args.limit > 0:
            cursor = cursor.limit(args.limit)
        report = summarize_shadow_sessions(cursor, example_limit=args.examples)
    finally:
        client.close()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
