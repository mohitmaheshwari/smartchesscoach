"""Build independent Caption evidence for the stored mating-line family.

The independent gold path is imported from the read-only measurement module.
It never imports the production detector, proof builder, stored-line verifier,
admission verdict, engine, or LLM. The production candidate is loaded only by
the separate candidate grader so the two calculations can be compared.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
import hashlib
import importlib.util
import json
import math
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import chess
from pymongo import MongoClient

try:
    from scripts.measure_forced_mate_caption_promotion import (
        CP_LOSS_FLOOR,
        POOLS,
        PROJECTION,
        QUALITY_ID,
        _moves,
        _parse_move,
        _source_key,
        _token,
        independent_adjudication,
    )
except ImportError:  # direct execution from backend/scripts
    from measure_forced_mate_caption_promotion import (  # type: ignore
        CP_LOSS_FLOOR,
        POOLS,
        PROJECTION,
        QUALITY_ID,
        _moves,
        _parse_move,
        _source_key,
        _token,
        independent_adjudication,
    )


SCHEMA_VERSION = "forced_mate_exact.caption_promotion.v1"
SEED = "20260905-forced-mate-exact-caption-v1"
SUBTYPES = ("mate_in_one", "longer_line")
POSITIVE_PER_SUBTYPE = 25
MIN_POOL_PER_SUBTYPE = 5
NATURAL_NEGATIVE_STRATA = (
    "line_does_not_end_in_checkmate",
    "illegal_or_incomplete_line",
    "insufficient_consequence",
    "played_best_move",
    "invalid_played_move",
    "invalid_consequence",
)
MUTATION_NEGATIVE_STRATA = (
    "truncated_before_mate",
    "moves_after_checkmate",
    "different_leading_move",
    "mating_move_replaced",
)
NEGATIVE_PER_STRATUM = 5
POSITIVE_TARGET = POSITIVE_PER_SUBTYPE * len(SUBTYPES)
NEGATIVE_TARGET = NEGATIVE_PER_STRATUM * (
    len(NATURAL_NEGATIVE_STRATA) + len(MUTATION_NEGATIVE_STRATA)
)


def _hash(value: object, *, namespace: str, length: int = 20) -> str:
    return hashlib.sha256(
        f"{namespace}\x1f{value}".encode("utf-8")
    ).hexdigest()[:length]


def _rank(case: Mapping[str, Any], label: str) -> str:
    return hashlib.sha256(
        f"{SEED}\x1f{label}\x1f{case['case_id']}".encode("utf-8")
    ).hexdigest()


def _candidate_builder():
    override = os.environ.get("FORCED_MATE_CANDIDATE_MODULE_PATH")
    if not override:
        from services.forced_mate_puzzle_proof import build_forced_mate_proof

        return build_forced_mate_proof
    spec = importlib.util.spec_from_file_location(
        "forced_mate_candidate_under_test", override
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("candidate module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_forced_mate_proof


def _candidate_grade(row: Mapping[str, Any]) -> Dict[str, Any]:
    board, played, best = _moves(row)
    if board is None or played is None or best is None:
        return {"fired": False}
    try:
        proof = _candidate_builder()(
            board,
            played.uci(),
            best.uci(),
            row.get("pv_after_best") or (),
            row.get("cp_loss"),
        )
    except (TypeError, ValueError, AssertionError):
        return {"fired": False}
    if not proof or not proof.verifier.verified:
        return {"fired": False}
    fact = proof.verifier.facts[0] if proof.verifier.facts else {}
    return {
        "fired": True,
        "concept_id": proof.detector.concept_id,
        "quality_id": proof.quality_id,
        "facts": {
            "mate_ply": fact.get("mate_ply"),
            "replayed_uci": list(fact.get("replayed_uci") or ()),
            "best_move_san": fact.get("best_move_san"),
            "mating_move_san": fact.get("mating_move_san"),
            "mating_piece": fact.get("mating_piece"),
            "mating_square": fact.get("mating_square"),
            "king_square": fact.get("king_square"),
            "terminal_legal_replies": fact.get("terminal_legal_replies"),
            "claim_strength": fact.get("claim_strength"),
        },
    }


def _safe_line(row: Mapping[str, Any]) -> list[str]:
    return [
        token
        for raw in (row.get("pv_after_best") or ())
        if (token := _token(raw))
    ]


def _normalized_full_line(row: Mapping[str, Any]) -> list[str]:
    board, _played, best = _moves(row)
    if board is None or best is None:
        return []
    continuation = _safe_line(row)
    first = _parse_move(board, continuation[0]) if continuation else None
    return continuation if first == best else [best.uci(), *continuation]


def _public_gold(gold: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = (
        "status",
        "reason",
        "subtype",
        "best_move_uci",
        "best_move_san",
        "first_piece",
        "first_destination",
        "cp_loss",
        "replayed_uci",
        "replayed_san",
        "mate_ply",
        "mating_move_uci",
        "mating_move_san",
        "mating_piece",
        "mating_square",
        "king_square",
        "terminal_legal_replies",
        "legal_prefix_plies",
    )
    return {key: gold.get(key) for key in allowed if key in gold}


def _case(
    row: Mapping[str, Any],
    *,
    pool: str,
    stratum: Optional[str] = None,
    source_suffix: str = "",
) -> Dict[str, Any]:
    source_key = _source_key(row, pool=pool)
    payload = {
        "pool": pool,
        "fen": row.get("fen"),
        "played_move": row.get("played_move")
        or row.get("user_move")
        or row.get("move")
        or row.get("user_move_uci")
        or row.get("user_move_san"),
        "best_move": row.get("best_move_uci") or row.get("best_move_san"),
        "cp_loss": row.get("cp_loss"),
        "pv_after_best": _safe_line(row),
    }
    case_id = _hash(
        json.dumps(
            {**payload, "source": source_key, "stratum": stratum},
            sort_keys=True,
            default=str,
        ),
        namespace="forced-mate-caption-case",
    )
    return {
        "case_id": case_id,
        "source_key": f"{source_key}{source_suffix}",
        **payload,
        "stratum": stratum,
        "gold": _public_gold(independent_adjudication(row)),
        "candidate": _candidate_grade(row),
    }


def _load_rows(db: Any) -> list[Dict[str, Any]]:
    rows = []
    for pool in POOLS:
        for row in db[pool].find({}, PROJECTION):
            rows.append({"pool": pool, "row": row})
    return rows


def _positive_sample(cases: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    available = list(cases)
    selected: list[Dict[str, Any]] = []
    used: set[str] = set()

    def take_distinct(
        candidates: Iterable[Dict[str, Any]], count: int
    ) -> list[Dict[str, Any]]:
        chosen = []
        seen = set(used)
        for candidate in candidates:
            source_key = candidate["source_key"]
            if source_key in seen:
                continue
            chosen.append(candidate)
            seen.add(source_key)
            if len(chosen) == count:
                break
        return chosen

    for subtype in SUBTYPES:
        subtype_selected = []
        for pool in POOLS:
            candidates = sorted(
                (
                    case
                    for case in available
                    if case["gold"].get("subtype") == subtype
                    and case["pool"] == pool
                    and case["source_key"] not in used
                ),
                key=lambda item: _rank(item, f"positive:{subtype}:{pool}"),
            )
            chosen = take_distinct(candidates, MIN_POOL_PER_SUBTYPE)
            if len(chosen) != MIN_POOL_PER_SUBTYPE:
                raise RuntimeError(f"insufficient {subtype}:{pool} supply")
            subtype_selected.extend(chosen)
            used.update(case["source_key"] for case in chosen)
        remainder = sorted(
            (
                case
                for case in available
                if case["gold"].get("subtype") == subtype
                and case["source_key"] not in used
            ),
            key=lambda item: _rank(item, f"positive:{subtype}:fill"),
        )
        needed = POSITIVE_PER_SUBTYPE - len(subtype_selected)
        subtype_selected.extend(take_distinct(remainder, needed))
        if len(subtype_selected) != POSITIVE_PER_SUBTYPE:
            raise RuntimeError(f"insufficient distinct {subtype} sources")
        used.update(case["source_key"] for case in subtype_selected)
        selected.extend(subtype_selected)
    return selected


def _natural_negative_sample(
    rows: Iterable[Dict[str, Any]],
    positive_sources: set[str],
) -> list[Dict[str, Any]]:
    available = []
    for item in rows:
        gold = independent_adjudication(item["row"])
        reason = gold.get("reason")
        if reason not in NATURAL_NEGATIVE_STRATA:
            continue
        case = _case(item["row"], pool=item["pool"], stratum=str(reason))
        if case["source_key"] not in positive_sources:
            available.append(case)

    selected = []
    used = set(positive_sources)
    for stratum in NATURAL_NEGATIVE_STRATA:
        candidates = sorted(
            (
                case
                for case in available
                if case["stratum"] == stratum
                and case["source_key"] not in used
            ),
            key=lambda item: _rank(item, f"negative:{stratum}"),
        )
        chosen = candidates[:NEGATIVE_PER_STRATUM]
        if len(chosen) != NEGATIVE_PER_STRATUM:
            raise RuntimeError(f"insufficient negative supply for {stratum}")
        selected.extend(chosen)
        used.update(case["source_key"] for case in chosen)
    return selected


def _alternative_best(row: Mapping[str, Any]) -> Optional[str]:
    board, played, best = _moves(row)
    if board is None or best is None:
        return None
    for move in sorted(board.legal_moves, key=lambda value: value.uci()):
        if move != best and move != played:
            return move.uci()
    return None


def _replace_final_move(row: Mapping[str, Any]) -> Optional[list[str]]:
    board, _played, _best = _moves(row)
    full = _normalized_full_line(row)
    if board is None or not full:
        return None
    before_final = board.copy(stack=False)
    for raw in full[:-1]:
        move = _parse_move(before_final, raw)
        if move is None:
            return None
        before_final.push(move)
    original = _parse_move(before_final, full[-1])
    for move in sorted(before_final.legal_moves, key=lambda value: value.uci()):
        if move == original:
            continue
        probe = before_final.copy(stack=False)
        probe.push(move)
        if not probe.is_checkmate():
            return [*full[:-1], move.uci()]
    return None


def _mutate(
    case: Mapping[str, Any], stratum: str
) -> Optional[Dict[str, Any]]:
    row = {
        "fen": case.get("fen"),
        "played_move": case.get("played_move"),
        "best_move_uci": case.get("best_move"),
        "cp_loss": case.get("cp_loss"),
        "pv_after_best": list(case.get("pv_after_best") or ()),
    }
    full = _normalized_full_line(row)
    if stratum == "truncated_before_mate":
        if len(full) <= 1:
            return None
        row["pv_after_best"] = full[:-1]
    elif stratum == "moves_after_checkmate":
        row["pv_after_best"] = [*full, "a1a1"]
    elif stratum == "different_leading_move":
        alternative = _alternative_best(row)
        if not alternative:
            return None
        row["best_move_uci"] = alternative
        row["pv_after_best"] = full
    elif stratum == "mating_move_replaced":
        replacement = _replace_final_move(row)
        if not replacement:
            return None
        row["pv_after_best"] = replacement
    else:
        raise ValueError(f"unknown mutation: {stratum}")
    return row


def _mutation_negative_sample(
    positives: Sequence[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    selected = []
    used_bases = set()
    for stratum in MUTATION_NEGATIVE_STRATA:
        candidates = sorted(
            positives,
            key=lambda item: _rank(item, f"mutation:{stratum}"),
        )
        for base in candidates:
            if base["source_key"] in used_bases:
                continue
            mutated = _mutate(base, stratum)
            if mutated is None:
                continue
            case = _case(
                mutated,
                pool=str(base["pool"]),
                stratum=stratum,
                source_suffix=f":{stratum}",
            )
            if case["gold"].get("status") == "exact":
                continue
            selected.append(case)
            used_bases.add(base["source_key"])
            if sum(
                item["stratum"] == stratum for item in selected
            ) == NEGATIVE_PER_STRATUM:
                break
        if sum(item["stratum"] == stratum for item in selected) != (
            NEGATIVE_PER_STRATUM
        ):
            raise RuntimeError(f"insufficient mutation supply for {stratum}")
    return selected


def _wilson_lower(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * total)) / total
    )
    return (centre - margin) / denominator


def _facts_match(case: Mapping[str, Any]) -> bool:
    gold = case["gold"]
    candidate = case["candidate"]
    facts = candidate.get("facts") or {}
    expected_strength = (
        "mate_in_one"
        if gold.get("subtype") == "mate_in_one"
        else "verified_stored_continuation"
    )
    return bool(
        candidate.get("fired")
        and candidate.get("quality_id") == QUALITY_ID
        and candidate.get("concept_id")
        == (
            "tactic.mate_in_one"
            if gold.get("subtype") == "mate_in_one"
            else "tactic.forced_mate"
        )
        and facts.get("mate_ply") == gold.get("mate_ply")
        and facts.get("replayed_uci") == gold.get("replayed_uci")
        and facts.get("best_move_san") == gold.get("best_move_san")
        and facts.get("mating_move_san") == gold.get("mating_move_san")
        and facts.get("mating_piece") == gold.get("mating_piece")
        and facts.get("mating_square") == gold.get("mating_square")
        and facts.get("king_square") == gold.get("king_square")
        and facts.get("terminal_legal_replies") == 0
        and facts.get("claim_strength") == expected_strength
    )


def build_report(db: Any) -> Dict[str, Any]:
    rows = _load_rows(db)
    stored = [
        item
        for item in rows
        if (item["row"].get("verified_admission") or {}).get("quality_id")
        == QUALITY_ID
    ]
    stored_cases = [
        _case(item["row"], pool=item["pool"])
        for item in stored
    ]
    reproducible = [
        case for case in stored_cases if case["gold"].get("status") == "exact"
    ]
    unreproducible = [
        case for case in stored_cases if case["gold"].get("status") != "exact"
    ]
    positives = _positive_sample(reproducible)
    positive_sources = {case["source_key"] for case in positives}
    negatives = [
        *_natural_negative_sample(rows, positive_sources),
        *_mutation_negative_sample(positives),
    ]

    positive_counts = Counter(case["gold"].get("subtype") for case in positives)
    true_by_subtype = Counter(
        case["gold"].get("subtype")
        for case in positives
        if _facts_match(case)
    )
    pool_by_subtype = Counter(
        f"{case['gold'].get('subtype')}:{case['pool']}" for case in positives
    )
    negative_counts = Counter(case["stratum"] for case in negatives)
    true_negatives = sum(
        case["gold"].get("status") != "exact"
        and not case["candidate"].get("fired")
        for case in negatives
    )
    full_reproducible_matches = sum(_facts_match(case) for case in reproducible)
    unreproducible_abstentions = sum(
        not case["candidate"].get("fired") for case in unreproducible
    )
    fact_mismatches = len(reproducible) - full_reproducible_matches
    subtype_wilson = {
        subtype: _wilson_lower(
            true_by_subtype[subtype], positive_counts[subtype]
        )
        for subtype in SUBTYPES
    }
    combined_wilson = _wilson_lower(
        sum(true_by_subtype.values()), len(positives)
    )
    critical_errors = (
        len(positives)
        - sum(true_by_subtype.values())
        + len(negatives)
        - true_negatives
        + fact_mismatches
        + len(unreproducible)
        - unreproducible_abstentions
    )
    required_counts = {
        **{name: NEGATIVE_PER_STRATUM for name in NATURAL_NEGATIVE_STRATA},
        **{name: NEGATIVE_PER_STRATUM for name in MUTATION_NEGATIVE_STRATA},
    }
    gate_checks = {
        "positive_target": len(positives) == POSITIVE_TARGET,
        "positive_sources_distinct": (
            len({case["source_key"] for case in positives}) == len(positives)
        ),
        "subtype_precision": all(
            positive_counts[subtype] == POSITIVE_PER_SUBTYPE
            and true_by_subtype[subtype] == POSITIVE_PER_SUBTYPE
            and subtype_wilson[subtype] >= 0.85
            for subtype in SUBTYPES
        ),
        "combined_precision": combined_wilson >= 0.85,
        "pool_coverage": all(
            pool_by_subtype[f"{subtype}:{pool}"] >= MIN_POOL_PER_SUBTYPE
            for subtype in SUBTYPES
            for pool in POOLS
        ),
        "mate_ply_validity": (
            bool(reproducible)
            and all(
                isinstance(case["gold"].get("mate_ply"), int)
                and case["gold"]["mate_ply"] > 0
                and case["gold"]["mate_ply"] % 2 == 1
                for case in reproducible
            )
        ),
        "negative_target": len(negatives) == NEGATIVE_TARGET,
        "negative_abstentions": true_negatives == len(negatives),
        "negative_strata": all(
            negative_counts[name] == count
            for name, count in required_counts.items()
        ),
        "reproducible_population_nonempty": bool(reproducible),
        "full_population_matches": (
            full_reproducible_matches == len(reproducible)
        ),
        "unreproducible_fail_closed": (
            unreproducible_abstentions == len(unreproducible)
        ),
        "zero_critical_errors": critical_errors == 0,
    }
    gate = all(gate_checks.values())
    selection_manifest = {
        "fires": [case["case_id"] for case in positives],
        "negatives": [case["case_id"] for case in negatives],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "quality_id": QUALITY_ID,
        "authorized_caption_claim": (
            "The displayed first move and stored legal continuation end in "
            "checkmate by the player, with the exact mating move, piece, "
            "square, checked king square and zero terminal legal replies."
        ),
        "explicitly_unauthorized_claims": [
            "every defence loses",
            "forced",
            "unavoidable",
            "only move",
            "mate in N for longer lines",
            "persistent weakness or mastery",
        ],
        "selection": {
            "seed": SEED,
            "positive_per_subtype": POSITIVE_PER_SUBTYPE,
            "minimum_pool_cases_per_subtype": MIN_POOL_PER_SUBTYPE,
            "negative_per_stratum": NEGATIVE_PER_STRATUM,
            "selection_fingerprint_sha256": hashlib.sha256(
                json.dumps(
                    selection_manifest,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
        "population": {
            "documents_scanned": len(rows),
            "stored_candidates": len(stored_cases),
            "reproducible_candidates": len(reproducible),
            "unreproducible_candidates": len(unreproducible),
            "full_reproducible_matches": full_reproducible_matches,
            "unreproducible_abstentions": unreproducible_abstentions,
            "fact_mismatches": fact_mismatches,
        },
        "summary": {
            "reviewed_fires": len(positives),
            "true_positives": sum(true_by_subtype.values()),
            "mate_in_one_true_positives": true_by_subtype["mate_in_one"],
            "longer_line_true_positives": true_by_subtype["longer_line"],
            "combined_wilson_lower_pct": round(combined_wilson * 100, 2),
            "mate_in_one_wilson_lower_pct": round(
                subtype_wilson["mate_in_one"] * 100, 2
            ),
            "longer_line_wilson_lower_pct": round(
                subtype_wilson["longer_line"] * 100, 2
            ),
            "reviewed_negatives": len(negatives),
            "true_negatives": true_negatives,
            "critical_adversarial_errors": critical_errors,
            "caption_promotion_gate_passed": gate,
            "gate_checks": gate_checks,
        },
        "positive_coverage": {
            "subtypes": dict(sorted(positive_counts.items())),
            "subtype_pools": dict(sorted(pool_by_subtype.items())),
            "mate_plies": dict(sorted(Counter(
                str(case["gold"].get("mate_ply")) for case in positives
            ).items())),
        },
        "negative_counts": dict(sorted(negative_counts.items())),
        "fires": positives,
        "negatives": negatives,
    }


def main() -> int:
    client = MongoClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=10_000
    )
    try:
        report = build_report(
            client[os.environ.get("DB_NAME", "chess_coach")]
        )
        output: Mapping[str, Any] = report
        if os.environ.get("FORCED_MATE_INCLUDE_CASES") != "1":
            output = {
                "schema_version": report["schema_version"],
                "selection": report["selection"],
                "population": report["population"],
                "summary": report["summary"],
                "positive_coverage": report["positive_coverage"],
                "negative_counts": report["negative_counts"],
                "case_records_exported": 0,
            }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return (
            0
            if report["summary"]["caption_promotion_gate_passed"]
            else 1
        )
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
