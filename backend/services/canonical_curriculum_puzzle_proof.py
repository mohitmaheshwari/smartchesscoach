"""Exact curriculum proofs for opening, trap and endgame puzzles.

This is an adapter, not another chess-content catalogue. Candidate matches
come from the validated canonical curriculum. Independent verification replays
the authored line or checks committed Syzygy/pinned-engine evidence. It never
invokes Stockfish, an LLM or a network service.

The proof is intentionally exact. A transposition or similar-looking position
is not enough to name an opening or trap; broader detectors need their own
corpus evidence and quality authorization.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import chess
import chess.pgn

from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.verified_puzzle_admission import DetectorProof, VerifierProof


CURRICULUM_PROOF_VERSION = "canonical_curriculum_puzzle_proof.v2"
OPENING_QUALITY_ID = "curriculum:opening_exact_decision"
TRAP_QUALITY_ID = "curriculum:trap_exact_decision"
OPENING_PLAN_QUALITY_ID = "curriculum:opening_plan_exact_decision"
ENDGAME_QUALITY_ID = "curriculum:endgame_exact_position"
OPENING_POSITION_QUALITY_ID = "curriculum:opening_exact_position"
TRAP_POSITION_QUALITY_ID = "curriculum:trap_exact_position"
OPENING_PLAN_POSITION_QUALITY_ID = "curriculum:opening_plan_exact_position"

_TABLEBASE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "corpus_snapshots"
    / "curriculum_endgame_tablebase_2026-08-29.json"
)


@dataclass(frozen=True)
class CurriculumProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str
    broad_category: str
    acceptable_moves: Tuple[str, ...] = ()
    priority: int = 0


@dataclass(frozen=True)
class ExactEndgameTransfer:
    """Verified canonical identity for one exact endgame position."""

    concept_id: str
    content_id: str
    position_index: int
    expected_uci: str
    evidence_method: str


@dataclass(frozen=True)
class _LineDecision:
    concept_id: str
    family: str
    expected_uci: str
    prefix_uci: Tuple[str, ...]
    source_ref: str
    mode: str
    lesson_side: str = ""
    explanation: str = ""
    lesson_rule: str = ""


@dataclass(frozen=True)
class _EndgameDecision:
    concept_id: str
    content_id: str
    position_index: int
    fen: str
    expected_uci: str
    accepted_uci: Tuple[str, ...]
    evidence_method: str


def _normalized_fen(board_or_fen: Any) -> str:
    board = (
        board_or_fen
        if isinstance(board_or_fen, chess.Board)
        else chess.Board(str(board_or_fen))
    )
    return " ".join(board.fen().split()[:4])


def _uci_line(moves: Iterable[str]) -> Optional[Tuple[str, ...]]:
    board = chess.Board()
    result = []
    try:
        for raw in moves:
            move = board.parse_san(str(raw))
            result.append(move.uci())
            board.push(move)
    except (ValueError, AssertionError):
        return None
    return tuple(result)


def _history_from_pgn(source_pgn: str, source_ply: int) -> Optional[Tuple[str, ...]]:
    try:
        game = chess.pgn.read_game(io.StringIO(source_pgn))
        if game is None:
            return None
        moves = tuple(move.uci() for move in game.mainline_moves())
        if source_ply < 0 or source_ply >= len(moves):
            return None
        return moves[:source_ply]
    except (ValueError, TypeError, IndexError):
        return None


@lru_cache(maxsize=1)
def _opening_index() -> Mapping[Tuple[Tuple[str, ...], str], Tuple[_LineDecision, ...]]:
    from services.curriculum_content_validator import get_publishable_content_ids
    from services.opening_theory_json_service import (
        get_all_lesson_move_paths,
        get_opening_theory,
    )

    grouped: Dict[Tuple[Tuple[str, ...], str], list[_LineDecision]] = {}
    for opening_id in sorted(get_publishable_content_ids("openings")):
        opening = get_opening_theory(opening_id) or {}
        lesson_side = str(opening.get("color") or "white").lower()
        rules = opening.get("golden_rules") or opening.get("common_learnings") or ()
        lesson_rule = str(rules[0]).strip() if rules else ""
        for path_index, steps in enumerate(get_all_lesson_move_paths(opening_id)):
            line = _uci_line(step.get("move") for step in steps)
            if line is None:
                continue
            for index, expected in enumerate(line):
                step = steps[index]
                if str(step.get("side") or "").lower() != lesson_side:
                    continue
                decision = _LineDecision(
                    concept_id=f"opening:{opening_id}", family="opening",
                    expected_uci=expected, prefix_uci=line[:index],
                    source_ref=opening_id, mode=f"path:{path_index}",
                    lesson_side=lesson_side,
                    explanation=str(step.get("explanation") or "").strip(),
                    lesson_rule=lesson_rule,
                )
                grouped.setdefault((decision.prefix_uci, expected), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


@lru_cache(maxsize=1)
def _trap_index() -> Mapping[Tuple[Tuple[str, ...], str], Tuple[_LineDecision, ...]]:
    from trick_library_service import TRAPS_DATABASE, get_trap_for_practice

    grouped: Dict[Tuple[Tuple[str, ...], str], list[_LineDecision]] = {}
    for trap_key in sorted(TRAPS_DATABASE):
        for mode in ("avoidance", "execution"):
            practice = get_trap_for_practice(trap_key, mode)
            if not practice:
                continue
            line = _uci_line(practice.get("full_sequence") or ())
            if line is None:
                continue
            decisions = practice.get("user_moves") or ()
            if mode == "execution":
                decisions = [item for item in decisions if item.get("is_winning")]
            for raw in decisions:
                try:
                    index = int(raw["index"])
                    expected = line[index]
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
                decision = _LineDecision(
                    concept_id=f"trap:{practice.get('content_id') or trap_key}",
                    family="trap", expected_uci=expected,
                    prefix_uci=line[:index],
                    source_ref=trap_key,
                    mode=mode,
                )
                grouped.setdefault((decision.prefix_uci, expected), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


@lru_cache(maxsize=1)
def _opening_plan_index() -> Mapping[Tuple[Tuple[str, ...], str], Tuple[_LineDecision, ...]]:
    from trick_library_service import (
        OPENING_IDEAS_DATABASE,
        get_opening_idea_for_practice,
    )

    grouped: Dict[Tuple[Tuple[str, ...], str], list[_LineDecision]] = {}
    for lesson_key in sorted(OPENING_IDEAS_DATABASE):
        practice = get_opening_idea_for_practice(lesson_key, "execution")
        if not practice:
            continue
        line = _uci_line(practice.get("full_sequence") or ())
        if line is None:
            continue
        for raw in practice.get("user_moves") or ():
            try:
                index = int(raw["index"])
                expected = line[index]
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            decision = _LineDecision(
                concept_id=(
                    f"opening_plan:{practice.get('content_id') or lesson_key}"
                ),
                family="opening_plan",
                expected_uci=expected,
                prefix_uci=line[:index],
                source_ref=lesson_key,
                mode="execution",
                lesson_side=str(practice.get("user_color") or "").lower(),
                explanation=str(raw.get("explanation") or "").strip(),
                lesson_rule=str(practice.get("learning_goal") or "").strip(),
            )
            grouped.setdefault((decision.prefix_uci, expected), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


def _load_tablebase_evidence() -> Mapping[Tuple[str, int], Mapping[str, Any]]:
    with _TABLEBASE_PATH.open("r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    return {
        (str(entry.get("content_id")), int(entry.get("position_index"))): entry
        for entry in snapshot.get("entries", ())
    }


@lru_cache(maxsize=1)
def _endgame_index() -> Mapping[str, Tuple[_EndgameDecision, ...]]:
    from services.endgame_theory_service import (
        get_all_categories,
        get_verified_lesson_data,
    )

    tablebase = _load_tablebase_evidence()
    grouped: Dict[str, list[_EndgameDecision]] = {}
    for category in get_all_categories():
        category_key = str(category["key"])
        for lesson_summary in category.get("lessons") or ():
            lesson_key = str(lesson_summary["key"])
            content_id = f"{category_key}/{lesson_key}"
            lesson = get_verified_lesson_data(category_key, lesson_key)
            if not lesson:
                continue
            for index, position in enumerate(lesson.get("positions") or ()):
                try:
                    board = chess.Board(str(position["fen"]))
                    expected = chess.Move.from_uci(
                        str(position["correct_move_uci"]).lower()
                    )
                    if expected not in board.legal_moves:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue

                evidence = tablebase.get((content_id, index))
                accepted: Tuple[str, ...] = (expected.uci(),)
                method = "pinned_stockfish"
                if len(board.piece_map()) <= 7:
                    if not evidence or not evidence.get("preserves_wdl"):
                        continue
                    preserving = {
                        str(item.get("uci") or "").lower()
                        for item in evidence.get("preserving_moves") or ()
                    }
                    preserving.discard("")
                    if expected.uci() not in preserving:
                        continue
                    # WDL-preserving moves are useful objective evidence, but
                    # only the authored move demonstrates this exact lesson.
                    accepted = (expected.uci(),)
                    method = "committed_syzygy"
                else:
                    verification = position.get("verification") or {}
                    if not (
                        verification.get("method") == "stockfish"
                        and verification.get("status") == "verified"
                        and verification.get("fen") == board.fen()
                        and verification.get("move_uci") == expected.uci()
                    ):
                        continue

                decision = _EndgameDecision(
                    concept_id=f"endgame:{content_id}",
                    content_id=content_id,
                    position_index=index,
                    fen=board.fen(),
                    expected_uci=expected.uci(),
                    accepted_uci=accepted,
                    evidence_method=method,
                )
                grouped.setdefault(_normalized_fen(board), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


def _verify_endgame_decision(
    decision: _EndgameDecision,
) -> Optional[Tuple[str, ...]]:
    """Freshly check canonical position plus committed objective evidence."""
    from services.endgame_theory_service import get_verified_lesson_data

    try:
        category_key, lesson_key = decision.content_id.split("/", 1)
        lesson = get_verified_lesson_data(category_key, lesson_key)
        position = (lesson or {}).get("positions", ())[decision.position_index]
        board = chess.Board(str(position["fen"]))
        expected = str(position["correct_move_uci"]).lower()
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    if (
        board.fen() != decision.fen
        or expected != decision.expected_uci
        or chess.Move.from_uci(expected) not in board.legal_moves
    ):
        return None

    if len(board.piece_map()) <= 7:
        evidence = _load_tablebase_evidence().get(
            (decision.content_id, decision.position_index)
        )
        if not evidence or not evidence.get("preserves_wdl"):
            return None
        result_preserving = tuple(sorted({
            str(item.get("uci") or "").lower()
            for item in evidence.get("preserving_moves") or ()
            if item.get("uci")
        }))
        return (expected,) if expected in result_preserving else None

    verification = position.get("verification") or {}
    if not (
        verification.get("method") == "stockfish"
        and verification.get("status") == "verified"
        and verification.get("fen") == board.fen()
        and verification.get("move_uci") == expected
    ):
        return None
    return (expected,)


def _unique_decision(
    matches: Iterable[_LineDecision],
) -> Optional[_LineDecision]:
    choices = list(matches)
    by_identity = {
        (
            item.concept_id,
            item.source_ref,
            item.mode if item.family in {"trap", "opening_plan"} else item.lesson_side,
        ): item
        for item in choices
    }
    return next(iter(by_identity.values())) if len(by_identity) == 1 else None


def _fen_after_prefix(prefix: Tuple[str, ...]) -> Optional[str]:
    board = chess.Board()
    try:
        for uci in prefix:
            board.push_uci(uci)
    except (ValueError, AssertionError):
        return None
    return _normalized_fen(board)


@lru_cache(maxsize=1)
def _opening_position_index(
) -> Mapping[Tuple[str, str], Tuple[_LineDecision, ...]]:
    grouped: Dict[Tuple[str, str], list[_LineDecision]] = {}
    seen = set()
    for decisions in _opening_index().values():
        for decision in decisions:
            identity = (
                decision.concept_id,
                decision.prefix_uci,
                decision.expected_uci,
            )
            if identity in seen:
                continue
            seen.add(identity)
            fen = _fen_after_prefix(decision.prefix_uci)
            if fen:
                grouped.setdefault((fen, decision.expected_uci), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


@lru_cache(maxsize=1)
def _trap_position_index(
) -> Mapping[Tuple[str, str], Tuple[_LineDecision, ...]]:
    grouped: Dict[Tuple[str, str], list[_LineDecision]] = {}
    seen = set()
    for decisions in _trap_index().values():
        for decision in decisions:
            identity = (
                decision.concept_id,
                decision.prefix_uci,
                decision.expected_uci,
            )
            if identity in seen:
                continue
            seen.add(identity)
            fen = _fen_after_prefix(decision.prefix_uci)
            if fen:
                grouped.setdefault((fen, decision.expected_uci), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


@lru_cache(maxsize=1)
def _opening_plan_position_index(
) -> Mapping[Tuple[str, str], Tuple[_LineDecision, ...]]:
    grouped: Dict[Tuple[str, str], list[_LineDecision]] = {}
    seen = set()
    for decisions in _opening_plan_index().values():
        for decision in decisions:
            identity = (
                decision.concept_id,
                decision.prefix_uci,
                decision.expected_uci,
            )
            if identity in seen:
                continue
            seen.add(identity)
            fen = _fen_after_prefix(decision.prefix_uci)
            if fen:
                grouped.setdefault((fen, decision.expected_uci), []).append(decision)
    return {key: tuple(value) for key, value in grouped.items()}


def _verify_line_decision(decision: _LineDecision) -> bool:
    """Freshly replay one canonical line without using the detector index."""
    if decision.family == "opening":
        from services.opening_theory_json_service import get_all_lesson_move_paths

        for steps in get_all_lesson_move_paths(decision.source_ref):
            line = _uci_line(step.get("move") for step in steps)
            index = len(decision.prefix_uci)
            if (
                line is not None
                and index < len(line)
                and line[:index] == decision.prefix_uci
                and line[index] == decision.expected_uci
                and str(steps[index].get("side") or "").lower()
                == decision.lesson_side
            ):
                return True
        return False
    elif decision.family == "trap":
        from trick_library_service import get_trap_for_practice

        practice = get_trap_for_practice(decision.source_ref, decision.mode)
        if not practice:
            return False
        moves = list(practice.get("full_sequence") or ())
        eligible = list(practice.get("user_moves") or ())
        if decision.mode == "execution":
            eligible = [item for item in eligible if item.get("is_winning")]
        eligible_indexes = {
            int(item["index"])
            for item in eligible
            if isinstance(item, Mapping) and "index" in item
        }
    elif decision.family == "opening_plan":
        from trick_library_service import get_opening_idea_for_practice

        practice = get_opening_idea_for_practice(decision.source_ref, "execution")
        if not practice:
            return False
        moves = list(practice.get("full_sequence") or ())
        eligible_indexes = {
            int(item["index"])
            for item in practice.get("user_moves") or ()
            if isinstance(item, Mapping) and "index" in item
        }
    else:
        return False

    line = _uci_line(moves)
    index = len(decision.prefix_uci)
    return bool(
        line is not None
        and index < len(line)
        and index in eligible_indexes
        and line[:index] == decision.prefix_uci
        and line[index] == decision.expected_uci
    )


def _line_bundle(
    decision: _LineDecision,
    *,
    quality_id: str,
    broad_category: str,
    priority: int,
) -> CurriculumProofBundle:
    detector = DetectorProof(
        concept_id=decision.concept_id,
        family=decision.family,
        detector_id=f"canonical_{decision.family}_decision_index",
        detector_version=CURRICULUM_PROOF_VERSION,
        calculation_id="validated_curriculum_prefix_lookup",
        facts=({
            "source_ref": decision.source_ref,
            "mode": decision.mode,
            "decision_ply": len(decision.prefix_uci),
            "lesson_side": decision.lesson_side,
            "explanation": decision.explanation,
            "lesson_rule": decision.lesson_rule,
        },),
        acceptable_moves=(decision.expected_uci,),
        counterfactual={"canonical_move": decision.expected_uci},
    )
    independently_verified = _verify_line_decision(decision)
    verifier = VerifierProof(
        concept_id=decision.concept_id,
        verifier_id=f"independent_{decision.family}_line_replay",
        verifier_version=CURRICULUM_PROOF_VERSION,
        calculation_id="fresh_legal_full_line_reconstruction",
        verified=independently_verified,
        acceptable_moves=(decision.expected_uci,) if independently_verified else (),
        facts=({
            "source_ref": decision.source_ref,
            "mode": decision.mode,
            "exact_prefix_uci": decision.prefix_uci,
        },),
    )
    return CurriculumProofBundle(
        detector=detector,
        verifier=verifier,
        quality_id=quality_id,
        broad_category=broad_category,
        acceptable_moves=(decision.expected_uci,),
        priority=priority,
    )


def _position_bundle(
    decision: _LineDecision,
    *,
    actual_fen: str,
    quality_id: str,
    broad_category: str,
    priority: int,
) -> CurriculumProofBundle:
    replayed_fen = _fen_after_prefix(decision.prefix_uci)
    verified = bool(
        _verify_line_decision(decision)
        and replayed_fen == actual_fen
    )
    detector = DetectorProof(
        concept_id=decision.concept_id,
        family=decision.family,
        detector_id=f"canonical_{decision.family}_position_index",
        detector_version=CURRICULUM_PROOF_VERSION,
        calculation_id="validated_exact_fen_answer_lookup",
        facts=({
            "source_ref": decision.source_ref,
            "mode": decision.mode,
            "matched_fen": actual_fen,
            "lesson_side": decision.lesson_side,
            "explanation": decision.explanation,
            "lesson_rule": decision.lesson_rule,
        },),
        acceptable_moves=(decision.expected_uci,),
        counterfactual={"canonical_move": decision.expected_uci},
    )
    verifier = VerifierProof(
        concept_id=decision.concept_id,
        verifier_id=f"independent_{decision.family}_line_to_fen",
        verifier_version=CURRICULUM_PROOF_VERSION,
        calculation_id="fresh_full_line_reconstruction_to_position",
        verified=verified,
        acceptable_moves=(decision.expected_uci,) if verified else (),
        facts=({
            "source_ref": decision.source_ref,
            "replayed_fen": replayed_fen,
            "actual_fen": actual_fen,
        },),
    )
    return CurriculumProofBundle(
        detector=detector,
        verifier=verifier,
        quality_id=quality_id,
        broad_category=broad_category,
        acceptable_moves=(decision.expected_uci,),
        priority=priority,
    )


def build_exact_line_proofs(
    *,
    source_pgn: Optional[str],
    source_ply: Optional[int],
    best_move_uci: Optional[str],
    cp_loss: Any,
) -> Tuple[CurriculumProofBundle, ...]:
    """Return exact trap/opening proofs for a reconstructed PGN decision."""
    if not source_pgn or source_ply is None or not best_move_uci:
        return ()
    history = _history_from_pgn(source_pgn, source_ply)
    if history is None:
        return ()
    try:
        loss = require_nonnegative_cp_loss(cp_loss)
    except (TypeError, ValueError):
        return ()
    # A low-loss deviation is not evidence that the named line was necessary.
    if loss <= 50:
        return ()

    key = (history, str(best_move_uci).lower())
    proofs = []
    trap = _unique_decision(_trap_index().get(key, ()))
    if trap:
        proofs.append(_line_bundle(
            trap,
            quality_id=TRAP_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=400,
        ))
    opening_plan = _unique_decision(_opening_plan_index().get(key, ()))
    if opening_plan:
        proofs.append(_line_bundle(
            opening_plan,
            quality_id=OPENING_PLAN_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=200,
        ))
    opening = _unique_decision(_opening_index().get(key, ()))
    if opening:
        proofs.append(_line_bundle(
            opening,
            quality_id=OPENING_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=100,
        ))
    return tuple(proofs)


def build_exact_opening_trap_position_proofs(
    *,
    board_before: chess.Board,
    best_move_uci: Optional[str],
    cp_loss: Any,
) -> Tuple[CurriculumProofBundle, ...]:
    """Match the exact full position when legal move order transposed."""
    if not best_move_uci:
        return ()
    try:
        loss = require_nonnegative_cp_loss(cp_loss)
    except (TypeError, ValueError):
        return ()
    if loss <= 50:
        return ()
    fen = _normalized_fen(board_before)
    key = (fen, str(best_move_uci).lower())
    proofs = []
    trap = _unique_decision(_trap_position_index().get(key, ()))
    if trap:
        proofs.append(_position_bundle(
            trap,
            actual_fen=fen,
            quality_id=TRAP_POSITION_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=390,
        ))
    opening_plan = _unique_decision(_opening_plan_position_index().get(key, ()))
    if opening_plan:
        proofs.append(_position_bundle(
            opening_plan,
            actual_fen=fen,
            quality_id=OPENING_PLAN_POSITION_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=190,
        ))
    opening = _unique_decision(_opening_position_index().get(key, ()))
    if opening:
        proofs.append(_position_bundle(
            opening,
            actual_fen=fen,
            quality_id=OPENING_POSITION_QUALITY_ID,
            broad_category="opening_knowledge",
            priority=90,
        ))
    return tuple(proofs)


def build_exact_endgame_proof(
    board_before: chess.Board,
    played_move_uci: Optional[str],
    best_move_uci: Optional[str],
    cp_loss: Any,
) -> Optional[CurriculumProofBundle]:
    """Return an exact canonical endgame proof for this precise position."""
    if not played_move_uci or not best_move_uci:
        return None
    try:
        played = chess.Move.from_uci(str(played_move_uci).lower())
        best = chess.Move.from_uci(str(best_move_uci).lower())
        loss = require_nonnegative_cp_loss(cp_loss)
    except (TypeError, ValueError):
        return None
    if (
        played not in board_before.legal_moves
        or best not in board_before.legal_moves
        or played == best
        or loss <= 50
    ):
        return None
    transfer = match_exact_endgame_transfer(board_before, best_move_uci)
    if transfer is None:
        return None

    detector = DetectorProof(
        concept_id=transfer.concept_id,
        family="endgame",
        detector_id="canonical_endgame_position_index",
        detector_version=CURRICULUM_PROOF_VERSION,
        calculation_id="validated_exact_fen_answer_lookup",
        facts=({
            "content_id": transfer.content_id,
            "position_index": transfer.position_index,
        },),
        acceptable_moves=(transfer.expected_uci,),
        counterfactual={"canonical_move": transfer.expected_uci},
    )
    verifier = VerifierProof(
        concept_id=transfer.concept_id,
        verifier_id="independent_endgame_evidence_verifier",
        verifier_version=CURRICULUM_PROOF_VERSION,
        calculation_id=(
            "committed_syzygy_wdl_preservation"
            if transfer.evidence_method == "committed_syzygy"
            else "pinned_stockfish_evidence_match"
        ),
        verified=True,
        acceptable_moves=(transfer.expected_uci,),
        facts=({
            "content_id": transfer.content_id,
            "position_index": transfer.position_index,
            "evidence_method": transfer.evidence_method,
            "accepted_move_count": 1,
        },),
    )
    return CurriculumProofBundle(
        detector=detector,
        verifier=verifier,
        quality_id=ENDGAME_QUALITY_ID,
        broad_category="endgame_technique",
        acceptable_moves=(transfer.expected_uci,),
        priority=300,
    )


def exact_endgame_lesson_ids() -> Tuple[str, ...]:
    """Canonical lesson identities that own at least one verified position."""
    return tuple(sorted({
        decision.content_id
        for decisions in _endgame_index().values()
        for decision in decisions
    }))


def match_exact_endgame_transfer(
    board_before: chess.Board,
    best_move_uci: Optional[str],
) -> Optional[ExactEndgameTransfer]:
    """Match one exact canonical position and independently verify its answer.

    This is the single public matcher used by both puzzle admission and
    curriculum-mastery adapters. It consumes stored best-move evidence only.
    """
    if not best_move_uci:
        return None
    try:
        best = chess.Move.from_uci(str(best_move_uci).lower())
    except (TypeError, ValueError):
        return None
    if best not in board_before.legal_moves:
        return None
    matches = _endgame_index().get(_normalized_fen(board_before), ())
    by_identity = {
        (item.concept_id, item.content_id, item.position_index): item
        for item in matches
    }
    if len(by_identity) != 1:
        return None
    decision = next(iter(by_identity.values()))
    if best.uci() != decision.expected_uci:
        return None
    independently_accepted = _verify_endgame_decision(decision)
    if independently_accepted != (decision.expected_uci,):
        return None
    return ExactEndgameTransfer(
        concept_id=decision.concept_id,
        content_id=decision.content_id,
        position_index=decision.position_index,
        expected_uci=decision.expected_uci,
        evidence_method=decision.evidence_method,
    )


def clear_curriculum_proof_caches() -> None:
    """Testing/reload hook after canonical curriculum content changes."""
    _opening_index.cache_clear()
    _trap_index.cache_clear()
    _opening_position_index.cache_clear()
    _trap_position_index.cache_clear()
    _endgame_index.cache_clear()
