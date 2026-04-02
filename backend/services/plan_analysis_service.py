"""
Plan Analysis Service
=====================

Analyzes user's intended plan vs reality to identify cognitive gaps.

The key insight: We don't GUESS what went wrong - we PROVE it mathematically
by comparing the user's intended line with Stockfish's best responses.

Example:
    User played: Bh4 (blunder)
    User's plan: Bh4 gxh4 Qxh4 "I thought I had an attack"
    Reality:     Bh4 gxh4 Qxh4 Nf6+! wins the queen
    
    Analysis: "Calculation error - you stopped at move 3, but Nf6+ on move 4 
              is a discovered attack winning your queen. Always check for 
              in-between moves (zwischenzugs) before committing to an exchange."
"""

import chess
import chess.engine
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

STOCKFISH_PATH = "/usr/games/stockfish"


@dataclass
class PlanAnalysis:
    """Result of analyzing user's plan vs reality."""
    
    # Classification
    gap_type: str  # calculation_depth, missed_tactic, wrong_evaluation, pattern_blindness
    gap_severity: str  # critical, significant, minor
    
    # The divergence point
    divergence_move_number: int  # Move where user's plan breaks down
    user_expected_move: str  # What user thought opponent would play
    actual_best_move: str  # What opponent should actually play
    
    # Evaluation comparison
    user_expected_eval: float  # What user thought the eval would be
    actual_eval: float  # What the eval actually is after best play
    eval_swing: float  # How wrong user was (in pawns)
    
    # Tactic identification (if applicable)
    missed_tactic_type: Optional[str]  # fork, pin, discovery, skewer, zwischenzug, etc.
    missed_tactic_square: Optional[str]  # Key square of the tactic
    
    # Human explanation
    explanation: str  # Clear explanation of what went wrong
    lesson: str  # Transferable learning
    
    # Visual data for board
    critical_moves: List[str]  # Moves to highlight
    arrows: List[Dict]  # Arrows to draw on board


