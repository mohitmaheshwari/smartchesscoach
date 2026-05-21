"""Shared classifier — auto-loads every caption variant from
backend/data/captions/*.json, converts each template to a regex, and
classifies move-record captions by (file, variant, tier).

Used by:
  - backend/scripts/caption_coverage_v5.py (CLI audit)
  - backend/routes/caption_authoring.py (web UI audit endpoint)

Single source of truth for the regex tier mapping. When you author a
new variant in a JSON file, the classifier picks it up automatically
on next reload — no Python edit needed.

Tier definitions (Mohit-locked):
  HIGH — names a specific tactical/strategic concept (mate-in-N,
         piece-win, opening name, trap name, clearance-for-attack,
         king-pawn weakness, named tactic like pin/skewer/fork).
  MID  — concrete chess observation but not named (threats, captures,
         castling, check, opening pawn pushes, "engine's pick" praise).
  LOW  — generic fallback prose that should be improved (e.g.
         'wins material in the resulting line', 'Opponent's strongest
         reply: X', basic_mistake severity-only).
  NONE — no variant matched the caption (bare severity from R12 with
         no why-clause) or no caption at all (R_FALLBACK silence).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


CAPTIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "captions",
)

# Files in CAPTIONS_DIR that are NOT rule template files (have no
# `variants` block, or are metadata).
_SKIP_FILES = {"promotion_ladder.json", "caption_config.json"}


def _classify_tier(variant_key: str, file_name: str) -> str:
    """Tier classification per (variant, file).

    Edit here when the tier philosophy shifts. The mapping below is a
    one-time judgement on each rule's pedagogical value:
      - Tactical names (mate, forks, pins, skewers, clearance, missed
        piece) → HIGH
      - Named opening / trap / shape / principle promotions → HIGH
      - Structural observations (check, capture, castling, central
        pawn, threat) → MID
      - Generic fallbacks (wins material in resulting line, Opponent's
        strongest reply, basic_mistake severity-only) → LOW
    """
    # HIGH — explicit named tactics + strategic-decline framing +
    # board-state coach-voice (Mohit 2026-05-21: board-state describer
    # produces coordinated multi-fact teachings; each bs_* template is
    # a verifiable geometric observation in user-facing language).
    high_keys = {
        "why_user_missed_mate",
        "why_user_missed_piece",
        "why_user_missed_clearance_attack",
        "why_user_missed_king_pawn_pressure",
        "why_user_position_already_losing",
        "why_user_position_already_losing_since_known",
        "why_user_curriculum_deviation",
        "why_user_blocks_pawn_supports",
        "why_user_blocks_pawn",
        "why_user_board_state",
        "bs_isolated_attacker",
        "bs_worst_placed_piece",
        "bs_development_gap",
        "bs_pieces_on_back_rank",
        "bs_king_shield_broken",
        "bs_king_attackers",
        "bs_central_control_gap",
        "bs_open_file_owned_by_opp",
        "bs_queen_alone_active",
        "bs_connected_rooks_only_opp",
        "bs_passive_pieces_count",
    }
    if variant_key in high_keys:
        return "HIGH"

    # HIGH pair-overrides — when a file's variant key marks a
    # board-state path, classify HIGH even if the file's default
    # entries are LOW (R_PROMOTED_basic_mistake.json default stays
    # LOW; with_board_state becomes HIGH).
    high_pairs = {
        ("R_PROMOTED_basic_mistake.json", "with_board_state"),
        ("R_PROMOTED_basic_mistake.json", "with_blocked_pawn"),
        ("R_PROMOTED_basic_mistake.json", "with_blocked_pawn_supports"),
        ("R_PROMOTED_basic_mistake.json", "with_curriculum_deviation"),
    }
    if (file_name, variant_key) in high_pairs:
        return "HIGH"

    # HIGH files — every variant is a named teaching surface
    high_files = {
        "R01_mate.json",                   # named mate scenarios
        "R02_multi_target_attack.json",    # forks
        "R03_aligned_pieces.json",         # pin / skewer / xray
        "R04_discovered_attack.json",      # discovered
        "R05_check_extra.json",            # check + tactic
        "R_PROMOTED_opening.json",         # named opening teaching
        "R_PROMOTED_trap_setup.json",      # named trap
        "R_PROMOTED_trap_defense.json",
        "R_PROMOTED_shape.json",           # named shape pattern
        "R_PROMOTED_principle.json",       # named principle
    }
    if file_name in high_files:
        return "HIGH"

    # LOW — known generic fallbacks (engine-speak / no specific
    # content surfaced even though a rule fired).
    low_pairs = {
        ("R12_blunder.json", "why_user_missed_material"),
        ("R12_blunder.json", "why_user_reply"),
        ("R_PROMOTED_basic_mistake.json", "default"),
    }
    if (file_name, variant_key) in low_pairs:
        return "LOW"

    # MID by default — structural observations (threats, captures,
    # castling, check, central-pawn, forced-best, good-move, etc.).
    return "MID"


_SAN_RE = r"[A-Za-z][A-Za-z0-9+#=x\-]*"
_SQUARE_RE = r"[a-h][1-8]"
_PIECE_RE = r"(?:pawn|knight|bishop|rook|queen|king)"
_INT_RE = r"\d+"

# Map placeholder name → tighter regex so we don't over-match. Tighter
# placeholders make variant matching far more accurate than the
# permissive ".+?" wildcard.
_PLACEHOLDER_REGEX = {
    # SAN moves
    "played_san": _SAN_RE,
    "move_san": _SAN_RE,
    "best_move_san": _SAN_RE,
    "best_move": _SAN_RE,
    "opp_reply_san": _SAN_RE,
    "user_best_reply_san": _SAN_RE,
    "capturing_move": _SAN_RE,
    "mating_move": _SAN_RE,

    # Squares
    "target_square": _SQUARE_RE,
    "from_square": _SQUARE_RE,
    "front_square": _SQUARE_RE,
    "rear_square": _SQUARE_RE,
    "square": _SQUARE_RE,
    "t0_square": _SQUARE_RE,
    "t1_square": _SQUARE_RE,
    "missed_tactic_target_square": _SQUARE_RE,
    "missed_clearance_attack_square": _SQUARE_RE,
    "shape_pattern_target_square": _SQUARE_RE,

    # Piece types
    "piece_type": _PIECE_RE,
    "moving_piece_type": _PIECE_RE,
    "front_piece_type": _PIECE_RE,
    "rear_piece_type": _PIECE_RE,
    "captured_piece_type": _PIECE_RE,
    "target_piece_type": _PIECE_RE,
    "t0_piece_type": _PIECE_RE,
    "t1_piece_type": _PIECE_RE,
    "discovered_attacker_piece_type": _PIECE_RE,
    "missed_tactic_target_piece": _PIECE_RE,
    "missed_clearance_attacker_piece": _PIECE_RE,

    # Integers
    "ply": _INT_RE,
    "pawn_swing": _INT_RE,
    "missed_tactic_ply": _INT_RE,

    # Severity phrase — known options only
    "severity_phrase": r"is a (?:major blunder|serious mistake|mistake)",

    # Why-clause — itself a clause, can be any prose
    "why_clause": r".+?",
}


def _template_to_regex(template: str) -> Optional["re.Pattern"]:
    """Convert a JSON template string with {placeholders} into a regex
    that matches a rendered caption.

    Tighter than the naive ".+?" approach — uses field-specific regex
    for known placeholders (SAN moves, squares, piece types, integers,
    severity_phrase). Unknown placeholders default to a moderately
    permissive `.+?`."""
    if not template:
        return None
    parts = re.split(r"(\{[a-zA-Z_]\w*\})", template)
    out: List[str] = []
    for p in parts:
        if p.startswith("{") and p.endswith("}"):
            key = p[1:-1]
            out.append(_PLACEHOLDER_REGEX.get(key, r".+?"))
        else:
            out.append(re.escape(p))
    pat = "^" + "".join(out) + "$"
    try:
        return re.compile(pat, re.IGNORECASE | re.DOTALL)
    except re.error as exc:
        logger.warning(f"[classifier] failed to compile regex from {template!r}: {exc}")
        return None


class CaptionClassifier:
    """Loads variant templates from backend/data/captions/*.json and
    classifies caption strings. Cached on first build; call .reload()
    to pick up JSON edits."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.by_file: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False

    def _build(self) -> None:
        entries: List[Dict[str, Any]] = []
        by_file: Dict[str, List[Dict[str, Any]]] = {}
        if not os.path.isdir(CAPTIONS_DIR):
            self.entries = []
            self.by_file = {}
            self._loaded = True
            return
        for fname in sorted(os.listdir(CAPTIONS_DIR)):
            if not fname.endswith(".json") or fname in _SKIP_FILES:
                continue
            path = os.path.join(CAPTIONS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except Exception as exc:
                logger.warning(f"[classifier] couldn't load {fname}: {exc}")
                continue
            variants = data.get("variants") or {}
            for variant_key, template in variants.items():
                if not isinstance(template, str) or not template:
                    continue
                # Why-clause variants in R12 are sub-sentences appended
                # to a main variant — they don't appear as standalone
                # captions, so we look for them as substrings, not as
                # full caption matches. bs_* variants are individual
                # sentences joined inside the board_state_clause — also
                # substring-matched so each carries its own tier.
                is_substring = (
                    variant_key.startswith("why_")
                    or variant_key.startswith("bs_")
                )
                regex = _template_to_regex(template)
                if regex is None:
                    continue
                # For substring matching, also build a non-anchored regex.
                # Skip templates that are pure single-placeholder
                # passthrough (e.g. why_user_board_state = "{x}") — those
                # match every non-empty string and would swallow
                # every caption.
                sub_regex = None
                if is_substring:
                    sub_pat = regex.pattern[1:-1]  # strip ^ $
                    # Skip pure-placeholder passthrough templates like
                    # "{x}" → regex `.+?` — those match every string
                    # and would swallow every caption.
                    if sub_pat in (".+?", ".+", "(.+?)", "(.+)"):
                        sub_regex = None
                    else:
                        try:
                            sub_regex = re.compile(sub_pat, re.IGNORECASE | re.DOTALL)
                        except re.error:
                            sub_regex = None
                entry = {
                    "file": fname,
                    "variant_key": variant_key,
                    "template": template,
                    "tier": _classify_tier(variant_key, fname),
                    "regex": regex,
                    "sub_regex": sub_regex,
                    "is_substring": is_substring,
                    "json_path": f"{fname} → variants.{variant_key}",
                }
                entries.append(entry)
                by_file.setdefault(fname, []).append(entry)
        self.entries = entries
        self.by_file = by_file
        self._loaded = True
        logger.info(
            f"[classifier] loaded {len(entries)} variants from {len(by_file)} files"
        )

    def _ensure_loaded(self):
        if not self._loaded:
            self._build()

    def reload(self):
        self._loaded = False
        self._build()

    def classify(self, caption: str, rule_name: str = "") -> Dict[str, Any]:
        """Return classification for a caption string.

        `rule_name` (when provided) is the move record's rule_name
        field — e.g. 'R12_blunder', 'R09_king_safety', or compound
        like 'R_FALLBACK_no_trigger_fired→R_PROMOTED_opening:italian_game'.
        We use it to ROUTE to the right file before matching variants
        within that file. Without rule_name, fall back to text-only
        classification (less accurate — identical-structure templates
        clash, e.g. R12 user_with_best vs R_PROMOTED_basic_mistake).

        Returns {tier, file, variant_key, json_path}.
        """
        self._ensure_loaded()
        if not caption:
            return {
                "tier": "NONE", "file": None, "variant_key": "empty",
                "json_path": None,
            }

        # Always try why-clause substrings first — these are the
        # high-value tactical signals appended to R12 captions.
        for e in self.entries:
            if not e["is_substring"] or e["sub_regex"] is None:
                continue
            if e["sub_regex"].search(caption):
                return {
                    "tier": e["tier"], "file": e["file"],
                    "variant_key": e["variant_key"],
                    "json_path": e["json_path"],
                }

        target_file = _file_from_rule_name(rule_name) if rule_name else None

        # If we know which file produced this caption, search ONLY
        # within that file. Avoids identical-structure templates from
        # other files (R_PROMOTED_basic_mistake vs R12 user_with_best,
        # R_PROMOTED_shape vs R_PROMOTED_opening) wrongly matching.
        if target_file:
            scoped = [
                e for e in self.entries
                if not e["is_substring"] and e["file"] == target_file
            ]
            scoped.sort(key=lambda e: -len(e["template"]))
            for e in scoped:
                if e["regex"].search(caption):
                    return {
                        "tier": e["tier"], "file": e["file"],
                        "variant_key": e["variant_key"],
                        "json_path": e["json_path"],
                    }

        # No rule_name (or its file had no match) — fall back to
        # scanning all variants longest-first.
        all_full = [e for e in self.entries if not e["is_substring"]]
        all_full.sort(key=lambda e: -len(e["template"]))
        for e in all_full:
            if e["regex"].search(caption):
                return {
                    "tier": e["tier"], "file": e["file"],
                    "variant_key": e["variant_key"],
                    "json_path": e["json_path"],
                }

        return {
            "tier": "NONE", "file": None, "variant_key": "bare_severity",
            "json_path": "R12_blunder.json → why_clauses_user (add new variant)",
        }


def _file_from_rule_name(rule_name: str) -> Optional[str]:
    """Map a move record's rule_name → the JSON file that produced
    the caption. Compound rule_names like
    'R_FALLBACK_no_trigger_fired→R_PROMOTED_opening:italian_game'
    use the promotion (post-arrow) part."""
    if not rule_name:
        return None
    # Compound — split on the arrow, use the right-hand side
    if "→" in rule_name:
        promo = rule_name.split("→", 1)[1]
        # Promotion patterns: "R_PROMOTED_<kind>:<id>" or just "R_PROMOTED_<kind>"
        promo_prefix = promo.split(":", 1)[0].strip()
        promo_map = {
            "R_PROMOTED_opening":        "R_PROMOTED_opening.json",
            "R_PROMOTED_trap":           "R_PROMOTED_trap_setup.json",
            "R_PROMOTED_trap_defense":   "R_PROMOTED_trap_defense.json",
            "R_PROMOTED_shape":          "R_PROMOTED_shape.json",
            "R_PROMOTED_principle":      "R_PROMOTED_principle.json",
            "R_PROMOTED_basic_mistake":  "R_PROMOTED_basic_mistake.json",
        }
        return promo_map.get(promo_prefix)

    # Plain R-rule
    rule_map = {
        "R01_mate":                 "R01_mate.json",
        "R02_multi_target_attack":  "R02_multi_target_attack.json",
        "R03_aligned_pieces":       "R03_aligned_pieces.json",
        "R04_discovered_attack":    "R04_discovered_attack.json",
        "R05_check_extra":          "R05_check_extra.json",
        "R06_check_plain":          "R06_check_plain.json",
        "R07_forced_recapture":     "R07_forced_recapture.json",
        "R08_material":             "R08_material.json",
        "R09_king_safety":          "R09_king_safety.json",
        "R10_threat":               "R10_threat.json",
        "R11_development":          None,  # silent, no JSON variant
        "R12_blunder":              "R12_blunder.json",
        "R13_opening_central_pawn": "R13_opening_central_pawn.json",
        "R14_forced_best":          "R14_forced_best.json",
        "R15_good_move":            "R15_good_move.json",
    }
    return rule_map.get(rule_name.strip())


# Module-level singleton
classifier = CaptionClassifier()
