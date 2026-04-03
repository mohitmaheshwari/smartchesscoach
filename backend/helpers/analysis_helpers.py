"""
Analysis Helpers
================

Shared helper functions extracted from server.py that are used by
multiple route files.

Functions:
- compute_recurring_pattern_context: Detect recurring mistake patterns across games
- parse_pgn_games: Parse PGN text and extract structured game data
"""

from datetime import datetime, timezone, timedelta
from collections import Counter
from typing import List, Dict
import re


# ECO code to opening name mapping
ECO_TO_OPENING = {
    "A00": "Uncommon Opening", "A01": "Nimzowitsch-Larsen Attack", "A04": "Reti Opening",
    "A10": "English Opening", "A20": "English Opening", "A40": "Queen's Pawn Game",
    "A45": "Indian Defense", "A80": "Dutch Defense",
    "B00": "Uncommon King's Pawn", "B01": "Scandinavian Defense", "B02": "Alekhine's Defense",
    "B06": "Modern Defense", "B07": "Pirc Defense", "B10": "Caro-Kann Defense",
    "B20": "Sicilian Defense", "B21": "Sicilian Defense", "B22": "Sicilian Defense",
    "B23": "Sicilian Defense", "B27": "Sicilian Defense", "B30": "Sicilian Defense",
    "B40": "Sicilian Defense", "B50": "Sicilian Defense", "B90": "Sicilian Najdorf",
    "C00": "French Defense", "C01": "French Defense", "C02": "French Defense",
    "C10": "French Defense", "C20": "King's Pawn Game", "C21": "Danish Gambit",
    "C24": "Bishop's Opening", "C25": "Vienna Game", "C30": "King's Gambit",
    "C40": "King's Knight Opening", "C41": "Philidor Defense", "C42": "Petrov Defense",
    "C44": "Scotch Game", "C45": "Scotch Game", "C46": "Three Knights Game",
    "C47": "Four Knights Game", "C50": "Italian Game", "C51": "Evans Gambit",
    "C52": "Evans Gambit", "C53": "Italian Game", "C54": "Italian Game", "C55": "Two Knights Defense",
    "C60": "Ruy Lopez", "C61": "Ruy Lopez", "C62": "Ruy Lopez", "C63": "Ruy Lopez",
    "C64": "Ruy Lopez", "C65": "Ruy Lopez", "C70": "Ruy Lopez", "C80": "Ruy Lopez",
    "D00": "Queen's Pawn Game", "D02": "London System", "D04": "Colle System",
    "D06": "Queen's Gambit", "D10": "Slav Defense", "D20": "Queen's Gambit Accepted",
    "D30": "Queen's Gambit Declined", "D35": "Queen's Gambit Declined",
    "D37": "Queen's Gambit Declined", "D50": "Queen's Gambit Declined",
    "E00": "Indian Defense", "E10": "Queen's Indian Defense", "E12": "Queen's Indian Defense",
    "E20": "Nimzo-Indian Defense", "E30": "Nimzo-Indian Defense",
    "E60": "King's Indian Defense", "E70": "King's Indian Defense",
    "E80": "King's Indian Defense", "E90": "King's Indian Defense",
}


