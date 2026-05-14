"""
Deep Position Analyzer for Auto-Correction System

This module provides REAL chess understanding by analyzing positions deeply.
It extracts tactical patterns, piece relationships, king safety, and geometry
from actual board positions - not just keyword matching.

When a user says "knight forks my king and queen", this module:
1. Finds where the knight, king, and queen actually are
2. Analyzes the geometry of the attack
3. Understands WHY this is a fork (knight controls both squares)
4. Creates a rule that matches ANY similar geometric pattern

When a user says "king has no breathing space", this module:
1. Finds the king's position
2. Checks which pieces (own/enemy) block each adjacent square
3. Counts actual escape squares
4. Understands the pawn structure trapping the king
5. Creates a rule that matches ANY similar trapped king pattern
"""

import chess
import chess.engine
import os
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# Piece values
PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100
}

PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
}


class TacticalMotif(Enum):
    """Types of tactical patterns we can detect"""
    FORK = "fork"
    PIN = "pin"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    BACK_RANK_MATE = "back_rank_mate"
    KING_TRAPPED = "king_trapped"
    HANGING_PIECE = "hanging_piece"
    OVERLOADED_PIECE = "overloaded"
    TRAPPED_PIECE = "trapped_piece"
    DEFLECTION = "deflection"
    REMOVAL_OF_GUARD = "removal_of_guard"


@dataclass
class ForkPattern:
    """Detailed fork pattern extracted from position"""
    attacker_piece: str  # "knight", "pawn", etc.
    attacker_square: str  # "c7"
    attacker_color: str  # "white" or "black"
    targets: List[Dict]  # [{"piece": "king", "square": "e8", "value": 100}, ...]
    fork_geometry: str  # Description of the geometric pattern
    total_target_value: int
    can_escape: bool  # Can targets escape?
    best_response: Optional[str]  # Best defensive move if any
    
    def to_dict(self):
        return asdict(self)


@dataclass
class KingSafetyPattern:
    """Detailed king safety pattern extracted from position"""
    king_square: str
    king_color: str
    is_on_back_rank: bool
    escape_squares: List[str]  # Actual squares king can move to
    num_escape_squares: int
    blocked_by_own_pieces: List[Dict]  # [{"piece": "pawn", "square": "f2"}, ...]
    blocked_by_enemy_pieces: List[Dict]
    blocked_by_attacks: List[str]  # Squares controlled by enemy
    pawn_shield: Dict  # {"intact": True, "missing": ["h3"]}
    back_rank_attackers: List[Dict]  # Enemy rooks/queens that can attack back rank
    is_castled: bool
    luft_needed: bool  # Does king need escape square?
    suggested_luft_move: Optional[str]  # e.g., "h3" to create escape
    
    def to_dict(self):
        return asdict(self)


@dataclass 
class PinPattern:
    """Pin pattern extracted from position"""
    pinning_piece: str
    pinning_square: str
    pinned_piece: str
    pinned_square: str
    protected_piece: str  # Usually king
    protected_square: str
    pin_line: str  # "diagonal", "file", "rank"
    is_absolute: bool  # Absolute pin (to king) vs relative pin
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HangingPiecePattern:
    """Hanging piece pattern"""
    piece: str
    square: str
    value: int
    attackers: List[Dict]  # [{"piece": "knight", "square": "e5"}, ...]
    defenders: List[Dict]
    is_protected: bool
    can_be_captured_for_free: bool
    
    def to_dict(self):
        return asdict(self)


