"""
Personalized Moments — Topic Registry.

This module is the SINGLE SOURCE OF TRUTH for the topics our re-engagement
emails are allowed to link to. Every CTA in a coaching email must reference
a topic that exists here. If you write an email script with a CTA topic
that isn't registered, the lint check (scripts/pwc_coaching_lint.py + a
new email_link_lint check) will fail before send.

Why this exists:
  - Earlier in the coach-experience design we shipped emails to Shobhit and
    Mohit promising "3 specific moments from your games." The link went to
    /lab — a generic page that does NOT show 3 specific moments. That's a
    credibility crater the first time a user clicks.
  - Going forward: an email CTA = a topic registry entry = a page that
    actually delivers what the email promised. No daylight between promise
    and delivery.

How to add a new topic (4 steps, all in this file):
  1) Add a new entry to TOPICS below with:
        - key             — the URL slug (used in /coach/moments/<key>)
        - label           — human label (used as page H1)
        - subtitle        — one-line under the H1
        - filter          — query callable(db, user_id) → list of moments
        - explainer       — one-paragraph teaching insight (used on the page)
  2) The frontend /coach/moments/:topic page picks up new topics automatically
     by calling the unified endpoint.
  3) New email script imports TOPICS and references key. Lint will catch typos.
  4) Add the topic to docs/email_page_contract.md so the doc stays current.
"""
from typing import Callable, Awaitable, Dict, Any, List

# Each filter returns a list of "moment" dicts with at minimum:
#   { "game_id", "move_number", "fen_before", "user_played", "best_move",
#     "cp_loss", "date_played", "why" }


