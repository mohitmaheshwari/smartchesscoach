"""
Auto-Coach Service - Live Post-Game Coaching Feedback

This service generates brief, coach-like commentary after each game analysis.
Uses GPT-4o-mini for cost-effective, high-quality coaching summaries.

Design Rules:
- 300-600 tokens max
- No move lines or deep variations
- Must reference provided deterministic data only
- Coach-like tone, not engine-like
"""

import os
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# LLM Configuration
LLM_MODEL = "gpt-4o"  # Using gpt-4o as gpt-4o-mini
LLM_PROVIDER = "openai"
MAX_TOKENS = 600

# System prompt for the coach
COACH_SYSTEM_PROMPT = """You are a chess coach providing brief, actionable feedback after a game.

RULES:
1. Keep response between 100-200 words
2. Never mention specific move sequences or variations
3. Never invent analysis - only reference the provided data
4. Be encouraging but honest
5. Focus on ONE key lesson per game
6. Use "you" language (personal, direct)
7. End with ONE specific action item

TONE: Supportive coach who's watched your game, not a computer engine.

STRUCTURE (follow exactly):
1. One sentence acknowledging the result
2. The core lesson (1-2 sentences)
3. One specific improvement action

DO NOT:
- Write essays
- List multiple issues
- Use chess notation
- Say "I analyzed" or refer to yourself
- Be generic ("play better moves")
"""


def build_deterministic_summary(analysis: Dict, game: Dict = None) -> Dict:
    """
    Build structured deterministic data from game analysis.
    This is the ONLY data the LLM should use.
    """
    stockfish = analysis.get("stockfish_analysis", {})
    move_evals = stockfish.get("move_evaluations", [])
    
    # Calculate basic stats
    user_color = game.get("user_color", "white") if game else "white"
    result = game.get("result", "") if game else ""
    
    # Determine win/loss/draw
    if result == "1-0":
        outcome = "Win" if user_color == "white" else "Loss"
    elif result == "0-1":
        outcome = "Loss" if user_color == "white" else "Win"
    elif result == "1/2-1/2":
        outcome = "Draw"
    else:
        outcome = "Unknown"
    
    # Count mistakes by user
    blunders = 0
    mistakes = 0
    inaccuracies = 0
    critical_moment = None
    max_swing = 0
    
    for m in move_evals:
        # Check if it's user's move based on FEN
        fen = m.get("fen_before", "")
        parts = fen.split(" ")
        turn = parts[1] if len(parts) > 1 else "w"
        is_user_move = (user_color == "white" and turn == "w") or (user_color == "black" and turn == "b")
        
        if not is_user_move:
            continue
            
        cp_loss = abs(m.get("cp_loss", 0))
        
        if cp_loss >= 300:
            blunders += 1
        elif cp_loss >= 100:
            mistakes += 1
        elif cp_loss >= 50:
            inaccuracies += 1
        
        # Track biggest swing
        if cp_loss > max_swing:
            max_swing = cp_loss
            eval_before = m.get("eval_before", 0)
            eval_after = m.get("eval_after", 0)
            critical_moment = {
                "move_number": m.get("move_number"),
                "eval_before": round(eval_before / 100, 1) if eval_before else 0,
                "eval_after": round(eval_after / 100, 1) if eval_after else 0,
                "cp_loss": round(cp_loss / 100, 1)
            }
    
    # Determine phase where most errors occurred
    opening_errors = sum(1 for m in move_evals if m.get("move_number", 0) <= 10 and abs(m.get("cp_loss", 0)) >= 100)
    middlegame_errors = sum(1 for m in move_evals if 10 < m.get("move_number", 0) <= 30 and abs(m.get("cp_loss", 0)) >= 100)
    endgame_errors = sum(1 for m in move_evals if m.get("move_number", 0) > 30 and abs(m.get("cp_loss", 0)) >= 100)
    
    phase_issue = "Opening" if opening_errors > max(middlegame_errors, endgame_errors) else \
                  "Endgame" if endgame_errors > middlegame_errors else "Middlegame"
    
    # Determine if player was ahead at some point
    was_ahead = False
    for m in move_evals:
        eval_val = m.get("eval_before", 0) / 100
        if (user_color == "white" and eval_val > 1.5) or (user_color == "black" and eval_val < -1.5):
            was_ahead = True
            break
    
    # Get dominant mistake pattern from core lesson
    dominant_mistake = analysis.get("commentary", {}).get("core_lesson", {}).get("pattern", "general_errors")
    
    # Map pattern to readable text
    pattern_labels = {
        "attacks_before_checking": "Attacking before checking opponent threats",
        "relaxes_when_winning": "Relaxing when ahead",
        "one_move_blunders": "One-move tactical oversights",
        "positional_drift": "Gradual positional decline",
        "missed_tactics": "Missing tactical opportunities",
        "time_trouble_collapse": "Time pressure mistakes",
        "opening_inaccuracies": "Opening preparation gaps",
        "endgame_technique": "Endgame technique issues",
        "clean_game": "No major issues"
    }
    dominant_mistake_text = pattern_labels.get(dominant_mistake, "General mistakes")
    
    return {
        "result": outcome,
        "accuracy": stockfish.get("accuracy", 0),
        "blunders": blunders,
        "mistakes": mistakes,
        "inaccuracies": inaccuracies,
        "dominant_mistake": dominant_mistake_text,
        "critical_moment": critical_moment,
        "phase_issue": phase_issue,
        "was_ahead": was_ahead,
        "opponent": game.get("black_player") if user_color == "white" else game.get("white_player") if game else "Opponent",
        "user_color": user_color
    }


