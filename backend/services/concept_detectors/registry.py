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
}


def has_detector(skill_id: str) -> bool:
    """True when an in-game detector is registered for this skill."""
    return skill_id in DETECTORS


def get_detector(skill_id: str) -> Optional[DetectorFn]:
    return DETECTORS.get(skill_id)


def all_detectors() -> Dict[str, DetectorFn]:
    """Read-only view of every registered detector."""
    return dict(DETECTORS)
