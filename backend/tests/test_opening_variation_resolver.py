import chess

from services.opening_variation_resolver import (
    OpeningVariationResolver,
    _variation_count,
)
from services.curriculum_content_validator import get_publishable_content_ids
from services.engine2_skill_builder import (
    _augment_endgames_from_catalog,
    _augment_openings_from_curriculum,
    _augment_trap_sets_from_catalog,
)
from services.opening_library_service import resolve_teachable_opening
from services.opening_theory_json_service import (
    get_all_lesson_move_paths,
    get_lesson_move_steps,
    get_opening_theory,
)


def _uci_identity(path):
    board = chess.Board()
    moves = []
    for step in path:
        move = board.parse_san(step["move"])
        moves.append(move.uci())
        board.push(move)
    return tuple(moves)


def test_json_list_pair_preserves_game_count():
    assert _variation_count(["Caro Kann Defense", 17]) == 17


def test_resolve_real_mapper_row_does_not_crash():
    resolver = OpeningVariationResolver()
    result = resolver.resolve("Caro Kann Defense")

    assert result is not None
    assert result["base_opening"] == "Caro Kann Defense"
    assert result["game_count"] >= 0


def test_get_variations_shapes_json_pairs():
    resolver = OpeningVariationResolver()
    resolver.base_to_variations = {
        "Example": [["Example Main Line", 5], ["Example Side Line", 2]],
    }

    assert resolver.get_variations("Example") == [
        {"variation": "Example Main Line", "games": 5},
        {"variation": "Example Side Line", "games": 2},
    ]


def test_recognition_only_variation_routes_to_verified_family_foundation():
    result = resolve_teachable_opening("petrovs_defense_classical_vari")

    assert result is not None
    assert result["lesson_key"] == "petrov_defense"
    assert result["lesson_relation"] == "family_foundation"
    assert result["recognized_opening_name"] == "Petrovs Defense Classical Variation"


def test_complete_opening_remains_an_exact_lesson():
    result = resolve_teachable_opening("italian-game")

    assert result is not None
    assert result["lesson_key"] == "italian_game"
    assert result["lesson_relation"] == "exact_lesson"


def test_completed_foundation_remains_an_exact_lesson():
    result = resolve_teachable_opening("van_t_kruijs_opening")

    assert result is not None
    assert result["lesson_key"] == "van_t_kruijs_opening"
    assert result["lesson_relation"] == "exact_lesson"


def test_explicit_provider_alias_routes_to_canonical_foundation():
    result = resolve_teachable_opening("center_game_accepted_normal_va")

    assert result is not None
    assert result["lesson_key"] == "center_game"
    assert result["lesson_relation"] == "family_foundation"
    assert result["recognized_opening_name"] == "Center Game Accepted Normal Variation"


def test_every_recognition_only_opening_has_an_honest_teachable_foundation():
    publishable = get_publishable_content_ids("openings")
    from services.opening_unified_source import get_unified_source

    openings = get_unified_source().get_all_openings()
    unresolved = {
        key
        for key in openings
        if key not in publishable and resolve_teachable_opening(key) is None
    }

    assert unresolved == set()


def test_every_authored_variation_is_in_the_canonical_lesson_path_index():
    for opening_key in get_publishable_content_ids("openings"):
        opening = get_opening_theory(opening_key) or {}
        indexed = {
            _uci_identity(path)
            for path in get_all_lesson_move_paths(opening_key)
        }
        for variation_key in (opening.get("variations") or {}):
            authored = get_lesson_move_steps(opening_key, variation_key)
            assert authored, (opening_key, variation_key)
            assert _uci_identity(authored) in indexed, (opening_key, variation_key)


def test_engine2_derives_only_publishable_opening_lessons():
    skills = {}
    _augment_openings_from_curriculum(skills)
    publishable = get_publishable_content_ids("openings")

    refs = {
        skill["content_ref"]
        for skill in skills.values()
        if skill.get("kind") == "opening"
    }
    assert refs
    assert refs <= publishable
    assert "petrovs_defense_classical_vari" not in refs


def test_verified_trap_sets_inherit_their_opening_envelope():
    skills = {}
    _augment_openings_from_curriculum(skills)
    _augment_trap_sets_from_catalog(skills)

    trap = skills["trap_set_queens_gambit"]
    opening = next(
        node
        for node in skills.values()
        if node.get("kind") == "opening"
        and node.get("content_ref") == "queens_gambit"
    )
    assert trap["content_ref"] == "queens-gambit"
    assert trap["rating_min"] == opening["rating_min"]
    assert trap["rating_max"] == opening["rating_max"]
    assert trap["prerequisites"]


def test_missing_endgames_reuse_existing_category_envelope():
    skills = {
        "endgame_opposition": {
            "kind": "endgame",
            "label": "Opposition",
            "content_ref": "opposition",
            "prerequisites": [],
            "rating_min": 1000,
            "rating_max": 1499,
            "tier": 1,
        }
    }
    _augment_endgames_from_catalog(skills)

    key_squares = skills["endgame_key_squares"]
    assert key_squares["content_ref"] == "king_and_pawn/key_squares"
    assert key_squares["rating_min"] == 1000
    assert key_squares["rating_max"] == 1499
