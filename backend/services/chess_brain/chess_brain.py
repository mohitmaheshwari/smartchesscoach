"""
Chess Brain - Main Orchestrator
================================

This is the ENTRY POINT for the deterministic coaching engine.

ChessBrain orchestrates:
1. Position analysis (Stockfish truth layer)
2. Pattern detection (DetectorRegistry)
3. Lesson selection (LessonSelectionEngine)
4. Output rendering (SelectedLesson)

Usage:
    brain = ChessBrain(db)
    coaching = await brain.analyze_move(
        fen_before="rnbqkbnr/pppppppp/...",
        user_move="e4",
        user_id="user123",
        session_id="session456"
    )
    
    # coaching.selected_lesson contains what to teach
    # coaching.explanation is ready to show to user
"""

import chess
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .schemas import (
    PositionInsightObject,
    SelectedLesson,
    MistakeFingerprint,
    LessonMemory
)
from .enums import (
    TeachingMode,
    GamePhase,
    MoveQuality
)
from .detector_registry import get_detector_registry
from .lesson_selection_engine import LessonSelectionEngine

# Import existing services
from services.game_phase_service import GamePhaseCalculator

logger = logging.getLogger(__name__)


@dataclass
class ChessBrainOutput:
    """
    Complete output from ChessBrain analysis.
    
    This is what gets passed to the frontend/API response.
    """
    # The selected lesson
    selected_lesson: SelectedLesson
    
    # Position context
    move_quality: MoveQuality
    cp_loss: int
    best_move: str
    
    # For UI
    coaching_message: str
    socratic_question: Optional[str] = None
    encouragement: Optional[str] = None
    quality_badge: Optional[str] = None
    
    # For board highlighting
    highlight_squares: list = field(default_factory=list)
    
    # Teaching mode info
    teaching_mode: TeachingMode = TeachingMode.POSITIVE_REINFORCEMENT
    
    # Metadata
    candidates_evaluated: int = 1
    winning_score: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "coaching_message": self.coaching_message,
            "socratic_question": self.socratic_question,
            "encouragement": self.encouragement,
            "quality_badge": self.quality_badge,
            "move_quality": self.move_quality.value,
            "cp_loss": self.cp_loss,
            "best_move": self.best_move,
            "better_move_explanation": self.selected_lesson.better_move_explanation,
            "highlight_squares": self.highlight_squares,
            "teaching_mode": self.teaching_mode.value,
            "lesson_title": self.selected_lesson.title,
            "main_insight": self.selected_lesson.main_insight,
            "why_section": self.selected_lesson.why_section,
            "next_idea": self.selected_lesson.next_idea,
            # Legacy field compatibility
            "user_move_quality": self.move_quality.value,
            "best_move_explanation": self.selected_lesson.better_move_explanation or ""
        }


