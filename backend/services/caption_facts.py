"""
Caption Facts — the canonical chess-semantics layer for ChessGuru.

Per design doc `docs/caption_pipeline_design.md` and memory rule
`feedback_renderer_never_computes_chess_meaning.md`:

    THIS MODULE COMPUTES CHESS MEANING. The renderer does not.

Every fact returned by `extract_facts()` is:
    - atomic (a single deterministic value, never interpreted prose)
    - geometric (derivable from FEN + engine data; no opinions)
    - machine-composable (renderers select and format; never re-derive)

──────────────────────────────────────────────────────────────────────
Four implementation laws (locked 2026-05-11):
──────────────────────────────────────────────────────────────────────

LAW 1 — NO SMART STRINGS AS FACTS.
    Bad:   {"best_reason": "wins a pawn"}
    Good:  {"best_move_wins_material": True,
            "best_move_material_delta_cp": 100,
            "best_move_targets": [(sq, piece_type), ...]}
    Phrasing belongs to the renderer. Facts stay atomic.

LAW 2 — NO FUTURE CONVENIENCE FACTS.
    Forbidden: is_nice_move, is_aggressive, is_positional, is_sharp,
    is_natural, and anything that smuggles in human emotional judgment
    as a fact. This module answers: what changed, what attacks what,
    what is defended, what the PV proves, what geometry exists.
    It does NOT answer: whether a human emotionally approves.

LAW 3 — TACTIC DETECTORS EMIT EVIDENCE, NOT LABELS.
    Bad:   {"tactic": "fork"}
    Good:  {"tactic": "fork", "forker_square": "f3",
            "targets": [(sq, piece_type), ...]}
    The renderer must be able to write the caption from the evidence
    alone, without re-running any chess logic of its own.

LAW 4 — THIS MODULE IS REPLAYABLE IN ISOLATION.
    A CLI entry point and a pure-function API let any extracted fact
    be reproduced from a (FEN, move, engine_data) triple. Every Parth
    disagreement and every hallucination claim traces back here.
    Treat this file like a chess-science layer, not an app helper.

──────────────────────────────────────────────────────────────────────
First commit covers:
    - Engine truth (pass-through from stored move_evaluations)
    - Basic position facts (check, capture, castling, forced recapture)
    - Attack/defense lists (raw — NOT SEE yet; that's commit #2)
    - Phase, opening name (uses existing detect_opening_from_moves)
    - Target square, captured piece, moving piece type

Not yet implemented (subsequent commits):
    - SEE (Static Exchange Evaluation) — commit #2
    - Threats created / pieces now undefended — commit #2
    - Tactic detection with evidence — commit #3
    - PV material walk — commit #3
    - Primary-reason extractor — commit #4
    - Concept-library facts (passed pawn, doubled, etc) — Phase 3

Usage (Python):
    from services.caption_facts import extract_facts
    facts = extract_facts(
        fen_before="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
        played_san="Nc3",
        best_move_san="O-O",
        eval_before_cp=20, eval_after_cp=15,
        cp_loss=5,
        pv_after_played=["Nc3", "Bc5", "O-O"],
        pv_after_best=["O-O", "Bc5", "c3"],
        move_history_san=["e4", "e5", "Nf3", "Nc6", "Bc4"],
        full_move_number=3,
    )

Usage (CLI):
    python -m backend.services.caption_facts \\
        --fen "..." --move Nc3 --best O-O \\
        --eval-before 20 --eval-after 15 --cp-loss 5
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import chess

if TYPE_CHECKING:
    from services.stored_line_verifier import StoredLineEvent, StoredLineReplay

from services.exact_endgame_service import ExactEndgameCause

from services.caption_config import (
    MAX_CP_LOSS_FOR_TACTIC_CELEBRATION,
    MIN_THREAT_SEE_CP,
)


# ────────────────────────────────────────────────────────────────────
# Public constants
# ────────────────────────────────────────────────────────────────────

PIECE_TYPE_NAMES: Dict[int, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

PIECE_VALUE_CP: Dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # king has no exchange value (SEE caps before king capture)
}

LEGAL_MATERIAL_LOSS_CAUSE_VERSION = "legal_material_loss_cause.v2"
VERIFIED_LINE_CAUSE_VERSION = "verified_line_cause.v1"
VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION = "verified_line_cause.v2"
TARGET_LINE_CAUSAL_PROOF_VERSION = "target_line_causal_proof.v6"
TARGET_LINE_CAUSAL_QUALITY_ID = "review:target_line_causal_proof"
TARGET_LINE_MIN_PAYOFF_CP = PIECE_VALUE_CP[chess.KNIGHT]
FORCING_TEMPO_CAUSAL_PROOF_VERSION = "forcing_tempo_causal_proof.v2"
FORCING_TEMPO_CAUSAL_QUALITY_ID = "review:forcing_tempo_causal_proof"
ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION = "endgame_geometry_causal_proof.v2"
ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID = "review:endgame_geometry_causal_proof"
BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION = (
    "board_transformation_causal_proof.v1"
)
BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID = (
    "review:board_transformation_causal_proof"
)
VERIFIED_LINE_MIN_CP_LOSS = 100
_LEGAL_MATERIAL_PURPOSES = frozenset({
    "moves_affected_piece",
    "removes_attacker",
    "adds_defender",
})
_VERIFIED_PLAYED_PURPOSES = frozenset({
    "gives_check",
    "captures",
    "develops",
    "pressures_king_ring",
    "attacks_opponent_piece",
})


@dataclass(frozen=True)
class PieceOnSquare:
    piece: str
    square: str

    def __post_init__(self) -> None:
        if self.piece not in set(PIECE_TYPE_NAMES.values()):
            raise ValueError("unknown piece type")
        chess.parse_square(self.square)

    def contract_dict(self) -> Dict[str, str]:
        return {"piece": self.piece, "square": self.square}


@dataclass(frozen=True)
class LegalMaterialLossCause:
    """Exact legal-exchange cause shared by captions, Review and PWC."""

    affected: PieceOnSquare
    attacker: PieceOnSquare
    punishment_san: str
    material_loss_cp: int
    best_move_san: str
    best_move_purpose: Optional[str]
    best_move_from: str
    best_move_to: str
    played_capture: Optional[PieceOnSquare] = None
    played_purposes: Tuple[str, ...] = ()
    proof_authority: str = "caption_facts.legally_hanging_pieces"
    proof_version: str = LEGAL_MATERIAL_LOSS_CAUSE_VERSION

    def __post_init__(self) -> None:
        if not self.punishment_san or not self.best_move_san:
            raise ValueError("cause moves must be non-empty")
        if self.material_loss_cp <= 0:
            raise ValueError("material loss must be positive")
        chess.parse_square(self.best_move_from)
        chess.parse_square(self.best_move_to)
        if (
            self.best_move_purpose is not None
            and self.best_move_purpose not in _LEGAL_MATERIAL_PURPOSES
        ):
            raise ValueError("unknown best-move purpose")
        if not isinstance(self.played_purposes, tuple) or any(
            purpose not in _VERIFIED_PLAYED_PURPOSES
            for purpose in self.played_purposes
        ):
            raise ValueError("unknown played-move purpose")

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def contract_dict(self, *, include_fingerprint: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": self.proof_version,
            "kind": "legal_material_loss",
            "affected": self.affected.contract_dict(),
            "attacker": self.attacker.contract_dict(),
            "punishment_san": self.punishment_san,
            "material_loss_cp": self.material_loss_cp,
            "best_move_san": self.best_move_san,
            "best_move_purpose": self.best_move_purpose,
            "best_move_purpose_verified": self.best_move_purpose is not None,
            "best_move_from": self.best_move_from,
            "best_move_to": self.best_move_to,
            "played_capture": (
                self.played_capture.contract_dict()
                if self.played_capture is not None
                else None
            ),
            "played_purposes": list(self.played_purposes),
            "proof": {
                "authority": self.proof_authority,
                "version": self.proof_version,
            },
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class VerifiedLineCapture:
    """One capture in a fully legal stored continuation."""

    ply: int
    actor: str
    move_san: str
    origin: str
    destination: str
    capturing_piece: str
    captured_piece: str
    captured_square: str
    captured_value_cp: int

    def __post_init__(self) -> None:
        if self.ply < 1 or self.actor not in {"initiator", "opponent"}:
            raise ValueError("invalid verified-line capture identity")
        for square in (self.origin, self.destination, self.captured_square):
            chess.parse_square(square)
        if self.capturing_piece not in set(PIECE_TYPE_NAMES.values()):
            raise ValueError("unknown capturing piece")
        if self.captured_piece not in set(PIECE_TYPE_NAMES.values()):
            raise ValueError("unknown captured piece")
        if self.captured_value_cp <= 0:
            raise ValueError("captured value must be positive")

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "ply": self.ply,
            "actor": self.actor,
            "move_san": self.move_san,
            "origin": self.origin,
            "destination": self.destination,
            "capturing_piece": self.capturing_piece,
            "captured_piece": self.captured_piece,
            "captured_square": self.captured_square,
            "captured_value_cp": self.captured_value_cp,
        }


@dataclass(frozen=True)
class CauseRelationship:
    origin: str
    destination: str
    role: str

    def __post_init__(self) -> None:
        chess.parse_square(self.origin)
        chess.parse_square(self.destination)
        if self.role not in {"threat", "safe_move", "opportunity"}:
            raise ValueError("unknown cause relationship role")

    def contract_dict(self) -> Dict[str, str]:
        return {
            "from": self.origin,
            "to": self.destination,
            "role": self.role,
        }


@dataclass(frozen=True)
class VerifiedBranchDifference:
    """Objective differences between two complete stored branch traces."""

    played_trace_fingerprint: str
    best_trace_fingerprint: str
    played_terminal: str
    best_terminal: str
    net_material_edge_cp: int
    played_only_captures: Tuple[VerifiedLineCapture, ...]
    best_only_captures: Tuple[VerifiedLineCapture, ...]
    played_check_plies: Tuple[int, ...]
    best_check_plies: Tuple[int, ...]
    played_single_reply_plies: Tuple[int, ...]
    best_single_reply_plies: Tuple[int, ...]
    played_promotion_plies: Tuple[int, ...]
    best_promotion_plies: Tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.played_trace_fingerprint or not self.best_trace_fingerprint:
            raise ValueError("branch trace fingerprints are required")
        terminals = {
            "none",
            "initiator_mates",
            "opponent_mates",
            "stalemate",
        }
        if (
            self.played_terminal not in terminals
            or self.best_terminal not in terminals
        ):
            raise ValueError("unknown branch terminal result")
        for values in (
            self.played_check_plies,
            self.best_check_plies,
            self.played_single_reply_plies,
            self.best_single_reply_plies,
            self.played_promotion_plies,
            self.best_promotion_plies,
        ):
            if any(value < 1 for value in values):
                raise ValueError("branch event plies must be positive")

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "played_trace_fingerprint": self.played_trace_fingerprint,
            "best_trace_fingerprint": self.best_trace_fingerprint,
            "played_terminal": self.played_terminal,
            "best_terminal": self.best_terminal,
            "net_material_edge_cp": self.net_material_edge_cp,
            "played_only_captures": [
                item.contract_dict() for item in self.played_only_captures
            ],
            "best_only_captures": [
                item.contract_dict() for item in self.best_only_captures
            ],
            "played_check_plies": list(self.played_check_plies),
            "best_check_plies": list(self.best_check_plies),
            "played_single_reply_plies": list(
                self.played_single_reply_plies
            ),
            "best_single_reply_plies": list(self.best_single_reply_plies),
            "played_promotion_plies": list(self.played_promotion_plies),
            "best_promotion_plies": list(self.best_promotion_plies),
        }


@dataclass(frozen=True)
class VerifiedBranchEvidence:
    """Complete typed branch traces plus their objective difference.

    The trace objects are owned by stored_line_verifier. This wrapper is the
    canonical cause projection and deliberately contains no motif label.
    """

    played_trace: StoredLineReplay
    best_trace: StoredLineReplay
    difference: VerifiedBranchDifference

    def __post_init__(self) -> None:
        for name, trace in (
            ("played", self.played_trace),
            ("best", self.best_trace),
        ):
            if (
                not getattr(trace, "complete", False)
                or not getattr(trace, "events", ())
            ):
                raise ValueError(f"{name} branch trace must be complete")
            if trace.events[0].actor != "initiator":
                raise ValueError(f"{name} branch must start with initiator")
            if trace.fingerprint != getattr(
                self.difference, f"{name}_trace_fingerprint"
            ):
                raise ValueError(f"{name} trace fingerprint mismatch")

    def contract_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION,
            "played": self.played_trace.contract_dict(),
            "best": self.best_trace.contract_dict(),
            "difference": self.difference.contract_dict(),
        }


@dataclass(frozen=True)
class VerifiedCausalStep:
    """One exact setup, constraint, or payoff fact in a proved chain."""

    role: str
    branch: str
    ply: int
    fact_kind: str
    actor: str
    move_san: str
    moving_piece: str
    moving_piece_id: str
    origin: str
    destination: str
    target_piece: Optional[str] = None
    target_piece_id: Optional[str] = None
    target_square: Optional[str] = None
    target_value_cp: Optional[int] = None

    def __post_init__(self) -> None:
        if self.role not in {"setup", "constraint", "payoff"}:
            raise ValueError("unknown causal-step role")
        if self.branch not in {"played", "best"}:
            raise ValueError("unknown causal-step branch")
        if self.ply < 1 or not self.fact_kind:
            raise ValueError("causal step requires ply and fact kind")
        if not self.moving_piece_id:
            raise ValueError("causal step requires persistent piece identity")
        target_values = (
            self.target_piece,
            self.target_piece_id,
            self.target_square,
        )
        if any(target_values) and not all(target_values):
            raise ValueError("causal-step target identity must be complete")
        if self.target_value_cp is not None:
            if not all(target_values):
                raise ValueError(
                    "causal-step target value requires target identity"
                )
            if self.target_value_cp < 0:
                raise ValueError("causal-step target value cannot be negative")

    def contract_dict(self) -> Dict[str, Any]:
        payload = {
            "role": self.role,
            "branch": self.branch,
            "ply": self.ply,
            "fact_kind": self.fact_kind,
            "actor": self.actor,
            "move_san": self.move_san,
            "moving_piece": self.moving_piece,
            "moving_piece_id": self.moving_piece_id,
            "origin": self.origin,
            "destination": self.destination,
        }
        if self.target_piece_id is not None:
            payload.update({
                "target_piece": self.target_piece,
                "target_piece_id": self.target_piece_id,
                "target_square": self.target_square,
            })
            if self.target_value_cp is not None:
                payload["target_value_cp"] = self.target_value_cp
        return payload


@dataclass(frozen=True)
class VerifiedTargetLineOpportunity:
    """Shadow-only target/line chain derived from both stored branches."""

    mechanism: str
    setup: VerifiedCausalStep
    constraint: VerifiedCausalStep
    payoff: VerifiedCausalStep
    branch_evidence: VerifiedBranchEvidence
    settled_material_gain_cp: int
    supporting_quality_ids: Tuple[str, ...] = ()
    supporting_concept_ids: Tuple[str, ...] = ()
    family: str = "target_and_line_geometry_with_payoff"
    quality_id: str = TARGET_LINE_CAUSAL_QUALITY_ID
    proof_version: str = TARGET_LINE_CAUSAL_PROOF_VERSION

    def __post_init__(self) -> None:
        if self.mechanism not in {
            "persistent_piece_attack",
            "target_enters_controlled_square",
            "exchange_sequence",
            "remove_future_attacker",
            "immediate_free_capture",
        }:
            raise ValueError("unknown target/line mechanism")
        if (
            self.setup.role != "setup"
            or self.constraint.role != "constraint"
            or self.payoff.role != "payoff"
        ):
            raise ValueError("causal chain roles are out of order")
        if self.branch_evidence.difference.net_material_edge_cp <= 0:
            raise ValueError("target/line proof requires a positive branch edge")
        if (
            self.payoff.target_value_cp is None
            or self.payoff.target_value_cp < TARGET_LINE_MIN_PAYOFF_CP
        ):
            raise ValueError(
                "target/line payoff must win at least a minor piece"
            )
        if self.settled_material_gain_cp < TARGET_LINE_MIN_PAYOFF_CP:
            raise ValueError(
                "target/line payoff must survive whole-branch settlement"
            )
        if len(self.supporting_quality_ids) != len(
            self.supporting_concept_ids
        ):
            raise ValueError("supporting proof identities must stay paired")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def contract_dict(
        self, *, include_fingerprint: bool = True
    ) -> Dict[str, Any]:
        payload = {
            "schema_version": self.proof_version,
            "family": self.family,
            "mechanism": self.mechanism,
            "quality_id": self.quality_id,
            "setup": self.setup.contract_dict(),
            "constraint": self.constraint.contract_dict(),
            "payoff": self.payoff.contract_dict(),
            "supporting_quality_ids": list(self.supporting_quality_ids),
            "supporting_concept_ids": list(self.supporting_concept_ids),
            "settled_material_gain_cp": self.settled_material_gain_cp,
            "branch_evidence": self.branch_evidence.contract_dict(),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class VerifiedForcingTempoOpportunity:
    """Shadow-only move-order proof from exact cross-branch events."""

    mechanism: str
    setup: VerifiedCausalStep
    constraint: VerifiedCausalStep
    payoff: VerifiedCausalStep
    material_payoff_cp: int
    branch_evidence: VerifiedBranchEvidence
    family: str = "forcing_tempo_and_move_order"
    quality_id: str = FORCING_TEMPO_CAUSAL_QUALITY_ID
    proof_version: str = FORCING_TEMPO_CAUSAL_PROOF_VERSION

    def __post_init__(self) -> None:
        if self.mechanism not in {
            "profitable_exchange_before_retreat",
            "check_displaces_recapturer",
            "forced_exchange_then_escape",
            "forcing_target_displacement",
            "check_saves_future_target",
            "capture_order_compound_payoff",
        }:
            raise ValueError("unknown forcing-tempo mechanism")
        if (
            self.setup.role != "setup"
            or self.constraint.role != "constraint"
            or self.payoff.role != "payoff"
        ):
            raise ValueError("forcing-tempo causal roles are out of order")
        if self.material_payoff_cp <= 0:
            raise ValueError("forcing-tempo proof requires positive payoff")
        if self.branch_evidence.difference.net_material_edge_cp <= 0:
            raise ValueError("forcing-tempo proof requires positive branch edge")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def contract_dict(
        self, *, include_fingerprint: bool = True
    ) -> Dict[str, Any]:
        payload = {
            "schema_version": self.proof_version,
            "family": self.family,
            "mechanism": self.mechanism,
            "quality_id": self.quality_id,
            "setup": self.setup.contract_dict(),
            "constraint": self.constraint.contract_dict(),
            "payoff": self.payoff.contract_dict(),
            "material_payoff_cp": self.material_payoff_cp,
            "branch_evidence": self.branch_evidence.contract_dict(),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class VerifiedEndgameGeometryOpportunity:
    """Shadow-only endgame resource proved by stored-board geometry."""

    mechanism: str
    setup: VerifiedCausalStep
    constraint: VerifiedCausalStep
    payoff: VerifiedCausalStep
    payoff_kind: str
    payoff_value_cp: int
    branch_evidence: VerifiedBranchEvidence
    promotion_piece: Optional[str] = None
    family: str = "exact_endgame_and_promotion_geometry"
    quality_id: str = ENDGAME_GEOMETRY_CAUSAL_QUALITY_ID
    proof_version: str = ENDGAME_GEOMETRY_CAUSAL_PROOF_VERSION

    def __post_init__(self) -> None:
        mechanisms = {
            "king_route_reaches_pawn",
            "immediate_pawn_push_promotes",
            "king_move_preserves_rook_exchange",
            "alternate_rook_preserves_promotion_capture",
        }
        payoff_kinds = {
            "pawn_capture",
            "promotion",
            "checking_rook_exchange",
            "promoted_piece_capture",
        }
        if self.mechanism not in mechanisms:
            raise ValueError("unknown endgame-geometry mechanism")
        if self.payoff_kind not in payoff_kinds:
            raise ValueError("unknown endgame-geometry payoff kind")
        if (
            self.setup.role != "setup"
            or self.constraint.role != "constraint"
            or self.payoff.role != "payoff"
        ):
            raise ValueError("endgame-geometry causal roles are out of order")
        if self.payoff_value_cp <= 0:
            raise ValueError("endgame geometry requires a concrete payoff")
        if self.branch_evidence.difference.net_material_edge_cp <= 0:
            raise ValueError("endgame geometry requires a positive branch edge")
        if self.payoff_kind == "promotion":
            if self.promotion_piece is None:
                raise ValueError("promotion proof requires the promoted piece")
        elif self.promotion_piece is not None:
            raise ValueError("non-promotion proof cannot claim a promotion")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def contract_dict(
        self, *, include_fingerprint: bool = True
    ) -> Dict[str, Any]:
        payload = {
            "schema_version": self.proof_version,
            "family": self.family,
            "mechanism": self.mechanism,
            "quality_id": self.quality_id,
            "payoff_kind": self.payoff_kind,
            "payoff_value_cp": self.payoff_value_cp,
            "setup": self.setup.contract_dict(),
            "constraint": self.constraint.contract_dict(),
            "payoff": self.payoff.contract_dict(),
            "branch_evidence": self.branch_evidence.contract_dict(),
        }
        if self.promotion_piece is not None:
            payload["promotion_piece"] = self.promotion_piece
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class VerifiedBoardTransformationOpportunity:
    """Shadow-only multi-step board transformation with a resolved payoff."""

    mechanism: str
    setup: VerifiedCausalStep
    transformation_steps: Tuple[VerifiedCausalStep, ...]
    payoff: VerifiedCausalStep
    line_net_material_gain_cp: int
    branch_evidence: VerifiedBranchEvidence
    family: str = "board_transformations_with_payoff"
    quality_id: str = BOARD_TRANSFORMATION_CAUSAL_QUALITY_ID
    proof_version: str = BOARD_TRANSFORMATION_CAUSAL_PROOF_VERSION

    def __post_init__(self) -> None:
        if self.mechanism not in {
            "intermediate_exchange_preserves_rook",
            "forced_king_capture_then_queen_capture",
            "sacrifice_opens_rook_capture_route",
        }:
            raise ValueError("unknown board-transformation mechanism")
        if self.setup.role != "setup" or self.payoff.role != "payoff":
            raise ValueError("board-transformation endpoints are invalid")
        if not self.transformation_steps or any(
            step.role != "constraint" for step in self.transformation_steps
        ):
            raise ValueError("board transformation requires ordered steps")
        if self.line_net_material_gain_cp <= 0:
            raise ValueError("board transformation requires a positive line gain")
        if self.branch_evidence.difference.net_material_edge_cp <= 0:
            raise ValueError("board transformation requires a positive branch edge")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def contract_dict(
        self, *, include_fingerprint: bool = True
    ) -> Dict[str, Any]:
        payload = {
            "schema_version": self.proof_version,
            "family": self.family,
            "mechanism": self.mechanism,
            "quality_id": self.quality_id,
            "setup": self.setup.contract_dict(),
            "transformation_steps": [
                step.contract_dict() for step in self.transformation_steps
            ],
            "payoff": self.payoff.contract_dict(),
            "line_net_material_gain_cp": self.line_net_material_gain_cp,
            "branch_evidence": self.branch_evidence.contract_dict(),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class VerifiedLineCause:
    """Caption-only truth rebuilt from complete, already-stored legal lines.

    This does not name a tactical motif or diagnose recurrence. It says only
    what the two stored continuations prove: mate, an exchange ledger, or a
    concrete material opportunity.
    """

    lesson_kind: str
    phase: str
    position_kind: str
    played_move_san: str
    best_move_san: str
    best_move_from: str
    best_move_to: str
    played_line_san: Tuple[str, ...]
    best_line_san: Tuple[str, ...]
    played_captures: Tuple[VerifiedLineCapture, ...]
    best_captures: Tuple[VerifiedLineCapture, ...]
    played_net_material_gain_cp: int
    best_net_material_gain_cp: int
    played_purposes: Tuple[str, ...] = ()
    mate_in: Optional[int] = None
    reply_san: Optional[str] = None
    reply_from: Optional[str] = None
    reply_to: Optional[str] = None
    relationships: Tuple[CauseRelationship, ...] = ()
    branch_evidence: Optional[VerifiedBranchEvidence] = None
    proof_authority: str = "stored_line_verifier.replay_stored_line"
    proof_version: str = VERIFIED_LINE_CAUSE_VERSION

    def __post_init__(self) -> None:
        if self.lesson_kind not in {
            "missed_forced_mate",
            "allowed_forced_mate",
            "exchange_sequence",
            "missed_material_opportunity",
        }:
            raise ValueError("unknown verified-line lesson kind")
        if self.phase not in {"opening", "middlegame", "endgame"}:
            raise ValueError("unknown game phase")
        if self.position_kind not in {"pawn_ending", "general"}:
            raise ValueError("unknown verified-line position kind")
        if not self.played_move_san or not self.best_move_san:
            raise ValueError("verified-line moves must be non-empty")
        chess.parse_square(self.best_move_from)
        chess.parse_square(self.best_move_to)
        if not self.played_line_san or not self.best_line_san:
            raise ValueError("verified lines must be complete and non-empty")
        if self.mate_in is not None and self.mate_in < 1:
            raise ValueError("mate distance must be positive")
        if bool(self.reply_san) != bool(self.reply_from and self.reply_to):
            raise ValueError("reply identity must be complete")
        if (
            self.branch_evidence is not None
            and self.proof_version != VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION
        ):
            raise ValueError("causal branch evidence requires cause schema v2")

    @property
    def first_best_capture(self) -> Optional[VerifiedLineCapture]:
        return self.best_captures[0] if self.best_captures else None

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            self.contract_dict(include_fingerprint=False),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def contract_dict(self, *, include_fingerprint: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": self.proof_version,
            "kind": "verified_stored_line",
            "lesson_kind": self.lesson_kind,
            "phase": self.phase,
            "position_kind": self.position_kind,
            "played_move_san": self.played_move_san,
            "best_move_san": self.best_move_san,
            "best_move_from": self.best_move_from,
            "best_move_to": self.best_move_to,
            "played_line_san": list(self.played_line_san),
            "best_line_san": list(self.best_line_san),
            "played_captures": [item.contract_dict() for item in self.played_captures],
            "best_captures": [item.contract_dict() for item in self.best_captures],
            "played_net_material_gain_cp": self.played_net_material_gain_cp,
            "best_net_material_gain_cp": self.best_net_material_gain_cp,
            "played_purposes": list(self.played_purposes),
            "mate_in": self.mate_in,
            "reply_san": self.reply_san,
            "reply_from": self.reply_from,
            "reply_to": self.reply_to,
            "relationships": [item.contract_dict() for item in self.relationships],
            "proof": {
                "authority": self.proof_authority,
                "version": self.proof_version,
            },
        }
        if self.branch_evidence is not None:
            payload["branch_evidence"] = self.branch_evidence.contract_dict()
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


ReviewTeachingCause = LegalMaterialLossCause | VerifiedLineCause | ExactEndgameCause

# Phase boundary thresholds (mirrors detect_phase in game_decryption_v5_service)
_OPENING_MAX_MOVE_HIGH_PIECES = 10  # if piece_count >= 28
_OPENING_MAX_MOVE_MID_PIECES = 15   # if piece_count >= 24

# Eval thresholds — kept inside the extractor so renderers don't drift
# into their own "winning/losing" semantics. Numeric, deterministic,
# universally reusable. Renderers consume the booleans, not the threshold.
EVAL_WINNING_THRESHOLD_CP = 200    # user_is_winning when user_eval_after >= +200cp
EVAL_LOSING_THRESHOLD_CP = -200    # user_is_losing  when user_eval_after <= -200cp

# Exchange loss threshold — for is_exchange_losing flag (Phase 2).
# A move whose SEE loses more than this counts as a material-losing
# exchange. Set above small-fluctuation noise (a half-pawn).
EXCHANGE_LOSS_THRESHOLD_CP = 50


# ────────────────────────────────────────────────────────────────────
# Helpers (private — no chess judgment, just data)
# ────────────────────────────────────────────────────────────────────

def _normalize_san(san: str) -> str:
    """Strip annotation suffixes (!, ?, +, #) so equality comparisons work."""
    return (san or "").rstrip("!?+#")


def _freeze_state_key(components: Dict[str, Any]) -> Tuple:
    """Convert a state-key components dict to a hashable tuple.

    Used by the Phase 0.5 state-keyed suppression layer
    (see project_suppression_key_overhaul.md).

    Sorted by key so the tuple is stable across detectors. Nested
    lists are converted to tuples; everything else must be already
    hashable (str / int / bool / None).
    """
    items = []
    for k in sorted(components):
        v = components[k]
        if isinstance(v, list):
            v = tuple(v)
        elif isinstance(v, dict):
            v = _freeze_state_key(v)
        items.append((k, v))
    return tuple(items)


def _piece_type_at(board: chess.Board, square: int) -> Optional[int]:
    p = board.piece_at(square)
    return p.piece_type if p else None


def _piece_name_at(board: chess.Board, square: int) -> Optional[str]:
    pt = _piece_type_at(board, square)
    return PIECE_TYPE_NAMES.get(pt) if pt is not None else None


def _attackers_of(board: chess.Board, color: chess.Color, square: int) -> List[Tuple[str, str]]:
    """Return [(square_name, piece_name), ...] for every piece of `color`
    that attacks `square` in the given board position."""
    out: List[Tuple[str, str]] = []
    for sq in board.attackers(color, square):
        p = board.piece_at(sq)
        if p:
            out.append((chess.square_name(sq), PIECE_TYPE_NAMES.get(p.piece_type, "piece")))
    return out


def _detect_phase(board: chess.Board, full_move_number: int) -> str:
    """Game-phase determination mirrored from V5's detect_phase.
    Returns one of: opening | middlegame | endgame."""
    piece_count = len(board.piece_map())
    queens = (
        len(board.pieces(chess.QUEEN, chess.WHITE))
        + len(board.pieces(chess.QUEEN, chess.BLACK))
    )
    if full_move_number <= _OPENING_MAX_MOVE_HIGH_PIECES and piece_count >= 28:
        return "opening"
    if full_move_number <= _OPENING_MAX_MOVE_MID_PIECES and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


# ────────────────────────────────────────────────────────────────────
# Static Exchange Evaluation (SEE) — chess-textbook capture-sequence math.
#
# Walks the recapture sequence on a target square. At each ply, the side
# to move uses their CHEAPEST available attacker and the OPPOSING side
# (now to move) decides whether to continue or stop. The "stop or
# continue" choice is the standard backwards pass:
#     gain[d] = -max(-gain[d], gain[d+1])
#
# Returns SEE in centipawns from the INITIATING side's perspective:
#     SEE > 0  → exchange wins material for initiator
#     SEE == 0 → even trade (or exchange not played)
#     SEE < 0  → exchange loses material; initiator should NOT initiate
#
# Why we need SEE instead of raw attacker/defender counts:
#   - pinned defenders don't really defend
#   - x-ray defenders/attackers need lining up
#   - piece-value imbalance: P-defended Q is still lost to a R attack
#   - recapture order matters (cheapest-first or you waste material)
# Counts get all of these wrong. SEE gets them right by simulation.
#
# Implementation notes:
#   - We exclude pieces already used in earlier captures from being
#     reused (the `consumed` set).
#   - Pinned attackers that can't legally move to the target are skipped
#     (would otherwise hang the king).
#   - En-passant is supported: the captured pawn is identified before
#     the simulated move.
# ────────────────────────────────────────────────────────────────────

def _square_set(squares) -> chess.SquareSet:
    """Tolerant SquareSet builder accepting iterables of squares."""
    if isinstance(squares, chess.SquareSet):
        return squares
    out = chess.SquareSet()
    for sq in squares:
        out.add(sq)
    return out


def _is_pinned_against_target(board: chess.Board, attacker_sq: int, target_sq: int) -> bool:
    """True if the piece on `attacker_sq` is absolutely pinned in a way
    that prevents it from moving to `target_sq` (i.e. moving there
    would expose its own king).

    Uses python-chess `board.pin(color, square)` which returns the set
    of squares the pinned piece CAN move to along the pin line. This
    check is TURN-INDEPENDENT — works whether or not the piece's side
    is currently to move (important inside SEE simulation where we
    flip sides on each ply without actually pushing moves).
    """
    piece = board.piece_at(attacker_sq)
    if not piece:
        return True
    if not board.is_pinned(piece.color, attacker_sq):
        return False
    # Get the squares the pinned piece can still legally reach.
    pin_mask = board.pin(piece.color, attacker_sq)
    # pin_mask may be a SquareSet or an int bitboard depending on version
    if isinstance(pin_mask, chess.SquareSet):
        return target_sq not in pin_mask
    return not (chess.BB_SQUARES[target_sq] & pin_mask)


def detect_relevant_king_pin(
    board: chess.Board,
    mover_color: chess.Color,
    played_move: Optional[chess.Move] = None,
    best_move: Optional[chess.Move] = None,
) -> Optional[Dict[str, Any]]:
    """The mover's most valuable non-pawn piece ABSOLUTELY pinned to its own king,
    when the pin is RELEVANT to this move — the pinned piece is attacked, OR a move
    under discussion (played/best) defends it. Emits GEOMETRIC EVIDENCE only (LAW 3:
    detectors emit geometry, the renderer labels it "pinned"): the pinned piece + its
    square + the pinning enemy slider + its square. Board-verified via board.is_pinned
    + the pin ray. Returns None when no relevant king-pin exists.
    docs/reasoning_correctness_scope.md — the crux the caption kept missing (m9)."""
    king_sq = board.king(mover_color)
    if king_sq is None:
        return None
    enemy = not mover_color
    best_ev: Optional[tuple] = None
    for sq, p in board.piece_map().items():
        if p.color != mover_color or p.piece_type in (chess.PAWN, chess.KING):
            continue
        if not board.is_pinned(mover_color, sq):
            continue
        # The pinner = the enemy slider on the pin ray (board.pin returns the ray).
        ray = board.pin(mover_color, sq)
        ray_sqs = ray if isinstance(ray, chess.SquareSet) else chess.SquareSet(ray)
        pinner_sq = None
        for rsq in ray_sqs:
            rp = board.piece_at(rsq)
            if rp is not None and rp.color == enemy and rp.piece_type in (
                chess.BISHOP, chess.ROOK, chess.QUEEN
            ):
                pinner_sq = rsq
                break
        if pinner_sq is None:
            continue
        # Relevance: attacked, OR a move under discussion adds a defender of it.
        relevant = bool(board.attackers(enemy, sq))
        if not relevant:
            for mv in (played_move, best_move):
                if mv is None or mv.from_square == sq:
                    continue
                b2 = board.copy()
                try:
                    b2.push(mv)
                except Exception:
                    continue
                if sq in b2.attacks(mv.to_square):
                    relevant = True
                    break
        if not relevant:
            continue
        val = PIECE_VALUE_CP.get(p.piece_type, 0)
        if best_ev is None or val > best_ev[0]:
            pinner = board.piece_at(pinner_sq)
            best_ev = (val, {
                "piece": PIECE_TYPE_NAMES.get(p.piece_type, "piece"),
                "square": chess.square_name(sq),
                "pinner_piece": PIECE_TYPE_NAMES.get(pinner.piece_type, "piece"),
                "pinner_square": chess.square_name(pinner_sq),
            })
    return best_ev[1] if best_ev else None


def static_exchange_eval(board: chess.Board, target_sq: int, initiating_side: chess.Color) -> int:
    """
    Compute SEE on `target_sq` assuming `initiating_side` makes the
    first capture using their cheapest legal attacker. Returns net
    material in centipawns from `initiating_side`'s POV.

    If `initiating_side` has no legal attacker on `target_sq`, returns 0.
    """
    # Find cheapest legal NON-KING attacker from initiating_side.
    # Kings are excluded from SEE recapture sequences by convention:
    # a king "recapture" is only legal when no other opponent attacker
    # remains AND the destination square isn't attacked. Modelling that
    # exactly is fragile; the conservative choice (skip the king) yields
    # SEE estimates that are correct in middlegame positions and slightly
    # too-cautious in some K+P endgames. Tracked as a Phase-1 limitation
    # in design doc §18.1.
    attackers = board.attackers(initiating_side, target_sq)
    if not attackers:
        return 0

    cheapest_sq = None
    cheapest_val = 10 ** 9
    for sq in attackers:
        piece = board.piece_at(sq)
        if not piece:
            continue
        if piece.piece_type == chess.KING:
            continue
        if _is_pinned_against_target(board, sq, target_sq):
            continue
        val = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if val < cheapest_val:
            cheapest_val = val
            cheapest_sq = sq

    if cheapest_sq is None:
        return 0

    captured = board.piece_at(target_sq)
    if not captured:
        return 0
    captured_val = PIECE_VALUE_CP.get(captured.piece_type, 0)

    # First capture
    gain = [captured_val]
    current_piece_val = cheapest_val  # piece that just moved onto target
    consumed = {cheapest_sq}
    side = not initiating_side

    while True:
        # Same king-skip rule applies on every recapture ply.
        candidates = board.attackers(side, target_sq) & ~_square_set(consumed)
        cheapest_sq = None
        cheapest_val_iter = 10 ** 9
        for sq in candidates:
            piece = board.piece_at(sq)
            if not piece:
                continue
            if piece.piece_type == chess.KING:
                continue
            if _is_pinned_against_target(board, sq, target_sq):
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val_iter:
                cheapest_val_iter = val
                cheapest_sq = sq

        if cheapest_sq is None:
            break

        gain.append(current_piece_val - gain[-1])
        consumed.add(cheapest_sq)
        current_piece_val = cheapest_val_iter
        side = not side

    # Backwards pass: at each level, the side can choose not to continue.
    for d in range(len(gain) - 2, -1, -1):
        gain[d] = -max(-gain[d], gain[d + 1])

    return gain[0]


def _captured_value_for_legal_move(board: chess.Board, move: chess.Move) -> int:
    """Material removed by one legal capture, including en passant."""
    if board.is_en_passant(move):
        return PIECE_VALUE_CP[chess.PAWN]
    captured = board.piece_at(move.to_square)
    return PIECE_VALUE_CP.get(captured.piece_type, 0) if captured else 0


def _promotion_gain_for_move(move: chess.Move) -> int:
    """Material created when a pawn capture promotes on the exchange square."""
    if move.promotion is None:
        return 0
    return PIECE_VALUE_CP.get(move.promotion, 0) - PIECE_VALUE_CP[chess.PAWN]


def legal_exchange_gain(
    board: chess.Board,
    target_sq: int,
    initiating_side: chess.Color,
    *,
    first_move: Optional[chess.Move] = None,
) -> int:
    """Exact material gain for legal captures on one square.

    Unlike :func:`static_exchange_eval`, this pushes every capture on a copied
    board. That makes newly opened x-rays, king safety, checks, pins and king
    recaptures part of the truth. The side to move may stop at every later
    step; ``first_move`` forces only the already-played first capture.

    This function deliberately requires ``initiating_side == board.turn``.
    The older static evaluator also supports hypothetical captures by the side
    that is *not* to move, which is useful for shape research but is not valid
    evidence that a hanging piece can be taken now.
    """
    if initiating_side != board.turn:
        raise ValueError("legal_exchange_gain requires initiating_side to move")

    def best_gain(work: chess.Board, depth: int = 0) -> int:
        if depth > 32:
            return 0
        best = 0  # the side to move may decline the exchange
        for move in list(work.legal_moves):
            if move.to_square != target_sq or not work.is_capture(move):
                continue
            immediate = (
                _captured_value_for_legal_move(work, move)
                + _promotion_gain_for_move(move)
            )
            after = work.copy(stack=False)
            after.push(move)
            best = max(best, immediate - best_gain(after, depth + 1))
        return best

    if first_move is None:
        return best_gain(board)

    if (
        first_move not in board.legal_moves
        or first_move.to_square != target_sq
        or not board.is_capture(first_move)
    ):
        raise ValueError("first_move must be a legal capture on target_sq")
    immediate = (
        _captured_value_for_legal_move(board, first_move)
        + _promotion_gain_for_move(first_move)
    )
    after = board.copy(stack=False)
    after.push(first_move)
    return immediate - best_gain(after, 1)


def legally_hanging_pieces(
    board: chess.Board,
    owner: chess.Color,
    minimum_gain_cp: int,
) -> List[Dict[str, Any]]:
    """Return owner pieces the side to move can win by legal exchange.

    This is the structured player-facing view of ``legal_exchange_gain``.
    ``owner`` must be the side that just moved, so the opponent is currently
    entitled to capture. The caller supplies the product-specific material
    floor; this function owns only chess truth.
    """
    if board.turn == owner:
        raise ValueError("legally_hanging_pieces requires the opponent to move")

    facts: List[Dict[str, Any]] = []
    for target_sq, piece in board.piece_map().items():
        if piece.color != owner or piece.piece_type == chess.KING:
            continue

        material_loss_cp = legal_exchange_gain(board, target_sq, board.turn)
        if material_loss_cp < minimum_gain_cp:
            continue

        winning_move = None
        winning_gain = 0
        for move in list(board.legal_moves):
            if move.to_square != target_sq or not board.is_capture(move):
                continue
            forced_gain = legal_exchange_gain(
                board,
                target_sq,
                board.turn,
                first_move=move,
            )
            if forced_gain > winning_gain:
                winning_gain = forced_gain
                winning_move = move

        facts.append({
            "square": chess.square_name(target_sq),
            "piece_type": PIECE_TYPE_NAMES.get(piece.piece_type, "piece"),
            "piece_type_id": piece.piece_type,
            "piece_value_cp": PIECE_VALUE_CP.get(piece.piece_type, 0),
            "material_loss_cp": material_loss_cp,
            "winning_capture_san": board.san(winning_move) if winning_move else None,
            "winning_capture_uci": winning_move.uci() if winning_move else None,
        })

    facts.sort(
        key=lambda fact: (
            -fact["material_loss_cp"],
            -fact["piece_value_cp"],
            fact["square"],
        )
    )
    return facts


def verified_move_purposes(
    *, fen_before: str, played_san: str
) -> Tuple[str, ...]:
    """Return only literal, board-verifiable purposes of the played move."""
    try:
        board = chess.Board(fen_before)
        move = board.parse_san(played_san)
    except (ValueError, AssertionError):
        return ()
    piece = board.piece_at(move.from_square)
    opponent = not board.turn
    was_capture = board.is_capture(move)
    home_squares = {
        chess.B1,
        chess.G1,
        chess.C1,
        chess.F1,
        chess.B8,
        chess.G8,
        chess.C8,
        chess.F8,
    }
    purposes: List[str] = []
    board.push(move)
    moved = board.piece_at(move.to_square)
    if board.is_check():
        purposes.append("gives_check")
    if was_capture:
        purposes.append("captures")
    if (
        piece is not None
        and piece.piece_type in {chess.KNIGHT, chess.BISHOP}
        and move.from_square in home_squares
    ):
        purposes.append("develops")
    enemy_king = board.king(opponent)
    if moved is not None and enemy_king is not None:
        king_ring = set(chess.SquareSet(chess.BB_KING_ATTACKS[enemy_king]))
        if set(board.attacks(move.to_square)) & king_ring:
            purposes.append("pressures_king_ring")
    if moved is not None and any(
        (target := board.piece_at(square)) is not None
        and target.color == opponent
        for square in board.attacks(move.to_square)
    ):
        purposes.append("attacks_opponent_piece")
    return tuple(purposes)


def build_legal_material_loss_cause(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    minimum_gain_cp: int,
) -> Optional[LegalMaterialLossCause]:
    """Build one exact loose-piece cause, or abstain when proof is incomplete.

    The best-move purpose is deliberately narrow. It is named only when the
    engine move moves the affected piece, captures its exact attacker, or adds
    a legal defender and the same exchange is no longer winning.
    """
    if not isinstance(minimum_gain_cp, int) or minimum_gain_cp <= 0:
        raise ValueError("minimum_gain_cp must be a positive integer")
    try:
        before = chess.Board(fen_before)
        played = before.parse_san(played_san)
        best = before.parse_san(best_move_san)
    except (ValueError, AssertionError):
        return None

    owner = before.turn
    opponent = not owner
    if played.promotion is not None:
        # Promotion exchanges need dedicated wording for the material created
        # by promotion; the simple piece-for-piece contract cannot say this
        # completely, so it abstains.
        return None
    played_capture: Optional[PieceOnSquare] = None
    played_material_gain_cp = 0
    if before.is_capture(played):
        capture_square = played.to_square
        if before.is_en_passant(played):
            capture_square += -8 if owner == chess.WHITE else 8
        captured = before.piece_at(capture_square)
        if captured is None or captured.color == owner:
            return None
        played_capture = PieceOnSquare(
            piece=PIECE_TYPE_NAMES[captured.piece_type],
            square=chess.square_name(capture_square),
        )
        played_material_gain_cp = PIECE_VALUE_CP.get(captured.piece_type, 0)
    after_played = before.copy(stack=False)
    after_played.push(played)
    hanging = legally_hanging_pieces(after_played, owner, minimum_gain_cp)
    if not hanging:
        return None

    target_fact = hanging[0]
    net_material_loss_cp = (
        int(target_fact.get("material_loss_cp") or 0)
        - played_material_gain_cp
    )
    if net_material_loss_cp < minimum_gain_cp:
        return None
    target_square = chess.parse_square(str(target_fact["square"]))
    target = after_played.piece_at(target_square)
    try:
        reply = chess.Move.from_uci(str(target_fact.get("winning_capture_uci") or ""))
    except ValueError:
        return None
    if reply not in after_played.legal_moves or not after_played.is_capture(reply):
        return None
    attacker = after_played.piece_at(reply.from_square)
    if (
        target is None
        or target.color != owner
        or attacker is None
        or attacker.color != opponent
    ):
        return None

    best_was_capture = before.is_capture(best)
    captured_by_best = (
        before.piece_at(best.to_square) if best_was_capture else None
    )
    after_best = before.copy(stack=False)
    after_best.push(best)
    hanging_after_best = legally_hanging_pieces(
        after_best, owner, minimum_gain_cp
    )
    hanging_squares_after_best = {
        str(item.get("square") or "") for item in hanging_after_best
    }
    target_name = chess.square_name(target_square)
    played_piece = before.piece_at(played.from_square)
    affected_origin_before = (
        played.from_square
        if target_square == played.to_square
        and played_piece is not None
        and played_piece.color == owner
        and played_piece.piece_type == target.piece_type
        else target_square
    )
    target_after_best = after_best.piece_at(target_square)
    affected_remains_on_target = (
        affected_origin_before == target_square
        and target_after_best is not None
        and target_after_best.color == owner
        and target_after_best.piece_type == target.piece_type
    )
    purpose: Optional[str] = None
    if best.from_square == affected_origin_before and chess.square_name(
        best.to_square
    ) not in hanging_squares_after_best:
        purpose = "moves_affected_piece"
    elif (
        affected_remains_on_target
        and
        captured_by_best is not None
        and best.to_square == reply.from_square
        and target_name not in hanging_squares_after_best
    ):
        purpose = "removes_attacker"
    elif (
        affected_remains_on_target
        and
        target_name not in hanging_squares_after_best
        and best.to_square in after_best.attackers(owner, target_square)
    ):
        purpose = "adds_defender"

    return LegalMaterialLossCause(
        affected=PieceOnSquare(
            piece=PIECE_TYPE_NAMES[target.piece_type], square=target_name
        ),
        attacker=PieceOnSquare(
            piece=PIECE_TYPE_NAMES[attacker.piece_type],
            square=chess.square_name(reply.from_square),
        ),
        punishment_san=str(target_fact.get("winning_capture_san") or ""),
        material_loss_cp=net_material_loss_cp,
        best_move_san=best_move_san,
        best_move_purpose=purpose,
        best_move_from=chess.square_name(best.from_square),
        best_move_to=chess.square_name(best.to_square),
        played_capture=played_capture,
        played_purposes=verified_move_purposes(
            fen_before=fen_before, played_san=played_san
        ),
    )


def _verified_line_capture(raw: Any) -> VerifiedLineCapture:
    return VerifiedLineCapture(
        ply=int(raw.ply),
        actor=str(raw.actor),
        move_san=str(raw.move_san),
        origin=str(raw.origin),
        destination=str(raw.destination),
        capturing_piece=str(raw.capturing_piece),
        captured_piece=str(raw.captured_piece),
        captured_square=str(raw.captured_square),
        captured_value_cp=int(raw.captured_value_cp),
    )


def _capture_identity(
    capture: VerifiedLineCapture,
) -> Tuple[str, str, str]:
    """Identify the payoff target without conflating branch move order."""
    return (
        capture.actor,
        capture.captured_piece,
        capture.captured_square,
    )


def _capture_difference(
    primary: Tuple[VerifiedLineCapture, ...],
    comparison: Tuple[VerifiedLineCapture, ...],
) -> Tuple[VerifiedLineCapture, ...]:
    remaining: Dict[Tuple[str, str, str], int] = {}
    for capture in comparison:
        key = _capture_identity(capture)
        remaining[key] = remaining.get(key, 0) + 1
    unique = []
    for capture in primary:
        key = _capture_identity(capture)
        if remaining.get(key, 0):
            remaining[key] -= 1
        else:
            unique.append(capture)
    return tuple(unique)


def _branch_terminal(replay: Any) -> str:
    if replay.checkmate:
        first_actor_color = chess.Board(replay.initial_fen).turn
        if replay.checkmating_color == first_actor_color:
            return "initiator_mates"
        return "opponent_mates"
    if replay.events and replay.events[-1].stalemate:
        return "stalemate"
    return "none"


def _verified_branch_evidence(
    *,
    played_replay: Any,
    best_replay: Any,
    played_captures: Tuple[VerifiedLineCapture, ...],
    best_captures: Tuple[VerifiedLineCapture, ...],
) -> VerifiedBranchEvidence:
    difference = VerifiedBranchDifference(
        played_trace_fingerprint=played_replay.fingerprint,
        best_trace_fingerprint=best_replay.fingerprint,
        played_terminal=_branch_terminal(played_replay),
        best_terminal=_branch_terminal(best_replay),
        net_material_edge_cp=(
            best_replay.net_material_gain_cp
            - played_replay.net_material_gain_cp
        ),
        played_only_captures=_capture_difference(
            played_captures, best_captures
        ),
        best_only_captures=_capture_difference(
            best_captures, played_captures
        ),
        played_check_plies=tuple(
            event.ply for event in played_replay.events if event.gave_check
        ),
        best_check_plies=tuple(
            event.ply for event in best_replay.events if event.gave_check
        ),
        played_single_reply_plies=tuple(
            event.ply
            for event in played_replay.events
            if event.legal_reply_count == 1
        ),
        best_single_reply_plies=tuple(
            event.ply
            for event in best_replay.events
            if event.legal_reply_count == 1
        ),
        played_promotion_plies=tuple(
            event.ply
            for event in played_replay.events
            if event.promotion_piece is not None
        ),
        best_promotion_plies=tuple(
            event.ply
            for event in best_replay.events
            if event.promotion_piece is not None
        ),
    )
    return VerifiedBranchEvidence(
        played_trace=played_replay,
        best_trace=best_replay,
        difference=difference,
    )


def build_verified_branch_evidence(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
) -> Optional[VerifiedBranchEvidence]:
    """Build complete branch traces without selecting a lesson or motif."""
    try:
        before = chess.Board(fen_before)
        played = before.parse_san(played_san)
        best = before.parse_san(best_move_san)
    except (ValueError, AssertionError):
        return None
    if played == best:
        return None

    from services.stored_line_verifier import replay_stored_line

    played_replay = replay_stored_line(
        before,
        played,
        pv_after_played,
        include_events=True,
        resolve_ambiguous_continuation=True,
    )
    best_replay = replay_stored_line(
        before,
        best,
        pv_after_best,
        include_events=True,
        resolve_ambiguous_continuation=True,
    )
    if (
        not played_replay.complete
        or not best_replay.complete
        or not played_replay.events
        or not best_replay.events
    ):
        return None
    return _verified_branch_evidence(
        played_replay=played_replay,
        best_replay=best_replay,
        played_captures=tuple(
            _verified_line_capture(item)
            for item in played_replay.captures
        ),
        best_captures=tuple(
            _verified_line_capture(item)
            for item in best_replay.captures
        ),
    )


def _causal_step(
    event: StoredLineEvent,
    *,
    role: str,
    branch: str,
    fact_kind: str,
    target_piece: Optional[str] = None,
    target_piece_id: Optional[str] = None,
    target_square: Optional[str] = None,
    target_value_cp: Optional[int] = None,
) -> VerifiedCausalStep:
    return VerifiedCausalStep(
        role=role,
        branch=branch,
        ply=event.ply,
        fact_kind=fact_kind,
        actor=event.actor,
        move_san=event.move_san,
        moving_piece=event.moving_piece,
        moving_piece_id=event.moving_piece_id,
        origin=event.origin,
        destination=event.destination,
        target_piece=target_piece,
        target_piece_id=target_piece_id,
        target_square=target_square,
        target_value_cp=target_value_cp,
    )


def _captured_target(event: StoredLineEvent) -> Dict[str, Any]:
    if (
        event.captured_piece is None
        or event.captured_piece_id is None
        or event.captured_square is None
    ):
        raise ValueError("capture event has no complete target identity")
    return {
        "target_piece": event.captured_piece,
        "target_piece_id": event.captured_piece_id,
        "target_square": event.captured_square,
        "target_value_cp": event.captured_value_cp,
    }


def _state_after_for_piece(
    event: StoredLineEvent,
    piece_id: str,
) -> Optional[Any]:
    return next(
        (
            change.after
            for change in event.relation_changes
            if change.after is not None
            and change.after.piece_id == piece_id
        ),
        None,
    )


def _supporting_target_line_proofs(
    *,
    board: chess.Board,
    played_uci: str,
    best_uci: str,
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: Any,
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Reuse canonical exact proof owners; never recreate their motifs."""
    from services.aligned_tactic_puzzle_proof import (
        build_aligned_tactic_proof,
    )
    from services.fork_puzzle_proof import build_fork_proof
    from services.free_piece_puzzle_proof import build_free_piece_proof

    candidates = (
        build_free_piece_proof(board, played_uci, best_uci, cp_loss),
        build_fork_proof(
            board,
            played_uci,
            best_uci,
            pv_after_best,
            cp_loss,
        ),
        build_aligned_tactic_proof(
            board,
            played_uci,
            best_uci,
            pv_after_best,
            cp_loss,
        ),
    )
    verified = tuple(
        bundle
        for bundle in candidates
        if bundle is not None and bundle.verifier.verified
    )
    return (
        tuple(bundle.quality_id for bundle in verified),
        tuple(bundle.verifier.concept_id for bundle in verified),
    )


def _line_piece_material_yield_cp(
    events: Tuple[Any, ...],
    *,
    moving_piece_id: str,
    payoff_event: Any,
) -> int:
    """Return the proved material yield of one physical piece's sequence.

    A captured target is not a payoff when the capturing piece is simply
    recaptured for an equal or worse trade.  When the payoff is the final
    stored ply, a legal immediate recapture is treated pessimistically as a
    loss of the capturing piece.  This closes the four-ply horizon leak while
    preserving genuinely profitable exchanges such as bishop-for-rook.
    """
    later_recapture = next(
        (
            event
            for event in events[payoff_event.ply :]
            if event.captured_piece_id == moving_piece_id
        ),
        None,
    )
    captured_value_cp = sum(
        event.captured_value_cp
        for event in events
        if (
            event.moving_piece_id == moving_piece_id
            and event.captured_piece_id is not None
            and (
                later_recapture is None
                or event.ply < later_recapture.ply
            )
        )
    )
    if later_recapture is not None:
        return captured_value_cp - later_recapture.captured_value_cp

    last_piece_move = next(
        (
            event
            for event in reversed(events)
            if event.moving_piece_id == moving_piece_id
        ),
        payoff_event,
    )
    board = chess.Board(events[-1].fen_after)
    payoff_square = chess.parse_square(last_piece_move.destination)
    payoff_piece = board.piece_at(payoff_square)
    if payoff_piece is None or payoff_piece.color == board.turn:
        return captured_value_cp
    # Resolve the complete legal exchange on the payoff square. A legal
    # recapture is not automatically a refutation when the recapturing piece
    # is itself lost (for example ...Qxd4 Rxd4). The canonical legal exchange
    # evaluator pushes every capture, includes king legality and x-rays, and
    # lets each later side stop. Subtract only material the opponent can
    # actually win from initiating that exchange.
    return captured_value_cp - legal_exchange_gain(
        board,
        payoff_square,
        board.turn,
    )


def _causal_sequence_material_yield_cp(
    events: Tuple[Any, ...],
    *,
    payoff_piece_id: str,
    payoff_event: Any,
) -> int:
    """Net material proved by the complete sequence through one payoff.

    Every capture before the payoff is counted for its side, so an equal queen
    trade contributes zero rather than being mistaken for a queen sacrifice.
    The payoff piece's canonical yield then adds any pessimistic post-horizon
    recapture adjustment without counting its captures twice.
    """
    through_payoff = sum(
        (
            event.captured_value_cp
            if event.actor == "initiator"
            else -event.captured_value_cp
        )
        for event in events[: payoff_event.ply]
        if event.captured_piece_id is not None
    )
    payoff_piece_captures = sum(
        event.captured_value_cp
        for event in events[: payoff_event.ply]
        if (
            event.actor == "initiator"
            and event.moving_piece_id == payoff_piece_id
            and event.captured_piece_id is not None
        )
    )
    payoff_piece_yield = _line_piece_material_yield_cp(
        events,
        moving_piece_id=payoff_piece_id,
        payoff_event=payoff_event,
    )
    return through_payoff + payoff_piece_yield - payoff_piece_captures


def _piece_survives_stored_horizon(
    events: Tuple[Any, ...],
    *,
    piece_id: str,
) -> bool:
    """Require an escaping piece to remain safe through the stored horizon.

    A line ending immediately before a legal recapture does not prove that the
    piece was saved. If the same side is to move at the horizon, it has already
    survived to its next turn; otherwise every legal immediate capture is
    checked pessimistically.
    """
    if any(event.captured_piece_id == piece_id for event in events):
        return False
    last_piece_move = next(
        (
            event
            for event in reversed(events)
            if event.moving_piece_id == piece_id
        ),
        None,
    )
    if last_piece_move is None:
        return False
    board = chess.Board(events[-1].fen_after)
    square = chess.parse_square(last_piece_move.destination)
    piece = board.piece_at(square)
    if piece is None:
        return False
    if piece.color == board.turn:
        return True
    return not any(
        board.is_capture(move) and move.to_square == square
        for move in board.legal_moves
    )


def _piece_name_value_cp(piece_name: str) -> int:
    return next(
        (
            PIECE_VALUE_CP[piece_type]
            for piece_type, name in PIECE_TYPE_NAMES.items()
            if name == piece_name
        ),
        0,
    )


def _moved_piece_target(event: Any) -> Dict[str, Any]:
    return {
        "target_piece": event.moving_piece,
        "target_piece_id": event.moving_piece_id,
        "target_square": event.destination,
        "target_value_cp": _piece_name_value_cp(event.moving_piece),
    }


def _persistent_piece_attack_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep]]:
    best_events = evidence.best_trace.events
    if not best_events:
        return None
    setup_event = best_events[0]
    setup_state = _state_after_for_piece(
        setup_event, setup_event.moving_piece_id
    )
    if setup_state is None:
        return None
    played_captures = {
        event.captured_piece_id
        for event in evidence.played_trace.events
        if event.actor == "initiator" and event.captured_piece_id
    }
    candidates = []
    for payoff_event in best_events[1:]:
        if (
            payoff_event.actor != "initiator"
            or payoff_event.moving_piece_id != setup_event.moving_piece_id
            or payoff_event.captured_piece_id is None
            or payoff_event.captured_piece_id in played_captures
            or payoff_event.destination not in setup_state.attack_squares
        ):
            continue
        intervening = tuple(
            event
            for event in best_events[1 : payoff_event.ply - 1]
            if event.moving_piece_id == setup_event.moving_piece_id
        )
        if intervening:
            continue
        causal_sequence_yield_cp = _causal_sequence_material_yield_cp(
            best_events,
            payoff_piece_id=setup_event.moving_piece_id,
            payoff_event=payoff_event,
        )
        if causal_sequence_yield_cp <= 0:
            continue
        target_moves = tuple(
            event
            for event in best_events[1 : payoff_event.ply - 1]
            if event.moving_piece_id == payoff_event.captured_piece_id
        )
        if target_moves:
            target_move = target_moves[-1]
            if target_move.destination != payoff_event.destination:
                continue
            mechanism = "target_enters_controlled_square"
            constraint = _causal_step(
                target_move,
                role="constraint",
                branch="best",
                fact_kind="target_enters_controlled_square",
                target_piece=setup_event.moving_piece,
                target_piece_id=setup_event.moving_piece_id,
                target_square=setup_event.destination,
            )
        else:
            initial_target_square = payoff_event.captured_piece_id.rsplit(
                ":", 1
            )[-1]
            if initial_target_square != payoff_event.destination:
                continue
            target_state = _state_after_for_piece(
                setup_event, payoff_event.captured_piece_id
            )
            fact_kind = (
                "pinned_target"
                if target_state is not None
                and target_state.pinned_to_king
                else "target_starts_on_controlled_square"
            )
            mechanism = "persistent_piece_attack"
            constraint = _causal_step(
                setup_event,
                role="constraint",
                branch="best",
                fact_kind=fact_kind,
                **_captured_target(payoff_event),
            )
        candidates.append((
            payoff_event.captured_value_cp,
            -payoff_event.ply,
            mechanism,
            _causal_step(
                setup_event,
                role="setup",
                branch="best",
                fact_kind="establishes_persistent_attack",
                **_captured_target(payoff_event),
            ),
            constraint,
            _causal_step(
                payoff_event,
                role="payoff",
                branch="best",
                fact_kind="same_piece_captures_target",
                **_captured_target(payoff_event),
            ),
        ))
    if not candidates:
        return None
    _, _, mechanism, setup, constraint, payoff = max(
        candidates, key=lambda item: item[:2]
    )
    return mechanism, setup, constraint, payoff


def _exchange_sequence_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep]]:
    events = evidence.best_trace.events
    if len(events) < 3:
        return None
    first, second, third = events[:3]
    played_initiator_captures = {
        event.captured_piece_id
        for event in evidence.played_trace.events
        if event.actor == "initiator" and event.captured_piece_id
    }
    if (
        first.actor != "initiator"
        or first.captured_piece_id is None
        or first.captured_piece_id in played_initiator_captures
        or second.actor != "opponent"
        or second.captured_piece_id != first.moving_piece_id
        or third.actor != "initiator"
        or third.captured_piece_id != second.moving_piece_id
    ):
        return None
    return (
        "exchange_sequence",
        _causal_step(
            first,
            role="setup",
            branch="best",
            fact_kind="initiates_exchange",
            **_captured_target(first),
        ),
        _causal_step(
            second,
            role="constraint",
            branch="best",
            fact_kind="opponent_recaptures",
            **_captured_target(second),
        ),
        _causal_step(
            third,
            role="payoff",
            branch="best",
            fact_kind="initiator_recaptures",
            **_captured_target(third),
        ),
    )


def _remove_future_attacker_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep]]:
    best_events = evidence.best_trace.events
    if not best_events or best_events[0].captured_piece_id is None:
        return None
    setup_event = best_events[0]
    future_attacker_id = setup_event.captured_piece_id
    best_opponent_losses = {
        event.captured_piece_id
        for event in best_events
        if event.actor == "opponent" and event.captured_piece_id
    }
    candidates = []
    for contrast_event in evidence.played_trace.events:
        if (
            contrast_event.actor != "opponent"
            or contrast_event.moving_piece_id != future_attacker_id
            or contrast_event.captured_piece_id is None
            or contrast_event.captured_piece_id in best_opponent_losses
        ):
            continue
        candidates.append((
            contrast_event.captured_value_cp,
            -contrast_event.ply,
            contrast_event,
        ))
    if not candidates:
        return None
    _, _, contrast_event = max(
        candidates, key=lambda item: item[:2]
    )
    return (
        "remove_future_attacker",
        _causal_step(
            setup_event,
            role="setup",
            branch="best",
            fact_kind="captures_future_attacker",
            **_captured_target(setup_event),
        ),
        _causal_step(
            contrast_event,
            role="constraint",
            branch="played",
            fact_kind="same_piece_attacks_in_played_branch",
            **_captured_target(contrast_event),
        ),
        _causal_step(
            contrast_event,
            role="payoff",
            branch="played",
            fact_kind="piece_loss_absent_from_best_branch",
            **_captured_target(contrast_event),
        ),
    )


def _immediate_free_capture_chain(
    evidence: VerifiedBranchEvidence,
    supporting_quality_ids: Tuple[str, ...],
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep]]:
    if "tactic:free_piece_exact" not in supporting_quality_ids:
        return None
    event = evidence.best_trace.events[0]
    if event.captured_piece_id is None:
        return None
    if _line_piece_material_yield_cp(
        evidence.best_trace.events,
        moving_piece_id=event.moving_piece_id,
        payoff_event=event,
    ) <= 0:
        return None
    if any(
        played_event.actor == "initiator"
        and played_event.captured_piece_id == event.captured_piece_id
        for played_event in evidence.played_trace.events
    ):
        return None
    target = _captured_target(event)
    return (
        "immediate_free_capture",
        _causal_step(
            event,
            role="setup",
            branch="best",
            fact_kind="loose_target_is_capturable",
            **target,
        ),
        _causal_step(
            event,
            role="constraint",
            branch="best",
            fact_kind="no_legal_immediate_recapture",
            **target,
        ),
        _causal_step(
            event,
            role="payoff",
            branch="best",
            fact_kind="captures_loose_target",
            **target,
        ),
    )


def build_target_line_opportunity_proof(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: Any,
) -> Optional[VerifiedTargetLineOpportunity]:
    """Build one shadow target/line chain without authoring a motif claim."""
    evidence = build_verified_branch_evidence(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=pv_after_played,
        pv_after_best=pv_after_best,
    )
    if (
        evidence is None
        or evidence.difference.net_material_edge_cp <= 0
    ):
        return None
    board = chess.Board(fen_before)
    played = board.parse_san(played_san)
    best = board.parse_san(best_move_san)
    quality_ids, concept_ids = _supporting_target_line_proofs(
        board=board,
        played_uci=played.uci(),
        best_uci=best.uci(),
        pv_after_best=pv_after_best,
        cp_loss=cp_loss,
    )
    chain = next(
        (
            candidate
            for candidate in (
                _persistent_piece_attack_chain(evidence),
                _exchange_sequence_chain(evidence),
                _remove_future_attacker_chain(evidence),
                _immediate_free_capture_chain(evidence, quality_ids),
            )
            if (
                candidate is not None
                and candidate[3].target_value_cp is not None
                and candidate[3].target_value_cp
                >= TARGET_LINE_MIN_PAYOFF_CP
            )
        ),
        None,
    )
    if chain is None:
        return None
    mechanism, setup, constraint, payoff = chain
    # Local import avoids the existing module cycle: the stored-line verifier
    # reads this module's canonical piece-value table.
    from services.stored_line_verifier import settled_material_gain_cp

    settled_gain = settled_material_gain_cp(evidence.best_trace)
    if settled_gain is None or settled_gain < TARGET_LINE_MIN_PAYOFF_CP:
        return None
    return VerifiedTargetLineOpportunity(
        mechanism=mechanism,
        setup=setup,
        constraint=constraint,
        payoff=payoff,
        branch_evidence=evidence,
        settled_material_gain_cp=settled_gain,
        supporting_quality_ids=quality_ids,
        supporting_concept_ids=concept_ids,
    )


def _profitable_exchange_tempo_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    events = evidence.best_trace.events
    if len(events) < 2:
        return None
    first, second = events[:2]
    if (
        first.actor != "initiator"
        or first.captured_piece_id is None
        or second.actor != "opponent"
        or second.captured_piece_id != first.moving_piece_id
    ):
        return None
    material_payoff_cp = (
        first.captured_value_cp - second.captured_value_cp
    )
    if material_payoff_cp <= 0 or any(
        event.actor == "initiator"
        and event.captured_piece_id == first.captured_piece_id
        for event in evidence.played_trace.events
    ):
        return None
    return (
        "profitable_exchange_before_retreat",
        _causal_step(
            first,
            role="setup",
            branch="best",
            fact_kind="captures_higher_value_target_first",
            **_captured_target(first),
        ),
        _causal_step(
            second,
            role="constraint",
            branch="best",
            fact_kind="opponent_recaptures",
            **_captured_target(second),
        ),
        _causal_step(
            first,
            role="payoff",
            branch="best",
            fact_kind="exchange_remains_materially_profitable",
            **_captured_target(first),
        ),
        material_payoff_cp,
    )


def _check_displaces_recapturer_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    played = evidence.played_trace.events
    best = evidence.best_trace.events
    if len(played) < 2 or len(best) < 3:
        return None
    played_capture, played_recapture = played[:2]
    setup, king_move, payoff = best[:3]
    if (
        played_capture.actor != "initiator"
        or played_capture.captured_piece_id is None
        or played_recapture.actor != "opponent"
        or played_recapture.moving_piece != "king"
        or played_recapture.captured_piece_id
        != played_capture.moving_piece_id
        or not setup.gave_check
        or king_move.actor != "opponent"
        or king_move.moving_piece_id != played_recapture.moving_piece_id
        or payoff.actor != "initiator"
        or payoff.moving_piece_id != played_capture.moving_piece_id
        or payoff.captured_piece_id != played_capture.captured_piece_id
    ):
        return None
    material_payoff_cp = _line_piece_material_yield_cp(
        best,
        moving_piece_id=payoff.moving_piece_id,
        payoff_event=payoff,
    )
    if material_payoff_cp <= 0:
        return None
    return (
        "check_displaces_recapturer",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="inserts_check_before_capture",
            **(
                _captured_target(setup)
                if setup.captured_piece_id is not None
                else _moved_piece_target(setup)
            ),
        ),
        _causal_step(
            king_move,
            role="constraint",
            branch="best",
            fact_kind="recapturing_king_is_displaced",
            **_moved_piece_target(king_move),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="same_target_captured_without_king_recapture",
            **_captured_target(payoff),
        ),
        material_payoff_cp,
    )


def _forced_exchange_then_escape_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if len(best) < 3:
        return None
    setup, recapture = best[:2]
    if (
        not setup.gave_check
        or setup.captured_piece_id is None
        or setup.legal_reply_count != 1
        or recapture.actor != "opponent"
        or recapture.captured_piece_id != setup.moving_piece_id
    ):
        return None
    played_losses = [
        event
        for event in played
        if event.actor == "opponent" and event.captured_piece_id
    ]
    for loss in sorted(
        played_losses, key=lambda event: (-event.captured_value_cp, event.ply)
    ):
        escape = next(
            (
                event
                for event in best[2:]
                if (
                    event.actor == "initiator"
                    and event.moving_piece_id == loss.captured_piece_id
                    and event.captured_piece_id is None
                )
            ),
            None,
        )
        if (
            escape is None
            or not _piece_survives_stored_horizon(
                best,
                piece_id=loss.captured_piece_id,
            )
        ):
            continue
        return (
            "forced_exchange_then_escape",
            _causal_step(
                setup,
                role="setup",
                branch="best",
                fact_kind="forces_exchange_with_check",
                **_captured_target(setup),
            ),
            _causal_step(
                recapture,
                role="constraint",
                branch="best",
                fact_kind="sole_reply_completes_exchange",
                **_captured_target(recapture),
            ),
            _causal_step(
                escape,
                role="payoff",
                branch="best",
                fact_kind="endangered_piece_escapes_after_exchange",
                **_moved_piece_target(escape),
            ),
            loss.captured_value_cp,
        )
    return None


def _forcing_target_displacement_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    best = evidence.best_trace.events
    if len(best) < 3:
        return None
    setup, displaced, payoff = best[:3]
    if (
        not setup.gave_check
        or setup.legal_reply_count != 1
        or displaced.actor != "opponent"
        or payoff.actor != "initiator"
        or payoff.moving_piece_id != setup.moving_piece_id
        or payoff.captured_piece_id != displaced.moving_piece_id
        or payoff.destination not in (
            _state_after_for_piece(setup, setup.moving_piece_id).attack_squares
            if _state_after_for_piece(setup, setup.moving_piece_id)
            is not None
            else ()
        )
    ):
        return None
    material_payoff_cp = _line_piece_material_yield_cp(
        best,
        moving_piece_id=setup.moving_piece_id,
        payoff_event=payoff,
    )
    if material_payoff_cp <= 0:
        return None
    return (
        "forcing_target_displacement",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="check_controls_forced_reply_square",
            **_captured_target(payoff),
        ),
        _causal_step(
            displaced,
            role="constraint",
            branch="best",
            fact_kind="sole_reply_moves_target_into_control",
            **_moved_piece_target(displaced),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="forcing_piece_captures_displaced_target",
            **_captured_target(payoff),
        ),
        material_payoff_cp,
    )


def _check_saves_future_target_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    best = evidence.best_trace.events
    if not best or not best[0].gave_check:
        return None
    setup = best[0]
    played_loss = next(
        (
            event
            for event in evidence.played_trace.events
            if (
                event.actor == "opponent"
                and event.captured_piece_id == setup.moving_piece_id
            )
        ),
        None,
    )
    if (
        played_loss is None
        or not _piece_survives_stored_horizon(
            best,
            piece_id=setup.moving_piece_id,
        )
    ):
        return None
    return (
        "check_saves_future_target",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="moves_endangered_piece_with_check",
            **_moved_piece_target(setup),
        ),
        _causal_step(
            played_loss,
            role="constraint",
            branch="played",
            fact_kind="same_piece_is_captured_without_tempo",
            **_captured_target(played_loss),
        ),
        _causal_step(
            setup,
            role="payoff",
            branch="best",
            fact_kind="piece_survives_by_moving_with_tempo",
            **_moved_piece_target(setup),
        ),
        played_loss.captured_value_cp,
    )


def _capture_order_compound_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, int]]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if not best or best[0].captured_piece_id is None:
        return None
    moving_piece_id = best[0].moving_piece_id
    best_captures = [
        event
        for event in best
        if (
            event.actor == "initiator"
            and event.moving_piece_id == moving_piece_id
            and event.captured_piece_id is not None
        )
    ]
    if len(best_captures) < 2:
        return None
    played_capture = next(
        (
            event
            for event in played
            if (
                event.actor == "initiator"
                and event.moving_piece_id == moving_piece_id
                and event.captured_piece_id is not None
            )
        ),
        None,
    )
    played_loss = next(
        (
            event
            for event in played
            if event.captured_piece_id == moving_piece_id
        ),
        None,
    )
    if played_capture is None or played_loss is None:
        return None
    best_payoff = _line_piece_material_yield_cp(
        best,
        moving_piece_id=moving_piece_id,
        payoff_event=best_captures[-1],
    )
    played_payoff = _line_piece_material_yield_cp(
        played,
        moving_piece_id=moving_piece_id,
        payoff_event=played_capture,
    )
    material_payoff_cp = best_payoff - played_payoff
    if material_payoff_cp <= 0:
        return None
    return (
        "capture_order_compound_payoff",
        _causal_step(
            best[0],
            role="setup",
            branch="best",
            fact_kind="starts_capture_route_with_correct_target",
            **_captured_target(best[0]),
        ),
        _causal_step(
            played_loss,
            role="constraint",
            branch="played",
            fact_kind="same_piece_is_lost_in_played_order",
            **_captured_target(played_loss),
        ),
        _causal_step(
            best_captures[-1],
            role="payoff",
            branch="best",
            fact_kind="same_piece_completes_compound_capture_route",
            **_captured_target(best_captures[-1]),
        ),
        material_payoff_cp,
    )


def build_forcing_tempo_opportunity_proof(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: Any,
) -> Optional[VerifiedForcingTempoOpportunity]:
    """Prove a forcing move-order payoff from both complete stored lines."""
    if build_target_line_opportunity_proof(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=pv_after_played,
        pv_after_best=pv_after_best,
        cp_loss=cp_loss,
    ) is not None:
        return None
    evidence = build_verified_branch_evidence(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=pv_after_played,
        pv_after_best=pv_after_best,
    )
    if (
        evidence is None
        or evidence.difference.net_material_edge_cp <= 0
    ):
        return None
    chain = (
        _profitable_exchange_tempo_chain(evidence)
        or _check_displaces_recapturer_chain(evidence)
        or _forced_exchange_then_escape_chain(evidence)
        or _forcing_target_displacement_chain(evidence)
        or _check_saves_future_target_chain(evidence)
        or _capture_order_compound_chain(evidence)
    )
    if chain is None:
        return None
    mechanism, setup, constraint, payoff, material_payoff_cp = chain
    return VerifiedForcingTempoOpportunity(
        mechanism=mechanism,
        setup=setup,
        constraint=constraint,
        payoff=payoff,
        material_payoff_cp=material_payoff_cp,
        branch_evidence=evidence,
    )


def _king_route_reaches_pawn_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, str, int, Optional[str]]]:
    board = chess.Board(evidence.best_trace.initial_fen)
    if any(
        piece.piece_type not in {chess.KING, chess.PAWN}
        for piece in board.piece_map().values()
    ):
        return None
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if not best or best[0].moving_piece != "king":
        return None
    king_id = best[0].moving_piece_id
    payoff = next(
        (
            event
            for event in best[1:]
            if (
                event.actor == "initiator"
                and event.moving_piece_id == king_id
                and event.captured_piece == "pawn"
            )
        ),
        None,
    )
    if payoff is None or any(
        event.actor == "initiator"
        and event.captured_piece_id == payoff.captured_piece_id
        for event in played
    ):
        return None
    route_step = next(
        (
            event
            for event in reversed(best[1 : payoff.ply - 1])
            if (
                event.actor == "initiator"
                and event.moving_piece_id == king_id
            )
        ),
        None,
    )
    if route_step is None:
        return None
    material_yield = _line_piece_material_yield_cp(
        best,
        moving_piece_id=king_id,
        payoff_event=payoff,
    )
    if material_yield <= 0:
        return None
    return (
        "king_route_reaches_pawn",
        _causal_step(
            best[0],
            role="setup",
            branch="best",
            fact_kind="king_starts_capture_route",
            **_moved_piece_target(best[0]),
        ),
        _causal_step(
            route_step,
            role="constraint",
            branch="best",
            fact_kind="same_king_continues_route",
            **_moved_piece_target(route_step),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="same_king_reaches_pawn",
            **_captured_target(payoff),
        ),
        "pawn_capture",
        payoff.captured_value_cp,
        None,
    )


def _immediate_pawn_push_promotes_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, str, int, Optional[str]]]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if (
        not best
        or best[0].moving_piece != "pawn"
        or best[0].captured_piece_id is not None
        or best[0].promotion_piece is not None
    ):
        return None
    pawn_id = best[0].moving_piece_id
    promotion = next(
        (
            event
            for event in best[1:]
            if (
                event.actor == "initiator"
                and event.moving_piece_id == pawn_id
                and event.promotion_piece is not None
            )
        ),
        None,
    )
    played_push = next(
        (
            event
            for event in played
            if (
                event.actor == "initiator"
                and event.moving_piece_id == pawn_id
                and event.destination == best[0].destination
            )
        ),
        None,
    )
    if (
        promotion is None
        or played_push is None
        or played_push.ply <= best[0].ply
        or any(
            event.moving_piece_id == pawn_id
            and event.promotion_piece is not None
            for event in played
        )
        or not _piece_survives_stored_horizon(best, piece_id=pawn_id)
    ):
        return None
    promoted_type = chess.PIECE_NAMES.index(promotion.promotion_piece)
    promotion_gain = (
        PIECE_VALUE_CP[promoted_type] - PIECE_VALUE_CP[chess.PAWN]
    )
    if promotion_gain <= 0:
        return None
    return (
        "immediate_pawn_push_promotes",
        _causal_step(
            best[0],
            role="setup",
            branch="best",
            fact_kind="pushes_passed_pawn_immediately",
            **_moved_piece_target(best[0]),
        ),
        _causal_step(
            played_push,
            role="constraint",
            branch="played",
            fact_kind="same_pawn_push_arrives_later",
            **_moved_piece_target(played_push),
        ),
        _causal_step(
            promotion,
            role="payoff",
            branch="best",
            fact_kind="same_pawn_promotes_in_stored_line",
            **_moved_piece_target(promotion),
        ),
        "promotion",
        promotion_gain,
        promotion.promotion_piece,
    )


def _king_move_preserves_rook_exchange_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, str, int, Optional[str]]]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if (
        not best
        or not played
        or best[0].moving_piece != "king"
        or played[0].moving_piece != "rook"
    ):
        return None
    rook_id = played[0].moving_piece_id
    payoff = next(
        (
            event
            for event in best[1:]
            if (
                event.actor == "initiator"
                and event.moving_piece_id == rook_id
                and event.captured_piece == "rook"
            )
        ),
        None,
    )
    if payoff is None or payoff.ply < 2:
        return None
    checking_rook = best[payoff.ply - 2]
    if (
        not checking_rook.gave_check
        or payoff.captured_piece_id != checking_rook.moving_piece_id
        or any(
            event.moving_piece_id == rook_id
            for event in best[: payoff.ply - 1]
        )
        or any(
            event.actor == "initiator"
            and event.captured_piece_id == checking_rook.moving_piece_id
            for event in played
        )
    ):
        return None
    return (
        "king_move_preserves_rook_exchange",
        _causal_step(
            best[0],
            role="setup",
            branch="best",
            fact_kind="king_moves_without_displacing_rook",
            **_moved_piece_target(best[0]),
        ),
        _causal_step(
            checking_rook,
            role="constraint",
            branch="best",
            fact_kind="opponent_rook_gives_check_on_capture_line",
            **_moved_piece_target(checking_rook),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="preserved_rook_exchanges_checking_rook",
            **_captured_target(payoff),
        ),
        "checking_rook_exchange",
        payoff.captured_value_cp,
        None,
    )


def _alternate_rook_preserves_promotion_capture_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[Tuple[str, VerifiedCausalStep, VerifiedCausalStep, VerifiedCausalStep, str, int, Optional[str]]]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if (
        not best
        or not played
        or best[0].moving_piece != "rook"
        or played[0].moving_piece != "rook"
        or best[0].moving_piece_id == played[0].moving_piece_id
        or best[0].captured_piece_id is None
        or best[0].captured_piece_id != played[0].captured_piece_id
    ):
        return None
    best_promotion = next(
        (event for event in best if event.promotion_piece is not None),
        None,
    )
    played_promotion = next(
        (event for event in played if event.promotion_piece is not None),
        None,
    )
    if (
        best_promotion is None
        or played_promotion is None
        or best_promotion.moving_piece_id
        != played_promotion.moving_piece_id
        or best_promotion.destination != played_promotion.destination
        or best_promotion.promotion_piece != played_promotion.promotion_piece
    ):
        return None
    preserved_rook_id = played[0].moving_piece_id
    payoff = next(
        (
            event
            for event in best
            if (
                event.actor == "initiator"
                and event.moving_piece_id == preserved_rook_id
                and event.captured_piece_id == best_promotion.moving_piece_id
            )
        ),
        None,
    )
    if (
        payoff is None
        or not _piece_survives_stored_horizon(
            played,
            piece_id=played_promotion.moving_piece_id,
        )
        or any(
            event.actor == "initiator"
            and event.captured_piece_id == played_promotion.moving_piece_id
            for event in played
        )
        or _line_piece_material_yield_cp(
            best,
            moving_piece_id=preserved_rook_id,
            payoff_event=payoff,
        ) <= 0
    ):
        return None
    return (
        "alternate_rook_preserves_promotion_capture",
        _causal_step(
            best[0],
            role="setup",
            branch="best",
            fact_kind="other_rook_captures_blocker",
            **_captured_target(best[0]),
        ),
        _causal_step(
            best_promotion,
            role="constraint",
            branch="best",
            fact_kind="opponent_pawn_promotes_on_first_rank",
            **_moved_piece_target(best_promotion),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="preserved_rook_captures_promoted_piece",
            **_captured_target(payoff),
        ),
        "promoted_piece_capture",
        payoff.captured_value_cp,
        None,
    )


def build_endgame_geometry_opportunity_proof(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: Any,
) -> Optional[VerifiedEndgameGeometryOpportunity]:
    """Prove one endgame resource without asserting an unproved result."""
    common = {
        "fen_before": fen_before,
        "played_san": played_san,
        "best_move_san": best_move_san,
        "pv_after_played": pv_after_played,
        "pv_after_best": pv_after_best,
        "cp_loss": cp_loss,
    }
    if (
        build_target_line_opportunity_proof(**common) is not None
        or build_forcing_tempo_opportunity_proof(**common) is not None
    ):
        return None
    evidence = build_verified_branch_evidence(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=pv_after_played,
        pv_after_best=pv_after_best,
    )
    if (
        evidence is None
        or evidence.difference.net_material_edge_cp <= 0
        or _detect_phase(chess.Board(fen_before), chess.Board(fen_before).fullmove_number)
        != "endgame"
    ):
        return None
    chain = (
        _king_route_reaches_pawn_chain(evidence)
        or _immediate_pawn_push_promotes_chain(evidence)
        or _king_move_preserves_rook_exchange_chain(evidence)
        or _alternate_rook_preserves_promotion_capture_chain(evidence)
    )
    if chain is None:
        return None
    (
        mechanism,
        setup,
        constraint,
        payoff,
        payoff_kind,
        payoff_value_cp,
        promotion_piece,
    ) = chain
    return VerifiedEndgameGeometryOpportunity(
        mechanism=mechanism,
        setup=setup,
        constraint=constraint,
        payoff=payoff,
        payoff_kind=payoff_kind,
        payoff_value_cp=payoff_value_cp,
        promotion_piece=promotion_piece,
        branch_evidence=evidence,
    )


def _line_net_material_after_horizon_exchange_cp(
    trace: Any,
    *,
    payoff_event: Any,
) -> int:
    """Resolve any immediate legal exchange after the stored payoff line."""
    events = trace.events
    if not events or payoff_event not in events:
        return 0
    if any(
        event.ply > payoff_event.ply
        and event.captured_piece_id == payoff_event.moving_piece_id
        for event in events
    ):
        return trace.net_material_gain_cp
    last_piece_move = next(
        (
            event
            for event in reversed(events)
            if event.moving_piece_id == payoff_event.moving_piece_id
        ),
        None,
    )
    if last_piece_move is None:
        return 0
    board = chess.Board(events[-1].fen_after)
    square = chess.parse_square(last_piece_move.destination)
    piece = board.piece_at(square)
    if piece is None or piece.color == board.turn:
        return trace.net_material_gain_cp
    return trace.net_material_gain_cp - legal_exchange_gain(
        board,
        square,
        board.turn,
    )


def _transformation_step(
    event: Any,
    *,
    fact_kind: str,
) -> VerifiedCausalStep:
    target = (
        _captured_target(event)
        if event.captured_piece_id is not None
        else _moved_piece_target(event)
    )
    return _causal_step(
        event,
        role="constraint",
        branch="best",
        fact_kind=fact_kind,
        **target,
    )


def _intermediate_exchange_preserves_rook_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[
    Tuple[
        str,
        VerifiedCausalStep,
        Tuple[VerifiedCausalStep, ...],
        VerifiedCausalStep,
        int,
    ]
]:
    best = evidence.best_trace.events
    played = evidence.played_trace.events
    if len(best) < 5 or len(played) < 2:
        return None
    setup, recapture = best[:2]
    if (
        setup.actor != "initiator"
        or setup.captured_piece_id is None
        or recapture.actor != "opponent"
        or recapture.captured_piece_id != setup.moving_piece_id
    ):
        return None
    played_rook_loss = next(
        (
            event
            for event in played
            if (
                event.actor == "opponent"
                and event.captured_piece == "rook"
                and event.captured_piece_id is not None
            )
        ),
        None,
    )
    if played_rook_loss is None:
        return None
    rook_escape = next(
        (
            event
            for event in best[2:]
            if (
                event.actor == "initiator"
                and event.moving_piece_id == played_rook_loss.captured_piece_id
                and event.captured_piece_id is None
            )
        ),
        None,
    )
    payoff = next(
        (
            event
            for event in best[2:]
            if (
                event.actor == "initiator"
                and event.ply > (rook_escape.ply if rook_escape else 0)
                and event.captured_piece_id == played_rook_loss.moving_piece_id
            )
        ),
        None,
    )
    if rook_escape is None or payoff is None:
        return None
    between = tuple(event for event in best[1 : payoff.ply - 1])
    if rook_escape not in between:
        return None
    line_gain = _line_net_material_after_horizon_exchange_cp(
        evidence.best_trace,
        payoff_event=payoff,
    )
    if line_gain <= 0:
        return None
    step_kinds = {
        recapture.ply: "opponent_accepts_intermediate_exchange",
        rook_escape.ply: "same_threatened_rook_leaves_capture_line",
    }
    return (
        "intermediate_exchange_preserves_rook",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="starts_intermediate_exchange_before_rook_escape",
            **_captured_target(setup),
        ),
        tuple(
            _transformation_step(
                event,
                fact_kind=step_kinds.get(
                    event.ply,
                    "opponent_uses_intervening_move_before_payoff",
                ),
            )
            for event in between
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="captures_exact_rook_attacker_after_escape",
            **_captured_target(payoff),
        ),
        line_gain,
    )


def _forced_king_capture_then_queen_capture_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[
    Tuple[
        str,
        VerifiedCausalStep,
        Tuple[VerifiedCausalStep, ...],
        VerifiedCausalStep,
        int,
    ]
]:
    best = evidence.best_trace.events
    if len(best) < 5:
        return None
    setup, king_capture, queen_check, queen_move, payoff = best[:5]
    if (
        setup.actor != "initiator"
        or setup.moving_piece != "rook"
        or not setup.gave_check
        or setup.legal_reply_count != 1
        or king_capture.actor != "opponent"
        or king_capture.moving_piece != "king"
        or king_capture.captured_piece_id != setup.moving_piece_id
        or queen_check.actor != "initiator"
        or queen_check.moving_piece != "queen"
        or not queen_check.gave_check
        or queen_move.actor != "opponent"
        or queen_move.moving_piece != "queen"
        or payoff.actor != "initiator"
        or payoff.moving_piece_id != queen_check.moving_piece_id
        or payoff.captured_piece_id != queen_move.moving_piece_id
    ):
        return None
    if any(
        event.actor == "initiator"
        and event.captured_piece_id == payoff.captured_piece_id
        for event in evidence.played_trace.events
    ):
        return None
    line_gain = _line_net_material_after_horizon_exchange_cp(
        evidence.best_trace,
        payoff_event=payoff,
    )
    if line_gain <= 0:
        return None
    return (
        "forced_king_capture_then_queen_capture",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="offers_rook_with_only_one_legal_reply",
            **_moved_piece_target(setup),
        ),
        (
            _transformation_step(
                king_capture,
                fact_kind="king_is_forced_to_capture_offered_rook",
            ),
            _transformation_step(
                queen_check,
                fact_kind="queen_check_uses_displaced_king",
            ),
            _transformation_step(
                queen_move,
                fact_kind="opponent_queen_interposes_on_capture_square",
            ),
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="same_queen_captures_interposing_queen",
            **_captured_target(payoff),
        ),
        line_gain,
    )


def _sacrifice_opens_rook_capture_route_chain(
    evidence: VerifiedBranchEvidence,
) -> Optional[
    Tuple[
        str,
        VerifiedCausalStep,
        Tuple[VerifiedCausalStep, ...],
        VerifiedCausalStep,
        int,
    ]
]:
    best = evidence.best_trace.events
    if len(best) < 5:
        return None
    setup, recapture, rook_capture = best[:3]
    if (
        setup.actor != "initiator"
        or setup.moving_piece in {"pawn", "rook", "queen", "king"}
        or setup.captured_piece != "pawn"
        or recapture.actor != "opponent"
        or recapture.moving_piece != "pawn"
        or recapture.captured_piece_id != setup.moving_piece_id
        or rook_capture.actor != "initiator"
        or rook_capture.moving_piece != "rook"
        or rook_capture.captured_piece_id != recapture.moving_piece_id
        or not rook_capture.gave_check
    ):
        return None
    opened_route = any(
        change.kind == "opened"
        and change.actor == "initiator"
        and change.piece == "rook"
        and change.slider_square == rook_capture.origin
        and rook_capture.destination in change.changed_squares
        for change in recapture.line_geometry_changes
    )
    if not opened_route:
        return None
    payoff = next(
        (
            event
            for event in best[3:]
            if (
                event.actor == "initiator"
                and event.moving_piece_id == rook_capture.moving_piece_id
                and event.captured_piece
                in {"knight", "bishop", "rook", "queen"}
            )
        ),
        None,
    )
    if payoff is None or any(
        event.actor == "initiator"
        and event.captured_piece_id == payoff.captured_piece_id
        for event in evidence.played_trace.events
    ):
        return None
    between = tuple(event for event in best[1 : payoff.ply - 1])
    if recapture not in between or rook_capture not in between:
        return None
    line_gain = _line_net_material_after_horizon_exchange_cp(
        evidence.best_trace,
        payoff_event=payoff,
    )
    if line_gain <= 0:
        return None
    step_kinds = {
        recapture.ply: "pawn_recapture_opens_exact_rook_route",
        rook_capture.ply: "same_rook_enters_opened_route_with_check",
    }
    return (
        "sacrifice_opens_rook_capture_route",
        _causal_step(
            setup,
            role="setup",
            branch="best",
            fact_kind="sacrifices_minor_piece_for_pawn_recapture",
            **_captured_target(setup),
        ),
        tuple(
            _transformation_step(
                event,
                fact_kind=step_kinds.get(
                    event.ply,
                    "opponent_blocks_first_rook_check",
                ),
            )
            for event in between
        ),
        _causal_step(
            payoff,
            role="payoff",
            branch="best",
            fact_kind="same_rook_captures_piece_after_route_opens",
            **_captured_target(payoff),
        ),
        line_gain,
    )


def build_board_transformation_opportunity_proof(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: Any,
) -> Optional[VerifiedBoardTransformationOpportunity]:
    """Prove a multi-step board change and its legal material payoff."""
    common = {
        "fen_before": fen_before,
        "played_san": played_san,
        "best_move_san": best_move_san,
        "pv_after_played": pv_after_played,
        "pv_after_best": pv_after_best,
        "cp_loss": cp_loss,
    }
    if (
        build_target_line_opportunity_proof(**common) is not None
        or build_forcing_tempo_opportunity_proof(**common) is not None
        or build_endgame_geometry_opportunity_proof(**common) is not None
    ):
        return None
    evidence = build_verified_branch_evidence(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        pv_after_played=pv_after_played,
        pv_after_best=pv_after_best,
    )
    if (
        evidence is None
        or evidence.difference.net_material_edge_cp <= 0
    ):
        return None
    chain = (
        _intermediate_exchange_preserves_rook_chain(evidence)
        or _forced_king_capture_then_queen_capture_chain(evidence)
        or _sacrifice_opens_rook_capture_route_chain(evidence)
    )
    if chain is None:
        return None
    mechanism, setup, transformation_steps, payoff, line_gain = chain
    return VerifiedBoardTransformationOpportunity(
        mechanism=mechanism,
        setup=setup,
        transformation_steps=transformation_steps,
        payoff=payoff,
        line_net_material_gain_cp=line_gain,
        branch_evidence=evidence,
    )


def build_verified_line_cause(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: str,
    pv_after_played: Tuple[Any, ...] | List[Any],
    pv_after_best: Tuple[Any, ...] | List[Any],
    cp_loss: int,
    include_branch_evidence: bool = False,
) -> Optional[VerifiedLineCause]:
    """Build a narrow caption cause from two complete legal stored lines.

    No engine is run and no motif is inferred. The returned lesson is limited
    to terminal mate, a full capture/recapture ledger, or a material payoff
    that occurs inside the already-stored best continuation.
    """
    try:
        loss = int(cp_loss)
    except (TypeError, ValueError):
        return None
    if loss < VERIFIED_LINE_MIN_CP_LOSS:
        return None
    try:
        before = chess.Board(fen_before)
        played = before.parse_san(played_san)
        best = before.parse_san(best_move_san)
    except (ValueError, AssertionError):
        return None
    if played == best:
        return None

    # Local import avoids a module cycle: stored_line_verifier consumes the
    # canonical piece-value table owned by this module.
    from services.stored_line_verifier import replay_stored_line

    played_replay = replay_stored_line(before, played, pv_after_played)
    best_replay = replay_stored_line(before, best, pv_after_best)
    if (
        not played_replay.complete
        or not best_replay.complete
        or not played_replay.replayed_san
        or not best_replay.replayed_san
    ):
        return None

    initiator = before.turn
    played_captures = tuple(
        _verified_line_capture(item) for item in played_replay.captures
    )
    best_captures = tuple(
        _verified_line_capture(item) for item in best_replay.captures
    )
    opponent_reply = (
        played_replay.replayed_uci[1]
        if len(played_replay.replayed_uci) > 1
        else None
    )
    reply_san = (
        played_replay.replayed_san[1]
        if len(played_replay.replayed_san) > 1
        else None
    )
    reply_from = opponent_reply[:2] if opponent_reply else None
    reply_to = opponent_reply[2:4] if opponent_reply else None

    lesson_kind: Optional[str] = None
    mate_in: Optional[int] = None
    if (
        best_replay.checkmate
        and best_replay.checkmating_color == initiator
        and best_replay.mate_ply is not None
    ):
        lesson_kind = "missed_forced_mate"
        mate_in = (best_replay.mate_ply + 1) // 2
    elif (
        played_replay.checkmate
        and played_replay.checkmating_color == (not initiator)
        and played_replay.mate_ply is not None
    ):
        lesson_kind = "allowed_forced_mate"
        # The opponent moves on even plies in the player-initiated line.
        mate_in = max(1, played_replay.mate_ply // 2)
    else:
        capture_actors = {item.actor for item in played_captures}
        if (
            len(played_captures) >= 2
            and capture_actors == {"initiator", "opponent"}
            and played_replay.net_material_gain_cp <= -100
        ):
            lesson_kind = "exchange_sequence"
        elif (
            best_captures
            and best_replay.net_material_gain_cp >= 100
            and (
                best_replay.net_material_gain_cp
                - played_replay.net_material_gain_cp
            ) >= 100
        ):
            lesson_kind = "missed_material_opportunity"
    if lesson_kind is None:
        return None

    relationships: List[CauseRelationship] = []
    if reply_from and reply_to and lesson_kind in {
        "allowed_forced_mate",
        "exchange_sequence",
    }:
        relationships.append(CauseRelationship(reply_from, reply_to, "threat"))
    relationships.append(CauseRelationship(
        chess.square_name(best.from_square),
        chess.square_name(best.to_square),
        "safe_move",
    ))
    first_best_capture = best_captures[0] if best_captures else None
    if (
        lesson_kind == "missed_material_opportunity"
        and
        first_best_capture is not None
        and (
            first_best_capture.origin,
            first_best_capture.destination,
        ) != (
            chess.square_name(best.from_square),
            chess.square_name(best.to_square),
        )
    ):
        relationships.append(CauseRelationship(
            first_best_capture.origin,
            first_best_capture.destination,
            "opportunity",
        ))

    branch_evidence = None
    if include_branch_evidence:
        branch_evidence = build_verified_branch_evidence(
            fen_before=fen_before,
            played_san=played_san,
            best_move_san=best_move_san,
            pv_after_played=pv_after_played,
            pv_after_best=pv_after_best,
        )
        if branch_evidence is None:
            return None

    return VerifiedLineCause(
        lesson_kind=lesson_kind,
        phase=_detect_phase(before, before.fullmove_number),
        position_kind=(
            "pawn_ending"
            if not any(
                before.pieces(piece_type, color)
                for piece_type in (
                    chess.KNIGHT,
                    chess.BISHOP,
                    chess.ROOK,
                    chess.QUEEN,
                )
                for color in (chess.WHITE, chess.BLACK)
            )
            else "general"
        ),
        played_move_san=played_san,
        best_move_san=best_move_san,
        best_move_from=chess.square_name(best.from_square),
        best_move_to=chess.square_name(best.to_square),
        played_line_san=played_replay.replayed_san,
        best_line_san=best_replay.replayed_san,
        played_captures=played_captures,
        best_captures=best_captures,
        played_net_material_gain_cp=played_replay.net_material_gain_cp,
        best_net_material_gain_cp=best_replay.net_material_gain_cp,
        played_purposes=verified_move_purposes(
            fen_before=fen_before, played_san=played_san
        ),
        mate_in=mate_in,
        reply_san=reply_san,
        reply_from=reply_from,
        reply_to=reply_to,
        relationships=tuple(relationships),
        branch_evidence=branch_evidence,
        proof_version=(
            VERIFIED_LINE_CAUSAL_EVIDENCE_VERSION
            if branch_evidence is not None
            else VERIFIED_LINE_CAUSE_VERSION
        ),
    )


def _see_for_played_move(board_before: chess.Board, played_move: chess.Move) -> Optional[int]:
    """Return SEE for a capture move (the played side's perspective),
    or None if the move is not a capture."""
    if not board_before.is_capture(played_move):
        return None
    # Force the move that was actually played. The legacy SEE picked the
    # cheapest attacker instead, which could grade a different capture.
    initiator = board_before.turn
    return legal_exchange_gain(
        board_before,
        played_move.to_square,
        initiator,
        first_move=played_move,
    )


def _target_square_exchange_cp(board_after: chess.Board, target_sq: int) -> Optional[int]:
    """For NON-CAPTURE moves: after the played move, would the opponent
    capturing on `target_sq` win material? Returns SEE from the
    opponent's POV (positive = they win material by capturing).
    Returns None when there's nothing on target_sq.

    Named target_square_exchange_cp (was see_target_square_cp) to prevent
    semantic overload — there are now multiple SEE-flavoured fields and
    each one needs to say WHICH exchange it represents.
    """
    piece_on_target = board_after.piece_at(target_sq)
    if not piece_on_target:
        return None
    initiator = board_after.turn  # opponent is to move in board_after
    return legal_exchange_gain(board_after, target_sq, initiator)


def _exchange_participants(
    board: chess.Board,
    target_sq: int,
    initiating_side: chess.Color,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Return (effective_attackers, effective_defenders) — the pieces
    that would actually participate in the SEE sequence in cheapest-
    first order, with pinned-against-king pieces filtered out.

    Distinct from raw `attackers_on_target` / `defenders_on_target`
    which list ALL pieces with line-of-sight regardless of legality.
    """
    eff_attackers: List[Tuple[str, str]] = []
    eff_defenders: List[Tuple[str, str]] = []

    # Walk the exchange sequence. We don't actually need the SEE result
    # here — just the order of participants.
    consumed: set = set()
    side = initiating_side

    while True:
        attackers = board.attackers(side, target_sq) & ~_square_set(consumed)
        cheapest_sq = None
        cheapest_val = 10 ** 9
        for sq in attackers:
            piece = board.piece_at(sq)
            if not piece:
                continue
            if piece.piece_type == chess.KING:
                continue  # Kings don't participate in SEE per convention
            if _is_pinned_against_target(board, sq, target_sq):
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val:
                cheapest_val = val
                cheapest_sq = sq
        if cheapest_sq is None:
            break

        piece = board.piece_at(cheapest_sq)
        entry = (chess.square_name(cheapest_sq), PIECE_TYPE_NAMES.get(piece.piece_type, "piece"))
        if side == initiating_side:
            eff_attackers.append(entry)
        else:
            eff_defenders.append(entry)
        consumed.add(cheapest_sq)
        side = not side

    return eff_attackers, eff_defenders


# ────────────────────────────────────────────────────────────────────
# Threats and undefended pieces
# ────────────────────────────────────────────────────────────────────

def _threats_created(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """Return structured evidence of every threat the played move creates.

    A threat is: own piece NOW attacks an enemy piece such that SEE on
    capturing that enemy piece is favorable for us. Evidence (NOT labels)
    per LAW 3 — renderer can render but never re-derive.

    Each threat:
      {
        "attacker_square":          str,   # piece that's now threatening
        "target_square":            str,   # enemy piece being threatened
        "target_piece_type":        str,
        "target_value_cp":          int,
        "see_cp":                   int,   # net material if we capture
        "is_immediate":             bool,  # we'd play it next without prep
        "via_moving_piece":         bool,  # the moving piece is the attacker
        "via_discovered":           bool,  # a different own piece's line opened up
      }
    """
    threats: List[Dict[str, Any]] = []
    own_color = not board_after.turn  # we just moved; board_after.turn is opp
    opp_color = board_after.turn

    # Pre-compute which enemy pieces are attacked by which of OUR pieces
    # in board_before vs board_after. The diff = new threats.
    enemy_squares = [sq for pt in range(chess.PAWN, chess.KING + 1)
                       for sq in board_after.pieces(pt, opp_color)]

    for enemy_sq in enemy_squares:
        enemy_piece = board_after.piece_at(enemy_sq)
        if not enemy_piece or enemy_piece.piece_type == chess.KING:
            continue  # checks are handled by is_check, not threats

        attackers_after = board_after.attackers(own_color, enemy_sq)
        attackers_before = board_before.attackers(own_color, enemy_sq)
        # A NEW attacker is one that's in 'after' but not in 'before'.
        # Or: the from-square was an attacker and it moved away (capture case — handled elsewhere).
        new_attackers = attackers_after - attackers_before
        if not new_attackers:
            continue

        # Pick the cheapest new attacker as the "primary threat-maker"
        cheapest_attacker_sq = None
        cheapest_val = 10 ** 9
        for atk_sq in new_attackers:
            piece = board_after.piece_at(atk_sq)
            if not piece:
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val:
                cheapest_val = val
                cheapest_attacker_sq = atk_sq
        if cheapest_attacker_sq is None:
            continue

        # SEE: if we initiate a capture on enemy_sq, do we win material?
        see_cp = static_exchange_eval(board_after, enemy_sq, own_color)
        if see_cp <= 0:
            continue  # not a winning threat — opponent defends adequately

        # Mutual-line / attacker-survival gate. The above SEE assumes WE
        # initiate, but it's actually opp's move next. If opp can take
        # our threatening attacker at SEE ≥ 0, the threat doesn't
        # materialise — they capture before we get to. From d7ce40cf
        # corpus: #14 Kf1 was emitting "threatens Rxe8 winning the rook"
        # while ...Rxe1+ was the immediate reply on the same cleared line.
        opp_attackers_on_attacker = board_after.attackers(opp_color, cheapest_attacker_sq)
        if opp_attackers_on_attacker:
            opp_see_on_attacker = static_exchange_eval(
                board_after, cheapest_attacker_sq, opp_color
            )
            if opp_see_on_attacker >= 0:
                continue

        attacker_piece = board_after.piece_at(cheapest_attacker_sq)
        target_value_cp = PIECE_VALUE_CP.get(enemy_piece.piece_type, 0)
        # If see_cp < target_value, the winning sequence cost us some
        # material along the way → it required at least one recapture
        # exchange. Renderer uses this to phrase confidently for free
        # captures vs. cautiously for trade-required ones.
        winning_line_requires_recapture = see_cp < target_value_cp

        threats.append({
            "attacker_square": chess.square_name(cheapest_attacker_sq),
            "attacker_piece_type": (
                PIECE_TYPE_NAMES.get(attacker_piece.piece_type, "piece")
                if attacker_piece else "piece"
            ),
            "target_square": chess.square_name(enemy_sq),
            "target_piece_type": PIECE_TYPE_NAMES.get(enemy_piece.piece_type, "piece"),
            "target_value_cp": target_value_cp,
            "see_cp": see_cp,
            "is_immediate": True,  # for now all detected threats are immediate;
                                   # multi-ply threat chains arrive in commit #4.
            "via_moving_piece": cheapest_attacker_sq == played_move.to_square,
            "via_discovered": cheapest_attacker_sq != played_move.to_square,
            "winning_line_requires_recapture": winning_line_requires_recapture,
        })

    # Sort by target value descending — highest-value threat first.
    threats.sort(key=lambda t: -t["target_value_cp"])
    return threats


def _pieces_now_undefended(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """Return own pieces that LOST a defender as a result of the played move.

    Evidence (NOT a label per LAW 3):
      [
        {
          "square":                 str,    # the undefended piece
          "piece_type":             str,
          "piece_color":            "white|black",
          "lost_defender_square":   str | None,  # if a specific defender disappeared
          "lost_defender_piece":    str | None,
          "now_attacked":           bool,   # is this piece under attack from opp?
          "see_if_captured_cp":     int,    # SEE from opp's POV
        },
        ...
      ]

    Computed by diffing defender counts before vs after for each own
    piece. Renderer decides how to phrase it (or whether to mention).
    """
    out: List[Dict[str, Any]] = []
    own_color = not board_after.turn
    opp_color = board_after.turn
    from_sq = played_move.from_square

    # Own pieces that existed BEFORE the move and still exist after.
    # (The moved piece itself is on a different square afterwards — skip.)
    own_squares_before = [
        sq for pt in range(chess.PAWN, chess.KING + 1)
        for sq in board_before.pieces(pt, own_color)
        if sq != from_sq
    ]

    for sq in own_squares_before:
        piece = board_after.piece_at(sq)
        if not piece or piece.color != own_color:
            # Piece was captured during the move (e.g., en passant edge case)
            continue

        defenders_before = board_before.attackers(own_color, sq)
        defenders_after = board_after.attackers(own_color, sq)
        lost = defenders_before - defenders_after

        # Did this piece lose a defender? The from_square will normally
        # appear in `lost` if the moved piece was defending sq.
        if not lost:
            continue

        # Was the lost defender the moved piece?
        lost_defender_sq = None
        lost_defender_piece = None
        if from_sq in lost:
            moved_piece = board_before.piece_at(from_sq)
            if moved_piece:
                lost_defender_sq = chess.square_name(from_sq)
                lost_defender_piece = PIECE_TYPE_NAMES.get(moved_piece.piece_type, "piece")
        else:
            # A different defender disappeared (e.g. through-line broken).
            # Pick the most valuable lost defender.
            best_lost = None
            best_val = -1
            for ldsq in lost:
                piece_lost = board_before.piece_at(ldsq)
                if piece_lost and PIECE_VALUE_CP.get(piece_lost.piece_type, 0) > best_val:
                    best_val = PIECE_VALUE_CP[piece_lost.piece_type]
                    best_lost = (ldsq, piece_lost)
            if best_lost:
                lost_defender_sq = chess.square_name(best_lost[0])
                lost_defender_piece = PIECE_TYPE_NAMES.get(best_lost[1].piece_type, "piece")

        attackers_after = board_after.attackers(opp_color, sq)
        now_attacked = bool(attackers_after)
        # Defenders of `sq` are own-color pieces that ATTACK that square
        # (in chess parlance, defending = attacking your own piece's square).
        # The piece on sq doesn't defend itself.
        remaining_defenders = board_after.attackers(own_color, sq)
        remaining_defender_count = len(remaining_defenders)
        see_if_captured = 0
        if now_attacked:
            see_if_captured = legal_exchange_gain(board_after, sq, opp_color)
        # "Hanging" is a strong renderer signal — distinct from "lost a
        # defender but still adequately defended." Defined as:
        # under attack AND the exchange loses material AND no other
        # defender remains. Renderer can branch on this without re-
        # checking geometry.
        is_now_hanging = (
            now_attacked
            and see_if_captured > 0
            and remaining_defender_count == 0
        )

        out.append({
            "square": chess.square_name(sq),
            "piece_type": PIECE_TYPE_NAMES.get(piece.piece_type, "piece"),
            "piece_value_cp": PIECE_VALUE_CP.get(piece.piece_type, 0),
            "piece_color": "white" if piece.color == chess.WHITE else "black",
            "lost_defender_square": lost_defender_sq,
            "lost_defender_piece": lost_defender_piece,
            "now_attacked": now_attacked,
            "see_if_captured_cp": see_if_captured,
            "remaining_defender_count": remaining_defender_count,
            "is_now_hanging": is_now_hanging,
        })

    # Sort: pieces that are now under losing exchange first (highest material at risk).
    out.sort(key=lambda x: -x["see_if_captured_cp"] if x["now_attacked"] else 0)
    return out


# ────────────────────────────────────────────────────────────────────
# Tactic-shape detectors
#
# Each detector emits STRUCTURED EVIDENCE — coordinates, piece types,
# values — never a label like "fork" or "pin". The renderer decides
# whether to call something a fork / double attack / pressure / battery
# based on the evidence + context.
#
# Per LAW 3 in the module docstring. Per user instruction (2026-05-11):
# "Same for pins. DO NOT emit `is_pinned: true`. Emit the geometric
# evidence of the line."
# ────────────────────────────────────────────────────────────────────

# ── Promotion policy, NOT geometry ───────────────────────────────────────────
#
# Minimum value of a WINNABLE target before ChessGuru will NAME a shape as a
# fork and use it as training material. The enemy king never counts toward it.
#
# This is deliberately NOT a gate inside the detector. A knight that checks the
# king while attacking a pawn IS a fork — saying otherwise would make the
# canonical evidence assert something chessically false, and would let the
# caption layer and the lesson layer drift into different definitions of the
# word. So: the evidence records the complete geometry, and this one shared
# predicate decides what gets promoted into named teaching.
#
# Locked against the distribution, not picked by feel (2026-08-13, 6k-move
# corpus): of 82 royal forks, 47 (57%) had a pawn as their only winnable target
# and 35 (43%) had a minor piece or better. 300 keeps the 35 meaningful ones
# across queens, knights, rooks and bishops; 500 would wrongly discard valid
# check-plus-minor forks such as Qb5+ (king + knight). Pawn-only royal forks are
# not silenced — they fall through to the existing "check, and it attacks a
# pawn" explanation. Confirmed by Mohit 2026-08-13.
FORK_MIN_NAMED_TARGET_CP = 300


def is_named_fork(shape: Dict[str, Any]) -> bool:
    """Should ChessGuru NAME this multi-target shape as a fork and teach from it?

    THE one promotion predicate. Captions, Gold-content selection and the
    Stage 8 grader all call this, so "what counts as a teachable fork" cannot
    diverge between the caption system and the lesson system.

    Chess truth (is it a fork?) lives in the evidence. Product policy (do we
    name it?) lives here. Piece-agnostic — a bishop, rook or queen fork is
    judged exactly like a knight's.

    THE RULE: at least one target we can actually WIN must be worth a minor
    piece or more. The enemy king never counts toward that — it is a forced
    target, not winnable material — so a royal fork is named on the strength of
    its other target alone.

    Applied uniformly to royal and normal shapes. The asymmetric version (floor
    on royal only) was tried first and rejected: it forced Gold-content
    selection to use a STRICTER predicate than the caption layer, which is the
    exact drift this function exists to prevent — Gold-eligible candidates
    inflated from 97 to 193 by admitting pawn+pawn forks nobody would teach.

    Measured cost of uniformity, 6,000-move corpus: **32 moves (0.5%)** lose a
    fork caption and fall back to another rule rather than to silence. (An
    earlier note said "20 / 0.3%" — that was counting pawn-only normal *shapes*,
    not moves; one move can carry several shapes. 32 moves is the user-visible
    figure and the one the evidence doc uses.) The existing principle path
    `_p_tac_fork_pattern` already applied this same >=300 bar, so this aligns
    `extract_primary_reason` with a rule the codebase already held.
    """
    winnable = [
        t for t in (shape.get("attacked_targets") or []) if not t.get("is_forced")
    ]
    return any(
        (t.get("value_cp") or 0) >= FORK_MIN_NAMED_TARGET_CP for t in winnable
    )


def named_fork_shapes(evidence: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """The subset of multi_target_attack_evidence eligible to be named/taught."""
    return [s for s in (evidence or []) if is_named_fork(s)]


def _forced_king_target(
    threats: List[Dict[str, Any]],
    board_after: chess.Board,
    played_move: Optional[chess.Move] = None,
) -> Optional[Dict[str, Any]]:
    """The royal-fork gap: one attacker giving CHECK while also attacking a
    winnable piece is a fork, but `_threats_created` can never see it.

    `_threats_created` skips the king outright ("checks are handled by is_check,
    not threats") because a king is not winnable material and every SEE on it is
    meaningless. Correct for material accounting — but it means a check-plus-piece
    fork reaches the grouper with only ONE target and is discarded.

    Measured 2026-08-13: this rejected the historically-correct fork move on 16 of
    63 gold knight-fork positions, every one a check-plus-piece shape
    (`Nxc2+` -> targets seen `['rook','pawn']`). Royal forks are the most
    instructive forks there are, and the canonical detector could not express one.

    This is PIECE-AGNOSTIC by construction: it keys off "the checking piece" and
    "the attacker already has a winnable target", never off knights. A bishop
    checking while hitting a rook, or a pawn checking while hitting a knight, is
    the same shape and is treated identically.

    Returns a synthetic target entry to append to that attacker's group, or None.
    Three gates, all required — a checking move is NOT automatically a fork:

      1. SEE on the other target — inherited. Every entry in `threats` already
         passed `see_cp > 0` in _threats_created, so the second target is
         genuinely winnable, not merely attacked.
      2. Moving piece — the CHECK must come from the piece that just moved.
         A pre-existing check, or a discovered check from another piece, is a
         different shape and is not folded in here.
      3. Material safety — the checking piece must not simply hang. If the
         opponent profits by capturing it (SEE > 0 on the forker's own square),
         the "fork" resolves by taking the forker and there is nothing to win.

    Gate 3 is where `pattern_confidence/fork.py:120` was too lenient: it treated
    `gives_check` as making the forker safe outright, which accepts a knight that
    checks and is captured by the king for free.

    Known approximation: SEE ignores check legality, so a recapture by a pinned
    defender is still counted. Same approximation used throughout this module.
    """
    if not board_after.is_check():
        return None

    king_sq = board_after.king(board_after.turn)
    if king_sq is None:
        return None

    checkers = board_after.checkers()
    if len(checkers) != 1:
        return None  # double check is a different (stronger) shape — not folded in

    checker_sq = next(iter(checkers))

    # Gate 2 — the check must come from the piece that just moved.
    if played_move is not None and checker_sq != played_move.to_square:
        return None

    # Gate 1 — that same attacker must already hold a winnable target.
    # NO value floor here on purpose: check + pawn is still geometrically a fork,
    # and the evidence layer must say so. Whether we NAME it is decided later by
    # is_named_fork(). Keeping the floor here would make the canonical evidence
    # claim a real fork does not exist.
    checker_name = chess.square_name(checker_sq)
    if not any(t.get("attacker_square") == checker_name for t in threats):
        return None

    # Gate 3 — the checking piece must survive.
    opp_color = board_after.turn
    if static_exchange_eval(board_after, checker_sq, opp_color) > 0:
        return None

    return {
        "attacker_square": checker_name,
        "attacker_piece_type": chess.piece_name(
            board_after.piece_at(checker_sq).piece_type
        ),
        "target_square": chess.square_name(king_sq),
        "target_piece_type": "king",
        # A king is never won. Value 0 keeps it out of every material
        # calculation while still counting as a target that must be answered.
        "target_value_cp": 0,
        "see_cp": 0,
        "is_forced": True,
        "is_immediate": True,
        "via_moving_piece": played_move is None or checker_sq == played_move.to_square,
        "via_discovered": False,
    }


def _multi_target_attack_evidence(
    threats: List[Dict[str, Any]],
    board_after: Optional[chess.Board] = None,
    played_move: Optional[chess.Move] = None,
) -> List[Dict[str, Any]]:
    """Group `threats_created` entries by attacker_square. Any attacker
    with ≥2 separately-winning threats forms a multi-target-attack shape.

    NAMED `multi_target_attack` rather than `fork`: the geometric primitive
    is "one piece, multiple targets." The renderer decides whether to
    call it "fork" / "double attack" / "pressure on two pieces" based on
    context (piece type, target values, position).

    King-defender filter (2026-05-17 Parth fb_e5fff03bdde6 "no fork"):
    static_exchange_eval explicitly skips the king as an attacker
    (caption_facts.py:272-273) — a known SEE limitation. Targets
    defended ONLY by the enemy king register as see_cp > 0 even when
    capturing them would clearly lose the attacker (queen takes pawn,
    king takes queen). Drop targets where attacker_value > target_value
    AND the enemy king is among the target's defenders in board_after.
    """
    by_attacker: Dict[str, List[Dict[str, Any]]] = {}
    for t in threats:
        by_attacker.setdefault(t["attacker_square"], []).append(t)

    # Royal forks: fold in the enemy king as a forced target when the checking
    # piece is also holding a winnable target. Appended AFTER grouping by
    # attacker so it can only ever join an attacker that already has a real
    # threat — it can never create a group on its own. See _forced_king_target.
    if board_after is not None:
        _king_t = _forced_king_target(threats, board_after, played_move)
        if _king_t is not None:
            by_attacker.setdefault(_king_t["attacker_square"], []).append(_king_t)

    out: List[Dict[str, Any]] = []
    for attacker_sq, ts in by_attacker.items():
        if board_after is not None:
            # The king entry is exempt from the king-defended-overvalue filter:
            # that filter drops targets whose only defender is the enemy king,
            # which is meaningless for the king itself.
            _forced = [t for t in ts if t.get("is_forced")]
            ts = _filter_king_defended_overvalue_targets(
                [t for t in ts if not t.get("is_forced")], board_after
            ) + _forced
        if len(ts) < 2:
            continue
        # Sort targets by value descending so renderer sees the most valuable first
        targets_sorted = sorted(ts, key=lambda t: -t["target_value_cp"])
        out.append({
            "attacker_square": attacker_sq,
            "attacker_piece_type": ts[0]["attacker_piece_type"],
            "attacked_targets": [
                {
                    "square": t["target_square"],
                    "piece_type": t["target_piece_type"],
                    "value_cp": t["target_value_cp"],
                    "see_cp": t["see_cp"],
                    # True only for the enemy king in a royal fork: a target that
                    # must be answered but can never be won. Consumers doing
                    # material maths must skip it; consumers counting "how many
                    # things are attacked" must not.
                    "is_forced": bool(t.get("is_forced")),
                }
                for t in targets_sorted
            ],
            # Lets a consumer branch on royal-vs-normal without re-scanning targets.
            "includes_forced_king": any(t.get("is_forced") for t in ts),
            "via_moving_piece": all(t.get("via_moving_piece", False) for t in ts),
        })
    # Sort fork shapes by the highest-value target descending
    out.sort(key=lambda f: -f["attacked_targets"][0]["value_cp"])
    return out


def _filter_king_defended_overvalue_targets(
    ts: List[Dict[str, Any]],
    board_after: chess.Board,
) -> List[Dict[str, Any]]:
    """Drop threat entries where capturing the target loses the attacker.

    Specifically: target defended by enemy king AND attacker value >
    target value. SEE misses this because it skips kings as attackers.
    """
    kept: List[Dict[str, Any]] = []
    for t in ts:
        attacker_sq_name = t.get("attacker_square")
        target_sq_name = t.get("target_square")
        attacker_piece_type_name = t.get("attacker_piece_type", "")
        # Map piece-type name back to chess.PieceType for value lookup.
        type_lookup = {
            "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
            "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING,
        }
        attacker_pt = type_lookup.get(attacker_piece_type_name)
        attacker_value = PIECE_VALUE_CP.get(attacker_pt, 0) if attacker_pt else 0
        target_value = t.get("target_value_cp", 0) or 0
        try:
            target_sq = chess.parse_square(target_sq_name)
            attacker_sq = chess.parse_square(attacker_sq_name)
        except (TypeError, ValueError):
            kept.append(t)
            continue
        attacker_piece = board_after.piece_at(attacker_sq)
        if attacker_piece is None:
            kept.append(t)
            continue
        enemy_color = not attacker_piece.color
        defenders = board_after.attackers(enemy_color, target_sq)
        if not defenders:
            kept.append(t)
            continue
        # Is the king among the defenders?
        king_defends = any(
            board_after.piece_at(sq) is not None
            and board_after.piece_at(sq).piece_type == chess.KING
            for sq in defenders
        )
        if king_defends and attacker_value > target_value:
            # Capturing loses the attacker — not a real fork target.
            continue
        kept.append(t)
    return kept


# Pin/skewer shapes share a common geometry: a sliding own piece lines
# up two enemy pieces. The difference is value ordering of front/rear.
# The renderer decides terminology; the extractor only emits evidence.

_SLIDING_PIECE_TYPES = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _ray_squares(from_sq: int, direction: Tuple[int, int]) -> List[int]:
    """Walk a (dx, dy) direction from from_sq, yielding each on-board
    square in order until off-board."""
    df, dr = direction
    file_, rank_ = chess.square_file(from_sq), chess.square_rank(from_sq)
    out: List[int] = []
    while True:
        file_ += df
        rank_ += dr
        if not (0 <= file_ < 8 and 0 <= rank_ < 8):
            break
        out.append(chess.square(file_, rank_))
    return out


def _piece_can_move_along_line(
    board: chess.Board,
    piece_square: int,
    line_squares: List[int],
) -> bool:
    """Returns True if the piece on `piece_square` can move to ANY square
    in `line_squares` legally. Used to determine whether a pinned piece
    can still slide along the pin line (e.g. a rook pinned on a file can
    still move on the file)."""
    piece = board.piece_at(piece_square)
    if not piece:
        return False
    # We don't need legal_moves (turn-dependent). We check pin geometry:
    # piece can move along the line iff the line direction is the SAME
    # as the pin direction. python-chess `board.pin(color, sq)` returns
    # the SquareSet of legal destinations (along the pin line).
    pin_mask = board.pin(piece.color, piece_square)
    if isinstance(pin_mask, chess.SquareSet):
        return any(sq in pin_mask for sq in line_squares)
    return any(bool(chess.BB_SQUARES[sq] & pin_mask) for sq in line_squares)


def _aligned_pieces_evidence(
    board_after: chess.Board,
    own_color: chess.Color,
) -> List[Dict[str, Any]]:
    """Return ALL aligned-piece configurations seen in board_after — the
    geometric shape that the renderer can interpret as a pin / skewer /
    x-ray depending on value relations.

    For each own sliding piece (bishop, rook, queen), walk its rays.
    If a ray hits enemy piece A then enemy piece B (further along,
    same line), emit one evidence dict with a `front_value_vs_rear`
    flag — "lower" | "higher" | "equal" — that lets the renderer
    decide naming.

    NAMED `aligned_pieces` rather than `pin_shape`/`skewer_shape`:
    pin and skewer are RENDER-time names; the geometric primitive is
    "three pieces on a line." Merging them into one field with a value-
    comparison flag prevents the extractor from cementing renderer
    taxonomy (per user feedback 2026-05-11).
    """
    out: List[Dict[str, Any]] = []
    opp_color = not own_color

    # Directions per piece type
    DIAGONAL_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    ORTHO_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    sliding_pieces = []
    for piece_type in _SLIDING_PIECE_TYPES:
        for sq in board_after.pieces(piece_type, own_color):
            sliding_pieces.append((sq, piece_type))

    for slider_sq, slider_type in sliding_pieces:
        if slider_type == chess.BISHOP:
            dirs = DIAGONAL_DIRS
        elif slider_type == chess.ROOK:
            dirs = ORTHO_DIRS
        else:  # QUEEN
            dirs = DIAGONAL_DIRS + ORTHO_DIRS

        slider_piece = board_after.piece_at(slider_sq)

        for direction in dirs:
            ray = _ray_squares(slider_sq, direction)
            # Walk along the ray, collecting up to 2 enemy pieces.
            first_enemy = None
            second_enemy = None
            blocked_by_own = False
            for sq in ray:
                piece = board_after.piece_at(sq)
                if not piece:
                    continue
                if piece.color == own_color:
                    blocked_by_own = True
                    break
                if first_enemy is None:
                    first_enemy = (sq, piece)
                else:
                    second_enemy = (sq, piece)
                    break
            if blocked_by_own or first_enemy is None or second_enemy is None:
                continue

            front_sq, front_piece = first_enemy
            rear_sq, rear_piece = second_enemy
            # A king is the load-bearing rear piece in an absolute pin. The
            # general material table intentionally gives kings no exchange
            # value, but using that zero here reverses the alignment taxonomy:
            # a knight pinned to its king looks "higher" than the rear piece
            # and downstream motif code calls it a skewer. Alignment needs an
            # ordering value, not a capturable-material value, so kings sort
            # above every other piece on either side of the pair.
            front_val = (
                10_000
                if front_piece.piece_type == chess.KING
                else PIECE_VALUE_CP.get(front_piece.piece_type, 0)
            )
            rear_val = (
                10_000
                if rear_piece.piece_type == chess.KING
                else PIECE_VALUE_CP.get(rear_piece.piece_type, 0)
            )

            # Front-vs-rear value comparison (renderer decides taxonomy):
            #   "lower"  → front cheaper than rear  (classic pin shape)
            #   "higher" → front more valuable      (classic skewer shape)
            #   "equal"  → renderer's call          (e.g. R+R battery, N+B)
            if front_val < rear_val:
                front_value_vs_rear = "lower"
            elif front_val > rear_val:
                front_value_vs_rear = "higher"
            else:
                front_value_vs_rear = "equal"

            line_kind = (
                "diagonal" if direction in DIAGONAL_DIRS else
                ("file" if direction[0] == 0 else "rank")
            )

            # Can the front piece move along this line (sliding piece
            # of same direction)? If not, even a non-king rear creates
            # an effective pin.
            front_can_move_along = False
            front_pt = front_piece.piece_type
            if front_pt == chess.QUEEN:
                front_can_move_along = True
            elif front_pt == chess.ROOK and line_kind in ("file", "rank"):
                front_can_move_along = True
            elif front_pt == chess.BISHOP and line_kind == "diagonal":
                front_can_move_along = True

            out.append({
                "attacker_square": chess.square_name(slider_sq),
                "attacker_piece_type": PIECE_TYPE_NAMES.get(slider_type, "piece"),
                "front_piece_square": chess.square_name(front_sq),
                "front_piece_type": PIECE_TYPE_NAMES.get(front_piece.piece_type, "piece"),
                "front_piece_value_cp": front_val,
                "rear_piece_square": chess.square_name(rear_sq),
                "rear_piece_type": PIECE_TYPE_NAMES.get(rear_piece.piece_type, "piece"),
                "rear_piece_value_cp": rear_val,
                "line_kind": line_kind,
                "front_value_vs_rear": front_value_vs_rear,
                "front_can_move_along_line": front_can_move_along,
                "rear_is_king": rear_piece.piece_type == chess.KING,
                "front_is_king": front_piece.piece_type == chess.KING,
            })

    return out


def _discovered_attack_evidence(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """If the played move's from_square was on a line between an own
    sliding piece and an enemy piece, the move uncovered the slider's
    attack. Emit evidence per such uncovered line.

    Pure geometry — slider on one side, played-move from_square in the
    middle, enemy piece on the other side. After the move, the line is
    open and the slider attacks the enemy.

    NAMED `discovered_attack` rather than `discovery_shape`: cleaner
    primitive; the "shape" suffix added no information.
    """
    out: List[Dict[str, Any]] = []
    own_color = not board_after.turn  # we just moved
    opp_color = board_after.turn
    from_sq = played_move.from_square

    # For each own sliding piece, walk rays. If a ray passes through
    # from_sq (the played move's origin) and lands on an enemy piece,
    # AND the slider doesn't attack that enemy in board_before but DOES
    # in board_after, → discovered attack.
    for piece_type in _SLIDING_PIECE_TYPES:
        for slider_sq in board_after.pieces(piece_type, own_color):
            if slider_sq == played_move.to_square:
                continue  # the moving piece itself isn't doing "discovery"
            # Walk all rays from slider_sq
            slider_piece = board_after.piece_at(slider_sq)
            if piece_type == chess.BISHOP:
                dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            elif piece_type == chess.ROOK:
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            else:
                dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1),
                        (1, 0), (-1, 0), (0, 1), (0, -1)]
            for direction in dirs:
                ray = _ray_squares(slider_sq, direction)
                if from_sq not in ray:
                    continue
                from_idx = ray.index(from_sq)
                # Ray BETWEEN slider and from_sq must be clear in
                # board_after — otherwise the line was already blocked
                # by some OTHER piece, and the moving piece never had a
                # blocking role on this ray. Bug from feedback
                # fb_a6f596afbba0 / move Nc2: detector claimed bishop f8
                # uncovered onto a3, but f8→a3 is blocked at c5 by
                # black's own queen. Moving the knight off b4 doesn't
                # open that line. Without this check, ANY slider whose
                # ray crosses from_sq looks like a discoverer.
                blocked = False
                for sq in ray[:from_idx]:
                    if board_after.piece_at(sq) is not None:
                        blocked = True
                        break
                if blocked:
                    continue
                # Find the first piece on this ray AFTER from_sq.
                target_sq = None
                target_piece = None
                for sq in ray[from_idx + 1:]:
                    p = board_after.piece_at(sq)
                    if p:
                        target_sq = sq
                        target_piece = p
                        break
                if target_sq is None or target_piece is None:
                    continue
                if target_piece.color == own_color:
                    continue  # uncovered to an own piece — not a threat
                if target_piece.piece_type == chess.KING:
                    # Discovered CHECK — emit separately; renderer will pick
                    # check-with-bonus template (R06) but the discovery
                    # evidence is useful for explaining why.
                    pass
                # Verify it's actually a NEW attack — in board_before the
                # slider's attack on target_sq was blocked by the piece
                # on from_sq.
                if board_before.is_attacked_by(own_color, target_sq):
                    # The slider already attacked this square via another
                    # path; not a real discovery for this target.
                    # Heuristic: check if from_sq blocks the line in board_before
                    pre_attackers = board_before.attackers(own_color, target_sq)
                    if slider_sq in pre_attackers:
                        continue  # slider already attacked via clear line

                # Mutual-line gate. The line that opened works both ways
                # — opponent may now see our slider through the same gap.
                # Since it's opp's move next, if they can capture our
                # slider at SEE ≥ 0 the discovered attack is illusory:
                # the slider is taken before it can execute the discovery.
                # From d7ce40cf corpus: #14 Kf1 was emitting "uncovers
                # rook hitting e8" while black's Rxe1+ was right there.
                opp_attackers_on_slider = board_after.attackers(opp_color, slider_sq)
                if opp_attackers_on_slider:
                    opp_see_on_slider = static_exchange_eval(
                        board_after, slider_sq, opp_color
                    )
                    if opp_see_on_slider >= 0:
                        continue
                out.append({
                    "discovered_attacker_square": chess.square_name(slider_sq),
                    "discovered_attacker_piece_type": PIECE_TYPE_NAMES.get(piece_type, "piece"),
                    "moved_piece_from_square": chess.square_name(from_sq),
                    "target_square": chess.square_name(target_sq),
                    "target_piece_type": PIECE_TYPE_NAMES.get(target_piece.piece_type, "piece"),
                    "target_value_cp": PIECE_VALUE_CP.get(target_piece.piece_type, 0),
                    "is_check": target_piece.piece_type == chess.KING,
                    "line_direction": direction,
                })
    return out


# ────────────────────────────────────────────────────────────────────
# PV material walks + mate threat detection
#
# SEE tells us about IMMEDIATE exchange material. The PV walk tells us
# about MULTI-PLY tactical material — e.g. a 4-ply combination that
# wins a piece in the third move. SEE alone misses these; the PV walk
# resolves them.
#
# Mate threat detection: walks the PV for checkmate notation (#) or
# detects mate-distance via eval sentinel. Mate priority overrides
# material in primary_reason scoring.
# ────────────────────────────────────────────────────────────────────


def _side_material_cp(board: chess.Board, color: chess.Color) -> int:
    """Sum of piece values for `color` in board. Excludes king (no
    SEE value). Centipawns."""
    total = 0
    for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(pt, color)) * PIECE_VALUE_CP[pt]
    return total


def _normalize_pv_starting_with(
    leading_san: Optional[str], pv: List[str]
) -> List[str]:
    """Ensure the PV list starts with `leading_san`. Different engine
    record formats include or omit the leading move; this helper makes
    walks idempotent regardless.

    Returns a NEW list; doesn't mutate input.
    """
    if not leading_san:
        return list(pv)
    leading_clean = _normalize_san(leading_san)
    if pv and _normalize_san(pv[0]) == leading_clean:
        return list(pv)
    return [leading_san] + list(pv)


def _pv_material_delta(
    board_before: chess.Board,
    pv_san: List[str],
    initiator_color: chess.Color,
    max_plies: int = 8,
) -> int:
    """Walk the PV (SAN list) up to `max_plies` plies; return net
    material change for `initiator_color` in centipawns.

    Positive = initiator gained material.
    Returns 0 if the PV can't be replayed cleanly.
    """
    if not pv_san:
        return 0

    sim = board_before.copy()
    init_own = _side_material_cp(sim, initiator_color)
    init_opp = _side_material_cp(sim, not initiator_color)

    plies_pushed = 0
    for san in pv_san[:max_plies]:
        try:
            move = sim.parse_san(san)
            sim.push(move)
            plies_pushed += 1
        except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
            break

    if plies_pushed == 0:
        return 0

    final_own = _side_material_cp(sim, initiator_color)
    final_opp = _side_material_cp(sim, not initiator_color)

    own_delta = final_own - init_own         # ≤ 0 (can only lose pieces)
    opp_delta = final_opp - init_opp         # ≤ 0
    # Net gain for initiator = pieces they took (= -opp_delta) minus
    # pieces they lost (= -own_delta). Equivalent: own_delta - opp_delta.
    return own_delta - opp_delta


def _pv_resolves_to_mate(pv_san: List[str], max_plies: int = 8) -> Optional[int]:
    """If the PV ends in checkmate (SAN ending with '#'), return the
    1-indexed ply at which mate is delivered. Otherwise None.
    """
    for i, san in enumerate(pv_san[:max_plies]):
        if san.endswith("#"):
            return i + 1
    return None


def _mate_threat_evidence(
    board_before: chess.Board,
    played_san: str,
    best_move_san: Optional[str],
    eval_before_cp: Optional[int],
    eval_after_cp: Optional[int],
    pv_after_played: List[str],
    pv_after_best: List[str],
    own_color: chess.Color,
    is_checkmate: bool = False,
) -> Optional[Dict[str, Any]]:
    """Build branch-owned mate evidence from complete stored continuations.

    ``eval_before_cp`` belongs to the best branch; ``eval_after_cp`` belongs
    to the played branch.  Older code merged a mate suffix from either PV with
    the played-branch evaluation.  That made a missed winning mate read as
    "you allowed mate."  This contract keeps each result attached to its
    branch and emits one explicit transition from the mover's perspective.

    No engine is run here.  Legal lines are replayed by the canonical stored
    line verifier; a mate sentinel may establish the winner when the stored PV
    is truncated, but it never supplies a made-up distance.
    """

    def _eval_mating_side(value: Optional[int]) -> Optional[str]:
        if value is None or abs(value) < 9000:
            return None
        return "white" if value > 0 else "black"

    def _branch(
        leading_move: Optional[str],
        continuation: List[str],
        branch_eval: Optional[int],
        *,
        delivered_now: bool = False,
    ) -> Dict[str, Any]:
        # Local import avoids the existing module cycle: the stored-line
        # verifier reads this module's canonical piece-value table.
        from services.stored_line_verifier import replay_stored_line

        replay = (
            replay_stored_line(board_before, leading_move, continuation)
            if leading_move
            else None
        )
        replay_side = None
        if replay and replay.complete and replay.checkmate:
            replay_side = (
                "white"
                if replay.checkmating_color == chess.WHITE
                else "black"
            )
        eval_side = _eval_mating_side(branch_eval)
        conflict = bool(replay_side and eval_side and replay_side != eval_side)
        side = None if conflict else (replay_side or eval_side)
        raw_ply = replay.mate_ply if replay_side and replay else None
        if delivered_now:
            side = "white" if own_color == chess.WHITE else "black"
            raw_ply = 1
            conflict = False
        mate_in = None
        if raw_ply is not None and side is not None:
            branch_mover = board_before.turn
            mating_color = chess.WHITE if side == "white" else chess.BLACK
            mate_in = (
                (raw_ply + 1) // 2
                if mating_color == branch_mover
                else max(1, raw_ply // 2)
            )
        sources = []
        if delivered_now:
            sources.append("board_checkmate")
        elif replay_side:
            sources.append("stored_line_replay")
        if eval_side:
            sources.append("stored_eval_sentinel")
        return {
            "complete": bool(replay and replay.complete),
            "has_forced_mate": bool(side),
            "side_delivering_mate": side,
            "ply_to_mate": raw_ply,
            "mate_in": mate_in,
            "line_san": list(replay.replayed_san) if replay else [],
            "engine_eval_indicates_mate": bool(eval_side),
            "proof_sources": sources,
            "evidence_conflict": conflict,
        }

    played_branch = _branch(
        played_san,
        pv_after_played,
        eval_after_cp,
        delivered_now=is_checkmate,
    )
    best_branch = _branch(
        best_move_san,
        pv_after_best,
        eval_before_cp,
    )
    if (
        played_branch["evidence_conflict"]
        or best_branch["evidence_conflict"]
    ):
        return None

    mover = "white" if own_color == chess.WHITE else "black"
    opponent = "black" if own_color == chess.WHITE else "white"
    played_side = played_branch["side_delivering_mate"]
    best_side = best_branch["side_delivering_mate"]

    if is_checkmate:
        transition = "delivered"
        relevant = played_branch
    elif played_side == opponent:
        transition = "already_lost" if best_side == opponent else "allowed"
        relevant = played_branch
    elif played_side == mover:
        transition = "preserved"
        relevant = played_branch
    elif best_side == mover:
        transition = "missed"
        relevant = best_branch
    elif best_side == opponent:
        transition = "already_lost"
        relevant = best_branch
    else:
        return None

    return {
        "transition": transition,
        "mover_color": mover,
        "opponent_color": opponent,
        "played_branch": played_branch,
        "best_branch": best_branch,
        # Backward-compatible summary fields.  They are derived from the
        # branch-owned result and must never be used to infer a transition.
        "side_delivering_mate": relevant["side_delivering_mate"],
        "ply_to_mate": relevant["mate_in"],
        "mate_in": relevant["mate_in"],
        "via_played_move": played_branch["has_forced_mate"],
        "via_best_move": best_branch["has_forced_mate"],
        "engine_eval_indicates_mate": bool(
            played_branch["engine_eval_indicates_mate"]
            or best_branch["engine_eval_indicates_mate"]
        ),
        "delivered_on_this_move": is_checkmate,
    }


# ────────────────────────────────────────────────────────────────────
# Missed-tactic detection (commit #4b)
#
# Run the same tactic-shape detectors that we use on the played position
# but apply them to the position AFTER the engine's best move. If a
# tactic shape exists in pv_after_best that didn't exist in
# pv_after_played, the user missed a tactic.
#
# Visibility scoring (per user feedback 2026-05-11):
#   The shape must be HUMAN-VISIBLE — Stockfish ghost tactics that
#   require 6-ply only-move precision should NOT trigger missed-tactic
#   coaching. Score 1 = trivial (immediate, ≥minor piece), score 5 =
#   engine-only depth.
#
# Renderer thresholds the score via DEFAULT_VISIBLE_TACTIC_THRESHOLD in
# caption renderer config (default 2). Different surfaces (1200 coach,
# 1800 coach, puzzle mode) can set different thresholds.
# ────────────────────────────────────────────────────────────────────


def _missed_tactic_evidence(
    board_before: chess.Board,
    pv_after_best: List[str],
    best_move_san: Optional[str],
    played_tactics_exist: bool,
) -> List[Dict[str, Any]]:
    """If the user did NOT play the best move, run the shape detectors
    on the position after best_move and the next opponent reply.

    Returns a list of missed-tactic entries — each with:
      - tactic_kind: "multi_target_attack" | "aligned_pieces" | "discovered_attack"
      - tactic_data: the evidence dict from the corresponding detector
      - tactic_resolves_at_ply: 1 = after best move; 2 = after best
        move + forced response; etc.
      - minimum_material_gain_cp: SEE value of best capturing move
        in the detected shape
      - human_visibility_score: 1 = trivial, 5 = engine-only depth.
        Computed from tactic_resolves_at_ply + material gain +
        complexity of intervening moves.
    """
    if not pv_after_best or not best_move_san:
        return []
    if played_tactics_exist:
        # User already created a tactic with the played move; don't
        # bother surfacing alternative tactics from pv_after_best.
        return []

    # Walk pv_after_best up to a few plies, run shape detectors on each
    # board_after-best-line position, return any new shapes found.
    sim = board_before.copy()
    normalized_pv = _normalize_pv_starting_with(best_move_san, pv_after_best)

    plies_walked = 0
    own_color = sim.turn  # whoever was to move at board_before
    out: List[Dict[str, Any]] = []

    for ply_idx, san in enumerate(normalized_pv[:4]):
        try:
            move = sim.parse_san(san)
            sim.push(move)
            plies_walked += 1
        except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
            break

        # Only check tactics AFTER own-color moves resolve (i.e. after
        # plies 1 (best), 3 (best + opponent reply + own next), etc.).
        # Tactic in board AFTER own move means we're looking at what
        # WE could have created.
        is_own_move = (ply_idx % 2 == 0)
        if not is_own_move:
            continue

        # Synthesize a played_move stub for discovery detection (using
        # the actual played move at this ply). We need the move object,
        # not just SAN.
        # _discovered_attack_evidence needs the pre-move and post-move
        # boards. Since we already pushed `move`, we'd need to track the
        # pre-move state. Simplest: skip discovered_attack here; it's
        # heavily move-context dependent. Focus on aligned_pieces and
        # multi-target patterns which depend only on the post-move
        # position.

        # Run aligned-pieces and multi-target detectors on the current
        # sim board (which is the post-ply position from own POV).
        aligned = _aligned_pieces_evidence(sim, own_color)
        # Multi-target requires threats_created which requires a
        # before+after diff. We approximate: any aligned-pieces shape
        # with rear_value > 300 counts as a potential winning tactic.
        for shape in aligned:
            # Only flag shapes that win material — front_value_vs_rear
            # = "lower" (classic pin/winning skewer scenario) and rear
            # is high-value (rook or queen).
            if shape["rear_piece_value_cp"] < 500:
                continue
            # Resolves at the ply where the shape was detected.
            tactic_resolves_at_ply = plies_walked
            minimum_material_gain_cp = shape["rear_piece_value_cp"] - shape["front_piece_value_cp"]
            if minimum_material_gain_cp <= 0:
                # Not actually a winning gain at this geometry.
                continue
            # Visibility: 1 if resolves on ply 1, +1 per extra ply.
            # If gain is < 200cp (less than a minor piece), bump score
            # by 1 (smaller targets are harder for humans to value).
            visibility = tactic_resolves_at_ply
            if minimum_material_gain_cp < 200:
                visibility += 1
            out.append({
                "tactic_kind": "aligned_pieces",
                "tactic_data": shape,
                "tactic_resolves_at_ply": tactic_resolves_at_ply,
                "minimum_material_gain_cp": minimum_material_gain_cp,
                "human_visibility_score": visibility,
            })

    # Sort by visibility ascending (most visible first), then by gain desc
    out.sort(key=lambda x: (x["human_visibility_score"], -x["minimum_material_gain_cp"]))
    return out


# ────────────────────────────────────────────────────────────────────
# Primary-reason scoring layer (commit #4b)
#
# Pick ONE category of reason from the facts dict using a HARD priority
# order. Returns a structured dict identifying the category and the
# reference to the supporting evidence — NOT a coaching string. The
# renderer turns the category into prose.
#
# Priority (highest first):
#   1.  mate            — mate_threat_evidence is present
#   2.  tactic_played   — own tactic shape on the played move
#   3.  check_extra     — is_check AND threats_created non-empty
#   4.  forced_recapture — single-best forced response
#   5.  material        — gated: material delta accounts for ≥70% of
#                         eval swing AND is positive (own gain)
#   6.  king_safety     — is_castling
#   7.  defense         — defends a higher-value attacked piece
#   8.  threat          — threats_created non-empty (no tactic above)
#   9.  pawn_structure  — recapture toward centre (Phase 1 minimal)
#  10.  development     — opening + develops_minor + concrete next-step
#  11.  None            — no extractable reason; renderer stays silent
# ────────────────────────────────────────────────────────────────────


def _eval_swing_cp(facts: Dict[str, Any]) -> int:
    """Eval delta from side-to-move's POV. Positive = the move made the
    position better for the side that just moved."""
    eb = facts.get("eval_before_cp")
    ea = facts.get("eval_after_cp")
    if eb is None or ea is None:
        return 0
    side_white = facts.get("moving_piece_color") == "white"
    # Eval-after is white-POV; for black, we flip both then take diff.
    if side_white:
        return ea - eb
    return -(ea - eb)


def _material_explains_eval(facts: Dict[str, Any]) -> bool:
    """Material gain accounts for at least 70% of the eval swing.
    Prevents 'wins a pawn' from drowning out 'creates a mating attack'
    when the eval swing is much larger than the material gain.

    Free-capture short-circuit (from d7ce40cf #22 USER Rxc6): when the
    capture has no recapture (free_capture=True), the move's STORY is
    the capture even if the engine eval swing is ~0 because it already
    discounted the captured piece in scoring the previous opp blunder.
    Without this short-circuit, "punish the opp's hung knight" reads
    silent — exactly when the user most needs the celebration.
    """
    delta_played = facts.get("material_delta_played_cp") or 0
    if delta_played <= 0:
        return False
    if facts.get("free_capture"):
        return True
    swing = _eval_swing_cp(facts)
    if swing <= 50:
        return False
    return abs(delta_played) >= 0.7 * abs(swing) - 50


def extract_primary_reason(facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a structured dict identifying THE primary-reason category
    for this move, plus a reference to the supporting evidence in the
    facts dict. Returns None when no extractable reason exists (renderer
    should render silently per R-FALLBACK).

    Output shape:
      {
        "category": "mate" | "tactic_played" | "check_extra" | ...,
        "ref_field": str,             # which facts key holds the evidence
        "priority_level": int,        # for debugging / regression
      }

    Does NOT produce coaching prose — LAW 1 (no smart strings).
    """
    # Priority 1: mate (essence overrides everything)
    if facts.get("mate_threat_evidence"):
        return {
            "category": "mate",
            "ref_field": "mate_threat_evidence",
            "priority_level": 1,
        }

    # ── Tactic-celebration safety gate ──────────────────────────────
    # If the engine calls this move a mistake/blunder, the geometric
    # tactic shape is incidental — celebrating "you forked X and Y"
    # on a 286-cp blunder is teaching the wrong thing. Fall through
    # to the blunder/mistake rules (added in a later commit) instead.
    # Bug from d7ce40cf corpus: #19 Re7, #17 a3, #9 Bg5.
    _move_cpl = facts.get("cp_loss") or 0
    _tactic_ok = _move_cpl < MAX_CP_LOSS_FOR_TACTIC_CELEBRATION

    # Priority 2: own tactic shape on the played move (gated)
    # Routed through is_named_fork() — the shared promotion policy. A royal fork
    # whose only winnable target is a pawn is a real fork geometrically, but it
    # is not worth NAMING as one; it falls through to the check_extra rule
    # below, which explains the check and the pawn honestly.
    if _tactic_ok and named_fork_shapes(facts.get("multi_target_attack_evidence")):
        return {
            "category": "tactic_played",
            "ref_field": "named_fork_evidence",
            "priority_level": 2,
        }
    if _tactic_ok and facts.get("aligned_pieces_evidence"):
        # Only fire if rear piece has real value (≥ rook) — pawn pins
        # are too trivial to be the primary reason. Also skip pawn-front
        # pins (front=pawn) unless the rear is a king — "pins the pawn
        # on d2 against the queen on d1" reads as a real pin but isn't
        # actionable (pawn pushes don't expose anything on an x-ray
        # geometry where the attacker is also on the file). Pawn pinned
        # against king IS absolute and worth captioning.
        for shape in facts["aligned_pieces_evidence"]:
            if shape.get("rear_piece_value_cp", 0) < 500:
                continue
            if (shape.get("front_piece_type") == "pawn"
                and not shape.get("rear_is_king", False)):
                continue
            return {
                "category": "tactic_played",
                "ref_field": "aligned_pieces_evidence",
                "priority_level": 2,
            }
    if _tactic_ok and facts.get("discovered_attack_evidence"):
        for ev in facts["discovered_attack_evidence"]:
            if ev.get("target_value_cp", 0) >= 300:
                return {
                    "category": "tactic_played",
                    "ref_field": "discovered_attack_evidence",
                    "priority_level": 2,
                }

    # Priority 3: check + extra attack (concrete tactical pressure)
    # Gated on _tactic_ok: don't celebrate a check on a blunder move
    # (e.g., Qxc2+ cp_loss=9923 that gives check). Fix #5.
    if _tactic_ok and facts.get("is_check") and facts.get("threats_created"):
        return {
            "category": "check_extra",
            "ref_field": "threats_created",
            "priority_level": 3,
        }

    # Priority 4: plain check — is_check without an extra attack still
    # represents a forcing teaching moment ("king has to respond").
    # Lower than check_extra so a check + fork goes to category=tactic_played.
    # Gated on _tactic_ok: don't celebrate a plain check on a blunder.
    # Fix #5 cont'd.
    if _tactic_ok and facts.get("is_check"):
        return {
            "category": "check_plain",
            "ref_field": "is_check",
            "priority_level": 4,
        }

    # Priority 5: forced recapture (factual, no praise).
    # Same cp_loss gate as tactic/threat — "only move, takes back the
    # piece" is celebratory framing that misleads on a losing recapture
    # (e.g. d7ce40cf #7 Nxd5 330 cp blunder where declining was better).
    if _tactic_ok and facts.get("is_forced_recapture"):
        return {
            "category": "forced_recapture",
            "ref_field": "captured_piece_type",
            "priority_level": 5,
        }

    # Priority 6: material — gated by eval-swing accounting
    # Also gated on _tactic_ok: don't celebrate a capture on a blunder.
    # Fix #5 cont'd.
    if _tactic_ok and _material_explains_eval(facts):
        return {
            "category": "material",
            "ref_field": "material_delta_played_cp",
            "priority_level": 6,
        }

    # Priority 7: king safety. Gated by _tactic_ok — celebrating
    # "King is safe; rook joins the game" on a castling blunder
    # (fb_f35ee12cdd51 O-O-O cpl=698 left a piece hanging;
    #  fb_5efd285edc07 O-O cpl=112) buries the actual problem. When
    # the engine flags this castle as a mistake or worse, fall through
    # to the blunder/mistake category so R12 renders the real cost.
    if _tactic_ok and facts.get("is_castling"):
        return {
            "category": "king_safety",
            "ref_field": "is_castling",
            "priority_level": 7,
        }

    # Priority 7: defense — defends a higher-value attacked piece.
    # Phase 1 implementation: any piece in pieces_now_undefended which
    # is NOT now-hanging counts as "successfully defended elsewhere."
    # Stronger detection arrives when we add an explicit
    # `pieces_now_defended` field in a later phase.

    # Priority 8: threat creation (non-tactic threats; same gate as
    # tactics — threats are only worth celebrating on non-mistake moves
    # AND the threat must clear MIN_THREAT_SEE_CP so this category
    # matches the R10 trigger. From d7ce40cf v2 review: #3 Bb7, #4 Nf6,
    # #15 Nc6 each created weak see=100 threats; primary_reason picked
    # "threat" but R10 needs see ≥ 200, so no rule fired and a clean
    # development move went silent.
    threats = facts.get("threats_created") or []
    if _tactic_ok and any(t.get("see_cp", 0) >= MIN_THREAT_SEE_CP for t in threats):
        return {
            "category": "threat",
            "ref_field": "threats_created",
            "priority_level": 8,
        }

    # Priority 9: opening central pawn — first 1–2 full moves where a
    # pawn lands on a central square (d4/d5/e4/e5). Covers the silent
    # #1 e4 / #1 d5 case from the d7ce40cf review. Gated on cp_loss
    # like other celebratory categories.
    if (
        _tactic_ok
        and facts.get("phase") == "opening"
        and facts.get("is_pawn_move")
        and (facts.get("full_move_number") or 0) <= 2
        and facts.get("target_square") in ("d4", "d5", "e4", "e5")
    ):
        return {
            "category": "opening_central_pawn",
            "ref_field": "target_square",
            "priority_level": 9,
        }

    # Priority 9: pawn structure (Phase 1 minimal — explicit fact)
    # Reserved for when concept facts arrive.

    # Priority 10: development — opening + develops minor + has next-step.
    # v76 (2026-05-23) — Mohit + Parth: tightened cp_loss gate from
    # <100 to <30. A developing move with cp_loss 30-99 is a small
    # INACCURACY, not a clean development move; routing it to
    # category="development" makes R11 (silenced) eat the move and
    # blocks R12 from firing the now-wired opp-narration. Parth
    # surfaced this on m4 Be6 (cp_loss=88) and m9 Be7 (cp_loss=72) —
    # both opp inaccuracies that should fall through to "blunder"
    # category so R12 produces "Opponent's Be6 is a mistake. You
    # can play X to punish it."
    _dev_ok = _move_cpl < 30
    # Parth yellow-bucket (cp_loss 1-29 near-best gap): when the move is
    # a USER move with cp_loss < 30, route it to "good_move" so R15 can
    # produce a specific caption (develop / capture / central_break /
    # bishop_pair_trade) or fall through silent. The previous _is_user_best
    # gate (cp_loss==0 + played_is_best) covered only exact-best moves;
    # this extends positive-reinforcement coverage to near-best moves
    # (Nf6 cpl=6, c6 cpl=2, Qa5 cpl=5, Qd8 cpl=27 all fell into the
    # silent gap before — fb_deed013c3f35 / fb_b250249f7724 / fb_dc63587ede08
    # / fb_fa464cae3b84).
    if (
        _dev_ok
        and facts.get("phase") == "opening"
        and facts.get("moving_piece_type") in ("knight", "bishop")
        and facts.get("mover_is_user") is not True
    ):
        # Opp minor-piece development in opening with cpl < 30 -> R11 silent.
        # User moves with cpl < 30 fall through to good_move below.
        return {
            "category": "development",
            "ref_field": "moving_piece_type",
            "priority_level": 10,
        }

    # Priority 11: blunder — last-resort category that fills the silence
    # for any move whose engine evaluation calls it a mistake or worse.
    # All celebratory categories above are gated on cp_loss < the
    # MAX_CP_LOSS_FOR_TACTIC_CELEBRATION threshold, so anything that
    # reaches this point with cp_loss above that threshold is a real
    # blunder/mistake with no redeeming tactical or developmental story.
    # From d7ce40cf corpus this fills silences on:
    #   user side : #6 d3, #7 Nxd5, #9 Bg5, #17 a3, #19 Re7
    #   opp side  : #19 Rd8, #21 Rd8
    #
    # CORNER: when played_is_best == True and cp_loss is high, the
    # position was already lost and the player chose the best damage
    # control. Calling that a "blunder" lies. Forced-best category
    # below catches it BEFORE the blunder fallback fires.
    # v76 (2026-05-23): blunder category gate lowered 100 → 30 in
    # concert with R12_blunder.json's trigger gate lowering. The
    # forced_best CORNER (where the played move IS engine's #1 despite
    # high cp_loss — damage-control) keeps its higher threshold (100)
    # because it only makes sense when the player had no good option.
    if _move_cpl >= MAX_CP_LOSS_FOR_TACTIC_CELEBRATION:
        if facts.get("played_is_best"):
            return {
                "category": "forced_best",
                "ref_field": "played_is_best",
                "priority_level": 10,
            }
    if _move_cpl >= 30:
        return {
            "category": "blunder",
            "ref_field": "cp_loss",
            "priority_level": 11,
        }

    # Priority 12: good_move — user played a NEAR-BEST move in a
    # not-already-lost position. Originally gated tight (played_is_best
    # AND cp_loss==0 AND mover_is_user) — Mohit 2026-05-19. Yellow-
    # bucket re-probe 2026-05-28 found user moves with cp_loss 1-29 fell
    # in a silent gap (good_move requires ==0; blunder requires >=30).
    # Loosened to cp_loss < 30 + mover_is_user so R15 can fire its
    # SPECIFIC variants (develop / capture / central_break /
    # bishop_pair_trade) on near-best moves; R15's default "strongest
    # move here" still only renders when cp_loss == 0 (no overclaim on
    # non-exact-best). Per Parth fb_deed013c3f35 / fb_b250249f7724 /
    # fb_dc63587ede08 / fb_fa464cae3b84.
    if (
        _tactic_ok
        and (_move_cpl < 30)
        and facts.get("mover_is_user") is True
    ):
        return {
            "category": "good_move",
            "ref_field": "cp_loss",
            "priority_level": 12,
        }

    return None


def _queen_sortie_evidence(
    board_before: chess.Board,
    played_move: chess.Move,
    move_history_san: List[str],
    full_move_number: int,
) -> Optional[Dict[str, Any]]:
    """Evidence dict for early queen sorties — when a queen moves out
    in the opening before sufficient minor-piece development.

    Returns None when the move isn't a queen move, or when the position
    is past the opening phase (move_number > 10), or when adequate
    minor pieces are already developed.

    Per user feedback (2026-05-11): emit EVIDENCE, not a boolean
    judgment. Numbers the renderer can use to decide phrasing.
    """
    moving_piece = board_before.piece_at(played_move.from_square)
    if not moving_piece or moving_piece.piece_type != chess.QUEEN:
        return None
    if full_move_number > 10:
        return None

    queen_color = moving_piece.color
    # Count minor pieces (knight + bishop) of this color OFF their starting squares.
    # python-chess starting bitboards:
    if queen_color == chess.WHITE:
        starting_knights = {chess.B1, chess.G1}
        starting_bishops = {chess.C1, chess.F1}
    else:
        starting_knights = {chess.B8, chess.G8}
        starting_bishops = {chess.C8, chess.F8}

    developed_minor = 0
    for sq in board_before.pieces(chess.KNIGHT, queen_color):
        if sq not in starting_knights:
            developed_minor += 1
    for sq in board_before.pieces(chess.BISHOP, queen_color):
        if sq not in starting_bishops:
            developed_minor += 1

    # Count how many queen moves of this color have happened in history.
    queen_moves_so_far = 0
    for idx, san in enumerate(move_history_san):
        # White moves are even-indexed (0, 2, 4...), black are odd-indexed.
        is_white_move = (idx % 2 == 0)
        if is_white_move != (queen_color == chess.WHITE):
            continue
        if san.startswith("Q"):
            queen_moves_so_far += 1
    # The current move counts as the next queen move (about to be played).
    queen_move_index = queen_moves_so_far + 1

    return {
        "piece_color": "white" if queen_color == chess.WHITE else "black",
        "from_square": chess.square_name(played_move.from_square),
        "to_square": chess.square_name(played_move.to_square),
        "full_move_number": full_move_number,
        "minor_pieces_developed": developed_minor,
        "queen_move_index_in_opening": queen_move_index,
    }


def _is_forced_recapture(board_before: chess.Board, played_move: chess.Move) -> bool:
    """A move is a 'forced recapture' if and only if:
      - The previous move was a capture into prev.to_square
      - The played move captures on that same square
      - There is LITERALLY ONLY ONE legal move in the pre-move position
        (the strict definition where R07's "only move" caption is true).

    Pre-2026-05-13 implementation used a soft criterion ("did we
    recapture on the same square?") which fired "only move" on
    positions with many legal alternatives. User-flagged bugs:
      fb_0bc718b251da (Qxc4) — "not the only move"
      fb_ee278d250e5c (dxe5) — alternatives like f6-fork avoidance
      fb_f49d896177d8 (exd5) — "this is not the only move. White can
                                capture on d5 or play e5 or just ignore"
    Tightened to len(legal_moves)==1 so the caption is accurate.

    This silences R07 on most recaptures (since chess positions rarely
    have only one legal move). Those fall through to R08 (material gain)
    or R12 (mistake/blunder) which frame correctly.
    """
    if not played_move or not board_before.move_stack:
        return False
    prev = board_before.peek()
    if not prev or prev.to_square is None:
        return False
    landing_piece = board_before.piece_at(prev.to_square)
    if not landing_piece:
        return False
    if landing_piece.color == board_before.turn:
        return False
    if played_move.to_square != prev.to_square or not board_before.is_capture(played_move):
        return False
    # Strict "only move" check — what the R07 caption actually claims.
    return board_before.legal_moves.count() == 1


# ────────────────────────────────────────────────────────────────────
# Principle detectors (the teaching layer)
#
# Each detector is a pure function of (facts, board_before) that returns
# an evidence dict if the principle matches, or None otherwise. Detectors
# are NEVER aware of game state ("has this fired before this game?") —
# that's the V5 wiring layer's job. They just answer "would this
# principle fire on THIS move in THIS position?"
#
# Per memory rule feedback_design_clean_code_leaky.md:
#   - Detectors ship ONE AT A TIME, each with a corpus audit before the next
#   - Edge cases enumerated at the top of every detector docstring
#   - Real-corpus tests (not synthetic) before commit
#
# Catalog is in services/caption_principles.py — every principle_id
# returned here must exist in that file.
# ────────────────────────────────────────────────────────────────────


def _principle_engine_endorsement(
    aligned_moves: List[str],
    best_move_san: Optional[str],
) -> str:
    """Compare engine's #1 to the principle-aligned move set.

    Returns:
      "best"    — engine's #1 IS one of the aligned moves (strong claim)
      "absent"  — engine prefers a non-aligned move (long-term principle)

    Note: tier "top_n" (aligned move in engine top-3 PV) is documented in
    caption_principles.py for future multi-PV support. V5 currently
    ships single-line PV only, so this function returns binary
    best/absent. Once multi-PV lands, add a top_n branch here without
    touching detectors.
    """
    if not best_move_san or not aligned_moves:
        return "absent"
    best_norm = _normalize_san(best_move_san)
    for am in aligned_moves:
        if _normalize_san(am) == best_norm:
            return "best"
    return "absent"


def _developing_minor_moves(
    board_before: chess.Board,
    color: chess.Color,
) -> List[str]:
    """All legal moves that develop a knight or bishop from its starting
    square. Used by opening principles whose aligned_moves spec is
    "any minor-piece development."

    Edge cases handled:
      - Already-developed minors are skipped (only starting-square pieces)
      - Returns SAN strings, normalised (no annotation suffixes)
      - Returns [] if no developing moves are legal in this position
    """
    if color == chess.WHITE:
        starting_knights = {chess.B1, chess.G1}
        starting_bishops = {chess.C1, chess.F1}
    else:
        starting_knights = {chess.B8, chess.G8}
        starting_bishops = {chess.C8, chess.F8}

    out: List[str] = []
    for move in board_before.legal_moves:
        piece = board_before.piece_at(move.from_square)
        if not piece or piece.color != color:
            continue
        if piece.piece_type == chess.KNIGHT and move.from_square in starting_knights:
            out.append(_normalize_san(board_before.san(move)))
        elif piece.piece_type == chess.BISHOP and move.from_square in starting_bishops:
            out.append(_normalize_san(board_before.san(move)))
    return out


# ── Detector #1: OP_QUEEN_OUT_EARLY ─────────────────────────────────
#
# Edge cases enumerated:
#   1. Queen recaptures (e.g. Qxe2+) — `queen_sortie_evidence` returns
#      None because we're past move 10 in most of these cases; if not,
#      cp_loss_strict filters (recaptures rarely cost ≥30 cp).
#   2. Queen check-blocks (Qe2 to block check) — same as above; the
#      cp_loss filter catches these because forced moves have cp_loss ~0.
#   3. Move 1-2 queen moves (e.g. 1.Qh5 or 2.Qf3) — fire correctly;
#      these are textbook queen-sortie cases.
#   4. Position with castling rights already lost — still fires; the
#      principle is about development order, not castling specifically.
#   5. Endgame queen moves — phase_in_scope gates to opening only;
#      queen_sortie_evidence also caps at full_move_number ≤ 10.
#   6. Aligned-moves empty (no minor pieces left to develop) — endorsement
#      becomes "absent" automatically; principle still fires with the
#      cue_absent tone.
def _p_op_queen_out_early(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Detector for OP_QUEEN_OUT_EARLY.

    Fires when:
      - Played move is a queen move
      - Position is in opening phase (full_move_number ≤ 10)
      - queen_sortie_evidence is populated (already enforces #1, #2 above)
      - cp_loss ≥ 30 (engine confirms the move is suboptimal)

    Returns evidence dict or None.
    """
    if facts.get("moving_piece_type") != "queen":
        return None
    sortie = facts.get("queen_sortie_evidence")
    if not sortie:
        return None
    if facts.get("phase") != "opening":
        return None
    # gate_policy from caption_principles.py:
    #   "endorsement_preferred + cp_loss_strict"
    # cp_loss_strict applies regardless of endorsement.
    if (facts.get("cp_loss") or 0) < 30:
        return None

    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    # v91 (2026-05-25): mirror the v81 OP_FINISH_DEVELOPMENT fix.
    # Parth flagged Qd8 m5 (queen RETREAT from d5 back to d8 after
    # being chased) firing this principle with the cue "Bringing the
    # queen out early — develop a minor piece first. Queens out early
    # get chased and lose tempo." That's exactly backwards on a
    # retreat — the queen is going BACK to home, not coming out.
    # Per [[fix-framing-not-detection]], silence the principle for
    # retreats rather than rewriting the cue (the cue is correct for
    # genuine sorties). queen_sortie_evidence is computed for ANY
    # queen move in the opening; gate the principle on the queen
    # actually LEAVING her home square.
    home_square = "d1" if own_color == chess.WHITE else "d8"
    if sortie.get("from_square") != home_square:
        return None
    aligned = _developing_minor_moves(board_before, own_color)
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))

    return {
        "principle_id": "OP_QUEEN_OUT_EARLY",
        "evidence": {
            "queen_from": sortie.get("from_square"),
            "queen_to": sortie.get("to_square"),
            "queen_move_index_in_opening": sortie.get("queen_move_index_in_opening"),
            "minor_pieces_developed": sortie.get("minor_pieces_developed"),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #2: TAC_FORK_PATTERN ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Multi-target shape evidence already filters pawn-only forks
#      into a different render template at the rule layer, but here
#      we surface the principle if ANY multi_target shape exists with
#      at least one target valued ≥ knight (300 cp). Pure pawn-pawn
#      forks don't fire (catches "Rc7 attacks two pawns" cases).
#   2. cp_loss gate: principle fires on a TACTIC the user found, so
#      cp_loss is expected to be LOW (engine endorses). gate_policy
#      "endorsement_required" enforces this implicitly.
#   3. Mover_is_user — fork principles fire for either side; the cue
#      branches at render time on perspective. Detector is symmetric.
def _p_tac_fork_pattern(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the played move creates a multi-target attack with at
    least one target valued ≥ knight, AND the engine endorses the move."""
    # Promotion policy comes from the shared predicate — this used to inline its
    # own `any(value_cp >= 300)`, a second copy of the threshold that could drift
    # from is_named_fork(). Falls back to filtering the raw list so the helper
    # still works when handed a facts dict built before the view existed.
    shapes = facts.get("named_fork_evidence")
    if shapes is None:
        shapes = named_fork_shapes(facts.get("multi_target_attack_evidence"))
    if not shapes:
        return None
    shape = shapes[0]
    # endorsement_required: only fire when engine endorses the move
    # itself. Since the played move IS what created the fork, the
    # engine's #1 should match played_san for the principle to apply.
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    endorsement = "best" if (played and best and played == best) else "absent"
    if endorsement == "absent":
        return None
    return {
        "principle_id": "TAC_FORK_PATTERN",
        "evidence": {
            "attacker_square": shape.get("attacker_square"),
            "attacker_piece_type": shape.get("attacker_piece_type"),
            "targets": [
                {"square": t["square"], "piece_type": t["piece_type"]}
                for t in targets[:2]
            ],
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": [played],
    }


# ── Detector #3: TAC_PIN_PATTERN ────────────────────────────────────
#
# Edge cases enumerated:
#   1. Pawn-front pins already filtered by aligned_pieces_evidence
#      (bend #8 — pawn pinned against queen is geometric but trivial,
#      excluded unless rear is king).
#   2. Rear must be at least rook value (already gated in
#      MIN_ALIGNED_REAR_VALUE_CP); also requires engine endorses move.
#   3. front_value_vs_rear "higher" reads as skewer at render time;
#      here both pin AND skewer fire under the same principle for the
#      teaching layer (the catalog uses TAC_PIN_PATTERN broadly).
def _p_tac_pin_pattern(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the played move creates a pin/skewer alignment with a
    rear piece worth at least a rook AND the front piece is not a pawn
    (unless rear is king), AND the engine endorses the move."""
    shapes = facts.get("aligned_pieces_evidence") or []
    # Apply the filter, with rear-is-king exemption added 2026-05-18.
    # Previously this filter excluded king-rear shapes because the king's
    # PIECE_VALUE_CP is 0 (SEE-capped) and 0 < MIN_ALIGNED_REAR_VALUE_CP (500).
    # That excluded the MOST COMMON pin a 1200 ever sees — Ruy Lopez Bb5
    # pinning c6 knight to e8 king (the absolute pin, where the front
    # piece is LITERALLY illegal to move). Self-audit 2026-05-18 caught
    # this when coach-move teaching wouldn't fire on Bb5.
    # Symmetric with the R03 renderer fix (caption_rules.py 2349b2d2).
    relevant = []
    for s in shapes:
        is_king_rear = s.get("rear_is_king", False)
        if not is_king_rear and s.get("rear_piece_value_cp", 0) < 500:
            continue
        if s.get("front_piece_type") == "pawn" and not is_king_rear:
            continue
        relevant.append(s)
    if not relevant:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    endorsement = "best" if (played and best and played == best) else "absent"
    if endorsement == "absent":
        return None
    shape = max(relevant, key=lambda s: s.get("rear_piece_value_cp", 0))
    return {
        "principle_id": "TAC_PIN_PATTERN",
        "evidence": {
            "attacker_square": shape.get("attacker_square"),
            "front_piece_type": shape.get("front_piece_type"),
            "front_square": shape.get("front_piece_square"),
            "rear_piece_type": shape.get("rear_piece_type"),
            "rear_square": shape.get("rear_piece_square"),
            "rear_is_king": shape.get("rear_is_king", False),
            "front_is_king": shape.get("front_is_king", False),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": [played],
    }


# ── Detector #4: TAC_DISCOVERED_PATTERN ─────────────────────────────
#
# Edge cases enumerated:
#   1. Mutual-line discoveries already filtered by bend #4 SEE gate —
#      false discoveries where opp captures the slider first are gone.
#   2. Ray-before-from_sq must be clear (bend #4 fix from feedback
#      fb_a6f596afbba0) — blocked lines don't emit evidence.
#   3. Endorsement_required — only fire when engine's #1 IS the move
#      that uncovers.
def _p_tac_discovered_pattern(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the played move uncovers a slider attack on an enemy
    piece AND the engine endorses the move."""
    evs = facts.get("discovered_attack_evidence") or []
    if not evs:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    endorsement = "best" if (played and best and played == best) else "absent"
    if endorsement == "absent":
        return None
    # 2026-05-25: require the discovered target to be a non-pawn piece
    # (≥knight). Mohit caught m7 e5 (central pawn push, cp_loss=10) firing
    # this principle because the e7→e5 push uncovered the f8 bishop's
    # f8-a3 diagonal onto a3 (a white pawn). Geometrically a "discovered
    # attack," tactically meaningless — it's just a classical opening
    # pawn push, and the cue ("Play this immediately") talks like a
    # tactic was found. Mirrors the TAC_FORK_PATTERN gate that already
    # excludes pawn-only forks (target value_cp ≥ 300). For discovered
    # attacks the relevant target is a real piece the slider can win.
    evs_nonpawn = [e for e in evs if (e.get("target_piece_type") or "") != "pawn"]
    if not evs_nonpawn:
        return None
    ev0 = evs_nonpawn[0]
    return {
        "principle_id": "TAC_DISCOVERED_PATTERN",
        "evidence": {
            "slider_square": ev0.get("discovered_attacker_square"),
            "slider_piece_type": ev0.get("discovered_attacker_piece_type"),
            "moved_from": ev0.get("moved_piece_from_square"),
            "target_square": ev0.get("target_square"),
            "target_piece_type": ev0.get("target_piece_type"),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": [played],
    }


# ── Detector #5: TAC_HANGING_PIECE ──────────────────────────────────
#
# Edge cases enumerated:
#   1. PRIMARY trigger: is_exchange_losing — the played move puts the
#      moving piece on a square where opponent's SEE is positive (more
#      attackers than defenders). Most common 600–1200 mistake.
#   2. SECONDARY trigger: pieces_now_undefended — the played move
#      removed a defender from another own piece, leaving it hanging.
#   3. Both gated by cp_loss ≥ 30 (engine confirms the move is bad).
#      Without this gate, intentional sacrifices and even trades fire.
#   4. endorsement_required: engine's #1 must DIFFER from played
#      (because the played move IS the hanging move; an aligned move
#      is any other safe move).
def _p_tac_hanging_piece(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the played move hangs a piece — either the moving
    piece lands on a losing-exchange square OR the move strips a
    defender off another own piece, leaving it attacked with no
    defender. cp_loss ≥ 30 confirms engine disagreement.
    """
    if (facts.get("cp_loss") or 0) < 30:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    # endorsement_required: engine's #1 must differ from played
    if not (best and played != best):
        return None

    # The hanging piece always belongs to the side that just moved.
    # Capture whether that side is the user (vs the opponent) so the
    # resolver detail + cue can render "your" vs "their" correctly.
    # Parth fb_b31dacc286bf (2026-05-17): the resolver_detail used
    # `owner == "user"` but evidence stored actual color ("black"),
    # so all captions read "their piece" even when the user hung
    # their own knight.
    mover_is_user = facts.get("mover_is_user")

    # PRIMARY: moving piece itself lands on losing-exchange square.
    if facts.get("is_exchange_losing"):
        loss = facts.get("exchange_loss_cp", 0) or 0
        return {
            "principle_id": "TAC_HANGING_PIECE",
            "evidence": {
                "hanging_piece_square": facts.get("target_square"),
                "hanging_piece_type": facts.get("moving_piece_type"),
                "piece_color": facts.get("moving_piece_color"),
                "mover_is_user": mover_is_user,
                "exchange_loss_cp": loss,
                "trigger": "moved_into_hanging_square",
            },
            "engine_endorsement": "best",
            "aligned_moves_offered": [best],
        }

    # SECONDARY: another own piece lost a defender and is now hanging.
    pieces = facts.get("pieces_now_undefended") or []
    hanging = [p for p in pieces if p.get("now_attacked") and p.get("is_now_hanging")]
    if not hanging:
        return None
    worst = max(
        hanging,
        key=lambda p: p.get("piece_value_cp", 0)
            if isinstance(p.get("piece_value_cp"), int) else 0
    )
    return {
        "principle_id": "TAC_HANGING_PIECE",
        "evidence": {
            "hanging_piece_square": worst.get("square"),
            "hanging_piece_type": worst.get("piece_type"),
            "piece_color": worst.get("piece_color"),
            "mover_is_user": mover_is_user,
            "trigger": "lost_defender",
            # The piece (and from-square) the played move took away from
            # defending. Surfaced so R12_blunder can compose the
            # "you moved your {piece} away from defending {square}" lead
            # clause that pairs with the better-move why_clause. Mohit
            # 2026-05-25: a 1200's mistake-of-the-move IS the act of
            # removing the defender — caption must say WHY the move was
            # wrong, not just what was better.
            "lost_defender_piece": worst.get("lost_defender_piece"),
            "lost_defender_square": worst.get("lost_defender_square"),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best],
    }


# ── Detector #6: OP_KNIGHT_ON_RIM ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Only triggers in opening phase.
#   2. Only triggers on a knight move TO an a- or h-file square.
#   3. Only when the knight came FROM a starting square (so this is the
#      knight's first developing move) — re-routing an already-developed
#      knight to the rim isn't a "developmental sin," it's a regrouping
#      choice.
#   4. cp_loss_strict (≥30): engine confirms the rim move is bad.
def _p_op_knight_on_rim(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when a knight develops to the a or h file in opening."""
    if facts.get("phase") != "opening":
        return None
    if facts.get("moving_piece_type") != "knight":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    target = facts.get("target_square") or ""
    if not target or target[0] not in ("a", "h"):
        return None
    # Only fire when the knight came from a starting square (development,
    # not regrouping).
    from_sq = facts.get("from_square") or ""
    own_color_str = facts.get("moving_piece_color")
    starting = {"b1", "g1"} if own_color_str == "white" else {"b8", "g8"}
    if from_sq not in starting:
        return None
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    aligned = _developing_minor_moves(board_before, own_color)
    # Filter to non-rim targets
    aligned = [m for m in aligned if not (len(m) >= 2 and m[-2] in ("a", "h"))]
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "OP_KNIGHT_ON_RIM",
        "evidence": {
            "knight_from": from_sq,
            "knight_to": target,
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #7: OP_SAME_PIECE_TWICE ────────────────────────────────
#
# Edge cases enumerated:
#   1. Captures don't count (capture buys back a tempo by winning
#      something — we don't penalise the second move of a piece if it
#      captures).
#   2. Checks don't count (forcing moves serve a different purpose).
#   3. Only triggers when there's a previously-moved own piece of
#      the SAME piece type. Tracked by walking move_history_san.
#   4. cp_loss_strict (≥30).
def _p_op_same_piece_twice(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the player moves a piece type they already moved in
    the opening — not a capture, not a check, and engine confirms
    suboptimal."""
    if facts.get("phase") != "opening":
        return None
    if facts.get("is_capture") or facts.get("is_check"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    moving_piece_type = facts.get("moving_piece_type")
    if not moving_piece_type:
        return None
    # Don't count pawn moves toward "same piece twice" — that's
    # covered by OP_PAWN_HEAVY.
    if moving_piece_type == "pawn":
        return None
    own_color_str = facts.get("moving_piece_color")
    own_is_white = (own_color_str == "white")
    # Walk own moves in history (own moves are at even/odd ply by color).
    history = facts.get("pv_after_played")  # not what we want
    # Actually pull move_history from facts. We stored move_index;
    # rebuild own history from board_before.move_stack.
    own_moves_history: List[chess.Move] = []
    for i, m in enumerate(board_before.move_stack):
        # First move (i=0) is white; even i = white moves, odd = black
        move_color = chess.WHITE if (i % 2 == 0) else chess.BLACK
        if move_color == (chess.WHITE if own_is_white else chess.BLACK):
            own_moves_history.append(m)
    # Look for a prior own move with the same piece type to a square
    # other than this one's from_square.
    moved_piece_chess_type = {
        "pawn": chess.PAWN, "knight": chess.KNIGHT, "bishop": chess.BISHOP,
        "rook": chess.ROOK, "queen": chess.QUEEN, "king": chess.KING,
    }.get(moving_piece_type)
    if moved_piece_chess_type is None:
        return None
    # Track every destination square that an own piece of this type
    # has reached. The principle fires only when the played move's
    # from_square is one of those destinations — meaning we're moving
    # an already-moved piece again (the SAME piece, even after
    # transposition). Walking the full move stack handles cases like
    # "knight moved a3 to c2 to d4" where the most-recent destination
    # changes; we want the union of all known destinations for this
    # piece type.
    prior_destinations: set = set()
    replay = chess.Board()
    for orig_idx, m in enumerate(board_before.move_stack):
        piece_at_from = replay.piece_at(m.from_square)
        piece_type_moved = piece_at_from.piece_type if piece_at_from else None
        replay.push(m)
        move_color = chess.WHITE if (orig_idx % 2 == 0) else chess.BLACK
        own_match = move_color == (chess.WHITE if own_is_white else chess.BLACK)
        if own_match and piece_type_moved == moved_piece_chess_type:
            # Remove the source from tracking — that square is no longer
            # this piece's location. Add the destination.
            prior_destinations.discard(m.from_square)
            prior_destinations.add(m.to_square)
    # v91 (2026-05-25) — Parth fb_441026e27b10. Previously this detector
    # fired on "any same-type-twice case" (the v1 comment), which caught
    # Bd7 (c8-bishop's FIRST move) as the second-bishop move while the
    # c5-bishop had already moved. Result: principle fired with the cue
    # "This move solves a specific threat. As a default..." on a clean
    # first-bishop-move. Tighten: require played_move's from_square to
    # be one of the prior destinations — i.e., we're moving an
    # already-moved piece, not a fresh same-type piece.
    played_from_san = facts.get("from_square")
    if played_from_san:
        try:
            played_from_sq = chess.parse_square(played_from_san)
        except Exception:
            played_from_sq = None
    else:
        played_from_sq = None
    if played_from_sq is None or played_from_sq not in prior_destinations:
        return None
    # Track for evidence (most-recent destination = where this piece
    # was about to be re-moved from).
    prior_same_type_to: Optional[int] = played_from_sq
    own_color = chess.WHITE if own_is_white else chess.BLACK
    aligned = _developing_minor_moves(board_before, own_color)
    # Filter: aligned moves should be of OTHER piece types (not the
    # type we already moved).
    aligned_other_types = []
    for san in aligned:
        # Quick check: knight SAN starts with N, bishop with B.
        if moving_piece_type == "knight" and san.startswith("N"):
            continue
        if moving_piece_type == "bishop" and san.startswith("B"):
            continue
        aligned_other_types.append(san)
    endorsement = _principle_engine_endorsement(aligned_other_types, facts.get("best_move_san"))
    return {
        "principle_id": "OP_SAME_PIECE_TWICE",
        "evidence": {
            "piece_type": moving_piece_type,
            "first_move_to_square": chess.square_name(prior_same_type_to),
            "this_move_from": facts.get("from_square"),
            "this_move_to": facts.get("target_square"),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned_other_types[:5],
    }


# ── Detector #8: OP_NOT_CASTLED ─────────────────────────────────────
#
# Edge cases enumerated:
#   1. State-entry match: only fires the first move that full_move ≥ 13
#      AND king on starting square AND castling rights still held AND
#      played move isn't castling. Suppression (once_per_state_entry)
#      handled at V5 wiring layer; detector fires every match.
#   2. No castling rights: principle moot, don't fire.
#   3. King already moved (off starting square): principle moot.
#   4. gate_policy endorsement_preferred — fires with cue_absent when
#      engine prefers something other than castling.
def _p_op_not_castled(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when full_move ≥ 13, king is still on its starting square,
    castling rights still held, played move isn't castling."""
    full_move = facts.get("full_move_number") or 0
    if full_move < 13:
        return None
    if facts.get("is_castling"):
        return None
    own_color_str = facts.get("moving_piece_color")
    own_is_white = (own_color_str == "white")
    own_color = chess.WHITE if own_is_white else chess.BLACK
    king_start = chess.E1 if own_is_white else chess.E8
    king_square = board_before.king(own_color)
    if king_square != king_start:
        return None
    if not (board_before.has_kingside_castling_rights(own_color)
            or board_before.has_queenside_castling_rights(own_color)):
        return None
    # Compute legal castling moves as aligned moves.
    aligned: List[str] = []
    for move in board_before.legal_moves:
        if board_before.is_castling(move):
            aligned.append(_normalize_san(board_before.san(move)))
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "OP_NOT_CASTLED",
        "evidence": {
            "king_square": chess.square_name(king_start),
            "full_move_number": full_move,
            "has_kingside_rights": board_before.has_kingside_castling_rights(own_color),
            "has_queenside_rights": board_before.has_queenside_castling_rights(own_color),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned,
    }


# ── Detector #9: OP_PAWN_HEAVY ──────────────────────────────────────
#
# Edge cases enumerated:
#   1. Only triggers in opening phase.
#   2. Only triggers on pawn moves (this move adds to pawn count).
#   3. Threshold: ≥3 OWN pawn moves in the first 6 own moves means
#      the player has spent too much opening time pushing pawns
#      (typical 600–1200 misallocation).
#   4. Captures count as pawn moves (they spend a tempo too).
#   5. cp_loss_strict (≥30).
def _p_op_pawn_heavy(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when player has played ≥3 pawn moves in their first 6
    own opening moves (including this one) AND engine disagrees."""
    if facts.get("phase") != "opening":
        return None
    if facts.get("moving_piece_type") != "pawn":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    own_color_str = facts.get("moving_piece_color")
    own_is_white = (own_color_str == "white")
    # Count own pawn moves in history INCLUDING this move.
    replay = chess.Board()
    own_move_count = 0
    own_pawn_count = 0
    for i, m in enumerate(board_before.move_stack):
        move_color = chess.WHITE if (i % 2 == 0) else chess.BLACK
        if move_color == (chess.WHITE if own_is_white else chess.BLACK):
            own_move_count += 1
            piece = replay.piece_at(m.from_square)
            if piece and piece.piece_type == chess.PAWN:
                own_pawn_count += 1
        replay.push(m)
    own_move_count += 1  # the current move
    own_pawn_count += 1  # the current move is a pawn move (per guard above)
    if own_move_count > 6:
        return None  # only the early opening window matters
    if own_pawn_count < 3:
        return None
    own_color = chess.WHITE if own_is_white else chess.BLACK
    aligned = _developing_minor_moves(board_before, own_color)
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "OP_PAWN_HEAVY",
        "evidence": {
            "own_pawn_moves_so_far": own_pawn_count,
            "own_moves_so_far": own_move_count,
            "this_move_from": facts.get("from_square"),
            "this_move_to": facts.get("target_square"),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #10: OP_CLAIM_CENTER ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Counterfactual match: fires when engine's best is a central
#      pawn push AND played move is something else. Captures the
#      "should have grabbed the centre" teaching moment.
#   2. Only in opening (full_move ≤ 6 is the tightest window where
#      central pawn is unambiguously the right choice).
#   3. Aligned central pawn pushes are e4 / d4 / e5 / d5.
#   4. gate_policy endorsement_preferred — fires with cue_absent when
#      the player's move WAS reasonable but engine still preferred the
#      central pawn (the "long-term habit" case).
def _p_op_claim_center(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 move is a central pawn push (e4/d4/e5/d5)
    AND the player played something else in the first 6 full moves
    AND the player's choice is actually suboptimal (cp_loss ≥ 20).

    The cp_loss gate was added in audit pass #1: without it, this
    fired on 1...c5 (Sicilian, cp_loss=0) saying "engine wanted e5"
    — technically true but misleading because the Sicilian is fine.
    Now only fires when the engine flags the player's choice as
    a real loss vs the central pawn.
    """
    if facts.get("phase") != "opening":
        return None
    full_move = facts.get("full_move_number") or 0
    if full_move > 6:
        return None
    if (facts.get("cp_loss") or 0) < 20:
        return None
    best = _normalize_san(facts.get("best_move_san") or "")
    if not best:
        return None
    # Aligned moves: e4/d4/e5/d5 pawn pushes legal in this position.
    own_color_str = facts.get("moving_piece_color")
    own_is_white = (own_color_str == "white")
    central_squares = {chess.D4, chess.E4} if own_is_white else {chess.D5, chess.E5}
    aligned: List[str] = []
    for move in board_before.legal_moves:
        piece = board_before.piece_at(move.from_square)
        if piece and piece.piece_type == chess.PAWN and move.to_square in central_squares:
            aligned.append(_normalize_san(board_before.san(move)))
    if not aligned:
        return None
    # Best move must be one of the aligned moves (counterfactual:
    # engine wanted the centre).
    if best not in aligned:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    if played in aligned:
        return None  # player DID claim the centre — no violation
    return {
        "principle_id": "OP_CLAIM_CENTER",
        "evidence": {
            "played": played,
            "engine_central_choice": best,
        },
        "engine_endorsement": "best",  # engine endorsed an aligned move
        "aligned_moves_offered": aligned,
    }


# ── Detector #11: TAC_DEFENDER_COUNT ────────────────────────────────
#
# Edge cases enumerated:
#   1. Trigger: is_exchange_losing — played move drops material in an
#      attacker-vs-defender mismatch. Same primary trigger as
#      TAC_HANGING_PIECE; priority resolution at render time picks
#      between them.
#   2. cp_loss_strict (≥30) — same gate.
#   3. endorsement_required — engine's #1 must differ from played.
#
# Overlap note: this fires alongside TAC_HANGING_PIECE on the same
# move records. Same firing event, different teaching emphasis
# ("count attackers/defenders" vs "loose piece"). Renderer priority
# (11 vs 12) lets HANGING_PIECE win when both fire.
def _p_tac_defender_count(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when a move loses material in an attacker-vs-defender
    count mismatch. Engine-endorsed (cp_loss ≥ 30 + best differs)."""
    if not facts.get("is_exchange_losing"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    if not (best and played != best):
        return None
    return {
        "principle_id": "TAC_DEFENDER_COUNT",
        "evidence": {
            "target_square": facts.get("target_square"),
            "moving_piece_type": facts.get("moving_piece_type"),
            "exchange_loss_cp": facts.get("exchange_loss_cp", 0),
            "attackers": facts.get("attacker_count", 0),
            "defenders": facts.get("defender_count", 0),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best],
    }


# ── Detector #12: DEF_MOST_ATTACKED ─────────────────────────────────
#
# Edge cases enumerated:
#   1. Fires when 2+ own pieces are attacked simultaneously AND the
#      played move addressed the WRONG one. Encoded as: pieces_now_
#      undefended has ≥2 entries with now_attacked=True, AND the
#      played move didn't address the highest-value one.
#   2. For v1, the "most attacked" definition is highest piece_value_cp.
#   3. cp_loss_strict (≥30): engine confirms suboptimal.
def _p_def_most_attacked(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when multiple own pieces are attacked but the played move
    addressed the wrong one (or no one)."""
    if (facts.get("cp_loss") or 0) < 30:
        return None
    pieces = facts.get("pieces_now_undefended") or []
    attacked = [p for p in pieces if p.get("now_attacked")]
    if len(attacked) < 2:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    if not (best and played != best):
        return None
    # Pick the most-attacked / highest-value piece.
    worst = max(
        attacked,
        key=lambda p: p.get("piece_value_cp", 0)
            if isinstance(p.get("piece_value_cp"), int) else 0
    )
    return {
        "principle_id": "DEF_MOST_ATTACKED",
        "evidence": {
            "most_attacked_square": worst.get("square"),
            "most_attacked_piece_type": worst.get("piece_type"),
            "attacked_pieces_count": len(attacked),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best],
    }


# ── Detector #13: END_PASSED_PAWN ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Fires in endgame or late middlegame when own player has a
#      passed pawn that wasn't pushed this move. Counterfactual match:
#      engine's #1 must be advancing the passed pawn.
#   2. A "passed pawn" is a pawn with no enemy pawn on its file or
#      adjacent files in front of it.
#   3. Side-on-move only (we only check the player who just moved).
#   4. cp_loss_strict (≥30) gate so we don't accuse correct moves of
#      "missing the push."
def _own_passed_pawns(board: chess.Board, color: chess.Color) -> List[int]:
    """Return squares of own passed pawns. Pure geometry helper."""
    out = []
    for sq in board.pieces(chess.PAWN, color):
        file_ = chess.square_file(sq)
        rank_ = chess.square_rank(sq)
        # Enemy pawns blocking: any enemy pawn on file or adjacent
        # files at a rank "ahead" of this pawn (depending on color).
        files_to_check = {file_, file_ - 1, file_ + 1} & set(range(8))
        if color == chess.WHITE:
            ranks_ahead = range(rank_ + 1, 8)
        else:
            ranks_ahead = range(0, rank_)
        blocked = False
        for f in files_to_check:
            for r in ranks_ahead:
                p = board.piece_at(chess.square(f, r))
                if p and p.piece_type == chess.PAWN and p.color != color:
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            out.append(sq)
    return out


def _p_end_passed_pawn(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when own player has a passed pawn AND engine's #1 is to
    push it AND the player played something else."""
    phase = facts.get("phase")
    if phase not in ("endgame", "middlegame"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best = _normalize_san(facts.get("best_move_san") or "")
    if not best:
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    passed = _own_passed_pawns(board_before, own_color)
    if not passed:
        return None
    # Aligned moves = legal pawn pushes of any passed pawn forward 1 square.
    aligned: List[str] = []
    for sq in passed:
        # Find legal moves whose from_square is this passed pawn.
        for move in board_before.legal_moves:
            if move.from_square == sq:
                aligned.append(_normalize_san(board_before.san(move)))
    # Best move must be one of the aligned passed-pawn pushes.
    if best not in aligned:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    if played in aligned:
        return None  # player DID push a passed pawn
    return {
        "principle_id": "END_PASSED_PAWN",
        "evidence": {
            "passed_pawn_squares": [chess.square_name(s) for s in passed],
            "engine_chose_push": best,
            "player_chose": played,
        },
        "state_key": _freeze_state_key({
            "principle_id":     "END_PASSED_PAWN",
            "phase":            phase or "endgame",
            "intent_type":      "promotion_push",
            "focal_squares":    tuple(sorted(chess.square_name(s) for s in passed)),
            "involved_piece":   "pawn",
            "best_move_family": "pawn_push",
        }),
        "engine_endorsement": "best",
        "aligned_moves_offered": aligned[:5],
    }


import re


def _move_target_from_san(san: str) -> Optional[str]:
    """Extract destination square from a SAN string like Re8+, Qxe7,
    Nf3. Strips +/# and promotion suffix. Returns 'e8' / 'e7' / 'f3'
    or None if no square found."""
    s = (san or "").rstrip("+#!?")
    m = re.search(r"([a-h][1-8])(?:=[QRBN])?$", s)
    return m.group(1) if m else None


# ── Detector #14: OP_LOOSE_KING_PAWNS ───────────────────────────────
#
# Edge cases enumerated:
#   1. Only fires in opening, on pawn moves, before castling.
#   2. Target on f/g/h file (kingside) or a/b/c file (queenside) —
#      both apply (the player might have been intending q-side castle).
#      Simpler: only check kingside-pawn loosening since 90%+ of 600-
#      1400 castles are kingside.
#   3. King still on starting square AND kingside castling rights held.
#   4. cp_loss_strict (≥30).
def _p_op_loose_king_pawns(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when pawn pushes to f/g/h file before castling, with
    king on starting square and kingside castling rights held."""
    if facts.get("phase") != "opening":
        return None
    if facts.get("moving_piece_type") != "pawn":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    target = facts.get("target_square") or ""
    if not target or target[0] not in ("f", "g", "h"):
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    king_start = chess.E1 if own_color == chess.WHITE else chess.E8
    if board_before.king(own_color) != king_start:
        return None
    if not board_before.has_kingside_castling_rights(own_color):
        return None
    aligned = _developing_minor_moves(board_before, own_color)
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "OP_LOOSE_KING_PAWNS",
        "evidence": {
            "loosened_pawn_to": target,
            "king_still_on": chess.square_name(king_start),
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #15: OP_BISHOP_BLOCKED ─────────────────────────────────
#
# Edge cases enumerated:
#   1. Only fires on pawn moves in opening/early middlegame.
#   2. The pawn lands on a diagonal of own bishop WITH a clear path
#      from bishop to target_sq in board_before (i.e., the bishop
#      ACTUALLY sees the target square; otherwise the move isn't
#      "blocking" anything).
#   3. cp_loss_strict (≥30).
def _bishop_sees_square(board: chess.Board, bsq: int, target_sq: int) -> bool:
    """True iff bishop on bsq has clear diagonal line of sight to
    target_sq in `board` (nothing blocking)."""
    bf, br = chess.square_file(bsq), chess.square_rank(bsq)
    tf, tr = chess.square_file(target_sq), chess.square_rank(target_sq)
    if abs(bf - tf) != abs(br - tr) or bf == tf:
        return False
    df = 1 if tf > bf else -1
    dr = 1 if tr > br else -1
    f, r = bf + df, br + dr
    while (f, r) != (tf, tr):
        if board.piece_at(chess.square(f, r)) is not None:
            return False
        f += df
        r += dr
    return True


def _p_op_bishop_blocked(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when a pawn move lands on a square that an own bishop
    currently sees on the diagonal — locking the bishop in."""
    if facts.get("phase") not in ("opening", "middlegame"):
        return None
    if facts.get("moving_piece_type") != "pawn":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    target_name = facts.get("target_square")
    if not target_name:
        return None
    target_sq = chess.parse_square(target_name)
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    blocked_bishop = None
    for bsq in board_before.pieces(chess.BISHOP, own_color):
        if _bishop_sees_square(board_before, bsq, target_sq):
            blocked_bishop = bsq
            break
    if blocked_bishop is None:
        return None
    # Aligned: any non-blocking pawn move
    aligned: List[str] = []
    bishops = list(board_before.pieces(chess.BISHOP, own_color))
    for move in board_before.legal_moves:
        piece = board_before.piece_at(move.from_square)
        if not piece or piece.color != own_color or piece.piece_type != chess.PAWN:
            continue
        if any(_bishop_sees_square(board_before, bsq, move.to_square) for bsq in bishops):
            continue
        aligned.append(_normalize_san(board_before.san(move)))
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "OP_BISHOP_BLOCKED",
        "evidence": {
            "bishop_square": chess.square_name(blocked_bishop),
            "blocking_pawn_to": target_name,
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #16: OP_FINISH_DEVELOPMENT ─────────────────────────────
#
# Edge cases enumerated:
#   1. Played move creates a threat (threats_created non-empty) — the
#      "attacking move" trigger.
#   2. Own side has ≥2 undeveloped minor pieces (knights / bishops on
#      starting squares).
#   3. cp_loss_strict (≥30) — engine confirms the attack is premature.
def _p_op_finish_development(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when player attacks (creates a threat OR makes an early
    queen sortie) with 2+ minor pieces still on starting squares.

    Trigger broadening: threats_created uses SEE > 0, which misses
    Scholar's-Mate-style attacks (queen aims at f7 but loses material
    in SEE because king defends). So we also accept queen_sortie_
    evidence as an "attacking signal" — that catches Qh5/Qf3 attempts
    by 600–1200 players regardless of SEE.
    """
    if facts.get("phase") not in ("opening", "middlegame"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    threats = facts.get("threats_created") or []
    has_threat_attack = bool(threats)
    has_queen_sortie = bool(facts.get("queen_sortie_evidence"))
    if not (has_threat_attack or has_queen_sortie):
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    # The queen_sortie trigger is meant to catch FORWARD aggression
    # (Qh5/Qf3-style attempts that aim at f7/f2). A queen retreating or
    # making a second move after already leaving home is the OPPOSITE —
    # there's no "premature attack" to teach against. Without this guard
    # FD fires on Qd5→Qd8 retreats with the off-topic cue "this position
    # rewards attacking, but most positions don't" on what's actually a
    # tempo loss / same-piece-twice case. Require the queen to be LEAVING
    # her starting square for queen_sortie to count as the attack signal.
    if has_queen_sortie and not has_threat_attack:
        sortie = facts.get("queen_sortie_evidence") or {}
        home_square = "d1" if own_color == chess.WHITE else "d8"
        if sortie.get("from_square") != home_square:
            return None
    if own_color == chess.WHITE:
        starting_n = {chess.B1, chess.G1}
        starting_b = {chess.C1, chess.F1}
    else:
        starting_n = {chess.B8, chess.G8}
        starting_b = {chess.C8, chess.F8}
    undeveloped = 0
    for sq in board_before.pieces(chess.KNIGHT, own_color):
        if sq in starting_n:
            undeveloped += 1
    for sq in board_before.pieces(chess.BISHOP, own_color):
        if sq in starting_b:
            undeveloped += 1
    if undeveloped < 2:
        return None
    aligned = _developing_minor_moves(board_before, own_color)
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    premature_target = threats[0].get("target_square") if threats else None
    trigger_kind = "threat_created" if has_threat_attack else "queen_sortie"
    return {
        "principle_id": "OP_FINISH_DEVELOPMENT",
        "evidence": {
            "undeveloped_minor_count": undeveloped,
            "premature_attack_target": premature_target,
            "trigger_kind": trigger_kind,
        },
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #17: TAC_CHECKS_CAPTURES_THREATS ───────────────────────
#
# Edge cases enumerated:
#   1. Engine's #1 (best_move_san) is a check (+/# suffix) OR capture
#      (x in SAN). "Threat" detection is harder without simulating the
#      best move; deferred for v1.
#   2. Played move is NOT a check and NOT a capture (player chose
#      quiet over forcing).
#   3. cp_loss_strict (≥30).
def _p_tac_checks_captures_threats(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 is a forcing move (check or capture)
    and the player played a quiet move instead."""
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    played = _normalize_san(facts.get("played_san") or "")
    if not best_raw:
        return None
    best_is_check = best_raw.endswith("+") or best_raw.endswith("#")
    best_is_capture = "x" in best_raw
    if not (best_is_check or best_is_capture):
        return None
    played_raw = facts.get("played_san") or ""
    played_is_check = played_raw.endswith("+") or played_raw.endswith("#")
    played_is_capture = bool(facts.get("is_capture"))
    if played_is_check or played_is_capture:
        return None
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "TAC_CHECKS_CAPTURES_THREATS",
        "evidence": {
            "best_move": best_raw,
            "best_kind": "check" if best_is_check else "capture",
            "played": played,
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #18: TAC_BACK_RANK ─────────────────────────────────────
#
# Edge cases enumerated:
#   1. Engine's #1 ends with '#' (delivers mate).
#   2. Target square of the mating move is on enemy's back rank
#      (rank 8 for white attackers, rank 1 for black attackers).
#   3. Played move ≠ the mating move.
def _p_tac_back_rank(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the engine's #1 is a back-rank checkmate and player
    played something else.

    Bug fix 2026-05-12: per-fire audit caught this firing on positions
    where the enemy king was NOT on its back rank — best move ended in
    '#' with target on rank 8, but the king was on rank 2/6/7. That's
    not a back-rank mate. Now also require enemy_king on its back rank
    in fen_before.
    """
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    if not best_raw.endswith("#"):
        return None
    target = _move_target_from_san(best_raw)
    if not target:
        return None
    own_color_str = facts.get("moving_piece_color")
    enemy_back_rank = "8" if own_color_str == "white" else "1"
    if target[1] != enemy_back_rank:
        return None
    # Enemy king must currently sit on its back rank for this to be a
    # true back-rank mate pattern. Without this gate the detector fires
    # on accidental mate-on-rank-8 cases (e.g. mate after king is
    # forced to retreat) which read pedagogically as confusing.
    enemy_color = chess.BLACK if own_color_str == "white" else chess.WHITE
    enemy_king_sq = board_before.king(enemy_color)
    if enemy_king_sq is None:
        return None
    expected_king_rank = 7 if enemy_color == chess.BLACK else 0
    if chess.square_rank(enemy_king_sq) != expected_king_rank:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "TAC_BACK_RANK",
        "evidence": {
            "mating_move": best_raw,
            "mating_square": target,
            "enemy_king_square": chess.square_name(enemy_king_sq),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #19: TAC_CHANGED_AFTER_MOVE ────────────────────────────
#
# Edge cases enumerated:
#   1. Broad fallback: fires when cp_loss ≥ 100 and the player's own
#      move created a consequence (exchange-losing OR pieces_now_
#      undefended). Catches "missed what my move does."
#   2. Priority 18 means specific tactical principles (hanging,
#      defender_count) win when they also fire.
#   3. Engine endorsement: best_move ≠ played (true by definition for
#      high cp_loss).
def _p_tac_changed_after_move(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Catch-all: fires when the played move had unseen consequences —
    high cp_loss + own side's exposure changed."""
    if (facts.get("cp_loss") or 0) < 100:
        return None
    has_loss = facts.get("is_exchange_losing")
    undef = facts.get("pieces_now_undefended") or []
    has_undef = bool(undef)
    if not (has_loss or has_undef):
        return None
    best = _normalize_san(facts.get("best_move_san") or "")
    played = _normalize_san(facts.get("played_san") or "")
    if not (best and best != played):
        return None
    return {
        "principle_id": "TAC_CHANGED_AFTER_MOVE",
        "evidence": {
            "played": played,
            "cp_loss": facts.get("cp_loss"),
            "is_exchange_losing": bool(has_loss),
            "pieces_lost_defender_count": len(undef),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best],
    }


# ── Detector #20: DEF_WALK_KING ─────────────────────────────────────
#
# Edge cases enumerated:
#   1. Own king has lost castling rights (can't castle anymore).
#   2. Engine's #1 move is a king move (SAN starts with 'K').
#   3. Played move was NOT a king move.
#   4. cp_loss_strict (≥30).
def _p_def_walk_king(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine wants a king walk to safety but player did
    something else, with no castling rights remaining."""
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    if not best_raw.startswith("K"):
        return None
    # Exclude castling — that's its own principle
    if best_raw in ("O-O", "O-O-O", "0-0", "0-0-0"):
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    if (board_before.has_kingside_castling_rights(own_color)
            or board_before.has_queenside_castling_rights(own_color)):
        return None
    if facts.get("moving_piece_type") == "king":
        return None  # player WAS walking the king (just not the engine's choice)
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "DEF_WALK_KING",
        "evidence": {
            "engine_king_move": best_raw,
            "played": played,
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #21: MID_ROOK_OPEN_FILE ────────────────────────────────
#
# Edge cases enumerated:
#   1. Engine's #1 is a rook move (SAN starts with 'R').
#   2. The destination file is open (no own pawns on it) OR half-open
#      (own pawns on it but no enemy pawns).
#   3. Player didn't play that move.
#   4. cp_loss_strict (≥30).
def _file_is_open_for(board: chess.Board, file_idx: int, own_color: chess.Color) -> bool:
    """True if there are no OWN pawns on this file. Half-open from
    own perspective. (For 'fully open' both sides need to be checked;
    half-open is fine for rook-belongs-here teaching.)"""
    for rank in range(8):
        p = board.piece_at(chess.square(file_idx, rank))
        if p and p.piece_type == chess.PAWN and p.color == own_color:
            return False
    return True


def _p_mid_rook_open_file(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 is a rook move to a half-open or open
    file AND the player played something else."""
    if facts.get("phase") not in ("middlegame", "endgame"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    if not best_raw.startswith("R"):
        return None
    target = _move_target_from_san(best_raw)
    if not target:
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    target_sq = chess.parse_square(target)
    file_idx = chess.square_file(target_sq)
    if not _file_is_open_for(board_before, file_idx, own_color):
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "MID_ROOK_OPEN_FILE",
        "evidence": {
            "rook_target_file": target[0],
            "rook_target_square": target,
            "engine_chose": best_raw,
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #22: MID_PAWN_BREAK ────────────────────────────────────
#
# Edge cases enumerated:
#   1. Middlegame phase only.
#   2. Engine's #1 is a pawn move (no piece-letter prefix, just file/
#      square like "e5" or "exd5").
#   3. Played wasn't that pawn move.
#   4. cp_loss_strict (≥30).
def _p_mid_pawn_break(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 is a pawn move in middlegame and player
    played something else. Catches missed pawn-break attacks.

    cp_loss threshold raised 30 → 80 after audit pass #1: at 30, this
    fired on quiet positions where the engine's pawn-move preference
    is small (e.g. cpl=62 sample). 80+ tightens to genuinely-missed
    pawn-break opportunities where the engine sees a meaningful
    advantage in the break.
    """
    if facts.get("phase") != "middlegame":
        return None
    if (facts.get("cp_loss") or 0) < 80:
        return None
    best_raw = facts.get("best_move_san") or ""
    if not best_raw:
        return None
    # Pawn moves in SAN start with a file letter (a-h) — no piece prefix
    if not (best_raw and best_raw[0] in "abcdefgh"):
        return None
    # Castling is "O-O" — already excluded.
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    target = _move_target_from_san(best_raw)
    return {
        "principle_id": "MID_PAWN_BREAK",
        "evidence": {
            "pawn_break_move": best_raw,
            "pawn_break_target": target,
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ────────────────────────────────────────────────────────────────────
# Shared endgame helpers (added 2026-05-16, Mohit signoff)
# ────────────────────────────────────────────────────────────────────


def _is_clean_king_and_pawn_endgame(board: chess.Board) -> bool:
    """Pedagogical purity gate for Rule of the Square.

    Returns True only for positions where Rule-of-the-Square is the
    actual relevant teaching: no queens or rooks for either side, and
    at most one minor piece (knight or bishop) per side. With heavier
    pieces present, OTHER dynamics dominate — rook activity, tactical
    threats — and Rule of the Square fires correctly by geometry but
    teaches the wrong lesson.

    Audit on 2026-05-17 (Mohit verification of 135 fires across the
    corpus): ~75% of fires were positions with rooks/queens where
    Rule of the Square was technically correct but pedagogically
    irrelevant. This gate eliminates those.
    """
    for color in (chess.WHITE, chess.BLACK):
        if board.pieces(chess.QUEEN, color):
            return False
        if board.pieces(chess.ROOK, color):
            return False
        minors = (
            len(board.pieces(chess.KNIGHT, color))
            + len(board.pieces(chess.BISHOP, color))
        )
        if minors > 1:
            return False
    return True


def _p_end_rule_of_square(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Caption adapter over the canonical legal pawn-race truth."""
    if facts.get("phase") != "endgame":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None

    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        side_white = facts.get("moving_piece_color") == "white"
        stm_eval = (
            eval_before_white_pov
            if side_white
            else -eval_before_white_pov
        )
        if stm_eval > 300:
            return None

    from services.concept_detectors.rule_of_the_square import (
        analyze_rule_of_square,
        detect_rule_of_the_square_application,
    )

    canonical = analyze_rule_of_square(board_before)
    if canonical is None or board_before.turn != canonical.defender_color:
        return None

    best_san = _normalize_san(facts.get("best_move_san") or "")
    played_san = _normalize_san(facts.get("played_san") or "")
    if not best_san or not played_san or best_san == played_san:
        return None
    try:
        best_move = board_before.parse_san(best_san)
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None

    us = board_before.turn
    best_piece = board_before.piece_at(best_move.from_square)
    if (
        best_piece is None
        or best_piece.color != us
        or best_piece.piece_type != chess.KING
    ):
        return None

    best_grade = detect_rule_of_the_square_application(
        board_before, best_move, us
    )
    played_grade = detect_rule_of_the_square_application(
        board_before, played_move, us
    )
    if best_grade != "applied" or played_grade != "missed":
        return None

    board_after_best = board_before.copy(stack=False)
    board_after_best.push(best_move)
    after_best = analyze_rule_of_square(board_after_best)
    best_captured_pawn = (
        board_before.is_capture(best_move)
        and best_move.to_square == canonical.pawn_square
    )
    if after_best is None and not best_captured_pawn:
        return None
    if after_best is not None and not after_best.catchable:
        return None

    evidence = canonical.evidence()
    evidence.update({
        "pawn_distance": canonical.pawn_pushes_to_promote,
        "king_square_played": chess.square_name(
            canonical.defending_king_square
        ),
        "king_distance_before": chess.square_distance(
            canonical.defending_king_square,
            canonical.promotion_square,
        ),
        "king_should_move_to": chess.square_name(best_move.to_square),
        "king_distance_after_best": chess.square_distance(
            best_move.to_square,
            canonical.promotion_square,
        ),
        "catchable_before": canonical.catchable,
        "catchable_after_best": (
            True if best_captured_pawn else after_best.catchable
        ),
        "played_san": facts.get("played_san") or "",
        "best_san": facts.get("best_move_san") or "",
    })
    return {
        "principle_id": "END_RULE_OF_SQUARE",
        "evidence": evidence,
        "state_key": _freeze_state_key({
            "principle_id": "END_RULE_OF_SQUARE",
            "phase": "endgame",
            "intent_type": "defensive_geometry",
            "focal_squares": (
                chess.square_name(canonical.pawn_square),
                chess.square_name(best_move.to_square),
            ),
            "involved_piece": "king",
            "best_move_family": "K_move",
        }),
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_san],
    }


def _kings_in_opposition(king1_sq: int, king2_sq: int) -> Optional[str]:
    """Returns "direct" / "distant" / "diagonal" if the two king squares
    sit in an opposition shape, else None.

    Does NOT check whose turn it is — that's the caller's job. The
    pattern is purely geometric.
    """
    f1, r1 = chess.square_file(king1_sq), chess.square_rank(king1_sq)
    f2, r2 = chess.square_file(king2_sq), chess.square_rank(king2_sq)
    df = abs(f1 - f2)
    dr = abs(r1 - r2)
    # Same file: rank diff 2 = direct; 4 or 6 = distant
    if df == 0 and dr in (2, 4, 6):
        return "direct" if dr == 2 else "distant"
    # Same rank: file diff 2 = direct; 4 or 6 = distant
    if dr == 0 and df in (2, 4, 6):
        return "direct" if df == 2 else "distant"
    # Same diagonal with 1 square between (Chebyshev 2)
    if df == dr == 2:
        return "diagonal"
    return None


# ── Detector #25: END_OPPOSITION ────────────────────────────────────
#
# Fires when:
#   1. Phase is endgame.
#   2. cp_loss >= 30 — engine confirms the move was suboptimal.
#   3. Clean K+P endgame (≤1 minor per side, no rooks/queens) —
#      pedagogical-purity gate inherited from END_RULE_OF_SQUARE.
#   4. STM eval <= +300cp — drop already-winning positions (Pass-4
#      style asymmetric filter; losing positions kept because the
#      Opposition concept is teachable even when the game is lost).
#   5. King_move_required (Mohit signoff 2026-05-16 locked refinement):
#      engine's best (best_move_san) MUST be a king move. Without this
#      gate, technically-true opposition fires on positions where
#      triangulation / breakthrough is the actual lesson.
#   6. After the engine's best king move, your king is in DIRECT
#      (or distant / diagonal) opposition with the enemy king.
#   7. You did NOT ALREADY have opposition before the played move
#      (kings on opposition shape with YOU to move — that's the
#      "you've lost it" lesson, different from "missed taking it").
#   8. The played move did NOT also take opposition.
#
# Edge cases enumerated:
#   A. Multiple king moves could create opposition — fire on engine's #1.
#   B. Kings already in opposition with us to move — DON'T fire.
#   C. Diagonal opposition included for completeness; rare but valid.
#   D. SAN parse failures — return None safely.
#   E. Eval data missing — fall back to geometric only.
def _p_end_opposition(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """The Opposition — your king should have moved to face the enemy
    king on the same line, leaving them to move with no good square."""
    if facts.get("phase") != "endgame":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None

    # Pedagogical purity gate #1 — clean K+P endgame.
    if not _is_clean_king_and_pawn_endgame(board_before):
        return None

    # Pedagogical purity gate #2 — eval bracket. Asymmetric: keep
    # losing positions (named-pattern teaching value > position saving),
    # drop already-winning (caption would frame a non-issue as a miss).
    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        side_white = facts.get("moving_piece_color") == "white"
        stm_eval = eval_before_white_pov if side_white else -eval_before_white_pov
        if stm_eval > 300:
            return None

    best_san = _normalize_san(facts.get("best_move_san") or "")
    played_san = _normalize_san(facts.get("played_san") or "")
    if not best_san:
        return None

    us = board_before.turn
    them = not us

    # king_move_required gate — engine's #1 must be a king move.
    try:
        best_move = board_before.parse_san(best_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None
    best_piece = board_before.piece_at(best_move.from_square)
    if not best_piece or best_piece.piece_type != chess.KING or best_piece.color != us:
        return None
    best_king_dest = best_move.to_square

    our_king_sq = board_before.king(us)
    their_king_sq = board_before.king(them)
    if our_king_sq is None or their_king_sq is None:
        return None

    # Case B: we ALREADY have opposition with us to move — we've actually
    # lost it (the side NOT to move has opposition). Different lesson;
    # don't fire here.
    if _kings_in_opposition(our_king_sq, their_king_sq):
        return None

    # After best king move, do we create opposition?
    opposition_kind = _kings_in_opposition(best_king_dest, their_king_sq)
    if not opposition_kind:
        return None

    # Case E: played move ALSO takes opposition (a different king move
    # that happens to land on a valid opposition square) — no fire.
    try:
        played_move = board_before.parse_san(played_san)
        played_piece = board_before.piece_at(played_move.from_square)
        if (played_piece
                and played_piece.piece_type == chess.KING
                and played_piece.color == us
                and _kings_in_opposition(played_move.to_square, their_king_sq)):
            return None
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        pass

    return {
        "principle_id": "END_OPPOSITION",
        "evidence": {
            "your_king_square":          chess.square_name(our_king_sq),
            "their_king_square":         chess.square_name(their_king_sq),
            "your_king_should_move_to":  chess.square_name(best_king_dest),
            "opposition_kind":           opposition_kind,
            "played_san":                facts.get("played_san") or "",
            "best_san":                  facts.get("best_move_san") or "",
        },
        "state_key": _freeze_state_key({
            "principle_id":     "END_OPPOSITION",
            "phase":            "endgame",
            "intent_type":      "positional_squeeze",
            "focal_squares":    (chess.square_name(best_king_dest), chess.square_name(their_king_sq)),
            "opposition_kind":  opposition_kind,
            "involved_piece":   "king",
            "best_move_family": "K_move",
        }),
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_san],
    }


# ── Helper: squares behind a passed pawn ────────────────────────────
#
# Tarrasch's rule: rook belongs BEHIND the passed pawn — defined
# relative to the pawn's origin side (its own back rank). So for a
# WHITE passer, "behind" = lower ranks (toward rank 1). For a BLACK
# passer, "behind" = higher ranks (toward rank 8).
def _passed_pawn_behind_squares(pawn_sq: int, pawn_color: chess.Color) -> List[int]:
    """Return all squares on the same file as pawn_sq that are 'behind'
    it from the pawn's origin perspective (excluding the pawn square
    itself).
    """
    pf = chess.square_file(pawn_sq)
    pr = chess.square_rank(pawn_sq)
    behind: List[int] = []
    if pawn_color == chess.WHITE:
        for r in range(pr - 1, -1, -1):
            behind.append(chess.square(pf, r))
    else:
        for r in range(pr + 1, 8):
            behind.append(chess.square(pf, r))
    return behind


# ── Detector #26: END_ROOK_BEHIND_PASSER ────────────────────────────
#
# Tarrasch's rule — rook belongs behind the passed pawn, yours or
# theirs. Mohit signoff 2026-05-16 locked refinement: single-passer-
# only in v1. Multi-passer positions deferred to v2 once the simple
# case audit is clean.
#
# Fires when:
#   1. Phase in (middlegame, endgame).
#   2. cp_loss >= 30 — engine confirms the move was suboptimal.
#   3. Exactly ONE passed pawn on the board (either color).
#   4. Eval bracket: drop STM > +300cp (already-winning case where
#      Tarrasch isn't the load-bearing lesson). Losing positions
#      KEPT per Mohit's directive ("fire with lost positions too").
#   5. Engine's best (best_move_san) is a rook move by OUR rook.
#   6. That rook move lands on the same file as the passed pawn,
#      on the side BEHIND the pawn (the pawn-color's origin side).
#   7. Played move was NOT this rook lift.
#
# Edge cases enumerated:
#   A. Multiple passers — skip (single-passer-only v1).
#   B. Best move is not a rook move — skip.
#   C. Rook lands on the pawn's file but in front (between pawn
#      and promotion) — skip (that's "rook in front", not Tarrasch).
#   D. SAN parse failures — return None.
#   E. Eval data missing — fall back to geometric only.
#   F. Our own rook is already behind the passer — engine's best
#      is something else; principle doesn't fire (correctly).
def _rook_reachable_count(board: chess.Board, rook_sq: int, color: chess.Color) -> int:
    """How many squares the rook on rook_sq could legally reach if it were
    `color`'s turn (turn-independent mobility — see the kiandraa10 trap)."""
    b = board.copy()
    b.turn = color
    return sum(1 for m in b.legal_moves if m.from_square == rook_sq)


def _p_end_pawn_traps_own_rook(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """A pawn push that TRAPS your own rook — the rook's mobility collapses because
    the just-pushed pawn now blocks its rank or file. The CAUSE (rook went dead),
    not the downstream effect ("pawn got captured"). Board-derived, any phase.
    Diagnosed by Mohit on the kiandraa10 endgame: 52.g7 entombed Rh7 (8 squares → 1),
    so the win evaporated. 2026-06-22."""
    if (facts.get("cp_loss") or 0) < 150:        # only when it actually cost something
        return None
    best_san = _normalize_san(facts.get("best_move_san") or "")
    played_san = _normalize_san(facts.get("played_san") or "")
    if not best_san or not played_san or best_san == played_san:
        return None
    try:
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None
    pc = board_before.piece_at(played_move.from_square)
    if not pc or pc.piece_type != chess.PAWN or board_before.is_capture(played_move):
        return None  # must be a pawn PUSH
    us = board_before.turn
    pushed_to = played_move.to_square
    push_rank, push_file = chess.square_rank(pushed_to), chess.square_file(pushed_to)
    post = board_before.copy()
    post.push(played_move)

    # Find a friendly rook the pushed pawn entombs: it sits on the rook's rank or
    # file, and the rook's mobility collapses from active (>=5) to trapped (<=2).
    trap = None
    for rook_sq in board_before.pieces(chess.ROOK, us):
        on_line = (chess.square_rank(rook_sq) == push_rank
                   or chess.square_file(rook_sq) == push_file)
        if not on_line:
            continue
        before_n = _rook_reachable_count(board_before, rook_sq, us)
        after_n = _rook_reachable_count(post, rook_sq, us)
        if before_n >= 5 and after_n <= 2 and (before_n - after_n) >= 4:
            trap = (rook_sq, before_n, after_n)
            break
    if trap is None:
        return None
    rook_sq, before_n, after_n = trap

    # Opponent's punishing plan: name their best reply, and (when the engine line
    # shows it) that it goes on to win the now-undefendable pushed pawn. Verified
    # by tracking the pushed pawn through the PV.
    pv = facts.get("pv_after_played") or []
    opp_reply = _normalize_san(pv[0]) if pv else ""
    opp_is_king = False
    if opp_reply:
        try:
            _om = post.parse_san(opp_reply)
            _op = post.piece_at(_om.from_square)
            opp_is_king = bool(_op and _op.piece_type == chess.KING)
        except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
            opp_reply = ""
    track_sq = pushed_to
    pawn_lost = False
    b2 = post.copy()
    for san in pv[:12]:
        try:
            mv = b2.parse_san(_normalize_san(san))
        except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
            break
        if b2.turn != us and b2.is_capture(mv) and mv.to_square == track_sq:
            pawn_lost = True
            break
        if b2.turn == us and mv.from_square == track_sq:
            track_sq = mv.to_square
        b2.push(mv)

    rook_name = chess.square_name(rook_sq)
    pushed_name = chess.square_name(pushed_to)
    only_sq = None
    if after_n == 1:
        b3 = post.copy(); b3.turn = us
        only_sq = next((chess.square_name(m.to_square) for m in b3.legal_moves
                        if m.from_square == rook_sq), None)

    # The R12 shell already states "{played} is a blunder. {best} was better." —
    # so the why_text must NOT restate the move or the recommendation (no dupes).
    why = f"It traps your own rook on {rook_name}"
    why += f" — the rook can only reach {only_sq} now." if only_sq else f" — its mobility drops from {before_n} squares to {after_n}."
    if opp_reply and pawn_lost:
        mover = "their king steps up" if opp_is_king else "they reply"
        why += f" With the rook stuck, {mover} ({opp_reply}) to win the {pushed_name} pawn it can no longer hold."
    why += " Keep your rook active."

    return {
        "principle_id": "PAWN_PUSH_TRAPS_OWN_ROOK",
        "engine_endorsement": "best",
        "evidence": {
            "trapped_rook_square": rook_name,
            "rook_squares_before": before_n,
            "rook_squares_after": after_n,
            "pushed_pawn_square": pushed_name,
            "opp_reply_san": pv[0] if pv else "",
            "pawn_lost_in_line": pawn_lost,
            "played_san": facts.get("played_san") or "",
            "best_san": facts.get("best_move_san") or "",
            "why_text": why,
        },
        "state_key": _freeze_state_key({
            "principle_id": "PAWN_PUSH_TRAPS_OWN_ROOK",
            "rook_sq": rook_name,
            "pushed_to": pushed_name,
        }),
    }


def _p_end_rook_behind_passer(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Tarrasch's rule — your rook should have gone to the square
    behind the single passed pawn on the board."""
    if facts.get("phase") not in ("endgame", "middlegame"):
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None

    # Eval bracket — asymmetric, drop already-winning per Mohit 2026-05-17.
    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        side_white = facts.get("moving_piece_color") == "white"
        stm_eval = eval_before_white_pov if side_white else -eval_before_white_pov
        if stm_eval > 300:
            return None

    # Single-passer-only restriction.
    all_passers: List[Tuple[int, chess.Color]] = []
    for color in (chess.WHITE, chess.BLACK):
        for sq in _own_passed_pawns(board_before, color):
            all_passers.append((sq, color))
    if len(all_passers) != 1:
        return None
    passer_sq, passer_color = all_passers[0]

    best_san = _normalize_san(facts.get("best_move_san") or "")
    played_san = _normalize_san(facts.get("played_san") or "")
    if not best_san or best_san == played_san:
        return None

    us = board_before.turn

    # Engine's best must be a rook move by us.
    try:
        best_move = board_before.parse_san(best_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None
    best_piece = board_before.piece_at(best_move.from_square)
    if not best_piece or best_piece.piece_type != chess.ROOK or best_piece.color != us:
        return None

    # Target must be on the passer's file AND on the "behind" side
    # of the pawn (passer's origin-side).
    behind_squares = _passed_pawn_behind_squares(passer_sq, passer_color)
    if best_move.to_square not in behind_squares:
        return None

    is_own_passer = (passer_color == us)
    perspective = "supporting" if is_own_passer else "restraining"

    return {
        "principle_id": "END_ROOK_BEHIND_PASSER",
        "evidence": {
            "passer_square":       chess.square_name(passer_sq),
            "passer_color":        "white" if passer_color == chess.WHITE else "black",
            "rook_square_played":  chess.square_name(best_move.from_square),
            "rook_target_square":  chess.square_name(best_move.to_square),
            "perspective":         perspective,
            "played_san":          facts.get("played_san") or "",
            "best_san":            facts.get("best_move_san") or "",
        },
        "state_key": _freeze_state_key({
            "principle_id":     "END_ROOK_BEHIND_PASSER",
            "phase":            facts.get("phase") or "endgame",
            "intent_type":      "tarrasch_rule",
            "focal_squares":    (chess.square_name(passer_sq), chess.square_name(best_move.to_square)),
            "perspective":      perspective,
            "involved_piece":   "rook",
            "best_move_family": "rook_move",
        }),
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_san],
    }


# ── Helper: count pawns on a file for a color ──────────────────────
def _pawns_on_file(board: chess.Board, file_: int, color: chess.Color) -> int:
    """Count own pawns on a given file. Used by OP_BISHOP_TRADE_DOUBLES_PAWN
    to detect when a recapture would create (or extend) doubled pawns."""
    count = 0
    for rank in range(8):
        sq = chess.square(file_, rank)
        p = board.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == color:
            count += 1
    return count


# ── Detector #27: OP_BISHOP_TRADE_DOUBLES_PAWN ──────────────────────
#
# The classic English / Nimzo-Indian / Vienna structural concession:
# Bxc3 → bxc3 (or Bxf6 → gxf6), where the player trades their bishop
# for an enemy minor piece and forces the opponent to recapture with
# a pawn that creates doubled pawns on that file. Long-term target.
#
# Fires when:
#   1. Phase in (opening, middlegame). Cross-opening pattern, but the
#      teaching value is highest while pawn structures are still fluid.
#   2. Played move is a CAPTURE.
#   3. Mover's piece is a BISHOP.
#   4. Captured piece is an enemy MINOR (knight or bishop).
#   5. After the played move, the opponent's CHEAPEST legal recapture
#      onto the capture square is a PAWN (i.e., the SEE recapture sequence
#      starts with a pawn). This is the "forced recapture" definition.
#   6. The pawn that would recapture comes from a DIFFERENT file than
#      the capture square (so the recapture is a diagonal pawn move
#      that CREATES doubled pawns on the capture-square's file).
#   7. After the hypothetical recapture, the capture-square's file
#      contains ≥2 enemy pawns (the doubled-pawn outcome).
#   8. The capture square is not already on a file with multiple enemy
#      pawns BEFORE the trade — otherwise we'd fire on a position that
#      was already doubled (no teaching value).
#
# Edge cases enumerated:
#   A. Captured piece is the queen / rook — different lesson (material gain).
#      Filter to minor pieces only.
#   B. The recapture COULD be a non-pawn (e.g., bishop trade where a
#      queen, rook, or other minor can also recapture). We only fire
#      when the pawn IS the engine's preferred recapture or the only
#      legal recapture. For v1: fire when ALL pawn-recaptures from
#      adjacent files would double, AND there are no non-pawn
#      recaptures of equal or higher value (pawn recapture would be
#      the rational choice).
#   C. The bishop is captured back by something other than a pawn
#      (e.g., the opponent has a rook on c-file ready to recapture
#      with Rxc3). Don't fire — the pawn isn't forced.
#   D. The trade is SEE-losing for the mover (e.g., they sacrificed
#      a bishop for a pawn). Don't fire — different lesson.
#   E. Eval bracket — drop already-winning positions per existing
#      pedagogical-purity pattern.
#   F. SAN parse failures — return None.
#   G. Same-file pawn recapture (rare, possible with en passant
#      mechanics?) — would NOT double pawns, don't fire.
def _p_op_bishop_trade_doubles_pawn(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the player's bishop takes an enemy minor on a square
    whose forced pawn recapture doubles the opponent's pawns on that
    file. The Bxc3 / Bxf6 structural-concession pattern."""
    if facts.get("phase") not in ("opening", "middlegame"):
        return None

    # Played move must be a capture by a bishop.
    if not facts.get("is_capture"):
        return None
    if facts.get("moving_piece_type") != "bishop":
        return None

    # Captured piece must be a minor (knight or bishop).
    captured = facts.get("captured_piece_type")
    if captured not in ("knight", "bishop"):
        return None

    played_san = _normalize_san(facts.get("played_san") or "")
    if not played_san:
        return None

    # Eval bracket — drop already-winning per existing pattern.
    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        side_white = facts.get("moving_piece_color") == "white"
        stm_eval = eval_before_white_pov if side_white else -eval_before_white_pov
        if stm_eval > 300:
            return None

    try:
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None

    target_sq = played_move.to_square
    from_sq = played_move.from_square
    us = board_before.turn
    them = not us
    target_file = chess.square_file(target_sq)

    # Edge case D — the trade must not be SEE-losing (i.e., bishop for
    # less than equivalent material). If the bishop is captured back
    # cleanly with material loss, that's a different lesson.
    played_see = _see_for_played_move(board_before, played_move)
    if played_see is not None and played_see < -50:
        # Bishop-for-pawn-style sacrifice — different lesson.
        return None

    # Edge case H — opponent's pawns on target_file BEFORE the trade
    # must NOT already include multiple pawns. Otherwise we'd fire on
    # an already-doubled file, removing the "you CREATED doubling"
    # teaching. Note we count BEFORE the move because the captured
    # piece on target_sq is a knight/bishop, not a pawn — but we still
    # want to compare apples-to-apples.
    enemy_pawns_on_target_file_before = _pawns_on_file(board_before, target_file, them)
    if enemy_pawns_on_target_file_before >= 2:
        return None

    # Now simulate the played move on a copy of the board and look at
    # what the OPPONENT's cheapest legal recapture onto target_sq is.
    board_after = board_before.copy()
    board_after.push(played_move)

    # Enumerate opponent's legal recaptures onto target_sq.
    pawn_recapturers: List[int] = []
    non_pawn_recapturers: List[int] = []
    for move in board_after.legal_moves:
        if move.to_square != target_sq:
            continue
        if not board_after.is_capture(move):
            continue
        piece = board_after.piece_at(move.from_square)
        if not piece or piece.color != them:
            continue
        if piece.piece_type == chess.PAWN:
            pawn_recapturers.append(move.from_square)
        else:
            non_pawn_recapturers.append(move.from_square)

    # Edge case C — must have at least one pawn recapture available.
    if not pawn_recapturers:
        return None

    # Edge case B — if a NON-pawn recapture is available AND its piece
    # value is comparable to or cheaper than a pawn (impossible since
    # pawn is the cheapest piece), pawn is preferred. But if a non-pawn
    # is also legal, we need a tie-breaker. For v1: still fire (because
    # in practice the engine still often chooses bxc3 to keep pieces
    # active, AND the doubled-pawn LESSON is the same). However, if
    # the engine's BEST move (what opponent would actually play) is a
    # non-pawn recapture, the doubled-pawn structure never materialises
    # in the played game — drop those cases.
    #
    # Simpler v1 gate: fire when the pawn recapture is from a
    # DIFFERENT FILE than the target (so it would create doubled
    # pawns). If multiple pawn recapturers exist, pick the one from
    # an adjacent file (the one that creates doubling).
    doubling_recapturers: List[int] = []
    for pawn_sq in pawn_recapturers:
        if chess.square_file(pawn_sq) != target_file:
            doubling_recapturers.append(pawn_sq)

    # Edge case G — same-file pawn recapture would NOT double pawns.
    # If only same-file recaptures exist, skip.
    if not doubling_recapturers:
        return None

    # Verify the post-recapture state would have ≥2 enemy pawns on
    # target_file. Simulate one of the doubling recaptures.
    sample_pawn_sq = doubling_recapturers[0]
    board_check = board_after.copy()
    # Find the matching legal move and push it.
    sim_move = None
    for move in board_check.legal_moves:
        if move.from_square == sample_pawn_sq and move.to_square == target_sq:
            sim_move = move
            break
    if sim_move is None:
        return None
    board_check.push(sim_move)
    enemy_pawns_after = _pawns_on_file(board_check, target_file, them)
    if enemy_pawns_after < 2:
        return None

    # Compute engine endorsement — was this trade engine-preferred?
    best_san_raw = _normalize_san(facts.get("best_move_san") or "")
    if best_san_raw and best_san_raw == played_san:
        endorsement = "best"
    else:
        # Even if not engine-best, the structural lesson still fires
        # (educationally — "here's what this trade DOES to their
        # pawns"). Use top_n bucket so cue_top_n voice runs.
        endorsement = "top_n"

    recapture_file_letter = chess.FILE_NAMES[target_file]

    return {
        "principle_id": "OP_BISHOP_TRADE_DOUBLES_PAWN",
        "evidence": {
            "bishop_from_square":   chess.square_name(from_sq),
            "capture_square":       chess.square_name(target_sq),
            "captured_piece_type":  captured,
            "recapture_pawn_from":  chess.square_name(sample_pawn_sq),
            "doubled_pawn_file":    recapture_file_letter,
            "enemy_pawns_after_on_file": enemy_pawns_after,
            "perspective":          "creating" if facts.get("mover_is_user") else "conceding",
            "played_san":           facts.get("played_san") or "",
            "best_san":             facts.get("best_move_san") or "",
        },
        "state_key": _freeze_state_key({
            "principle_id":     "OP_BISHOP_TRADE_DOUBLES_PAWN",
            "phase":            facts.get("phase") or "opening",
            "intent_type":      "structural_concession",
            "focal_squares":    (chess.square_name(target_sq), recapture_file_letter),
            "involved_piece":   "bishop",
            "best_move_family": "BxN",
        }),
        "engine_endorsement": endorsement,
        "aligned_moves_offered": [played_san],
    }


# ── Detector #28: OP_F2_F7_STRIKE ───────────────────────────────────
#
# The classic Fried-Liver / Légal-trap / Scholar's-mate-defense theme:
# capture on f7 (white attacker) or f2 (black attacker) — the square
# is defended only by the king in the starting position, and many
# opening blunders leave it that way through the first 10–15 moves.
#
# Fires when:
#   1. Phase in (opening, middlegame).
#   2. Played move is a CAPTURE.
#   3. Capture square is f7 (when mover is white) OR f2 (when mover
#      is black). Geometric definition of "the weak square."
#   4. Before the played move, the ONLY defender of the capture
#      square was the enemy king. (If a knight / bishop / rook also
#      defends, the strike is no longer thematic — it's a standard
#      trade.)
#   5. The played move's SEE is non-negative (the strike actually
#      wins material — sacrifices that fail SEE are a different
#      pattern, e.g., Greek Gift, and need their own detector).
#   6. Eval bracket — drop already-winning STM > +300cp.
#
# Edge cases enumerated:
#   A. The capture is a pure piece exchange (e.g., Nxf7 by a knight
#      that's also defended adequately) — caught by SEE >= 0.
#   B. f7/f2 has another defender (a knight on c6 defends f7 in some
#      positions; bxc6 first might be needed). Don't fire.
#   C. SAN parse failures — return None safely.
#   D. Mover_is_user not relevant here — the lesson applies symmetrically.
#      But the resolver detail flips voice (you struck / they struck).
#   E. Endgame phase — exclude. f7/f2 weakness vanishes once king
#      castles + middlegame trades complete.
#   F. The captured piece is a pawn (e.g., exf7 from e6) — fire.
#      The thematic teaching IS about the f-square, not what's on it.
#      But if there's another piece on f7 (a pawn that was pushed
#      there from f6, say), we still fire — same square, same lesson.
#   G. f7 / f2 attacked but not captured (e.g., Bc4 eyes f7) — don't
#      fire. v1 covers captures only; threat-only is a future v2.
def _p_op_f2_f7_strike(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the player captures on f7 (white) or f2 (black) and
    the strike square was defended only by the enemy king."""
    if facts.get("phase") not in ("opening", "middlegame"):
        return None
    if not facts.get("is_capture"):
        return None

    own_color_str = facts.get("moving_piece_color")
    if own_color_str not in ("white", "black"):
        return None
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    enemy_color = not own_color

    # f7 if mover is white, f2 if mover is black.
    strike_sq_name = "f7" if own_color == chess.WHITE else "f2"
    target = facts.get("target_square") or ""
    if target != strike_sq_name:
        return None

    played_san = _normalize_san(facts.get("played_san") or "")
    if not played_san:
        return None

    # Eval bracket — drop already-winning per existing pattern.
    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        side_white = (own_color == chess.WHITE)
        stm_eval = eval_before_white_pov if side_white else -eval_before_white_pov
        if stm_eval > 300:
            return None

    try:
        played_move = board_before.parse_san(played_san)
    except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
        return None

    strike_sq = chess.parse_square(strike_sq_name)

    # Edge case B — defenders BEFORE the move must be only the king.
    defenders = board_before.attackers(enemy_color, strike_sq)
    non_king_defenders = []
    has_king_defender = False
    for sq in defenders:
        p = board_before.piece_at(sq)
        if not p:
            continue
        if p.piece_type == chess.KING:
            has_king_defender = True
        else:
            non_king_defenders.append(sq)
    if non_king_defenders:
        return None
    if not has_king_defender:
        # The king doesn't even defend the strike square — likely the
        # king already moved off its starting rank. The thematic lesson
        # ("the only defender is the king") doesn't apply. Skip.
        return None

    # Edge case A — SEE must be non-negative (the strike wins material).
    played_see = _see_for_played_move(board_before, played_move)
    if played_see is None:
        # Not a capture (shouldn't reach here since is_capture is set),
        # bail.
        return None
    if played_see < 0:
        # Sacrifice that fails SEE — different lesson (Greek Gift etc).
        return None

    enemy_king_sq = board_before.king(enemy_color)
    if enemy_king_sq is None:
        return None

    # Engine endorsement — if the played move IS the engine's best,
    # full endorsement. Otherwise the lesson is still teachable
    # (top_n) — the capture exists, the geometric pattern holds.
    best_san_raw = _normalize_san(facts.get("best_move_san") or "")
    if best_san_raw and best_san_raw == played_san:
        endorsement = "best"
    elif played_see > 0:
        # Material-winning strike — even if not engine #1, the lesson
        # is real. Voice will use cue_top_n.
        endorsement = "top_n"
    else:
        # Even-trade strike (SEE == 0). Less material-claim teaching.
        endorsement = "absent"

    moving_piece_sq = played_move.from_square

    return {
        "principle_id": "OP_F2_F7_STRIKE",
        "evidence": {
            "strike_square":          strike_sq_name,
            "attacker_from_square":   chess.square_name(moving_piece_sq),
            "attacker_piece_type":    facts.get("moving_piece_type") or "",
            "captured_piece_type":    facts.get("captured_piece_type") or "",
            "enemy_king_square":      chess.square_name(enemy_king_sq),
            "see_cp":                 played_see,
            "perspective":            "attacker" if facts.get("mover_is_user") else "defender",
            "played_san":             facts.get("played_san") or "",
            "best_san":               facts.get("best_move_san") or "",
        },
        "state_key": _freeze_state_key({
            "principle_id":     "OP_F2_F7_STRIKE",
            "phase":            facts.get("phase") or "opening",
            "intent_type":      "tactical_attack",
            "focal_squares":    (strike_sq_name, chess.square_name(enemy_king_sq)),
            "involved_piece":   facts.get("moving_piece_type") or "",
            "best_move_family": "capture_on_weak_square",
        }),
        "engine_endorsement": endorsement,
        "aligned_moves_offered": [played_san],
    }


# ── Helper: is a square "safe" for a piece of given color? ──────────
def _square_is_safe_for_piece(
    board: chess.Board,
    target_sq: int,
    piece_color: chess.Color,
    piece_value_cp: int,
) -> bool:
    """True if a piece of `piece_color` and `piece_value_cp` could
    occupy `target_sq` without losing material.

    Implementation: simulate the piece on target_sq (assume it's there
    after a move) and check whether the OPPONENT'S SEE on target_sq
    wins more than 0. If they can win material, square is unsafe.

    Note: this assumes the piece is ALREADY on target_sq (i.e., we've
    moved it there). For knight-move-safety we set up a hypothetical
    board with the knight on target_sq and ask: can the opponent capture
    it for material?
    """
    enemy_color = not piece_color
    # Compute SEE on target_sq with enemy as initiator.
    see = static_exchange_eval(board, target_sq, enemy_color)
    # SEE is from initiator's POV — positive means enemy wins material.
    # The piece itself sitting on target_sq IS the material at stake.
    # If enemy SEE > 0 (they net material), the square is unsafe.
    # Threshold of 50cp matches EXCHANGE_LOSS_THRESHOLD_CP for
    # consistency with other detectors.
    return see <= 50


# ── Detector #29: OP_TRAPPED_KNIGHT ─────────────────────────────────
#
# A knight is "trapped" when EVERY legal destination square either
# (a) is attacked by an enemy piece with insufficient defense, OR
# (b) would lose material on SEE. Combined: every escape is unsafe.
#
# This is distinct from OP_KNIGHT_ON_RIM (which fires on opening-
# development-to-rim regardless of mobility). TRAPPED_KNIGHT is
# about LOSS OF MOBILITY caused by the opponent's structure — a
# Nh5 attacked by g4-g5 with no safe retreat, or a Na5 cornered
# by b4-c3-d4 with no return path.
#
# Fires when:
#   1. Phase in (opening, middlegame). Endgames have different knight
#      patterns (e.g., shepherd / blockader) so excluded.
#   2. Player has at least one knight whose every legal-move
#      destination is unsafe.
#   3. The knight isn't already captured (obviously).
#   4. The knight has at least one pseudo-legal destination (a knight
#      with NO legal moves at all is either pinned — different lesson —
#      or boxed by own pieces, also different). If literally zero
#      legal moves: skip; this is a state-entry detector for the
#      "every option is unsafe" case.
#   5. eval bracket: drop already-winning (STM > +300cp) per pedagogy.
#
# match_kind = state_entry: the trapped state can hold for several
# moves before the knight is lost. State_key (knight_square + phase)
# dedupes — same trapped knight, one lesson.
#
# Edge cases enumerated:
#   A. Knight has NO legal moves at all (pinned, blocked by own
#      pieces only). Different lesson. Skip.
#   B. Knight could be defended ENOUGH that SEE-safe on every square
#      (e.g., own queen + bishop + rook covering its destinations).
#      Don't fire — it's not really trapped.
#   C. Knight could be CAPTURED-then-replaced safely (defended on its
#      current square). Doesn't matter — the question is whether it
#      can MOVE. We don't fire on "your knight is defended but stuck"
#      because that's still a lesson; the cue text covers it.
#   D. Two knights — fire on the first one detected. State_key keys on
#      the knight's square so a second trapped knight in the same
#      game re-fires.
#   E. The "trapped" claim must include enemy attackers on the
#      knight's CURRENT square too — if the knight is currently
#      hanging AND has no safe move, it's about to be won. Don't
#      special-case this; the trapped condition holds.
#   F. SAN-parse-required: NO. The detector doesn't need to parse
#      the played move; it inspects the board state.
#   G. mover_is_user perspective: fire when the user's OWN knight
#      is trapped (cue_best path), OR when the OPPONENT'S knight is
#      trapped (a winnable position — different voice but same
#      pattern). For v1: fire only on the side-to-move's own knight.
#      The mover is the side whose knight just got cornered, OR the
#      side whose previous move trapped the opponent. We use
#      board.turn = side-to-move. If side-to-move has a trapped
#      knight, fire (they need to rescue it). If opponent has a
#      trapped knight, the mover could win it — that's a different
#      teaching surface and would conflict with TAC_HANGING_PIECE.
#      Keep v1 focused: own-knight-trapped only.
def _p_op_trapped_knight(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when the side-to-move has a knight whose every legal
    destination is unsafe — the knight has no safe square."""
    if facts.get("phase") not in ("opening", "middlegame"):
        return None

    # Eval bracket — drop already-winning per pedagogy.
    eval_before_white_pov = facts.get("eval_before_cp")
    if eval_before_white_pov is not None:
        own_color_str = facts.get("moving_piece_color")
        side_white = (own_color_str == "white")
        stm_eval = eval_before_white_pov if side_white else -eval_before_white_pov
        if stm_eval > 300:
            return None

    us = board_before.turn

    knight_value_cp = PIECE_VALUE_CP[chess.KNIGHT]
    # Find every own knight.
    own_knight_squares = list(board_before.pieces(chess.KNIGHT, us))
    if not own_knight_squares:
        return None

    # For each knight, compute its legal destinations and check safety.
    for knight_sq in own_knight_squares:
        # Enumerate legal moves originating from knight_sq.
        legal_destinations = []
        for move in board_before.legal_moves:
            if move.from_square != knight_sq:
                continue
            # Sanity — should be a knight move (board.legal_moves
            # already filters by piece on from_square).
            legal_destinations.append(move.to_square)

        # Edge case A — knight has zero legal moves. Pinned or blocked
        # by own pieces. Different lesson; skip.
        if not legal_destinations:
            continue

        # Check safety of each destination. A destination is "safe" if
        # the knight could land there without losing material to a
        # forced recapture.
        any_safe = False
        unsafe_destinations: List[int] = []
        for dest_sq in legal_destinations:
            # Simulate: push the candidate move and check whether the
            # opponent's SEE on dest_sq wins material on the knight.
            # We find the matching legal Move object for this dest.
            sim_move = None
            for move in board_before.legal_moves:
                if move.from_square == knight_sq and move.to_square == dest_sq:
                    sim_move = move
                    break
            if sim_move is None:
                continue
            board_after_sim = board_before.copy()
            board_after_sim.push(sim_move)
            # Now opponent is to move. Their SEE on dest_sq tells us
            # if they win material.
            opp_see = static_exchange_eval(board_after_sim, dest_sq, not us)
            if opp_see <= 50:
                # This destination is safe — they don't win meaningful
                # material. Knight has an escape.
                any_safe = True
                break
            else:
                unsafe_destinations.append(dest_sq)

        if any_safe:
            continue

        # Every legal destination is unsafe — knight is trapped.
        # Also confirm at least one ENEMY attacker on the knight's
        # current square (otherwise the knight isn't actually under
        # threat — the "trapped but unattacked" case is less urgent
        # and is covered by other pattern detectors). This guards
        # against false fires on closed positions where the knight
        # has no good square but no enemy threat either.
        enemy_attackers_on_knight = list(board_before.attackers(not us, knight_sq))
        if not enemy_attackers_on_knight:
            continue

        # Found a trapped knight. Build evidence.
        # Aligned moves: any move that resolves the trap. Hard to
        # enumerate concretely — skip the aligned_moves list (use
        # the gate_policy=endorsement_preferred path).
        endorsement_word = "absent"  # default — engine prefers something
        best_san_raw = _normalize_san(facts.get("best_move_san") or "")
        if best_san_raw:
            # If engine's best move ORIGINATES from the trapped knight,
            # the engine sees a rescue — mark as best.
            try:
                best_move = board_before.parse_san(best_san_raw)
                if best_move.from_square == knight_sq:
                    endorsement_word = "best"
            except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError):
                pass

        # List enemy attackers for evidence (helps resolver detail
        # surface "they're hit by the pawn on g4" etc).
        enemy_attacker_squares = [chess.square_name(s) for s in enemy_attackers_on_knight]

        return {
            "principle_id": "OP_TRAPPED_KNIGHT",
            "evidence": {
                "trapped_knight_square":   chess.square_name(knight_sq),
                "knight_color":            "white" if us == chess.WHITE else "black",
                "legal_destination_count": len(legal_destinations),
                "enemy_attacker_squares":  enemy_attacker_squares,
                "best_san":                facts.get("best_move_san") or "",
            },
            "state_key": _freeze_state_key({
                "principle_id":     "OP_TRAPPED_KNIGHT",
                "phase":            facts.get("phase") or "opening",
                "intent_type":      "piece_safety",
                "focal_squares":    (chess.square_name(knight_sq),),
                "involved_piece":   "knight",
                "best_move_family": "rescue_or_trade",
            }),
            "engine_endorsement": endorsement_word,
            "aligned_moves_offered": [best_san_raw] if best_san_raw and endorsement_word == "best" else [],
        }

    return None


# ── Detector #23: END_KING_ACTIVE ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Endgame phase only.
#   2. Own king is on back rank (rank 1 for white, rank 8 for black) —
#      passive position.
#   3. State-entry match: fires the first move this state holds
#      (V5 wiring suppresses subsequent fires per once_per_state_entry).
def _p_end_king_active(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires in endgame when own king is still on its back rank.

    Gated to ACTUAL king moves (2026-06-23): the cue is rendered as
    "{played_san}. Activate the king …", so firing on a non-king move
    produced misleading captions like "h6. Activate the king." — as if
    the pawn push activated the king. The once-per-game king-activation
    lesson lands correctly when it accompanies the king step itself.
    """
    if facts.get("phase") != "endgame":
        return None
    if facts.get("moving_piece_type") != "king":
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    king_sq = board_before.king(own_color)
    if king_sq is None:
        return None
    king_rank = chess.square_rank(king_sq)
    back_rank = 0 if own_color == chess.WHITE else 7
    if king_rank != back_rank:
        return None
    # The played king move must actually go TOWARD the centre, so the cue
    # ("Activate the king — the centre is where it fights") matches the move.
    # Without this, Kh1->h2 (off the back rank but toward the rim) earned the
    # centre cue. Chebyshev distance to the central 4x4 (file/rank 3.5). 2026-06-23.
    try:
        _pm = board_before.parse_san(facts.get("played_san") or "")
        _from_d = max(abs(chess.square_file(king_sq) - 3.5),
                      abs(chess.square_rank(king_sq) - 3.5))
        _to_d = max(abs(chess.square_file(_pm.to_square) - 3.5),
                    abs(chess.square_rank(_pm.to_square) - 3.5))
        if _to_d >= _from_d:
            return None
    except Exception:
        pass
    # Aligned moves: king moves that LEAVE the back rank (must step off).
    aligned: List[str] = []
    for move in board_before.legal_moves:
        piece = board_before.piece_at(move.from_square)
        if not piece or piece.piece_type != chess.KING or piece.color != own_color:
            continue
        new_rank = chess.square_rank(move.to_square)
        if new_rank != back_rank:
            aligned.append(_normalize_san(board_before.san(move)))
    endorsement = _principle_engine_endorsement(aligned, facts.get("best_move_san"))
    return {
        "principle_id": "END_KING_ACTIVE",
        "evidence": {
            "king_square": chess.square_name(king_sq),
        },
        # END_KING_ACTIVE is a one-time-per-game lesson (catalog declares
        # once_per_game). state_key is included for consistency but the
        # suppression layer keys on principle_id when policy is
        # once_per_game.
        "state_key": _freeze_state_key({
            "principle_id":     "END_KING_ACTIVE",
            "phase":            "endgame",
            "intent_type":      "king_activation",
            "focal_squares":    (chess.square_name(king_sq),),
            "involved_piece":   "king",
            "best_move_family": "K_move",
        }),
        "engine_endorsement": endorsement,
        "aligned_moves_offered": aligned[:5],
    }


# ── Detector #24: MID_KING_SAFETY ───────────────────────────────────
#
# Edge cases enumerated:
#   1. Middlegame phase only.
#   2. Own king is castled — on g1/h1/c1/b1 (white) or g8/h8/c8/b8 (black).
#   3. At least one pawn in front of king (1-square ahead, in the
#      king's file + adjacent files) is MISSING from the player's
#      pawns. Captures the "loose king pawns" structural weakness.
#   4. State-entry match: fires once per state-entry per game.
def _p_mid_king_safety(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires in middlegame when own castled king has missing front
    pawns (a structural weakness — opponent can attack through gaps)."""
    if facts.get("phase") != "middlegame":
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    king_sq = board_before.king(own_color)
    if king_sq is None:
        return None
    castled_squares = (
        {chess.G1, chess.C1, chess.H1, chess.B1, chess.F1}
        if own_color == chess.WHITE
        else {chess.G8, chess.C8, chess.H8, chess.B8, chess.F8}
    )
    if king_sq not in castled_squares:
        return None
    king_file = chess.square_file(king_sq)
    pawn_rank = 1 if own_color == chess.WHITE else 6
    files_to_check = [f for f in (king_file - 1, king_file, king_file + 1) if 0 <= f < 8]
    pawn_missing = 0
    for f in files_to_check:
        sq = chess.square(f, pawn_rank)
        p = board_before.piece_at(sq)
        if not (p and p.piece_type == chess.PAWN and p.color == own_color):
            pawn_missing += 1
    if pawn_missing == 0:
        return None
    # gate_policy endorsement_preferred — we don't compute aligned moves
    # precisely (would require defensive-move classification). Use
    # binary endorsement based on whether engine prefers any move at all.
    return {
        "principle_id": "MID_KING_SAFETY",
        "evidence": {
            "king_square": chess.square_name(king_sq),
            "front_pawns_missing": pawn_missing,
        },
        "engine_endorsement": "absent",  # always uses cue_absent voice
        "aligned_moves_offered": [],
    }


# ── Detector #25: MID_KEEP_ATTACKERS ────────────────────────────────
#
# Edge cases enumerated:
#   1. Played move is a capture (must trade something).
#   2. The trade results in is_exchange_losing OR cp_loss >= 50.
#   3. The captured piece in board_before was NOT attacking any own
#      piece (so the player traded a "non-attacker" — likely traded
#      their own attacker for a defender, or worse).
#   4. cp_loss_strict implicit via gate above.
#
# v1 LIMITATION: precise "attacker" / "defender" identification
# requires intent analysis. This is a simple proxy that should fire
# on obvious cases and miss subtle ones; corpus audit will tune.
def _p_mid_keep_attackers(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires on a losing capture trade where the player traded their
    own attacker rather than the opponent's. v1 proxy: any capture
    move with cp_loss ≥ 50 AND engine prefers something else."""
    if facts.get("phase") != "middlegame":
        return None
    if not facts.get("is_capture"):
        return None
    if (facts.get("cp_loss") or 0) < 50:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best = _normalize_san(facts.get("best_move_san") or "")
    if not (best and best != played):
        return None
    return {
        "principle_id": "MID_KEEP_ATTACKERS",
        "evidence": {
            "trade_made": played,
            "engine_alternative": best,
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best],
    }


# ── Detector #26: DEF_TRADE_ATTACKERS ───────────────────────────────
#
# Edge cases enumerated:
#   1. Engine's #1 is a capture (player should have traded).
#   2. The captured piece (best_move's target) was attacking own
#      side in board_before — i.e., trading it removes an attacker.
#   3. Player played a non-capture / different capture.
#   4. cp_loss_strict (≥30).
def _p_def_trade_attackers(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 is to capture an enemy piece that's
    currently attacking own side, and player played something else."""
    if facts.get("phase") != "middlegame":
        return None
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    if "x" not in best_raw:
        return None  # best move is not a capture
    target = _move_target_from_san(best_raw)
    if not target:
        return None
    target_sq = chess.parse_square(target)
    captured_piece = board_before.piece_at(target_sq)
    if not captured_piece:
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    if captured_piece.color == own_color:
        return None  # not an enemy piece (shouldn't happen)
    # Does the captured enemy piece attack any own piece in board_before?
    attacks = board_before.attacks(target_sq)
    attacker_squares = [s for s in attacks
                        if board_before.piece_at(s) and
                        board_before.piece_at(s).color == own_color]
    if not attacker_squares:
        return None  # captured piece wasn't attacking anything of ours
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "DEF_TRADE_ATTACKERS",
        "evidence": {
            "engine_capture": best_raw,
            "attacker_square": target,
            "attacker_piece": PIECE_TYPE_NAMES.get(captured_piece.piece_type, "piece"),
            "attacks_own_pieces_at": [chess.square_name(s) for s in attacker_squares],
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #27: TAC_SKEWER_PATTERN ────────────────────────────────
#
# Edge cases enumerated:
#   1. Engine's #1 is a check (+ suffix, not # — that's TAC_BACK_RANK).
#   2. The checking piece lands on a line (rank/file/diagonal) that
#      includes the enemy king and extends past it to an enemy piece.
#   3. The enemy piece behind the king is valuable (≥ rook).
#   4. Player played something else.
#   5. cp_loss_strict (≥30).
def _p_tac_skewer_pattern(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires when engine's #1 is a check that exposes a piece behind
    the king on the same line — classic skewer."""
    if (facts.get("cp_loss") or 0) < 30:
        return None
    best_raw = facts.get("best_move_san") or ""
    if not (best_raw.endswith("+") and not best_raw.endswith("#")):
        return None
    target = _move_target_from_san(best_raw)
    if not target:
        return None
    target_sq = chess.parse_square(target)
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    enemy_color = not own_color
    enemy_king_sq = board_before.king(enemy_color)
    if enemy_king_sq is None:
        return None
    # Is target_sq on the same line as enemy king (rank/file/diagonal)?
    tf, tr = chess.square_file(target_sq), chess.square_rank(target_sq)
    kf, kr = chess.square_file(enemy_king_sq), chess.square_rank(enemy_king_sq)
    df = kf - tf
    dr = kr - tr
    # Determine direction unit vector
    if df == 0 and dr == 0:
        return None
    if df == 0:
        step_f, step_r = 0, (1 if dr > 0 else -1)
    elif dr == 0:
        step_f, step_r = (1 if df > 0 else -1), 0
    elif abs(df) == abs(dr):
        step_f = 1 if df > 0 else -1
        step_r = 1 if dr > 0 else -1
    else:
        return None  # not on a line
    # Walk past king in the same direction; find first piece
    behind_f, behind_r = kf + step_f, kr + step_r
    behind_piece = None
    behind_sq = None
    while 0 <= behind_f < 8 and 0 <= behind_r < 8:
        sq = chess.square(behind_f, behind_r)
        p = board_before.piece_at(sq)
        if p:
            if p.color == enemy_color and p.piece_type in (chess.ROOK, chess.QUEEN):
                behind_piece = p
                behind_sq = sq
            break
        behind_f += step_f
        behind_r += step_r
    if behind_piece is None:
        return None
    played = _normalize_san(facts.get("played_san") or "")
    best_norm = _normalize_san(best_raw)
    if played == best_norm:
        return None
    return {
        "principle_id": "TAC_SKEWER_PATTERN",
        "evidence": {
            "checking_move": best_raw,
            "enemy_king_square": chess.square_name(enemy_king_sq),
            "behind_piece_square": chess.square_name(behind_sq),
            "behind_piece_type": PIECE_TYPE_NAMES.get(behind_piece.piece_type, "piece"),
        },
        "engine_endorsement": "best",
        "aligned_moves_offered": [best_norm],
    }


# ── Detector #28: MID_BAD_BISHOP ────────────────────────────────────
#
# Edge cases enumerated:
#   1. State-entry match: any move in middlegame where own bishop is
#      "bad" — defined as ≥4 own pawns on the same color squares as
#      the bishop.
#   2. cp_loss gate not strict; this is a long-term principle.
#   3. endorsement_preferred — fires with cue_absent when engine
#      doesn't endorse rerouting the bishop this move.
def _p_mid_bad_bishop(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Optional[Dict[str, Any]]:
    """Fires in middlegame when own bishop is blocked by ≥4 same-
    color own pawns (a structural bad bishop)."""
    if facts.get("phase") != "middlegame":
        return None
    own_color_str = facts.get("moving_piece_color")
    own_color = chess.WHITE if own_color_str == "white" else chess.BLACK
    bad_bishop_sq = None
    pawn_count = 0
    # A bad bishop must be DEVELOPED but trapped — not still on its home square.
    # Audit (2026-06-20): 69/100 firings were the undeveloped home-square bishop
    # (e.g. f8 with 7 same-colour pawns) — that's "develop it", not "bad bishop".
    _home_bishop_sq = {chess.C1, chess.F1} if own_color == chess.WHITE else {chess.C8, chess.F8}
    for bsq in board_before.pieces(chess.BISHOP, own_color):
        if bsq in _home_bishop_sq:
            continue
        bishop_sq_color = (chess.square_file(bsq) + chess.square_rank(bsq)) % 2
        same_color_pawns = 0
        for psq in board_before.pieces(chess.PAWN, own_color):
            if (chess.square_file(psq) + chess.square_rank(psq)) % 2 == bishop_sq_color:
                same_color_pawns += 1
        # Threshold raised 4 → 5 after audit pass #1: 4 same-color
        # pawns fires even on starting positions where no pawns
        # have been traded (every side starts with 4 on each colour).
        # 5+ catches the genuinely-locked-in cases.
        if same_color_pawns >= 5:
            # v91 (2026-05-25) — Parth fb_164108af2618. Previously this
            # detector fired on "5+ same-color pawns" alone, which
            # misfired on positions where the bishop is ALREADY active
            # outside the pawn chain (e.g. white Bishop on e5 in Parth's
            # case: 5 dark-square pawns total, but e5 is in the centre
            # with ~7 attack squares). A genuinely "bad" bishop is
            # locked BEHIND its own pawns — meaning its mobility is
            # restricted. Mobility check: count squares the bishop can
            # actually reach (including captures). Active bishops with
            # ≥4 legal squares are NOT bad — their teaching surface
            # would mislead a 1200 ("the bishop on e5 needs to reroute"
            # when it's already well-placed).
            bishop_attacks = board_before.attacks(bsq)
            # Subtract squares occupied by OWN pieces (can't move there)
            own_pieces_bb = board_before.occupied_co[own_color]
            mobility = chess.popcount(int(bishop_attacks) & ~int(own_pieces_bb))
            if mobility >= 4:
                continue
            bad_bishop_sq = bsq
            pawn_count = same_color_pawns
            break
    if bad_bishop_sq is None:
        return None
    return {
        "principle_id": "MID_BAD_BISHOP",
        "evidence": {
            "bad_bishop_square": chess.square_name(bad_bishop_sq),
            "same_color_pawn_count": pawn_count,
        },
        "engine_endorsement": "absent",
        "aligned_moves_offered": [],
    }


def _principles_violated(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> List[Dict[str, Any]]:
    """Run every shipped principle detector against the facts dict.
    Returns a list of evidence dicts for every principle that matches.

    Suppression (once_per_move / once_per_state_entry / once_per_game)
    and priority resolution happen at the V5 wiring layer, NOT here.
    The extractor stays pure: same input → same output every time.

    Catalog progress: 28 / 28 detectors live. Corpus audit will
    surface false positives and threshold mis-calibrations per
    detector; tuning happens after data lands, not before.
    """
    out: List[Dict[str, Any]] = []
    for detector in (
        _p_op_queen_out_early,
        _p_tac_fork_pattern,
        _p_tac_pin_pattern,
        _p_tac_discovered_pattern,
        _p_tac_hanging_piece,
        _p_op_knight_on_rim,
        _p_op_same_piece_twice,
        _p_op_not_castled,
        _p_op_pawn_heavy,
        _p_op_claim_center,
        _p_tac_defender_count,
        _p_def_most_attacked,
        _p_end_passed_pawn,
        _p_op_loose_king_pawns,
        _p_op_bishop_blocked,
        _p_op_finish_development,
        _p_tac_checks_captures_threats,
        _p_tac_back_rank,
        _p_tac_changed_after_move,
        _p_def_walk_king,
        _p_mid_rook_open_file,
        _p_mid_pawn_break,
        _p_end_king_active,
        _p_end_rule_of_square,   # added 2026-05-16 (Mohit signoff)
        _p_end_opposition,       # added 2026-05-17 (Mohit signoff) — king_move_required gate
        _p_end_rook_behind_passer, # added 2026-05-18 (Phase 4) — Tarrasch's rule, single-passer-only
        _p_end_pawn_traps_own_rook,  # added 2026-06-22 — pawn push that entombs your own rook (mobility collapse)
        _p_op_bishop_trade_doubles_pawn,  # added 2026-05-18 (Phase 6) — cross-opening structural concession
        _p_op_f2_f7_strike,               # added 2026-05-18 (Phase 6) — weak-king-square strike
        _p_op_trapped_knight,             # added 2026-05-18 (Phase 6) — knight with zero safe squares
        _p_mid_king_safety,
        _p_mid_keep_attackers,
        _p_def_trade_attackers,
        _p_tac_skewer_pattern,
        _p_mid_bad_bishop,
    ):
        try:
            ev = detector(facts, board_before)
        except Exception:
            # Detector crashes never break extract_facts. Same defensive
            # posture as the rest of the extractor.
            ev = None
        if ev:
            out.append(ev)
    return out


# ────────────────────────────────────────────────────────────────────
# Move-principle classifier (P2b — plan-behind-a-good-move + missed-opportunity)
# ────────────────────────────────────────────────────────────────────

_CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}


def _is_outpost(board: chess.Board, move: chess.Move) -> bool:
    """Outpost via the CANONICAL detector (single source: shape_detectors.
    simulate_knight_outpost) — central files c-f, defended by an own piece, not
    currently pawn-attacked. My earlier standalone version was a DUPLICATE and WRONG
    (allowed rim files, so it called Na4/Nh4 'outposts'). Reuse, don't re-derive."""
    try:
        from services.shape_detectors import simulate_knight_outpost
        return bool(simulate_knight_outpost(board.fen(), board.san(move)))
    except Exception:
        return False


def _classify_move_principle(board: chess.Board, move: Optional[chess.Move]) -> Optional[str]:
    """The transferable PRINCIPLE a move embodies, board-verified. Used to name the
    idea behind a good move ("develops, fighting for the center") and the idea behind
    the engine's better move on a missed opportunity ("Nf3 was calmer, developing").
    Returns center / develop / castle / rook_open_file, or None when no clean
    principle applies (the caption then stays generic — right-or-silent)."""
    if move is None:
        return None
    try:
        if board.is_castling(move):
            return "castle"
        pc = board.piece_at(move.from_square)
        if pc is None:
            return None
        # outpost (a knight no pawn can chase) is more specific + valuable than "center"
        if _is_outpost(board, move):
            return "outpost"
        if move.to_square in _CENTER_SQUARES and pc.piece_type in (
            chess.PAWN, chess.KNIGHT, chess.BISHOP,
        ):
            return "center"
        if pc.piece_type in (chess.KNIGHT, chess.BISHOP):
            r = chess.square_rank(move.from_square)
            if (pc.color == chess.WHITE and r == 0) or (pc.color == chess.BLACK and r == 7):
                return "develop"
        if pc.piece_type == chess.ROOK:
            f = chess.square_file(move.to_square)
            own_pawn = any(
                board.piece_at(chess.square(f, rr)) == chess.Piece(chess.PAWN, pc.color)
                for rr in range(8)
            )
            if not own_pawn:
                return "rook_open_file"
    except Exception:
        return None
    return None


_REC_PRINCIPLE_PHRASE = {
    "center": "takes the center",
    "develop": "develops a piece",
    "castle": "gets your king to safety",
    "rook_open_file": "takes the open file",
    # "outpost" is banned jargon (600-1500 audience) — describe it plainly.
    "outpost": "posts a knight on a strong square the opponent can't challenge",
}


def _recommended_move_why(board: chess.Board, move: Optional[chess.Move]) -> Optional[str]:
    """WHY a recommended move is good, as a short 3rd-person verb phrase that slots into
    'it {why}' — 'develops a piece', 'takes the center', 'trades off his bishop', 'wins a
    pawn'. The law: every recommended move needs its why (memory
    feedback_explain_why_recommended_move_good). Board-verified; material claims SEE-gated.
    Returns None when no clean why is derivable (caller falls back to naming the move)."""
    if move is None:
        return None
    try:
        pr = _classify_move_principle(board, move)
        mover = board.turn
        # 1) CAPTURE — concrete material (SEE-gated, never overclaims).
        if board.is_capture(move):
            if board.is_en_passant(move):
                cap_pt = chess.PAWN
            else:
                cpiece = board.piece_at(move.to_square)
                cap_pt = cpiece.piece_type if cpiece else None
            if cap_pt is None:
                return None
            name = PIECE_TYPE_NAMES.get(cap_pt, "piece")
            see = static_exchange_eval(board, move.to_square, mover)
            if see is not None and see >= 200:
                return "wins material"
            if see is not None and see >= 80:
                return "wins a pawn" if cap_pt == chess.PAWN else "wins material"
            # equal-ish exchange — the value is removing the piece, not material
            return f"trades his {name}"

        # CASTLE — its whole purpose is king safety; name that, not an incidental
        # "defends f7" the rook happens to add. Checked before threat/escape/defends.
        if pr == "castle":
            return _REC_PRINCIPLE_PHRASE["castle"]

        # Non-capture: derive the why from what the move DOES on the board.
        # Every branch is board-verified (true by construction) — right-or-silent.
        moved = board.piece_at(move.from_square)
        if moved is None:
            return _REC_PRINCIPLE_PHRASE.get(pr)
        enemy = not mover
        my_val = PIECE_VALUE_CP.get(moved.piece_type, 0)
        after = board.copy()
        after.push(move)

        # 2) THREAT — the moved piece now attacks an enemy piece that is UNDEFENDED
        #    or worth MORE than the moving piece (a real threat, not a defended equal).
        #    Pick the most valuable such target. (Mirrors developed_eyes gating.)
        best_threat = None  # (square, value, piece_type)
        for sq in after.attacks(move.to_square):
            p = after.piece_at(sq)
            if not p or p.color != enemy or p.piece_type == chess.KING:
                continue
            val = PIECE_VALUE_CP.get(p.piece_type, 0)
            defended = bool(after.attackers(enemy, sq))
            if (not defended) or (val > my_val):
                if best_threat is None or val > best_threat[1]:
                    best_threat = (sq, val, p.piece_type)
        if best_threat is not None:
            return (f"attacks the {PIECE_TYPE_NAMES.get(best_threat[2], 'piece')} "
                    f"on {chess.square_name(best_threat[0])}")

        # 3) ESCAPE — the moved piece was hanging (enemy wins it on its old square)
        #    and is safe after the move: the move saves material.
        if moved.piece_type != chess.KING:
            see_before = static_exchange_eval(board, move.from_square, enemy)
            see_after = static_exchange_eval(after, move.to_square, enemy)
            if (see_before or 0) >= 100 and (see_after or 0) <= 0:
                return (f"moves your {PIECE_TYPE_NAMES.get(moved.piece_type, 'piece')} "
                        f"out of danger")

        # 4) DEFENDS — a DIFFERENT friendly piece was hanging before and is safe after
        #    because this move adds a defender (the move rescues it without moving it).
        for sq in chess.SQUARES:
            if sq == move.from_square:
                continue
            fp = board.piece_at(sq)
            if not fp or fp.color != mover or fp.piece_type == chess.KING:
                continue
            if (static_exchange_eval(board, sq, enemy) or 0) >= 100 and \
               (static_exchange_eval(after, sq, enemy) or 0) <= 0 and \
               move.to_square in after.attackers(mover, sq):
                return (f"defends your {PIECE_TYPE_NAMES.get(fp.piece_type, 'piece')} "
                        f"on {chess.square_name(sq)}")

        # 4b) MATE / CHECK / PROMOTION — concrete forcing purposes the floor
        #     was missing (2026-07-14, Q2: "Qc4+ was the stronger move here"
        #     rendered with no why because checks had no branch). All three
        #     are true by construction on the after-board.
        if after.is_checkmate():
            return "delivers checkmate"
        if move.promotion == chess.QUEEN:
            return "makes a new queen"
        if after.is_check():
            return "gives check, forcing your opponent to respond"

        # 5) PRINCIPLE — castle/center/develop/outpost/rook (transferable idea).
        if pr in _REC_PRINCIPLE_PHRASE:
            return _REC_PRINCIPLE_PHRASE[pr]
    except Exception:
        return None
    return None


# ────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────

def extract_facts(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str] = None,
    eval_before_cp: Optional[int] = None,
    eval_after_cp: Optional[int] = None,
    cp_loss: int = 0,
    pv_after_played: Optional[List[str]] = None,
    pv_after_best: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
    mover_is_user: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Extract the deterministic facts dict for one move.

    Inputs are pure data: a FEN string, the played move (SAN), the
    engine's best move (SAN), eval/cp_loss, and the engine's PV after
    each. No database access, no global state.

    Returns a flat dict whose keys match the contract described in
    `docs/caption_pipeline_design.md` §4. Every key is atomic — no
    interpreted prose, no judgment, no convenience labels.

    Raises:
        chess.InvalidMoveError if played_san cannot be parsed from fen_before.
        ValueError if fen_before is invalid.
    """
    pv_after_played = pv_after_played or []
    pv_after_best = pv_after_best or []
    move_history_san = move_history_san or []
    cp_loss = max(0, cp_loss or 0)

    # Build board_before. If the caller provided move_history, replay it
    # so board_before.move_stack has the previous moves (needed for the
    # forced-recapture check). Otherwise rely on the FEN alone.
    if move_history_san:
        board_before = chess.Board()
        for san in move_history_san:
            try:
                board_before.push_san(san)
            except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
                # History invalid — fall back to FEN-only board (no stack)
                board_before = chess.Board(fen_before)
                break
        # Sanity check: replayed position should match the FEN we got
        # (board_before.fen() may differ in halfmove/fullmove counters
        # but the position part should match).
        if " ".join(board_before.fen().split()[:4]) != " ".join(fen_before.split()[:4]):
            # History didn't reach the same position. Trust the FEN.
            board_before = chess.Board(fen_before)
    else:
        board_before = chess.Board(fen_before)

    # Parse the played move.
    played_move = board_before.parse_san(played_san)

    # Build board_after.
    board_after = board_before.copy()
    board_after.push(played_move)

    # ── Engine truth (pass-through) ────────────────────────────────────
    played_is_best = (
        best_move_san is not None
        and _normalize_san(played_san) == _normalize_san(best_move_san)
    )

    # ── Position facts ─────────────────────────────────────────────────
    moving_piece = board_before.piece_at(played_move.from_square)
    moving_piece_type = moving_piece.piece_type if moving_piece else None
    moving_piece_color = moving_piece.color if moving_piece else None

    is_capture = board_before.is_capture(played_move)
    captured_piece = None
    if is_capture:
        # Detect en-passant: in EP, the captured pawn is NOT on
        # played_move.to_square — it's one rank behind/ahead.
        if board_before.is_en_passant(played_move):
            captured_piece = chess.Piece(chess.PAWN, not board_before.turn)
        else:
            captured_piece = board_before.piece_at(played_move.to_square)
    captured_piece_type_name = (
        PIECE_TYPE_NAMES.get(captured_piece.piece_type)
        if captured_piece else None
    )

    is_check = board_after.is_check()
    is_checkmate = board_after.is_checkmate()
    is_castling = board_before.is_castling(played_move)

    # ── OPPONENT FAILURE-MODE facts (2026-06-06) ───────────────────────
    # Only meaningful for OPPONENT moves where the engine's best_move was
    # available (Phase 0: stockfish_service now stores opp best_move + PV
    # for opp mistakes/blunders). These explain WHY the opponent's move
    # was bad — what they should have played — instead of the bare
    # "Opponent's X is a mistake." shell. Parallel to the user-side
    # failure_mode_clauses but from the opponent's perspective.
    #
    # missed_capture: opp had a capture available (best_move) that wins
    #   material, and played something else. The canonical case
    #   (fb_4899b11157fa Nbd7): Black could play Qxd4 grabbing a free
    #   pawn but played Nbd7 instead.
    opp_failure_missed_capture = False
    opp_missed_capture_san: Optional[str] = None
    opp_missed_capture_piece: Optional[str] = None
    opp_missed_capture_square: Optional[str] = None
    opp_failure_missed_mate = False
    opp_missed_mate_san: Optional[str] = None
    opp_failure_missed_tactic = False
    opp_missed_tactic_san: Optional[str] = None
    opp_missed_tactic_desc: Optional[str] = None
    if (mover_is_user is False and best_move_san
            and not played_is_best):
        try:
            _bm = board_before.parse_san(best_move_san)
            # missed capture: best move is a capture of a real piece
            if board_before.is_capture(_bm):
                if board_before.is_en_passant(_bm):
                    _cap_pc = chess.Piece(chess.PAWN, not board_before.turn)
                    _cap_sq = _bm.to_square
                else:
                    _cap_pc = board_before.piece_at(_bm.to_square)
                    _cap_sq = _bm.to_square
                if _cap_pc is not None:
                    opp_failure_missed_capture = True
                    opp_missed_capture_san = best_move_san
                    opp_missed_capture_piece = PIECE_TYPE_NAMES.get(
                        _cap_pc.piece_type, "piece"
                    )
                    opp_missed_capture_square = chess.SQUARE_NAMES[_cap_sq]
            # missed mate: the best-move PV forces mate
            if pv_after_best and any("#" in m for m in pv_after_best[:6]):
                opp_failure_missed_mate = True
                opp_missed_mate_san = best_move_san
            # missed tactic: the best move is a quiet (non-capture) FORK against
            # the user — they had a strong double-attack and played something else.
            # Explains the danger the user DODGED (Na4 case: missed Nd5 forking the
            # e7 bishop + f6 knight). Parth QA 2026-06-22. Engine already endorsed
            # best_move as far superior, so naming its fork is safe.
            if (not opp_failure_missed_capture
                    and not board_before.is_capture(_bm)):
                _sim = board_before.copy(); _sim.push(_bm)
                _user_color = not board_before.turn  # opp is to move → user is the other
                _tgts = []
                for _ts in _sim.attacks(_bm.to_square):
                    _tp = _sim.piece_at(_ts)
                    if (_tp and _tp.color == _user_color and _tp.piece_type in (
                            chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)):
                        _tgts.append((_ts, _tp.piece_type))
                # Winnability gate so "forking" is truthful, not a double-attack on
                # two defended equals: at least one target must be undefended OR worth
                # more than the forking piece (capturing it wins material).
                _forker_val = PIECE_VALUE_CP.get(_sim.piece_at(_bm.to_square).piece_type, 0)
                _winnable = any(
                    PIECE_VALUE_CP.get(_p, 0) > _forker_val
                    or not _sim.attackers(_user_color, _s)
                    for _s, _p in _tgts)
                if len(_tgts) >= 2 and _winnable:
                    _tgts.sort(key=lambda x: -PIECE_VALUE_CP.get(x[1], 0))
                    (_s1, _p1), (_s2, _p2) = _tgts[0], _tgts[1]
                    opp_failure_missed_tactic = True
                    opp_missed_tactic_san = best_move_san
                    opp_missed_tactic_desc = (
                        "forking your %s on %s and %s on %s" % (
                            chess.piece_name(_p1), chess.square_name(_s1),
                            chess.piece_name(_p2), chess.square_name(_s2)))
        except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError, AssertionError):
            # best_move_san didn't parse on board_before (PGN/eval drift).
            # Leave facts unset rather than raising.
            pass
    is_promotion = played_move.promotion is not None
    forced_recapture = _is_forced_recapture(board_before, played_move)

    target_square = chess.square_name(played_move.to_square)
    from_square = chess.square_name(played_move.from_square)

    # ── Attack/defense math (raw lists; SEE comes in commit #2) ────────
    # All measured on board_after (the position after the move).
    own_color = moving_piece_color if moving_piece_color is not None else board_before.turn
    opp_color = not own_color

    attackers_on_target = _attackers_of(board_after, opp_color, played_move.to_square)
    defenders_on_target = _attackers_of(board_after, own_color, played_move.to_square)

    # ── SEE-driven exchange truth (commit #2) ──────────────────────────
    # Raw attacker/defender counts above are kept for renderer reference
    # but DO NOT drive trigger logic. SEE handles pinned/x-ray/value-
    # imbalance correctly by simulating the actual cheapest-first
    # recapture sequence.
    see_played_capture_cp = _see_for_played_move(board_before, played_move)
    # For non-capture moves: would opponent win material capturing on
    # target_square next? SEE from their POV in board_after.
    target_square_exchange_cp = None
    if not is_capture:
        target_square_exchange_cp = _target_square_exchange_cp(board_after, played_move.to_square)

    # `is_exchange_losing` consolidates the two SEE signals:
    #   - if it's a capture: SEE for the played capture is negative
    #   - if not a capture: opponent's SEE on the target square is positive
    #     (meaning OUR piece is in danger of being won)
    if is_capture and see_played_capture_cp is not None:
        is_exchange_losing = see_played_capture_cp < -EXCHANGE_LOSS_THRESHOLD_CP
        exchange_loss_cp = abs(see_played_capture_cp) if see_played_capture_cp < 0 else 0
    elif target_square_exchange_cp is not None:
        is_exchange_losing = target_square_exchange_cp > EXCHANGE_LOSS_THRESHOLD_CP
        exchange_loss_cp = target_square_exchange_cp if target_square_exchange_cp > 0 else 0
    else:
        is_exchange_losing = False
        exchange_loss_cp = 0

    # ── Effective attackers/defenders (SEE-participating, pin-filtered) ─
    # Distinct from the RAW lists above. Effective = the pieces that
    # actually take part in the exchange sequence. Renderers should
    # prefer these for trigger logic; raw lists stay for reference.
    initiating_for_target = opp_color  # who'd start a capture sequence on the target?
    if is_capture:
        # The piece sitting on target was captured — exchange continues from
        # opponent's POV (they'd recapture).
        initiating_for_target = opp_color
    effective_attackers, effective_defenders = _exchange_participants(
        board_after, played_move.to_square, initiating_for_target
    )

    # ── Phase / full move number (needed by detectors below) ────────────
    full_move = full_move_number or board_before.fullmove_number
    phase = _detect_phase(board_before, full_move)

    # ── Threats created by the played move (structured evidence) ────────
    threats_created = _threats_created(board_before, board_after, played_move)

    # ── Pieces that lost a defender (structured evidence) ──────────────
    pieces_now_undefended = _pieces_now_undefended(board_before, board_after, played_move)

    # ── Opponent's expected reply (2026-05-13) ─────────────────────────
    # pv_after_played[0] is the engine's expected opponent response after
    # the played move. For R12_blunder's WHY composition (and any future
    # rule that needs to say "after their reply, X happens"), expose:
    #   - opp_reply_san: the SAN of opp's first move
    #   - opp_reply_attacks_played_piece: True if opp's reply attacks the
    #     square the played piece landed on (covers "your knight is now
    #     attacked with no safe square" cases like Ne5 -> f4)
    #   - opp_reply_captures_piece_type: piece type captured by opp's
    #     reply, if any (covers "opponent wins your X" cases)
    opp_reply_san: Optional[str] = None
    opp_reply_attacks_played_piece: bool = False
    opp_reply_captures_piece_type: Optional[str] = None
    opp_reply_captures_square: Optional[str] = None
    # WHY-BAD enrichment (2026-06-23): the played move DROPS material — the
    # opponent's best reply wins a piece/pawn (SEE-verified), and it is NOT an
    # equal recapture of the user's own just-captured piece. Lets a quiet move
    # that hangs material (e.g. Bc5 -> Nxc5) get a concrete why-bad instead of a
    # bare "is a mistake" + generic principle. Filled in the capture branch below.
    played_drops_material: bool = False
    played_drops_piece: Optional[str] = None
    played_drops_to_san: Optional[str] = None
    # Mohit 2026-06-06 (fb_22528b6266b1, Parth): when the played move is
    # a capture AND opp_reply captures on the same square, both SANs
    # render identically ("Bxe5 hangs to Bxe5 winning your bishop") —
    # a confusing tautology. This fact lets the template switch to a
    # recapture-specific branch that names the square instead.
    opp_reply_recaptures_on_played_square: bool = False
    played_to_square: Optional[str] = None
    # Mohit 2026-06-02: fork detection (Phase 2 of why_played_wrong
    # spec). Covers m24 Qb8 from the 2026-06-01 feedback batch — Qb8
    # didn't walk into an attack on the queen itself (opp_reply_attacks_
    # played_piece=False) but Nb7 forked the queen on c8 and the rook
    # on a8. New facts:
    #   opp_reply_creates_fork: True when opp's reply attacks ≥2 user
    #                           pieces (or 1 king + ≥1 piece) from its
    #                           landing square, where targets weren't
    #                           ALREADY attacked by that piece's old
    #                           square — i.e. the fork is created BY
    #                           the move, not pre-existing.
    #   fork_target_1, fork_target_2: piece-type names of the two
    #     most-valuable targets (king named separately as "king" so
    #     templates can phrase "your king and queen").
    #   fork_target_1_square, fork_target_2_square: squares for the
    #     same two targets. Templates can phrase "your queen on c8
    #     and rook on a8".
    opp_reply_creates_fork: bool = False
    fork_target_1: Optional[str] = None
    fork_target_2: Optional[str] = None
    fork_target_1_square: Optional[str] = None
    fork_target_2_square: Optional[str] = None
    if pv_after_played:
        raw = (pv_after_played[0] or "").strip()
        if raw:
            opp_reply_san = raw
            try:
                opp_mv = board_after.parse_san(raw)
                if board_after.is_capture(opp_mv):
                    captured = board_after.piece_at(opp_mv.to_square)
                    if captured:
                        opp_reply_captures_piece_type = PIECE_TYPE_NAMES.get(
                            captured.piece_type, "piece"
                        )
                        opp_reply_captures_square = chess.SQUARE_NAMES[opp_mv.to_square]
                    # Recapture detection (2026-06-06): the played move
                    # was a capture AND opp_reply captures on the same
                    # square. Without this branch, the failure template
                    # renders "Bxe5 hangs to Bxe5 winning your bishop" —
                    # confusing tautology.
                    if (
                        board_before.is_capture(played_move)
                        and opp_mv.to_square == played_move.to_square
                    ):
                        opp_reply_recaptures_on_played_square = True
                        played_to_square = chess.SQUARE_NAMES[played_move.to_square]
                    # WHY-BAD: the reply WINS material (SEE>=100). Gated to a
                    # NON-capture played move — a clean "you moved and left this
                    # hanging" story. (A played CAPTURE that also drops material is
                    # a murkier net-trade; skip it to avoid confusing framing.)
                    _drop_see = static_exchange_eval(board_after, opp_mv.to_square, board_after.turn)
                    if (_drop_see or 0) >= 100 and not board_before.is_capture(played_move):
                        played_drops_material = True
                        played_drops_piece = opp_reply_captures_piece_type
                        played_drops_to_san = raw
                sim = board_after.copy()
                sim.push(opp_mv)

                # Determine user's color (needed for both attacks and fork detection)
                _user_color = played_move and board_before.piece_at(played_move.from_square)
                _user_color = _user_color.color if _user_color else None

                # After opp's reply, does its piece attack the square our
                # played piece is sitting on? Gate on defender count: only
                # flag as attacked if more opp attackers than our defenders.
                # Per issue fb_0f74b8a30d24: "After Qxd4, your knight on f4
                # is under attack" but knight was defended by bishop — never
                # mention "under attack" if piece is actually defended.
                if played_move.to_square in sim.attacks(opp_mv.to_square):
                    if _user_color is not None:
                        opp_attackers = len(sim.attackers(not _user_color, played_move.to_square))
                        own_defenders = len(sim.attackers(_user_color, played_move.to_square))
                        # Only flag as "under attack" if undefended or more attacked than defended
                        if opp_attackers > own_defenders:
                            opp_reply_attacks_played_piece = True
                    else:
                        opp_reply_attacks_played_piece = True

                # Fork detection: identify which user pieces opp's
                # moved piece attacks from its NEW square. The played
                # piece itself is excluded if already counted (that's
                # the attacks_played fact). King is always a target;
                # other pieces only count if value >= minor (knight/
                # bishop+). Pawns excluded.
                attacked_by_opp = sim.attacks(opp_mv.to_square)
                _PIECE_VALUE_MIN_FOR_FORK = 3  # knight value
                _targets: list = []
                if _user_color is not None:
                    for sq in attacked_by_opp:
                        pc = sim.piece_at(sq)
                        if pc is None or pc.color != _user_color:
                            continue
                        if pc.piece_type == chess.KING:
                            _targets.append(("king", chess.SQUARE_NAMES[sq], 1000))
                        else:
                            val = {chess.QUEEN: 9, chess.ROOK: 5,
                                   chess.BISHOP: 3, chess.KNIGHT: 3,
                                   chess.PAWN: 1}.get(pc.piece_type, 0)
                            if val >= _PIECE_VALUE_MIN_FOR_FORK:
                                name = PIECE_TYPE_NAMES.get(pc.piece_type, "piece")
                                _targets.append((name, chess.SQUARE_NAMES[sq], val))
                # Need 2+ targets to be a fork. Sort by value desc so
                # the more impressive target is named first.
                if len(_targets) >= 2:
                    _targets.sort(key=lambda t: -t[2])
                    opp_reply_creates_fork = True
                    fork_target_1 = _targets[0][0]
                    fork_target_1_square = _targets[0][1]
                    fork_target_2 = _targets[1][0]
                    fork_target_2_square = _targets[1][1]
            except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError, AssertionError):
                # PGN drift defensive — pv_after_played may not align with
                # board_after in rare cases. Leave facts empty rather than
                # raising.
                pass

    # ── User move failures (NEW detectors 2026-07-14) ────────────────────
    # Wire built-but-unwired detectors into the central facts layer.
    # Non-fatal: detector errors are caught and logged; facts stay empty.
    played_hangs_result = None
    played_hangs_square = None
    played_hangs_piece = None
    try:
        from services.played_hangs_detector import detect_played_hangs
        _hangs = detect_played_hangs(board_before, played_move)
        if _hangs:
            played_hangs_result = True
            played_hangs_square = _hangs.get("square")
            played_hangs_piece = _hangs.get("piece")
    except Exception as e:
        logger.warning(f"played_hangs_detector failed: {e}")

    # ── Opponent move failures (NEW detectors 2026-07-14) ────────────────
    opp_traded_active_result = None
    opp_traded_active_piece = None
    opp_traded_active_square = None
    opp_traded_active_recapture = None
    try:
        if mover_is_user is False:  # opponent move
            from services.opp_traded_active_detector import detect_opp_traded_active
            _opp_ta = detect_opp_traded_active(board_before, played_move, pv_after_played, cp_loss)
            if _opp_ta:
                opp_traded_active_result = True
                opp_traded_active_piece = _opp_ta.get("piece")
                opp_traded_active_square = _opp_ta.get("square")
                opp_traded_active_recapture = _opp_ta.get("recapture_san")
    except Exception as e:
        logger.warning(f"opp_traded_active_detector failed: {e}")

    opp_quiet_threat_result = None
    opp_quiet_threat_piece = None
    opp_quiet_threat_square = None
    opp_quiet_threat_best = None
    try:
        if mover_is_user is False:  # opponent move
            from services.opp_quiet_threat_detector import detect_quiet_when_threatened
            _opp_qt = detect_quiet_when_threatened(board_before, played_move, best_move_san, cp_loss)
            if _opp_qt:
                opp_quiet_threat_result = True
                opp_quiet_threat_piece = _opp_qt.get("piece")
                opp_quiet_threat_square = _opp_qt.get("square")
                opp_quiet_threat_best = _opp_qt.get("best_san")
    except Exception as e:
        logger.warning(f"opp_quiet_threat_detector failed: {e}")

    # ── Tactic-shape evidence (commit #3 + renamed in #4a) ──────────────
    # All detectors emit structured evidence per LAW 3. Names changed
    # from {fork/pin/skewer/discovery}_shape to more primitive forms:
    #   multi_target_attack — "one attacker, multiple targets"
    #   aligned_pieces     — "three pieces on a line" (renderer picks
    #                        pin/skewer/x-ray via front_value_vs_rear)
    #   discovered_attack  — "uncovered attacker via played move"
    multi_target_attack_evidence = _multi_target_attack_evidence(
        threats_created, board_after, played_move
    )
    # User-flagged bug 2026-05-13 (fb_69b32c5fdcbf): R03 fired
    # "Nf3. Pins the knight on f6 against the queen on d8" — knight Nf3
    # can't pin (knights aren't sliders), so the pin must have been
    # pre-existing in the position. R03 assumed the played move CREATED
    # the pin (match_kind: played_move) but the detector emitted ANY
    # pin geometry in the post-move board. Fix: compute the delta vs
    # board_before, emit only pins the played move actually created.
    _aligned_after = _aligned_pieces_evidence(board_after, own_color)
    _aligned_before = _aligned_pieces_evidence(board_before, own_color)
    _before_keys = {
        (s["attacker_square"], s["front_piece_square"], s["rear_piece_square"])
        for s in _aligned_before
    }
    # Also dedup by the target pair (front, rear): a slider that slides
    # along its existing pin line (e.g. Bc5→Bb6 keeps pinning f2 against
    # the king on g1) gets a NEW attacker_square in the after-position
    # but isn't a new tactical pin. Mohit 2026-05-25 on m8 Bb6 — caption
    # claimed "pin or skewer the front one with a slider" on what was
    # just a bishop retreat along an already-active diagonal.
    _before_target_pairs = {
        (s["front_piece_square"], s["rear_piece_square"])
        for s in _aligned_before
    }
    # And: if the played piece's FROM-square was already on the same ray
    # through (attacker, rear), the pin was geometrically pre-existing
    # even if there was no front piece between then (e.g. a now-blocked
    # version of the same line). Belt-and-braces with the target-pair check.
    def _from_on_same_ray(s: Dict[str, Any]) -> bool:
        try:
            atk = chess.parse_square(s["attacker_square"])
            rear = chess.parse_square(s["rear_piece_square"])
            return played_move.from_square in chess.SquareSet(chess.ray(atk, rear))
        except Exception:
            return False

    aligned_pieces_evidence = [
        s for s in _aligned_after
        if (s["attacker_square"], s["front_piece_square"], s["rear_piece_square"]) not in _before_keys
        and (s["front_piece_square"], s["rear_piece_square"]) not in _before_target_pairs
        and not _from_on_same_ray(s)
    ]
    discovered_attack_evidence = _discovered_attack_evidence(
        board_before, board_after, played_move
    )

    # ── Queen sortie evidence (NOT a boolean — evidence per LAW 3) ─────
    queen_sortie_evidence = _queen_sortie_evidence(
        board_before, played_move, move_history_san, full_move
    )

    # ── PV material walks (commit #4a) ──────────────────────────────────
    # SEE handles immediate exchange material. The PV walk handles multi-
    # ply tactical sequences (e.g. a 4-ply combo that wins a piece on
    # the third move). The two layers stack: SEE for one-shot exchanges,
    # PV-walk for sequences.
    #
    # Convention: both pv_after_played and pv_after_best may or may not
    # include the leading move (depends on engine record format).
    # _normalize_pv_starting_with_move handles both — the played move
    # is prepended only if missing.
    played_pv_normalized = _normalize_pv_starting_with(played_san, pv_after_played)
    best_pv_normalized = (
        _normalize_pv_starting_with(best_move_san, pv_after_best)
        if best_move_san else []
    )
    material_delta_played_cp = _pv_material_delta(
        board_before, played_pv_normalized, own_color
    )
    material_delta_best_cp = _pv_material_delta(
        board_before, best_pv_normalized, own_color
    ) if best_pv_normalized else 0

    # `free_capture` means PURELY "no recapture exists" — there is no
    # opponent piece (of the owner's color) attacking the target square
    # in board_before. This is geometric, not PV-derived: a 4-ply
    # exchange that nets positive material (e.g. bishop-for-knight
    # trade in commit's case A) is NOT a free capture even though
    # net material is positive. The renderer needs to distinguish
    # "took a piece nothing defends" from "won material via favourable
    # trade sequence."
    free_capture = False
    if is_capture and captured_piece is not None:
        owner_color = captured_piece.color
        # Recapturers = pieces of the OWNER's color (the one being
        # captured) that still attack the target after the capture
        # (excluding the moving piece itself; it's now on target_square).
        recapturers = board_after.attackers(owner_color, played_move.to_square)
        free_capture = len(recapturers) == 0

    # ── free_capture_uncontested ──────────────────────────────────────
    # `free_capture` (above) is purely geometric — "no piece attacks the
    # target after the capture." But that's not enough for the
    # user-facing "Free X — nothing recaptures" caption: a player can
    # take a geometrically undefended piece AND pay positional
    # compensation (king exposure, weakened structure) such that the
    # eval barely moves.
    #
    # Parth fb_0467dc2bc44f (exf6 free bishop, swing 0cp vs bishop
    # ~300cp) and fb_5d4a86e264e6 (Kxf7 free pawn, swing 22cp vs pawn
    # 100cp) both flagged "Free X" captions on captures where eval
    # showed no real material gain.
    #
    # Gate: require swing >= half the captured piece's value (mover's
    # perspective). Below that, the move is geometric-free but
    # compensated; the renderer falls back to "wins material in the
    # exchange" / silence rather than the celebratory "Free X" line.
    #
    # `free_capture` itself stays untouched — `_material_explains_eval`'s
    # short-circuit (d7ce40cf #22 USER Rxc6) keeps relying on it.
    # Tradeoff: that celebration moment may downgrade if the
    # "punish opp's hung piece" eval swing is ~0; acceptable since
    # the alternative caption ("wins material in the exchange") is
    # still accurate.
    free_capture_uncontested = False
    if free_capture and captured_piece is not None:
        cap_value_cp = PIECE_VALUE_CP.get(captured_piece.piece_type, 0) or 0
        if eval_before_cp is not None and eval_after_cp is not None:
            swing_white_pov = eval_after_cp - eval_before_cp
            swing_mover_pov = (
                swing_white_pov if own_color == chess.WHITE else -swing_white_pov
            )
            if swing_mover_pov >= cap_value_cp // 2:
                free_capture_uncontested = True
        else:
            # No eval data — fall back to geometric (legacy behavior).
            free_capture_uncontested = True

    # ── Mate threat evidence (commit #4a) ───────────────────────────────
    mate_threat_evidence = _mate_threat_evidence(
        board_before,
        played_san,
        best_move_san,
        eval_before_cp,
        eval_after_cp,
        pv_after_played,
        pv_after_best,
        own_color,
        is_checkmate=is_checkmate,
    )

    # ── Missed tactic evidence (commit #4b) ─────────────────────────────
    # Run shape detectors on pv_after_best to see if the user missed a
    # tactic. Visibility-scored — renderer thresholds via config.
    played_tactics_exist = bool(
        multi_target_attack_evidence
        or [s for s in aligned_pieces_evidence if s.get("rear_piece_value_cp", 0) >= 500]
        or discovered_attack_evidence
    )
    played_is_best_check = (
        best_move_san is not None
        and _normalize_san(played_san) == _normalize_san(best_move_san)
    )
    missed_tactic_evidence = (
        []
        if played_is_best_check
        else _missed_tactic_evidence(
            board_before, pv_after_best, best_move_san, played_tactics_exist
        )
    )

    # ── Opening (uses existing detector) ───────────────────────────────
    opening_name = None
    opening_variation = None
    opening_key = None
    try:
        from services.opening_mastery import detect_opening_from_moves
        # Include the played move so the detector sees the current position
        history_inc_played = list(move_history_san) + [played_san]
        info = detect_opening_from_moves(history_inc_played)
        if info:
            opening_name = info.get("opening_name")
            opening_variation = info.get("variation")
            opening_key = info.get("opening_key")
    except Exception:
        # Detector unavailable — opening facts stay None
        pass

    # ── Game-state flags (purely from eval — no chess judgment) ────────
    # "user_is_winning" / "user_is_losing" are PERSISTENT-STATE flags:
    # they describe whether the user was decisively ahead/behind BEFORE
    # the played move AND remains so AFTER (Mohit overnight 2026-05-21
    # backlog: m20_Qe6_losing flagged that 'you were already losing'
    # framing was inaccurate when the PLAYED MOVE was what made the
    # position losing). Use BOTH eval_before and eval_after — only frame
    # as winning/losing when the user was already in that state.
    # eval_*_cp are from white's POV; flip for black.
    user_eval_before = eval_before_cp
    user_eval_after = eval_after_cp
    if own_color == chess.BLACK:
        if user_eval_before is not None:
            user_eval_before = -user_eval_before
        if user_eval_after is not None:
            user_eval_after = -user_eval_after

    user_is_winning = (
        user_eval_before is not None
        and user_eval_after is not None
        and user_eval_before >= EVAL_WINNING_THRESHOLD_CP
        and user_eval_after >= EVAL_WINNING_THRESHOLD_CP
    )
    user_is_losing = (
        user_eval_before is not None
        and user_eval_after is not None
        and user_eval_before <= EVAL_LOSING_THRESHOLD_CP
        and user_eval_after <= EVAL_LOSING_THRESHOLD_CP
    )

    # ── Move-history facts ─────────────────────────────────────────────
    move_index = len(move_history_san)  # 0-based ply index of the played move

    # ── Move-principle facts (P2b) ─────────────────────────────────────
    played_move_principle = _classify_move_principle(board_before, played_move)
    _best_mv = None
    if best_move_san:
        try:
            _best_mv = board_before.parse_san(best_move_san)
        except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
            _best_mv = None
    best_move_principle = _classify_move_principle(board_before, _best_mv)
    # WHY the engine's best move is good (principle OR trade/win) — for the law that
    # every recommended move needs its why (feedback_explain_why_recommended_move_good).
    best_move_why = _recommended_move_why(board_before, _best_mv)

    # DISTINGUISH GATE (2026-07-01, docs/reasoning_correctness_scope.md): a "why the better
    # move is good" that is ALSO true of the move the user PLAYED explains nothing — "Be7
    # was stronger, develops a piece" (but Bc5 also develops); "Rd8 was better — moves your
    # rook out of danger" (but Rc8 also escapes). Null it so NO surface (R12 template or the
    # why-better append) can crown a move with a reason that doesn't distinguish the choice.
    # Mohit 2026-07-01: "Bc5 is also development, something is not good here."
    if best_move_why and played_move is not None and _best_mv is not None and played_move != _best_mv:
        try:
            _played_move_why = _recommended_move_why(board_before, played_move)
            if _played_move_why and _played_move_why == best_move_why:
                best_move_why = None
        except Exception:
            pass

    # Queen-chase (verifiable-true): a NON-check, NON-capture queen move that's a real
    # mistake, met by a NON-capturing lower piece attacking the queen → the queen must
    # move, losing time. Gated to pure sorties (recaptures/grabs are recapture-choice or
    # material, handled elsewhere). Loop-converged 2026-06-20: 61% are chase-as-headline;
    # the rest are true-but-secondary, so this is wired LOW priority (fallback only).
    queen_chased_by_reply = False
    queen_chaser_piece = None
    try:
        if (moving_piece_type == chess.QUEEN and not is_check and not is_capture
                and cp_loss >= 40 and pv_after_played):
            _rb = board_after.copy()
            _rmv = _rb.parse_san(pv_after_played[0])
            _rpc = _rb.piece_at(_rmv.from_square)
            if (_rpc and _rpc.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP)
                    and not _rb.is_capture(_rmv)):
                _rb.push(_rmv)
                if played_move.to_square in _rb.attacks(_rmv.to_square):
                    queen_chased_by_reply = True
                    queen_chaser_piece = PIECE_TYPE_NAMES.get(_rpc.piece_type)
    except Exception:
        pass

    # Developing minor newly aiming at an enemy non-pawn piece — powers the
    # tier-2 develop "eyeing your {piece}" upgrade (esp. opponent developing
    # moves; Parth liked gold's "lining the bishop up at your center"). Board-
    # verified: the developed piece literally attacks that square. 2026-06-23.
    developed_eyes_piece = None
    developed_eyes_square = None
    try:
        _mp = board_before.piece_at(played_move.from_square)
        if _mp and _mp.piece_type in (chess.KNIGHT, chess.BISHOP):
            _br = 0 if _mp.color == chess.WHITE else 7
            if (chess.square_rank(played_move.from_square) == _br
                    and chess.square_rank(played_move.to_square) != _br):
                _enemy = not _mp.color
                _center_sqs = {chess.D4, chess.E4, chess.D5, chess.E5}
                _cands = []
                for _s in board_after.attacks(played_move.to_square):
                    _q = board_after.piece_at(_s)
                    if not (_q and _q.color == _enemy):
                        continue
                    # any minor/major piece, OR a pawn on a central square (the
                    # "lining up on the long diagonal, watch that e5 pawn" case).
                    if _q.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) \
                            or (_q.piece_type == chess.PAWN and _s in _center_sqs):
                        _cands.append((_s, _q.piece_type))
                if _cands:
                    _pv2 = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3}
                    _cands.sort(key=lambda x: -_pv2.get(x[1], 0))
                    developed_eyes_piece = PIECE_TYPE_NAMES.get(_cands[0][1], "piece")
                    developed_eyes_square = chess.square_name(_cands[0][0])
    except Exception:
        pass

    # ── Build the facts dict ───────────────────────────────────────────
    facts: Dict[str, Any] = {
        # ENGINE TRUTH (pass-through)
        "cp_loss": cp_loss,
        "developed_eyes_piece": developed_eyes_piece,
        "developed_eyes_square": developed_eyes_square,
        "eval_before_cp": eval_before_cp,
        "eval_after_cp": eval_after_cp,
        "best_move_san": best_move_san,
        "played_san": played_san,
        "played_is_best": played_is_best,
        "played_move_principle": played_move_principle,
        "best_move_principle": best_move_principle,
        "best_move_why": best_move_why,
        "queen_chased_by_reply": queen_chased_by_reply,
        "queen_chaser_piece": queen_chaser_piece,
        "pv_after_played": list(pv_after_played),
        "pv_after_best": list(pv_after_best),

        # POSITION FACTS
        "fen_before": fen_before,
        "fen_after": board_after.fen(),
        "from_square": from_square,
        "target_square": target_square,
        "moving_piece_type": PIECE_TYPE_NAMES.get(moving_piece_type) if moving_piece_type else None,
        "moving_piece_color": "white" if own_color == chess.WHITE else "black",
        "is_capture": is_capture,
        "captured_piece_type": captured_piece_type_name,
        "is_check": is_check,
        "is_checkmate": is_checkmate,
        "is_castling": is_castling,
        "is_promotion": is_promotion,
        "is_forced_recapture": forced_recapture,
        "is_pawn_move": moving_piece_type == chess.PAWN,

        # ATTACK / DEFENSE — RAW LISTS (pure geometry, no judgment)
        "attackers_on_target": attackers_on_target,
        "defenders_on_target": defenders_on_target,
        "attacker_count": len(attackers_on_target),
        "defender_count": len(defenders_on_target),

        # EFFECTIVE PARTICIPANTS (SEE-filtered, pin-aware)
        # These are the pieces that ACTUALLY take part in the exchange
        # sequence — renderer rules should prefer these over raw lists
        # for trigger logic. Raw lists remain available for reference.
        "effective_attackers_on_target": effective_attackers,
        "effective_defenders_on_target": effective_defenders,

        # PHASE / MOVE INDEX
        "phase": phase,
        "move_index": move_index,
        "full_move_number": full_move,

        # OPENING (best-effort; None when no match)
        "opening_name": opening_name,
        "opening_variation": opening_variation,
        "opening_key": opening_key,
        "is_book_move": opening_name is not None and move_index <= 12,

        # GAME-STATE FLAGS (purely eval-derived)
        "user_is_winning": user_is_winning,
        "user_is_losing": user_is_losing,

        # SESSION CONTEXT (not chess truth — caller-supplied). Optional;
        # rules with perspective-specific voicing read this to flip "you"
        # vs "they" framing. Bend #5 — without it the renderer can't
        # tell a user's castling from an opponent's castling.
        "mover_is_user": mover_is_user,

        # EXCHANGE TRUTH (SEE — commit #2)
        "see_played_capture_cp": see_played_capture_cp,
        "target_square_exchange_cp": target_square_exchange_cp,
        "is_exchange_losing": is_exchange_losing,
        "exchange_loss_cp": exchange_loss_cp,
        "threats_created": threats_created,
        "pieces_now_undefended": pieces_now_undefended,

        # OPPONENT REPLY (2026-05-13) — used by R12_blunder WHY composer
        # and any future rule that needs to say "after their reply, ...".
        "opp_reply_san": opp_reply_san,
        "opp_reply_attacks_played_piece": opp_reply_attacks_played_piece,
        "opp_reply_captures_piece_type": opp_reply_captures_piece_type,
        "opp_reply_captures_square": opp_reply_captures_square,
        # Recapture collision (Mohit 2026-06-06, fb_22528b6266b1) —
        # when both played + opp_reply land on the same square the SANs
        # render identically; switch to a recapture-specific template.
        "opp_reply_recaptures_on_played_square": opp_reply_recaptures_on_played_square,
        "played_to_square": played_to_square,
        # WHY-BAD enrichment (2026-06-23) — played move drops material to the reply.
        "played_drops_material": played_drops_material,
        "played_drops_piece": played_drops_piece,
        "played_drops_to_san": played_drops_to_san,
        # OPPONENT FAILURE-MODE (2026-06-06) — opp had a better move and
        # didn't play it. Drives failure_mode_clauses_opp in R12.
        "opp_failure_missed_capture": opp_failure_missed_capture,
        "opp_missed_capture_san": opp_missed_capture_san,
        "opp_missed_capture_piece": opp_missed_capture_piece,
        "opp_missed_capture_square": opp_missed_capture_square,
        "opp_failure_missed_mate": opp_failure_missed_mate,
        "opp_missed_mate_san": opp_missed_mate_san,
        # opp missed a quiet FORK (the danger the user dodged) — Parth QA 2026-06-22
        "opp_failure_missed_tactic": opp_failure_missed_tactic,
        "opp_missed_tactic_san": opp_missed_tactic_san,
        "opp_missed_tactic_desc": opp_missed_tactic_desc,

        # USER MOVE FAILURES (2026-07-14, backlog items #6) — played hangs
        "played_hangs_result": played_hangs_result,
        "played_hangs_square": played_hangs_square,
        "played_hangs_piece": played_hangs_piece,

        # OPPONENT MOVE FAILURES (2026-07-14, backlog items #15, #16) —
        # traded active for inactive, or quiet when threatened
        "opp_traded_active_result": opp_traded_active_result,
        "opp_traded_active_piece": opp_traded_active_piece,
        "opp_traded_active_square": opp_traded_active_square,
        "opp_traded_active_recapture": opp_traded_active_recapture,
        "opp_quiet_threat_result": opp_quiet_threat_result,
        "opp_quiet_threat_piece": opp_quiet_threat_piece,
        "opp_quiet_threat_square": opp_quiet_threat_square,
        "opp_quiet_threat_best": opp_quiet_threat_best,
        # FORK DETECTION (Mohit 2026-06-02, why_played_wrong Phase 2).
        # Drives failure_allows_fork in R12_blunder.json. See in-place
        # comment at the extraction site.
        "opp_reply_creates_fork": opp_reply_creates_fork,
        "fork_target_1": fork_target_1,
        "fork_target_2": fork_target_2,
        "fork_target_1_square": fork_target_1_square,
        "fork_target_2_square": fork_target_2_square,

        # TACTIC-SHAPE EVIDENCE — STRUCTURED, NO LABELS.
        # Names use the GEOMETRIC primitive, not renderer taxonomy.
        # Renderer rules read these and decide whether to say "fork" /
        # "pin" / "skewer" / "x-ray" / "double attack" / "pressure" —
        # the extractor never commits to a coaching word.
        # Raw geometry — complete chess truth, including shapes we do not name.
        # For geometry audits, detector research and regression work ONLY.
        "multi_target_attack_evidence": multi_target_attack_evidence,
        # The PROMOTED view: the subset ChessGuru is willing to call a fork.
        # Every user-facing surface — captions, profile claims, drills — must
        # read this, never the raw list, or one surface will say "check, and it
        # attacks a pawn" while another says "you keep getting forked" about the
        # same move. Derived solely by is_named_fork().
        "named_fork_evidence": named_fork_shapes(multi_target_attack_evidence),
        "aligned_pieces_evidence": aligned_pieces_evidence,
        "discovered_attack_evidence": discovered_attack_evidence,

        # QUEEN SORTIE EVIDENCE (commit #3) — DICT or None, not bool.
        # Renderer reads numbers (move_number, minor_pieces_developed)
        # and decides whether/how to mention.
        "queen_sortie_evidence": queen_sortie_evidence,

        # PV MATERIAL WALKS (commit #4a) — multi-ply tactical material
        # truth that SEE alone can't see. Renderer rules use these to
        # detect long tactical sequences and gate the material primary
        # reason (only fire when the eval swing is explained by
        # material delta — prevents "wins a pawn" from drowning out
        # "creates a mating attack").
        "material_delta_played_cp": material_delta_played_cp,
        "material_delta_best_cp": material_delta_best_cp,
        "free_capture": free_capture,
        "free_capture_uncontested": free_capture_uncontested,

        # MATE THREAT EVIDENCE (commit #4a) — highest priority reason.
        # When present, any primary_reason picker MUST prefer this
        # over tactic/material reasons. Mate is essence; everything
        # else is consequence.
        "mate_threat_evidence": mate_threat_evidence,

        # MISSED TACTIC EVIDENCE (commit #4b) — list of structured
        # evidence dicts with human_visibility_score. Renderer applies
        # its own visibility threshold via caption-renderer config.
        "missed_tactic_evidence": missed_tactic_evidence,

        # PRIMARY REASON (commit #4b) — see extract_primary_reason for
        # priority order. Computed AFTER all other facts are built so
        # the scorer has the full dict to read from.
        "primary_reason": None,  # populated below after the dict is built

        # PRINCIPLES VIOLATED (the teaching layer) — list of detector
        # outputs from caption_principles.py. Each entry has:
        #   {principle_id, evidence, engine_endorsement,
        #    aligned_moves_offered}
        # Suppression + priority happen at the V5 wiring layer; this
        # list is the raw detector output. Ships one detector per
        # commit per feedback_design_clean_code_leaky.md.
        "principles_violated": [],  # populated below
    }

    # Compute primary_reason using the now-complete facts dict.
    facts["primary_reason"] = extract_primary_reason(facts)

    # Run principle detectors. Pure functions of (facts, board_before).
    facts["principles_violated"] = _principles_violated(facts, board_before)

    # Lost-defender lead clause (Mohit 2026-05-25). When TAC_HANGING_PIECE
    # fires with trigger=lost_defender on a user move and the piece left
    # hanging is the user's own, R12_blunder can compose a "you moved your
    # {piece} away from defending {square}" lead that pairs with the
    # better-move why_clause. For a 1200 the act of removing the
    # defender IS the teachable mistake; the caption must say WHY the
    # move was wrong, not just what was better.
    #
    # Parth fb_e98ce18cc5a8: DO NOT emit this clause when the user was IN
    # CHECK before the move. The phrasing "you moved your king away from
    # defending X" implies the user had a choice; for a forced check
    # escape, the user had no choice — and the caption was wrong on its
    # face. Suppress the lead clause so the caption falls through to the
    # plain "X is a mistake. Y was better. {why_clause}" form.
    facts["lost_defender_lead_clause"] = ""
    if not board_before.is_check():
        for ev in facts["principles_violated"]:
            if ev.get("principle_id") != "TAC_HANGING_PIECE":
                continue
            e = ev.get("evidence") or {}
            if e.get("trigger") != "lost_defender":
                continue
            if not e.get("mover_is_user"):
                continue
            moved_piece = e.get("lost_defender_piece")
            hanging_sq = e.get("hanging_piece_square")
            if moved_piece and hanging_sq:
                facts["lost_defender_lead_clause"] = (
                    f"you moved your {moved_piece} away from defending {hanging_sq}"
                )
            break

    return facts


# ────────────────────────────────────────────────────────────────────
# CLI — pure replayability per LAW 4
# ────────────────────────────────────────────────────────────────────

def _main() -> int:
    p = argparse.ArgumentParser(
        description="Extract caption facts for a single move. Pure function, "
                    "no DB access. Output is JSON. Used to inspect what the "
                    "extractor sees for any (FEN, move) pair without booting "
                    "the rest of the app."
    )
    p.add_argument("--fen", required=True,
                   help="FEN of the position BEFORE the move.")
    p.add_argument("--move", required=True,
                   help="The played move in SAN (e.g. Nf3).")
    p.add_argument("--best", default=None,
                   help="The engine's best move in SAN.")
    p.add_argument("--eval-before", type=int, default=None,
                   help="Eval in centipawns from white's POV before the move.")
    p.add_argument("--eval-after", type=int, default=None,
                   help="Eval in centipawns from white's POV after the move.")
    p.add_argument("--cp-loss", type=int, default=0,
                   help="cp_loss from the side-to-move's POV.")
    p.add_argument("--pv-played", default="",
                   help="Space-separated SAN list of pv_after_played.")
    p.add_argument("--pv-best", default="",
                   help="Space-separated SAN list of pv_after_best.")
    p.add_argument("--history", default="",
                   help="Space-separated SAN list of moves played BEFORE the position.")
    p.add_argument("--full-move", type=int, default=None,
                   help="Full move number.")
    args = p.parse_args()

    facts = extract_facts(
        fen_before=args.fen,
        played_san=args.move,
        best_move_san=args.best,
        eval_before_cp=args.eval_before,
        eval_after_cp=args.eval_after,
        cp_loss=args.cp_loss,
        pv_after_played=args.pv_played.split() if args.pv_played else [],
        pv_after_best=args.pv_best.split() if args.pv_best else [],
        move_history_san=args.history.split() if args.history else [],
        full_move_number=args.full_move,
    )
    json.dump(facts, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    # Allow `python -m services.caption_facts ...` from backend/ root
    sys.exit(_main())
