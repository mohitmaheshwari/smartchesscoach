from __future__ import annotations

import json

import chess
import chess.pgn

from scripts import build_exact_terminal_checkmate_caption_packet as builder
from services.caption_facts import build_exact_terminal_fact
from services.caption_pipeline import build_exact_terminal_teaching


def _game(moves: list[str], *, identity: str) -> chess.pgn.Game:
    game = chess.pgn.Game()
    game.headers.update({
        "Event": "Private-looking source event",
        "White": f"private-white-{identity}",
        "Black": f"private-black-{identity}",
        "WhiteElo": "1000",
        "BlackElo": "1000",
        "Variant": "Standard",
    })
    board = game.board()
    node: chess.pgn.GameNode = game
    for san in moves:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)
    return game


def _cycles(count: int) -> list[str]:
    return [move for _ in range(count) for move in ("Nf3", "Nf6", "Ng1", "Ng8")]


def _source_games() -> list[chess.pgn.Game]:
    candidates = [
        _game(
            _cycles(index) + ["f3", "e5", "g4", "Qh4#"],
            identity=f"mate-{index}",
        )
        for index in range(50)
    ]
    controls = [
        _game(
            _cycles(index) + ["e4", "e5", "Nf3"],
            identity=f"control-{index}",
        )
        for index in range(20)
    ]
    check_controls = [
        _game(
            _cycles(index) + [
                "e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7+",
            ],
            identity=f"check-control-{index}",
        )
        for index in range(4)
    ]
    return candidates + controls + check_controls


def test_packet_is_blinded_identity_free_and_bound_to_exact_board_truth(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "public-prefix.zst"
    source.write_bytes(b"bounded-public-source")
    games = _source_games()
    monkeypatch.setattr(builder, "_read_source_games", lambda *args, **kwargs: games)

    packet, membership = builder.build_packet(
        source_path=source,
        release_id="lichess_db_standard_rated_test",
        release_sha256="a" * 64,
        with_membership=True,
    )

    assert len(packet["cases"]) == 70
    assert len(membership["candidate_case_ids"]) == 50
    assert len(membership["control_case_ids"]) == 20
    assert len({case["case_id"] for case in packet["cases"]}) == 70
    assert set(membership["candidate_case_ids"]).isdisjoint(
        membership["control_case_ids"]
    )
    serialized = json.dumps(packet)
    assert "private-white" not in serialized
    assert "private-black" not in serialized
    assert "source_unit" not in serialized
    assert "control_family" not in serialized
    assert "Qh4#" not in serialized

    candidates = set(membership["candidate_case_ids"])
    for case in packet["cases"]:
        assert not case["played_move"]["san_without_check_suffix"].endswith(
            ("+", "#")
        )
        fact = build_exact_terminal_fact(
            fen_before=case["position"]["fen"],
            played_move=case["played_move"]["uci"],
        )
        assert (fact is not None) == (case["case_id"] in candidates)
        if fact is not None:
            rendered = build_exact_terminal_teaching(fact)
            assert case["proposed_player_copy"] == {
                "headline": rendered["headline"],
                "explanation": rendered["explanation"],
                "principle": rendered["principle"],
            }


def test_answer_key_binds_the_frozen_packet_and_keeps_membership_separate(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "public-prefix.zst"
    source.write_bytes(b"bounded-public-source")
    monkeypatch.setattr(
        builder,
        "_read_source_games",
        lambda *args, **kwargs: _source_games(),
    )
    packet, membership = builder.build_packet(
        source_path=source,
        release_id="lichess_db_standard_rated_test",
        release_sha256="b" * 64,
        with_membership=True,
    )
    answer_key = builder.build_answer_key(
        packet=packet,
        membership=membership,
        packet_sha256="c" * 64,
    )
    assert answer_key["sealed"] is True
    assert answer_key["source_packet"]["sha256"] == "c" * 64
    assert answer_key["source_packet"]["selection_fingerprint_sha256"] == (
        packet["selection"]["selection_fingerprint_sha256"]
    )
