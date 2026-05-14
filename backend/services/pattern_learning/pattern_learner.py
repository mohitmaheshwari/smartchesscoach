"""
Pattern Learner AI

The brain of the self-learning system. Uses GPT-4o to:
1. Analyze why the current classifier failed
2. Extract generalizable patterns from feedback
3. Generate new classification rules
4. Ensure rules are Stockfish-validated (no hallucination)

Key Principle: AI interprets Stockfish data, never invents chess facts.
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

import chess

logger = logging.getLogger(__name__)


@dataclass
class LearnedRule:
    """A classification rule learned from user feedback"""
    
    rule_id: str = field(default_factory=lambda: f"lr_{uuid.uuid4().hex[:12]}")
    
    # What pattern this rule detects
    pattern: str = ""  # e.g., "SEQUENTIAL_PAWN_FORK"
    pattern_description: str = ""
    
    # Detection signals (what to look for in Stockfish data)
    detection_signals: List[str] = field(default_factory=list)
    
    # Board conditions
    board_conditions: List[str] = field(default_factory=list)
    
    # How to distinguish from other patterns
    distinguishes_from: List[str] = field(default_factory=list)
    
    # Explanation template
    explanation_template: str = ""
    
    # Rule configuration
    priority: int = 50  # 0-100, higher = checked first
    confidence: float = 0.85
    status: str = "pending_review"  # pending_review -> active -> deprecated
    
    # Learning source
    source_feedback_id: str = ""
    source_game_id: str = ""
    source_position_fen: str = ""
    
    # Validation
    stockfish_validated: bool = False
    regression_passed: bool = False
    human_approved: bool = False
    
    # Stats (updated at runtime)
    stats: Dict = field(default_factory=lambda: {
        "times_triggered": 0,
        "positive_feedback": 0,
        "negative_feedback": 0,
        "accuracy_rate": 1.0
    })
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> "LearnedRule":
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PatternLearner:
    """
    AI-powered pattern learner that generates classification rules from feedback.
    
    Uses GPT-4o to:
    1. Analyze the position and Stockfish data
    2. Understand why the classification was wrong
    3. Generate a rule to correctly classify similar positions
    
    Key: The AI ONLY interprets Stockfish data. It does not invent chess facts.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the pattern learner.

        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY found. Pattern learning will be disabled.")

    async def _send(self, prompt: str) -> str:
        """Issue a single LLM call with this learner's system prompt."""
        from llm_service import call_llm
        from config import LLM_MODEL
        return await call_llm(
            system_message=self._get_system_prompt(),
            user_message=prompt,
            model=LLM_MODEL,
            max_tokens=2048,
        )
    
    def _get_system_prompt(self) -> str:
        """System prompt for the pattern learner AI"""
        return """You are a chess tactical pattern analyzer. Your job is to analyze user feedback on incorrect coach explanations and generate improved classification rules.

CRITICAL RULES:
1. You NEVER invent chess facts. You only interpret Stockfish data.
2. The Stockfish Principal Variation (PV) is the SOURCE OF TRUTH for what happens after a move.
3. Your rules must be based on CONCRETE evidence from the position and engine analysis.
4. Every rule you generate must be verifiable by looking at the board and PV.

Your task is to:
1. Analyze WHY the current classification was wrong
2. Identify what pattern indicators were missed
3. Generate a NEW rule that correctly identifies this tactical pattern
4. Ensure the rule generalizes to similar positions (not just this exact position)

When generating rules, focus on:
- What pieces are involved
- What the PV shows (sequence of moves)
- Material consequences
- Geometric patterns (same diagonal, same file, fork geometry, etc.)

Output your analysis as JSON."""
    
    async def analyze_feedback(self, feedback: Dict) -> Dict:
        """
        Analyze a piece of feedback to understand why classification failed.
        
        Args:
            feedback: User feedback dictionary with position, move, PV, etc.
            
        Returns:
            Analysis dictionary with root cause and pattern insights
        """
        if not self.api_key:
            return {"error": "No API key configured"}
        
        prompt = self._build_analysis_prompt(feedback)

        try:
            response = await self._send(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Error analyzing feedback: {e}")
            return {"error": str(e)}
    
    async def generate_rule(self, feedback: Dict, analysis: Dict = None) -> Optional[LearnedRule]:
        """
        Generate a new classification rule from feedback.
        
        Args:
            feedback: User feedback dictionary
            analysis: Optional pre-computed analysis
            
        Returns:
            LearnedRule if successful, None if failed
        """
        if not self.api_key:
            return None
        
        # Get analysis if not provided
        if not analysis:
            analysis = await self.analyze_feedback(feedback)
        
        if "error" in analysis:
            return None
        
        prompt = self._build_rule_generation_prompt(feedback, analysis)

        try:
            response = await self._send(prompt)
            rule_dict = self._parse_json_response(response)
            
            if not rule_dict or "error" in rule_dict:
                return None
            
            # Create the LearnedRule
            rule = LearnedRule(
                pattern=rule_dict.get("pattern", feedback.get("correct_classification", "UNKNOWN")),
                pattern_description=rule_dict.get("pattern_description", ""),
                detection_signals=rule_dict.get("detection_signals", []),
                board_conditions=rule_dict.get("board_conditions", []),
                distinguishes_from=rule_dict.get("distinguishes_from", []),
                explanation_template=rule_dict.get("explanation_template", ""),
                priority=rule_dict.get("priority", 50),
                confidence=rule_dict.get("confidence", 0.85),
                source_feedback_id=feedback.get("feedback_id", ""),
                source_game_id=feedback.get("game_id", ""),
                source_position_fen=feedback.get("position_fen", "")
            )
            
            return rule
            
        except Exception as e:
            logger.error(f"Error generating rule: {e}")
            return None
    
    async def generate_corrected_explanation(self, feedback: Dict) -> Optional[str]:
        """
        Generate a corrected explanation for the position.
        
        This is used for immediate display to the user while the rule is being validated.
        
        Args:
            feedback: User feedback with position context
            
        Returns:
            Corrected explanation string
        """
        if not self.api_key:
            return None
        
        prompt = self._build_correction_prompt(feedback)

        try:
            response = await self._send(prompt)
            result = self._parse_json_response(response)
            return result.get("corrected_explanation", response)
        except Exception as e:
            logger.error(f"Error generating corrected explanation: {e}")
            return None
    
    def _build_analysis_prompt(self, feedback: Dict) -> str:
        """Build prompt for analyzing why classification failed"""
        user_explanation = feedback.get('user_explanation', '')
        
        return f"""Analyze this chess position and explain why our classification was wrong. The user provided valuable insight - USE IT.

POSITION (FEN): {feedback.get('position_fen', 'N/A')}

MOVE PLAYED: {feedback.get('move_san', feedback.get('move_played', 'N/A'))}

STOCKFISH DATA:
- Eval before: {feedback.get('eval_before', 'N/A')} (centipawns)
- Eval after: {feedback.get('eval_after', 'N/A')} (centipawns)
- Best move was: {feedback.get('best_move', 'N/A')}
- Principal Variation after played move: {feedback.get('pv_after_played', [])}

OUR WRONG CLASSIFICATION: {feedback.get('system_classification', 'N/A')}
OUR WRONG EXPLANATION: {feedback.get('system_explanation', 'N/A')}

USER'S CORRECTION (IMPORTANT - THEY OFTEN SEE THE REAL ISSUE):
User says pattern is: {feedback.get('correct_classification', 'N/A')}
User's insight: "{user_explanation}"

Analyze the position and Stockfish data. The user's insight "{user_explanation}" is likely correct - incorporate it.

Output JSON:
{{
    "root_cause": "Why did our classifier fail? What did we miss?",
    "user_insight_validity": "How does the user's insight apply here?",
    "missed_indicators": ["What pattern indicators were missed?"],
    "pv_analysis": "What does the PV show happens?",
    "correct_pattern": "What is the actual tactical pattern? (Use user's insight)",
    "key_insight": "The key insight for identifying this pattern"
}}"""
    
    def _build_rule_generation_prompt(self, feedback: Dict, analysis: Dict) -> str:
        """Build prompt for generating a classification rule"""
        return f"""Based on this analysis, generate a classification rule that will correctly identify this pattern in the future.

ORIGINAL FEEDBACK:
- Position: {feedback.get('position_fen', 'N/A')}
- Move: {feedback.get('move_san', 'N/A')}
- PV: {feedback.get('pv_after_played', [])}
- Correct pattern: {feedback.get('correct_classification', 'N/A')}

ANALYSIS:
{json.dumps(analysis, indent=2)}

Generate a rule that:
1. Can detect this pattern by analyzing Stockfish PV data
2. Works for similar positions (not just this exact one)
3. Has clear detection signals based on concrete evidence
4. Distinguishes this pattern from the incorrectly assigned one

Output JSON:
{{
    "pattern": "PATTERN_NAME_IN_CAPS",
    "pattern_description": "Clear description of the pattern",
    "detection_signals": [
        "Signal 1: What to look for in PV",
        "Signal 2: What pieces are involved",
        "Signal 3: Material/positional consequence"
    ],
    "board_conditions": [
        "Condition 1: Board state requirement",
        "Condition 2: Piece placement requirement"
    ],
    "distinguishes_from": ["PATTERN_1", "PATTERN_2"],
    "explanation_template": "Your [piece] walked into a [pattern]. [Consequence based on PV].",
    "priority": 75,
    "confidence": 0.85
}}"""
    
    def _build_correction_prompt(self, feedback: Dict) -> str:
        """Build prompt for generating corrected explanation"""
        user_explanation = feedback.get('user_explanation', '')
        
        return f"""You are a chess coach correcting an incorrect explanation. A user flagged this explanation as wrong and provided their insight.

POSITION: {feedback.get('position_fen', 'N/A')}
MOVE PLAYED: {feedback.get('move_san', 'N/A')}
BEST MOVE WAS: {feedback.get('best_move', 'N/A')}

STOCKFISH DATA:
- Eval before: {feedback.get('eval_before', 'N/A')} centipawns
- Eval after: {feedback.get('eval_after', 'N/A')} centipawns
- What happens after played move (PV): {feedback.get('pv_after_played', [])}

THE WRONG EXPLANATION WE GAVE:
"{feedback.get('system_explanation', 'N/A')}"

USER'S CORRECTION (IMPORTANT - USE THIS INSIGHT):
Pattern type: {feedback.get('correct_classification', 'N/A')}
User's explanation: "{user_explanation}"

Your task:
1. INCORPORATE the user's insight - they often see something we missed
2. The user said: "{user_explanation}" - this is likely the REAL reason
3. Generate a corrected explanation that combines:
   - The user's insight (primary)
   - What the Stockfish PV shows (supporting evidence)
4. Keep it simple, 1-2 sentences max
5. Speak directly to the student ("You played X instead of Y because...")

Output JSON:
{{
    "corrected_explanation": "Your explanation incorporating the user's insight",
    "tactical_motif": "KING_SAFETY/FORK/PIN/SKEWER/DISCOVERED_ATTACK/TRAPPED_PIECE/BACK_RANK/OTHER",
    "consequence": "What material/position is lost",
    "user_insight_used": true
}}"""
    
    def _parse_json_response(self, response: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks"""
        try:
            # Try direct JSON parse first
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    return json.loads(response[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # Try to find any JSON object in the response
        import re
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"Could not parse JSON from response: {response[:200]}...")
        return {"error": "Could not parse response", "raw": response}
    
    def extract_pv_pattern(self, pv: List[str], position_fen: str) -> Dict:
        """
        Extract pattern indicators from Principal Variation.
        
        This is a helper method that analyzes the PV to identify:
        - Piece types involved
        - Capture sequences
        - Check patterns
        - Fork/pin geometry
        """
        if not pv:
            return {}
        
        try:
            board = chess.Board(position_fen)
        except Exception:
            return {}
        
        pattern_info = {
            "pv_length": len(pv),
            "captures": [],
            "checks": [],
            "piece_moves": [],
            "is_sequential_capture": False,
            "same_piece_captures_twice": False
        }
        
        capturing_piece = None
        
        for i, move_str in enumerate(pv[:5]):  # Analyze first 5 moves
            try:
                if len(move_str) >= 4:
                    move = chess.Move.from_uci(move_str)
                else:
                    move = board.parse_san(move_str)
                
                piece = board.piece_at(move.from_square)
                captured = board.piece_at(move.to_square)
                
                move_info = {
                    "move": move_str,
                    "piece": chess.piece_name(piece.piece_type) if piece else "unknown",
                    "from": chess.square_name(move.from_square),
                    "to": chess.square_name(move.to_square),
                    "is_capture": captured is not None,
                    "captured": chess.piece_name(captured.piece_type) if captured else None
                }
                
                if board.gives_check(move):
                    move_info["gives_check"] = True
                    pattern_info["checks"].append(i)
                
                pattern_info["piece_moves"].append(move_info)
                
                if captured:
                    pattern_info["captures"].append({
                        "move_index": i,
                        "capturing_piece": move_info["piece"],
                        "captured_piece": move_info["captured"]
                    })
                    
                    # Check for same piece capturing twice (fork pattern)
                    if capturing_piece == (move.from_square, piece.piece_type if piece else None):
                        pattern_info["same_piece_captures_twice"] = True
                    
                    if piece:
                        capturing_piece = (move.to_square, piece.piece_type)
                
                board.push(move)
                
            except Exception as e:
                logger.debug(f"Error parsing PV move {move_str}: {e}")
                break
        
        # Check for sequential captures (fork indicator)
        if len(pattern_info["captures"]) >= 2:
            indices = [c["move_index"] for c in pattern_info["captures"]]
            if indices == list(range(indices[0], indices[0] + len(indices))):
                pattern_info["is_sequential_capture"] = True
        
        return pattern_info
