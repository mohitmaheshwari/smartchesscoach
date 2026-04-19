"""
Coach Memory System
===================

Deep memory integration for personalized coaching across games.

Tracks:
1. User's recurring mistakes and patterns
2. Openings learned and mastery levels
3. Endgame knowledge
4. Improvement trends over time
5. Habits (good and bad)
6. Learning goals and progress

Uses this data during coaching to provide personalized feedback.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HabitCategory(str, Enum):
    """Categories of chess habits"""
    OPENING = "opening"
    TACTICS = "tactics"
    POSITIONAL = "positional"
    ENDGAME = "endgame"
    TIME = "time_management"
    PSYCHOLOGY = "psychology"


@dataclass
class UserHabit:
    """A tracked habit (good or bad)"""
    habit_id: str
    name: str
    category: HabitCategory
    is_good: bool  # True = strength, False = weakness
    description: str
    detection_count: int = 0  # How many times detected
    last_detected: Optional[str] = None
    improving: bool = False  # Trend direction
    games_tracked: int = 0


@dataclass
class SkillProgress:
    """
    Track progress for a single skill (opening, trap, pattern, endgame, concept).

    The "learned" rule: a skill is learned when
      - seen >= 5 times
      - correct >= 3 times
      - no failure in the last 2 occurrences

    Outcomes is a rolling list of the last 10 attempts: "correct", "wrong", "seen".
    "seen" = encountered but no pass/fail signal (e.g., opening played casually).
    """
    skill_id: str                      # e.g., "italian_game", "fried_liver_attack"
    skill_type: str                    # "opening", "trap", "pattern", "endgame", "concept"
    seen: int = 0
    correct: int = 0
    wrong: int = 0
    outcomes: List[str] = field(default_factory=list)  # Last 10: "correct"|"wrong"|"seen"
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    learned_at: Optional[str] = None   # When promoted to learned (if ever)

    def is_learned(self) -> bool:
        """Apply the 5/3/no-recent-fail rule."""
        if self.seen < 5:
            return False
        if self.correct < 3:
            return False
        last_two = self.outcomes[-2:] if len(self.outcomes) >= 2 else self.outcomes
        if "wrong" in last_two:
            return False
        return True


@dataclass
class LearningProgress:
    """Track what the user has learned"""
    openings_learned: List[str] = field(default_factory=list)
    traps_learned: List[str] = field(default_factory=list)
    traps_mastered: List[str] = field(default_factory=list)  # Backward compatibility
    endgames_learned: List[str] = field(default_factory=list)
    concepts_mastered: List[str] = field(default_factory=list)
    current_focus: Optional[str] = None
    suggested_next: List[str] = field(default_factory=list)
    # Structured skill tracking — the real seen/correct counts per skill
    skills: List[SkillProgress] = field(default_factory=list)


@dataclass 
class PerformanceTrend:
    """Track performance over time"""
    games_played: int = 0
    avg_accuracy: float = 0.0
    avg_blunders_per_game: float = 0.0
    best_performance_rating: int = 0
    worst_performance_rating: int = 0
    recent_results: List[str] = field(default_factory=list)  # Last 10: "win", "loss", "draw"
    improvement_rate: float = 0.0  # Positive = improving


@dataclass
class CoachMemory:
    """Complete coach memory for a user"""
    user_id: str
    created_at: str
    updated_at: str
    
    # Habits
    weaknesses: List[UserHabit] = field(default_factory=list)
    strengths: List[UserHabit] = field(default_factory=list)
    
    # Learning
    learning: LearningProgress = field(default_factory=LearningProgress)
    
    # Performance
    performance: PerformanceTrend = field(default_factory=PerformanceTrend)
    
    # Session memory
    last_game_insights: List[str] = field(default_factory=list)
    recurring_patterns: List[str] = field(default_factory=list)
    
    # Coaching notes
    coach_notes: List[str] = field(default_factory=list)


# Common weakness patterns to detect
DETECTABLE_WEAKNESSES = {
    "early_queen": {
        "name": "Early Queen Development",
        "category": HabitCategory.OPENING,
        "description": "Moving the queen too early, before developing minor pieces",
        "detection": "Queen moves in first 6 moves"
    },
    "one_move_blunder": {
        "name": "One-Move Blunders",
        "category": HabitCategory.TACTICS,
        "description": "Missing immediate threats or hanging pieces",
        "detection": "Losing material to simple tactics"
    },
    "no_castling": {
        "name": "Delayed Castling",
        "category": HabitCategory.OPENING,
        "description": "Not castling early enough, leaving the king in the center",
        "detection": "King still in center after move 15"
    },
    "pawn_weaknesses": {
        "name": "Creating Pawn Weaknesses",
        "category": HabitCategory.POSITIONAL,
        "description": "Creating isolated, doubled, or backward pawns unnecessarily",
        "detection": "Pawn structure deterioration"
    },
    "time_trouble": {
        "name": "Time Management",
        "category": HabitCategory.TIME,
        "description": "Running low on time and making rushed decisions",
        "detection": "Many moves made with < 30 seconds"
    },
    "overconfidence": {
        "name": "Overconfidence in Winning Positions",
        "category": HabitCategory.PSYCHOLOGY,
        "description": "Making careless moves when ahead, letting opponent back in",
        "detection": "Blunders while significantly ahead"
    },
    "giving_up": {
        "name": "Giving Up Too Easily",
        "category": HabitCategory.PSYCHOLOGY,
        "description": "Resigning or playing carelessly in difficult positions",
        "detection": "Resigning in drawable positions"
    }
}


async def get_or_create_memory(db, user_id: str) -> CoachMemory:
    """Get existing memory or create new one for user."""
    memory_doc = await db.coach_memory.find_one({"user_id": user_id})
    
    if memory_doc:
        # Convert to CoachMemory object
        return _doc_to_memory(memory_doc)
    
    # Create new memory
    now = datetime.now(timezone.utc).isoformat()
    memory = CoachMemory(
        user_id=user_id,
        created_at=now,
        updated_at=now
    )
    
    await db.coach_memory.insert_one(_memory_to_doc(memory))
    return memory


def _doc_to_memory(doc: Dict) -> CoachMemory:
    """Convert MongoDB document to CoachMemory object."""
    weaknesses = [
        UserHabit(**w) for w in doc.get("weaknesses", [])
    ]
    strengths = [
        UserHabit(**s) for s in doc.get("strengths", [])
    ]
    # Deserialize skills list separately (it's a list of dicts in MongoDB)
    learning_doc = dict(doc.get("learning", {}) or {})
    skills_raw = learning_doc.pop("skills", [])
    # Filter to only fields LearningProgress knows about (forward-compat safety)
    import dataclasses as _dc
    valid_fields = {f.name for f in _dc.fields(LearningProgress)}
    learning_doc = {k: v for k, v in learning_doc.items() if k in valid_fields}
    learning = LearningProgress(**learning_doc)
    learning.skills = [SkillProgress(**s) for s in skills_raw if isinstance(s, dict)]
    performance = PerformanceTrend(**doc.get("performance", {}))
    
    return CoachMemory(
        user_id=doc["user_id"],
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        weaknesses=weaknesses,
        strengths=strengths,
        learning=learning,
        performance=performance,
        last_game_insights=doc.get("last_game_insights", []),
        recurring_patterns=doc.get("recurring_patterns", []),
        coach_notes=doc.get("coach_notes", [])
    )


def _memory_to_doc(memory: CoachMemory) -> Dict:
    """Convert CoachMemory object to MongoDB document."""
    return {
        "user_id": memory.user_id,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "weaknesses": [asdict(w) for w in memory.weaknesses],
        "strengths": [asdict(s) for s in memory.strengths],
        "learning": asdict(memory.learning),
        "performance": asdict(memory.performance),
        "last_game_insights": memory.last_game_insights,
        "recurring_patterns": memory.recurring_patterns,
        "coach_notes": memory.coach_notes
    }


async def update_memory_after_game(
    db,
    user_id: str,
    game_result: str,
    accuracy: float,
    blunders: int,
    mistakes: int,
    habits_violated: List[str],
    habits_improved: List[str],
    opening_played: Optional[str],
    endgame_reached: bool,
    performance_rating: int,
    loss_phase: Optional[str] = None,  # "opening", "middlegame", "endgame" - where the game was lost
    coach_prescription: Optional[str] = None,  # The ONE thing to work on next
    prescription_type: Optional[str] = None,  # "habit", "endgame_lesson", "pattern_drill"
    mistake_types: Optional[List[str]] = None,  # Engine 2: list of MistakeType.value strings from this game
    was_winning: bool = False,  # Engine 2: did the user have a winning position at some point?
) -> CoachMemory:
    """
    Update coach memory after a game.
    
    This is the key function that builds the coach's knowledge of the player.
    """
    memory = await get_or_create_memory(db, user_id)
    now = datetime.now(timezone.utc).isoformat()
    
    # Update performance trends
    memory.performance.games_played += 1
    
    # Update rolling average accuracy
    old_avg = memory.performance.avg_accuracy
    n = memory.performance.games_played
    memory.performance.avg_accuracy = ((old_avg * (n-1)) + accuracy) / n
    
    # Update blunders per game
    old_blunders = memory.performance.avg_blunders_per_game
    memory.performance.avg_blunders_per_game = ((old_blunders * (n-1)) + blunders) / n
    
    # Track best/worst performance
    if performance_rating > memory.performance.best_performance_rating:
        memory.performance.best_performance_rating = performance_rating
    if memory.performance.worst_performance_rating == 0 or performance_rating < memory.performance.worst_performance_rating:
        memory.performance.worst_performance_rating = performance_rating
    
    # Update recent results (keep last 10)
    memory.performance.recent_results.append(game_result)
    memory.performance.recent_results = memory.performance.recent_results[-10:]
    
    # Calculate improvement rate (wins - losses in last 10 games)
    recent = memory.performance.recent_results
    wins = recent.count("win")
    losses = recent.count("loss")
    memory.performance.improvement_rate = (wins - losses) / max(len(recent), 1)
    
    # Update weaknesses
    for habit_id in habits_violated:
        _update_weakness(memory, habit_id, now, violated=True)
    
    for habit_id in habits_improved:
        _update_weakness(memory, habit_id, now, violated=False)
    
    # Track opening skill progress
    # "Correct" if game won or drew with decent accuracy; "wrong" if blundered hard;
    # "seen" otherwise (just played it). Promotion to openings_learned happens
    # automatically when 5 seen / 3 correct / no recent failure is met.
    if opening_played:
        if game_result == "win" and accuracy >= 70 and blunders == 0:
            skill_outcome = "correct"
        elif game_result == "loss" and blunders >= 2:
            skill_outcome = "wrong"
        else:
            skill_outcome = "seen"
        record_skill_attempt(memory, opening_played, "opening", skill_outcome, now)
    
    # Track loss phase for this opening (helps identify WHERE user struggles)
    if opening_played and game_result == "loss" and loss_phase:
        try:
            # Update opening-specific loss phase stats
            await db.user_opening_progress.update_one(
                {"user_id": user_id, "opening_name": opening_played},
                {
                    "$inc": {f"loss_phases.{loss_phase}": 1, "total_losses": 1},
                    "$set": {"last_loss_phase": loss_phase, "updated_at": now}
                },
                upsert=True
            )
            logger.info(f"Tracked loss in {loss_phase} phase for {opening_played}")
        except Exception as e:
            logger.warning(f"Failed to track loss phase: {e}")
    
    # Generate insights from this game
    insights = _generate_game_insights(
        game_result, accuracy, blunders, habits_violated, habits_improved, memory
    )
    memory.last_game_insights = insights

    # Check for recurring patterns
    _detect_recurring_patterns(memory)

    # === ENGINE 2: record skill attempts across the 12-skill tree ===
    # Without this, tier-1 skills never accrue stats, Engine 2 cycles forever.
    try:
        record_engine2_skills_from_game(
            memory=memory,
            user_rating=performance_rating or 1000,
            mistake_types=mistake_types or [],
            blunders=blunders or 0,
            accuracy=accuracy or 0.0,
            game_result=game_result,
            was_winning=was_winning,
            endgame_reached=endgame_reached,
            timestamp=now,
        )
    except Exception as e:
        logger.debug(f"[ENGINE2] skill-attempt recording failed (non-fatal): {e}")

    # === CURRICULUM BRAIN: Store the coach's prescription ===
    if coach_prescription:
        old_focus = memory.learning.current_focus
        memory.learning.current_focus = coach_prescription
        # If focus changed, track the old one as "suggested_next" for later
        if old_focus and old_focus != coach_prescription:
            if old_focus not in memory.learning.suggested_next:
                memory.learning.suggested_next.append(old_focus)
            # Keep only last 5 suggestions
            memory.learning.suggested_next = memory.learning.suggested_next[-5:]
        logger.info(f"[CURRICULUM] User {user_id}: focus set to '{coach_prescription}' (was '{old_focus}')")

    memory.updated_at = now

    # Save to database
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": _memory_to_doc(memory)},
        upsert=True
    )

    # Bust the Lab/Home coaching cache so screens reflect the new focus
    # immediately (instead of waiting up to 5 minutes for TTL expiry).
    if coach_prescription:
        try:
            await db.coaching_cache.delete_one({"user_id": user_id})
        except Exception:
            pass

        # Sync sibling focus systems so every surface agrees:
        #   - users.focus (focus_engine cluster → HomePage focusPlan card)
        #   - user_streaks.current_focus_mistake (PlateauBreakerDashboard streak)
        try:
            from services.focus_engine import sync_focus_with_brain
            await sync_focus_with_brain(db, user_id, coach_prescription)
        except Exception as e:
            logger.debug(f"[CURRICULUM] focus_engine sync failed (non-fatal): {e}")
        try:
            from services.mistake_streak_service import sync_streak_focus_with_brain
            await sync_streak_focus_with_brain(db, user_id, coach_prescription)
        except Exception as e:
            logger.debug(f"[CURRICULUM] streak sync failed (non-fatal): {e}")

    return memory


def record_skill_attempt(
    memory: CoachMemory,
    skill_id: str,
    skill_type: str,
    outcome: str,  # "correct", "wrong", or "seen"
    timestamp: Optional[str] = None,
) -> SkillProgress:
    """
    Record one attempt at a skill. Applies the learned rule:
      seen >= 5, correct >= 3, no failure in last 2 outcomes.

    When a skill crosses the threshold, it gets promoted to the appropriate
    learned list (openings_learned / traps_learned / endgames_learned /
    concepts_mastered) based on skill_type.
    """
    if outcome not in ("correct", "wrong", "seen"):
        outcome = "seen"

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    # Find or create the skill
    skill = next((s for s in memory.learning.skills
                  if s.skill_id == skill_id and s.skill_type == skill_type), None)
    if skill is None:
        skill = SkillProgress(
            skill_id=skill_id,
            skill_type=skill_type,
            first_seen=timestamp,
        )
        memory.learning.skills.append(skill)

    # Record the attempt
    skill.seen += 1
    skill.last_seen = timestamp
    if outcome == "correct":
        skill.correct += 1
    elif outcome == "wrong":
        skill.wrong += 1
    skill.outcomes.append(outcome)
    # Keep only last 10 outcomes for the rule check
    skill.outcomes = skill.outcomes[-10:]

    # Promotion / demotion check — apply the 5/3/no-recent-fail rule.
    # "Learned" is not a badge — it's the current state of demonstrated
    # competence. If the user backslides (2+ wrongs in the last 2 outcomes)
    # we demote them back to learning so Engine 2 teaches it again.
    was_learned = skill.learned_at is not None
    currently_learned = skill.is_learned()

    target_list = {
        "opening": memory.learning.openings_learned,
        "trap": memory.learning.traps_learned,
        "endgame": memory.learning.endgames_learned,
        "concept": memory.learning.concepts_mastered,
        "pattern": memory.learning.concepts_mastered,
    }.get(skill_type)

    if currently_learned and not was_learned:
        # Promote
        skill.learned_at = timestamp
        if target_list is not None and skill_id not in target_list:
            target_list.append(skill_id)
            logger.info(f"[SKILL] {skill_id} ({skill_type}) LEARNED — "
                       f"seen={skill.seen} correct={skill.correct}")
    elif was_learned and not currently_learned:
        # Demote — user was performing it, now they're not
        skill.learned_at = None
        if target_list is not None and skill_id in target_list:
            target_list.remove(skill_id)
            logger.info(f"[SKILL] {skill_id} ({skill_type}) DEMOTED — "
                       f"user backslid, re-teaching required")

    return skill


def record_engine2_skills_from_game(
    memory: CoachMemory,
    user_rating: int,
    mistake_types: List[str],
    blunders: int,
    accuracy: float,
    game_result: str,
    was_winning: bool,
    endgame_reached: bool,
    timestamp: Optional[str] = None,
) -> List[str]:
    """
    Turn one completed game into skill-attempt outcomes — but ONLY for
    skills whose opportunity actually occurred in this game. If there's
    no evidence the skill was tested, we skip it entirely (no seen++).

    This matters: a quiet positional game where no forks were available
    does NOT count as "demonstrated fork knowledge." Otherwise 5 such
    games would graduate the user out of a skill they never proved.

    Opportunity signals come from the classifier's positive + negative
    events (MistakeType enum): WALKED_INTO_FORK / AVOIDED_FORK / etc.

    mistake_types: list of MistakeType.value strings found this game.
    Returns list of skill_ids that received an attempt.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    mset = set(mistake_types or [])
    recorded = []

    SKILL_RANGES = {
        "pre_move_check":    (400, 1400),
        "hanging_piece":     (500, 1500),
        "opponent_threat":   (600, 1500),
        "king_safety":       (500, 1500),
        "simple_mates":      (600, 1200),
        "free_piece_capture": (500, 1300),
        "basic_trade":       (700, 1400),
        "fork":              (800, 1600),
        "pin":               (900, 1700),
        "conversion":        (1000, 1800),
        "king_pawn_endgame": (900, 1600),
        "opening_principles": (700, 1500),
    }

    def _rec(skill_id: str, outcome: str):
        rmin, rmax = SKILL_RANGES.get(skill_id, (0, 9999))
        if not (rmin <= user_rating <= rmax):
            return
        record_skill_attempt(memory, skill_id, "concept", outcome, timestamp)
        recorded.append(skill_id)

    # ── pre_move_check ── meta-skill: every game is a test. Blunder = failed
    # the habit, clean = passed it. This is the one skill where absence of
    # an explicit opportunity still counts (the habit applies every move).
    _rec("pre_move_check", "wrong" if blunders > 0 else "correct")

    # ── hanging_piece ── opportunity = user actually had material at risk.
    # Evidence: either they hung one (wrong) or avoided a threat (correct).
    # No event → can't prove they know how to keep pieces safe → skip.
    hanging_wrong = {"hanging_piece", "material_blunder", "ignored_threat"}
    hanging_right = {"avoided_threat"}
    if mset & hanging_wrong:
        _rec("hanging_piece", "wrong")
    elif mset & hanging_right:
        _rec("hanging_piece", "correct")
    # else: skip

    # ── opponent_threat ── opportunity = opponent actually made a threat.
    threat_wrong = {"ignored_threat", "missed_winning_tactic"}
    threat_right = {"avoided_threat"}
    if mset & threat_wrong:
        _rec("opponent_threat", "wrong")
    elif mset & threat_right:
        _rec("opponent_threat", "correct")
    # else: skip (no threat occurred)

    # ── king_safety ── opportunity = king came under fire OR user
    # demonstrated threat handling (a superset skill).
    #   - king_safety_error → wrong (direct failure)
    #   - avoided_threat    → correct (threat handling generalises to king safety)
    # No events → skip.
    if "king_safety_error" in mset:
        _rec("king_safety", "wrong")
    elif "avoided_threat" in mset:
        _rec("king_safety", "correct")

    # ── simple_mates ── only in K+Q/K+R endgames. Endgame reached + result.
    # (Without ability to detect specific material, endgame_reached is
    # the best proxy we have.)
    if endgame_reached:
        if game_result == "win":
            _rec("simple_mates", "correct")
        elif was_winning and game_result != "win":
            _rec("simple_mates", "wrong")
        # else: can't tell — skip

    # ── free_piece_capture ── opportunity = free material on the board.
    # Positive proxy: executed_fork/pin/skewer all win material by force,
    # so they count as demonstrating "I take what's free."
    fpc_wrong = {"missed_winning_tactic"}
    fpc_right = {"executed_fork", "executed_pin", "executed_skewer",
                 "executed_discovered_attack"}
    if mset & fpc_wrong:
        _rec("free_piece_capture", "wrong")
    elif mset & fpc_right:
        _rec("free_piece_capture", "correct")
    # else: skip (no free-material event this game)

    # ── basic_trade ── no reliable deterministic detector. Skip entirely
    # rather than giving false "seen" credit. Can be added when we have
    # trade-quality analysis.

    # ── fork ── classifier emits both positive AND negative signals.
    fork_wrong = {"walked_into_fork", "missed_fork"}
    fork_right = {"executed_fork", "avoided_fork"}
    if mset & fork_wrong:
        _rec("fork", "wrong")
    elif mset & fork_right:
        _rec("fork", "correct")
    # else: no fork opportunity this game → skip

    # ── pin (includes skewer, which shares the same recognition pattern) ──
    pin_wrong = {"walked_into_pin", "missed_pin", "walked_into_skewer", "missed_skewer"}
    pin_right = {"executed_pin", "executed_skewer", "avoided_pin", "avoided_skewer"}
    if mset & pin_wrong:
        _rec("pin", "wrong")
    elif mset & pin_right:
        _rec("pin", "correct")
    # else: skip

    # ── conversion ── opportunity = user actually held a winning position.
    if was_winning:
        _rec("conversion", "correct" if game_result == "win" else "wrong")
    elif {"failed_conversion", "blunder_when_ahead"} & mset:
        _rec("conversion", "wrong")
    # else: no winning position held → can't test conversion → skip

    # ── king_pawn_endgame ── endgame reached with a clear result.
    if endgame_reached:
        if game_result == "win":
            _rec("king_pawn_endgame", "correct")
        elif was_winning and game_result != "win":
            _rec("king_pawn_endgame", "wrong")
        elif game_result == "loss":
            _rec("king_pawn_endgame", "wrong")
        # draws from equal positions: can't tell → skip

    # ── opening_principles ── every game has an opening. Use accuracy
    # as the signal. (Overall accuracy is a rough proxy for opening
    # play; when we get phase-split accuracy, swap to opening-phase only.)
    if accuracy:
        if accuracy >= 70 and blunders == 0:
            _rec("opening_principles", "correct")
        elif accuracy < 55:
            _rec("opening_principles", "wrong")
        # mid-range: not clear evidence either way → skip

    return recorded


