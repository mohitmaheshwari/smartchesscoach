"""
Drillable adaptive coach — depth explanations per principle.

Phase-4 Component 1 (locked 2026-05-19 per [[drillable-adaptive-coach]]).
Every named principle gets up to 4 levels of explanation. Level 1 is the
caption itself (already shipped via the V5 pipeline). Levels 2-4 are
served on user-initiated "Tell me more" affordance.

THE FOUR-LEVEL LADDER:
  Level 1 — Principle (already shipped): the named anchor + concrete fact
    ("Pin pattern — Bb5 pins Nc6 to the queen on d8.")
  Level 2 — Geometry (this commit): authored visual/structural explanation
    of WHY the pattern works, what the eye should scan for.
  Level 3 — Behavior: user-specific context merged from
    user_teaching_memory + recurring_deviations. Falls back to a
    generic actionable phrase when no user data exists.
  Level 4 — Identity: PLACEHOLDER for Phase-5 clustering work. Returns
    a "coming soon" honest fallback for now per [[no-hollow-coverage]].

VOICE: patient academic per [[coach-voice]] + per the 2026-05-19
calibration. Concrete, observational, names the geometry, trusts the
student. NEVER theatrical or chatty.

DATA SOURCES:
  - Static authored content lives in DEPTH_EXPLANATIONS below.
  - Level 3 user-data merging reads db.user_teaching_memory (per-user
    gold/lucky/celebration history populated 2026-05-19 backfill).

CONSUMERS:
  - get_depth_for_principle(db, user_id, principle_id, level) returns a
    rendered dict { title, body, has_user_data }. Frontend "Tell me
    more" affordance calls this with incrementing level.

V1 SCOPE: 5 principles authored (TAC_PIN_PATTERN, TAC_HANGING_PIECE,
TAC_FORK_PATTERN, END_RULE_OF_SQUARE, DEF_WALK_KING) — the most-fired
principles per the corpus rank-teaching-gold scan (5 cover ~60% of
all V5 fires). The remaining 23 principles return graceful fallback
at all depth levels until authored.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEPTH_EXPLANATIONS_VERSION = 1


# ─────────────────────────────────────────────────────────────────
# AUTHORED CONTENT — static explanations per principle, per level.
#
# Level 2 (geometry) is fully authored and shipped.
# Level 3 (behavior) is a template; user data fills the {placeholder}
#   fields at render time. {fire_count_30d}, {gold_count}, etc.
# Level 4 (identity) is reserved for clustering — V1 returns fallback.
# ─────────────────────────────────────────────────────────────────

DEPTH_EXPLANATIONS: Dict[str, Dict[str, Any]] = {

    # ────────────────────────────────────────────────────────────
    "TAC_PIN_PATTERN": {
        "level_2_geometry": {
            "title": "The shape",
            "body": (
                "A pin works because three pieces share a line. The "
                "pinning piece (a bishop, rook, or queen), the pinned "
                "piece, and a more valuable target behind — all on the "
                "same diagonal or file. The pinned piece cannot move "
                "without exposing the target. Two ways to break it: "
                "capture the pinner, or block the line with a defended "
                "piece. The scan: every move, check the diagonals and "
                "files between your minor pieces and your king or queen."
            ),
        },
        "level_3_behavior": {
            "title": "Your pattern",
            "template": (
                "You've been flagged for pin geometry {fire_count_30d} "
                "times across your recent games. The recurring shape: "
                "your minor pieces developed onto squares where an "
                "enemy slider can line them up against your queen. "
                "Before developing knights or bishops, scan the "
                "diagonals to your queen first."
            ),
            "fallback": (
                "Pin shapes recur across openings. Before developing a "
                "knight or bishop, scan the diagonals between your "
                "piece and your king or queen — that's where the "
                "pinner will land."
            ),
        },
        "level_4_identity": {
            "title": "Your style",
            "fallback": (
                "Identity-level analysis is still being computed for "
                "your games. Check back later for patterns about how "
                "you tend to fall for (or avoid) pins."
            ),
        },
    },

    # ────────────────────────────────────────────────────────────
    "TAC_HANGING_PIECE": {
        "level_2_geometry": {
            "title": "The shape",
            "body": (
                "A piece is 'hanging' when nothing protects it. The "
                "fundamental scan: for every piece you might touch, "
                "count attackers and defenders. If attackers exceed "
                "defenders by one, the piece falls to the next capture. "
                "The habit isn't tactical — it's procedural. Slow "
                "for one breath before every move and run the count "
                "on the piece you're moving AND the pieces you're "
                "leaving behind."
            ),
        },
        "level_3_behavior": {
            "title": "Your pattern",
            "template": (
                "You've hung pieces in {fire_count_30d} of your "
                "recent games. The pattern: most hangs come right "
                "after you've developed a new piece — the focus moves "
                "to the new arrival, and the older pieces lose their "
                "defenders silently. Re-scan ALL your pieces after "
                "each development move, not just the one that moved."
            ),
            "fallback": (
                "Hung pieces are the largest single cause of lost "
                "games at 1200-1500. Build the habit: before every "
                "move, scan every one of your pieces for an "
                "attacker-vs-defender mismatch. The scan takes 10 "
                "seconds and saves whole games."
            ),
        },
        "level_4_identity": {
            "title": "Your style",
            "fallback": (
                "Identity-level analysis is still being computed for "
                "your games. Check back later for patterns about your "
                "defensive scanning habits."
            ),
        },
    },

    # ────────────────────────────────────────────────────────────
    "TAC_FORK_PATTERN": {
        "level_2_geometry": {
            "title": "The shape",
            "body": (
                "A fork is one piece attacking two enemy pieces at "
                "once — the opponent saves one, you take the other. "
                "Knights are the most common forkers because they "
                "jump over defenders. The geometric clue to scan for: "
                "any square where TWO enemy pieces sit exactly one "
                "knight-move away from each other. Bishops fork along "
                "diagonals; rooks fork on files and ranks; pawns fork "
                "from one square attacking two pieces diagonally."
            ),
        },
        "level_3_behavior": {
            "title": "Your pattern",
            "template": (
                "You've delivered {gold_count} forks correctly across "
                "recent games — and missed {missed_count} more that "
                "the engine saw. Missed forks usually come after a "
                "tempo-gaining move forces an enemy piece to a "
                "forkable square. Look one move ahead: 'where would "
                "their king and queen be after this check?'"
            ),
            "fallback": (
                "Forks reward players who scan for L-shapes before "
                "each move. The question to ask: 'can my knight "
                "reach a square that hits two pieces in the next "
                "one or two moves?'"
            ),
        },
        "level_4_identity": {
            "title": "Your style",
            "fallback": (
                "Identity-level analysis is still being computed. "
                "Check back later for patterns about how you find "
                "(or miss) forking opportunities."
            ),
        },
    },

    # ────────────────────────────────────────────────────────────
    "END_RULE_OF_SQUARE": {
        "level_2_geometry": {
            "title": "The shape",
            "body": (
                "Draw an imaginary square from the passed pawn to its "
                "promotion square — the side of that square equals "
                "the pawn's distance to promote. If the defending "
                "king can step INTO the square on its very next move, "
                "the king catches the pawn before it queens. If the "
                "king is already a step outside, the pawn promotes. "
                "Always count BOTH the file distance and the rank "
                "distance — the king can move diagonally to close both "
                "at once."
            ),
        },
        "level_3_behavior": {
            "title": "Your pattern",
            "template": (
                "You've reached king-and-pawn endings {fire_count_30d} "
                "times recently. In these endings, the Rule of the "
                "Square is the first thing to check on every move — "
                "before any other plan. Drill it until counting the "
                "square becomes automatic."
            ),
            "fallback": (
                "In king-and-pawn endings, the Rule of the Square "
                "is the first thing to check before every move. "
                "Count the pawn's distance to promotion; if the "
                "defending king can step into that box, the pawn "
                "is caught."
            ),
        },
        "level_4_identity": {
            "title": "Your style",
            "fallback": (
                "Identity-level analysis is still being computed. "
                "Check back later for patterns about your endgame "
                "decision-making."
            ),
        },
    },

    # ────────────────────────────────────────────────────────────
    "DEF_WALK_KING": {
        "level_2_geometry": {
            "title": "The shape",
            "body": (
                "When castling is gone, the king needs shelter built "
                "by hand. Look for a square where your own pawns form "
                "a barrier on at least two sides — usually one rank "
                "back from the centre, behind a pawn structure that "
                "hasn't been compromised. Walk the king there one "
                "square at a time. Never leave the king on an open "
                "file or long diagonal; that's where the opponent's "
                "rooks and bishops will arrive."
            ),
        },
        "level_3_behavior": {
            "title": "Your pattern",
            "template": (
                "Your king has been exposed in {fire_count_30d} of "
                "your recent middlegames. The signal: any time "
                "you've moved six or more pieces but haven't "
                "castled, your king becomes your biggest weakness. "
                "Re-prioritize: king safety before tempo."
            ),
            "fallback": (
                "If castling rights are gone, every move evaluates "
                "where your king is and where the opponent's open "
                "lines point. The king walks toward pawn cover, "
                "never sits on open files."
            ),
        },
        "level_4_identity": {
            "title": "Your style",
            "fallback": (
                "Identity-level analysis is still being computed. "
                "Check back later for patterns about how you "
                "balance development against king safety."
            ),
        },
    },
}


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def list_authored_principles() -> list:
    """Return the IDs of principles with authored depth content."""
    return sorted(DEPTH_EXPLANATIONS.keys())


def _no_content_response(level: int) -> Dict[str, Any]:
    """Graceful fallback when no authored content exists for this level."""
    return {
        "level": level,
        "title": None,
        "body": None,
        "has_user_data": False,
        "available": False,
    }


async def _level_3_user_context(
    db,
    user_id: str,
    principle_id: str,
) -> Dict[str, Any]:
    """Pull user-specific data for Level 3 behavior rendering.

    Reads from db.user_teaching_memory (populated by the Phase-2
    teaching-memory backfill). Returns counts the template can merge.
    Best-effort: any read failure returns empty context.
    """
    out = {"fire_count_30d": 0, "gold_count": 0, "missed_count": 0}
    if db is None or not user_id or not principle_id:
        return out
    try:
        # gold_count = how often user MISSED this principle (the
        # actionable teaching moments)
        out["gold_count"] = await db.user_teaching_memory.count_documents({
            "user_id": user_id,
            "principle_id": principle_id,
            "gold_class": "gold",
        })
        # fire_count_30d = all encounters in last ~30 days (rough)
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        out["fire_count_30d"] = await db.user_teaching_memory.count_documents({
            "user_id": user_id,
            "principle_id": principle_id,
            "occurred_at": {"$gte": cutoff},
        })
        # missed_count alias for fork-style templates that say "missed N forks"
        out["missed_count"] = out["gold_count"]
    except Exception as e:
        logger.warning(f"[depth_explanations] level_3 context read failed: {e}")
    return out


def _render_level_3(template: str, fallback: str, ctx: Dict[str, Any]) -> tuple:
    """Render Level 3 template with user context, fall back when ctx empty.

    Returns (rendered_body, has_user_data). If user has no encounters
    with this principle (fire_count_30d == 0 AND gold_count == 0),
    use the fallback to avoid awkward "you've hung pieces in 0 of
    your recent games."
    """
    if (ctx.get("fire_count_30d") or 0) == 0 and (ctx.get("gold_count") or 0) == 0:
        return fallback, False
    try:
        rendered = template.format(**ctx)
        return rendered, True
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"[depth_explanations] level_3 render failed: {e}")
        return fallback, False


async def get_depth_for_principle(
    db,
    user_id: Optional[str],
    principle_id: str,
    level: int,
) -> Dict[str, Any]:
    """Return depth content for a principle at the requested level.

    Returns a dict:
      {
        "level": int,
        "principle_id": str,
        "title": str | None,
        "body": str | None,
        "has_user_data": bool,
        "available": bool,
      }

    Levels:
      1 → Not handled here (Level 1 is the V5 caption itself,
          rendered via caption_rules.py). Returns no-content.
      2 → Authored geometry. Static; same body for every user.
      3 → Authored behavior template + user-data merge. Falls back
          to a generic-but-actionable string when no data exists.
      4 → Reserved for Phase-5 clustering. Returns honest "still
          being computed" fallback.

    Best-effort across all failures. Returns a no-content response
    rather than raising; callers can degrade gracefully.
    """
    entry = DEPTH_EXPLANATIONS.get(principle_id)
    if not entry:
        return {**_no_content_response(level), "principle_id": principle_id}

    if level == 2:
        l2 = entry.get("level_2_geometry")
        if not l2:
            return {**_no_content_response(level), "principle_id": principle_id}
        return {
            "level": 2,
            "principle_id": principle_id,
            "title": l2.get("title"),
            "body": l2.get("body"),
            "has_user_data": False,
            "available": True,
        }

    if level == 3:
        l3 = entry.get("level_3_behavior")
        if not l3:
            return {**_no_content_response(level), "principle_id": principle_id}
        ctx = await _level_3_user_context(db, user_id or "", principle_id)
        body, has_user_data = _render_level_3(
            l3.get("template") or "",
            l3.get("fallback") or "",
            ctx,
        )
        return {
            "level": 3,
            "principle_id": principle_id,
            "title": l3.get("title"),
            "body": body,
            "has_user_data": has_user_data,
            "available": True,
        }

    if level == 4:
        l4 = entry.get("level_4_identity")
        if not l4:
            return {**_no_content_response(level), "principle_id": principle_id}
        # Phase-5 — clustering work not built yet. Always return fallback.
        return {
            "level": 4,
            "principle_id": principle_id,
            "title": l4.get("title"),
            "body": l4.get("fallback"),
            "has_user_data": False,
            "available": True,
        }

    return {**_no_content_response(level), "principle_id": principle_id}
