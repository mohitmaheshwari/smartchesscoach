"""Pure Phase 2 projection from central move decisions to review events.

This module deliberately has no board parser, engine, detector, database, or
LLM dependency. The caller must provide the detector/content identity and the
opportunity evidence that produced the already-canonical
``MoveTeachingDecision``. That prevents Review from becoming a second chess
reasoning pipeline.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from services.caption_pipeline import MoveTeachingDecision
from services.caption_facts import LegalMaterialLossCause, VerifiedLineCause
from services.exact_endgame_service import (
    ExactEndgameCause,
    render_exact_endgame_cause,
)
from services.detector_quality import QualitySurface
from services.game_review_contracts import (
    ConceptReference,
    EventActor,
    EventEvidence,
    EventOutcome,
    MoveReference,
    OpportunityEvidence,
    PracticalFrame,
    PracticalFrameKind,
    RelationshipArrow,
    RelationshipArrowRole,
    ReviewContractViolation,
    TeachableEvent,
    TeachingReference,
    VisualReference,
    personalized_game_review_enabled,
    personalized_review_quality_v2_enabled,
)
from services.game_review_planner import QUALITY_V2_FORMULA, SHADOW_FORMULA


PHASE2_SOURCE_VERSION = "game_review_event_adapter.v1"


@dataclass(frozen=True)
class MoveEventContext:
    """Explicit upstream evidence needed to project one move decision."""

    game_id: str
    ply: int
    move_number: int
    san: str
    actor: EventActor
    concept_id: str
    outcome: EventOutcome
    quality_id: str
    provenance: Tuple[str, ...]
    opportunity_eligible: bool
    opportunity_before: Optional[str] = None
    opportunity_after: Optional[str] = None
    content_ref: Optional[str] = None
    canonical_source: Optional[str] = None
    requested_surface: QualitySurface = QualitySurface.CAPTION
    reflection_requested: bool = False
    quality_v2_requested: bool = False
    source_version: str = PHASE2_SOURCE_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "game_id",
            "san",
            "concept_id",
            "quality_id",
            "source_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ReviewContractViolation(f"context.{field_name} is required")
        if not isinstance(self.provenance, tuple) or not self.provenance:
            raise ReviewContractViolation("context.provenance must be a non-empty tuple")
        if self.quality_id.startswith("gap:") and not any(
            item.startswith("move_observation:") for item in self.provenance
        ):
            raise ReviewContractViolation(
                "gap events require an upstream move_observation provenance reference"
            )
        if bool(self.content_ref) != bool(self.canonical_source):
            raise ReviewContractViolation(
                "context content_ref and canonical_source must be supplied together"
            )
        if not isinstance(self.quality_v2_requested, bool):
            raise ReviewContractViolation("context.quality_v2_requested must be boolean")


def _validate_central_identity(
    decision: MoveTeachingDecision,
    context: MoveEventContext,
) -> None:
    """Reject a caller that relabels central shape/principle evidence."""
    if context.quality_id.startswith("shape:"):
        expected = context.quality_id.split(":", 1)[1]
        if decision.teaching_meta.shape_pattern_id != expected:
            raise ReviewContractViolation(
                "shape quality_id does not match MoveTeachingDecision"
            )
    if context.quality_id.startswith("principle:"):
        expected = context.quality_id.split(":", 1)[1]
        if decision.teaching_meta.principle_id_used != expected:
            raise ReviewContractViolation(
                "principle quality_id does not match MoveTeachingDecision"
            )


def _visual(decision: MoveTeachingDecision) -> VisualReference:
    arrows = []
    for arrow in decision.visual.arrows:
        origin = arrow.get("from") if isinstance(arrow, Mapping) else None
        destination = arrow.get("to") if isinstance(arrow, Mapping) else None
        if origin and destination:
            arrows.append((str(origin), str(destination)))
    highlights = tuple(
        str(square) for square in decision.visual.highlight_squares if square
    )
    return VisualReference(arrows=tuple(arrows), highlights=highlights)


def _practical_frame(
    decision: MoveTeachingDecision,
    san: str,
) -> PracticalFrame:
    meta = decision.teaching_meta
    cause = decision.cause
    if isinstance(cause, ExactEndgameCause):
        headline, _, _ = render_exact_endgame_cause(cause)
        before = "won" if cause.outcome_before == "win" else "a draw"
        after = "a draw" if cause.outcome_after == "draw" else "a loss"
        return PracticalFrame(
            kind=PracticalFrameKind.STATE_CHANGED,
            state_before=cause.outcome_before,
            state_after=cause.outcome_after,
            headline=headline,
            lead=f"Before {san}, this exact ending was {before}; afterward it was {after}.",
        )
    if meta.stayed_winning:
        return PracticalFrame(
            kind=PracticalFrameKind.STAYED_WINNING,
            state_before=meta.mover_state_before,
            state_after=meta.mover_state_after,
            headline=(
                "You kept control — but left one piece behind"
                if isinstance(cause, LegalMaterialLossCause)
                else "You kept control — but missed a cleaner path"
            ),
            lead=f"You were already winning and {san} did not throw the game away.",
        )
    if meta.decisiveness_changed:
        return PracticalFrame(
            kind=PracticalFrameKind.STATE_CHANGED,
            state_before=meta.mover_state_before,
            state_after=meta.mover_state_after,
            headline="This is where the game changed",
            lead=(
                f"After {san}, the position changed from "
                f"{meta.mover_state_before} to {meta.mover_state_after}."
            ),
        )
    if isinstance(cause, VerifiedLineCause):
        verified_frame = {
            "missed_forced_mate": (
                "You had a checkmating finish",
                f"{san} let the winning attack slip.",
            ),
            "allowed_forced_mate": (
                "This move allowed checkmate",
                f"After {san}, your opponent had an immediate checkmate.",
            ),
            "exchange_sequence": (
                "The capture sequence cost material",
                f"{san} began a series of captures that ended badly for you.",
            ),
            "missed_material_opportunity": (
                "There was material to win",
                f"{san} missed a line that won material.",
            ),
        }[cause.lesson_kind]
        return PracticalFrame(
            kind=PracticalFrameKind.MATERIAL_MISSED,
            state_before=meta.mover_state_before,
            state_after=meta.mover_state_after,
            headline=verified_frame[0],
            lead=verified_frame[1],
        )
    return PracticalFrame(
        kind=PracticalFrameKind.MATERIAL_MISSED,
        state_before=meta.mover_state_before,
        state_after=meta.mover_state_after,
        headline=(
            "The exchange cost material"
            if isinstance(cause, LegalMaterialLossCause)
            and cause.played_capture is not None
            else "One loose piece changed the position"
        ),
        lead=(
            f"{san} started an unfavorable exchange."
            if isinstance(cause, LegalMaterialLossCause)
            and cause.played_capture is not None
            else f"{san} left a concrete capture available."
        ),
    )


def _material_cause_teaching(
    decision: MoveTeachingDecision,
    san: str,
    frame: PracticalFrame,
) -> TeachingReference:
    cause = decision.cause
    if cause is None:
        raise ReviewContractViolation("V2 cause teaching requires a cause")
    affected = cause.affected
    attacker = cause.attacker
    if cause.played_capture is not None:
        captured = cause.played_capture
        opening = (
            f"{san} won the {captured.piece} on {captured.square}, but "
            f"{cause.punishment_san} then won your {affected.piece} on "
            f"{affected.square}. That sequence trades your {affected.piece} "
            f"for their {captured.piece}."
        )
    else:
        opening = (
            f"{san} left your {affected.piece} on {affected.square} available. "
            f"Their {attacker.piece} on {attacker.square} could win it with "
            f"{cause.punishment_san}."
        )
    if cause.best_move_purpose == "moves_affected_piece":
        best = (
            f"{cause.best_move_san} moved the {affected.piece} out of danger."
        )
    elif cause.best_move_purpose == "removes_attacker":
        best = (
            f"{cause.best_move_san} removed the {attacker.piece} before it "
            f"could take the {affected.piece}."
        )
    elif cause.best_move_purpose == "adds_defender":
        best = (
            f"{cause.best_move_san} added a defender, so "
            f"{cause.punishment_san} no longer won the {affected.piece}."
        )
    else:
        best = f"{cause.best_move_san} was the safer move."
    principle = (
        "Before committing to your idea, check what their next capture wins."
    )
    relationships = (
        RelationshipArrow(
            attacker.square,
            affected.square,
            RelationshipArrowRole.THREAT,
        ),
        RelationshipArrow(
            cause.best_move_from,
            cause.best_move_to,
            RelationshipArrowRole.SAFE_MOVE,
        ),
    )
    return TeachingReference(
        caption=f"{opening} {best}",
        principle=principle,
        visual=VisualReference(
            arrows=tuple(
                (item.origin, item.destination) for item in relationships
            ),
            highlights=(affected.square,),
            relationship_arrows=relationships,
        ),
        headline=frame.headline,
        practical_lead=frame.lead,
        cause_fingerprint=cause.fingerprint,
    )


def _line_sequence_text(moves: Tuple[str, ...], *, limit: int = 5) -> str:
    shown = tuple(moves[:limit])
    return ", ".join(shown)


def _piece_list(pieces: Tuple[str, ...]) -> str:
    """Name captured material without turning engine scores into piece values."""
    if not pieces:
        return "nothing"
    number_words = {2: "two", 3: "three", 4: "four", 5: "five"}
    names = []
    for piece, count in Counter(pieces).items():
        if count == 1:
            names.append(f"a {piece}")
        else:
            plural = "pawns" if piece == "pawn" else f"{piece}s"
            names.append(f"{number_words.get(count, str(count))} {plural}")
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _verified_line_teaching(
    cause: VerifiedLineCause,
    san: str,
    frame: PracticalFrame,
) -> TeachingReference:
    if cause.lesson_kind == "missed_forced_mate":
        caption = (
            f"{san} missed the finish because the line "
            f"{_line_sequence_text(cause.best_line_san)} ends in checkmate."
        )
        principle = (
            "Before choosing your move, examine every check and follow each "
            "reply until the checks stop."
        )
    elif cause.lesson_kind == "allowed_forced_mate":
        caption = (
            f"{san} fails because it allows {cause.reply_san}, which is checkmate. "
            f"{cause.best_move_san} stopped that immediate finish."
        )
        principle = (
            "Before moving, scan every check your opponent can play next."
        )
    elif cause.lesson_kind == "exchange_sequence":
        sequence = _line_sequence_text(cause.played_line_san)
        pieces_taken = tuple(
            capture.captured_piece
            for capture in cause.played_captures
            if capture.actor == "initiator"
        )
        pieces_given = tuple(
            capture.captured_piece
            for capture in cause.played_captures
            if capture.actor == "opponent"
        )
        if cause.played_net_material_gain_cp == 0:
            result = (
                f"you give up {_piece_list(pieces_given)} and take "
                f"{_piece_list(pieces_taken)}. The rough count is close, "
                "but the pieces left on the board are different"
            )
        elif cause.played_net_material_gain_cp == -100:
            result = (
                f"you give up {_piece_list(pieces_given)} and recover "
                f"only {_piece_list(pieces_taken)}, so you finish one pawn down"
            )
        elif cause.played_net_material_gain_cp < 0:
            result = (
                f"you give up {_piece_list(pieces_given)} but take only "
                f"{_piece_list(pieces_taken)}"
            )
        else:
            result = (
                f"you take {_piece_list(pieces_taken)} while giving up "
                f"{_piece_list(pieces_given)}"
            )
        caption = (
            f"After {san}, the line is {sequence}. When every recapture is "
            f"counted, {result}."
        )
        principle = (
            "Before starting a capture sequence, count every recapture to "
            "the end."
        )
    elif cause.lesson_kind == "missed_material_opportunity":
        capture = cause.first_best_capture
        if capture is None:
            raise ReviewContractViolation(
                "material-opportunity cause requires a verified capture"
            )
        line = _line_sequence_text(cause.best_line_san[: capture.ply])
        if cause.position_kind == "pawn_ending":
            caption = (
                f"{san} missed material because the line {line} takes the "
                f"{capture.captured_piece} on {capture.captured_square}."
            )
            principle = (
                "In a pawn ending, trace how each king move changes which "
                "pawns you can reach."
            )
        else:
            caption = (
                f"{san} missed material because the line {line} takes the "
                f"{capture.captured_piece} on {capture.captured_square}."
            )
            principle = (
                "When comparing moves, follow each reply sequence until you "
                "can see what the line actually wins."
            )
    else:
        raise ReviewContractViolation("unsupported verified-line lesson")

    relationships = tuple(
        RelationshipArrow(
            item.origin,
            item.destination,
            RelationshipArrowRole(item.role),
        )
        for item in cause.relationships
    )
    highlights = tuple(dict.fromkeys(
        square
        for item in relationships
        for square in (item.origin, item.destination)
    ))
    return TeachingReference(
        caption=caption,
        principle=principle,
        visual=VisualReference(
            arrows=tuple(
                (item.origin, item.destination) for item in relationships
            ),
            highlights=highlights,
            relationship_arrows=relationships,
        ),
        headline=frame.headline,
        practical_lead=frame.lead,
        cause_fingerprint=cause.fingerprint,
    )


def _cause_teaching(
    decision: MoveTeachingDecision,
    san: str,
    frame: PracticalFrame,
) -> TeachingReference:
    cause = decision.cause
    if isinstance(cause, LegalMaterialLossCause):
        return _material_cause_teaching(decision, san, frame)
    if isinstance(cause, VerifiedLineCause):
        return _verified_line_teaching(cause, san, frame)
    if isinstance(cause, ExactEndgameCause):
        _, caption, principle = render_exact_endgame_cause(cause)
        return TeachingReference(
            caption=caption,
            principle=principle,
            headline=frame.headline,
            practical_lead=frame.lead,
            cause_fingerprint=cause.fingerprint,
        )
    raise ReviewContractViolation("V2 cause teaching requires a supported cause")


def adapt_move_teaching_decision(
    decision: MoveTeachingDecision,
    context: MoveEventContext,
) -> TeachableEvent:
    """Project central typed output without reinterpreting the chess position."""
    if not isinstance(decision, MoveTeachingDecision):
        raise ReviewContractViolation("decision must be MoveTeachingDecision")
    if not isinstance(context, MoveEventContext):
        raise ReviewContractViolation("context must be MoveEventContext")
    _validate_central_identity(decision, context)

    explanation = decision.explanation
    caption = (explanation.board_explanation or decision.text.caption or "").strip()
    principle = (
        explanation.transferable_instruction
        or decision.teaching_meta.principle_cue
        or ""
    ).strip()
    final_verified = bool(explanation.final_verified and not decision.should_skip)
    usable = bool(caption or principle or decision.visual.arrows or decision.visual.highlight_squares)

    evidence = EventEvidence(
        quality_id=context.quality_id,
        source_version=context.source_version,
        provenance=context.provenance,
        final_verified=final_verified,
    )

    use_quality_v2 = bool(
        context.quality_v2_requested
        and decision.cause is not None
        and final_verified
        and evidence.authorizes(QualitySurface.CAPTION)
    )

    if not final_verified or not usable:
        outcome = EventOutcome.SILENT
        surface = QualitySurface.DIAGNOSTIC
        teaching = TeachingReference()
        reflection_eligible = False
    else:
        outcome = context.outcome
        surface = context.requested_surface
        if surface != QualitySurface.DIAGNOSTIC and not evidence.authorizes(surface):
            surface = QualitySurface.DIAGNOSTIC
        if use_quality_v2:
            practical = _practical_frame(decision, context.san)
            teaching = _cause_teaching(decision, context.san, practical)
        else:
            practical = None
            teaching = TeachingReference(
                caption=caption,
                principle=principle,
                visual=_visual(decision),
            )
        reflection_eligible = bool(
            context.reflection_requested
            and surface != QualitySurface.DIAGNOSTIC
            and evidence.authorizes(QualitySurface.CAPTION)
        )

    return TeachableEvent(
        event_id=(
            f"{context.game_id}:{context.ply}:{context.concept_id}:"
            f"{outcome.value}"
        ),
        move=MoveReference(
            ply=context.ply,
            number=context.move_number,
            san=context.san,
            actor=context.actor,
        ),
        concept=ConceptReference(
            concept_id=context.concept_id,
            content_ref=context.content_ref,
            canonical_source=context.canonical_source,
        ),
        outcome=outcome,
        opportunity=OpportunityEvidence(
            eligible=context.opportunity_eligible,
            before=context.opportunity_before,
            after=context.opportunity_after,
        ),
        evidence=evidence,
        teaching=teaching,
        requested_surface=surface,
        cause=decision.cause if use_quality_v2 else None,
        practical=practical if use_quality_v2 else None,
        reflection_eligible=reflection_eligible,
    )


def maybe_attach_phase2_review_fields(
    legacy_response: Dict[str, Any],
    *,
    stored_moves: Optional[Tuple[Mapping[str, Any], ...]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Expose precomputed Phase 2 fields; flag-off preserves object and bytes."""
    if not personalized_game_review_enabled(env):
        return legacy_response
    quality_v2_visible = personalized_review_quality_v2_enabled(env)

    def stored_event_is_authorized(event: Mapping[str, Any]) -> bool:
        display = event.get("display")
        evidence = event.get("evidence")
        teaching = event.get("teaching")
        if not isinstance(display, Mapping) or not isinstance(evidence, Mapping):
            return False
        has_v2_payload = "cause" in event or "practical" in event
        if has_v2_payload:
            cause = event.get("cause")
            practical = event.get("practical")
            if (
                not quality_v2_visible
                or not isinstance(cause, Mapping)
                or not isinstance(practical, Mapping)
                or not isinstance(teaching, Mapping)
                or teaching.get("cause_fingerprint") != cause.get("fingerprint")
                or teaching.get("headline") != practical.get("headline")
                or teaching.get("practical_lead") != practical.get("lead")
            ):
                return False
        surface = display.get("requested_surface")
        authorized_surfaces = evidence.get("authorized_surfaces")
        return bool(
            event.get("outcome") != EventOutcome.SILENT.value
            and surface in (QualitySurface.CAPTION.value, QualitySurface.PLAN.value)
            and display.get("authorized")
            and evidence.get("final_verified")
            and isinstance(authorized_surfaces, Mapping)
            and authorized_surfaces.get(surface)
        )

    events = []
    prompts = []
    source_moves = (
        stored_moves
        if stored_moves is not None
        else tuple(legacy_response.get("decryption_data") or [])
    )
    for move in source_moves:
        if not isinstance(move, Mapping):
            continue
        event = move.get("teachable_event")
        if isinstance(event, Mapping) and stored_event_is_authorized(event):
            events.append(dict(event))
            prompt = move.get("reflection_prompt")
            if (
                (display := event.get("display"))
                and display.get("reflection_eligible")
                and isinstance(prompt, Mapping)
                and prompt.get("event_id") == event.get("event_id")
            ):
                prompts.append(dict(prompt))

    sanitized_moves = []
    for move in legacy_response.get("decryption_data") or []:
        if not isinstance(move, Mapping):
            sanitized_moves.append(move)
            continue
        clean_move = dict(move)
        clean_move.pop("teachable_event", None)
        clean_move.pop("reflection_prompt", None)
        sanitized_moves.append(clean_move)

    augmented = dict(legacy_response)
    augmented["decryption_data"] = sanitized_moves
    augmented["teachable_events"] = events
    augmented["reflection_prompts"] = prompts
    return augmented


