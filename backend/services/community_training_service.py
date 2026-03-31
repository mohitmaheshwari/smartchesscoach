"""
Community Training Service
===========================

The core insight: Every user's mistake is another user's training material.

This service:
1. Extracts training-worthy positions from V5 decrypted games
2. Stores them in `community_training_positions` with source player info
3. Serves a mix of user's own positions + community positions from similar-rated players
4. Tracks solve attempts and stats per position

Data flow:
- Game gets V5 decrypted → positions auto-extracted → stored in DB
- Training page → fetch mix of own + community positions → user solves → stats updated
"""

import chess
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Minimum cp_loss to qualify as a training position
MIN_CP_LOSS = 150

# Rating range for "similar" players (e.g., +/- 200)
RATING_RANGE = 200


def classify_pattern_type(issue_type: str, critical_detail: str = "", cognitive_gap: str = "", coaching_focus: str = "") -> str:
    """Map issue types to human-readable pattern types."""
    # Direct mapping from known issue types
    mapping = {
        "allows_mate_in_1": "checkmate_pattern",
        "allows_mate_in_2": "checkmate_pattern",
        "misses_mate_in_1": "checkmate_pattern",
        "misses_mate_in_2": "checkmate_pattern",
        "hangs_queen": "hanging_piece",
        "hangs_rook": "hanging_piece",
        "hangs_piece": "hanging_piece",
        "walks_into_fork": "fork",
        "walks_into_pin": "pin",
        "misses_fork": "fork",
        "misses_pin": "pin",
        "misses_skewer": "skewer",
        "back_rank_weakness": "back_rank",
        "positional_error": "positional",
    }
    result = mapping.get(issue_type, "")
    
    # If no direct mapping, infer from cognitive_gap (the thinking-level pattern)
    if not result and cognitive_gap:
        gap_lower = cognitive_gap.lower().replace(" ", "_")
        gap_map = {
            "calculation_depth": "calculation_depth",
            "short_calculation": "short_calculation",
            "tactical_oversight": "tactical_miss",
            "tactical_miss": "tactical_miss",
            "ignore_threat": "missed_threat",
            "missed_threat": "missed_threat",
            "hanging_piece": "hanging_piece",
            "impulse_move": "impulse_move",
            "king_safety": "king_safety",
            "positional": "positional",
        }
        for key, val in gap_map.items():
            if key in gap_lower:
                result = val
                break

    # Fallback: infer from coaching_focus text
    if not result and coaching_focus:
        focus_lower = coaching_focus.lower()
        if "calculat" in focus_lower and "depth" in focus_lower:
            result = "calculation_depth"
        elif "calculat" in focus_lower and "short" in focus_lower:
            result = "short_calculation"
        elif "calculat" in focus_lower:
            result = "calculation_depth"
        elif "threat" in focus_lower:
            result = "missed_threat"
        elif "tactic" in focus_lower:
            result = "tactical_miss"
        elif "hang" in focus_lower or "undefend" in focus_lower:
            result = "hanging_piece"
        elif "fork" in focus_lower:
            result = "fork"
        elif "pin" in focus_lower:
            result = "pin"
        elif "back rank" in focus_lower:
            result = "back_rank"

    # Last resort: infer from critical_detail
    if not result and critical_detail:
        detail_lower = critical_detail.lower()
        if "fork" in detail_lower:
            result = "fork"
        elif "pin" in detail_lower:
            result = "pin"
        elif "back rank" in detail_lower:
            result = "back_rank"
        elif "skewer" in detail_lower:
            result = "skewer"
        elif "hanging" in detail_lower or "undefended" in detail_lower:
            result = "hanging_piece"
        elif "mate" in detail_lower:
            result = "checkmate_pattern"

    return result or "tactical"


def classify_difficulty(cp_loss: int) -> str:
    """Higher cp_loss = easier to spot."""
    if cp_loss >= 500:
        return "easy"
    elif cp_loss >= 200:
        return "medium"
    return "hard"


def format_pattern_name(key: str) -> str:
    """Format pattern key for display."""
    return key.replace("_", " ").title()


