"""
Plan Audit Service - Phase-Based Execution Evaluation

Evaluates the previous game's execution across 5 domains:
1. Opening - Did they follow opening plan?
2. Middlegame - Did they maintain strategic discipline?
3. Endgame - Did they apply endgame principles?
4. Tactical Discipline - Did they avoid blunders?
5. Time Discipline - Did they manage clock properly?

Design Principles:
- Only show domains where plan existed OR something meaningful happened
- Bullet format, under 4 lines per domain
- Always include data point
- No motivational phrases
- Deterministic verdicts
"""

import logging
import re
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def audit_opening(
    game: Dict, 
    analysis: Dict, 
    opening_guidance: Dict,
    user_color: str
) -> Optional[Dict]:
    """
    Audit Opening Domain
    
    Checks:
    - Did they play the suggested opening?
    - Opening accuracy (first 10 moves)
    - Early eval stability
    
    Returns None if no opening plan existed.
    """
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    # Extract opening played
    pgn = game.get("pgn", "")
    opening_played = "Unknown"
    eco_match = re.search(r'\[ECOUrl "[^"]+/([^/"]+)"\]', pgn)
    if eco_match:
        opening_played = eco_match.group(1).replace("-", " ").title()
    else:
        opening_match = re.search(r'\[Opening "([^"]+)"\]', pgn)
        if opening_match:
            opening_played = opening_match.group(1)
    
    # Clean up opening name
    if "/" in opening_played or "Www" in opening_played:
        eco_code = re.search(r'\[ECO "([^"]+)"\]', pgn)
        opening_played = f"Opening {eco_code.group(1)}" if eco_code else "Standard Opening"
    
    # Get opening guidance for this color
    color_key = "as_white" if user_color == "white" else "as_black"
    guidance = opening_guidance.get(color_key, {}) if opening_guidance else {}
    working_well = [o.get("name", "") for o in guidance.get("working_well", [])]
    pause_for_now = [o.get("name", "") for o in guidance.get("pause_for_now", [])]
    
    # Calculate opening accuracy (first 10 user moves)
    opening_moves = []
    for m in move_evals:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move and move_num <= 20:  # First 10 moves per side = 20 total
            opening_moves.append(m)
    
    if not opening_moves:
        return None
    
    # Calculate opening accuracy
    total_cp_loss = sum(m.get("cp_loss", 0) for m in opening_moves)
    avg_cp_loss = total_cp_loss / len(opening_moves) if opening_moves else 0
    opening_accuracy = max(0, 100 - (avg_cp_loss / 2))  # Simple accuracy formula
    
    # Check for early eval drops
    max_eval_drop = 0
    for m in opening_moves:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        if user_color == "black":
            eval_before, eval_after = -eval_before, -eval_after
        drop = eval_before - eval_after
        if drop > max_eval_drop:
            max_eval_drop = drop
    
    # Determine early eval stability
    eval_stability = "Stable" if max_eval_drop < 50 else "Unstable" if max_eval_drop < 150 else "Poor"
    
    # Determine if plan was followed
    plan_existed = len(working_well) > 0 or len(pause_for_now) > 0
    
    played_suggested = any(
        sug.lower() in opening_played.lower() or opening_played.lower() in sug.lower()
        for sug in working_well
    ) if working_well else None
    
    played_paused = any(
        p.lower() in opening_played.lower() or opening_played.lower() in p.lower()
        for p in pause_for_now
    ) if pause_for_now else False
    
    # Only return if there's something meaningful to show
    has_meaningful_data = plan_existed or opening_accuracy < 70 or max_eval_drop >= 100
    
    if not has_meaningful_data:
        return None
    
    # Build the audit result
    result = {
        "domain": "Opening",
        "has_plan": plan_existed,
        "data": {
            "opening_accuracy": round(opening_accuracy, 0),
            "early_eval_stability": eval_stability,
            "max_eval_drop": round(max_eval_drop / 100, 1) if max_eval_drop >= 50 else None
        }
    }
    
    # Determine plan and what happened
    if plan_existed:
        if working_well:
            result["plan"] = f"Play {working_well[0]}" if len(working_well) == 1 else f"Play {working_well[0]} or similar"
        else:
            result["plan"] = f"Avoid {pause_for_now[0]}" if pause_for_now else "Follow preparation"
        
        result["what_happened"] = []
        result["what_happened"].append(f"You played {opening_played}")
        
        if opening_accuracy >= 80:
            result["what_happened"].append("Development clean through opening")
        elif opening_accuracy >= 65:
            result["what_happened"].append("Some inaccuracies in development")
        else:
            result["what_happened"].append("Struggled in the opening phase")
        
        if max_eval_drop >= 100:
            result["what_happened"].append(f"Eval dropped {round(max_eval_drop/100, 1)} in first 10 moves")
        
        # Verdict
        if played_paused:
            result["verdict"] = "Opening Plan Ignored"
            result["verdict_type"] = "fail"
        elif played_suggested:
            if opening_accuracy >= 75 and max_eval_drop < 100:
                result["verdict"] = "Opening Plan Executed"
                result["verdict_type"] = "pass"
            else:
                result["verdict"] = "Opening Choice OK, Execution Poor"
                result["verdict_type"] = "partial"
        else:
            if opening_accuracy >= 75:
                result["verdict"] = "Different Opening, Clean Execution"
                result["verdict_type"] = "partial"
            else:
                result["verdict"] = "Opening Preparation Missed"
                result["verdict_type"] = "fail"
    else:
        # No plan existed, but show if something meaningful happened
        result["plan"] = None
        result["what_happened"] = [f"Played {opening_played}"]
        
        if opening_accuracy < 65:
            result["what_happened"].append(f"Opening accuracy only {round(opening_accuracy)}%")
            result["verdict"] = "Opening Struggled"
            result["verdict_type"] = "fail"
        elif max_eval_drop >= 150:
            result["what_happened"].append(f"Early eval drop of {round(max_eval_drop/100, 1)}")
            result["verdict"] = "Opening Unstable"
            result["verdict_type"] = "fail"
        else:
            return None  # Nothing meaningful to report
    
    return result


