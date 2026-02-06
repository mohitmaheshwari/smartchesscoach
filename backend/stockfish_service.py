"""
Stockfish Chess Engine Service for Chess Coach AI

This module provides accurate chess position evaluation using Stockfish 15,
the world's strongest open-source chess engine.

Features:
- Position evaluation (centipawn scores)
- Best move suggestions
- Move classification (blunder, mistake, inaccuracy, good, excellent)
- Full game analysis with move-by-move evaluation
"""

import chess
import chess.pgn
import chess.engine
import io
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Stockfish binary path
STOCKFISH_PATH = "/usr/games/stockfish"

# Analysis depth - higher = more accurate but slower
DEFAULT_DEPTH = 18  # Good balance of speed and accuracy
QUICK_DEPTH = 12    # For rapid analysis
DEEP_DEPTH = 22     # For critical positions

# Centipawn thresholds for move classification
# These match Chess.com's classification system
class MoveClassification(str, Enum):
    BRILLIANT = "brilliant"      # Found a very difficult winning move
    GREAT = "great"              # Strong move, better than expected
    BEST = "best"                # The engine's top choice
    EXCELLENT = "excellent"      # Very close to best (< 10 cp loss)
    GOOD = "good"                # Small loss (10-30 cp)
    INACCURACY = "inaccuracy"   # Noticeable loss (30-100 cp)
    MISTAKE = "mistake"          # Significant loss (100-300 cp)
    BLUNDER = "blunder"          # Severe loss (> 300 cp) or missed mate

# Centipawn loss thresholds
CP_THRESHOLDS = {
    "excellent": 10,     # 0-10 cp loss
    "good": 30,          # 10-30 cp loss
    "inaccuracy": 100,   # 30-100 cp loss
    "mistake": 300,      # 100-300 cp loss
    "blunder": float('inf')  # > 300 cp loss
}

@dataclass
class MoveEvaluation:
    """Evaluation result for a single move"""
    move_number: int
    move_san: str           # Standard algebraic notation (e.g., "Nf3")
    move_uci: str           # UCI notation (e.g., "g1f3")
    player: str             # "white" or "black"
    fen_before: str         # FEN position before the move
    eval_before: int        # Centipawn evaluation before the move (from white's perspective)
    eval_after: int         # Centipawn evaluation after the move
    cp_loss: int            # Centipawn loss (always positive, 0 = best move)
    classification: str     # blunder, mistake, inaccuracy, good, excellent, best
    best_move_san: str      # What Stockfish recommended
    best_move_uci: str
    is_mate_before: bool    # Was there a forced mate before this move?
    is_mate_after: bool     # Is there a forced mate after this move?
    mate_in_before: Optional[int]  # Mate in X moves (before)
    mate_in_after: Optional[int]   # Mate in X moves (after)

@dataclass
class GameAnalysis:
    """Complete game analysis result"""
    moves: List[MoveEvaluation]
    blunders: int
    mistakes: int
    inaccuracies: int
    best_moves: int
    excellent_moves: int
    average_cp_loss_white: float
    average_cp_loss_black: float
    accuracy_white: float   # Chess.com style accuracy (0-100)
    accuracy_black: float

