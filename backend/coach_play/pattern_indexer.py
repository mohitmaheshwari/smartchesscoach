"""
Pattern Indexer - Deterministic Cross-Game Pattern Recall

This is the CORE of personalization. NOT about LLM phrasing.
It's about STRUCTURED, DETERMINISTIC pattern retrieval.

Key Concepts:
1. Each position/mistake is tagged with a MOTIF (CognitiveGap enum)
2. We index games by these motifs for fast retrieval
3. When a new position matches a motif, we retrieve the EXACT past game ID
4. Only THEN do we pass to LLM for phrasing

The test should verify:
- Was the correct past game ID retrieved?
- Was the correct motif matched?
- Was the injection into LLM context correct?

NOT: "Did the LLM mention something about past games?"
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import chess

# Import CognitiveGap from existing service
import sys
sys.path.insert(0, '/app/backend')
from cognitive_gap_service import CognitiveGap, find_hanging_pieces, find_threats


@dataclass
class PatternMatch:
    """A deterministic pattern match result"""
    matched: bool
    motif: Optional[CognitiveGap]
    past_game_id: Optional[str]
    past_move_number: Optional[int]
    opponent: Optional[str]
    when: Optional[str]
    what_happened: Optional[str]
    confidence: float  # 0.0 to 1.0


@dataclass
class IndexedPattern:
    """A pattern indexed from a past game"""
    game_id: str
    move_number: int
    fen: str
    motif: CognitiveGap
    theme: str  # Additional theme tag
    eval_context: str  # "winning", "equal", "losing"
    opponent: str
    date: datetime
    what_happened: str  # "Lost queen to knight fork"


class PatternIndexer:
    """
    Deterministic pattern index for cross-game recall.
    
    This is NOT LLM-based. It's a structured retrieval system.
    """
    
    # Motif detection thresholds
    FORK_MATERIAL_THRESHOLD = 300  # cp loss indicates fork-like pattern
    KING_SAFETY_THRESHOLD = 400  # cp loss when king is exposed
    
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        self._pattern_index: List[IndexedPattern] = []
        self._loaded = False
    
    async def build_index(self, max_games: int = 50) -> int:
        """
        Build pattern index from user's game history.
        
        Returns: Number of patterns indexed
        """
        # Get analyzed games with stockfish data
        cursor = self.db.game_analyses.find(
            {"user_id": self.user_id}
        ).sort("analyzed_at", -1).limit(max_games)
        
        patterns_count = 0
        async for game in cursor:
            game_id = game.get("game_id")
            sf_analysis = game.get("stockfish_analysis", {})
            move_evals = sf_analysis.get("move_evaluations", [])
            opponent = game.get("opponent", "unknown")
            
            analyzed_at = game.get("analyzed_at")
            if isinstance(analyzed_at, str):
                try:
                    analyzed_at = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00'))
                except:
                    analyzed_at = datetime.now(timezone.utc)
            elif not analyzed_at:
                analyzed_at = datetime.now(timezone.utc)
            
            # Index each blunder/mistake with its motif
            for m in move_evals:
                if m.get("evaluation") not in ["blunder", "mistake"]:
                    continue
                
                fen_before = m.get("fen_before")
                if not fen_before:
                    continue
                
                cp_loss = m.get("cp_loss", 0)
                eval_before = m.get("eval_before", 0)
                
                # Determine eval context
                if eval_before > 1.0:
                    eval_context = "winning"
                elif eval_before < -1.0:
                    eval_context = "losing"
                else:
                    eval_context = "equal"
                
                # Detect motif from position
                motif, theme = self._detect_motif(fen_before, m)
                
                if motif == CognitiveGap.UNCLEAR:
                    continue
                
                # Generate what_happened description
                what_happened = self._describe_mistake(m, motif)
                
                indexed = IndexedPattern(
                    game_id=game_id,
                    move_number=m.get("move_number", 0),
                    fen=fen_before,
                    motif=motif,
                    theme=theme,
                    eval_context=eval_context,
                    opponent=opponent,
                    date=analyzed_at,
                    what_happened=what_happened
                )
                
                self._pattern_index.append(indexed)
                patterns_count += 1
        
        self._loaded = True
        return patterns_count
    
    def _detect_motif(self, fen: str, move_eval: Dict) -> Tuple[CognitiveGap, str]:
        """
        Detect the specific motif/theme of a mistake.
        
        This is DETERMINISTIC - based on position features, not LLM.
        Returns: (CognitiveGap, theme_description)
        """
        try:
            board = chess.Board(fen)
        except:
            return CognitiveGap.UNCLEAR, ""
        
        cp_loss = move_eval.get("cp_loss", 0)
        best_move = move_eval.get("best_move", "")
        played_move = move_eval.get("move", "")
        
        # Check for king safety issues
        if self._is_king_exposed(board):
            if cp_loss >= self.KING_SAFETY_THRESHOLD:
                return CognitiveGap.KING_SAFETY_NEGLECT, "king_safety"
        
        # Check for fork patterns
        if self._detects_fork_pattern(board, best_move):
            return CognitiveGap.MISSED_FORK, "knight_fork"
        
        # Check for hanging piece
        color = board.turn
        hanging = find_hanging_pieces(board, color)
        if hanging and cp_loss >= 200:
            return CognitiveGap.HANGING_PIECE_BLINDNESS, "hanging_piece"
        
        # Check for threat blindness
        opponent_threats = find_threats(board, not color)
        high_threats = [t for t in opponent_threats if t.get("severity") == "high"]
        if high_threats and cp_loss >= 200:
            return CognitiveGap.THREAT_BLINDNESS, "threat_ignored"
        
        # Check for back rank issues
        if self._is_back_rank_weak(board, color):
            return CognitiveGap.BACK_RANK_BLINDNESS, "back_rank"
        
        # Check for pin patterns
        if self._detects_pin_pattern(board, best_move):
            return CognitiveGap.MISSED_PIN, "pin"
        
        # Generic tactical oversight
        if cp_loss >= 150:
            return CognitiveGap.TACTICAL_OVERSIGHT, "tactical"
        
        return CognitiveGap.UNCLEAR, ""
    
    def _is_king_exposed(self, board: chess.Board) -> bool:
        """Check if the side-to-move's king is exposed."""
        color = board.turn
        king_sq = board.king(color)
        if not king_sq:
            return False
        
        # King in center and not castled
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        
        home_rank = 0 if color == chess.WHITE else 7
        
        # King still on home rank but not on g or c file (not castled)
        if king_rank == home_rank and king_file in [3, 4]:  # d or e file
            return True
        
        # Check pawn shelter
        pawn_shield = 0
        for file_offset in [-1, 0, 1]:
            shield_file = king_file + file_offset
            if 0 <= shield_file <= 7:
                shield_rank = king_rank + (1 if color == chess.WHITE else -1)
                if 0 <= shield_rank <= 7:
                    piece = board.piece_at(chess.square(shield_file, shield_rank))
                    if piece and piece.piece_type == chess.PAWN and piece.color == color:
                        pawn_shield += 1
        
        return pawn_shield == 0 and king_rank != home_rank
    
    def _detects_fork_pattern(self, board: chess.Board, best_move: str) -> bool:
        """Check if best move creates a fork."""
        if not best_move:
            return False
        
        try:
            move = board.parse_san(best_move)
            board_after = board.copy()
            board_after.push(move)
            
            # Check if the moved piece attacks multiple high-value pieces
            to_sq = move.to_square
            piece = board_after.piece_at(to_sq)
            if not piece:
                return False
            
            # Knight forks are most common
            if piece.piece_type == chess.KNIGHT:
                attacked = list(board_after.attacks(to_sq))
                high_value_targets = 0
                for sq in attacked:
                    target = board_after.piece_at(sq)
                    if target and target.color != piece.color:
                        if target.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                            high_value_targets += 1
                
                return high_value_targets >= 2
            
        except:
            pass
        
        return False
    
    def _detects_pin_pattern(self, board: chess.Board, best_move: str) -> bool:
        """Check if best move creates or exploits a pin."""
        if not best_move:
            return False
        
        # Simplified: check if move is by bishop/rook/queen on a file/diagonal with king behind
        try:
            move = board.parse_san(best_move)
            piece = board.piece_at(move.from_square)
            if piece and piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                return True  # Simplified - could be a pin
        except:
            pass
        
        return False
    
    def _is_back_rank_weak(self, board: chess.Board, color: chess.Color) -> bool:
        """Check if back rank is weak (no escape squares for king)."""
        king_sq = board.king(color)
        if not king_sq:
            return False
        
        back_rank = 0 if color == chess.WHITE else 7
        king_rank = chess.square_rank(king_sq)
        
        # King must be on back rank
        if king_rank != back_rank:
            return False
        
        # Check if king has escape squares
        for sq in board.attacks(king_sq):
            sq_rank = chess.square_rank(sq)
            if sq_rank != back_rank:  # Escape to next rank
                piece = board.piece_at(sq)
                if not piece or piece.color != color:
                    return False  # Has escape
        
        return True
    
    def _describe_mistake(self, move_eval: Dict, motif: CognitiveGap) -> str:
        """Generate a short description of what happened."""
        played = move_eval.get("move", "?")
        best = move_eval.get("best_move", "?")
        cp_loss = move_eval.get("cp_loss", 0)
        
        descriptions = {
            CognitiveGap.MISSED_FORK: f"Missed fork with {best}, played {played} instead",
            CognitiveGap.KING_SAFETY_NEGLECT: f"Ignored king safety, played {played}",
            CognitiveGap.HANGING_PIECE_BLINDNESS: f"Left piece hanging with {played}",
            CognitiveGap.THREAT_BLINDNESS: f"Missed threat, played {played}",
            CognitiveGap.BACK_RANK_BLINDNESS: f"Ignored back rank weakness with {played}",
            CognitiveGap.MISSED_PIN: f"Missed pin with {best}, played {played}",
            CognitiveGap.TACTICAL_OVERSIGHT: f"Missed tactic: {best} was better than {played}",
        }
        
        return descriptions.get(motif, f"Mistake with {played}, {best} was better")
    
    async def find_similar_pattern(
        self,
        current_fen: str,
        current_motif: CognitiveGap,
        current_game_id: str = None
    ) -> PatternMatch:
        """
        Find a DETERMINISTIC match from past games.
        
        This is the core retrieval function.
        Returns exact game_id of the match, not fuzzy text.
        """
        if not self._loaded:
            await self.build_index()
        
        # Filter patterns by motif (EXACT match)
        matches = [
            p for p in self._pattern_index
            if p.motif == current_motif and p.game_id != current_game_id
        ]
        
        if not matches:
            return PatternMatch(
                matched=False,
                motif=None,
                past_game_id=None,
                past_move_number=None,
                opponent=None,
                when=None,
                what_happened=None,
                confidence=0.0
            )
        
        # Sort by recency (most recent first)
        matches.sort(key=lambda x: x.date, reverse=True)
        best_match = matches[0]
        
        # Format date
        days_ago = (datetime.now(timezone.utc) - best_match.date.replace(tzinfo=timezone.utc)).days
        if days_ago == 0:
            when = "earlier today"
        elif days_ago == 1:
            when = "yesterday"
        elif days_ago < 7:
            when = f"{days_ago} days ago"
        else:
            when = f"on {best_match.date.strftime('%b %d')}"
        
        return PatternMatch(
            matched=True,
            motif=current_motif,
            past_game_id=best_match.game_id,
            past_move_number=best_match.move_number,
            opponent=best_match.opponent,
            when=when,
            what_happened=best_match.what_happened,
            confidence=0.9  # High confidence for exact motif match
        )
    
    def detect_current_motif(self, fen: str, cp_loss: int, best_move: str) -> CognitiveGap:
        """
        Detect motif for current position.
        
        Used to find what pattern the user is about to make/made.
        """
        move_eval = {
            "cp_loss": cp_loss,
            "best_move": best_move,
        }
        motif, _ = self._detect_motif(fen, move_eval)
        return motif


