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

# Import centralized config
from config import STOCKFISH_PATH, STOCKFISH_DEPTH, CP_THRESHOLDS as CONFIG_CP_THRESHOLDS

logger = logging.getLogger(__name__)

# Analysis depth - higher = more accurate but slower
DEFAULT_DEPTH = STOCKFISH_DEPTH
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

# Piece values for sacrifice detection
PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
}

# Minimum eval gap between best and 2nd-best move to qualify as "only good move" (cp)
BRILLIANT_MULTIPV_GAP = 150


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
    classification: str     # blunder, mistake, inaccuracy, good, excellent, best, brilliant
    best_move_san: str      # What Stockfish recommended
    best_move_uci: str
    is_mate_before: bool    # Was there a forced mate before this move?
    is_mate_after: bool     # Is there a forced mate after this move?
    mate_in_before: Optional[int]  # Mate in X moves (before)
    mate_in_after: Optional[int]   # Mate in X moves (after)
    # Principal variations for understanding WHY moves are good/bad
    pv_after_played: List[str] = None    # What happens after the move you played
    pv_after_best: List[str] = None      # What would happen after the best move
    threat_after_played: str = None      # The immediate threat you face after your move
    # NEW: Position after move and turning point detection
    fen_after: str = None                # FEN position after the move
    is_turning_point: bool = False       # Eval swing >= 120cp
    eval_swing: int = 0                  # Absolute eval change
    is_sacrifice: bool = False           # Material sacrifice detected
    is_brilliant: bool = False           # Brilliant move (sacrifice + only good move)

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
    
    def get_principal_variation(self, board: chess.Board, depth: int = DEFAULT_DEPTH, pv_length: int = 5) -> List[str]:
        """
        Get the principal variation (best line of play) from current position.
        
        Returns:
            List of moves in SAN notation (e.g., ["Bb5+", "Kf7", "Ng5+"])
        """
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        try:
            info = self.engine.analyse(board, chess.engine.Limit(depth=depth))
            pv_moves = info.get("pv", [])
            
            # Convert to SAN notation
            pv_san = []
            temp_board = board.copy()
            for move in pv_moves[:pv_length]:
                pv_san.append(temp_board.san(move))
                temp_board.push(move)
            
            return pv_san
        except Exception as e:
            logger.error(f"Failed to get PV: {e}")
            return []
    
    def get_threat(self, board: chess.Board, depth: int = DEFAULT_DEPTH) -> Optional[str]:
        """
        Get the main threat in the position (opponent's best response).
        
        Returns:
            The threatening move in SAN notation, or None
        """
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        try:
            # Get opponent's best move (which is the threat)
            info = self.engine.analyse(board, chess.engine.Limit(depth=depth))
            pv = info.get("pv", [])
            if pv:
                return board.san(pv[0])
            return None
        except Exception as e:
            logger.error(f"Failed to get threat: {e}")
            return None
    
    def classify_move(
        self,
        cp_loss: int,
        missed_mate: bool = False,
        eval_before_player_cp: Optional[int] = None,
    ) -> str:
        """Classify a move based on centipawn loss.

        Args:
            cp_loss: how much the eval dropped from the moving player's
                perspective. Always >= 0.
            missed_mate: True when the player had a forced mate and
                played a non-mating move. These stay as blunders even
                in winning positions.
            eval_before_player_cp: position eval BEFORE the move, from
                the moving player's perspective. When provided, applies
                winning-/losing-position grace so we don't tag moves as
                blunders just for dropping +900 to +500 (still
                completely winning). Without it, falls back to raw
                cp_loss thresholds.

        The grace mirrors what Chess.com does via win-probability
        deltas: a 400cp drop in a +900 position is meaningless because
        you're still winning by 5 pawns. Calling that a "blunder" in
        the analyzed-game pipeline is the bug that produced 41%
        accuracy on a game Chess.com scored 85%.
        """
        if missed_mate:
            return MoveClassification.BLUNDER

        if cp_loss <= 0:
            return MoveClassification.BEST

        # Position-context grace
        if eval_before_player_cp is not None:
            eval_after_player_cp = eval_before_player_cp - cp_loss

            # Already completely winning AND still completely winning.
            # Worst case is "inaccuracy" — never blunder/mistake.
            if eval_before_player_cp >= 500 and eval_after_player_cp >= 300:
                if cp_loss <= 30:
                    return MoveClassification.EXCELLENT
                elif cp_loss <= 150:
                    return MoveClassification.GOOD
                else:
                    return MoveClassification.INACCURACY

            # Already completely losing AND still completely losing.
            # Don't pile on penalties — the player is fighting a lost
            # game. Worst case "inaccuracy".
            if eval_before_player_cp <= -500 and eval_after_player_cp <= -300:
                if cp_loss <= 100:
                    return MoveClassification.GOOD
                else:
                    return MoveClassification.INACCURACY

            # Dropping FROM winning DOWN to balanced/losing — that's a
            # real blunder (threw the win). Use stricter threshold.
            if eval_before_player_cp >= 500 and eval_after_player_cp < 300:
                # threw a winning position
                if cp_loss >= 200:
                    return MoveClassification.BLUNDER
                elif cp_loss >= 100:
                    return MoveClassification.MISTAKE

        # Standard thresholds (no context, or in roughly balanced
        # positions where every centipawn matters)
        if cp_loss <= CP_THRESHOLDS["excellent"]:
            return MoveClassification.EXCELLENT
        elif cp_loss <= CP_THRESHOLDS["good"]:
            return MoveClassification.GOOD
        elif cp_loss <= CP_THRESHOLDS["inaccuracy"]:
            return MoveClassification.INACCURACY
        elif cp_loss <= CP_THRESHOLDS["mistake"]:
            return MoveClassification.MISTAKE
        else:
            return MoveClassification.BLUNDER

    def is_sacrifice(self, board: chess.Board, move: chess.Move) -> bool:
        """
        Detect if a move is a material sacrifice.

        A sacrifice means giving up more material than you capture.
        Examples: Queen takes pawn, Rook takes pawn, piece for pawn.
        Does NOT count equal exchanges (knight takes knight).
        """
        if not board.is_capture(move):
            return False

        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)

        # En passant
        if captured_piece is None and moving_piece and moving_piece.piece_type == chess.PAWN:
            return False

        if not moving_piece or not captured_piece:
            return False

        moving_value = PIECE_VALUES.get(moving_piece.piece_type, 0)
        captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)

        # Sacrifice = giving up strictly more material (at least 2 points gap)
        return moving_value > captured_value + 1

    def detect_brilliant(self, board: chess.Board, move: chess.Move, depth: int = DEFAULT_DEPTH) -> bool:
        """
        Detect if a move qualifies as brilliant.

        Chess.com criteria (simplified):
        1. The move is a sacrifice (gives up material)
        2. The move is the ONLY good move (all alternatives are significantly worse)
        3. The move is not a simple recapture

        Uses MultiPV analysis to check if alternatives are much worse.
        """
        if not self.engine:
            return False

        # Must be a sacrifice
        if not self.is_sacrifice(board, move):
            return False

        # Skip simple recaptures (if opponent just captured on the same square)
        if board.move_stack:
            last_move = board.move_stack[-1]
            if last_move.to_square == move.to_square:
                return False

        try:
            # MultiPV analysis: get top 3 moves
            infos = self.engine.analyse(
                board,
                chess.engine.Limit(depth=max(depth, 18)),
                multipv=3
            )

            if not infos or len(infos) < 2:
                return False

            # Get eval of best and second-best move
            best_score = infos[0]["score"].white()
            second_score = infos[1]["score"].white()

            # Check that our move IS the best move (or very close)
            best_pv = infos[0].get("pv", [])
            if not best_pv or best_pv[0] != move:
                # Our move isn't the engine's top choice — not brilliant
                # (could still be excellent but not the "only good move")
                return False

            # Calculate gap between best and second-best
            if best_score.is_mate() and not second_score.is_mate():
                # Best move leads to mate but alternative doesn't — brilliant
                return True

            if best_score.is_mate() and second_score.is_mate():
                # Both lead to mate — the sacrifice wasn't necessary
                return False

            if not best_score.is_mate() and not second_score.is_mate():
                gap = best_score.score() - second_score.score()
                # For the side making the move: gap should be large
                if board.turn == chess.BLACK:
                    gap = -gap
                return gap >= BRILLIANT_MULTIPV_GAP

            return False

        except Exception as e:
            logger.debug(f"Brilliant detection failed: {e}")
            return False


