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

    # Add eval labels + reading prompts
    for pos in all_positions:
        # Position eval label (use stored eval_cp if available, else compute material-based)
        try:
            from services.position_eval_label import get_eval_label, get_eval_label_from_fen
            stored_eval = pos.get("eval_cp")
            if stored_eval is not None:
                import chess as chess_mod
                board_t = chess_mod.Board(pos.get("fen", ""))
                uc = "white" if board_t.turn == chess_mod.WHITE else "black"
                pos["eval_label"] = get_eval_label(stored_eval, uc)
            else:
                # Lightweight: use material balance instead of Stockfish (too slow for 12 positions)
                import chess as chess_mod
                board_t = chess_mod.Board(pos.get("fen", ""))
                uc = "white" if board_t.turn == chess_mod.WHITE else "black"
                values = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}
                w = sum(values.get(p.piece_type, 0) for p in board_t.piece_map().values() if p.color == chess_mod.WHITE)
                b = sum(values.get(p.piece_type, 0) for p in board_t.piece_map().values() if p.color == chess_mod.BLACK)
                mat_cp = (w - b) * 100
                pos["eval_label"] = get_eval_label(mat_cp, uc)
        except Exception:
            pos["eval_label"] = None

    for pos in all_positions:
        try:
            from services.position_intelligence import read_board_like_a_coach
            fen = pos.get("fen", "")
            # Determine user color from FEN (whose turn it is = user solving)
            import chess
            board_temp = chess.Board(fen)
            color = "white" if board_temp.turn == chess.WHITE else "black"
            coach_read = read_board_like_a_coach(fen, user_color=color, user_rating=user_rating)
            pos["reading_prompt"] = {
                "prompt": coach_read.get("summary", "Look at the board. What stands out?"),
                "observations": [o.get("description", "") for o in coach_read.get("observations", [])],
                "question": coach_read.get("plan", "What's the best move?"),
                "focus": coach_read.get("focus", ""),
                "phase": coach_read.get("phase", ""),
                "material": coach_read.get("material", ""),
            }
        except Exception:
            pos["reading_prompt"] = None

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
        from services.game_decryption_v5_service import _get_stockfish_candidates

        sf_candidates = await _get_stockfish_candidates(board, num_moves=3, depth=14)
        
        # Analyze each candidate with explanation
        if sf_candidates:
            user_color_bool = board.turn  # whose turn it is = user
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

    # Check if this position matches a KNOWN TRAP
    known_trap = _match_known_trap(fen)

    # Build side-by-side comparison for wrong answers
    comparison = None
    if not solved and your_move_analysis and explanation:
        comparison = {
            "your_move": your_move_analysis.get("your_move", user_move),
            "your_move_does": your_move_analysis.get("what_it_does", ""),
            "best_move": best_move_san,
            "best_move_does": explanation.get("move_description", ""),
            "difference": _build_comparison_sentence(
                your_move_analysis.get("your_move", user_move),
                your_move_analysis.get("what_it_does", ""),
                best_move_san,
                explanation.get("move_description", ""),
                your_move_analysis.get("why_bad", ""),
            ),
        }

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
        "comparison": comparison,
        "known_trap": known_trap,
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
    """
    Generate a position-specific WHY explanation.
    Key improvement: explains what the best move DOES on the board, not abstract concepts.
    """
    import chess
    from services.move_intent_analyzer import analyze_move_intent

    board = chess.Board(fen)

    # 1. What does the best move actually do on THIS board?
    move_explanation = ""
    try:
        intent = analyze_move_intent(fen, best_move)
        move_explanation = intent.description
    except Exception:
        move_explanation = f"The best move is {best_move}."

    # Make the explanation concrete — what piece, what square, what it attacks/defends
    concrete_why = _build_concrete_explanation(board, best_move)
    if concrete_why:
        move_explanation = concrete_why

    # 2. What happens AFTER the best move? (the continuation)
    continuation = ""
    continuation_moves = []
    try:
        board_sim = chess.Board(fen)
        best_move_obj = board_sim.parse_san(best_move)
        board_sim.push(best_move_obj)

        from stockfish_service import StockfishEngine
        engine = StockfishEngine()
        engine.start()
        try:
            reply_info = engine.get_best_move(board_sim, depth=10)
            if reply_info and reply_info.get("move"):
                reply_san = board_sim.san(reply_info["move"])
                continuation_moves.append({"move": best_move, "by": "you"})
                continuation_moves.append({"move": reply_san, "by": "opponent"})

                board_sim.push(reply_info["move"])
                follow_info = engine.get_best_move(board_sim, depth=10)
                if follow_info and follow_info.get("move"):
                    follow_san = board_sim.san(follow_info["move"])
                    continuation_moves.append({"move": follow_san, "by": "you"})
                    continuation = f"After {best_move}, they play {reply_san}, then you play {follow_san}."
                else:
                    continuation = f"After {best_move}, they respond with {reply_san}."
        finally:
            engine.stop()
    except Exception:
        pass

    # 3. What was the "trap" — the tempting but wrong move?
    trap_explanation = ""
    try:
        board_trap = chess.Board(fen)
        legal = list(board_trap.legal_moves)
        captures = [m for m in legal if board_trap.is_capture(m)]
        checks = [m for m in legal if board_trap.gives_check(m)]
        tempting = captures + checks

        tempting_sans = [board_trap.san(m) for m in tempting]
        if best_move in tempting_sans:
            tempting_sans.remove(best_move)

        if tempting_sans:
            trap_move = tempting_sans[0]
            trap_intent = analyze_move_intent(fen, trap_move, best_move, 200)
            trap_explanation = f"{trap_move} looks tempting, but {trap_intent.feedback}"
    except Exception:
        pass

    # Pattern-specific lesson (concrete, actionable)
    lessons = {
        "tactical_miss": "Before each move, check: are there any captures, checks, or threats I'm missing?",
        "hanging_piece": "Before moving a piece, count: how many of their pieces attack this square? How many of mine defend it?",
        "calculation_depth": "Don't stop at your move. Ask: what will they do next? Then what do I do?",
        "checkmate_pattern": "When their king is exposed, look at every possible check. One of them might be checkmate.",
        "positional": "Not every good move is a tactic. Sometimes the best move improves your worst-placed piece.",
        "winning_position_collapse": "When you're ahead in material, trade pieces. Fewer pieces = easier to win.",
        "opening_principles": "In the opening: develop pieces, control the center, castle early.",
        "time_management": "When low on time, play simple moves. Don't start complicated attacks.",
        "game_abandonment": "Finish every game. You learn the most from the positions where you're losing.",
    }

    return {
        "move_description": move_explanation,
        "why_best": f"{move_explanation} {continuation}" if continuation else move_explanation,
        "continuation": continuation_moves,
        "trap": trap_explanation,
        "lesson": lessons.get(pattern_type, "Look at the whole board. Which piece can do the most from a new square?"),
        "what_to_look_for": "Checks, captures, threats — in that order.",
        "pattern_type": pattern_type,
    }


