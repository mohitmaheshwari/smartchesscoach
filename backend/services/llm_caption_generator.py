"""
LLM Caption Generator — compact prompt + resolved-focus contract.

Architecture (after 2026-05-15 refactor):
  1. caption_priority_resolver.resolve_priority(move) → decides ONE focus
     in pure Python (was: 9 LLM branches with collision)
  2. This module: builds a SMALL prompt for the resolved focus and
     calls gpt-4.1-mini
  3. caption_verifier.verify_caption(...) → strips hallucinated
     opening / shape / move / advice-tail residues

Prompt size: ~800 chars (was 21K). One focus branch instead of nine.
Per-call cost: ~$0.0002 (was ~$0.0005).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional

from llm_service import call_llm
from services.coach_voice_prompt import COACH_VOICE_RULES
from services.caption_priority_resolver import (
    resolve_priority,
    TEACHING_SEVERITIES,
)
from services.caption_verifier import verify_caption
from services.trap_recognition import detect_trap_setup, match_trap_line_step
from services.opening_lookup import match_opening_for_mover

logger = logging.getLogger(__name__)


# Compact voice block — distilled from the 65-line coach voice rules to
# the 4 hard rules that matter for one-shot caption generation. The
# full canonical rules still live in services/coach_voice_prompt.py;
# this is the inline reminder for the LLM.
_VOICE_BLOCK = """You are a smart chess friend writing ONE coaching sentence for a 600-1500 rated player.

VOICE: short, concrete, names the move and the square. Use contractions.
RULES (each one fails the task):
  1. Max 18 words. One sentence.
  2. No engine talk: no cp, no eval, no "centipawns", no "%".
  3. No generic praise: "Nice!", "Great move!", "Well done!".
  4. No advice tail: never end with "consider", "try", "focus on", "watch for", "should", "be careful", "remember to"."""


# Focus-specific framing. Each block is small and tells the LLM EXACTLY
# what to do for that focus. The LLM never sees the other branches.
_FOCUS_BLOCKS = {
    "trap":
        "FOCUS — TRAP. Name the trap by its anchor. State the IDEA in the rest of the sentence.\n"
        "  Form: \"{move} — {anchor}. {one-clause idea}.\"\n"
        "  Example: \"Nd4 — Blackburne Shilling Gambit. The e5 pawn is bait; if they grab, Qg5! wins.\"",

    "shape":
        "FOCUS — SHAPE PATTERN. Name the pattern (anchor). Describe what this move does using the pattern's idea.\n"
        "  Form: \"{move} — {anchor}. {what fires}.\"\n"
        "  Example: \"Qxh1+ — Free Piece. Their rook on h1 had no defender.\"",

    "principle":
        "FOCUS — PRINCIPLE. Name the principle (anchor) and describe the specific issue on the board.\n"
        "  Form: \"{move} — {anchor}: {specific fact}.\"\n"
        "  Example: \"Nd4 — Loose piece on the board: black knight on d4 has no defender.\"",

    "opening":
        "FOCUS — OPENING. Name the opening (anchor) and say what THIS move does in the opening's plan.\n"
        "  Form: \"{move} — {anchor}. {role of this move}.\"\n"
        "  Example: \"c5 — Caro-Kann Defense. Challenges white's d4 pawn directly.\"",

    "mistake":
        "FOCUS — MISTAKE. Name what went wrong with the played move (anchor = 'Mistake' / 'Blunder'). Suggest the engine's best.\n"
        "  Form: \"{move} {what went wrong}; better was {best}.\"\n"
        "  Example: \"Ng4+ blunders the knight; better was Qf3+ keeping pressure.\"",

    "category":
        "FOCUS — POSITION. Describe what this move does on the board, using the anchor as a guide.\n"
        "  Form: \"{move} {what it does}.\"\n"
        "  Example: \"e4 claims the centre and opens lines for the bishop.\"",
}


@lru_cache(maxsize=2)
def _build_voice_prompt(_dummy: bool = False) -> str:
    """The Coach Voice rules live in shared module; here we just embed
    the compact 4-rule block. The full rules can be enabled by setting
    use_full_voice=True (not currently used).
    """
    return _VOICE_BLOCK


def build_user_prompt(decision: Dict[str, Any]) -> str:
    """Tight per-move prompt body. Whitelists the entities the LLM may
    name; everything else is implicitly disallowed (verifier strips it).
    """
    focus = decision.get("focus", "empty")
    move = decision.get("move_played", "")
    anchor = decision.get("anchor_name") or ""
    detail = decision.get("anchor_detail") or ""
    allowed_moves = decision.get("allowed_moves") or []
    allowed_pieces = decision.get("allowed_pieces") or []
    voice_hint = decision.get("voice_hint", "observe")
    perspective = decision.get("perspective", "user")

    focus_block = _FOCUS_BLOCKS.get(focus, "")

    perspective_line = (
        "PERSPECTIVE: this is the user's move — use 'you/your' when relevant."
        if perspective == "user"
        else "PERSPECTIVE: this is the OPPONENT's move — use 'they/their' when naming their pieces. Never 'you/your'."
    )

    voice_line = {
        "praise":   "TONE: positive — acknowledge a well-played move, but only specifically (name the principle/shape/idea).",
        "critique": "TONE: critical — explain the problem with the move, with the fact.",
        "observe":  "TONE: neutral observation — describe what just happened.",
    }.get(voice_hint, "TONE: neutral.")

    allowed_pieces_line = (
        f"Pieces/squares: {', '.join(allowed_pieces)}"
        if allowed_pieces else "Pieces/squares: (none specified — keep general)"
    )

    return f"""{focus_block}

