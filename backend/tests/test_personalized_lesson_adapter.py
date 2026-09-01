import asyncio

from services.personalized_lesson_adapter import (
    grade_personalized_move,
    public_lesson_descriptor,
    resolve_personalized_lesson,
    select_blind_diagnostic_pair,
    supports_personalized_lesson_identity,
)


class _NoDB:
    pass


def test_verified_endgame_is_normalized_without_public_answers():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="endgame",
        content_id="king_and_pawn/square_rule",
    ))
    public = public_lesson_descriptor(descriptor)

    assert public["canonical_source"] == (
        "backend/data/coaching/endgame_theory_tree.json"
    )
    assert public["items"][-1]["stage"] == "transfer"
    assert all(
        "correct_move" not in str(item)
        and "_endgame_position_index" not in item
        for item in public["items"]
    )


def test_verified_opening_projection_reads_canonical_authored_steps():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="opening",
        content_id="london_system",
        params={"player_color": "white"},
    ))
    public = public_lesson_descriptor(descriptor)

    assert public["canonical_source"] == "backend/data/opening_curriculum.json"
    assert public["items"]
    assert all("_expected_san" not in item for item in public["items"])
    assert all("_expected_reason" not in item for item in public["items"])
    assert public["items"][0]["reason_choices"]
    assert public["content_version"]
    assert descriptor["skill_id"] == "opening_london_white"


def test_verified_trap_projection_is_defense_first_when_available():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap",
        content_id="scholars_mate",
        params={"mode": "avoidance"},
    ))

    assert descriptor["canonical_source"] == "backend/data/traps.json"
    assert descriptor["skill_id"] == "defend_scholars_mate"
    assert descriptor["items"]
    assert "danger" in descriptor["intro"].lower() or descriptor["rule"]


def test_verified_trap_set_is_one_distinct_defense_per_family_trap():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap_set",
        content_id="italian-game",
        params={"skill_id": "trap_set_italian"},
    ))
    public = public_lesson_descriptor(descriptor)

    assert descriptor["kind"] == "trap_set"
    assert descriptor["canonical_source"] == "backend/data/traps.json"
    assert descriptor["skill_id"] == "trap_set_italian"
    assert len(descriptor["items"]) == 5
    assert len({item["fen"] for item in descriptor["items"]}) == 5
    assert descriptor["items"][-1]["stage"] == "transfer"
    assert all("_expected_uci" not in item for item in public["items"])


def test_verified_endgame_uses_tree_skill_id_without_explicit_param():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="endgame",
        content_id="king_and_pawn/square_rule",
    ))

    assert descriptor["skill_id"] == "endgame_rule_of_square"


def test_verified_trap_set_uses_tree_skill_id_without_explicit_param():
    descriptor = asyncio.run(resolve_personalized_lesson(
        _NoDB(),
        "u1",
        content_kind="trap_set",
        content_id="italian-game",
    ))

    assert descriptor["skill_id"] == "trap_set_italian"


def test_curriculum_only_enters_workspace_for_resolvable_canonical_lessons():
    assert supports_personalized_lesson_identity(
        "opening", "london_system"
    )
    assert supports_personalized_lesson_identity(
        "trap", "fried_liver_defense"
    )
    assert supports_personalized_lesson_identity(
        "trap_set", "italian-game"
    )
    assert supports_personalized_lesson_identity(
        "endgame", "basic_mates/queen_mate"
    )
    assert supports_personalized_lesson_identity(
        "concept", "piece_safety"
    )
    assert not supports_personalized_lesson_identity(
        "concept", "iqp_play"
    )
    assert not supports_personalized_lesson_identity(
        "concept", "not_a_real_lesson"
    )


def _pair_candidate(pid, game, fen, piece, quality="q", version="v1"):
    return {
        "puzzle_id": pid,
        "source_game_id": game,
        "normalized_fen": fen,
        "moved_piece": piece,
        "quality_id": quality,
        "detector_version": version,
    }


def test_blind_pair_requires_different_game_position_piece_and_same_proof():
    base = _pair_candidate("p1", "g1", "fen-1", "rook")
    candidates = [
        base,
        _pair_candidate("same-game", "g1", "fen-2", "bishop"),
        _pair_candidate("same-fen", "g2", "fen-1", "bishop"),
        _pair_candidate("same-piece", "g2", "fen-2", "rook"),
        _pair_candidate("mixed-quality", "g2", "fen-2", "bishop", quality="other"),
        _pair_candidate("mixed-version", "g2", "fen-2", "bishop", version="v2"),
        _pair_candidate("valid", "g3", "fen-3", "queen"),
    ]

    pair = select_blind_diagnostic_pair(candidates)
    assert [item["puzzle_id"] for item in pair["items"]] == ["p1", "valid"]
    assert pair["fingerprint"]


def test_blind_pair_fails_closed_when_only_lookalikes_exist():
    candidates = [
        _pair_candidate("p1", "g1", "fen-1", "rook"),
        _pair_candidate("p2", "g2", "fen-2", "rook"),
    ]
    assert select_blind_diagnostic_pair(candidates) is None


