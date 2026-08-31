"""
Diagnostic onboarding service — 20-puzzle warm-up that produces a real
diagnosis when the user has no analyzed games OR while their imported
games are still in the Stockfish queue.

Spec: memory/project_diagnostic_onboarding_20_puzzles.md
  - 20 puzzles, stratified across community_puzzles issue_types
  - No time pressure, no gamification
  - Output: rating estimate range + per-category strengths/growth-areas
  - After 10+ real-game analyses land, real-game data supersedes this.

Public API:
    select_diagnostic_puzzles(db, user_id) -> List[Dict]
    score_diagnostic(attempts) -> Dict
    coerce_diagnosis_voice(diagnosis) -> Dict   (voice hygiene pass)
"""

from __future__ import annotations

import logging
import random
import hashlib
import json
from typing import Any, Dict, List, Optional

from services.verified_puzzle_admission import (
    AdmissionStatus,
    stored_verdict_is_structurally_current,
)

logger = logging.getLogger(__name__)

# Issue types worth probing. Roughly ordered from "everyone has this gap"
# to "more advanced." The selector tries to cover all 7; if an issue type
# has zero approved puzzles we silently skip it.
DIAGNOSTIC_ISSUE_TYPES: List[str] = [
    "piece_safety",
    "tactical_oversight",
    "missed_tactic",
    "calculation_depth",
    "king_safety",
    "piece_activity",
    "opening_knowledge",
]

# Friendly labels for diagnosis output. Keep concrete, no jargon.
ISSUE_TYPE_LABEL: Dict[str, str] = {
    "piece_safety": "Spotting hanging pieces",
    "tactical_oversight": "Seeing tactics",
    "missed_tactic": "Forks, pins, and skewers",
    "calculation_depth": "Calculating a few moves ahead",
    "king_safety": "Keeping your king safe",
    "piece_activity": "Activating pieces",
    "opening_knowledge": "Opening principles",
}

TARGET_PUZZLES = 20
MIN_PER_CATEGORY = 1   # If a category exists at all, include at least one
MAX_PER_CATEGORY = 4   # Avoid drowning one category