class StockfishEngine:
    """Wrapper for Stockfish chess engine"""
    
    def __init__(self, path: str = STOCKFISH_PATH, threads: int = 1, hash_mb: int = 128):
        self.path = path
        self.threads = threads
        self.hash_mb = hash_mb
        self.engine = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    def start(self):
        """Start the Stockfish engine"""
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
            self.engine.configure({
                "Threads": self.threads,
                "Hash": self.hash_mb
            })
            logger.info(f"Stockfish engine started: {self.path}")
        except Exception as e:
            logger.error(f"Failed to start Stockfish: {e}")
            raise
    
    def stop(self):
        """Stop the Stockfish engine"""
        if self.engine:
            self.engine.quit()
            self.engine = None
            logger.info("Stockfish engine stopped")
    
    def evaluate_position(self, board: chess.Board, depth: int = DEFAULT_DEPTH) -> Tuple[int, Optional[int]]:
        """
        Evaluate a position.
        
        Returns:
            Tuple of (centipawn_score, mate_in_moves)
            - centipawn_score: Evaluation in centipawns from white's perspective
            - mate_in_moves: If there's a forced mate, number of moves (positive = white mates, negative = black mates)
        """
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        info = self.engine.analyse(board, chess.engine.Limit(depth=depth))
        score = info["score"].white()
        
        if score.is_mate():
            mate_in = score.mate()
            # Convert mate to a large centipawn value for comparison
            cp_value = 10000 - abs(mate_in) * 10  # Closer mate = higher value
            if mate_in < 0:
                cp_value = -cp_value
            return cp_value, mate_in
        else:
            return score.score(), None
    
    def get_best_move(self, board: chess.Board, depth: int = DEFAULT_DEPTH) -> Tuple[chess.Move, int, Optional[int]]:
        """
        Get the best move for a position.
        
        Returns:
            Tuple of (best_move, eval_score, mate_in_moves)
        """
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        result = self.engine.play(board, chess.engine.Limit(depth=depth), info=chess.engine.INFO_SCORE)
        
        # Get evaluation
        if result.info and "score" in result.info:
            score = result.info["score"].white()
            if score.is_mate():
                return result.move, 10000 if score.mate() > 0 else -10000, score.mate()
            return result.move, score.score(), None
        
        return result.move, 0, None
    
    def classify_move(self, cp_loss: int, missed_mate: bool = False) -> str:
        """Classify a move based on centipawn loss"""
        if missed_mate:
            return MoveClassification.BLUNDER
        
        if cp_loss <= 0:
            return MoveClassification.BEST
        elif cp_loss <= CP_THRESHOLDS["excellent"]:
            return MoveClassification.EXCELLENT
        elif cp_loss <= CP_THRESHOLDS["good"]:
            return MoveClassification.GOOD
        elif cp_loss <= CP_THRESHOLDS["inaccuracy"]:
            return MoveClassification.INACCURACY
        elif cp_loss <= CP_THRESHOLDS["mistake"]:
            return MoveClassification.MISTAKE
        else:
            return MoveClassification.BLUNDER


def calculate_accuracy(cp_losses: List[int]) -> float:
    """
    Calculate Chess.com-style accuracy score (0-100).
    Uses a formula that weights severe mistakes more heavily.
    """
    if not cp_losses:
        return 100.0
    
    # Formula based on Chess.com's accuracy calculation
    # Accuracy = 100 * (1 - avg_cp_loss / 100) with diminishing returns for high losses
    total_weight = 0
    weighted_score = 0
    
    for cp_loss in cp_losses:
        # Cap individual move loss at 500 cp for accuracy calculation
        capped_loss = min(abs(cp_loss), 500)
        
        # Convert to accuracy contribution (0-1)
        move_accuracy = max(0, 1 - capped_loss / 200)
        
        weighted_score += move_accuracy
        total_weight += 1
    
    if total_weight == 0:
        return 100.0
    
    return round(weighted_score / total_weight * 100, 1)


