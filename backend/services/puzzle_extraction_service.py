"""
Puzzle Extraction Pipeline
==========================

Extracts training puzzles from analyzed games automatically.
When a game is analyzed and blunders are detected, the position BEFORE
the bad move becomes a training puzzle tagged with the cognitive gap.

These puzzles form the "community" pool that other users with the same
weakness pattern get served.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import chess
import logging

logger = logging.getLogger(__name__)


async def extract_puzzles_from_game(
    db: AsyncIOMotorDatabase,
    game_id: str,
    user_id: str,
) -> List[Dict]:
    """
    Extract training puzzles from an analyzed game.

    Looks at move evaluations, finds significant blunders (cp_loss >= 100),
    and creates puzzle entries from the position before the bad move.

    Returns list of created puzzle dicts.
    """
    analysis = await db.game_analyses.find_one(
        {"game_id": game_id, "user_id": user_id},
        {"_id": 0},
    )
    if not analysis:
        return []

    game = await db.games.find_one(
        {"game_id": game_id},
        {"_id": 0, "user_color": 1, "opening": 1, "opening_eco": 1},
    )
    if not game:
        return []

    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white")

    created = []

    for ev in evals:
        cp_loss = ev.get("cp_loss", 0)
        # Only extract significant mistakes
        if cp_loss < 100:
            continue

        fen_before = ev.get("fen_before")
        # Support both field names
        best_move = ev.get("best_move_san") or ev.get("best_move")
        cognitive_gap = ev.get("cognitive_gap", "")
        move_number = ev.get("move_number", 0)

        if not fen_before or not best_move:
            continue

        # Infer cognitive gap from position if not explicitly tagged
        if not cognitive_gap:
            cognitive_gap = _infer_cognitive_gap(fen_before, best_move, cp_loss)

        if not cognitive_gap:
            cognitive_gap = "calculation_depth"  # Default for unclassified blunders

        # Validate the position and move
        try:
            board = chess.Board(fen_before)
            board.parse_san(best_move)
        except (ValueError, chess.InvalidMoveError):
            continue

        # Skip if puzzle already exists (same FEN + best move)
        existing = await db.community_puzzles.find_one({
            "fen": fen_before,
            "best_move_san": best_move,
        })
        if existing:
            continue

        # Determine difficulty from cp_loss
        if cp_loss >= 400:
            difficulty = "beginner"  # Big blunder = obvious to spot
        elif cp_loss >= 200:
            difficulty = "intermediate"
        else:
            difficulty = "advanced"  # Subtle mistake

        puzzle = {
            "fen": fen_before,
            "best_move_san": best_move,
            "issue_type": cognitive_gap,
            "theme": _gap_to_theme(cognitive_gap),
            "difficulty": difficulty,
            "opening_name": game.get("opening"),
            "opening_eco": game.get("opening_eco"),
            "move_number": move_number,
            "user_color": user_color,
            "shared_by": user_id,
            "source_game_id": game_id,
            "source": "auto_extracted",
            "description": f"From a real game — find the best move (was a {cognitive_gap.replace('_', ' ')} mistake)",
            "cp_loss": cp_loss,
            "attempts": 0,
            "solves": 0,
            "solve_rate": 0.0,
            "ratings": [],
            "avg_rating": 0.0,
            "created_at": datetime.now(timezone.utc),
            "approved": True,
            "featured": False,
        }

        result = await db.community_puzzles.insert_one(puzzle)
        puzzle_copy = {k: v for k, v in puzzle.items() if k != "_id"}
        puzzle_copy["puzzle_id"] = str(result.inserted_id)
        created.append(puzzle_copy)

    if created:
        logger.info(
            f"Extracted {len(created)} puzzles from game {game_id} (user {user_id})"
        )

    return created


async def backfill_puzzles_for_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    max_games: int = 30,
) -> int:
    """
    Backfill puzzles from a user's already-analyzed games.
    Returns total puzzles created.
    """
    # Find games that have analyses (regardless of is_analyzed flag)
    analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0, "game_id": 1},
    ).sort("created_at", -1).limit(max_games).to_list(max_games)

    total = 0
    for a in analyses:
        puzzles = await extract_puzzles_from_game(db, a["game_id"], user_id)
        total += len(puzzles)

    return total


async def get_pattern_training_puzzles(
    db: AsyncIOMotorDatabase,
    user_id: str,
    pattern: str,
    limit: int = 15,
) -> Dict:
    """
    Get training puzzles for a specific cognitive gap pattern.

    Priority:
    1. User's own game positions (most impactful — they recognize the context)
    2. Community puzzles from other users with the same pattern
    Excludes puzzles the user has already solved.

    Returns:
    {
        "pattern": "piece_safety",
        "own_puzzles": [...],
        "community_puzzles": [...],
        "total": N,
        "solved_count": M,
    }
    """
    # Get puzzle IDs the user has already solved
    solved_cursor = db.puzzle_attempts.find(
        {"user_id": user_id, "correct": True},
        {"_id": 0, "puzzle_id": 1},
    )
    solved_ids = set()
    async for doc in solved_cursor:
        solved_ids.add(doc.get("puzzle_id", ""))

    # 1. User's own puzzles for this pattern
    own_cursor = db.community_puzzles.find(
        {
            "shared_by": user_id,
            "issue_type": pattern,
            "approved": True,
        },
    ).sort("created_at", -1).limit(limit)

    own_puzzles = []
    async for p in own_cursor:
        pid = str(p["_id"])
        own_puzzles.append({
            "puzzle_id": pid,
            "fen": p["fen"],
            "best_move_san": p["best_move_san"],
            "issue_type": p["issue_type"],
            "difficulty": p.get("difficulty", "intermediate"),
            "move_number": p.get("move_number"),
            "user_color": p.get("user_color", "white"),
            "source": "own_game",
            "source_game_id": p.get("source_game_id"),
            "description": p.get("description", ""),
            "already_solved": pid in solved_ids,
            "solve_rate": round(p.get("solve_rate", 0), 1),
        })

    # 2. Community puzzles (from other users, same pattern, not already solved)
    remaining = max(0, limit - len([p for p in own_puzzles if not p["already_solved"]]))

    community_query = {
        "shared_by": {"$ne": user_id},
        "issue_type": pattern,
        "approved": True,
    }

    community_cursor = db.community_puzzles.find(community_query).sort(
        "solve_rate", -1  # Easier ones first to build confidence
    ).limit(remaining + 10)  # Fetch extra to filter solved

    community_puzzles = []
    async for p in community_cursor:
        pid = str(p["_id"])
        if pid in solved_ids:
            continue
        if len(community_puzzles) >= remaining:
            break
        community_puzzles.append({
            "puzzle_id": pid,
            "fen": p["fen"],
            "best_move_san": p["best_move_san"],
            "issue_type": p["issue_type"],
            "difficulty": p.get("difficulty", "intermediate"),
            "move_number": p.get("move_number"),
            "user_color": p.get("user_color", "white"),
            "source": "community",
            "description": p.get("description", ""),
            "already_solved": False,
            "solve_rate": round(p.get("solve_rate", 0), 1),
        })

    # Stats
    total_own = len(own_puzzles)
    total_community = len(community_puzzles)
    unsolved_own = len([p for p in own_puzzles if not p["already_solved"]])

    return {
        "pattern": pattern,
        "pattern_label": pattern.replace("_", " ").title(),
        "own_puzzles": own_puzzles,
        "community_puzzles": community_puzzles,
        "total_available": total_own + total_community,
        "unsolved_count": unsolved_own + total_community,
        "solved_count": len(solved_ids),
    }


def _gap_to_theme(gap: str) -> str:
    """Map cognitive gap to a broader theme category."""
    mapping = {
        "piece_safety": "tactical",
        "missed_tactic": "tactical",
        "missed_fork": "tactical",
        "missed_pin": "tactical",
        "missed_skewer": "tactical",
        "back_rank": "tactical",
        "king_safety": "defensive",
        "pawn_structure": "positional",
        "piece_activity": "positional",
        "calculation_depth": "calculation",
        "time_pressure": "time_management",
        "opening_knowledge": "opening",
        "endgame_technique": "endgame",
    }
    return mapping.get(gap, "tactical")



def _infer_cognitive_gap(fen: str, best_move: str, cp_loss: int) -> str:
    """
    Infer the cognitive gap from position characteristics when not explicitly tagged.
    Uses the position, the best move, and the centipawn loss to classify.
    """
    try:
        board = chess.Board(fen)
        move = board.parse_san(best_move)

        # Check if best move is a capture — likely piece safety issue
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and captured.piece_type in (chess.QUEEN, chess.ROOK):
                return "piece_safety"
            if captured:
                return "missed_tactic"

        # Check if best move gives check — likely tactical miss
        board.push(move)
        if board.is_check():
            board.pop()
            return "missed_tactic"
        board.pop()

        # Check for hanging pieces in the position
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == board.turn:
                if board.is_attacked_by(not board.turn, sq):
                    if not board.is_attacked_by(board.turn, sq):
                        return "piece_safety"

        # Large cp_loss without obvious tactical features
        if cp_loss >= 300:
            return "piece_safety"
        elif cp_loss >= 150:
            return "calculation_depth"

    except Exception:
        pass

    return ""
