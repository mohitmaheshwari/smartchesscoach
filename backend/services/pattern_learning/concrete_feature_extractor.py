"""
Concrete Feature Extractor for Auto-Correction System

This module extracts QUERYABLE features from user feedback.
Unlike the text-based rule generation, this creates features that
can be matched against future positions programmatically.

Example:
User says: "The knight forks my queen and rook"

Extracts:
{
    "pattern_type": "fork",
    "attacker_piece": "knight",
    "target_pieces": ["queen", "rook"],
    "target_squares": ["d5", "f7"],  # From position analysis
    "min_targets": 2,
    "attacker_value": 3,  # Knight = 3
    "min_target_value": 5  # At least a rook
}

This can then be matched against any new position:
"Is there a knight attacking 2+ pieces worth 5+ points?"
"""

import chess
import re
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Piece values for matching
PIECE_VALUES = {
    "pawn": 1, "knight": 3, "bishop": 3, 
    "rook": 5, "queen": 9, "king": 100
}

PIECE_NAMES = ["pawn", "knight", "bishop", "rook", "queen", "king"]


@dataclass
class ConcretePatternRule:
    """A pattern rule with queryable features that can match future positions"""
    
    rule_id: str
    pattern_type: str  # fork, pin, skewer, back_rank, hanging, discovered, etc.
    
    # Attacker features (the piece making the tactic)
    attacker_piece: Optional[str] = None  # "knight", "bishop", etc.
    attacker_color: Optional[str] = None  # "white", "black", or None for relative
    
    # Target features (pieces being attacked)
    target_pieces: List[str] = field(default_factory=list)  # ["queen", "rook"]
    min_targets: int = 1  # Minimum number of pieces attacked
    min_target_value: int = 0  # Minimum combined value of targets
    
    # King safety features
    king_on_back_rank: Optional[bool] = None
    king_escape_squares: Optional[int] = None  # Max escape squares for match
    back_rank_threat: Optional[bool] = None
    
    # Geometric features
    same_diagonal: Optional[bool] = None
    same_file: Optional[bool] = None
    same_rank: Optional[bool] = None
    
    # Material features
    material_loss: Optional[int] = None  # Minimum material loss in centipawns
    
    # The explanation to show when this pattern matches
    explanation_template: str = ""
    
    # User's original insight (for reference)
    user_insight: str = ""
    
    # Metadata
    confidence: float = 0.8
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_feedback_id: str = ""
    match_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConcretePatternRule":
        # Filter out _id and unknown fields
        valid_fields = {k: v for k, v in data.items() 
                       if k in cls.__dataclass_fields__ and k != '_id'}
        return cls(**valid_fields)


