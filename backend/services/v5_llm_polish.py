"""V5 LLM Polish Service — Mohit 2026-05-22

LLM as COPYWRITER, not chess engine. Takes a deterministic caption +
structured facts and rewrites the prose in coach voice without inventing
any new chess content.

Key principles (per memory rule feedback_renderer_never_computes_chess_meaning):
1. LLM is ONLY a language translator — all chess content comes from
   the deterministic detector layer upstream.
2. Output must contain only chess nouns present in the structured facts
   or the base caption. A verifier post-check enforces this.
3. If the LLM output violates the constraint, fall back to the base
   caption silently. Never serve hallucinated chess to the user.
4. Pre-computed at game-analysis time, stored alongside the base caption
   in mongo. Zero latency at read time.

Usage:
    from services.v5_llm_polish import polish_caption_async

    polished = await polish_caption_async(
        facts={
            "played_san": "a5",
            "best_move_san": "Qe7",
            "defended_piece": "knight",
            "defended_square": "b4",
            ...
        },
        base_caption="a5 is a mistake. Qe7 was better — it defends ...",
        pattern_family="active_defense",
    )

    # polished is either the rewritten string OR None (verifier rejected
    # the LLM output — caller falls back to base_caption).
"""
from __future__ import annotations

import os
import re
import logging
from typing import Any, Dict, Optional

from llm_service import call_llm

logger = logging.getLogger(__name__)

# Default model — GPT-4.1-mini is strictly better than 4o-mini for
# instruction-following (esp. "do not invent X" constraints) and only
# marginally more expensive. Configurable via env if needed.
POLISH_MODEL = os.environ.get("V5_POLISH_MODEL", "gpt-4.1-mini")
# Mohit 2026-05-27: "we don't want to use LLM at this stage right now,
# in review as well … i don't want to use LLM." The LLM polish layer
# is DISABLED by default. The deterministic R12/R17/R18 caption from
# build_move_teaching_decision is the only text the user sees.
# polish_caption_async now returns None unless someone explicitly sets
# V5_POLISH_ENABLED=true (kept as an escape hatch, not a default).
# Per [[one-source-of-truth-for-coaching]] + [[llm-as-controlled-narrator]].
POLISH_ENABLED = os.environ.get("V5_POLISH_ENABLED", "false").lower() in ("true", "1", "yes")


SYSTEM_PROMPT = """You are polishing a chess coaching caption for a 600-1500 rated player.

You are a REWRITER, not an author. The chess analysis was done upstream by an engine + deterministic detectors. Your job is to make the prose flow naturally in a patient coaching voice while preserving every chess fact exactly.

Voice target: patient, direct coach. Warm but not saccharine. No exclamation marks. No "great!" / "amazing!". Trust the student.

HARD RULES — violating these fails the task:
1. DO NOT name any chess move, square, piece, or tactic NOT present in the input. The whitelist is: every chess noun in the structured facts and the base caption. Nothing else.
2. DO NOT predict what happens after the engine's best move beyond what the input already says.
3. DO NOT invent threats, captures, mates, or follow-ups not in the input.
4. DO NOT use chess jargon (fianchetto, prophylaxis, zwischenzug, en prise). Name squares concretely.
5. Output 1-3 short sentences. Same teaching structure as the base caption.
6. Output ONLY the rewritten caption text. No preface, no explanation, no quotes."""


def _build_user_prompt(facts: Dict[str, Any], base_caption: str, pattern_family: Optional[str]) -> str:
    """Render the structured facts + base caption as the user message."""
    lines = ["STRUCTURED FACTS (whitelist of chess nouns you may use):"]
    # Pick the chess-noun-bearing facts; skip booleans, ints, internal flags
    skip_keys = {
        "mover_is_user", "best_move_san_differs", "cp_loss", "is_white",
        "why_clause", "why_clause_em_dash", "user_is_winning",
        "user_is_losing", "needs_acknowledgment", "already_acknowledged",
        "is_best_move", "phase", "move_number", "severity_phrase",
        "pieces_now_undefended_present", "opp_reply_attacks_played_piece",
        "is_exchange_losing", "opp_pieces_now_undefended_present",
        "opp_played_landed_unsafe", "opp_reply_san_is_check",
        "user_best_reply_san_is_forcing", "position_was_already_losing",
    }
    for key, value in sorted(facts.items()):
        if key in skip_keys:
            continue
        if value is None or value is False:
            continue
        if isinstance(value, (list, dict)):
            continue
        lines.append(f"  {key}: {value}")
    if pattern_family:
        lines.append(f"  pattern_family: {pattern_family}")
    lines.append("")
    lines.append("BASE CAPTION (fact-verified, deterministic):")
    lines.append(f"  {base_caption}")
    lines.append("")
    lines.append("Rewrite the BASE CAPTION in a warmer, more natural coaching voice. "
                 "Keep every chess noun (moves, squares, pieces) EXACTLY as they appear. "
                 "Do NOT introduce any new chess content. 1-3 sentences. "
                 "Output ONLY the rewritten caption text.")
    return "\n".join(lines)


# Regex patterns for chess tokens in the LLM output. We use these to
# verify the LLM didn't sneak in new content.
_SAN_PATTERN = re.compile(
    r"\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b"
)
_SQUARE_PATTERN = re.compile(r"\b[a-h][1-8]\b")
_PIECE_PATTERN = re.compile(
    r"\b(?:knight|bishop|rook|queen|king|pawn|knights|bishops|rooks|queens|kings|pawns)\b",
    re.IGNORECASE,
)


