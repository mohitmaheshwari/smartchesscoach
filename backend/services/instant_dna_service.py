"""
Instant Chess DNA Service
=========================

Generates a comprehensive player profile from PGN data alone — NO Stockfish needed.
Designed to run in <3 seconds on 20-30 games, giving new users an instant "wow" moment.

This is the first thing a user sees after connecting their Chess.com/Lichess account.
It needs to feel like the coach already knows them.

Data sources:
- PGN headers (opening, ECO, result, time control, ratings)
- PGN moves (castling, game length, piece development)
- PGN clock annotations (time management, if available)
"""

import chess
import chess.pgn
import io
import re
import logging
from typing import Dict, List, Optional, Tuple
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── ARCHETYPE DEFINITIONS ───

ARCHETYPES = {
    "tactical_attacker": {
        "label": "Tactical Attacker",
        "description": "You play sharp, aggressive chess. Short games, decisive results.",
        "emoji": "sword",
    },
    "positional_grinder": {
        "label": "Positional Grinder",
        "description": "You play long, strategic games. Patient and methodical.",
        "emoji": "shield",
    },
    "rapid_warrior": {
        "label": "Rapid Warrior",
        "description": "You thrive in fast time controls. Quick decisions, sharp instincts.",
        "emoji": "zap",
    },
    "endgame_specialist": {
        "label": "Endgame Specialist",
        "description": "Your games go deep. You convert advantages in the endgame.",
        "emoji": "crown",
    },
    "opening_theorist": {
        "label": "Opening Theorist",
        "description": "You know your openings well. Strong preparation, consistent repertoire.",
        "emoji": "book",
    },
    "all_rounder": {
        "label": "All-Rounder",
        "description": "Balanced play across all phases. Adaptable and well-rounded.",
        "emoji": "target",
    },
    "aggressive_gambler": {
        "label": "Aggressive Gambler",
        "description": "You take risks. Big wins and big losses — never boring.",
        "emoji": "flame",
    },
    "solid_defender": {
        "label": "Solid Defender",
        "description": "You rarely blunder. Patient, careful, hard to beat.",
        "emoji": "wall",
    },
}