async def extract_training_positions(
    db: AsyncIOMotorDatabase,
    game_id: str,
    user_id: str
) -> List[Dict]:
    """
    Extract training-worthy positions from a V5 decrypted game.
    Stores them in community_training_positions collection.
    
    Returns list of extracted positions.
    """
    # Get the game analysis
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0}
    )
    if not analysis:
        logger.info(f"No analysis found for game {game_id}")
        return []
    
    # Get game info
    game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    if not game:
        logger.info(f"Game not found: {game_id}")
        return []
    
    # Get user info for source attribution
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1})
    user_name = (user.get("name", "Anonymous") if user else "Anonymous").split()[0]  # First name only
    
    # Get user rating
    profile = await db.player_profiles.find_one(
        {"user_id": user_id}, 
        {"_id": 0, "estimated_rating": 1, "current_rating": 1}
    )
    user_rating = 1200
    if profile:
        user_rating = profile.get("current_rating") or profile.get("estimated_rating") or 1200
    
    user_color = game.get("user_color", "white")
    opening_name = game.get("opening")
    
    # Parse V5 data or stockfish analysis
    sf_analysis = analysis.get("stockfish_analysis", {})
    moves = sf_analysis.get("move_evaluations", [])
    
    extracted = []
    
    for move_data in moves:
        cp_loss = move_data.get("cp_loss", 0)
        
        # Only extract positions with significant mistakes
        if cp_loss < MIN_CP_LOSS:
            continue
        
        fen = move_data.get("fen_before")
        user_move = move_data.get("move")
        best_move = move_data.get("best_move")
        move_number = move_data.get("move_number")
        
        if not all([fen, user_move, best_move]):
            continue
        
        # Validate position and moves
        best_move_uci = None
        user_move_uci = None
        try:
            board = chess.Board(fen)
            best_move_obj = board.parse_san(best_move)
            best_move_uci = best_move_obj.uci()
            user_move_obj = board.parse_san(user_move)
            user_move_uci = user_move_obj.uci()
        except Exception:
            continue
        
        # Determine pattern type from cognitive_gap, coaching_focus, or classification
        issue_type = move_data.get("classification", "")
        critical_detail = move_data.get("explanation", "")
        cognitive_gap = move_data.get("cognitive_gap", "")
        coaching_focus = move_data.get("coaching_focus", "")
        pattern_type = classify_pattern_type(issue_type, critical_detail, cognitive_gap, coaching_focus)
        
        position_id = f"{game_id}_m{move_number}"
        
        # Check if this position already exists
        existing = await db.community_training_positions.find_one(
            {"position_id": position_id}
        )
        if existing:
            continue
        
        position = {
            "position_id": position_id,
            "fen": fen,
            "best_move_san": best_move,
            "best_move_uci": best_move_uci,
            "user_move_san": user_move,
            "user_move_uci": user_move_uci,
            "cp_loss": cp_loss,
            "pattern_type": pattern_type,
            "difficulty": classify_difficulty(cp_loss),
            "move_number": move_number,
            "opening_name": opening_name,
            
            # Source attribution
            "source_game_id": game_id,
            "source_user_id": user_id,
            "source_user_name": user_name,
            "source_user_rating": user_rating,
            "user_color": user_color,
            
            # Stats
            "attempts": 0,
            "solves": 0,
            "solve_rate": 0.0,
            
            # Metadata
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        extracted.append(position)
    
    # Bulk insert
    if extracted:
        await db.community_training_positions.insert_many(extracted)
        logger.info(f"Extracted {len(extracted)} training positions from game {game_id}")
    
    return extracted


async def get_training_feed(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 10,
    pattern_filter: str = None
) -> Dict:
    """
    Get a mixed training feed: user's own positions + community positions.
    
    Mix ratio: ~40% own, ~60% community (from similar-rated players).
    Excludes positions the user has already solved.
    """
    # Get user rating for matching
    profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "estimated_rating": 1, "current_rating": 1}
    )
    user_rating = 1200
    if profile:
        user_rating = profile.get("current_rating") or profile.get("estimated_rating") or 1200
    
    # Get positions user already solved
    solved_ids = set()
    solved_attempts = await db.training_solve_attempts.find(
        {"user_id": user_id, "solved": True},
        {"position_id": 1, "_id": 0}
    ).to_list(500)
    solved_ids = {a["position_id"] for a in solved_attempts}
    
    own_limit = max(2, limit * 2 // 5)  # ~40%
    community_limit = max(0, limit - own_limit)
    
    # 1. Fetch user's own positions (most recent first)
    own_query = {"source_user_id": user_id}
    if pattern_filter:
        own_query["pattern_type"] = pattern_filter
    if solved_ids:
        own_query["position_id"] = {"$nin": list(solved_ids)}
    
    own_positions = await db.community_training_positions.find(
        own_query,
        {"_id": 0}
    ).sort("created_at", -1).limit(own_limit).to_list(own_limit)
    
    # Tag them
    for pos in own_positions:
        pos["source_type"] = "your_game"
    
    # 2. Fetch community positions from similar-rated players
    rating_low = user_rating - RATING_RANGE
    rating_high = user_rating + RATING_RANGE
    
    community_query = {
        "source_user_id": {"$ne": user_id},
        "source_user_rating": {"$gte": rating_low, "$lte": rating_high},
    }
    if pattern_filter:
        community_query["pattern_type"] = pattern_filter
    if solved_ids:
        community_query["position_id"] = {"$nin": list(solved_ids)}
    
    community_positions = await db.community_training_positions.find(
        community_query,
        {"_id": 0}
    ).sort("created_at", -1).limit(community_limit).to_list(community_limit)
    
    # If not enough community positions in rating range, widen the search
    if len(community_positions) < community_limit:
        remaining = community_limit - len(community_positions)
        existing_ids = [p["position_id"] for p in community_positions]
        
        wider_query = {
            "source_user_id": {"$ne": user_id},
            "position_id": {"$nin": list(solved_ids) + existing_ids},
        }
        if pattern_filter:
            wider_query["pattern_type"] = pattern_filter
        
        wider_positions = await db.community_training_positions.find(
            wider_query,
            {"_id": 0}
        ).sort("created_at", -1).limit(remaining).to_list(remaining)
        community_positions.extend(wider_positions)
    
    # Tag them
    for pos in community_positions:
        pos["source_type"] = "community"
    
    # Combine: own first, then community
    all_positions = own_positions + community_positions
    
    # Get pattern stats for user
    pattern_stats = await get_user_pattern_stats(db, user_id)
    
    return {
        "positions": all_positions,
        "total": len(all_positions),
        "own_count": len(own_positions),
        "community_count": len(community_positions),
        "user_rating": user_rating,
        "pattern_stats": pattern_stats,
    }


async def record_solve_attempt(
    db: AsyncIOMotorDatabase,
    user_id: str,
    position_id: str,
    user_move: str,
    time_taken_seconds: int = 0
) -> Dict:
    """Record a solve attempt and update position stats."""
    
    # Get the position
    position = await db.community_training_positions.find_one(
        {"position_id": position_id},
        {"_id": 0}
    )
    if not position:
        return {"error": "Position not found"}
    
    # Check if move is correct
    best_move_san = position["best_move_san"]
    best_move_uci = position["best_move_uci"]
    fen = position["fen"]
    
    solved = False
    user_move_uci = None
    
    try:
        board = chess.Board(fen)
        # Try parsing as SAN first
        try:
            move_obj = board.parse_san(user_move)
            user_move_uci = move_obj.uci()
        except chess.InvalidMoveError:
            # Try as UCI
            try:
                move_obj = chess.Move.from_uci(user_move)
                if move_obj in board.legal_moves:
                    user_move_uci = user_move
            except Exception:
                pass
        
        # Check if correct (compare both SAN and UCI)
        if user_move_uci:
            solved = (user_move_uci == best_move_uci) or (user_move == best_move_san)
    except Exception as e:
        logger.warning(f"Error checking move: {e}")
    
    # Record the attempt
    attempt = {
        "user_id": user_id,
        "position_id": position_id,
        "user_move": user_move,
        "user_move_uci": user_move_uci,
        "solved": solved,
        "time_taken_seconds": time_taken_seconds,
        "pattern_type": position.get("pattern_type", "tactical"),
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.training_solve_attempts.insert_one(attempt)
    
    # Update position stats
    new_attempts = position.get("attempts", 0) + 1
    new_solves = position.get("solves", 0) + (1 if solved else 0)
    new_solve_rate = round(new_solves / new_attempts * 100, 1) if new_attempts > 0 else 0
    
    await db.community_training_positions.update_one(
        {"position_id": position_id},
        {"$set": {
            "attempts": new_attempts,
            "solves": new_solves,
            "solve_rate": new_solve_rate,
        }}
    )
    
    # Get solve rate for similar-rated players
    user_profile = await db.player_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0, "estimated_rating": 1, "current_rating": 1}
    )
    user_rating = 1200
    if user_profile:
        user_rating = user_profile.get("current_rating") or user_profile.get("estimated_rating") or 1200
    
    # Count how many similar-rated players missed this
    rating_low = user_rating - RATING_RANGE
    rating_high = user_rating + RATING_RANGE
    
    # Get all attempts from similar-rated players for this position
    pipeline = [
        {"$match": {"position_id": position_id}},
        {"$lookup": {
            "from": "player_profiles",
            "localField": "user_id",
            "foreignField": "user_id",
            "as": "profile"
        }},
        {"$unwind": {"path": "$profile", "preserveNullAndEmptyArrays": True}},
        {"$match": {
            "$or": [
                {"profile.current_rating": {"$gte": rating_low, "$lte": rating_high}},
                {"profile.estimated_rating": {"$gte": rating_low, "$lte": rating_high}},
                {"profile": {"$exists": False}}
            ]
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "missed": {"$sum": {"$cond": [{"$eq": ["$solved", False]}, 1, 0]}}
        }}
    ]
    
    miss_rate_at_level = None
    try:
        agg_result = await db.training_solve_attempts.aggregate(pipeline).to_list(1)
        if agg_result and agg_result[0].get("total", 0) > 1:
            total = agg_result[0]["total"]
            missed = agg_result[0]["missed"]
            miss_rate_at_level = round(missed / total * 100)
    except Exception as e:
        logger.warning(f"Error computing miss rate: {e}")
    
    # Generate candidate moves analysis for rich feedback
    candidates = []
    try:
        board = chess.Board(fen)
        from services.game_decryption_v5_service import _get_stockfish_candidates, _analyze_candidate_moves

        sf_candidates = await _get_stockfish_candidates(board, num_moves=3, depth=14)
        
        # Analyze each candidate with explanation
        if sf_candidates:
            user_color_bool = board.turn  # whose turn it is = user
            played_move_obj = None
            if user_move_uci:
                try:
                    chess.Move.from_uci(user_move_uci)
                except Exception:
                    pass
            
            for sf in sf_candidates:
                move_san = sf.get("move", "")
                eval_cp = sf.get("eval_cp", 0)
                pv = sf.get("pv", [])
                is_best = sf.get("is_best", False)
                
                # Explain the idea behind this move
                idea = ""
                move_type = "engine_choice"
                try:
                    from services.game_decryption_v5_service import _explain_move_idea
                    idea_data = _explain_move_idea(board, move_san, user_color_bool)
                    if idea_data:
                        idea = idea_data.get("explanation", "")
                        move_type = idea_data.get("type", "engine_choice")
                except Exception:
                    pass
                
                if not idea:
                    idea = f"{move_san} is a strong move in this position"
                
                candidates.append({
                    "move": move_san,
                    "eval_cp": eval_cp,
                    "idea": idea,
                    "type": move_type,
                    "is_best": is_best,
                    "pv": pv[:3],
                })
    except Exception as e:
        logger.warning(f"Could not generate candidates: {e}")

    # Generate WHY explanation tied to the pattern/focus
    pattern_type = position.get("pattern_type", "tactical")
    explanation = _get_pattern_explanation(pattern_type, best_move_san, fen, solved)

    # Analyze the user's wrong move — what's bad about it + opponent's punishment
    your_move_analysis = None
    if not solved and user_move_uci:
        try:
            from services.move_intent_analyzer import analyze_move_intent
            board_copy = chess.Board(fen)
            user_san = board_copy.san(chess.Move.from_uci(user_move_uci))

            # What your move does
            intent = analyze_move_intent(fen, user_san, best_move_san, 200)

            # What opponent does after your move
            board_copy.push(chess.Move.from_uci(user_move_uci))
            opponent_response = None
            try:
                from stockfish_service import StockfishEngine
                engine = StockfishEngine()
                engine.start()
                best_reply = engine.get_best_move(board_copy, depth=12)
                if best_reply and best_reply.get("move"):
                    reply_san = board_copy.san(best_reply["move"])
                    reply_intent = analyze_move_intent(board_copy.fen(), reply_san)
                    opponent_response = {
                        "move": reply_san,
                        "description": reply_intent.description,
                        "threat": reply_intent.feedback,
                    }
                engine.stop()
            except Exception:
                pass

            your_move_analysis = {
                "your_move": user_san,
                "what_it_does": intent.description,
                "why_bad": intent.feedback,
                "opponent_punishes": opponent_response,
            }
        except Exception as e:
            logger.warning(f"User move analysis failed: {e}")

    return {
        "solved": solved,
        "correct_move": best_move_san,
        "correct_move_uci": best_move_uci,
        "user_move_san": user_move,
        "original_player_move": position.get("user_move_san", ""),
        "position_solve_rate": new_solve_rate,
        "miss_rate_at_your_level": miss_rate_at_level,
        "pattern_type": pattern_type,
        "candidates": candidates,
        "explanation": explanation,
        "your_move_analysis": your_move_analysis,
    }


