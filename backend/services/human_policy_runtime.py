"""Governed runtime evidence from the existing Maia-2/Otter providers.

Human-policy evidence is a population/player prior, never chess truth.  This
module verifies history, legality, probability shape and provenance before a
consumer may use the distribution to rank a separately verified safe set.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import chess

from services.human_behavior_engine import (
    HumanBehaviorProvider,
    Maia2Provider,
    MoveContext,
    MoveDistribution,
    OtterProvider,
)


HUMAN_POLICY_SCHEMA_VERSION = "human_policy_evidence.v1"
HUMAN_POLICY_EVIDENCE_FLAG = "HUMAN_POLICY_EVIDENCE_ENABLED"
OTTER_PINNED_MODEL_SHA256 = "53dc65068c88e298de5abe3dfd93141ea1e3bf795961a686f239b5574804757d"
MAIA2_PINNED_MODEL_SHA256 = "65aae8465eed5e65df66a24ea7370715579f9e5435098d06fe18bdb1e267e997"
OTTER_PINNED_PACKAGE_VERSION = "0.2.0"
MAIA2_PINNED_PACKAGE_VERSION = "0.11.0:rapid"
VALIDATED_ELO_MIN = 600
VALIDATED_ELO_MAX = 1500
_TRUE = frozenset({"1", "true", "yes", "on"})


class HumanPolicyError(ValueError):
    """Raised when model evidence is illegal, stale or malformed."""


def human_policy_evidence_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(HUMAN_POLICY_EVIDENCE_FLAG, "false")).strip().lower() in _TRUE


def _position_key(fen: str) -> str:
    return " ".join(chess.Board(fen).fen().split()[:4])


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _history_digest(history_uci: Sequence[str]) -> str:
    raw = json.dumps(list(history_uci), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def history_reaches_fen(history_uci: Sequence[str], fen: str) -> bool:
    if not history_uci:
        return False
    board = chess.Board()
    try:
        for uci in history_uci:
            move = chess.Move.from_uci(str(uci))
            if move not in board.legal_moves:
                return False
            board.push(move)
    except (ValueError, TypeError):
        return False
    return _position_key(board.fen()) == _position_key(fen)


@dataclass(frozen=True)
class HumanMoveProbability:
    move_uci: str
    probability: float

    def __post_init__(self) -> None:
        if not isinstance(self.move_uci, str) or len(self.move_uci) not in {4, 5}:
            raise HumanPolicyError("human-policy move must be UCI")
        if not math.isfinite(self.probability) or not 0.0 <= self.probability <= 1.0:
            raise HumanPolicyError("human-policy probability must be within [0, 1]")

    def contract_dict(self) -> Dict[str, Any]:
        return {"move_uci": self.move_uci, "probability": self.probability}


@dataclass(frozen=True)
class HumanPolicyEvidence:
    fen: str
    player_elo: int
    opponent_elo: int
    time_control: str
    provider: str
    provider_version: str
    provider_role: str
    model_sha256: str
    probabilities: Tuple[HumanMoveProbability, ...]
    history_mode: str
    history_plies: int
    history_sha256: str
    latency_ms: int
    warnings: Tuple[str, ...] = ()
    schema_version: str = HUMAN_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        board = chess.Board(self.fen)
        if self.provider not in {"otter", "maia2"}:
            raise HumanPolicyError("unsupported human-policy provider")
        if self.provider_role not in {"preferred_history", "no_history_fallback"}:
            raise HumanPolicyError("unsupported human-policy provider role")
        expected_sha = (
            OTTER_PINNED_MODEL_SHA256 if self.provider == "otter"
            else MAIA2_PINNED_MODEL_SHA256
        )
        if self.model_sha256 != expected_sha:
            raise HumanPolicyError("human-policy model hash is not the pinned research model")
        expected_version = (
            OTTER_PINNED_PACKAGE_VERSION if self.provider == "otter"
            else MAIA2_PINNED_PACKAGE_VERSION
        )
        if self.provider_version != expected_version:
            raise HumanPolicyError("human-policy package/model family is not pinned")
        if self.history_mode not in {"verified", "none"}:
            raise HumanPolicyError("invalid human-policy history mode")
        if self.provider == "otter" and self.history_mode != "verified":
            raise HumanPolicyError("Otter requires verified history")
        if self.provider == "maia2" and self.provider_role != "no_history_fallback":
            raise HumanPolicyError("Maia-2 is the locked fallback only")
        if not re.fullmatch(r"[0-9a-f]{64}", self.history_sha256):
            raise HumanPolicyError("human-policy history SHA-256 is required")
        if self.history_mode == "none" and (
            self.history_plies != 0
            or self.history_sha256 != _history_digest(())
        ):
            raise HumanPolicyError("no-history evidence must use the empty-history identity")
        if self.history_mode == "verified" and self.history_plies <= 0:
            raise HumanPolicyError("verified-history evidence requires at least one ply")
        if not self.probabilities:
            raise HumanPolicyError("human-policy evidence returned no moves")
        moves = [item.move_uci for item in self.probabilities]
        if len(moves) != len(set(moves)):
            raise HumanPolicyError("human-policy distribution contains duplicate moves")
        legal = {move.uci() for move in board.legal_moves}
        if any(move not in legal for move in moves):
            raise HumanPolicyError("human-policy distribution contains an illegal move")
        if tuple(sorted(self.probabilities, key=lambda item: -item.probability)) != self.probabilities:
            raise HumanPolicyError("human-policy probabilities must be sorted")
        probability_mass = sum(item.probability for item in self.probabilities)
        if probability_mass <= 0 or probability_mass > 1.001:
            raise HumanPolicyError("human-policy probability mass is invalid")
        if self.latency_ms < 0:
            raise HumanPolicyError("human-policy latency cannot be negative")

    @property
    def returned_probability_mass(self) -> float:
        return sum(item.probability for item in self.probabilities)

    @property
    def entropy(self) -> float:
        return -sum(
            item.probability * math.log(item.probability)
            for item in self.probabilities
            if item.probability > 0
        )

    @property
    def input_fingerprint(self) -> str:
        return _digest({
            "fen": _position_key(self.fen),
            "player_elo": self.player_elo,
            "opponent_elo": self.opponent_elo,
            "time_control": self.time_control,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "provider_role": self.provider_role,
            "history_mode": self.history_mode,
            "history_plies": self.history_plies,
            "history_sha256": self.history_sha256,
        })

    def probability_of(self, move_uci: str) -> Optional[float]:
        for item in self.probabilities:
            if item.move_uci == move_uci:
                return item.probability
        return None

    def rank_of(self, move_uci: str) -> Optional[int]:
        for index, item in enumerate(self.probabilities, start=1):
            if item.move_uci == move_uci:
                return index
        return None

    def rank_verified_candidates(self, candidates_uci: Sequence[str]) -> Tuple[str, ...]:
        allowed = set(candidates_uci)
        return tuple(
            item.move_uci for item in self.probabilities if item.move_uci in allowed
        )

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fen": _position_key(self.fen),
            "player_elo": self.player_elo,
            "opponent_elo": self.opponent_elo,
            "time_control": self.time_control,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "provider_role": self.provider_role,
            "model_sha256": self.model_sha256,
            "probabilities": [item.contract_dict() for item in self.probabilities],
            "history_mode": self.history_mode,
            "history_plies": self.history_plies,
            "history_sha256": self.history_sha256,
            "clock_mode": (
                "controlled_neutral_0.5"
                if self.provider == "otter"
                else "unsupported"
            ),
            "clock_used_for_causal_diagnosis": False,
            "latency_ms": self.latency_ms,
            "returned_probability_mass": self.returned_probability_mass,
            "entropy": self.entropy,
            "warnings": list(self.warnings),
            "input_fingerprint": self.input_fingerprint,
            "chess_authority": False,
        }

    @classmethod
    def from_contract(cls, raw: Mapping[str, Any]) -> "HumanPolicyEvidence":
        if raw.get("schema_version") != HUMAN_POLICY_SCHEMA_VERSION:
            raise HumanPolicyError("unsupported human-policy schema")
        evidence = cls(
            fen=str(raw.get("fen") or ""),
            player_elo=int(raw.get("player_elo")),
            opponent_elo=int(raw.get("opponent_elo")),
            time_control=str(raw.get("time_control") or ""),
            provider=str(raw.get("provider") or ""),
            provider_version=str(raw.get("provider_version") or ""),
            provider_role=str(raw.get("provider_role") or ""),
            model_sha256=str(raw.get("model_sha256") or ""),
            probabilities=tuple(
                HumanMoveProbability(
                    move_uci=str(item.get("move_uci") or ""),
                    probability=float(item.get("probability")),
                )
                for item in raw.get("probabilities") or ()
            ),
            history_mode=str(raw.get("history_mode") or ""),
            history_plies=int(raw.get("history_plies") or 0),
            history_sha256=str(raw.get("history_sha256") or ""),
            latency_ms=int(raw.get("latency_ms") or 0),
            warnings=tuple(raw.get("warnings") or ()),
        )
        if raw.get("input_fingerprint") != evidence.input_fingerprint:
            raise HumanPolicyError("human-policy fingerprint mismatch")
        return evidence


def human_policy_evidence_matches_context(
    evidence: HumanPolicyEvidence,
    ctx: MoveContext,
) -> bool:
    """Reject a stored packet joined to another position/player/history."""
    if (
        _position_key(evidence.fen) != _position_key(ctx.fen)
        or evidence.player_elo != int(ctx.player_elo)
        or evidence.opponent_elo != int(ctx.opponent_elo)
        or evidence.time_control != str(ctx.time_control)
    ):
        return False
    expected_history = tuple(ctx.history_uci) if evidence.provider == "otter" else ()
    return (
        evidence.history_plies == len(expected_history)
        and evidence.history_sha256 == _history_digest(expected_history)
        and (evidence.provider != "otter" or history_reaches_fen(expected_history, ctx.fen))
    )


def _validated_distribution(
    ctx: MoveContext,
    distribution: MoveDistribution,
    *,
    provider_role: str,
    model_sha256: str,
    history_mode: str,
    latency_ms: int,
    warnings: Sequence[str],
) -> HumanPolicyEvidence:
    ordered = tuple(
        HumanMoveProbability(str(move), float(probability))
        for move, probability in sorted(
            distribution.probabilities.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        )
    )
    return HumanPolicyEvidence(
        fen=_position_key(ctx.fen),
        player_elo=int(ctx.player_elo),
        opponent_elo=int(ctx.opponent_elo),
        time_control=str(ctx.time_control),
        provider=distribution.provider,
        provider_version=distribution.provider_version,
        provider_role=provider_role,
        model_sha256=model_sha256,
        probabilities=ordered,
        history_mode=history_mode,
        history_plies=len(ctx.history_uci) if history_mode == "verified" else 0,
        history_sha256=_history_digest(
            ctx.history_uci if history_mode == "verified" else ()
        ),
        latency_ms=latency_ms,
        warnings=tuple(warnings),
    )


@lru_cache(maxsize=1)
def _runtime_providers() -> Tuple[HumanBehaviorProvider, HumanBehaviorProvider]:
    """Load each optional model at most once per worker process."""
    return (
        OtterProvider(device="cpu", checkpoint_path=os.environ.get("OTTER_MODEL_PATH")),
        Maia2Provider(
            model_type="rapid",
            device="cpu",
            model_path=os.environ.get("MAIA2_MODEL_PATH"),
        ),
    )


def _provenance_matches(
    provider: HumanBehaviorProvider,
    *,
    expected_version: str,
    expected_sha256: str,
) -> bool:
    return (
        provider.version == expected_version
        and provider.artifact_sha256 == expected_sha256
    )


def derive_human_policy_evidence(
    ctx: MoveContext,
    *,
    otter: Optional[HumanBehaviorProvider] = None,
    maia: Optional[HumanBehaviorProvider] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[Optional[HumanPolicyEvidence], str]:
    """Use history-verified Otter, then the measured Maia no-history fallback."""
    if not human_policy_evidence_enabled(env):
        return None, "disabled"
    # The frozen corpus selected the player being modelled at 600-1500.
    # Opponent ratings were observed inputs and legitimately extend outside it.
    if not VALIDATED_ELO_MIN <= int(ctx.player_elo) <= VALIDATED_ELO_MAX:
        return None, "outside_validated_rating_range"
    try:
        chess.Board(ctx.fen)
    except ValueError:
        return None, "invalid_fen"
    history_verified = history_reaches_fen(ctx.history_uci, ctx.fen)
    warnings = []
    if ctx.clock_fraction is not None or ctx.clock_seconds is not None:
        warnings.append("clock_ignored_by_locked_policy")

    if history_verified:
        provider = otter or _runtime_providers()[0]
        provenance_ok = otter is not None or _provenance_matches(
            provider,
            expected_version=OTTER_PINNED_PACKAGE_VERSION,
            expected_sha256=OTTER_PINNED_MODEL_SHA256,
        )
        if not provenance_ok:
            warnings.append("otter_provenance_rejected")
        elif provider.available():
            history_ctx = MoveContext(
                fen=ctx.fen,
                player_elo=ctx.player_elo,
                opponent_elo=ctx.opponent_elo,
                time_control=ctx.time_control,
                history_uci=tuple(ctx.history_uci),
                clock_seconds=None,
                # This exactly reproduces the winning Stage 1 history-only
                # ablation. It is controlled neutral context, not player clock
                # evidence and can never support a "you rushed" claim.
                clock_fraction=0.5,
                move_number=ctx.move_number,
            )
            started = time.perf_counter()
            distribution = provider.predict(history_ctx, top_k=20)
            latency = int(round((time.perf_counter() - started) * 1000))
            if distribution is not None:
                try:
                    return _validated_distribution(
                        history_ctx,
                        distribution,
                        provider_role="preferred_history",
                        model_sha256=OTTER_PINNED_MODEL_SHA256,
                        history_mode="verified",
                        latency_ms=latency,
                        warnings=warnings,
                    ), "otter_history"
                except HumanPolicyError:
                    warnings.append("otter_output_rejected")
            else:
                warnings.append("otter_inference_unavailable")
        else:
            warnings.append("otter_provider_unavailable")
    elif ctx.history_uci:
        warnings.append("history_does_not_reach_position")
    else:
        warnings.append("history_unavailable")

    provider = maia or _runtime_providers()[1]
    provenance_ok = maia is not None or _provenance_matches(
        provider,
        expected_version=MAIA2_PINNED_PACKAGE_VERSION,
        expected_sha256=MAIA2_PINNED_MODEL_SHA256,
    )
    if not provenance_ok:
        return None, "maia_provenance_rejected"
    if not provider.available():
        return None, "no_provider_available"
    fallback_ctx = MoveContext(
        fen=ctx.fen,
        player_elo=ctx.player_elo,
        opponent_elo=ctx.opponent_elo,
        time_control=ctx.time_control,
        history_uci=(),
        clock_seconds=None,
        clock_fraction=None,
        move_number=ctx.move_number,
    )
    started = time.perf_counter()
    distribution = provider.predict(fallback_ctx, top_k=20)
    latency = int(round((time.perf_counter() - started) * 1000))
    if distribution is None:
        return None, "maia_inference_unavailable"
    try:
        return _validated_distribution(
            fallback_ctx,
            distribution,
            provider_role="no_history_fallback",
            model_sha256=MAIA2_PINNED_MODEL_SHA256,
            history_mode="none",
            latency_ms=latency,
            warnings=warnings,
        ), "maia_fallback"
    except HumanPolicyError:
        return None, "maia_output_rejected"
