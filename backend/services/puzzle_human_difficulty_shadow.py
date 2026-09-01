"""Maia-2 puzzle findability metadata, isolated from puzzle truth and serving.

The rating grid is the measured Stage 3 grid.  This module never changes
admission, the accepted answer set, legacy difficulty, or ordering.  It only
records how often the pinned human-policy model expects the already-verified
answer to be found at each target rating.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import chess

from services.human_behavior_engine import HumanBehaviorProvider, MoveContext
from services.human_policy_runtime import derive_human_policy_evidence


PUZZLE_HUMAN_DIFFICULTY_SHADOW_FLAG = "PUZZLE_HUMAN_DIFFICULTY_SHADOW_ENABLED"
PUZZLE_HUMAN_DIFFICULTY_SCHEMA_VERSION = "puzzle_human_difficulty_shadow.v1"
MEASURED_RATING_GRID = (800, 1000, 1200, 1400)
_TRUE = frozenset({"1", "true", "yes", "on"})


def puzzle_human_difficulty_shadow_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    source = os.environ if env is None else env
    return str(source.get(PUZZLE_HUMAN_DIFFICULTY_SHADOW_FLAG, "false")).lower() in _TRUE


@dataclass(frozen=True)
class RatingFindability:
    rating: int
    answer_probability: Optional[float]
    answer_rank: Optional[int]
    provider: Optional[str]
    reason: str

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "rating": self.rating,
            "answer_probability": self.answer_probability,
            "answer_rank": self.answer_rank,
            "provider": self.provider,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PuzzleHumanDifficultyShadow:
    fen: str
    answer_uci: str
    ratings: Tuple[RatingFindability, ...]
    schema_version: str = PUZZLE_HUMAN_DIFFICULTY_SCHEMA_VERSION

    @property
    def input_fingerprint(self) -> str:
        raw = json.dumps(
            {
                "fen": " ".join(chess.Board(self.fen).fen().split()[:4]),
                "answer_uci": self.answer_uci,
                "rating_grid": [item.rating for item in self.ratings],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def contract_dict(self) -> Dict[str, Any]:
        complete = all(item.answer_probability is not None for item in self.ratings)
        return {
            "schema_version": self.schema_version,
            "fen": " ".join(chess.Board(self.fen).fen().split()[:4]),
            "answer_uci": self.answer_uci,
            "rating_grid": [item.rating for item in self.ratings],
            "ratings": [item.contract_dict() for item in self.ratings],
            "status": "complete" if complete else "partial",
            "input_fingerprint": self.input_fingerprint,
            "shadow_only": True,
            "changes_admission": False,
            "changes_answer": False,
            "changes_serving": False,
            "chess_authority": False,
        }


def build_puzzle_human_difficulty_shadow(
    *,
    fen: str,
    answer_uci: str,
    maia: Optional[HumanBehaviorProvider] = None,
    env: Optional[Mapping[str, str]] = None,
    rating_grid: Sequence[int] = MEASURED_RATING_GRID,
) -> Tuple[Optional[PuzzleHumanDifficultyShadow], str]:
    source = os.environ if env is None else env
    if not puzzle_human_difficulty_shadow_enabled(source):
        return None, "disabled"
    try:
        board = chess.Board(fen)
        answer = chess.Move.from_uci(str(answer_uci))
        if answer not in board.legal_moves:
            return None, "illegal_answer"
    except (ValueError, TypeError):
        return None, "invalid_position_or_answer"

    findings = []
    for rating in tuple(int(value) for value in rating_grid):
        evidence, reason = derive_human_policy_evidence(
            MoveContext(
                fen=board.fen(),
                player_elo=rating,
                opponent_elo=rating,
                time_control="puzzle",
                history_uci=(),
            ),
            maia=maia,
            env=source,
        )
        findings.append(
            RatingFindability(
                rating=rating,
                answer_probability=(evidence.probability_of(answer.uci()) if evidence else None),
                answer_rank=(evidence.rank_of(answer.uci()) if evidence else None),
                provider=(evidence.provider if evidence else None),
                reason=reason,
            )
        )
    if not any(item.answer_probability is not None for item in findings):
        return None, "no_valid_model_evidence"
    return PuzzleHumanDifficultyShadow(
        fen=board.fen(),
        answer_uci=answer.uci(),
        ratings=tuple(findings),
    ), "shadow_recorded"
