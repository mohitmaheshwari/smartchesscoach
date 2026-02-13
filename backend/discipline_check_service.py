"""
Discipline Check Service - Sharp, Data-Driven Analysis of Last Game

This is NOT a "coach review" with soft language. It's a ruthless accountability check:
- Did you follow the app's advice?
- Did you maintain composure when winning?
- Evidence-based verdicts, no fluff

Architecture:
- ALL metrics are DETERMINISTIC (calculated from game data)
- NO LLM for analysis - only for the final verdict summary (optional)
- Compact, card-based output
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def calculate_decision_stability(move_evaluations: List[Dict], user_color: str) -> Dict:
    """
    Decision Stability After Advantage:
    When you're winning (eval >= +2.0), how often do you maintain that advantage?
    
    Returns:
        {
            "score": 0-100 (percentage of moves that maintained advantage),
            "sample_size": number of moves analyzed,
            "collapses": number of times advantage was squandered,
            "collapse_positions": list of positions where collapse happened
        }
    """
    if not move_evaluations:
        return {"score": None, "sample_size": 0, "collapses": 0, "collapse_positions": []}
    
    # Filter for user's moves only based on move number and color
    user_moves = []
    for m in move_evaluations:
        move_num = m.get("move_number", 0)
        # White moves are odd (1, 3, 5...), Black moves are even (2, 4, 6...)
        is_white_move = (move_num % 2 == 1)
        if (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move):
            user_moves.append(m)
    
    # Find moves where user was winning (eval >= 200 centipawns = +2.0)
    winning_positions = []
    for m in user_moves:
        eval_before = m.get("eval_before", 0)
        # Normalize for black (black wants negative eval)
        if user_color == "black":
            eval_before = -eval_before
        
        if eval_before >= 200:  # +2.0 or better
            winning_positions.append(m)
    
    if len(winning_positions) < 3:
        return {"score": None, "sample_size": len(winning_positions), "collapses": 0, "collapse_positions": []}
    
    # Count collapses (losing significant advantage after a winning position)
    collapses = 0
    collapse_positions = []
    
    for m in winning_positions:
        cp_loss = m.get("cp_loss", 0)
        classification = m.get("classification", "")
        
        # A "collapse" is a significant blunder when winning
        if cp_loss >= 150 or classification in ["blunder", "mistake"]:
            collapses += 1
            collapse_positions.append({
                "move_number": m.get("move_number"),
                "move": m.get("move"),
                "fen_before": m.get("fen_before"),
                "cp_loss": cp_loss,
                "eval_before": m.get("eval_before"),
                "best_move": m.get("best_move")
            })
    
    # Score = percentage of winning positions where advantage was maintained
    stable_count = len(winning_positions) - collapses
    score = round((stable_count / len(winning_positions)) * 100)
    
    return {
        "score": score,
        "sample_size": len(winning_positions),
        "collapses": collapses,
        "collapse_positions": collapse_positions[:3]  # Limit evidence
    }


def check_opening_compliance(game: Dict, opening_guidance: Dict) -> Dict:
    """
    Did the user play an opening we suggested?
    
    Returns:
        {
            "complied": True/False/None (None if no suggestion),
            "played": "Italian Game",
            "suggested": ["Italian Game", "Ruy Lopez"],
            "paused_and_played": True if they played an opening we told them to avoid,
            "verdict": "FOLLOWED" | "IGNORED" | "NEUTRAL"
        }
    """
    import re
    
    # Extract opening from PGN
    pgn = game.get("pgn", "")
    opening_name = "Unknown"
    
    # Try ECOUrl first - extract only the last part of the path
    eco_match = re.search(r'\[ECOUrl "[^"]+/([^/"]+)"\]', pgn)
    if eco_match:
        # Get the last segment after the final slash
        opening_name = eco_match.group(1).replace("-", " ").title()
    
    # Fallback to Opening tag
    if opening_name == "Unknown" or "Www." in opening_name:
        opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
        if opening_match:
            opening_name = opening_match.group(1)
    
    # Final cleanup - remove any URL artifacts
    if "/" in opening_name or "Www" in opening_name:
        # Try to extract from ECO tag as fallback
        eco_code_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
        if eco_code_match:
            opening_name = f"Opening {eco_code_match.group(1)}"
        else:
            opening_name = "Standard Opening"
    
    user_color = game.get("user_color", "white")
    
    # Get suggestions for this color
    color_key = "as_white" if user_color == "white" else "as_black"
    guidance = opening_guidance.get(color_key, {})
    
    working_well = [o.get("name", "") for o in guidance.get("working_well", [])]
    pause_for_now = [o.get("name", "") for o in guidance.get("pause_for_now", [])]
    
    # Check compliance
    played_suggested = any(
        sug.lower() in opening_name.lower() or opening_name.lower() in sug.lower()
        for sug in working_well
    ) if working_well else None
    
    played_paused = any(
        p.lower() in opening_name.lower() or opening_name.lower() in p.lower()
        for p in pause_for_now
    ) if pause_for_now else False
    
    # Determine verdict
    if played_paused:
        verdict = "IGNORED"
        complied = False
    elif played_suggested:
        verdict = "FOLLOWED"
        complied = True
    elif working_well:  # We had suggestions but they played something else
        verdict = "NEUTRAL"
        complied = None
    else:
        verdict = "NEUTRAL"
        complied = None
    
    return {
        "complied": complied,
        "played": opening_name,
        "suggested": working_well[:2],
        "paused": pause_for_now[:2],
        "paused_and_played": played_paused,
        "verdict": verdict
    }


def calculate_blunder_context(move_evaluations: List[Dict], user_color: str) -> Dict:
    """
    Analyze WHEN blunders happened:
    - Were you winning, equal, or losing when you blundered?
    - This reveals if the issue is "relaxing when winning" vs "panicking when losing"
    
    Returns:
        {
            "when_winning": count,
            "when_equal": count,
            "when_losing": count,
            "total_blunders": count,
            "primary_trigger": "winning" | "losing" | "equal" | "none"
        }
    """
    if not move_evaluations:
        return {
            "when_winning": 0, "when_equal": 0, "when_losing": 0,
            "total_blunders": 0, "primary_trigger": "none"
        }
    
    when_winning = 0
    when_equal = 0
    when_losing = 0
    
    for m in move_evaluations:
        # Check if this was user's move
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if not is_user_move:
            continue
        
        classification = m.get("classification", "")
        if classification not in ["blunder", "mistake"]:
            continue
        
        eval_before = m.get("eval_before", 0)
        # Normalize for black
        if user_color == "black":
            eval_before = -eval_before
        
        # Categorize
        if eval_before >= 150:  # +1.5 or better = winning
            when_winning += 1
        elif eval_before <= -150:  # -1.5 or worse = losing
            when_losing += 1
        else:
            when_equal += 1
    
    total = when_winning + when_equal + when_losing
    
    # Determine primary trigger
    if total == 0:
        primary_trigger = "none"
    elif when_winning >= when_losing and when_winning >= when_equal:
        primary_trigger = "winning"
    elif when_losing >= when_winning and when_losing >= when_equal:
        primary_trigger = "losing"
    else:
        primary_trigger = "equal"
    
    return {
        "when_winning": when_winning,
        "when_equal": when_equal,
        "when_losing": when_losing,
        "total_blunders": total,
        "primary_trigger": primary_trigger
    }


def did_reach_winning_position(move_evaluations: List[Dict], user_color: str) -> Dict:
    """
    Did you ever reach a winning position (+2.0 or better)?
    
    Returns:
        {
            "reached": True/False,
            "peak_advantage": highest eval reached (in pawns),
            "peak_move": move number where peak was reached,
            "converted": True if game was won, False if advantage was squandered
        }
    """
    if not move_evaluations:
        return {"reached": False, "peak_advantage": 0, "peak_move": None, "converted": None}
    
    peak_eval = 0
    peak_move = None
    
    for m in move_evaluations:
        eval_after = m.get("eval_after", 0)
        # Normalize for black
        if user_color == "black":
            eval_after = -eval_after
        
        if eval_after > peak_eval:
            peak_eval = eval_after
            peak_move = m.get("move_number")
    
    reached_winning = peak_eval >= 200  # +2.0 pawns
    
    return {
        "reached": reached_winning,
        "peak_advantage": round(peak_eval / 100, 1),  # Convert to pawns
        "peak_move": peak_move,
        "converted": None  # Will be set by caller based on game result
    }


def generate_verdict(
    stability: Dict,
    opening_check: Dict,
    blunder_context: Dict,
    winning_position: Dict,
    game_result: str,
    accuracy: float
) -> Dict:
    """
    Generate the final verdict - sharp, evidence-based, no fluff.
    
    Returns:
        {
            "headline": "You collapsed under pressure" | "Clean execution" | etc,
            "detail": One specific sentence with evidence,
            "grade": "A" | "B" | "C" | "D" | "F",
            "tone": "positive" | "neutral" | "critical"
        }
    """
    
    issues = []
    positives = []
    
    # Check opening compliance
    if opening_check.get("paused_and_played"):
        issues.append(f"Played {opening_check['played']} despite being told to avoid it")
    elif opening_check.get("complied") is True:
        positives.append("Followed opening guidance")
    
    # Check stability
    stability_score = stability.get("score")
    if stability_score is not None:
        if stability_score < 50:
            issues.append(f"Only {stability_score}% decision stability when winning")
        elif stability_score >= 80:
            positives.append(f"{stability_score}% stability when ahead")
    
    # Check blunder pattern
    primary_trigger = blunder_context.get("primary_trigger", "none")
    total_blunders = blunder_context.get("total_blunders", 0)
    
    if total_blunders > 0:
        if primary_trigger == "winning":
            when_winning = blunder_context.get("when_winning", 0)
            issues.append(f"{when_winning}/{total_blunders} blunders happened when winning")
        elif primary_trigger == "losing":
            when_losing = blunder_context.get("when_losing", 0)
            issues.append(f"{when_losing}/{total_blunders} blunders happened under pressure")
    elif total_blunders == 0:
        positives.append("Zero blunders")
    
    # Check conversion
    if winning_position.get("reached"):
        peak = winning_position.get("peak_advantage", 0)
        if game_result == "win":
            positives.append(f"Converted +{peak} advantage")
        elif game_result == "loss":
            issues.append(f"Had +{peak} advantage but lost")
        elif game_result == "draw":
            if peak >= 3:
                issues.append(f"Drew from +{peak} position")
    
    # Generate headline and grade
    if len(issues) == 0 and accuracy >= 80:
        headline = "Clean execution"
        grade = "A"
        tone = "positive"
    elif len(issues) == 0:
        headline = "Solid game, room to grow"
        grade = "B"
        tone = "positive"
    elif opening_check.get("paused_and_played"):
        headline = "Ignored opening advice"
        grade = "D" if game_result != "win" else "C"
        tone = "critical"
    elif stability_score is not None and stability_score < 50:
        headline = "Collapsed when winning"
        grade = "D"
        tone = "critical"
    elif primary_trigger == "winning" and blunder_context.get("when_winning", 0) >= 2:
        headline = "Lost focus when ahead"
        grade = "C"
        tone = "critical"
    elif total_blunders >= 3:
        headline = "Too many errors"
        grade = "D"
        tone = "critical"
    else:
        headline = "Mixed signals"
        grade = "C"
        tone = "neutral"
    
    # Build detail sentence
    if issues:
        detail = issues[0]  # Most important issue
    elif positives:
        detail = positives[0]
    else:
        detail = f"Accuracy: {accuracy}%"
    
    return {
        "headline": headline,
        "detail": detail,
        "grade": grade,
        "tone": tone,
        "issues": issues,
        "positives": positives
    }


async def get_discipline_check(db, user_id: str) -> Dict:
    """
    Main entry point for the Discipline Check feature.
    
    Returns a PERSONALIZED, data-driven assessment that:
    - References our guidance (openings we suggested, patterns we identified)
    - Celebrates when they follow advice
    - Connects to their #1 weakness (Rating Killer)
    - Adapts tone based on game quality
    
    If the most recent game is NOT analyzed yet, returns a pending state.
    """
    import re
    
    # 1. Get user's MOST RECENT game (regardless of analysis status)
    most_recent_game = await db.games.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("imported_at", -1)]
    )
    
    if not most_recent_game:
        return {"has_data": False, "reason": "no_games"}
    
    # Check if most recent game is analyzed
    most_recent_is_analyzed = most_recent_game.get("is_analyzed", False)
    
    # If most recent game is NOT analyzed, return pending state with basic info
    if not most_recent_is_analyzed:
        game_id = most_recent_game.get("game_id")
        user_color = most_recent_game.get("user_color", "white")
        pgn = most_recent_game.get("pgn", "")
        result = most_recent_game.get("result", "*")
        
        # Determine game result
        if user_color == "white":
            game_result = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
        else:
            game_result = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
        
        # Get opponent name
        opponent = "Opponent"
        if user_color == "white":
            match = re.search(r'\[Black "([^"]+)"\]', pgn)
        else:
            match = re.search(r'\[White "([^"]+)"\]', pgn)
        if match:
            opponent = match.group(1)
        
        # Check if in analysis queue
        queue_item = await db.analysis_queue.find_one({"game_id": game_id})
        in_queue = queue_item is not None
        queue_status = queue_item.get("status", "pending") if queue_item else None
        
        # Generate appropriate message based on result
        if game_result == "win":
            pending_message = "Nice win! Let's see how clean it was once analysis is complete."
        elif game_result == "loss":
            pending_message = "Tough loss. Analysis will show what to work on."
        else:
            pending_message = "A draw - let's see if there were missed opportunities."
        
        return {
            "has_data": True,
            "analysis_pending": True,
            "in_queue": in_queue,
            "queue_status": queue_status,
            "game_id": game_id,
            "opponent": opponent,
            "game_result": game_result,
            "user_color": user_color,
            "pending_message": pending_message,
            "verdict": {
                "headline": "Analysis in Queue" if in_queue else "Queuing for Analysis",
                "tone": "neutral",
                "result_text": f"{'Won' if game_result == 'win' else 'Lost' if game_result == 'loss' else 'Drew'} vs {opponent}",
                "opening_line": None,
                "accuracy_line": "Calculating...",
                "blunders": None,
                "checklist": []
            }
        }
    
    # 2. Most recent game IS analyzed - use it
    last_game = most_recent_game
    game_id = last_game.get("game_id")
    user_color = last_game.get("user_color", "white")
    
    # 3. Get analysis for this game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not analysis:
        return {"has_data": False, "reason": "no_analysis"}
    
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evaluations = sf_analysis.get("move_evaluations", [])
    accuracy = sf_analysis.get("accuracy", 0)
    blunders = sf_analysis.get("blunders", 0)
    mistakes = sf_analysis.get("mistakes", 0)
    
    # 3. Get all games and analyses for context
    all_games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(200)
    
    all_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(200)
    
    # 4. Get opening guidance
    from blunder_intelligence_service import get_opening_guidance, get_dominant_weakness_ranking
    opening_guidance = get_opening_guidance(all_analyses, all_games)
    
    # 5. Get user's #1 weakness (Rating Killer) - THIS IS KEY FOR PERSONALIZATION
    weakness_data = get_dominant_weakness_ranking(all_analyses, all_games)
    top_weakness = weakness_data.get("weaknesses", [{}])[0] if weakness_data.get("weaknesses") else {}
    rating_killer_pattern = top_weakness.get("pattern", "")
    rating_killer_label = top_weakness.get("label", "")
    
    # 6. Calculate user's average accuracy (excluding this game)
    other_analyses = [a for a in all_analyses if a.get("game_id") != game_id]
    if other_analyses:
        avg_accuracy = sum(
            a.get("stockfish_analysis", {}).get("accuracy", 0) 
            for a in other_analyses
        ) / len(other_analyses)
    else:
        avg_accuracy = None
    
    # 7. Calculate deterministic metrics
    stability = calculate_decision_stability(move_evaluations, user_color)
    opening_check = check_opening_compliance(last_game, opening_guidance)
    blunder_context = calculate_blunder_context(move_evaluations, user_color)
    winning_position = did_reach_winning_position(move_evaluations, user_color)
    
    # Determine game result from user's perspective
    result = last_game.get("result", "*")
    if user_color == "white":
        game_result = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
    else:
        game_result = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
    
    winning_position["converted"] = game_result == "win" if winning_position["reached"] else None
    
    # 8. Check if they AVOIDED their #1 weakness in this game
    avoided_rating_killer = check_avoided_pattern(analysis, rating_killer_pattern)
    
    # 9. Generate PERSONALIZED verdict
    verdict = generate_personalized_verdict(
        stability, opening_check, blunder_context, winning_position,
        game_result, accuracy, avg_accuracy,
        rating_killer_pattern, rating_killer_label, avoided_rating_killer,
        blunders  # Pass actual stockfish blunder count
    )
    
    # 10. Extract opponent name from PGN
    import re
    pgn = last_game.get("pgn", "")
    opponent = "Opponent"
    if user_color == "white":
        match = re.search(r'\[Black "([^"]+)"\]', pgn)
    else:
        match = re.search(r'\[White "([^"]+)"\]', pgn)
    if match:
        opponent = match.group(1)
    
    return {
        "has_data": True,
        "game_id": game_id,
        "opponent": opponent,
        "result": game_result,
        "user_color": user_color,
        
        # Core metrics
        "metrics": {
            "accuracy": round(accuracy, 1),
            "avg_accuracy": round(avg_accuracy, 1) if avg_accuracy else None,
            "blunders": blunders,
            "mistakes": mistakes,
            "decision_stability": stability,
            "opening_compliance": opening_check,
            "blunder_context": blunder_context,
            "winning_position": winning_position
        },
        
        # Personalization context
        "personalization": {
            "rating_killer_pattern": rating_killer_pattern,
            "rating_killer_label": rating_killer_label,
            "avoided_rating_killer": avoided_rating_killer,
            "accuracy_vs_avg": round(accuracy - avg_accuracy, 1) if avg_accuracy else None
        },
        
        # The verdict - personalized and connected
        "verdict": verdict
    }


def check_avoided_pattern(analysis: Dict, pattern: str) -> bool:
    """
    Check if the user avoided their #1 weakness pattern in this game.
    
    Returns True if:
    - Pattern is about hanging pieces and they had zero hanging piece mistakes
    - Pattern is about blunders when winning and they didn't blunder when ahead
    - etc.
    """
    if not pattern:
        return None
    
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    blunders = sf_analysis.get("blunders", 0)
    
    pattern_lower = pattern.lower()
    
    # Check for common patterns
    if "hanging" in pattern_lower or "undefended" in pattern_lower:
        # Check if any blunder was a hanging piece
        hanging_blunders = [
            m for m in move_evals 
            if m.get("classification") == "blunder" and 
            ("hang" in str(m.get("mistake_type", "")).lower() or 
             "undefend" in str(m.get("mistake_type", "")).lower())
        ]
        return len(hanging_blunders) == 0
    
    elif "winning" in pattern_lower or "ahead" in pattern_lower or "advantage" in pattern_lower:
        # Check if they blundered when winning
        blunders_when_winning = [
            m for m in move_evals
            if m.get("classification") == "blunder" and m.get("eval_before", 0) >= 150
        ]
        return len(blunders_when_winning) == 0
    
    elif "fork" in pattern_lower or "pin" in pattern_lower or "tactic" in pattern_lower:
        # Check if they walked into tactics
        tactical_blunders = [
            m for m in move_evals
            if m.get("classification") == "blunder" and
            any(t in str(m.get("mistake_type", "")).lower() for t in ["fork", "pin", "skewer"])
        ]
        return len(tactical_blunders) == 0
    
    # Default: if zero blunders, they avoided the pattern
    return blunders == 0


def generate_personalized_verdict(
    stability: Dict,
    opening_check: Dict,
    blunder_context: Dict,
    winning_position: Dict,
    game_result: str,
    accuracy: float,
    avg_accuracy: float,
    rating_killer_pattern: str,
    rating_killer_label: str,
    avoided_rating_killer: bool,
    actual_blunders: int = 0,  # Actual stockfish blunder count
    actual_mistakes: int = 0   # Actual stockfish mistake count
) -> Dict:
    """
    Generate a PERSONALIZED, COACH-LIKE verdict.
    
    For WINS: Explain what worked well + what still needs improvement
    For LOSSES: Highlight good plays despite outcome + identify core problem
    
    No fluff - deterministic logic based on actual game data.
    """
    
    observations = []  # Personalized observations that show we're paying attention
    issues = []
    positives = []
    coach_feedback = {}  # Rich feedback for the coach section
    
    # === ANALYZE GAME QUALITY REGARDLESS OF RESULT ===
    
    # 1. Did they avoid their #1 pattern?
    if avoided_rating_killer is True and rating_killer_label:
        observations.append(f"No {rating_killer_label.lower()} mistakes this game")
        positives.append("Avoided your #1 pattern")
    elif avoided_rating_killer is False and rating_killer_label:
        observations.append(f"Your pattern showed up again: {rating_killer_label.lower()}")
    
    # 2. Opening compliance
    if opening_check.get("paused_and_played"):
        issues.append(f"Played {opening_check['played']} (we suggested pausing this)")
        observations.append(f"Tried {opening_check['played']} despite our advice")
    elif opening_check.get("complied") is True:
        positives.append(f"Played {opening_check['played']} as suggested")
        observations.append(f"Followed opening guidance with {opening_check['played']}")
    
    # 3. Accuracy vs their average
    if avg_accuracy:
        diff = accuracy - avg_accuracy
        if diff >= 5:
            positives.append(f"Above your usual {round(avg_accuracy)}%")
            observations.append(f"Accuracy up {round(diff)}% from your average")
        elif diff <= -10:
            issues.append(f"Below your usual {round(avg_accuracy)}%")
    
    # 4. Stability when ahead
    stability_score = stability.get("score")
    if stability_score is not None:
        if stability_score < 50:
            issues.append(f"Only {stability_score}% composure when winning")
        elif stability_score >= 80:
            positives.append(f"Held advantage well ({stability_score}% stable)")
    
    # 5. Blunder context
    primary_trigger = blunder_context.get("primary_trigger", "none")
    context_blunders = blunder_context.get("total_blunders", 0)
    
    if actual_blunders > 0:
        if context_blunders > 0 and primary_trigger == "winning":
            when_winning = blunder_context.get("when_winning", 0)
            issues.append(f"{when_winning}/{context_blunders} errors when ahead")
        elif context_blunders > 0 and primary_trigger == "losing":
            when_losing = blunder_context.get("when_losing", 0)
            issues.append(f"{when_losing}/{context_blunders} errors under pressure")
    elif actual_blunders == 0:
        positives.append("Zero blunders")
    
    # 6. Conversion
    if winning_position.get("reached"):
        peak = winning_position.get("peak_advantage", 0)
        if game_result == "win":
            positives.append(f"Converted +{peak} advantage")
        elif game_result == "loss":
            issues.append(f"Had +{peak} but lost")
    
    # === COACH-LIKE FEEDBACK BASED ON RESULT ===
    
    if game_result == "win":
        # WIN: What worked + what still needs work
        coach_feedback = _generate_win_feedback(
            accuracy, avg_accuracy, actual_blunders, actual_mistakes,
            stability, winning_position, avoided_rating_killer, 
            rating_killer_label, opening_check
        )
    elif game_result == "loss":
        # LOSS: Good plays despite outcome + core problem
        coach_feedback = _generate_loss_feedback(
            accuracy, avg_accuracy, actual_blunders, actual_mistakes,
            stability, winning_position, blunder_context, 
            rating_killer_label, avoided_rating_killer, opening_check
        )
    else:  # draw
        coach_feedback = _generate_draw_feedback(
            accuracy, avg_accuracy, actual_blunders, actual_mistakes,
            stability, winning_position
        )
    
    # === GENERATE HEADLINE AND GRADE ===
    
    if game_result == "win":
        if len(issues) == 0 and accuracy >= 80:
            headline = "Clean win - you played well"
            grade = "A"
            tone = "positive"
        elif len(issues) == 0:
            headline = "Nice win, some room to grow"
            grade = "B"
            tone = "positive"
        elif actual_blunders >= 2:
            headline = "You won, but got lucky"
            grade = "C"
            tone = "neutral"
        else:
            headline = "Win secured, lessons learned"
            grade = "B"
            tone = "positive"
        show_rating_killer = len(issues) > 0
    
    elif game_result == "loss":
        if avoided_rating_killer and actual_blunders <= 1 and accuracy >= 70:
            headline = "Tough loss, but you played solid"
            grade = "B"
            tone = "neutral"
        elif avoided_rating_killer is False:
            headline = "Same pattern cost you again"
            grade = "C"
            tone = "critical"
        elif stability_score is not None and stability_score < 50:
            headline = "You had it, then let go"
            grade = "D"
            tone = "critical"
        elif actual_blunders >= 3:
            headline = "Too many errors decided this"
            grade = "D"
            tone = "critical"
        else:
            headline = "One or two moments changed it"
            grade = "C"
            tone = "neutral"
        show_rating_killer = True
    
    else:  # draw
        if winning_position.get("reached") and winning_position.get("peak_advantage", 0) >= 2:
            headline = "Should have been a win"
            grade = "C"
            tone = "neutral"
        else:
            headline = "Fair result"
            grade = "B"
            tone = "neutral"
        show_rating_killer = len(issues) > 0
    
    # Build the personalized summary sentence
    if coach_feedback.get("summary"):
        summary = coach_feedback["summary"]
    elif observations:
        summary = observations[0]
    elif positives:
        summary = positives[0]
    elif issues:
        summary = issues[0]
    else:
        summary = f"Accuracy: {accuracy}%"
    
    return {
        "headline": headline,
        "summary": summary,
        "grade": grade,
        "tone": tone,
        "issues": issues,
        "positives": positives,
        "observations": observations,
        "show_rating_killer": show_rating_killer,
        "coach_feedback": coach_feedback  # Rich feedback for UI
    }


def _generate_win_feedback(
    accuracy: float, avg_accuracy: float, blunders: int, mistakes: int,
    stability: Dict, winning_position: Dict, avoided_rating_killer: bool,
    rating_killer_label: str, opening_check: Dict
) -> Dict:
    """
    Generate coach feedback for a WIN.
    Focus on: What worked well + What still needs improvement
    """
    what_worked = []
    needs_work = []
    
    # === WHAT WORKED ===
    
    # Accuracy
    if accuracy >= 85:
        what_worked.append("Excellent accuracy - you found the right moves consistently")
    elif accuracy >= 75:
        what_worked.append("Solid accuracy - good decision making overall")
    elif avg_accuracy and accuracy > avg_accuracy + 5:
        what_worked.append(f"Better than your usual {round(avg_accuracy)}% accuracy")
    
    # Clean play
    if blunders == 0:
        what_worked.append("Zero blunders - stayed focused throughout")
    elif blunders == 1 and mistakes <= 1:
        what_worked.append("Mostly clean play with just one slip")
    
    # Pattern avoidance
    if avoided_rating_killer and rating_killer_label:
        what_worked.append(f"Avoided your usual {rating_killer_label.lower()} issue")
    
    # Conversion
    stability_score = stability.get("score")
    if stability_score and stability_score >= 80:
        what_worked.append("Good composure when ahead - didn't let the advantage slip")
    
    # Opening
    if opening_check.get("complied"):
        what_worked.append(f"Stuck to {opening_check.get('played')} - our suggested approach")
    
    # === STILL NEEDS WORK ===
    
    # Blunders in a win
    if blunders >= 2:
        needs_work.append(f"Still had {blunders} blunders - opponent didn't punish them")
    
    # Stability issues
    if stability_score and stability_score < 60:
        needs_work.append("Lost focus when winning - got away with it this time")
    
    # Below average accuracy in a win
    if avg_accuracy and accuracy < avg_accuracy - 5:
        needs_work.append(f"Accuracy was below your usual ({round(accuracy)}% vs {round(avg_accuracy)}%)")
    
    # Pattern showed up but still won
    if avoided_rating_killer is False and rating_killer_label:
        needs_work.append(f"Your {rating_killer_label.lower()} pattern showed up again")
    
    # Had a big advantage earlier
    peak = winning_position.get("peak_advantage", 0)
    if peak >= 4 and blunders > 0:
        needs_work.append(f"Had +{peak} advantage - could have closed faster")
    
    # Generate summary
    if what_worked and not needs_work:
        summary = what_worked[0]
    elif what_worked and needs_work:
        summary = f"{what_worked[0]}, but {needs_work[0].lower()}"
    else:
        summary = "A win is a win - good job getting the result"
    
    return {
        "what_worked": what_worked[:3],
        "needs_work": needs_work[:2],
        "summary": summary
    }


def _generate_loss_feedback(
    accuracy: float, avg_accuracy: float, blunders: int, mistakes: int,
    stability: Dict, winning_position: Dict, blunder_context: Dict,
    rating_killer_label: str, avoided_rating_killer: bool, opening_check: Dict
) -> Dict:
    """
    Generate coach feedback for a LOSS.
    Focus on: Good plays despite outcome + The core problem
    """
    good_plays = []
    core_problem = None
    
    # === GOOD PLAYS DESPITE THE LOSS ===
    
    # Good accuracy despite loss
    if accuracy >= 75:
        good_plays.append(f"{round(accuracy)}% accuracy - you played well, just got unlucky")
    elif accuracy >= 65:
        good_plays.append("Decent accuracy overall - loss wasn't due to poor play throughout")
    
    # Had a winning position
    peak = winning_position.get("peak_advantage", 0)
    if peak >= 1.5:
        good_plays.append(f"You built a +{peak} advantage - showing good play")
    
    # Low blunders despite losing
    if blunders <= 1:
        good_plays.append("Only 1 or 2 critical moments decided this")
    
    # Pattern avoided even though lost
    if avoided_rating_killer and rating_killer_label:
        good_plays.append(f"You avoided your usual {rating_killer_label.lower()} issue")
    
    # Better than average accuracy
    if avg_accuracy and accuracy > avg_accuracy:
        good_plays.append(f"Accuracy above your average - loss wasn't about bad moves")
    
    # === IDENTIFY THE CORE PROBLEM ===
    
    stability_score = stability.get("score")
    when_winning = blunder_context.get("when_winning", 0)
    when_losing = blunder_context.get("when_losing", 0)
    
    # Priority 1: Pattern repeated
    if avoided_rating_killer is False and rating_killer_label:
        core_problem = f"Your {rating_killer_label.lower()} pattern showed up at a critical moment"
    
    # Priority 2: Collapsed when winning
    elif peak >= 2 and (stability_score is None or stability_score < 60):
        core_problem = f"You had +{peak} but couldn't hold it - composure is the issue"
    
    # Priority 3: Blunders when ahead
    elif when_winning >= 2:
        core_problem = f"{when_winning} mistakes happened when you were winning - relaxed too soon"
    
    # Priority 4: Panicked when under pressure
    elif when_losing >= 2:
        core_problem = f"{when_losing} mistakes under pressure - need to stay calm when behind"
    
    # Priority 5: Too many blunders
    elif blunders >= 3:
        core_problem = f"{blunders} blunders is too many - slow down and check threats"
    
    # Priority 6: Opening issues
    elif opening_check.get("paused_and_played"):
        core_problem = f"The {opening_check.get('played')} didn't work - try a different setup"
    
    # Default
    else:
        core_problem = "One or two moments swung the game - analyze those specific positions"
    
    # Generate summary
    if good_plays:
        summary = f"{good_plays[0]}. {core_problem}"
    else:
        summary = core_problem
    
    return {
        "good_plays": good_plays[:3],
        "core_problem": core_problem,
        "summary": summary
    }


def _generate_draw_feedback(
    accuracy: float, avg_accuracy: float, blunders: int, mistakes: int,
    stability: Dict, winning_position: Dict
) -> Dict:
    """
    Generate coach feedback for a DRAW.
    """
    observations = []
    
    peak = winning_position.get("peak_advantage", 0)
    
    if peak >= 2:
        observations.append(f"Had +{peak} advantage - should have been a win")
        summary = f"You built a +{peak} lead but couldn't convert. Work on winning technique."
    elif accuracy >= 80:
        observations.append("Good accuracy - well-fought draw")
        summary = "Solid play from both sides. Nothing wrong with this draw."
    elif blunders >= 2:
        observations.append(f"Had {blunders} blunders - draw might be a fair result")
        summary = f"With {blunders} blunders, a draw is actually a reasonable outcome."
    else:
        observations.append("Fairly played game")
        summary = "Both sides played well. Look for missed opportunities."
    
    return {
        "observations": observations,
        "summary": summary
    }
