from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import chess
import chess.pgn

from scripts import build_exact_terminal_checkmate_caption_packet as builder
from scripts import score_exact_terminal_checkmate_caption_review as scorer


def _game(moves: list[str]) -> chess.pgn.Game:
    game = chess.pgn.Game()
    game.headers.update({
        "White": "source-white",
        "Black": "source-black",
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
    return [
        _game(_cycles(index) + ["f3", "e5", "g4", "Qh4#"])
        for index in range(50)
    ] + [
        _game(_cycles(index) + ["e4", "e5", "Nf3"])
        for index in range(20)
    ]


def _artifacts(tmp_path, monkeypatch):
    source = tmp_path / "source.zst"
    source.write_bytes(b"public-source")
    monkeypatch.setattr(
        builder, "_read_source_games", lambda *args, **kwargs: _source_games()
    )
    packet, membership = builder.build_packet(
        source_path=source,
        release_id="test-release",
        release_sha256="a" * 64,
        with_membership=True,
    )
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    answer_key = builder.build_answer_key(
        packet=packet,
        membership=membership,
        packet_sha256=packet_sha,
    )
    answer_path = tmp_path / "answer.json"
    answer_path.write_text(json.dumps(answer_key), encoding="utf-8")
    reviewed = deepcopy(packet)
    candidate_ids = set(membership["candidate_case_ids"])
    for case in reviewed["cases"]:
        candidate = case["case_id"] in candidate_ids
        case["reviewer_response"] = {
            "schema_version": builder.REVIEW_RESPONSE_SCHEMA_VERSION,
            "verdict": (
                "proved_exact_terminal_checkmate" if candidate else "not_proved"
            ),
            "teaching_verdict": (
                "correct_and_teachable" if candidate else "incorrect_or_overclaimed"
            ),
            "critical_false_claim": not candidate,
            "review_note": "Independent legal-board verification.",
        }
    reviewed["independent_review"] = {
        "packet_sha256": packet_sha,
        "frozen": True,
        "reviewer": "Independent test reviewer",
        "method": "Replayed every move and enumerated every legal reply.",
    }
    reviewed_path = tmp_path / "reviewed.json"
    reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
    return packet_path, reviewed_path, answer_path, reviewed, candidate_ids


def test_perfect_independent_review_clears_exact_caption_gate(tmp_path, monkeypatch):
    packet_path, reviewed_path, answer_path, _, _ = _artifacts(
        tmp_path, monkeypatch
    )
    score = scorer.score_review(
        packet_path=packet_path,
        reviewed_path=reviewed_path,
        answer_key_path=answer_path,
    )
    assert score["confusion_matrix"] == {
        "true_positive": 50,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 20,
    }
    assert score["promotion_gate"]["caption_promotion_gate_passed"] is True
    assert score["caption_evidence"]["wilson_lower_bound_pct"] > 85


def test_any_exact_fact_false_positive_keeps_family_shadow(tmp_path, monkeypatch):
    packet_path, reviewed_path, answer_path, reviewed, candidate_ids = _artifacts(
        tmp_path, monkeypatch
    )
    bad_id = next(iter(candidate_ids))
    case = next(row for row in reviewed["cases"] if row["case_id"] == bad_id)
    case["reviewer_response"]["verdict"] = "not_proved"
    case["reviewer_response"]["review_note"] = "The checked side has a legal reply."
    reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
    score = scorer.score_review(
        packet_path=packet_path,
        reviewed_path=reviewed_path,
        answer_key_path=answer_path,
    )
    assert score["promotion_gate"]["exact_fact_has_zero_false_positives"] is False
    assert score["promotion_gate"]["caption_promotion_gate_passed"] is False
    assert score["promotion_gate"]["status"] == "shadow"
