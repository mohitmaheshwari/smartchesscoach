"""coach_memory and the curriculum speak two different KINDS of skill.

Measured on production 2026-09-12:

    stored skill ids (67 users) : 3,623
    curriculum concept ids      :   238
    overlap                     :     0
    players where a strict lookup found any history : 0 of 124

They are not two spellings of one identity. Openings are prose with move
notation ("Alapin Sicilian Defense 2...Nc6 3.Nf3"); concepts are identifiers
("DEF_WALK_KING", "TAC_PIN_PATTERN", "piece_safety"). Mapping one onto the other
is a category error, which is why fable/skill-id-bridge helped exactly 1 player.

Typing them does NOT by itself create matches -- the overlap is still 0. What it
does is stop a concept lookup scanning 3,579 opening lines it can never match,
and make the opening history reachable at all.
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.personal_teaching_profile import (  # noqa: E402
    CONCEPT_SKILL,
    OPENING_SKILL,
    _exact_skill,
    _skill_records,
    opening_skill_records,
    skill_kind,
)


@pytest.mark.parametrize("skill_id", [
    "DEF_WALK_KING", "END_OPPOSITION", "TAC_PIN_PATTERN",
    "piece_safety", "pin", "fork", "endgame_opposition", "pre_move_check",
])
def test_concept_ids_are_concepts(skill_id):
    assert skill_kind(skill_id) == CONCEPT_SKILL


@pytest.mark.parametrize("skill_id", [
    "Alapin Sicilian Defense 2...Nc6 3.Nf3",
    "Italian Game",
    "Ruy Lopez, Berlin Defence",
    # snake_case opening keys have no space, so the prefix is checked explicitly
    "opening_ruy_lopez", "opening_sicilian_black", "opening_principles",
])
def test_opening_ids_are_openings(skill_id):
    assert skill_kind(skill_id) == OPENING_SKILL


def test_the_opening_prefix_is_not_mistaken_for_a_concept():
    """Without this, opening_ruy_lopez looked like a plausible match for
    golden_opening_principle_10 purely because both contain "opening"."""
    assert skill_kind("opening_ruy_lopez") == OPENING_SKILL
    assert skill_kind("golden_opening_principle_10") == CONCEPT_SKILL


def _memory():
    return {"learning": {"skills": {
        "DEF_WALK_KING": {"level": 2},
        "piece_safety": {"level": 1},
        "Alapin Sicilian Defense 2...Nc6": {"seen": 5},
        "opening_ruy_lopez": {"seen": 3},
    }}}


def test_records_are_tagged_and_filterable():
    all_records = _skill_records(_memory())
    assert len(all_records) == 4
    assert all("skill_kind" in r for r in all_records)
    concepts = {r["skill_id"] for r in _skill_records(_memory(), kind=CONCEPT_SKILL)}
    assert concepts == {"DEF_WALK_KING", "piece_safety"}


def test_opening_history_is_reachable():
    """The point of the change: 67 users hold this and nothing read it."""
    openings = {r["skill_id"] for r in opening_skill_records(_memory())}
    assert openings == {"Alapin Sicilian Defense 2...Nc6", "opening_ruy_lopez"}


def test_a_concept_lookup_does_not_match_an_opening_line():
    """An honest miss, not a false match."""
    assert _exact_skill(_memory(), ["TAC_PIN_PATTERN"]) is None


def test_a_concept_lookup_still_finds_a_stored_concept():
    found = _exact_skill(_memory(), ["DEF_WALK_KING"])
    assert found is not None and found["skill_id"] == "DEF_WALK_KING"


def test_an_empty_alias_list_is_a_miss_not_a_crash():
    assert _exact_skill(_memory(), []) is None


# ---------------------------------------------------------------------------
# The record's own skill_type is the authority (added 2026-09-13).
#
# coach_memory.record_skill_attempt has always written skill_type on every
# record. Guessing the kind from the id string duplicated a field the data
# already carried -- and got it wrong. Measured over all 8,166 production
# records, the string heuristic disagrees with the declared field on 47:
#   22 openings it called concepts, and the 25 `opening_principles` records --
#   a declared CONCEPT, the second-largest concept by volume -- it called an
#   opening, which would have excluded them from the concept lookup.
# ---------------------------------------------------------------------------

from services.personal_teaching_profile import (  # noqa: E402
    CONCEPT_SKILL,
    LESSON_SKILL,
    OPENING_SKILL,
    _skill_records,
    skill_kind,
)


@pytest.mark.parametrize(
    "stored_id,declared,expected,why",
    [
        # The 47 real mismatches, by example.
        ("opening_principles", "concept", CONCEPT_SKILL,
         "the heuristic's opening_ prefix rule would have hidden 25 records"),
        ("Qgd", "opening", OPENING_SKILL,
         "an opening abbreviation with no space and no prefix"),
        ("caro_kann", "opening", OPENING_SKILL, "a snake_case opening name"),
        ("kings_pawn", "opening", OPENING_SKILL, "a snake_case opening name"),
        ("Undefined", "opening", OPENING_SKILL,
         "garbage, but the writer still declared what it was"),
        # Lessons are their own kind: neither an opening line nor an observation.
        ("endgame_opposition", "endgame", LESSON_SKILL, "a finished lesson"),
        ("mate_kq_vs_k", "mate_pattern", LESSON_SKILL, "a finished lesson"),
        ("italian_game_fried_liver_attack", "trap", LESSON_SKILL, "a trap lesson"),
        ("trap_set_italian", "trap_set", LESSON_SKILL, "a trap lesson"),
        # Habits and legacy patterns are observed concepts.
        ("pre_move_check", "concept", CONCEPT_SKILL, "a habit"),
        ("some_habit", "coached_play", CONCEPT_SKILL, "habits are concepts"),
        ("some_pattern", "pattern", CONCEPT_SKILL, "legacy concept spelling"),
    ],
)
def test_the_declared_type_beats_the_string_guess(stored_id, declared, expected, why):
    assert skill_kind(stored_id, declared) == expected, why


@pytest.mark.parametrize("declared", [None, "", "   ", "something_new"])
def test_the_heuristic_still_covers_records_with_no_declared_type(declared):
    """Old records predate the field; an unknown value must not silently win."""
    assert skill_kind("Alapin Sicilian Defense 2...Nc6", declared) == OPENING_SKILL
    assert skill_kind("opening_ruy_lopez", declared) == OPENING_SKILL
    assert skill_kind("TAC_PIN_PATTERN", declared) == CONCEPT_SKILL


def test_records_are_tagged_from_their_own_declared_type():
    memory = {"learning": {"skills": [
        {"skill_id": "opening_principles", "skill_type": "concept"},
        {"skill_id": "caro_kann", "skill_type": "opening"},
        {"skill_id": "endgame_opposition", "skill_type": "endgame"},
        {"skill_id": "legacy_no_type"},
    ]}}
    kinds = {r["skill_id"]: r["skill_kind"] for r in _skill_records(memory)}
    assert kinds == {
        "opening_principles": CONCEPT_SKILL,
        "caro_kann": OPENING_SKILL,
        "endgame_opposition": LESSON_SKILL,
        "legacy_no_type": CONCEPT_SKILL,
    }
    # A lesson must not leak into either real vocabulary.
    assert [r["skill_id"] for r in _skill_records(memory, kind=CONCEPT_SKILL)] == [
        "opening_principles", "legacy_no_type"]
    assert [r["skill_id"] for r in _skill_records(memory, kind=OPENING_SKILL)] == [
        "caro_kann"]
