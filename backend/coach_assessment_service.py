"""
Coach Assessment Service - Personalized Chess Coaching

Provides:
1. Honest coach assessment (not just stats)
2. Capability detection (true level vs execution gaps)
3. Rating reality (framed constructively)
4. Proof from games (examples)
5. Memorable rules
6. Next games plan

Style: Direct, honest, Indian coaching approach
"Sach + Safai + Direction" (Truth + Explanation + Direction)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import statistics

from llm_service import call_llm

logger = logging.getLogger(__name__)


async def generate_coach_assessment(db, user_id: str, badges: Dict, analyses: List[Dict]) -> Dict:
    """
    Generate a personalized coach assessment.
    
    Not stats - but honest diagnosis of what's really happening.
    """
    if not analyses or len(analyses) < 3:
        return {
            "message": "Not enough games analyzed yet. Analyze 5-10 games for a clear picture.",
            "primary_issue": None,
            "secondary_issue": None,
            "has_enough_data": False
        }
    
    # Find the two biggest issues
    badge_scores = badges.get("badges", {})
    sorted_badges = sorted(badge_scores.items(), key=lambda x: x[1].get("score", 5))
    
    primary_weakness = sorted_badges[0] if sorted_badges else None
    secondary_weakness = sorted_badges[1] if len(sorted_badges) > 1 else None
    
    # Detect capability vs execution gap
    capability_analysis = detect_capability_gap(analyses, badge_scores)
    
    # Generate coach-style message
    assessment = await _generate_assessment_message(
        primary_weakness,
        secondary_weakness,
        capability_analysis,
        analyses
    )
    
    return {
        "message": assessment["message"],
        "primary_issue": {
            "badge": primary_weakness[0] if primary_weakness else None,
            "name": badge_scores.get(primary_weakness[0], {}).get("name") if primary_weakness else None,
            "description": assessment.get("primary_description", "")
        },
        "secondary_issue": {
            "badge": secondary_weakness[0] if secondary_weakness else None,
            "name": badge_scores.get(secondary_weakness[0], {}).get("name") if secondary_weakness else None,
            "description": assessment.get("secondary_description", "")
        },
        "capability_gap": capability_analysis,
        "has_enough_data": True
    }


def detect_capability_gap(analyses: List[Dict], badges: Dict) -> Dict:
    """
    Detect if player has skill gap or execution gap.
    
    Skill gap = They don't know the pattern
    Execution gap = They know it but missed it (focus issue)
    """
    best_tactical_finds = []
    simple_misses = []
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        move_evals = sf.get("move_evaluations", [])
        
        for m in move_evals:
            eval_change = abs(m.get("eval_after", 0) - m.get("eval_before", 0))
            
            # Track best finds (complex tactics player found)
            if m.get("evaluation") in ["excellent", "best"] and eval_change > 200:
                best_tactical_finds.append({
                    "game_id": analysis.get("game_id"),
                    "move_number": m.get("move_number"),
                    "complexity": eval_change
                })
            
            # Track simple misses (obvious stuff they missed)
            if m.get("evaluation") == "blunder" and eval_change > 150 and eval_change < 400:
                simple_misses.append({
                    "game_id": analysis.get("game_id"),
                    "move_number": m.get("move_number"),
                    "complexity": eval_change
                })
    
    # Analyze the gap
    has_capability_gap = False
    gap_type = "none"
    evidence = {}
    
    if best_tactical_finds and simple_misses:
        best_complexity = max(f["complexity"] for f in best_tactical_finds)
        worst_miss_complexity = min(m["complexity"] for m in simple_misses)
        
        if best_complexity > worst_miss_complexity * 1.5:
            # Player can find hard tactics but misses easy ones = execution gap
            gap_type = "execution"
            evidence = {
                "best_find": best_tactical_finds[0],
                "simple_miss": simple_misses[0],
                "message": "You can find complex tactics, but you're missing simple threats. This isn't a skill problem - it's a focus problem."
            }
        else:
            gap_type = "skill"
            evidence = {
                "message": "You need to work on tactical patterns. Solve daily puzzles."
            }
    
    return {
        "gap_type": gap_type,
        "best_finds": len(best_tactical_finds),
        "simple_misses": len(simple_misses),
        "evidence": evidence
    }


async def _generate_assessment_message(
    primary: Tuple,
    secondary: Tuple,
    capability: Dict,
    analyses: List[Dict]
) -> Dict:
    """Generate the coach assessment message."""
    
    primary_key = primary[0] if primary else "focus"
    secondary_key = secondary[0] if secondary else "tactical"
    gap_type = capability.get("gap_type", "none")
    
    # Map badge keys to readable issues
    issue_map = {
        "opening": "opening preparation",
        "tactical": "tactical awareness",
        "positional": "positional understanding",
        "endgame": "endgame technique",
        "defense": "defensive play",
        "converting": "converting winning positions",
        "focus": "focus and discipline",
        "time": "time management"
    }
    
    primary_issue = issue_map.get(primary_key, "general play")
    secondary_issue = issue_map.get(secondary_key, "consistency")
    
    # Generate message based on gap type
    if gap_type == "execution":
        message = f"""Your chess isn't getting worse.

