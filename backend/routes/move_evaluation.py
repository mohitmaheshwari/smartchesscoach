"""
Move Evaluation Endpoint (Training)
Routes to the proven game_decryption_v5 flow used by review pages.
One source of truth for all captions - no parallel systems.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from routes.auth import get_current_user, User
from services.game_decryption_v5_service import generate_game_decryption_v5

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/move-eval", tags=["Move Evaluation"])

db = None

def set_db(database):
    """Set database reference"""
    global db
    db = database


class MoveTeachingRequest(BaseModel):
    """Request to get teaching caption for a move in a game"""
    game_id: str
    move_number: int  # 1-indexed full move number (1, 2, 3, etc.)


class MoveTeachingResponse(BaseModel):
    """Teaching response from the review pipeline"""
    caption_text: str
    severity: str
    teaching_meta: dict
    engine_data: dict


@router.post("/teaching-caption")
async def get_teaching_caption(
    req: MoveTeachingRequest,
    user: User = Depends(get_current_user)
) -> MoveTeachingResponse:
    """
    Get teaching caption for a move using the SAME pipeline as game review.

    This ensures training and review use ONE source of truth for captions.
    The caption includes full game context (trap history, pattern tracking,
    eval history, opening detection) - not just the isolated position.
    """

    try:
        # Fetch the game
        game = await db.games.find_one(
            {"game_id": req.game_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        if not game.get("is_analyzed"):
            raise HTTPException(
                status_code=400,
                detail="Game must be analyzed first (use /api/games/analyze endpoint)"
            )

        # Fetch the game analysis (contains move_evaluations array)
        analysis = await db.game_analyses.find_one(
            {"game_id": req.game_id},
            {"_id": 0}
        )
        if not analysis:
            raise HTTPException(status_code=404, detail="Game analysis not found")

        # Generate full game decryption (this is the review pipeline)
        decryption = await generate_game_decryption_v5(db, game, analysis)

        if not decryption or "moves" not in decryption:
            raise HTTPException(status_code=500, detail="Could not decrypt game")

        # Find the move we want
        moves = decryption["moves"]
        # moves array is indexed by full_move_number (1, 2, 3, ...)
        # Need to find the move at this index
        target_move = None
        for move_data in moves:
            if move_data.get("full_move_number") == req.move_number:
                target_move = move_data
                break

        if not target_move:
            raise HTTPException(
                status_code=404,
                detail=f"Move {req.move_number} not found in game"
            )

        # Extract the caption and metadata
        caption_text = target_move.get("caption", "")
        severity = target_move.get("severity", "context")

        # Teaching metadata
        teaching_meta_dict = {
            "severity": severity,
            "severity_canonical": target_move.get("severity_canonical", "good"),
            "caption_tier": target_move.get("caption_tier", "NONE"),
            "has_teaching_content": len(caption_text) > 10,  # Heuristic: non-empty teaching
        }

        # Engine data from the analysis
        engine_data_dict = {
            "move_san": target_move.get("move", ""),
            "best_move_san": target_move.get("best_move", ""),
            "cp_loss": target_move.get("cp_loss", 0),
            "eval_before_cp": target_move.get("eval_before", 0),
            "eval_after_cp": target_move.get("eval_after", 0),
            "classification": target_move.get("classification", ""),
            "cognitive_gap": target_move.get("cognitive_gap", ""),
            "move_number": req.move_number,
        }

        return MoveTeachingResponse(
            caption_text=caption_text,
            severity=severity,
            teaching_meta=teaching_meta_dict,
            engine_data=engine_data_dict
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in move teaching caption: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
