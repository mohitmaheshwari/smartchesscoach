"""
Live Behavior Extractor - Step 3

Detects behavioral patterns during gameplay in real-time.
These signals feed into CPR (Step 4) and Identity (Step 5).

Behavioral Signals Detected:
1. IMPULSE_MOVE - Very fast move (<2s) that's a mistake
2. THREAT_IGNORED - Didn't address opponent's immediate threat
3. PANIC_DEFENSE - Rapid defensive moves under pressure
4. RAPID_STREAK - Multiple fast moves in a row (tilt indicator)
5. TIME_PRESSURE_MISTAKE - Error when clock is low
6. CALCULATED_SACRIFICE - Intentional material sacrifice (positive)
7. POSITIONAL_PATIENCE - Taking time for quiet moves (positive)
8. TACTICAL_ALERTNESS - Quick response to tactics (positive)
"""

import chess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone


class BehaviorType(str, Enum):
    """Types of behavioral events"""
    # Negative behaviors (contribute to lower CPR)
    IMPULSE_MOVE = "impulse_move"
    THREAT_IGNORED = "threat_ignored"
    PANIC_DEFENSE = "panic_defense"
    RAPID_STREAK = "rapid_streak"
    TIME_PRESSURE_MISTAKE = "time_pressure_mistake"
    REPEATED_MISTAKE = "repeated_mistake"
    
    # Positive behaviors (contribute to higher CPR)
    CALCULATED_SACRIFICE = "calculated_sacrifice"
    POSITIONAL_PATIENCE = "positional_patience"
    TACTICAL_ALERTNESS = "tactical_alertness"
    THREAT_ADDRESSED = "threat_addressed"
    ACCURATE_UNDER_PRESSURE = "accurate_under_pressure"


class BehaviorSeverity(str, Enum):
    """Severity/impact of behavior"""
    HIGH = "high"       # Major impact on CPR
    MEDIUM = "medium"   # Moderate impact
    LOW = "low"         # Minor impact


@dataclass
class BehaviorEvent:
    """A detected behavioral event during gameplay"""
    behavior_type: BehaviorType
    severity: BehaviorSeverity
    move_number: int
    move_san: str
    fen_before: str
    time_spent: float
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "behavior_type": self.behavior_type.value,
            "severity": self.severity.value,
            "move_number": self.move_number,
            "move_san": self.move_san,
            "fen_before": self.fen_before,
            "time_spent": self.time_spent,
            "description": self.description,
            "details": self.details,
            "timestamp": self.timestamp
        }


# Thresholds for behavior detection
IMPULSE_THRESHOLD_SECONDS = 2.0      # Moves faster than this are "impulse"
RAPID_STREAK_THRESHOLD = 3           # N consecutive fast moves = streak
RAPID_MOVE_THRESHOLD = 3.0           # Threshold for "rapid" in streak
TIME_PRESSURE_THRESHOLD = 60.0       # Under 1 minute = time pressure
PATIENCE_THRESHOLD_SECONDS = 15.0    # Taking >15s on quiet position = patience


