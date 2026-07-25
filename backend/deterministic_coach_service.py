"""
Rating band lookup shared across the coaching services.

The "Deterministic Adaptive Coach" plan/audit engine that used to live in
this file (round-preparation, plan-audit, coaching-loop) was removed on
2026-07-25 - it was only reachable from the dead /round-preparation,
/plan-audit and /coaching-loop/* routes, which had zero frontend callers.
RATING_BANDS and get_rating_band are still imported live by
services/coaching_policy.py, services/rating_resolver.py, and
services/today_composer.py.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# =============================================================================
# RATING BANDS - Granular System
# =============================================================================

RATING_BANDS = {
    "beginner_low": {"min": 0, "max": 999, "label": "600-1000", "strictness": 0.5},
    "beginner_high": {"min": 1000, "max": 1399, "label": "1000-1400", "strictness": 0.7},
    "intermediate": {"min": 1400, "max": 1799, "label": "1400-1800", "strictness": 0.85},
    "advanced": {"min": 1800, "max": 9999, "label": "1800+", "strictness": 1.0},
}


def get_rating_band(rating: int) -> Dict:
    """Get the rating band for a given rating."""
    for band_name, band_data in RATING_BANDS.items():
        if band_data["min"] <= rating <= band_data["max"]:
            return {"name": band_name, **band_data}
    return {"name": "beginner_low", **RATING_BANDS["beginner_low"]}