async def compute_recurring_pattern_context(
    db,
    user_id: str,
    current_game_id: str,
    stockfish_eval: list,
    blunders: list
) -> dict:
    """
    Compute recurring pattern context for the coach memory.

    Returns information like:
    - "This is the 3rd game this week with threat blindness"
    - "You've had this pattern 5 times in the last 10 games"
    - Whether this pattern is improving or worsening

    This is what makes the coach feel like it REMEMBERS.
    """
    # Determine the primary pattern in THIS game
    current_pattern = None
    pattern_context = {
        "has_recurring": False,
        "pattern_name": None,
        "occurrence_count_week": 0,
        "occurrence_count_month": 0,
        "trend": "stable",
        "coach_memory_line": None,
        "games_with_pattern": [],
    }

    # Classify the mistakes in this game
    game_patterns = []
    for m in stockfish_eval:
        if m.get("evaluation") in ["blunder", "mistake"]:
            cp_loss = m.get("cp_loss", 0)
            eval_before = m.get("eval_before", 0)

            if cp_loss >= 150:
                if eval_before > 1.0:
                    game_patterns.append("blunder_when_winning")
                elif eval_before < -1.0:
                    game_patterns.append("blunder_when_losing")
                else:
                    game_patterns.append("blunder_in_equal_position")

    for b in blunders:
        cat = b.get("mistake_category", "")
        if "ignored_opponent" in cat or "forcing" in cat.lower():
            game_patterns.append("threat_blindness")

    if not game_patterns:
        return pattern_context

    pattern_counts = Counter(game_patterns)
    current_pattern, _ = pattern_counts.most_common(1)[0]
    pattern_context["pattern_name"] = current_pattern

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    recent_analyses = await db.game_analyses.find(
        {
            "user_id": user_id,
            "game_id": {"$ne": current_game_id}
        },
        {"game_id": 1, "stockfish_analysis": 1, "blunders": 1, "created_at": 1, "analyzed_at": 1}
    ).sort("created_at", -1).limit(50).to_list(50)

    week_count = 0
    month_count = 0
    games_with_pattern = []

    for a in recent_analyses:
        sf = a.get("stockfish_analysis", {})
        game_blunders = a.get("blunders", [])
        game_date = a.get("analyzed_at") or a.get("created_at")

        has_pattern = False
        for m in sf.get("move_evaluations", []):
            if m.get("evaluation") in ["blunder", "mistake"]:
                cp_loss = m.get("cp_loss", 0)
                eval_before = m.get("eval_before", 0)

                if current_pattern == "blunder_when_winning" and eval_before > 1.0 and cp_loss >= 150:
                    has_pattern = True
                    break
                elif current_pattern == "blunder_when_losing" and eval_before < -1.0 and cp_loss >= 150:
                    has_pattern = True
                    break
                elif current_pattern == "blunder_in_equal_position" and abs(eval_before) <= 1.0 and cp_loss >= 150:
                    has_pattern = True
                    break

        if current_pattern == "threat_blindness":
            for b in game_blunders:
                cat = b.get("mistake_category", "")
                if "ignored_opponent" in cat or "forcing" in cat.lower():
                    has_pattern = True
                    break

        if has_pattern:
            games_with_pattern.append(a.get("game_id"))

            if game_date:
                if isinstance(game_date, str):
                    try:
                        game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                    except:
                        game_date = None

                if game_date:
                    if game_date > week_ago:
                        week_count += 1
                    if game_date > month_ago:
                        month_count += 1

    pattern_context["occurrence_count_week"] = week_count
    pattern_context["occurrence_count_month"] = month_count
    pattern_context["games_with_pattern"] = games_with_pattern[:5]

    if week_count >= 2:
        pattern_context["has_recurring"] = True
        if week_count >= 4:
            pattern_context["trend"] = "worsening"
        elif week_count <= 1 and month_count >= 4:
            pattern_context["trend"] = "improving"

    pattern_labels = {
        "blunder_when_winning": "losing focus when ahead",
        "blunder_when_losing": "panicking when behind",
        "blunder_in_equal_position": "missing threats in balanced positions",
        "threat_blindness": "missing opponent threats",
    }

    pattern_label = pattern_labels.get(current_pattern, current_pattern.replace("_", " "))

    if week_count >= 3:
        pattern_context["coach_memory_line"] = f"This is familiar. You've had {week_count} games this week with {pattern_label}."
    elif week_count >= 1:
        pattern_context["coach_memory_line"] = f"I've seen this before. {pattern_label.capitalize()} appeared {week_count + 1} times recently."
    elif month_count >= 3:
        pattern_context["coach_memory_line"] = f"This pattern has come up {month_count} times this month."
    else:
        pattern_context["coach_memory_line"] = None

    return pattern_context


def parse_pgn_games(pgn_text: str, platform: str, user_username: str) -> List[Dict]:
    """Parse PGN text and extract games"""
    games = []
    current_game = {}
    moves = []

    for line in pgn_text.split('\n'):
        line = line.strip()
        if not line:
            if current_game and moves:
                current_game['pgn_moves'] = ' '.join(moves)
                games.append(current_game)
                current_game = {}
                moves = []
            continue

        if line.startswith('['):
            match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if match:
                key, value = match.groups()
                current_game[key.lower()] = value
        else:
            moves.append(line)

    if current_game and moves:
        current_game['pgn_moves'] = ' '.join(moves)
        games.append(current_game)

    parsed_games = []
    for g in games:
        white = g.get('white', 'Unknown')
        black = g.get('black', 'Unknown')
        user_color = 'white' if white.lower() == user_username.lower() else 'black'

        full_pgn = ""
        for key, value in g.items():
            if key != 'pgn_moves':
                full_pgn += f'[{key.capitalize()} "{value}"]\n'
        full_pgn += f'\n{g.get("pgn_moves", "")}'

        opening_name = g.get('opening', '')
        eco_code = g.get('eco', '')

        if not opening_name and eco_code:
            opening_name = ECO_TO_OPENING.get(eco_code)
            if not opening_name:
                eco_prefix = eco_code[:2] + "0" if len(eco_code) >= 2 else eco_code
                opening_name = ECO_TO_OPENING.get(eco_prefix, f"ECO {eco_code}")

        parsed_games.append({
            'platform': platform,
            'pgn': full_pgn,
            'white_player': white,
            'black_player': black,
            'result': g.get('result', '*'),
            'time_control': g.get('timecontrol', g.get('event', '')),
            'date_played': g.get('date', g.get('utcdate', '')),
            'opening': opening_name or eco_code,
            'user_color': user_color
        })

    return parsed_games
