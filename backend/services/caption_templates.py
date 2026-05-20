"""Caption Templates — JSON-driven content + decision layer.

ARCHITECTURE PRINCIPLE (Mohit 2026-05-20):
  Both content AND coaching decisions live in JSON.
  Python loads JSON, evaluates predicates against the facts dict,
  picks variants, substitutes. It does not hardcode words, thresholds,
  priority orders, or branch logic for variant selection.

  Mohit + Parth author everything under `backend/data/captions/`.
  See README.md there for schema + authoring guide.

Three layers of authorable JSON:

  1. Templates — `variants.<key>` is the prose with `{placeholder}` slots.
  2. Decisions — `select_variant`, `severity_tiers`, `why_clauses_*`,
     `suppression` are predicate-based rule lists Python evaluates in
     order. First match wins.
  3. Dispatch order — `promotion_ladder.json` encodes the priority of
     opening/trap/shape/principle/basic_mistake promotions as data.

Predicate vocabulary (used inside `when` blocks):

  Equality (default):
    {"mover_is_user": false}            → facts["mover_is_user"] == false
    {"mover_is_user": "user"}           → facts["mover_is_user"] == "user"

  Presence:
    {"opp_reply_san": "present"}        → facts["opp_reply_san"] is truthy
    {"opp_reply_san": "absent"}         → facts["opp_reply_san"] is falsy

  Numeric:
    {"cp_loss": {"gte": 400}}           → facts["cp_loss"] >= 400
    {"cp_loss": {"lte": 20}}            → facts["cp_loss"] <= 20
    {"cp_loss": {"lt": 250}}            → facts["cp_loss"] < 250
    {"cp_loss": {"gt": 0}}              → facts["cp_loss"] > 0

  Membership:
    {"step_label": {"in": ["a", "b"]}}  → facts["step_label"] in [...]

  Dotted access for nested facts:
    {"trap_record.step_label": "setup_completed"}
                                        → facts["trap_record"]["step_label"]
                                          == "setup_completed"

  Multiple keys in one `when` → all must match (AND).

Runtime contract:
  - Missing predicate field → predicate evaluates to false.
  - Missing template / variant → render returns None → fallthrough.
  - Never crash, never render a literal `{placeholder}` to the user.
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
        # Absence of rule_name = "this file isn't a rule" (e.g. an
        # index / dispatch file like promotion_ladder.json). Skip
        # without complaining; its own loader handles it.
        rule_name = data.get("rule_name")
        if not rule_name:
            continue
        out[rule_name] = data
    _CAPTION_TEMPLATES = out
    logger.info(f"[caption_templates] loaded {len(out)} rule files from {CAPTIONS_DIR}")
    return out


def reload_templates() -> None:
    global _CAPTION_TEMPLATES
    _CAPTION_TEMPLATES = None
    _load_all()


# ────────────────────────────────────────────────────────────────────
# Predicate interpreter — evaluates `when` blocks against facts
# ────────────────────────────────────────────────────────────────────

def _get_dotted(facts: Dict[str, Any], path: str) -> Any:
    """Read a fact by dotted path: 'trap_record.step_label' walks dicts."""
    cur: Any = facts
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _eval_single(value: Any, expected: Any) -> bool:
    """Evaluate one predicate. `value` is the fact's value; `expected`
    is the JSON-authored expectation. Supports the 6 operators in the
    module docstring."""
    if isinstance(expected, dict):
        # Operator form: {"gte": N}, {"lte": N}, {"lt": N}, {"gt": N},
        # {"in": [...]}.
        for op, arg in expected.items():
            try:
                if op == "gte":
                    if value is None or not (value >= arg):
                        return False
                elif op == "lte":
                    if value is None or not (value <= arg):
                        return False
                elif op == "gt":
                    if value is None or not (value > arg):
                        return False
                elif op == "lt":
                    if value is None or not (value < arg):
                        return False
                elif op == "in":
                    if value not in (arg or []):
                        return False
                else:
                    logger.warning(f"[caption_templates] unknown op {op!r}")
                    return False
            except TypeError:
                return False
        return True
    if expected == "present":
        return bool(value)
    if expected == "absent":
        return not bool(value)
    return value == expected


def evaluate_when(when: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    """All keys in `when` must match (AND). Missing keys → no match."""
    if not when:
        return True
    for key, expected in when.items():
        value = _get_dotted(facts, key) if "." in key else facts.get(key)
        if not _eval_single(value, expected):
            return False
    return True


def select_first_match(rules: list, facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Walk a list of `{"when": {...}, ...}` entries; return the first
    whose `when` evaluates true against facts. An entry without `when`
    matches unconditionally (default fallback). Returns None if none match."""
    for entry in rules or []:
        when = entry.get("when") or {}
        if evaluate_when(when, facts):
            return entry
    return None


