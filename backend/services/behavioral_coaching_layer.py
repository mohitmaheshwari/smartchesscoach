"""
Behavioral Coaching Layer
==========================

Connects player behavioral diagnosis to explicit coaching advice.

This layer analyzes the player's BehavioralProfile and BlunderTaxonomy
from player_identity and generates specific, actionable coaching based on:

1. Impatient Players (impulse_moves, rushes_in_winning_positions)
2. Hope Chess Players (WINNING_POSITION_COLLAPSE, low post_blunder_accuracy)
3. Lazy Players (high knowledge but inconsistent application)
4. Time Management Issues (under_time_pressure)
5. Tilt Issues (post_blunder_tilt, blunder_spiral)

Philosophy:
- Address ROOT CAUSE, not symptoms
- Give PROCESS, not just advice
- Be SPECIFIC, not generic
- Time coaching to CONTEXT (when it's relevant)

Author: Built for 600-1600 rating players
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PlayerProblemType(str, Enum):
    """Root cause of player's issues"""
    IMPATIENT = "impatient"  # Moves too fast
    HOPE_CHESS = "hope_chess"  # Plays moves hoping opponent misses
    LAZY_CHECKING = "lazy_checking"  # Knows better but doesn't verify
    TIME_MANAGEMENT = "time_management"  # Gets into time trouble
    TILT_PRONE = "tilt_prone"  # Spirals after mistakes
    CALCULATION_WEAK = "calculation_weak"  # Doesn't calculate deep enough
    OPPONENT_BLIND = "opponent_blind"  # Doesn't consider opponent's threats
    NO_ISSUES = "no_issues"  # Doing well!


@dataclass
class BehavioralInsight:
    """A specific behavioral insight with coaching advice"""
    problem_type: PlayerProblemType
    severity: str  # "mild", "moderate", "severe"
    evidence: str  # What data shows this
    coaching_message: str  # What to tell the player
    process_checklist: List[str]  # Steps to fix it
    when_to_coach: str  # "always", "when_winning", "after_blunder", etc.
    priority: int  # 1 = highest priority


@dataclass
class BehavioralCoachingProfile:
    """Complete behavioral coaching profile for a player"""
    primary_issue: Optional[PlayerProblemType]
    all_insights: List[BehavioralInsight]
    custom_checklist: List[Dict]
    coaching_approach: str  # "gentle", "direct", "challenging"


# =============================================================================
# THRESHOLDS FOR DIAGNOSIS
# =============================================================================

# Impatience thresholds
IMPULSE_MOVE_THRESHOLD = 10  # >10 impulse moves = impatient
RUSH_WHEN_WINNING_THRESHOLD = 0.3  # Rushes 30%+ when winning

# Hope chess thresholds
POSITION_COLLAPSE_THRESHOLD = 3  # 3+ collapses from winning
POST_BLUNDER_ACCURACY_THRESHOLD = 0.5  # <50% accuracy after blunder

# Lazy checking thresholds
HANGING_PIECE_THRESHOLD = 5  # 5+ hanging pieces
UNDEFENDED_PIECE_THRESHOLD = 8  # 8+ undefended pieces

# Time management thresholds
TIME_TROUBLE_FREQUENCY_THRESHOLD = 0.25  # 25%+ games end in time trouble
TIME_PRESSURE_BLUNDER_THRESHOLD = 5  # 5+ blunders from time pressure

# Tilt thresholds
BLUNDER_SPIRAL_THRESHOLD = 0.2  # 20%+ games have multiple blunders
TILT_DETECTION_THRESHOLD = 3  # 3+ tilt episodes detected


# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