def audit_middlegame(
    game: Dict,
    analysis: Dict,
    user_color: str,
    mission: Dict = None
) -> Optional[Dict]:
    """
    Audit Middlegame Domain
    
    Checks:
    - When ahead, did they simplify or increase complexity?
    - Eval stability after gaining advantage
    - Strategic discipline based on position type
    """
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    if not move_evals:
        return None
    
    # Find middlegame phase (moves 11-30 typically)
    middlegame_moves = []
    for m in move_evals:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move and 20 < move_num <= 60:  # Middlegame range
            middlegame_moves.append(m)
    
    if len(middlegame_moves) < 5:
        return None  # Game ended early, no middlegame to audit
    
    # Check if user reached winning position
    winning_positions = []
    max_advantage = 0
    max_advantage_move = None
    
    for m in middlegame_moves:
        eval_before = m.get("eval_before", 0)
        if user_color == "black":
            eval_before = -eval_before
        
        if eval_before > max_advantage:
            max_advantage = eval_before
            max_advantage_move = m.get("move_number")
        
        if eval_before >= 150:  # +1.5 or better
            winning_positions.append(m)
    
    # Calculate eval stability after advantage
    collapses = 0
    biggest_collapse = 0
    collapse_move = None
    
    for m in winning_positions:
        eval_before = m.get("eval_before", 0)
        eval_after = m.get("eval_after", 0)
        if user_color == "black":
            eval_before, eval_after = -eval_before, -eval_after
        
        drop = eval_before - eval_after
        if drop > 150:  # Significant drop
            collapses += 1
            if drop > biggest_collapse:
                biggest_collapse = drop
                collapse_move = m.get("move_number")
    
    # Determine if there was something meaningful
    had_advantage = max_advantage >= 150
    had_collapse = biggest_collapse >= 150
    
    if not had_advantage and not had_collapse:
        return None  # Nothing meaningful to report
    
    # Determine the "plan" based on mission or general principle
    if mission and mission.get("weakness_key") == "loses_focus_when_winning":
        plan = "When ahead, simplify. Stay alert."
    elif had_advantage:
        plan = "Maintain advantage. Don't overpress."
    else:
        plan = None
    
    result = {
        "domain": "Middlegame",
        "has_plan": plan is not None,
        "plan": plan,
        "what_happened": [],
        "data": {
            "max_advantage": f"+{round(max_advantage/100, 1)}" if max_advantage >= 100 else None,
            "max_advantage_move": max_advantage_move,
            "eval_swing": f"-{round(biggest_collapse/100, 1)}" if biggest_collapse >= 100 else None
        }
    }
    
    # Describe what happened
    if had_advantage:
        result["what_happened"].append(f"Advantage reached at move {max_advantage_move} (+{round(max_advantage/100, 1)})")
    
    if had_collapse:
        result["what_happened"].append(f"Eval dropped {round(biggest_collapse/100, 1)} in {collapses} collapse(s)")
        if collapse_move:
            result["what_happened"].append(f"Biggest drop around move {collapse_move}")
    elif had_advantage:
        result["what_happened"].append("Maintained pressure throughout")
    
    # Verdict
    if had_advantage and not had_collapse:
        result["verdict"] = "Strategic Discipline Maintained"
        result["verdict_type"] = "pass"
    elif had_advantage and had_collapse:
        if biggest_collapse >= 300:
            result["verdict"] = "Strategic Discipline Broken"
            result["verdict_type"] = "fail"
        else:
            result["verdict"] = "Minor Lapses in Control"
            result["verdict_type"] = "partial"
    else:
        result["verdict"] = "Position Stayed Balanced"
        result["verdict_type"] = "neutral"
    
    return result


