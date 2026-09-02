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

from services.puzzle_extraction_service import (
    verified_issue_type,
    verified_puzzle_admission_enforced,
    verdict_serves_pattern,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_imported_game_verdict
from services.verified_puzzle_admission import stored_verdict_is_structurally_current
from services.verified_puzzle_runtime import grade_resolved_puzzle

logger = logging.getLogger(__name__)

# Minimum cp_loss to qualify as a training position
MIN_CP_LOSS = 150

# Rating range for "similar" players (e.g., +/- 200)
RATING_RANGE = 200


def _servable_positions(positions: List[Dict], requested_pattern: Optional[str], limit: int) -> List[Dict]:
    """Filter after reads because this production collection has unreliable
    compound/index behavior. Quarantine is never served; current-verdict
    enforcement remains default-off until the versioned backfill is complete.
    """
    result = []
    for position in positions:
        if position.get("approved") is False:
            continue
        pattern = requested_pattern or position.get("pattern_type") or "calculation_depth"
        if not verdict_serves_pattern(position, pattern):
            continue
        result.append(position)
        if len(result) >= limit:
            break
    return result


def _verified_feed_pattern(pattern: Optional[str]) -> Optional[str]:
    """Map an unverified recommendation to the closest honest feed family."""
    if not pattern or not verified_puzzle_admission_enforced():
        return pattern
    if pattern in {"piece_safety", "hanging_piece"}:
        return "piece_safety"
    if pattern == "calculation_depth":
        return pattern
    return "calculation_depth"


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
        user_move = move_data.get("move") or move_data.get("move_san") or move_data.get("played_move")
        best_move = move_data.get("best_move_san") or move_data.get("best_move")
        move_number = move_data.get("move_number")
        eval_before = move_data.get("eval_before", 0) or 0
        eval_after = move_data.get("eval_after", 0) or 0

        if not all([fen, user_move, best_move]):
            continue

        if move_data.get("is_opponent_move") is True or move_data.get("is_user_move") is False:
            continue
        try:
            if (chess.Board(fen).turn == chess.WHITE) != (str(user_color).lower() == "white"):
                continue
        except ValueError:
            continue

        # ── CONTEXT FILTER: Skip positions where the game was already decided ──
        # eval_before is from WHITE's perspective (centipawns as float or int)
        eval_before_cp = int(eval_before * 100) if isinstance(eval_before, float) and abs(eval_before) < 100 else int(eval_before)
        eval_after_cp = int(eval_after * 100) if isinstance(eval_after, float) and abs(eval_after) < 100 else int(eval_after)

        # From user's perspective
        user_eval_before = eval_before_cp if user_color == "white" else -eval_before_cp
        user_eval_after = eval_after_cp if user_color == "white" else -eval_after_cp

        # Skip if position was already lost (user was -400+ before the mistake)
        if user_eval_before <= -400:
            continue  # Already losing badly — this mistake didn't matter

        # Skip if position was already completely winning and mistake didn't change outcome
        if user_eval_before >= 600 and user_eval_after >= 200:
            continue  # Was winning +6, still winning +2 — not a meaningful training position

        # ── TAG: What kind of moment was this? ──
        eval_swing = user_eval_before - user_eval_after  # Positive = user got worse

        if user_eval_before >= 100 and user_eval_after <= -100:
            moment_tag = "game_changer"  # Went from winning to losing
        elif user_eval_before >= 200 and user_eval_after <= 50:
            moment_tag = "threw_advantage"  # Had clear advantage, let it slip
        elif abs(user_eval_before) <= 100 and user_eval_after <= -200:
            moment_tag = "decisive_moment"  # Equal position, one mistake decided it
        elif user_eval_before <= -100 and eval_swing >= 200:
            moment_tag = "missed_defense"  # Was worse, needed to find the right move
        elif eval_swing >= 300:
            moment_tag = "critical_mistake"  # Big swing regardless of starting position
        else:
            moment_tag = "learning_moment"  # Standard training position

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

        # Determine pattern type
        issue_type = move_data.get("classification", "")
        critical_detail = move_data.get("explanation", "")
        cognitive_gap = move_data.get("cognitive_gap", "")
        coaching_focus = move_data.get("coaching_focus", "")
        legacy_pattern_type = classify_pattern_type(
            issue_type, critical_detail, cognitive_gap, coaching_focus
        )
        verdict = build_imported_game_verdict(
            game=game,
            move_evaluation=move_data,
            broad_category=cognitive_gap or None,
        )
        pattern_type = verified_issue_type(verdict)

        position_id = f"{game_id}_m{move_number}"

        # Check if already exists
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
            "eval_cp": eval_before_cp,  # Store for eval labels
            "eval_before_user": user_eval_before,
            "eval_after_user": user_eval_after,
            "pattern_type": pattern_type,
            "legacy_pattern_type": legacy_pattern_type,
            "moment_tag": moment_tag,
            "difficulty": classify_difficulty(cp_loss),
            "move_number": move_number,
            "opening_name": opening_name,

            # Source attribution
            "source_game_id": game_id,
            "source_user_id": user_id,
            "source_user_name": user_name,
            "source_user_rating": user_rating,
            "user_color": user_color,

            # The answer and label are admitted from stored analysis only.
            # No engine or LLM is called while extracting or solving.
            "pv_after_best": move_data.get("pv_after_best") or [],
            "pv_after_played": move_data.get("pv_after_played") or [],
            "verified_admission": verdict.to_document(),
            "approved": verdict.status != AdmissionStatus.QUARANTINE,

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

    # ── SMART PATTERN SELECTION ──
    # When no specific pattern is requested, pick the pattern the user needs most.
    # Based on: what they get wrong in games + what they fail in puzzles.
    recommended_pattern = None
    if not pattern_filter:
        recommended_pattern = await _pick_priority_pattern(db, user_id)
        recommended_pattern = _verified_feed_pattern(recommended_pattern)

    own_limit = max(2, limit * 2 // 5)  # ~40%
    community_limit = max(0, limit - own_limit)

    # 1. Fetch user's own positions (most recent first)
    own_query = {"source_user_id": user_id}
    if pattern_filter:
        own_query["pattern_type"] = pattern_filter
    elif recommended_pattern:
        # Serve mostly from the weak pattern, but allow some variety
        own_query["pattern_type"] = recommended_pattern
    if solved_ids:
        own_query["position_id"] = {"$nin": list(solved_ids)}
    
    own_fetch_limit = own_limit * (10 if verified_puzzle_admission_enforced() else 1)
    own_positions = await db.community_training_positions.find(
        own_query,
        {"_id": 0}
    ).sort("created_at", -1).limit(own_fetch_limit).to_list(own_fetch_limit)
    own_positions = _servable_positions(
        own_positions, pattern_filter or recommended_pattern, own_limit
    )
    
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
    elif recommended_pattern:
        community_query["pattern_type"] = recommended_pattern
    if solved_ids:
        community_query["position_id"] = {"$nin": list(solved_ids)}
    
    community_fetch_limit = community_limit * (10 if verified_puzzle_admission_enforced() else 1)
    community_positions = await db.community_training_positions.find(
        community_query,
        {"_id": 0}
    ).sort("created_at", -1).limit(community_fetch_limit).to_list(community_fetch_limit)
    community_positions = _servable_positions(
        community_positions, pattern_filter or recommended_pattern, community_limit
    )
    
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
        
        wider_fetch_limit = remaining * (10 if verified_puzzle_admission_enforced() else 1)
        wider_positions = await db.community_training_positions.find(
            wider_query,
            {"_id": 0}
        ).sort("created_at", -1).limit(wider_fetch_limit).to_list(wider_fetch_limit)
        wider_positions = _servable_positions(
            wider_positions, pattern_filter or recommended_pattern, remaining
        )
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
            from services.position_eval_label import get_eval_label
            import chess as chess_mod

            board_t = chess_mod.Board(pos.get("fen", ""))
            solver_is_white = board_t.turn == chess_mod.WHITE

            # Priority 1: eval_before_user (already from solver's perspective)
            user_eval = pos.get("eval_before_user")
            if user_eval is not None:
                pos["eval_label"] = get_eval_label(int(user_eval), "white")  # already user-perspective, no flip
            else:
                # Priority 2: eval_cp (from White's perspective) — flip if solver is Black
                stored_eval = pos.get("eval_cp")
                if stored_eval is not None:
                    solver_eval = int(stored_eval) if solver_is_white else -int(stored_eval)
                    pos["eval_label"] = get_eval_label(solver_eval, "white")  # already flipped, no double-flip
                else:
                    # Priority 3: material count
                    values = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}
                    w = sum(values.get(p.piece_type, 0) for p in board_t.piece_map().values() if p.color == chess_mod.WHITE)
                    b = sum(values.get(p.piece_type, 0) for p in board_t.piece_map().values() if p.color == chess_mod.BLACK)
                    solver_eval = (w - b) * 100 if solver_is_white else (b - w) * 100
                    pos["eval_label"] = get_eval_label(solver_eval, "white")  # already from solver's perspective
        except Exception:
            pos["eval_label"] = None

    # Reading prompts are now generated on-demand via LLM (async)
    # We add them here using the deep board reading
    for pos in all_positions:
        try:
            # Use DETERMINISTIC board reading — no LLM calls per position
            # LLM was being called 10 times per training page load
            from services.position_intelligence import read_board_like_a_coach
            fen = pos.get("fen", "")
            board_temp = chess.Board(fen)
            color = "white" if board_temp.turn == chess.WHITE else "black"
            coach_read = read_board_like_a_coach(fen, user_color=color, user_rating=user_rating)
            pos["reading_prompt"] = {
                "prompt": coach_read.get("summary", "Look at the board. What stands out?"),
                "observations": [o.get("description", "") for o in coach_read.get("observations", [])] if coach_read.get("observations") else [],
                "question": coach_read.get("plan", "What's the best move?"),
                "focus": coach_read.get("focus", ""),
                "phase": coach_read.get("phase", ""),
                "material": coach_read.get("material", ""),
                "source": coach_read.get("source", "deterministic"),
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
        "recommended_pattern": recommended_pattern,
    }


async def _pick_priority_pattern(db, user_id: str) -> Optional[str]:
    """
    Decide which pattern the user should train RIGHT NOW.

    Logic:
    1. Get patterns that appear in games (from pattern memory)
    2. Get puzzle solve rates per pattern
    3. Priority = frequent in games + low solve rate in puzzles
       → This is the pattern they keep making AND can't solve when shown

    If user has no puzzle data yet, fall back to most frequent game pattern.
    If user has mastered their frequent patterns (solve rate > 75%), pick next one.
    """
    # Get game patterns (what they get wrong)
    game_patterns = {}
    try:
        from services.pattern_memory_service import get_pattern_summary
        summary = await get_pattern_summary(db, user_id)
        for p in summary.get("patterns", []):
            pt = p.get("pattern_type", "")
            if pt:
                game_patterns[pt] = p.get("recent_count", 0)
    except Exception:
        pass

    if not game_patterns:
        return None

    # Get puzzle solve rates
    puzzle_rates = {}
    try:
        stats = await get_user_pattern_stats(db, user_id)
        for s in stats:
            pt = s.get("pattern", "")
            if pt and s.get("total_attempts", 0) >= 2:
                puzzle_rates[pt] = s.get("solve_rate", 50)
    except Exception:
        pass

    # Score each pattern: high game frequency + low solve rate = high priority
    scored = []
    for pattern, game_count in game_patterns.items():
        solve_rate = puzzle_rates.get(pattern, 50)  # Default 50% if no puzzle data

        # Priority formula:
        # - game_count matters (frequent pattern = urgent)
        # - low solve rate matters (can't fix it yet = needs more practice)
        # - mastered patterns (solve > 75%) get deprioritized
        if solve_rate >= 75 and puzzle_rates.get(pattern) is not None:
            priority = game_count * 0.3  # Mastered — low priority
        else:
            priority = game_count * (100 - solve_rate) / 50  # Frequent + hard = highest

        scored.append((pattern, priority))

    scored.sort(key=lambda x: -x[1])

    # Check if there are positions available for the top pattern
    for pattern, _ in scored[:3]:
        count = await db.community_training_positions.count_documents({
            "pattern_type": pattern,
            "$or": [
                {"source_user_id": user_id},
                {"source_user_id": {"$ne": user_id}},
            ]
        })
        if count > 0:
            return pattern

    return None


def _pv_token(item) -> Optional[str]:
    if isinstance(item, str):
        return item.strip() or None
    if isinstance(item, dict):
        value = item.get("move") or item.get("uci") or item.get("san")
        return str(value).strip() if value else None
    return None


def _legal_move_from_token(board: chess.Board, token: str) -> Optional[chess.Move]:
    try:
        move = chess.Move.from_uci(token)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(token)
    except ValueError:
        return None


def _first_legal_pv_move(board: chess.Board, stored_pv: List) -> Optional[str]:
    """Read the next legal move from an already-stored principal variation."""
    for item in stored_pv:
        token = _pv_token(item)
        if not token:
            continue
        move = _legal_move_from_token(board, token)
        if move is not None:
            return board.san(move)
    return None


async def record_solve_attempt(
    db: AsyncIOMotorDatabase,
    user_id: str,
    position_id: str,
    user_move: str,
    time_taken_seconds: int = 0,
    submission_id: Optional[str] = None,
) -> Dict:
    """Record a solve attempt and update position stats."""
    
    # Get the position
    position = await db.community_training_positions.find_one(
        {"position_id": position_id},
        {"_id": 0}
    )
    if not position:
        return {"error": "Position not found"}
    
    from services.verified_puzzle_runtime import resolve_verified_puzzle
    from services.verified_puzzle_attempt_service import record_verified_puzzle_attempt
    resolved = await resolve_verified_puzzle(db, position_id, user_id=user_id)
    if not resolved:
        return {"error": "This position is being checked and is not ready yet."}
    best_move_san = resolved.get("best_move_san") or position.get("best_move_san") or ""
    best_move_uci = resolved.get("best_move_uci") or position.get("best_move_uci") or ""
    fen = resolved.get("fen") or position.get("fen")
    admission = resolved.get("verified_admission") or {}
    has_current_verdict = True
    accepted_moves = set(admission.get("acceptable_moves_uci") or [])
    
    solved = False
    near_miss = False  # Player's move is good (top 2-3) but not THE best
    user_move_uci = None
    verified_grade = None

    try:
        board = chess.Board(fen)
        # Try parsing as SAN first
        try:
            move_obj = board.parse_san(user_move)
            user_move_uci = move_obj.uci()
        except (ValueError, AssertionError):
            # Try as UCI
            try:
                move_obj = chess.Move.from_uci(user_move)
                if move_obj in board.legal_moves:
                    user_move_uci = user_move
            except Exception:
                pass

        if user_move_uci:
            verified_grade = await record_verified_puzzle_attempt(
                db,
                user_id=user_id,
                puzzle_id=position_id,
                puzzle=resolved,
                played_uci=user_move_uci,
                time_taken_ms=max(0, int(time_taken_seconds or 0)) * 1000,
                attempt_context="community_training",
                submission_id=submission_id,
            )
            if verified_grade.get("quality") == "invalid":
                return {"error": verified_grade.get("feedback")}
            solved = bool(verified_grade.get("correct"))
    except Exception as e:
        logger.warning(f"Error checking move: {e}")
    
    # Record the attempt (near_miss counts as partial understanding)
    attempt = {
        "user_id": user_id,
        "position_id": position_id,
        "user_move": user_move,
        "user_move_uci": user_move_uci,
        "solved": solved,
        "near_miss": near_miss,
        "time_taken_seconds": time_taken_seconds,
        "pattern_type": position.get("pattern_type", "tactical"),
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    }
    # The canonical attempt owns retry identity. A repeated transport request
    # must not create a second legacy row or increment the position again.
    duplicate_attempt = bool(
        verified_grade and verified_grade.get("duplicate")
    )
    if not duplicate_attempt:
        await db.training_solve_attempts.insert_one(attempt)
    
    # Update position stats
    new_attempts = position.get("attempts", 0) + (0 if duplicate_attempt else 1)
    new_solves = position.get("solves", 0) + (
        0 if duplicate_attempt else (1 if solved else 0)
    )
    new_solve_rate = round(new_solves / new_attempts * 100, 1) if new_attempts > 0 else 0
    
    if not duplicate_attempt:
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
    
    # Build answer cards from the answer set and PV stored during the original
    # analysis. Never re-run Stockfish while the player is solving.
    candidates = []
    try:
        board = chess.Board(fen)
        ordered_answers = [best_move_uci] + sorted(accepted_moves - {best_move_uci})
        for answer_uci in ordered_answers:
            if not answer_uci:
                continue
            answer_obj = chess.Move.from_uci(answer_uci)
            if answer_obj not in board.legal_moves:
                continue
            answer_san = board.san(answer_obj)
            concrete = _build_concrete_explanation(board, answer_san)
            candidates.append({
                "move": answer_san,
                "move_uci": answer_uci,
                "eval_cp": None,
                "idea": concrete or (
                    f"Calculate {answer_san}, then check the opponent's strongest reply."
                ),
                "type": "verified_answer",
                "is_best": answer_uci == best_move_uci,
                "pv": (position.get("pv_after_best") or [])[:3]
                if answer_uci == best_move_uci else [],
            })
    except Exception as e:
        logger.warning(f"Could not build stored answer cards: {e}")

    # Generate WHY explanation tied to the pattern/focus
    pattern_type = position.get("pattern_type", "calculation_depth")
    explanation = _get_pattern_explanation(
        pattern_type,
        best_move_san,
        fen,
        solved or near_miss,
        position.get("pv_after_best") or [],
    )

    # Analyze the user's wrong move — what's bad about it + opponent's punishment
    your_move_analysis = None
    if not solved and not near_miss and user_move_uci:
        try:
            board_copy = chess.Board(fen)
            user_obj = chess.Move.from_uci(user_move_uci)
            user_san = board_copy.san(user_obj)
            move_description = _build_concrete_explanation(board_copy, user_san)
            board_copy.push(user_obj)
            reply_san = _first_legal_pv_move(
                board_copy, position.get("pv_after_played") or []
            )
            opponent_response = ({
                "move": reply_san,
                "description": f"The stored continuation begins with {reply_san}.",
                "threat": "Calculate this reply before committing to your move.",
            } if reply_san else None)

            your_move_analysis = {
                "your_move": user_san,
                "what_it_does": move_description or f"You played {user_san}.",
                "why_bad": (
                    ((verified_grade or {}).get("coaching_feedback") or {}).get("why")
                    or "That move does not solve the board problem this lesson is testing."
                ),
                "opponent_punishes": opponent_response,
            }
        except Exception as e:
            logger.warning(f"User move analysis failed: {e}")

    # A trap name is shown only after a trap detector and its independent
    # verifier have earned a specific admission verdict.
    concept_id = str(admission.get("concept_id") or "")
    known_trap = _match_known_trap(fen) if "trap" in concept_id else None

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

    coaching_feedback = (
        (verified_grade or {}).get("coaching_feedback")
        if has_current_verdict
        else None
    ) or {
        "why": (explanation or {}).get("why_best") or (explanation or {}).get("move_description") or "",
        "remember": (explanation or {}).get("lesson") or (
            "Before you commit, calculate the opponent's strongest legal reply."
        ),
        "behavior": (
            "Name the board clue you used, then look for the same clue in your next game."
            if solved else
            "Try the position again and say the opponent's strongest reply before moving."
        ),
        "source": "legacy_rollout",
    }

    return {
        "solved": solved,
        "near_miss": near_miss,
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
        "coaching_feedback": coaching_feedback,
    }


async def get_training_progress(
    db: AsyncIOMotorDatabase,
    user_id: str,
    pattern: str,
    required: int = 5
) -> Dict:
    """
    Get training progress for the active pattern.
    Counts CORRECT solves only. Resets if 2 wrong in a row (recent).
    """
    # Get all attempts for this pattern, sorted by time
    attempts = await db.training_solve_attempts.find(
        {"user_id": user_id, "pattern_type": pattern},
        {"_id": 0, "solved": 1, "near_miss": 1, "attempted_at": 1}
    ).sort("attempted_at", -1).to_list(100)

    if not attempts:
        return {"correct": 0, "required": required, "completed": False, "streak": 0}

    # Count correct solves, but reset if 2 consecutive wrong
    correct = 0
    streak = 0
    consecutive_wrong = 0

    # Walk from OLDEST to NEWEST
    for a in reversed(attempts):
        if a.get("solved") or a.get("near_miss"):
            correct += 1
            streak += 1
            consecutive_wrong = 0
        else:
            consecutive_wrong += 1
            streak = 0
            if consecutive_wrong >= 2:
                # Reset — user lost focus
                correct = max(0, correct - 1)
                consecutive_wrong = 0

    correct = min(correct, required)

    return {
        "correct": correct,
        "required": required,
        "completed": correct >= required,
        "streak": streak,
        "total_attempts": len(attempts),
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


def _get_pattern_explanation(
    pattern_type: str,
    best_move: str,
    fen: str,
    solved: bool,
    stored_pv: Optional[List] = None,
) -> Dict:
    """
    Generate a position-specific WHY explanation.
    Key improvement: explains what the best move DOES on the board, not abstract concepts.
    """
    import chess
    board = chess.Board(fen)

    # 1. What does the best move actually do on THIS board?
    move_explanation = _build_concrete_explanation(board, best_move)
    if not move_explanation:
        move_explanation = f"The move to learn here is {best_move}."

    # 2. What happens AFTER the best move? (the continuation)
    continuation = ""
    continuation_moves = []
    try:
        board_sim = chess.Board(fen)
        best_move_obj = board_sim.parse_san(best_move)
        board_sim.push(best_move_obj)

        continuation_moves.append({"move": best_move, "by": "you"})
        for item in stored_pv or []:
            token = _pv_token(item)
            if not token:
                continue
            next_move = _legal_move_from_token(board_sim, token)
            if next_move is None:
                continue
            next_san = board_sim.san(next_move)
            by = "opponent" if len(continuation_moves) == 1 else "you"
            continuation_moves.append({"move": next_san, "by": by})
            board_sim.push(next_move)
            if len(continuation_moves) >= 3:
                break
        if len(continuation_moves) == 3:
            continuation = (
                f"The stored line continues {continuation_moves[1]['move']}, "
                f"then {continuation_moves[2]['move']}."
            )
        elif len(continuation_moves) == 2:
            continuation = f"The stored reply is {continuation_moves[1]['move']}."
    except Exception:
        pass

    # Pattern-specific lesson with a universal habit ending.
    lessons = {
        "piece_safety": "Before every move, scan each of your pieces once: attacked, defended, or able to move.",
        "hanging_piece": "Before every move, scan each of your pieces once: attacked, defended, or able to move.",
        "tactical_miss": "Before every move, check their strongest reply before you commit.",
        "calculation_depth": "Before every move, calculate their strongest reply before you commit.",
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
        "trap": "",
        "lesson": lessons.get(pattern_type, "Before every move, calculate their strongest reply before you commit."),
        "what_to_look_for": (
            "Scan every one of your pieces before choosing the move."
            if pattern_type in {"piece_safety", "hanging_piece"}
            else "Calculate their strongest reply before choosing the move."
        ),
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

    # Check for discovered attacks / opened lines (ANY piece moving, including pawns)
    # When a pawn moves off a diagonal, it can open a line for a bishop/queen behind it
    if True:  # Always check — pawns opening diagonals is critical
        for sq in chess.SQUARES:
            target = sim.piece_at(sq)
            if target and target.color != user_color and target.piece_type != chess.KING and target.piece_type != chess.PAWN:
                # Is this target now attacked but wasn't before?
                now_attacked = sim.is_attacked_by(user_color, sq)
                was_attacked = board.is_attacked_by(user_color, sq)
                if now_attacked and not was_attacked:
                    target_name = PIECE_NAMES.get(target.piece_type, "piece")
                    # Find WHICH of our pieces now attacks this target (the one behind the moved piece)
                    new_attackers = list(sim.attackers(user_color, sq))
                    old_attackers = list(board.attackers(user_color, sq))
                    revealed_pieces = [a for a in new_attackers if a not in old_attackers and a != move.to_square]
                    if revealed_pieces:
                        revealer = sim.piece_at(revealed_pieces[0])
                        if revealer:
                            revealer_name = PIECE_NAMES.get(revealer.piece_type, "piece")
                            revealer_sq = chess.square_name(revealed_pieces[0])
                            parts.append(f"and opens the line for your {revealer_name} on {revealer_sq} to attack their {target_name}")
                        else:
                            parts.append(f"and reveals an attack on their {target_name} on {chess.square_name(sq)}")
                    else:
                        parts.append(f"and reveals an attack on their {target_name} on {chess.square_name(sq)}")
                    break

    # Check if the move opened a line for our sliding piece (even if no immediate attack target)
    # E.g., pawn moves off diagonal → bishop gets a longer line
    if len(parts) <= 2:
        for sq in chess.SQUARES:
            our_piece = sim.piece_at(sq)
            if not our_piece or our_piece.color != user_color:
                continue
            if our_piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                continue
            # Compare mobility before vs after
            attacks_after = len(list(sim.attacks(sq)))
            attacks_before = len(list(board.attacks(sq))) if board.piece_at(sq) else 0
            if attacks_after > attacks_before + 3:  # Significant increase
                p_name = PIECE_NAMES.get(our_piece.piece_type, "piece")
                parts.append(f"and opens up the line for your {p_name} on {chess.square_name(sq)}")
                break

    if len(parts) <= 1:
        return ""

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