class ChessBrain:
    """
    The main orchestrator for deterministic chess coaching.
    
    This class ties together:
    - Stockfish analysis (truth layer)
    - Pattern detection (detector registry)
    - Lesson selection (selection engine)
    - Memory/fingerprint tracking
    """
    
    def __init__(self, db=None):
        """
        Initialize ChessBrain.
        
        Args:
            db: Database connection for fingerprint/memory access
        """
        self.db = db
        self.detector_registry = get_detector_registry()
        self.lesson_engine = LessonSelectionEngine()
        self.phase_calculator = GamePhaseCalculator()
        
        # Session lesson memories (in-memory for now)
        self._session_memories: Dict[str, LessonMemory] = {}
    
    async def analyze_move(
        self,
        fen_before: str,
        user_move: str,
        user_id: str,
        session_id: str,
        stockfish_analysis: Optional[Dict[str, Any]] = None,
        time_spent: Optional[float] = None,
        time_remaining: Optional[float] = None,
        consecutive_blunders: int = 0,
        opening_name: Optional[str] = None,
        opening_key: Optional[str] = None
    ) -> ChessBrainOutput:
        """
        Main entry point - analyze a move and generate coaching.
        
        Args:
            fen_before: Position before user's move
            user_move: User's move in SAN notation
            user_id: For fingerprint lookup
            session_id: For lesson memory
            stockfish_analysis: Pre-computed analysis (optional)
            time_spent: Seconds spent on this move
            time_remaining: Remaining clock time
            consecutive_blunders: Number of blunders in a row
            opening_name: If in known opening
            opening_key: Opening identifier
        
        Returns:
            ChessBrainOutput with coaching ready for display
        """
        try:
            # === STEP 1: Build Position Insight Object ===
            insight = await self._build_insight(
                fen_before=fen_before,
                user_move=user_move,
                stockfish_analysis=stockfish_analysis,
                time_spent=time_spent,
                time_remaining=time_remaining,
                consecutive_blunders=consecutive_blunders,
                opening_name=opening_name,
                opening_key=opening_key
            )
            
            # === STEP 2: Get User Fingerprint (if available) ===
            fingerprint = await self._get_fingerprint(user_id)
            
            # === STEP 3: Get Session Memory ===
            memory = self._get_session_memory(session_id, insight.move_number)
            
            # === STEP 4: Select Best Lesson ===
            lesson = self.lesson_engine.select_lesson(insight, fingerprint, memory)
            
            # === STEP 5: Build Output ===
            return ChessBrainOutput(
                selected_lesson=lesson,
                move_quality=insight.move_quality,
                cp_loss=insight.cp_loss,
                best_move=insight.best_move,
                coaching_message=lesson.explanation,
                socratic_question=lesson.socratic_question,
                encouragement=lesson.encouragement,
                quality_badge=lesson.quality_badge,
                highlight_squares=lesson.highlight_squares,
                teaching_mode=lesson.teaching_mode,
                candidates_evaluated=lesson.candidate_count,
                winning_score=lesson.score
            )
            
        except Exception as e:
            logger.error(f"ChessBrain analysis failed: {e}")
            # Return safe fallback
            return self._create_fallback_output(user_move)
    
    async def _build_insight(
        self,
        fen_before: str,
        user_move: str,
        stockfish_analysis: Optional[Dict[str, Any]],
        time_spent: Optional[float],
        time_remaining: Optional[float],
        consecutive_blunders: int,
        opening_name: Optional[str],
        opening_key: Optional[str]
    ) -> PositionInsightObject:
        """Build the complete PositionInsightObject."""
        
        board = chess.Board(fen_before)
        
        # Parse Stockfish analysis
        if stockfish_analysis:
            best_move = stockfish_analysis.get("best_move", "")
            eval_before = stockfish_analysis.get("eval_before", 0.0)
            eval_after = stockfish_analysis.get("eval_after", 0.0)
            pv = stockfish_analysis.get("pv", [])
        else:
            # Fallback - no Stockfish data
            best_move = user_move
            eval_before = 0.0
            eval_after = 0.0
            pv = []
        
        # Calculate move quality
        cp_loss = self._calculate_cp_loss(eval_before, eval_after, board.turn)
        move_quality = self._classify_move_quality(cp_loss)
        
        # Get game phase
        phase_info = self.phase_calculator.calculate_phase(board)
        game_phase = GamePhase(phase_info.phase_label.value)
        
        # Determine move number
        move_number = board.fullmove_number
        
        # Check if user was winning
        user_color = "white" if board.turn else "black"
        was_winning = (user_color == "white" and eval_before > 1.0) or \
                     (user_color == "black" and eval_before < -1.0)
        
        # Run detectors
        context = {
            "game_phase": game_phase,
            "time_spent": time_spent,
            "time_remaining": time_remaining,
            "consecutive_blunders": consecutive_blunders,
            "move_number": move_number
        }
        
        tactical, strategic, behavioral = self.detector_registry.run_all(
            board, user_move, best_move, context
        )
        
        # Check opening book status
        in_opening_book = move_number <= 10 and opening_name is not None
        
        # Build and return insight
        return PositionInsightObject(
            fen=fen_before,
            move_number=move_number,
            user_color=user_color,
            eval_before=eval_before,
            eval_after=eval_after,
            best_move=best_move,
            user_move=user_move,
            move_quality=move_quality,
            cp_loss=cp_loss,
            pv_after_best=pv,
            game_phase=game_phase,
            phase_percent=phase_info.phase_percent,
            tactical_detections=tactical,
            strategic_detections=strategic,
            behavioral_detections=behavioral,
            in_opening_book=in_opening_book,
            opening_name=opening_name,
            opening_key=opening_key,
            was_winning=was_winning,
            time_spent=time_spent,
            time_remaining=time_remaining
        )
    
    def _calculate_cp_loss(
        self,
        eval_before: float,
        eval_after: float,
        is_white_turn: bool
    ) -> int:
        """Calculate centipawn loss from evaluation change."""
        # Convert to centipawns
        before_cp = int(eval_before * 100)
        after_cp = int(eval_after * 100)
        
        if is_white_turn:
            # White just moved - positive change is good
            return max(0, before_cp - after_cp)
        else:
            # Black just moved - negative change is good (from black's perspective)
            return max(0, after_cp - before_cp)
    
    def _classify_move_quality(self, cp_loss: int) -> MoveQuality:
        """Classify move quality based on centipawn loss."""
        if cp_loss < 10:
            return MoveQuality.EXCELLENT
        elif cp_loss < 30:
            return MoveQuality.GOOD
        elif cp_loss < 100:
            return MoveQuality.INACCURACY
        elif cp_loss < 250:
            return MoveQuality.MISTAKE
        else:
            return MoveQuality.BLUNDER
    
    async def _get_fingerprint(self, user_id: str) -> Optional[MistakeFingerprint]:
        """Get user's mistake fingerprint from database."""
        if not self.db:
            return None
        
        try:
            doc = await self.db.player_fingerprints.find_one(
                {"user_id": user_id},
                {"_id": 0}
            )
            
            if doc:
                return MistakeFingerprint(
                    user_id=user_id,
                    tactical=doc.get("tactical", {}),
                    strategic=doc.get("strategic", {}),
                    phase=doc.get("phase", {}),
                    behavioral=doc.get("behavioral", {}),
                    total_mistakes=doc.get("total_mistakes", 0),
                    games_analyzed=doc.get("games_analyzed", 0),
                    last_updated=doc.get("last_updated")
                )
        except Exception as e:
            logger.warning(f"Failed to get fingerprint: {e}")
        
        return None
    
    def _get_session_memory(self, session_id: str, move_number: int) -> LessonMemory:
        """Get or create session lesson memory."""
        if session_id not in self._session_memories:
            self._session_memories[session_id] = LessonMemory(session_id=session_id)
        
        return self._session_memories[session_id]
    
    def _create_fallback_output(self, user_move: str) -> ChessBrainOutput:
        """Create safe fallback output when analysis fails."""
        fallback_lesson = SelectedLesson(
            teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
            title="Move Played",
            main_insight=f"You played {user_move}",
            explanation="Let's continue the game.",
            score=0.1,
            candidate_count=0
        )
        
        return ChessBrainOutput(
            selected_lesson=fallback_lesson,
            move_quality=MoveQuality.GOOD,
            cp_loss=0,
            best_move=user_move,
            coaching_message="Let's continue the game.",
            teaching_mode=TeachingMode.POSITIVE_REINFORCEMENT,
            candidates_evaluated=0,
            winning_score=0.1
        )
    
    async def update_fingerprint(
        self,
        user_id: str,
        pattern_type: str,
        category: str
    ):
        """Update user's mistake fingerprint after a mistake."""
        if not self.db:
            return
        
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            
            # Build update path based on category
            category_field = f"{category}.{pattern_type}"
            
            await self.db.player_fingerprints.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        f"{category_field}.count": 1,
                        "total_mistakes": 1
                    },
                    "$set": {
                        f"{category_field}.last_seen": now,
                        f"{category_field}.decay_score": 1.0,
                        "last_updated": now
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "created_at": now
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to update fingerprint: {e}")


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

async def analyze_with_chess_brain(
    db,
    fen_before: str,
    user_move: str,
    user_id: str,
    session_id: str,
    stockfish_analysis: Optional[Dict] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to analyze a move with ChessBrain.
    
    Returns dictionary ready for API response.
    """
    brain = ChessBrain(db)
    output = await brain.analyze_move(
        fen_before=fen_before,
        user_move=user_move,
        user_id=user_id,
        session_id=session_id,
        stockfish_analysis=stockfish_analysis,
        **kwargs
    )
    return output.to_dict()