def audit_endgame(
    game: Dict,
    analysis: Dict,
    user_color: str,
    game_result: str
) -> Optional[Dict]:
    """
    Audit Endgame Domain
    
    Only triggers if endgame was reached.
    Checks king activity, pawn advancement, conversion.
    """
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    if not move_evals:
        return None
    
    # Endgame = moves after move 30 (move_number > 60)
    endgame_moves = []
    for m in move_evals:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move and move_num > 60:
            endgame_moves.append(m)
    
    if len(endgame_moves) < 3:
        return None  # No real endgame phase
    
    # Check if user had winning endgame position
    had_winning_endgame = False
    endgame_eval = 0
    
    for m in endgame_moves[:5]:  # Check start of endgame
        eval_before = m.get("eval_before", 0)
        if user_color == "black":
            eval_before = -eval_before
        if eval_before >= 100:
            had_winning_endgame = True
            endgame_eval = eval_before
            break
    
    # Check conversion
    converted = game_result == "win"
    
    # Check for endgame blunders
    endgame_blunders = 0
    biggest_drop = 0
    for m in endgame_moves:
        cp_loss = m.get("cp_loss", 0)
        if cp_loss >= 200:
            endgame_blunders += 1
        if cp_loss > biggest_drop:
            biggest_drop = cp_loss
    
    # Only show if something meaningful
    if not had_winning_endgame and endgame_blunders == 0:
        return None
    
    result = {
        "domain": "Endgame",
        "has_plan": had_winning_endgame,
        "plan": "Convert winning position" if had_winning_endgame else None,
        "what_happened": [],
        "data": {
            "endgame_eval": f"+{round(endgame_eval/100, 1)}" if endgame_eval >= 100 else None,
            "conversion": "Yes" if converted else "No" if had_winning_endgame else None
        }
    }
    
    if had_winning_endgame:
        result["what_happened"].append(f"Entered endgame with +{round(endgame_eval/100, 1)}")
        if converted:
            result["what_happened"].append("Successfully converted advantage")
            result["verdict"] = "Endgame Converted"
            result["verdict_type"] = "pass"
        else:
            result["what_happened"].append("Failed to convert winning position")
            if biggest_drop >= 200:
                result["what_happened"].append(f"Blundered {round(biggest_drop/100, 1)} pawns")
            result["verdict"] = "Endgame Conversion Failed"
            result["verdict_type"] = "fail"
    else:
        if endgame_blunders >= 2:
            result["what_happened"].append(f"{endgame_blunders} errors in endgame")
            result["verdict"] = "Endgame Technique Weak"
            result["verdict_type"] = "fail"
        else:
            return None  # Nothing meaningful
    
    return result