But you're consistently losing points in 2 areas:

1. **{primary_issue.title()}** - You're making simple mistakes that are below your level

2. **{secondary_issue.title()}** - This also needs improvement

The key point: You handle complex positions well, but lose focus in easy moments. This isn't a skill problem - it's a discipline problem."""
    else:
        message = f"""Your games show 2 clear patterns:

1. **{primary_issue.title()}** - This is where you're losing the most rating points

2. **{secondary_issue.title()}** - This is a secondary issue

Focus on {primary_issue} first. Fix one thing, and the rest will improve automatically."""
    
    return {
        "message": message,
        "primary_description": f"Your {primary_issue} needs the most attention",
        "secondary_description": f"Secondary area: {secondary_issue}"
    }


async def generate_rating_reality(db, user_id: str, analyses: List[Dict]) -> Dict:
    """
    Generate rating reality section - framed constructively.
    
    Not "you dropped 26 points" but "here's why and what to do"
    """
    if not analyses or len(analyses) < 3:
        return {
            "message": "Not enough data yet",
            "rating_change": 0,
            "points_recoverable": 0,
            "cause": None
        }
    
    # Calculate blunder impact
    total_blunders = 0
    blunders_in_losses = 0
    
    for analysis in analyses:
        user_color = analysis.get("user_color", "white")
        result = analysis.get("result", "")
        user_lost = (user_color == "white" and "0-1" in result) or (user_color == "black" and "1-0" in result)
        
        sf = analysis.get("stockfish_analysis", {})
        blunders = sf.get("blunders", 0)
        total_blunders += blunders
        
        if user_lost and blunders > 0:
            blunders_in_losses += blunders
    
    # Estimate recoverable points
    # Rough estimate: each avoided blunder in a loss = 3-4 rating points
    estimated_recoverable = blunders_in_losses * 3.5
    
    if blunders_in_losses > 0:
        message = f"""Rating fluctuation is normal during improvement.

If you had avoided simple one-move blunders, you could have saved approximately **{int(estimated_recoverable)} rating points** in the last {len(analyses)} games.

This is fixable. Before every move, take one second and ask: "Is my piece safe?"
"""
    else:
        message = """Your rating is stable. Blunders are under control.

