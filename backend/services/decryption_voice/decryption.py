"""
Decryption generator — produces the per-moment / Plan Decryption text.

ZERO LLM. The decryption pipeline is now fully deterministic:

  1. Try the concept dispatcher — if a tactical / strategic / endgame
     pattern fires, use its rendered template caption (zero hallucination,
     every word from verified facts).

  2. Otherwise, emit a minimal engine-fact line:
        "The engine prefers Nf3 here."
     Always true (the SAN comes from Stockfish), no invented geometry.
     The moment is auto-flagged via confidence_score → coach overrides
     it from /admin → Review.

We deleted the LLM call and prompt machinery. Templates expand over
time as the review queue tells us which patterns to add next; LLM
prose is no longer trusted on the player surface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


# ── Engine fallback ──────────────────────────────────────────────────
# Single-sentence placeholder using only Stockfish-verified facts.
# Cannot hallucinate because the only variable is best_move_san.

def engine_fallback_text(best_move_san: Optional[str]) -> str:
    if best_move_san:
        return f"The engine prefers {best_move_san} here."
    return "The engine had a stronger move here."


# ── Public API ───────────────────────────────────────────────────────

@dataclass
class DecryptionResult:
    text: str
    source: str          # "template:<pattern>" | "engine_fallback"
    attempts: int
    delta_present: bool
    # Kept for back-compat with the orchestrator's moment dict — always
    # None now that we don't run an LLM retry loop.
    failed_attempts: Optional[List[Dict]] = None


async def generate_decryption(
    *,
    fen_before: str,
    fen_after: str,
    move_uci: str,
    user_color: str,
    moment_context: Optional[Dict] = None,
    best_move_san: Optional[str] = None,
    pv_after_best: Optional[List[str]] = None,
) -> Optional[DecryptionResult]:
    """Build a Decryption block for one critical move.

    Two paths:
      1. Concept dispatcher fires a template → use its caption.
      2. Otherwise → engine_fallback_text (one sentence). The
         orchestrator marks these moments needs_review=true via the
         confidence score so the coach overrides them.

    Args:
        fen_before:    position before the user's move.
        fen_after:     position after the user's move (kept for signature
                       back-compat; not currently read).
        move_uci:      the user's move in UCI form.
        user_color:    'white' or 'black'.
        moment_context: kept for signature back-compat. We no longer
                       feed it to an LLM.
        best_move_san: Stockfish's recommended move in SAN. Powers the
                       engine fallback line; also passed to the
                       dispatcher so its templates can name the saving
                       move.

    Returns:
        DecryptionResult — never None for valid input. (Returns None
        only when the move can't be parsed against fen_before, which
        is a data error.)
    """
    # Resolve the user's SAN from UCI. Without this we can't run the
    # dispatcher (which keys on SAN).
    user_san = None
    try:
        b = chess.Board(fen_before)
        m = chess.Move.from_uci(move_uci)
        if m in b.legal_moves:
            user_san = b.san(m)
    except Exception as e:
        logger.warning(f"[decryption] cannot parse user move {move_uci} on {fen_before}: {e}")
        return None

    # Path 1: concept dispatcher — deterministic templates only.
    if user_san:
        try:
            from .concept_dispatcher import caption_for_moment
            caption, meta = caption_for_moment(
                fen_before=fen_before,
                user_move_san=user_san,
                best_move_san=best_move_san,
                pv_after_best=pv_after_best,
                user_color=user_color,
            )
            if caption:
                pattern = (meta or {}).get("pattern_type") or "concept"
                return DecryptionResult(
                    text=caption,
                    source=f"template:{pattern}",
                    attempts=0,
                    delta_present=True,
                )
        except Exception as e:
            logger.warning(f"[decryption] dispatcher failed: {e}")

    # Path 2: engine fallback. Always safe — single sentence, single
    # variable (best_move_san) which is Stockfish-verified.
    return DecryptionResult(
        text=engine_fallback_text(best_move_san),
        source="engine_fallback",
        attempts=0,
        delta_present=True,
    )
