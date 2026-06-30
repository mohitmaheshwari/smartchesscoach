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
    """Moments where the user was winning (>= +0.5 eval) then hung a piece (>= 200 cp loss)."""
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
            # eval_before is in centipawns; +50 = +0.5 pawn advantage
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
    """Moments from games reaching move 40+ that the user lost despite having ≥+0.3 eval before move 30."""
    out = []
    cur = db.game_analyses.find(
        {"user_id": user_id},
        {"game_id": 1, "stockfish_analysis.move_evaluations": 1, "analyzed_at": 1}
    ).sort("analyzed_at", -1).limit(80)
    async for a in cur:
        if len(out) >= limit:
            break
        # Need to fetch the game to know the result
        game = await db.games.find_one(
            {"game_id": a["game_id"]},
            {"result": 1, "user_color": 1, "pgn": 1}
        )
        if not game:
            continue
        result = (game.get("result") or "").strip()
        col = game.get("user_color", "")
        # Was the game long?
        pgn = game.get("pgn", "")
        if not any(f" {n}." in pgn for n in (40, 45, 50)):
            continue
        # Did the user lose?
        user_lost = (result == "1-0" and col == "black") or (result == "0-1" and col == "white")
        if not user_lost:
            continue
        # Find the move where the advantage cratered (their eval_before was good, cp_loss large, after move 25)
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
                break  # one moment per game is enough
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