def diagnose_player_behavior(player_identity: Dict) -> BehavioralCoachingProfile:
    """
    Main diagnostic function.
    
    Analyzes player_identity and returns behavioral coaching profile
    with specific, actionable advice.
    
    Args:
        player_identity: Full player identity from player_identity.py
        
    Returns:
        BehavioralCoachingProfile with insights and coaching
    """
    insights = []
    
    # Extract relevant data
    blunder_tax = player_identity.get("blunder_taxonomy", {})
    behavioral = player_identity.get("behavioral_profile", {})
    games_analyzed = player_identity.get("games_analyzed", 0)
    
    # Need minimum data
    if games_analyzed < 5:
        return BehavioralCoachingProfile(
            primary_issue=None,
            all_insights=[],
            custom_checklist=[],
            coaching_approach="encouraging"
        )
    
    # 1. Check for IMPATIENCE
    impulse_moves = blunder_tax.get("impulse_moves", 0)
    rushes_when_winning = behavioral.get("rushes_in_winning_positions", False)
    
    if impulse_moves > IMPULSE_MOVE_THRESHOLD or rushes_when_winning:
        severity = "severe" if impulse_moves > 20 else "moderate"
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.IMPATIENT,
            severity=severity,
            evidence=f"You've played {impulse_moves} moves with less than 2 seconds of thought",
            coaching_message=(
                "I notice you move very quickly. You see a good square and play immediately. "
                "But you're not checking: 'Is this piece protected THERE?' That's why pieces hang. "
                "It's not that you don't KNOW - you're just not taking time to CHECK."
            ),
            process_checklist=[
                "See a good move? DON'T play it yet",
                "Touch the piece (don't move)",
                "Count slowly: 1-2-3-4-5",
                "Ask: Is it protected THERE?",
                "Ask: What's opponent's best reply?",
                "If both answers are okay → NOW move"
            ],
            when_to_coach="when_moving_quickly",
            priority=1
        ))
    
    # 2. Check for HOPE CHESS
    position_collapses = blunder_tax.get("by_type", {}).get("WINNING_POSITION_COLLAPSE", 0)
    post_blunder_acc = behavioral.get("post_blunder_accuracy", 1.0)
    
    if position_collapses >= POSITION_COLLAPSE_THRESHOLD or post_blunder_acc < POST_BLUNDER_ACCURACY_THRESHOLD:
        severity = "severe" if position_collapses > 5 else "moderate"
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.HOPE_CHESS,
            severity=severity,
            evidence=f"You've collapsed from winning positions {position_collapses} times",
            coaching_message=(
                "You're playing 'hope chess' - making moves and hoping your opponent doesn't see your mistake. "
                "That's not a strategy. ASSUME your opponent sees EVERYTHING. "
                "If your plan only works if they miss something, it's a bad plan."
            ),
            process_checklist=[
                "Before playing a move, ask: 'What am I HOPING they miss?'",
                "If there's something → Assume they WILL see it",
                "Ask: 'If they see it, do I lose material or position?'",
                "If yes → Don't play it, find a safer move",
                "Only play moves that work even if opponent plays perfectly"
            ],
            when_to_coach="when_winning",
            priority=1
        ))
    
    # 3. Check for LAZY CHECKING
    hanging_pieces = blunder_tax.get("by_type", {}).get("HANGING_PIECE", 0)
    undefended_pieces = blunder_tax.get("by_type", {}).get("UNDEFENDED_PIECE", 0)
    consistency = behavioral.get("consistency_score", 0.5)
    
    if (hanging_pieces >= HANGING_PIECE_THRESHOLD or undefended_pieces >= UNDEFENDED_PIECE_THRESHOLD) and consistency > 0.6:
        # High consistency but still hangs pieces = lazy checking, not lack of knowledge
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.LAZY_CHECKING,
            severity="moderate",
            evidence=f"You've hung {hanging_pieces} pieces and left {undefended_pieces} undefended",
            coaching_message=(
                "You KNOW pieces need to be protected - you do it most of the time. "
                "But sometimes you're lazy. You see the good square, you play, you don't CHECK. "
                "This isn't a knowledge problem. It's a discipline problem."
            ),
            process_checklist=[
                "MANDATORY: Before EVERY move, verify:",
                "  1. Is this piece protected? YES / NO",
                "  2. Can opponent take it for free? YES / NO",
                "  3. Did I check opponent's threats? YES / NO",
                "All three = YES? → Move",
                "Any NO? → Think again"
            ],
            when_to_coach="after_hanging_piece",
            priority=2
        ))
    
    # 4. Check for TIME MANAGEMENT issues
    time_trouble_freq = behavioral.get("time_trouble_frequency", 0.0)
    time_pressure_blunders = blunder_tax.get("under_time_pressure", 0)
    
    if time_trouble_freq > TIME_TROUBLE_FREQUENCY_THRESHOLD or time_pressure_blunders > TIME_PRESSURE_BLUNDER_THRESHOLD:
        severity = "severe" if time_trouble_freq > 0.4 else "moderate"
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.TIME_MANAGEMENT,
            severity=severity,
            evidence=f"{int(time_trouble_freq * 100)}% of your games end in time trouble",
            coaching_message=(
                "You're getting into time trouble too often. You think deeply in the opening, "
                "then have no time for the complex middlegame. That's backwards. "
                "Opening moves are mostly known - play them faster. Save time for positions where you NEED to think."
            ),
            process_checklist=[
                "In opening (moves 1-10): Play faster",
                "  - If you know the move → Play in 5 seconds",
                "  - If unsure → Max 15 seconds",
                "In middlegame (moves 11-25): Use saved time",
                "  - Complex position? Take 30-60 seconds",
                "  - Simple position? 10-15 seconds",
                "Check clock after EVERY move",
                "If under 2 minutes → Switch to fast but safe moves"
            ],
            when_to_coach="at_game_start",
            priority=2
        ))
    
    # 5. Check for TILT issues
    blunder_spiral = behavioral.get("blunder_spiral_rate", 0.0)
    tilt_count = behavioral.get("tilt_detected_count", 0)
    
    if blunder_spiral > BLUNDER_SPIRAL_THRESHOLD or tilt_count > TILT_DETECTION_THRESHOLD:
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.TILT_PRONE,
            severity="moderate",
            evidence=f"You've had {tilt_count} tilt episodes, and {int(blunder_spiral*100)}% of games have blunder spirals",
            coaching_message=(
                "After you blunder, you tilt. One mistake becomes two, becomes three. "
                "You need to RESET after a mistake. The blunder already happened - "
                "getting upset doesn't undo it. Take a breath, refocus."
            ),
            process_checklist=[
                "After a blunder:",
                "  1. Take 3 deep breaths",
                "  2. Say: 'That move is gone, next move matters'",
                "  3. Look at the NEW position (forget the past)",
                "  4. Ask: What's the best move NOW?",
                "  5. Play that move carefully",
                "DON'T try to get the piece back immediately",
                "DON'T play fast to 'make up for it'",
                "Play the position, not your emotions"
            ],
            when_to_coach="after_blunder",
            priority=2
        ))
    
    # 6. Check for OPPONENT BLINDNESS
    # Heuristic: If lots of missed_fork, missed_pin but NOT hanging_piece
    missed_tactics = (
        blunder_tax.get("by_type", {}).get("MISSED_FORK", 0) +
        blunder_tax.get("by_type", {}).get("MISSED_PIN", 0) +
        blunder_tax.get("by_type", {}).get("MISSED_SKEWER", 0)
    )
    
    if missed_tactics > 8 and hanging_pieces < 3:
        # Sees their own pieces okay, but doesn't see opponent threats
        insights.append(BehavioralInsight(
            problem_type=PlayerProblemType.OPPONENT_BLIND,
            severity="moderate",
            evidence=f"You've missed {missed_tactics} opponent tactics",
            coaching_message=(
                "You're only thinking about YOUR plan. You're not asking: 'What is my OPPONENT trying to do?' "
                "That's why you miss their forks and pins. You need to think from BOTH sides."
            ),
            process_checklist=[
                "After EVERY opponent move:",
                "  1. Ask: What are they attacking?",
                "  2. Ask: What's their plan?",
                "  3. Ask: What are they HOPING I'll do?",
                "  4. Check: Can they fork/pin/skewer any of my pieces?",
                "  5. THEN plan your move",
                "Think from THEIR perspective, not just yours"
            ],
            when_to_coach="after_opponent_move",
            priority=2
        ))
    
    # Determine primary issue (highest priority + severity)
    primary = None
    if insights:
        insights.sort(key=lambda x: (x.priority, {"severe": 0, "moderate": 1, "mild": 2}[x.severity]))
        primary = insights[0].problem_type
    
    # Determine coaching approach
    approach = "encouraging"  # Default
    if primary == PlayerProblemType.LAZY_CHECKING:
        approach = "direct"  # They know better, be more direct
    elif primary == PlayerProblemType.TILT_PRONE:
        approach = "gentle"  # Psychological issue, be supportive
    
    # Build custom checklist (combine relevant checklists)
    custom_checklist = []
    for insight in insights[:2]:  # Top 2 issues only
        custom_checklist.append({
            "issue": insight.problem_type.value,
            "title": _get_checklist_title(insight.problem_type),
            "steps": insight.process_checklist,
            "when": insight.when_to_coach
        })
    
    return BehavioralCoachingProfile(
        primary_issue=primary,
        all_insights=insights,
        custom_checklist=custom_checklist,
        coaching_approach=approach
    )