class LiveBehaviorExtractor:
    """
    Extracts behavioral patterns from moves in real-time.
    
    Call analyze_move() after each player move to detect behaviors.
    """
    
    def __init__(self):
        self.recent_move_times: List[float] = []  # Last N move times
        self.behavior_events: List[BehaviorEvent] = []
        self.move_count = 0
        self.mistakes_made = 0
        self.threats_faced = 0
        self.threats_addressed = 0
    
    def analyze_move(
        self,
        fen_before: str,
        move_san: str,
        fen_after: str,
        time_spent: float,
        time_remaining: float,
        is_mistake: bool = False,
        is_blunder: bool = False,
        evaluation_change: float = 0.0,
        opponent_had_threat: bool = False
    ) -> List[BehaviorEvent]:
        """
        Analyze a player's move for behavioral patterns.
        
        Args:
            fen_before: Position before move
            move_san: Move played in SAN
            fen_after: Position after move
            time_spent: Seconds spent on this move
            time_remaining: Seconds remaining on clock
            is_mistake: Whether this move is a mistake/inaccuracy
            is_blunder: Whether this is a blunder (severe mistake)
            evaluation_change: Change in evaluation (negative = worse)
            opponent_had_threat: Whether opponent had a threat we needed to address
        
        Returns:
            List of BehaviorEvents detected for this move
        """
        self.move_count += 1
        events = []
        
        # Track move times for streak detection
        self.recent_move_times.append(time_spent)
        if len(self.recent_move_times) > 5:
            self.recent_move_times.pop(0)
        
        # 1. Impulse Move Detection
        if time_spent < IMPULSE_THRESHOLD_SECONDS and (is_mistake or is_blunder):
            severity = BehaviorSeverity.HIGH if is_blunder else BehaviorSeverity.MEDIUM
            events.append(BehaviorEvent(
                behavior_type=BehaviorType.IMPULSE_MOVE,
                severity=severity,
                move_number=self.move_count,
                move_san=move_san,
                fen_before=fen_before,
                time_spent=time_spent,
                description=f"Quick move ({time_spent:.1f}s) led to {'blunder' if is_blunder else 'mistake'}",
                details={
                    "is_blunder": is_blunder,
                    "eval_change": evaluation_change
                }
            ))
            self.mistakes_made += 1
        
        # 2. Threat Ignored Detection
        if opponent_had_threat:
            self.threats_faced += 1
            threat_addressed = self._check_threat_addressed(fen_before, move_san)
            if not threat_addressed and is_mistake:
                events.append(BehaviorEvent(
                    behavior_type=BehaviorType.THREAT_IGNORED,
                    severity=BehaviorSeverity.HIGH,
                    move_number=self.move_count,
                    move_san=move_san,
                    fen_before=fen_before,
                    time_spent=time_spent,
                    description="Opponent's threat was not addressed",
                    details={"eval_change": evaluation_change}
                ))
            elif threat_addressed:
                self.threats_addressed += 1
                events.append(BehaviorEvent(
                    behavior_type=BehaviorType.THREAT_ADDRESSED,
                    severity=BehaviorSeverity.LOW,
                    move_number=self.move_count,
                    move_san=move_san,
                    fen_before=fen_before,
                    time_spent=time_spent,
                    description="Successfully addressed opponent's threat",
                    details={}
                ))
        
        # 3. Rapid Streak Detection (tilt indicator)
        if len(self.recent_move_times) >= RAPID_STREAK_THRESHOLD:
            recent = self.recent_move_times[-RAPID_STREAK_THRESHOLD:]
            if all(t < RAPID_MOVE_THRESHOLD for t in recent):
                # Check if we haven't already flagged this streak
                if not any(e.behavior_type == BehaviorType.RAPID_STREAK 
                          and e.move_number >= self.move_count - 1 
                          for e in self.behavior_events):
                    events.append(BehaviorEvent(
                        behavior_type=BehaviorType.RAPID_STREAK,
                        severity=BehaviorSeverity.MEDIUM,
                        move_number=self.move_count,
                        move_san=move_san,
                        fen_before=fen_before,
                        time_spent=time_spent,
                        description=f"Rapid move streak detected ({RAPID_STREAK_THRESHOLD} fast moves)",
                        details={
                            "streak_times": recent,
                            "avg_time": sum(recent) / len(recent)
                        }
                    ))
        
        # 4. Time Pressure Mistake
        if time_remaining < TIME_PRESSURE_THRESHOLD and (is_mistake or is_blunder):
            events.append(BehaviorEvent(
                behavior_type=BehaviorType.TIME_PRESSURE_MISTAKE,
                severity=BehaviorSeverity.MEDIUM,
                move_number=self.move_count,
                move_san=move_san,
                fen_before=fen_before,
                time_spent=time_spent,
                description=f"Mistake under time pressure ({time_remaining:.0f}s remaining)",
                details={
                    "time_remaining": time_remaining,
                    "is_blunder": is_blunder
                }
            ))
        
        # 5. Accurate Under Pressure (positive)
        if time_remaining < TIME_PRESSURE_THRESHOLD and not is_mistake and not is_blunder:
            if self._is_critical_position(fen_before):
                events.append(BehaviorEvent(
                    behavior_type=BehaviorType.ACCURATE_UNDER_PRESSURE,
                    severity=BehaviorSeverity.MEDIUM,
                    move_number=self.move_count,
                    move_san=move_san,
                    fen_before=fen_before,
                    time_spent=time_spent,
                    description=f"Accurate move under time pressure ({time_remaining:.0f}s)",
                    details={"time_remaining": time_remaining}
                ))
        
        # 6. Positional Patience (positive)
        if time_spent > PATIENCE_THRESHOLD_SECONDS and not is_mistake:
            if self._is_quiet_position(fen_before):
                events.append(BehaviorEvent(
                    behavior_type=BehaviorType.POSITIONAL_PATIENCE,
                    severity=BehaviorSeverity.LOW,
                    move_number=self.move_count,
                    move_san=move_san,
                    fen_before=fen_before,
                    time_spent=time_spent,
                    description=f"Patient thinking ({time_spent:.1f}s) in quiet position",
                    details={}
                ))
        
        # 7. Calculated Sacrifice Detection
        if self._is_sacrifice(fen_before, move_san) and not is_blunder:
            events.append(BehaviorEvent(
                behavior_type=BehaviorType.CALCULATED_SACRIFICE,
                severity=BehaviorSeverity.MEDIUM,
                move_number=self.move_count,
                move_san=move_san,
                fen_before=fen_before,
                time_spent=time_spent,
                description="Material sacrifice played",
                details={"eval_change": evaluation_change}
            ))
        
        # Store events
        self.behavior_events.extend(events)
        
        return events
    
    def _check_threat_addressed(self, fen: str, move_san: str) -> bool:
        """Check if the move addresses an existing threat"""
        try:
            board = chess.Board(fen)
            our_color = board.turn
            
            # Find threatened pieces before move
            threatened_squares = []
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == our_color:
                    if board.is_attacked_by(not our_color, square):
                        threatened_squares.append(square)
            
            if not threatened_squares:
                return True  # No threat to address
            
            # Parse the move
            move = board.parse_san(move_san)
            
            # Did we move a threatened piece?
            if move.from_square in threatened_squares:
                return True
            
            # Did we capture the attacker?
            if board.is_capture(move):
                return True  # Simplified check
            
            # Did we block?
            # (Complex to check, simplified to False for now)
            
            return False
        except Exception:
            return False
    
    def _is_critical_position(self, fen: str) -> bool:
        """Check if position is critical (tactics, threats)"""
        try:
            board = chess.Board(fen)
            # Position is critical if:
            # - King is in check
            # - Multiple pieces are attacked
            # - Few pieces left (endgame)
            
            if board.is_check():
                return True
            
            # Count attacked pieces
            our_color = board.turn
            attacked_count = 0
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == our_color:
                    if board.is_attacked_by(not our_color, square):
                        attacked_count += 1
            
            return attacked_count >= 2
        except Exception:
            return False
    
    def _is_quiet_position(self, fen: str) -> bool:
        """Check if position is quiet (no immediate tactics)"""
        try:
            board = chess.Board(fen)
            
            # Not quiet if in check
            if board.is_check():
                return False
            
            # Not quiet if there are hanging pieces
            our_color = board.turn
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == our_color:
                    if board.is_attacked_by(not our_color, square):
                        if not board.is_attacked_by(our_color, square):
                            return False
            
            return True
        except Exception:
            return True
    
    def _is_sacrifice(self, fen: str, move_san: str) -> bool:
        """Check if move is a material sacrifice"""
        try:
            board = chess.Board(fen)
            move = board.parse_san(move_san)
            
            # Is it a capture where we lose material?
            if not board.is_capture(move):
                return False
            
            captured = board.piece_at(move.to_square)
            moving = board.piece_at(move.from_square)
            
            if not captured or not moving:
                return False
            
            piece_values = {
                chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
            }
            
            captured_value = piece_values.get(captured.piece_type, 0)
            moving_value = piece_values.get(moving.piece_type, 0)
            
            # Sacrifice if we're giving up more than we're taking
            return moving_value > captured_value + 1
        except Exception:
            return False
    
    def get_summary(self) -> Dict:
        """Get summary of all behavioral events"""
        positive_events = [e for e in self.behavior_events 
                         if e.behavior_type in [
                             BehaviorType.CALCULATED_SACRIFICE,
                             BehaviorType.POSITIONAL_PATIENCE,
                             BehaviorType.TACTICAL_ALERTNESS,
                             BehaviorType.THREAT_ADDRESSED,
                             BehaviorType.ACCURATE_UNDER_PRESSURE
                         ]]
        
        negative_events = [e for e in self.behavior_events
                         if e.behavior_type in [
                             BehaviorType.IMPULSE_MOVE,
                             BehaviorType.THREAT_IGNORED,
                             BehaviorType.PANIC_DEFENSE,
                             BehaviorType.RAPID_STREAK,
                             BehaviorType.TIME_PRESSURE_MISTAKE,
                             BehaviorType.REPEATED_MISTAKE
                         ]]
        
        return {
            "total_events": len(self.behavior_events),
            "positive_events": len(positive_events),
            "negative_events": len(negative_events),
            "move_count": self.move_count,
            "threats_faced": self.threats_faced,
            "threats_addressed": self.threats_addressed,
            "threat_response_rate": self.threats_addressed / self.threats_faced if self.threats_faced > 0 else 1.0,
            "events": [e.to_dict() for e in self.behavior_events]
        }


