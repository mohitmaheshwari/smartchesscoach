"""Bounded branch evidence for the central caption pipeline.

This module owns evidence transport, never chess labels or teaching prose.
Only the background writer may call a provider or engine. Readers validate
the packet against the unchanged source row and replay its legal moves.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from typing import Any, Mapping, Sequence

import chess

from services.stored_line_verifier import parse_legal_move, replay_stored_line

SCHEMA_VERSION = "candidate_caption_evidence.v1"
POLICY_VERSION = "candidate_budget.2026-09-10"
HUMAN_MASS = 0.80
HUMAN_FLOOR = 3
HUMAN_CAP = 8
TOTAL_CAP = 10
MOMENT_CAP = 3
ENRICHMENT_FLAG = "CANDIDATE_CAPTION_ENRICHMENT_ENABLED"
VISIBLE_FLAG = "CANDIDATE_CAUSAL_CAPTIONS_ENABLED"
LESSON_FLAG = "CANDIDATE_LESSON_REASONS_ENABLED"


def enabled(name: str) -> bool:
    return os.getenv(name, "false").lower().strip() in {"true", "1", "yes", "on"}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_identity(row: Mapping[str, Any]) -> dict:
    """Bind the original analysis, including both branches and score direction."""
    board, played, best = root_moves(row)
    return {
        "fen_before": board.fen(),
        "played_move_uci": played.uci(),
        "best_move_uci": best.uci(),
        "eval_before": row.get("eval_before"),
        "eval_after": row.get("eval_after"),
        "cp_loss": int(row.get("cp_loss") or 0),
        "pv_after_played": list(row.get("pv_after_played") or ()),
        "pv_after_best": list(row.get("pv_after_best") or ()),
        "is_opponent_move": bool(row.get("is_opponent_move")),
        "move_number": int(row.get("move_number") or 0),
    }


def root_moves(row: Mapping[str, Any]) -> tuple[chess.Board, chess.Move, chess.Move]:
    board = chess.Board(str(row.get("fen_before") or ""))
    if not board.is_valid():
        raise ValueError("invalid_root")
    played = parse_legal_move(board, row.get("move_uci") or row.get("move_san") or row.get("move"))
    best = parse_legal_move(board, row.get("best_move_uci") or row.get("best_move_san") or row.get("best_move"))
    if played is None or best is None:
        raise ValueError("missing_legal_authoritative_move")
    return board, played, best


def select_candidates(row: Mapping[str, Any], *, human=None, context=None,
                      exact_moves: Sequence[str] = ()) -> tuple[str, ...]:
    board, played, best = root_moves(row)
    selected = list(dict.fromkeys((played.uci(), best.uci())))
    # Exact candidates are supplied by a verified authority at the writer.
    for raw in exact_moves[:2]:
        move = parse_legal_move(board, raw)
        if move is None:
            raise ValueError("illegal_exact_candidate")
        if move.uci() not in selected:
            selected.append(move.uci())
    if human is not None:
        # A caller holding the live context must prove the join.  The
        # background caption writer may instead consume the already-validated
        # immutable HumanPolicyEvidence stored on this exact row; in that case
        # its signed contract and canonical FEN are the available identity.
        if context is not None:
            from services.human_policy_runtime import human_policy_evidence_matches_context
            if not human_policy_evidence_matches_context(human, context):
                return tuple(selected)
        elif " ".join(human.fen.split()[:4]) != " ".join(board.fen().split()[:4]):
            return tuple(selected)
        mass = 0.0
        for index, item in enumerate(human.probabilities[:HUMAN_CAP], 1):
            mass += item.probability
            if item.move_uci not in selected and len(selected) < TOTAL_CAP:
                selected.append(item.move_uci)
            if index >= HUMAN_FLOOR and mass >= HUMAN_MASS:
                break
    return tuple(selected)


@dataclass(frozen=True)
class CandidateBranch:
    root_uci: str
    moves_uci: tuple[str, ...]
    moves_san: tuple[str, ...]
    final_fen: str
    source: str
    score_white_cp: int | None = None
    mate_white: int | None = None

    @classmethod
    def from_line(cls, board: chess.Board, root: chess.Move, continuation,
                  *, source: str, score_white_cp=None, mate_white=None):
        replay = replay_stored_line(board, root, continuation)
        if not replay.complete or not replay.replayed_uci:
            raise ValueError("incomplete_branch")
        if source not in {"stored_stockfish", "candidate_stockfish"}:
            raise ValueError("unknown_branch_authority")
        for value in (score_white_cp, mate_white):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError("invalid_score")
        return cls(root.uci(), replay.replayed_uci, replay.replayed_san,
                   replay.final_fen, source, score_white_cp, mate_white)

    def document(self):
        doc = asdict(self)
        doc["moves_uci"] = list(self.moves_uci)
        doc["moves_san"] = list(self.moves_san)
        return doc


@dataclass(frozen=True)
class CandidateEvidence:
    fen: str
    source_fingerprint: str
    candidates: tuple[str, ...]
    branches: tuple[CandidateBranch, ...]
    provenance: Mapping[str, Any]

    def document(self) -> dict:
        result = {
            "schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
            "fen": self.fen, "source_fingerprint": self.source_fingerprint,
            "candidates": list(self.candidates),
            "branches": [branch.document() for branch in self.branches],
            "provenance": dict(self.provenance),
        }
        return {**result, "fingerprint": fingerprint(result)}

    def branch(self, uci: str) -> CandidateBranch | None:
        return next((branch for branch in self.branches if branch.root_uci == uci), None)

    @classmethod
    def from_document(cls, document: Mapping[str, Any], row: Mapping[str, Any]):
        raw = dict(document)
        supplied = raw.pop("fingerprint", None)
        if supplied != fingerprint(raw):
            raise ValueError("packet_fingerprint_mismatch")
        if raw.get("schema_version") != SCHEMA_VERSION or raw.get("policy_version") != POLICY_VERSION:
            raise ValueError("obsolete_packet")
        board, played, best = root_moves(row)
        if raw.get("source_fingerprint") != fingerprint(source_identity(row)) or raw.get("fen") != board.fen():
            raise ValueError("source_mismatch")
        candidates = tuple(raw.get("candidates") or ())
        if (not 1 <= len(candidates) <= TOTAL_CAP or len(set(candidates)) != len(candidates)
                or any(parse_legal_move(board, uci) is None for uci in candidates)
                or not {played.uci(), best.uci()}.issubset(candidates)):
            raise ValueError("invalid_candidates")
        provenance = raw.get("provenance") or {}
        if provenance.get("source") != "stored_stockfish" or not provenance.get("writer_version"):
            raise ValueError("missing_provenance")
        branches = []
        for data in raw.get("branches") or ():
            root = parse_legal_move(board, data.get("root_uci"))
            if root is None or root.uci() not in candidates:
                raise ValueError("branch_outside_candidates")
            branch = CandidateBranch.from_line(board, root, data.get("moves_uci") or (),
                source=data.get("source"), score_white_cp=data.get("score_white_cp"),
                mate_white=data.get("mate_white"))
            if branch.document() != dict(data):
                raise ValueError("branch_replay_mismatch")
            if branch.source == "candidate_stockfish" and not provenance.get("engine"):
                raise ValueError("missing_engine_provenance")
            branches.append(branch)
        if len({b.root_uci for b in branches}) != len(branches):
            raise ValueError("duplicate_branch")
        return cls(board.fen(), raw["source_fingerprint"], candidates, tuple(branches), provenance)


def collect_candidate_evidence(row: Mapping[str, Any], *, human=None, context=None,
                               engine=None, limit=None, engine_identity=None):
    """Writer-only: reuse stored branches; one restricted search for missing ones.

    Callers own a persistent engine and pass an explicit measured limit.
    An omitted engine always means stored evidence only.
    """
    board, played, best = root_moves(row)
    if human is None and row.get("human_policy_evidence"):
        try:
            from services.human_policy_runtime import HumanPolicyEvidence
            human = HumanPolicyEvidence.from_contract(
                row["human_policy_evidence"]
            )
        except (TypeError, ValueError):
            human = None
    human_accepted = False
    if human is not None:
        if context is not None:
            from services.human_policy_runtime import human_policy_evidence_matches_context
            human_accepted = human_policy_evidence_matches_context(human, context)
        else:
            human_accepted = (
                " ".join(human.fen.split()[:4])
                == " ".join(board.fen().split()[:4])
            )
    candidates = select_candidates(row, human=human, context=context)
    branches = {}
    rejected = []
    for root, field in ((played, "pv_after_played"), (best, "pv_after_best")):
        continuation = row.get(field)
        if not continuation:
            continue
        try:
            branches[root.uci()] = CandidateBranch.from_line(board, root, continuation, source="stored_stockfish")
        except ValueError:
            rejected.append(root.uci())
    missing = [uci for uci in candidates if uci not in branches]
    provenance = {"source": "stored_stockfish", "writer_version": SCHEMA_VERSION}
    if human_accepted:
        provenance["human"] = {
            "provider": human.provider,
            "provider_version": human.provider_version,
            "model_sha256": human.model_sha256,
            "input_fingerprint": human.input_fingerprint,
            "history_sha256": human.history_sha256,
        }
    if missing and engine is not None:
        if limit is None or not engine_identity:
            raise ValueError("candidate_search_requires_budget_and_provenance")
        results = engine.analyse(board, limit, root_moves=[chess.Move.from_uci(uci) for uci in missing],
                                 multipv=len(missing))
        if isinstance(results, Mapping):
            results = [results]
        for info in results:
            pv = info.get("pv") or ()
            if not pv or pv[0].uci() not in missing or info.get("lowerbound") or info.get("upperbound"):
                continue
            score = info.get("score")
            if score is None:
                continue
            branch = CandidateBranch.from_line(board, pv[0], [m.uci() for m in pv], source="candidate_stockfish",
                score_white_cp=score.white().score(), mate_white=score.white().mate())
            branches[branch.root_uci] = branch
        provenance["engine"] = dict(engine_identity)
    packet = CandidateEvidence(board.fen(), fingerprint(source_identity(row)), candidates,
                               tuple(branches[uci] for uci in candidates if uci in branches), provenance)
    return packet, {"candidates": len(candidates), "reused": len(candidates) - len(missing),
                    "missing": len(candidates) - len(branches), "invalid_stored": len(rejected)}


def candidate_packet_state(
    document: Mapping[str, Any] | None,
    row: Mapping[str, Any],
) -> str:
    """Classify one stored packet without repairing or interpreting it."""
    if not document:
        return "missing"
    try:
        CandidateEvidence.from_document(document, row)
        return "current"
    except (TypeError, ValueError) as exc:
        reason = str(exc)
        if reason == "obsolete_packet":
            return "stale"
        if reason == "source_mismatch":
            return "changed"
        return "rejected"