{perspective_line}
{voice_line}

GROUND TRUTH for this move:
  Move:    {move}
  Anchor:  {anchor}
  Detail:  {detail}

YOU MAY MENTION ONLY THESE ENTITIES:
  Moves: {', '.join(allowed_moves) if allowed_moves else move}
  {allowed_pieces_line}

Output the sentence. Nothing else. No labels, no quotes."""


def _retry_seconds_from_error(err_text: str) -> Optional[float]:
    """OpenAI 429 messages embed 'Please try again in X.YYYs'."""
    m = re.search(r"try again in ([\d.]+)s", err_text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


async def call_with_retry(
    sys_prompt: str,
    user_prompt: str,
    model: str = "gpt-4.1-mini",
    max_attempts: int = 8,
    max_tokens: int = 80,
) -> str:
    """Call the LLM with retry-on-429."""
    last_err: Optional[Exception] = None
    delay = 2.0
    for attempt in range(1, max_attempts + 1):
        try:
            out = await call_llm(
                system_message=sys_prompt,
                user_message=user_prompt,
                model=model,
                max_tokens=max_tokens,
            )
            return (out or "").strip().strip('"').strip("'")
        except Exception as e:
            last_err = e
            err_text = str(e)
            if "rate_limit" in err_text or "429" in err_text:
                suggested = _retry_seconds_from_error(err_text)
                if attempt >= 4:
                    wait = max(suggested or 0, 30.0)
                else:
                    wait = (suggested + 0.5) if suggested else delay
                print(f"[llm-cap] rate limit on attempt {attempt}/{max_attempts}, waiting {wait:.1f}s",
                      file=sys.stderr)
                await asyncio.sleep(wait)
                delay = min(delay * 2, 60)
                continue
            return f"[ERROR: {e}]"
    return f"[ERROR after {max_attempts} attempts: {last_err}]"


# ───────────────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────────────


def has_teaching_signal(move: Dict[str, Any]) -> bool:
    """Decide whether to even call the LLM. Delegates to the priority
    resolver — same source of truth used to build the prompt.
    """
    decision = resolve_priority(move)
    return not decision.get("should_skip")


def annotate_runtime_facts(moves: List[Dict[str, Any]]) -> None:
    """In-place: walk `moves` and attach `_trap` and `_opening` runtime
    annotations to each. Unchanged from the prior implementation.
    """
    played_san_so_far: List[str] = []
    active_trap: Optional[Dict[str, Any]] = None
    active_trap_step_cursor: int = 0
    active_trap_setup_completed_by_user: Optional[bool] = None

    for m in moves:
        san = m.get("move_san")
        if not san:
            continue
        played_san_so_far.append(san)

        mover_color = "white" if m.get("is_white") else "black"
        opening_match = match_opening_for_mover(played_san_so_far, mover_color)
        if opening_match:
            m["_opening"] = opening_match

        if active_trap is None:
            hit = detect_trap_setup(played_san_so_far)
            if hit:
                active_trap = hit
                active_trap_setup_completed_by_user = bool(m.get("is_user_move"))
                active_trap_step_cursor = 0
                m["_trap"] = {
                    "name": hit["name"],
                    "family": hit["family"],
                    "description": hit["description"],
                    "step": 0,
                    "step_label": "setup_completed",
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(m.get("is_user_move")),
                    "next_expected_move": hit["trap_line"][0] if hit["trap_line"] else None,
                }
        else:
            step_index = active_trap_step_cursor
            if match_trap_line_step(active_trap, san, step_index):
                step_label = "victim_falls" if step_index % 2 == 0 else "trap_player_punishes"
                step_expl = ""
                if step_index < len(active_trap.get("trap_line_steps") or []):
                    step_expl = active_trap["trap_line_steps"][step_index].get("explanation", "")
                next_mv = None
                if step_index + 1 < len(active_trap["trap_line"]):
                    next_mv = active_trap["trap_line"][step_index + 1]
                m["_trap"] = {
                    "name": active_trap["name"],
                    "family": active_trap["family"],
                    "description": active_trap["description"],
                    "step": step_index + 1,
                    "step_label": step_label,
                    "step_explanation": step_expl,
                    "completed_by_user": active_trap_setup_completed_by_user,
                    "this_move_by_user": bool(m.get("is_user_move")),
                    "next_expected_move": next_mv,
                }
                active_trap_step_cursor = step_index + 1
                if active_trap_step_cursor >= len(active_trap["trap_line"]):
                    active_trap = None
                    active_trap_step_cursor = 0
            else:
                active_trap = None
                active_trap_step_cursor = 0


def build_system_prompt(include_shape_catalog: bool = True) -> str:
    """Backward-compat shim. Returns the new compact voice prompt.
    The include_shape_catalog flag is ignored — the catalog isn't needed
    in the compact prompt because the resolver passes a single anchor.
    """
    return _build_voice_prompt(False)


async def generate_caption_for_move(
    move: Dict[str, Any],
    sys_prompt: Optional[str] = None,
    model: str = "gpt-4.1-mini",
) -> str:
    """End-to-end per-move flow.

    1. resolve_priority(move) decides the focus
    2. If should_skip → return empty
    3. Build a compact user prompt around the focus + whitelist
    4. Call the LLM with the compact voice system prompt
    5. Pass through caption_verifier to strip residual hallucinations
    """
    decision = resolve_priority(move)
    if decision["should_skip"]:
        return ""

    sys_text = _build_voice_prompt(False)
    user_text = build_user_prompt(decision)

    raw = await call_with_retry(sys_text, user_text, model=model)
    return verify_caption(raw, decision)


def build_move_facts(move: Dict[str, Any]) -> Dict[str, Any]:
    """Kept for backward-compat callers that still inspect the facts
    dict (test_llm_captions.py prints `facts: ...` for debugging).
    Returns the resolver's decision dict instead of the legacy
    facts-shape dict — the contract callers care about.
    """
    return resolve_priority(move)