def _diagnostic_item():
    return {
        "item_id": "diagnostic-position-1",
        "fen": "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
        "_diagnostic_quality_id": "gap:piece_safety:destination_safety_exact",
        "_detector_version": "piece_safety.destination_safety_exact.v1",
    }


def test_diagnostic_grading_keeps_target_and_soundness_separate(monkeypatch):
    async def losing_move(*args, **kwargs):
        return {"quality": "mistake", "is_acceptable": False}

    monkeypatch.setattr(
        "services.puzzle_move_evaluator.evaluate_puzzle_move",
        losing_move,
    )
    result = asyncio.run(grade_personalized_move(
        {"kind": "concept"},
        _diagnostic_item(),
        "d1a1",
    ))

    assert result["target_result"] == "pass"
    assert result["correct"] is True
    assert result["soundness"]["status"] == "serious_problem"
    assert result["answer_uci"] is None


def test_diagnostic_safe_sound_move_passes_both_checks(monkeypatch):
    async def acceptable(*args, **kwargs):
        return {"quality": "good", "is_acceptable": True}

    monkeypatch.setattr(
        "services.puzzle_move_evaluator.evaluate_puzzle_move",
        acceptable,
    )
    result = asyncio.run(grade_personalized_move(
        {"kind": "concept"},
        _diagnostic_item(),
        "d1a1",
    ))
    assert result["target_result"] == "pass"
    assert result["soundness"]["status"] == "sound"


def test_diagnostic_minor_inaccuracy_is_not_called_a_serious_problem(monkeypatch):
    async def inaccuracy(*args, **kwargs):
        return {"quality": "inaccuracy", "is_acceptable": False}

    monkeypatch.setattr(
        "services.puzzle_move_evaluator.evaluate_puzzle_move",
        inaccuracy,
    )
    result = asyncio.run(grade_personalized_move(
        {"kind": "concept"},
        _diagnostic_item(),
        "d1a1",
    ))
    assert result["target_result"] == "pass"
    assert result["soundness"]["status"] == "sound"


def test_diagnostic_destination_loss_fails_target_even_if_other_grader_accepts(monkeypatch):
    async def acceptable(*args, **kwargs):
        return {"quality": "good", "is_acceptable": True}

    monkeypatch.setattr(
        "services.puzzle_move_evaluator.evaluate_puzzle_move",
        acceptable,
    )
    result = asyncio.run(grade_personalized_move(
        {"kind": "concept"},
        _diagnostic_item(),
        "d1d5",
    ))
    assert result["target_result"] == "fail"
    assert result["correct"] is False


class _ObservationCursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *args):
        return self

    def limit(self, *args):
        return self

    async def to_list(self, length=None):
        return list(self.rows)


class _Observations:
    def __init__(self, rows):
        self.rows = rows
        self.query = None

    def find(self, query, projection):
        self.query = query
        return _ObservationCursor(self.rows)


class _DiagnosticDB:
    def __init__(self, rows):
        self.move_observations = _Observations(rows)


def test_blind_descriptor_reads_exact_observations_not_generic_puzzle_supply(monkeypatch):
    rows = [
        {"game_id": "g1", "move_number": 3, "fen_before": "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1"},
        {"game_id": "g2", "move_number": 8, "fen_before": "r3k3/8/8/8/8/8/8/R3K3 w - - 0 1"},
    ]
    resolved = {
        "g1_m3": {
            "puzzle_id": "g1_m3",
            "fen": rows[0]["fen_before"],
            "verified_admission": {
                "quality_id": "gap:piece_safety:destination_safety_exact",
                "detector_version": "piece_safety.destination_safety_exact.v1",
                "played_move_uci": "d1d5",
            },
        },
        "g2_m8": {
            "puzzle_id": "g2_m8",
            "fen": rows[1]["fen_before"],
            "verified_admission": {
                "quality_id": "gap:piece_safety:destination_safety_exact",
                "detector_version": "piece_safety.destination_safety_exact.v1",
                "played_move_uci": "a1a5",
            },
        },
    }

    async def resolve(db, puzzle_id, user_id=None):
        return resolved.get(puzzle_id)

    monkeypatch.setattr(
        "services.verified_puzzle_runtime.resolve_verified_puzzle", resolve
    )
    db = _DiagnosticDB(rows)
    descriptor = asyncio.run(resolve_personalized_lesson(
        db,
        "u1",
        content_kind="concept",
        content_id="piece_safety",
        params={"mode": "blind_diagnostic"},
    ))

    assert descriptor["delivery_mode"] == "blind_diagnostic"
    assert [item["item_id"] for item in descriptor["items"]] == [
        "diagnostic-position-1", "diagnostic-position-2"
    ]
    assert descriptor["items"][0]["_moved_piece"] == "queen"
    assert descriptor["items"][1]["_moved_piece"] == "rook"
    assert descriptor["items"][0]["_help_squares"] == ["d1"]
    assert descriptor["items"][1]["_help_squares"] == ["a1"]
    assert db.move_observations.query["destination_safety_exact.fires"] is True
