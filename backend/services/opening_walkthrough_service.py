"""
Opening Walkthrough Service
============================

"Your coach walks you through YOUR game in YOUR opening."

Takes the user's most-played opening, picks a real game, and builds
a step-by-step guided lesson from it.

Each move has:
- The IDEA (why this move matters)
- The PLAN (what to aim for next)
- A flag if the user went wrong + what to do instead
- Interactive challenges at key positions
"""

import chess
import chess.pgn
import io
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def get_user_top_openings(db, user_id: str, limit: int = 5) -> List[Dict]:
    """Get user's most-played openings with win/loss stats."""
    games = await db.games.find(
        {"user_id": user_id, "opening_name": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "game_id": 1, "opening_name": 1, "opening": 1, "result": 1, "user_color": 1}
    ).to_list(200)

    openings = {}
    for g in games:
        name = g.get("opening_name") or g.get("opening") or "Unknown"
        # Normalize: take first 2-3 words as the key
        short_name = " ".join(name.split()[:3])
        if short_name not in openings:
            openings[short_name] = {"name": name, "games": 0, "wins": 0, "losses": 0, "draws": 0, "game_ids": []}

        openings[short_name]["games"] += 1
        openings[short_name]["game_ids"].append(g["game_id"])

        result = g.get("result", "")
        color = g.get("user_color", "white")
        user_won = (result == "1-0" and color == "white") or (result == "0-1" and color == "black")
        user_lost = (result == "0-1" and color == "white") or (result == "1-0" and color == "black")

        if user_won:
            openings[short_name]["wins"] += 1
        elif user_lost:
            openings[short_name]["losses"] += 1
        else:
            openings[short_name]["draws"] += 1

    # Sort by most played
    sorted_openings = sorted(openings.values(), key=lambda x: x["games"], reverse=True)
    return sorted_openings[:limit]