def _update_weakness(memory: CoachMemory, habit_id: str, timestamp: str, violated: bool):
    """Update a weakness in memory."""
    # Find existing weakness
    existing = None
    for i, w in enumerate(memory.weaknesses):
        if w.habit_id == habit_id:
            existing = (i, w)
            break
    
    if violated:
        if existing:
            _, weakness = existing
            weakness.detection_count += 1
            weakness.last_detected = timestamp
            weakness.games_tracked += 1
            weakness.improving = False
        else:
            # Add new weakness
            weakness_info = DETECTABLE_WEAKNESSES.get(habit_id, {})
            new_weakness = UserHabit(
                habit_id=habit_id,
                name=weakness_info.get("name", habit_id),
                category=weakness_info.get("category", HabitCategory.TACTICS),
                is_good=False,
                description=weakness_info.get("description", ""),
                detection_count=1,
                last_detected=timestamp,
                games_tracked=1
            )
            memory.weaknesses.append(new_weakness)
    else:
        # Habit improved - mark as improving
        if existing:
            idx, weakness = existing
            weakness.games_tracked += 1
            weakness.improving = True
            
            # If improved 3+ times, might be becoming a strength
            # For now, just track improvement


def _generate_game_insights(
    result: str,
    accuracy: float,
    blunders: int,
    violated: List[str],
    improved: List[str],
    memory: CoachMemory
) -> List[str]:
    """Generate insights about this game based on memory."""
    insights = []
    
    # Compare to average
    if accuracy > memory.performance.avg_accuracy + 5:
        insights.append(f"Your accuracy ({accuracy:.1f}%) was above your average ({memory.performance.avg_accuracy:.1f}%)! Great focus!")
    elif accuracy < memory.performance.avg_accuracy - 10:
        insights.append("Your accuracy was below your usual level. What happened?")
    
    # Blunder comparison
    if blunders == 0 and memory.performance.avg_blunders_per_game > 0.5:
        insights.append("Zero blunders! You're usually at {:.1f} per game - excellent discipline!".format(
            memory.performance.avg_blunders_per_game
        ))
    elif blunders > memory.performance.avg_blunders_per_game + 1:
        insights.append(f"More blunders than usual ({blunders} vs your avg {memory.performance.avg_blunders_per_game:.1f})")
    
    # Habit insights
    for habit_id in improved:
        habit_info = DETECTABLE_WEAKNESSES.get(habit_id, {})
        insights.append(f"You avoided {habit_info.get('name', habit_id)} this game! That's improvement!")
    
    # Recurring issues
    for habit_id in violated:
        habit_info = DETECTABLE_WEAKNESSES.get(habit_id, {})
        # Check if this is a recurring issue
        for w in memory.weaknesses:
            if w.habit_id == habit_id and w.detection_count >= 3:
                insights.append(f"'{w.name}' appeared again ({w.detection_count} times now). Let's focus on this!")
                break
    
    return insights[:4]  # Max 4 insights


