import ast
from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import scripts.export_whole_game_review_evidence as exporter_module

from scripts.export_whole_game_review_evidence import (
    FORBIDDEN_KEYS,
    FROZEN_DEVELOPMENT_ADJUDICATION_SHA256,
    TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS,
    TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256,
    _max_flow_allocations,
    _sha_members,
    _assert_teaching_intelligence_memberships,
    assert_private,
    assert_comparison_private,
    export_game,
    packet_selection_summary,
    select_teaching_intelligence_memberships,
    validate_system_comparison_gate,
    validate_freeze_marker,
)


def test_membership_digest_is_order_independent_and_separator_safe():
    assert _sha_members(["b", "a"]) == _sha_members(["a", "b"])
    assert _sha_members(["ab", "c"]) != _sha_members(["a", "bc"])


def test_capacity_allocation_meets_every_band_without_exceeding_player_cap():
    cells = {}
    for index, (band, quota) in enumerate(
        {
            "600-799": 19,
            "800-999": 11,
            "1000-1199": 30,
            "1200-1399": 31,
            "1400-1500": 9,
        }.items()
    ):
        for offset in range(quota):
            player = f"p{index}-{offset}"
            cells[(player, band)] = [{"source_game_id": player}]
    allocation = _max_flow_allocations(cells)
    assert sum(allocation.values()) == 100
    per_player = {}
    for (player, _band), amount in allocation.items():
        per_player[player] = per_player.get(player, 0) + amount
    assert max(per_player.values()) <= 3


@pytest.mark.parametrize(
    "payload",
    [
        {"game_id": "secret"},
        {"nested": [{"caption": "the system answer"}]},
        {"safe": "person@example.com"},
        {"safe": "https://example.com/game"},
    ],
)
def test_anonymizer_rejects_identity_answer_and_network_fields(payload):
    with pytest.raises(ValueError):
        assert_private(payload, ())


def test_anonymizer_rejects_a_source_identity_even_under_a_safe_key():
    with pytest.raises(ValueError):
        assert_private({"opaque": "internal-user-42"}, {"internal-user-42"})


def test_holdout_requires_a_complete_freeze_marker(tmp_path: Path):
    path = tmp_path / "freeze.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "whole_game_review_implementation_freeze.v1",
                "implementation_frozen": True,
                "holdout_open_authorized": False,
                "development_adjudication_sha256": "a" * 64,
                "source_commit": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        validate_freeze_marker(path)


def test_holdout_accepts_only_a_bound_complete_freeze_marker(tmp_path: Path):
    path = tmp_path / "freeze.json"
    marker = {
        "schema_version": "whole_game_review_implementation_freeze.v1",
        "implementation_frozen": True,
        "holdout_open_authorized": True,
        "development_adjudication_sha256": "a" * 64,
        "source_commit": "b" * 40,
    }
    path.write_text(json.dumps(marker), encoding="utf-8")
    assert validate_freeze_marker(path) == marker


def test_export_game_includes_stored_evidence_for_both_sides():
    pgn = "1. e4 e5 2. Nf3 Nc6"
    row = {
        "source_game_id": "game-1",
        "source_player_id": "player-1",
        "band": "1000-1199",
        "game": {
            "pgn": pgn,
            "user_color": "white",
            "result": "*",
            "opening": "King's Pawn Game",
            "time_control_category": "rapid",
        },
    }
    initial = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    analysis = {
        "decryption_v5_version": "v1",
        "decryption_v5_data": [
            {"fen_before": initial, "move_san": "e4", "phase": "opening"},
            {"fen_before": after_e4, "move_san": "e5", "phase": "opening"},
        ],
        "stockfish_analysis": {
            "move_evaluations": [{
                "fen_before": initial,
                "move": "e4",
                "move_uci": "e2e4",
                "best_move": "e4",
                "best_move_uci": "e2e4",
            }],
            "opponent_move_evaluations": [{
                "fen_before": after_e4,
                "move": "e5",
                "move_uci": "e7e5",
                "best_move": "e5",
                "best_move_uci": "e7e5",
            }],
        },
    }

    packet_game, _sensitive = export_game(row, analysis)

    assert [
        (item["ply"], item["actor"])
        for item in packet_game["stored_engine_evidence"]
    ] == [
        (1, "player"),
        (2, "opponent"),
    ]


def test_packet_summary_does_not_reuse_raw_player_field_names():
    rows = [{
        "source_player_id": "p1",
        "source_game_id": "g1",
        "band": "1000-1199",
        "phase_combination": "opening_only",
        "game": {
            "user_color": "black",
            "platform": "chess.com",
            "time_control_category": "rapid",
        },
    }]

    summary = packet_selection_summary(rows)

    assert "color" not in summary
    assert summary["player_color"] == [{"value": "black", "games": 1}]
    assert_private(summary, {"p1", "g1"})


def test_comparison_privacy_allows_frozen_caption_but_rejects_identity():
    assert "caption" in assert_comparison_private(
        {"caption": "Move the rook before taking."},
        (),
    )
    with pytest.raises(ValueError):
        assert_comparison_private({"user_id": "hidden"}, ())
    with pytest.raises(ValueError):
        assert_comparison_private(
            {"caption": "Hello internal-user-42"},
            {"internal-user-42"},
        )