class ConcreteFeatureExtractor:
    """
    Extracts concrete, queryable features from user feedback.
    
    This is the KEY piece that makes auto-correction actually work.
    It converts user's natural language into queryable conditions.
    """
    
    def __init__(self):
        self.api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
        self._chat = None
    
    def _get_chat(self):
        """Lazy-load the chat client"""
        if self._chat is None:
            try:
                from llm_helper import LlmChat
                import uuid
                self._chat = LlmChat(
                    api_key=self.api_key,
                    session_id=f"feature_extractor_{uuid.uuid4().hex[:8]}",
                    system_message=self._get_system_prompt()
                ).with_model("openai", "gpt-4o-mini")
            except ImportError:
                logger.error("emergentintegrations not installed")
                raise
        return self._chat
    
    def _get_system_prompt(self) -> str:
        return """You are a chess pattern analyzer. Your job is to extract CONCRETE, QUERYABLE features from user feedback about chess mistakes.

CRITICAL: Output must be machine-readable features, NOT prose descriptions.

For each pattern, extract:
1. pattern_type: fork, pin, skewer, back_rank, hanging, discovered, trapped, overloaded
2. attacker_piece: The piece making the attack (pawn, knight, bishop, rook, queen)
3. target_pieces: List of pieces being attacked ["queen", "rook"]
4. min_targets: Minimum pieces attacked (2 for fork)
5. king_safety features if relevant

Always output valid JSON with these exact field names."""
    
    async def extract_features(self, feedback: Dict) -> Optional[ConcretePatternRule]:
        """
        Extract concrete features from user feedback.
        
        Args:
            feedback: Dict with user_explanation, position_fen, etc.
            
        Returns:
            ConcretePatternRule with queryable features
        """
        user_insight = feedback.get("user_explanation", "")
        position_fen = feedback.get("position_fen", "")
        correct_pattern = feedback.get("correct_classification", "")
        
        if not user_insight:
            return None
        
        # First, try rule-based extraction (fast, no API call)
        rule = self._extract_from_keywords(user_insight, position_fen, correct_pattern)
        if rule and rule.pattern_type != "unknown":
            rule.source_feedback_id = feedback.get("feedback_id", "")
            rule.user_insight = user_insight
            return rule
        
        # Fall back to LLM extraction
        if self.api_key:
            return await self._extract_with_llm(feedback)
        
        return None
    
    def _extract_from_keywords(
        self, 
        user_insight: str, 
        position_fen: str,
        correct_pattern: str
    ) -> Optional[ConcretePatternRule]:
        """
        Extract features using keyword matching (no API call needed).
        Handles common patterns quickly.
        """
        insight_lower = user_insight.lower()
        pattern_lower = correct_pattern.lower()
        
        rule = ConcretePatternRule(
            rule_id=f"rule_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            pattern_type="unknown"
        )
        
        # ===== FORK DETECTION =====
        if "fork" in insight_lower or "fork" in pattern_lower:
            rule.pattern_type = "fork"
            rule.min_targets = 2
            
            # Extract attacker piece
            for piece in PIECE_NAMES:
                if piece in insight_lower:
                    rule.attacker_piece = piece
                    break
            
            # Default to knight/pawn forks (most common)
            if not rule.attacker_piece:
                if "pawn" in insight_lower or "pawn" in pattern_lower:
                    rule.attacker_piece = "pawn"
                else:
                    rule.attacker_piece = "knight"
            
            # Extract targets
            targets = []
            for piece in ["queen", "rook", "king", "bishop", "knight"]:
                if piece in insight_lower and piece != rule.attacker_piece:
                    targets.append(piece)
            rule.target_pieces = targets if targets else ["queen", "rook"]
            
            # Calculate minimum target value
            rule.min_target_value = sum(PIECE_VALUES.get(p, 0) for p in rule.target_pieces[:2])
            
            rule.explanation_template = f"You walked into a {rule.attacker_piece} fork. The {rule.attacker_piece} attacks your {{targets}} simultaneously - you can only save one."
            return rule
        
        # ===== PIN DETECTION =====
        if "pin" in insight_lower or "pin" in pattern_lower:
            rule.pattern_type = "pin"
            rule.same_diagonal = True  # Pins are usually diagonal or file-based
            
            # Extract pinning piece
            for piece in ["bishop", "rook", "queen"]:
                if piece in insight_lower:
                    rule.attacker_piece = piece
                    break
            
            if not rule.attacker_piece:
                rule.attacker_piece = "bishop"  # Most common
            
            rule.explanation_template = "You're pinned! Your piece can't move because it's protecting something more valuable behind it."
            return rule
        
        # ===== SKEWER DETECTION =====
        if "skewer" in insight_lower or "skewer" in pattern_lower:
            rule.pattern_type = "skewer"
            rule.same_diagonal = True
            
            for piece in ["bishop", "rook", "queen"]:
                if piece in insight_lower:
                    rule.attacker_piece = piece
                    break
            
            rule.explanation_template = "You're skewered! When your valuable piece moves, the piece behind it gets captured."
            return rule
        
        # ===== BACK RANK DETECTION =====
        if "back rank" in insight_lower or "back_rank" in pattern_lower or "backrank" in insight_lower:
            rule.pattern_type = "back_rank"
            rule.king_on_back_rank = True
            rule.king_escape_squares = 0
            rule.back_rank_threat = True
            rule.attacker_piece = "rook"  # Usually rook or queen
            
            rule.explanation_template = "Back rank mate threat! Your king is trapped on the back rank with no escape squares."
            return rule
        
        # ===== KING SAFETY / LUFT =====
        if any(kw in insight_lower for kw in ["breathing", "luft", "escape", "king.*trap", "king.*stuck"]):
            rule.pattern_type = "king_safety"
            rule.king_on_back_rank = True
            rule.king_escape_squares = 1  # 0 or 1 escape squares
            
            rule.explanation_template = "Your king needs breathing room (luft). Create an escape square to prevent back rank threats."
            return rule
        
        # ===== HANGING PIECE =====
        if "hanging" in insight_lower or "undefended" in insight_lower or "free" in insight_lower:
            rule.pattern_type = "hanging"
            
            for piece in PIECE_NAMES:
                if piece in insight_lower:
                    rule.target_pieces = [piece]
                    break
            
            rule.explanation_template = "You left a piece hanging! It's undefended and can be captured for free."
            return rule
        
        # ===== DISCOVERED ATTACK =====
        if "discover" in insight_lower:
            rule.pattern_type = "discovered"
            rule.explanation_template = "Discovered attack! When one piece moves, it reveals an attack from the piece behind it."
            return rule
        
        # ===== TRAPPED PIECE =====
        if "trap" in insight_lower:
            rule.pattern_type = "trapped"
            
            for piece in PIECE_NAMES:
                if piece in insight_lower:
                    rule.target_pieces = [piece]
                    break
            
            rule.explanation_template = "Your piece is trapped! It has no safe squares to escape to."
            return rule
        
        return rule
    
    async def _extract_with_llm(self, feedback: Dict) -> Optional[ConcretePatternRule]:
        """Use LLM to extract features when keyword matching isn't enough"""
        try:
            from llm_helper import UserMessage
            import json
            
            prompt = f"""Extract concrete, queryable features from this chess feedback.

USER'S EXPLANATION: "{feedback.get('user_explanation', '')}"
PATTERN THEY SELECTED: {feedback.get('correct_classification', '')}
POSITION (FEN): {feedback.get('position_fen', '')}
MOVE PLAYED: {feedback.get('move_san', feedback.get('move_played', ''))}

Output ONLY valid JSON with these fields:
{{
    "pattern_type": "fork|pin|skewer|back_rank|hanging|discovered|trapped|king_safety|other",
    "attacker_piece": "pawn|knight|bishop|rook|queen|null",
    "target_pieces": ["queen", "rook"],
    "min_targets": 2,
    "min_target_value": 14,
    "king_on_back_rank": true|false|null,
    "king_escape_squares": 0|1|2|null,
    "explanation_template": "Your piece walked into a fork..."
}}"""

            chat = self._get_chat()
            response = await chat.send_message(UserMessage(text=prompt))
            
            # Parse JSON response
            data = self._parse_json(response)
            if data:
                rule = ConcretePatternRule(
                    rule_id=f"rule_llm_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    pattern_type=data.get("pattern_type", "other"),
                    attacker_piece=data.get("attacker_piece"),
                    target_pieces=data.get("target_pieces", []),
                    min_targets=data.get("min_targets", 1),
                    min_target_value=data.get("min_target_value", 0),
                    king_on_back_rank=data.get("king_on_back_rank"),
                    king_escape_squares=data.get("king_escape_squares"),
                    explanation_template=data.get("explanation_template", ""),
                    user_insight=feedback.get("user_explanation", ""),
                    source_feedback_id=feedback.get("feedback_id", "")
                )
                return rule
                
        except Exception as e:
            logger.error(f"LLM feature extraction failed: {e}")
        
        return None
    
    def _parse_json(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        import json
        
        try:
            return json.loads(response)
        except:
            pass
        
        # Try extracting from markdown
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    return json.loads(response[start:end].strip())
                except:
                    pass
        
        # Try finding JSON object
        match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return None


class ConcretePatternMatcher:
    """
    Matches positions against concrete pattern rules.
    
    This is what makes auto-correction work for FUTURE positions.
    """
    
    def __init__(self):
        pass
    
    def match(self, rule: ConcretePatternRule, position_fen: str, move_played: str = None) -> Tuple[bool, float]:
        """
        Check if a position matches a pattern rule.
        
        Returns:
            (matches: bool, confidence: float)
        """
        try:
            board = chess.Board(position_fen)
        except:
            return False, 0.0
        
        confidence = 0.0
        matches_required = 0
        matches_found = 0
        
        # Check pattern-specific conditions
        if rule.pattern_type == "fork":
            return self._match_fork(rule, board)
        
        elif rule.pattern_type == "pin":
            return self._match_pin(rule, board)
        
        elif rule.pattern_type == "back_rank" or rule.pattern_type == "king_safety":
            return self._match_king_safety(rule, board)
        
        elif rule.pattern_type == "hanging":
            return self._match_hanging(rule, board)
        
        # Generic feature matching for other patterns
        if rule.king_on_back_rank is not None:
            matches_required += 1
            king_sq = board.king(board.turn)
            if king_sq:
                is_back_rank = chess.square_rank(king_sq) in [0, 7]
                if is_back_rank == rule.king_on_back_rank:
                    matches_found += 1
        
        if rule.king_escape_squares is not None:
            matches_required += 1
            escapes = self._count_king_escapes(board)
            if escapes <= rule.king_escape_squares:
                matches_found += 1
        
        if matches_required > 0:
            confidence = matches_found / matches_required
            return confidence >= 0.7, confidence
        
        return False, 0.0
    
    def _match_fork(self, rule: ConcretePatternRule, board: chess.Board) -> Tuple[bool, float]:
        """Check if there's a fork pattern"""
        # Look for any piece attacking 2+ valuable pieces
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece:
                continue
            
            # Check if this piece type matches the rule's attacker
            if rule.attacker_piece:
                piece_name = chess.piece_name(piece.piece_type)
                if piece_name != rule.attacker_piece:
                    continue
            
            # Count valuable pieces this attacks
            attacks = board.attacks(square)
            valuable_targets = []
            for target_sq in attacks:
                target = board.piece_at(target_sq)
                if target and target.color != piece.color:
                    target_name = chess.piece_name(target.piece_type)
                    target_value = PIECE_VALUES.get(target_name, 0)
                    if target_value >= 3:  # Knight value or higher
                        valuable_targets.append(target_name)
            
            # Check if it matches the fork criteria
            if len(valuable_targets) >= (rule.min_targets or 2):
                total_value = sum(PIECE_VALUES.get(t, 0) for t in valuable_targets)
                if total_value >= (rule.min_target_value or 0):
                    return True, 0.9
        
        return False, 0.0
    
    def _match_pin(self, rule: ConcretePatternRule, board: chess.Board) -> Tuple[bool, float]:
        """Check if there's a pin"""
        # Simplified pin detection
        color = board.turn
        king_sq = board.king(color)
        if not king_sq:
            return False, 0.0
        
        # Check for pieces on same file/rank/diagonal as king
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece or piece.color == color:
                continue
            
            # Check if it's a sliding piece (can pin)
            if piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                continue
            
            # Check if there's a friendly piece between this and the king
            # that would be pinned
            ray = chess.SquareSet.ray(square, king_sq)
            if ray:
                pieces_in_ray = [s for s in ray if board.piece_at(s) and s != square and s != king_sq]
                if len(pieces_in_ray) == 1:
                    pinned_sq = pieces_in_ray[0]
                    pinned = board.piece_at(pinned_sq)
                    if pinned and pinned.color == color:
                        return True, 0.85
        
        return False, 0.0
    
    def _match_king_safety(self, rule: ConcretePatternRule, board: chess.Board) -> Tuple[bool, float]:
        """Check king safety patterns"""
        color = board.turn
        king_sq = board.king(color)
        if not king_sq:
            return False, 0.0
        
        # Check back rank
        king_rank = chess.square_rank(king_sq)
        back_rank = 0 if color == chess.WHITE else 7
        
        if rule.king_on_back_rank and king_rank != back_rank:
            return False, 0.0
        
        # Count escape squares
        escapes = self._count_king_escapes(board)
        if rule.king_escape_squares is not None and escapes > rule.king_escape_squares:
            return False, 0.0
        
        # If all conditions met
        if king_rank == back_rank and escapes <= (rule.king_escape_squares or 1):
            return True, 0.9
        
        return False, 0.0
    
    def _match_hanging(self, rule: ConcretePatternRule, board: chess.Board) -> Tuple[bool, float]:
        """Check for hanging pieces"""
        color = board.turn
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece or piece.color != color:
                continue
            
            # Check if attacked and undefended
            if board.is_attacked_by(not color, square):
                if not board.is_attacked_by(color, square):
                    piece_name = chess.piece_name(piece.piece_type)
                    if not rule.target_pieces or piece_name in rule.target_pieces:
                        return True, 0.9
        
        return False, 0.0
    
    def _count_king_escapes(self, board: chess.Board) -> int:
        """Count safe squares the king can move to"""
        color = board.turn
        king_sq = board.king(color)
        if not king_sq:
            return 0
        
        escapes = 0
        for sq in board.attacks(king_sq):
            target = board.piece_at(sq)
            # Empty or enemy piece
            if target is None or target.color != color:
                # Check if safe
                if not board.is_attacked_by(not color, sq):
                    escapes += 1
        
        return escapes


class ConcretePatternStore:
    """Store and retrieve concrete pattern rules from MongoDB"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.concrete_patterns
        self.extractor = ConcreteFeatureExtractor()
        self.matcher = ConcretePatternMatcher()
    
    async def add_rule(self, rule: ConcretePatternRule) -> str:
        """Add a new concrete pattern rule"""
        doc = rule.to_dict()
        await self.collection.update_one(
            {"rule_id": rule.rule_id},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Stored concrete pattern rule: {rule.pattern_type} - {rule.rule_id}")
        return rule.rule_id
    
    async def find_matching_rules(self, position_fen: str) -> List[Tuple[ConcretePatternRule, float]]:
        """Find all rules that match a position"""
        matching = []
        
        async for doc in self.collection.find():
            try:
                rule = ConcretePatternRule.from_dict(doc)
                matches, confidence = self.matcher.match(rule, position_fen)
                if matches:
                    matching.append((rule, confidence))
            except Exception as e:
                logger.error(f"Error matching rule: {e}")
        
        # Sort by confidence
        matching.sort(key=lambda x: x[1], reverse=True)
        return matching
    
    async def extract_and_store_from_feedback(self, feedback: Dict) -> Optional[ConcretePatternRule]:
        """Extract concrete features from feedback and store as rule"""
        rule = await self.extractor.extract_features(feedback)
        if rule and rule.pattern_type != "unknown":
            await self.add_rule(rule)
            return rule
        return None
    
    async def increment_match_count(self, rule_id: str):
        """Increment the match count for a rule"""
        await self.collection.update_one(
            {"rule_id": rule_id},
            {"$inc": {"match_count": 1}}
        )