def _detect_recurring_patterns(memory: CoachMemory):
    """Detect patterns across multiple games."""
    patterns = []
    
    # Check for recurring weaknesses (3+ times)
    for w in memory.weaknesses:
        if w.detection_count >= 3:
            patterns.append(f"Recurring: {w.name} ({w.detection_count} times)")
    
    # Check win/loss streaks
    recent = memory.performance.recent_results
    if len(recent) >= 3:
        if recent[-3:] == ["win", "win", "win"]:
            patterns.append("On a 3-game winning streak!")
        elif recent[-3:] == ["loss", "loss", "loss"]:
            patterns.append("3 losses in a row - time to refocus")
    
    memory.recurring_patterns = patterns[:5]


async def get_coaching_context(db, user_id: str) -> Dict:
    """
    Get coaching context from memory for use in live coaching.
    
    This should be called at the start of each game and used
    to personalize the coaching messages.
    """
    memory = await get_or_create_memory(db, user_id)
    
    # Get REAL opening mastery from user_opening_progress
    opening_progress = await db.user_opening_progress.find({
        "user_id": user_id,
        "mastery_level": {"$in": ["practiced", "mastered", "comfortable"]}
    }).to_list(10)
    
    real_openings_known = [p.get("opening_name") for p in opening_progress if p.get("opening_name")]
    
    # Get REAL trap statistics
    trap_stats = await db.user_trap_stats.find_one({"user_id": user_id})
    real_traps_known = []
    if trap_stats:
        for trap_key, stats in trap_stats.get("traps", {}).items():
            if stats.get("success_rate", 0) >= 70:  # Mastered = 70%+ success rate
                real_traps_known.append(trap_key.replace("_", " ").title())
    
    # Build context for the coach
    context = {
        "games_played": memory.performance.games_played,
        "avg_accuracy": memory.performance.avg_accuracy,
        "avg_blunders": memory.performance.avg_blunders_per_game,
        "improving": memory.performance.improvement_rate > 0,
        "improvement_rate": memory.performance.improvement_rate,
        
        # Top weaknesses to watch for
        "watch_for": [
            {"name": w.name, "count": w.detection_count, "improving": w.improving}
            for w in sorted(memory.weaknesses, key=lambda x: x.detection_count, reverse=True)[:3]
        ],
        
        # What they've ACTUALLY learned (from real progress data)
        "openings_known": real_openings_known[:5],
        "traps_known": real_traps_known[:3],
        "endgames_known": memory.learning.endgames_learned[:3],
        
        # Recent insights
        "last_game_insights": memory.last_game_insights,
        "recurring_patterns": memory.recurring_patterns,
        
        # Personalized messages
        "greeting_context": _get_greeting_context(memory),
        "focus_suggestion": _get_focus_suggestion(memory)
    }
    
    return context


