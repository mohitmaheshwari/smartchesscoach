#!/usr/bin/env python3
"""Measure reusable teaching-family gaps after the blind review is frozen.

This is an offline evidence join. It does not detect new chess facts, run an
engine, call a model, read a database, or authorize player-facing content.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


SCHEMA_VERSION = "deterministic_teaching_intelligence_opportunity_report.v1"
BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_development_packet_v1.json"
)
DEFAULT_REVIEW = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_codex_complete_game_review_v1.json"
)
DEFAULT_BASELINE = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_system_baseline_v1.json"
)
DEFAULT_COVERAGE = (
    BACKEND
    / "data/detector_gold/deterministic_teaching_intelligence_current_coverage_adjudication_v1.json"
)
EXPECTED_SHA256 = {
    "packet": "b9d912b1cc72fb1c928c576a70baf1b982e0cdbe08e28eb01e8a55915948af91",
    "review": "ae933d3445ab4a4057ea6bb5b9ecad780b191ab4fa7eccb5787a0d051af504b6",
    "baseline": "0bd15422c57742133701376d46c0cd2a2ab5194170890232897995bbf0692c60",
    "coverage": "a6d16a4ad3bb57d2e769d55e8e883f4f4882751e28e3c16e74499603bbd758ae",
}

# Research feasibility only. These entries choose which canonical proof assets
# could prove a family; they are not runtime knowledge or authorization.
PROOF_FEASIBILITY = {
    "back_rank_geometry": ("high", ["python-chess legal geometry", "stored mate line"]),
    "clean_or_positive_play": ("medium", ["stored best line", "causal fact", "independent recognition guard"]),
    "countercheck_or_forcing_defense": ("high", ["legal reply set", "stored played and best lines"]),
    "defensive_remove_attacker": ("high", ["legal capture", "threat removal", "stored continuation"]),
    "exact_endgame": ("medium", ["canonical exact-ending source", "tablebase where eligible"]),
    "forced_mate_story": ("high", ["stored mate score", "legal mate replay", "story deduplication"]),
    "forcing_pawn_tempo": ("high", ["attack map before and after", "stored continuation"]),
    "fork_or_double_attack_geometry": ("high", ["exact target identities", "settled material payoff"]),
    "king_safety_commitment": ("medium", ["legal forcing replies", "stored mate or material consequence"]),
    "known_trap_or_mating_pattern": ("high", ["canonical trap registry", "exact legal sequence"]),
    "multi_move_material_accounting": ("high", ["stored_line_verifier.v4", "settled material payoff"]),
    "opening_purpose": ("medium", ["canonical opening identity", "legal consequence fact"]),
    "passed_pawn_race": ("high", ["promotion distance", "legal stopping moves", "exact ending where eligible"]),
    "pin_xray_or_line_geometry": ("high", ["python-chess attack rays", "exact target identities"]),
    "promotion_choice": ("high", ["legal promotion set", "stored mate or exact-ending result"]),
    "queen_safety_or_greedy_capture": ("high", ["legal reply set", "settled material payoff"]),
    "rook_activity_coordination": ("medium", ["legal rook mobility", "concrete stored consequence"]),
    "unpunished_opponent_opportunity": ("high", ["opponent best line", "played-line divergence", "causal fact"]),
    "zwischenzug_or_move_order": ("high", ["legal intermediate move", "settled branch comparison"]),
}
FEASIBILITY_RANK = {"medium": 1, "high": 2}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound(path: Path, expected_sha256: str) -> Any:
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"frozen evidence hash mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _evidence_by_ply(game: Mapping[str, Any]) -> Dict[int, Mapping[str, Any]]:
    result = {}
    for row in game.get("stored_engine_evidence") or []:
        ply = int(row["ply"])
        if ply in result:
            raise ValueError("duplicate stored evidence ply")
        result[ply] = row
    return result


def _is_high_consequence(rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(
        bool(row.get("is_critical"))
        or int(row.get("cp_loss") or 0) >= 300
        or bool(row.get("mate_info"))
        for row in rows
    )


def _pareto_front(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    dimensions = (
        "uncovered_opportunities",
        "uncovered_players",
        "confirmed_high_consequence_uncovered",
        "feasibility_rank",
    )
    winners = []
    for candidate in rows:
        dominated = False
        for other in rows:
            if other is candidate:
                continue
            no_worse = all(other[key] >= candidate[key] for key in dimensions)
            strictly_better = any(other[key] > candidate[key] for key in dimensions)
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            winners.append(str(candidate["family"]))
    return winners


def measure(
    packet: Mapping[str, Any],
    review: Mapping[str, Any],
    baseline: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> Dict[str, Any]:
    packet_games = list(packet.get("games") or [])
    review_rows = list(review.get("game_reviews") or [])
    baseline_games = list(baseline.get("games") or [])
    if not (
        len(packet_games) == len(review_rows) == len(baseline_games) == 100
    ):
        raise ValueError("development comparison must contain exactly 100 games")
    packet_keys = [str(game["anonymous_game_key"]) for game in packet_games]
    if packet_keys != [str(row["anonymous_game_key"]) for row in review_rows]:
        raise ValueError("review membership or order differs from packet")
    if packet_keys != [str(game["anonymous_game_key"]) for game in baseline_games]:
        raise ValueError("system baseline membership or order differs from packet")

    covered = {
        (int(item["review_index"]), str(item["family"]))
        for item in coverage.get("covered_family_occurrences") or []
    }
    if len(covered) != len(coverage.get("covered_family_occurrences") or []):
        raise ValueError("duplicate covered family occurrence")

    family_games: Counter[str] = Counter()
    family_players: dict[str, set[str]] = defaultdict(set)
    family_uncovered_games: Counter[str] = Counter()
    family_uncovered_players: dict[str, set[str]] = defaultdict(set)
    family_confirmed_high: Counter[str] = Counter()
    family_confirmed_high_uncovered: Counter[str] = Counter()
    family_consequence_complete: Counter[str] = Counter()
    family_consequence_partial: Counter[str] = Counter()
    family_consequence_absent: Counter[str] = Counter()
    candidate_ply_count = 0
    candidate_ply_evidence_count = 0
    occurrence_identities = set()
    occurrence_records = []
    for source, reviewed in zip(packet_games, review_rows):
        if int(reviewed["review_index"]) < 1:
            raise ValueError("invalid review index")
        evidence = _evidence_by_ply(source)
        candidate_plies = [int(ply) for ply in reviewed["candidate_plies"]]
        candidate_rows = [evidence[ply] for ply in candidate_plies if ply in evidence]
        candidate_ply_count += len(candidate_plies)
        candidate_ply_evidence_count += len(candidate_rows)
        if len(candidate_rows) == len(candidate_plies):
            consequence_evidence_state = "complete"
        elif candidate_rows:
            consequence_evidence_state = "partial"
        else:
            consequence_evidence_state = "absent"
        confirmed_high = _is_high_consequence(candidate_rows)
        player = str(source["anonymous_player_key"])
        for family in reviewed["required_families"]:
            family = str(family)
            identity = (int(reviewed["review_index"]), family)
            if identity in occurrence_identities:
                raise ValueError("duplicate reviewed family occurrence")
            occurrence_identities.add(identity)
            occurrence_records.append({
                "identity": identity,
                "family": family,
                "player": player,
                "covered": identity in covered,
                "confirmed_high": confirmed_high,
            })
            family_games[family] += 1
            family_players[family].add(player)
            if consequence_evidence_state == "complete":
                family_consequence_complete[family] += 1
            elif consequence_evidence_state == "partial":
                family_consequence_partial[family] += 1
            else:
                family_consequence_absent[family] += 1
            if confirmed_high:
                family_confirmed_high[family] += 1
            if identity not in covered:
                family_uncovered_games[family] += 1
                family_uncovered_players[family].add(player)
                if confirmed_high:
                    family_confirmed_high_uncovered[family] += 1
    if not covered <= occurrence_identities:
        raise ValueError("coverage adjudication refers to an unknown family occurrence")

    family_rows = []
    for family in sorted(family_games):
        feasibility, assets = PROOF_FEASIBILITY[family]
        total = family_games[family]
        current = total - family_uncovered_games[family]
        family_rows.append({
            "family": family,
            "opportunities": total,
            "players": len(family_players[family]),
            "current_causal_coverage": current,
            "current_causal_coverage_pct": round(100.0 * current / total, 2),
            "uncovered_opportunities": family_uncovered_games[family],
            "uncovered_players": len(family_uncovered_players[family]),
            "confirmed_high_consequence_opportunities": family_confirmed_high[family],
            "confirmed_high_consequence_uncovered": family_confirmed_high_uncovered[family],
            "consequence_evidence_complete": family_consequence_complete[family],
            "consequence_evidence_partial": family_consequence_partial[family],
            "consequence_evidence_absent": family_consequence_absent[family],
            "proof_feasibility": feasibility,
            "feasibility_rank": FEASIBILITY_RANK[feasibility],
            "canonical_proof_assets": assets,
        })

    def ranked(keys: Sequence[str]) -> list[str]:
        return [
            str(row["family"])
            for row in sorted(
                family_rows,
                key=lambda row: tuple(-int(row[key]) for key in keys)
                + (str(row["family"]),),
            )
        ]

    frequency_first = ranked(("uncovered_opportunities", "uncovered_players"))
    player_reach_first = ranked(("uncovered_players", "uncovered_opportunities"))
    safety_first = ranked((
        "feasibility_rank",
        "confirmed_high_consequence_uncovered",
        "uncovered_players",
        "uncovered_opportunities",
    ))
    pareto_front = _pareto_front(family_rows)
    rows_by_family = {str(row["family"]): row for row in family_rows}
    candidate_bundles = {
        "pareto_first": set(pareto_front),
        "high_feasibility_reach_floor": {
            family
            for family, row in rows_by_family.items()
            if row["proof_feasibility"] == "high"
            and int(row["uncovered_opportunities"]) >= 8
            and int(row["uncovered_players"]) >= 7
        },
        "frequency_top_8": set(frequency_first[:8]),
        "all_high_feasibility": {
            family
            for family, row in rows_by_family.items()
            if row["proof_feasibility"] == "high"
        },
        "all_families": set(rows_by_family),
    }

    def bundle_result(families: set[str]) -> Dict[str, Any]:
        uncovered = [
            row
            for row in occurrence_records
            if not row["covered"] and row["family"] in families
        ]
        return {
            "families": sorted(families),
            "family_count": len(families),
            "uncovered_opportunities": len(uncovered),
            "unique_games": len({row["identity"][0] for row in uncovered}),
            "unique_players": len({row["player"] for row in uncovered}),
            "confirmed_high_consequence_uncovered": sum(
                bool(row["confirmed_high"]) for row in uncovered
            ),
            "maximum_visible_coverage_if_all_prove": len(covered) + len(uncovered),
            "maximum_visible_coverage_pct_if_all_prove": round(
                100.0 * (len(covered) + len(uncovered)) / len(occurrence_identities),
                2,
            ),
        }

    system_moves = [
        move
        for game in baseline_games
        for move in game["system_baseline"]["moves"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "measured_not_authorized",
        "sources": dict(EXPECTED_SHA256),
        "execution_contract": {
            "database_reads": 0,
            "database_writes": 0,
            "engine_runs": 0,
            "model_calls": 0,
            "holdout_opened": False,
            "player_facing_authorization": False,
        },
        "current_product_reach": {
            "games": len(baseline_games),
            "stored_move_captions": sum(bool(move.get("caption")) for move in system_moves),
            "stored_caption_explanations": sum(bool(move.get("caption_explanation")) for move in system_moves),
            "stored_teachable_events": sum(bool(move.get("teachable_event")) for move in system_moves),
            "games_with_stored_whole_game_plan": sum(
                game["system_baseline"].get("stored_plan") is not None
                for game in baseline_games
            ),
        },
        "summary": {
            "reviewed_games": len(review_rows),
            "games_with_candidate_teaching": sum(
                row["disposition"] != "honest_no_strong_lesson"
                for row in review_rows
            ),
            "honest_no_strong_lesson_games": sum(
                row["disposition"] == "honest_no_strong_lesson"
                for row in review_rows
            ),
            "family_occurrences": len(occurrence_identities),
            "candidate_plies": candidate_ply_count,
            "candidate_plies_with_stored_engine_evidence": candidate_ply_evidence_count,
            "candidate_plies_without_stored_engine_evidence": (
                candidate_ply_count - candidate_ply_evidence_count
            ),
            "current_causally_covered_occurrences": len(covered),
            "current_causal_coverage_pct": round(
                100.0 * len(covered) / len(occurrence_identities), 2
            ),
            "uncovered_family_occurrences": len(occurrence_identities) - len(covered),
        },
        "families": family_rows,
        "policy_comparison": {
            "frequency_first": frequency_first,
            "player_reach_first": player_reach_first,
            "safety_and_feasibility_first": safety_first,
            "balanced_pareto_front": pareto_front,
            "balanced_definition": (
                "Non-dominated across uncovered opportunity count, uncovered "
                "player reach, confirmed high-consequence uncovered count, and proof "
                "feasibility. No hidden weighted score is used."
            ),
        },
        "candidate_bundle_comparison": {
            name: bundle_result(families)
            for name, families in candidate_bundles.items()
        },
    }


def build_report(
    packet_path: Path = DEFAULT_PACKET,
    review_path: Path = DEFAULT_REVIEW,
    baseline_path: Path = DEFAULT_BASELINE,
    coverage_path: Path = DEFAULT_COVERAGE,
) -> Dict[str, Any]:
    packet = _load_bound(packet_path, EXPECTED_SHA256["packet"])
    review = _load_bound(review_path, EXPECTED_SHA256["review"])
    baseline = _load_bound(baseline_path, EXPECTED_SHA256["baseline"])
    coverage = _load_bound(coverage_path, EXPECTED_SHA256["coverage"])
    return measure(packet, review, baseline, coverage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.packet, args.review, args.baseline, args.coverage)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