class DeepPositionAnalyzer:
    """
    Analyzes chess positions deeply to extract tactical patterns.
    
    This is the REAL chess intelligence that understands:
    - Where pieces are and their relationships
    - Geometric patterns (forks, pins, skewers)
    - King safety (escape squares, pawn shield, back rank)
    - Hanging pieces and tactical vulnerabilities
    """
    
    def __init__(self):
        self.stockfish_path = "/usr/games/stockfish"
        self._engine = None
    
    def _get_engine(self):
        """Get or create Stockfish engine"""
        if self._engine is None:
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            except Exception as e:
                logger.warning(f"Could not start Stockfish: {e}")
        return self._engine
    
    def close(self):
        """Close the engine"""
        if self._engine:
            self._engine.quit()
            self._engine = None
    
    # =========================================
    # FORK DETECTION
    # =========================================
    
    def find_forks(self, board: chess.Board, color: bool = None) -> List[ForkPattern]:
        """
        Find all fork patterns in the position.
        
        A fork is when one piece attacks two or more valuable pieces simultaneously.
        """
        forks = []
        
        if color is None:
            # Check both colors
            forks.extend(self._find_forks_for_color(board, chess.WHITE))
            forks.extend(self._find_forks_for_color(board, chess.BLACK))
        else:
            forks = self._find_forks_for_color(board, color)
        
        return forks
    
    def _find_forks_for_color(self, board: chess.Board, color: bool) -> List[ForkPattern]:
        """Find forks for a specific color"""
        forks = []
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue
            
            # Get all squares this piece attacks
            attacks = board.attacks(square)
            
            # Find valuable enemy pieces being attacked
            targets = []
            for target_sq in attacks:
                target_piece = board.piece_at(target_sq)
                if target_piece and target_piece.color != color:
                    value = PIECE_VALUES.get(target_piece.piece_type, 0)
                    if value >= 3:  # Knight value or higher
                        targets.append({
                            "piece": PIECE_NAMES[target_piece.piece_type],
                            "square": chess.square_name(target_sq),
                            "value": value
                        })
            
            # It's a fork if attacking 2+ valuable pieces
            if len(targets) >= 2:
                # Sort by value (highest first)
                targets.sort(key=lambda x: x["value"], reverse=True)
                
                # Describe the geometry
                piece_name = PIECE_NAMES[piece.piece_type]
                target_names = [t["piece"] for t in targets[:3]]
                geometry = f"{piece_name} on {chess.square_name(square)} simultaneously attacks {', '.join(target_names)}"
                
                fork = ForkPattern(
                    attacker_piece=piece_name,
                    attacker_square=chess.square_name(square),
                    attacker_color="white" if color == chess.WHITE else "black",
                    targets=targets,
                    fork_geometry=geometry,
                    total_target_value=sum(t["value"] for t in targets),
                    can_escape=self._can_escape_fork(board, targets),
                    best_response=None  # Could use Stockfish here
                )
                forks.append(fork)
        
        return forks
    
    def _can_escape_fork(self, board: chess.Board, targets: List[Dict]) -> bool:
        """Check if all forked pieces can escape"""
        # Simplified: if king is one of the targets, usually can escape
        for t in targets:
            if t["piece"] == "king":
                return True
        return False
    
    def find_potential_fork_squares(self, board: chess.Board, piece_type: int, color: bool) -> List[Dict]:
        """
        Find squares where a piece could move to create a fork.
        
        This is for detecting "walked into a fork" patterns.
        """
        potential_forks = []
        
        # For each square the piece could potentially reach
        for target_sq in chess.SQUARES:
            # Simulate piece being on this square
            attacks = self._get_attacks_from_square(piece_type, target_sq, board)
            
            # Find valuable enemy pieces that would be attacked
            targets = []
            for att_sq in attacks:
                target_piece = board.piece_at(att_sq)
                if target_piece and target_piece.color != color:
                    value = PIECE_VALUES.get(target_piece.piece_type, 0)
                    if value >= 3:
                        targets.append({
                            "piece": PIECE_NAMES[target_piece.piece_type],
                            "square": chess.square_name(att_sq),
                            "value": value
                        })
            
            if len(targets) >= 2:
                potential_forks.append({
                    "fork_square": chess.square_name(target_sq),
                    "targets": targets,
                    "total_value": sum(t["value"] for t in targets)
                })
        
        return potential_forks
    
    def _get_attacks_from_square(self, piece_type: int, square: int, board: chess.Board) -> Set[int]:
        """Get squares a piece type would attack from a given square"""
        if piece_type == chess.KNIGHT:
            return chess.SquareSet(chess.BB_KNIGHT_ATTACKS[square])
        elif piece_type == chess.BISHOP:
            return board.attacks_mask(square) & chess.BB_DIAG_ATTACKS[square][0]
        elif piece_type == chess.ROOK:
            return board.attacks_mask(square) & (chess.BB_RANK_ATTACKS[square][0] | chess.BB_FILE_ATTACKS[square][0])
        elif piece_type == chess.QUEEN:
            return board.attacks_mask(square)
        elif piece_type == chess.KING:
            return chess.SquareSet(chess.BB_KING_ATTACKS[square])
        elif piece_type == chess.PAWN:
            # Pawn attacks depend on color - assume white for now
            return chess.SquareSet(chess.BB_PAWN_ATTACKS[chess.WHITE][square])
        return set()
    
    # =========================================
    # KING SAFETY ANALYSIS
    # =========================================
    
    def analyze_king_safety(self, board: chess.Board, color: bool) -> KingSafetyPattern:
        """
        Deep analysis of king safety.
        
        Checks:
        - Where is the king?
        - Is it on the back rank?
        - How many escape squares does it have?
        - What's blocking each adjacent square (own pieces, enemy pieces, enemy attacks)?
        - Is the pawn shield intact?
        - Are there back rank threats?
        """
        king_sq = board.king(color)
        if king_sq is None:
            return None
        
        king_rank = chess.square_rank(king_sq)
        back_rank = 0 if color == chess.WHITE else 7
        is_back_rank = king_rank == back_rank
        
        # Analyze each adjacent square
        adjacent_squares = list(board.attacks(king_sq))
        escape_squares = []
        blocked_by_own = []
        blocked_by_enemy = []
        blocked_by_attacks = []
        
        for sq in adjacent_squares:
            piece = board.piece_at(sq)
            
            if piece is None:
                # Empty square - check if it's attacked by enemy
                if board.is_attacked_by(not color, sq):
                    blocked_by_attacks.append(chess.square_name(sq))
                else:
                    escape_squares.append(chess.square_name(sq))
            elif piece.color == color:
                # Blocked by own piece
                blocked_by_own.append({
                    "piece": PIECE_NAMES[piece.piece_type],
                    "square": chess.square_name(sq)
                })
            else:
                # Blocked by enemy piece
                if not board.is_attacked_by(color, sq):
                    # Can't capture because not protected
                    blocked_by_enemy.append({
                        "piece": PIECE_NAMES[piece.piece_type],
                        "square": chess.square_name(sq)
                    })
                else:
                    # Can capture
                    escape_squares.append(chess.square_name(sq))
        
        # Analyze pawn shield
        pawn_shield = self._analyze_pawn_shield(board, king_sq, color)
        
        # Find back rank threats
        back_rank_attackers = self._find_back_rank_threats(board, color)
        
        # Check if castled (simplified)
        is_castled = king_rank == back_rank and chess.square_file(king_sq) in [1, 2, 6]  # b, c, g files
        
        # Determine if luft is needed
        luft_needed = is_back_rank and len(escape_squares) == 0 and len(back_rank_attackers) > 0
        
        # Suggest luft move
        suggested_luft = None
        if luft_needed:
            suggested_luft = self._suggest_luft_move(board, king_sq, color)
        
        return KingSafetyPattern(
            king_square=chess.square_name(king_sq),
            king_color="white" if color == chess.WHITE else "black",
            is_on_back_rank=is_back_rank,
            escape_squares=escape_squares,
            num_escape_squares=len(escape_squares),
            blocked_by_own_pieces=blocked_by_own,
            blocked_by_enemy_pieces=blocked_by_enemy,
            blocked_by_attacks=blocked_by_attacks,
            pawn_shield=pawn_shield,
            back_rank_attackers=back_rank_attackers,
            is_castled=is_castled,
            luft_needed=luft_needed,
            suggested_luft_move=suggested_luft
        )
    
    def _analyze_pawn_shield(self, board: chess.Board, king_sq: int, color: bool) -> Dict:
        """Analyze the pawn shield in front of the king"""
        king_file = chess.square_file(king_sq)
        chess.square_rank(king_sq)
        
        # Expected pawn shield squares (2nd/7th rank for white/black)
        if color == chess.WHITE:
            shield_rank = 1  # 2nd rank
            files_to_check = [max(0, king_file - 1), king_file, min(7, king_file + 1)]
        else:
            shield_rank = 6  # 7th rank
            files_to_check = [max(0, king_file - 1), king_file, min(7, king_file + 1)]
        
        intact_pawns = []
        missing_pawns = []
        advanced_pawns = []
        
        for f in files_to_check:
            shield_sq = chess.square(f, shield_rank)
            piece = board.piece_at(shield_sq)
            
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                intact_pawns.append(chess.square_name(shield_sq))
            else:
                # Check if pawn has advanced
                for r in range(shield_rank + (1 if color == chess.WHITE else -1), 
                              8 if color == chess.WHITE else -1,
                              1 if color == chess.WHITE else -1):
                    check_sq = chess.square(f, r)
                    p = board.piece_at(check_sq)
                    if p and p.piece_type == chess.PAWN and p.color == color:
                        advanced_pawns.append(chess.square_name(check_sq))
                        break
                else:
                    missing_pawns.append(chess.square_name(shield_sq))
        
        return {
            "intact": len(missing_pawns) == 0,
            "intact_pawns": intact_pawns,
            "missing_pawns": missing_pawns,
            "advanced_pawns": advanced_pawns
        }
    
    def _find_back_rank_threats(self, board: chess.Board, color: bool) -> List[Dict]:
        """Find enemy rooks/queens that could deliver back rank mate"""
        threats = []
        back_rank = 0 if color == chess.WHITE else 7
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color != color and piece.piece_type in [chess.ROOK, chess.QUEEN]:
                # Check if it can reach the back rank
                chess.square_file(sq)
                piece_rank = chess.square_rank(sq)
                
                # Rook/Queen on same file or can slide to back rank
                if piece_rank == back_rank or self._can_reach_rank(board, sq, back_rank, not color):
                    threats.append({
                        "piece": PIECE_NAMES[piece.piece_type],
                        "square": chess.square_name(sq),
                        "distance_to_back_rank": abs(piece_rank - back_rank)
                    })
        
        return threats
    
    def _can_reach_rank(self, board: chess.Board, from_sq: int, to_rank: int, color: bool) -> bool:
        """Check if a rook/queen can reach a specific rank"""
        piece = board.piece_at(from_sq)
        if piece is None:
            return False
        
        from_file = chess.square_file(from_sq)
        to_sq = chess.square(from_file, to_rank)
        
        # Check if path is clear
        attacks = board.attacks(from_sq)
        return to_sq in attacks
    
    def _suggest_luft_move(self, board: chess.Board, king_sq: int, color: bool) -> Optional[str]:
        """Suggest a pawn move to create escape square for king"""
        king_file = chess.square_file(king_sq)
        
        # Check pawns that could move to create escape
        if color == chess.WHITE:
            pawn_squares = [
                chess.square(f, 1) for f in [max(0, king_file-1), king_file, min(7, king_file+1)]
            ]
            advance_direction = 1
        else:
            pawn_squares = [
                chess.square(f, 6) for f in [max(0, king_file-1), king_file, min(7, king_file+1)]
            ]
            advance_direction = -1
        
        for sq in pawn_squares:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                # Suggest advancing this pawn
                dest_sq = chess.square(chess.square_file(sq), chess.square_rank(sq) + advance_direction)
                if board.piece_at(dest_sq) is None:
                    return chess.square_name(dest_sq)  # e.g., "h3"
        
        return None
    
    # =========================================
    # PIN DETECTION
    # =========================================
    
    def find_pins(self, board: chess.Board, color: bool = None) -> List[PinPattern]:
        """Find all pin patterns in the position"""
        pins = []
        
        if color is None:
            pins.extend(self._find_pins_for_color(board, chess.WHITE))
            pins.extend(self._find_pins_for_color(board, chess.BLACK))
        else:
            pins = self._find_pins_for_color(board, color)
        
        return pins
    
    def _find_pins_for_color(self, board: chess.Board, pinned_color: bool) -> List[PinPattern]:
        """Find pins against a specific color"""
        pins = []
        king_sq = board.king(pinned_color)
        if king_sq is None:
            return pins
        
        # Check all enemy sliding pieces
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None or piece.color == pinned_color:
                continue
            
            if piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                continue
            
            # Check if there's a ray between this piece and the king
            ray = chess.SquareSet.between(sq, king_sq)
            if not ray:
                continue
            
            # Check if exactly one friendly piece is in the ray
            pieces_in_ray = []
            for ray_sq in ray:
                ray_piece = board.piece_at(ray_sq)
                if ray_piece:
                    pieces_in_ray.append((ray_sq, ray_piece))
            
            if len(pieces_in_ray) == 1:
                pinned_sq, pinned_piece = pieces_in_ray[0]
                if pinned_piece.color == pinned_color:
                    # This is a pin!
                    # Determine pin line type
                    if chess.square_file(sq) == chess.square_file(king_sq):
                        pin_line = "file"
                    elif chess.square_rank(sq) == chess.square_rank(king_sq):
                        pin_line = "rank"
                    else:
                        pin_line = "diagonal"
                    
                    pins.append(PinPattern(
                        pinning_piece=PIECE_NAMES[piece.piece_type],
                        pinning_square=chess.square_name(sq),
                        pinned_piece=PIECE_NAMES[pinned_piece.piece_type],
                        pinned_square=chess.square_name(pinned_sq),
                        protected_piece="king",
                        protected_square=chess.square_name(king_sq),
                        pin_line=pin_line,
                        is_absolute=True  # All pins to king are absolute
                    ))
        
        return pins
    
    # =========================================
    # HANGING PIECE DETECTION
    # =========================================
    
    def find_hanging_pieces(self, board: chess.Board, color: bool) -> List[HangingPiecePattern]:
        """Find all undefended or inadequately defended pieces"""
        hanging = []
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None or piece.color != color:
                continue
            
            # Skip pawns for now (less critical)
            if piece.piece_type == chess.PAWN:
                continue
            
            attackers = self._get_attackers(board, sq, not color)
            defenders = self._get_attackers(board, sq, color)
            
            # Count attacker/defender values
            attacker_value = sum(PIECE_VALUES.get(board.piece_at(a).piece_type, 0) for a in attackers)
            sum(PIECE_VALUES.get(board.piece_at(d).piece_type, 0) for d in defenders)
            
            is_hanging = len(attackers) > 0 and len(defenders) == 0
            can_be_captured_free = is_hanging or (len(attackers) > len(defenders))
            
            if is_hanging or (len(attackers) > 0 and attacker_value < PIECE_VALUES.get(piece.piece_type, 0)):
                hanging.append(HangingPiecePattern(
                    piece=PIECE_NAMES[piece.piece_type],
                    square=chess.square_name(sq),
                    value=PIECE_VALUES.get(piece.piece_type, 0),
                    attackers=[{"piece": PIECE_NAMES[board.piece_at(a).piece_type], "square": chess.square_name(a)} for a in attackers],
                    defenders=[{"piece": PIECE_NAMES[board.piece_at(d).piece_type], "square": chess.square_name(d)} for d in defenders],
                    is_protected=len(defenders) > 0,
                    can_be_captured_for_free=can_be_captured_free
                ))
        
        return hanging
    
    def _get_attackers(self, board: chess.Board, square: int, color: bool) -> List[int]:
        """Get all pieces of a color attacking a square"""
        attackers = []
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == color:
                if square in board.attacks(sq):
                    attackers.append(sq)
        return attackers
    
    # =========================================
    # COMPREHENSIVE POSITION ANALYSIS
    # =========================================
    
    def analyze_position_for_feedback(
        self, 
        fen: str, 
        user_insight: str,
        move_played: str = None,
        best_move: str = None
    ) -> Dict:
        """
        Comprehensive position analysis based on user's feedback.
        
        This is the main entry point. Given a position and user's insight,
        it extracts all relevant tactical patterns.
        """
        try:
            board = chess.Board(fen)
        except:
            return {"error": "Invalid FEN"}
        
        analysis = {
            "fen": fen,
            "user_insight": user_insight,
            "detected_patterns": [],
            "position_features": {}
        }
        
        # Determine which color to analyze based on whose turn it is
        color_to_analyze = board.turn
        enemy_color = not color_to_analyze
        
        # 1. Check for forks
        enemy_forks = self.find_forks(board, enemy_color)
        if enemy_forks:
            for fork in enemy_forks:
                analysis["detected_patterns"].append({
                    "type": "fork",
                    "details": fork.to_dict()
                })
        
        # 2. Analyze king safety
        king_safety = self.analyze_king_safety(board, color_to_analyze)
        if king_safety:
            analysis["position_features"]["king_safety"] = king_safety.to_dict()
            
            if king_safety.num_escape_squares == 0 and king_safety.is_on_back_rank:
                analysis["detected_patterns"].append({
                    "type": "king_trapped",
                    "details": {
                        "king_square": king_safety.king_square,
                        "escape_squares": 0,
                        "blocked_by": king_safety.blocked_by_own_pieces,
                        "luft_needed": king_safety.luft_needed,
                        "suggested_move": king_safety.suggested_luft_move
                    }
                })
        
        # 3. Check for pins
        pins = self.find_pins(board, color_to_analyze)
        if pins:
            for pin in pins:
                analysis["detected_patterns"].append({
                    "type": "pin",
                    "details": pin.to_dict()
                })
        
        # 4. Check for hanging pieces
        hanging = self.find_hanging_pieces(board, color_to_analyze)
        if hanging:
            for h in hanging:
                analysis["detected_patterns"].append({
                    "type": "hanging_piece",
                    "details": h.to_dict()
                })
        
        # 5. Use user insight to prioritize patterns
        insight_lower = user_insight.lower()
        
        if "fork" in insight_lower:
            # Prioritize fork patterns
            analysis["primary_pattern"] = "fork"
        elif any(kw in insight_lower for kw in ["breathing", "luft", "escape", "trapped", "back rank"]):
            analysis["primary_pattern"] = "king_safety"
        elif "pin" in insight_lower:
            analysis["primary_pattern"] = "pin"
        elif "hang" in insight_lower or "undefended" in insight_lower:
            analysis["primary_pattern"] = "hanging_piece"
        
        return analysis


