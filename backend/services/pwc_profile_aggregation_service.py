"""
PWC Profile Aggregation Service

Aggregates Play-mode PWC games into player_profiles and player_identities.
Extracts: move quality, tactical patterns, opening repertoire, endgame conversion, time resilience.

Called after play-mode games complete and are analyzed.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import chess

logger = logging.getLogger(__name__)


async def aggregate_pwc_games_into_profile(db, user_id: str, min_games: int = 5):
    """
    Aggregate last N play-mode PWC games into player_profiles and player_identities.

    Called after a play-mode game is analyzed. Builds deep understanding:
    - Move quality distribution (blunder %, mistake %, good %)
    - Tactical pattern mastery (forks/pins/skewers recognition)
    - Opening repertoire (openings played, accuracy)
    - Endgame conversion (win %, hold %)
    - Time resilience (blunder rate under time pressure)

    Args:
        db: MongoDB database
        user_id: User ID
        min_games: Minimum play-mode games to aggregate (default 5)
    """
    try:
        # Fetch last N play-mode games with analysis
        play_mode_games = await db.coach_sessions.find({
            "user_id": user_id,
            "game_mode": "play",
            "status": {"$in": ["completed", "abandoned"]},  # only finished games
        }).sort("created_at", -1).limit(20).to_list(20)

        if len(play_mode_games) < min_games:
            logger.info(f"[PWC-Profile] User {user_id} has {len(play_mode_games)} play-mode games (need {min_games}), skipping")
            return None

        logger.info(f"[PWC-Profile] Aggregating {len(play_mode_games)} play-mode games for {user_id}")

        # Initialize aggregators
        profile_data = {
            "user_id": user_id,
            "source": "pwc_play_mode",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "games_analyzed": len(play_mode_games),

            # Move quality distribution
            "move_quality": {
                "blunders": 0,
                "mistakes": 0,
                "inaccuracies": 0,
                "goods": 0,
                "blunder_rate": 0.0,  # % of user moves
                "mistake_rate": 0.0,
                "accuracy_rate": 0.0,  # combined good + accidental
            },

            # Tactical patterns
            "tactical_patterns": {
                "forks_missed": 0,
                "pins_missed": 0,
                "skewers_missed": 0,
                "tactical_recognition_rate": 0.0,
            },

            # Opening repertoire
            "opening_repertoire": {},  # {opening_name: {games: N, accuracy: X%}}

            # Endgame conversion
            "endgame_conversion": {
                "winning_positions": 0,
                "won_from_winning": 0,
                "conversion_rate": 0.0,
                "drawn_positions": 0,
                "held_draws": 0,
                "hold_rate": 0.0,
            },

            # Time resilience
            "time_resilience": {
                "blunders_with_time": 0,
                "total_moves_with_time": 0,
                "time_pressure_blunder_rate": 0.0,
            },
        }

        total_user_moves = 0

        # Process each game
        for session_idx, session in enumerate(play_mode_games):
            session_id = session.get("session_id")
            fen_history = session.get("fen_history", [])
            move_history = session.get("move_history", [])
            result = session.get("result", {})
            user_color = session.get("user_color", "white")

            # Fetch game analysis
            analysis = await db.game_analyses.find_one({"session_id": session_id})
            if not analysis:
                logger.debug(f"[PWC-Profile] No analysis found for session {session_id}, skipping")
                continue

            move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

            # ─── MOVE QUALITY ───
            for move_idx, move_eval in enumerate(move_evals):
                is_user_move = not move_eval.get("is_opponent_move", False)
                if is_user_move:
                    total_user_moves += 1
                    cp_loss = move_eval.get("cp_loss", 0)

                    # Classify based on rating bands (use user's current rating)
                    user_rating = session.get("user_rating", 1200)
                    if user_rating < 1000:
                        if cp_loss < -300: profile_data["move_quality"]["blunders"] += 1
                        elif cp_loss < -150: profile_data["move_quality"]["mistakes"] += 1
                        elif cp_loss < -50: profile_data["move_quality"]["inaccuracies"] += 1
                        else: profile_data["move_quality"]["goods"] += 1
                    elif user_rating < 1400:
                        if cp_loss < -200: profile_data["move_quality"]["blunders"] += 1
                        elif cp_loss < -75: profile_data["move_quality"]["mistakes"] += 1
                        elif cp_loss < -20: profile_data["move_quality"]["inaccuracies"] += 1
                        else: profile_data["move_quality"]["goods"] += 1
                    elif user_rating < 1800:
                        if cp_loss < -150: profile_data["move_quality"]["blunders"] += 1
                        elif cp_loss < -50: profile_data["move_quality"]["mistakes"] += 1
                        elif cp_loss < -15: profile_data["move_quality"]["inaccuracies"] += 1
                        else: profile_data["move_quality"]["goods"] += 1
                    else:
                        if cp_loss < -100: profile_data["move_quality"]["blunders"] += 1
                        elif cp_loss < -30: profile_data["move_quality"]["mistakes"] += 1
                        elif cp_loss < -10: profile_data["move_quality"]["inaccuracies"] += 1
                        else: profile_data["move_quality"]["goods"] += 1

                    # Time resilience: check if move was under time pressure
                    time_spent = move_eval.get("time_spent", 0)
                    if time_spent < 5:  # Less than 5 seconds = time pressure
                        profile_data["time_resilience"]["total_moves_with_time"] += 1
                        if cp_loss < -150:  # Blunder under time
                            profile_data["time_resilience"]["blunders_with_time"] += 1

                    # ─── TACTICAL PATTERNS ───
                    cognitive_gap = move_eval.get("cognitive_gap")
                    if cognitive_gap == "missed_tactic":
                        profile_data["tactical_patterns"]["forks_missed"] += 1
                    elif cognitive_gap == "tactical_oversight":
                        profile_data["tactical_patterns"]["pins_missed"] += 1

            # ─── OPENING REPERTOIRE ───
            # Detect opening from first 10 plies
            opening_name = _detect_opening(fen_history, move_history, user_color)
            if opening_name:
                if opening_name not in profile_data["opening_repertoire"]:
                    profile_data["opening_repertoire"][opening_name] = {"games": 0, "accuracy": 0.0}
                profile_data["opening_repertoire"][opening_name]["games"] += 1
                # Calculate opening accuracy (moves in opening that weren't mistakes)
                opening_accuracy = _calculate_opening_accuracy(move_evals[:20])
                profile_data["opening_repertoire"][opening_name]["accuracy"] = opening_accuracy

            # ─── ENDGAME CONVERSION ───
            # Check if game reached endgame (queens off or < 2 bishops)
            final_fen = fen_history[-1] if fen_history else ""
            if _is_endgame(final_fen):
                if result.get("result") == "win" and (result.get("winner") == user_color if result.get("winner") else False):
                    profile_data["endgame_conversion"]["winning_positions"] += 1
                    profile_data["endgame_conversion"]["won_from_winning"] += 1
                elif result.get("result") == "draw":
                    profile_data["endgame_conversion"]["drawn_positions"] += 1
                    profile_data["endgame_conversion"]["held_draws"] += 1

        # ─── CALCULATE RATES ───
        if total_user_moves > 0:
            profile_data["move_quality"]["blunder_rate"] = round(
                profile_data["move_quality"]["blunders"] / total_user_moves * 100, 1
            )
            profile_data["move_quality"]["mistake_rate"] = round(
                profile_data["move_quality"]["mistakes"] / total_user_moves * 100, 1
            )
            profile_data["move_quality"]["accuracy_rate"] = round(
                (profile_data["move_quality"]["goods"] + profile_data["move_quality"]["inaccuracies"])
                / total_user_moves * 100, 1
            )

        if profile_data["tactical_patterns"]["forks_missed"] > 0:
            profile_data["tactical_patterns"]["tactical_recognition_rate"] = round(
                (1.0 - profile_data["tactical_patterns"]["forks_missed"] / max(total_user_moves, 1)) * 100, 1
            )

        if profile_data["endgame_conversion"]["winning_positions"] > 0:
            profile_data["endgame_conversion"]["conversion_rate"] = round(
                profile_data["endgame_conversion"]["won_from_winning"] /
                profile_data["endgame_conversion"]["winning_positions"] * 100, 1
            )

        if profile_data["endgame_conversion"]["drawn_positions"] > 0:
            profile_data["endgame_conversion"]["hold_rate"] = round(
                profile_data["endgame_conversion"]["held_draws"] /
                profile_data["endgame_conversion"]["drawn_positions"] * 100, 1
            )

        if profile_data["time_resilience"]["total_moves_with_time"] > 0:
            profile_data["time_resilience"]["time_pressure_blunder_rate"] = round(
                profile_data["time_resilience"]["blunders_with_time"] /
                profile_data["time_resilience"]["total_moves_with_time"] * 100, 1
            )

        # ─── MERGE INTO player_profiles ───
        await db.player_profiles.update_one(
            {"user_id": user_id},
            {"$set": profile_data},
            upsert=True
        )

        # ─── UPDATE player_identities WITH TACTICAL STYLE ───
        tactical_style = _derive_tactical_style(profile_data)
        await db.player_identities.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "pwc_tactical_profile": tactical_style,
                    "last_pwc_analysis": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True
        )

        logger.info(f"[PWC-Profile] Updated profile for {user_id}: {profile_data['move_quality']['blunder_rate']}% blunder rate")
        return profile_data

    except Exception as e:
        logger.error(f"[PWC-Profile] Error aggregating games for {user_id}: {e}", exc_info=True)
        return None


def _detect_opening(fen_history: List[str], move_history: List[str], user_color: str) -> Optional[str]:
    """Detect opening from first ~10 plies."""
    # Simplified: just count half-moves and use basic opening names
    if len(move_history) < 4:
        return None

    # Get first 4 moves (8 plies)
    opening_moves = move_history[:8]

    # Very basic opening detection (could be enhanced with opening_book)
    if "e4" in opening_moves[:2]:
        return "e4 Opening"
    elif "d4" in opening_moves[:2]:
        return "d4 Opening"
    elif "c4" in opening_moves[:2]:
        return "English Opening"

    return None


def _calculate_opening_accuracy(move_evals: List[Dict]) -> float:
    """Calculate accuracy of moves in opening phase."""
    if not move_evals:
        return 0.0

    good_moves = sum(1 for m in move_evals if m.get("cp_loss", 0) > -50)
    return round(good_moves / len(move_evals) * 100, 1)


def _is_endgame(fen: str) -> bool:
    """Check if position is endgame (queens off or low material)."""
    try:
        board = chess.Board(fen)
        # Endgame: no queens or very few pieces
        white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
        black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
        total_pieces = len(board.pieces_mask())

        return (white_queens == 0 and black_queens == 0) or total_pieces < 8
    except:
        return False


def _derive_tactical_style(profile_data: Dict) -> Dict[str, Any]:
    """Derive tactical style from profile metrics."""
    return {
        "blunder_proneness": "high" if profile_data["move_quality"]["blunder_rate"] > 15 else "medium" if profile_data["move_quality"]["blunder_rate"] > 5 else "low",
        "tactical_awareness": "strong" if profile_data["tactical_patterns"]["tactical_recognition_rate"] > 70 else "developing" if profile_data["tactical_patterns"]["tactical_recognition_rate"] > 40 else "weak",
        "endgame_skill": "strong" if profile_data["endgame_conversion"]["conversion_rate"] > 60 else "developing" if profile_data["endgame_conversion"]["conversion_rate"] > 30 else "weak",
        "time_resilience": "strong" if profile_data["time_resilience"]["time_pressure_blunder_rate"] < 5 else "moderate" if profile_data["time_resilience"]["time_pressure_blunder_rate"] < 15 else "weak",
    }
