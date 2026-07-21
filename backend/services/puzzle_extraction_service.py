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


# ── Quality gates for "is this position worth keeping as a puzzle?" ──
# Loose extraction gave us positional moves where the engine prefers
# move A over move B by 30cp — bad teaching material because there's
# no clean idea to teach. Real puzzles need a forcing best move OR a
# detectable tactical pattern.

# Mate-detection sentinel cap. cp_loss can spike to 5000+ on missed
# mates; we exclude those — "find mate-in-7" is not a 1200 puzzle.
PUZZLE_MAX_CP_LOSS = 2000

# Below this rating, an endgame-phase mistake (move > END_PHASE_PLY)
# usually isn't tactical training material — they need pattern training,
# not endgame conversion grind.
ENDGAME_FILTER_RATING = 1500
END_PHASE_PLY = 30  # full-move number, not ply


def _is_puzzle_worthy(
    fen_before: str,
    best_move_san: str,
    best_move_uci: Optional[str],
    pv_after_best: Optional[List[str]],
    move_number: int,
    user_rating: int,
    cp_loss: int,
) -> bool:
    """Decide whether a (position, best_move) pair is good teaching
    material. Three checks:

    1. cp_loss within sane bounds (no mate sentinels)
    2. Best move is forcing (capture / check / mate) OR
       pv_tactical_analyzer detects a real pattern
    3. Phase appropriate for the user's rating
    """
    # 1. Bounds
    if cp_loss <= 0 or cp_loss > PUZZLE_MAX_CP_LOSS:
        return False

    # 3. Phase filter — endgame mistakes for low-rated users aren't
    # the tactical pattern training the system serves.
    if user_rating < ENDGAME_FILTER_RATING and move_number > END_PHASE_PLY:
        return False

    # 2. Forcing test (cheap): capture / check / mate marker in SAN.
    san = (best_move_san or "").strip()
    if not san:
        return False
    is_forcing = any(ch in san for ch in ("x", "+", "#"))

    if is_forcing:
        return True

    # 2b. Tactical-pattern test (more expensive): does the engine's PV
    # show a fork/pin/skewer/discovery/exposed-defender after best move?
    # If yes, it's a real pattern even though SAN doesn't have x/+/#
    # (e.g., a quiet move that sets up a winning threat).
    if best_move_uci and pv_after_best:
        try:
            from services.pv_tactical_analyzer import explain_best_move_tactically
            tactical = explain_best_move_tactically(
                fen_before, best_move_uci, san, pv_after_best
            )
            if tactical:
                return True
        except Exception as e:
            logger.debug(f"pv_tactical_analyzer failed for puzzle screen: {e}")

    # No forcing move, no detectable pattern — likely a positional
    # preference. Skip; it's not pattern training.
    return False