def _build_concrete_explanation(board: chess.Board, best_move_san: str) -> str:
    """
    Build a concrete, board-specific explanation of what the best move does.
    Only attributes attacks/defenses to the MOVED PIECE, not the whole army.
    """
    import chess

    try:
        move = board.parse_san(best_move_san)
    except Exception:
        return ""

    piece = board.piece_at(move.from_square)
    if not piece:
        return ""

    PIECE_NAMES = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
    }
    piece_name = PIECE_NAMES.get(piece.piece_type, "piece")
    to_sq = chess.square_name(move.to_square)
    user_color = board.turn

    parts = []

    # Is it a capture?
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:
            cap_name = PIECE_NAMES.get(captured.piece_type, "piece")
            parts.append(f"{best_move_san} takes their {cap_name} on {to_sq}")
        else:
            # En passant
            parts.append(f"{best_move_san} captures on {to_sq}")
    else:
        parts.append(f"{best_move_san} moves your {piece_name} to {to_sq}")

    # Play the move
    sim = board.copy()
    sim.push(move)

    # Does it give check?
    if sim.is_check():
        parts.append("and gives check")

    # What does the MOVED PIECE attack from its new square?
    # Use sim.attacks(square) to get squares attacked BY the piece on to_square
    moved_piece_attacks = sim.attacks(move.to_square)
    attacks = []
    for sq in moved_piece_attacks:
        target = sim.piece_at(sq)
        if target and target.color != user_color and target.piece_type != chess.KING:
            target_name = PIECE_NAMES.get(target.piece_type, "piece")
            # Only mention non-pawn targets, or pawns if we're a pawn (pawn takes pawn is relevant)
            if target.piece_type != chess.PAWN or piece.piece_type == chess.PAWN:
                attacks.append(f"their {target_name} on {chess.square_name(sq)}")

    if attacks and len(attacks) <= 3:
        if len(attacks) == 1:
            parts.append(f"attacking {attacks[0]}")
        else:
            parts.append(f"attacking {', '.join(attacks[:-1])} and {attacks[-1]}")

    # Does the moved piece now DEFEND something that was under attack?
    # Check squares the moved piece covers that contain our pieces
    for sq in moved_piece_attacks:
        our_piece = sim.piece_at(sq)
        if our_piece and our_piece.color == user_color and our_piece.piece_type != chess.KING:
            # Was this piece under attack before?
            enemy_attackers_before = list(board.attackers(not user_color, sq))
            if enemy_attackers_before:
                # And was it undefended or underdefended before?
                our_defenders_before = list(board.attackers(user_color, sq))
                if len(our_defenders_before) <= len(enemy_attackers_before):
                    def_name = PIECE_NAMES.get(our_piece.piece_type, "piece")
                    parts.append(f"and defends your {def_name} on {chess.square_name(sq)}")
                    break

    # Also check for discovered attacks (piece moved away, revealing an attack)
    # Only for non-pawn pieces moving off a file/diagonal
    if piece.piece_type != chess.PAWN and len(attacks) == 0:
        # Check if moving this piece reveals an attack from a rook/bishop/queen behind it
        for sq in chess.SQUARES:
            target = sim.piece_at(sq)
            if target and target.color != user_color and target.piece_type != chess.KING and target.piece_type != chess.PAWN:
                # Is this target now attacked but wasn't before?
                now_attacked = sim.is_attacked_by(user_color, sq)
                was_attacked = board.is_attacked_by(user_color, sq)
                if now_attacked and not was_attacked:
                    target_name = PIECE_NAMES.get(target.piece_type, "piece")
                    parts.append(f"and reveals an attack on their {target_name} on {chess.square_name(sq)}")
                    break

    if len(parts) <= 1:
        return ""  # Not enough info for a concrete explanation

    return " ".join(parts[:3]) + "."


