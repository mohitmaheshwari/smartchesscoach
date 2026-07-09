"""Endgame principle detectors package"""

from services.endgame_detectors.rule_of_square_detector import detect_rule_of_square
from services.endgame_detectors.critical_piece_detector import detect_critical_piece_abandonment
from services.endgame_detectors.promotion_threat_detector import detect_promotion_threat_violation
from services.endgame_detectors.principle_detector_registry import (
    DETECTORS,
    run_detectors_on_move,
    extract_principles_from_results,
)

__all__ = [
    "detect_rule_of_square",
    "detect_critical_piece_abandonment",
    "detect_promotion_threat_violation",
    "DETECTORS",
    "run_detectors_on_move",
    "extract_principles_from_results",
]
