"""
Opening Variation Resolver

Maps specific game opening variations to base curriculum openings.
Example: "Caro Kann Defense Exchange Variation 3...cxd5 4.Nf3" → "Caro Kann Defense"

This enables teaching fundamentals while showing users the context of their
specific game opening variation.
"""

import json
import os
from typing import Optional, Dict, List


def _variation_count(record) -> int:
    """Read one JSON variation row without assuming tuples survive JSON."""
    if isinstance(record, (list, tuple)) and len(record) >= 2:
        try:
            return int(record[1] or 0)
        except (TypeError, ValueError):
            return 0
    if isinstance(record, dict):
        try:
            return int(record.get("games", record.get("count", 0)) or 0)
        except (TypeError, ValueError):
            return 0
    return 0

class OpeningVariationResolver:
    def __init__(self):
        self.game_to_base = {}
        self.base_to_variations = {}
        self._load_mapper()

    def _load_mapper(self):
        """Load the opening variations map."""
        mapper_path = os.path.join(
            os.path.dirname(__file__),
            "../data/opening_variations_map.json"
        )
        try:
            with open(mapper_path) as f:
                data = json.load(f)
                self.game_to_base = data.get("game_to_base", {})
                # Convert base_to_variations keys back to dicts for easy access
                for base, variations in data.get("base_to_variations", {}).items():
                    self.base_to_variations[base] = variations
        except Exception as e:
            print(f"Warning: Could not load opening mapper: {e}")

    def resolve(self, game_opening_name: str) -> Optional[Dict]:
        """
        Resolve a game opening to its base curriculum opening.

        Args:
            game_opening_name: The specific opening name from a game

        Returns:
            {
                "base_opening": "Caro Kann Defense",
                "game_opening": "Caro Kann Defense Exchange Variation 3...cxd5 4.Nf3",
                "is_exact_match": False,
                "variation_count": 188,
                "game_count": 605
            }

            Returns None if no match found.
        """
        if not game_opening_name:
            return None

        # Try exact match first
        if game_opening_name in self.game_to_base:
            base = self.game_to_base[game_opening_name]
            is_exact = (game_opening_name == base)
            variations = self.base_to_variations.get(base, [])

            return {
                "base_opening": base,
                "game_opening": game_opening_name,
                "is_exact_match": is_exact,
                "variation_count": len(variations) if isinstance(variations, list) else len(variations),
                "game_count": sum(
                    _variation_count(v)
                    for v in (variations if isinstance(variations, list) else variations.values())
                )
            }

        return None

    def get_variations(self, base_opening_name: str) -> List[Dict]:
        """
        Get all variations of a base curriculum opening played in games.

        Args:
            base_opening_name: e.g. "Caro Kann Defense"

        Returns:
            [
                {"variation": "Caro Kann Defense", "games": 109},
                {"variation": "Caro Kann Defense Exchange Variation 3...cxd5 4.Nf3", "games": 55},
                ...
            ]
        """
        variations = self.base_to_variations.get(base_opening_name, [])
        if not variations:
            return []

        result = []
        for var in variations:
            if isinstance(var, (list, tuple)) and len(var) >= 2:
                name, count = var
                result.append({"variation": name, "games": _variation_count(var)})
            elif isinstance(var, dict):
                result.append(var)

        return sorted(result, key=lambda x: x.get("games", 0), reverse=True)

    def is_mapped(self, game_opening_name: str) -> bool:
        """Check if a game opening has a curriculum mapping."""
        return game_opening_name in self.game_to_base


# Singleton instance
_resolver = None

def get_resolver() -> OpeningVariationResolver:
    """Get the global opening variation resolver."""
    global _resolver
    if _resolver is None:
        _resolver = OpeningVariationResolver()
    return _resolver