def generate_position_reading_prompt(fen: str, pattern_type: str = "") -> Dict:
    """
    Generate a 'what to notice' prompt for a training position.
    This trains the player's eyes BEFORE they try to find the move.

    Returns:
        {
            "prompt": "Look at this position. Notice...",
            "observations": ["Black's knight on a8 has no squares", "White's rook is on an open file"],
            "question": "Which piece is in the most danger?"
        }
    """
    import chess

    board = chess.Board(fen)
    user_color = board.turn
    opp_color = not user_color

    observations = []
    key_feature = None

    piece_names = {
        chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
    }

    # 1. Find hanging pieces (attacked with no/fewer defenders)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.piece_type == chess.KING:
            continue
        sq_name = chess.square_name(sq)
        p_name = piece_names.get(piece.piece_type, "piece")
        attackers = list(board.attackers(not piece.color, sq))
        defenders = list(board.attackers(piece.color, sq))

        if piece.color == opp_color and attackers and not defenders:
            observations.append(f"Their {p_name} on {sq_name} is undefended.")
            key_feature = "undefended_piece"
        elif piece.color == user_color and attackers and not defenders:
            observations.append(f"Your {p_name} on {sq_name} is under attack with no defenders.")
            key_feature = "your_piece_attacked"

    # 2. Pieces with limited mobility
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if piece.color == opp_color:
            # Count legal moves for this piece (approximate by checking attacked squares)
            sq_name = chess.square_name(sq)
            p_name = piece_names.get(piece.piece_type, "piece")
            # Quick mobility check
            escape_count = 0
            for target_sq in chess.SQUARES:
                if board.is_attacked_by(opp_color, target_sq):
                    # This is a rough check - we just want a signal
                    pass
            # Use piece attack map instead
            attacks = board.attacks(sq)
            mobility = len([s for s in attacks if not board.piece_at(s) or board.piece_at(s).color == user_color])
            if mobility <= 2 and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                observations.append(f"Their {p_name} on {sq_name} has very few squares to go to.")
                if not key_feature:
                    key_feature = "trapped_piece"

    # 3. Check for pins, open files, exposed king
    # Open file for rooks
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.ROOK:
            file = chess.square_file(sq)
            has_own_pawn = False
            for rank in range(8):
                p = board.piece_at(chess.square(file, rank))
                if p and p.piece_type == chess.PAWN and p.color == user_color:
                    has_own_pawn = True
                    break
            if not has_own_pawn:
                sq_name = chess.square_name(sq)
                observations.append(f"Your rook on {sq_name} is on an open file — it can attack down the board.")
                if not key_feature:
                    key_feature = "open_file"

    # 4. King safety
    opp_king_sq = board.king(opp_color)
    if opp_king_sq:
        king_sq_name = chess.square_name(opp_king_sq)
        # Count attackers near enemy king
        king_neighbors = chess.SquareSet(chess.BB_KING_ATTACKS[opp_king_sq])
        our_attackers_near_king = 0
        for neighbor in king_neighbors:
            if board.is_attacked_by(user_color, neighbor):
                our_attackers_near_king += 1
        if our_attackers_near_king >= 3:
            observations.append(f"Their king on {king_sq_name} is exposed — you have pieces pointing at it.")
            key_feature = "king_attack"

    # 5. Material count
    our_material = sum(piece_names.get(board.piece_at(sq).piece_type, "") != "king" and board.piece_at(sq).color == user_color for sq in chess.SQUARES if board.piece_at(sq))
    their_material = sum(piece_names.get(board.piece_at(sq).piece_type, "") != "king" and board.piece_at(sq).color == opp_color for sq in chess.SQUARES if board.piece_at(sq))

    # Cap observations at 3
    observations = observations[:3]

    # Build the question based on what we found
    questions = {
        "undefended_piece": "Which of their pieces can you take?",
        "your_piece_attacked": "How can you save your piece — or do something even better?",
        "trapped_piece": "Can you take advantage of their stuck piece?",
        "open_file": "How can you use your active pieces?",
        "king_attack": "Their king is weak. What's the strongest move?",
    }

    # Pattern-specific questions as fallback
    pattern_questions = {
        "hanging_piece": "Look for pieces that are attacked but not defended.",
        "tactical_miss": "Look for checks, captures, and threats.",
        "calculation_depth": "Think two moves ahead. What happens after your move?",
        "checkmate_pattern": "Their king is in danger. Can you find checkmate?",
        "piece_safety": "Which pieces are safe? Which ones are in trouble?",
    }

    question = questions.get(key_feature, "")
    if not question:
        question = pattern_questions.get(pattern_type, "Take 5 seconds to scan the board. What stands out?")

    prompt = "Before you move, look at the board."
    if observations:
        prompt = f"Before you move, notice: {observations[0].rstrip('.')}"

    return {
        "prompt": prompt,
        "observations": observations,
        "question": question,
    }


