"""
Chess Brain Schemas
===================

Core data structures for the deterministic coaching engine.
These are the building blocks that flow through the system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .enums import (
    TeachingMode,
    GamePhase,
    MistakeCategory,
    TacticalPattern,
    StrategicConcept,
    BehavioralPattern,
    LessonPriority,
    MoveQuality,
    ExplanationType
)


@dataclass
class DetectorResult:
    """
    Result from a single detector run.
    Each detector produces one of these when it fires.
    """
    detector_id: str                    # Unique detector identifier
    detected: bool                      # Whether the pattern was found
    confidence: float = 1.0             # 0.0-1.0, how sure are we?
    
    # What was detected
    pattern_type: Optional[str] = None  # TacticalPattern, StrategicConcept, or BehavioralPattern value
    category: Optional[str] = None      # MistakeCategory value
    
    # Specific details
    details: Dict[str, Any] = field(default_factory=dict)
    # Example details:
    # - attacking_piece: "knight"
    # - target_squares: ["e4", "f7"]  
    # - target_pieces: ["queen", "rook"]
    # - severity: "major" | "minor"
    
    # Teaching hook
    teaching_hook: Optional[str] = None  # Short phrase: "Knight fork wins the queen"
    key_squares: List[str] = field(default_factory=list)  # For board highlighting


@dataclass
class PositionInsightObject:
    """
    The CORE data structure - everything known about a position.
    Built by aggregating all detector results + Stockfish data.
    
    This is passed to the LessonSelectionEngine to choose
    what to teach.
    """
    # === Position Identity ===
    fen: str
    move_number: int
    user_color: str  # "white" | "black"
    
    # === Stockfish Truth Layer ===
    eval_before: float              # Centipawn eval before user's move
    eval_after: float               # Centipawn eval after user's move
    best_move: str                  # Stockfish's best move (SAN)
    user_move: str                  # What user played (SAN)
    move_quality: MoveQuality       # Classified quality
    cp_loss: int                    # Centipawn loss
    pv_after_best: List[str] = field(default_factory=list)  # Principal variation
    
    # === Game Phase ===
    game_phase: GamePhase = GamePhase.MIDDLEGAME
    phase_percent: int = 50         # 0=opening, 100=endgame
    
    # === Detector Results ===
    tactical_detections: List[DetectorResult] = field(default_factory=list)
    strategic_detections: List[DetectorResult] = field(default_factory=list)
    behavioral_detections: List[DetectorResult] = field(default_factory=list)
    
    # === Opening Context ===
    in_opening_book: bool = False
    opening_name: Optional[str] = None
    opening_key: Optional[str] = None
    is_known_trap: bool = False
    trap_name: Optional[str] = None
    
    # === Context ===
    was_winning: bool = False       # Was user winning before this move?
    is_check: bool = False
    is_capture: bool = False
    threats_after: List[str] = field(default_factory=list)  # What opponent threatens
    
    # === Time Data (if available) ===
    time_spent: Optional[float] = None       # Seconds on this move
    time_remaining: Optional[float] = None   # Clock time left
    
    def get_all_detections(self) -> List[DetectorResult]:
        """Get all detector results combined."""
        return (
            self.tactical_detections + 
            self.strategic_detections + 
            self.behavioral_detections
        )
    
    def has_detection(self, pattern_type: str) -> bool:
        """Check if a specific pattern was detected."""
        for d in self.get_all_detections():
            if d.pattern_type == pattern_type and d.detected:
                return True
        return False
    
    def get_primary_detection(self) -> Optional[DetectorResult]:
        """Get the highest-confidence detection, if any."""
        all_detections = [d for d in self.get_all_detections() if d.detected]
        if not all_detections:
            return None
        return max(all_detections, key=lambda x: x.confidence)


@dataclass
class LessonCandidate:
    """
    A potential lesson to teach, with embedded teaching mode.
    The LessonSelectionEngine generates multiple candidates
    and scores them to select one.
    """
    # Identity
    candidate_id: str
    teaching_mode: TeachingMode     # EMBEDDED - which mode this would use
    
    # What to teach
    title: str                      # "Fork Attack Pattern"
    main_insight: str               # "Your knight on d5 could fork the queen and rook"
    explanation_type: ExplanationType
    
    # Scoring inputs
    severity: float = 0.5           # 0-1, how serious is this?
    clarity: float = 0.5            # 0-1, how clear to teach?
    player_relevance: float = 0.5   # 0-1, relevant to player's profile?
    freshness: float = 1.0          # 0-1, decays if recently taught
    
    # Priority
    priority: LessonPriority = LessonPriority.NORMAL
    
    # Detection source
    source_detector: Optional[str] = None
    detector_result: Optional[DetectorResult] = None
    
    # Template for explanation
    template_key: Optional[str] = None
    template_vars: Dict[str, Any] = field(default_factory=dict)
    
    # Optional Socratic hook
    socratic_question: Optional[str] = None
    
    def calculate_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate lesson score using weighted formula.
        
        Score = (Severity * W1) + (Clarity * W2) + (Player_Relevance * W3) 
                * Priority_Multiplier * Freshness
        """
        w = weights or {
            "severity": 0.4,
            "clarity": 0.3,
            "relevance": 0.3
        }
        
        base_score = (
            self.severity * w.get("severity", 0.4) +
            self.clarity * w.get("clarity", 0.3) +
            self.player_relevance * w.get("relevance", 0.3)
        )
        
        # Priority multiplier
        priority_mult = {
            LessonPriority.CRITICAL: 2.0,
            LessonPriority.HIGH: 1.5,
            LessonPriority.NORMAL: 1.0,
            LessonPriority.LOW: 0.5,
            LessonPriority.OPTIONAL: 0.25
        }
        
        return base_score * priority_mult.get(self.priority, 1.0) * self.freshness


