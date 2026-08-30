"""Bridge curriculum content_ids to the skill_ids production history uses.

The personalized teaching profile looks up a player's history in
coach_memory.learning.skills by skill_id. The curriculum passes its own
content_id (e.g. "king_and_pawn/square_rule"), but production history was
written under an older vocabulary (e.g. "endgame_rule_of_square"), so the
strict-equality lookup found history for 1 of 65 players (measured
2026-08-30 against chess_coach.coach_memory).

Two joins, both deterministic — no fuzzy matching:

1. LEGACY_ALIASES: the complete non-opening production vocabulary is only
   19 distinct ids. Each alias below was hand-verified to be the SAME
   teachable concept as the curriculum lesson, because the profile's
   message ("you have used this idea in a game before") is a factual claim
   about the player. Ids that are broader than any one lesson
   (king_pawn_endgame, trap_set_italian) are deliberately NOT mapped —
   see UNMAPPED_TOO_BROAD.

2. Opening slugs: curriculum opening ids were generated from the same
   display names production stores, as slugify(name) truncated to 30
   characters ("Four Knights Game Italian Variation" ->
   "four_knights_game_italian_vari"). matches_opening_id applies that
   exact generation rule rather than guessing similarity.
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping, Tuple

_SLUG_BREAKS = re.compile(r"[^a-z0-9]+")

# Curriculum opening ids are slugified display names cut at this length.
OPENING_SLUG_MAX_LEN = 30

# curriculum content_id -> production skill_ids holding the same concept.
# Order matters: the first alias with history wins.
LEGACY_ALIASES: Mapping[str, Tuple[str, ...]] = {
    # endgames — identical concepts under older ids
    "king_and_pawn/square_rule": ("endgame_rule_of_square",),
    "king_and_pawn/opposition": ("endgame_opposition",),
    "basic_mates/rook_mate": ("mate_kr_vs_k",),
    "basic_mates/queen_mate": ("mate_kq_vs_k",),
    "rook_endgames/philidor": ("endgame_philidor",),
    # traps — same trap, older slug format
    "queens-gambit/elephant-trap": ("queens_gambit_elephant_trap",),
    "italian-game/fried-liver-attack": (
        "italian_game_fried_liver_attack",
        "defend_fried_liver",
    ),
    # Defending Scholar's mate is direct evidence for both Scholar lessons.
    "italian-game/scholar-s-mate-defense-trap": ("defend_scholars_mate",),
    "italian-game/scholar-s-mate-danger": ("defend_scholars_mate",),
}

# Production ids that are REAL history but broader than any single lesson.
# Mapping them would overstate evidence ("you have used this idea" about a
# lesson the player may never have met). Kept here so nobody "fixes" the
# gap by adding them without noticing the problem.
UNMAPPED_TOO_BROAD: Tuple[str, ...] = (
    "king_pawn_endgame",   # five king_and_pawn lessons; no way to pick one
    "trap_set_italian",    # a set of traps, not one trap
    "opening_principles",  # not a single lesson
    "pre_move_check",      # habit concept; matches exactly if a lesson exists
)


def slugify_opening_name(name: str) -> str:
    """The generation rule curriculum opening ids were built with."""
    slug = _SLUG_BREAKS.sub("_", str(name or "").lower()).strip("_")
    return slug[:OPENING_SLUG_MAX_LEN]


def matches_opening_id(curriculum_id: str, legacy_skill_id: str) -> bool:
    """True when legacy_skill_id names the same opening as curriculum_id.

    Exact rule inversion, not similarity: the curriculum id must equal the
    slugified legacy name after the same 30-char truncation. A shorter
    curriculum id must match the full slug (no prefix matching), so
    "Italian Game" cannot claim "italian_game_knight_attack".
    """
    cid = str(curriculum_id or "")
    if not cid:
        return False
    slug = _SLUG_BREAKS.sub("_", str(legacy_skill_id or "").lower()).strip("_")
    if slug == cid:
        return True
    # Only ids produced by truncation may match on a truncated slug.
    return len(cid) == OPENING_SLUG_MAX_LEN and slug[:OPENING_SLUG_MAX_LEN] == cid


def candidate_skill_ids(curriculum_id: str) -> Tuple[str, ...]:
    """The curriculum id itself, then its verified legacy aliases."""
    cid = str(curriculum_id or "")
    if not cid:
        return ()
    return (cid, *LEGACY_ALIASES.get(cid, ()))


def find_skill_record(
    records: Iterable[Mapping[str, object]],
    curriculum_id: str,
) -> Mapping[str, object] | None:
    """First record matching the curriculum id, an alias, or the opening rule."""
    items = [r for r in records if isinstance(r, Mapping)]
    for wanted in candidate_skill_ids(curriculum_id):
        for item in items:
            if str(item.get("skill_id") or "") == wanted:
                return item
    for item in items:
        sid = str(item.get("skill_id") or "")
        if sid and matches_opening_id(curriculum_id, sid):
            return item
    return None