async def analyze_user_plan(
    fen: str,
    user_move: str,
    user_plan_moves: List[str],
    user_plan_reasoning: str = ""
) -> PlanAnalysis:
    """
    Analyze user's intended plan and identify where their calculation failed.
    
    Args:
        fen: Position before user's move
        user_move: The move user actually played (e.g., "Bh4")
        user_plan_moves: User's intended continuation (e.g., ["gxh4", "Qxh4"])
        user_plan_reasoning: User's text explanation of their plan
    
    Returns:
        PlanAnalysis with detailed breakdown of the cognitive gap
    """
    
    try:
        transport, engine = await chess.engine.popen_uci(STOCKFISH_PATH)
        
        board = chess.Board(fen)
        
        # First, make user's move
        try:
            move = board.parse_san(user_move)
            board.push(move)
        except Exception as e:
            logger.error(f"Invalid user move {user_move}: {e}")
            await engine.quit()
            return _create_error_analysis("Could not parse your move")
        
        # Now analyze the user's plan step by step
        analysis_results = []
        current_board = board.copy()
        user_line_valid = True
        divergence_found = False
        divergence_data = None
        
        for i, plan_move_san in enumerate(user_plan_moves):
            # Get Stockfish's best move in this position
            try:
                result = await engine.analyse(
                    current_board, 
                    chess.engine.Limit(depth=18),
                    multipv=1
                )
                
                best_move = result[0]["pv"][0] if result and result[0].get("pv") else None
                best_move_san = current_board.san(best_move) if best_move else None
                score = result[0].get("score")
                eval_cp = score.relative.score(mate_score=10000) if score else 0
                
            except Exception as e:
                logger.error(f"Engine analysis failed: {e}")
                best_move_san = None
                eval_cp = 0
            
            # Try to make user's expected move
            try:
                user_expected = current_board.parse_san(plan_move_san)
                user_expected_san = plan_move_san
            except:
                # User's plan is illegal at this point
                user_line_valid = False
                if not divergence_found:
                    divergence_found = True
                    divergence_data = {
                        "move_number": i + 1,
                        "user_expected": plan_move_san,
                        "actual_best": best_move_san,
                        "eval_before": eval_cp,
                        "reason": "illegal_move"
                    }
                break
            
            # Check if user's expected move matches best move
            if best_move_san and user_expected_san != best_move_san and not divergence_found:
                # This is where user's calculation diverges from reality
                
                # Get eval after user's expected move
                test_board = current_board.copy()
                test_board.push(user_expected)
                user_result = await engine.analyse(test_board, chess.engine.Limit(depth=15), multipv=1)
                user_eval = user_result[0].get("score").relative.score(mate_score=10000) if user_result else 0
                
                # Get eval after best move  
                best_board = current_board.copy()
                best_board.push(best_move)
                best_result = await engine.analyse(best_board, chess.engine.Limit(depth=15), multipv=1)
                best_eval = best_result[0].get("score").relative.score(mate_score=10000) if best_result else 0
                
                eval_diff = abs(user_eval - best_eval)
                
                # Only flag as divergence if significant (> 100cp difference)
                if eval_diff > 100:
                    divergence_found = True
                    
                    # Identify tactic type
                    tactic_type, tactic_square = _identify_tactic(current_board, best_move)
                    
                    divergence_data = {
                        "move_number": i + 1,
                        "user_expected": user_expected_san,
                        "actual_best": best_move_san,
                        "user_eval": user_eval / 100,
                        "actual_eval": best_eval / 100,
                        "eval_diff": eval_diff / 100,
                        "tactic_type": tactic_type,
                        "tactic_square": tactic_square,
                        "board_fen": current_board.fen()
                    }
            
            # Continue with user's expected move for further analysis
            current_board.push(user_expected)
            analysis_results.append({
                "move": user_expected_san,
                "best": best_move_san,
                "eval": eval_cp / 100
            })
        
        await engine.quit()
        
        # Build the analysis result
        if divergence_data:
            return _build_divergence_analysis(divergence_data, user_plan_moves, user_plan_reasoning)
        elif not user_line_valid:
            return _create_error_analysis("Your planned line contains an illegal move")
        else:
            # User's plan was actually correct (or close enough)
            return _build_correct_plan_analysis(analysis_results)
            
    except Exception as e:
        logger.error(f"Plan analysis failed: {e}", exc_info=True)
        return _create_error_analysis(f"Analysis failed: {str(e)}")