async def generate_coach_commentary(analysis: Dict, game: Dict = None) -> Optional[str]:
    """
    Generate LLM-based coaching commentary for a game.
    
    Args:
        analysis: The game analysis with stockfish data
        game: The game metadata
        
    Returns:
        Coaching commentary string or None if generation fails
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            logger.error("EMERGENT_LLM_KEY not found in environment")
            return None
        
        # Build deterministic summary
        summary = build_deterministic_summary(analysis, game)
        
        # Skip if clean game
        if summary["blunders"] == 0 and summary["mistakes"] == 0 and summary["inaccuracies"] <= 2:
            return f"Clean game! Your {summary['accuracy']:.0f}% accuracy shows solid play. Keep up this focused approach in your next games."
        
        # Build prompt with structured data
        game_context = f"""
GAME DATA (use ONLY this information):
- Result: {summary['result']}
- Accuracy: {summary['accuracy']:.1f}%
- Blunders: {summary['blunders']}
- Mistakes: {summary['mistakes']}
- Main issue: {summary['dominant_mistake']}
- Problem phase: {summary['phase_issue']}
- Was winning at some point: {'Yes' if summary['was_ahead'] else 'No'}
"""
        
        if summary['critical_moment']:
            cm = summary['critical_moment']
            game_context += f"- Turning point: Move {cm['move_number']} (position went from {cm['eval_before']:+.1f} to {cm['eval_after']:+.1f})\n"
        
        # Initialize chat
        chat = LlmChat(
            api_key=api_key,
            session_id=f"coach_{analysis.get('game_id', 'unknown')}",
            system_message=COACH_SYSTEM_PROMPT
        ).with_model(LLM_PROVIDER, LLM_MODEL)
        
        # Send message
        user_message = UserMessage(text=game_context)
        response = await chat.send_message(user_message)
        
        logger.info(f"Generated coaching commentary for game {analysis.get('game_id')}")
        return response.strip()
        
    except Exception as e:
        logger.error(f"Error generating coach commentary: {e}")
        return None


async def generate_and_save_commentary(db, analysis: Dict, game: Dict = None) -> Optional[str]:
    """
    Generate coaching commentary and save to database.
    Only generates once - cached permanently.
    """
    game_id = analysis.get("game_id")
    
    # Check if commentary already exists
    existing = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "coach_commentary": 1}
    )
    
    if existing and existing.get("coach_commentary"):
        logger.info(f"Using cached coach commentary for game {game_id}")
        return existing["coach_commentary"]
    
    # Generate new commentary
    commentary = await generate_coach_commentary(analysis, game)
    
    if commentary:
        # Save to database
        await db.game_analyses.update_one(
            {"game_id": game_id},
            {"$set": {
                "coach_commentary": commentary,
                "coach_commentary_generated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.info(f"Saved coach commentary for game {game_id}")
    
    return commentary


def get_quick_notification_message(summary: Dict) -> str:
    """
    Generate a quick 1-sentence notification for the user.
    """
    if summary["blunders"] == 0 and summary["mistakes"] == 0:
        return f"Clean {summary['result'].lower()}! No major mistakes detected."
    
    if summary["result"] == "Win":
        if summary["blunders"] > 0:
            return f"You won, but {summary['dominant_mistake'].lower()} cost you some advantage."
        return f"Nice win with {summary['accuracy']:.0f}% accuracy!"
    
    elif summary["result"] == "Loss":
        if summary["was_ahead"]:
            return f"You had a winning position but {summary['dominant_mistake'].lower()}."
        return f"Game analyzed. Focus area: {summary['dominant_mistake'].lower()}."
    
    else:
        return f"Draw analyzed. Your {summary['phase_issue'].lower()} phase needs attention."
