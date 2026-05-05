"""
Decryption generator — produces the "Show me why" text shown when the
user expands the Truth headline.

Strict separation from Truth: this module never sees Truth output, never
reads Truth pools, never shares prompt or input. Truth and Decryption
are two different speech acts (Coach Voice vs Decryption Voice).

Pipeline:
    fen_before + fen_after + move → position_delta (deterministic facts)
                                  → LLM prompt with locked Voice rules
                                  → validator pass (geometry + felt + why)
                                  → retry up to MAX_RETRIES on failure
                                  → safe template fallback if still bad

Output: a single 3–4-sentence prose block, ≤80 words, validated against
project_decryption_voice.md rules in code (not just prompt).
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .position_delta import compute_position_delta, format_delta_for_prompt
from .validators import validate_decryption

logger = logging.getLogger(__name__)


# How many LLM regenerations before falling back to template.
MAX_RETRIES = 2


# ── System prompt — the locked Decryption Voice ──────────────────────
# Prompt discipline alone does not hold (we hard-validate after).
# But the prompt encodes the rules so the first attempt is usually clean.

DECRYPTION_SYSTEM_PROMPT = """You write short chess decryptions for players rated 600–1500, mostly in India. Easy spoken English. Short sentences. No idioms.

You are a coach naming three things:
  1. What the opponent's plan was.
  2. What move the player missed (the saving / winning move).
  3. What that missed move would have done — name the next move or two of the line.

You NEVER tell the player what they did wrong. You describe what was happening on the board, and the rescue line they didn't see.

# Hard rules (every output must satisfy ALL):

0. STRICT GROUNDING. ONLY name pieces and squares listed in the facts. The facts include "USER pieces on the board" and "OPPONENT pieces on the board" — do NOT mention any piece or square that is not in those lists. Do NOT invent positions. Do NOT guess where the kings are. If the facts don't list a piece, it isn't on the board.

1. Translate the board, not the engine. Never mention centipawns, evaluation, Stockfish, "best move was X", accuracy %.

2. Name a specific piece, square, or file. Use real geometry (their bishop on g5, the d-file, your king on h1) — but only the ones from the facts.

3. NAME THE MISSED LINE. If the facts give you the user's missed move and the line that follows, USE IT. "Kd6 would have used it: your king reaches e7 next move and parks in front of their pawn." This is the difference between a chess.com clone and real coaching.

4. Easy Indian English. Short subject-verb-object sentences (max ~12 words). NO American idioms ("dies on the board", "smell a win", "run with it", "off the rails", "clean game", "got hosed"). Plain spoken words.

5. Each sentence must advance the position. No filler. No rephrasing. If a sentence doesn't add a new fact about pieces, squares, plans, or lines — cut it.

6. Plain words a 1100 player uses. No "tactically", "positionally", "strategically", "compensation", "initiative", "pressure", "advantage", "strong move", "dynamic", "harmonious".

7. End on the cause, not the verdict. Don't say "and that's why you lost." Say what made it inevitable.

8. Do NOT explain the move the user played. Explain what was happening, what the line was, what they missed.

# Length

3 to 4 sentences. ≤ 80 words total. Hard caps.

# Structure (use exactly these three beats, in order)

- Sentence 1: WHAT WAS HAPPENING on the board that the user's move ran into.
  Describe the opponent's piece + square + what it was pointed at, OR what
  the opponent JUST played and what it threatens. Plain Indian English, no idioms.
  NEVER start with "Your rook moved" or "You played X" — that narrates the move; we ban that.
  Example GOOD: "Their queen on a5 was already pointing at d8."
  Example GOOD: "Their pawn pushed to e6 to attack your king."
  Example BAD: "Your rook moved from b8 to d8."

- Sentence 2: NAME THE MISSED MOVE AND THE LINE.
  If the facts list a "USER's MISSED MOVE" — name it. If they list "the line
  that would have followed" — name the next move or two of that line. This is
  the rescue plan the player didn't see.

  Example GOOD: "Kd6 would have used the open d-file. Your king reaches e7 next move
  and stops their pawn."
  Example GOOD: "Qb6+ was sitting there. After the check, you trade queens and you're up a rook."
  Example BAD: "Your rook was attacked." (no missed move, no rescue line)
  Example BAD: "A better move was available." (vague — name it)

- Sentence 3: WHY THE MISSED MOVE WORKED, OR WHY THE PLAYED MOVE FAILED.
  Causality required ("because", "with no", "couldn't", "stops", "blocks", "they could not").
  Stay grounded in what's on the board.

  Example GOOD: "With your king on e7, their pawn cannot promote without a defender."
  Example GOOD: "Their king was on the wrong side, so they could not catch your pawn."
  Example BAD: "The move was strong because it was strong." (circular)

- Optional Sentence 4: only if it adds a new concrete piece/square fact. Never a verdict.

# Tone

The smartest friend who plays better than you, telling the truth without making the player feel small. Direct. No softening, no praising, no "but you played well in the opening." Decryption is consequence.

# Output

