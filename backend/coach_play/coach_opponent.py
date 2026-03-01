"""
Coach Opponent - Engine that plays against the user

Step 1: Simple strongest-move engine using Stockfish.

Later phases will add:
- Pedagogical opponent (creates instructive scenarios)
- Difficulty matching
- Intentional mistake creation for teaching moments

Key principle: Don't overengineer in early iteration.
Interception matters more than fancy opponent weighting.
"""

import chess
import chess.engine
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

STOCKFISH_PATH = "/usr/games/stockfish"

# Thread pool for Stockfish calls (blocking)
_executor = ThreadPoolExecutor(max_workers=2)


class CoachOpponent:
    """
    Coach opponent engine.
    
    Step 1: Just plays the strongest move using Stockfish.
    Uses low depth for fast responses in rapid games.
    """
    
    def __init__(self, depth: int = 12, time_limit: float = 0.5):
        """
        Initialize coach opponent.
        
        Args:
            depth: Search depth for Stockfish (lower = faster)
            time_limit: Time limit per move in seconds
        """
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
    
    def _get_move_sync(self, fen: str) -> Optional[str]:
        """Synchronous Stockfish call"""
        board = chess.Board(fen)
        
        if board.is_game_over():
            return None
        
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
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
    
    def _get_fallback_move(self, fen: str) -> Optional[str]:
        """Fallback: return first legal move"""
        try:
            board = chess.Board(fen)
            legal_moves = list(board.legal_moves)
            if legal_moves:
                return board.san(legal_moves[0])
        except:
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
