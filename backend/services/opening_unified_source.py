"""
Opening Unified Source

Single source of truth for all opening data: opening_curriculum.json

This service replaces multiple JSON files:
- opening_theory_tree.json (27 openings → merged into curriculum)
- opening_plans.json (11 openings → merged into curriculum)
- opening_demands.json (16 openings → merged into curriculum)

Backwards compatible: provides the same interface as old files, loads from curriculum.
"""

import json
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class OpeningUnifiedSource:
    def __init__(self):
        self.curriculum = None
        self._load_curriculum()

    def _load_curriculum(self):
        """Load the unified opening curriculum."""
        curriculum_path = os.path.join(
            os.path.dirname(__file__),
            "../data/opening_curriculum.json"
        )
        try:
            with open(curriculum_path) as f:
                self.curriculum = json.load(f)
        except Exception as e:
            logger.error(f"Could not load opening curriculum: {e}")
            self.curriculum = {}

    def get_theory_tree(self) -> Dict[str, Any]:
        """
        Get theory tree data (backwards compatible with opening_theory_tree.json).

        2026-07-14 (Q3 revival): the projection used to strip everything but 5
        fields, which silently KILLED the theory-lookup teaching features —
        caption_pipeline's opening critical-position captions,
        game_decryption_v5's get_mistake_from_theory, golden_rule_service's
        learning lines, and the mastery tracker's variation ideas all read
        variations/critical_positions/common_learnings/move_ideas and always
        got nothing. Those fields (merged into the curriculum from the retired
        theory_tree file, 24-25 openings) are now projected through.
        """
        result = {}
        for key, opening in self.curriculum.items():
            if isinstance(opening, dict) and "eco_prefix" in opening:
                entry = {
                    "name": opening.get("name"),
                    "eco_prefix": opening.get("eco_prefix"),
                    "main_line": opening.get("main_line"),
                    "white_plan": opening.get("white_plan"),
                    "black_plan": opening.get("black_plan"),
                }
                for rich in ("variations", "critical_positions",
                             "common_learnings", "move_ideas"):
                    if opening.get(rich):
                        entry[rich] = opening[rich]
                result[key] = entry
        return result

    def get_opening_plans(self) -> Dict[str, Any]:
        """
        Get opening plans data (backwards compatible with opening_plans.json).

        Returns all openings with middlegame and endgame plans.
        """
        result = {}
        for key, opening in self.curriculum.items():
            if isinstance(opening, dict) and ("middlegame_plans" in opening or "endgame_tips" in opening):
                result[key] = {
                    "name": opening.get("name"),
                    "plans": opening.get("middlegame_plans"),
                    "endgame_tips": opening.get("endgame_tips"),
                }
        return result

    def get_opening_demands(self) -> Dict[str, Any]:
        """
        Get opening demands data (backwards compatible with opening_demands.json).

        Returns all openings with demands/requirements.
        """
        result = {}
        for key, opening in self.curriculum.items():
            if isinstance(opening, dict) and "demands" in opening:
                result[key] = opening.get("demands")
        return result

    def get_opening(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a single opening by key."""
        return self.curriculum.get(key)

    def get_all_openings(self) -> Dict[str, Any]:
        """Get all openings (excluding metadata keys)."""
        return {
            k: v for k, v in self.curriculum.items()
            if not k.startswith("_")
        }

    def search_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Search for an opening by name."""
        name_lower = name.lower()
        for key, opening in self.curriculum.items():
            if isinstance(opening, dict):
                if opening.get("name", "").lower() == name_lower:
                    return opening
        return None

    def get_eco_openings(self) -> Dict[str, str]:
        """
        Get ECO code to opening name mapping.

        Returns: {"A00": "Irregular Opening", "A01": "Larsen's Opening", ...}
        """
        result = {}
        for key, opening in self.curriculum.items():
            if isinstance(opening, dict) and "eco_prefix" in opening:
                eco = opening["eco_prefix"]
                name = opening.get("name")
                if eco and name:
                    result[eco] = name
        return result


# Singleton instance
_unified_source = None

def get_unified_source() -> OpeningUnifiedSource:
    """Get the global unified opening source."""
    global _unified_source
    if _unified_source is None:
        _unified_source = OpeningUnifiedSource()
    return _unified_source


# Backwards compatibility functions
def load_theory_tree() -> Dict[str, Any]:
    """Load theory tree (backwards compatible)."""
    return get_unified_source().get_theory_tree()


def load_opening_plans() -> Dict[str, Any]:
    """Load opening plans (backwards compatible)."""
    return get_unified_source().get_opening_plans()


def load_opening_demands() -> Dict[str, Any]:
    """Load opening demands (backwards compatible)."""
    return get_unified_source().get_opening_demands()
