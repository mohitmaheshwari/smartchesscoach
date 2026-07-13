"""
Move Evaluation Endpoint
Evaluates moves in real-time during training and returns coaching captions
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import chess
import subprocess
import logging

from routes.auth import get_current_user, User
from services.move_teaching_template import build_move_caption

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/move-eval", tags=["Move Evaluation"])

db = None

def set_db(database):
    """Set database reference"""
    global db
    db = database


class MoveEvaluationRequest(BaseModel):
    """Request to evaluate a move"""
    fen: str
    user_move_san: str
    user_rating: Optional[int] = 1500


class MoveTeachingResponse(BaseModel):
    """Teaching caption for a move"""
    classification: str
    move_played: str
    best_move: str
    cp_loss: float
    headline: str
    analysis: str
    best_plan: str
    show_teaching: bool


def get_stockfish_analysis(position_fen: str, depth: int = 20) -> dict:
    """
    Query Stockfish for move analysis.
    Returns: best_move, evaluation, principal_variation
    """
    try:
        result = subprocess.run(
            ['/usr/games/stockfish'],
            input=f"position fen {position_fen}\ngo depth {depth}\n",
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout
        best_move = None
        evaluation = None
        best_line = None

        # Parse Stockfish output
        for line in output.split('\n'):
            if 'bestmove ' in line:
                parts = line.split('bestmove ')
                if len(parts) > 1:
                    best_move = parts[1].split()[0]

            # Get latest score and pv for depth 20
            if 'depth 20' in line and 'score cp' in line:
                if 'pv ' in line:
                    pv_parts = line.split('pv ')
                    if len(pv_parts) > 1:
                        best_line = pv_parts[1].strip()

                if 'cp ' in line:
                    cp_parts = line.split('cp ')
                    if len(cp_parts) > 1:
                        try:
                            score_str = cp_parts[1].split()[0]
                            evaluation = int(score_str)
                        except:
                            pass

        return {
            'best_move': best_move,
            'evaluation': evaluation,
            'best_line': best_line
        }

    except Exception as e:
        logger.error(f"Stockfish error: {e}")
        return {'best_move': None, 'evaluation': None, 'best_line': None}


@router.post("/teaching-caption")
async def get_teaching_caption(
    req: MoveEvaluationRequest,
    user: User = Depends(get_current_user)
) -> MoveTeachingResponse:
    """
    Get an AI-generated teaching caption for a move.

    Evaluates the move using Stockfish and returns a coaching explanation.

    Example:
        Input: FEN + move "Nxd4"
        Output: Classification, best move, cp_loss, and English teaching caption
    """

    try:
        # Validate FEN
        board = chess.Board(req.fen)

        # Parse user's move in SAN notation
        try:
            user_move = board.push_san(req.user_move_san)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid move: {req.user_move_san}")

        # Get position after user's move
        fen_after_user = board.fen()
        user_eval = get_stockfish_analysis(fen_after_user)

        # Reset and get best move in original position
        board = chess.Board(req.fen)
        best_analysis = get_stockfish_analysis(board.fen())

        if not best_analysis['best_move']:
            raise HTTPException(status_code=500, detail="Could not analyze position")

        # Get position after best move
        board.push_san(chess.Move.from_uci(best_analysis['best_move']).uci())
        best_fen = board.fen()
        best_eval_data = get_stockfish_analysis(best_fen)

        # Build the teaching caption
        caption = build_move_caption(
            user_move=req.user_move_san,
            best_move=chess.Move.from_uci(best_analysis['best_move']).uci(),
            your_eval=user_eval['evaluation'] or 0,
            best_eval=best_eval_data['evaluation'] or 0,
            best_line=best_eval_data['best_line'],
            user_rating=req.user_rating
        )

        return MoveTeachingResponse(
            classification=caption['classification'],
            move_played=caption['move_played'],
            best_move=caption['best_move'],
            cp_loss=caption['cp_loss'],
            headline=caption['headline'],
            analysis=caption['analysis'],
            best_plan=caption['best_plan'],
            show_teaching=caption['show_teaching']
        )

    except chess.InvalidMoveError as e:
        logger.error(f"Invalid move error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid move: {str(e)}")
    except Exception as e:
        logger.error(f"Error in move evaluation: {e}")
        raise HTTPException(status_code=500, detail=f"Error evaluating move: {str(e)}")