async def _fetch_approved_pool(
    db, user_id: str
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Return {issue_type: {difficulty: [puzzle_doc, ...]}} for approved
    community puzzles the user hasn't already attempted. Two-level
    nesting so the selector can pull across difficulty buckets within
    a category — that's how the diagnostic probes depth, not just
    pattern recognition.
    """
    # Exclude puzzles the user has previously attempted (e.g. from
    # /training/pattern flows) — keep the diagnostic fresh.
    attempted_ids: set = set()
    async for a in db.puzzle_attempts.find(
        {"user_id": user_id}, {"_id": 0, "puzzle_id": 1}
    ):
        pid = a.get("puzzle_id")
        if pid:
            attempted_ids.add(pid)

    by_issue: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        it: {"beginner": [], "intermediate": [], "advanced": []}
        for it in DIAGNOSTIC_ISSUE_TYPES
    }

    cursor = db.community_puzzles.find(
        {"approved": True, "issue_type": {"$in": DIAGNOSTIC_ISSUE_TYPES}},
        {
            "_id": 1,
            "fen": 1,
            "best_move_san": 1,
            "best_move_uci": 1,
            "issue_type": 1,
            "difficulty": 1,
            "user_color": 1,
            "opening_name": 1,
            "move_number": 1,
            "cp_loss": 1,
            "verified_admission": 1,
        },
    )
    async for p in cursor:
        pid = str(p.get("_id"))
        if pid in attempted_ids:
            continue
        if (
            not p.get("fen")
            or not p.get("best_move_san")
            or not stored_verdict_is_structurally_current(p)
            or (p.get("verified_admission") or {}).get("status")
            == AdmissionStatus.QUARANTINE.value
        ):
            continue
        p["puzzle_id"] = pid
        p.pop("_id", None)
        it = p.get("issue_type")
        diff = p.get("difficulty")
        if it in by_issue and diff in by_issue[it]:
            by_issue[it][diff].append(p)

    # Within each category+difficulty bucket, larger cp_loss = louder
    # mistake = easier to spot. Order by descending cp_loss so the
    # selector picks the clearer instances first.
    for cat in by_issue.values():
        for diff_list in cat.values():
            diff_list.sort(key=lambda d: -(d.get("cp_loss") or 0))
    return by_issue


async def select_diagnostic_puzzles(db, user_id: str) -> List[Dict[str, Any]]:
    """Pick up to 20 stratified puzzles for the diagnostic. Each category
    contributes a SPREAD across difficulty buckets — that's what makes
    it a depth probe rather than a pattern-recognition pop-quiz.

    Stable order (caller persists the list and walks it). Returns []
    if the pool is too thin for even a useful diagnostic.
    """
    pool = await _fetch_approved_pool(db, user_id)

    # Drop categories that have nothing at any difficulty.
    non_empty = {
        it: cat for it, cat in pool.items()
        if any(cat[d] for d in ("beginner", "intermediate", "advanced"))
    }
    if not non_empty:
        return []

    diff_order = ("beginner", "intermediate", "advanced")
    n_cats = len(non_empty)
    base_per_cat = max(MIN_PER_CATEGORY, TARGET_PUZZLES // n_cats)
    base_per_cat = min(base_per_cat, MAX_PER_CATEGORY)

    # Phase 1: for each category, take one of each difficulty until we
    # hit base_per_cat. This is the depth-probe step. If a difficulty
    # bucket is empty, fall through to whichever has stock.
    picked: List[Dict[str, Any]] = []
    leftovers: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        it: {d: list(lst) for d, lst in cat.items()} for it, cat in non_empty.items()
    }

    for it, cat in non_empty.items():
        taken = 0
        # First pass: try one of each difficulty (depth probe)
        for d in diff_order:
            if taken >= base_per_cat:
                break
            if leftovers[it][d]:
                picked.append(leftovers[it][d].pop(0))
                taken += 1
        # Second pass: top up from any difficulty if base_per_cat > 3
        while taken < base_per_cat:
            took = False
            for d in diff_order:
                if leftovers[it][d]:
                    picked.append(leftovers[it][d].pop(0))
                    taken += 1
                    took = True
                    break
            if not took:
                break

    # Phase 2: round-robin top-up to TARGET_PUZZLES across categories.
    cat_cycle = [it for it in non_empty.keys()
                 if any(leftovers[it][d] for d in diff_order)]
    while len(picked) < TARGET_PUZZLES and cat_cycle:
        it = cat_cycle[0]
        took = False
        for d in diff_order:
            if leftovers[it][d]:
                picked.append(leftovers[it][d].pop(0))
                took = True
                break
        if any(leftovers[it][d] for d in diff_order):
            cat_cycle.append(cat_cycle.pop(0))
        else:
            cat_cycle.pop(0)
        if not took:
            continue

    # Phase 3: interleave so the user doesn't see 3 consecutive same-
    # category puzzles. Round-robin across categories.
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for p in picked:
        by_cat.setdefault(p["issue_type"], []).append(p)
    ordered: List[Dict[str, Any]] = []
    cats = list(by_cat.keys())
    while any(by_cat[c] for c in cats):
        for c in cats:
            if by_cat[c]:
                ordered.append(by_cat[c].pop(0))

    return ordered[:TARGET_PUZZLES]


def _rating_estimate(correct_total: int, total: int, weighted_score: float) -> Dict[str, int]:
    """Map raw correct count + difficulty-weighted score to a rating range.

    Weighted score: each correct puzzle contributes 1.0 (beginner) /
    1.3 (intermediate) / 1.6 (advanced). Max score with 20 puzzles
    depends on the difficulty mix; we normalize against the actual
    available max from the attempt set.
    """
    if total <= 0:
        return {"low": 600, "high": 900}

    # Bin by accuracy + weighted score
    pct = correct_total / total
    if pct < 0.20:
        return {"low": 600, "high": 800}
    if pct < 0.35:
        return {"low": 700, "high": 950}
    if pct < 0.50:
        return {"low": 850, "high": 1100}
    if pct < 0.65:
        return {"low": 1000, "high": 1250}
    if pct < 0.80:
        return {"low": 1200, "high": 1450}
    if pct < 0.90:
        return {"low": 1400, "high": 1650}
    return {"low": 1600, "high": 1900}


def _category_label(correct: int, total: int) -> str:
    """Map per-category correct/total to a strength label. No "X%"
    gamification per [[no-gamification]] — descriptive, not percentage."""
    if total == 0:
        return "Not tested"
    pct = correct / total
    if pct >= 0.80:
        return "Strong"
    if pct >= 0.50:
        return "Mixed"
    return "Needs work"


def score_diagnostic(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score a completed diagnostic. attempts is the list stored on the
    session; each entry has at minimum: issue_type, difficulty, is_correct.
    Returns the diagnosis dict that goes onto the session + dashboard.
    """
    if not attempts:
        return {
            "rating_estimate": {"low": 600, "high": 900},
            "per_category": {},
            "strengths": [],
            "growth_areas": [],
            "summary_line": "Not enough data yet. Play a few games and we'll build a real picture.",
            "total_correct": 0,
            "total_attempted": 0,
        }

    diff_weight = {"beginner": 1.0, "intermediate": 1.3, "advanced": 1.6}
    correct_total = sum(1 for a in attempts if a.get("is_correct"))
    weighted = sum(
        diff_weight.get(a.get("difficulty", "intermediate"), 1.0)
        for a in attempts if a.get("is_correct")
    )

    # Per-category tally
    per_cat: Dict[str, Dict[str, Any]] = {}
    for a in attempts:
        it = a.get("issue_type")
        if not it:
            continue
        cat = per_cat.setdefault(it, {"correct": 0, "total": 0})
        cat["total"] += 1
        if a.get("is_correct"):
            cat["correct"] += 1

    for it, cat in per_cat.items():
        cat["label"] = _category_label(cat["correct"], cat["total"])
        cat["display_name"] = ISSUE_TYPE_LABEL.get(it, it)

    strengths = [
        per_cat[it]["display_name"]
        for it in per_cat
        if per_cat[it]["label"] == "Strong"
    ]
    growth_areas = [
        per_cat[it]["display_name"]
        for it in per_cat
        if per_cat[it]["label"] == "Needs work"
    ]

    rating_band = _rating_estimate(correct_total, len(attempts), weighted)

    # Voice-pass summary: concrete, no gamification, no "score!"
    # Four shapes depending on whether the user showed clear strengths
    # and/or clear growth areas.
    if strengths and growth_areas:
        summary = (
            f"Strong signal in {strengths[0].lower()}. "
            f"The clearest place to grow: {growth_areas[0].lower()}."
        )
    elif strengths and not growth_areas:
        summary = (
            f"Strong signal in {strengths[0].lower()}. "
            f"A few real games will sharpen the rest of the picture."
        )
    elif growth_areas and not strengths:
        summary = (
            f"Mixed results across the board. "
            f"The clearest place to grow: {growth_areas[0].lower()}."
        )
    else:
        summary = "Mixed across the board. A few real games will sharpen this picture."

    return {
        "rating_estimate": rating_band,
        "per_category": per_cat,
        "strengths": strengths,
        "growth_areas": growth_areas,
        "summary_line": summary,
        "total_correct": correct_total,
        "total_attempted": len(attempts),
    }


# ── Wiring #1: diagnostic result → the SAME weakness pipeline game analysis uses ──
# A cold-start user has no analyzed games, so the diagnostic is their only weakness
# signal. We map its issue_type (already cognitive_gap-shaped) onto the weakness
# taxonomy that player_profiles.top_weaknesses (drives /home) and
# coach_memory.learning.current_focus (routes /training/prescribed/current) use,
# then write through the existing chokepoint (update_user_weaknesses). So a
# cold user's training/home personalize off the diagnostic exactly like a game-user.

# diagnostic issue_type -> (category, subcategory) for player_profiles.top_weaknesses
_ISSUE_TO_WEAKNESS: Dict[str, tuple] = {
    "piece_safety":       ("tactical", "one_move_blunders"),
    "tactical_oversight": ("tactical", "one_move_blunders"),
    "missed_tactic":      ("tactical", "fork_misses"),
    "calculation_depth":  ("tactical", "one_move_blunders"),
    "king_safety":        ("king_safety", "exposing_own_king"),
    "piece_activity":     ("strategic", "poor_piece_activity"),
    "opening_knowledge":  ("opening_principles", "neglecting_development"),
}

# diagnostic issue_type -> coach_memory focus key (routes prescribed training).
# Types with no clean focus key are omitted; top_weaknesses still drives /home.
_ISSUE_TO_FOCUS: Dict[str, str] = {
    "piece_safety":       "hanging_piece",
    "missed_tactic":      "missed_fork",
    "tactical_oversight": "tactical_error",
    "calculation_depth":  "tactical_error",
    "king_safety":        "king_safety",
}


def _worst_issue_type(diagnosis: Dict[str, Any]) -> Optional[str]:
    """The issue_type the user did WORST on (lowest correct rate; >=2 attempts
    preferred). Falls back to any 'Needs work' category, else None."""
    per_cat = diagnosis.get("per_category") or {}
    ranked = []
    for it, c in per_cat.items():
        total = c.get("total", 0)
        if total < 2:
            continue
        rate = c.get("correct", 0) / total
        ranked.append((rate, -total, it))
    if ranked:
        ranked.sort()
        return ranked[0][2]
    for it, c in per_cat.items():
        if c.get("label") == "Needs work":
            return it
    return None


async def apply_diagnosis_to_training(db, user_id: str, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score the (possibly partial) attempts and feed the worst category into the
    same weakness pipeline game analysis uses. Safe to call repeatedly (a longer
    run just refines the focus). Returns the diagnosis dict.
    """
    from player_profile_service import update_weakness_tracking, get_or_create_profile

    diagnosis = score_diagnostic(attempts)
    worst = _worst_issue_type(diagnosis)
    if not worst:
        return diagnosis  # not enough signal yet — nothing to write

    # Cold users have no player_profiles doc, and update_weakness_tracking no-ops
    # without one — so ensure a full default profile exists first.
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1})
    await get_or_create_profile(db, user_id, (u or {}).get("name") or "Player")

    cat, subcat = _ISSUE_TO_WEAKNESS.get(worst, ("tactical", "one_move_blunders"))
    try:
        await update_weakness_tracking(db, user_id, [{"category": cat, "subcategory": subcat}])
    except Exception as e:  # never let a wiring hiccup break the diagnostic
        logger.warning(f"diagnostic->weakness write failed for {user_id}: {e}")

    focus = _ISSUE_TO_FOCUS.get(worst)
    if focus:
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {"$set": {"learning.current_focus": focus, "learning.focus_source": "diagnostic"}},
            upsert=True,
        )

    return diagnosis


def diagnostic_supersedes_after(num_analyzed_games: int) -> bool:
    """When enough real games are analyzed, the diagnostic stops being
    the primary signal. Spec: 10 games."""
    return num_analyzed_games >= 10


# ═════════════════════════════════════════════════════════════════════
# Diagnostic V2 — consequence-graded, staircase-tiered, concept-gated.
#
# Puzzles come from the curated `diagnostic_pool` collection
# (built offline by scripts/build_diagnostic_pool.py: 10 concepts x
# 3 rating tiers, each engine-verified single-idea with precomputed
# multipv baselines). Grading is by CONSEQUENCE, not exact-match:
# the user's move is evaluated and classified UNDERSTOOD / PARTIAL /
# MISSING against the precomputed solution eval.
# ═════════════════════════════════════════════════════════════════════

import chess as _chess

# Priority order = fundamentals first. Doubles as the headline-gap
# tie-break: the earliest concept in this list with the worst level wins.
CONCEPT_PRIORITY: List[str] = [
    "threat_response",
    "piece_safety",
    "mate_patterns",
    "fork",
    "pin",
    "skewer",
    "calculation",
    "opening",
    "endgame",
    "winning_technique",
]

CONCEPT_LABEL: Dict[str, str] = {
    "threat_response": "Answering threats",
    "piece_safety": "Keeping pieces safe",
    "mate_patterns": "Spotting checkmates",
    "fork": "Forks",
    "pin": "Pins",
    "skewer": "Skewers",
    "calculation": "Calculating a few moves ahead",
    "opening": "Opening principles",
    "endgame": "Endgame technique",
    "winning_technique": "Converting a winning position",
}

TIER_RATING: Dict[str, int] = {"low": 800, "mid": 1200, "high": 1600}
_TIER_UP = {"low": "mid", "mid": "high", "high": "high"}
_TIER_DOWN = {"low": "low", "mid": "low", "high": "mid"}

VERDICT_SYMBOL = {"UNDERSTOOD": "✓", "PARTIAL": "≈", "MISSING": "✗"}

# Mate-score convention shared with stockfish_service / the pool script.
_MATE_CP_BASE = 10000

_PIECE_NAME = {
    _chess.PAWN: "pawn", _chess.KNIGHT: "knight", _chess.BISHOP: "bishop",
    _chess.ROOK: "rook", _chess.QUEEN: "queen", _chess.KING: "king",
}


def _grading_thresholds(puzzle_rating: int) -> tuple:
    """(partial_threshold, missing_threshold) in cp — same bands as
    rating_resolver.MOVE_CLASSIFY_THRESHOLDS (inaccuracy/mistake edges)."""
    r = puzzle_rating or 1200
    if r < 1000:
        return 100, 300
    if r < 1400:
        return 75, 200
    if r < 1800:
        return 50, 150
    return 30, 100


def _eval_sign(cp: float) -> int:
    """Coarse winning/equal/losing bucket, solver POV."""
    if cp > 50:
        return 1
    if cp < -50:
        return -1
    return 0


DIAGNOSTIC_GRADE_VERSION = "diagnostic_frozen_grades.v1"


def classify_diagnostic_eval(
    solution_eval: int,
    eval_after: int,
    puzzle_rating: Optional[int],
) -> tuple[str, int]:
    """Classify an offline engine comparison; safe to share with the builder."""
    cp_loss = int(solution_eval) - int(eval_after)
    partial_th, missing_th = _grading_thresholds(puzzle_rating)
    sign_unchanged = _eval_sign(eval_after) >= _eval_sign(solution_eval)
    if eval_after >= solution_eval - 50 or (
        sign_unchanged and cp_loss < partial_th
    ):
        verdict = "UNDERSTOOD"
    elif sign_unchanged and cp_loss < missing_th:
        verdict = "PARTIAL"
    else:
        verdict = "MISSING"
    return verdict, max(0, cp_loss)


def diagnostic_grade_fingerprint(puzzle: Dict[str, Any]) -> str:
    """Bind frozen grades to the exact position, line, rating, and move map."""
    payload = {
        "grade_version": puzzle.get("grade_version"),
        "puzzle_id": puzzle.get("puzzle_id"),
        "fen": puzzle.get("fen"),
        "moves": puzzle.get("moves") or [],
        "puzzle_rating": puzzle.get("puzzle_rating"),
        "step_grades": puzzle.get("step_grades") or [],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def frozen_diagnostic_grades_are_current(puzzle: Dict[str, Any]) -> bool:
    return bool(
        puzzle.get("grade_version") == DIAGNOSTIC_GRADE_VERSION
        and puzzle.get("grade_fingerprint")
        and puzzle.get("grade_fingerprint") == diagnostic_grade_fingerprint(puzzle)
        and puzzle.get("step_grades")
    )


class UnverifiedDiagnosticMove(ValueError):
    """The pool has no content-bound offline truth for this legal move."""


class DiagnosticGrader:
    """Grade solely from content-bound evaluations produced offline."""

    # ── move parsing ────────────────────────────────────────────────

    @staticmethod
    def parse_user_move(board: "_chess.Board", user_move: str) -> Optional["_chess.Move"]:
        """Accept SAN ('Nxd5', 'O-O') or UCI ('e2e4'). None if illegal."""
        try:
            return board.parse_san(user_move)
        except Exception:
            pass
        try:
            mv = _chess.Move.from_uci(user_move)
            if mv in board.legal_moves:
                return mv
        except Exception:
            pass
        return None

    # ── core grading ────────────────────────────────────────────────

    def _grade_move_consequence(
        self,
        user_move: str,
        puzzle: Dict[str, Any],
        fen: Optional[str] = None,
        solution_uci: Optional[str] = None,
        solution_eval_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Grade one move. `fen`/`solution_uci` default to the puzzle's
        starting position + first solution move; the multi-move walk
        passes the current mid-line position instead.

        Returns {"verdict", "cp_loss", "eval_after", "explanation",
                 "is_exact", "user_move_san", "solution_san"}.
        """
        fen = fen or puzzle["fen"]
        board = _chess.Board(fen)
        solver = board.turn
        solution_uci = solution_uci or puzzle["moves"][puzzle.get("user_move_idx", 0)]
        sol_move = _chess.Move.from_uci(solution_uci)
        solution_san = board.san(sol_move)

        user_mv = self.parse_user_move(board, user_move)
        if user_mv is None:
            raise ValueError(f"Illegal or unparseable move: {user_move}")
        user_san = board.san(user_mv)

        if not frozen_diagnostic_grades_are_current(puzzle):
            raise UnverifiedDiagnosticMove(
                "This diagnostic position needs an offline verification refresh."
            )
        wanted_fen = " ".join(board.fen().split()[:4])
        step = next(
            (
                item
                for item in (puzzle.get("step_grades") or [])
                if " ".join(str(item.get("fen") or "").split()[:4]) == wanted_fen
                and item.get("solution_uci") == solution_uci
            ),
            None,
        )
        frozen = (step or {}).get("grade_by_uci", {}).get(user_mv.uci())
        if not frozen:
            raise UnverifiedDiagnosticMove(
                "This legal move is missing from the offline verification map."
            )
        is_exact = user_mv.uci() == solution_uci
        verdict = "UNDERSTOOD" if is_exact else str(frozen.get("verdict"))
        cp_loss = 0 if is_exact else int(frozen.get("cp_loss") or 0)
        eval_after = int(frozen.get("eval_after_cp") or 0)

        return {
            "verdict": verdict,
            "cp_loss": cp_loss,
            "eval_after": eval_after,
            "is_exact": is_exact,
            "source": "offline_frozen",
            "user_move_san": user_san,
            "solution_san": solution_san,
            "explanation": self._generate_verdict_explanation(
                puzzle, user_san, solution_san, verdict,
                is_exact=is_exact, eval_after=eval_after, fen=fen,
                solution_uci=solution_uci,
            ),
        }

    # ── explanation copy (deterministic, no jargon beyond fork/pin/skewer) ──

    @staticmethod
    def _solution_facts(fen: str, solution_uci: str) -> Dict[str, Any]:
        """Board facts about the solution move, for the outcome clause."""
        facts = {"captures": None, "gives_check": False, "is_mate": False}
        try:
            board = _chess.Board(fen)
            mv = _chess.Move.from_uci(solution_uci)
            target = board.piece_at(mv.to_square)
            if board.is_en_passant(mv):
                facts["captures"] = "pawn"
            elif target:
                facts["captures"] = _PIECE_NAME.get(target.piece_type)
            board.push(mv)
            facts["is_mate"] = board.is_checkmate()
            facts["gives_check"] = board.is_check()
        except Exception:
            pass
        return facts

    @staticmethod
    def _outcome_clause(facts: Dict[str, Any]) -> str:
        if facts.get("is_mate"):
            return "is checkmate"
        cap = facts.get("captures")
        if cap and facts.get("gives_check"):
            return f"wins the {cap} with check"
        if cap:
            return f"wins the {cap}"
        if facts.get("gives_check"):
            return "keeps the pressure on with check"
        return "was the strongest idea here"

    _UNDERSTOOD_TAIL = {
        "fork": "that's exactly the fork.",
        "pin": "the pin made it work.",
        "skewer": "that's the skewer.",
        "mate_patterns": "you saw the mate.",
        "piece_safety": "nothing left hanging.",
        "threat_response": "threat handled.",
        "calculation": "you saw the line through.",
        "opening": "good opening judgment.",
        "endgame": "clean technique.",
        "winning_technique": "that keeps the win in hand.",
    }

    def _generate_verdict_explanation(
        self, puzzle: Dict[str, Any], user_san: str, solution_san: str,
        verdict: str, *, is_exact: bool, eval_after: int, fen: str,
        solution_uci: str,
    ) -> str:
        concept = puzzle.get("concept", "")
        facts = self._solution_facts(fen, solution_uci)
        outcome = self._outcome_clause(facts)

        if verdict == "UNDERSTOOD":
            if is_exact:
                tail = self._UNDERSTOOD_TAIL.get(concept, "well spotted.")
                return f"{solution_san} {outcome} — {tail}"
            return (
                f"{user_san} works too — it keeps you on top. "
                f"Our line was {solution_san}."
            )

        if verdict == "PARTIAL":
            return (
                f"{user_san} doesn't give anything big away, but "
                f"{solution_san} {outcome} — worth a second look."
            )

        # MISSING
        if concept == "threat_response" and _eval_sign(eval_after) < 0:
            consequence = "the threat is still hanging over you"
        elif _eval_sign(eval_after) < 0:
            consequence = "your opponent takes over"
        elif _eval_sign(eval_after) == 0:
            consequence = "the advantage is gone"
        else:
            consequence = "most of your edge slips away"
        if facts.get("is_mate"):
            idea = f"The idea was {solution_san} — checkmate on the spot."
        elif outcome == "was the strongest idea here":
            idea = f"The idea was {solution_san}."
        else:
            idea = f"The idea was {solution_san} — it {outcome}."
        return f"{idea} After {user_san}, {consequence}."


# ── consistency gating + difficulty staircase ────────────────────────


def next_tier(tier: str, verdict: str) -> str:
    """UNDERSTOOD → up a tier, MISSING → down, PARTIAL → repeat."""
    if verdict == "UNDERSTOOD":
        return _TIER_UP.get(tier, "high")
    if verdict == "MISSING":
        return _TIER_DOWN.get(tier, "low")
    return tier


def concept_done(verdicts: List[str]) -> tuple:
    """(done, adaptive_triggered_now).

    [U,U] or [M,M] → done after 2. Anything else at 2 → adaptive third
    puzzle. After 3 (or more) → done regardless."""
    n = len(verdicts)
    if n >= 3:
        return True, False
    if n == 2:
        if verdicts[0] == verdicts[1] and verdicts[0] in ("UNDERSTOOD", "MISSING"):
            return True, False
        return False, True
    return False, False


def concept_level(verdicts: List[str]) -> str:
    """solid / developing / missing from the verdict list."""
    if not verdicts:
        return "untested"
    score = sum(
        1.0 if v == "UNDERSTOOD" else 0.5 if v == "PARTIAL" else 0.0
        for v in verdicts
    ) / len(verdicts)
    if score >= 0.75:
        return "solid"
    if score >= 0.35:
        return "developing"
    return "missing"


def _round25(x: float) -> int:
    return int(round(x / 25.0) * 25)


def estimate_rating_v2(attempts: List[Dict[str, Any]]) -> Dict[str, int]:
    """Staircase midpoint of (highest tier passed, lowest tier failed)."""
    passed = [a.get("puzzle_rating") or TIER_RATING.get(a.get("tier"), 1200)
              for a in attempts if a.get("verdict") == "UNDERSTOOD"]
    failed = [a.get("puzzle_rating") or TIER_RATING.get(a.get("tier"), 1200)
              for a in attempts if a.get("verdict") == "MISSING"]
    if passed and failed:
        mid = (max(passed) + min(failed)) / 2.0
    elif passed:
        mid = max(passed) + 150
    elif failed:
        mid = min(failed) - 200
    else:
        partial = [a.get("puzzle_rating") or 1000 for a in attempts]
        mid = sum(partial) / len(partial) if partial else 1000
    mid = max(700, min(1800, mid))
    return {"low": _round25(mid - 100), "high": _round25(mid + 100)}


def score_diagnostic_v2(session: Dict[str, Any]) -> Dict[str, Any]:
    """Build the final diagnosis from a v2 session document."""
    attempts = session.get("attempts", [])
    progress = session.get("concept_progress", {})

    per_concept: Dict[str, Any] = {}
    for concept in CONCEPT_PRIORITY:
        prog = progress.get(concept)
        if not prog or not prog.get("verdicts"):
            continue
        verdicts = prog["verdicts"]
        tiers = prog.get("tiers", [])
        tier_passed = None
        for v, t in zip(verdicts, tiers):
            if v == "UNDERSTOOD":
                r = TIER_RATING.get(t, t if isinstance(t, int) else 1200)
                tier_passed = max(tier_passed or 0, r) or r
        per_concept[concept] = {
            "level": concept_level(verdicts),
            "verdicts": [VERDICT_SYMBOL.get(v, "?") for v in verdicts],
            "tier_passed": tier_passed,
            "display_name": CONCEPT_LABEL.get(concept, concept),
        }

    headline_gap = None
    for want in ("missing", "developing"):
        for concept in CONCEPT_PRIORITY:
            if per_concept.get(concept, {}).get("level") == want:
                headline_gap = concept
                break
        if headline_gap:
            break

    n_missing = sum(1 for a in attempts if a.get("verdict") == "MISSING")
    blunder_rate = round(n_missing / len(attempts), 2) if attempts else 0.0

    solid = [per_concept[c]["display_name"] for c in per_concept
             if per_concept[c]["level"] == "solid"]
    if headline_gap and solid:
        summary = (
            f"You handled {solid[0].lower()} well. The clearest place to "
            f"grow: {CONCEPT_LABEL[headline_gap].lower()} — that's where "
            f"we'll start."
        )
    elif headline_gap:
        summary = (
            f"The clearest place to grow: "
            f"{CONCEPT_LABEL[headline_gap].lower()} — that's where we'll start."
        )
    elif solid:
        summary = (
            f"Strong across the board, especially {solid[0].lower()}. "
            f"A few real games will sharpen the picture."
        )
    else:
        summary = "Mixed across the board. A few real games will sharpen this picture."

    return {
        "version": 2,
        "rating_estimate": estimate_rating_v2(attempts),
        "per_concept": per_concept,
        "headline_gap": headline_gap,
        "summary": summary,
        "blunder_rate": blunder_rate,
        "total_attempted": len(attempts),
    }


# ── wiring: v2 diagnosis → the same weakness pipeline v1 used ────────

_CONCEPT_TO_WEAKNESS: Dict[str, tuple] = {
    "threat_response": ("king_safety", "exposing_own_king"),
    "piece_safety": ("tactical", "one_move_blunders"),
    "mate_patterns": ("tactical", "one_move_blunders"),
    "fork": ("tactical", "fork_misses"),
    "pin": ("tactical", "fork_misses"),
    "skewer": ("tactical", "fork_misses"),
    "calculation": ("tactical", "one_move_blunders"),
    "opening": ("opening_principles", "neglecting_development"),
    "endgame": ("tactical", "one_move_blunders"),
    "winning_technique": ("tactical", "one_move_blunders"),
}

_CONCEPT_TO_FOCUS: Dict[str, str] = {
    "threat_response": "king_safety",
    "piece_safety": "hanging_piece",
    "mate_patterns": "tactical_error",
    "fork": "missed_fork",
    "pin": "missed_fork",
    "skewer": "missed_fork",
    "calculation": "tactical_error",
}


async def apply_diagnosis_v2_to_training(db, user_id: str, session: Dict[str, Any]) -> Dict[str, Any]:
    """Score a v2 session and feed the headline gap into the same
    weakness pipeline game analysis uses (see v1 wiring notes above)."""
    from player_profile_service import update_weakness_tracking, get_or_create_profile

    diagnosis = score_diagnostic_v2(session)
    gap = diagnosis.get("headline_gap")
    if not gap:
        return diagnosis

    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1})
    await get_or_create_profile(db, user_id, (u or {}).get("name") or "Player")

    cat, subcat = _CONCEPT_TO_WEAKNESS.get(gap, ("tactical", "one_move_blunders"))
    try:
        await update_weakness_tracking(db, user_id, [{"category": cat, "subcategory": subcat}])
    except Exception as e:
        logger.warning(f"diagnostic v2 -> weakness write failed for {user_id}: {e}")

    focus = _CONCEPT_TO_FOCUS.get(gap)
    if focus:
        await db.coach_memory.update_one(
            {"user_id": user_id},
            {"$set": {"learning.current_focus": focus, "learning.focus_source": "diagnostic"}},
            upsert=True,
        )
    return diagnosis
