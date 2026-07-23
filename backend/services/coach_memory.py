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
    Track progress for a single skill. Graduation rule is KIND-AWARE —
    knowledge concepts (an endgame rule, a mate pattern, a defence idea)
    graduate on first correct application, while exposure-based skills
    (openings, habits) need repeated proof.

    Outcomes is a rolling list of the last 10 attempts: "correct", "wrong", "seen".
    "seen" = encountered but no pass/fail signal (e.g., opening played casually).

    Rules per kind:

      mate_pattern / endgame / concept     — Knowledge. 1 correct, no wrongs still
                                             pending retry = learned.
      trap_set                             — Studied + correctly handled once = learned.
      opening                              — Exposure. 5 seen, 3 correct, last 2 not
                                             wrong = learned.
      coached_play                         — Habit. 3 correct, last 3 not wrong = learned.
      unknown / legacy "pattern"           — Conservative default: 5/3/no-recent-fail.
    """
    skill_id: str                      # e.g., "endgame_rule_of_square", "opening_london_white"
    skill_type: str                    # "opening" | "trap_set" | "trap" | "endgame" |
                                       # "mate_pattern" | "concept" | "coached_play" | "pattern"
    seen: int = 0
    correct: int = 0
    wrong: int = 0
    # Mohit 2026-05-29: in-game concept application count, separate from
    # lesson `correct`. An `applied` outcome is recorded when an in-game
    # detector (services/concept_detectors/*) confirms the user
    # demonstrated the concept in unprompted gameplay. Used to lift the
    # graduation bar from "completed a lesson" to "completed a lesson +
    # applied it in a game" — the honest "learned" claim per the
    # concept_detectors docstring design note.
    applied: int = 0
    outcomes: List[str] = field(default_factory=list)  # Last 10: "correct"|"wrong"|"seen"|"applied"
    # Mohit 2026-05-30: per-grade evidence. Each entry pins the credit
    # to a concrete artefact the user can audit — game_id + move_number
    # + fen_before + move_san for in-game grades; lesson_key for
    # lesson-completion grades. Surfaced via /api/engine2/skill-
    # evidence/{skill_id}. Capped at 20 entries (latest wins) to keep
    # the document size bounded.
    evidence: List[Dict] = field(default_factory=list)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    learned_at: Optional[str] = None   # When promoted to learned (if ever)

    def is_learned(self) -> bool:
        """Kind-aware graduation. See docstring for rules per kind."""
        last_two = self.outcomes[-2:] if len(self.outcomes) >= 2 else self.outcomes
        last_three = self.outcomes[-3:] if len(self.outcomes) >= 3 else self.outcomes

        # ── Knowledge concepts — one correct demonstration is enough,
        # BUT if a real in-game detector ever fired for this skill (the
        # `applied` counter > 0 OR an in-game "wrong" outcome from a
        # detector was recorded), lift the bar to "lesson correct AND
        # applied in real play." This keeps the rule lenient for skills
        # without detectors yet (back-compat) but rigorous where the
        # infrastructure exists. See concept_detectors/__init__.py.
        if self.skill_type in ("mate_pattern", "endgame", "concept"):
            if self.correct < 1:
                return False
            if self.wrong > 0 and "wrong" in last_two:
                return False
            # When a detector has ever graded this skill, require an
            # `applied` to graduate. Detector grades show up as either
            # `applied` outcome or `wrong` outcome from in-game play.
            detector_engaged = (self.applied > 0) or ("applied" in self.outcomes)
            if detector_engaged and self.applied < 1:
                return False
            return True

        # ── Trap sets — studied at least once and handled correctly at least once.
        if self.skill_type in ("trap_set", "trap"):
            if self.seen < 1 or self.correct < 1:
                return False
            if "wrong" in last_two:
                return False
            return True

        # ── Openings — exposure-based. Classic 5 seen, 3 correct, no recent fail.
        if self.skill_type == "opening":
            if self.seen < 5 or self.correct < 3:
                return False
            return "wrong" not in last_two

        # ── Coached play — habit formation. 3 consecutive clean games.
        if self.skill_type == "coached_play":
            if self.correct < 3:
                return False
            return "wrong" not in last_three

        # ── Legacy / unknown — original 5/3/no-recent-fail as safe default.
        if self.seen < 5 or self.correct < 3:
            return False
        return "wrong" not in last_two


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
    },
    # Mohit 2026-07-21: native cognitive_gap categories (see CLAUDE.md's
    # "Cognitive Gap Types" table) added as first-class habit_ids so
    # imported-game weaknesses can be driven directly from the per-move
    # `cognitive_gap` tag already present in stockfish_analysis.move_evaluations
    # — no lossy remapping to the older 7 habit ids above.
    "piece_safety": {
        "name": "Piece Safety",
        "category": HabitCategory.TACTICS,
        "description": "Hanging pieces or leaving them undefended",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "missed_tactic": {
        "name": "Missed Tactics",
        "category": HabitCategory.TACTICS,
        "description": "Missing forks, pins, or skewers available on the board",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "tactical_oversight": {
        "name": "Tactical Oversight",
        "category": HabitCategory.TACTICS,
        "description": "Seeing one move ahead but missing the follow-up",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "calculation_depth": {
        "name": "Calculation Depth",
        "category": HabitCategory.TACTICS,
        "description": "Shallow calculation, missing deeper forcing lines",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "king_safety": {
        "name": "King Safety",
        "category": HabitCategory.POSITIONAL,
        "description": "Weak king position or ignoring threats to it",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "pawn_structure": {
        "name": "Pawn Structure",
        "category": HabitCategory.POSITIONAL,
        "description": "Creating weak pawns or bad pawn breaks",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "piece_activity": {
        "name": "Piece Activity",
        "category": HabitCategory.POSITIONAL,
        "description": "Passive pieces or poor piece coordination",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "opening_knowledge": {
        "name": "Opening Knowledge",
        "category": HabitCategory.OPENING,
        "description": "Deviating from sound opening principles early",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "endgame_technique": {
        "name": "Endgame Technique",
        "category": HabitCategory.ENDGAME,
        "description": "Poor conversion or technique in the endgame",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
    "time_pressure": {
        "name": "Time Pressure",
        "category": HabitCategory.TIME,
        "description": "Blunders made while running low on time",
        "detection": "cognitive_gap tag on mistake/blunder moves"
    },
}


def compute_habit_violations_from_moves(move_evaluations: List[Dict]) -> List[str]:
    """
    Derive habits_violated for update_memory_after_game() directly from the
    per-move `cognitive_gap` tags that stockfish analysis already writes to
    game_analyses.stockfish_analysis.move_evaluations. This is the bridge
    that was missing for imported games: analysis_worker.py used to pass a
    hardcoded [] here because "imported games don't have HabitViolation
    objects" — but the cognitive_gap tag on each mistake/blunder move IS
    that signal, just under a different name.
    """
    gaps = set()
    for m in move_evaluations or []:
        if m.get("is_opponent_move"):
            continue
        evaluation = (m.get("evaluation") or "").lower()
        gap = m.get("cognitive_gap")
        if gap and evaluation in ("mistake", "blunder"):
            gaps.add(gap)
    return sorted(gaps)


async def backfill_weaknesses_for_user(db, user_id: str, dry_run: bool = True) -> Dict:
    """
    One-time backfill for games analyzed BEFORE the analysis_worker.py fix
    (which hardcoded habits_violated=[] for every imported game). Scans all
    of a user's already-analyzed games directly and populates
    coach_memory.weaknesses from the cognitive_gap tags already present in
    stockfish_analysis.move_evaluations — no re-analysis needed, the tags
    already exist.

    Only touches `weaknesses`; deliberately leaves performance stats
    (games_played, avg_accuracy, etc.) untouched since those are already
    correctly maintained incrementally and replaying this per historical
    game would double-count them.

    dry_run=True (default) returns what WOULD be written without writing.
    """
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "analyzed_at": 1, "stockfish_analysis.move_evaluations": 1},
    ).to_list(None)

    gap_stats: Dict[str, Dict[str, Any]] = {}
    for a in analyses:
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations", [])
        raw_analyzed_at = a.get("analyzed_at") or ""
        # analyzed_at is a native datetime in some documents, an ISO string
        # in others — normalize to a string so comparisons below never mix
        # types (datetime > str raises TypeError).
        analyzed_at = (
            raw_analyzed_at.isoformat()
            if isinstance(raw_analyzed_at, datetime)
            else str(raw_analyzed_at)
        )
        game_id = a.get("game_id")
        gaps_this_game = set()
        for m in moves:
            if m.get("is_opponent_move"):
                continue
            evaluation = (m.get("evaluation") or "").lower()
            gap = m.get("cognitive_gap")
            if gap and evaluation in ("mistake", "blunder"):
                gaps_this_game.add(gap)
        for gap in gaps_this_game:
            st = gap_stats.setdefault(gap, {"count": 0, "games": set(), "last_at": ""})
            st["count"] += 1
            st["games"].add(game_id)
            if analyzed_at and analyzed_at > st["last_at"]:
                st["last_at"] = analyzed_at

    summary = {
        gap: {"detection_count": st["count"], "games_tracked": len(st["games"]), "last_detected": st["last_at"]}
        for gap, st in gap_stats.items()
    }

    if dry_run or not gap_stats:
        return {"user_id": user_id, "games_scanned": len(analyses), "would_write": summary, "written": False}

    now = datetime.now(timezone.utc).isoformat()
    memory = await get_or_create_memory(db, user_id)
    for gap, st in gap_stats.items():
        existing = next((w for w in memory.weaknesses if w.habit_id == gap), None)
        if existing:
            existing.detection_count = max(existing.detection_count, st["count"])
            existing.games_tracked = max(existing.games_tracked, len(st["games"]))
            existing.last_detected = st["last_at"] or existing.last_detected or now
        else:
            info = DETECTABLE_WEAKNESSES.get(gap, {})
            memory.weaknesses.append(UserHabit(
                habit_id=gap,
                name=info.get("name", gap),
                category=info.get("category", HabitCategory.TACTICS),
                is_good=False,
                description=info.get("description", ""),
                detection_count=st["count"],
                last_detected=st["last_at"] or now,
                games_tracked=len(st["games"]),
            ))
    memory.updated_at = now
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": {"weaknesses": [asdict(w) for w in memory.weaknesses], "updated_at": now}},
        upsert=True,
    )
    return {"user_id": user_id, "games_scanned": len(analyses), "would_write": summary, "written": True}


async def backfill_current_focus_for_user(db, user_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    One-time correction for coach_memory.learning.current_focus. Found via
    production audit 2026-07-21: 18 of 57 users with any current_focus set
    were stuck on "time_management" as a stale/default value with ZERO
    time_pressure occurrences anywhere in their actual games — this is the
    focus resolve_daily_fix() falls back to (services/daily_fix_service.py
    _resolve_focus) whenever user_active_focus has no active WEAKNESS-type
    doc, so it drove the Daily Fix card (the primary home-page re-engagement
    loop) to show every one of those users an irrelevant drill.

    Root cause: current_focus is only updated by update_memory_after_game()
    when _pick_prescription() returns a truthy value for THAT game's call
    (services/postgame_analysis.py); before today's habits_violated fix,
    persistent_weaknesses was always [] for imported-game users, so that
    logic could never fire and current_focus stayed wherever it was first
    seeded. Games analyzed from now on will self-correct via that fixed path
    (using the freshly-backfilled weaknesses) — this backfill fixes it
    immediately for users who won't have a new game analyzed soon.

    Sets current_focus to the user's top ACTIVE pattern by decay-weighted
    score (pattern_decay_service.refresh_user_pattern_decay) — the same
    ranking already used by home_intelligence_service and
    get_realtime_pattern_context, so the coach's "one thing to work on"
    stays consistent across Home, Daily Fix, and live coaching.

    Only overwrites when pattern data exists and disagrees with the stored
    focus (skips users with no real pattern data rather than clearing a
    focus that might be legitimately set from a source this function
    doesn't know about, e.g. a manually-set diagnostic focus).
    """
    from services.pattern_decay_service import refresh_user_pattern_decay

    scores = await refresh_user_pattern_decay(db, user_id)
    active_scores = {k: v for k, v in scores.items() if v.get("state") == "active"}
    candidates = active_scores or scores
    if not candidates:
        return {"user_id": user_id, "written": False, "reason": "no pattern data"}

    top_pattern = max(candidates.items(), key=lambda kv: kv[1].get("weighted_score", 0))[0]

    memory = await get_or_create_memory(db, user_id)
    old_focus = memory.learning.current_focus
    if old_focus == top_pattern:
        return {"user_id": user_id, "written": False, "reason": "already correct", "focus": top_pattern}

    if dry_run:
        return {"user_id": user_id, "written": False, "old_focus": old_focus, "new_focus": top_pattern}

    now = datetime.now(timezone.utc).isoformat()
    await db.coach_memory.update_one(
        {"user_id": user_id},
        {"$set": {"learning.current_focus": top_pattern, "updated_at": now}},
        upsert=True,
    )
    return {"user_id": user_id, "written": True, "old_focus": old_focus, "new_focus": top_pattern}


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
    # Filter each skill dict to known SkillProgress fields. Forward-
    # compat: if older docs grew stray keys, or newer docs have fields
    # that this server doesn't know about, we skip the unknowns rather
    # than crashing on TypeError.
    _valid_skill_fields = {f.name for f in _dc.fields(SkillProgress)}
    learning.skills = [
        SkillProgress(**{k: v for k, v in s.items() if k in _valid_skill_fields})
        for s in skills_raw
        if isinstance(s, dict)
    ]
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
    move_evaluations: Optional[List[Dict[str, Any]]] = None,  # Per-move records for concept-detector replay
    user_color: Optional[str] = None,  # "white" | "black" — needed when move_evaluations is supplied
    game_id: Optional[str] = None,     # Stamped on per-move evidence so users can audit the credit
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

    # === ENGINE 2: record knowledge-acquisition signals from this game ===
    # Mostly opening exposure — endgames/traps/concepts are recorded in
    # the teaching-engine flow, not here.
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
            opening_played=opening_played,
            timestamp=now,
        )
    except Exception as e:
        logger.debug(f"[ENGINE2] skill-attempt recording failed (non-fatal): {e}")

    # === CONCEPT DETECTORS: in-game application grading ===
    # Mohit 2026-05-29: walk USER moves through every registered
    # concept detector. Each "applied" grade lifts the skill from
    # "studied" (lesson done) to "learned" (also demonstrated in real
    # play); each "missed" grade demotes it. Detectors are scope-gated
    # — they return None when the position isn't a clean test — so
    # most moves contribute nothing. See concept_detectors/registry.py
    # for the live list; today only endgame_rule_of_square is wired.
    if move_evaluations and user_color:
        try:
            record_concept_applications_from_game(
                memory=memory,
                move_evaluations=move_evaluations,
                user_color=user_color,
                timestamp=now,
                game_id=game_id,
            )
        except Exception as e:
            logger.debug(f"[CONCEPT_DETECTORS] failed (non-fatal): {e}")

    # === CURRICULUM BRAIN: Store the coach's prescription ===
    # 2026-07-03: focus_bridge is now the authoritative source of the user's
    # current focus (see services/focus_bridge.py). This legacy path is
    # DEMOTED — it takes whatever focus_bridge says, so downstream readers
    # of memory.learning.current_focus stay coherent with FocusCard and
    # session_goal. The coach_prescription argument becomes advisory only.
    try:
        from services.focus_bridge import get_active_focus_bundle
        _bundle = await get_active_focus_bundle(db, user_id)
        _bridge_focus = _bundle.get("topic_key") if _bundle else None
    except Exception:
        _bridge_focus = None

    _new_focus = _bridge_focus or coach_prescription
    if _new_focus:
        old_focus = memory.learning.current_focus
        memory.learning.current_focus = _new_focus
        if old_focus and old_focus != _new_focus:
            if old_focus not in memory.learning.suggested_next:
                memory.learning.suggested_next.append(old_focus)
            memory.learning.suggested_next = memory.learning.suggested_next[-5:]
        if _bridge_focus:
            logger.info(
                f"[CURRICULUM] User {user_id}: focus delegated to focus_bridge "
                f"→ '{_bridge_focus}' (was '{old_focus}')"
            )
        else:
            logger.info(f"[CURRICULUM] User {user_id}: focus set to '{_new_focus}' (was '{old_focus}')")

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
    outcome: str,  # "correct", "wrong", "seen", or "applied"
    timestamp: Optional[str] = None,
    evidence: Optional[Dict] = None,
) -> SkillProgress:
    """
    Record one attempt at a skill. Applies the learned rule:
      seen >= 5, correct >= 3, no failure in last 2 outcomes.

    When a skill crosses the threshold, it gets promoted to the appropriate
    learned list (openings_learned / traps_learned / endgames_learned /
    concepts_mastered) based on skill_type.
    """
    # Mohit 2026-05-29: 'applied' is the new outcome type for in-game
    # detector confirmations. Treated like 'correct' for graduation but
    # tracked separately so is_learned() can require BOTH a lesson
    # correct AND a real in-game application.
    if outcome not in ("correct", "wrong", "seen", "applied"):
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
    elif outcome == "applied":
        # Counts toward graduation but is a different signal than
        # lesson-correct. Bump both `applied` and `correct` so callers
        # that read `correct` (e.g. the progress hint generator) still
        # see the user made forward progress.
        skill.applied += 1
        skill.correct += 1
    skill.outcomes.append(outcome)
    # Keep only last 10 outcomes for the rule check
    skill.outcomes = skill.outcomes[-10:]

    # Append the evidence record if the caller supplied one. Capped at
    # 20 entries (latest wins) so the document size stays bounded even
    # for users who play hundreds of games.
    if evidence:
        ev_entry = {
            "outcome": outcome,
            "timestamp": timestamp,
            **{k: v for k, v in evidence.items() if v is not None},
        }
        skill.evidence.append(ev_entry)
        skill.evidence = skill.evidence[-20:]

    # Promotion / demotion check — apply the 5/3/no-recent-fail rule.
    # "Learned" is not a badge — it's the current state of demonstrated
    # competence. If the user backslides (2+ wrongs in the last 2 outcomes)
    # we demote them back to learning so Engine 2 teaches it again.
    was_learned = skill.learned_at is not None
    currently_learned = skill.is_learned()

    target_list = {
        "opening":       memory.learning.openings_learned,
        "trap":          memory.learning.traps_learned,       # legacy
        "trap_set":      memory.learning.traps_learned,       # new (v2 kind)
        "endgame":       memory.learning.endgames_learned,
        "mate_pattern":  memory.learning.endgames_learned,    # mate patterns live with endgames
        "concept":       memory.learning.concepts_mastered,
        "coached_play":  memory.learning.concepts_mastered,   # habits land in concepts_mastered
        "pattern":       memory.learning.concepts_mastered,   # legacy
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
    opening_played: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> List[str]:
    """
    Record knowledge-acquisition attempts after a game.

    Engine 2 is about CHESS KNOWLEDGE (openings, traps, endgames, concepts),
    not tactical mistakes (Engine 1 owns those). So this function no longer
    scans mistake_types for forks/pins/etc.

    Per game we record:
      - Opening exposure: if the played opening matches an Engine 2 opening
        node, that node gets +1 seen, +correct if played well, +wrong if
        played badly.
      - Failing-hard in an opening: big blunders in a tracked opening count
        as wrong (we're exposing weakness in that repertoire).

    Endgame lessons, traps, mate patterns, and concepts are recorded
    elsewhere (teaching-engine flows in Play with Coach). This function
    only handles the signals available from a regular finished game.

    Signature kept backward-compatible — `mistake_types`, `was_winning`,
    `endgame_reached` are still accepted but no longer drive recording.
    Returns list of skill_ids that received an attempt.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    recorded: List[str] = []

    try:
        from services.engine2_skill_builder import _load_tree, get_skill_node  # noqa
    except Exception as e:
        logger.debug(f"[ENGINE2] tree load failed: {e}")
        return recorded

    # ── Opening exposure ──
    if opening_played:
        opening_slug = _normalize_opening_key(opening_played)
        from services.engine2_skill_builder import list_skills_by_kind, get_skill_node
        for sid in list_skills_by_kind("opening"):
            node = get_skill_node(sid) or {}
            if node.get("content_ref") != opening_slug:
                continue
            # Rating gate
            if not (node.get("rating_min", 0) <= user_rating <= node.get("rating_max", 9999)):
                continue
            outcome = _opening_outcome(accuracy, blunders, game_result, node.get("tier", 1))
            record_skill_attempt(memory, sid, "opening", outcome, timestamp)
            recorded.append(sid)

    return recorded


def record_concept_applications_from_game(
    memory: CoachMemory,
    move_evaluations: List[Dict[str, Any]],
    user_color: str,
    timestamp: Optional[str] = None,
    game_id: Optional[str] = None,
) -> List[tuple]:
    """Run every registered concept detector against this game's USER
    moves. Each `applied` / `missed` grade is persisted via
    record_skill_attempt (outcome = 'applied' or 'wrong'). Returns the
    list of (skill_id, outcome) tuples recorded.

    Mohit 2026-05-29: this is the integration point promised in the
    concept_detectors __init__ docstring ("not wired yet — design
    only"). The detector module already shipped; this function ties it
    to coach_memory.

    move_evaluations must contain per-move dicts with at least
    `fen_before` + `move` (SAN). Empty list / missing fields are
    skipped silently — detector bugs and bad data must not poison the
    memory-update pipeline.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    if not move_evaluations:
        return []

    try:
        import chess
        from services.concept_detectors._runner import run_detectors_for_move
        from services.engine2_skill_builder import get_skill_node
    except Exception as e:
        logger.debug(f"[CONCEPT_DETECTORS] import failed: {e}")
        return []

    user_is_white = (user_color or "white").lower() == "white"
    uc = chess.WHITE if user_is_white else chess.BLACK

    # Mohit 2026-05-30: run detectors PER MOVE so we can capture the
    # specific (game_id, move_number, fen_before, move_san) tuple as
    # evidence for each grade. The older approach (run_detectors_for_game)
    # aggregated grades into one (skill_id, outcome) pair per game,
    # losing the move-level provenance the user needs to audit.
    #
    # If multiple moves in the same game grade the same skill, the LAST
    # grade wins (matches the original aggregation semantics) and its
    # evidence is the one we keep.
    latest_grade = {}   # skill_id -> (outcome, evidence_dict)
    for me in move_evaluations:
        fen_before = me.get("fen_before")
        san = me.get("move") or me.get("move_san")
        if not fen_before or not san:
            continue
        try:
            board = chess.Board(fen_before)
            if board.turn != uc:
                continue
            move = board.parse_san(san)
            for skill_id, outcome in run_detectors_for_move(board, move, uc):
                latest_grade[skill_id] = (
                    outcome,
                    {
                        "game_id": game_id,
                        "move_number": me.get("move_number"),
                        "fen_before": fen_before,
                        "move_san": san,
                        "source": "detector",
                    },
                )
        except Exception:
            continue

    recorded = []
    for skill_id, (outcome, evidence) in latest_grade.items():
        node = get_skill_node(skill_id) or {}
        skill_type = node.get("kind", "concept")
        record_skill_attempt(
            memory, skill_id, skill_type, outcome, timestamp,
            evidence=evidence,
        )
        recorded.append((skill_id, outcome))
        logger.info(
            f"[CONCEPT_DETECTORS] {skill_id} ({skill_type}) -> "
            f"{outcome} for {memory.user_id}"
        )
    return recorded


def _normalize_opening_key(opening: str) -> str:
    """opening_curriculum.json uses underscore keys (italian_game, caro_kann).
    Game.opening fields vary — normalize to underscore-lowercase."""
    if not opening:
        return ""
    return (
        opening.strip().lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def _opening_outcome(accuracy: float, blunders: int, game_result: str, tier: int) -> str:
    """
    Did the user play this opening well this game?
      - correct: won or drew with accuracy above the tier's threshold and no blunders
      - wrong:   lost badly OR accuracy far below threshold OR 2+ blunders in the opening
      - seen:    middle ground (played it, no strong signal either way)

    Tier sets the accuracy bar: tier 1 = 60, tier 2 = 65, tier 3 = 72.
    """
    thresholds = {0: 55, 1: 60, 2: 65, 3: 72}
    bar = thresholds.get(tier, 60)
    acc = accuracy or 0.0

    # Strong wrong signals
    if blunders >= 2 and acc < bar:
        return "wrong"
    if game_result == "loss" and acc < bar - 10:
        return "wrong"

    # Strong correct signals
    if game_result in ("win", "draw") and acc >= bar and blunders == 0:
        return "correct"

    return "seen"


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
        insights.append(f"Your accuracy ({accuracy:.1f}%) was above your average ({memory.performance.avg_accuracy:.1f}%) — sharp game.")
    elif accuracy < memory.performance.avg_accuracy - 10:
        insights.append("Your accuracy was below your usual level. What happened?")

    # Blunder comparison
    if blunders == 0 and memory.performance.avg_blunders_per_game > 0.5:
        insights.append("Zero blunders this game — you usually average {:.1f}.".format(
            memory.performance.avg_blunders_per_game
        ))
    elif blunders > memory.performance.avg_blunders_per_game + 1:
        insights.append(f"More blunders than usual ({blunders} vs your avg {memory.performance.avg_blunders_per_game:.1f}).")

    # Habit insights
    for habit_id in improved:
        habit_info = DETECTABLE_WEAKNESSES.get(habit_id, {})
        insights.append(f"You avoided {habit_info.get('name', habit_id)} this game. That's the pattern starting to fade.")

    # Recurring issues
    for habit_id in violated:
        habit_info = DETECTABLE_WEAKNESSES.get(habit_id, {})
        # Check if this is a recurring issue
        for w in memory.weaknesses:
            if w.habit_id == habit_id and w.detection_count >= 3:
                insights.append(f"'{w.name}' showed up again — {w.detection_count} times now. This is the one to fix.")
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
        "first_game": "First game together. I don't know your patterns yet, so today's teaching will be general — that gets sharper as we play more.",
        "after_win": "Welcome back. Good win last time — let's keep the momentum.",
        "after_loss": "Welcome back. Last game was tough; today's a fresh one.",
        "improving": f"You're playing well — {memory.performance.improvement_rate*100:.0f}% win rate recently.",
        "struggling": "Welcome back. Things have been tough — let's focus on one thing today.",
        "normal": f"Welcome back. Game #{memory.performance.games_played + 1}.",
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
    
    # Map legacy mistake-type labels to the older 7-habit vocabulary; any
    # other value (including the native cognitive_gap categories added
    # 2026-07-21 — piece_safety, missed_tactic, king_safety, etc.) is used
    # directly as the habit_id, since those are now first-class entries in
    # DETECTABLE_WEAKNESSES and in memory.weaknesses.
    mistake_to_habit = {
        "hanging_piece": "piece_safety",
        "tactical_miss": "tactical_oversight",
        "early_queen": "early_queen",
        "pawn_weakness": "pawn_structure",
        "time_trouble": "time_trouble",
        "overconfidence": "overconfidence"
    }

    habit_id = mistake_to_habit.get(mistake_type, mistake_type)
    
    if habit_id:
        # Check if this is a known weakness
        for weakness in memory.weaknesses:
            if weakness.habit_id == habit_id:
                result["is_recurring"] = True
                result["last_occurrence"] = weakness.last_detected

                # Mohit 2026-07-21: use the decay-weighted RECENT count for
                # the live message, not weakness.detection_count (a lifetime
                # cumulative total that can run into the hundreds for an
                # established user — "this is the 803rd time" is not
                # something a real coach would ever say; recency is the
                # whole point of the decay model). Falls back to the
                # lifetime count only if decay scoring is unavailable.
                recent_count = weakness.detection_count
                is_improving = weakness.improving
                try:
                    from services.pattern_decay_service import refresh_user_pattern_decay
                    decay_scores = await refresh_user_pattern_decay(db, user_id)
                    decay_info = decay_scores.get(habit_id)
                    if decay_info:
                        recent_count = decay_info.get("recent_raw", recent_count)
                        is_improving = decay_info.get("clean_streak", 0) >= 2
                except Exception:
                    pass
                result["occurrence_count"] = recent_count

                # Generate pattern message
                if recent_count >= 3:
                    result["pattern_message"] = (
                        f"{weakness.name} — {recent_count} times in your recent games. "
                        f"This is the one to fix."
                    )
                elif recent_count == 2:
                    result["pattern_message"] = (
                        f"{weakness.name} happened last game too. Same kind of slip."
                    )

                # Check if improving
                if is_improving:
                    result["improvement_note"] = (
                        f"You're getting better at {weakness.name} — the pattern is fading."
                    )
                break
    
    # Get recent game reference if available
    try:
        if db is not None:
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


async def backfill_coach_memory_from_imported_games(db, user_id: str) -> Dict:
    """
    Backfill coach memory for a new user based on their imported/analyzed games.

    This runs on first login to unlock coaching immediately, even before the user
    has played games WITH the coach. Extracts:
    - Recurring mistake patterns (from game analyses)
    - Opening repertoire
    - Performance trends
    - Detected weaknesses

    Returns: {
        "success": bool,
        "games_analyzed": int,
        "patterns_detected": List[str],
        "message": str
    }
    """
    try:
        # Get or create memory
        memory = await get_or_create_memory(db, user_id)

        # Get user's rating
        rating_info = await get_user_rating_from_games(db, user_id)
        user_rating = rating_info.get('rating', 1200)

        # Fetch analyzed games (up to 30 recent ones)
        games_analyzed = 0
        patterns_detected = []
        openings_seen = {}

        analyses = await db.game_analyses.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("analyzed_at", -1).limit(30).to_list(30)

        if not analyses:
            # No analyzed games yet - just set initialized flag
            memory.performance.best_performance_rating = user_rating
            await update_memory_after_game(
                db, user_id,
                game_result="unknown",
                accuracy=0,
                blunders=0,
                mistakes=0,
                habits_violated=[],
                habits_improved=[],
                opening_played=None,
                endgame_reached=False,
                performance_rating=user_rating,
            )
            return {
                "success": True,
                "games_analyzed": 0,
                "patterns_detected": [],
                "message": "No analyzed games found yet. Coach is ready to learn from your Play with Coach sessions!"
            }

        # Analyze each game to detect patterns
        pattern_counts = {}
        for analysis in analyses:
            games_analyzed += 1
            sf = analysis.get("stockfish_analysis", {})
            moves = sf.get("move_evaluations", [])

            # Extract cognitive gaps (patterns)
            for move in moves:
                if not move.get("is_opponent_move"):
                    gap = move.get("cognitive_gap")
                    if gap and gap != "unknown":
                        pattern_counts[gap] = pattern_counts.get(gap, 0) + 1

        # Get top 3-5 patterns
        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        for pattern, count in sorted_patterns[:5]:
            if count >= 2:  # Only patterns that appear multiple times
                patterns_detected.append(pattern)
                # Add to memory's recurring patterns
                if pattern not in memory.recurring_patterns:
                    memory.recurring_patterns.append(pattern)

        # Set performance baseline
        memory.performance.best_performance_rating = user_rating
        memory.performance.games_played = games_analyzed

        # If patterns detected, set one as current focus for coaching
        if patterns_detected:
            memory.learning.current_focus = patterns_detected[0]

        # Save updated memory
        now = datetime.now(timezone.utc).isoformat()
        memory.updated_at = now
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {"$set": _memory_to_doc(memory)},
            upsert=True
        )

        # Also mark that backfill has been done by setting a flag in users collection
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"coach_memory_initialized": True}}
        )

        return {
            "success": True,
            "games_analyzed": games_analyzed,
            "patterns_detected": patterns_detected,
            "message": f"Coach memory ready! Detected {len(patterns_detected)} patterns from {games_analyzed} games."
        }

    except Exception as e:
        logger.error(f"Backfill coach memory failed for {user_id}: {e}")
        return {
            "success": False,
            "games_analyzed": 0,
            "patterns_detected": [],
            "message": "Coach memory backfill failed, but coaching is still available."
        }