def _identify_tactic(board: chess.Board, move: chess.Move) -> Tuple[Optional[str], Optional[str]]:
    """Identify what type of tactic this move represents."""
    
    piece = board.piece_at(move.from_square)
    if not piece:
        return None, None
    
    # Make the move to analyze
    test_board = board.copy()
    test_board.push(move)
    
    to_square = chess.square_name(move.to_square)
    
    # Check if it's a check
    if test_board.is_check():
        # Is it a discovered check?
        if piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
            # The checking piece might be different from the moved piece
            king_sq = test_board.king(not test_board.turn)
            checkers = list(test_board.attackers(test_board.turn, king_sq))
            for checker_sq in checkers:
                if checker_sq != move.to_square:
                    return "discovered_check", to_square
        
        # Check if it's a fork (check + attacks another piece)
        attacked = list(test_board.attacks(move.to_square))
        valuable_attacked = [sq for sq in attacked 
                           if test_board.piece_at(sq) 
                           and test_board.piece_at(sq).color != piece.color
                           and test_board.piece_at(sq).piece_type in [chess.QUEEN, chess.ROOK]]
        if valuable_attacked:
            return "fork_with_check", to_square
        
        return "zwischenzug", to_square  # In-between check
    
    # Check for fork (attacks multiple pieces)
    attacked = list(test_board.attacks(move.to_square))
    valuable_attacked = [sq for sq in attacked 
                        if test_board.piece_at(sq) 
                        and test_board.piece_at(sq).color != piece.color
                        and test_board.piece_at(sq).piece_type in [chess.QUEEN, chess.ROOK, chess.KING]]
    if len(valuable_attacked) >= 2:
        return "fork", to_square
    
    # Check for discovered attack
    # (piece moves and reveals attack from another piece)
    from_file = chess.square_file(move.from_square)
    from_rank = chess.square_rank(move.from_square)
    
    # Check diagonals
    for direction in [(1,1), (1,-1), (-1,1), (-1,-1)]:
        # Check if there was a piece behind that now attacks through
        behind_sq = None
        f, r = from_file - direction[0], from_rank - direction[1]
        while 0 <= f <= 7 and 0 <= r <= 7:
            sq = chess.square(f, r)
            p = board.piece_at(sq)
            if p:
                if p.color == piece.color and p.piece_type in [chess.BISHOP, chess.QUEEN]:
                    behind_sq = sq
                break
            f -= direction[0]
            r -= direction[1]
        
        if behind_sq:
            # Check if this piece now attacks something valuable
            for target_sq in test_board.attacks(behind_sq):
                target = test_board.piece_at(target_sq)
                if target and target.color != piece.color and target.piece_type in [chess.QUEEN, chess.ROOK]:
                    return "discovered_attack", to_square
    
    # Check files/ranks for rook discoveries
    for direction in [(1,0), (-1,0), (0,1), (0,-1)]:
        behind_sq = None
        f, r = from_file - direction[0], from_rank - direction[1]
        while 0 <= f <= 7 and 0 <= r <= 7:
            sq = chess.square(f, r)
            p = board.piece_at(sq)
            if p:
                if p.color == piece.color and p.piece_type in [chess.ROOK, chess.QUEEN]:
                    behind_sq = sq
                break
            f -= direction[0]
            r -= direction[1]
        
        if behind_sq:
            for target_sq in test_board.attacks(behind_sq):
                target = test_board.piece_at(target_sq)
                if target and target.color != piece.color and target.piece_type in [chess.QUEEN, chess.KING]:
                    return "discovered_attack", to_square
    
    # Check for pin
    # (if opponent moves the attacked piece, they lose something bigger)
    
    # Check for skewer
    # (attack on valuable piece that must move, revealing attack on piece behind)
    
    # Default - it's a strong move but no specific tactic identified
    return "tactical_shot", to_square


def _build_divergence_analysis(divergence: Dict, user_plan: List[str], reasoning: str) -> PlanAnalysis:
    """Build analysis result when we found where user's calculation failed."""
    
    move_num = divergence["move_number"]
    user_expected = divergence["user_expected"]
    actual_best = divergence["actual_best"]
    eval_diff = divergence.get("eval_diff", 0)
    tactic_type = divergence.get("tactic_type")
    tactic_square = divergence.get("tactic_square")
    
    # Determine gap type
    if tactic_type in ["zwischenzug", "discovered_check", "fork_with_check"]:
        gap_type = "missed_tactic"
        gap_severity = "critical"
    elif tactic_type in ["fork", "discovered_attack"]:
        gap_type = "missed_tactic"
        gap_severity = "significant"
    elif move_num <= 2:
        gap_type = "calculation_depth"
        gap_severity = "critical" if eval_diff > 3 else "significant"
    else:
        gap_type = "calculation_depth"
        gap_severity = "significant" if eval_diff > 2 else "minor"
    
    # Build explanation
    explanation = _build_explanation(
        gap_type, move_num, user_expected, actual_best, 
        tactic_type, eval_diff, user_plan
    )
    
    # Build lesson
    lesson = _build_lesson(gap_type, tactic_type)
    
    # Build visual data
    arrows = []
    if tactic_square:
        arrows.append({
            "from": tactic_square[:2] if len(tactic_square) > 2 else tactic_square,
            "to": tactic_square,
            "color": "red"
        })
    
    return PlanAnalysis(
        gap_type=gap_type,
        gap_severity=gap_severity,
        divergence_move_number=move_num,
        user_expected_move=user_expected,
        actual_best_move=actual_best,
        user_expected_eval=divergence.get("user_eval", 0),
        actual_eval=divergence.get("actual_eval", 0),
        eval_swing=eval_diff,
        missed_tactic_type=tactic_type,
        missed_tactic_square=tactic_square,
        explanation=explanation,
        lesson=lesson,
        critical_moves=[actual_best],
        arrows=arrows
    )


