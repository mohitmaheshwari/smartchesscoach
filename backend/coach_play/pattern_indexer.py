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


# =============================================================================
# CROSS-GAME PATTERN INDEX
# =============================================================================
# This is the STRUCTURAL layer that makes personalization deterministic.
# NOT about language - about DATA RETRIEVAL.

@dataclass
class PatternFrequency:
    """Cross-game pattern frequency analysis"""
    motif: CognitiveGap
    total_occurrences: int
    recent_occurrences: int  # Last 5 games
    games_with_pattern: List[str]  # Game IDs
    first_seen: datetime
    last_seen: datetime
    trend: str  # "improving", "worsening", "stable"
    trend_confidence: float


@dataclass  
class CrossGameIndex:
    """Complete cross-game pattern index for a user"""
    user_id: str
    total_games_analyzed: int
    pattern_frequencies: Dict[str, PatternFrequency]
    dominant_weakness: Optional[CognitiveGap]
    improving_patterns: List[CognitiveGap]
    worsening_patterns: List[CognitiveGap]


class CrossGamePatternIndex:
    """
    Cross-Game Pattern Index - The STRUCTURAL personalization layer.
    
    This answers:
    - "This is your 3rd missed fork in 5 games" (frequency)
    - "This pattern is getting worse" (trend)
    - "Your main weakness is threat blindness" (dominant)
    
    NOT LLM-based. Deterministic data retrieval.
    """
    
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        self._index: Optional[CrossGameIndex] = None
        self._pattern_list: List[IndexedPattern] = []
    
    async def build_cross_game_index(self, max_games: int = 50) -> CrossGameIndex:
        """
        Build complete cross-game pattern index.
        
        Returns structured analysis of ALL patterns across games.
        """
        # First build the pattern list
        indexer = PatternIndexer(self.db, self.user_id)
        await indexer.build_index(max_games)
        self._pattern_list = indexer._pattern_index
        
        # Count pattern frequencies
        pattern_counts: Dict[CognitiveGap, List[IndexedPattern]] = {}
        for p in self._pattern_list:
            if p.motif not in pattern_counts:
                pattern_counts[p.motif] = []
            pattern_counts[p.motif].append(p)
        
        # Build frequency analysis for each motif
        pattern_frequencies: Dict[str, PatternFrequency] = {}
        
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=14)  # Last 2 weeks
        
        for motif, patterns in pattern_counts.items():
            # Sort by date
            patterns.sort(key=lambda x: x.date)
            
            # Count recent vs total
            recent = [p for p in patterns if p.date.replace(tzinfo=timezone.utc) > recent_cutoff]
            older = [p for p in patterns if p.date.replace(tzinfo=timezone.utc) <= recent_cutoff]
            
            # Calculate trend
            trend, trend_confidence = self._calculate_trend(older, recent)
            
            pattern_frequencies[motif.value] = PatternFrequency(
                motif=motif,
                total_occurrences=len(patterns),
                recent_occurrences=len(recent),
                games_with_pattern=[p.game_id for p in patterns],
                first_seen=patterns[0].date if patterns else now,
                last_seen=patterns[-1].date if patterns else now,
                trend=trend,
                trend_confidence=trend_confidence
            )
        
        # Identify dominant weakness (most frequent pattern)
        dominant = None
        max_count = 0
        for motif, freq in pattern_frequencies.items():
            if freq.total_occurrences > max_count:
                max_count = freq.total_occurrences
                dominant = freq.motif
        
        # Identify trends
        improving = [f.motif for f in pattern_frequencies.values() if f.trend == "improving"]
        worsening = [f.motif for f in pattern_frequencies.values() if f.trend == "worsening"]
        
        # Count unique games
        unique_games = set(p.game_id for p in self._pattern_list)
        
        self._index = CrossGameIndex(
            user_id=self.user_id,
            total_games_analyzed=len(unique_games),
            pattern_frequencies=pattern_frequencies,
            dominant_weakness=dominant,
            improving_patterns=improving,
            worsening_patterns=worsening
        )
        
        return self._index
    
    def _calculate_trend(
        self, 
        older_patterns: List[IndexedPattern], 
        recent_patterns: List[IndexedPattern]
    ) -> Tuple[str, float]:
        """
        Calculate trend: is this pattern improving, worsening, or stable?
        
        Returns (trend, confidence)
        """
        older_count = len(older_patterns)
        recent_count = len(recent_patterns)
        
        # Need data for meaningful trend
        if older_count == 0 and recent_count == 0:
            return "stable", 0.0
        
        if older_count == 0:
            # New pattern - can't determine trend yet
            return "new", 0.3
        
        if recent_count == 0:
            # Pattern hasn't appeared recently - improving!
            return "improving", 0.7
        
        # Calculate rate change
        # Normalize by expected rate (assume older period = 2 weeks)
        older_rate = older_count / 14  # per day
        recent_rate = recent_count / 14  # per day
        
        if recent_rate > older_rate * 1.5:
            return "worsening", min(0.9, 0.5 + (recent_rate / older_rate - 1) * 0.3)
        elif recent_rate < older_rate * 0.5:
            return "improving", min(0.9, 0.5 + (1 - recent_rate / older_rate) * 0.3)
        else:
            return "stable", 0.6
    
    async def get_pattern_frequency(self, motif: CognitiveGap) -> Optional[PatternFrequency]:
        """Get frequency data for a specific motif."""
        if not self._index:
            await self.build_cross_game_index()
        
        return self._index.pattern_frequencies.get(motif.value)
    
    async def get_pattern_context_for_coaching(
        self, 
        current_motif: CognitiveGap,
        current_game_id: str = None
    ) -> Dict[str, Any]:
        """
        Get COMPLETE pattern context for coaching.
        
        This is the MASTER function that returns everything needed:
        - Frequency: "This is your 3rd missed fork"
        - Trend: "This pattern is getting worse"
        - Similar game: "Remember your game against X?"
        - Injection context: Ready for LLM
        """
        if not self._index:
            await self.build_cross_game_index()
        
        result = {
            "has_pattern": False,
            "frequency": None,
            "trend": None,
            "similar_game": None,
            "injection_context": None
        }
        
        freq = self._index.pattern_frequencies.get(current_motif.value)
        if not freq:
            return result
        
        result["has_pattern"] = True
        result["frequency"] = {
            "total": freq.total_occurrences,
            "recent": freq.recent_occurrences,
            "message": self._format_frequency_message(freq)
        }
        result["trend"] = {
            "direction": freq.trend,
            "confidence": freq.trend_confidence,
            "message": self._format_trend_message(freq)
        }
        
        # Get similar game (most recent with same motif, excluding current)
        similar_games = [
            p for p in self._pattern_list 
            if p.motif == current_motif and p.game_id != current_game_id
        ]
        
        if similar_games:
            similar_games.sort(key=lambda x: x.date, reverse=True)
            most_recent = similar_games[0]
            
            days_ago = (datetime.now(timezone.utc) - most_recent.date.replace(tzinfo=timezone.utc)).days
            when = self._format_when(days_ago)
            
            result["similar_game"] = {
                "game_id": most_recent.game_id,
                "move_number": most_recent.move_number,
                "opponent": most_recent.opponent,
                "when": when,
                "what_happened": most_recent.what_happened
            }
        
        # Build complete injection context
        result["injection_context"] = self._build_injection_context(
            current_motif, freq, result.get("similar_game")
        )
        
        return result
    
    def _format_frequency_message(self, freq: PatternFrequency) -> str:
        """Format frequency for human consumption."""
        if freq.recent_occurrences == 0:
            return f"You've had this pattern {freq.total_occurrences} times total, but not recently."
        
        total = freq.total_occurrences
        recent = freq.recent_occurrences
        
        if recent == 1:
            return f"This is only the 2nd time you've made this mistake recently."
        else:
            return f"This is your {recent + 1}th time making this mistake in recent games ({total} total)."
    
    def _format_trend_message(self, freq: PatternFrequency) -> str:
        """Format trend for human consumption."""
        if freq.trend == "improving":
            return "Good news: this pattern is becoming less frequent."
        elif freq.trend == "worsening":
            return "Warning: this pattern is becoming more frequent."
        elif freq.trend == "new":
            return "This is a new pattern in your games."
        else:
            return "This pattern has been stable."
    
    def _format_when(self, days_ago: int) -> str:
        """Format days ago to human string."""
        if days_ago == 0:
            return "earlier today"
        elif days_ago == 1:
            return "yesterday"
        elif days_ago < 7:
            return f"{days_ago} days ago"
        elif days_ago < 30:
            return f"{days_ago // 7} weeks ago"
        else:
            return f"{days_ago // 30} months ago"
    
    def _build_injection_context(
        self, 
        motif: CognitiveGap, 
        freq: PatternFrequency,
        similar_game: Optional[Dict]
    ) -> str:
        """Build complete injection context for LLM."""
        
        lines = ["PERSONAL PATTERN HISTORY (You MUST reference this!):"]
        
        # Frequency
        lines.append(f"- Pattern: {motif.value}")
        lines.append(f"- Frequency: {freq.total_occurrences} total, {freq.recent_occurrences} in last 2 weeks")
        lines.append(f"- Trend: {freq.trend.upper()}")
        
        # Similar game reference
        if similar_game:
            lines.append(f"- Last occurrence: Game against {similar_game['opponent']} {similar_game['when']}")
            lines.append(f"- What happened: {similar_game['what_happened']}")
            lines.append(f">>> SAY: 'Remember your game against {similar_game['opponent']}? This is the same pattern.'")
        
        # Frequency-aware instruction
        if freq.recent_occurrences >= 3:
            lines.append(f">>> EMPHASIZE: 'This is your {freq.recent_occurrences + 1}th time. We need to break this habit.'")
        
        # Trend-aware instruction
        if freq.trend == "worsening":
            lines.append(">>> TONE: Be direct. This pattern is getting worse.")
        elif freq.trend == "improving":
            lines.append(">>> TONE: Acknowledge progress. This pattern is less frequent than before.")
        
        return "\n".join(lines)


async def get_full_pattern_context(
    db,
    user_id: str,
    current_motif: CognitiveGap,
    current_game_id: str = None
) -> Dict[str, Any]:
    """
    Master function: Get COMPLETE pattern context for personalized coaching.
    
    This combines:
    - Pattern frequency (how often this happens)
    - Trend analysis (improving/worsening)
    - Similar game retrieval (exact game ID)
    - LLM injection context
    
    Use this for the richest personalization.
    """
    index = CrossGamePatternIndex(db, user_id)
    return await index.get_pattern_context_for_coaching(current_motif, current_game_id)

