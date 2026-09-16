"""Truth-preserving adapters for independent PWC V2 shadow candidates.

This module owns no chess knowledge. It projects the repository's canonical,
independently verified curriculum proofs into the shared candidate envelope.
If the engine evidence, exact position, answer set, or canonical content does
not line up, the adapter stays silent or emits a rejected candidate for the
shadow audit. Nothing here is player-visible.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import chess

from .contracts import (
    CandidateFocus,
    CandidateNovelty,
    CandidateTiming,
    CandidateUrgency,
    CoachingCandidate,
    stable_candidate_id,
)

CURRICULUM_ADAPTER_VERSION = "pwc_v2_adapter.canonical_curriculum.v1"
CURRICULUM_PROOF_AUTHORITY = "canonical_curriculum_puzzle_proof"


def _legal_move_uci(board: chess.Board, raw: Any) -> Optional[str]:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        move = chess.Move.from_uci(value.lower())
        if move in board.legal_moves:
            return move.uci()
    except (ValueError, chess.InvalidMoveError):
        pass
    try:
        move = board.parse_san(value)
    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
        return None
    return move.uci() if move in board.legal_moves else None


def _focus_relevance(
    category: str,
    coaching_context: Optional[Mapping[str, Any]],
) -> CandidateFocus:
    context = coaching_context or {}
    primary = context.get("primary_focus") or {}
    if str(primary.get("topic_key") or "") == category:
        return CandidateFocus.PRIMARY
    for supporting in context.get("supporting_focuses") or ():
        if (
            isinstance(supporting, Mapping)
            and str(supporting.get("topic_key") or "") == category
        ):
            return CandidateFocus.SUPPORTING
    return CandidateFocus.NONE


def _fact(bundle: Any, key: str) -> Any:
    for fact in bundle.detector.facts:
        if isinstance(fact, Mapping) and fact.get(key) not in (None, ""):
            return fact.get(key)
    for fact in bundle.verifier.facts:
        if isinstance(fact, Mapping) and fact.get(key) not in (None, ""):
            return fact.get(key)
    return None


def _canonical_copy(bundle: Any) -> tuple[str, Optional[str]]:
    """Read names/instructions from canonical services; never author content."""
    family = str(bundle.detector.family or "")
    source_ref = str(_fact(bundle, "source_ref") or "")
    explanation = str(_fact(bundle, "explanation") or "").strip()
    lesson_rule = str(_fact(bundle, "lesson_rule") or "").strip()

    try:
        if family == "opening":
            from services.opening_theory_json_service import get_opening_theory

            lesson = get_opening_theory(source_ref) or {}
            name = str(lesson.get("name") or source_ref).strip()
            learnings = lesson.get("common_learnings") or ()
            instruction = (
                explanation
                or lesson_rule
                or (str(learnings[0]).strip() if learnings else "")
            )
            return name, instruction or None

        if family in {"trap", "opening_plan"}:
            from trick_library_service import (
                get_opening_idea_for_practice,
                get_trap_for_practice,
            )

            mode = str(_fact(bundle, "mode") or "execution")
            lesson = (
                get_trap_for_practice(source_ref, mode)
                if family == "trap"
                else get_opening_idea_for_practice(source_ref, "execution")
            ) or {}
            name = str(lesson.get("name") or source_ref).strip()
            if mode == "avoidance":
                instruction = str(
                    lesson.get("how_to_avoid")
                    or lesson.get("learning_goal")
                    or lesson.get("description")
                    or ""
                ).strip()
            else:
                instruction = str(
                    lesson.get("learning_goal")
                    or explanation
                    or lesson_rule
                    or lesson.get("description")
                    or ""
                ).strip()
            return name, instruction or None

        if family == "endgame":
            from services.endgame_theory_service import get_verified_lesson_data

            content_id = str(_fact(bundle, "content_id") or "")
            position_index = int(_fact(bundle, "position_index") or 0)
            category_key, lesson_key = content_id.split("/", 1)
            lesson = get_verified_lesson_data(category_key, lesson_key) or {}
            positions: Sequence[Mapping[str, Any]] = lesson.get("positions") or ()
            position = (
                positions[position_index]
                if 0 <= position_index < len(positions)
                else {}
            )
            name = str(lesson.get("name") or content_id).strip()
            instruction = str(
                position.get("idea")
                or lesson.get("rule")
                or lesson.get("description")
                or ""
            ).strip()
            return name, instruction or None
    except (IndexError, TypeError, ValueError):
        pass

    fallback = source_ref or str(bundle.detector.concept_id).split(":", 1)[-1]
    return fallback.replace("_", " ").replace("-", " ").title(), (
        explanation or lesson_rule or None
    )


def _proof_is_aligned(bundle: Any, best_move_uci: str) -> bool:
    detector_moves = tuple(bundle.detector.acceptable_moves)
    verifier_moves = tuple(bundle.verifier.acceptable_moves)
    bundle_moves = tuple(bundle.acceptable_moves)
    return bool(
        bundle.verifier.verified
        and bundle.detector.concept_id == bundle.verifier.concept_id
        and detector_moves
        and detector_moves == verifier_moves == bundle_moves
        and best_move_uci in bundle_moves
    )


def curriculum_candidates_from_turn(
    *,
    turn_id: str,
    fen_before: str,
    played_uci: str,
    engine_evidence: Mapping[str, Any],
    coaching_context: Optional[Mapping[str, Any]] = None,
    assistance_level: Optional[int] = None,
    game_phase: Optional[str] = None,
) -> tuple[CoachingCandidate, ...]:
    """Return exact-position opening/trap/plan/endgame candidates.

    ``fast_eval`` reports its best move in SAN. The canonical proof service
    accepts UCI, so this adapter converts notation on the same frozen board;
    it never performs another engine search.
    """
    if not engine_evidence.get("eval_valid"):
        return ()
    try:
        board = chess.Board(str(fen_before))
        played = chess.Move.from_uci(str(played_uci).lower())
    except (ValueError, chess.InvalidMoveError):
        return ()
    if played not in board.legal_moves:
        return ()

    best_move_uci = _legal_move_uci(board, engine_evidence.get("best_move"))
    if not best_move_uci or best_move_uci == played.uci():
        return ()
    best_move = chess.Move.from_uci(best_move_uci)
    best_move_san = board.san(best_move)

    from services.canonical_curriculum_puzzle_proof import (
        build_exact_endgame_proof,
        build_exact_opening_trap_position_proofs,
    )

    cp_loss = engine_evidence.get("cp_loss")
    bundles = list(
        build_exact_opening_trap_position_proofs(
            board_before=board,
            best_move_uci=best_move_uci,
            cp_loss=cp_loss,
        )
    )
    endgame = build_exact_endgame_proof(
        board,
        played.uci(),
        best_move_uci,
        cp_loss,
    )
    if endgame is not None:
        bundles.append(endgame)
    if not bundles:
        return ()

    if game_phase is None:
        try:
            from services.game_phase_service import get_game_phase

            game_phase = str(get_game_phase(fen_before).get("phase_label") or "")
        except Exception:
            game_phase = None

    candidates = []
    for bundle in bundles:
        family = str(bundle.detector.family or "curriculum")
        source = f"canonical_curriculum_{family}"
        category = str(bundle.broad_category or "")
        concept_key = str(bundle.detector.concept_id or "")
        lesson_name, instruction = _canonical_copy(bundle)
        claim = (
            f"This exact position matches {lesson_name}; "
            f"{best_move_san} is the verified move."
        )
        aligned = _proof_is_aligned(bundle, best_move_uci)
        source_ref = str(
            _fact(bundle, "source_ref") or _fact(bundle, "content_id") or ""
        )
        proof_references = tuple(
            reference
            for reference in (
                str(bundle.quality_id or ""),
                f"{bundle.detector.detector_id}@{bundle.detector.detector_version}",
                f"{bundle.verifier.verifier_id}@{bundle.verifier.verifier_version}",
                source_ref,
            )
            if reference
        )
        urgency = (
            CandidateUrgency.IMPORTANT
            if family in {"trap", "endgame"}
            else CandidateUrgency.TEACHABLE
        )
        candidates.append(
            CoachingCandidate(
                candidate_id=stable_candidate_id(
                    turn_id=turn_id,
                    source=source,
                    concept_key=concept_key,
                    claim=claim,
                ),
                turn_id=turn_id,
                source=source,
                timing=CandidateTiming.AFTER_MOVE,
                category=category,
                concept_key=concept_key,
                claim=claim,
                transferable_instruction=instruction,
                urgency=urgency,
                focus_relevance=_focus_relevance(category, coaching_context),
                novelty=CandidateNovelty.UNKNOWN,
                assistance_level=assistance_level,
                proof_authority=CURRICULUM_PROOF_AUTHORITY,
                proof_references=proof_references,
                proof_verified=aligned,
                abstention_reason=(None if aligned else "curriculum_proof_mismatch"),
                game_phase=game_phase,
                evidence={
                    "fen": fen_before,
                    "move": played.uci(),
                    "source_version": CURRICULUM_ADAPTER_VERSION,
                    "best_move": best_move_san,
                    "best_move_uci": best_move_uci,
                    "cp_loss": cp_loss,
                    "eval_valid": True,
                    "quality_id": bundle.quality_id,
                    "detector_id": bundle.detector.detector_id,
                    "detector_calculation_id": bundle.detector.calculation_id,
                    "detector_facts": [dict(fact) for fact in bundle.detector.facts],
                    "verifier_id": bundle.verifier.verifier_id,
                    "verifier_calculation_id": bundle.verifier.calculation_id,
                    "verifier_facts": [dict(fact) for fact in bundle.verifier.facts],
                    "acceptable_moves": list(bundle.acceptable_moves),
                },
                visual={
                    "arrows": [
                        [
                            chess.square_name(best_move.from_square),
                            chess.square_name(best_move.to_square),
                            "green",
                        ]
                    ],
                    "highlight_squares": [
                        chess.square_name(best_move.from_square),
                        chess.square_name(best_move.to_square),
                    ],
                },
            )
        )
    return tuple(candidates)


__all__ = [
    "CURRICULUM_ADAPTER_VERSION",
    "CURRICULUM_PROOF_AUTHORITY",
    "curriculum_candidates_from_turn",
]
