"""
Tag Feedback Integration Service
================================

Connects the game tagging system (33 tags) with the auto-correction feedback loop.

When users disagree with a tag applied to their game:
1. Their feedback is captured
2. A smart_pattern is generated to refine future tagging
3. The tagging system learns from corrections

This enables the coach to learn from implicit feedback on tags,
not just explicit corrections on explanations.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Import the game tags
from services.game_tagging_service import GAME_TAGS, get_tag_label, get_tag_description


class TagFeedbackService:
    """
    Service for processing feedback on game tags.
    
    Integrates with the existing auto-correction system to create
    smart_patterns that improve future tagging accuracy.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def submit_tag_feedback(
        self,
        user_id: str,
        game_id: str,
        move_number: int,
        position_fen: str,
        move_san: str,
        current_tag: str,
        correct_tag: str,
        user_explanation: str = "",
        cp_loss: float = 0,
        phase: str = "middlegame"
    ) -> Dict:
        """
        Submit feedback when a user disagrees with a tag.
        
        This:
        1. Stores the tag feedback
        2. Triggers pattern learning to refine tagging
        3. Returns immediate acknowledgment
        
        Args:
            user_id: User providing feedback
            game_id: Game where the tag was applied
            move_number: Move number with the tag
            position_fen: FEN of the position
            move_san: The move played
            current_tag: The tag the system assigned
            correct_tag: What the user says it should be
            user_explanation: Why the user thinks it's different
            cp_loss: Centipawn loss of the move
            phase: Game phase (opening/middlegame/endgame)
        
        Returns:
            Feedback result with learning status
        """
        feedback_id = f"tf_{uuid.uuid4().hex[:12]}"
        
        # Validate tags
        if current_tag not in GAME_TAGS and current_tag != "unknown":
            logger.warning(f"Unknown current_tag: {current_tag}")
        
        if correct_tag not in GAME_TAGS and correct_tag not in ["none", "correct"]:
            logger.warning(f"Unknown correct_tag: {correct_tag}")
        
        # Store the tag feedback
        feedback_doc = {
            "feedback_id": feedback_id,
            "user_id": user_id,
            "game_id": game_id,
            "move_number": move_number,
            "position_fen": position_fen,
            "move_san": move_san,
            "current_tag": current_tag,
            "correct_tag": correct_tag,
            "user_explanation": user_explanation,
            "cp_loss": cp_loss,
            "phase": phase,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "feedback_type": "tag_correction"
        }
        
        await self.db.tag_feedback.insert_one(feedback_doc)
        
        # Try to generate a smart pattern from this feedback
        pattern_result = await self._generate_tag_pattern(feedback_doc)
        
        result = {
            "success": True,
            "feedback_id": feedback_id,
            "learning_status": pattern_result.get("status", "queued"),
            "message": "Thank you! Your feedback helps improve the coach."
        }
        
        if pattern_result.get("pattern_id"):
            result["pattern_id"] = pattern_result["pattern_id"]
        
        logger.info(f"Tag feedback submitted: {feedback_id} - {current_tag} -> {correct_tag}")
        
        return result
    
    async def _generate_tag_pattern(self, feedback: Dict) -> Dict:
        """
        Generate a smart pattern from tag feedback.
        
        This creates a rule that will help the tagging system
        make better decisions in similar positions.
        """
        try:
            current_tag = feedback.get("current_tag", "")
            correct_tag = feedback.get("correct_tag", "")
            position_fen = feedback.get("position_fen", "")
            user_explanation = feedback.get("user_explanation", "")
            cp_loss = feedback.get("cp_loss", 0)
            phase = feedback.get("phase", "middlegame")
            
            # If user says the tag was correct, just acknowledge
            if correct_tag in ["correct", "none", current_tag]:
                return {"status": "acknowledged", "pattern_id": None}
            
            # Create a tag correction pattern
            pattern_id = f"tcp_{uuid.uuid4().hex[:10]}"
            
            # Extract key features from the position
            position_features = self._extract_position_features(position_fen)
            
            # Create the correction pattern
            pattern = {
                "pattern_id": pattern_id,
                "pattern_type": "tag_correction",
                "source": "tag_feedback",
                "wrong_tag": current_tag,
                "correct_tag": correct_tag,
                "position_features": position_features,
                "cp_loss_range": {
                    "min": max(0, cp_loss - 50),
                    "max": cp_loss + 50
                },
                "phase": phase,
                "user_insight": user_explanation,
                "explanation_template": self._generate_correction_explanation(
                    current_tag, correct_tag, user_explanation
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_feedback_id": feedback.get("feedback_id"),
                "usage_count": 0,
                "accuracy_rate": 1.0,
                "status": "active"
            }
            
            # Store the pattern
            await self.db.tag_correction_patterns.update_one(
                {"pattern_id": pattern_id},
                {"$set": pattern},
                upsert=True
            )
            
            # Update the original feedback
            await self.db.tag_feedback.update_one(
                {"feedback_id": feedback.get("feedback_id")},
                {"$set": {
                    "status": "processed",
                    "generated_pattern_id": pattern_id
                }}
            )
            
            logger.info(f"Tag correction pattern created: {pattern_id}")
            
            return {
                "status": "pattern_generated",
                "pattern_id": pattern_id
            }
            
        except Exception as e:
            logger.error(f"Error generating tag pattern: {e}")
            return {"status": "error", "error": str(e)}
    
    def _extract_position_features(self, fen: str) -> Dict:
        """Extract key features from a position for pattern matching"""
        features = {
            "has_fen": bool(fen),
            "piece_count": {},
            "king_safety": "unknown"
        }
        
        try:
            import chess
            board = chess.Board(fen)
            
            # Count pieces
            for piece_type in chess.PIECE_TYPES:
                white_count = len(board.pieces(piece_type, chess.WHITE))
                black_count = len(board.pieces(piece_type, chess.BLACK))
                piece_name = chess.piece_name(piece_type)
                features["piece_count"][f"white_{piece_name}"] = white_count
                features["piece_count"][f"black_{piece_name}"] = black_count
            
            # Check for checks/pins
            features["is_check"] = board.is_check()
            features["legal_moves_count"] = len(list(board.legal_moves))
            
            # Detect material balance
            white_material = sum([
                len(board.pieces(chess.QUEEN, chess.WHITE)) * 9,
                len(board.pieces(chess.ROOK, chess.WHITE)) * 5,
                len(board.pieces(chess.BISHOP, chess.WHITE)) * 3,
                len(board.pieces(chess.KNIGHT, chess.WHITE)) * 3,
                len(board.pieces(chess.PAWN, chess.WHITE)) * 1,
            ])
            black_material = sum([
                len(board.pieces(chess.QUEEN, chess.BLACK)) * 9,
                len(board.pieces(chess.ROOK, chess.BLACK)) * 5,
                len(board.pieces(chess.BISHOP, chess.BLACK)) * 3,
                len(board.pieces(chess.KNIGHT, chess.BLACK)) * 3,
                len(board.pieces(chess.PAWN, chess.BLACK)) * 1,
            ])
            features["material_balance"] = white_material - black_material
            
        except Exception as e:
            logger.debug(f"Error extracting position features: {e}")
        
        return features
    
    def _generate_correction_explanation(
        self,
        wrong_tag: str,
        correct_tag: str,
        user_explanation: str
    ) -> str:
        """Generate an explanation for why the tag was corrected"""
        wrong_label = get_tag_label(wrong_tag)
        correct_label = get_tag_label(correct_tag)
        correct_desc = get_tag_description(correct_tag)
        
        if user_explanation:
            return f"This was actually a {correct_label}: {user_explanation}"
        elif correct_desc:
            return f"This was a {correct_label}. {correct_desc}"
        else:
            return f"This was a {correct_label}, not a {wrong_label}."
    
    async def get_correction_for_tag(
        self,
        position_fen: str,
        proposed_tag: str,
        cp_loss: float,
        phase: str
    ) -> Optional[str]:
        """
        Check if we have a learned correction for this tag.
        
        Called by the tagging system before applying a tag.
        If a correction pattern matches, returns the corrected tag.
        
        Args:
            position_fen: FEN of the position
            proposed_tag: The tag the system wants to apply
            cp_loss: CP loss of the move
            phase: Game phase
        
        Returns:
            Corrected tag if found, None otherwise
        """
        # Look for matching correction patterns
        query = {
            "wrong_tag": proposed_tag,
            "phase": phase,
            "status": "active",
            "cp_loss_range.min": {"$lte": cp_loss},
            "cp_loss_range.max": {"$gte": cp_loss}
        }
        
        # Find best matching pattern (highest usage count for reliability)
        pattern = await self.db.tag_correction_patterns.find_one(
            query,
            sort=[("usage_count", -1)]
        )
        
        if pattern:
            # Increment usage count
            await self.db.tag_correction_patterns.update_one(
                {"pattern_id": pattern["pattern_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            corrected_tag = pattern.get("correct_tag")
            logger.info(f"Tag correction applied: {proposed_tag} -> {corrected_tag}")
            
            return corrected_tag
        
        return None
    
    async def get_tag_feedback_stats(self) -> Dict:
        """Get statistics about tag feedback and corrections"""
        total_feedback = await self.db.tag_feedback.count_documents({})
        processed = await self.db.tag_feedback.count_documents({"status": "processed"})
        pending = await self.db.tag_feedback.count_documents({"status": "pending"})
        
        # Get correction patterns stats
        total_patterns = await self.db.tag_correction_patterns.count_documents({})
        active_patterns = await self.db.tag_correction_patterns.count_documents({"status": "active"})
        
        # Get top corrected tags
        pipeline = [
            {"$match": {"status": "processed"}},
            {"$group": {
                "_id": {"current": "$current_tag", "correct": "$correct_tag"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        top_corrections = []
        async for doc in self.db.tag_feedback.aggregate(pipeline):
            top_corrections.append({
                "from_tag": doc["_id"]["current"],
                "to_tag": doc["_id"]["correct"],
                "count": doc["count"]
            })
        
        return {
            "total_feedback": total_feedback,
            "processed": processed,
            "pending": pending,
            "total_correction_patterns": total_patterns,
            "active_correction_patterns": active_patterns,
            "top_corrections": top_corrections
        }
    
    async def get_pending_tag_feedback(self, limit: int = 20) -> List[Dict]:
        """Get pending tag feedback items"""
        cursor = self.db.tag_feedback.find(
            {"status": "pending"},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)


# ==================== INTEGRATION WITH GAME TAGGING ====================

async def get_corrected_tag(
    db,
    position_fen: str,
    proposed_tag: str,
    cp_loss: float,
    phase: str
) -> str:
    """
    Get the potentially corrected tag for a position.
    
    This is called by the game tagging service to check if
    we have learned corrections for a particular tag.
    
    Args:
        db: Database connection
        position_fen: FEN of the position
        proposed_tag: The tag the system wants to apply
        cp_loss: CP loss of the move
        phase: Game phase
    
    Returns:
        The corrected tag (or original if no correction found)
    """
    service = TagFeedbackService(db)
    corrected = await service.get_correction_for_tag(
        position_fen, proposed_tag, cp_loss, phase
    )
    
    return corrected if corrected else proposed_tag


# ==================== API ENDPOINT MODELS ====================

from pydantic import BaseModel
from typing import Optional


class TagFeedbackRequest(BaseModel):
    """Request model for submitting tag feedback"""
    game_id: str
    move_number: int
    position_fen: str
    move_san: str
    current_tag: str
    correct_tag: str
    user_explanation: Optional[str] = ""
    cp_loss: Optional[float] = 0
    phase: Optional[str] = "middlegame"