def _get_greeting_context(memory: CoachMemory) -> str:
    """Get context for personalized greeting."""
    if memory.performance.games_played == 0:
        return "first_game"
    
    recent = memory.performance.recent_results
    if len(recent) >= 1:
        if recent[-1] == "win":
            return "after_win"
        elif recent[-1] == "loss":
            return "after_loss"
    
    if memory.performance.improvement_rate > 0.3:
        return "improving"
    elif memory.performance.improvement_rate < -0.3:
        return "struggling"
    
    return "normal"


def _get_focus_suggestion(memory: CoachMemory) -> Optional[str]:
    """Get what to focus on this game based on history."""
    # Find most problematic weakness
    if memory.weaknesses:
        worst = max(memory.weaknesses, key=lambda w: w.detection_count)
        if worst.detection_count >= 2:
            return f"Focus on avoiding {worst.name} today"
    
    # Suggest learning something new
    if len(memory.learning.openings_learned) < 3:
        return "Let's explore a new opening today"
    
    if len(memory.learning.endgames_learned) < 2:
        return "We should work on endgame technique"
    
    return None


async def get_personalized_greeting(db, user_id: str) -> str:
    """Generate a personalized greeting based on memory."""
    memory = await get_or_create_memory(db, user_id)
    
    # Refresh patterns before generating greeting
    _detect_recurring_patterns(memory)
    
    context = _get_greeting_context(memory)
    
    greetings = {
        "first_game": "Welcome! I'm your chess coach. Let's see what you've got!",
        "after_win": "Welcome back! Great win last time. Ready to keep the momentum?",
        "after_loss": "Good to see you again! Last game was tough, but every game teaches us something. Let's go!",
        "improving": f"You're on fire! {memory.performance.improvement_rate*100:.0f}% win rate recently. Let's keep it up!",
        "struggling": "Hey! I know it's been tough lately, but I'm here to help you improve. Let's focus today.",
        "normal": f"Welcome back! Game #{memory.performance.games_played + 1}. Ready to improve?"
    }
    
    return greetings.get(context, greetings["normal"])


