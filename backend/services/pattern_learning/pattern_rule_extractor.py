"""
Pattern Rule Extractor

This module extracts GENERALIZABLE rules from user feedback.
Instead of just fixing one position, we learn PATTERNS that apply to similar positions.

Example:
- User feedback: "King had no breathing space, Rf8 gives luft"
- Extracted pattern: KING_SAFETY_LUFT
- Rule: When king is on back rank with no escape squares and a move creates an escape, 
        classify as KING_SAFETY, not piece traps
- Features to detect:
  - King on 1st/8th rank
  - No pawn shield or escape squares
  - Best move creates escape square
"""

import chess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import re


@dataclass
class PositionFeatures:
    """Features extracted from a chess position that define a pattern"""
    # King safety features
    king_on_back_rank: bool = False
    king_escape_squares: int = 0  # Number of safe squares king can go to
    king_has_luft: bool = False  # Does king have breathing room?
    back_rank_vulnerable: bool = False  # Is back rank mate possible?
    
    # Piece activity features
    rook_on_same_file_as_king: bool = False
    rook_on_same_rank_as_king: bool = False
    enemy_rook_on_back_rank: bool = False
    
    # Pawn structure
    pawn_shield_intact: bool = False
    
    # Tactical features
    hanging_pieces: List[str] = None  # List of undefended pieces
    pieces_under_attack: List[str] = None
    fork_possible: bool = False
    pin_exists: bool = False
    
    # Material
    material_balance: int = 0  # Positive = side to move is up
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PatternRule:
    """A rule that matches positions with similar patterns"""
    rule_id: str
    pattern_name: str  # e.g., "KING_SAFETY_LUFT", "BACK_RANK_WEAKNESS"
    
    # Conditions that must be true to match this pattern
    required_features: Dict[str, Any]
    
    # The correct classification for this pattern
    correct_classification: str
    
    # Template for generating explanations
    explanation_template: str
    
    # Metadata
    confidence: float = 0.8
    source_feedback_ids: List[str] = None
    created_at: str = None
    match_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PositionAnalyzer:
    """Analyzes chess positions to extract features"""
    
    def extract_features(self, fen: str, best_move: str = None, played_move: str = None) -> PositionFeatures:
        """Extract relevant features from a position"""
        board = chess.Board(fen)
        features = PositionFeatures(hanging_pieces=[], pieces_under_attack=[])
        
        side_to_move = board.turn
        
        # Find the king
        king_square = board.king(side_to_move)
        if king_square is None:
            return features
        
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)
        
        # King safety features
        back_rank = 0 if side_to_move == chess.WHITE else 7
        features.king_on_back_rank = (king_rank == back_rank)
        
        # Count king escape squares
        escape_squares = 0
        for sq in board.attacks(king_square):
            if board.piece_at(sq) is None or board.piece_at(sq).color != side_to_move:
                # Check if moving there would be safe
                if not board.is_attacked_by(not side_to_move, sq):
                    escape_squares += 1
        features.king_escape_squares = escape_squares
        features.king_has_luft = escape_squares > 0
        
        # Check for back rank vulnerability
        if features.king_on_back_rank and escape_squares == 0:
            # Check if enemy has rook or queen that could deliver mate
            enemy_heavy_pieces = (
                board.pieces(chess.ROOK, not side_to_move) | 
                board.pieces(chess.QUEEN, not side_to_move)
            )
            for sq in enemy_heavy_pieces:
                if chess.square_rank(sq) == back_rank:
                    features.back_rank_vulnerable = True
                    features.enemy_rook_on_back_rank = True
                    break
        
        # Check own pieces near king
        own_rooks = board.pieces(chess.ROOK, side_to_move)
        for rook_sq in own_rooks:
            if chess.square_file(rook_sq) == king_file:
                features.rook_on_same_file_as_king = True
            if chess.square_rank(rook_sq) == king_rank:
                features.rook_on_same_rank_as_king = True
        
        # Check pawn shield
        pawn_shield_squares = []
        if side_to_move == chess.WHITE:
            if king_file > 0:
                pawn_shield_squares.append(chess.square(king_file - 1, 1))
            pawn_shield_squares.append(chess.square(king_file, 1))
            if king_file < 7:
                pawn_shield_squares.append(chess.square(king_file + 1, 1))
        else:
            if king_file > 0:
                pawn_shield_squares.append(chess.square(king_file - 1, 6))
            pawn_shield_squares.append(chess.square(king_file, 6))
            if king_file < 7:
                pawn_shield_squares.append(chess.square(king_file + 1, 6))
        
        pawn_count = sum(1 for sq in pawn_shield_squares 
                        if board.piece_at(sq) and 
                        board.piece_at(sq).piece_type == chess.PAWN and
                        board.piece_at(sq).color == side_to_move)
        features.pawn_shield_intact = pawn_count >= 2
        
        # Find hanging pieces
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == side_to_move:
                # Is it attacked?
                if board.is_attacked_by(not side_to_move, sq):
                    features.pieces_under_attack.append(chess.square_name(sq))
                    # Is it defended?
                    if not board.is_attacked_by(side_to_move, sq):
                        features.hanging_pieces.append(chess.square_name(sq))
        
        # Material count
        piece_values = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9
        }
        white_material = sum(len(board.pieces(pt, chess.WHITE)) * val 
                           for pt, val in piece_values.items())
        black_material = sum(len(board.pieces(pt, chess.BLACK)) * val 
                           for pt, val in piece_values.items())
        if side_to_move == chess.WHITE:
            features.material_balance = white_material - black_material
        else:
            features.material_balance = black_material - white_material
        
        # Check if best move creates luft
        if best_move and features.king_on_back_rank and not features.king_has_luft:
            try:
                move = board.parse_san(best_move)
                board.push(move)
                # Recount escape squares
                new_escapes = 0
                for sq in board.attacks(king_square):
                    if board.piece_at(sq) is None or board.piece_at(sq).color != side_to_move:
                        if not board.is_attacked_by(not side_to_move, sq):
                            new_escapes += 1
                if new_escapes > escape_squares:
                    features.king_has_luft = True  # Best move creates luft
                board.pop()
            except:
                pass
        
        return features