# ────────────────────────────────────────────────────────────────────
# Template rendering — substitute facts into a chosen variant
# ────────────────────────────────────────────────────────────────────

def render_template(
    rule_name: str, variant: str, facts: Dict[str, Any]
) -> Optional[str]:
    """Look up `variants[variant]` in the rule's JSON, substitute facts,
    return rendered text. Returns None when the rule, variant, or any
    `requires` fact is missing. Empty-string templates render as ''."""
    cfg = _load_all().get(rule_name)
    if not cfg:
        return None
    variants = cfg.get("variants") or {}
    if variant not in variants:
        return None
    template = variants[variant]
    if template == "":
        return ""
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


# ────────────────────────────────────────────────────────────────────
# High-level helpers — used by caption_rules + V5 service to keep
# the calling code free of variant-picking conditionals.
# ────────────────────────────────────────────────────────────────────

def resolve_severity_tier(rule_name: str, facts: Dict[str, Any]) -> Optional[str]:
    """Walk the rule's `severity_tiers` list, return the matched tier key
    (or None if no entry has a `tier` and no entry matches). Picks up
    `severity_phrases[tier]` for the caller to inject."""
    cfg = _load_all().get(rule_name) or {}
    tiers = cfg.get("severity_tiers") or []
    match = select_first_match(tiers, facts)
    return (match or {}).get("tier") if match else None


def resolve_severity_phrase(rule_name: str, facts: Dict[str, Any]) -> str:
    """Returns the authored severity adjective phrase ('is a mistake',
    'is a major blunder', ...) for the rule's severity tier given facts."""
    cfg = _load_all().get(rule_name) or {}
    tier = resolve_severity_tier(rule_name, facts)
    phrases = cfg.get("severity_phrases") or {}
    return phrases.get(tier or "", "")


def resolve_variant(rule_name: str, facts: Dict[str, Any]) -> Optional[str]:
    """Walk the rule's `select_variant` list, return the matched variant
    key. None when no entry matches."""
    cfg = _load_all().get(rule_name) or {}
    sel = cfg.get("select_variant") or []
    match = select_first_match(sel, facts)
    return (match or {}).get("variant")


def resolve_why_clause(
    rule_name: str, list_key: str, facts: Dict[str, Any]
) -> Optional[str]:
    """Walk the rule's `why_clauses_<side>` list, render the first
    matching variant against facts, return the text. None when no
    entry matches or the matched template fails to render."""
    cfg = _load_all().get(rule_name) or {}
    candidates = cfg.get(list_key) or []
    match = select_first_match(candidates, facts)
    if not match:
        return None
    variant = match.get("variant")
    if not variant:
        return None
    return render_template(rule_name, variant, facts)


def should_fire(rule_name: str, facts: Dict[str, Any]) -> bool:
    """Evaluate the rule's `trigger.when` block against facts.

    Rules without a `trigger` block return True (fire unconditionally
    — the rule's caller already gated it some other way). Otherwise
    every predicate in `trigger.when` must match for the rule to fire."""
    cfg = _load_all().get(rule_name) or {}
    trigger = cfg.get("trigger")
    if not trigger:
        return True
    return evaluate_when(trigger.get("when") or {}, facts)


