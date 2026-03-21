"""
Chess Theory Service

Reads the admin-editable chess_theory.json and matches positions against known patterns.
Provides explanations based on documented opening and endgame theory.

This is the "smart class" that:
1. Loads theory from JSON
2. Matches Stockfish analysis to known patterns
3. Returns theory-based explanations when available
4. Falls back to line parsing when no theory match
"""

import json
import os
import chess
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Path to the theory database
THEORY_DB_PATH = Path(__file__).parent.parent / "data" / "chess_theory.json"


class ChessTheoryService:
    """Service to match positions against the theory database."""
    
    def __init__(self):
        self.theory_db = None
        self.opening_patterns = {}
        self.endgame_patterns = {}
        self.tactical_patterns = {}
        self._load_theory()
    
    def _load_theory(self):
        """Load theory database from JSON."""
        try:
            if THEORY_DB_PATH.exists():
                with open(THEORY_DB_PATH, 'r') as f:
                    self.theory_db = json.load(f)
                
                # Index patterns for fast lookup
                self.opening_patterns = self.theory_db.get("opening_theory", {})
                self.endgame_patterns = self.theory_db.get("endgame_theory", {})
                self.tactical_patterns = self.theory_db.get("tactical_patterns", {})
                
                # Remove meta fields
                for patterns in [self.opening_patterns, self.endgame_patterns, self.tactical_patterns]:
                    patterns.pop("_description", None)
                
                logger.info(f"Loaded {len(self.opening_patterns)} opening patterns, "
                           f"{len(self.endgame_patterns)} endgame patterns, "
                           f"{len(self.tactical_patterns)} tactical patterns")
            else:
                logger.warning(f"Theory database not found at {THEORY_DB_PATH}")
        except Exception as e:
            logger.error(f"Error loading theory database: {e}")
    
    def reload_theory(self):
        """Reload theory from JSON (call after admin updates)."""
        self._load_theory()
    
    def match_opening_theory(
        self, 
        fen: str, 
        played_move: str, 
        best_move: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if position + moves match a known opening pattern.
        
        Returns theory dict if match found, None otherwise.
        """
        # Normalize moves
        played_clean = played_move.lower().replace("+", "").replace("#", "").replace("x", "")
        best_clean = best_move.lower().replace("+", "").replace("#", "").replace("x", "")
        
        # Extract board position (ignore castling rights, move counters)
        try:
            board = chess.Board(fen)
            board_fen = board.board_fen()  # Just piece positions
        except (ValueError, chess.InvalidMoveError):
            return None
        
        for pattern_id, pattern in self.opening_patterns.items():
            # Skip non-dict entries
            if not isinstance(pattern, dict):
                continue
            
            # Check FEN pattern match
            pattern_fen = pattern.get("fen_pattern", "")
            if not pattern_fen:
                continue
            
            try:
                pattern_board = chess.Board(pattern_fen)
                pattern_board_fen = pattern_board.board_fen()
            except (ValueError, chess.InvalidMoveError):
                continue
            
            # Check if positions match (just pieces, ignore other FEN parts)
            if board_fen != pattern_board_fen:
                continue
            
            # Check if moves match
            pattern_bad = pattern.get("bad_move", "").lower()
            pattern_good = pattern.get("good_move", "").lower()
            
            # Normalize pattern moves
            pattern_bad_clean = pattern_bad.replace("+", "").replace("#", "").replace("x", "")
            pattern_good_clean = pattern_good.replace("+", "").replace("#", "").replace("x", "")
            
            if played_clean == pattern_bad_clean and best_clean == pattern_good_clean:
                return {
                    "pattern_id": pattern_id,
                    "name": pattern.get("name", "Opening Pattern"),
                    "eco": pattern.get("eco"),
                    "explanation": pattern.get("explanation", ""),
                    "why_bad": pattern.get("why_bad", ""),
                    "why_good": pattern.get("why_good", ""),
                    "rule": pattern.get("rule", ""),
                    "category": pattern.get("category", "opening"),
                    "difficulty": pattern.get("difficulty", "intermediate")
                }
        
        return None
    
    def match_endgame_theory(self, fen: str) -> Optional[Dict[str, Any]]:
        """
        Check if position matches a known endgame pattern.
        
        Returns theory dict if match found, None otherwise.
        """
        try:
            board = chess.Board(fen)
        except (ValueError, chess.InvalidMoveError):
            return None
        
        # Count material to determine endgame type
        white_pieces = {
            "K": len(board.pieces(chess.KING, chess.WHITE)),
            "Q": len(board.pieces(chess.QUEEN, chess.WHITE)),
            "R": len(board.pieces(chess.ROOK, chess.WHITE)),
            "B": len(board.pieces(chess.BISHOP, chess.WHITE)),
            "N": len(board.pieces(chess.KNIGHT, chess.WHITE)),
            "P": len(board.pieces(chess.PAWN, chess.WHITE)),
        }
        black_pieces = {
            "K": len(board.pieces(chess.KING, chess.BLACK)),
            "Q": len(board.pieces(chess.QUEEN, chess.BLACK)),
            "R": len(board.pieces(chess.ROOK, chess.BLACK)),
            "B": len(board.pieces(chess.BISHOP, chess.BLACK)),
            "N": len(board.pieces(chess.KNIGHT, chess.BLACK)),
            "P": len(board.pieces(chess.PAWN, chess.BLACK)),
        }
        
        # Determine endgame type
        total_material = sum(white_pieces.values()) + sum(black_pieces.values()) - 2  # Exclude kings
        
        # Only match endgame theory in actual endgames
        if total_material > 10:
            return None
        
        # Check for specific endgame types
        pattern_type = None
        
        # Rook endgames
        if (white_pieces["R"] >= 1 or black_pieces["R"] >= 1) and \
           white_pieces["Q"] == 0 and black_pieces["Q"] == 0:
            pattern_type = "rook_endgame"
        
        # King and pawn
        elif total_material <= 3 and (white_pieces["P"] >= 1 or black_pieces["P"] >= 1):
            pattern_type = "KP_vs_K"
        
        # Bishop endgames
        elif (white_pieces["B"] >= 1 or black_pieces["B"] >= 1) and \
             white_pieces["R"] == 0 and black_pieces["R"] == 0 and \
             white_pieces["Q"] == 0 and black_pieces["Q"] == 0:
            
            # Check for opposite colored bishops
            white_bishops = list(board.pieces(chess.BISHOP, chess.WHITE))
            black_bishops = list(board.pieces(chess.BISHOP, chess.BLACK))
            
            if white_bishops and black_bishops:
                white_square_color = chess.square_color(white_bishops[0])
                black_square_color = chess.square_color(black_bishops[0])
                
                if white_square_color != black_square_color:
                    pattern_type = "bishop_endgame"
        
        # Minor piece endgames
        elif (white_pieces["B"] + white_pieces["N"] + black_pieces["B"] + black_pieces["N"]) >= 1:
            pattern_type = "minor_piece_endgame"
        
        # Find matching theory
        if pattern_type:
            for pattern_id, pattern in self.endgame_patterns.items():
                if not isinstance(pattern, dict):
                    continue
                
                if pattern.get("pattern_type") == pattern_type:
                    return {
                        "pattern_id": pattern_id,
                        "name": pattern.get("name", "Endgame Pattern"),
                        "key_rule": pattern.get("key_rule", ""),
                        "explanation": pattern.get("explanation", ""),
                        "common_mistake": pattern.get("common_mistake", ""),
                        "correct_technique": pattern.get("correct_technique", ""),
                        "rule": pattern.get("rule", ""),
                        "category": pattern.get("category", "endgame"),
                        "difficulty": pattern.get("difficulty", "intermediate")
                    }
        
        return None
    
    def match_tactical_pattern(self, pattern_type: str) -> Optional[Dict[str, Any]]:
        """
        Get tactical pattern info by type.
        
        pattern_type: "hanging_piece", "pin", "fork", "back_rank", "discovered"
        """
        for pattern_id, pattern in self.tactical_patterns.items():
            if not isinstance(pattern, dict):
                continue
            
            if pattern.get("pattern_type") == pattern_type:
                return {
                    "pattern_id": pattern_id,
                    "name": pattern.get("name", "Tactical Pattern"),
                    "rule": pattern.get("rule", ""),
                    "explanation": pattern.get("explanation", ""),
                    "category": pattern.get("category", "tactical"),
                    "difficulty": pattern.get("difficulty", "beginner")
                }
        
        return None
    
    def get_all_opening_patterns(self) -> List[Dict[str, Any]]:
        """Get all opening patterns (for admin view)."""
        patterns = []
        for pattern_id, pattern in self.opening_patterns.items():
            if isinstance(pattern, dict):
                patterns.append({
                    "id": pattern_id,
                    **pattern
                })
        return patterns
    
    def get_all_endgame_patterns(self) -> List[Dict[str, Any]]:
        """Get all endgame patterns (for admin view)."""
        patterns = []
        for pattern_id, pattern in self.endgame_patterns.items():
            if isinstance(pattern, dict):
                patterns.append({
                    "id": pattern_id,
                    **pattern
                })
        return patterns
    
    def get_all_tactical_patterns(self) -> List[Dict[str, Any]]:
        """Get all tactical patterns (for admin view)."""
        patterns = []
        for pattern_id, pattern in self.tactical_patterns.items():
            if isinstance(pattern, dict):
                patterns.append({
                    "id": pattern_id,
                    **pattern
                })
        return patterns
    
    def get_theory_stats(self) -> Dict[str, int]:
        """Get counts of theory patterns."""
        return {
            "opening_patterns": len([p for p in self.opening_patterns.values() if isinstance(p, dict)]),
            "endgame_patterns": len([p for p in self.endgame_patterns.values() if isinstance(p, dict)]),
            "tactical_patterns": len([p for p in self.tactical_patterns.values() if isinstance(p, dict)]),
            "total": (
                len([p for p in self.opening_patterns.values() if isinstance(p, dict)]) +
                len([p for p in self.endgame_patterns.values() if isinstance(p, dict)]) +
                len([p for p in self.tactical_patterns.values() if isinstance(p, dict)])
            )
        }


# Singleton instance
_theory_service = None


def get_theory_service() -> ChessTheoryService:
    """Get the singleton theory service instance."""
    global _theory_service
    if _theory_service is None:
        _theory_service = ChessTheoryService()
    return _theory_service
