"""
Mistake Card Service - The Mistake Mastery System

This service manages the spaced repetition system for learning from your own mistakes.
Every mistake from your games becomes a "card" that you'll review until mastered.

Core Concepts:
1. Cards are extracted from game analyses (blunders, mistakes, inaccuracies)
2. Each card is tagged with a habit (back_rank, pins, hanging_pieces, etc.)
3. Spaced repetition schedules reviews: correct = longer interval, wrong = see it sooner
4. Mastery = 3 consecutive correct answers
5. User focuses on ONE habit at a time until all cards for that habit are mastered
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from bson import ObjectId
import uuid

logger = logging.getLogger(__name__)

# =============================================================================
# HABIT DEFINITIONS
# =============================================================================

HABIT_DEFINITIONS = {
    "back_rank_weakness": {
        "display_name": "Back-Rank Awareness",
        "description": "Missing threats to the back rank (1st/8th rank)",
        "patterns": ["back rank", "back-rank", "mate on first", "mate on eighth"]
    },
    "hanging_pieces": {
        "display_name": "Hanging Pieces",
        "description": "Leaving pieces undefended or missing free captures",
        "patterns": ["undefended", "hanging", "free piece", "takes for free"]
    },
    "pin_blindness": {
        "display_name": "Pin Awareness",
        "description": "Missing pins or moving pinned pieces",
        "patterns": ["pin", "pinned", "absolute pin", "relative pin"]
    },
    "fork_blindness": {
        "display_name": "Fork Awareness",
        "description": "Missing knight forks or double attacks",
        "patterns": ["fork", "double attack", "knight fork", "family fork"]
    },
    "king_safety": {
        "display_name": "King Safety",
        "description": "Weakening king position or missing king attacks",
        "patterns": ["king safety", "exposed king", "weak king", "attack on king"]
    },
    "piece_activity": {
        "display_name": "Piece Activity",
        "description": "Passive pieces or missing activation opportunities",
        "patterns": ["passive", "inactive", "improve piece", "activate"]
    },
    "pawn_structure": {
        "display_name": "Pawn Structure",
        "description": "Creating or missing pawn weaknesses",
        "patterns": ["doubled pawn", "isolated pawn", "backward pawn", "pawn structure"]
    },
    "tactical_oversight": {
        "display_name": "Tactical Oversight",
        "description": "Missing simple tactics (captures, threats)",
        "patterns": ["missed", "oversight", "blunder", "simple tactic"]
    },
    "endgame_technique": {
        "display_name": "Endgame Technique",
        "description": "Mistakes in endgame play",
        "patterns": ["endgame", "king activity", "passed pawn", "opposition"]
    },
    "calculation_error": {
        "display_name": "Calculation",
        "description": "Miscalculating variations or missing moves",
        "patterns": ["calculation", "miscalculated", "missed line", "didn't see"]
    }
}

# Default habit for unclassified mistakes
DEFAULT_HABIT = "tactical_oversight"

# =============================================================================
# SPACED REPETITION ALGORITHM (SM-2 variant)
# =============================================================================

def calculate_next_review(card: Dict, correct: bool) -> Dict:
    """
    Update card scheduling based on answer correctness.
    Uses a simplified SM-2 algorithm.
    
    Intervals: 1 day → 3 days → 7 days → 14 days → 30 days → 60 days
    """
    consecutive = card.get("consecutive_correct", 0)
    interval = card.get("interval_days", 1)
    ease = card.get("ease_factor", 2.5)
    
    if correct:
        consecutive += 1
        
        # Determine new interval
        if interval == 0 or interval == 1:
            new_interval = 3
        elif interval == 3:
            new_interval = 7
        elif interval == 7:
            new_interval = 14
        elif interval == 14:
            new_interval = 30
        else:
            new_interval = min(int(interval * ease), 90)  # Cap at 90 days
        
        # Increase ease slightly on correct
        new_ease = min(ease + 0.1, 3.0)
        
        # Check mastery (3 consecutive correct)
        is_mastered = consecutive >= 3
    else:
        # Reset on wrong answer
        consecutive = 0
        new_interval = 1  # Review again tomorrow
        new_ease = max(ease - 0.2, 1.3)  # Decrease ease, min 1.3
        is_mastered = False
    
    next_review = datetime.now(timezone.utc) + timedelta(days=new_interval)
    
    return {
        "consecutive_correct": consecutive,
        "interval_days": new_interval,
        "ease_factor": round(new_ease, 2),
        "next_review": next_review.isoformat(),
        "is_mastered": is_mastered,
        "last_reviewed": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# HABIT CLASSIFICATION
# =============================================================================

def classify_mistake_habit(move_data: Dict, commentary: str = "") -> str:
    """
    Classify a mistake into a habit category based on move data and commentary.
    """
    # Combine all text for pattern matching
    text_to_search = (
        (commentary or "") + " " +
        (move_data.get("feedback", "") or "") + " " +
        (move_data.get("threat", "") or "") + " " +
        str(move_data.get("details", {}))
    ).lower()
    
    # Check each habit's patterns
    for habit_key, habit_info in HABIT_DEFINITIONS.items():
        for pattern in habit_info["patterns"]:
            if pattern.lower() in text_to_search:
                return habit_key
    
    # Check based on evaluation type and phase
    phase = move_data.get("phase", "middlegame")
    if phase == "endgame":
        return "endgame_technique"
    
    # Check for specific move patterns
    cp_loss = move_data.get("cp_loss", 0)
    if cp_loss >= 300:  # Big blunder
        return "tactical_oversight"
    
    return DEFAULT_HABIT


def get_habit_display_name(habit_key: str) -> str:
    """Get the display name for a habit key."""
    return HABIT_DEFINITIONS.get(habit_key, {}).get("display_name", habit_key.replace("_", " ").title())


# =============================================================================
# CARD EXTRACTION
# =============================================================================

async def extract_mistake_cards_from_analysis(
    db, 
    user_id: str, 
    game_id: str, 
    analysis: Dict,
    game: Dict
) -> List[Dict]:
    """
    Extract mistake cards from a game analysis.
    Only extracts blunders, mistakes, and significant inaccuracies.
    """
    cards_created = []
    
    # Get stockfish move evaluations
    stockfish_data = analysis.get("stockfish_analysis", {})
    move_evaluations = stockfish_data.get("move_evaluations", [])
    
    # Get commentary for additional context
    commentary = analysis.get("commentary", [])
    commentary_by_move = {c.get("move_number"): c for c in commentary}
    
    # Get phase data if available
    phase_analysis = analysis.get("phase_analysis", {})
    phases = phase_analysis.get("phases", [])
    
    # Get user color and opponent info for personalization
    user_color = game.get("user_color", "white")
    opponent = game.get("opponent", "")
    if not opponent:
        # Try to extract from white/black fields
        if user_color == "white":
            opponent = game.get("black", "")
        else:
            opponent = game.get("white", "")
    
    for move in move_evaluations:
        # Get evaluation type safely
        eval_type = move.get("evaluation", "")
        if hasattr(eval_type, "value"):
            eval_type = eval_type.value
        
        # Only create cards for mistakes, not neutral/good moves
        if eval_type not in ["blunder", "mistake", "inaccuracy"]:
            continue
        
        # Skip minor inaccuracies (cp_loss < 50)
        cp_loss = move.get("cp_loss", 0)
        if eval_type == "inaccuracy" and cp_loss < 50:
            continue
        
        move_number = move.get("move_number", 0)
        fen = move.get("fen_before", "")
        
        if not fen:
            continue
        
        # Get commentary for this move
        move_commentary = commentary_by_move.get(move_number, {})
        
        # Determine phase for this move
        move_phase = "middlegame"  # Default
        for phase in phases:
            if phase.get("start_move", 0) <= move_number <= phase.get("end_move", 999):
                move_phase = phase.get("phase", "middlegame")
                break
        
        # Build context for habit classification
        move_context = {
            "cp_loss": cp_loss,
            "evaluation": eval_type,
            "phase": move_phase,
            "feedback": move_commentary.get("feedback", ""),
            "threat": move.get("threat", ""),
            "details": move_commentary.get("details", {}),
            "pv_after_played": move.get("pv_after_played", []),
            "pv_after_best": move.get("pv_after_best", [])
        }
        
        # Classify into a habit
        habit_tag = classify_mistake_habit(move_context, move_commentary.get("feedback", ""))
        
        # Build explanation from available data
        explanation_parts = []
        if move_commentary.get("feedback"):
            explanation_parts.append(move_commentary["feedback"])
        if move.get("threat"):
            explanation_parts.append(f"The threat was {move['threat']}.")
        if move.get("pv_after_played"):
            explanation_parts.append(f"After your move: {' '.join(move['pv_after_played'][:3])}")
        
        explanation = " ".join(explanation_parts) if explanation_parts else f"This was a {eval_type} losing {cp_loss/100:.1f} pawns."
        
        # Create the card
        card = {
            "card_id": f"card_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "game_id": game_id,
            "fen": fen,
            "correct_move": move.get("best_move", ""),
            "correct_move_uci": move.get("best_move_uci", ""),
            "user_move": move.get("move", ""),
            "user_move_uci": move.get("move_uci", ""),
            "move_number": move_number,
            "habit_tag": habit_tag,
            "phase": move_phase,
            "cp_loss": cp_loss,
            "evaluation": eval_type,
            "explanation": explanation,
            "threat_line": move.get("pv_after_played", []),
            "better_line": move.get("pv_after_best", []),
            
            # Personalized context
            "opponent": opponent,
            "user_color": user_color,
            
            # Spaced repetition - starts due immediately
            "next_review": datetime.now(timezone.utc).isoformat(),
            "interval_days": 0,
            "ease_factor": 2.5,
            "consecutive_correct": 0,
            "total_attempts": 0,
            "total_correct": 0,
            "is_mastered": False,
            
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_reviewed": None
        }
        
        # Check if card already exists for this position in this game
        existing = await db.mistake_cards.find_one({
            "user_id": user_id,
            "game_id": game_id,
            "fen": fen
        })
        
        if not existing:
            await db.mistake_cards.insert_one(card)
            cards_created.append(card)
            logger.info(f"Created mistake card {card['card_id']} for habit {habit_tag}")
    
    # Update user's habit progress
    if cards_created:
        await update_user_habit_progress(db, user_id)
    
    return cards_created


# =============================================================================
# CARD RETRIEVAL
# =============================================================================

async def get_due_cards(db, user_id: str, limit: int = 5) -> List[Dict]:
    """
    Get cards due for review today, prioritized by:
    1. Active habit first
    2. Overdue cards (past next_review date)
    3. Cards with lower consecutive_correct (struggling)
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Get user's active habit
    progress = await get_user_habit_progress(db, user_id)
    active_habit = progress.get("active_habit")
    
    # Query for due cards
    query = {
        "user_id": user_id,
        "is_mastered": False,
        "next_review": {"$lte": now}
    }
    
    # Prioritize active habit
    if active_habit:
        # First get cards from active habit
        active_cards = await db.mistake_cards.find(
            {**query, "habit_tag": active_habit},
            {"_id": 0}
        ).sort([
            ("consecutive_correct", 1),  # Struggling cards first
            ("next_review", 1)  # Oldest due first
        ]).limit(limit).to_list(limit)
        
        if len(active_cards) >= limit:
            return active_cards
        
        # Fill with other habits if needed
        remaining = limit - len(active_cards)
        other_cards = await db.mistake_cards.find(
            {**query, "habit_tag": {"$ne": active_habit}},
            {"_id": 0}
        ).sort([
            ("consecutive_correct", 1),
            ("next_review", 1)
        ]).limit(remaining).to_list(remaining)
        
        return active_cards + other_cards
    
    # No active habit - get any due cards
    cards = await db.mistake_cards.find(
        query,
        {"_id": 0}
    ).sort([
        ("consecutive_correct", 1),
        ("next_review", 1)
    ]).limit(limit).to_list(limit)
    
    return cards


