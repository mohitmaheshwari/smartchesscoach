"""
Player Profile Service
======================

Generates a coaching narrative comparing the user to their rating band.
Purely observational — "who you are as a player", not prescriptive.

Regenerates every 5 games (cached in DB).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Common opening family keywords — used to group variations
_FAMILY_SUFFIXES = {"Defense", "Opening", "Game", "Gambit", "Attack", "System", "Variation", "Indian"}


def _get_opening_family(name: str) -> str:
    """Extract the base opening family from a full variation name.
    e.g. 'Scandinavian Defense Mieses Kotrc Variation 3.Nc3' -> 'Scandinavian Defense'
    e.g. 'Italian Game Two Knights Modern' -> 'Italian Game'
    """
    if not name or name in ("Unknown", "Undefined"):
        return "Other"
    parts = name.split()
    # Find the first "family keyword" and take everything up to and including it
    for i, word in enumerate(parts):
        if word in _FAMILY_SUFFIXES and i > 0:
            return " ".join(parts[:i + 1])
    # If no keyword found, take first 2 words
    return " ".join(parts[:min(2, len(parts))])


async def get_player_profile(db, user_id: str):
    """
    Return cached player profile narrative, or generate a new one
    if the user has played 5+ new games since last generation.
    """
    # Check cache
    cached = await db.player_profiles.find_one({"user_id": user_id}, {"_id": 0})
    current_game_count = await db.games.count_documents({"user_id": user_id})

    if cached and current_game_count - cached.get("games_at_generation", 0) < 5:
        return {
            "narrative": cached["narrative"],
            "generated_at": cached["generated_at"],
            "games_at_generation": cached["games_at_generation"],
            "current_game_count": current_game_count,
            "needs_refresh": False,
        }

    # Need minimum games to generate meaningful narrative
    if current_game_count < 5:
        return {
            "narrative": None,
            "current_game_count": current_game_count,
            "needs_refresh": False,
            "min_games_needed": 5,
        }

    # Gather data and generate
    profile_data = await _gather_profile_data(db, user_id)
    narrative = await _generate_narrative(profile_data)

    # Cache
    doc = {
        "user_id": user_id,
        "narrative": narrative,
        "profile_data": profile_data,
        "games_at_generation": current_game_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.player_profiles.update_one(
        {"user_id": user_id}, {"$set": doc}, upsert=True
    )

    return {
        "narrative": narrative,
        "generated_at": doc["generated_at"],
        "games_at_generation": current_game_count,
        "current_game_count": current_game_count,
        "needs_refresh": False,
    }


async def _gather_profile_data(db, user_id: str) -> dict:
    """Gather all data needed for the narrative."""

    # --- Game results ---
    games = []
    async for g in db.games.find(
        {"user_id": user_id},
        {"_id": 0, "result": 1, "user_color": 1, "opening": 1, "game_id": 1}
    ).sort("imported_at", -1).limit(30):
        games.append(g)

    total = len(games)
    wins, losses, draws = 0, 0, 0
    openings = {}
    for g in games:
        r = g.get("result", "")
        c = g.get("user_color", "")
        if (r == "1-0" and c == "white") or (r == "0-1" and c == "black"):
            wins += 1
        elif (r == "1-0" and c == "black") or (r == "0-1" and c == "white"):
            losses += 1
        elif r == "1/2-1/2":
            draws += 1
        op = g.get("opening", "Unknown")
        openings[op] = openings.get(op, 0) + 1

    top_openings = sorted(openings.items(), key=lambda x: -x[1])[:3]

    # --- Opening families (group by base name, not specific variation) ---
    opening_families = {}
    for op_name, count in openings.items():
        # Extract base family: take first 2-3 meaningful words before "Variation"/"Defense"/"Game" details
        family = _get_opening_family(op_name)
        opening_families[family] = opening_families.get(family, 0) + count
    unique_families = len(opening_families)
    top_families = sorted(opening_families.items(), key=lambda x: -x[1])[:4]
    most_played_family = top_families[0] if top_families else ("Unknown", 0)
    most_played_family_pct = round(most_played_family[1] / max(total, 1) * 100) if total > 0 else 0

    # --- Where games are decided (phase analysis from game summaries) ---
    phase_mistakes = {"opening": 0, "middlegame": 0, "endgame": 0}
    blunder_count = 0
    mistake_types = {}

    game_ids = [g["game_id"] for g in games if "game_id" in g]
    if game_ids:
        async for analysis in db.game_analyses.find(
            {"user_id": user_id, "game_id": {"$in": game_ids}},
            {"_id": 0, "game_summary": 1, "turning_point": 1, "interpretation": 1}
        ):
            # Turning point phase
            tp = analysis.get("turning_point")
            if isinstance(tp, dict) and tp.get("move_number"):
                move_num = tp["move_number"]
                if move_num <= 12:
                    phase_mistakes["opening"] += 1
                elif move_num <= 25:
                    phase_mistakes["middlegame"] += 1
                else:
                    phase_mistakes["endgame"] += 1

            # Key mistakes from summary
            summary = analysis.get("game_summary")
            if isinstance(summary, dict):
                for km in summary.get("key_mistakes", []):
                    phase = km.get("phase", "middlegame")
                    if phase in phase_mistakes:
                        phase_mistakes[phase] += 1
                    if km.get("severity") == "blunder":
                        blunder_count += 1
                    ct = km.get("concept_type", "unknown")
                    mistake_types[ct] = mistake_types.get(ct, 0) + 1

            # Interpretation breakdown
            interp = analysis.get("interpretation")
            if isinstance(interp, dict):
                rb = interp.get("reason_breakdown", {})
                for reason, count in rb.items():
                    if isinstance(count, (int, float)):
                        mistake_types[reason] = mistake_types.get(reason, 0) + count

    # Sort mistake types
    top_mistake_types = sorted(mistake_types.items(), key=lambda x: -x[1])[:3]

    # Determine where most games are lost
    worst_phase = max(phase_mistakes, key=phase_mistakes.get) if any(phase_mistakes.values()) else "middlegame"

    # --- Community comparison (aggregate from other users) ---
    other_user_count = await db.users.count_documents({"user_id": {"$ne": user_id}})
    community_games = await db.games.count_documents({"user_id": {"$ne": user_id}})

    # --- Opening diversity ---
    len(openings)
    sum(openings.values())
    most_played = top_openings[0] if top_openings else ("Unknown", 0)
    round(most_played[1] / max(total, 1) * 100) if total > 0 else 0

    # --- User rating ---
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "rating": 1, "name": 1})
    rating = user_doc.get("rating", 1200) if user_doc else 1200
    name = user_doc.get("name", "Player") if user_doc else "Player"

    return {
        "name": name,
        "rating": rating,
        "total_games": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / max(total, 1) * 100),
        "top_openings": [{"name": o[0], "count": o[1]} for o in top_openings],
        "unique_openings": unique_families,
        "top_opening_families": [{"name": f[0], "count": f[1]} for f in top_families],
        "most_played_opening": most_played_family[0],
        "most_played_opening_pct": most_played_family_pct,
        "phase_mistakes": phase_mistakes,
        "worst_phase": worst_phase,
        "blunder_count": blunder_count,
        "top_mistake_types": [{"type": t[0], "count": int(t[1])} for t in top_mistake_types],
        "other_users_in_system": other_user_count,
        "community_games": community_games,
    }


async def _generate_narrative(data: dict) -> str:
    """Generate a coaching narrative using LLM."""
    try:
        import os
        from llm_service import call_llm
        from services.coach_voice_prompt import with_coach_voice
        from config import LLM_MODEL

        needs_anthropic = LLM_MODEL.startswith("claude")
        api_key = os.environ.get("ANTHROPIC_API_KEY") if needs_anthropic else os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return _fallback_narrative(data)

        prompt = f"""Look at this player's data and tell them who they are as a chess player right now. Talk to them like their personal coach — someone who's watched all their games and knows their patterns.

