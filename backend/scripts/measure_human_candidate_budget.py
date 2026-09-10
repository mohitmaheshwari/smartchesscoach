#!/usr/bin/env python3
"""Measure a bounded human-policy candidate budget without production data.

The input may contain public game rows, but the output is aggregate-only: no
player names, game identifiers, positions, or moves are retained.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.human_behavior_engine import Maia2Provider, MoveContext  # noqa: E402


SCHEMA_VERSION = "human_candidate_budget_bakeoff.v1"
RATING_BANDS: Tuple[Tuple[str, int, int], ...] = (
    ("600-899", 600, 899),
    ("900-1199", 900, 1199),
    ("1200-1500", 1200, 1500),
)
PHASES: Tuple[Tuple[str, int, int], ...] = (
    ("opening", 0, 19),
    ("middlegame", 20, 59),
    ("late", 60, 10_000),
)
CANDIDATE_COUNTS: Tuple[int, ...] = (1, 3, 5, 8, 10, 20)
MASS_TARGETS: Tuple[float, ...] = (0.70, 0.80, 0.90)
ADAPTIVE_POLICIES: Tuple[Tuple[str, float, int, int], ...] = (
    ("mass_0.80_floor_3_cap_8", 0.80, 3, 8),
    ("mass_0.90_floor_3_cap_10", 0.90, 3, 10),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rating_band(rating: int) -> str | None:
    for name, low, high in RATING_BANDS:
        if low <= rating <= high:
            return name
    return None


def _phase(ply: int) -> str:
    for name, low, high in PHASES:
        if low <= ply <= high:
            return name
    return "late"


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    weight = index - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _summary(values: Sequence[float]) -> Dict[str, float]:
    return {
        "mean": round(statistics.fmean(values), 6) if values else 0.0,
        "p25": round(_percentile(values, 0.25), 6),
        "median": round(_percentile(values, 0.50), 6),
        "p75": round(_percentile(values, 0.75), 6),
        "p90": round(_percentile(values, 0.90), 6),
    }


def _sample_rows(path: Path, per_stratum: int) -> Tuple[List[Dict[str, str]], Mapping[str, int]]:
    """Keep the lowest deterministic hashes per rating-band/phase stratum."""
    heaps: MutableMapping[str, List[Tuple[int, Dict[str, str]]]] = defaultdict(list)
    eligible = Counter()
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                rating = int(row["active_elo"])
                opponent = int(row["opponent_elo"])
                ply = int(row["move_ply"])
                fen = row["board"]
                move = row["move"]
            except (KeyError, TypeError, ValueError):
                continue
            band = _rating_band(rating)
            if band is None or not fen or not move:
                continue
            stratum = f"{band}:{_phase(ply)}"
            eligible[stratum] += 1
            identity = f"{fen}|{move}|{rating}|{opponent}|{ply}".encode("utf-8")
            score = int.from_bytes(hashlib.sha256(identity).digest()[:8], "big")
            heap = heaps[stratum]
            item = (-score, row)
            if len(heap) < per_stratum:
                heapq.heappush(heap, item)
            elif score < -heap[0][0]:
                heapq.heapreplace(heap, item)
    selected: List[Dict[str, str]] = []
    for stratum in sorted(heaps):
        selected.extend(row for _, row in sorted(heaps[stratum], reverse=True))
    return selected, dict(sorted(eligible.items()))


def _rank(sorted_moves: Sequence[Tuple[str, float]], played: str) -> int | None:
    for index, (move, _) in enumerate(sorted_moves, start=1):
        if move == played:
            return index
    return None


def _count_for_mass(sorted_moves: Sequence[Tuple[str, float]], target: float) -> int | None:
    total = 0.0
    for index, (_, probability) in enumerate(sorted_moves, start=1):
        total += probability
        if total >= target:
            return index
    return None


def _adaptive_count(
    sorted_moves: Sequence[Tuple[str, float]],
    *,
    target: float,
    floor: int,
    cap: int,
) -> int:
    needed = _count_for_mass(sorted_moves, target)
    if needed is None:
        needed = cap
    return max(floor, min(cap, needed, len(sorted_moves)))


def run(args: argparse.Namespace) -> Dict[str, Any]:
    source = Path(args.input).resolve()
    model = Path(args.model).resolve()
    rows, eligible = _sample_rows(source, args.per_stratum)
    provider = Maia2Provider(
        model_type="rapid",
        device="cpu",
        model_path=str(model),
    )
    if not provider.available():
        raise RuntimeError("Maia-2 package is unavailable")

    # Load and warm the model before latency measurement.
    first = rows[0]
    warm = provider.predict(
        MoveContext(
            fen=first["board"],
            player_elo=int(first["active_elo"]),
            opponent_elo=int(first["opponent_elo"]),
        ),
        top_k=20,
    )
    if warm is None:
        raise RuntimeError("Maia-2 warm-up inference failed")

    hits = Counter()
    valid = 0
    failures = 0
    ranks: List[int] = []
    masses: Dict[int, List[float]] = {count: [] for count in CANDIDATE_COUNTS}
    mass_counts: Dict[float, List[int]] = {target: [] for target in MASS_TARGETS}
    adaptive_counts: Dict[str, List[int]] = {
        name: [] for name, _, _, _ in ADAPTIVE_POLICIES
    }
    adaptive_masses: Dict[str, List[float]] = {
        name: [] for name, _, _, _ in ADAPTIVE_POLICIES
    }
    adaptive_hits = Counter()
    latency_ms: List[float] = []
    stratum_results = Counter()

    for row in rows:
        context = MoveContext(
            fen=row["board"],
            player_elo=int(row["active_elo"]),
            opponent_elo=int(row["opponent_elo"]),
        )
        started = time.perf_counter()
        distribution = provider.predict(context, top_k=20)
        latency_ms.append((time.perf_counter() - started) * 1000)
        if distribution is None:
            failures += 1
            continue
        ordered = sorted(
            distribution.probabilities.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        )
        played_rank = _rank(ordered, row["move"])
        if played_rank is None:
            failures += 1
            continue
        valid += 1
        ranks.append(played_rank)
        band = _rating_band(int(row["active_elo"]))
        stratum_results[f"{band}:{_phase(int(row['move_ply']))}"] += 1
        for count in CANDIDATE_COUNTS:
            if played_rank <= count:
                hits[count] += 1
            masses[count].append(sum(probability for _, probability in ordered[:count]))
        for target in MASS_TARGETS:
            needed = _count_for_mass(ordered, target)
            if needed is not None:
                mass_counts[target].append(needed)
        for name, target, floor, cap in ADAPTIVE_POLICIES:
            count = _adaptive_count(
                ordered,
                target=target,
                floor=floor,
                cap=cap,
            )
            adaptive_counts[name].append(count)
            adaptive_masses[name].append(
                sum(probability for _, probability in ordered[:count])
            )
            if played_rank <= count:
                adaptive_hits[name] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_date": "2026-09-10",
        "method": {
            "source": "local public Maia-2 example test dataset",
            "selection": "lowest SHA-256 score per rating-band/phase stratum",
            "per_stratum": args.per_stratum,
            "rating_range": [600, 1500],
            "candidate_counts": list(CANDIDATE_COUNTS),
            "mass_targets": list(MASS_TARGETS),
            "production_reads": 0,
            "production_writes": 0,
            "stockfish_runs": 0,
            "llm_calls": 0,
        },
        "privacy": "Aggregate only; no names, ids, FENs, moves, PGNs, or free text.",
        "source_sha256": _sha256(source),
        "model": {
            "provider": provider.name,
            "provider_version": provider.version,
            "artifact_sha256": provider.artifact_sha256,
        },
        "population": {
            "eligible_by_stratum": eligible,
            "selected": len(rows),
            "valid": valid,
            "failures": failures,
            "valid_by_stratum": dict(sorted(stratum_results.items())),
        },
        "actual_move_coverage_pct": {
            f"top_{count}": round(100.0 * hits[count] / valid, 2) if valid else 0.0
            for count in CANDIDATE_COUNTS
        },
        "actual_move_rank": _summary(ranks),
        "probability_mass_by_fixed_count": {
            f"top_{count}": _summary(masses[count]) for count in CANDIDATE_COUNTS
        },
        "candidate_count_to_cumulative_mass": {
            str(target): _summary(mass_counts[target]) for target in MASS_TARGETS
        },
        "adaptive_policy": {
            name: {
                "target_mass": target,
                "floor": floor,
                "cap": cap,
                "candidate_count": _summary(adaptive_counts[name]),
                "returned_mass": _summary(adaptive_masses[name]),
                "actual_move_coverage_pct": (
                    round(100.0 * adaptive_hits[name] / valid, 2) if valid else 0.0
                ),
            }
            for name, target, floor, cap in ADAPTIVE_POLICIES
        },
        "latency_ms_per_position_after_warmup": _summary(latency_ms),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output")
    parser.add_argument("--per-stratum", type=int, default=100)
    args = parser.parse_args()
    result = run(args)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