def test_frozen_adjudication_hash_is_full_sha256():
    assert len(FROZEN_DEVELOPMENT_ADJUDICATION_SHA256) == 64


def test_teaching_intelligence_system_baseline_opens_only_for_frozen_review():
    review_path = (
        Path(__file__).resolve().parents[1]
        / "data/detector_gold/deterministic_teaching_intelligence_codex_complete_game_review_v1.json"
    )
    assert hashlib.sha256(review_path.read_bytes()).hexdigest() == (
        TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256
    )
    with pytest.raises(ValueError, match="frozen complete-game review"):
        validate_system_comparison_gate(
            cycle=exporter_module.TEACHING_INTELLIGENCE_CYCLE,
            adjudication_sha256=None,
        )
    with pytest.raises(ValueError, match="frozen complete-game review"):
        validate_system_comparison_gate(
            cycle=exporter_module.TEACHING_INTELLIGENCE_CYCLE,
            adjudication_sha256="0" * 64,
        )
    assert validate_system_comparison_gate(
        cycle=exporter_module.TEACHING_INTELLIGENCE_CYCLE,
        adjudication_sha256=TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256,
    ) == TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256


def test_forbidden_contract_includes_labels_and_raw_source_fields():
    assert {
        "email",
        "user_id",
        "game_id",
        "pgn",
        "caption",
        "cognitive_gap",
        "quality_id",
    }.issubset(FORBIDDEN_KEYS)


def test_exporter_cannot_invoke_runtime_composer_or_spawn_an_engine():
    source = inspect.getsource(exporter_module)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called_names.add(func.id)
            elif isinstance(func, ast.Attribute):
                called_names.add(func.attr)

    assert "services.game_decryption_v5_service" not in imported_modules
    assert not {
        "generate_game_decryption_v5",
        "popen_uci",
        "SimpleEngine",
        "Popen",
    } & called_names
    assert "recompose_system" not in source


def _fresh_cycle_rows():
    bands = tuple(TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS)
    rows = []
    for player_index in range(34):
        for game_index in range(12):
            band = bands[(player_index + game_index) % len(bands)]
            rows.append({
                "source_player_id": f"player-{player_index}",
                "source_game_id": f"game-{player_index}-{game_index}",
                "band": band,
            })
    return rows


def test_fresh_cycle_excludes_every_consumed_game_and_reserves_one_holdout_per_player():
    rows = _fresh_cycle_rows()
    prior_development = [
        row for row in rows if row["source_game_id"].endswith(("-0", "-1", "-2"))
    ]
    prior_holdout = [
        row for row in rows if row["source_game_id"].endswith("-3")
    ]

    development, holdout, qualified = select_teaching_intelligence_memberships(
        rows,
        prior_development=prior_development,
        prior_holdout=prior_holdout,
    )

    consumed_ids = {
        row["source_game_id"] for row in (*prior_development, *prior_holdout)
    }
    development_ids = {row["source_game_id"] for row in development}
    holdout_ids = {row["source_game_id"] for row in holdout}
    assert len(qualified) == len(rows)
    assert len(holdout) == 34
    assert len({row["source_player_id"] for row in holdout}) == 34
    assert len(development) == 100
    assert not consumed_ids & (development_ids | holdout_ids)
    assert not development_ids & holdout_ids
    assert Counter(row["band"] for row in development) == Counter(
        TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS
    )
    assert max(Counter(
        row["source_player_id"] for row in development
    ).values()) <= 3


def test_fresh_cycle_excludes_players_below_the_measured_eight_game_floor():
    rows = _fresh_cycle_rows()
    rows.extend({
        "source_player_id": "too-small",
        "source_game_id": f"small-{index}",
        "band": "1000-1199",
    } for index in range(7))

    development, holdout, qualified = select_teaching_intelligence_memberships(
        rows,
        prior_development=(),
        prior_holdout=(),
    )

    assert all(row["source_player_id"] != "too-small" for row in qualified)
    assert all(row["source_player_id"] != "too-small" for row in development)
    assert all(row["source_player_id"] != "too-small" for row in holdout)


def test_fresh_cycle_content_export_fails_until_membership_hashes_are_pinned(
    monkeypatch,
):
    rows = _fresh_cycle_rows()
    development, holdout, qualified = select_teaching_intelligence_memberships(
        rows,
        prior_development=(),
        prior_holdout=(),
    )

    monkeypatch.setattr(
        exporter_module,
        "TEACHING_INTELLIGENCE_EXPECTED_CORPUS_SHA256",
        "",
    )
    monkeypatch.setattr(
        exporter_module,
        "TEACHING_INTELLIGENCE_EXPECTED_DEVELOPMENT_SHA256",
        "",
    )
    monkeypatch.setattr(
        exporter_module,
        "TEACHING_INTELLIGENCE_EXPECTED_HOLDOUT_SHA256",
        "",
    )
    with pytest.raises(ValueError, match="membership is not pinned"):
        _assert_teaching_intelligence_memberships(
            qualified,
            development,
            holdout,
            metadata={"previous_overlap": 0},
        )