def _build_explanation(
    gap_type: str, 
    move_num: int, 
    user_expected: str, 
    actual_best: str,
    tactic_type: Optional[str],
    eval_diff: float,
    user_plan: List[str]
) -> str:
    """Build human-readable explanation of what went wrong."""
    
    if gap_type == "missed_tactic":
        tactic_names = {
            "zwischenzug": "in-between move",
            "discovered_check": "discovered check", 
            "fork_with_check": "fork with check",
            "fork": "fork",
            "discovered_attack": "discovered attack",
            "tactical_shot": "tactical shot"
        }
        tactic_name = tactic_names.get(tactic_type, "tactic")
        
        return (
            f"Your calculation stopped at move {move_num}. "
            f"You expected {user_expected}, but {actual_best} is a {tactic_name} "
            f"that changes everything ({eval_diff:+.1f} pawns swing). "
            f"This is the move you missed."
        )
    
    elif gap_type == "calculation_depth":
        return (
            f"You calculated {len(user_plan)} moves deep, but the critical response "
            f"comes on move {move_num}. Instead of {user_expected}, "
            f"{actual_best} refutes your plan ({eval_diff:+.1f} pawns). "
            f"Your calculation needed to go deeper."
        )
    
    else:
        return (
            f"On move {move_num} of your planned line, {actual_best} "
            f"was much better than {user_expected} ({eval_diff:+.1f} pawns difference)."
        )


def _build_lesson(gap_type: str, tactic_type: Optional[str]) -> str:
    """Build transferable lesson based on the gap type."""
    
    lessons = {
        "zwischenzug": "Always check for in-between moves (zwischenzugs) - especially checks - before committing to a sequence.",
        "discovered_check": "Discovered checks are powerful because they attack two things at once. Scan for pieces that could move to reveal an attack.",
        "fork_with_check": "Checks that also attack another piece are devastating. Always ask: 'Does this move come with check?'",
        "fork": "Before executing your plan, check if your opponent can attack two pieces at once.",
        "discovered_attack": "Watch for pieces that can move to reveal attacks from pieces behind them.",
        "calculation_depth": "In tactical positions, calculate one move deeper than feels necessary. The refutation often comes just beyond where you stopped.",
        "tactical_shot": "In sharp positions, always check ALL forcing moves (checks, captures, threats) for your opponent before assuming your plan works."
    }
    
    return lessons.get(
        tactic_type or gap_type, 
        "Verify your opponent's best response at each step of your calculation."
    )


def _build_correct_plan_analysis(results: List[Dict]) -> PlanAnalysis:
    """Build analysis when user's plan was actually reasonable."""
    
    return PlanAnalysis(
        gap_type="correct_plan",
        gap_severity="none",
        divergence_move_number=0,
        user_expected_move="",
        actual_best_move="",
        user_expected_eval=0,
        actual_eval=0,
        eval_swing=0,
        missed_tactic_type=None,
        missed_tactic_square=None,
        explanation="Your calculation was correct! The issue may have been earlier in your thinking, or this was a reasonable try that just didn't work out.",
        lesson="Sometimes we calculate correctly but the position is just difficult. Focus on the root cause of getting into this position.",
        critical_moves=[],
        arrows=[]
    )


def _create_error_analysis(error_msg: str) -> PlanAnalysis:
    """Create an error response."""
    
    return PlanAnalysis(
        gap_type="error",
        gap_severity="unknown",
        divergence_move_number=0,
        user_expected_move="",
        actual_best_move="",
        user_expected_eval=0,
        actual_eval=0,
        eval_swing=0,
        missed_tactic_type=None,
        missed_tactic_square=None,
        explanation=error_msg,
        lesson="",
        critical_moves=[],
        arrows=[]
    )
