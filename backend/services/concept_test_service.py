"""Concept test — proof, not impressions.

docs/teaching_loop_scope.md

The coaching loop used to promote a concept to "understood" on a 3-game
clean streak alone. That cannot tell "he learned it" apart from "it stopped
coming up". This service adds the missing step: after a review teaches a
concept, the user can ask to be tested on it, and only passing moves him on.

    SHOWN --(opt in)--> TESTED --fail--> TESTED_FAILED (teach again)
                               \\--pass--> UNDERSTOOD --> MONITORING
                                              (real games) --> MASTERED

Two position sources, in precedence order:

  1. Lichess (`lichess_puzzles`, 4.11M) wherever the concept maps to a
     theme. These are CALIBRATED — each rating is earned against thousands
     of real solves — so selecting at the user's rating gives a known
     difficulty instead of a guessed one.
  2. `user_pattern_events` for the ~9 positional concepts Lichess has no
     theme for (`same_piece_better_square`, `knight_outpost`, ...). Real
     positions from real games, but UNCALIBRATED.

Because (2) is uncalibrated, a test served from it records its result but
does NOT promote — see `CONCEPT_TEST_PROMOTE_UNCALIBRATED`.
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chess

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────
STATE_SHOWN = "shown"
STATE_TESTED_FAILED = "tested_failed"
STATE_UNDERSTOOD = "understood"
STATE_MONITORING = "monitoring"
STATE_MASTERED = "mastered"

#: States from which the monitoring streak is allowed to advance toward
#: mastery. Anything earlier has not been proven and must not be promoted.
PROVEN_STATES = (STATE_UNDERSTOOD, STATE_MONITORING)

TEST_SIZE = 5

#: Pass mark, as a config value rather than a constant — there is no
#: difficulty distribution to lock it against yet (65 of 44,982 community
#: positions have ever been attempted). Real graded solve rate across all
#: existing attempts is 57.3%, so 5/5 would be punitive. Revisit against
#: the first real cohort. docs/teaching_loop_scope.md Q1.
DEFAULT_PASS_MARK = 3


def pass_mark() -> int:
    try:
        return max(1, min(TEST_SIZE, int(os.environ.get("CONCEPT_TEST_PASS_MARK", DEFAULT_PASS_MARK))))
    except (TypeError, ValueError):
        return DEFAULT_PASS_MARK


def promote_on_uncalibrated() -> bool:
    """Whether a test served from uncalibrated positions may promote.

    Default OFF. Until the first real cohort's score distribution is
    reviewed we do not know what a passing score means on these, so the
    result is recorded and the user is told he passed — but the state
    machine does not move him. Turning this on is a deliberate act.
    """
    return os.environ.get("CONCEPT_TEST_PROMOTE_UNCALIBRATED", "false").strip().lower() == "true"


#: cp_loss band for uncalibrated positions. Holds difficulty roughly
#: constant across concepts without any solve data: a mistake that cost
#: 800cp is far more obvious than one that cost 120cp. Measured p50 is
#: 205cp, and this band still leaves >= 5 positions for 21 of 23 concepts.
UNCALIBRATED_CP_MIN = 200
UNCALIBRATED_CP_MAX = 500

#: Opening-prefixed duplicates. They carry too few positions to test on
#: their own (2 and 4 in-band) and mean the same thing as their siblings.
CONCEPT_ALIASES = {
    "OP_KNIGHT_ON_RIM": "knight_on_rim",
    "OP_SAME_PIECE_TWICE": "same_piece_better_square",
}


def canonical_concept(concept_id: str) -> str:
    return CONCEPT_ALIASES.get(concept_id, concept_id)


def may_promote_to_mastered(
    state: Optional[str],
    streak_clean: int,
    streak_required: int,
    *,
    tests_passed: int = 0,
) -> bool:
    """The single place that decides whether a clean streak earns mastery.

    The rule this encodes, and the bug it closes: a clean streak is
    MONITORING evidence. It is not a route to "understood". Before
    2026-09-21 the tracker promoted on the streak alone, so a concept could
    reach mastered without the user demonstrating anything — it had merely
    stopped coming up. Proof comes first; the streak only confirms it holds.

    `tests_passed` is the load-bearing half, and it is checked separately
    from `state` on purpose. The 2026-09-21 backfill put 1,078 pre-existing
    rows into `monitoring` so their streak history was not thrown away —
    but `monitoring` is a proven state, so on a state check alone 532 of
    them would have promoted straight to mastered on their next clean game,
    having never taken a test. That is precisely the bug this service
    exists to close, so the proof is required explicitly rather than
    inferred from where a row happens to sit.
    """
    if state not in PROVEN_STATES:
        return False
    if state == STATE_MASTERED:
        return False
    if int(tests_passed or 0) < 1:
        return False
    return int(streak_clean or 0) >= int(streak_required or 0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Position sourcing ─────────────────────────────────────────────────────

async def _lichess_positions(
    db, concept_id: str, rating: int, limit: int, exclude_ids: set,
) -> List[Dict[str, Any]]:
    """Calibrated positions, selected at the user's rating.

    IMPORTANT: a Lichess row's stored `fen` is the position BEFORE the
    opponent's move, and `moves[0]` IS that opponent move. The position the
    solver actually sees is the one AFTER it. Serving the stored fen as-is
    shows the wrong position with the user on the wrong colour, and fails
    silently because that position is still legal. Verified 2026-09-21.
    """
    from services.coaching_puzzle_service import WEAKNESS_TO_PUZZLE_THEMES

    themes = WEAKNESS_TO_PUZZLE_THEMES.get(concept_id)
    if not themes:
        return []

    lo, hi = max(400, rating - 200), rating + 200
    query = {"themes": {"$in": themes}, "rating": {"$gte": lo, "$lte": hi}}
    if exclude_ids:
        query["puzzle_id"] = {"$nin": list(exclude_ids)[:500]}

    out: List[Dict[str, Any]] = []
    cursor = db.lichess_puzzles.find(
        query,
        {"_id": 0, "puzzle_id": 1, "fen": 1, "moves": 1, "rating": 1,
         "themes": 1, "popularity": 1, "game_url": 1},
    ).sort("popularity", -1).limit(limit * 6)

    async for p in cursor:
        moves = p.get("moves") or []
        if len(moves) < 2 or not p.get("fen"):
            continue
        try:
            board = chess.Board(p["fen"])
            setup = chess.Move.from_uci(moves[0])
            if setup not in board.legal_moves:
                continue
            board.push(setup)                       # <- the position the user sees
            answer = chess.Move.from_uci(moves[1])
            if answer not in board.legal_moves:
                continue
            answer_san = board.san(answer)
        except (ValueError, AssertionError, KeyError):
            continue

        out.append({
            "position_id": f"lichess_{p['puzzle_id']}",
            "source": "lichess",
            "calibrated": True,
            "fen": board.fen(),
            "solution_uci": moves[1],
            "solution_san": answer_san,
            "side_to_move": "white" if board.turn else "black",
            "rating": p.get("rating"),
            "themes": p.get("themes") or [],
            "game_url": p.get("game_url"),
        })
        if len(out) >= limit:
            break
    return out


async def _own_game_positions(
    db, user_id: str, concept_id: str, limit: int, exclude_ids: set,
) -> List[Dict[str, Any]]:
    """Uncalibrated positions from OTHER players' games.

    Other players', deliberately: the user has already been shown the answer
    to his own mistakes in the review, so testing him on those measures
    memory rather than understanding. His own positions are reserved for the
    re-teach when he fails.
    """
    query = {
        "outcome": "miss",
        "user_id": {"$ne": user_id},
        "fen_before": {"$nin": [None, ""]},
        "best_move_san": {"$nin": [None, ""]},
        "cp_loss": {"$gte": UNCALIBRATED_CP_MIN, "$lt": UNCALIBRATED_CP_MAX},
        "$or": [{"concept_id": concept_id}, {"pattern_id": concept_id}],
    }

    seen_fens: set = set()
    out: List[Dict[str, Any]] = []
    cursor = db.user_pattern_events.find(
        query,
        {"_id": 0, "fen_before": 1, "best_move_san": 1, "cp_loss": 1,
         "game_id": 1, "move_number": 1},
    ).limit(limit * 40)

    async for ev in cursor:
        fen = ev.get("fen_before")
        pid = f"upe_{ev.get('game_id')}_{ev.get('move_number')}"
        if fen in seen_fens or pid in exclude_ids:
            continue
        try:
            board = chess.Board(fen)
            mv = board.parse_san(ev["best_move_san"])
        except (ValueError, AssertionError, KeyError):
            continue
        seen_fens.add(fen)
        out.append({
            "position_id": pid,
            "source": "user_games",
            "calibrated": False,
            "fen": fen,
            "solution_uci": mv.uci(),
            "solution_san": ev["best_move_san"],
            "side_to_move": "white" if board.turn else "black",
            "rating": None,
            "cp_loss": ev.get("cp_loss"),
        })
        if len(out) >= limit:
            break
    return out


async def _already_tested_ids(db, user_id: str, concept_id: str) -> set:
    ids: set = set()
    cursor = db.concept_test_results.find(
        {"user_id": user_id, "concept_id": concept_id}, {"_id": 0, "positions": 1},
    )
    async for row in cursor:
        for pos in row.get("positions") or []:
            pid = pos.get("position_id") if isinstance(pos, dict) else pos
            if pid:
                ids.add(str(pid).replace("lichess_", ""))
                ids.add(str(pid))
    return ids


async def build_concept_test(
    db, user_id: str, concept_id: str, rating: int = 1200,
) -> Dict[str, Any]:
    """Assemble a 5-position test. Lichess first, own-games as fallback."""
    concept_id = canonical_concept(concept_id)
    exclude = await _already_tested_ids(db, user_id, concept_id)

    positions = await _lichess_positions(db, concept_id, rating, TEST_SIZE, exclude)
    if len(positions) < TEST_SIZE:
        fill = await _own_game_positions(
            db, user_id, concept_id, TEST_SIZE - len(positions), exclude,
        )
        positions.extend(fill)

    if not positions:
        return {"available": False, "concept_id": concept_id, "positions": []}

    random.shuffle(positions)
    calibrated = all(p["calibrated"] for p in positions)

    test_id = f"ct_{uuid.uuid4().hex[:12]}"
    await db.concept_tests.insert_one({
        "test_id": test_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "calibrated": calibrated,
        "created_at": _now(),
        # the solutions live server-side only; they are stripped from the
        # payload below so the answer never ships to the browser
        "positions": positions,
    })

    return {
        "available": True,
        "test_id": test_id,
        "concept_id": concept_id,
        "calibrated": calibrated,
        "pass_mark": pass_mark(),
        "positions": [
            {k: v for k, v in p.items() if k not in ("solution_uci", "solution_san")}
            for p in positions
        ],
    }


# ── Grading and state transition ──────────────────────────────────────────

async def grade_concept_test(
    db, user_id: str, test_id: str, answers: List[str],
) -> Dict[str, Any]:
    """Grade a submitted test and move the concept's state.

    `answers` is a list of UCI strings, positionally aligned with the
    positions that were served.
    """
    test = await db.concept_tests.find_one({"test_id": test_id, "user_id": user_id})
    if not test:
        return {"error": "test_not_found"}
    if test.get("graded_at"):
        return {"error": "already_graded"}

    positions = test.get("positions") or []
    concept_id = test.get("concept_id")
    results = []
    score = 0

    for idx, pos in enumerate(positions):
        given = (answers[idx] if idx < len(answers) else "") or ""
        correct = given.strip().lower() == (pos.get("solution_uci") or "").lower()
        if correct:
            score += 1
        results.append({
            "position_id": pos.get("position_id"),
            "fen": pos.get("fen"),
            "answer_uci": given,
            "solution_uci": pos.get("solution_uci"),
            "solution_san": pos.get("solution_san"),
            "correct": correct,
            "source": pos.get("source"),
        })

    mark = pass_mark()
    passed = score >= mark
    calibrated = bool(test.get("calibrated"))
    # An uncalibrated pass is real to the user but does not move the state
    # machine until we know what a passing score means on those positions.
    promotes = passed and (calibrated or promote_on_uncalibrated())

    now = _now()
    await db.concept_tests.update_one(
        {"test_id": test_id}, {"$set": {"graded_at": now, "score": score, "passed": passed}},
    )
    await db.concept_test_results.insert_one({
        "test_id": test_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "score": score,
        "pass_mark": mark,
        "passed": passed,
        "calibrated": calibrated,
        "promoted": promotes,
        "positions": results,
        "tested_at": now,
    })

    new_state = await _apply_state_transition(
        db, user_id, concept_id, passed=passed, promotes=promotes,
    )

    first_wrong = next((r for r in results if not r["correct"]), None)
    return {
        "test_id": test_id,
        "concept_id": concept_id,
        "score": score,
        "out_of": len(positions),
        "pass_mark": mark,
        "passed": passed,
        "calibrated": calibrated,
        "state": new_state,
        "results": results,
        "review_position": first_wrong,
    }


async def _apply_state_transition(
    db, user_id: str, concept_id: str, *, passed: bool, promotes: bool,
) -> str:
    """Move the concept's state, and keep `acknowledged` in sync.

    `acknowledged` is kept written because four existing readers still
    consult it (v5_learning_tracker, game_decryption_v5_service,
    routes/coach). `state` is the authority.
    """
    now = _now()
    inc: Dict[str, int] = {"tests_taken": 1}
    if promotes:
        new_state = STATE_MONITORING
        update = {
            "state": new_state,
            "acknowledged": True,
            "understood_at": now,
            "streak_clean": 0,
            "updated_at": now,
        }
        inc["tests_passed"] = 1
    elif passed:
        # Passed, but on uncalibrated positions — recorded, not promoted.
        new_state = STATE_SHOWN
        update = {"state": new_state, "last_test_passed_unpromoted_at": now, "updated_at": now}
    else:
        new_state = STATE_TESTED_FAILED
        update = {
            "state": new_state,
            "acknowledged": False,
            "last_test_failed_at": now,
            "updated_at": now,
        }

    await db.user_concept_understanding.update_one(
        {"user_id": user_id, "concept_id": concept_id},
        {"$set": update, "$inc": inc,
         "$setOnInsert": {"user_id": user_id, "concept_id": concept_id,
                          "created_at": now, "shown_count": 0}},
        upsert=True,
    )
    return new_state


# ── Offer / decline ───────────────────────────────────────────────────────

async def record_test_declined(db, user_id: str, concept_id: str) -> None:
    """'Not now' is a first-class outcome, not a failure.

    Re-offer once after the next game that surfaces the concept, then stop
    asking. It must never fall back to promoting without proof — that is the
    bug this whole service exists to close.
    """
    await db.user_concept_understanding.update_one(
        {"user_id": user_id, "concept_id": canonical_concept(concept_id)},
        {"$set": {"updated_at": _now()}, "$inc": {"tests_declined": 1}},
    )


async def pick_concept_for_game(
    db, user_id: str, game_id: str,
) -> Optional[Dict[str, Any]]:
    """Which concept did THIS game teach, and may we test it?

    Not named testable_* : pytest collects any module-level name starting
    with "test", so importing it into a test file made pytest try to run the
    service function as a test case and fail on a missing "db" fixture.

    The review card cannot answer this. `concept_id` on a stored card has
    been hardcoded to None since the 2026-05-11 "legacy prose fields retired"
    migration -- deliberately, because the V5 caption pipeline replaced that
    prose. ConceptTestCard was then built in September reading those retired
    fields, so the proof step has never once appeared: measured 2026-09-26,
    concept_id is null on all 16,292 stored cards.

    Reviving the retired fields would be the wrong fix twice over: it
    resurrects a surface that was removed on purpose, and it still would not
    speak the vocabulary the puzzle pools are keyed on.

    user_pattern_events already holds the answer. Every detector miss row
    carries user_id, game_id, concept_id and cp_loss, in exactly the
    vocabulary build_concept_test() draws positions for. Measured on games
    analysed in 2026-09: 51.2% carry at least one concept, and 1,596 of 1,596
    games that carry one carry a testable one.

    The biggest mistake wins. If a game taught several things, the one that
    cost the most is the one worth proving he understood.
    """
    if not (user_id and game_id):
        return None

    cursor = db.user_pattern_events.find(
        {
            "outcome": "miss",
            "user_id": user_id,
            "game_id": game_id,
            "concept_id": {"$nin": [None, ""]},
        },
        {"_id": 0, "concept_id": 1, "cp_loss": 1, "move_number": 1},
    ).sort("cp_loss", -1)

    seen: set = set()
    async for ev in cursor:
        concept_id = str(ev.get("concept_id") or "").strip()
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        # Ask the same gate the offer endpoint asks, so a concept he has
        # already proven or declined twice is skipped rather than offered
        # and then refused one call later.
        if not await should_offer_test(db, user_id, concept_id):
            continue
        return {
            "concept_id": concept_id,
            "cp_loss": int(ev.get("cp_loss") or 0),
            "move_number": ev.get("move_number"),
        }
    return None


async def should_offer_test(db, user_id: str, concept_id: str) -> bool:
    """Offer after a review taught the concept, unless already proven, or
    declined twice."""
    row = await db.user_concept_understanding.find_one(
        {"user_id": user_id, "concept_id": canonical_concept(concept_id)},
        {"_id": 0, "state": 1, "tests_declined": 1},
    )
    if not row:
        return True
    if row.get("state") in PROVEN_STATES or row.get("state") == STATE_MASTERED:
        return False
    return int(row.get("tests_declined") or 0) < 2
