"""Model-neutral human-policy evidence contract for offline research.

The contract deliberately has no concept, weakness, mastery, or correctness
field.  A human model predicts behavior; Stockfish/tablebases and authorized
detectors own chess truth and player-facing interpretation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import chess

CONTRACT_VERSION = "human_policy_evidence.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$", re.IGNORECASE)


class PolicyContractError(ValueError):
    """Evidence cannot be compared because its provenance or moves are unsafe."""


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_history(history: Iterable[str]) -> Tuple[str, ...]:
    out = []
    for move in history:
        uci = str(move or "").strip().lower()
        if not _UCI_RE.fullmatch(uci):
            raise PolicyContractError(f"invalid history UCI: {move!r}")
        out.append(uci)
    return tuple(out)


@dataclass(frozen=True)
class HumanPolicyRequest:
    fen: str
    player_elo: int
    opponent_elo: int
    history_moves: Tuple[str, ...] = field(default_factory=tuple)
    time_control: Optional[str] = None
    clock_fraction: Optional[float] = None
    game_id: Optional[str] = None
    ply_index: Optional[int] = None

    def __post_init__(self) -> None:
        try:
            board = chess.Board(self.fen)
        except Exception as exc:
            raise PolicyContractError("request FEN is invalid") from exc
        if board.is_game_over():
            raise PolicyContractError("request position has no move to predict")
        if not 100 <= int(self.player_elo) <= 3500:
            raise PolicyContractError("player Elo is outside the evidence contract")
        if not 100 <= int(self.opponent_elo) <= 3500:
            raise PolicyContractError("opponent Elo is outside the evidence contract")
        cleaned = _clean_history(self.history_moves)
        object.__setattr__(self, "history_moves", cleaned)
        if self.clock_fraction is not None:
            clock = float(self.clock_fraction)
            if not math.isfinite(clock) or not 0.0 <= clock <= 1.0:
                raise PolicyContractError("clock_fraction must be within [0, 1]")
            object.__setattr__(self, "clock_fraction", clock)
        if self.ply_index is not None and int(self.ply_index) < 0:
            raise PolicyContractError("ply_index cannot be negative")

    def model_inputs(self) -> Dict[str, Any]:
        """Only fields a provider may consume; audit IDs are excluded."""
        return {
            "fen": self.fen,
            "player_elo": int(self.player_elo),
            "opponent_elo": int(self.opponent_elo),
            "history_moves": list(self.history_moves),
            "time_control": self.time_control,
            "clock_fraction": self.clock_fraction,
        }

    @property
    def input_fingerprint(self) -> str:
        return _sha256(_canonical_json(self.model_inputs()))


@dataclass(frozen=True)
class MoveProbability:
    move_uci: str
    probability: float

    def __post_init__(self) -> None:
        move = str(self.move_uci or "").strip().lower()
        probability = float(self.probability)
        if not _UCI_RE.fullmatch(move):
            raise PolicyContractError(f"invalid predicted UCI: {self.move_uci!r}")
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise PolicyContractError("move probability must be finite and within [0, 1]")
        object.__setattr__(self, "move_uci", move)
        object.__setattr__(self, "probability", probability)


@dataclass(frozen=True)
class HumanPolicyEvidence:
    provider: str
    model_version: str
    model_sha256: str
    input_fingerprint: str
    moves: Tuple[MoveProbability, ...]
    latency_ms: float
    policy_configuration: Mapping[str, str] = field(default_factory=dict)
    value_estimate: Optional[float] = None
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", str(self.provider or "").strip())
        object.__setattr__(self, "model_version", str(self.model_version or "").strip())
        object.__setattr__(self, "model_sha256", str(self.model_sha256 or "").lower())
        object.__setattr__(self, "input_fingerprint", str(self.input_fingerprint or "").lower())
        object.__setattr__(self, "moves", tuple(self.moves))
        object.__setattr__(self, "policy_configuration", {
            str(key): str(value)
            for key, value in dict(self.policy_configuration).items()
        })
        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))
        latency = float(self.latency_ms)
        if not math.isfinite(latency) or latency < 0:
            raise PolicyContractError("latency_ms must be finite and non-negative")
        object.__setattr__(self, "latency_ms", latency)
        if self.value_estimate is not None:
            value = float(self.value_estimate)
            if not math.isfinite(value):
                raise PolicyContractError("value_estimate must be finite")
            object.__setattr__(self, "value_estimate", value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "provider": self.provider,
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "input_fingerprint": self.input_fingerprint,
            "moves": [
                {"move_uci": move.move_uci, "probability": move.probability}
                for move in self.moves
            ],
            "probability_mass_returned": sum(move.probability for move in self.moves),
            "latency_ms": self.latency_ms,
            "policy_configuration": dict(self.policy_configuration),
            "value_estimate": self.value_estimate,
            "warnings": list(self.warnings),
        }


def validate_evidence(
    request: HumanPolicyRequest,
    evidence: HumanPolicyEvidence,
) -> HumanPolicyEvidence:
    """Fail closed on illegal moves, stale inputs, or missing provenance.

    Top-k providers do not need to return probability mass summing to one; the
    returned mass is recorded.  They may not return duplicates, an ordering
    that contradicts their own probabilities, or total mass above one beyond
    floating-point tolerance.
    """
    if evidence.contract_version != CONTRACT_VERSION:
        raise PolicyContractError("unsupported human-policy contract version")
    if not evidence.provider:
        raise PolicyContractError("provider is required")
    if not evidence.model_version:
        raise PolicyContractError("model_version is required")
    if not _SHA256_RE.fullmatch(evidence.model_sha256):
        raise PolicyContractError("model_sha256 must be a lowercase SHA-256")
    required_configuration = {"clock_mode", "history_mode"}
    if not required_configuration.issubset(evidence.policy_configuration):
        raise PolicyContractError("clock_mode and history_mode are required policy configuration")
    if evidence.input_fingerprint != request.input_fingerprint:
        raise PolicyContractError("evidence was produced for different model inputs")
    if not evidence.moves:
        raise PolicyContractError("provider returned no moves")

    board = chess.Board(request.fen)
    legal = {move.uci() for move in board.legal_moves}
    seen = set()
    previous = float("inf")
    mass = 0.0
    for prediction in evidence.moves:
        if prediction.move_uci not in legal:
            raise PolicyContractError(f"provider returned illegal move {prediction.move_uci}")
        if prediction.move_uci in seen:
            raise PolicyContractError(f"provider returned duplicate move {prediction.move_uci}")
        if prediction.probability > previous + 1e-12:
            raise PolicyContractError("moves must be ordered by descending probability")
        seen.add(prediction.move_uci)
        previous = prediction.probability
        mass += prediction.probability
    if mass > 1.000001:
        raise PolicyContractError("returned move probability mass exceeds one")
    return evidence