def analyze_game_with_stockfish(pgn_string: str, user_color: str = "white", depth: int = DEFAULT_DEPTH) -> Dict[str, Any]:
    """
    Analyze a complete game using Stockfish.
    
    Args:
        pgn_string: The game in PGN format
        user_color: Which color the user played ("white" or "black")
        depth: Analysis depth (higher = more accurate but slower)
    
    Returns:
        Complete analysis with move-by-move evaluations
    """
    try:
        # Parse PGN
        pgn_io = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn_io)
        
        if not game:
            logger.error("Failed to parse PGN")
            return {"error": "Failed to parse PGN"}
        
        moves_analysis = []
        white_cp_losses = []
        black_cp_losses = []
        
        blunders = 0
        mistakes = 0
        inaccuracies = 0
        best_moves = 0
        excellent_moves = 0
        
        with StockfishEngine() as engine:
            board = game.board()
            prev_eval = 0
            prev_mate = None
            
            # Get initial evaluation
            prev_eval, prev_mate = engine.evaluate_position(board, depth)
            
            move_number = 0
            for node in game.mainline():
                move = node.move
                move_number += 1
                
                is_white_move = board.turn == chess.WHITE
                player = "white" if is_white_move else "black"
                
                # Get best move before making the actual move
                best_move, best_eval, best_mate = engine.get_best_move(board, depth)
                best_move_san = board.san(best_move)
                
                # Make the actual move
                move_san = board.san(move)
                board.push(move)
                
                # Evaluate position after the move
                current_eval, current_mate = engine.evaluate_position(board, depth)
                
                # Calculate centipawn loss
                # For white: loss = prev_eval - current_eval (if white moved)
                # For black: loss = current_eval - prev_eval (if black moved)
                if is_white_move:
                    cp_loss = max(0, prev_eval - current_eval)
                    if cp_loss > 0:
                        white_cp_losses.append(cp_loss)
                else:
                    cp_loss = max(0, current_eval - prev_eval)
                    if cp_loss > 0:
                        black_cp_losses.append(cp_loss)
                
                # Check for missed mate
                missed_mate = prev_mate is not None and (
                    (is_white_move and prev_mate > 0 and (current_mate is None or current_mate <= 0)) or
                    (not is_white_move and prev_mate < 0 and (current_mate is None or current_mate >= 0))
                )
                
                # Classify the move
                classification = engine.classify_move(cp_loss, missed_mate)
                
                # Count classifications
                if classification == MoveClassification.BLUNDER:
                    blunders += 1
                elif classification == MoveClassification.MISTAKE:
                    mistakes += 1
                elif classification == MoveClassification.INACCURACY:
                    inaccuracies += 1
                elif classification == MoveClassification.BEST:
                    best_moves += 1
                elif classification == MoveClassification.EXCELLENT:
                    excellent_moves += 1
                
                # Only include analysis for the user's moves
                if (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move):
                    # Get FEN before this move (need to undo and redo)
                    board.pop()
                    fen_before = board.fen()
                    board.push(move)
                    
                    move_eval = MoveEvaluation(
                        move_number=(move_number + 1) // 2,
                        move_san=move_san,
                        move_uci=move.uci(),
                        player=player,
                        fen_before=fen_before,
                        eval_before=prev_eval,
                        eval_after=current_eval,
                        cp_loss=cp_loss,
                        classification=classification,
                        best_move_san=best_move_san if best_move != move else move_san,
                        best_move_uci=best_move.uci() if best_move != move else move.uci(),
                        is_mate_before=prev_mate is not None,
                        is_mate_after=current_mate is not None,
                        mate_in_before=prev_mate,
                        mate_in_after=current_mate
                    )
                    moves_analysis.append(move_eval)
                
                # Update previous evaluation for next iteration
                prev_eval = current_eval
                prev_mate = current_mate
        
        # Calculate accuracies
        accuracy_white = calculate_accuracy(white_cp_losses)
        accuracy_black = calculate_accuracy(black_cp_losses)
        
        # User-specific stats
        user_moves = [m for m in moves_analysis]
        user_blunders = sum(1 for m in user_moves if m.classification == MoveClassification.BLUNDER)
        user_mistakes = sum(1 for m in user_moves if m.classification == MoveClassification.MISTAKE)
        user_inaccuracies = sum(1 for m in user_moves if m.classification == MoveClassification.INACCURACY)
        user_best_moves = sum(1 for m in user_moves if m.classification == MoveClassification.BEST)
        user_excellent = sum(1 for m in user_moves if m.classification == MoveClassification.EXCELLENT)
        
        user_cp_losses = white_cp_losses if user_color == "white" else black_cp_losses
        user_accuracy = accuracy_white if user_color == "white" else accuracy_black
        
        return {
            "success": True,
            "moves": [
                {
                    "move_number": m.move_number,
                    "move": m.move_san,
                    "move_uci": m.move_uci,
                    "fen_before": m.fen_before,
                    "evaluation": m.classification,
                    "cp_loss": m.cp_loss,
                    "eval_before": m.eval_before,
                    "eval_after": m.eval_after,
                    "best_move": m.best_move_san,
                    "best_move_uci": m.best_move_uci,
                    "is_best": m.cp_loss <= CP_THRESHOLDS["excellent"],
                    "mate_info": {
                        "before": m.mate_in_before,
                        "after": m.mate_in_after
                    } if m.is_mate_before or m.is_mate_after else None
                }
                for m in moves_analysis
            ],
            "user_stats": {
                "blunders": user_blunders,
                "mistakes": user_mistakes,
                "inaccuracies": user_inaccuracies,
                "best_moves": user_best_moves,
                "excellent_moves": user_excellent,
                "accuracy": user_accuracy,
                "avg_cp_loss": round(sum(user_cp_losses) / len(user_cp_losses), 1) if user_cp_losses else 0
            },
            "game_stats": {
                "total_moves": move_number,
                "blunders": blunders,
                "mistakes": mistakes,
                "inaccuracies": inaccuracies,
                "best_moves": best_moves,
                "excellent_moves": excellent_moves,
                "accuracy_white": accuracy_white,
                "accuracy_black": accuracy_black
            }
        }
        
    except Exception as e:
        logger.error(f"Stockfish analysis failed: {e}")
        return {"success": False, "error": str(e)}


