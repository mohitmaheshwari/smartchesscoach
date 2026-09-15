from __future__ import annotations

import io

import chess.pgn
import pytest

from scripts import build_community_game_study_review_packet as builder


LITERATE = """[Event "Anonymous fixture"]
[Site "https://lichess.org/AbCd1234"]
[Result "1-0"]
[WhiteElo "1100"]
[BlackElo "1120"]
[TimeControl "600+0"]
[Variant "Standard"]

1. e4 { [%eval 0.20] } e5 { [%eval 0.10] }
2. Nf3?! { (0.10 -> -0.80) Inaccuracy. Nc3 was best. [%eval -0.80] }
(2. Nc3 Nc6 3. Nf3 Nf6) 2... Nc6 { [%eval -0.60] }
3. Bb5 { [%eval -0.55] } a6 { [%eval -0.40] } 1-0
"""


def _game():
    game = chess.pgn.read_game(io.StringIO(LITERATE))
    assert game is not None
    assert not game.errors
    return game


def test_rows_recover_stored_best_variation_without_inventing_played_pv():
    rows = builder.rows_from_literate_game(_game())
    row = rows[2]
    assert row["move"] == "Nf3"
    assert row["best_move"] == "Nc3"
    assert row["pv_after_best"][:2] == ["Nc6", "Nf3"]
    assert row["pv_after_played"] == []
    assert row["cp_loss"] == 90


def test_source_candidate_requires_same_canonical_band_and_strips_identity():
    game = _game()
    # The compact fixture is intentionally below the production density floor.
    assert builder._source_candidate(game) is None
    game.headers["WhiteElo"] = "999"
    game.headers["BlackElo"] = "1000"
    assert builder._rating_band(999) != builder._rating_band(1000)


def test_sanitized_movetext_contains_no_headers_or_names():
    rendered = builder._sanitized_movetext(_game())
    assert "Anonymous fixture" not in rendered
    assert "WhiteElo" not in rendered
    assert "1. e4" in rendered


def test_cp_loss_preserves_white_pov_direction_for_both_sides():
    assert builder._cp_loss(100, -50, True) == 150
    assert builder._cp_loss(-50, 100, False) == 150
    assert builder._cp_loss(0, 30, True) == 0


def test_demonstration_must_replay_legally_and_match_its_branch_kind():
    assert builder._validated_demonstration(
        fen_before=chess.STARTING_FEN,
        played_san="e4",
        value={"kind": "played_refutation", "moves_san": ["e4", "e5"]},
    ) == {"kind": "played_refutation", "moves_san": ["e4", "e5"]}
    with pytest.raises(builder.CommunityGameStudyError, match="does not start"):
        builder._validated_demonstration(
            fen_before=chess.STARTING_FEN,
            played_san="e4",
            value={"kind": "played_refutation", "moves_san": ["d4", "d5"]},
        )
    with pytest.raises(builder.CommunityGameStudyError, match="not legal"):
        builder._validated_demonstration(
            fen_before=chess.STARTING_FEN,
            played_san="e4",
            value={"kind": "better_line", "moves_san": ["e5"]},
        )


def test_blank_reviewer_response_is_machine_checkable_and_unanswered():
    response = builder.blank_reviewer_response()
    assert response["schema_version"] == (
        "community_game_study.independent_review_response.v1"
    )
    assert response["would_assign_to_a_player_in_this_band"] is None
    assert response["whole_game_story_is_coherent"] is None
    assert response["repeats_primary_principle_as_separate_chapters"] is None
    assert response["chapter_verdicts"] == []
