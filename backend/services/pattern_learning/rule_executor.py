"""
Rule Executor

Executes learned rules against chess positions to classify mistakes.
This is the runtime component that uses the learned rules.

Flow:
1. Receive position + move + Stockfish data
2. Extract pattern indicators from the data
3. Run through learned rules (highest priority first)
4. Return best matching classification with explanation
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

import chess

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of running learned rules against a position"""
    
    pattern: str
    confidence: float
    explanation: str
    rule_id: str
    
    # Evidence used for classification
    matched_signals: List[str]
    evidence: Dict
    
    # For tracking
    is_learned_rule: bool = True


class RuleExecutor:
    """
    Executes learned rules against positions.
    
    Usage:
        executor = RuleExecutor(db)
        await executor.load_rules()
        
        result = executor.classify(
            position_fen="...",
            move_played="Nf3",
            pv_after_played=["e5d4", "d4c3"],
            eval_drop=2.5
        )
        
        if result:
            print(f"Pattern: {result.pattern}")
            print(f"Explanation: {result.explanation}")
    """
    
    def __init__(self, db):
        """
        Initialize executor.
        
        Args:
            db: LearningDB instance
        """
        self.db = db
        self.rules: List[Dict] = []
        self.rules_loaded = False
    
    async def load_rules(self):
        """Load all active rules from database"""
        self.rules = await self.db.get_active_rules()
        self.rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        self.rules_loaded = True
        logger.info(f"Loaded {len(self.rules)} active learned rules")
    
    async def reload_rules(self):
        """Reload rules (call after new rules are added)"""
        await self.load_rules()
    
    def classify(
        self,
        position_fen: str,
        move_played: str,
        pv_after_played: List[str],
        eval_drop: float,
        best_move: str = None,
        user_color: str = "white"
    ) -> Optional[ClassificationResult]:
        """
        Classify a move using learned rules.
        
        Args:
            position_fen: FEN before the move
            move_played: The move that was played
            pv_after_played: Stockfish PV after the move
            eval_drop: Evaluation drop in pawns
            best_move: What Stockfish recommends
            user_color: "white" or "black"
            
        Returns:
            ClassificationResult if a rule matches, None otherwise
        """
        if not self.rules_loaded:
            logger.warning("Rules not loaded. Call load_rules() first.")
            return None
        
        # Extract indicators from the position and PV
        indicators = self._extract_indicators(
            position_fen, move_played, pv_after_played, eval_drop, user_color
        )
        
        # Try each rule in priority order
        for rule in self.rules:
            match_result = self._try_rule(rule, indicators)
            
            if match_result["matched"]:
                # Build explanation from template
                explanation = self._build_explanation(
                    rule, indicators, match_result["matched_signals"]
                )
                
                result = ClassificationResult(
                    pattern=rule.get("pattern", "UNKNOWN"),
                    confidence=rule.get("confidence", 0.5) * match_result["match_strength"],
                    explanation=explanation,
                    rule_id=rule.get("rule_id", ""),
                    matched_signals=match_result["matched_signals"],
                    evidence=indicators
                )
                
                # Track that this rule was triggered
                # (async tracking should be done by caller)
                
                return result
        
        return None
    
    def _extract_indicators(
        self,
        position_fen: str,
        move_played: str,
        pv: List[str],
        eval_drop: float,
        user_color: str
    ) -> Dict:
        """
        Extract pattern indicators from position and Stockfish data.
        
        These indicators are what the rules match against.
        """
        indicators = {
            "position_fen": position_fen,
            "move_played": move_played,
            "pv": pv,
            "eval_drop": eval_drop,
            "eval_drop_category": self._categorize_eval_drop(eval_drop),
            "user_color": user_color,
            "pv_length": len(pv),
            
            # PV analysis
            "pv_captures": [],
            "pv_checks": [],
            "same_piece_captures_twice": False,
            "is_sequential_capture": False,
            "capture_piece_types": [],
            
            # Position analysis
            "piece_types_involved": [],
            "attacked_squares": [],
        }
        
        if not pv or not position_fen:
            return indicators
        
        try:
            board = chess.Board(position_fen)
            _ = chess.WHITE if user_color == "white" else chess.BLACK
            
            # Analyze PV moves
            capturing_piece_sq = None
            capturing_piece_type = None
            captures_by_same_piece = 0
            consecutive_captures = 0
            last_was_capture = False
            
            for i, move_str in enumerate(pv[:5]):
                try:
                    # Parse move
                    if len(move_str) >= 4:
                        move = chess.Move.from_uci(move_str)
                    else:
                        move = board.parse_san(move_str)
                    
                    piece = board.piece_at(move.from_square)
                    captured = board.piece_at(move.to_square)
                    
                    if piece:
                        indicators["piece_types_involved"].append(
                            chess.piece_name(piece.piece_type)
                        )
                    
                    # Track captures
                    if captured:
                        indicators["pv_captures"].append({
                            "move_index": i,
                            "capturing_piece": chess.piece_name(piece.piece_type) if piece else "?",
                            "captured_piece": chess.piece_name(captured.piece_type),
                            "square": chess.square_name(move.to_square)
                        })
                        indicators["capture_piece_types"].append(
                            chess.piece_name(captured.piece_type)
                        )
                        
                        # Check for same piece capturing twice (fork)
                        if piece and (move.from_square == capturing_piece_sq or 
                                     (capturing_piece_type == piece.piece_type and 
                                      capturing_piece_type == chess.PAWN)):
                            captures_by_same_piece += 1
                            if captures_by_same_piece >= 2:
                                indicators["same_piece_captures_twice"] = True
                        
                        capturing_piece_sq = move.to_square
                        capturing_piece_type = piece.piece_type if piece else None
                        
                        # Track consecutive captures
                        if last_was_capture:
                            consecutive_captures += 1
                            if consecutive_captures >= 1:
                                indicators["is_sequential_capture"] = True
                        last_was_capture = True
                    else:
                        last_was_capture = False
                    
                    # Track checks
                    if board.gives_check(move):
                        indicators["pv_checks"].append(i)
                    
                    board.push(move)
                    
                except Exception as e:
                    logger.debug(f"Error parsing PV move {move_str}: {e}")
                    break
            
            # Unique piece types
            indicators["piece_types_involved"] = list(set(indicators["piece_types_involved"]))
            
        except Exception as e:
            logger.debug(f"Error extracting indicators: {e}")
        
        return indicators
    
    def _categorize_eval_drop(self, eval_drop: float) -> str:
        """Categorize evaluation drop"""
        if eval_drop < 0.5:
            return "small"
        elif eval_drop < 1.5:
            return "medium"
        elif eval_drop < 3.0:
            return "large"
        else:
            return "critical"
    
    def _try_rule(self, rule: Dict, indicators: Dict) -> Dict:
        """
        Try to match a rule against the indicators.
        
        Returns:
            {"matched": bool, "match_strength": float, "matched_signals": list}
        """
        detection_signals = rule.get("detection_signals", [])
        if not detection_signals:
            return {"matched": False, "match_strength": 0, "matched_signals": []}
        
        matched_signals = []
        
        for signal in detection_signals:
            signal_lower = signal.lower()
            
            # Check various signal types
            
            # PV-based signals
            if "sequential capture" in signal_lower or "consecutive capture" in signal_lower:
                if indicators.get("is_sequential_capture"):
                    matched_signals.append(signal)
            
            elif "same piece captures" in signal_lower or "captures twice" in signal_lower:
                if indicators.get("same_piece_captures_twice"):
                    matched_signals.append(signal)
            
            elif "pawn" in signal_lower and "capture" in signal_lower:
                if any("pawn" in c.get("capturing_piece", "").lower() 
                       for c in indicators.get("pv_captures", [])):
                    matched_signals.append(signal)
            
            elif "fork" in signal_lower:
                # Fork indicators
                if (indicators.get("same_piece_captures_twice") or 
                    len(indicators.get("pv_captures", [])) >= 2):
                    matched_signals.append(signal)
            
            elif "check" in signal_lower:
                if indicators.get("pv_checks"):
                    matched_signals.append(signal)
            
            # Eval-based signals
            elif "material" in signal_lower and "swing" in signal_lower:
                if indicators.get("eval_drop_category") in ["large", "critical"]:
                    matched_signals.append(signal)
            
            elif "eval drop" in signal_lower or "evaluation" in signal_lower:
                if indicators.get("eval_drop", 0) > 1.0:
                    matched_signals.append(signal)
            
            # Piece-based signals
            elif "knight" in signal_lower:
                if "knight" in indicators.get("piece_types_involved", []):
                    matched_signals.append(signal)
            
            elif "bishop" in signal_lower:
                if "bishop" in indicators.get("piece_types_involved", []):
                    matched_signals.append(signal)
            
            elif "rook" in signal_lower:
                if "rook" in indicators.get("piece_types_involved", []):
                    matched_signals.append(signal)
        
        # Calculate match strength
        if not detection_signals:
            match_strength = 0
        else:
            match_strength = len(matched_signals) / len(detection_signals)
        
        # Need at least 50% of signals to match
        matched = match_strength >= 0.5
        
        return {
            "matched": matched,
            "match_strength": match_strength,
            "matched_signals": matched_signals
        }
    
    def _build_explanation(
        self, 
        rule: Dict, 
        indicators: Dict, 
        matched_signals: List[str]
    ) -> str:
        """Build explanation from rule template and indicators"""
        template = rule.get("explanation_template", "")
        
        if not template:
            pattern = rule.get("pattern", "tactical error")
            return f"This move was a {pattern.lower().replace('_', ' ')}."
        
        # Fill in template variables
        try:
            # Extract pieces from indicators
            piece = "piece"
            if indicators.get("piece_types_involved"):
                piece = indicators["piece_types_involved"][0]
            
            # Extract captured pieces
            captured = "material"
            if indicators.get("capture_piece_types"):
                captured = " and ".join(indicators["capture_piece_types"][:2])
            
            # Extract pawn info for pawn forks
            pawn_square = "pawn"
            if indicators.get("pv_captures"):
                for cap in indicators["pv_captures"]:
                    if "pawn" in cap.get("capturing_piece", "").lower():
                        pawn_square = cap.get("square", "pawn")
                        break
            
            explanation = template.format(
                piece=piece,
                captured=captured,
                pawn_square=pawn_square,
                consequence=f"losing {captured}",
                pattern=rule.get("pattern", "").lower().replace("_", " ")
            )
            
            return explanation
            
        except Exception as e:
            logger.debug(f"Error building explanation: {e}")
            return template
    
    async def track_rule_usage(self, rule_id: str, was_correct: bool):
        """Track when a rule is used (for accuracy stats)"""
        await self.db.increment_rule_trigger(rule_id, was_correct)
    
    def get_loaded_rules_count(self) -> int:
        """Get count of loaded rules"""
        return len(self.rules)
    
    def get_rules_summary(self) -> Dict:
        """Get summary of loaded rules"""
        if not self.rules:
            return {"total": 0, "by_pattern": {}}
        
        by_pattern = {}
        for rule in self.rules:
            pattern = rule.get("pattern", "UNKNOWN")
            by_pattern[pattern] = by_pattern.get(pattern, 0) + 1
        
        return {
            "total": len(self.rules),
            "by_pattern": by_pattern
        }