_CHAPTER_ROLES = frozenset(
    {
        "turning_point",
        "demonstrated_knowledge",
        "opponent_plan",
        "missed_opportunity",
        "knowledge_gap",
        "recurring_connection",
        "reflection",
    }
)


def _safe_stored_plan(
    envelope: Mapping[str, Any],
    events: Tuple[Mapping[str, Any], ...],
    *,
    expected_formula_id: str,
) -> Optional[Dict[str, Any]]:
    """Fail closed unless every stored chapter still has authorization."""
    if (
        envelope.get("rollout_mode") != "shadow"
        or envelope.get("formula_id") != expected_formula_id
    ):
        return None
    plan = envelope.get("plan")
    if not isinstance(plan, Mapping):
        return None
    required_text = ("plan_id", "opening", "game_arc", "takeaway")
    if any(not str(plan.get(field) or "").strip() for field in required_text):
        return None
    if (
        plan.get("schema_version") != "personalized_game_review.v1"
        or plan.get("rollout_mode") != "shadow"
    ):
        return None

    event_index = {
        str(event.get("event_id") or ""): event
        for event in events
        if event.get("event_id")
    }
    raw_chapters = plan.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters:
        return None
    if any(not isinstance(item, Mapping) for item in raw_chapters):
        return None
    chapter_ids = [str(item.get("event_id") or "") for item in raw_chapters]
    if not all(chapter_ids) or len(chapter_ids) != len(set(chapter_ids)):
        return None
    if chapter_ids != list(envelope.get("selected_event_ids") or []):
        return None

    chapters = []
    for raw in raw_chapters:
        event = event_index.get(str(raw.get("event_id") or ""))
        role = str(raw.get("role") or "")
        if event is None or role not in _CHAPTER_ROLES:
            return None
        surfaces = (event.get("evidence") or {}).get("authorized_surfaces") or {}
        required_surface = (
            "plan" if role == "recurring_connection" else "caption"
        )
        if not surfaces.get(required_surface):
            return None
        concept = event.get("concept") or {}
        if (
            raw.get("content_ref") != concept.get("content_ref")
            or raw.get("canonical_source") != concept.get("canonical_source")
        ):
            return None
        chapters.append({
            "event_id": raw["event_id"],
            "role": role,
            "content_ref": raw.get("content_ref"),
            "canonical_source": raw.get("canonical_source"),
        })

    next_action = plan.get("next_action")
    safe_action = None
    if next_action is not None:
        if not isinstance(next_action, Mapping):
            return None
        source_id = str(next_action.get("source_event_id") or "")
        source_event = event_index.get(source_id)
        href = str(next_action.get("href") or "")
        if (
            source_id not in set(chapter_ids)
            or source_event is None
            or not href.startswith("/")
            or href.startswith("//")
            or not (
                (source_event.get("evidence") or {})
                .get("authorized_surfaces", {})
                .get("plan")
            )
        ):
            return None
        action_fields = (
            "action_kind",
            "content_kind",
            "content_id",
            "canonical_source",
        )
        if any(not str(next_action.get(field) or "").strip() for field in action_fields):
            return None
        safe_action = {
            "source_event_id": source_id,
            "href": href,
            **{field: next_action[field] for field in action_fields},
        }

    return {
        "schema_version": plan["schema_version"],
        "plan_id": plan["plan_id"],
        "opening": plan["opening"],
        "game_arc": plan["game_arc"],
        "chapters": chapters,
        "takeaway": plan["takeaway"],
        "next_action": safe_action,
        "rollout_mode": "shadow",
    }


def maybe_attach_phase5_review_fields(
    legacy_response: Dict[str, Any],
    *,
    stored_moves: Tuple[Mapping[str, Any], ...],
    stored_plan: Optional[Mapping[str, Any]],
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Expose one internally consistent plan; otherwise keep legacy UI."""
    if not personalized_game_review_enabled(env):
        return legacy_response
    augmented = maybe_attach_phase2_review_fields(
        legacy_response,
        stored_moves=stored_moves,
        env=env,
    )
    if not isinstance(stored_plan, Mapping):
        return augmented
    safe_plan = _safe_stored_plan(
        stored_plan,
        tuple(augmented.get("teachable_events") or []),
        expected_formula_id=(
            QUALITY_V2_FORMULA
            if personalized_review_quality_v2_enabled(env)
            else SHADOW_FORMULA
        ),
    )
    if safe_plan is not None:
        augmented["game_teaching_plan"] = safe_plan
    return augmented