def is_suppressed(rule_name: str, facts: Dict[str, Any]) -> bool:
    """Check if any `suppression` entry's `when` matches. Returns True
    to tell the caller 'render nothing for this move'."""
    cfg = _load_all().get(rule_name) or {}
    rules = cfg.get("suppression") or []
    for entry in rules:
        if evaluate_when(entry.get("when") or {}, facts):
            return True
    return False


# ────────────────────────────────────────────────────────────────────
# Generic rule renderer + promotion dispatcher
# ────────────────────────────────────────────────────────────────────

def render_rule(rule_name: str, facts: Dict[str, Any]) -> Optional[str]:
    """Render any rule with the full JSON-driven pipeline:

      1. Pre-compute severity_phrase if the rule has `severity_tiers`
         (injected into facts as `severity_phrase`).
      2. Pre-compute why_clause from `why_clauses_user`/`why_clauses_opp`
         when present (chosen by mover_is_user). Injected as `why_clause`.
      3. Check `suppression` — return None if any match.
      4. Pick the variant via `select_variant`.
      5. Render the variant template.

    Returns the caption text, or None when the rule has nothing to say.
    """
    cfg = _load_all().get(rule_name) or {}
    if not cfg:
        return None
    facts = dict(facts)  # don't mutate caller's dict

    if cfg.get("severity_tiers"):
        facts["severity_phrase"] = resolve_severity_phrase(rule_name, facts)

    if cfg.get("why_clauses_user") or cfg.get("why_clauses_opp"):
        side_key = "why_clauses_opp" if facts.get("mover_is_user") is False else "why_clauses_user"
        why = resolve_why_clause(rule_name, side_key, facts)
        facts["why_clause"] = why if why else None

    if is_suppressed(rule_name, facts):
        return None

    variant = resolve_variant(rule_name, facts)
    if not variant:
        # No select_variant block, or none matched → try "default".
        variant = "default"

    return render_template(rule_name, variant, facts)


_PROMOTION_LADDER: Optional[Dict[str, Any]] = None


def _load_promotion_ladder() -> Dict[str, Any]:
    """Load promotion_ladder.json once; cached."""
    global _PROMOTION_LADDER
    if _PROMOTION_LADDER is not None:
        return _PROMOTION_LADDER
    path = os.path.join(CAPTIONS_DIR, "promotion_ladder.json")
    if not os.path.isfile(path):
        _PROMOTION_LADDER = {}
        return _PROMOTION_LADDER
    try:
        with open(path, "r", encoding="utf-8") as fp:
            _PROMOTION_LADDER = json.load(fp)
    except Exception as exc:
        logger.warning(f"[caption_templates] promotion_ladder load failed: {exc}")
        _PROMOTION_LADDER = {}
    return _PROMOTION_LADDER


def reload_promotion_ladder() -> None:
    global _PROMOTION_LADDER
    _PROMOTION_LADDER = None
    _load_promotion_ladder()


def dispatch_promotion(facts: Dict[str, Any]):
    """Walk `promotion_ladder.json` priority list, find first matching
    entry, render its rule's caption, return (text, source_label) or
    (None, None) if nothing matches / nothing renders.

    Returns a Tuple[Optional[str], Optional[str]] — the caption text
    and the source label that should be written into the move record's
    `rule_name` suffix (after the R-rule layer's contribution)."""
    ladder = _load_promotion_ladder()
    priority = ladder.get("priority") or []
    for entry in priority:
        when = entry.get("when") or {}
        if not evaluate_when(when, facts):
            continue
        rule_name = entry.get("rule")
        if not rule_name:
            continue
        text = render_rule(rule_name, facts)
        if not text:
            continue
        source_tmpl = entry.get("source_template") or rule_name
        try:
            source = source_tmpl.format(**facts)
        except (KeyError, IndexError, ValueError):
            source = rule_name
        return text, source
    return None, None
