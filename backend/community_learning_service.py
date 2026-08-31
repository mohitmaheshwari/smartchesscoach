"""
Community Learning Service

Allows users to share puzzles from their games and browse community puzzles.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import chess
import logging

from services.puzzle_extraction_service import (
    verified_mongo_clause,
    verified_pool_mongo_clause,
    verified_issue_type,
    verified_puzzle_admission_enforced,
)
from services.verified_puzzle_admission import (
    ADMISSION_VERSION,
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import build_imported_game_verdict
from services.verified_puzzle_runtime import (
    public_puzzle_payload,
    resolve_verified_puzzle,
)
from services.verified_puzzle_attempt_service import record_verified_puzzle_attempt

logger = logging.getLogger(__name__)


async def share_puzzle(
    db: AsyncIOMotorDatabase,
    user_id: str,
    puzzle_data: Dict
) -> Dict:
    """
    Share a puzzle from the user's game to the community pool.
    """
    # Client values identify the source position; they do not establish the
    # answer or diagnosis. Those come from the stored game analysis below.
    required = ["fen", "best_move_san", "game_id"]
    for field in required:
        if field not in puzzle_data:
            return {"error": f"Missing required field: {field}"}
    
    # Validate FEN format
    try:
        board = chess.Board(puzzle_data["fen"])
        # Also validate the best move is legal in this position
        try:
            board.parse_san(puzzle_data["best_move_san"])
        except chess.InvalidMoveError:
            return {"error": f"Invalid move '{puzzle_data['best_move_san']}' for this position"}
    except ValueError as e:
        return {"error": f"Invalid FEN: {str(e)}"}

    game_id = puzzle_data.get("game_id")
    game = await db.games.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1,
         "opening": 1, "opening_name": 1, "opening_eco": 1},
    )
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1},
    )
    if not game or not analysis:
        return {"error": "This position could not be verified against your analyzed game."}

    wanted_fen = " ".join(board.fen().split()[:4])
    source_move = None
    for move_evaluation in (
        ((analysis.get("stockfish_analysis") or {}).get("move_evaluations")) or []
    ):
        try:
            candidate_fen = " ".join(
                chess.Board(move_evaluation.get("fen_before")).fen().split()[:4]
            )
        except (TypeError, ValueError):
            continue
        if candidate_fen != wanted_fen:
            continue
        source_best = (
            move_evaluation.get("best_move_san")
            or move_evaluation.get("best_move")
        )
        if source_best == puzzle_data.get("best_move_san"):
            source_move = move_evaluation
            break
    if source_move is None:
        return {"error": "The shared answer does not match the stored analysis for this game."}

    verdict = build_imported_game_verdict(
        game=game,
        move_evaluation=source_move,
        broad_category=source_move.get("cognitive_gap") or None,
    )
    if verdict.status == AdmissionStatus.QUARANTINE:
        return {"error": "This position needs evidence repair before it can be shared."}
    issue_type = verified_issue_type(verdict)
    
    # Check if puzzle already exists (same FEN and best move)
    existing = await db.community_puzzles.find_one({
        "fen": puzzle_data["fen"],
        "best_move_san": puzzle_data["best_move_san"]
    })
    
    if existing:
        return {"error": "This puzzle already exists in the community", "existing_id": str(existing["_id"])}
    
    # Create community puzzle document
    puzzle = {
        "fen": puzzle_data["fen"],
        "best_move_san": puzzle_data["best_move_san"],
        "issue_type": issue_type,
        "legacy_issue_type": puzzle_data.get("issue_type"),
        "theme": "calculation" if issue_type == "calculation_depth" else "tactical",
        "difficulty": puzzle_data.get("difficulty", "intermediate"),
        "opening_name": puzzle_data.get("opening_name"),
        "opening_eco": puzzle_data.get("opening_eco"),
        "move_number": puzzle_data.get("move_number"),
        "user_color": puzzle_data.get("user_color", "white"),
        "shared_by": user_id,
        "source_game_id": puzzle_data.get("game_id"),
        "description": (
            "From a real game — find the move that keeps every piece safe."
            if issue_type == "piece_safety"
            else "From a real game — calculate the best continuation."
        ),
        "best_move_uci": source_move.get("best_move_uci"),
        "played_move": source_move.get("move") or source_move.get("move_san"),
        "pv_after_best": source_move.get("pv_after_best") or [],
        "pv_after_played": source_move.get("pv_after_played") or [],
        "verified_admission": verdict.to_document(),
        "attempts": 0,
        "solves": 0,
        "solve_rate": 0.0,
        "ratings": [],
        "avg_rating": 0.0,
        "created_at": datetime.now(timezone.utc),
        "approved": True,
        "featured": False
    }
    
    result = await db.community_puzzles.insert_one(puzzle)
    
    # Update user's contribution count
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": {"puzzles_shared": 1},
            "$set": {"last_share": datetime.now(timezone.utc)}
        }
    )
    
    return {
        "success": True,
        "puzzle_id": str(result.inserted_id),
        "message": "Puzzle shared with the community!"
    }


async def get_community_puzzles(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    theme: Optional[str] = None,
    opening: Optional[str] = None,
    sort_by: str = "newest",
    skip: int = 0,
    limit: int = 20
) -> Dict:
    """
    Get community puzzles with optional filtering.
    """
    # Build query
    query = {"approved": True, **verified_pool_mongo_clause()}
    if verified_puzzle_admission_enforced():
        if theme:
            query["$and"] = [verified_mongo_clause(theme)]
    
    if difficulty:
        query["difficulty"] = difficulty
    
    if theme:
        query["issue_type"] = theme
    
    if opening:
        query.setdefault("$and", []).append({"$or": [
            {"opening_name": {"$regex": opening, "$options": "i"}},
            {"opening_eco": {"$regex": opening, "$options": "i"}}
        ]})
    
    # Build sort
    sort_options = {
        "newest": [("created_at", -1)],
        "oldest": [("created_at", 1)],
        "most_solved": [("solves", -1)],
        "hardest": [("solve_rate", 1), ("attempts", -1)],
        "easiest": [("solve_rate", -1), ("attempts", -1)],
        "highest_rated": [("avg_rating", -1)]
    }
    
    sort = sort_options.get(sort_by, [("created_at", -1)])
    
    # Get puzzles
    fetch_limit = limit * (5 if verified_puzzle_admission_enforced() else 1)
    cursor = db.community_puzzles.find(query).sort(sort).skip(skip).limit(fetch_limit)
    puzzles = await cursor.to_list(fetch_limit)
    if verified_puzzle_admission_enforced():
        puzzles = [p for p in puzzles if stored_verdict_is_structurally_current(p)]
    puzzles = puzzles[:limit]
    
    # Get total count
    total = await db.community_puzzles.count_documents(query)
    
    # Process puzzles
    processed = []
    for p in puzzles:
        # Check if current user has solved this puzzle
        user_solved = False
        if user_id:
            attempt = await db.puzzle_attempts.find_one({
                "puzzle_id": str(p["_id"]),
                "user_id": user_id,
                "correct": True
            })
            user_solved = attempt is not None
        
        processed.append(public_puzzle_payload({
            "puzzle_id": str(p["_id"]),
            "fen": p["fen"],
            "issue_type": p["issue_type"],
            "theme": p.get("theme", "tactical"),
            "difficulty": p["difficulty"],
            "opening_name": p.get("opening_name"),
            "user_color": p.get("user_color", "white"),
            "attempts": p["attempts"],
            "solves": p["solves"],
            "solve_rate": round(p.get("solve_rate", 0), 1),
            "avg_rating": round(p.get("avg_rating", 0), 1),
            "shared_by": p["shared_by"],
            "created_at": p["created_at"].isoformat() if p.get("created_at") else None,
            "featured": p.get("featured", False),
            "user_solved": user_solved
        }))
    
    return {
        "puzzles": processed,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + limit < total
    }


async def attempt_community_puzzle(
    db: AsyncIOMotorDatabase,
    user_id: str,
    puzzle_id: str,
    user_move: str,
    time_taken: Optional[int] = None
) -> Dict:
    """
    Record a user's attempt on a community puzzle.
    """
    try:
        puzzle_oid = ObjectId(puzzle_id)
    except Exception:
        return {"error": "Invalid puzzle ID"}
    
    puzzle = await db.community_puzzles.find_one({"_id": puzzle_oid})
    if not puzzle:
        return {"error": "Puzzle not found"}
    if puzzle.get("approved") is False:
        return {"error": "Puzzle is not available for training"}
    
    try:
        board = chess.Board(puzzle.get("fen"))
        try:
            user_obj = board.parse_san(user_move)
        except ValueError:
            user_obj = chess.Move.from_uci(user_move)
            if user_obj not in board.legal_moves:
                raise ValueError("illegal move")
    except (TypeError, ValueError):
        return {"error": "That move is not legal in this position"}

    resolved = await resolve_verified_puzzle(db, puzzle_id, user_id=user_id)
    if not resolved:
        return {"error": "Puzzle needs evidence repair before it can be graded"}
    grade = await record_verified_puzzle_attempt(
        db,
        user_id=user_id,
        puzzle_id=puzzle_id,
        puzzle=resolved,
        played_uci=user_obj.uci(),
        time_taken_ms=time_taken,
    )
    if grade.get("quality") == "invalid":
        return {"error": grade.get("feedback") or "This move could not be graded"}
    correct = bool(grade.get("correct"))
    
    # Update puzzle stats
    update = {
        "$inc": {
            "attempts": 1,
            "solves": 1 if correct else 0
        }
    }
    
    result = await db.community_puzzles.find_one_and_update(
        {"_id": puzzle_oid},
        update,
        return_document=True
    )
    
    # Recalculate solve rate
    if result:
        new_solve_rate = (result["solves"] / result["attempts"] * 100) if result["attempts"] > 0 else 0
        await db.community_puzzles.update_one(
            {"_id": puzzle_oid},
            {"$set": {"solve_rate": new_solve_rate}}
        )
    
    return {
        "correct": correct,
        "expected_move": grade.get("best_move_san"),
        "solve_rate": round(new_solve_rate if result else 0, 1),
        "message": grade.get("feedback"),
        "recovery_credit_awarded": grade.get("recovery_credit_awarded", False),
    }


async def rate_puzzle(
    db: AsyncIOMotorDatabase,
    user_id: str,
    puzzle_id: str,
    rating: int
) -> Dict:
    """
    Rate a community puzzle (1-5 stars).
    """
    if rating < 1 or rating > 5:
        return {"error": "Rating must be between 1 and 5"}
    
    try:
        puzzle_oid = ObjectId(puzzle_id)
    except Exception:
        return {"error": "Invalid puzzle ID"}
    
    # Check if user already rated
    existing = await db.puzzle_ratings.find_one({
        "puzzle_id": puzzle_id,
        "user_id": user_id
    })
    
    if existing:
        # Update existing rating
        await db.puzzle_ratings.update_one(
            {"_id": existing["_id"]},
            {"$set": {"rating": rating, "updated_at": datetime.now(timezone.utc)}}
        )
    else:
        # Add new rating
        await db.puzzle_ratings.insert_one({
            "puzzle_id": puzzle_id,
            "user_id": user_id,
            "rating": rating,
            "created_at": datetime.now(timezone.utc)
        })
    
    # Recalculate average rating
    ratings = await db.puzzle_ratings.find({"puzzle_id": puzzle_id}).to_list(1000)
    avg_rating = sum(r["rating"] for r in ratings) / len(ratings) if ratings else 0
    
    await db.community_puzzles.update_one(
        {"_id": puzzle_oid},
        {
            "$set": {"avg_rating": avg_rating},
            "$addToSet": {"ratings": user_id}
        }
    )
    
    return {
        "success": True,
        "avg_rating": round(avg_rating, 1),
        "total_ratings": len(ratings)
    }


async def get_community_stats(
    db: AsyncIOMotorDatabase
) -> Dict:
    """
    Get overall community puzzle statistics.
    """
    # Total puzzles
    pool_query = {"approved": True, **verified_pool_mongo_clause()}
    total_puzzles = await db.community_puzzles.count_documents(pool_query)
    
    # Total attempts
    total_attempts = await db.puzzle_attempts.count_documents({})
    
    # Total solves
    total_solves = await db.puzzle_attempts.count_documents({"correct": True})
    
    # Unique contributors
    contributors_pipeline = [
        {"$match": pool_query},
        {"$group": {"_id": "$shared_by"}},
        {"$count": "count"}
    ]
    contributors_result = await db.community_puzzles.aggregate(contributors_pipeline).to_list(1)
    unique_contributors = contributors_result[0]["count"] if contributors_result else 0
    
    # Most popular puzzles
    sample_limit = 25 if verified_puzzle_admission_enforced() else 5
    popular = await db.community_puzzles.find(
        {**pool_query, "attempts": {"$gt": 0}}
    ).sort("attempts", -1).limit(sample_limit).to_list(sample_limit)
    
    # Hardest puzzles (lowest solve rate with sufficient attempts)
    hardest = await db.community_puzzles.find(
        {**pool_query, "attempts": {"$gte": 5}}
    ).sort("solve_rate", 1).limit(sample_limit).to_list(sample_limit)
    if verified_puzzle_admission_enforced():
        popular = [p for p in popular if stored_verdict_is_structurally_current(p)]
        hardest = [p for p in hardest if stored_verdict_is_structurally_current(p)]
    popular = popular[:5]
    hardest = hardest[:5]
    
    def format_puzzle(p):
        return {
            "puzzle_id": str(p["_id"]),
            "fen": p["fen"],
            "issue_type": p.get("issue_type"),
            "difficulty": p.get("difficulty"),
            "attempts": p["attempts"],
            "solves": p["solves"],
            "solve_rate": round(p.get("solve_rate", 0), 1)
        }
    
    return {
        "total_puzzles": total_puzzles,
        "total_attempts": total_attempts,
        "total_solves": total_solves,
        "overall_solve_rate": round((total_solves / total_attempts * 100) if total_attempts > 0 else 0, 1),
        "unique_contributors": unique_contributors,
        "most_popular": [format_puzzle(p) for p in popular],
        "hardest_puzzles": [format_puzzle(p) for p in hardest]
    }


async def get_user_contributions(
    db: AsyncIOMotorDatabase,
    user_id: str
) -> Dict:
    """
    Get a user's puzzle contributions and stats.
    """
    # User's shared puzzles
    puzzles = await db.community_puzzles.find(
        {"shared_by": user_id, "approved": True, **verified_pool_mongo_clause()}
    ).sort("created_at", -1).to_list(50)
    if verified_puzzle_admission_enforced():
        puzzles = [p for p in puzzles if stored_verdict_is_structurally_current(p)]
    
    # Calculate totals
    total_shared = len(puzzles)
    total_attempts = sum(p.get("attempts", 0) for p in puzzles)
    total_solves = sum(p.get("solves", 0) for p in puzzles)
    
    formatted_puzzles = []
    for p in puzzles:
        formatted_puzzles.append({
            "puzzle_id": str(p["_id"]),
            "fen": p["fen"],
            "issue_type": p.get("issue_type"),
            "difficulty": p.get("difficulty"),
            "attempts": p.get("attempts", 0),
            "solves": p.get("solves", 0),
            "solve_rate": round(p.get("solve_rate", 0), 1),
            "avg_rating": round(p.get("avg_rating", 0), 1),
            "created_at": p["created_at"].isoformat() if p.get("created_at") else None
        })
    
    return {
        "total_shared": total_shared,
        "total_attempts_received": total_attempts,
        "total_solves_received": total_solves,
        "puzzles": formatted_puzzles
    }