def _get_checklist_title(problem_type: PlayerProblemType) -> str:
    """Get friendly title for checklist"""
    titles = {
        PlayerProblemType.IMPATIENT: "Slow Down Protocol",
        PlayerProblemType.HOPE_CHESS: "Stop Hope Chess",
        PlayerProblemType.LAZY_CHECKING: "Piece Safety Verification",
        PlayerProblemType.TIME_MANAGEMENT: "Time Management Plan",
        PlayerProblemType.TILT_PRONE: "Post-Blunder Reset",
        PlayerProblemType.OPPONENT_BLIND: "Opponent Perspective Check",
        PlayerProblemType.CALCULATION_WEAK: "Calculation Discipline",
    }
    return titles.get(problem_type, "Improvement Checklist")


def get_contextual_coaching_message(
    behavioral_profile: BehavioralCoachingProfile,
    context: str,
    game_state: Optional[Dict] = None
) -> Optional[str]:
    """
    Get coaching message appropriate for current context.
    
    Args:
        behavioral_profile: Player's behavioral coaching profile
        context: Current context (e.g., "before_move", "after_blunder", "when_winning")
        game_state: Optional game state info (position, time left, etc.)
        
    Returns:
        Coaching message if appropriate for context, else None
    """
    if not behavioral_profile.all_insights:
        return None
    
    # Find insights relevant to this context
    relevant_insights = [
        insight for insight in behavioral_profile.all_insights
        if _is_context_relevant(insight, context, game_state)
    ]
    
    if not relevant_insights:
        return None
    
    # Return highest priority relevant insight
    return relevant_insights[0].coaching_message


