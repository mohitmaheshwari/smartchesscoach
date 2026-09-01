"""Canonical authorization for detector output.

Detector implementations and catalogs remain in their existing canonical
registries. This module stores only the right to influence a player-facing
surface. Unknown IDs deliberately fail closed to SHADOW.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

class QualityGrade(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    SHADOW = "shadow"
    DISABLED = "disabled"


class QualitySurface(str, Enum):
    PLAN = "plan"
    CAPTION = "caption"
    MASTERY = "mastery"
    PROMPT = "prompt"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class Authorization:
    grade: QualityGrade
    evidence_ref: str
    rationale: str
    limitations: Tuple[str, ...] = ()


_UNKNOWN = Authorization(
    grade=QualityGrade.SHADOW,
    evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
    rationale="No reviewed promotion packet; unknown IDs fail closed.",
    limitations=("Independent semantic precision and recall are not established.",),
)


_EXACT_ENDGAME_CURRICULUM = Authorization(
    grade=QualityGrade.SHADOW,
    evidence_ref=(
        "backend/data/corpus_snapshots/"
        "curriculum_endgame_tablebase_2026-08-29.json"
    ),
    rationale=(
        "The detector is derived from one exact publishable endgame lesson "
        "position, requires the already-stored best move, and reuses the "
        "independent tablebase or pinned-engine curriculum verifier."
    ),
    limitations=(
        "Exact canonical position only; it does not generalize the technique.",
        "Blind application review is still required before mastery promotion.",
    ),
)


# Promotions are intentionally sparse. Adding a detector to its canonical
# registry does not grant it product authority. Promotion is a separate,
# evidence-reviewed edit here.
_AUTHORIZATIONS: Mapping[str, Authorization] = {
    "review:exact_endgame_result_change": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "docs/exact_endgame_result_caption_evidence_2026_09_01.md"
        ),
        rationale=(
            "The caption names only an exact win/draw/loss transition from a "
            "pinned local Fathom/Syzygy probe whose buckets partition every "
            "legal move. The renderer accepts no model or detector inference."
        ),
        limitations=(
            "Single-position Caption authority only; no technique name or recurrence.",
            "CursedWin and BlessedLoss abstain from simple result language.",
            "Plan, mastery, prescription and psychological claims remain unauthorized.",
        ),
    ),
    "review:verified_single_game_cause": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref=(
            "docs/verified_single_game_cause_caption_promotion_2026_09_01.md"
        ),
        rationale=(
            "Caption text is limited to one fully reconstructed board cause: "
            "legal exchange truth or two complete legal stored continuations. "
            "The ten-game reviewed packet and expanded structural/adversarial "
            "gates contain zero critical false claims."
        ),
        limitations=(
            "Single-move Caption authority only; no recurrence or learner diagnosis.",
            "It may not name an opening, trap, tactic motif, or endgame technique.",
            "Plan, mastery, prescription, and persistent prompts remain unauthorized.",
        ),
    ),
    "gap:piece_safety:trapped_piece_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_trapped_piece_puzzle_proof.py",
        rationale=(
            "The canonical causal candidate is independently checked with a "
            "legal target-capture minimax across every escape, while the stored "
            "best move must avoid that exact trapped state."
        ),
        limitations=(
            "Only attacked non-pawn pieces with no escape below the material floor are named.",
            "Requires a different stored best move and at least 100cp consequence.",
        ),
    ),
    "tactic:discovered_attack_with_stored_payoff": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_discovered_attack_puzzle_proof.py",
        rationale=(
            "A canonical vacated-ray candidate is independently rebuilt as a "
            "single-blocker line, and the complete legal stored continuation "
            "must capture that exact target with the uncovered slider."
        ),
        limitations=(
            "Only discovered attacks with the exact stored material payoff are named.",
            "Quiet discoveries and truncated continuations remain generic.",
        ),
    ),
    "tactic:back_rank_mate_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_back_rank_mate_puzzle_proof.py",
        rationale=(
            "The canonical candidate is independently checked on the terminal "
            "board: a rook or queen delivers checkmate along the defender's "
            "home rank while the mated king remains on that rank."
        ),
        limitations=(
            "Only immediate exact mates receive the back-rank name.",
            "Other stored forced mates retain the broader forced-mate concept.",
        ),
    ),
    "tactic:remove_defender_with_stored_payoff": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_removal_defender_puzzle_proof.py",
        rationale=(
            "The canonical sole-guard candidate is independently checked before "
            "and after the stored best capture, and the legal stored line must "
            "then capture the exact newly exposed target for net material."
        ),
        limitations=(
            "Only literal sole-defender removal with a stored payoff is named.",
            "Overload, deflection and decoy require separate proof families.",
        ),
    ),
    "tactic:aligned_with_stored_payoff": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_aligned_tactic_puzzle_proof.py",
        rationale=(
            "A canonical before/after alignment proposal is independently "
            "rebuilt by a fresh two-blocker ray walk, and the legal stored line "
            "must exploit those exact pin or skewer targets for net material."
        ),
        limitations=(
            "Quiet or merely geometric alignments remain unverified.",
            "Requires a different played move and at least 100cp stored loss.",
        ),
    ),
    "tactic:fork_with_stored_payoff": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_fork_puzzle_proof.py",
        rationale=(
            "The canonical shape detector's stored-best fork is independently "
            "reconstructed from the post-move attack map and the complete stored "
            "line must legally demonstrate a net material gain."
        ),
        limitations=(
            "Only forks whose payoff appears in the stored continuation are named.",
            "Requires a different played move and at least 100cp stored loss.",
        ),
    ),
    "tactic:free_piece_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_free_piece_puzzle_proof.py",
        rationale=(
            "The canonical shape detector proposes the stored best capture; "
            "a separate verifier confirms the captured piece is worth at least "
            "a minor piece and enumerates zero legal immediate recaptures."
        ),
        limitations=(
            "Only immediate unrecapturable best-move captures are named.",
            "Requires a different played move and at least 100cp stored loss.",
        ),
    ),
    "tactic:forced_mate_exact": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_forced_mate_puzzle_proof.py",
        rationale=(
            "The stored best line is independently replayed as legal chess to "
            "an actual checkmate delivered by the player side, with at least "
            "100cp of stored consequence for the missed move."
        ),
        limitations=(
            "Only the exact stored best move is accepted.",
            "A mate marker without a complete legal replay remains unverified.",
        ),
    ),
    "curriculum:opening_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/curriculum_truth_and_delivery_scope.md",
        rationale=(
            "The claim is limited to an exact legal prefix in one publishable "
            "canonical opening line, with the stored best move matching the "
            "authored move and a greater-than-50cp stored consequence."
        ),
        limitations=(
            "Exact move order only; no transposition or similar-position claim.",
            "One match is lesson evidence, not a general opening-mastery claim.",
        ),
    ),
    "curriculum:opening_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_canonical_curriculum_puzzle_proof.py",
        rationale=(
            "The complete four-field position and stored best move match one "
            "unique publishable canonical opening decision; an independent "
            "legal replay reaches the same position."
        ),
        limitations=(
            "Exact position only; no similar-position or strategic-plan inference.",
            "One match is lesson evidence, not general opening mastery.",
        ),
    ),
    "curriculum:opening_plan_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The complete legal history and stored best move identify one "
            "publishable authored opening-plan decision."
        ),
        limitations=(
            "Exact canonical line only; no analogous-plan inference.",
            "Blind per-plan application review is pending.",
        ),
    ),
    "curriculum:opening_plan_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The complete four-field position and stored best move identify "
            "one publishable authored opening-plan decision."
        ),
        limitations=(
            "Exact canonical position only; no analogous-plan inference.",
            "Blind per-plan application review is pending.",
        ),
    ),
    "curriculum:trap_exact_decision": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/curriculum_truth_and_delivery_scope.md",
        rationale=(
            "The claim is limited to an exact validated defense or final trap "
            "decision, independently replayed, with the stored best move agreeing "
            "and a greater-than-50cp stored consequence."
        ),
        limitations=(
            "Does not generalize the trap name across transpositions.",
            "Arbitrary safe_moves metadata is not accepted as proof.",
        ),
    ),
    "curriculum:trap_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/tests/test_canonical_curriculum_puzzle_proof.py",
        rationale=(
            "The complete four-field position and stored best move match one "
            "unique validated trap decision; an independent legal replay reaches "
            "the same danger or execution position."
        ),
        limitations=(
            "Exact position only; no visually similar trap claim.",
            "Arbitrary safe_moves metadata is not accepted as proof.",
        ),
    ),
    "curriculum:endgame_exact_position": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/"
            "curriculum_endgame_tablebase_2026-08-29.json"
        ),
        rationale=(
            "The exact validated FEN and canonical answer are independently "
            "backed by committed Syzygy WDL preservation or pinned Stockfish "
            "evidence for positions outside tablebase coverage."
        ),
        limitations=(
            "Exact canonical positions only; no approximate-geometry claim.",
            "One solve is evidence, not a general endgame-mastery claim.",
        ),
    ),
    "gap:piece_safety:simple_hang": Authorization(
        grade=QualityGrade.CAPTION,
        evidence_ref="docs/simple_hang_caption_promotion_2026_08_31.md",
        rationale=(
            "Meets every Caption-grade value in the 2026-08-27 threshold lock: "
            "96.9% reviewed semantic precision over 260 fires (Wilson lower "
            "bound ~94.0%, bar 85%), 40 independently adjudicated "
            "non-opportunity cases (bar 20), and zero critical false claims "
            "across a 40-case near-threshold adversarial packet. Caption-grade "
            "sets no recall floor because a caption detector may safely stay "
            "silent, so the 61.61% taxonomy recall that correctly blocks "
            "Plan-grade does not bar the caption surface."
        ),
        limitations=(
            "Authorization applies only to the current-schema simple_hang subtype.",
            "Caption surface only. Plan-grade still requires the sealed blind "
            "packet, independent semantic review, and the >=60% recall floor "
            "that 16.09% D_live miss recall does not meet.",
            "Non-opportunity and adversarial cases are board/SEE-adjudicated "
            "facts, not human semantic gold; they supplement, and do not "
            "replace, the reviewed 260-fire precision corpus.",
        ),
    ),

    # Measured candidates remain explicit Shadow entries so the quality report
    # carries their real evidence and limitations instead of making them look
    # identical to never-reviewed detectors.
    "shape:free_piece": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Strict post-capture recapture truth passed 200/200 rerated fires "
            "and 20/20 near-negative controls."
        ),
        limitations=(
            "No blinded independent semantic review packet.",
            "No Plan-grade opportunity/recall denominator.",
        ),
    ),
    "principle:TAC_HANGING_PIECE": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_exchange_truth_lock_2026_08_27.md",
        rationale=(
            "Board-mutating legal exchange truth removed 3,571 unsafe stored "
            "claims and passed the fresh deterministic rerating packet."
        ),
        limitations=(
            "No blinded causal-language review.",
            "Recall against independently selected hanging-piece opportunities is unknown.",
        ),
    ),
    "brain:hanging_piece_detector": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/hanging_piece_detector_implementation_2026_08_28.md",
        rationale=(
            "Chess Brain now adapts canonical board-mutating legal-exchange "
            "truth with a measured material floor, engine consequence and a "
            "strict played-versus-best issue-set counterfactual."
        ),
        limitations=(
            "The residual candidates have not received blinded semantic review.",
            "No independent Chess Brain hanging-piece opportunity denominator exists.",
        ),
    ),
    "principle:TAC_FORK_PATTERN": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_quality_threshold_lock_2026_08_27.md",
        rationale=(
            "Full-solution Lichess fork coverage reached 99.7%; a 28/28 "
            "move-attribution sample used the moving piece."
        ),
        limitations=(
            "Specificity is not established because theme absence is not negative truth.",
            "Independent semantic attribution sample is below the Caption-grade minimum.",
        ),
    ),
    "shape:pin": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and absolute-pin "
            "king ordering is corrected."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "Recall and hard-negative performance are unknown.",
        ),
    ),
    "shape:skewer": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/detector_tactical_attribution_2026_08_27.md",
        rationale=(
            "Before/after causal filtering is implemented and pin/skewer "
            "value ordering now treats the king as the highest alignment piece."
        ),
        limitations=(
            "Fresh independent semantic precision is not yet measured.",
            "The defended-front-piece adversarial packet is incomplete.",
        ),
    ),
    "concept:opening_play": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale=(
            "The detector proves exact canonical in-book play and now requires "
            "at least two player decisions."
        ),
        limitations=(
            "A blind per-opening application review has not yet passed.",
            "Off-book moves remain ungraded rather than being called mistakes.",
        ),
    ),
    "concept:opening_sound_deviation": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "At an exact authored opening decision, the player chose a move "
            "outside the curriculum and that move exactly matched the already-"
            "stored Stockfish best move."
        ),
        limitations=(
            "This proves the deviation was sound in that position, not that the "
            "player mastered the authored opening line.",
            "Positive-only candidate; blind review pending.",
        ),
    ),
    "concept:opening_castling": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale="The stored best opening move was legal castling.",
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_center": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best opening move advanced a home d- or e-pawn to "
            "occupy d4/e4 or d5/e5."
        ),
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_development_with_tempo": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best opening move developed a home minor piece and the "
            "developed piece immediately attacked the enemy queen, rook or king."
        ),
        limitations=("Positive-only candidate; blind review pending.",),
    ),
    "concept:opening_plan_play": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="backend/data/traps.json",
        rationale=(
            "The played move and stored best move agree at one exact legal "
            "position from one publishable canonical opening-plan line."
        ),
        limitations=(
            "Exact authored positions only; analogous plans are not inferred.",
            "Positive-only candidate; blind per-plan review pending.",
        ),
    ),
    "concept:trap_detection": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale=(
            "Only publishable canonical trap continuations and exact authored "
            "victim defenses can produce a candidate."
        ),
        limitations=(
            "Broad production trap misses were unsafe in the locked replay.",
            "The repaired exact-defense candidate still needs blind review.",
        ),
    ),
    "concept:coached_development": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The player developed a home-square minor piece with the exact "
            "already-stored Stockfish best move during the opening."
        ),
        limitations=("Positive application only; no missed claim.",),
    ),
    "concept:endgame_king_centralization": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "In the canonical endgame phase, the stored best king move reduced "
            "distance to a central square."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_create_passed_pawn": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best pawn move changed a non-passed pawn into a passed "
            "pawn by exact board geometry."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_active_rook": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best rook move changed an inactive rook into one on an "
            "open file or the seventh rank in the canonical endgame phase."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_stop_promotion": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move captured or physically blockaded an advanced "
            "enemy passed pawn."
        ),
        limitations=("Positive application only; blind semantic review pending.",),
    ),
    "concept:endgame_opposition": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="Exact king-and-pawn opposition geometry is reconstructed.",
        limitations=("The missed-move branch has not passed blind review.",),
    ),
    "concept:endgame_lucena": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="A narrow rook-and-pawn bridge geometry is detected.",
        limitations=("Production opportunity coverage is extremely sparse.",),
    ),
    "concept:endgame_philidor": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref=(
            "backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json"
        ),
        rationale="A narrow defensive rook geometry is detected.",
        limitations=("Production opportunity coverage is extremely sparse.",),
    ),
    "concept:concept_knight_outpost": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a pawn-supported knight outpost."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_rook_open_file": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as occupying an open file."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_rook_seventh": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a rook reaching the seventh rank."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_central_pawn_break": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a central pawn break."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_minority_attack": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a minority-attack pawn push."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_iqp": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as play specific to an isolated queen-pawn structure."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_luft": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as creating an escape square for the king."
        ),
        limitations=("Positive-only candidate; blind positional review pending.",),
    ),
    "concept:concept_prophylactic_king_tuck": Authorization(
        grade=QualityGrade.SHADOW,
        evidence_ref="docs/verified_puzzle_detector_data_lock_2026_08_30.md",
        rationale=(
            "The stored best move is recognized by the canonical middlegame "
            "pattern source as a narrow preventive king tuck."
        ),
        limitations=(
            "This is not authorization for the broader prophylaxis concept.",
            "Positive-only candidate; blind positional review pending.",
        ),
    ),
    # Known unsafe claims do not need to execute in normal product paths.
    "concept:endgame_rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "Canonical legal-race truth is implemented and all consumers are "
            "adapters, but the production scan found only five eligible positions "
            "and all five belong to one game."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "legacy_endgame:rule_of_square": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The legacy surface is now a thin adapter over canonical legal-race "
            "truth; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "principle:END_RULE_OF_SQUARE": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/rule_of_square_consolidation_implementation_2026_08_27.md",
        rationale=(
            "The caption predicate now consumes canonical legal-race truth, including "
            "immediate captures; production evidence is still too sparse for authorization."
        ),
        limitations=(
            "Needs the locked review counts across independent games and source units "
            "before reconsideration.",
        ),
    ),
    "brain:trapped_piece_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/trapped_piece_detector_implementation_2026_08_27.md",
        rationale=(
            "The turn-order defect is fixed and Chess Brain now adapts canonical "
            "move-causal trapped-piece truth, but independent semantic precision "
            "and recall are not established."
        ),
        limitations=(
            "No stable trapped-piece opportunity denominator.",
            "The seven post-gate production candidates still need blinded review.",
        ),
    ),
    "brain:king_safety_detector": Authorization(
        grade=QualityGrade.DISABLED,
        evidence_ref="docs/king_safety_detector_implementation_2026_08_28.md",
        rationale=(
            "Broad post-move geometry was replaced with canonical board-state facts, "
            "a best-move issue-set counterfactual, a consequence floor and an endgame "
            "gate; independent semantic precision and recall are not established."
        ),
        limitations=(
            "The 90 residual production candidates still need blinded review.",
            "No independent king-safety opportunity denominator exists.",
        ),
    ),
}


def gap_quality_id(pattern: str, subtype: Optional[str]) -> str:
    return f"gap:{pattern}:{subtype or '*'}"


def shape_quality_id(pattern_id: str) -> str:
    return f"shape:{pattern_id}"


def principle_quality_id(principle_id: str) -> str:
    return f"principle:{principle_id}"


def concept_quality_id(skill_id: str) -> str:
    return f"concept:{skill_id}"


def brain_quality_id(detector_id: str) -> str:
    return f"brain:{detector_id}"


def observation_concept_quality_id(concept_id: str) -> str:
    return f"observation_concept:{concept_id}"


def get_authorization(quality_id: str) -> Authorization:
    if str(quality_id).startswith("concept:endgame_curriculum__"):
        return _EXACT_ENDGAME_CURRICULUM
    return _AUTHORIZATIONS.get(quality_id, _UNKNOWN)


def explicit_authorizations() -> Dict[str, Authorization]:
    return dict(_AUTHORIZATIONS)


def grade_for(quality_id: str) -> QualityGrade:
    return get_authorization(quality_id).grade


def is_authorized(quality_id: str, surface: QualitySurface | str) -> bool:
    surface = QualitySurface(surface)
    grade = grade_for(quality_id)
    if surface == QualitySurface.DIAGNOSTIC:
        return grade != QualityGrade.DISABLED
    if surface == QualitySurface.CAPTION:
        return grade in (QualityGrade.CAPTION, QualityGrade.PLAN)
    # Plans, mastery claims and persistent coaching prompts need Plan-grade.
    return grade == QualityGrade.PLAN


def enforcement_enabled() -> bool:
    """Whether Shadow authorization is enforced on product output.

    Fail closed by default so Shadow output cannot silently influence players.
    Explicitly Disabled IDs remain blocked in either mode.
    """
    return os.environ.get(
        "DETECTOR_QUALITY_GATE_ENFORCED", "true"
    ).lower() == "true"


def can_influence(quality_id: str, surface: QualitySurface | str) -> bool:
    grade = grade_for(quality_id)
    if grade == QualityGrade.DISABLED:
        return False
    if not enforcement_enabled():
        return True
    return is_authorized(quality_id, surface)


def authorized_gap_subtypes(pattern: str) -> Tuple[str, ...]:
    prefix = f"gap:{pattern}:"
    return tuple(
        quality_id[len(prefix):]
        for quality_id, auth in _AUTHORIZATIONS.items()
        if quality_id.startswith(prefix)
        and auth.grade == QualityGrade.PLAN
        and not quality_id.endswith(":*")
    )


def sanitize_plan_observation(observation: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a plan-safe observation while retaining shadow diagnostics.

    Neutral engine facts remain available. Detector-derived gap/concept fields
    are copied into detector_quality_shadow when they lack Plan authority,
    then removed from the fields consumed by focus/strength aggregation.
    """
    safe = dict(observation)
    shadow: Dict[str, Any] = dict(safe.get("detector_quality_shadow") or {})

    pattern = safe.get("missed_pattern")
    subtype = safe.get("subtype")
    if pattern:
        quality_id = gap_quality_id(str(pattern), str(subtype) if subtype else None)
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["gap"] = {
                "quality_id": quality_id,
                "missed_pattern": pattern,
                "subtype": subtype,
                "severity": safe.get("severity"),
                "grade": grade_for(quality_id).value,
            }
            safe["missed_pattern"] = None
            safe["subtype"] = None
            safe["severity"] = None

    pattern_id = safe.get("tactical_pattern_executed")
    if pattern_id:
        quality_id = shape_quality_id(str(pattern_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["tactical_pattern_executed"] = {
                "quality_id": quality_id,
                "pattern_id": pattern_id,
                "grade": grade_for(quality_id).value,
            }
            safe["tactical_pattern_executed"] = None

    concept_id = safe.get("concept_used")
    if concept_id:
        quality_id = observation_concept_quality_id(str(concept_id))
        if not can_influence(quality_id, QualitySurface.PLAN):
            shadow["concept_used"] = {
                "quality_id": quality_id,
                "concept_id": concept_id,
                "grade": grade_for(quality_id).value,
            }
            safe["concept_used"] = None

    if shadow:
        safe["detector_quality_shadow"] = shadow
    return safe


def quality_id_for_focus_document(focus: Mapping[str, Any]) -> Optional[str]:
    explicit = focus.get("detector_quality_id")
    if explicit:
        return str(explicit)
    # Compatibility for the already-built, versioned PIC focus document.
    if (
        focus.get("focus_kind") == "piece_safety/simple_hang"
        and focus.get("diagnosis_detector_id")
        == "move_observation.simple_hang.v16_plus"
    ):
        return gap_quality_id("piece_safety", "simple_hang")
    return None


def focus_document_is_authorized(focus: Mapping[str, Any]) -> bool:
    quality_id = quality_id_for_focus_document(focus)
    if not quality_id:
        return not enforcement_enabled()
    return can_influence(quality_id, QualitySurface.PLAN)


def filter_authorized_events(
    events: Iterable[Mapping[str, Any]],
    *,
    id_field: str,
    namespace: str,
    surface: QualitySurface | str,
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """Split events into authorized and shadow lists without losing evidence."""
    allowed: list[Dict[str, Any]] = []
    shadow: list[Dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        detector_id = copied.get(id_field)
        quality_id = f"{namespace}:{detector_id}" if detector_id else ""
        copied["detector_quality_id"] = quality_id or None
        copied["detector_quality_grade"] = grade_for(quality_id).value
        if quality_id and is_authorized(quality_id, surface):
            allowed.append(copied)
        else:
            shadow.append(copied)
    return allowed, shadow
