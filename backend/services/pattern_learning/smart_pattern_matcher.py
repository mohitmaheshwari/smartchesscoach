"""
Smart Pattern Matcher - The Missing Piece

This module COMPLETES the auto-correction loop by:
1. Querying the smart_patterns database
2. Matching new positions against learned rules
3. Returning the learned explanation when a match is found

This is what makes the system ACTUALLY learn from user feedback.

Flow:
  New position → Query DB → Match against stored patterns → Return learned explanation
"""

import chess
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Piece values for matching
PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100
}

PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
}


@dataclass
class MatchResult:
    """Result of matching a position against learned patterns"""
    matched: bool
    pattern_type: str
    rule_id: str
    confidence: float
    explanation: str
    match_details: Dict
    

class SmartPatternMatcher:
    """
    Matches new positions against learned patterns from the database.
    
    This is the CRITICAL piece that closes the auto-correction loop.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db
        self._cached_patterns = None
        self._cache_time = None
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        """Get or create database connection"""
        if self.db is None:
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
            self.db = client[os.environ.get("DB_NAME", "test_database")]
        return self.db
    
    async def _load_patterns(self, force_refresh: bool = False) -> List[Dict]:
        """Load patterns from database with caching"""
        import time
        
        # Cache for 60 seconds
        if not force_refresh and self._cached_patterns and self._cache_time:
            if time.time() - self._cache_time < 60:
                return self._cached_patterns
        
        db = await self._get_db()
        self._cached_patterns = await db.smart_patterns.find({}).to_list(length=1000)
        self._cache_time = time.time()
        
        logger.debug(f"Loaded {len(self._cached_patterns)} smart patterns from DB")
        return self._cached_patterns
    
    async def match_position(
        self, 
        fen: str, 
        move_played: str = None,
        best_move: str = None
    ) -> Optional[MatchResult]:
        """
        Match a position against all learned patterns.
        
        This is the main entry point called during position analysis.
        
        Args:
            fen: Position FEN
            move_played: Move the user played (optional)
            best_move: Best move according to engine (optional)
            
        Returns:
            MatchResult if a pattern matches, None otherwise
        """
        try:
            board = chess.Board(fen)
        except Exception as e:
            logger.error(f"Invalid FEN: {fen} - {e}")
            return None
        
        # Load learned patterns
        patterns = await self._load_patterns()
        
        if not patterns:
            return None
        
        # Try to match each pattern
        best_match = None
        best_confidence = 0.0
        
        for pattern in patterns:
            result = self._match_single_pattern(board, pattern, move_played, best_move)
            if result and result.confidence > best_confidence:
                best_match = result
                best_confidence = result.confidence
        
        if best_match:
            # Increment match count in DB
            await self._increment_match_count(best_match.rule_id)
            logger.info(f"MATCHED learned pattern: {best_match.pattern_type} (confidence: {best_confidence:.2f})")
        
        return best_match
    
    def _match_single_pattern(
        self, 
        board: chess.Board, 
        pattern: Dict,
        move_played: str = None,
        best_move: str = None
    ) -> Optional[MatchResult]:
        """Match a single pattern against the position"""
        
        pattern_type = pattern.get("pattern_type", "")
        criteria = pattern.get("match_criteria", {})
        
        if pattern_type == "fork":
            return self._match_fork_pattern(board, pattern, criteria)
        
        elif pattern_type == "king_trapped":
            return self._match_king_trapped_pattern(board, pattern, criteria)
        
        elif pattern_type == "pin":
            return self._match_pin_pattern(board, pattern, criteria)
        
        elif pattern_type == "hanging_piece":
            return self._match_hanging_pattern(board, pattern, criteria)
        
        return None
    
    def _match_fork_pattern(
        self, 
        board: chess.Board, 
        pattern: Dict,
        criteria: Dict
    ) -> Optional[MatchResult]:
        """
        Match fork pattern by finding actual forks in the position.
        
        Checks:
        - Is there a piece attacking 2+ valuable pieces?
        - Does the attacker piece type match?
        - Are the target pieces similar?
        """
        required_attacker = criteria.get("attacker_piece")
        min_targets = criteria.get("min_targets", 2)
        target_pieces = criteria.get("target_pieces", [])
        
        # Check both colors for forks
        for color in [chess.WHITE, chess.BLACK]:
            forks = self._find_forks_in_position(board, color)
            
            for fork in forks:
                # Check attacker piece type
                if required_attacker and fork["attacker_piece"] != required_attacker:
                    continue
                
                # Check number of targets
                if len(fork["targets"]) < min_targets:
                    continue
                
                # Check target pieces match (if specified)
                if target_pieces:
                    fork_targets = set(t["piece"] for t in fork["targets"])
                    required_targets = set(target_pieces)
                    # At least some overlap
                    if not fork_targets.intersection(required_targets):
                        continue
                
                # MATCH FOUND!
                explanation = pattern.get("explanation_template", "")
                # Try to make explanation specific to this position
                explanation = self._customize_explanation(explanation, fork)
                
                return MatchResult(
                    matched=True,
                    pattern_type="fork",
                    rule_id=pattern.get("rule_id", ""),
                    confidence=0.9,
                    explanation=explanation,
                    match_details=fork
                )
        
        return None
    
    def _find_forks_in_position(self, board: chess.Board, color: bool) -> List[Dict]:
        """Find all forks for a color"""
        forks = []
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue
            
            # Get attacks
            attacks = board.attacks(square)
            
            # Find valuable targets
            targets = []
            for target_sq in attacks:
                target = board.piece_at(target_sq)
                if target and target.color != color:
                    value = PIECE_VALUES.get(target.piece_type, 0)
                    if value >= 3:
                        targets.append({
                            "piece": PIECE_NAMES[target.piece_type],
                            "square": chess.square_name(target_sq),
                            "value": value
                        })
            
            if len(targets) >= 2:
                forks.append({
                    "attacker_piece": PIECE_NAMES[piece.piece_type],
                    "attacker_square": chess.square_name(square),
                    "attacker_color": "white" if color else "black",
                    "targets": targets,
                    "total_value": sum(t["value"] for t in targets)
                })
        
        return forks
    
    def _match_king_trapped_pattern(
        self, 
        board: chess.Board, 
        pattern: Dict,
        criteria: Dict
    ) -> Optional[MatchResult]:
        """
        Match king trapped pattern.
        
        Checks:
        - Is king on back rank?
        - How many escape squares?
        - Is it blocked by own pieces?
        """
        require_back_rank = criteria.get("king_on_back_rank", False)
        max_escapes = criteria.get("max_escape_squares", 0)
        require_blocked_by_own = criteria.get("blocked_by_own_pieces", False)
        
        # Check the side to move
        color = board.turn
        king_sq = board.king(color)
        
        if king_sq is None:
            return None
        
        # Check back rank
        king_rank = chess.square_rank(king_sq)
        back_rank = 0 if color == chess.WHITE else 7
        is_back_rank = king_rank == back_rank
        
        if require_back_rank and not is_back_rank:
            return None
        
        # Count escape squares
        escape_squares = []
        blocked_by_own = []
        
        for sq in board.attacks(king_sq):
            piece = board.piece_at(sq)
            
            if piece is None:
                # Empty - check if attacked by enemy
                if not board.is_attacked_by(not color, sq):
                    escape_squares.append(chess.square_name(sq))
            elif piece.color == color:
                blocked_by_own.append({
                    "piece": PIECE_NAMES[piece.piece_type],
                    "square": chess.square_name(sq)
                })
        
        # Check escape squares
        if len(escape_squares) > max_escapes:
            return None
        
        # Check blocked by own pieces
        if require_blocked_by_own and len(blocked_by_own) == 0:
            return None
        
        # MATCH FOUND!
        explanation = pattern.get("explanation_template", "")
        
        # Customize with actual blocked squares
        if blocked_by_own:
            blockers = ", ".join(f"{p['piece']} on {p['square']}" for p in blocked_by_own[:2])
            if "{blocked_by}" in explanation:
                explanation = explanation.replace("{blocked_by}", blockers)
        
        return MatchResult(
            matched=True,
            pattern_type="king_trapped",
            rule_id=pattern.get("rule_id", ""),
            confidence=0.85,
            explanation=explanation,
            match_details={
                "king_square": chess.square_name(king_sq),
                "escape_squares": escape_squares,
                "blocked_by_own": blocked_by_own
            }
        )
    
    def _match_pin_pattern(
        self, 
        board: chess.Board, 
        pattern: Dict,
        criteria: Dict
    ) -> Optional[MatchResult]:
        """Match pin pattern"""
        color = board.turn
        king_sq = board.king(color)
        
        if king_sq is None:
            return None
        
        # Find pins
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None or piece.color == color:
                continue
            
            if piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                continue
            
            # Check ray to king
            ray = chess.SquareSet.between(sq, king_sq)
            if not ray:
                continue
            
            pieces_in_ray = []
            for ray_sq in ray:
                ray_piece = board.piece_at(ray_sq)
                if ray_piece:
                    pieces_in_ray.append((ray_sq, ray_piece))
            
            if len(pieces_in_ray) == 1:
                pinned_sq, pinned_piece = pieces_in_ray[0]
                if pinned_piece.color == color:
                    # PIN FOUND!
                    explanation = pattern.get("explanation_template", "")
                    
                    return MatchResult(
                        matched=True,
                        pattern_type="pin",
                        rule_id=pattern.get("rule_id", ""),
                        confidence=0.85,
                        explanation=explanation,
                        match_details={
                            "pinning_piece": PIECE_NAMES[piece.piece_type],
                            "pinning_square": chess.square_name(sq),
                            "pinned_piece": PIECE_NAMES[pinned_piece.piece_type],
                            "pinned_square": chess.square_name(pinned_sq)
                        }
                    )
        
        return None
    
    def _match_hanging_pattern(
        self, 
        board: chess.Board, 
        pattern: Dict,
        criteria: Dict
    ) -> Optional[MatchResult]:
        """Match hanging piece pattern"""
        color = board.turn
        
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None or piece.color != color:
                continue
            
            if piece.piece_type == chess.PAWN:
                continue
            
            # Check if attacked
            if not board.is_attacked_by(not color, sq):
                continue
            
            # Check if defended
            if board.is_attacked_by(color, sq):
                continue
            
            # HANGING PIECE FOUND!
            explanation = pattern.get("explanation_template", "")
            
            return MatchResult(
                matched=True,
                pattern_type="hanging_piece",
                rule_id=pattern.get("rule_id", ""),
                confidence=0.9,
                explanation=explanation,
                match_details={
                    "piece": PIECE_NAMES[piece.piece_type],
                    "square": chess.square_name(sq)
                }
            )
        
        return None
    
    def _customize_explanation(self, template: str, fork_details: Dict) -> str:
        """Customize explanation template with actual position details"""
        try:
            attacker = fork_details.get("attacker_piece", "piece")
            attacker_sq = fork_details.get("attacker_square", "")
            targets = fork_details.get("targets", [])
            target_names = " and ".join(t["piece"] for t in targets[:2])
            
            # Replace placeholders
            explanation = template
            if "{attacker}" in explanation:
                explanation = explanation.replace("{attacker}", attacker)
            if "{attacker_square}" in explanation:
                explanation = explanation.replace("{attacker_square}", attacker_sq)
            if "{targets}" in explanation:
                explanation = explanation.replace("{targets}", target_names)
            
            # If no placeholders, append details
            if explanation == template and attacker_sq:
                explanation = f"The {attacker} on {attacker_sq} forks your {target_names}. {template}"
            
            return explanation
        except:
            return template
    
    async def _increment_match_count(self, rule_id: str):
        """Increment match count for a rule"""
        try:
            db = await self._get_db()
            await db.smart_patterns.update_one(
                {"rule_id": rule_id},
                {"$inc": {"match_count": 1}}
            )
        except Exception as e:
            logger.error(f"Error incrementing match count: {e}")


# Global instance for easy access
_matcher_instance = None

async def get_matcher() -> SmartPatternMatcher:
    """Get global matcher instance"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = SmartPatternMatcher()
    return _matcher_instance


async def check_learned_patterns(
    fen: str, 
    move_played: str = None,
    best_move: str = None
) -> Optional[Dict]:
    """
    Main entry point - check if position matches any learned pattern.
    
    Call this from cognitive_gap_service BEFORE doing any analysis.
    
    Args:
        fen: Position FEN
        move_played: Move played by user
        best_move: Engine's best move
        
    Returns:
        Dict with explanation if matched, None otherwise
    """
    matcher = await get_matcher()
    result = await matcher.match_position(fen, move_played, best_move)
    
    if result and result.matched:
        return {
            "matched": True,
            "pattern_type": result.pattern_type,
            "rule_id": result.rule_id,
            "confidence": result.confidence,
            "explanation": result.explanation,
            "details": result.match_details,
            "learned_from_feedback": True
        }
    
    return None