async def get_realtime_pattern_context(
    db, 
    user_id: str, 
    mistake_type: str,
    position_type: str = ""
) -> Dict[str, Any]:
    """
    Get pattern context for real-time coaching during a game.
    
    Returns info about:
    - How often user makes this type of mistake
    - Recent games where similar mistake happened
    - Personalized advice based on history
    """
    memory = await get_or_create_memory(db, user_id)
    
    result = {
        "is_recurring": False,
        "occurrence_count": 0,
        "last_occurrence": None,
        "pattern_message": None,
        "memory_reference": None,
        "improvement_note": None
    }
    
    # Map mistake types to habit IDs
    mistake_to_habit = {
        "hanging_piece": "one_move_blunder",
        "missed_tactic": "one_move_blunder",
        "tactical_miss": "one_move_blunder",
        "early_queen": "early_queen",
        "king_safety": "no_castling",
        "pawn_weakness": "pawn_weaknesses",
        "time_trouble": "time_trouble",
        "overconfidence": "overconfidence"
    }
    
    habit_id = mistake_to_habit.get(mistake_type)
    
    if habit_id:
        # Check if this is a known weakness
        for weakness in memory.weaknesses:
            if weakness.habit_id == habit_id:
                result["is_recurring"] = True
                result["occurrence_count"] = weakness.detection_count
                result["last_occurrence"] = weakness.last_detected
                
                # Generate pattern message
                if weakness.detection_count >= 3:
                    result["pattern_message"] = (
                        f"This is the {weakness.detection_count}th time with {weakness.name}. "
                        f"We need to work on this na?"
                    )
                elif weakness.detection_count == 2:
                    result["pattern_message"] = (
                        f"This {weakness.name} happened last game too. Let's fix it!"
                    )
                
                # Check if improving
                if weakness.improving:
                    result["improvement_note"] = (
                        f"But I've noticed you're getting better at {weakness.name}. Keep it up!"
                    )
                break
    
    # Get recent game reference if available
    try:
        if db:
            # Find recent game with similar issue
            recent_game = await db.games.find_one(
                {
                    "user_id": user_id,
                    f"analysis.issues.{mistake_type}": {"$exists": True}
                },
                sort=[("created_at", -1)]
            )
            
            if recent_game:
                game_date = recent_game.get("created_at", "")
                if game_date:
                    # Format date nicely
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
                        days_ago = (datetime.now(timezone.utc) - dt).days
                        if days_ago == 0:
                            date_str = "earlier today"
                        elif days_ago == 1:
                            date_str = "yesterday"
                        elif days_ago < 7:
                            date_str = f"{days_ago} days ago"
                        else:
                            date_str = dt.strftime("%B %d")
                        
                        opponent = recent_game.get("opponent_name", "your opponent")
                        result["memory_reference"] = (
                            f"Remember your game against {opponent} {date_str}? "
                            f"Similar thing happened there."
                        )
                    except:
                        pass
    except Exception as e:
        logger.warning(f"Error getting game reference: {e}")
    
    return result