@dataclass
class SelectedLesson:
    """
    The FINAL output - the chosen lesson after selection.
    Ready to be rendered to the user.
    """
    # From selected candidate
    teaching_mode: TeachingMode
    title: str
    main_insight: str
    
    # Rendered explanation
    explanation: str                # Full explanation text
    why_section: Optional[str] = None  # Optional "Why?" explanation
    next_idea: Optional[str] = None    # "What to think about next"
    
    # Optional components
    socratic_question: Optional[str] = None
    better_move: Optional[str] = None
    better_move_explanation: Optional[str] = None
    
    # For memory/reinforcement
    relates_to_fingerprint: Optional[str] = None  # If relates to known weakness
    is_breakthrough: bool = False    # If they fixed a recurring issue
    
    # For UI
    highlight_squares: List[str] = field(default_factory=list)
    quality_badge: Optional[str] = None  # "Excellent!", "Mistake", etc.
    encouragement: Optional[str] = None
    
    # Metadata
    score: float = 0.0              # Final score that won selection
    candidate_count: int = 1        # How many candidates were evaluated


@dataclass
class MistakeFingerprint:
    """
    User's mistake profile across categories.
    Used to calculate player_relevance score.
    Updated after each analyzed game.
    """
    user_id: str
    
    # Tactical weaknesses: pattern -> {count, last_seen, decay_score}
    tactical: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Strategic weaknesses
    strategic: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Phase weaknesses: "opening", "middlegame", "endgame" -> count
    phase: Dict[str, int] = field(default_factory=dict)
    
    # Behavioral patterns
    behavioral: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Summary stats
    total_mistakes: int = 0
    games_analyzed: int = 0
    last_updated: Optional[str] = None
    
    def get_relevance_score(self, pattern_type: str, category: str) -> float:
        """
        Get how relevant a pattern is to this user.
        Higher = they make this mistake more often.
        
        Uses decay formula: relevance = count * decay_factor
        decay_factor = 0.9 ^ days_since_last
        """
        source = {
            MistakeCategory.TACTICAL.value: self.tactical,
            MistakeCategory.STRATEGIC.value: self.strategic,
            MistakeCategory.BEHAVIORAL.value: self.behavioral
        }.get(category, {})
        
        pattern_data = source.get(pattern_type, {})
        if not pattern_data:
            return 0.0
        
        count = pattern_data.get("count", 0)
        decay_score = pattern_data.get("decay_score", 0.5)
        
        # Normalize to 0-1
        return min(1.0, (count * decay_score) / 10)
    
    def record_mistake(self, pattern_type: str, category: str):
        """Record a new occurrence of this mistake pattern."""
        now = datetime.now(timezone.utc).isoformat()
        
        source = {
            MistakeCategory.TACTICAL.value: self.tactical,
            MistakeCategory.STRATEGIC.value: self.strategic,
            MistakeCategory.BEHAVIORAL.value: self.behavioral
        }.get(category)
        
        if source is None:
            return
        
        if pattern_type not in source:
            source[pattern_type] = {
                "count": 0,
                "last_seen": None,
                "decay_score": 1.0
            }
        
        source[pattern_type]["count"] += 1
        source[pattern_type]["last_seen"] = now
        source[pattern_type]["decay_score"] = 1.0  # Reset decay
        
        self.total_mistakes += 1
        self.last_updated = now


@dataclass
class LessonMemory:
    """
    Short-term memory for anti-spam control.
    Tracks what was recently taught to avoid repetition.
    """
    session_id: str
    
    # Recently taught patterns: pattern_type -> last_taught_move_number
    taught_patterns: Dict[str, int] = field(default_factory=dict)
    
    # Recently taught concepts: concept_name -> count_this_session
    concept_counts: Dict[str, int] = field(default_factory=dict)
    
    # Anti-spam settings
    min_moves_between_same_pattern: int = 5
    max_same_concept_per_session: int = 3
    
    def can_teach(self, pattern_type: str, current_move: int) -> bool:
        """Check if we can teach this pattern (not recently taught)."""
        last_taught = self.taught_patterns.get(pattern_type, -999)
        return (current_move - last_taught) >= self.min_moves_between_same_pattern
    
    def record_taught(self, pattern_type: str, concept_name: str, move_number: int):
        """Record that we taught something."""
        self.taught_patterns[pattern_type] = move_number
        self.concept_counts[concept_name] = self.concept_counts.get(concept_name, 0) + 1
    
    def get_freshness_score(self, pattern_type: str, current_move: int) -> float:
        """Get freshness score (1.0 = fresh, 0.0 = just taught)."""
        last_taught = self.taught_patterns.get(pattern_type, -999)
        moves_since = current_move - last_taught
        
        if moves_since >= self.min_moves_between_same_pattern:
            return 1.0
        
        # Linear decay from 0.5 to 1.0 as we approach min_moves
        return 0.5 + (0.5 * moves_since / self.min_moves_between_same_pattern)
