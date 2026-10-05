"""Of the chances the board gave you, how many did you take?

docs/chances_not_games_scope.md

THE CHANCE IS THE UNIT, NOT THE GAME. Mohit, 2026-10-05: *"it should be game
independent really, like quality of moves vs chances provided."* The denominator
is what the board offered and the player does not control it; the numerator is
what they did with it, which is entirely them. A game is only a container and
his vary from one chance to sixteen, so a per-game figure says nothing.

Game-independence is not a simplification, it removes two real problems:

  1,054 duplicate PGN groups exist across 19,229 games, and 2-move coach games
  repeat legitimately. A 2-move game provides no chances, so it lands on neither
  side of the ratio. The bad data stops mattering instead of needing cleaning.

  Three games one week and thirty the next compare directly, because the
  denominator is chances rather than games.

NO AUTHORED STRING HERE CARRIES A NUMBER. The counts ride in their own fields so
the surface can decide. Mohit has not settled whether plain counts may be shown,
and this way neither answer requires undoing work.

WHAT THIS DOES NOT SAY. It will not tell a player they are not improving. His
rate was flat over ten weeks in which his rating rose from 1067 to 1307 -- either
conversion is now the ceiling or he is holding the rate against harder
positions, and the reading cannot tell those apart. It describes conversion and
names the weakest shape. Nothing else.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

# Below this the ratio is noise with a decimal point. Same bar the opportunity
# gate uses to decide a player is judgeable at all.
MIN_CHANCES = 20

# A shape needs its own evidence before it can be named as the weak one. The
# gate's own measurement is that a single pattern is unstable at 10-30 chances
# and stable above roughly 800; 60 is a deliberate middle, chosen so the card
# can speak before a player has played hundreds of games, and the shape is only
# ever named as "where to practise" rather than as a judgement.
MIN_CHANCES_PER_SHAPE = 60

SHAPE_WORDS: Mapping[str, str] = {
    "free_piece": "free material",
    "fork": "forks",
    "pin": "pins",
    "skewer": "skewers",
    "hidden_attack": "hidden attacks",
    "remove_the_guard": "removing the defender",
    "force_the_king": "forcing the king",
}

# What the player reads when a shape is clearly the weakest. Keyed by shape so
# the sentence can name the idea rather than the label.
WEAKEST_LINE: Mapping[str, str] = {
    "pin": "Lining pieces up is what costs you.",
    "skewer": "Lining pieces up is what costs you.",
    "fork": "Spotting one piece hitting two is what costs you.",
    "free_piece": "Taking what is left loose is what costs you.",
    "hidden_attack": "Seeing what opens up behind a move is what costs you.",
    "remove_the_guard": "Noticing what defends what is what costs you.",
}

SCHEMA_VERSION = "chances_reading.v1"


def _share(slot: Mapping[str, Any]) -> Optional[float]:
    chances = slot.get("chances") or 0
    if not chances:
        return None
    return float(slot.get("took") or 0) / float(chances)


def build_reading(stored: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The card, from a `user_tactical_eye` document.

    Returns `measured: False` rather than a guess when the player has not been
    offered enough. Saying "you take about half" off nine chances would be a
    sentence invented from nothing.
    """
    stored = stored or {}
    chances = int(stored.get("chances") or 0)
    took = int(stored.get("took") or 0)
    if chances < MIN_CHANCES:
        return {"schema_version": SCHEMA_VERSION, "measured": False,
                "reason": "not enough chances watched yet"}

    by_pattern = stored.get("by_pattern") or {}
    shapes: List[Dict[str, Any]] = []
    for name, slot in by_pattern.items():
        if not isinstance(slot, Mapping):
            continue
        share = _share(slot)
        if share is None:
            continue
        shapes.append({
            "shape": name,
            "label": SHAPE_WORDS.get(name, str(name).replace("_", " ")),
            "chances": int(slot.get("chances") or 0),
            "took": int(slot.get("took") or 0),
            # The surface draws a bar from this. It is a share, never printed.
            "share": round(share, 4),
            "judgeable": int(slot.get("chances") or 0) >= MIN_CHANCES_PER_SHAPE,
        })
    shapes.sort(key=lambda row: row["share"], reverse=True)

    # The weakest shape with enough of its own evidence. A shape nobody has been
    # offered sixty times is not a finding about the player.
    judgeable = [row for row in shapes if row["judgeable"]]
    weakest = judgeable[-1] if judgeable else None

    overall = took / chances
    # Deliberately coarse. A tenth of a point of conversion is not a thing a
    # player can act on, and three buckets is what the sentence can honestly
    # support.
    if overall >= 0.66:
        headline = "You take most of what the board offers you."
    elif overall >= 0.4:
        headline = "You take about half of what the board offers you."
    else:
        headline = "Most of what the board offers you is going past."

    return {
        "schema_version": SCHEMA_VERSION,
        "measured": True,
        "headline": headline,
        "chances": chances,
        "took": took,
        "share": round(overall, 4),
        "shapes": shapes,
        "weakest": weakest,
        "weakest_line": (WEAKEST_LINE.get(weakest["shape"]) if weakest else None),
        # Filled by the caller, which is the only layer that knows whether a
        # drill has positions behind it.
        "practice": None,
    }