async def get_pattern_retrieval(
    db,
    user_id: str,
    current_fen: str,
    current_motif: CognitiveGap,
    current_game_id: str = None
) -> Dict[str, Any]:
    """
    Main entry point for deterministic pattern retrieval.
    
    Returns structured data for LLM injection:
    - matched: bool
    - past_game_id: exact ID for verification
    - injection_context: formatted text for LLM prompt
    """
    indexer = PatternIndexer(db, user_id)
    match = await indexer.find_similar_pattern(current_fen, current_motif, current_game_id)
    
    if not match.matched:
        return {
            "matched": False,
            "past_game_id": None,
            "injection_context": None
        }
    
    # Format injection context for LLM
    injection = f"""PERSONAL HISTORY (Reference this in your response!):
The user made a similar mistake ({match.motif.value}) in a game against {match.opponent} {match.when}.
What happened: {match.what_happened}
Game ID: {match.past_game_id}, Move: {match.past_move_number}
>>> SAY: "Remember your game against {match.opponent}? This is the same pattern."
"""
    
    return {
        "matched": True,
        "past_game_id": match.past_game_id,
        "past_move_number": match.past_move_number,
        "motif": match.motif.value,
        "opponent": match.opponent,
        "when": match.when,
        "what_happened": match.what_happened,
        "confidence": match.confidence,
        "injection_context": injection
    }