class SmartPatternExtractor:
    """
    Extracts INTELLIGENT pattern rules from user feedback + position analysis.
    
    This combines:
    1. Deep position analysis (actual chess understanding)
    2. User's insight (what they noticed)
    3. Creates queryable rules that match similar patterns
    """
    
    def __init__(self):
        self.analyzer = DeepPositionAnalyzer()
    
    async def extract_pattern(self, feedback: Dict) -> Optional[Dict]:
        """
        Extract an intelligent pattern from feedback.
        
        Combines position analysis with user insight.
        """
        fen = feedback.get("position_fen", "")
        user_insight = feedback.get("user_explanation", "")
        move_played = feedback.get("move_san", feedback.get("move_played", ""))
        best_move = feedback.get("best_move", "")
        
        if not fen or not user_insight:
            return None
        
        # Step 1: Deep position analysis
        analysis = self.analyzer.analyze_position_for_feedback(
            fen, user_insight, move_played, best_move
        )
        
        if "error" in analysis:
            return None
        
        # Step 2: Create pattern rule based on analysis + insight
        pattern_rule = self._create_pattern_rule(analysis, feedback)
        
        return pattern_rule
    
    def _create_pattern_rule(self, analysis: Dict, feedback: Dict) -> Dict:
        """Create a queryable pattern rule from analysis"""
        patterns = analysis.get("detected_patterns", [])
        primary_pattern = analysis.get("primary_pattern")
        king_safety = analysis.get("position_features", {}).get("king_safety", {})
        
        rule = {
            "rule_id": f"smart_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "source_feedback_id": feedback.get("feedback_id", ""),
            "user_insight": feedback.get("user_explanation", ""),
            "position_fen": feedback.get("position_fen", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "match_count": 0
        }
        
        # Set pattern type and matching criteria based on what was detected
        if primary_pattern == "fork" or any(p["type"] == "fork" for p in patterns):
            fork_details = next((p["details"] for p in patterns if p["type"] == "fork"), {})
            rule.update({
                "pattern_type": "fork",
                "match_criteria": {
                    "attacker_piece": fork_details.get("attacker_piece"),
                    "min_targets": 2,
                    "min_target_value": fork_details.get("total_target_value", 10),
                    "target_pieces": [t["piece"] for t in fork_details.get("targets", [])]
                },
                "explanation_template": self._generate_fork_explanation(fork_details),
                "geometry": fork_details.get("fork_geometry", "")
            })
        
        elif primary_pattern == "king_safety" or king_safety.get("num_escape_squares", 99) == 0:
            rule.update({
                "pattern_type": "king_trapped",
                "match_criteria": {
                    "king_on_back_rank": king_safety.get("is_on_back_rank", False),
                    "max_escape_squares": 0,
                    "blocked_by_own_pieces": len(king_safety.get("blocked_by_own_pieces", [])) > 0
                },
                "explanation_template": self._generate_king_safety_explanation(king_safety),
                "blocked_squares": [p["square"] for p in king_safety.get("blocked_by_own_pieces", [])]
            })
        
        elif primary_pattern == "pin" or any(p["type"] == "pin" for p in patterns):
            pin_details = next((p["details"] for p in patterns if p["type"] == "pin"), {})
            rule.update({
                "pattern_type": "pin",
                "match_criteria": {
                    "pinning_piece": pin_details.get("pinning_piece"),
                    "pinned_piece": pin_details.get("pinned_piece"),
                    "pin_line": pin_details.get("pin_line")
                },
                "explanation_template": self._generate_pin_explanation(pin_details)
            })
        
        elif any(p["type"] == "hanging_piece" for p in patterns):
            hanging_details = next((p["details"] for p in patterns if p["type"] == "hanging_piece"), {})
            rule.update({
                "pattern_type": "hanging_piece",
                "match_criteria": {
                    "piece": hanging_details.get("piece"),
                    "min_value": hanging_details.get("value", 3),
                    "undefended": not hanging_details.get("is_protected", False)
                },
                "explanation_template": self._generate_hanging_explanation(hanging_details)
            })
        
        else:
            # Generic pattern - use user insight
            rule.update({
                "pattern_type": "custom",
                "match_criteria": {},
                "explanation_template": feedback.get("user_explanation", "")
            })
        
        return rule
    
    def _generate_fork_explanation(self, fork_details: Dict) -> str:
        """Generate explanation for fork pattern"""
        attacker = fork_details.get("attacker_piece", "piece")
        targets = fork_details.get("targets", [])
        target_names = [t["piece"] for t in targets[:2]]
        
        return (
            f"You walked into a {attacker} fork! "
            f"The {attacker} on {fork_details.get('attacker_square', '?')} "
            f"attacks your {' and '.join(target_names)} simultaneously. "
            f"You can only save one."
        )
    
    def _generate_king_safety_explanation(self, king_safety: Dict) -> str:
        """Generate explanation for king safety pattern"""
        blocked_by = king_safety.get("blocked_by_own_pieces", [])
        blockers = [f"{p['piece']} on {p['square']}" for p in blocked_by[:2]]
        
        explanation = "Your king is trapped on the back rank with no escape squares. "
        if blockers:
            explanation += f"Your own pieces ({', '.join(blockers)}) are blocking the escape. "
        
        if king_safety.get("suggested_luft_move"):
            explanation += f"Consider playing {king_safety['suggested_luft_move']} to create breathing room (luft)."
        
        return explanation
    
    def _generate_pin_explanation(self, pin_details: Dict) -> str:
        """Generate explanation for pin pattern"""
        return (
            f"Your {pin_details.get('pinned_piece', 'piece')} on {pin_details.get('pinned_square', '?')} "
            f"is pinned to your {pin_details.get('protected_piece', 'king')} by the enemy "
            f"{pin_details.get('pinning_piece', 'piece')} on {pin_details.get('pinning_square', '?')}. "
            f"Moving it would expose your {pin_details.get('protected_piece', 'king')}."
        )
    
    def _generate_hanging_explanation(self, hanging_details: Dict) -> str:
        """Generate explanation for hanging piece"""
        attackers = hanging_details.get("attackers", [])
        attacker_str = attackers[0]["piece"] if attackers else "enemy piece"
        
        return (
            f"Your {hanging_details.get('piece', 'piece')} on {hanging_details.get('square', '?')} "
            f"is undefended and can be captured for free by the {attacker_str}."
        )
