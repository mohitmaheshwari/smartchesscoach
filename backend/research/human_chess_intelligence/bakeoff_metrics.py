"""Pure metric and baseline primitives for the human-policy bake-off."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import median
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

from .policy_contract import MoveProbability

EPSILON = 1e-12
ECE_BINS = 10


def rating_band(elo: int) -> str:
    if elo < 1000:
        return "600-999"
    if elo < 1400:
        return "1000-1399"
    return "1400-1500"


def normalize_time_control(value: Optional[str]) -> str:
    text = str(value or "unknown").strip().lower()
    if text in {"bullet", "blitz", "rapid", "classical", "correspondence", "daily"}:
        return "correspondence" if text == "daily" else text
    if "+" in text or text.isdigit():
        try:
            base, increment = (text.split("+", 1) + ["0"])[:2]
            effective = int(base) + 40 * int(increment)
        except ValueError:
            return "unknown"
        if effective < 180:
            return "bullet"
        if effective < 600:
            return "blitz"
        if effective < 1800:
            return "rapid"
        return "classical"
    return "unknown"


@dataclass
class PolicyMetricsAccumulator:
    count: int = 0
    missing_actual_probability: int = 0
    top_hits: MutableMapping[int, int] = field(default_factory=lambda: Counter({1: 0, 3: 0, 5: 0}))
    sum_nll: float = 0.0
    sum_brier: float = 0.0
    actual_probabilities: list[float] = field(default_factory=list)
    actual_ranks: list[int] = field(default_factory=list)
    top1_confidences: list[float] = field(default_factory=list)
    top1_correct: list[int] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)

    def update(
        self,
        moves: Sequence[MoveProbability],
        actual_move_uci: str,
        *,
        latency_ms: float = 0.0,
    ) -> None:
        self.count += 1
        ranked = list(moves)
        probability_by_move = {move.move_uci: move.probability for move in ranked}
        actual_probability = probability_by_move.get(actual_move_uci, 0.0)
        if actual_move_uci not in probability_by_move:
            self.missing_actual_probability += 1
        else:
            self.actual_ranks.append(next(
                index for index, move in enumerate(ranked, start=1)
                if move.move_uci == actual_move_uci
            ))
        self.actual_probabilities.append(actual_probability)
        self.sum_nll += -math.log(max(actual_probability, EPSILON))
        self.sum_brier += 1.0 - 2.0 * actual_probability + sum(
            move.probability ** 2 for move in ranked
        )
        for k in (1, 3, 5):
            if actual_move_uci in {move.move_uci for move in ranked[:k]}:
                self.top_hits[k] += 1
        top = ranked[0]
        self.top1_confidences.append(top.probability)
        self.top1_correct.append(int(top.move_uci == actual_move_uci))
        self.latencies_ms.append(float(latency_ms))

    def _ece(self) -> float:
        if not self.count:
            return 0.0
        total = 0.0
        for bin_index in range(ECE_BINS):
            lower = bin_index / ECE_BINS
            upper = (bin_index + 1) / ECE_BINS
            indices = [
                i for i, confidence in enumerate(self.top1_confidences)
                if lower <= confidence < upper or (bin_index == ECE_BINS - 1 and confidence == 1.0)
            ]
            if not indices:
                continue
            average_confidence = sum(self.top1_confidences[i] for i in indices) / len(indices)
            accuracy = sum(self.top1_correct[i] for i in indices) / len(indices)
            total += (len(indices) / self.count) * abs(accuracy - average_confidence)
        return total

    def finalize(self) -> Dict[str, object]:
        if not self.count:
            return {"count": 0}
        sorted_latency = sorted(self.latencies_ms)
        p95_index = max(0, math.ceil(0.95 * len(sorted_latency)) - 1)
        return {
            "count": self.count,
            "coverage": (self.count - self.missing_actual_probability) / self.count,
            "missing_actual_probability": self.missing_actual_probability,
            "top1_accuracy": self.top_hits[1] / self.count,
            "top3_accuracy": self.top_hits[3] / self.count,
            "top5_accuracy": self.top_hits[5] / self.count,
            "negative_log_likelihood": self.sum_nll / self.count,
            "multiclass_brier": self.sum_brier / self.count,
            "top1_ece_10_bin": self._ece(),
            "mean_actual_move_probability": sum(self.actual_probabilities) / self.count,
            "median_actual_move_rank": median(self.actual_ranks) if self.actual_ranks else None,
            "mean_latency_ms": sum(self.latencies_ms) / self.count,
            "p95_latency_ms": sorted_latency[p95_index],
        }


class SegmentedPolicyMetrics:
    """Keep aggregate metrics plus the pre-registered product segments."""

    def __init__(self) -> None:
        self.overall = PolicyMetricsAccumulator()
        self.segments: Dict[str, Dict[str, PolicyMetricsAccumulator]] = defaultdict(dict)

    def update(
        self,
        moves: Sequence[MoveProbability],
        actual_move_uci: str,
        *,
        latency_ms: float,
        player_elo: int,
        time_control: Optional[str],
        phase: str,
        color: str,
        cp_loss: int,
        extra_segments: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.overall.update(moves, actual_move_uci, latency_ms=latency_ms)
        values = {
            "rating_band": rating_band(player_elo),
            "time_control": normalize_time_control(time_control),
            "phase": str(phase or "unknown"),
            "color": str(color or "unknown").lower(),
            "error_band": (
                "cp_loss_200_plus" if cp_loss >= 200 else
                "cp_loss_150_199" if cp_loss >= 150 else
                "cp_loss_100_149" if cp_loss >= 100 else
                "cp_loss_below_100"
            ),
        }
        values.update({
            str(dimension): str(value)
            for dimension, value in (extra_segments or {}).items()
        })
        for dimension, value in values.items():
            accumulator = self.segments[dimension].setdefault(value, PolicyMetricsAccumulator())
            accumulator.update(moves, actual_move_uci, latency_ms=latency_ms)

    def finalize(self) -> Dict[str, object]:
        return {
            "overall": self.overall.finalize(),
            "segments": {
                dimension: {
                    value: accumulator.finalize()
                    for value, accumulator in sorted(groups.items())
                }
                for dimension, groups in sorted(self.segments.items())
            },
        }


class LegalMoveFrequencyBaseline:
    """Add-one legal-move frequency by rating band and opening/phase.

    Opening positions use rating band + phase + ECO. Other phases use rating
    band + phase. Prediction renormalizes the learned move counts over the
    current legal set, so it can never emit an illegal move.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        self.alpha = float(alpha)
        self.counts: Dict[Tuple[str, str, str], Counter] = defaultdict(Counter)

    @staticmethod
    def _key(player_elo: int, phase: str, eco: Optional[str]) -> Tuple[str, str, str]:
        phase_key = str(phase or "unknown")
        eco_key = str(eco or "unknown") if phase_key == "opening" else "all"
        return rating_band(player_elo), phase_key, eco_key

    def observe(self, *, player_elo: int, phase: str, eco: Optional[str], move_uci: str) -> None:
        self.counts[self._key(player_elo, phase, eco)][move_uci] += 1

    def predict(
        self,
        legal_moves_uci: Iterable[str],
        *,
        player_elo: int,
        phase: str,
        eco: Optional[str],
    ) -> Tuple[MoveProbability, ...]:
        legal = sorted(set(legal_moves_uci))
        if not legal:
            raise ValueError("baseline requires at least one legal move")
        counts = self.counts[self._key(player_elo, phase, eco)]
        weights = {move: counts.get(move, 0) + self.alpha for move in legal}
        total = sum(weights.values())
        return tuple(sorted(
            (MoveProbability(move, weight / total) for move, weight in weights.items()),
            key=lambda item: (-item.probability, item.move_uci),
        ))