async def generate_walkthrough(
    db, user_id: str, opening_name: Optional[str] = None, call_llm_func=None
) -> Dict:
    """
    Generate a guided opening walkthrough from the user's actual games.
    """
    # 1. Find their openings
    top_openings = await get_user_top_openings(db, user_id)
    if not top_openings:
        return {"error": "no_games", "message": "Play some games first so I can teach you your openings."}

    # 2. Pick the opening
    chosen = None
    if opening_name:
        for o in top_openings:
            if opening_name.lower() in o["name"].lower():
                chosen = o
                break
    if not chosen:
        chosen = top_openings[0]

    # 3. Find a game with analysis in this opening
    game_ids = chosen["game_ids"]
    best_game = None
    best_analysis = None

    for gid in game_ids:
        analysis = await db.game_analyses.find_one(
            {"game_id": gid, "user_id": user_id},
            {"_id": 0}
        )
        if analysis and analysis.get("stockfish_analysis", {}).get("move_evaluations"):
            game = await db.games.find_one({"game_id": gid}, {"_id": 0})
            if game:
                best_game = game
                best_analysis = analysis
                break

    if not best_game or not best_analysis:
        return {
            "error": "no_analysis",
            "message": f"No analyzed games found for {chosen['name']}. Games need to be analyzed first.",
            "opening": chosen,
        }

    # 4. Build the walkthrough
    sf = best_analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    user_color = best_game.get("user_color", "white")
    user_is_white = user_color == "white"
    result = best_game.get("result", "")
    pgn = best_game.get("pgn", "")
    opponent = best_game.get("opponent_name", "Opponent")

    # Parse PGN to get moves
    moves = []
    try:
        game_pgn = chess.pgn.read_game(io.StringIO(pgn))
        if game_pgn:
            board = game_pgn.board()
            for move in game_pgn.mainline_moves():
                san = board.san(move)
                moves.append({"san": san, "uci": move.uci(), "fen_before": board.fen()})
                board.push(move)
    except Exception as e:
        logger.warning(f"PGN parse failed: {e}")

    # 5. Build step-by-step walkthrough
    steps = []
    opening_phase_end = min(20, len(moves))  # Focus on first 20 moves (opening + early middle)

    for i in range(min(len(evals), opening_phase_end)):
        ev = evals[i]
        move_san = ev.get("move", ev.get("san", "?"))
        is_user_move = (i % 2 == 0 and user_is_white) or (i % 2 == 1 and not user_is_white)
        move_number = (i // 2) + 1
        cp_loss = ev.get("cp_loss", 0)
        best_move = ev.get("best_move", "")
        fen_before = ev.get("fen_before", "")
        phase = "opening" if i < 16 else "middlegame"

        step = {
            "move_index": i,
            "move_number": move_number,
            "move_san": move_san,
            "is_user_move": is_user_move,
            "fen_before": fen_before,
            "cp_loss": cp_loss,
            "phase": phase,
            "side": "white" if i % 2 == 0 else "black",
        }

        # Determine step type
        if is_user_move and cp_loss >= 150:
            step["type"] = "mistake"
            step["best_move"] = best_move
            step["best_move_uci"] = ev.get("best_move_uci", "")
            step["move_uci"] = ev.get("move_uci", "")
            step["idea"] = _get_mistake_idea(cp_loss, best_move, phase)
            step["is_challenge"] = True  # Player should try to find the right move
        elif is_user_move and cp_loss >= 80:
            step["type"] = "inaccuracy"
            step["best_move"] = best_move
            step["idea"] = _get_inaccuracy_idea(move_san, best_move, phase)
            step["is_challenge"] = False
        elif is_user_move:
            step["type"] = "good"
            step["idea"] = _get_good_move_idea(move_san, phase, i)
            step["is_challenge"] = False
        else:
            step["type"] = "opponent"
            step["idea"] = _get_opponent_idea(move_san, phase, i)
            step["is_challenge"] = False

        steps.append(step)

    # 6. Build opening summary
    user_opening_moves = [s for s in steps if s["is_user_move"] and s["phase"] == "opening"]
    opening_mistakes = [s for s in user_opening_moves if s["type"] == "mistake"]
    opening_good = [s for s in user_opening_moves if s["type"] == "good"]
    challenges = [s for s in steps if s.get("is_challenge")]

    # 7. Generate key lessons using LLM if available
    key_lessons = []
    remember_lines = []

    if opening_mistakes:
        for m in opening_mistakes[:2]:
            key_lessons.append({
                "move_number": m["move_number"],
                "what_happened": f"You played {m['move_san']} but {m.get('best_move', '?')} was better.",
                "why": m["idea"],
            })

    # Simple remember lines (no LLM needed)
    remember_lines = _generate_remember_lines(chosen["name"], steps, user_color)

    # 8. LLM-enhanced narrative (cached)
    llm_narrative = None
    game_id = best_game.get("game_id", "")

    cached = await db.opening_walkthroughs.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "llm_narrative": 1}
    )
    if cached and cached.get("llm_narrative"):
        llm_narrative = cached["llm_narrative"]
    elif call_llm_func:
        llm_narrative = await _generate_walkthrough_narrative(
            chosen["name"], steps, user_color, result, opponent, call_llm_func
        )
        if llm_narrative:
            try:
                await db.opening_walkthroughs.update_one(
                    {"game_id": game_id, "user_id": user_id},
                    {"$set": {"llm_narrative": llm_narrative, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            except Exception:
                pass

    return {
        "opening": {
            "name": chosen["name"],
            "games_played": chosen["games"],
            "wins": chosen["wins"],
            "losses": chosen["losses"],
            "draws": chosen["draws"],
            "win_rate": round(chosen["wins"] / chosen["games"] * 100) if chosen["games"] > 0 else 0,
        },
        "game": {
            "game_id": game_id,
            "opponent": opponent,
            "result": result,
            "user_color": user_color,
        },
        "steps": steps,
        "challenges": challenges,
        "key_lessons": key_lessons,
        "remember": remember_lines,
        "stats": {
            "total_moves": len(steps),
            "good_moves": len(opening_good),
            "mistakes": len(opening_mistakes),
            "challenges": len(challenges),
        },
        "all_openings": [{"name": o["name"], "games": o["games"], "win_rate": round(o["wins"] / o["games"] * 100) if o["games"] > 0 else 0} for o in top_openings],
        "llm_narrative": llm_narrative,
    }


# ─── IDEA GENERATORS (simple, no LLM) ────────────────────────

def _get_good_move_idea(move_san: str, phase: str, index: int) -> str:
    if index < 4:
        ideas = {
            "e4": "Controls the center and opens lines for your bishop and queen.",
            "d4": "Takes the center. Your pieces will have more room.",
            "Nf3": "Develops a piece and controls the center. Good start.",
            "Nc3": "Develops toward the center. Ready to support e4 or d5.",
            "Bc4": "Points at f7 — the weakest square. Classic attacking setup.",
            "Bb5": "Pins the knight or pressures the center. Solid choice.",
            "c4": "English-style. Fights for d5 control.",
            "e5": "Grabs your share of the center. Equal game.",
            "d5": "Takes the center back. Aggressive response.",
            "Nf6": "Develops and attacks e4. Good defense.",
            "Nc6": "Develops and defends e5. Textbook.",
            "c5": "Fights for the center from the side. Sicilian style.",
        }
        return ideas.get(move_san, "Solid move. Keeps your position healthy.")

    if phase == "opening":
        return "Good developing move. Keeps your position strong."
    return "Solid move. No problems here."


def _get_opponent_idea(move_san: str, phase: str, index: int) -> str:
    if index < 4:
        return f"Your opponent plays {move_san}. Standard response."
    if phase == "opening":
        return f"Opponent plays {move_san}. Nothing to worry about yet."
    return f"Opponent plays {move_san}."


def _get_mistake_idea(cp_loss: int, best_move: str, phase: str) -> str:
    if cp_loss >= 300:
        return f"Big mistake. {best_move} was much better here. Let's see why."
    elif cp_loss >= 150:
        return f"This hurt your position. {best_move} keeps you in the game."
    return f"Not the best. {best_move} was stronger."


def _get_inaccuracy_idea(move_san: str, best_move: str, phase: str) -> str:
    return f"{move_san} is okay, but {best_move} was a bit better. Small difference."


def _generate_remember_lines(opening_name: str, steps: List[Dict], user_color: str) -> List[str]:
    """Generate 2-3 simple things to remember about this opening."""
    lines = []
    mistakes = [s for s in steps if s.get("type") == "mistake" and s["is_user_move"]]
    good = [s for s in steps if s.get("type") == "good" and s["is_user_move"] and s["phase"] == "opening"]

    if good:
        first_good = good[0]
        lines.append(f"Your first moves were solid. Keep playing {first_good['move_san']} confidently.")

    if mistakes:
        first_mistake = mistakes[0]
        lines.append(f"At move {first_mistake['move_number']}, play {first_mistake.get('best_move', '?')} instead of {first_mistake['move_san']}.")

    if not mistakes:
        lines.append("Your opening play was clean. Focus on having a plan after the opening ends.")
    else:
        lines.append("Before each move in the opening, ask: am I developing a piece or controlling the center?")

    return lines[:3]


async def _generate_walkthrough_narrative(
    opening_name: str, steps: List[Dict], user_color: str, result: str, opponent: str, call_llm_func
) -> Optional[Dict]:
    """LLM generates simple commentary for key steps."""
    try:
        mistakes = [s for s in steps if s.get("type") == "mistake" and s["is_user_move"]]
        good_moves = [s for s in steps if s.get("type") == "good" and s["is_user_move"] and s["phase"] == "opening"]

        system_msg = "You are a friendly chess coach teaching a beginner their opening. Write like you're talking to a friend. Super simple. Return ONLY valid JSON."

        user_msg = f"""Opening: {opening_name}
Player color: {user_color}
Result: {result}
Opponent: {opponent}

Good moves in opening: {len(good_moves)}
Mistakes: {len(mistakes)}
"""
        if mistakes:
            for m in mistakes[:2]:
                user_msg += f"  Mistake at move {m['move_number']}: played {m['move_san']}, should have played {m.get('best_move', '?')}\n"

        user_msg += """
Write a JSON object:
{
  "intro": "One sentence intro to this walkthrough. Friendly, simple.",
  "opening_idea": "In 2 short sentences, what is the MAIN IDEA of this opening? What are you trying to do?",
  "biggest_lesson": "One sentence about the biggest lesson from this game.",
  "encouragement": "One warm sentence."
}

Rules: max 12 words per sentence. No chess notation. Like talking to a 12 year old."""

        raw = await call_llm_func(system_msg, user_msg)
        if raw:
            import json
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Walkthrough LLM failed: {e}")
    return None