async def get_user_pattern_stats(
    db: AsyncIOMotorDatabase,
    user_id: str
) -> List[Dict]:
    """Get user's pattern-level solve stats."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$pattern_type",
            "total_attempts": {"$sum": 1},
            "total_solved": {"$sum": {"$cond": [{"$eq": ["$solved", True]}, 1, 0]}},
        }},
        {"$project": {
            "pattern": "$_id",
            "total_attempts": 1,
            "total_solved": 1,
            "solve_rate": {
                "$cond": [
                    {"$gt": ["$total_attempts", 0]},
                    {"$round": [{"$multiply": [{"$divide": ["$total_solved", "$total_attempts"]}, 100]}, 0]},
                    0
                ]
            },
            "_id": 0
        }},
        {"$sort": {"total_attempts": -1}}
    ]
    
    stats = await db.training_solve_attempts.aggregate(pipeline).to_list(20)
    return stats



def _get_pattern_explanation(pattern_type: str, best_move: str, fen: str, solved: bool) -> Dict:
    """Generate a WHY explanation for the best move, tied to the pattern focus."""
    
    # Use the move intent analyzer for position-specific explanation
    try:
        from services.move_intent_analyzer import analyze_move_intent
        intent = analyze_move_intent(fen, best_move)
        move_explanation = intent.description
    except Exception:
        move_explanation = f"The best move was {best_move}."

    # Pattern-specific teaching
    pattern_lessons = {
        "tactical_miss": {
            "why": f"{best_move} wins material or creates an unstoppable threat. In this position, look for checks, captures, and threats — in that order.",
            "lesson": "Before every move in a tense position: check all captures and all checks. The tactic is hiding there.",
            "what_to_look_for": "Forks, pins, skewers, discovered attacks, back rank threats.",
        },
        "hanging_piece": {
            "why": f"{best_move} takes advantage of an undefended piece. Your opponent left something unprotected.",
            "lesson": "Scan the board for undefended pieces — yours AND theirs. Every move.",
            "what_to_look_for": "Pieces with no defenders, pieces that just moved away from defending something.",
        },
        "calculation_depth": {
            "why": f"{best_move} requires seeing 2-3 moves ahead. The first move sets up the real threat.",
            "lesson": "Don't just look at the first move — ask 'what happens AFTER they respond?'",
            "what_to_look_for": "Quiet moves that set up unstoppable threats on the next move.",
        },
        "checkmate_pattern": {
            "why": f"{best_move} leads to checkmate or forces a winning attack on the king.",
            "lesson": "When the opponent's king is exposed, check every possible check. Checkmate patterns repeat.",
            "what_to_look_for": "Back rank mates, smothered mates, queen + knight combos, bishop + queen batteries.",
        },
        "positional": {
            "why": f"{best_move} improves your position long-term — better piece placement, control of key squares.",
            "lesson": "Not every good move is a tactic. Sometimes the best move makes your position stronger gradually.",
            "what_to_look_for": "Open files for rooks, outposts for knights, weak squares in opponent's camp.",
        },
        "winning_position_collapse": {
            "why": f"{best_move} keeps your advantage safe. When you're winning, the best move is often the simplest one.",
            "lesson": "When ahead: simplify. Trade pieces, avoid complications. Don't give them chances.",
            "what_to_look_for": "Trades that keep your advantage, prophylactic moves that prevent counterplay.",
        },
        "opening_principles": {
            "why": f"{best_move} follows opening principles — develop pieces, control the center, get the king safe.",
            "lesson": "In the opening: develop, control center, castle. Don't move the same piece twice.",
            "what_to_look_for": "Undeveloped pieces, center control, king safety.",
        },
    }

    info = pattern_lessons.get(pattern_type, {
        "why": f"{best_move} was the strongest move in this position.",
        "lesson": "Look for the most active move — the one that creates the most problems for your opponent.",
        "what_to_look_for": "Checks, captures, threats.",
    })

    return {
        "move_description": move_explanation,
        "why_best": info["why"],
        "lesson": info["lesson"],
        "what_to_look_for": info["what_to_look_for"],
        "pattern_type": pattern_type,
    }


async def get_community_position_count(db: AsyncIOMotorDatabase) -> int:
    """Get total number of community training positions."""
    return await db.community_training_positions.count_documents({})
