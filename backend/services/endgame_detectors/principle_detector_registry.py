"""
Principle Detector Registry — Central access to all principle detectors.

Each detector answers: "Does this principle apply to this position?"
"""

import chess
from typing import Optional, Dict, List
from services.endgame_detectors.rule_of_square_detector import detect_rule_of_square
from services.endgame_detectors.critical_piece_detector import detect_critical_piece_abandonment
from services.endgame_detectors.promotion_threat_detector import detect_promotion_threat_violation


class PrincipleDetector:
    """Single detector with metadata"""

    def __init__(self, name: str, fn, description: str):
        self.name = name
        self.fn = fn
        self.description = description

    async def detect(self, board: chess.Board, move: chess.Move, user_color: chess.Color) -> Optional[str]:
        """Run detection on position. Returns 'applies', 'violates', or None"""
        try:
            return self.fn(board, move, user_color)
        except Exception as e:
            import logging

            logging.warning(f"Detector {self.name} failed: {e}")
            return None


# Registry of all principle detectors
DETECTORS = {
    "rule_of_square": PrincipleDetector(
        name="rule_of_square",
        fn=detect_rule_of_square,
        description="King can catch opponent pawn using rule of the square geometry",
    ),
    "critical_piece": PrincipleDetector(
        name="critical_piece",
        fn=detect_critical_piece_abandonment,
        description="Piece plays critical defensive role (e.g., only defender of pawn)",
    ),
    "promotion_threat": PrincipleDetector(
        name="promotion_threat",
        fn=detect_promotion_threat_violation,
        description="Move allows or stops opponent pawn promotion",
    ),
}


async def run_detectors_on_move(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Dict[str, Optional[str]]:
    """
    Run all detectors on a move.

    Returns:
        {
            "rule_of_square": "applies" | "violates" | None,
            "critical_piece": "applies" | "violates" | None,
            "promotion_threat": "applies" | "violates" | None,
        }
    """
    results = {}
    for detector_name, detector in DETECTORS.items():
        result = await detector.detect(board, move, user_color)
        results[detector_name] = result

    return results


def extract_principles_from_results(detector_results: Dict[str, Optional[str]]) -> List[str]:
    """Extract list of principles that apply or are violated"""
    principles = []
    for detector_name, result in detector_results.items():
        if result is not None:  # Either "applies" or "violates"
            principles.append(detector_name)

    return principles