For the next level, you need deeper understanding - focus on positional play and endgames."""
    
    return {
        "message": message,
        "total_blunders": total_blunders,
        "blunders_in_losses": blunders_in_losses,
        "points_recoverable": int(estimated_recoverable),
        "games_analyzed": len(analyses)
    }


async def generate_proof_from_games(db, user_id: str, analyses: List[Dict], primary_issue: str) -> Dict:
    """
    Find game examples showing the pattern.
    
    Show: Game where they made the mistake vs game where they didn't
    """
    if not analyses or len(analyses) < 2:
        return {"has_proof": False}
    
    bad_example = None
    good_example = None
    
    for analysis in analyses:
        sf = analysis.get("stockfish_analysis", {})
        blunders = sf.get("blunders", 0)
        user_color = analysis.get("user_color", "white")
        result = analysis.get("result", "")
        
        user_won = (user_color == "white" and "1-0" in result) or (user_color == "black" and "0-1" in result)
        user_lost = (user_color == "white" and "0-1" in result) or (user_color == "black" and "1-0" in result)
        
        # Find a loss with blunders (bad example)
        if not bad_example and user_lost and blunders > 0:
            bad_example = {
                "game_id": analysis.get("game_id"),
                "result": result,
                "blunders": blunders,
                "opponent": analysis.get("opponent_name", "Opponent"),
                "summary": f"Lost with {blunders} blunder(s)"
            }
        
        # Find a win with no blunders (good example)
        if not good_example and user_won and blunders == 0:
            good_example = {
                "game_id": analysis.get("game_id"),
                "result": result,
                "blunders": 0,
                "opponent": analysis.get("opponent_name", "Opponent"),
                "summary": "Won with no blunders - clean game"
            }
        
        if bad_example and good_example:
            break
    
    if bad_example and good_example:
        return {
            "has_proof": True,
            "bad_example": bad_example,
            "good_example": good_example,
            "message": "Look - same player, same skill. The only difference is focus."
        }
    
    return {"has_proof": False, "message": "More games needed for comparison"}


def generate_memorable_rules(primary_issue: str, capability_gap: Dict) -> List[Dict]:
    """
    Generate 2 memorable, actionable rules.
    
    Not textbook advice - sticky, repeatable phrases.
    """
    rules = []
    
    # Based on primary issue
    issue_rules = {
        "opening": [
            {"rule": "Castle your king to safety - every game", "reason": "King safety = peace of mind"},
            {"rule": "Develop first, attack later", "reason": "Get your pieces out, then attack"}
        ],
        "tactical": [
            {"rule": "Before moving: What does my opponent want?", "reason": "Check threats on every move"},
            {"rule": "Checks, captures, threats - look in this order", "reason": "CCT method catches everything"}
        ],
        "positional": [
            {"rule": "Put your pieces on active squares", "reason": "Active pieces > extra pawns"},
            {"rule": "Control the weak squares", "reason": "Control squares, control the game"}
        ],
        "endgame": [
            {"rule": "Bring your king to the center in endgames", "reason": "In endgames, the king is a strong piece"},
            {"rule": "Push your passed pawns", "reason": "Passed pawn = winning chance"}
        ],
        "defense": [
            {"rule": "Don't panic when in trouble", "reason": "Best defense = calm calculation"},
            {"rule": "Neutralize opponent's threats first", "reason": "Defense first, counterplay second"}
        ],
        "converting": [
            {"rule": "SLOW DOWN when winning", "reason": "Don't rush when you're ahead"},
            {"rule": "Simplify when you're ahead", "reason": "Trade pieces, make the win easy"}
        ],
        "focus": [
            {"rule": "Wait 5 seconds before every move", "reason": "5 seconds prevents 80% of blunders"},
            {"rule": "Before moving: Is my piece safe?", "reason": "One simple check saves many points"}
        ],
        "time": [
            {"rule": "First 10 moves: Fast. Middle: Slow. End: Careful.", "reason": "Distribute time evenly"},
            {"rule": "Under 30 seconds? Play simple moves.", "reason": "Time trouble = simple chess"}
        ]
    }
    
    rules = issue_rules.get(primary_issue, issue_rules["focus"])
    
    # Add capability-specific rule if execution gap
    if capability_gap.get("gap_type") == "execution":
        rules.insert(0, {
            "rule": "You have the skill. You lack focus. Check every move.",
            "reason": "You understand complex ideas but miss simple ones",
            "is_primary": True
        })
    
    return rules[:2]  # Return max 2 rules


def generate_next_games_plan(primary_issue: str, secondary_issue: str, opening_data: Dict = None) -> Dict:
    """
    Generate next 10 games plan.
    
    Clear, focused direction - not overwhelming.
    """
    plan = {
        "games_count": 10,
        "focus_areas": [],
        "opening_advice": None,
        "message": ""
    }
    
    # Primary focus
    focus_map = {
        "opening": "Opening ke first 10 moves pe focus - development complete karo safely",
        "tactical": "Har move pe 5 seconds ruko aur threats check karo",
        "positional": "Pieces ke best squares dhundho - active rakho",
        "endgame": "Jab endgame aaye, king ko center lao pehle",
        "defense": "Worse position mein calm raho - best defense dhundho",
        "converting": "Winning position mein simplify karo - jaldi mat karo",
        "focus": "Har move pe puchho: Mera piece safe hai?",
        "time": "Clock check karo har 5 moves pe"
    }
    
    plan["focus_areas"].append({
        "title": "Primary Focus",
        "action": focus_map.get(primary_issue, "Consistent play pe focus karo")
    })
    
    plan["focus_areas"].append({
        "title": "Secondary Focus", 
        "action": focus_map.get(secondary_issue, "Blunders avoid karo")
    })
    
    # Add opening advice if available
    if opening_data:
        best_white = opening_data.get("best_as_white")
        best_black = opening_data.get("best_as_black")
        
        if best_white:
            plan["opening_advice"] = f"White se {best_white['name']} khelo - {best_white['win_rate']}% win rate hai"
        if best_black:
            plan["opening_advice"] = (plan.get("opening_advice", "") + 
                f". Black se {best_black['name']} khelo - {best_black['win_rate']}% win rate hai")
    
    plan["message"] = f"""In your next {plan['games_count']} games, focus on just 2 things.

