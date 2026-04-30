"""
Public SEO routes — no authentication, served to crawlers + cold users.
=======================================================================

These endpoints power the public marketing surface (/learn/openings/*,
/learn/patterns/*, /improve/*) used for organic search traffic. No PII,
no user-specific state. Pure content + aggregate stats.

The auth-gated /coach/openings/* endpoints serve a different concern:
the logged-in interactive lesson flow. Both can coexist. SEO pages
display content; auth pages teach it interactively.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public", tags=["public-seo"])


# ─── Opening curriculum loader ────────────────────────────────────────
# The curriculum file is the source of truth. The auth-gated lesson
# flow already imports it via opening_curriculum_engine. Here we just
# expose a slimmed, public-safe view: same content, no internal
# scaffolding fields.

_CURRICULUM_PATH = Path(__file__).resolve().parent.parent / "data" / "opening_curriculum.json"
_CURRICULUM: Optional[Dict] = None


def _load_curriculum() -> Dict:
    """Lazy-load and cache the curriculum JSON."""
    global _CURRICULUM
    if _CURRICULUM is None:
        try:
            with open(_CURRICULUM_PATH, encoding="utf-8") as f:
                _CURRICULUM = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load opening_curriculum.json: {e}")
            _CURRICULUM = {}
    return _CURRICULUM


def _slug_to_key(slug: str) -> Optional[str]:
    """Map URL slug ('italian-game') to curriculum key ('italian_game').

    Slugs use hyphens; curriculum uses underscores. Also normalizes
    case and strips trailing slashes — a friendly URL surface should
    be forgiving."""
    if not slug:
        return None
    return slug.strip("/").lower().replace("-", "_")


@router.get("/openings")
async def list_openings_public():
    """Return the list of openings available as public guides.

    Each entry is the minimum a list page (or sitemap generator)
    needs: slug, name, color, summary, difficulty. Detail-level
    fields (tree, traps, golden_rules) are fetched per-opening."""
    curriculum = _load_curriculum()
    items = []
    for key, entry in curriculum.items():
        items.append(
            {
                "slug": key.replace("_", "-"),
                "key": key,
                "name": entry.get("name", key),
                "color": entry.get("color", ""),
                "summary": entry.get("summary", ""),
                "difficulty": entry.get("difficulty", ""),
                "trap_count": len(entry.get("traps", []) or []),
            }
        )
    # Stable sort: white openings first, then alphabetical by name
    items.sort(key=lambda x: (x["color"] != "white", x["name"]))
    return {"openings": items}


@router.get("/openings/{slug}")
async def get_opening_public(slug: str):
    """Return public-safe opening details by slug.

    The shape mirrors the auth-gated /coach/openings/{key} endpoint
    minus any user-specific scaffolding. Anyone can hit this — it's
    also what the SEO page renders into HTML for crawlers."""
    curriculum = _load_curriculum()
    key = _slug_to_key(slug)
    if not key or key not in curriculum:
        raise HTTPException(status_code=404, detail="Opening not found")

    entry = curriculum[key]
    return {
        "slug": slug,
        "key": key,
        "name": entry.get("name", key),
        "color": entry.get("color", ""),
        "summary": entry.get("summary", ""),
        "difficulty": entry.get("difficulty", ""),
        "setup_order": entry.get("setup_order", []),
        "golden_rules": entry.get("golden_rules", []),
        "traps": entry.get("traps", []),
        "middlegame_plans": entry.get("middlegame_plans", {}),
        "endgame_tips": entry.get("endgame_tips", []),
        # tree omitted from public response — too large for SEO page
        # and the auth-gated lesson flow already exposes it on demand
    }
