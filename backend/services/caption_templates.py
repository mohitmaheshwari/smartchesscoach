"""
Caption Templates — JSON-driven content layer for caption text.

ARCHITECTURE PRINCIPLE (Mohit 2026-05-20):
  No user-facing strings live in Python. Every caption phrase, severity
  word, opening/trap/principle blurb is authored in JSON files under
  `backend/data/captions/`. Python only loads, dispatches, and substitutes.

  Mohit + Parth own the JSON. Adding a new opening, trap, or rephrasing
  a caption is a JSON edit — no Python diff, no Claude session.

File layout:
  backend/data/captions/
    R10_threat.json
    R12_blunder.json
    ...

Each file is one rule's content. Schema:

  {
    "rule_name": "R10_threat",
    "description": "what this rule fires on (for the author)",
    "fact_glossary": { "<fact_name>": "<human description>", ... },
    "requires": ["fact_a", "fact_b"],
    "variants": {
      "default": "template string with {fact_a} {fact_b}",
      ...
    }
  }

Runtime behavior (Mohit-locked):
  - Missing fact in `requires` → render returns None → caller falls
    through to next-priority rule. Never crash, never render a literal
    `{placeholder}` to the user. Silence > broken.
  - First-load is cached in-process. To pick up edits in a running
    container, call `reload_templates()` (used by tests + dev tools).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CAPTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "captions")

_CAPTION_TEMPLATES: Optional[Dict[str, Dict[str, Any]]] = None


def _load_all() -> Dict[str, Dict[str, Any]]:
    global _CAPTION_TEMPLATES
    if _CAPTION_TEMPLATES is not None:
        return _CAPTION_TEMPLATES
    out: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(CAPTIONS_DIR):
        logger.warning(f"[caption_templates] dir missing: {CAPTIONS_DIR}")
        _CAPTION_TEMPLATES = out
        return out
    for fname in sorted(os.listdir(CAPTIONS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CAPTIONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as exc:
            logger.warning(f"[caption_templates] failed to load {fname}: {exc}")
            continue
        rule_name = data.get("rule_name")
        if not rule_name:
            logger.warning(f"[caption_templates] {fname} missing rule_name")
            continue
        out[rule_name] = data
    _CAPTION_TEMPLATES = out
    logger.info(f"[caption_templates] loaded {len(out)} rule files from {CAPTIONS_DIR}")
    return out


def reload_templates() -> None:
    global _CAPTION_TEMPLATES
    _CAPTION_TEMPLATES = None
    _load_all()


def render_template(
    rule_name: str, variant: str, facts: Dict[str, Any]
) -> Optional[str]:
    """Look up a rule's template, substitute facts, return rendered text.

    Returns None on any failure — rule_name missing, variant missing,
    required fact missing, or .format() raises. Caller treats None as
    'this rule had nothing to say' and falls through to next priority.
    """
    cfg = _load_all().get(rule_name)
    if not cfg:
        return None
    variants = cfg.get("variants") or {}
    template = variants.get(variant)
    if not template:
        return None
    required = cfg.get("requires") or []
    for key in required:
        if facts.get(key) is None or facts.get(key) == "":
            return None
    try:
        return template.format(**facts)
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning(
            f"[caption_templates] {rule_name}/{variant} render failed: {exc}"
        )
        return None
