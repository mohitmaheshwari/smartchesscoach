"""Caption renderer config — thin proxy over `backend/data/captions/caption_config.json`.

Values are authored in JSON (so Mohit + Parth can tune sensitivity
without a Python edit). This module re-exports them as module-level
constants for existing import sites — `from services.caption_config
import MAX_CAPTION_WORDS` still works exactly as before.

See `backend/data/captions/caption_config.json` for the fact glossary
explaining each threshold.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "captions", "caption_config.json"
)


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(f"[caption_config] load failed: {exc}; using hardcoded defaults")
        return {}


_CFG = _load_config()
_THRESH = _CFG.get("thresholds") or {}

# ── Caption length ──────────────────────────────────────────────────────
MAX_CAPTION_WORDS = _CFG.get("max_caption_words", 25)

# ── Tactic visibility thresholds ────────────────────────────────────────
DEFAULT_VISIBLE_TACTIC_THRESHOLD = _THRESH.get("default_visible_tactic_threshold", 2)

# ── Material thresholds ────────────────────────────────────────────────
MIN_MATERIAL_CAPTION_GAIN_CP = _THRESH.get("min_material_caption_gain_cp", 100)

# ── Threat thresholds ──────────────────────────────────────────────────
MIN_THREAT_SEE_CP = _THRESH.get("min_threat_see_cp", 200)

# ── Aligned-pieces (pin/skewer) significance ───────────────────────────
MIN_ALIGNED_REAR_VALUE_CP = _THRESH.get("min_aligned_rear_value_cp", 500)

# ── Tactic-celebration safety gate ──────────────────────────────────────
MAX_CP_LOSS_FOR_TACTIC_CELEBRATION = _THRESH.get("max_cp_loss_for_tactic_celebration", 100)