def compute_instant_dna(games: List[Dict]) -> Dict:
    """
    Compute a full Chess DNA report from raw game data (PGN + metadata).
    No Stockfish. No engine. Pure PGN parsing + stats.

    Args:
        games: List of game dicts from db.games collection.
               Each must have: pgn, result, user_color, opening (optional)

    Returns:
        Complete DNA report dict.
    """
    if not games:
        return _empty_report()

    total = len(games)
    start_time = datetime.now(timezone.utc)

    # ── BASIC STATS ──
    wins = 0
    losses = 0
    draws = 0
    white_games = 0
    white_wins = 0
    black_games = 0
    black_wins = 0

    for g in games:
        result = g.get("result", "")
        uc = g.get("user_color", "white")
        won = (result == "1-0" and uc == "white") or (result == "0-1" and uc == "black")
        lost = (result == "0-1" and uc == "white") or (result == "1-0" and uc == "black")
        drew = "1/2" in result

        if won:
            wins += 1
        elif lost:
            losses += 1
        elif drew:
            draws += 1

        if uc == "white":
            white_games += 1
            if won:
                white_wins += 1
        else:
            black_games += 1
            if won:
                black_wins += 1

    # ── OPENING REPERTOIRE ──
    white_openings = Counter()
    white_opening_wins = Counter()
    black_openings = Counter()
    black_opening_wins = Counter()

    for g in games:
        opening = g.get("opening", "") or _extract_opening_from_pgn(g.get("pgn", ""))
        if not opening or opening == "Unknown":
            continue
        uc = g.get("user_color", "white")
        result = g.get("result", "")
        won = (result == "1-0" and uc == "white") or (result == "0-1" and uc == "black")

        if uc == "white":
            white_openings[opening] += 1
            if won:
                white_opening_wins[opening] += 1
        else:
            black_openings[opening] += 1
            if won:
                black_opening_wins[opening] += 1

    top_white = [
        {
            "name": name,
            "games": count,
            "wins": white_opening_wins.get(name, 0),
            "win_rate": round((white_opening_wins.get(name, 0) / count) * 100, 1) if count > 0 else 0,
        }
        for name, count in white_openings.most_common(5)
    ]

    top_black = [
        {
            "name": name,
            "games": count,
            "wins": black_opening_wins.get(name, 0),
            "win_rate": round((black_opening_wins.get(name, 0) / count) * 100, 1) if count > 0 else 0,
        }
        for name, count in black_openings.most_common(5)
    ]

    best_opening = None
    all_openings = [(o, "white") for o in top_white] + [(o, "black") for o in top_black]
    for o, color in all_openings:
        if o["games"] >= 2:
            if best_opening is None or o["win_rate"] > best_opening["win_rate"]:
                best_opening = {**o, "color": color}

    # ── GAME LENGTH & STYLE ──
    game_lengths = []
    castling_moves = []
    castled_count = 0
    kingside_castles = 0
    queenside_castles = 0
    endgame_count = 0
    resignation_count = 0
    time_profiles = []

    for g in games:
        pgn_str = g.get("pgn", "")
        if not pgn_str:
            continue

        try:
            pgn_io = io.StringIO(pgn_str)
            game_obj = chess.pgn.read_game(pgn_io)
            if not game_obj:
                continue

            board = game_obj.board()
            uc = g.get("user_color", "white")
            user_is_white = uc == "white"
            move_count = 0
            user_castled = False
            user_castle_move = None

            for node in game_obj.mainline():
                move = node.move
                move_count += 1
                is_white_move = board.turn == chess.WHITE
                is_user_move = (user_is_white and is_white_move) or (not user_is_white and not is_white_move)

                if is_user_move and board.is_castling(move):
                    user_castled = True
                    user_castle_move = (move_count + 1) // 2
                    if board.is_kingside_castling(move):
                        kingside_castles += 1
                    else:
                        queenside_castles += 1

                board.push(move)

            full_moves = (move_count + 1) // 2
            game_lengths.append(full_moves)

            if user_castled:
                castled_count += 1
                castling_moves.append(user_castle_move)

            if full_moves >= 40:
                endgame_count += 1

            # Check if game ended by resignation (no checkmate)
            result = g.get("result", "")
            if result in ("1-0", "0-1") and not board.is_checkmate():
                resignation_count += 1

            # ── TIME DATA (from PGN clock annotations) ──
            time_profile = _extract_basic_time_data(pgn_str, user_is_white)
            if time_profile:
                time_profiles.append(time_profile)

        except Exception as e:
            logger.debug(f"PGN parse error in instant DNA: {e}")
            continue

    avg_game_length = round(sum(game_lengths) / len(game_lengths), 1) if game_lengths else 0
    avg_castle_move = round(sum(castling_moves) / len(castling_moves), 1) if castling_moves else 0
    castle_rate = round((castled_count / total) * 100, 1) if total > 0 else 0
    endgame_rate = round((endgame_count / total) * 100, 1) if total > 0 else 0
    resignation_rate = round((resignation_count / max(wins + losses, 1)) * 100, 1)

    # ── TIME MANAGEMENT ──
    time_summary = None
    if time_profiles:
        all_avg_times = [t["avg_time_per_move"] for t in time_profiles if t.get("avg_time_per_move")]
        all_pressure = [t["time_pressure_pct"] for t in time_profiles if t.get("time_pressure_pct") is not None]
        all_rushed = [t["rushed_move_pct"] for t in time_profiles if t.get("rushed_move_pct") is not None]

        time_summary = {
            "avg_time_per_move": round(sum(all_avg_times) / len(all_avg_times), 1) if all_avg_times else None,
            "time_pressure_pct": round(sum(all_pressure) / len(all_pressure), 1) if all_pressure else None,
            "rushed_move_pct": round(sum(all_rushed) / len(all_rushed), 1) if all_rushed else None,
            "games_with_clock_data": len(time_profiles),
        }

    # ── TIME CONTROL BREAKDOWN ──
    time_controls = Counter()
    for g in games:
        tc = g.get("time_control", "") or ""
        tc_label = _classify_time_control(tc)
        time_controls[tc_label] += 1

    format_profile = [
        {"format": fmt, "games": count, "pct": round((count / total) * 100, 1)}
        for fmt, count in time_controls.most_common()
    ]
    preferred_format = time_controls.most_common(1)[0][0] if time_controls else "Unknown"

    # ── RATING ──
    ratings = []
    for g in games:
        pgn_str = g.get("pgn", "")
        uc = g.get("user_color", "white")
        tag = "WhiteElo" if uc == "white" else "BlackElo"
        m = re.search(rf'\[{tag} "(\d+)"\]', pgn_str)
        if m:
            ratings.append(int(m.group(1)))

    current_rating = ratings[-1] if ratings else None
    earliest_rating = ratings[0] if ratings else None
    rating_change = (ratings[-1] - ratings[0]) if len(ratings) >= 2 else None

    # ── OPPONENT STRENGTH ──
    opp_ratings = []
    for g in games:
        pgn_str = g.get("pgn", "")
        uc = g.get("user_color", "white")
        opp_tag = "BlackElo" if uc == "white" else "WhiteElo"
        m = re.search(rf'\[{opp_tag} "(\d+)"\]', pgn_str)
        if m:
            opp_ratings.append(int(m.group(1)))
    avg_opponent = round(sum(opp_ratings) / len(opp_ratings)) if opp_ratings else None

    # ── DETERMINE ARCHETYPE ──
    archetype = _determine_archetype(
        avg_game_length=avg_game_length,
        win_rate=round((wins / total) * 100, 1) if total > 0 else 0,
        endgame_rate=endgame_rate,
        castle_rate=castle_rate,
        resignation_rate=resignation_rate,
        preferred_format=preferred_format,
        opening_diversity=len(white_openings) + len(black_openings),
        total_games=total,
    )

    # ── GENERATE INSIGHTS ──
    insights = _generate_insights(
        wins=wins, losses=losses, draws=draws, total=total,
        white_win_rate=round((white_wins / white_games) * 100, 1) if white_games > 0 else 0,
        black_win_rate=round((black_wins / black_games) * 100, 1) if black_games > 0 else 0,
        avg_game_length=avg_game_length,
        castle_rate=castle_rate,
        avg_castle_move=avg_castle_move,
        endgame_rate=endgame_rate,
        best_opening=best_opening,
        time_summary=time_summary,
    )

    elapsed_ms = round((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_time_ms": elapsed_ms,
        "games_analyzed": total,

        "archetype": ARCHETYPES.get(archetype, ARCHETYPES["all_rounder"]),
        "archetype_key": archetype,

        "record": {
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round((wins / total) * 100, 1) if total > 0 else 0,
            "white_win_rate": round((white_wins / white_games) * 100, 1) if white_games > 0 else 0,
            "black_win_rate": round((black_wins / black_games) * 100, 1) if black_games > 0 else 0,
        },

        "opening_repertoire": {
            "white": top_white,
            "black": top_black,
            "best_opening": best_opening,
            "diversity": len(white_openings) + len(black_openings),
        },

        "playing_style": {
            "avg_game_length": avg_game_length,
            "endgame_frequency": endgame_rate,
            "resignation_rate": resignation_rate,
            "style_label": "Tactical" if avg_game_length < 30 else "Positional" if avg_game_length > 45 else "Balanced",
        },

        "king_safety": {
            "castle_rate": castle_rate,
            "avg_castle_move": avg_castle_move,
            "kingside_pct": round((kingside_castles / max(castled_count, 1)) * 100, 1),
            "queenside_pct": round((queenside_castles / max(castled_count, 1)) * 100, 1),
            "assessment": _castle_assessment(castle_rate, avg_castle_move),
        },

        "time_management": time_summary,

        "format_profile": format_profile,
        "preferred_format": preferred_format,

        "rating": {
            "current": current_rating,
            "earliest": earliest_rating,
            "change": rating_change,
            "trend": "improving" if rating_change and rating_change > 20 else "declining" if rating_change and rating_change < -20 else "stable",
            "avg_opponent": avg_opponent,
        },

        "insights": insights,
    }


# ─── HELPERS ───

def _extract_opening_from_pgn(pgn_str: str) -> str:
    """Extract opening name from PGN headers."""
    m = re.search(r'\[Opening "([^"]+)"\]', pgn_str)
    if m:
        return m.group(1)
    m = re.search(r'\[ECO "([^"]+)"\]', pgn_str)
    if m:
        from helpers.analysis_helpers import ECO_TO_OPENING
        return ECO_TO_OPENING.get(m.group(1), m.group(1))
    return ""


def _extract_basic_time_data(pgn_str: str, user_is_white: bool) -> Optional[Dict]:
    """Extract basic time stats from PGN clock annotations."""
    clock_pattern = r'\{.*?\[%clk (\d+:\d+:\d+(?:\.\d+)?)\].*?\}'
    clocks = re.findall(clock_pattern, pgn_str)
    if len(clocks) < 4:
        return None

    # Parse all clock times
    def parse_clock(s):
        parts = s.split(':')
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except (ValueError, IndexError):
            return 0

    all_clocks = [parse_clock(c) for c in clocks]

    # Split by player (alternating)
    user_clocks = all_clocks[0::2] if user_is_white else all_clocks[1::2]

    if len(user_clocks) < 2:
        return None

    # Calculate time spent per move
    time_spent = []
    for i in range(1, len(user_clocks)):
        spent = user_clocks[i - 1] - user_clocks[i]
        if spent > 0:
            time_spent.append(spent)

    if not time_spent:
        return None

    avg_time = sum(time_spent) / len(time_spent)
    rushed = sum(1 for t in time_spent if t < 3)
    pressure = sum(1 for c in user_clocks if c < 30)

    return {
        "avg_time_per_move": round(avg_time, 1),
        "time_pressure_pct": round((pressure / len(user_clocks)) * 100, 1),
        "rushed_move_pct": round((rushed / len(time_spent)) * 100, 1),
    }


def _classify_time_control(tc: str) -> str:
    """Classify time control string into a format label."""
    if not tc:
        return "Unknown"
    m = re.match(r'(\d+)\+?(\d+)?', tc.replace('|', '+'))
    if not m:
        return "Unknown"
    base = int(m.group(1))
    inc = int(m.group(2)) if m.group(2) else 0
    total_est = base + inc * 40  # Estimate total game time
    if total_est < 180:
        return "Bullet"
    elif total_est < 600:
        return "Blitz"
    elif total_est < 1800:
        return "Rapid"
    else:
        return "Classical"


def _castle_assessment(castle_rate: float, avg_move: float) -> str:
    if castle_rate < 50:
        return "You often skip castling — your king is exposed in many games."
    elif avg_move <= 8:
        return "Great king safety. You castle early and consistently."
    elif avg_move <= 12:
        return "You castle regularly but sometimes delay it."
    else:
        return "You castle late. Consider prioritizing king safety earlier."


def _determine_archetype(
    avg_game_length, win_rate, endgame_rate, castle_rate,
    resignation_rate, preferred_format, opening_diversity, total_games
) -> str:
    # Score each archetype
    scores = {k: 0 for k in ARCHETYPES}

    # Short games + high win rate = tactical attacker
    if avg_game_length < 28:
        scores["tactical_attacker"] += 3
    if avg_game_length < 22:
        scores["tactical_attacker"] += 2
        scores["aggressive_gambler"] += 2

    # Long games = positional grinder or endgame specialist
    if avg_game_length > 40:
        scores["positional_grinder"] += 3
        scores["endgame_specialist"] += 2
    elif avg_game_length > 35:
        scores["positional_grinder"] += 1

    # Endgame rate
    if endgame_rate > 50:
        scores["endgame_specialist"] += 3
    elif endgame_rate > 30:
        scores["endgame_specialist"] += 1

    # Format preference
    if preferred_format in ("Bullet", "Blitz"):
        scores["rapid_warrior"] += 3
    elif preferred_format == "Rapid":
        scores["rapid_warrior"] += 1

    # Opening diversity
    if opening_diversity >= 8:
        scores["opening_theorist"] += 2
    elif opening_diversity <= 3 and total_games >= 10:
        scores["solid_defender"] += 1

    # Castle rate
    if castle_rate >= 85:
        scores["solid_defender"] += 2
    elif castle_rate < 50:
        scores["aggressive_gambler"] += 2

    # Win rate
    if win_rate > 55:
        scores["all_rounder"] += 1
    if win_rate < 40:
        scores["aggressive_gambler"] += 1  # Losing a lot = taking risks

    # Resignation
    if resignation_rate > 70:
        scores["solid_defender"] += 1  # Knows when to resign

    # Pick highest
    best = max(scores, key=scores.get)
    if scores[best] <= 1:
        return "all_rounder"
    return best


def _generate_insights(
    wins, losses, draws, total,
    white_win_rate, black_win_rate,
    avg_game_length, castle_rate, avg_castle_move,
    endgame_rate, best_opening, time_summary
) -> List[str]:
    """Generate 3-5 human-readable insights."""
    insights = []

    # Color imbalance
    diff = abs(white_win_rate - black_win_rate)
    if diff > 15:
        better = "White" if white_win_rate > black_win_rate else "Black"
        worse = "Black" if better == "White" else "White"
        insights.append(f"You win {round(max(white_win_rate, black_win_rate))}% as {better} but only {round(min(white_win_rate, black_win_rate))}% as {worse}. Your {worse} repertoire needs work.")

    # Best opening
    if best_opening and best_opening.get("games", 0) >= 2:
        insights.append(f"Your best opening: {best_opening['name']} ({best_opening['win_rate']:.0f}% win rate over {best_opening['games']} games).")

    # Game length
    if avg_game_length < 25:
        insights.append(f"Your games average {avg_game_length:.0f} moves — you play fast, decisive chess.")
    elif avg_game_length > 42:
        insights.append(f"Your games average {avg_game_length:.0f} moves — you're a patient, strategic player.")

    # Castling
    if castle_rate < 60:
        insights.append(f"You only castle in {castle_rate:.0f}% of games. This leaves your king vulnerable.")
    elif avg_castle_move > 0 and avg_castle_move <= 7:
        insights.append(f"You castle early (move {avg_castle_move:.0f} on average) — great king safety habit.")

    # Time management
    if time_summary and time_summary.get("rushed_move_pct") is not None:
        if time_summary["rushed_move_pct"] > 25:
            insights.append(f"{time_summary['rushed_move_pct']:.0f}% of your moves are rushed (<3 seconds). Slow down on critical positions.")
        elif time_summary.get("avg_time_per_move") and time_summary["avg_time_per_move"] > 20:
            insights.append(f"You average {time_summary['avg_time_per_move']:.0f}s per move — deep thinker. Make sure you don't run into time trouble.")

    # Win rate
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0
    if win_rate > 55:
        insights.append(f"Your {win_rate:.0f}% win rate is above average. You're playing above your rating.")
    elif win_rate < 40:
        insights.append(f"Your {win_rate:.0f}% win rate suggests you're being challenged. That's how you improve.")

    return insights[:5]


def _empty_report() -> Dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_time_ms": 0,
        "games_analyzed": 0,
        "archetype": ARCHETYPES["all_rounder"],
        "archetype_key": "all_rounder",
        "record": {"wins": 0, "losses": 0, "draws": 0, "win_rate": 0, "white_win_rate": 0, "black_win_rate": 0},
        "opening_repertoire": {"white": [], "black": [], "best_opening": None, "diversity": 0},
        "playing_style": {"avg_game_length": 0, "endgame_frequency": 0, "resignation_rate": 0, "style_label": "Unknown"},
        "king_safety": {"castle_rate": 0, "avg_castle_move": 0, "kingside_pct": 0, "queenside_pct": 0, "assessment": "No data yet."},
        "time_management": None,
        "format_profile": [],
        "preferred_format": "Unknown",
        "rating": {"current": None, "earliest": None, "change": None, "trend": "stable", "avg_opponent": None},
        "insights": ["Import your games to discover your Chess DNA."],
    }