Return ONLY the decryption text. No JSON, no headers, no preamble.
"""


# ── Safe fallback template ───────────────────────────────────────────
# Used when LLM fails validation MAX_RETRIES times. Generic but still
# in voice — better simple than broken-fancy.

def _safe_fallback_template(delta: Dict) -> str:
    md = (delta or {}).get("move_described") or {}
    piece = md.get("piece", "piece")
    to_sq = md.get("to_square", "")

    # Build a deliberately plain three-sentence block that still passes
    # validators (geometry: piece + square; player ref: "your"; causality:
    # "with nothing").
    sq_phrase = f" on {to_sq}" if to_sq else ""
    text = (
        f"Their move targeted your {piece}{sq_phrase}. "
        f"Your pieces had to defend, so they stopped attacking. "
        f"With nothing left to push back, the position fell apart."
    )
    return text


# ── LLM call ─────────────────────────────────────────────────────────

async def _call_llm(user_message: str) -> str:
    """Single LLM call. Uses the same emergent integrations the existing
    decryption service uses."""
    from llm_helper import LlmChat, UserMessage

    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No LLM API key configured (EMERGENT_LLM_KEY / OPENAI_API_KEY)")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"decryption-voice-{uuid.uuid4().hex[:8]}",
        system_message=DECRYPTION_SYSTEM_PROMPT,
    )
    # gpt-4o-mini is the canonical model in this stack (per CLAUDE.md).
    # The previous gpt-4.1-mini reference was inherited from the legacy
    # decryption service and isn't accessible on the production OpenAI
    # project.
    chat.with_model("openai", "gpt-4o-mini")
    return await chat.send_message(UserMessage(text=user_message))


def _build_user_message(
    delta: Dict,
    fen_before: str,
    user_color: str,
    moment_context: Optional[Dict] = None,
) -> str:
    """Build the user-message payload. Facts only — no engine evals,
    no best-move suggestion, no narrative hints. When moment_context
    is present, include the richer context (opponent's just-played
    move, user's missed move, the saving line) so the LLM can write
    real coaching prose instead of just describing one piece's fate.
    """
    parts = [
        f"User color: {user_color}",
        f"Position before the move (FEN): {fen_before}",
        "",
        "Concrete delta facts (what changed):",
        format_delta_for_prompt(delta),
    ]
    if moment_context:
        from .moment_context import format_moment_context_for_prompt
        ctx_text = format_moment_context_for_prompt(moment_context)
        if ctx_text:
            parts.extend([
                "",
                "Full moment context (USE these — name the opponent's plan, the missed move, and the line it would have led to):",
                ctx_text,
            ])
    parts.extend([
        "",
        "Write the decryption now (3 sentences, ≤80 words, the 3-beat structure). Easy spoken Indian English. Name the missed move and the line.",
    ])
    return "\n".join(parts)


# ── Public API ───────────────────────────────────────────────────────

@dataclass
class DecryptionResult:
    text: str
    source: str          # "llm" | "fallback_template"
    attempts: int
    delta_present: bool
    # Diagnostic — only populated when fallback fired. Captures every
    # LLM attempt that failed validation + the reason it was rejected,
    # so we can audit voice drift without grepping container logs.
    failed_attempts: Optional[List[Dict]] = None


async def generate_decryption(
    *,
    fen_before: str,
    fen_after: str,
    move_uci: str,
    user_color: str,
    moment_context: Optional[Dict] = None,
) -> Optional[DecryptionResult]:
    """Build a Decryption block for one critical move.

    Args:
        fen_before: position before the user's move.
        fen_after:  position after the user's move.
        move_uci:   the user's move in UCI form (e.g., "b8d8").
        user_color: "white" or "black".
        moment_context: optional richer context (opponent's just-played
            move, user's missed move, the saving line — see
            moment_context.build_moment_context). When present, the
            prompt produces real coaching prose instead of one-piece
            description.

    Returns:
        DecryptionResult or None if delta cannot be computed.
    """
    delta = compute_position_delta(fen_before, fen_after, move_uci, user_color)
    if not delta:
        return None

    user_msg = _build_user_message(delta, fen_before, user_color, moment_context)

    last_reason = ""
    text = ""
    failed_attempts: List[Dict] = []
    for attempt in range(1, MAX_RETRIES + 2):  # initial + MAX_RETRIES
        try:
            text = await _call_llm(user_msg)
        except Exception as e:
            logger.warning(f"[decryption] LLM call failed on attempt {attempt}: {e}")
            failed_attempts.append({"attempt": attempt, "text": "", "reason": f"LLM error: {e}"})
            break

        # Strip any wrapping quotes / markdown the model might add.
        text = text.strip().strip("`").strip("\"").strip()

        ok, reason = validate_decryption(text)
        if ok:
            return DecryptionResult(
                text=text, source="llm", attempts=attempt, delta_present=True
            )

        last_reason = reason
        failed_attempts.append({"attempt": attempt, "text": text, "reason": reason})
        logger.info(
            f"[decryption] attempt {attempt} rejected: {reason} | text='{text[:120]}...'"
        )
        # On retry, append the failure reason to the user message so the
        # model can correct (without leaking voice rules into Truth).
        user_msg = (
            user_msg
            + f"\n\nPrevious attempt rejected: {reason}. Fix this in the new output."
        )

    logger.warning(
        f"[decryption] all {MAX_RETRIES + 1} attempts failed (last: {last_reason}); "
        f"using safe fallback template"
    )
    fallback = _safe_fallback_template(delta)
    # Final safety: if even the template fails (shouldn't), flag for coach review.
    ok, reason = validate_decryption(fallback)
    if not ok:
        logger.error(f"[decryption] safe template ALSO invalid: {reason} — text='{fallback}'")
        return None

    return DecryptionResult(
        text=fallback,
        source="fallback_template",
        attempts=MAX_RETRIES + 1,
        delta_present=True,
        failed_attempts=failed_attempts,
    )
