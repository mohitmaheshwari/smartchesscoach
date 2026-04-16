"""
Teaching Move Selector v2 — Position-based, intent-driven.

Replaces the label-based v1 selector. The pipeline:
1. Generate safe candidate moves (Stockfish, soft eval filter)
2. Select ONE teaching intent (student profile + position feasibility)
3. Score each candidate against that intent (resulting position analysis)
4. Pick the highest-scoring candidate
5. Return structured result with full breakdown

Design rules:
- Score resulting POSITIONS, not move labels
- ONE intent per selection
- No top-3 restriction
- Structured breakdowns for every decision
"""

import chess
import chess.engine
import logging
from typing import Dict, List, Optional

from .types import (
    TeachingIntent, CandidateMove, MoveSelection, IntentScore,
)
from .candidate_generator import generate_candidates
from .intent_selector import select_intent
from .teaching_evaluator import score_all_candidates, MIN_FEASIBILITY_SCORE as MIN_FEASIBILITY

logger = logging.getLogger(__name__)


class TeachingMoveSelectorV2:
    """
    Position-based teaching move selector.

    Usage:
        selector = TeachingMoveSelectorV2()
        result = selector.select_move(
            board=board,
            coach_color=chess.WHITE,
            teaching_focus="tactics",
            student_weaknesses=["calculation"],
        )
    """

    def __init__(self, stockfish_path: str = "/usr/games/stockfish", user_rating: int = 1200):
        self.stockfish_path = stockfish_path
        self.user_rating = user_rating
        self.engine = None

        # Coach ALWAYS plays at full strength.
        # A real coach doesn't play weak chess — they play strong chess
        # and the TEACHING adapts to the student's level.
        self.skill_level = 20
            if user_rating < threshold:
                break
            self.skill_level = skill

    def _get_engine(self) -> chess.engine.SimpleEngine:
        if self.engine is None:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                self.engine.configure({"Skill Level": self.skill_level})
                logger.info(f"[SELECTOR-V2] Engine started: Skill Level {self.skill_level} (user rating {self.user_rating})")
            except Exception as e:
                logger.error(f"Failed to start Stockfish: {e}")
                raise
        return self.engine

    def _close_engine(self):
        if self.engine:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None

    def select_move(
        self,
        board: chess.Board,
        coach_color: chess.Color,
        teaching_focus: Optional[str] = None,
        student_weaknesses: Optional[List[str]] = None,
        last_game_violations: Optional[List[str]] = None,
        max_eval_drop: Optional[int] = None,
    ) -> MoveSelection:
        """
        Select the best teaching move for this position.

        Args:
            board: Current position
            coach_color: The color the coach is playing
            teaching_focus: Session-level focus (e.g. "tactics", "prophylaxis")
            student_weaknesses: Weakness clusters from focus_engine
            last_game_violations: Previous game's fundamental violations (learning loop)
            max_eval_drop: Soft eval cap for candidate generation (auto-scaled by rating if None)

        Returns:
            MoveSelection with selected move, intent, and full score breakdown
        """
        try:
            engine = self._get_engine()

            # Coach plays strong chess — only pick from top moves.
            # Teaching comes from WHICH top move we pick, not from playing weak moves.
            if max_eval_drop is None:
                max_eval_drop = 75  # Only consider moves within 0.75 pawns of best

            # Step 1: Generate candidates (6 moves, depth 10 — fast enough for live play)
            candidates = generate_candidates(
                board, engine,
                max_candidates=6,
                max_eval_drop_cp=max_eval_drop,
            )

            if not candidates:
                # No candidates — return first legal move
                fallback = list(board.legal_moves)[0]
                return MoveSelection(
                    selected_move=fallback,
                    selected_san=board.san(fallback),
                    intent=TeachingIntent.THREAT_AWARENESS,
                    intent_reason="no candidates available — fallback",
                    score_breakdown=IntentScore(
                        intent=TeachingIntent.THREAT_AWARENESS,
                        raw_score=0.0,
                        engine_quality=0.0,
                        final_score=0.0,
                        explanation="fallback move",
                    ),
                )

            # Step 2: Select intent with feasibility check
            intent, reason, scores, fallback_count = select_intent(
                board, candidates, coach_color,
                teaching_focus=teaching_focus,
                student_weaknesses=student_weaknesses,
                last_game_violations=last_game_violations,
                user_rating=self.user_rating,
            )

            # Step 3: Pick the best candidate for this intent
            # scores[i] corresponds to candidates[i]
            best_idx = 0
            best_score = -1.0
            for i, score in enumerate(scores):
                if score.final_score > best_score:
                    best_score = score.final_score
                    best_idx = i

            selected = candidates[best_idx]
            selected_score = scores[best_idx]

            result = MoveSelection(
                selected_move=selected.move,
                selected_san=selected.san,
                intent=intent,
                intent_reason=reason,
                score_breakdown=selected_score,
                all_candidates=[
                    IntentScore(
                        intent=scores[i].intent,
                        raw_score=scores[i].raw_score,
                        sub_scores=scores[i].sub_scores,
                        engine_quality=scores[i].engine_quality,
                        final_score=scores[i].final_score,
                        explanation=f"{candidates[i].san}: {scores[i].explanation}",
                    )
                    for i in range(len(scores))
                ],
                eval_cp=selected.eval_cp,
                eval_rank=selected.eval_rank,
                feasibility_fallbacks=fallback_count,
            )

            # Structured log for behavior validation
            all_raw = [s.raw_score for s in scores]
            all_final = [s.final_score for s in scores]
            score_spread = max(all_raw) - min(all_raw) if all_raw else 0
            logger.info(
                f"[SELECTOR-V2] {selected.san} "
                f"| intent={intent.value} "
                f"| best_raw={selected_score.raw_score:.2f} "
                f"| spread={score_spread:.2f} "
                f"| engine_q={selected_score.engine_quality:.2f} "
                f"| final={selected_score.final_score:.2f} "
                f"| rank={selected.eval_rank}/{len(candidates)} "
                f"| fallbacks={fallback_count} "
                f"| pattern={'YES' if selected_score.raw_score >= MIN_FEASIBILITY else 'weak'}"
            )
            # Per-candidate breakdown for debugging
            for i, (c, s) in enumerate(zip(candidates, scores)):
                marker = " <<<" if i == best_idx else ""
                logger.debug(
                    f"  [{i}] {c.san:6s} raw={s.raw_score:.2f} "
                    f"eng={s.engine_quality:.2f} final={s.final_score:.2f} "
                    f"eval={c.eval_cp:+d} rank={c.eval_rank}{marker}"
                )

            return result

        except Exception as e:
            logger.error(f"[SELECTOR-V2] Error: {e}", exc_info=True)
            # Fallback to first legal move
            fallback = list(board.legal_moves)[0]
            return MoveSelection(
                selected_move=fallback,
                selected_san=board.san(fallback),
                intent=TeachingIntent.THREAT_AWARENESS,
                intent_reason=f"error fallback: {e}",
                score_breakdown=IntentScore(
                    intent=TeachingIntent.THREAT_AWARENESS,
                    raw_score=0.0,
                    engine_quality=0.0,
                    final_score=0.0,
                    explanation=f"error: {e}",
                ),
            )

    def to_dict(self, result: MoveSelection) -> Dict:
        """Convert MoveSelection to a dict for API responses / logging."""
        return {
            "selected_move": result.selected_san,
            "move_uci": result.selected_move.uci(),
            "intent": result.intent.value,
            "intent_reason": result.intent_reason,
            "eval_cp": result.eval_cp,
            "eval_rank": result.eval_rank,
            "feasibility_fallbacks": result.feasibility_fallbacks,
            "score_breakdown": {
                "raw_score": round(result.score_breakdown.raw_score, 3),
                "engine_quality": round(result.score_breakdown.engine_quality, 3),
                "final_score": round(result.score_breakdown.final_score, 3),
                "sub_scores": {
                    k: round(v, 3) for k, v in result.score_breakdown.sub_scores.items()
                },
                "explanation": result.score_breakdown.explanation,
            },
            "all_candidates": [
                {
                    "final_score": round(s.final_score, 3),
                    "raw_score": round(s.raw_score, 3),
                    "explanation": s.explanation,
                }
                for s in result.all_candidates
            ],
        }

    def __del__(self):
        self._close_engine()
