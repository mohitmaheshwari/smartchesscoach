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
from services.severity_mismatch_guard import is_severity_mismatch
from services.caption_fallback_tiers import tier23_caption


def _tier23(facts: Dict[str, Any], silence_rule: str) -> CaptionOutput:
    """Never-silence floor: when no R-rule produced a caption, render a short
    TRUE-by-construction Tier-2/3 line instead of empty. See
    services/caption_fallback_tiers.py + memory feedback_coverage_is_first_class."""
    try:
        cap, rule = tier23_caption(facts)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[caption_renderer] tier23 fallback crashed: {exc}")
        cap, rule = "", silence_rule
    if not cap:
        return CaptionOutput(caption="", rule_name=silence_rule)
    return CaptionOutput(caption=_enforce_word_cap(cap), rule_name=rule)

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
        return _tier23(facts, "R_FALLBACK_no_primary")

    category = primary["category"]

    # Filter rules by category match. RULES is priority-sorted so first
    # match wins.
    candidates = [r for r in RULES if r.category == category]
    if not candidates:
        return _tier23(facts, "R_FALLBACK_no_rule_for_category")

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

                # Guard: suppress captions that praise a blunder (severity mismatch).
                # If caption has positive framing on a real blunder, suppress it and
                # fall through to a more honest template.
                if is_severity_mismatch(output.caption, facts.get("cp_loss"),
                                       is_user=facts.get("is_user_move", True)):
                    logger.debug(
                        f"[caption_renderer] severity_mismatch suppressed caption "
                        f"(cp_loss={facts.get('cp_loss')}): {output.caption}"
                    )
                    continue

                output.caption = _enforce_word_cap(output.caption)
                return output
        except Exception as exc:
            logger.warning(
                f"[caption_renderer] rule {rule.name} crashed: {exc}; falling through"
            )
            continue

    return _tier23(facts, "R_FALLBACK_no_trigger_fired")


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