async def _filter_piece_safety_in_winning_position(db, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Moments where the user was winning (>= +0.5 eval) then hung a piece (>= 200 cp loss).

    Phase 5: now queries move_observations directly. Indexed lookup,
    no per-game scan needed. Returns same shape as the legacy scanner.
    Falls back to the legacy scanner if move_observations is empty
    (e.g. for a brand-new user whose games haven't been backfilled yet).
    """
    # Try the new layer first — fast, indexed, single query
    try:
        # cap cp_loss at 1000 to exclude Stockfish mate-detection outliers
        # (we've seen values like 9342 when the position became forced-mate)
        cur = db.move_observations.find(
            {
                "user_id": user_id,
                "execution_quality": {"$in": ["blunder", "mistake"]},
                "eval_before": {"$gte": 50},     # winning when they moved
                "cp_loss": {"$gte": 200, "$lt": 1000},
            },
            {"_id": 0}
        ).sort("derived_at", -1).limit(limit)
        out = []
        async for o in cur:
            # Look up best_move from the source analysis. Don't use $slice —
            # move_evaluations is indexed by ply (incl. opponent moves) so
            # slicing by move_number * 2 is wrong. Just fetch + find.
            a = await db.game_analyses.find_one(
                {"game_id": o["game_id"]},
                {"stockfish_analysis.move_evaluations": 1}
            )
            best_move = None
            for mv in (((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if mv.get("move_number") == o["move_number"] and not mv.get("is_opponent_move"):
                    best_move = mv.get("best_move")
                    break
            eval_before_pawns = round((o.get("eval_before") or 0) / 100, 2)
            # Use narrative phrasing as primary "why" — user-facing landing
            # page benefits from a sentence over the terse takeaway label.
            narrative = (f"You had a winning position (+{eval_before_pawns}). "
                         f"Best was {best_move}. You played {o.get('move_san')} which dropped {o.get('cp_loss')}cp.")
            out.append({
                "game_id": o["game_id"],
                "move_number": o["move_number"],
                "fen_before": o.get("fen_before"),
                "user_played": o.get("move_san"),
                "best_move": best_move,
                "cp_loss": o.get("cp_loss"),
                "eval_before_pawns": eval_before_pawns,
                "date_played": o.get("derived_at"),
                "why": narrative,
            })
        if out:
            return out
    except Exception:
        # New layer not populated yet for this user — fall through to legacy scanner
        pass

    # Legacy scanner fallback (used until move_observations is populated for this user)
    from datetime import datetime, timezone, timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    out = []
    cur = db.game_analyses.find(
        {"user_id": user_id, "analyzed_at": {"$gte": since}},
        {"game_id": 1, "stockfish_analysis.move_evaluations": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1)
    async for a in cur:
        if len(out) >= limit:
            break
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        for mv in moves:
            if mv.get("is_opponent_move"):
                continue
            cp_loss = mv.get("cp_loss", 0) or 0
            eval_before = mv.get("eval_before", 0) or 0
            cg = mv.get("cognitive_gap")
            if eval_before >= 50 and cp_loss >= 200 and cg in ("piece_safety", None):
                out.append({
                    "game_id": a["game_id"],
                    "move_number": mv.get("move_number"),
                    "fen_before": mv.get("fen_before"),
                    "user_played": mv.get("move"),
                    "best_move": mv.get("best_move"),
                    "cp_loss": cp_loss,
                    "eval_before_pawns": round(eval_before / 100, 2),
                    "date_played": a.get("analyzed_at"),
                    "why": f"You had a winning position (+{round(eval_before/100,1)}). "
                           f"Best was {mv.get('best_move')}. You played {mv.get('move')} which dropped {cp_loss}cp.",
                })
                if len(out) >= limit:
                    break
    return out


async def _filter_long_game_conversion_losses(db, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Moments past move 25 where the user had ≥+0.3 eval and dropped ≥150cp,
    in long games (≥ move 40) that the user lost.

    Phase 5: uses move_observations directly for the move-level filter
    (indexed, fast), then validates game length + result with a single
    games.find_one per candidate. Falls back to legacy scanner if the
    new collection has no observations for this user yet.
    """
    out = []
    # Try the new layer first
    try:
        # Step 1: find candidate moves (late-game blunder while ahead) via index
        cur = db.move_observations.find(
            {
                "user_id": user_id,
                "move_number": {"$gte": 25},
                "execution_quality": {"$in": ["blunder", "mistake"]},
                "eval_before": {"$gte": 30},
                "cp_loss": {"$gte": 150},
            },
            {"_id": 0}
        ).sort("derived_at", -1).limit(limit * 5)  # over-fetch so we have margin after game-level filter
        async for o in cur:
            if len(out) >= limit:
                break
            game = await db.games.find_one(
                {"game_id": o["game_id"]},
                {"result": 1, "user_color": 1, "pgn": 1}
            )
            if not game:
                continue
            result = (game.get("result") or "").strip()
            col = game.get("user_color", "")
            pgn = game.get("pgn", "")
            # Was the game long?
            if not any(f" {n}." in pgn for n in (40, 45, 50)):
                continue
            user_lost = (result == "1-0" and col == "black") or (result == "0-1" and col == "white")
            if not user_lost:
                continue
            # Look up best_move from the source analysis
            best_move = None
            a = await db.game_analyses.find_one(
                {"game_id": o["game_id"]},
                {"stockfish_analysis.move_evaluations": 1}
            )
            for mv in (((a or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []):
                if mv.get("move_number") == o["move_number"] and not mv.get("is_opponent_move"):
                    best_move = mv.get("best_move")
                    break
            eval_before_pawns = round((o.get("eval_before") or 0) / 100, 2)
            narrative = (f"At move {o['move_number']} you were +{eval_before_pawns}. "
                         f"Best was {best_move}. You played {o.get('move_san')} — gave back {o.get('cp_loss')}cp. "
                         f"The game continued and you lost.")
            out.append({
                "game_id": o["game_id"],
                "move_number": o["move_number"],
                "fen_before": o.get("fen_before"),
                "user_played": o.get("move_san"),
                "best_move": best_move,
                "cp_loss": o.get("cp_loss"),
                "eval_before_pawns": eval_before_pawns,
                "date_played": o.get("derived_at"),
                "why": narrative,
            })
        if out:
            return out
    except Exception:
        # New layer not populated for this user — fall through
        pass

    # Legacy scanner fallback
    out = []
    cur = db.game_analyses.find(
        {"user_id": user_id},
        {"game_id": 1, "stockfish_analysis.move_evaluations": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(80)
    async for a in cur:
        if len(out) >= limit:
            break
        game = await db.games.find_one(
            {"game_id": a["game_id"]},
            {"result": 1, "user_color": 1, "pgn": 1}
        )
        if not game:
            continue
        result = (game.get("result") or "").strip()
        col = game.get("user_color", "")
        pgn = game.get("pgn", "")
        if not any(f" {n}." in pgn for n in (40, 45, 50)):
            continue
        user_lost = (result == "1-0" and col == "black") or (result == "0-1" and col == "white")
        if not user_lost:
            continue
        moves = (a.get("stockfish_analysis") or {}).get("move_evaluations") or []
        for mv in moves:
            if mv.get("is_opponent_move"):
                continue
            mn = mv.get("move_number", 0)
            if mn < 25:
                continue
            eval_before = mv.get("eval_before", 0) or 0
            cp_loss = mv.get("cp_loss", 0) or 0
            if eval_before >= 30 and cp_loss >= 150:
                out.append({
                    "game_id": a["game_id"],
                    "move_number": mn,
                    "fen_before": mv.get("fen_before"),
                    "user_played": mv.get("move"),
                    "best_move": mv.get("best_move"),
                    "cp_loss": cp_loss,
                    "eval_before_pawns": round(eval_before / 100, 2),
                    "date_played": a.get("analyzed_at"),
                    "why": f"At move {mn} you were +{round(eval_before/100,1)}. "
                           f"Best move was {mv.get('best_move')}. You played {mv.get('move')} — gave back {cp_loss}cp. "
                           f"The game then continued and you lost.",
                })
                break
    return out


# ============================ THE REGISTRY ============================
# Every email CTA must reference one of these keys.

TOPICS: Dict[str, Dict[str, Any]] = {
    "piece_safety": {
        "key": "piece_safety",
        "label": "When you stop thinking",
        "subtitle": "3 winning positions where one piece-safety scan would have saved the game.",
        "filter": _filter_piece_safety_in_winning_position,
        "explainer": (
            "Getting an advantage is a different skill from keeping one. After you get ahead, "
            "your brain switches from 'find the best plan' to 'execute the win' — and that switch "
            "is when you stop checking what your opponent is touching. Strong players don't relax "
            "after they get an edge; they get more careful. Before every move: 'is anyone touching "
            "any of my pieces?' Three seconds, saves the game."
        ),
    },
    "long_game_conversion": {
        "key": "long_game_conversion",
        "label": "Where the long game slipped",
        "subtitle": "3 moments past move 25 where your advantage gave way.",
        "filter": _filter_long_game_conversion_losses,
        "explainer": (
            "Holding a small advantage is a completely different skill from getting one. Most "
            "players treat the endgame like the opening — they keep looking for the next attack "
            "instead of squeezing the position. The fix is recognizing: once you're ahead, your "
            "job changes. Simplify, trade pieces, don't let the position get complicated again."
        ),
    },
}


def get_topic(key: str) -> Dict[str, Any]:
    """Returns the topic definition or raises KeyError."""
    if key not in TOPICS:
        raise KeyError(f"Unknown moments topic: {key}. Add it to TOPICS in moments_topic_registry.py.")
    return TOPICS[key]


def list_topics() -> List[str]:
    """All registered topic keys (used by lint to validate email scripts)."""
    return list(TOPICS.keys())
