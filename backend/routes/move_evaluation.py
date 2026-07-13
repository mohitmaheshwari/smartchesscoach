"""
Move Evaluation Endpoint
Real-time move evaluation using the caption pipeline (build_move_teaching_decision)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import chess
import subprocess
import logging
import json

from routes.auth import get_current_user, User
from services.caption_pipeline import MoveInputs, CrossMoveState, build_move_teaching_decision

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
    user_color: Optional[str] = "white"
    full_move_number: Optional[int] = 1
    move_history_san: Optional[List[str]] = None


class MoveTeachingResponse(BaseModel):
    """Teaching response from caption pipeline"""
    caption_text: str
    severity: str
    teaching_meta: dict


def get_stockfish_analysis(position_fen: str, depth: int = 20) -> dict:
    """Query Stockfish for move analysis."""
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
        best_line_uci = None

        for line in output.split('\n'):
            if 'bestmove ' in line:
                parts = line.split('bestmove ')
                if len(parts) > 1:
                    best_move = parts[1].split()[0]

            if 'depth 20' in line and 'score cp' in line:
                if 'pv ' in line:
                    pv_parts = line.split('pv ')
                    if len(pv_parts) > 1:
                        best_line_uci = pv_parts[1].strip()

                if 'cp ' in line:
                    cp_parts = line.split('cp ')
                    if len(cp_parts) > 1:
                        try:
                            evaluation = int(cp_parts[1].split()[0])
                        except:
                            pass

        return {
            'best_move': best_move,
            'evaluation': evaluation,
            'best_line_uci': best_line_uci
        }

    except Exception as e:
        logger.error(f"Stockfish error: {e}")
        return {'best_move': None, 'evaluation': None, 'best_line_uci': None}


@router.post("/teaching-caption")
async def get_teaching_caption(
    req: MoveEvaluationRequest,
    user: User = Depends(get_current_user)
) -> MoveTeachingResponse:
    """
    Get teaching caption using the central caption pipeline.
    Queries Stockfish, builds MoveInputs, calls build_move_teaching_decision.
    """

    try:
        # Validate FEN and parse user's move
        board = chess.Board(req.fen)

        try:
            user_move_obj = board.push_san(req.user_move_san)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid move: {req.user_move_san}")

        # Stockfish analysis for position after user's move
        fen_after_user = board.fen()
        user_analysis = get_stockfish_analysis(fen_after_user)

        # Stockfish analysis for original position (to find best move)
        board_orig = chess.Board(req.fen)
        best_analysis = get_stockfish_analysis(board_orig.fen())

        if not best_analysis['best_move']:
            raise HTTPException(status_code=500, detail="Could not analyze position")

        # Stockfish analysis for position after best move
        board_best = chess.Board(req.fen)
        try:
            best_move_obj = board_best.push_uci(best_analysis['best_move'])
            best_analysis_after = get_stockfish_analysis(board_best.fen())
        except:
            best_analysis_after = {'evaluation': None, 'best_line_uci': None}

        # Convert UCI best move to SAN
        board_for_san = chess.Board(req.fen)
        best_move_san = board_for_san.san(chess.Move.from_uci(best_analysis['best_move']))

        # Calculate cp_loss
        eval_before = best_analysis['evaluation'] or 0
        eval_after_user = user_analysis['evaluation'] or 0
        eval_after_best = best_analysis_after['evaluation'] or eval_before
        cp_loss = eval_after_best - eval_after_user

        # Build MoveInputs for the caption pipeline
        move_inputs = MoveInputs(
            fen_before=req.fen,
            played_san=req.user_move_san,
            mover_is_user=True,
            mover_is_white=(req.user_color.lower() == "white"),
            user_color=req.user_color.lower(),
            full_move_number=req.full_move_number or 1,
            move_history_san=req.move_history_san or [],
            best_move_san=best_move_san,
            eval_before_cp=eval_before,
            eval_after_cp=eval_after_user,
            cp_loss=max(0, cp_loss),
            pv_after_played=best_analysis['best_line_uci'].split() if best_analysis['best_line_uci'] else [],
            pv_after_best=best_analysis_after.get('best_line_uci', '').split() if best_analysis_after.get('best_line_uci') else [],
            user_rating=req.user_rating or 1500
        )

        # Call the central caption pipeline
        state = CrossMoveState()
        decision = build_move_teaching_decision(move_inputs, state)

        # Extract the teaching meta
        teaching_meta_dict = {
            "severity": decision.teaching_meta.severity,
            "severity_canonical": decision.teaching_meta.severity_canonical,
            "caption_tier": decision.teaching_meta.caption_tier,
            "has_teaching_content": decision.teaching_meta.has_teaching_content,
        }

        return MoveTeachingResponse(
            caption_text=decision.text.caption or "",
            severity=decision.teaching_meta.severity or "context",
            teaching_meta=teaching_meta_dict
        )

    except chess.InvalidMoveError as e:
        logger.error(f"Invalid move error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid move: {str(e)}")
    except Exception as e:
        logger.error(f"Error in move evaluation: {e}")
        raise HTTPException(status_code=500, detail=f"Error evaluating move: {str(e)}")
