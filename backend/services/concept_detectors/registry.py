"""
Concept-detector registry.

Maps an engine2 skill_id to the in-game detector that grades it. New
detectors register here so the per-move runner can find them.

A detector function has the signature:

    detector(
        board_before: chess.Board,
        move: chess.Move,
        user_color: chess.Color,
    ) -> Optional[str]    # "applied" | "missed" | None

`None` means the move wasn't a clean test (don't grade it). The runner
in `_runner.py` consumes this output and dispatches to
record_skill_attempt with outcome="applied" / "wrong" respectively.

Add a new detector:
  1. Implement detect_X_application() in services/concept_detectors/X.py.
  2. Import it here.
  3. Add the (skill_id, detector_fn) entry to DETECTORS.
  4. Once shipped, the corresponding skill in skill_tree.json
     automatically lifts its graduation bar from "lesson correct" to
     "lesson correct + in-game applied" (handled in
     SkillProgress.is_learned via the `detector_engaged` check).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

import chess

from services.concept_detectors.rule_of_the_square import (
    detect_rule_of_the_square_application,
)
from services.concept_detectors.defend_scholars_mate import (
    detect_defend_scholars_mate_application,
)
from services.concept_detectors.mate_kq_vs_k import (
    detect_mate_kq_vs_k_application,
)
from services.concept_detectors.mate_kr_vs_k import (
    detect_mate_kr_vs_k_application,
)
from services.concept_detectors.defend_fried_liver import (
    detect_defend_fried_liver_application,
)
from services.concept_detectors.endgame_opposition import (
    detect_endgame_opposition_application,
)
from services.concept_detectors.endgame_lucena import (
    detect_endgame_lucena_application,
)
from services.concept_detectors.endgame_philidor import (
    detect_endgame_philidor_application,
)
from services.concept_detectors.trap_detection import (
    detect_trap_application,
)
from services.concept_detectors.opening_play import (
    detect_opening_play_application,
    detect_sound_opening_deviation_application,
)
from services.concept_detectors.opening_principles import (
    detect_opening_castling_application,
    detect_opening_center_application,
    detect_opening_development_with_tempo_application,
)
from services.concept_detectors.opening_plan_play import (
    detect_opening_plan_application,
)
from services.concept_detectors.coach_principles import (
    detect_coached_development_application,
    detect_endgame_active_rook_application,
    detect_endgame_create_passed_pawn_application,
    detect_endgame_king_centralization_application,
    detect_endgame_stop_promotion_application,
)
from services.concept_detectors.positional_patterns import (
    detect_central_pawn_break_application,
    detect_iqp_play_application,
    detect_knight_outpost_application,
    detect_luft_application,
    detect_minority_attack_application,
    detect_prophylactic_king_tuck_application,
    detect_rook_open_file_application,
    detect_rook_seventh_application,
)
from services.concept_detectors.endgame_curriculum_positions import (
    curriculum_endgame_detectors,
)


# Type alias for clarity.
DetectorFn = Callable[[chess.Board, chess.Move, chess.Color], Optional[str]]


# skill_id (from data/coaching/skill_tree.json) -> detector
DETECTORS: Dict[str, DetectorFn] = {
    "endgame_rule_of_square": detect_rule_of_the_square_application,
    "defend_scholars_mate":   detect_defend_scholars_mate_application,
    "mate_kq_vs_k":           detect_mate_kq_vs_k_application,
    "mate_kr_vs_k":           detect_mate_kr_vs_k_application,
    "defend_fried_liver":     detect_defend_fried_liver_application,
    "endgame_opposition":     detect_endgame_opposition_application,
    "endgame_lucena":         detect_endgame_lucena_application,
    "endgame_philidor":       detect_endgame_philidor_application,
    # Trap and opening detection (Tier 2-3 wiring)
    "trap_detection":         detect_trap_application,
    "opening_play":           detect_opening_play_application,
    "opening_sound_deviation": detect_sound_opening_deviation_application,
    "opening_castling":       detect_opening_castling_application,
    "opening_center":         detect_opening_center_application,
    "opening_development_with_tempo": detect_opening_development_with_tempo_application,
    "opening_plan_play":      detect_opening_plan_application,
    "coached_development":    detect_coached_development_application,
    "endgame_king_centralization": detect_endgame_king_centralization_application,
    "endgame_create_passed_pawn": detect_endgame_create_passed_pawn_application,
    "endgame_active_rook":    detect_endgame_active_rook_application,
    "endgame_stop_promotion": detect_endgame_stop_promotion_application,
    # Broader coach-level positional candidates. These reuse the canonical
    # middlegame recognizers and are authorization-gated as Shadow.
    "concept_knight_outpost": detect_knight_outpost_application,
    "concept_rook_open_file": detect_rook_open_file_application,
    "concept_rook_seventh": detect_rook_seventh_application,
    "concept_central_pawn_break": detect_central_pawn_break_application,
    "concept_minority_attack": detect_minority_attack_application,
    "concept_iqp": detect_iqp_play_application,
    "concept_luft": detect_luft_application,
    "concept_prophylactic_king_tuck": detect_prophylactic_king_tuck_application,
}

# One exact-position transfer detector is derived from each publishable
# canonical endgame lesson. No lesson IDs, FENs, or answers are copied here.
DETECTORS.update(curriculum_endgame_detectors())


def has_detector(skill_id: str) -> bool:
    """True when an in-game detector is registered for this skill."""
    return skill_id in DETECTORS


def get_detector(skill_id: str) -> Optional[DetectorFn]:
    return DETECTORS.get(skill_id)


def all_detectors() -> Dict[str, DetectorFn]:
    """Read-only view of every registered detector."""
    return dict(DETECTORS)