async def get_post_game_card(db, user_id: str, hours_ago: int = 2) -> Optional[Dict]:
    """
    Get THE most critical mistake card from a recent game.
    Used for Post-Game Debrief.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    
    # Find most recent game
    recent_game = await db.games.find_one(
        {
            "user_id": user_id,
            "imported_at": {"$gte": cutoff},
            "is_analyzed": True
        },
        {"_id": 0, "game_id": 1, "white_player": 1, "black_player": 1, "result": 1, 
         "user_color": 1, "imported_at": 1, "platform": 1}
    )
    
    if not recent_game:
        return None
    
    # Get the worst mistake from this game (highest cp_loss)
    card = await db.mistake_cards.find_one(
        {
            "user_id": user_id,
            "game_id": recent_game["game_id"],
            "is_mastered": False
        },
        {"_id": 0},
        sort=[("cp_loss", -1)]  # Worst mistake first
    )
    
    if card:
        card["game_info"] = recent_game
    
    return card


async def get_card_by_id(db, card_id: str, user_id: str) -> Optional[Dict]:
    """Get a specific card by ID."""
    return await db.mistake_cards.find_one(
        {"card_id": card_id, "user_id": user_id},
        {"_id": 0}
    )


# =============================================================================
# CARD UPDATES
# =============================================================================

async def record_card_attempt(db, card_id: str, user_id: str, correct: bool) -> Dict:
    """
    Record an attempt on a card and update its schedule.
    """
    card = await db.mistake_cards.find_one(
        {"card_id": card_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not card:
        return {"error": "Card not found"}
    
    # Calculate new schedule
    schedule_update = calculate_next_review(card, correct)
    
    # Update stats
    total_attempts = card.get("total_attempts", 0) + 1
    total_correct = card.get("total_correct", 0) + (1 if correct else 0)
    
    update_data = {
        **schedule_update,
        "total_attempts": total_attempts,
        "total_correct": total_correct
    }
    
    await db.mistake_cards.update_one(
        {"card_id": card_id},
        {"$set": update_data}
    )
    
    # Update habit progress if card was mastered
    if schedule_update.get("is_mastered") and not card.get("is_mastered"):
        await update_user_habit_progress(db, user_id)
    
    return {
        "card_id": card_id,
        "correct": correct,
        "is_mastered": schedule_update.get("is_mastered", False),
        "next_review": schedule_update.get("next_review"),
        "interval_days": schedule_update.get("interval_days"),
        "consecutive_correct": schedule_update.get("consecutive_correct")
    }


# =============================================================================
# HABIT PROGRESS
# =============================================================================

async def get_user_habit_progress(db, user_id: str) -> Dict:
    """
    Get user's habit mastery progress.
    """
    # Check if progress doc exists
    progress = await db.user_habit_progress.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not progress:
        # Initialize progress
        progress = await update_user_habit_progress(db, user_id)
    
    return progress


async def update_user_habit_progress(db, user_id: str) -> Dict:
    """
    Recalculate and update user's habit progress.
    """
    # Get card counts by habit
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$habit_tag",
            "total": {"$sum": 1},
            "mastered": {"$sum": {"$cond": ["$is_mastered", 1, 0]}}
        }}
    ]
    
    habit_stats = await db.mistake_cards.aggregate(pipeline).to_list(100)
    
    # Build habits list
    habits = []
    total_cards = 0
    total_mastered = 0
    
    for stat in habit_stats:
        habit_key = stat["_id"]
        total = stat["total"]
        mastered = stat["mastered"]
        
        total_cards += total
        total_mastered += mastered
        
        # Determine status
        if mastered >= total and total > 0:
            status = "mastered"
        elif mastered > 0 or total > 0:
            status = "active"
        else:
            status = "pending"
        
        habits.append({
            "habit_key": habit_key,
            "display_name": get_habit_display_name(habit_key),
            "total_cards": total,
            "mastered_cards": mastered,
            "status": status,
            "progress_pct": round((mastered / total * 100) if total > 0 else 0, 1)
        })
    
    # Sort: active first (by progress), then pending, then mastered
    habits.sort(key=lambda h: (
        0 if h["status"] == "active" else (1 if h["status"] == "pending" else 2),
        -h["total_cards"],  # More cards = more important
        h["progress_pct"]
    ))
    
    # Determine active habit (first non-mastered with cards)
    active_habit = None
    for h in habits:
        if h["status"] != "mastered" and h["total_cards"] > 0:
            active_habit = h["habit_key"]
            break
    
    progress = {
        "user_id": user_id,
        "active_habit": active_habit,
        "active_habit_display": get_habit_display_name(active_habit) if active_habit else None,
        "habits": habits,
        "total_cards": total_cards,
        "total_mastered": total_mastered,
        "overall_progress_pct": round((total_mastered / total_cards * 100) if total_cards > 0 else 0, 1),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Upsert progress
    await db.user_habit_progress.update_one(
        {"user_id": user_id},
        {"$set": progress},
        upsert=True
    )
    
    return progress


async def set_active_habit(db, user_id: str, habit_key: str) -> Dict:
    """
    Manually set the active habit for a user.
    """
    # Verify habit exists for user
    card_count = await db.mistake_cards.count_documents({
        "user_id": user_id,
        "habit_tag": habit_key
    })
    
    if card_count == 0:
        return {"error": f"No cards found for habit {habit_key}"}
    
    await db.user_habit_progress.update_one(
        {"user_id": user_id},
        {"$set": {
            "active_habit": habit_key,
            "active_habit_display": get_habit_display_name(habit_key),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    return await get_user_habit_progress(db, user_id)


# =============================================================================
# TRAINING SESSION
# =============================================================================

async def get_training_session(db, user_id: str) -> Dict:
    """
    Get the current training session for the user.
    Returns either a Post-Game Debrief or Daily Training cards.
    """
    # Check for recent game first (Post-Game Debrief)
    post_game_card = await get_post_game_card(db, user_id, hours_ago=2)
    
    if post_game_card:
        return {
            "mode": "post_game_debrief",
            "card": post_game_card,
            "game_info": post_game_card.get("game_info"),
            "message": "You just played! Let's look at the critical moment."
        }
    
    # Get habit progress
    progress = await get_user_habit_progress(db, user_id)
    
    # Get due cards
    due_cards = await get_due_cards(db, user_id, limit=5)
    
    if due_cards:
        return {
            "mode": "daily_training",
            "cards": due_cards,
            "cards_due": len(due_cards),
            "active_habit": progress.get("active_habit"),
            "active_habit_display": progress.get("active_habit_display"),
            "habit_progress": next(
                (h for h in progress.get("habits", []) if h["habit_key"] == progress.get("active_habit")),
                None
            ),
            "overall_progress": {
                "total_cards": progress.get("total_cards", 0),
                "total_mastered": progress.get("total_mastered", 0),
                "progress_pct": progress.get("overall_progress_pct", 0)
            },
            "message": f"You have {len(due_cards)} positions to review."
        }
    
    # All caught up!
    return {
        "mode": "all_caught_up",
        "cards": [],
        "cards_due": 0,
        "active_habit": progress.get("active_habit"),
        "habit_progress": progress,
        "message": "You're all caught up! Go play a game.",
        "next_review": await get_next_review_time(db, user_id)
    }


async def get_next_review_time(db, user_id: str) -> Optional[str]:
    """Get the time of the next scheduled review."""
    next_card = await db.mistake_cards.find_one(
        {"user_id": user_id, "is_mastered": False},
        {"_id": 0, "next_review": 1},
        sort=[("next_review", 1)]
    )
    return next_card.get("next_review") if next_card else None


# =============================================================================
# STATS
# =============================================================================

async def get_training_stats(db, user_id: str) -> Dict:
    """Get overall training statistics."""
    total_cards = await db.mistake_cards.count_documents({"user_id": user_id})
    mastered_cards = await db.mistake_cards.count_documents({"user_id": user_id, "is_mastered": True})
    
    # Get total attempts and accuracy
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_attempts": {"$sum": "$total_attempts"},
            "total_correct": {"$sum": "$total_correct"}
        }}
    ]
    
    stats = await db.mistake_cards.aggregate(pipeline).to_list(1)
    attempt_stats = stats[0] if stats else {"total_attempts": 0, "total_correct": 0}
    
    accuracy = 0
    if attempt_stats["total_attempts"] > 0:
        accuracy = round(attempt_stats["total_correct"] / attempt_stats["total_attempts"] * 100, 1)
    
    return {
        "total_cards": total_cards,
        "mastered_cards": mastered_cards,
        "mastery_rate": round((mastered_cards / total_cards * 100) if total_cards > 0 else 0, 1),
        "total_attempts": attempt_stats["total_attempts"],
        "total_correct": attempt_stats["total_correct"],
        "accuracy": accuracy
    }


# =============================================================================
# WHY QUESTION GENERATION (Socratic Follow-up)
# =============================================================================

async def generate_why_question(db, card: Dict) -> Dict:
    """
    Generate a Socratic "Why is this move better?" question for a card.
    Returns options with one correct answer and two plausible distractors.
    
    This function uses position context to generate meaningful options
    without requiring LLM calls (to keep it fast and reliable).
    """
    import random
    
    habit_tag = card.get("habit_tag", "tactical_oversight")
    correct_move = card.get("correct_move", "")
    user_move = card.get("user_move", "")
    explanation = card.get("explanation", "")
    threat_line = card.get("threat_line", [])
    better_line = card.get("better_line", [])
    
    # Habit-based correct reasons
    habit_correct_reasons = {
        "back_rank_weakness": [
            "It defends the back rank against mate threats",
            "It prevents a back-rank mating attack",
            "It creates an escape square for the king"
        ],
        "hanging_pieces": [
            "It defends the attacked piece",
            "It moves the piece to safety",
            "It protects the undefended material"
        ],
        "pin_blindness": [
            "It breaks the pin or avoids it",
            "It addresses the pinned piece problem",
            "It removes the piece from the dangerous file/diagonal"
        ],
        "fork_blindness": [
            "It prevents the enemy's forking opportunity",
            "It sidesteps the double attack",
            "It removes a piece from the fork square"
        ],
        "king_safety": [
            "It improves the king's safety",
            "It prevents an attack on the exposed king",
            "It creates better protection around the king"
        ],
        "piece_activity": [
            "It activates a passive piece",
            "It improves piece coordination",
            "It brings a piece into the game"
        ],
        "pawn_structure": [
            "It maintains a healthy pawn structure",
            "It avoids creating pawn weaknesses",
            "It preserves the pawn formation"
        ],
        "tactical_oversight": [
            "It spots the winning tactical idea",
            "It avoids the tactical trap",
            "It creates a concrete threat"
        ],
        "endgame_technique": [
            "It applies correct endgame principles",
            "It improves king activity in the endgame",
            "It advances the passed pawn correctly"
        ],
        "calculation_error": [
            "It sees the full variation correctly",
            "It calculates the consequences accurately",
            "It considers all defensive resources"
        ]
    }
    
    # Generic distractor reasons (plausible but not the main point)
    generic_distractors = [
        "It develops a piece to a more active square",
        "It controls more central squares",
        "It prepares for future pawn breaks",
        "It creates more space for your pieces",
        "It simplifies the position",
        "It opens lines for your pieces",
        "It keeps tension in the position",
        "It follows classical opening principles",
        "It fights for the initiative",
        "It improves overall piece coordination",
        "It prepares for the endgame",
        "It creates attacking chances"
    ]
    
    # Select the correct reason based on habit
    correct_reasons = habit_correct_reasons.get(habit_tag, habit_correct_reasons["tactical_oversight"])
    correct_reason = random.choice(correct_reasons)
    
    # Build more specific correct reason from explanation if available
    if explanation and len(explanation) > 20:
        # Extract key insight from explanation
        if "threat" in explanation.lower():
            correct_reason = "It addresses the immediate threat in the position"
        elif "safe" in explanation.lower() or "defend" in explanation.lower():
            correct_reason = "It defends against the opponent's tactical idea"
        elif "attack" in explanation.lower():
            correct_reason = "It creates a stronger counter-threat"
    
    # Select 2 plausible distractors (not the same as correct)
    distractors = [d for d in generic_distractors if d.lower() != correct_reason.lower()]
    selected_distractors = random.sample(distractors, min(2, len(distractors)))
    
    # Build options and shuffle
    options = [
        {"id": "correct", "text": correct_reason, "is_correct": True}
    ] + [
        {"id": f"wrong_{i}", "text": d, "is_correct": False} 
        for i, d in enumerate(selected_distractors)
    ]
    random.shuffle(options)
    
    return {
        "question": f"Why is {correct_move} better than {user_move}?",
        "options": options,
        "correct_explanation": correct_reason,
        "hint": f"Think about what {habit_tag.replace('_', ' ')} means in this position.",
        "threat_line": threat_line[:5] if threat_line else [],
        "better_line": better_line[:5] if better_line else []
    }