def audit_tactical_discipline(
    analysis: Dict,
    user_color: str
) -> Optional[Dict]:
    """
    Audit Tactical Discipline Domain
    
    Checks:
    - Blunders committed
    - Missed opponent threats
    - Major eval drops from tactical oversights
    """
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    blunders = sf_analysis.get("blunders", 0)
    mistakes = sf_analysis.get("mistakes", 0)
    
    if not move_evals:
        return None
    
    # Filter user moves
    user_moves = []
    for m in move_evals:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        if is_user_move:
            user_moves.append(m)
    
    # Find the worst blunder
    worst_blunder = None
    worst_blunder_loss = 0
    
    for m in user_moves:
        cp_loss = m.get("cp_loss", 0)
        classification = m.get("classification", "")
        if classification == "blunder" and cp_loss > worst_blunder_loss:
            worst_blunder = m
            worst_blunder_loss = cp_loss
    
    # Always show tactical audit (it's a core discipline)
    result = {
        "domain": "Tactics",
        "has_plan": True,  # Tactical vigilance is always a plan
        "plan": "Scan checks, captures, threats before each move",
        "what_happened": [],
        "data": {
            "blunders": blunders,
            "mistakes": mistakes,
            "worst_drop": f"-{round(worst_blunder_loss/100, 1)}" if worst_blunder_loss >= 100 else None
        }
    }
    
    if blunders == 0:
        result["what_happened"].append("No blunders committed")
        if mistakes == 0:
            result["what_happened"].append("Clean tactical execution")
            result["verdict"] = "Tactical Protocol Followed"
            result["verdict_type"] = "pass"
        else:
            result["what_happened"].append(f"{mistakes} minor mistake(s), no damage")
            result["verdict"] = "Tactical Discipline OK"
            result["verdict_type"] = "pass"
    else:
        result["what_happened"].append(f"{blunders} blunder(s) committed")
        if worst_blunder:
            move_num = worst_blunder.get("move_number", 0)
            result["what_happened"].append(f"Worst at move {move_num} (-{round(worst_blunder_loss/100, 1)})")
        
        if blunders >= 3:
            result["verdict"] = "Tactical Protocol Failed"
            result["verdict_type"] = "fail"
        elif blunders >= 2:
            result["verdict"] = "Tactical Discipline Broken"
            result["verdict_type"] = "fail"
        else:
            result["verdict"] = "One Tactical Lapse"
            result["verdict_type"] = "partial"
    
    return result


def audit_time_discipline(
    game: Dict,
    analysis: Dict,
    user_color: str
) -> Optional[Dict]:
    """
    Audit Time Discipline Domain
    
    Checks:
    - Time usage patterns
    - Low-time blunders
    - Clock management
    
    Note: Time data may not be available in all games.
    """
    sf_analysis = analysis.get("stockfish_analysis", {})
    move_evals = sf_analysis.get("move_evaluations", [])
    
    # Check if we have time data
    pgn = game.get("pgn", "")
    has_time_data = "%clk" in pgn or "%emt" in pgn
    
    # Extract time control
    time_control = game.get("time_control", "")
    if not time_control:
        tc_match = re.search(r'\[TimeControl "([^"]+)"\]', pgn)
        time_control = tc_match.group(1) if tc_match else ""
    
    # Determine if it's a fast game (blitz/bullet)
    is_fast_game = False
    if time_control:
        try:
            base_time = int(time_control.split("+")[0])
            is_fast_game = base_time <= 300  # 5 min or less
        except (ValueError, IndexError):
            pass
    
    if not has_time_data and not is_fast_game:
        return None  # Can't audit time without data
    
    # Look for patterns suggesting time trouble
    # Late game blunders often indicate time pressure
    late_blunders = 0
    total_blunders = 0
    
    for m in move_evals:
        move_num = m.get("move_number", 0)
        is_white_move = (move_num % 2 == 1)
        is_user_move = (user_color == "white" and is_white_move) or (user_color == "black" and not is_white_move)
        
        if is_user_move:
            classification = m.get("classification", "")
            if classification == "blunder":
                total_blunders += 1
                if move_num > 50:  # Late game
                    late_blunders += 1
    
    # Only show if relevant
    if total_blunders == 0:
        # Clean game, but only show time audit for fast games
        if not is_fast_game:
            return None
    
    result = {
        "domain": "Time",
        "has_plan": is_fast_game,
        "plan": "Manage clock. Don't rush critical decisions." if is_fast_game else None,
        "what_happened": [],
        "data": {
            "time_control": time_control or "Unknown",
            "late_blunders": late_blunders if late_blunders > 0 else None
        }
    }
    
    if late_blunders >= 2:
        result["what_happened"].append(f"{late_blunders} blunders in late game")
        result["what_happened"].append("Possible time pressure issues")
        result["verdict"] = "Time Discipline Failed"
        result["verdict_type"] = "fail"
    elif late_blunders == 1:
        result["what_happened"].append("1 late-game error")
        result["verdict"] = "Minor Time Pressure Issue"
        result["verdict_type"] = "partial"
    elif total_blunders == 0 and is_fast_game:
        result["what_happened"].append("No time-related errors")
        result["verdict"] = "Time Managed Well"
        result["verdict_type"] = "pass"
    else:
        return None  # Nothing meaningful
    
    return result


