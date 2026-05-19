"""
Caption Renderer — picks one rule from `caption_rules.RULES`, applies
its render function, and returns a CaptionOutput.

Architecture laws (mechanically grep-checkable — see CI test below):

  L1. No `import chess`. No chess.Board. No parse_san. No engine calls.
  L2. The renderer NEVER inspects raw board state. Only the facts dict.
  L3. The renderer NEVER computes chess meaning. Selects + compresses.
  L4. The 25-word cap is enforced AFTER rule rendering. Rules should
      stay under it; the cap is a safety net.

Per design doc §3 + §7, and memory rule
`feedback_renderer_never_computes_chess_meaning.md`.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from services.caption_rules import RULES, CaptionOutput, Rule
from services.caption_config import MAX_CAPTION_WORDS

logger = logging.getLogger(__name__)


def render_caption(facts: Dict[str, Any]) -> CaptionOutput:
    """Pick a rule, render, enforce word cap, return.

    Selection logic:
      1. Read facts["primary_reason"]. If None, return silence.
      2. Filter RULES by category match.
      3. Among matching rules, take the lowest-priority one whose
         trigger returns True.
      4. Apply that rule's render function.
      5. Truncate caption to MAX_CAPTION_WORDS as a safety net.

    Output: a CaptionOutput with caption (str), highlight_squares (list),
    arrows (list of (from, to, color) tuples), rule_name (str).
    """
    primary = facts.get("primary_reason")
    if not primary or not primary.get("category"):
        return CaptionOutput(caption="", rule_name="R_FALLBACK_no_primary")

    category = primary["category"]

    # Filter rules by category match. RULES is priority-sorted so first
    # match wins.
    candidates = [r for r in RULES if r.category == category]
    if not candidates:
        return CaptionOutput(caption="", rule_name="R_FALLBACK_no_rule_for_category")

    for rule in candidates:
        try:
            if rule.trigger(facts):
                output = rule.render(facts)
                # A rule may return None or a CaptionOutput with an
                # empty caption to signal "I matched but have nothing
                # concrete to say." Per [[no-hollow-coverage]] / Parth
                # 2026-05-18 — honest silence > fluffy template. Fall
                # through to the next rule in priority order.
                if output is None or not output.caption:
                    continue
                output.caption = _enforce_word_cap(output.caption)
                return output
        except Exception as exc:
            logger.warning(
                f"[caption_renderer] rule {rule.name} crashed: {exc}; falling through"
            )
            continue

    return CaptionOutput(caption="", rule_name="R_FALLBACK_no_trigger_fired")


def _enforce_word_cap(caption: str) -> str:
    """Truncate to MAX_CAPTION_WORDS words. Hard cap — rules should
    self-limit but this is the safety net."""
    if not caption:
        return ""
    words = caption.split()
    if len(words) <= MAX_CAPTION_WORDS:
        return caption
    return " ".join(words[:MAX_CAPTION_WORDS]) + "…"


def render_caption_dict(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience: returns CaptionOutput as a plain dict for JSON
    serialization into the V5 move record."""
    output = render_caption(facts)
    return {
        "caption": output.caption,
        "rule_name": output.rule_name,
        "highlight_squares": list(output.highlight_squares),
        "arrows": [
            {"from": a[0], "to": a[1], "color": a[2]}
            for a in output.arrows
        ],
    }
