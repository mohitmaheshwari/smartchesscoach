"""
Claude-based endgame analyzer — generate principle-driven explanations.

Uses Claude to analyze endgame positions and explain why moves are good/bad
using chess principles (rule of square, critical pieces, threats).

This is the LLM layer that bridges classification → principle-based captions.
"""

import os
import logging
from typing import Optional, Dict, Any
import hashlib

logger = logging.getLogger(__name__)


class EndgameAnalyzer:
    """Analyzes endgame positions using Claude for principle-based explanations"""

    def __init__(self):
        self.client = None
        self._cache = {}  # Simple in-memory cache (FEN hash -> explanation)
        self._init_client()

    def _init_client(self):
        """Initialize Claude client"""
        try:
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY not set, Claude analyzer disabled")
                return

            self.client = Anthropic()
        except Exception as e:
            logger.warning(f"Failed to initialize Claude client: {e}")

    def _cache_key(self, fen: str, move: str) -> str:
        """Generate cache key from FEN + move"""
        key = f"{fen}_{move}"
        return hashlib.md5(key.encode()).hexdigest()

    async def analyze_move(
        self,
        fen: str,
        move_san: str,
        position_type: str,
        critical_pieces: Dict[str, str],
        threats: list,
        eval_before: int,
        eval_after: int,
        best_move_san: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a move using Claude and return principle-based explanation.

        Args:
            fen: Position FEN
            move_san: The move in SAN (e.g., "Rf3+")
            position_type: Endgame type (e.g., "K+R vs K+P")
            critical_pieces: Dict of critical pieces and their roles
            threats: List of identified threats
            eval_before: Evaluation before move
            eval_after: Evaluation after move
            best_move_san: Best move if different

        Returns:
            {
                "explanation": "principle-based explanation",
                "principles_used": ["rule_of_square", "critical_piece"],
                "quality_score": 0.8
            }
        """

        # Check cache
        cache_key = self._cache_key(fen, move_san)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.client:
            logger.warning("Claude client not available, using fallback")
            return self._fallback_explanation(move_san, best_move_san, eval_after - eval_before)

        try:
            # Build context for Claude
            context = self._build_context(
                position_type, critical_pieces, threats, eval_before, eval_after, best_move_san
            )

            # Prompt Claude for principle-based analysis
            prompt = f"""You are a chess coach explaining why a move is good or bad in this endgame.

POSITION TYPE: {position_type}

KEY ELEMENTS:
- Critical pieces: {', '.join([f'{piece}: {role}' for piece, role in critical_pieces.items()])}
- Threats: {', '.join(threats) if threats else 'None identified'}
- Evaluation before move: {eval_before} cp
- Evaluation after move: {eval_after} cp
- Change: {eval_after - eval_before:+d} cp

MOVE PLAYED: {move_san}
{f'BEST MOVE: {best_move_san}' if best_move_san else ''}

TASK:
1. Explain WHY {move_san} is {'bad' if eval_after < eval_before - 100 else 'good'} using chess PRINCIPLES, not just evaluation.
2. For {position_type} positions, explain using relevant principles:
   - Rule of the square (can the king catch the pawn?)
   - Critical piece roles (what does each piece defend/attack?)
   - Promotion threats (will a pawn promote if defended piece is removed?)
   - King activity and tempo
3. If the move is bad, suggest what the REAL problem is.
4. Format:
   - First sentence: What's the core issue?
   - Next sentences: Explain using principles
   - Last sentence: What should be played instead?

IMPORTANT: Use concrete, position-specific reasoning. Not generic principles.
Example of what we want:
"Rf3+ removes your rook - the only defender against Black's a5 pawn. By the rule of the square,
your king can't catch it alone from d6. Play Re1 or Re5 to keep your rook working."

Example of what we DON'T want:
"This move loses material. Try something better."
"""

            response = self.client.messages.create(
                model="claude-opus-4-1-20250805",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            explanation = response.content[0].text

            # Verify explanation mentions principles
            principles = self._extract_principles(explanation)

            result = {
                "explanation": explanation,
                "principles_used": principles,
                "quality_score": 0.8 if len(principles) >= 2 else 0.6,
            }

            # Cache it
            self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return self._fallback_explanation(move_san, best_move_san, eval_after - eval_before)

    def _build_context(
        self,
        position_type: str,
        critical_pieces: Dict[str, str],
        threats: list,
        eval_before: int,
        eval_after: int,
        best_move_san: Optional[str],
    ) -> str:
        """Build a concise context string for Claude"""
        lines = [
            f"Position type: {position_type}",
            f"Critical pieces: {critical_pieces}",
            f"Threats: {threats}",
            f"Eval shift: {eval_before} → {eval_after} (change: {eval_after - eval_before:+d}cp)",
        ]
        if best_move_san:
            lines.append(f"Better move: {best_move_san}")
        return "\n".join(lines)

    def _extract_principles(self, explanation: str) -> list:
        """Extract principle keywords from explanation"""
        principles = []
        keywords = {
            "rule of the square": "rule_of_square",
            "rule of square": "rule_of_square",
            "opposition": "opposition",
            "critical piece": "critical_piece",
            "promotion": "promotion_threat",
            "pawn promotes": "promotion_threat",
            "rook activity": "piece_activity",
            "king activity": "king_activity",
            "tempo": "tempo",
            "zugzwang": "zugzwang",
        }

        explanation_lower = explanation.lower()
        for keyword, principle in keywords.items():
            if keyword in explanation_lower and principle not in principles:
                principles.append(principle)

        return principles

    def _fallback_explanation(self, move: str, best_move: Optional[str], cp_loss: int) -> Dict:
        """Fallback when Claude is unavailable"""
        if cp_loss < -100:
            explanation = f"{move} is a significant mistake."
        elif cp_loss < -50:
            explanation = f"{move} is not ideal."
        else:
            explanation = f"{move} is fine."

        if best_move:
            explanation += f" Better: {best_move}."

        return {
            "explanation": explanation,
            "principles_used": [],
            "quality_score": 0.3,
        }


# Singleton instance
_analyzer = None


def get_analyzer() -> EndgameAnalyzer:
    """Get or create the analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = EndgameAnalyzer()
    return _analyzer


async def analyze_endgame_move(
    fen: str,
    move_san: str,
    position_type: str,
    critical_pieces: Dict[str, str],
    threats: list,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str] = None,
) -> str:
    """
    Main entry point: analyze an endgame move and return explanation.

    Returns:
        Principle-based explanation string
    """
    analyzer = get_analyzer()
    result = await analyzer.analyze_move(
        fen=fen,
        move_san=move_san,
        position_type=position_type,
        critical_pieces=critical_pieces,
        threats=threats,
        eval_before=eval_before,
        eval_after=eval_after,
        best_move_san=best_move_san,
    )
    return result["explanation"]