class PatternRuleExtractor:
    """Extracts generalizable rules from user feedback"""
    
    def __init__(self):
        self.analyzer = PositionAnalyzer()
        
        # Known pattern templates
        self.pattern_templates = {
            "KING_SAFETY_LUFT": {
                "required_features": {
                    "king_on_back_rank": True,
                    "king_escape_squares": 0,
                },
                "explanation_template": "The move {best_move} was better because it gives your king breathing room (luft), preventing back rank threats. Your king was trapped with no escape squares.",
            },
            "BACK_RANK_MATE_THREAT": {
                "required_features": {
                    "king_on_back_rank": True,
                    "back_rank_vulnerable": True,
                    "enemy_rook_on_back_rank": True,
                },
                "explanation_template": "You missed a back rank mate threat. Your king is stuck on the back rank with no escape, and the enemy rook/queen can deliver checkmate. {best_move} prevents this.",
            },
            "HANGING_PIECE": {
                "required_features": {
                    "hanging_pieces": ["*"],  # At least one hanging piece
                },
                "explanation_template": "You left a piece undefended. {best_move} would have protected it or removed it from danger.",
            },
            "PIECE_FORK": {
                "required_features": {
                    "fork_possible": True,
                },
                "explanation_template": "There was a fork threat. {best_move} would have prevented the opponent from attacking two pieces at once.",
            },
        }
    
    def extract_rule_from_feedback(
        self, 
        feedback: Dict,
        user_insight: str
    ) -> Optional[PatternRule]:
        """
        Extract a generalizable rule from user feedback.
        
        Args:
            feedback: The feedback document with position, moves, etc.
            user_insight: The user's explanation of what the real issue was
            
        Returns:
            A PatternRule that can match similar positions
        """
        fen = feedback.get("position_fen", "")
        best_move = feedback.get("best_move", "")
        played_move = feedback.get("move_played", "")
        
        if not fen:
            return None
        
        # Extract features from the position
        features = self.analyzer.extract_features(fen, best_move, played_move)
        
        # Analyze user insight to determine pattern type
        pattern_type = self._classify_user_insight(user_insight, features)
        
        # Get the template for this pattern
        template = self.pattern_templates.get(pattern_type)
        if not template:
            # Create a custom pattern from the features
            template = self._create_custom_pattern(features, user_insight, pattern_type)
        
        # Build the rule
        rule = PatternRule(
            rule_id=f"rule_{feedback.get('feedback_id', 'unknown')}",
            pattern_name=pattern_type,
            required_features=self._build_required_features(features, pattern_type),
            correct_classification=pattern_type,
            explanation_template=template.get("explanation_template", ""),
            confidence=0.8,
            source_feedback_ids=[feedback.get("feedback_id")],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        return rule
    
    def _classify_user_insight(self, user_insight: str, features: PositionFeatures) -> str:
        """Classify the user's insight into a pattern type"""
        insight_lower = user_insight.lower()
        
        # King safety patterns
        king_safety_keywords = [
            "breathing", "luft", "escape", "king.*safe", "king.*stuck", 
            "king.*trapped", "back rank", "no.*square", "king.*move"
        ]
        for keyword in king_safety_keywords:
            if re.search(keyword, insight_lower):
                if features.king_on_back_rank and features.king_escape_squares == 0:
                    return "KING_SAFETY_LUFT"
                elif features.back_rank_vulnerable:
                    return "BACK_RANK_MATE_THREAT"
                else:
                    return "KING_SAFETY"
        
        # Fork patterns
        fork_keywords = ["fork", "two pieces", "attack.*both", "double attack"]
        for keyword in fork_keywords:
            if re.search(keyword, insight_lower):
                return "PIECE_FORK"
        
        # Pin patterns
        pin_keywords = ["pin", "pinned", "cannot move"]
        for keyword in pin_keywords:
            if re.search(keyword, insight_lower):
                return "PIN"
        
        # Hanging piece patterns
        hanging_keywords = ["undefended", "hanging", "free piece", "take.*free"]
        for keyword in hanging_keywords:
            if re.search(keyword, insight_lower):
                return "HANGING_PIECE"
        
        # Defense patterns
        defense_keywords = ["defend", "protect", "guard", "cover"]
        for keyword in defense_keywords:
            if re.search(keyword, insight_lower):
                return "DEFENSIVE_MOVE"
        
        return "OTHER"
    
    def _build_required_features(self, features: PositionFeatures, pattern_type: str) -> Dict:
        """Build the required features for matching this pattern"""
        if pattern_type == "KING_SAFETY_LUFT":
            return {
                "king_on_back_rank": True,
                "king_escape_squares": {"$lte": 1},  # 0 or 1 escape squares
                "king_has_luft": False,
            }
        elif pattern_type == "BACK_RANK_MATE_THREAT":
            return {
                "king_on_back_rank": True,
                "back_rank_vulnerable": True,
            }
        elif pattern_type == "HANGING_PIECE":
            return {
                "hanging_pieces": {"$exists": True, "$ne": []},
            }
        elif pattern_type == "KING_SAFETY":
            return {
                "king_escape_squares": {"$lte": 2},
            }
        else:
            # Generic - use the actual features
            return {
                "king_on_back_rank": features.king_on_back_rank,
                "back_rank_vulnerable": features.back_rank_vulnerable,
            }
    
    def _create_custom_pattern(self, features: PositionFeatures, user_insight: str, pattern_type: str) -> Dict:
        """Create a custom pattern template based on features and insight"""
        return {
            "explanation_template": f"Based on the position features, the key issue was: {user_insight[:100]}. The best move addresses this by improving the position.",
        }
    
    def match_rule_to_position(self, rule: PatternRule, fen: str) -> Tuple[bool, float]:
        """
        Check if a rule matches a position.
        
        Returns:
            (matches: bool, confidence: float)
        """
        features = self.analyzer.extract_features(fen)
        features_dict = features.to_dict()
        
        matches = 0
        total = 0
        
        for key, required_value in rule.required_features.items():
            total += 1
            actual_value = features_dict.get(key)
            
            if isinstance(required_value, dict):
                # MongoDB-style operators
                if "$lte" in required_value and actual_value <= required_value["$lte"]:
                    matches += 1
                elif "$gte" in required_value and actual_value >= required_value["$gte"]:
                    matches += 1
                elif "$exists" in required_value:
                    if required_value["$exists"] and actual_value is not None:
                        if "$ne" in required_value and actual_value != required_value["$ne"]:
                            matches += 1
            elif actual_value == required_value:
                matches += 1
        
        if total == 0:
            return False, 0.0
        
        confidence = matches / total
        return confidence >= 0.7, confidence
    
    def generate_explanation(self, rule: PatternRule, fen: str, best_move: str, played_move: str) -> str:
        """Generate an explanation for a position using a matched rule"""
        template = rule.explanation_template
        
        # Fill in the template
        explanation = template.format(
            best_move=best_move,
            played_move=played_move,
        )
        
        return explanation


# Store and retrieve rules
class PatternRuleStore:
    """Stores and retrieves pattern rules from MongoDB"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.pattern_rules
        self.extractor = PatternRuleExtractor()
    
    async def add_rule(self, rule: PatternRule) -> str:
        """Add a new pattern rule"""
        doc = rule.to_dict()
        await self.collection.update_one(
            {"rule_id": rule.rule_id},
            {"$set": doc},
            upsert=True
        )
        return rule.rule_id
    
    async def find_matching_rules(self, fen: str) -> List[Tuple[PatternRule, float]]:
        """Find all rules that match a position"""
        matching = []
        
        async for doc in self.collection.find():
            rule = PatternRule(**{k: v for k, v in doc.items() if k != '_id'})
            matches, confidence = self.extractor.match_rule_to_position(rule, fen)
            if matches:
                matching.append((rule, confidence))
        
        # Sort by confidence
        matching.sort(key=lambda x: x[1], reverse=True)
        return matching
    
    async def extract_and_store_rule(self, feedback: Dict) -> Optional[PatternRule]:
        """Extract a rule from feedback and store it"""
        user_insight = feedback.get("user_explanation", "")
        if not user_insight:
            return None
        
        rule = self.extractor.extract_rule_from_feedback(feedback, user_insight)
        if rule:
            await self.add_rule(rule)
            return rule
        return None


# Main function to process feedback and extract rules
async def process_feedback_for_rules(db, feedback_id: str):
    """Process a feedback entry and extract pattern rules"""
    # Get the feedback
    feedback = await db.pattern_feedback.find_one({"feedback_id": feedback_id})
    if not feedback:
        return None
    
    store = PatternRuleStore(db)
    rule = await store.extract_and_store_rule(dict(feedback))
    
    if rule:
        print(f"Extracted rule: {rule.pattern_name}")
        print(f"Required features: {rule.required_features}")
        print(f"Explanation template: {rule.explanation_template}")
    
    return rule
