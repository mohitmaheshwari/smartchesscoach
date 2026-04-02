"""
Coach Review Service — "Human Coach" Game Review
=================================================

This is NOT a game analysis tool. This is a coaching session.

Structure (what a real human coach does):
1. THE STORY    — What happened in this game (narrative arc, no moves)
2. THE MIRROR   — What this reveals about YOU as a player (personality, not eval)
3. THE MOMENT   — The 2-3 decisions that defined the game (WHY you decided, not WHAT was best)
4. THE TAKEAWAY — ONE sentence to carry into your next game (mantra)
5. THE PROOF    — What's getting better compared to your history (honest encouragement)

Design Principles:
- Language a player REMEMBERS, not notation they forget
- About thinking patterns, not centipawns
- Connected to cross-game history (Chess DNA)
- Adaptive to rating level
- LLM is the LANGUAGE layer only — all logic is deterministic
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── PHASE DETECTION ─────────────────────────────────────────────

def _move_phase(move_index: int, total_moves: int) -> str:
    if move_index < 20:
        return "opening"
    elif move_index > total_moves * 0.7:
        return "endgame"
    return "middlegame"


def _phase_label(phase: str) -> str:
    return {"opening": "the opening", "middlegame": "the middlegame", "endgame": "the endgame"}.get(phase, phase)


# ─── 1. THE STORY ────────────────────────────────────────────────

def compute_game_story(
    move_evaluations: List[Dict],
    game: Dict,
    user_color: str,
) -> Dict:
    """
    Build the narrative arc of the game. No engine numbers — just the story.
    Returns: { opening, tension, climax, resolution, arc_type }
    """
    user_is_white = user_color == "white"
    result = game.get("result", "")
    user_won = (result == "1-0" and user_is_white) or (result == "0-1" and not user_is_white)
    is_draw = "1/2" in result
    opening_name = game.get("opening_name") or game.get("opening") or "the opening"
    opponent = game.get("opponent_name") or "your opponent"
    total_moves = len(move_evaluations)

    # Collect user moves with eval context
    user_moves = []
    for i, m in enumerate(move_evaluations):
        is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        if is_user:
            user_moves.append({
                "index": i,
                "move_number": (i // 2) + 1,
                "san": m.get("san", m.get("move", "?")),
                "cp_loss": m.get("cp_loss", 0),
                "eval_before": m.get("eval_before", 0),
                "eval_after": m.get("eval_after", 0),
                "phase": _move_phase(i, total_moves),
            })

    if not user_moves:
        return {
            "opening": "Not enough data to tell the story.",
            "tension": "",
            "climax": "",
            "resolution": "",
            "arc_type": "unknown",
        }

    # --- Opening chapter ---
    opening_moves = [m for m in user_moves if m["phase"] == "opening"]
    opening_mistakes = [m for m in opening_moves if m["cp_loss"] >= 100]
    opening_eval = user_moves[min(9, len(user_moves) - 1)]["eval_after"] if len(user_moves) > 5 else 0
    opening_eval_user = opening_eval if user_is_white else -opening_eval

    if not opening_mistakes and opening_eval_user >= -50:
        opening_text = f"Good start out of {opening_name}. No early mistakes."
    elif opening_eval_user > 100:
        opening_text = f"You got a nice edge from {opening_name}. Strong start."
    elif opening_mistakes:
        opening_text = f"Rough start. {len(opening_mistakes)} mistake{'s' if len(opening_mistakes) > 1 else ''} in {opening_name} put you behind early."
    else:
        opening_text = f"Even opening. No one had a clear edge after {opening_name}."

    # --- Tension / middlegame chapter ---
    mid_moves = [m for m in user_moves if m["phase"] == "middlegame"]
    mid_blunders = [m for m in mid_moves if m["cp_loss"] >= 150]

    # Track eval swings (from user perspective)
    eval_track = []
    for m in user_moves:
        ev = m["eval_before"] if user_is_white else -m["eval_before"]
        eval_track.append(ev)

    max_advantage = max(eval_track) if eval_track else 0
    min_advantage = min(eval_track) if eval_track else 0
    had_advantage = max_advantage >= 200
    was_losing = min_advantage <= -200

    if had_advantage and was_losing:
        tension_text = "Wild game. You were winning at one point, then losing. Back and forth."
    elif had_advantage:
        tension_text = "You had a big advantage in the middlegame. The game was yours to win."
    elif was_losing:
        tension_text = "You were struggling most of the middlegame. Tough position to play."
    elif mid_blunders:
        tension_text = f"The middlegame is where it went wrong. {len(mid_blunders)} big mistake{'s' if len(mid_blunders) > 1 else ''}."
    else:
        tension_text = "Close fight in the middlegame. Nobody had a clear edge."

    # --- Climax: the turning point ---
    # Find the single most impactful user mistake
    biggest = max(user_moves, key=lambda m: m["cp_loss"]) if user_moves else None
    climax_move = biggest if biggest and biggest["cp_loss"] >= 100 else None

    if climax_move:
        phase = _phase_label(climax_move["phase"])
        climax_text = f"Move {climax_move['move_number']} in {phase} changed everything."
    elif user_won:
        climax_text = "No single big moment. You just outplayed them move by move."
    elif is_draw:
        climax_text = "Nobody found the breakthrough. Even game throughout."
    else:
        climax_text = "No one big blunder. You just slowly lost ground."

    # --- Resolution ---
    if user_won and climax_move and climax_move["cp_loss"] >= 150:
        resolution_text = f"You won, but that mistake at move {climax_move['move_number']} could cost you against better players."
    elif user_won:
        resolution_text = f"Clean win against {opponent}. Well done."
    elif is_draw:
        resolution_text = "Draw. Could you have pushed harder at some point?"
    else:
        # Check termination
        termination = game.get("termination", "")
        if "time" in termination.lower():
            resolution_text = "You ran out of time. Work on using your clock better."
        elif "resign" in termination.lower():
            resolution_text = "You resigned. Was it really over though?"
        else:
            resolution_text = f"You lost to {opponent}. What's the one thing to fix?"

    # Arc type classification
    if user_won and not climax_move:
        arc_type = "dominant"
    elif user_won and climax_move:
        arc_type = "scrappy_win"
    elif is_draw:
        arc_type = "stalemate"
    elif had_advantage:
        arc_type = "thrown"
    elif not mid_blunders and biggest and biggest["cp_loss"] < 100:
        arc_type = "outplayed"
    else:
        arc_type = "collapsed"

    return {
        "opening": opening_text,
        "tension": tension_text,
        "climax": climax_text,
        "resolution": resolution_text,
        "arc_type": arc_type,
        "opponent": opponent,
        "opening_name": opening_name,
        "user_won": user_won,
        "is_draw": is_draw,
    }


# ─── 2. THE MIRROR ──────────────────────────────────────────────

def compute_mirror(
    game_story: Dict,
    game_summary_diagnosis: str,
    identity_doc: Optional[Dict],
    pattern_counts: Dict,
    total_recent_games: int,
) -> Dict:
    """
    What this game reveals about the player as a person.
    Not "you missed Nf5" — but "you play scared when you're ahead."
    """
    diagnosis = game_summary_diagnosis
    arc_type = game_story.get("arc_type", "unknown")

    # Build personality observation based on diagnosis + arc
    personality_observations = {
        ("THROW", "thrown"): "When you're winning, you get careful instead of staying sharp. You slow down, play safe, and the win slips away.",
        ("THROW", "scrappy_win"): "You almost threw this one. When you're ahead, you relax too early. Stay sharp till the end.",
        ("MATE_BLIND", None): "You forgot to check what your opponent was doing. Before every move: look at what THEY want to do first.",
        ("SLOW_BLEED", "outplayed"): "No big mistake, but your opponent had a plan and you didn't. Small errors added up. Think about WHAT you want to do each move.",
        ("OPENING_COLLAPSE", None): "You got lost early. After the first few moves, you didn't know what to do. Learn the IDEAS of your opening, not just the moves.",
        ("PIECE_GIVEAWAY", None): "You left a piece hanging. Before you move, ask: is my piece safe where it's going? Takes 2 seconds.",
        ("TACTICAL_MISS", None): "There was a winning move and you didn't see it. The good news: this gets better with practice. Do some puzzles.",
        ("TIME_COLLAPSE", None): "You played well, then ran out of time and everything fell apart. Spend your time on the hard moves, not the easy ones.",
        ("WON_CLEAN", "dominant"): "This is your best chess. You had a plan, you stuck to it, and you won. Remember how this feels.",
        ("WON_OPPONENT_BLUNDER", None): "You won because your opponent messed up, not because you played great. Be honest — would you win this again?",
        ("DRAW", None): "A draw. Not bad, but was there a moment where you could have pushed harder?",
    }

    # Try exact match first, then diagnosis-only
    observation = personality_observations.get((diagnosis, arc_type))
    if not observation:
        observation = personality_observations.get((diagnosis, None))
    if not observation:
        observation = "This game showed something about how you think under pressure. Take a moment to reflect on the key decision."

    # Cross-game pattern insight
    pattern_insight = ""
    count = pattern_counts.get(diagnosis, 0)
    if count >= 3:
        pattern_insight = f"This happened {count} times in your last {total_recent_games} games. It's a habit now, not a one-time thing."
    elif count == 2:
        pattern_insight = "This happened before. One more time and it's a pattern."
    elif count == 1:
        pattern_insight = "First time this showed up. Let's keep it that way."

    # Identity anchors from player identity doc
    style = "developing"
    strength = ""
    weakness = ""
    if identity_doc:
        style = identity_doc.get("play_style", identity_doc.get("style_profile", {}).get("primary_style", "developing"))
        strengths = identity_doc.get("strengths", [])
        if strengths:
            strength = strengths[0] if isinstance(strengths[0], str) else strengths[0].get("name", "")
        taxonomy = identity_doc.get("blunder_taxonomy", {})
        if isinstance(taxonomy, dict):
            by_type = taxonomy.get("by_type", taxonomy)
            if by_type and isinstance(by_type, dict):
                worst = max(by_type.items(), key=lambda x: x[1], default=("", 0))
                weakness = _readable_blunder_type(worst[0]) if worst[1] > 0 else ""

    return {
        "observation": observation,
        "pattern_insight": pattern_insight,
        "pattern_count": count,
        "total_games": total_recent_games,
        "style": style,
        "strength": strength,
        "weakness": weakness,
    }


# ─── 3. THE MOMENT ──────────────────────────────────────────────

def compute_critical_moments(
    move_evaluations: List[Dict],
    user_color: str,
    max_moments: int = 3,
) -> List[Dict]:
    """
    The 2-3 decisions that defined the game.
    Not every mistake — just the DEFINING ones.
    For each: WHAT happened, WHY they decided this way, and the ROOT CAUSE.
    """
    user_is_white = user_color == "white"
    total = len(move_evaluations)

    user_mistakes = []
    for i, m in enumerate(move_evaluations):
        is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        if not is_user:
            continue
        cp_loss = m.get("cp_loss", 0)
        if cp_loss < 80:
            continue

        move_number = (i // 2) + 1
        phase = _move_phase(i, total)

        # Detect what kind of thinking error this was
        thinking_error = _diagnose_thinking_error(m, i, move_evaluations, user_is_white)

        user_mistakes.append({
            "move_number": move_number,
            "move_san": m.get("san", m.get("move", "?")),
            "best_move": m.get("best_move", ""),
            "cp_loss": cp_loss,
            "eval_before": m.get("eval_before", 0),
            "eval_after": m.get("eval_after", 0),
            "fen_before": m.get("fen_before", ""),
            "phase": phase,
            "move_uci": m.get("move_uci", ""),
            "best_move_uci": m.get("best_move_uci", ""),
            "thinking_error": thinking_error,
            "half_move_index": i,
        })

    # Sort by impact (cp_loss), take top N
    user_mistakes.sort(key=lambda m: m["cp_loss"], reverse=True)
    top = user_mistakes[:max_moments]

    # Re-sort by move number for chronological presentation
    top.sort(key=lambda m: m["move_number"])

    return top


def _diagnose_thinking_error(move: Dict, index: int, all_evals: List[Dict], user_is_white: bool) -> Dict:
    """
    Figure out WHY the player made this decision. Not WHAT was wrong — but the THINKING error.
    """
    cp_loss = move.get("cp_loss", 0)
    eval_before = move.get("eval_before", 0)
    user_eval = eval_before if user_is_white else -eval_before

    # Was the player winning?
    was_winning = user_eval >= 200
    was_losing = user_eval <= -200
    was_equal = not was_winning and not was_losing

    # Check previous move for context
    prev_cp_loss = 0
    if index >= 2:
        prev = all_evals[index - 2]  # 2 back = previous user move
        prev_cp_loss = prev.get("cp_loss", 0)

    # Analyze the position for clues
    threat_info = move.get("threat", "")
    best_move = move.get("best_move", "")

    # Detect thinking error category
    if cp_loss >= 5000:
        return {
            "type": "tunnel_vision",
            "label": "Didn't look at opponent's move",
            "description": "You were thinking about YOUR plan and forgot to check what they're doing. Always look at their last move first.",
            "root_cause": "focus_on_own_plan",
        }

    if was_winning and cp_loss >= 200:
        if prev_cp_loss >= 50:
            return {
                "type": "frustration_spiral",
                "label": "Mistake after mistake",
                "description": "One bad move led to another. When you mess up, take a breath. Don't try to fix it immediately — just play solid.",
                "root_cause": "emotional_recovery",
            }
        return {
            "type": "complacency",
            "label": "Got lazy when ahead",
            "description": "You were winning and stopped being careful. Winning doesn't mean you can relax. Stay focused till the end.",
            "root_cause": "concentration_in_winning_position",
        }

    if was_losing and cp_loss >= 150:
        return {
            "type": "desperation",
            "label": "Panicked when losing",
            "description": "You were behind and tried something risky. When you're losing, play your best solid move — don't gamble.",
            "root_cause": "emotional_decision_under_pressure",
        }

    if was_equal and cp_loss >= 200:
        # Check if it's a tactical miss
        if threat_info or (best_move and any(c in best_move.lower() for c in ['x', '+'])):
            return {
                "type": "tactical_blindness",
                "label": "Missed a winning move",
                "description": "There was a strong move and you didn't see it. Puzzles help with this — do a few every day.",
                "root_cause": "pattern_recognition_gap",
            }
        return {
            "type": "no_plan",
            "label": "No plan, just moved",
            "description": "You didn't know what to do so you just played something. Next time, ask yourself: what's the most important thing in this position?",
            "root_cause": "strategic_thinking",
        }

    if cp_loss >= 100:
        total = len(all_evals)
        if index > total * 0.75:
            return {
                "type": "fatigue",
                "label": "Tired at the end",
                "description": "You played well early but lost focus near the end. Save your energy for the important moments.",
                "root_cause": "stamina",
            }

    # Default
    return {
        "type": "inaccuracy",
        "label": "Small slip",
        "description": "A small mistake. Not a big deal on its own, but these add up over a game.",
        "root_cause": "experience",
    }


# ─── 4. THE TAKEAWAY ────────────────────────────────────────────

def compute_takeaway(
    game_story: Dict,
    mirror: Dict,
    critical_moments: List[Dict],
    diagnosis: str,
) -> Dict:
    """
    ONE sentence the player carries into their next game. A mantra.
    """
    # Map diagnosis to memorable mantras — short, sticky, easy to remember
    mantras = {
        "THROW": "When you're winning: stay sharp, don't coast.",
        "MATE_BLIND": "Before you move, check: what is my opponent threatening?",
        "SLOW_BLEED": "No obvious move? Ask: what's the most important square right now?",
        "OPENING_COLLAPSE": "Learn WHY you play each opening move, not just the move itself.",
        "PIECE_GIVEAWAY": "Before moving: is my piece safe where it's going?",
        "TACTICAL_MISS": "When it feels tense, slow down. Check every capture and every check.",
        "TIME_COLLAPSE": "Use your time on the hard moves, not the first 5 moves.",
        "WON_CLEAN": "This is your real level. Remember how this felt.",
        "WON_OPPONENT_BLUNDER": "You got lucky. What if they hadn't blundered?",
        "DRAW": "Before accepting a draw: did you really try to win?",
    }

    mantra = mantras.get(diagnosis, "Every game teaches you something. What did this one teach you?")

    # If we have critical moments, add context
    primary_error = None
    if critical_moments:
        primary = critical_moments[0]
        primary_error = primary.get("thinking_error", {})

    return {
        "mantra": mantra,
        "primary_thinking_error": primary_error.get("type") if primary_error else None,
        "focus_area": primary_error.get("root_cause") if primary_error else None,
    }


# ─── 5. THE PROOF ───────────────────────────────────────────────

async def compute_proof(
    db,
    user_id: str,
    current_game_id: str,
    diagnosis: str,
) -> Dict:
    """
    What's getting better? Honest encouragement based on data.
    """
    # Get recent game analyses
    recent = []
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1, "stockfish_analysis": 1, "created_at": 1}
    ).sort("created_at", -1).limit(20)
    async for doc in cursor:
        recent.append(doc)

    if len(recent) < 3:
        return {
            "has_enough_data": False,
            "message": "Play a few more games and I'll show your progress.",
            "improvements": [],
            "still_working_on": [],
        }

    # Split into recent 5 vs previous 10
    recent_5 = recent[:5]
    older = recent[5:15]

    if not older:
        return {
            "has_enough_data": False,
            "message": "Keep playing. I need a few more games to track trends.",
            "improvements": [],
            "still_working_on": [],
        }

    # Compare blunder rates
    def _blunder_rate(analyses):
        total_blunders = 0
        total_games = len(analyses)
        for a in analyses:
            sf = a.get("stockfish_analysis", {})
            total_blunders += sf.get("blunders", 0)
        return total_blunders / total_games if total_games else 0

    def _avg_accuracy(analyses):
        total = 0
        count = 0
        for a in analyses:
            acc = a.get("stockfish_analysis", {}).get("accuracy")
            if acc:
                total += acc
                count += 1
        return total / count if count else 0

    recent_blunder_rate = _blunder_rate(recent_5)
    older_blunder_rate = _blunder_rate(older)
    recent_accuracy = _avg_accuracy(recent_5)
    older_accuracy = _avg_accuracy(older)

    improvements = []
    still_working = []

    # Blunder rate comparison
    if recent_blunder_rate < older_blunder_rate * 0.7:
        improvements.append({
            "area": "Fewer blunders",
            "detail": f"Blunders down from {older_blunder_rate:.1f} to {recent_blunder_rate:.1f} per game. Nice.",
        })
    elif recent_blunder_rate > older_blunder_rate * 1.3:
        still_working.append({
            "area": "Blunders going up",
            "detail": f"More blunders lately ({recent_blunder_rate:.1f} vs {older_blunder_rate:.1f}). Slow down.",
        })

    # Accuracy comparison
    if recent_accuracy > older_accuracy + 3:
        improvements.append({
            "area": "Better accuracy",
            "detail": f"Accuracy up from {older_accuracy:.0f}% to {recent_accuracy:.0f}%. You're getting sharper.",
        })
    elif older_accuracy > recent_accuracy + 3:
        still_working.append({
            "area": "Accuracy dropped",
            "detail": f"Accuracy went from {older_accuracy:.0f}% to {recent_accuracy:.0f}%. Rushing?",
        })

    # Opening play comparison
    def _opening_mistakes(analyses):
        total = 0
        count = len(analyses)
        for a in analyses:
            evals = a.get("stockfish_analysis", {}).get("move_evaluations", [])
            for m in evals[:20]:  # First 10 full moves
                if m.get("cp_loss", 0) >= 100:
                    total += 1
        return total / count if count else 0

    recent_opening = _opening_mistakes(recent_5)
    older_opening = _opening_mistakes(older)

    if recent_opening < older_opening * 0.6 and older_opening > 0.5:
        improvements.append({
            "area": "Opening play",
            "detail": "Your openings are getting cleaner. The early mistakes are decreasing.",
        })

    # Build encouraging message
    if improvements and not still_working:
        message = "You're getting better. The numbers show it."
    elif improvements and still_working:
        message = "Some things are improving, some need work. That's normal."
    elif still_working:
        message = "Tough stretch. But you know what to work on — that matters."
    else:
        message = "Steady play. No big changes — you're consistent."

    return {
        "has_enough_data": True,
        "message": message,
        "improvements": improvements,
        "still_working_on": still_working,
        "recent_accuracy": round(recent_accuracy, 1),
        "older_accuracy": round(older_accuracy, 1),
    }


# ─── LLM NARRATIVE LAYER ────────────────────────────────────────

async def generate_coach_narrative(
    story: Dict,
    mirror: Dict,
    moments: List[Dict],
    takeaway: Dict,
    proof: Dict,
    user_rating: int,
    call_llm_func,
) -> Optional[Dict]:
    """
    Uses LLM to transform the structured data into memorable coaching language.
    This is the LANGUAGE layer — all chess logic is already computed.
    """
    if not call_llm_func:
        return None

    try:
        system_msg = "You are a friendly chess coach talking to your student after a game. Write like you're texting a friend — super simple, no fancy words. Return ONLY valid JSON. No markdown."

        user_msg = f"""STUDENT: Rating ~{user_rating}, style: {mirror.get('style', 'developing')}