async def extract_puzzles_from_game(
    db: AsyncIOMotorDatabase,
    game_id: str,
    user_id: str,
) -> List[Dict]:
    """
    Extract training puzzles from an analyzed game.
    Uses rating-aware thresholds to determine what counts as a meaningful
    blunder worth extracting. An 800 player's 80cp inaccuracy isn't
    puzzle-worthy; their 300cp blunder is.
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

    # Get user's rating for threshold calculation
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "rating": 1})
    user_rating = (user_doc or {}).get("rating", 1200)

    # Rating-aware extraction thresholds (centipawns)
    # AGGRESSIVE backfill: extract ALL mistakes, not just big blunders
    # More drill material = more learning opportunity
    if user_rating < 1000:
        min_cp_loss = 75   # Include small mistakes for beginners (was 200)
    elif user_rating < 1400:
        min_cp_loss = 50   # More puzzles for intermediate (was 150)
    elif user_rating < 1800:
        min_cp_loss = 30   # Capture subtle mistakes for advanced (was 100)
    else:
        min_cp_loss = 20   # Capture inaccuracies for experts (was 75)

    sf = analysis.get("stockfish_analysis", {})
    evals = sf.get("move_evaluations", [])
    user_color = game.get("user_color", "white")

    created = []

    skipped_quality = 0
    for ev in evals:
        cp_loss = ev.get("cp_loss", 0)
        # Rating-aware threshold
        if cp_loss < min_cp_loss:
            continue

        fen_before = ev.get("fen_before")
        # Support both field names
        best_move = ev.get("best_move_san") or ev.get("best_move")
        best_move_uci = ev.get("best_move_uci")
        pv_after_best = ev.get("pv_after_best") or []
        cognitive_gap = ev.get("cognitive_gap", "")
        move_number = ev.get("move_number", 0)

        if not fen_before or not best_move:
            continue

        # Quality gate — skip positional/non-teaching positions.
        if not _is_puzzle_worthy(
            fen_before=fen_before,
            best_move_san=best_move,
            best_move_uci=best_move_uci,
            pv_after_best=pv_after_best if isinstance(pv_after_best, list) else [],
            move_number=move_number,
            user_rating=int(user_rating or 1200),
            cp_loss=int(cp_loss),
        ):
            skipped_quality += 1
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
            # `rating` = rating of the source user (whose game produced this puzzle).
            # Used by the serve-time rating filter so a 900-rated player doesn't
            # get puzzles from 1800-rated games. Stored from user_rating on
            # extraction; `ratings: []` + `avg_rating` separately track the
            # RATINGS OF USERS WHO ATTEMPT this puzzle (a different thing).
            "rating": int(user_rating) if user_rating else 1200,
            "ratings": [],
            "avg_rating": 0.0,
            "created_at": datetime.now(timezone.utc),
            "approved": True,
            "featured": False,
        }

        # Motif tag (fork; pin/skewer later) — the tactical motif the blunder walked into,
        # via the verified detector. Lets weakness drills filter by motif (own→community).
        try:
            from services.motif_profile_service import position_allows_motif
            _motif = position_allows_motif(ev)
            if _motif:
                puzzle["motif"] = _motif
        except Exception:
            pass

        result = await db.community_puzzles.insert_one(puzzle)
        puzzle_copy = {k: v for k, v in puzzle.items() if k != "_id"}
        puzzle_copy["puzzle_id"] = str(result.inserted_id)
        created.append(puzzle_copy)

    if created or skipped_quality:
        logger.info(
            f"Extracted {len(created)} puzzles from game {game_id} "
            f"(user {user_id}, skipped {skipped_quality} positional/no-pattern)"
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


# Map a cognitive-gap key (community_puzzles.issue_type) to the equivalent
# Play-with-Coach pattern_type(s) in community_training_positions, so the
# pattern-training page serves BOTH pools. Mohit 2026-07-10 — the PWC pool
# (~30k positions) was extracted but hidden from /training/pattern, which read
# community_puzzles (~4k) only.
GAP_TO_PWC_PATTERNS = {
    "piece_safety":       ["piece_safety", "hanging_piece"],
    "missed_tactic":      ["tactical", "tactical_miss", "missed_threat", "pin"],
    "tactical_oversight": ["tactical_oversight", "tactical"],
    "calculation_depth":  ["calculation_depth"],
    "king_safety":        ["king_safety"],
    # opening_knowledge / endgame_technique / piece_activity / pawn_structure:
    # no PWC-pool equivalent — those serve from community_puzzles only.
}


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

    Now includes decay state and score to help prioritize training.

    Returns:
    {
        "pattern": "piece_safety",
        "pattern_label": "Piece Safety",
        "decay_state": "active",
        "decay_score": 3.2,
        "own_puzzles": [...],
        "community_puzzles": [...],
        "total_available": N,
        "unsolved_count": M,
        "solved_count": P,
    }
    """
    # Get decay score for this pattern to add context to training
    from services.pattern_decay_service import refresh_user_pattern_decay
    pattern_scores = await refresh_user_pattern_decay(db, user_id)
    decay_state = "active"
    decay_score = 0.0
    if pattern in pattern_scores:
        decay_state = pattern_scores[pattern].get("state", "active")
        decay_score = pattern_scores[pattern].get("weighted_score", 0.0)

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
            "decay_state": decay_state,
            "decay_score": decay_score,
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
            "decay_state": decay_state,
            "decay_score": decay_score,
        })

    # 3. Play-with-Coach pool (community_training_positions) for the same gap.
    #    This pool is ~7x bigger than community_puzzles and was NOT reaching this
    #    page. The user's OWN coach-game mistakes are the most impactful, so they
    #    lead (own_puzzles); others fill the community list. Mohit 2026-07-10.
    pwc_types = GAP_TO_PWC_PATTERNS.get(pattern, [])
    if pwc_types:
        def _pwc_int(v):
            try:
                return int(v)
            except Exception:
                return None

        def _shape_pwc(p, source):
            pid = p.get("position_id") or str(p.get("_id"))
            return {
                "puzzle_id": pid,
                "fen": p.get("fen"),
                "best_move_san": p.get("best_move_san") or "",
                "issue_type": pattern,
                "difficulty": p.get("difficulty", "intermediate"),
                "move_number": _pwc_int(p.get("move_number")),
                "user_color": p.get("user_color", "white"),
                "source": source,
                "source_game_id": p.get("source_game_id"),
                "description": p.get("moment_tag") or "",
                "already_solved": pid in solved_ids,
                "solve_rate": round(float(p.get("solve_rate", 0) or 0), 1),
                "decay_state": decay_state,
                "decay_score": decay_score,
            }

        # IMPORTANT: on prod this collection reliably serves only EXACT-match
        # queries — it has just the _id_ index and $in / $exists return WRONG
        # results (0) on it (Mohit 2026-07-10 — flagged for a reindex). So query
        # each pattern_type EXACTLY and do the rest of the filtering in Python.
        for t in pwc_types:
            # 3a. the user's OWN coach-game mistakes for this pattern — lead.
            #     (compound exact match {pattern_type, source_user_id} works.)
            own_pwc = db.community_training_positions.find(
                {"pattern_type": t, "source_user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            async for p in own_pwc:
                sh = _shape_pwc(p, "own_coach_game")
                if sh["fen"] and sh["best_move_san"]:
                    own_puzzles.append(sh)
            # 3b. other users' coach-game puzzles — fill community up to `limit`.
            if len(community_puzzles) < limit:
                comm_pwc = db.community_training_positions.find(
                    {"pattern_type": t}
                ).sort("solve_rate", -1).limit(limit + 20)
                async for p in comm_pwc:
                    if len(community_puzzles) >= limit:
                        break
                    if p.get("source_user_id") == user_id:
                        continue  # own — already added above
                    sh = _shape_pwc(p, "coach_game")
                    if sh["puzzle_id"] in solved_ids or not sh["fen"] or not sh["best_move_san"]:
                        continue
                    community_puzzles.append(sh)

    # Stats
    total_own = len(own_puzzles)
    total_community = len(community_puzzles)
    unsolved_own = len([p for p in own_puzzles if not p["already_solved"]])

    # Calculate games to next state transition
    games_to_next = 999
    if decay_state == "active" and decay_score > 0:
        # How many more clean games until DECLINING (score <= 2)?
        games_to_next = max(0, int(decay_score - 2.0))
    elif decay_state == "declining" and decay_score > 0:
        # How many more clean games until FADING (score < 1)?
        games_to_next = max(0, int(decay_score - 1.0))

    return {
        "pattern": pattern,
        "pattern_label": pattern.replace("_", " ").title(),
        "decay_state": decay_state,
        "decay_score": round(decay_score, 2),
        "games_to_next_state": games_to_next,
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
