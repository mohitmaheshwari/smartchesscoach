"""The bridge may only ever claim history that is genuinely the same concept."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.skill_id_bridge import (  # noqa: E402
    LEGACY_ALIASES,
    UNMAPPED_TOO_BROAD,
    candidate_skill_ids,
    find_skill_record,
    matches_opening_id,
    slugify_opening_name,
)
from services.personal_teaching_profile import (  # noqa: E402
    derive_personal_teaching_profile,
)

# The complete non-opening skill_id vocabulary observed in production
# (chess_coach.coach_memory, 2026-08-30, 65 users, 19 distinct ids).
OBSERVED_PRODUCTION_IDS = {
    "endgame_rule_of_square", "defend_scholars_mate", "endgame_opposition",
    "mate_kr_vs_k", "mate_kq_vs_k", "pre_move_check", "opening_principles",
    "defend_fried_liver", "king_pawn_endgame", "queens_gambit_elephant_trap",
    "endgame_philidor", "hanging_piece", "free_piece_capture", "fork",
    "conversion", "pin", "opponent_threat", "italian_game_fried_liver_attack",
    "trap_set_italian",
}


def _curriculum_ids():
    from services.curriculum_content_validator import validate_all_content
    ids = set()
    for subject in validate_all_content()["subjects"].values():
        ids.update(str(k) for k in subject["records"].keys())
    return ids


def test_every_alias_key_is_a_real_curriculum_id():
    missing = set(LEGACY_ALIASES) - _curriculum_ids()
    assert not missing, f"alias keys not in curriculum: {sorted(missing)}"


def test_every_alias_value_was_observed_in_production():
    unknown = {
        alias
        for aliases in LEGACY_ALIASES.values()
        for alias in aliases
    } - OBSERVED_PRODUCTION_IDS
    assert not unknown, f"aliases never observed in production: {sorted(unknown)}"


def test_too_broad_ids_are_never_aliased():
    mapped = {a for aliases in LEGACY_ALIASES.values() for a in aliases}
    overlap = mapped & set(UNMAPPED_TOO_BROAD)
    assert not overlap, f"over-broad ids must stay unmapped: {sorted(overlap)}"


def test_opening_slug_matches_generation_rule():
    # The curriculum id for this name is truncated to exactly 30 chars.
    assert slugify_opening_name("Four Knights Game Italian Variation") == (
        "four_knights_game_italian_vari"
    )
    assert matches_opening_id(
        "four_knights_game_italian_vari", "Four Knights Game Italian Variation"
    )
    assert matches_opening_id("philidor_defense_3_bc4", "Philidor Defense 3.Bc4")
    assert matches_opening_id("italian_game", "Italian Game")


def test_short_curriculum_id_requires_full_equality():
    # "Italian Game" history must not claim a deeper variation's lesson...
    assert not matches_opening_id("italian_game_knight_attack", "Italian Game")
    # ...and a deeper variation must not collapse onto the plain opening.
    assert not matches_opening_id("italian_game", "Italian Game Knight Attack")


def test_exact_match_beats_alias():
    records = [
        {"skill_id": "endgame_rule_of_square", "seen": 9},
        {"skill_id": "king_and_pawn/square_rule", "seen": 2},
    ]
    hit = find_skill_record(records, "king_and_pawn/square_rule")
    assert hit is not None and hit["seen"] == 2


def test_alias_found_when_exact_absent():
    records = [{"skill_id": "endgame_rule_of_square", "seen": 9, "wrong": 3}]
    hit = find_skill_record(records, "king_and_pawn/square_rule")
    assert hit is not None and hit["seen"] == 9


def test_candidate_order_prefers_the_curriculum_id():
    assert candidate_skill_ids("basic_mates/rook_mate")[0] == "basic_mates/rook_mate"
    assert "mate_kr_vs_k" in candidate_skill_ids("basic_mates/rook_mate")


def test_broad_history_produces_no_lesson_match():
    records = [{"skill_id": "king_pawn_endgame", "seen": 30}]
    for lesson in (
        "king_and_pawn/square_rule",
        "king_and_pawn/opposition",
        "king_and_pawn/key_squares",
    ):
        assert find_skill_record(records, lesson) is None


def _lesson(kind="endgame", cid="king_and_pawn/square_rule"):
    return {
        "kind": kind,
        "id": cid,
        "canonical_source": "endgames",
        "content_version": "v1",
    }


def test_profile_surfaces_legacy_history_anchor():
    memory = {
        "learning": {
            "skills": [
                {"skill_id": "endgame_rule_of_square", "seen": 12,
                 "wrong": 0, "applied": 4},
            ]
        }
    }
    profile = derive_personal_teaching_profile(
        skill_id="king_and_pawn/square_rule",
        canonical_lesson=_lesson(),
        coach_memory=memory,
    )
    messages = " ".join(a.get("message", "") for a in profile.get("anchors", []))
    assert "used this idea in a game before" in messages


def test_profile_stays_silent_on_broad_history():
    memory = {"learning": {"skills": [{"skill_id": "king_pawn_endgame",
                                       "seen": 30, "wrong": 10}]}}
    profile = derive_personal_teaching_profile(
        skill_id="king_and_pawn/square_rule",
        canonical_lesson=_lesson(),
        coach_memory=memory,
    )
    messages = " ".join(a.get("message", "") for a in profile.get("anchors", []))
    assert "met this idea" not in messages
    assert "used this idea" not in messages
