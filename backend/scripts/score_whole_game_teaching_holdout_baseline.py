#!/usr/bin/env python3
"""Score the frozen whole-game candidate against the stored caption baseline.

The chess gold was frozen before the identity-free legacy captions were
exported.  This scorer contains the post-reveal semantic adjudication only; it
does not call a database, chess engine, model, or product runtime.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Dict, Mapping, Tuple


SCHEMA_VERSION = "whole_game_teaching_review_holdout_baseline_score.v1"
BACKEND = Path(__file__).resolve().parents[1]
WORKSHEET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_worksheet_v1.json"
)
CANDIDATE_COVERAGE = (
    BACKEND
    / "data/corpus_snapshots/whole_game_teaching_review_holdout_fact_coverage_v1_2026-09-13.json"
)
BASELINE = (
    BACKEND
    / "data/corpus_snapshots/whole_game_teaching_review_holdout_baseline_comparison_v1_2026-09-13.json"
)
DEFAULT_OUTPUT = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_holdout_baseline_adjudication_v1.json"
)

EXPECTED_WORKSHEET_SHA256 = (
    "adefb7104e7c48639f1f7c50064a3a3d14c71c4c2e5c11af6f09dc7927ca6a17"
)
EXPECTED_CANDIDATE_COVERAGE_SHA256 = (
    "df5b564ee852058176924d810360c98b3dc335fbe593bf85710da09c9af11c26"
)
EXPECTED_BASELINE_SHA256 = (
    "f4a08f9131a55b014e07a6bc24ed36f9d7ba7c4a4ab5ec4e2eec4731be0f4ca5"
)
EXPECTED_MEMBERSHIP_SHA256 = (
    "87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b"
)
BOOTSTRAP_SEED = 20260913
BOOTSTRAP_DRAWS = 200_000
COVERED_DISPOSITIONS = {"exact_match", "causal_equivalent"}

Identity = Tuple[str, int]


def _i(game_key: str, ply: int) -> Identity:
    return game_key, ply


# Every non-default judgment is named by its opaque game signature and ply.
# All other rows were manually read and judged exact matches.  This is safer
# than matching caption phrases in code: wording changes cannot alter a frozen
# verdict silently.
MANUAL_DISPOSITIONS: Dict[Identity, Tuple[str, str]] = {
    _i("3bbb6c0f290749a4b364766a63e61fac9495014ce12d40ef3e5d378e3b7a1560", 37): (
        "causal_equivalent", "Names Bxd4+ as the direct punishment without naming the captured knight."
    ),
    _i("0c3a26902f90ec257c3d5b4392d501dbe864e6db3338dfbfb14ee59368393c78", 32): (
        "causal_equivalent", "Names Rxg6 as the reply and resulting attack without the pawn wording."
    ),
    _i("0c3a26902f90ec257c3d5b4392d501dbe864e6db3338dfbfb14ee59368393c78", 38): (
        "causal_equivalent", "Names Qxh5+ as the reply and resulting attack without the pawn wording."
    ),
    _i("5c6e9669daaa583e0f3fe768f06eb4b3a8462825c6938d574e2a13c08ee0c736", 75): (
        "causal_equivalent", "Names Rxa2+ as the direct punishment without naming the captured pawn."
    ),
    _i("5c6e9669daaa583e0f3fe768f06eb4b3a8462825c6938d574e2a13c08ee0c736", 109): (
        "causal_equivalent", "Names gxf4+ as the direct punishment without repeating that the queen falls."
    ),
    _i("92709c8afefd190b07d1362c35b12ebddf0f6077fc6e8ba5791ddc22f26273f6", 65): (
        "causal_equivalent", "Correctly translates the opponent's mistake into a mating chance for the player."
    ),
    _i("3345e0ead087b90cd5572544b5ef6be2acd7fd52290b08963378751936d2762f", 73): (
        "causal_equivalent", "Names Kxf2 and the stronger fork consequence rather than only the pawn capture."
    ),
    _i("e25d3a266aad000304bd9cf3a812657f5e46e9fcdd6d8a7e667873bf49129c81", 24): (
        "causal_equivalent", "Explains Bxa6 taking the knight as a trade."
    ),
    _i("add76725f266e91f280bb3dfa5e3e446805ce817023efbd0498548752e795839", 23): (
        "causal_equivalent", "Names Bxc3+ as the reply and resulting attack without the pawn wording."
    ),
    _i("1018555d46ea0bde193430c14f106e608512dcdfe186d4036c16c72b9315dadc", 57): (
        "causal_equivalent", "Correctly translates the opponent's mistake into a mating chance for the player."
    ),
    _i("6b9635a46dfbe64f5fe0da2f7f49bf29d2fda478a29a7976eb382e230ae41457", 63): (
        "causal_equivalent", "Names Rxg2+ as the direct punishment without naming the captured pawn."
    ),
    _i("6b9635a46dfbe64f5fe0da2f7f49bf29d2fda478a29a7976eb382e230ae41457", 105): (
        "causal_equivalent", "Names Rxd1+, the pinned rook, and the resulting attack."
    ),
    _i("781bde6c39387bf05bb86fe7637ef451ce29ca21404dd7df9059fe53283d6dca", 64): (
        "causal_equivalent", "Names Rxh6+ as the direct punishment without naming the captured pawn."
    ),
    _i("d4b0907c9b4e2b579af1b67b505c78e83033eb2a11ada3573a77a7436f64ea69", 28): (
        "causal_equivalent", "Names Nxb6 and the stronger fork consequence rather than only the bishop capture."
    ),
    _i("c3e4e24b85474f5cddf8ee9786d24044d1a2204699f1496f0f71101bf7f511d3", 19): (
        "causal_equivalent", "Correctly translates the opponent's mistake into a mating chance for the player."
    ),
    _i("3c3ee087973f68ec21b9406afd224b902179cb8a61603232484d117f26a604b4", 59): (
        "same_move_wrong_reason", "Discusses dxc6 but omits the proved Nxd5 reply."
    ),
    _i("92709c8afefd190b07d1362c35b12ebddf0f6077fc6e8ba5791ddc22f26273f6", 68): (
        "same_move_wrong_reason", "Describes defending against mate instead of the proved chance to deliver mate."
    ),
    _i("92709c8afefd190b07d1362c35b12ebddf0f6077fc6e8ba5791ddc22f26273f6", 80): (
        "same_move_wrong_reason", "Describes defending against mate instead of the proved chance to deliver mate."
    ),
    _i("50750664ca85335327ece779c45adff36efb703d537cac3c47b65b96666c95cd", 70): (
        "verified_fact_not_wired", "Calls the queen isolated but omits the immediate Qxg4 capture."
    ),
    _i("c2207ffe78ff530485ee82b1a524ebcde1b79abd3249e8591551d3e70268cc0e", 57): (
        "detector_miss", "Reports severity and an alternative without the proved Nxf2+ consequence."
    ),
    _i("c2207ffe78ff530485ee82b1a524ebcde1b79abd3249e8591551d3e70268cc0e", 62): (
        "same_move_wrong_reason", "Treats Rf1+ as an ordinary check and omits that Rxf1 captures the rook."
    ),
    _i("3345e0ead087b90cd5572544b5ef6be2acd7fd52290b08963378751936d2762f", 18): (
        "detector_miss", "Reports severity but gives no proved Nxc6 consequence."
    ),
    _i("e25d3a266aad000304bd9cf3a812657f5e46e9fcdd6d8a7e667873bf49129c81", 12): (
        "same_move_wrong_reason", "Discusses axb6 rather than the proved bxa7 reply."
    ),
    _i("e25d3a266aad000304bd9cf3a812657f5e46e9fcdd6d8a7e667873bf49129c81", 38): (
        "same_move_wrong_reason", "Names Qxh6 but explains a later pawn attack instead of the free bishop."
    ),
    _i("955ab584ed073551caf90c0f2989eee747d96927be4e23cf3fe7790c507f49c0", 13): (
        "detector_miss", "Names a stronger move but omits the proved Bxd4 response."
    ),
    _i("955ab584ed073551caf90c0f2989eee747d96927be4e23cf3fe7790c507f49c0", 26): (
        "same_move_wrong_reason", "Treats Nd3+ as an ordinary check and omits Bxd3."
    ),
    _i("add76725f266e91f280bb3dfa5e3e446805ce817023efbd0498548752e795839", 5): (
        "same_move_wrong_reason", "Praises the pin while the proved reply Qxg5 wins the bishop."
    ),
    _i("1018555d46ea0bde193430c14f106e608512dcdfe186d4036c16c72b9315dadc", 39): (
        "same_move_wrong_reason", "Discusses Bxe5 rather than the proved hxg3 response."
    ),
    _i("0ee4ea13c0f0aa45abda696fd49016f0dcfb90960f5f19593ab96ef035239775", 62): (
        "same_move_wrong_reason", "Describes defending against mate instead of the proved chance to deliver mate."
    ),
    _i("0093cf71a378f8f4a8aae087825e9a8f4e5ef2d6b0bf6cf5dcc1dae0ba63db53", 28): (
        "verified_fact_not_wired", "Hints that the rook is in danger but never explains that Bxb8 takes it."
    ),
    _i("0093cf71a378f8f4a8aae087825e9a8f4e5ef2d6b0bf6cf5dcc1dae0ba63db53", 41): (
        "missing_concept_candidate", "Notices check but omits the proved double attack on king and knight."
    ),
    _i("963834dfc152682baeb573e27107f6ef2f94297903123dbdd46149b61515ca08", 47): (
        "same_move_wrong_reason", "Praises Bxe4 while the proved reply Nxe5 wins the knight."
    ),
    _i("ead9426dce0fccb963140080dcc4245fbfa8ea6abf9f242db96c546bda591261", 24): (
        "detector_miss", "Reports severity but gives no proved Rxf2 response."
    ),
    _i("ead9426dce0fccb963140080dcc4245fbfa8ea6abf9f242db96c546bda591261", 39): (
        "same_move_wrong_reason", "Calls Rxc7+ a sacrifice for attack instead of the proved safe pawn capture."
    ),
    _i("f1d2a7b52c92024b1c94dde446c297e7b7ce4282a56f0474e1f58f67a0df2638", 83): (
        "same_move_wrong_reason", "Says Rh8+ allows mate rather than teaching the proved Ra7 mating chance."
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound(path: Path, expected_sha256: str) -> Any:
    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"frozen evidence hash mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _percentile(sorted_values: list[float], proportion: float) -> float:
    index = int(proportion * (len(sorted_values) - 1))
    return sorted_values[index]


def build_report() -> Dict[str, Any]:
    worksheet = _load_bound(WORKSHEET, EXPECTED_WORKSHEET_SHA256)
    candidate = _load_bound(CANDIDATE_COVERAGE, EXPECTED_CANDIDATE_COVERAGE_SHA256)
    baseline = _load_bound(BASELINE, EXPECTED_BASELINE_SHA256)
    if baseline.get("membership_sha256") != EXPECTED_MEMBERSHIP_SHA256:
        raise ValueError("baseline membership changed")
    if not baseline.get("gold_frozen_before_reveal"):
        raise ValueError("baseline captions were not exported after the gold freeze")

    baseline_index = {
        _i(str(row["anonymous_game_key"]), int(row["ply"])): row
        for row in baseline.get("rows") or []
    }
    candidate_index = {
        _i(str(row["anonymous_game_key"]), int(row["ply"])): row
        for row in candidate.get("moments") or []
    }
    if len(baseline_index) != 90 or len(candidate_index) != 90:
        raise ValueError("comparison inputs must each contain 90 unique moments")

    rows = []
    seen: set[Identity] = set()
    disposition_counts: Counter[str] = Counter()
    family_counts: Counter[tuple[str, str]] = Counter()
    game_rows = []
    player_keys = set()
    zero_denominator_games = 0
    for game in worksheet.get("games") or []:
        game_key = str(game["anonymous_game_key"])
        player_key = str(game["anonymous_player_key"])
        if player_key in player_keys:
            raise ValueError("holdout must contain exactly one game per player")
        player_keys.add(player_key)
        moments = game.get("moments") or []
        if not moments:
            zero_denominator_games += 1
            continue
        legacy_covered = 0
        candidate_covered = 0
        for moment in moments:
            identity = _i(game_key, int(moment["ply"]))
            if identity in seen:
                raise ValueError("duplicate reviewed moment")
            seen.add(identity)
            old = baseline_index.get(identity)
            current = candidate_index.get(identity)
            if old is None or current is None:
                raise ValueError("a reviewed moment disappeared from the comparison")
            disposition, note = MANUAL_DISPOSITIONS.get(
                identity,
                (
                    "exact_match",
                    "Caption states the same causal reply, opportunity, or mate outcome.",
                ),
            )
            covered = disposition in COVERED_DISPOSITIONS
            current_covered = current.get("status") == "exact_fact"
            legacy_covered += int(covered)
            candidate_covered += int(current_covered)
            disposition_counts[disposition] += 1
            family = str(moment["cause_family"])
            family_counts[(family, disposition)] += 1
            rows.append(
                {
                    "anonymous_game_key": game_key,
                    "ply": identity[1],
                    "gold_family": family,
                    "gold_fact": str(moment["causal_chess_fact"]),
                    "legacy_caption": str(old.get("caption") or ""),
                    "legacy_explanation": old.get("caption_explanation"),
                    "legacy_principle_cue": str(old.get("principle_cue") or ""),
                    "legacy_disposition": disposition,
                    "legacy_covers_gold": covered,
                    "adjudication_note": note,
                    "candidate_fact_upper_bound_status": str(
                        current.get("status") or ""
                    ),
                    "candidate_fact_upper_bound_covers_gold": current_covered,
                }
            )
        denominator = len(moments)
        game_rows.append(
            {
                "anonymous_game_key": game_key,
                "anonymous_player_key": player_key,
                "proved_lessons": denominator,
                "legacy_covered": legacy_covered,
                "candidate_covered": candidate_covered,
                "legacy_coverage": legacy_covered / denominator,
                "candidate_coverage": candidate_covered / denominator,
                "paired_delta": (candidate_covered - legacy_covered) / denominator,
            }
        )

    if len(seen) != 90 or set(seen) != set(baseline_index) or set(seen) != set(candidate_index):
        raise ValueError("comparison must adjudicate every frozen moment exactly once")
    if set(MANUAL_DISPOSITIONS) - seen:
        raise ValueError("manual adjudication references a non-holdout moment")

    legacy_total = sum(row["legacy_covered"] for row in game_rows)
    candidate_total = sum(row["candidate_covered"] for row in game_rows)
    total = sum(row["proved_lessons"] for row in game_rows)
    legacy_macro = sum(row["legacy_coverage"] for row in game_rows) / len(game_rows)
    candidate_macro = sum(row["candidate_coverage"] for row in game_rows) / len(game_rows)
    delta = candidate_macro - legacy_macro

    rng = random.Random(BOOTSTRAP_SEED)
    deltas = [row["paired_delta"] for row in game_rows]
    bootstrap = []
    for _ in range(BOOTSTRAP_DRAWS):
        bootstrap.append(
            sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
        )
    bootstrap.sort()
    ci_low = _percentile(bootstrap, 0.025)
    ci_high = _percentile(bootstrap, 0.975)

    families = {}
    all_dispositions = sorted(disposition_counts)
    for family in sorted({row["gold_family"] for row in rows}):
        families[family] = {
            disposition: family_counts[(family, disposition)]
            for disposition in all_dispositions
            if family_counts[(family, disposition)]
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "frozen_failed_upper_bound_release_gate"
            if ci_low <= 0
            else "frozen_upper_bound_gate_passed_visible_gate_unresolved"
        ),
        "source": {
            "worksheet_sha256": EXPECTED_WORKSHEET_SHA256,
            "candidate_coverage_sha256": EXPECTED_CANDIDATE_COVERAGE_SHA256,
            "baseline_caption_packet_sha256": EXPECTED_BASELINE_SHA256,
            "membership_sha256": EXPECTED_MEMBERSHIP_SHA256,
            "gold_frozen_before_caption_reveal": True,
        },
        "execution_contract": {
            "database_reads": 0,
            "database_writes": 0,
            "engine_runs": 0,
            "model_calls": 0,
            "identity_fields": 0,
            "holdout_may_tune_product_logic": False,
        },
        "adjudication_contract": {
            "covered_dispositions": sorted(COVERED_DISPOSITIONS),
            "same_move_wrong_reason_is_covered": False,
            "every_proved_lesson_has_one_disposition": True,
            "review_unit": "same anonymous game and ply",
            "candidate_measure": (
                "pure shared-fact exact coverage; an upper bound on "
                "player-visible coverage because Shadow facts are included"
            ),
            "authorization_bypassed_for_runtime": False,
        },
        "summary": {
            "holdout_games": len(worksheet.get("games") or []),
            "players": len(player_keys),
            "proved_lessons": total,
            "zero_denominator_games": zero_denominator_games,
            "legacy_exact_match": disposition_counts["exact_match"],
            "legacy_causal_equivalent": disposition_counts["causal_equivalent"],
            "legacy_covered": legacy_total,
            "legacy_coverage_pct": round(100.0 * legacy_total / total, 2),
            "candidate_fact_upper_bound_covered": candidate_total,
            "candidate_fact_upper_bound_coverage_pct": round(
                100.0 * candidate_total / total, 2
            ),
            "upper_bound_micro_improvement_percentage_points": round(
                100.0 * (candidate_total - legacy_total) / total, 2
            ),
            "paired_games": len(game_rows),
            "legacy_macro_coverage_pct": round(100.0 * legacy_macro, 3),
            "candidate_fact_upper_bound_macro_coverage_pct": round(
                100.0 * candidate_macro, 3
            ),
            "upper_bound_paired_macro_improvement_percentage_points": round(
                100.0 * delta, 3
            ),
            "paired_games_upper_bound_better": sum(
                row["paired_delta"] > 0 for row in game_rows
            ),
            "paired_games_tied": sum(
                row["paired_delta"] == 0 for row in game_rows
            ),
            "paired_games_upper_bound_worse": sum(
                row["paired_delta"] < 0 for row in game_rows
            ),
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "player_clustered_ci95_low_percentage_points": round(100.0 * ci_low, 3),
            "player_clustered_ci95_high_percentage_points": round(100.0 * ci_high, 3),
            "release_gate_requires_ci_low_above_zero": True,
            "release_gate_passed": False,
            "failure_reason": (
                "Even the shared-fact upper bound has a confidence-interval "
                "lower bound at or below zero; the authorized visible subset "
                "cannot establish the required improvement."
            ),
        },
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "by_gold_family": families,
        "games": sorted(game_rows, key=lambda row: row["anonymous_game_key"]),
        "rows": sorted(rows, key=lambda row: (row["anonymous_game_key"], row["ply"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