def get_position_evaluation(fen: str, depth: int = DEFAULT_DEPTH) -> Dict[str, Any]:
    """
    Evaluate a single position from FEN.
    
    Args:
        fen: Position in FEN notation
        depth: Analysis depth
    
    Returns:
        Evaluation and best move for the position
    """
    try:
        board = chess.Board(fen)
        
        with StockfishEngine() as engine:
            eval_score, mate_in = engine.evaluate_position(board, depth)
            best_move, _, _ = engine.get_best_move(board, depth)
            
            return {
                "success": True,
                "fen": fen,
                "evaluation": {
                    "centipawns": eval_score,
                    "mate_in": mate_in,
                    "is_mate": mate_in is not None
                },
                "best_move": {
                    "san": board.san(best_move),
                    "uci": best_move.uci()
                },
                "turn": "white" if board.turn == chess.WHITE else "black"
            }
    except Exception as e:
        logger.error(f"Position evaluation failed: {e}")
        return {"success": False, "error": str(e)}


def get_best_moves_for_position(fen: str, num_moves: int = 3, depth: int = DEFAULT_DEPTH) -> Dict[str, Any]:
    """
    Get multiple best moves for a position (for showing alternatives).
    
    Args:
        fen: Position in FEN notation
        num_moves: Number of top moves to return
        depth: Analysis depth
    
    Returns:
        Top moves with evaluations
    """
    try:
        board = chess.Board(fen)
        
        with StockfishEngine() as engine:
            # Use multipv to get multiple lines
            engine.engine.configure({"MultiPV": num_moves})
            
            info = engine.engine.analyse(
                board, 
                chess.engine.Limit(depth=depth),
                multipv=num_moves
            )
            
            moves = []
            for line in info:
                if "pv" in line and len(line["pv"]) > 0:
                    move = line["pv"][0]
                    score = line["score"].white()
                    
                    moves.append({
                        "move_san": board.san(move),
                        "move_uci": move.uci(),
                        "evaluation": score.score() if not score.is_mate() else None,
                        "mate_in": score.mate() if score.is_mate() else None
                    })
            
            return {
                "success": True,
                "fen": fen,
                "top_moves": moves
            }
    except Exception as e:
        logger.error(f"Multi-move analysis failed: {e}")
        return {"success": False, "error": str(e)}


# Quick test function
if __name__ == "__main__":
    # Test with a simple position
    test_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    print("Testing position evaluation...")
    result = get_position_evaluation(test_fen)
    print(f"Result: {result}")
    
    # Test with a sample game
    test_pgn = """
    1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O
    """
    print("\nTesting game analysis...")
    result = analyze_game_with_stockfish(test_pgn, "white", depth=12)
    print(f"Result: {result}")