def extract_behaviors_from_move(
    fen_before: str,
    move_san: str,
    fen_after: str,
    time_spent: float,
    time_remaining: float,
    move_quality: str = "accurate",  # "accurate", "inaccuracy", "mistake", "blunder"
    eval_change: float = 0.0,
    session_behavior_history: List[Dict] = None
) -> List[Dict]:
    """
    Convenience function to extract behaviors from a single move.
    
    For use in the move endpoint without maintaining extractor state.
    """
    extractor = LiveBehaviorExtractor()
    
    # Restore history if provided
    if session_behavior_history:
        for event_dict in session_behavior_history:
            extractor.behavior_events.append(BehaviorEvent(
                behavior_type=BehaviorType(event_dict["behavior_type"]),
                severity=BehaviorSeverity(event_dict["severity"]),
                move_number=event_dict["move_number"],
                move_san=event_dict["move_san"],
                fen_before=event_dict["fen_before"],
                time_spent=event_dict["time_spent"],
                description=event_dict["description"],
                details=event_dict.get("details", {}),
                timestamp=event_dict.get("timestamp", "")
            ))
            if event_dict["move_number"] > extractor.move_count:
                extractor.move_count = event_dict["move_number"]
    
    is_mistake = move_quality in ["mistake", "inaccuracy"]
    is_blunder = move_quality == "blunder"
    
    # Detect if opponent had a threat (simplified check)
    opponent_had_threat = _detect_opponent_threat(fen_before)
    
    events = extractor.analyze_move(
        fen_before=fen_before,
        move_san=move_san,
        fen_after=fen_after,
        time_spent=time_spent,
        time_remaining=time_remaining,
        is_mistake=is_mistake,
        is_blunder=is_blunder,
        evaluation_change=eval_change,
        opponent_had_threat=opponent_had_threat
    )
    
    return [e.to_dict() for e in events]


def _detect_opponent_threat(fen: str) -> bool:
    """Detect if opponent has a significant threat in the position"""
    try:
        board = chess.Board(fen)
        our_color = board.turn
        
        # Check for attacked high-value pieces
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == our_color:
                if piece.piece_type in [chess.QUEEN, chess.ROOK]:
                    if board.is_attacked_by(not our_color, square):
                        return True
                # Knight or Bishop attacked and not defended
                if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                    if board.is_attacked_by(not our_color, square):
                        if not board.is_attacked_by(our_color, square):
                            return True
        
        return False
    except Exception:
        return False
