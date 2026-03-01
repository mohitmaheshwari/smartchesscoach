"""
Coach Opponent - Engine that plays against the user

Step 1: Simple strongest-move engine using Stockfish.

Later phases will add:
- Pedagogical opponent (creates instructive scenarios)
- Difficulty matching
- Intentional mistake creation for teaching moments

Key principle: Don't overengineer in early iteration.
Interception matters more than fancy opponent weighting.

Skill Level to Rating approximation:
- Skill 0: ~800 Elo
- Skill 5: ~1200 Elo
- Skill 10: ~1600 Elo
- Skill 15: ~2000 Elo
- Skill 20: ~3200+ Elo (full strength)
"""

import chess
import chess.engine
import asyncio
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

STOCKFISH_PATH = "/usr/games/stockfish"

# Thread pool for Stockfish calls (blocking)
_executor = ThreadPoolExecutor(max_workers=2)

# Map user rating to Stockfish skill level (0-20)
def rating_to_skill_level(user_rating: int) -> int:
    """Convert user rating to Stockfish skill level"""
    if user_rating < 800:
        return 0
    elif user_rating < 1000:
        return 3
    elif user_rating < 1200:
        return 5
    elif user_rating < 1400:
        return 8
    elif user_rating < 1600:
        return 10
    elif user_rating < 1800:
        return 12
    elif user_rating < 2000:
        return 15
    elif user_rating < 2200:
        return 17
    else:
        return 20  # Full strength


class CoachOpponent:
    """
    Coach opponent engine.
    
    Plays at a skill level matched to the user's rating.
    Also provides position evaluation for the eval bar.
    """
    
    def __init__(self, user_rating: int = 1200, depth: int = 10, time_limit: float = 0.5):
        """
        Initialize coach opponent.
        
        Args:
            user_rating: User's rating to match difficulty
            depth: Search depth for Stockfish
            time_limit: Time limit per move in seconds
        """
        self.user_rating = user_rating
        self.skill_level = rating_to_skill_level(user_rating)
        self.depth = depth
        self.time_limit = time_limit
    
    async def get_move(self, fen: str) -> Optional[str]:
        """
        Get the coach's move for a given position.
        
        Args:
            fen: Current position in FEN notation
        
        Returns:
            Move in SAN notation, or None if no legal moves
        """
        loop = asyncio.get_event_loop()
        try:
            move = await loop.run_in_executor(
                _executor,
                self._get_move_sync,
                fen
            )
            return move
        except Exception as e:
            print(f"CoachOpponent error: {e}")
            return self._get_fallback_move(fen)
    
    async def get_evaluation(self, fen: str) -> Tuple[float, Optional[int]]:
        """
        Get position evaluation.
        
        Args:
            fen: Position in FEN notation
        
        Returns:
            Tuple of (eval_score, mate_in) where:
            - eval_score: Centipawn score from white's perspective (e.g., 1.5 = +1.5 pawns for white)
            - mate_in: Number of moves to mate (positive = white mates, negative = black mates), or None
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                _executor,
                self._get_eval_sync,
                fen
            )
            return result
        except Exception as e:
            print(f"Evaluation error: {e}")
            return (0.0, None)
    
    def _get_move_sync(self, fen: str) -> Optional[str]:
        """Synchronous Stockfish call with skill level"""
        board = chess.Board(fen)
        
        if board.is_game_over():
            return None
        
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                # Set skill level to match user's rating
                engine.configure({"Skill Level": self.skill_level})
                
                # Use time limit for speed
                result = engine.play(
                    board,
                    chess.engine.Limit(time=self.time_limit, depth=self.depth)
                )
                
                if result.move:
                    return board.san(result.move)
                return None
                
        except Exception as e:
            print(f"Stockfish error: {e}")
            return self._get_fallback_move(fen)
    
    def _get_eval_sync(self, fen: str) -> Tuple[float, Optional[int]]:
        """Get position evaluation synchronously"""
        board = chess.Board(fen)
        
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                info = engine.analyse(board, chess.engine.Limit(depth=12, time=0.3))
                score = info.get("score")
                
                if score:
                    pov_score = score.white()  # Always from white's perspective
                    
                    if pov_score.is_mate():
                        mate_in = pov_score.mate()
                        # Cap eval at ±10 for display purposes when mate
                        eval_score = 10.0 if mate_in > 0 else -10.0
                        return (eval_score, mate_in)
                    else:
                        # Convert centipawns to pawns
                        cp = pov_score.score()
                        eval_score = cp / 100.0 if cp else 0.0
                        # Cap at ±10 for display
                        eval_score = max(-10.0, min(10.0, eval_score))
                        return (eval_score, None)
                
                return (0.0, None)
                
        except Exception as e:
            print(f"Eval error: {e}")
            return (0.0, None)
    
    def _get_fallback_move(self, fen: str) -> Optional[str]:
        """Fallback: return first legal move"""
        try:
            board = chess.Board(fen)
            legal_moves = list(board.legal_moves)
            if legal_moves:
                return board.san(legal_moves[0])
        except Exception:
            pass
        return None


class PedagogicalOpponent(CoachOpponent):
    """
    Future: Pedagogical opponent that creates instructive scenarios.
    
    Will be implemented in later phases.
    For now, just uses parent class (strongest move).
    """
    
    def __init__(self, user_rating: int = 1200, teaching_mode: str = "balanced"):
        """
        Initialize pedagogical opponent.
        
        Args:
            user_rating: User's estimated rating for difficulty matching
            teaching_mode: "challenging", "balanced", or "supportive"
        """
        super().__init__()
        self.user_rating = user_rating
        self.teaching_mode = teaching_mode
    
    async def get_move(self, fen: str) -> Optional[str]:
        """
        Get pedagogical move.
        
        Future implementation will:
        - Sometimes play sub-optimal moves to create learning opportunities
        - Match difficulty to user level
        - Create tactical scenarios based on user's weaknesses
        
        For now, just plays strongest move.
        """
        # TODO: Implement pedagogical logic in Phase 3+
        return await super().get_move(fen)
