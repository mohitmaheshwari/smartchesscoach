"""PWC ↔ V5 caption bridge.

Routes Play-with-Coach per-move captions through the SAME backend that
Lab game review uses (`generate_game_decryption_v5`). Both surfaces
read from `backend/data/captions/*.json` — when Mohit + Parth author a
new opening / trap / rule, both Lab AND PWC pick it up on the next
caption render.

The bridge does ONE job: take a PWC session's `move_history` (which
stores player evals + best moves per move) and reshape it into the
(pgn, user_color, move_evaluations, user_id, db) tuple V5 expects.
Then return the caption for whichever move the caller asks for.

Why a bridge module rather than calling V5 directly in coach_play:
  1. Keeps the V5 service single-purpose (game review).
  2. Isolates the PWC-specific data-shape adapter in one place — if
     PWC's move_history schema changes (more fields, new keys), this
     is the only file that has to track that.
  3. Lets us iterate on PWC voice without touching Lab.

Per architecture rule (Mohit 2026-05-20): no user-facing strings here.
Python only reshapes data + delegates to the JSON-driven V5 pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_pgn_from_history(move_history: List[Dict[str, Any]], user_color: str) -> str:
    """Reconstruct a minimal PGN string from a PWC session's move_history.

    Each entry has `move` (SAN), `by` ('player'|'coach'). PWC is always
    user vs Stockfish coach — assign white/black based on user_color.
    The PGN headers are placeholders; only the moves matter to V5."""
    sans: List[str] = []
    for m in move_history:
        san = m.get("move")
        if san:
            sans.append(san)
    if not sans:
        return ""
    # Format as standard PGN: "1. e4 e5 2. Nf3 Nc6 ..."
    body_tokens: List[str] = []
    for i, san in enumerate(sans):
        if i % 2 == 0:
            body_tokens.append(f"{(i // 2) + 1}.")
        body_tokens.append(san)
    white = "Player" if user_color.lower() == "white" else "Coach"
    black = "Coach" if user_color.lower() == "white" else "Player"
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    headers = (
        '[Event "Play with Coach"]\n'
        '[Site "ChessGuru"]\n'
        f'[Date "{today}"]\n'
        '[Round "-"]\n'
        f'[White "{white}"]\n'
        f'[Black "{black}"]\n'
        '[Result "*"]\n'
    )
    return f"{headers}\n{' '.join(body_tokens)} *\n"


def _build_move_evaluations(move_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reshape PWC move_history into the move_evaluations list shape
    V5 expects. PWC stores eval_before / eval_after in pawns from
    white's POV; V5 expects centipawns.

    Note: PWC currently only writes eval data on PLAYER moves, not coach
    moves. For coach moves, eval fields are absent — V5 looks up evals
    by fen_before so the missing-eval case becomes 'no cp_loss
    available', which V5 already handles (defaults to 0)."""
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(move_history):
        eval_before_pawns = m.get("eval_before")
        eval_after_pawns = m.get("eval_after")
        cp_loss = None
        if isinstance(eval_before_pawns, (int, float)) and isinstance(eval_after_pawns, (int, float)):
            # cp_loss is the perspective-corrected drop. V5 takes
            # abs(cp_loss) for user moves so sign correction isn't
            # strictly needed here.
            cp_loss = int(round((eval_before_pawns - eval_after_pawns) * 100))
        entry: Dict[str, Any] = {
            "move_number": (i // 2) + 1,
            "move": m.get("move"),
            "move_uci": m.get("uci"),
            "fen_before": m.get("fen_before"),
            "fen_after": m.get("fen_after"),
        }
        if isinstance(eval_before_pawns, (int, float)):
            entry["eval_before"] = int(round(eval_before_pawns * 100))
        if isinstance(eval_after_pawns, (int, float)):
            entry["eval_after"] = int(round(eval_after_pawns * 100))
        if cp_loss is not None:
            entry["cp_loss"] = abs(cp_loss)
            entry["eval_swing"] = cp_loss
        best_move = m.get("best_move")
        if best_move:
            entry["best_move_san"] = best_move
            entry["best_move"] = best_move
        out.append(entry)
    return out


async def caption_for_pwc_move(
    db,
    session_id: str,
    move_index: Optional[int] = None,
) -> Optional[str]:
    """Return the V5 caption for one move in a PWC session.

    Args:
      db: motor database client
      session_id: PWC session
      move_index: 0-indexed position in move_history. None → caption
        for the most recent user move (typical poll case).

    Returns:
      The caption string, or None when V5 has nothing to say (silence)
      or when the move can't be located. Callers should treat None as
      'no caption to show' and fall back to whatever they had before.
    """
    session = await db.coach_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session:
        return None
    move_history = session.get("move_history") or []
    if not move_history:
        return None
    user_color = (session.get("user_color") or "white").lower()
    user_id = session.get("user_id") or ""

    # Resolve which move_history index to caption. Default = last
    # player move (the one the frontend just polled feedback for).
    if move_index is None:
        for idx in range(len(move_history) - 1, -1, -1):
            if move_history[idx].get("by") == "player":
                move_index = idx
                break
        if move_index is None:
            return None
    if move_index < 0 or move_index >= len(move_history):
        return None

    pgn = _build_pgn_from_history(move_history, user_color)
    if not pgn:
        return None
    move_evaluations = _build_move_evaluations(move_history)

    # Delegate to the same V5 pipeline Lab review uses. Single source
    # of truth — JSON content in backend/data/captions/ drives both.
    try:
        from services.game_decryption_v5_service import generate_game_decryption_v5
    except ImportError as exc:  # pragma: no cover — defensive
        logger.warning(f"[pwc_caption_bridge] V5 import failed: {exc}")
        return None

    try:
        v5_data = await generate_game_decryption_v5(
            pgn, user_color, move_evaluations, user_id, db
        )
    except Exception as exc:
        logger.warning(f"[pwc_caption_bridge] V5 regen failed for {session_id}: {exc}")
        return None

    if not v5_data or move_index >= len(v5_data):
        return None

    caption = (v5_data[move_index] or {}).get("caption") or ""
    return caption or None