def _collect_chess_tokens(text: str) -> Dict[str, set]:
    """Extract chess tokens from a string. Returns SAN moves, squares, piece names."""
    return {
        "san": set(_SAN_PATTERN.findall(text)),
        "squares": set(_SQUARE_PATTERN.findall(text.lower())),
        "pieces": set(t.lower().rstrip("s") for t in _PIECE_PATTERN.findall(text)),
    }


def _verify_no_new_chess(polished: str, facts: Dict[str, Any], base_caption: str) -> bool:
    """Reject if the LLM output mentions a chess move/square/piece not in
    the input facts or the base caption. Returns True if safe to use."""
    # Build whitelist from facts + base caption
    whitelist_text = base_caption + " " + " ".join(
        str(v) for v in facts.values() if isinstance(v, (str, int)) and v
    )
    allowed = _collect_chess_tokens(whitelist_text)

    polished_tokens = _collect_chess_tokens(polished)

    # SAN moves: every polished SAN must be in the allowed SAN set OR
    # in the allowed squares set (squares like "e4" can match both).
    for san in polished_tokens["san"]:
        if san in allowed["san"]:
            continue
        # Some squares look like SAN (e.g., "e4"). Allow if it's a known square.
        if san.lower() in allowed["squares"]:
            continue
        logger.info(f"[polish] reject: SAN '{san}' not in whitelist")
        return False
    # Squares: every polished square must be in allowed squares
    for sq in polished_tokens["squares"]:
        if sq not in allowed["squares"]:
            logger.info(f"[polish] reject: square '{sq}' not in whitelist")
            return False
    # Pieces: every polished piece-name must be in allowed pieces.
    # (Common pieces like 'king' are usually in the base caption already
    # for any caption mentioning the king; pieces 'pawn' etc. similar.)
    for piece in polished_tokens["pieces"]:
        if piece not in allowed["pieces"]:
            logger.info(f"[polish] reject: piece '{piece}' not in whitelist")
            return False
    return True


def _llm_available() -> bool:
    """True if the model's API key is present in env."""
    if POLISH_MODEL.startswith("claude"):
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY"))


# Above this the LLM stops being safe even on a quiet position. Picked
# from the distribution, never from instinct -- see llm_may_write.
BLUNDER_CP = 300


def llm_may_write(
    *,
    best_move_san: Optional[str],
    fen_before: Optional[str],
    cp_loss: Optional[int],
) -> bool:
    """Is this the kind of card the model is actually good at?

    Mohit 2026-10-27: "straight up blunders and all are easy to capture
    with templates and we are already doing that, but positions which
    don't make sense, why something was an inaccuracy, endgames, where
    captions and templates can't justify stockfish, i need my engine and
    LLM to work there."

    He was right, and the split is sharper than the hypothesis. Measured
    over 316 user mistake cards from 55 games, scoring every caption with
    narrator_claim_verifier.verify_caption(strict_v2=True) -- the board
    deciding, not a word count:

        cause        cp band    n    LLM clean   added a new square
        quiet        100-199   141        95%           23%
        quiet        200-299    33       100%           18%
        quiet        300+       59        81%           15%
        mechanical   100-199    36        87%           19%
        mechanical   200-299    16        69%            6%
        mechanical   300+       31        48%           10%

    So the model is dangerous exactly where templates already work. Its
    failures on mechanical cards are `piece_on_square` and
    `free_when_defended` -- claiming a piece sits where it does not, or
    that a defended piece is free. That is invented board fact, the one
    class a better prompt cannot fix, so it has to be gated instead.

    The gate is `quiet AND under 300cp`: 142 of 148 clean, 96%, on 174 of
    the 316 cards. Two clauses rather than one because quiet-and-300+
    drops to 81%, well below the 95-100% of the band this admits.

    "Quiet" means the ENGINE's best move neither captures nor checks, so
    there is no concrete cause for a template to name. It is read off the
    position, never off rule_name, which is a knob.

    Fails CLOSED. An unparseable position returns False, because the
    expensive mistake is polishing a mechanical card, not skipping one.
    """
    try:
        cp = int(cp_loss) if cp_loss is not None else None
    except (TypeError, ValueError):
        return False
    if cp is None or cp >= BLUNDER_CP:
        return False
    if not fen_before or not best_move_san:
        return False
    try:
        import chess
        board = chess.Board(str(fen_before))
        best = board.parse_san(str(best_move_san))
        after = board.copy()
        after.push(best)
        return not (board.is_capture(best) or after.is_check())
    except Exception:
        return False


async def polish_caption_async(
    facts: Dict[str, Any],
    base_caption: str,
    pattern_family: Optional[str] = None,
) -> Optional[str]:
    """Polish the base caption with the LLM. Returns the polished string
    if the verifier accepts it; returns None otherwise (caller falls
    back to base_caption)."""
    if not POLISH_ENABLED:
        return None
    if not _llm_available():
        return None
    if not base_caption or not base_caption.strip():
        return None
    try:
        user_prompt = _build_user_prompt(facts, base_caption, pattern_family)
        polished = await call_llm(
            system_message=SYSTEM_PROMPT,
            user_message=user_prompt,
            model=POLISH_MODEL,
            max_tokens=200,
        )
    except Exception as exc:
        logger.warning(f"[polish] LLM call failed: {exc}")
        return None

    if not polished or not polished.strip():
        return None
    polished = polished.strip()
    # Strip leading/trailing quotes if the LLM wrapped its output
    if polished.startswith('"') and polished.endswith('"'):
        polished = polished[1:-1].strip()

    if not _verify_no_new_chess(polished, facts, base_caption):
        return None
    return polished
