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

from services.puzzle_extraction_service import (
    verified_issue_type,
    verified_puzzle_admission_enforced,
)
from services.verified_puzzle_admission import (
    ADMISSION_VERSION,
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)
from services.verified_puzzle_builder import build_imported_game_verdict
from services.verified_puzzle_feedback import build_verified_puzzle_feedback

logger = logging.getLogger(__name__)


# Mapping from skill_id to a human caption shown in the drill card.
# Kept here (not on the skill_tree) because skill-tree captions are
# the lesson hooks; these are drill prompts — different audience.
#
# ENGINE 2 SKILLS (endgames + concepts)
SKILL_PROMPT = {
    # Endgame skills (detector-graded)
    "endgame_rule_of_square": (
        "Pawn race. Can the king catch it? Find the right move."
    ),
    "endgame_opposition": (
        "King and pawn endgame. Use opposition to force your pawn through."
    ),
    "endgame_lucena": (
        "Rook + pawn endgame. Build a bridge to win the rook endgame."
    ),
    "endgame_philidor": (
        "Rook + pawn endgame. Draw by defending correctly."
    ),
    "mate_kq_vs_k": (
        "Checkmate with King and Queen. Restrict and deliver mate."
    ),
    "mate_kr_vs_k": (
        "Checkmate with King and Rook. Build the box and checkmate."
    ),

    # Concept skills
    "defend_scholars_mate": (
        "Defend against Scholar's Mate. Protect f7 and counterattack."
    ),
    "defend_fried_liver": (
        "Defend against Fried Liver Attack. Solid defense wins."
    ),
    "concept_iqp": (
        "Isolated Queen's Pawn positions. Exploit or defend the IQP."
    ),
    "concept_prophylaxis": (
        "Prophylaxis. Stop your opponent's plan before executing yours."
    ),
    "concept_minority_attack": (
        "Queenside attack. Use the minority attack to create weaknesses."
    ),

    # Trap detection
    "trap_detection": (
        "Opening trap. Avoid falling for the trap line."
    ),

    # Opening play
    "opening_play": (
        "Opening repertoire. Stay in theory or play sound deviations."
    ),
    "opening_london_white": (
        "London System for White. Solid setup and attack plan."
    ),
    "opening_caro_kann_black": (
        "Caro-Kann Defense. Solid response to 1.e4."
    ),
    "opening_italian_white": (
        "Italian Game. Attack the weak f7 square."
    ),
    "opening_ruy_lopez": (
        "Ruy Lopez. Deep classical opening with many nuances."
    ),
    "opening_sicilian_black": (
        "Sicilian Defense. Counterattack against 1.e4."
    ),

    # Trap sets
    "trap_set_italian": (
        "Italian Game traps. Know the common tricks and avoid them."
    ),
    "trap_set_caro_kann": (
        "Caro-Kann traps. Watch for opening surprises."
    ),
    "trap_set_london": (
        "London System traps. Defend against opponent counterplay."
    ),
}

# ENGINE 1 PATTERNS (cognitive gaps — for backfill extraction)
# These are extracted from game_analyses.move_evaluations.cognitive_gap
COGNITIVE_GAP_PROMPTS = {
    "piece_safety": "Check for hanging pieces before every move.",
    "missed_tactic": "Look for captures, checks, and threats.",
    "tactical_oversight": "Calculate your opponent's best response.",
    "calculation_depth": "Think one move deeper than you normally do.",
    "king_safety": "Don't attack if your king is under threat.",
    "piece_activity": "Activate passive pieces for better positions.",
    "pawn_structure": "Consider pawn structure before exchanges.",
    "opening_knowledge": "Stick to theory in the opening phase.",
    "endgame_technique": "Activate your king and push passed pawns.",
    "time_pressure": "Slow down on critical moves.",
}


from services.endgame_detectors.rule_of_square_detector import is_rule_of_square_relevant