Don't try to improve everything at once.

1. {plan['focus_areas'][0]['action']}
2. {plan['focus_areas'][1]['action']}

That's it. Keep it simple."""
    
    return plan


async def generate_full_progress_data(db, user_id: str) -> Dict:
    """
    Generate complete progress page data.
    
    Combines all sections into one cohesive response.
    """
    from badge_service import calculate_all_badges, get_badge_history, calculate_badge_trends, save_badge_snapshot
    
    # Get analyses
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    # Calculate badges
    badges = await calculate_all_badges(db, user_id)
    
    # Get badge history and trends
    history = await get_badge_history(db, user_id)
    trends = calculate_badge_trends(badges, history)
    
    # Add trends to badges
    for key in badges.get("badges", {}):
        badges["badges"][key]["trend"] = trends.get(key, "stable")
    
    # Save snapshot for future trend analysis
    if badges.get("badges"):
        await save_badge_snapshot(db, user_id, badges)
    
    # Generate coach assessment
    assessment = await generate_coach_assessment(db, user_id, badges, analyses)
    
    # Generate rating reality
    rating_reality = await generate_rating_reality(db, user_id, analyses)
    
    # Generate proof from games
    primary_issue = assessment.get("primary_issue", {}).get("badge", "focus")
    proof = await generate_proof_from_games(db, user_id, analyses, primary_issue)
    
    # Generate memorable rules
    rules = generate_memorable_rules(
        primary_issue,
        assessment.get("capability_gap", {})
    )
    
    # Generate next games plan
    plan = generate_next_games_plan(
        primary_issue,
        assessment.get("secondary_issue", {}).get("badge", "tactical")
    )
    
    # Get opening stats (if available)
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "opening_stats": 1}
    )
    opening_data = profile.get("opening_stats") if profile else None
    
    return {
        "coach_assessment": assessment,
        "rating_reality": rating_reality,
        "badges": badges,
        "proof_from_games": proof,
        "memorable_rules": rules,
        "next_games_plan": plan,
        "opening_stats": opening_data,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
