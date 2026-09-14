"""coach_memory skill ids must resolve to real curriculum concept ids.

coach_memory.learning.skills and user_concept_understanding speak different
vocabularies. Measured on production 2026-09-13 across all 8,166 stored skill
records: 7,910 are openings, 113 are concepts across 11 distinct ids, 143 are
lesson records. A strict concept lookup found history for 0 of 124 players
because not one stored id was spelled the way the curriculum spells it.

Two things this locks:

1. The bridge lives in data/pattern_catalog.json, which ALREADY held
   pattern_id -> canonical_concept_id and already had a resolver. No fifth
   vocabulary was created. (memory: single-source-of-truth)

2. A lesson is not a concept observation. "endgame_opposition" is the lesson
   that TEACHES END_OPPOSITION -- a player who sat through it has attendance,
   not demonstrated understanding. Lesson entries carry teaches_concept_id, so
   canonical_concept_id() deliberately does NOT translate them; filing them as
   concepts would write lesson attendance into the profile as competence.
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.pattern_catalog import canonical_concept_id  # noqa: E402

CATALOG = json.loads((BACKEND / "data" / "pattern_catalog.json").read_text(encoding="utf-8"))
PATTERNS = CATALOG["patterns"]

# Every alias, with the chess reason it is that concept and not a near neighbour.
ALIASES = {
    "pre_move_check": "TAC_CHECKS_CAPTURES_THREATS",
    "defend_fried_liver": "OP_F2_F7_STRIKE",
    "defend_scholars_mate": "OP_F2_F7_STRIKE",
    "hanging_piece": "TAC_HANGING_PIECE",
    "free_piece_capture": "TAC_HANGING_PIECE",
    "fork": "TAC_FORK_PATTERN",
    "pin": "TAC_PIN_PATTERN",
    "opponent_threat": "TAC_CHANGED_AFTER_MOVE",
}

LESSONS = {
    "endgame_opposition": "END_OPPOSITION",
    "endgame_rule_of_square": "END_RULE_OF_SQUARE",
}


@pytest.mark.parametrize("stored,concept", sorted(ALIASES.items()))
def test_each_alias_resolves_to_its_concept(stored, concept):
    assert canonical_concept_id(stored) == concept


@pytest.mark.parametrize("stored,taught", sorted(LESSONS.items()))
def test_a_lesson_is_not_translated_into_a_concept(stored, taught):
    """Attendance must not be readable as understanding."""
    assert canonical_concept_id(stored) == stored, (
        f"{stored} is the lesson that teaches {taught}; resolving it as the "
        "concept would count sitting through a lesson as holding the concept"
    )
    assert PATTERNS[stored]["teaches_concept_id"] == taught
    assert "canonical_concept_id" not in PATTERNS[stored]


@pytest.mark.parametrize("stored", sorted(ALIASES))
def test_every_alias_states_why_that_concept(stored):
    """A wrong pair writes false history into a player's profile.

    Where the two ids name the same thing ("pin" / "TAC_PIN_PATTERN") the
    mapping is self-evident and a sentence saying so is enough. Where they do
    NOT -- "defend_fried_liver" / "OP_F2_F7_STRIKE" -- the chess reason a
    reviewer could check must be written down.
    """
    reason = PATTERNS[stored]["why_this_concept"]
    assert reason.strip()
    concept_words = set(ALIASES[stored].lower().replace("_", " ").split())
    stored_words = set(stored.lower().replace("_", " ").split())
    self_evident = stored_words <= concept_words
    if not self_evident:
        assert len(reason) > 60, (
            f"{stored} -> {ALIASES[stored]} is not self-evident from the names; "
            "it needs a chess reason a reviewer can check"
        )


def test_the_unmapped_ids_each_carry_a_structural_reason():
    """What is left is not a pending opinion -- none is resolvable by anyone.

    Three earlier entries (opening_principles, king_pawn_endgame, conversion)
    DID look like judgement calls and were resolved as umbrellas above. These
    six are different: a trap lesson has no concept counterpart at all, and
    Philidor and the two basic mates are absent from the curriculum vocabulary.
    Those are content gaps, and inventing a pair would write false history.
    """
    unmapped = CATALOG["_doc"]["coach_memory_bridge"]["deliberately_unmapped"]
    assert set(unmapped) == {
        "endgame_philidor", "mate_kq_vs_k", "mate_kr_vs_k",
        "italian_game_fried_liver_attack", "queens_gambit_elephant_trap",
        "trap_set_italian",
    }, "the unmapped set changed -- update the reasoning, not just the list"
    for stored, reason in unmapped.items():
        assert len(reason) > 30, stored
        assert canonical_concept_id(stored) == stored


def test_no_alias_points_at_an_id_the_curriculum_does_not_have():
    """The whole failure mode being fixed is ids nothing recognises."""
    from services import caption_principles as cp  # noqa: F401
    known = set()
    for attr in dir(cp):
        value = getattr(cp, attr)
        if isinstance(value, dict):
            known.update(str(k) for k in value)
    if not known:
        pytest.skip("caption_principles exposes no id table to check against")
    for stored, concept in {**ALIASES, **LESSONS}.items():
        assert concept in known, f"{stored} -> {concept} is not a known concept id"


# ---------------------------------------------------------------------------
# The bridge has to be REACHED, not just be correct (added 2026-09-13).
#
# The aliases resolved correctly while nothing fed them: the one function that
# reads coach_memory skill records had no consumer, so a lookup still asked for
# the curriculum id alone and still matched nothing. Measured on production
# across all 124 coach_memory documents: 0 players before, 43 after.
# ---------------------------------------------------------------------------

from services.engine2_skill_builder import lesson_skill_aliases  # noqa: E402
from services.pattern_catalog import concept_aliases  # noqa: E402
from services.personal_teaching_profile import _exact_skill  # noqa: E402


@pytest.mark.parametrize("concept,older", sorted(
    {v: k for k, v in ALIASES.items()}.items()  # one older spelling per concept
))
def test_a_lookup_for_the_curriculum_id_reaches_the_older_spelling(concept, older):
    assert older in concept_aliases(concept)
    assert older in lesson_skill_aliases("concept", "", requested_skill_id=concept)


@pytest.mark.parametrize("concept,taught_by", sorted(
    {v: k for k, v in LESSONS.items()}.items()
))
def test_a_concept_lookup_never_reaches_a_lesson(concept, taught_by):
    """Attendance must not answer a question about competence."""
    assert taught_by not in concept_aliases(concept), (
        f"{taught_by} is the lesson that teaches {concept}; returning it as an "
        "alias would let sitting through the lesson count as holding the concept"
    )


def test_the_widened_lookup_finds_history_the_strict_one_missed():
    """The end-to-end property, on a record shaped like the real ones."""
    memory = {"learning": {"skills": [
        {"skill_id": "pre_move_check", "skill_type": "concept",
         "seen": 6, "correct": 4},
    ]}}
    strict = _exact_skill(memory, ["TAC_CHECKS_CAPTURES_THREATS"])
    assert strict is None, "the miss this change exists to fix"

    widened = lesson_skill_aliases(
        "concept", "", requested_skill_id="TAC_CHECKS_CAPTURES_THREATS")
    found = _exact_skill(memory, list(widened))
    assert found is not None and found["skill_id"] == "pre_move_check"


def test_a_lesson_record_still_does_not_satisfy_a_concept_lookup():
    memory = {"learning": {"skills": [
        {"skill_id": "endgame_opposition", "skill_type": "endgame",
         "seen": 9, "correct": 9},
    ]}}
    widened = lesson_skill_aliases("concept", "", requested_skill_id="END_OPPOSITION")
    assert _exact_skill(memory, list(widened)) is None, (
        "nine correct answers in the lesson are still not evidence the player "
        "holds the concept in a real game"
    )


def test_an_unknown_concept_widens_to_nothing():
    assert concept_aliases("NOT_A_CONCEPT") == ()
    assert concept_aliases("") == ()
    assert concept_aliases(None) == ()


# ---------------------------------------------------------------------------
# Umbrella entries close the last 28 records (added 2026-09-14).
#
# Three stored ids name a GROUP of concepts rather than one: "opening_principles"
# is develop/centre/castle, "king_pawn_endgame" is a whole class of ending,
# "conversion" is endgame technique. Mapping each to a single concept would
# assert detail the record does not carry, so each maps to its group and is
# marked broader-than-exact. Production after this change: 113/113 concept
# records, 11/11 distinct ids, 43/43 players holding one.
# ---------------------------------------------------------------------------

UMBRELLAS = {
    "opening_principles": ["OP_FINISH_DEVELOPMENT", "OP_CLAIM_CENTER", "OP_NOT_CASTLED"],
    "king_pawn_endgame": ["END_OPPOSITION", "END_PASSED_PAWN", "END_KING_ACTIVE",
                          "END_RULE_OF_SQUARE", "king_and_pawn_opposition"],
    "conversion": ["END_PASSED_PAWN", "END_KING_ACTIVE", "rook_endgame_activity"],
}


@pytest.mark.parametrize("stored,concepts", sorted(UMBRELLAS.items()))
def test_every_concept_in_the_group_reaches_the_umbrella(stored, concepts):
    for concept in concepts:
        assert stored in concept_aliases(concept), f"{concept} should reach {stored}"
        assert stored in lesson_skill_aliases(
            "concept", "", requested_skill_id=concept)


@pytest.mark.parametrize("stored,concepts", sorted(UMBRELLAS.items()))
def test_an_umbrella_is_never_offered_as_an_exact_match(stored, concepts):
    """It is real history, but broader than the question asked."""
    for concept in concepts:
        assert stored not in concept_aliases(concept, exact_only=True)


def test_exact_aliases_survive_the_exact_only_filter():
    """The strict path must keep what genuinely is the same idea."""
    assert concept_aliases("TAC_PIN_PATTERN", exact_only=True) == ("pin",)
    assert "pre_move_check" in concept_aliases(
        "TAC_CHECKS_CAPTURES_THREATS", exact_only=True)


def test_an_umbrella_does_not_answer_for_an_unrelated_concept():
    """The group is a list, not a wildcard."""
    for unrelated in ("TAC_PIN_PATTERN", "TAC_FORK_PATTERN", "MID_BAD_BISHOP"):
        assert "opening_principles" not in concept_aliases(unrelated)
        assert "king_pawn_endgame" not in concept_aliases(unrelated)


def test_a_lesson_still_cannot_be_reached_through_an_umbrella():
    """END_OPPOSITION gains king_pawn_endgame but must not gain the lesson."""
    reached = concept_aliases("END_OPPOSITION")
    assert "king_pawn_endgame" in reached
    assert "endgame_opposition" not in reached, (
        "the endgame lesson is attendance; an umbrella must not smuggle it in"
    )


def test_every_stored_concept_id_is_reachable():
    """100% coverage of the stored concept vocabulary, locked.

    The eleven ids are what production holds in coach_memory concept records.
    """
    stored_ids = set(ALIASES) | set(UMBRELLAS) | {"free_piece_capture"}
    catalog_concepts = {
        c
        for entry in PATTERNS.values()
        if isinstance(entry, dict)
        for c in ([entry.get("canonical_concept_id")]
                  + list(entry.get("umbrella_concept_ids") or []))
        if c
    }
    reachable = {
        alias
        for concept in catalog_concepts
        for alias in concept_aliases(concept)
    }
    missing = sorted(stored_ids - reachable)
    assert not missing, f"unreachable stored concept ids: {missing}"