def _build_comparison_sentence(
    your_move: str, your_does: str, best_move: str, best_does: str, why_bad: str
) -> str:
    """
    Build a clear comparison: 'Your move does X. The best move does Y. That's why it's better.'
    """
    parts = []
    if your_does:
        parts.append(f"Your move {your_move} {your_does.rstrip('.')}.")
    if best_does:
        parts.append(f"The best move {best_move} {best_does.rstrip('.')}.")
    if why_bad and len(parts) < 3:
        parts.append(f"{why_bad.rstrip('.')}.")

    if not parts:
        return f"{best_move} was better than {your_move} here."

    return " ".join(parts)


def _match_known_trap(fen: str) -> Optional[Dict]:
    """Check if a FEN matches any known opening trap."""
    import chess
    from services.verified_opening_traps import VERIFIED_TRAP_REGISTRY

    # For each trap, replay the setup_moves and check if FEN matches
    for trap_id, trap in VERIFIED_TRAP_REGISTRY.items():
        try:
            board = chess.Board()
            for move_san in trap.setup_moves:
                board.push_san(move_san)

            # Compare FEN (ignore move counters — just piece positions + turn)
            trap_fen_parts = board.fen().split(" ")[:2]  # pieces + turn
            pos_fen_parts = fen.split(" ")[:2]

            if trap_fen_parts == pos_fen_parts:
                return {
                    "trap_id": trap.trap_id,
                    "name": trap.name,
                    "opening": trap.opening_name,
                    "variation": trap.variation_name,
                    "explanation": trap.explanation,
                    "refutation": trap.refutation,
                    "trap_move": trap.trap_move,
                    "trap_for": trap.trap_for,
                    "victim_color": trap.victim_color,
                    "difficulty": trap.difficulty,
                    "full_line": trap.full_line,
                }

            # Also check one move BEFORE (the position right before the trap move)
            if len(trap.setup_moves) > 1:
                board2 = chess.Board()
                for move_san in trap.setup_moves[:-1]:
                    board2.push_san(move_san)
                pre_trap_fen = board2.fen().split(" ")[:2]
                if pre_trap_fen == pos_fen_parts:
                    return {
                        "trap_id": trap.trap_id,
                        "name": trap.name,
                        "opening": trap.opening_name,
                        "variation": trap.variation_name,
                        "explanation": f"This position can lead to the {trap.name}. {trap.explanation}",
                        "refutation": trap.refutation,
                        "trap_move": trap.trap_move,
                        "trap_for": trap.trap_for,
                        "victim_color": trap.victim_color,
                        "difficulty": trap.difficulty,
                        "full_line": trap.full_line,
                    }
        except Exception:
            continue

    return None


async def get_community_position_count(db: AsyncIOMotorDatabase) -> int:
    """Get total number of community training positions."""
    return await db.community_training_positions.count_documents({})