def _is_context_relevant(
    insight: BehavioralInsight,
    context: str,
    game_state: Optional[Dict]
) -> bool:
    """Check if this insight is relevant to current context"""
    
    # Map contexts
    context_map = {
        "when_moving_quickly": ["before_move", "during_game"],
        "when_winning": ["before_move", "during_game"],
        "after_blunder": ["after_move", "post_move_feedback"],
        "after_hanging_piece": ["after_move", "post_move_feedback"],
        "at_game_start": ["game_start"],
        "after_opponent_move": ["after_opponent_move", "before_move"],
        "always": ["before_move", "after_move", "during_game", "game_start"]
    }
    
    when_to_coach = insight.when_to_coach
    valid_contexts = context_map.get(when_to_coach, [])
    
    if context not in valid_contexts:
        return False
    
    # Additional game state checks
    if game_state:
        # Check if winning (for hope chess coaching)
        if when_to_coach == "when_winning":
            eval_score = game_state.get("eval_score", 0)
            if eval_score < 150:  # Not winning enough
                return False
        
        # Check if moving quickly (for impatience coaching)
        if when_to_coach == "when_moving_quickly":
            think_time = game_state.get("last_move_time_ms", 5000)
            if think_time > 3000:  # Took more than 3 seconds
                return False
    
    return True


def generate_progress_narrative(
    old_profile: BehavioralCoachingProfile,
    new_profile: BehavioralCoachingProfile,
    games_since_last: int
) -> str:
    """
    Generate a narrative about behavioral improvement.
    
    Args:
        old_profile: Profile from previous snapshot
        new_profile: Current profile
        games_since_last: Games played since last snapshot
        
    Returns:
        Human-readable progress narrative
    """
    if not old_profile or not old_profile.primary_issue:
        return "Keep playing! I'm learning your patterns."
    
    old_issue = old_profile.primary_issue
    new_issue = new_profile.primary_issue if new_profile else None
    
    # Check if primary issue resolved
    if old_issue and not new_issue:
        return (
            f"🎉 BREAKTHROUGH! You've overcome your {old_issue.value.replace('_', ' ')} issue! "
            f"In your last {games_since_last} games, you've shown much better discipline. "
            f"This is real growth. Keep it up!"
        )
    
    # Check if primary issue changed
    if old_issue and new_issue and old_issue != new_issue:
        return (
            f"Your main challenge has shifted from {old_issue.value.replace('_', ' ')} "
            f"to {new_issue.value.replace('_', ' ')}. This is actually progress - "
            f"you've improved the first issue enough that a different pattern is now more visible. "
            f"Let's work on this new one."
        )
    
    # Same issue persists
    if old_issue and new_issue and old_issue == new_issue:
        # Check severity change
        old_severity = old_profile.all_insights[0].severity if old_profile.all_insights else "moderate"
        new_severity = new_profile.all_insights[0].severity if new_profile.all_insights else "moderate"
        
        if old_severity == "severe" and new_severity == "moderate":
            return (
                f"You're making progress on {old_issue.value.replace('_', ' ')}! "
                f"It's gone from severe to moderate. Not solved yet, but definitely improving. "
                f"Keep following the checklist."
            )
        elif old_severity == new_severity:
            return (
                f"You're still working on {old_issue.value.replace('_', ' ')}. "
                f"It takes time to change habits. Keep using the checklist before EVERY move. "
                f"Consistency is key."
            )
    
    return "Keep working on your consistency. Progress takes time."


# =============================================================================
# SIMPLE API FOR COACHING INTEGRATION
# =============================================================================

def should_show_behavioral_coaching(
    player_identity: Dict,
    context: str,
    game_state: Optional[Dict] = None
) -> Tuple[bool, Optional[str]]:
    """
    Simple function to check if behavioral coaching should be shown.
    
    Args:
        player_identity: Full player identity
        context: Current context
        game_state: Optional game state
        
    Returns:
        (should_show, coaching_message)
    """
    profile = diagnose_player_behavior(player_identity)
    
    if not profile.all_insights:
        return (False, None)
    
    message = get_contextual_coaching_message(profile, context, game_state)
    
    return (message is not None, message)