async def get_plan_audit(db, user_id: str) -> Dict:
    """
    Main entry point for Plan Audit.
    
    Returns a structured audit of the last game across 5 domains.
    Only includes domains where:
    - A plan existed, OR
    - Something meaningful happened
    """
    
    # 1. Get user's most recent ANALYZED game
    last_game = await db.games.find_one(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0},
        sort=[("imported_at", -1)]
    )
    
    if not last_game:
        return {"has_data": False, "reason": "no_analyzed_games"}
    
    game_id = last_game.get("game_id")
    user_color = last_game.get("user_color", "white")
    
    # 2. Get analysis for this game
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not analysis:
        return {"has_data": False, "reason": "no_analysis"}
    
    # 3. Get all games and analyses for context
    all_games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(100)
    
    all_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(100)
    
    # 4. Get opening guidance and mission
    from blunder_intelligence_service import get_opening_guidance, get_mission
    opening_guidance = get_opening_guidance(all_analyses, all_games)
    mission = get_mission(all_analyses)
    
    # 5. Determine game result
    result = last_game.get("result", "*")
    if user_color == "white":
        game_result = "win" if result == "1-0" else "loss" if result == "0-1" else "draw"
    else:
        game_result = "win" if result == "0-1" else "loss" if result == "1-0" else "draw"
    
    # 6. Run all audits
    audits = []
    
    opening_audit = audit_opening(last_game, analysis, opening_guidance, user_color)
    if opening_audit:
        audits.append(opening_audit)
    
    middlegame_audit = audit_middlegame(last_game, analysis, user_color, mission)
    if middlegame_audit:
        audits.append(middlegame_audit)
    
    endgame_audit = audit_endgame(last_game, analysis, user_color, game_result)
    if endgame_audit:
        audits.append(endgame_audit)
    
    tactical_audit = audit_tactical_discipline(analysis, user_color)
    if tactical_audit:
        audits.append(tactical_audit)
    
    time_audit = audit_time_discipline(last_game, analysis, user_color)
    if time_audit:
        audits.append(time_audit)
    
    # 7. Calculate summary
    domains_executed = sum(1 for a in audits if a.get("verdict_type") == "pass")
    domains_partial = sum(1 for a in audits if a.get("verdict_type") == "partial")
    domains_failed = sum(1 for a in audits if a.get("verdict_type") == "fail")
    total_domains = len(audits)
    
    # Determine training focus based on failures
    training_focus = None
    for audit in audits:
        if audit.get("verdict_type") == "fail":
            training_focus = audit.get("domain")
            break
    
    # 8. Get opponent name
    pgn = last_game.get("pgn", "")
    opponent = "Opponent"
    if user_color == "white":
        match = re.search(r'\[Black "([^"]+)"\]', pgn)
    else:
        match = re.search(r'\[White "([^"]+)"\]', pgn)
    if match:
        opponent = match.group(1)
    
    # 9. Get basic stats
    sf_analysis = analysis.get("stockfish_analysis", {})
    accuracy = sf_analysis.get("accuracy", 0)
    blunders = sf_analysis.get("blunders", 0)
    
    return {
        "has_data": True,
        "game_id": game_id,
        "opponent": opponent,
        "result": game_result,
        "user_color": user_color,
        
        # Basic stats
        "accuracy": round(accuracy, 1),
        "blunders": blunders,
        
        # Domain audits (only those with meaningful data)
        "audits": audits,
        
        # Summary
        "summary": {
            "domains_shown": total_domains,
            "executed": domains_executed,
            "partial": domains_partial,
            "failed": domains_failed,
            "execution_score": f"{domains_executed}/{total_domains}",
            "training_focus": training_focus
        }
    }