async def record_in_game_mistake(
    db,
    user_id: str,
    mistake_type: str,
    move_number: int,
    position_fen: str = ""
):
    """
    Record a mistake that happened during a live game.
    This helps build the user's pattern profile in real-time.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        
        await db.in_game_mistakes.insert_one({
            "user_id": user_id,
            "mistake_type": mistake_type,
            "move_number": move_number,
            "position_fen": position_fen,
            "created_at": now
        })
        
        # Update weakness count in memory
        memory = await get_or_create_memory(db, user_id)
        
        # Map to habit
        mistake_to_habit = {
            "hanging_piece": "one_move_blunder",
            "missed_tactic": "one_move_blunder",
            "early_queen": "early_queen",
            "king_safety": "no_castling"
        }
        
        habit_id = mistake_to_habit.get(mistake_type)
        if habit_id:
            _update_weakness(memory, habit_id, now, violated=True)
            
            await db.coach_memory.update_one(
                {"user_id": user_id},
                {"$set": _memory_to_doc(memory)},
                upsert=True
            )
    except Exception as e:
        logger.warning(f"Error recording in-game mistake: {e}")




async def get_user_rating_from_games(db, user_id: str) -> Dict:
    """
    Get user's actual rating from their synced games (Lichess/Chess.com).
    
    Returns:
        Dict with:
        - rating: int (average of recent games for stability)
        - source: str (where rating came from)
        - games_analyzed: int
        - rating_trend: str (improving/stable/declining)
    """
    import re
    
    games_with_dates = []
    sources = set()
    
    # Check games collection for PGN-embedded ratings
    async for game in db.games.find(
        {'user_id': user_id},
        {'pgn': 1, 'user_color': 1, 'platform': 1}
    ).limit(200):  # Get more games to find the most recent by game date
        pgn = game.get('pgn', '')
        user_color = game.get('user_color', '')
        platform = game.get('platform', 'unknown')
        
        # Extract ratings and date from PGN headers
        white_elo = re.search(r'\[WhiteElo "(\d+)"\]', pgn)
        black_elo = re.search(r'\[BlackElo "(\d+)"\]', pgn)
        utc_date = re.search(r'\[UTCDate "(\d{4}\.\d{2}\.\d{2})"\]', pgn)
        utc_time = re.search(r'\[UTCTime "(\d{2}:\d{2}:\d{2})"\]', pgn)
        
        if white_elo and black_elo and utc_date:
            if user_color == 'white':
                rating = int(white_elo.group(1))
            elif user_color == 'black':
                rating = int(black_elo.group(1))
            else:
                continue
            
            # Create sortable datetime string
            game_datetime = utc_date.group(1).replace('.', '-')
            if utc_time:
                game_datetime += ' ' + utc_time.group(1)
            
            games_with_dates.append({
                'rating': rating,
                'datetime': game_datetime,
                'platform': platform
            })
            sources.add(platform)
    
    if not games_with_dates:
        # Fallback: check player_profiles for linked accounts
        profile = await db.player_profiles.find_one({'user_id': user_id})
        if profile:
            if profile.get('lichess_rating'):
                return {
                    'rating': profile['lichess_rating'],
                    'source': 'lichess_profile',
                    'games_analyzed': 0,
                    'rating_trend': 'unknown'
                }
            if profile.get('chesscom_rating'):
                return {
                    'rating': profile['chesscom_rating'],
                    'source': 'chesscom_profile',
                    'games_analyzed': 0,
                    'rating_trend': 'unknown'
                }
        
        # No rating data found
        return {
            'rating': 1200,  # Default
            'source': 'default',
            'games_analyzed': 0,
            'rating_trend': 'unknown'
        }
    
    # Sort by actual game date (most recent first)
    games_with_dates.sort(key=lambda x: x['datetime'], reverse=True)
    
    # Get ratings sorted by date
    ratings = [g['rating'] for g in games_with_dates]
    
    # Use average of last 10 games for stable rating (not just most recent)
    recent_ratings = ratings[:10]
    current_rating = int(sum(recent_ratings) / len(recent_ratings))
    
    # Calculate trend from recent vs older games
    if len(ratings) >= 20:
        recent_avg = sum(ratings[:10]) / 10
        older_avg = sum(ratings[10:20]) / 10
        
        if recent_avg > older_avg + 20:
            trend = 'improving'
        elif recent_avg < older_avg - 20:
            trend = 'declining'
        else:
            trend = 'stable'
    else:
        trend = 'unknown'
    
    return {
        'rating': current_rating,
        'source': ', '.join(sources) if sources else 'synced_games',
        'games_analyzed': len(ratings),
        'rating_trend': trend,
        'avg_rating': int(sum(ratings) / len(ratings)),
        'highest_rating': max(ratings),
        'lowest_rating': min(ratings),
        'most_recent_rating': ratings[0] if ratings else current_rating
    }