def calculate_accuracy(cp_losses: List[int], classifications: List[str] = None) -> float:
    """
    Calculate Chess.com CAPS2-style accuracy score (0-100).
    
    CAPS2 assigns scores based on move classifications, not raw cp loss.
    This produces scores that feel more like "school grades" (50-95 typical).
    
    Move scores (calibrated to match Chess.com CAPS2):
    - Best/Brilliant/Great: 100 points
    - Excellent: 98 points  
    - Good: 90 points
    - Inaccuracy: 65 points
    - Mistake: 35 points
    - Blunder: 0 points
    
    Chess.com also applies smoothing for mate-distance and consecutive blunders,
    which we approximate by being slightly generous on scores.
    """
    if not cp_losses:
        return 100.0
    
    # CAPS2-style move scores (calibrated to Chess.com)
    MOVE_SCORES = {
        "brilliant": 100,
        "great": 100,
        "best": 100,
        "excellent": 98,
        "good": 90,
        "book": 100,  # Opening book moves
        "inaccuracy": 65,
        "mistake": 35,
        "blunder": 0
    }
    
    total_score = 0
    num_moves = len(cp_losses)
    
    # If we have classifications, use them directly
    if classifications and len(classifications) == num_moves:
        prev_was_blunder = False
        for classification in classifications:
            score = MOVE_SCORES.get(classification, 75)  # Default to "good" range
            
            # CAPS2 smoothing: Reduce penalty for consecutive blunders
            if classification == "blunder" and prev_was_blunder:
                score = 15  # Second+ consecutive blunder gets partial credit
            
            total_score += score
            prev_was_blunder = (classification == "blunder")
    else:
        # Fall back to cp_loss-based classification
        for cp_loss in cp_losses:
            abs_loss = abs(cp_loss)
            if abs_loss <= CP_THRESHOLDS["excellent"]:
                total_score += MOVE_SCORES["excellent"]
            elif abs_loss <= CP_THRESHOLDS["good"]:
                total_score += MOVE_SCORES["good"]
            elif abs_loss <= CP_THRESHOLDS["inaccuracy"]:
                total_score += MOVE_SCORES["inaccuracy"]
            elif abs_loss <= CP_THRESHOLDS["mistake"]:
                total_score += MOVE_SCORES["mistake"]
            else:
                total_score += MOVE_SCORES["blunder"]
    
    accuracy = total_score / num_moves
    
    # CAPS2 typically produces scores between 50-95 for normal play
    return round(min(100, max(0, accuracy)), 1)


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
        white_classifications = []  # Track classifications for CAPS2-style accuracy
        black_classifications = []
        
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
                
                # Check if the game is over (checkmate, stalemate, etc.)
                is_checkmate = board.is_checkmate()
                
                # Evaluate position after the move
                current_eval, current_mate = engine.evaluate_position(board, depth)
                
                # CRITICAL FIX: If the played move IS the best move, cp_loss = 0
                # This handles checkmate moves and other cases where move == best_move
                if move == best_move:
                    cp_loss = 0
                # If the move delivers checkmate, it's always the best - no loss
                elif is_checkmate:
                    cp_loss = 0
                else:
                    # Calculate centipawn loss normally
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
                
                # Check for missed mate - but NOT if the player just delivered mate
                missed_mate = False
                if not is_checkmate:
                    missed_mate = prev_mate is not None and (
                        (is_white_move and prev_mate > 0 and (current_mate is None or current_mate <= 0)) or
                        (not is_white_move and prev_mate < 0 and (current_mate is None or current_mate >= 0))
                    )
                
                # Classify the move with position context.
                # Convert prev_eval (white's POV) to moving player's POV
                # so the classifier can apply winning-position grace.
                eval_before_player = prev_eval if is_white_move else -prev_eval
                classification = engine.classify_move(
                    cp_loss, missed_mate, eval_before_player_cp=eval_before_player,
                )

                # Detect sacrifice and brilliant moves
                move_is_sacrifice = False
                move_is_brilliant = False
                if classification in (MoveClassification.BEST, MoveClassification.EXCELLENT):
                    # Only check user's moves for brilliant (saves analysis time)
                    is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
                    if is_user_move:
                        board.pop()  # undo to check position before move
                        move_is_sacrifice = engine.is_sacrifice(board, move)
                        if move_is_sacrifice:
                            move_is_brilliant = engine.detect_brilliant(board, move, depth)
                            if move_is_brilliant:
                                classification = MoveClassification.BRILLIANT
                        board.push(move)  # redo

                # Track classifications for CAPS2-style accuracy
                classification_str = classification.value if hasattr(classification, 'value') else str(classification)
                if is_white_move:
                    white_classifications.append(classification_str)
                else:
                    black_classifications.append(classification_str)

                # Count classifications
                if classification == MoveClassification.BRILLIANT:
                    best_moves += 1  # brilliant counts as best for stats
                elif classification == MoveClassification.BLUNDER:
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
                    
                    # For mistakes/inaccuracies/blunders, get PV lines to explain WHY
                    pv_after_played = []
                    pv_after_best = []
                    threat_after_played = None
                    
                    is_bad_move = classification in [MoveClassification.INACCURACY, MoveClassification.MISTAKE, MoveClassification.BLUNDER]
                    
                    if is_bad_move:
                        # Get PV after the best move (what SHOULD have happened)
                        best_board = board.copy()
                        best_board.push(best_move)
                        pv_after_best = engine.get_principal_variation(best_board, depth=12, pv_length=4)
                        
                        # Get PV after the played move (shows the PROBLEM)
                        played_board = board.copy()
                        played_board.push(move)
                        pv_after_played = engine.get_principal_variation(played_board, depth=12, pv_length=4)
                        
                        # Get the immediate threat after the played move
                        threat_after_played = engine.get_threat(played_board, depth=12)
                    
                    board.push(move)
                    fen_after = board.fen()  # Store position after move
                    
                    # Detect turning point (eval swing >= 120 cp)
                    eval_swing = abs(current_eval - prev_eval)
                    is_turning_point = eval_swing >= 120 and not is_bad_move
                    
                    # If turning point but not already computed PV, compute now
                    if is_turning_point and not pv_after_played:
                        board.pop()
                        # Get PV after best move
                        best_board = board.copy()
                        best_board.push(best_move)
                        pv_after_best = engine.get_principal_variation(best_board, depth=12, pv_length=4)
                        
                        # Get PV after played move
                        played_board = board.copy()
                        played_board.push(move)
                        pv_after_played = engine.get_principal_variation(played_board, depth=12, pv_length=4)
                        
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
                        mate_in_after=current_mate,
                        pv_after_played=pv_after_played,
                        pv_after_best=pv_after_best,
                        threat_after_played=threat_after_played,
                        fen_after=fen_after,
                        is_turning_point=is_turning_point,
                        eval_swing=eval_swing,
                        is_sacrifice=move_is_sacrifice,
                        is_brilliant=move_is_brilliant
                    )
                    moves_analysis.append(move_eval)
                
                # Update previous evaluation for next iteration
                prev_eval = current_eval
                prev_mate = current_mate
        
        # Calculate accuracies using CAPS2-style scoring
        accuracy_white = calculate_accuracy(white_cp_losses, white_classifications)
        accuracy_black = calculate_accuracy(black_cp_losses, black_classifications)
        
        # User-specific stats
        user_moves = [m for m in moves_analysis]
        user_blunders = sum(1 for m in user_moves if m.classification == MoveClassification.BLUNDER)
        user_mistakes = sum(1 for m in user_moves if m.classification == MoveClassification.MISTAKE)
        user_inaccuracies = sum(1 for m in user_moves if m.classification == MoveClassification.INACCURACY)
        user_best_moves = sum(1 for m in user_moves if m.classification in (MoveClassification.BEST, MoveClassification.BRILLIANT))
        user_excellent = sum(1 for m in user_moves if m.classification == MoveClassification.EXCELLENT)
        user_brilliant = sum(1 for m in user_moves if m.classification == MoveClassification.BRILLIANT)
        user_sacrifices = sum(1 for m in user_moves if m.is_sacrifice)

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
                    "fen_after": m.fen_after,
                    "evaluation": m.classification,
                    "cp_loss": m.cp_loss,
                    "eval_before": m.eval_before,
                    "eval_after": m.eval_after,
                    "eval_swing": m.eval_swing,
                    "best_move": m.best_move_san,
                    "best_move_uci": m.best_move_uci,
                    "is_best": m.cp_loss <= CP_THRESHOLDS["excellent"],
                    "is_turning_point": m.is_turning_point,
                    "mate_info": {
                        "before": m.mate_in_before,
                        "after": m.mate_in_after
                    } if m.is_mate_before or m.is_mate_after else None,
                    # PV data for explaining WHY moves are good/bad
                    "pv_after_played": m.pv_after_played,   # Line showing the problem
                    "pv_after_best": m.pv_after_best,       # Line showing better continuation
                    "threat": m.threat_after_played,        # Immediate threat opponent has
                    # Brilliant move data
                    "is_sacrifice": m.is_sacrifice,
                    "is_brilliant": m.is_brilliant
                }
                for m in moves_analysis
            ],
            "user_stats": {
                "blunders": user_blunders,
                "mistakes": user_mistakes,
                "inaccuracies": user_inaccuracies,
                "best_moves": user_best_moves,
                "excellent_moves": user_excellent,
                "brilliant_moves": user_brilliant,
                "sacrifices": user_sacrifices,
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
