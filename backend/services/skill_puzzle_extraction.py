"""Skill-puzzle extraction — turns skill evidence into drillable puzzles.

Engine 2 already records skill evidence: each `coach_memory.learning.
skills[skill_id].evidence[i]` entry holds the position where a
concept detector fired, the user's move, and the outcome ("applied"
or "missed"). The MasteryPanel "Why we credited you" modal renders
these for inspection.

This module turns the SAME evidence into puzzles in the existing
`community_puzzles` collection — adding two new fields:

  skill_id          : "endgame_rule_of_square" (or whatever skill)
  grading_strategy  : "detector"  → grade by running the detector on
                                    the user's submitted move
                      "san_match" → grade by SAN equality (existing
                                    pattern-puzzle behavior)

Defaults preserve existing behavior: missing skill_id + missing
grading_strategy reads as a standard pattern puzzle. So extending
the schema doesn't disturb the existing serve/grade paths — they
just ignore the extra fields.

For skill puzzles we set `grading_strategy: "detector"` because the
"right answer" in a king-pawn race isn't always a single move (any
king move into the catch zone is correct, for example). The detector
already knows which moves are "applied" — so let it judge.

Mohit 2026-06-01. Built after we shipped the skill_id migration
(rule_of_square → endgame_rule_of_square) and validated the 22
evidence entries by hand. Piece 2 of the "evidence surface → drill
puzzles → community pool" track.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Mapping from skill_id to a human caption shown in the drill card.
# Kept here (not on the skill_tree) because skill-tree captions are
# the lesson hooks; these are drill prompts — different audience.
SKILL_PROMPT = {
    "endgame_rule_of_square": (
        "Pawn race. Can the king catch it? Find the right move."
    ),
    # extend as we wire other detectors into puzzles
}


async def extract_skill_puzzles_for_user(
    db: AsyncIOMotorDatabase,
    user_id: str,
    skill_id: str = "endgame_rule_of_square",
) -> Dict:
    """Idempotently turn this user's missed-evidence entries for `skill_id`
    into community_puzzles rows tagged with that skill.

    Returns {"created": n, "skipped_dupe": m, "evidence_seen": k}.

    Skips entries where the same (skill_id, fen) row already exists —
    so the call is safe to retry. Doesn't touch entries with no
    fen_before. Doesn't extract "applied" entries — those aren't
    teaching material, they're already-correct moves.
    """
    mem = await db.coach_memory.find_one({"user_id": user_id})
    if mem is None:
        return {"created": 0, "skipped_dupe": 0, "evidence_seen": 0}

    skills = (mem.get("learning") or {}).get("skills") or []
    skill = next((s for s in skills if s.get("skill_id") == skill_id), None)
    if skill is None:
        return {"created": 0, "skipped_dupe": 0, "evidence_seen": 0}

    user_rating = ((mem.get("identity") or {}).get("rating")
                   or (mem.get("profile") or {}).get("current_rating")
                   or 1200)
    prompt = SKILL_PROMPT.get(skill_id, "Apply the skill — what's the right move?")

    created = 0
    skipped_dupe = 0
    evidence = skill.get("evidence") or []

    for ev in evidence:
        if ev.get("outcome") != "missed":
            continue
        fen = ev.get("fen_before")
        if not fen:
            continue

        # Idempotency on (skill_id, fen). Same position from two users
        # is fine — different shared_by, same puzzle position. But
        # the SAME user inserting twice is a dupe.
        existing = await db.community_puzzles.find_one(
            {"skill_id": skill_id, "fen": fen, "shared_by": user_id}
        )
        if existing:
            skipped_dupe += 1
            continue

        gid = ev.get("game_id")
        game = None
        if gid:
            game = await db.games.find_one(
                {"game_id": gid},
                {"_id": 0, "opening_name": 1, "opening_eco": 1,
                 "user_color": 1, "result": 1, "date_played": 1}
            )

        # Try to pull the engine's best move for this position. Optional —
        # the puzzle is still valid without it (grading uses the detector),
        # but having the engine move on the doc lets the UI show "the
        # engine wanted X" as a follow-up tip after the user solves.
        engine_best_san = None
        engine_best_uci = None
        cp_loss = None
        if gid and ev.get("move_number") is not None:
            analysis = await db.game_analyses.find_one(
                {"game_id": gid},
                {"_id": 0, "move_evaluations": 1}
            )
            for me in (analysis or {}).get("move_evaluations") or []:
                if (me.get("move_number") == ev.get("move_number")
                        and me.get("move") == ev.get("move_san")):
                    engine_best_san = me.get("best_move")
                    engine_best_uci = me.get("best_move_uci")
                    cp_loss = me.get("cp_loss")
                    break

        puzzle = {
            "fen": fen,
            # Best-move fields are still set so the existing
            # community_puzzles indexes don't choke. If the engine
            # didn't give us one, leave empty — grading_strategy
            # "detector" doesn't read them.
            "best_move_san": engine_best_san or "",
            "best_move_uci": engine_best_uci,
            "skill_id": skill_id,
            "grading_strategy": "detector",
            # Tag with the corresponding cognitive gap so existing
            # filters (e.g. by issue_type) still surface these. ROS
            # missed pawn-race usually maps to endgame technique.
            "issue_type": "endgame_technique",
            "theme": "endgame",
            "difficulty": "intermediate",
            "opening_name": (game or {}).get("opening_name"),
            "opening_eco":  (game or {}).get("opening_eco"),
            "move_number":  ev.get("move_number"),
            "user_color":   (game or {}).get("user_color"),
            "shared_by":    user_id,
            "source_game_id": gid,
            "source":       "skill_evidence",
            "description":  prompt,
            "cp_loss":      cp_loss,
            "attempts":     0,
            "solves":       0,
            "solve_rate":   0.0,
            "rating":       int(user_rating),
            "ratings":      [],
            "avg_rating":   0.0,
            "created_at":   datetime.now(timezone.utc),
            "approved":     True,
            "featured":     False,
        }
        await db.community_puzzles.insert_one(puzzle)
        created += 1

    return {"created": created, "skipped_dupe": skipped_dupe,
            "evidence_seen": len(evidence)}


async def get_skill_puzzles(
    db: AsyncIOMotorDatabase,
    user_id: str,
    skill_id: str,
    limit: int = 20,
) -> Dict:
    """Fetch drillable puzzles for a skill.

    Order:
      1. The user's OWN missed positions (most impactful — they
         recognise the position).
      2. Community positions other users have missed on the same skill.

    Excludes already-solved (any `correct: True` puzzle_attempt by
    this user on the same puzzle_id).

    Mirrors the shape of get_pattern_training_puzzles so the existing
    frontend puzzle component can render this with no changes.
    """
    # Already-solved puzzle ids for this user.
    solved_ids = set()
    async for a in db.puzzle_attempts.find(
        {"user_id": user_id, "correct": True},
        {"_id": 0, "puzzle_id": 1}
    ):
        if a.get("puzzle_id"):
            solved_ids.add(str(a["puzzle_id"]))

    def _shape(p):
        pid = str(p.get("_id"))
        return {
            "puzzle_id": pid,
            "fen": p.get("fen"),
            "best_move_san": p.get("best_move_san") or "",
            "best_move_uci": p.get("best_move_uci"),
            "skill_id": p.get("skill_id"),
            "grading_strategy": p.get("grading_strategy", "san_match"),
            "description": p.get("description", ""),
            "opening_name": p.get("opening_name"),
            "difficulty": p.get("difficulty", "intermediate"),
            "move_number": p.get("move_number"),
            "user_color": p.get("user_color"),
            "source_game_id": p.get("source_game_id"),
            "is_own": p.get("shared_by") == user_id,
        }

    own = []
    async for p in db.community_puzzles.find(
        {"skill_id": skill_id, "shared_by": user_id}
    ).sort("created_at", -1).limit(limit * 2):
        if str(p.get("_id")) in solved_ids:
            continue
        own.append(_shape(p))
        if len(own) >= limit:
            break

    remaining = max(0, limit - len(own))
    community = []
    if remaining > 0:
        async for p in db.community_puzzles.find(
            {"skill_id": skill_id, "shared_by": {"$ne": user_id}}
        ).sort("created_at", -1).limit(remaining * 3):
            if str(p.get("_id")) in solved_ids:
                continue
            community.append(_shape(p))
            if len(community) >= remaining:
                break

    return {
        "skill_id": skill_id,
        "own_puzzles": own,
        "community_puzzles": community,
        "total": len(own) + len(community),
    }


def grade_skill_puzzle_attempt(
    fen_before: str,
    move_uci: str,
    skill_id: str,
    user_color_str: Optional[str] = None,
    engine_best_san: Optional[str] = None,
) -> Dict:
    """Run the skill's detector on the user's move and grade.

    Returns {"correct": bool, "verdict": "applied"|"missed"|"none"|"engine_best",
             "detail": <human-readable line>}.

    Grading layers (cheapest → most expensive):
      1. Detector says "applied" → correct.
      2. Detector says "missed"  → wrong.
      3. Detector says "none"    → ambiguous; if the move matches the
                                   engine's best move from the source
                                   game (passed in by the endpoint),
                                   accept as "engine_best". Otherwise
                                   tell the user this move sidesteps
                                   the rule.

    The engine fallback is what lets users get credit for finding the
    OBJECTIVELY winning move (a rook check, a tactical capture) in
    positions where ROS isn't the only path — without it the drill
    would over-reject and feel unfair on messy endgames.
    """
    import chess
    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
    except Exception as e:
        return {"correct": False, "verdict": "none",
                "detail": f"invalid position or move: {e}"}

    if user_color_str:
        color = chess.WHITE if user_color_str.lower() == "white" else chess.BLACK
    else:
        color = board.turn

    if mv not in board.legal_moves:
        return {"correct": False, "verdict": "none",
                "detail": "Not a legal move in this position."}

    if skill_id == "endgame_rule_of_square":
        from services.concept_detectors.rule_of_the_square import (
            detect_rule_of_the_square_application,
        )
        verdict = detect_rule_of_the_square_application(board, mv, color)
    else:
        from services.concept_detectors.registry import DETECTORS
        det = DETECTORS.get(skill_id)
        if det is None:
            return {"correct": False, "verdict": "none",
                    "detail": f"no detector registered for {skill_id}"}
        verdict = det(board, mv, color)

    if verdict == "applied":
        return {"correct": True, "verdict": "applied",
                "detail": "Right idea — the king geometry works out."}
    if verdict == "missed":
        return {"correct": False, "verdict": "missed",
                "detail": "Doesn't catch the pawn (or wastes a tempo). "
                          "Walk the king into the catch zone."}

    # verdict == None — non-ROS move. Engine-best fallback.
    if engine_best_san:
        try:
            user_san = board.san(mv)
            if user_san == engine_best_san:
                return {"correct": True, "verdict": "engine_best",
                        "detail": f"Not the rule-of-the-square idea, but "
                                  f"{user_san} is the engine's top choice — "
                                  f"a valid solution to this position."}
        except Exception:
            pass

    return {"correct": False, "verdict": "none",
            "detail": "That move sidesteps the race — try a move that "
                      "directly tests the catch zone."}