WHAT HAPPENED:
- Opening: {story.get('opening', '')}
- Middle: {story.get('tension', '')}
- Key moment: {story.get('climax', '')}
- End: {story.get('resolution', '')}

ABOUT THEM: {mirror.get('observation', '')}
PATTERN: {mirror.get('pattern_insight', '')}

MISTAKES ({len(moments)}):
"""
        for i, m in enumerate(moments):
            te = m.get("thinking_error", {})
            user_msg += f"  {i+1}. Move {m['move_number']}: {te.get('label', '?')} — {te.get('description', '')}\n"

        user_msg += f"""
MANTRA: {takeaway.get('mantra', '')}

Write a coaching review as JSON. Use DEAD SIMPLE English — like talking to a 12 year old. Short sentences. No big words.

{{
  "story_narrative": "What happened in this game in 2 simple sentences. Like telling a buddy.",
  "mirror_narrative": "What this says about how they play. 2 short sentences. Personal, not generic.",
  "moment_insights": ["One simple sentence per mistake — WHY they made it, not what was better."],
  "takeaway_refined": "One short sentence to remember before next game. Easy to repeat in your head.",
  "encouragement": "One warm sentence about something good."
}}

RULES:
- NO chess moves (no Nf5, no e4)
- NO numbers or percentages
- Talk like a friend, not a teacher
- Max 12 words per sentence
- Simple words only"""

        raw = await call_llm_func(system_msg, user_msg)
        if not raw:
            return None

        # Try to parse JSON from response
        import json
        import re
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
        return None

    except Exception as e:
        logger.error(f"Coach narrative LLM failed: {e}")
        return None


# ─── MAIN ENTRY POINT ───────────────────────────────────────────

async def generate_coach_review(
    db,
    game: Dict,
    analysis: Dict,
    user_id: str,
    user_color: str,
    call_llm_func=None,
) -> Dict:
    """
    Generate the complete "Human Coach" review for a game.
    Returns the 5-section structure.
    """
    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    result = game.get("result", "")

    # Get user rating
    user_rating = 0
    if user_color == "white":
        user_rating = game.get("white_rating") or game.get("user_rating") or 0
    else:
        user_rating = game.get("black_rating") or game.get("user_rating") or 0
    if not user_rating:
        import re as _re
        pgn = game.get("pgn", "")
        elo_tag = "WhiteElo" if user_color == "white" else "BlackElo"
        m = _re.search(rf'\[{elo_tag} "(\d+)"\]', pgn)
        if m:
            user_rating = int(m.group(1))

    # Get diagnosis from existing coach summary
    from services.game_coach_summary import compute_game_summary
    opening_name = game.get("opening_name") or game.get("opening") or ""
    summary = compute_game_summary(evals, result, user_color, opening_name)
    diagnosis = summary.get("diagnosis", "UNKNOWN")

    # Get player identity
    identity_doc = await db.player_identity.find_one({"user_id": user_id}, {"_id": 0})

    # Count patterns across recent games
    recent_analyses = []
    cursor = db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "stockfish_analysis": 1, "game_id": 1}
    ).sort("created_at", -1).limit(30)
    async for doc in cursor:
        recent_analyses.append(doc)

    pattern_counts = _count_pattern_occurrences(recent_analyses, user_color)
    total_games = len(recent_analyses) or 1

    # 1. THE STORY
    story = compute_game_story(evals, game, user_color)

    # 2. THE MIRROR
    mirror = compute_mirror(story, diagnosis, identity_doc, pattern_counts, total_games)

    # 3. THE MOMENT
    moments = compute_critical_moments(evals, user_color, max_moments=3)

    # 4. THE TAKEAWAY
    takeaway = compute_takeaway(story, mirror, moments, diagnosis)

    # 5. THE PROOF
    proof = await compute_proof(db, user_id, game.get("game_id", ""), diagnosis)

    # LLM narrative layer — cached in DB so we only call LLM once per game
    llm_narrative = None
    game_id = game.get("game_id", "")

    # Check cache first
    cached = await db.coach_reviews.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "llm_narrative": 1}
    )
    if cached and cached.get("llm_narrative"):
        llm_narrative = cached["llm_narrative"]
    elif call_llm_func:
        llm_narrative = await generate_coach_narrative(
            story, mirror, moments, takeaway, proof,
            user_rating or 1200, call_llm_func
        )
        # Cache it
        if llm_narrative:
            try:
                from datetime import datetime, timezone
                await db.coach_reviews.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {
                        "llm_narrative": llm_narrative,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
            except Exception as cache_err:
                logger.warning(f"Failed to cache coach review: {cache_err}")

    return {
        "story": story,
        "mirror": mirror,
        "moments": moments,
        "takeaway": takeaway,
        "proof": proof,
        "diagnosis": diagnosis,
        "user_rating": user_rating,
        "llm_narrative": llm_narrative,
    }


# ─── HELPER FUNCTIONS ────────────────────────────────────────────

def _count_pattern_occurrences(analyses: List[Dict], user_color: str) -> Dict:
    """Count how many games had each diagnosis type."""
    counts = {}
    for a in analyses:
        sf = a.get("stockfish_analysis", {})
        evals = sf.get("move_evaluations", [])
        if not evals:
            continue
        # We need game result — try to infer from evals or skip
        # This is a simplified pattern counter
        user_moves = []
        user_is_white = user_color == "white"
        for i, m in enumerate(evals):
            is_user = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
            if is_user:
                user_moves.append(m)

        total_loss = sum(m.get("cp_loss", 0) for m in user_moves)
        blunders = [m for m in user_moves if m.get("cp_loss", 0) >= 200]
        was_winning = any(m.get("eval_before", 0) >= 300 for m in user_moves) if user_is_white else any(-(m.get("eval_before", 0)) >= 300 for m in user_moves)

        # Simplified classification
        if any(m.get("cp_loss", 0) >= 5000 for m in user_moves):
            diag = "MATE_BLIND"
        elif was_winning and blunders:
            diag = "THROW"
        elif blunders:
            diag = "TACTICAL_MISS"
        elif total_loss > 500 and not blunders:
            diag = "SLOW_BLEED"
        else:
            diag = "OTHER"

        counts[diag] = counts.get(diag, 0) + 1

    return counts


def _readable_blunder_type(bt: str) -> str:
    readable = {
        "missed_fork": "missing forks",
        "missed_pin": "missing pins",
        "hanging_piece": "leaving pieces hanging",
        "king_safety_neglect": "king safety",
        "time_trouble_blunder": "time trouble",
        "impulse_move": "impulsive moves",
        "winning_position_collapse": "collapsing in winning positions",
        "opening_principle_violated": "opening mistakes",
        "calculation_error": "calculation",
        "post_blunder_tilt": "tilting after mistakes",
    }
    return readable.get(bt, bt.replace("_", " "))


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