RULES:
- Talk like a real Indian coach/mentor. Simple words. Straight talk. No dramatic language.
- Say what you actually see in the data. Name specific openings, specific phases.
- Do NOT give advice. Don't say "you should" or "you need to." Just tell them what you see.
- 2-3 short sentences. No essays, no fancy vocabulary.
- Use natural English the way an Indian person would speak — not American slang, not British formal.

BAD (too dramatic, too Western):
"You jump around openings like you're sampling a buffet — that's killing your start. Your tactical errors scream that something is off."

GOOD (how an Indian coach actually talks):
"You're playing too many different openings — {data['unique_openings']} families in {data['total_games']} games. That's a lot. Most of your trouble is happening early, in the opening itself, before you even reach the middlegame."

PLAYER DATA:
- Last {data['total_games']} games: {data['wins']}W / {data['losses']}L / {data['draws']}D ({data['win_rate']}% wins)
- Opening families played: {data['unique_openings']} different families
- Top openings: {', '.join(f"{o['name']} ({o['count']}x)" for o in data['top_opening_families']) or 'varied'}
- Most played: {data['most_played_opening']} ({data['most_played_opening_pct']}% of games)
- Where things go wrong most: {data['worst_phase']} (opening: {data['phase_mistakes']['opening']}, middlegame: {data['phase_mistakes']['middlegame']}, endgame: {data['phase_mistakes']['endgame']})
- Blunders: {data['blunder_count']}
- Common mistake types: {', '.join(f"{t['type']} ({t['count']}x)" for t in data['top_mistake_types']) or 'varied'}

Now write the profile. 2-3 short sentences. Simple language. Like a coach talking, not writing."""

        system_msg = "You are a chess coach in India. Talk simply and directly. No dramatic language, no metaphors, no Western slang. Honest, clear observations about the player — like talking to your student after watching their games. 2-3 short sentences."

        response = await call_llm(
            system_message=with_coach_voice(system_msg),
            user_message=prompt,
            model=LLM_MODEL,
            max_tokens=512,
        )
        narrative = response.strip().strip('"').strip("'")
        return narrative

    except Exception as e:
        logger.error(f"Failed to generate player profile narrative: {e}")
        return _fallback_narrative(data)


def _fallback_narrative(data: dict) -> str:
    """Generate a simple narrative without LLM if the API fails."""
    parts = []

    # Win rate characterization
    wr = data["win_rate"]
    if wr >= 60:
        parts.append(f"You're winning {wr}% of your recent games — that's a strong run.")
    elif wr >= 45:
        parts.append(f"Your recent form sits at {wr}% wins across {data['total_games']} games — competitive at your level.")
    else:
        parts.append(f"You're in a tough stretch at {wr}% wins over your last {data['total_games']} games.")

    # Phase characterization
    wp = data["worst_phase"]
    if wp == "opening":
        parts.append("Most of your trouble starts early — your games tend to go wrong in the opening.")
    elif wp == "endgame":
        parts.append("Your games are typically decided in the endgame — that's where the critical moments happen.")
    else:
        parts.append("The middlegame is where your games swing — that's your battlefield.")

    # Opening identity
    if data["most_played_opening_pct"] > 30:
        parts.append(f"You lean towards the {data['most_played_opening']} mostly.")
    elif data["unique_openings"] > 8:
        parts.append(f"You play quite a few different openings — {data['unique_openings']} families recently.")

    return " ".join(parts[:3])