# Per-skill FEN validators. A position may only be tagged with a skill if it
# actually exhibits that skill's concept — this guards against generic gap
# buckets (e.g. issue_type="endgame_technique") being mislabeled as a specific
# skill. Skills without a validator are ungated (current behavior preserved).
_SKILL_FEN_VALIDATOR = {
    "endgame_rule_of_square": is_rule_of_square_relevant,
}


def _skill_puzzle_is_servable(puzzle: Dict, skill_id: str) -> bool:
    if puzzle.get("approved") is False:
        return False
    if not verified_puzzle_admission_enforced():
        return True
    verdict = puzzle.get("verified_admission") or {}
    return (
        stored_verdict_is_structurally_current(puzzle)
        and verdict.get("status") == AdmissionStatus.SPECIFIC.value
        and verdict.get("concept_id") == skill_id
        and puzzle.get("skill_id") == skill_id
    )


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
    skipped_wrong_concept = 0
    validator = _SKILL_FEN_VALIDATOR.get(skill_id)
    evidence = skill.get("evidence") or []

    for ev in evidence:
        outcome = ev.get("outcome")
        # Extract both "missed" (rule_of_square) and "wrong" (opposition)
        # as teaching material. "applied" = already correct, skip.
        if outcome not in ("missed", "wrong"):
            continue
        fen = ev.get("fen_before")
        if not fen:
            continue

        # Concept gate: only tag positions that ACTUALLY exhibit this skill.
        # Guards against generic endgame_technique evidence being mislabeled
        # as endgame_rule_of_square (a position must be, or reduce to, K+P vs K).
        if validator and not validator(fen):
            skipped_wrong_concept += 1
            continue

        # Idempotency on (skill_id, fen). Same position from two users
        # is fine — different shared_by, same puzzle position. But
        # the SAME user inserting twice is a dupe.
        existing = await db.community_puzzles.find_one(
            {"legacy_skill_id": skill_id, "fen": fen, "shared_by": user_id}
        )
        if existing:
            skipped_dupe += 1
            continue

        gid = ev.get("game_id")
        game = None
        if gid:
            game = await db.games.find_one(
                {"game_id": gid},
                {"_id": 0, "game_id": 1, "pgn": 1,
                 "opening_name": 1, "opening_eco": 1,
                 "user_color": 1, "result": 1, "date_played": 1}
            )

        # Try to pull the engine's best move for this position. Optional —
        # the puzzle is still valid without it (grading uses the detector),
        # but having the engine move on the doc lets the UI show "the
        # engine wanted X" as a follow-up tip after the user solves.
        engine_best_san = None
        engine_best_uci = None
        cp_loss = None
        source_move = None
        verdict = None
        if gid and ev.get("move_number") is not None:
            analysis = await db.game_analyses.find_one(
                {"game_id": gid},
                {"_id": 0, "stockfish_analysis.move_evaluations": 1}
            )
            move_evaluations = (
                ((analysis or {}).get("stockfish_analysis") or {})
                .get("move_evaluations") or []
            )
            for me in move_evaluations:
                if (me.get("move_number") == ev.get("move_number")
                        and (me.get("move") or me.get("move_san")) == ev.get("move_san")):
                    source_move = me
                    engine_best_san = me.get("best_move_san") or me.get("best_move")
                    engine_best_uci = me.get("best_move_uci")
                    cp_loss = me.get("cp_loss")
                    break

        if game and source_move:
            verdict = build_imported_game_verdict(
                game=game,
                move_evaluation=source_move,
                broad_category=None,
            )

        if verdict is None:
            # Skill evidence without its source analysis cannot prove an
            # answer. Preserve it as a measured skip instead of manufacturing
            # a detector-graded puzzle.
            skipped_wrong_concept += 1
            continue

        issue_type = verified_issue_type(verdict)
        specific_skill = (
            skill_id
            if verdict.status == AdmissionStatus.SPECIFIC
            and verdict.concept_id == skill_id
            else None
        )

        puzzle = {
            "fen": fen,
            # Best-move fields are still set so the existing
            # community_puzzles indexes don't choke. If the engine
            # didn't give us one, leave empty — grading_strategy
            # "detector" doesn't read them.
            "best_move_san": engine_best_san or "",
            "best_move_uci": engine_best_uci,
            "skill_id": specific_skill,
            "legacy_skill_id": skill_id,
            "grading_strategy": "verified_answer_set",
            # Tag with the corresponding cognitive gap so existing
            # filters (e.g. by issue_type) still surface these. ROS
            # missed pawn-race usually maps to endgame technique.
            "issue_type": issue_type,
            "legacy_issue_type": "endgame_technique",
            "theme": "endgame" if issue_type == "endgame_technique" else "calculation",
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
            "pv_after_best": source_move.get("pv_after_best") or [],
            "pv_after_played": source_move.get("pv_after_played") or [],
            "verified_admission": verdict.to_document(),
            "attempts":     0,
            "solves":       0,
            "solve_rate":   0.0,
            "rating":       int(user_rating),
            "ratings":      [],
            "avg_rating":   0.0,
            "created_at":   datetime.now(timezone.utc),
            "approved":     verdict.status != AdmissionStatus.QUARANTINE,
            "featured":     False,
        }
        await db.community_puzzles.insert_one(puzzle)
        created += 1

    return {"created": created, "skipped_dupe": skipped_dupe,
            "skipped_wrong_concept": skipped_wrong_concept,
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
        if not _skill_puzzle_is_servable(p, skill_id):
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
            if not _skill_puzzle_is_servable(p, skill_id):
                continue
            community.append(_shape(p))
            if len(community) >= remaining:
                break

    from services.verified_puzzle_runtime import public_puzzle_payload
    return {
        "skill_id": skill_id,
        "own_puzzles": [public_puzzle_payload(p) for p in own],
        "community_puzzles": [public_puzzle_payload(p) for p in community],
        "total": len(own) + len(community),
    }


def grade_skill_puzzle_attempt(
    fen_before: str,
    move_uci: str,
    skill_id: str,
    user_color_str: Optional[str] = None,
    engine_best_san: Optional[str] = None,
    verified_admission: Optional[Dict] = None,
) -> Dict:
    """Grade a skill attempt only from a current server-owned verdict.

    The compatibility arguments remain while callers migrate, but neither a
    live detector nor a client-provided engine answer may award mastery.
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

    admission = verified_admission or {}
    if admission.get("admission_version") == ADMISSION_VERSION:
        if not stored_verdict_is_structurally_current({
            "fen": fen_before,
            "verified_admission": admission,
        }):
            return {
                "correct": False,
                "verdict": "unavailable",
                "detail": "This position is still being checked and is not ready yet.",
            }
        if (
            admission.get("status") != AdmissionStatus.SPECIFIC.value
            or admission.get("concept_id") != skill_id
        ):
            return {
                "correct": False,
                "verdict": "unavailable",
                "detail": "This position does not yet match this lesson closely enough.",
            }
        accepted = set(admission.get("acceptable_moves_uci") or [])
        primary = next(iter(admission.get("acceptable_moves_uci") or ()), "")
        coaching = build_verified_puzzle_feedback(
            {
                "fen": fen_before,
                "best_move_uci": primary,
                "pattern_type": skill_id,
                "verified_admission": admission,
            },
            mv.uci(),
            correct=mv.uci() in accepted,
            primary_uci=primary,
        )
        if mv.uci() in accepted:
            return {
                "correct": True,
                "verdict": "verified_answer",
                "detail": coaching["feedback"],
                "coaching_feedback": coaching,
            }
        return {
            "correct": False,
            "verdict": "verified_miss",
            "detail": coaching["feedback"],
            "coaching_feedback": coaching,
        }

    return {
        "correct": False,
        "verdict": "unavailable",
        "detail": "This position is still being checked and cannot be graded yet.",
    }
