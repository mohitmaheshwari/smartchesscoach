"""Committed regression coverage for the offline reasoning evidence substrate."""
from dataclasses import asdict, replace

import chess
import pytest

from services.reasoning import ReasoningConfig, explain_fen
from services.reasoning.engine import input_board
from services.reasoning.objectives import generate
from services.reasoning.search import comparison, score_order
from services.reasoning.timeline import build_timeline, event_facts
from services.reasoning.verify import verify, verify_dependencies
from services.stored_line_verifier import relationship_snapshot


NA4 = "r4rk1/ppp1bppp/5n2/4p3/1PPq2b1/P1N5/1B1PBPPP/R2QR1K1 w - - 0 13"
QF8 = "4r2r/2Q1bkq1/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR b - - 2 24"
CASTLE = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"


def config(**changes):
    values = dict(engine_path="unused-by-board-tests", nodes=100, stability_nodes=200,
                  max_queries=16, max_total_nodes=10000, rank_width=3, root_cap=3,
                  reply_width=2, max_plies=18, max_hypotheses=80,
                  max_expanded_nodes=16, hash_mb=16, equivalence_cp=30)
    return ReasoningConfig(**(values | changes))


def checked_line(fen, moves):
    line = build_timeline(chess.Board(fen), moves, "fixture-search", 18)
    facts = event_facts(line)
    hypotheses, extra = generate(line, facts)
    facts += extra
    return line, facts, hypotheses


@pytest.fixture
def sequence():
    return checked_line(NA4, ["c3d5", "g4e2", "b2d4", "e2d1", "d5e7", "g8h8", "d4e5"])


def test_every_generated_board_fact_verifies(sequence):
    line, facts, _ = sequence
    assert facts
    assert all(verify(p, line) is None for p in facts)


def test_sequence_joins_without_a_position_specific_detector(sequence):
    line, facts, hypotheses = sequence
    selected = next(h for h in hypotheses if h.operation == "SEQUENCE" and h.objective.get("target_id") == "black:bishop:e7")
    assert selected.objective["root_connected"]
    assert verify_dependencies(selected, {p.id: asdict(p) for p in facts}, {line["id"]: line}) is None


def test_only_reply_belongs_to_the_replying_side(sequence):
    _, facts, _ = sequence
    fact = next(p for p in facts if p.relation == "only_legal_reply" and p.ply == 5)
    assert fact.actor == "black"
    assert fact.subject == "g8h8"


@pytest.mark.parametrize("changes", [
    {"actor": "white"}, {"polarity": False}, {"quantifier": "all_continuations"},
    {"ply": 4}, {"object": "another-node"}, {"evidence_ids": ("unknown",)},
    {"evidence_class": "exhaustive_proof"}, {"timeline_id": "another-branch"},
])
def test_altered_only_reply_claim_is_rejected(sequence, changes):
    line, facts, _ = sequence
    fact = next(p for p in facts if p.relation == "only_legal_reply" and p.ply == 5)
    assert verify(replace(fact, **changes), line) is not None


@pytest.mark.parametrize("changes", [
    {"subject": "black:knight:f6"}, {"object": "white:bishop:e2"}, {"data": {}},
    {"relation": "wins_material"}, {"actor": "black"}, {"ply": 3},
])
def test_altered_capture_is_rejected(sequence, changes):
    line, facts, _ = sequence
    fact = next(p for p in facts if p.relation == "captures" and p.ply == 5)
    assert verify(replace(fact, **changes), line) is not None


def test_capture_square_is_bound_to_the_event(sequence):
    line, facts, _ = sequence
    fact = next(p for p in facts if p.relation == "captures" and p.ply == 5)
    assert verify(replace(fact, data=fact.data | {"square": "e2"}), line) is not None


def test_dependency_rejects_wrong_order(sequence):
    line, facts, hypotheses = sequence
    selected = next(h for h in hypotheses if h.operation == "SEQUENCE")
    selected.dependencies[0]["before"] = [selected.dependencies[0]["after"]]
    assert verify_dependencies(selected, {p.id: asdict(p) for p in facts}, {line["id"]: line}) == "wrong_sequence_timing"


@pytest.mark.parametrize("move,gained", [("g7f8", False), ("g7h7", True)])
def test_f5_is_added_by_alternative_never_abandoned_at_origin(move, gained):
    line, facts, _ = checked_line(QF8, [move])
    assert any(p.relation == "coverage_gained" and p.object == "f5" for p in facts) == gained
    assert not any(p.relation == "coverage_abandoned" and p.object == "f5" for p in facts)
    assert all(verify(p, line) is None for p in facts)


def test_castling_preserves_both_rook_lineages():
    line, facts, _ = checked_line(CASTLE, ["e1g1", "e8c8"])
    assert line["nodes"][1]["relations"]["f1"]["piece_id"] == "white:rook:h1"
    assert line["nodes"][2]["relations"]["d8"]["piece_id"] == "black:rook:a8"
    assert all(verify(p, line) is None for p in facts)


def test_en_passant_records_actual_capture_square_and_identity():
    line, _, _ = checked_line("7k/3p4/8/4P3/8/8/8/7K b - - 0 1", ["d7d5", "e5d6"])
    assert line["events"][1]["captured_square"] == "d5"
    assert line["events"][1]["captured_piece_id"] == "black:pawn:d7"


@pytest.mark.parametrize("promotion,piece", [("q", "queen"), ("r", "rook"), ("b", "bishop"), ("n", "knight")])
def test_promotion_retains_lineage_actor_and_actual_type(promotion, piece):
    line, facts, _ = checked_line("7k/P6p/8/8/8/8/8/K7 w - - 0 1", ["a7a8" + promotion])
    assert line["nodes"][1]["relations"]["a8"]["piece_id"] == "white:pawn:a7"
    fact = next(p for p in facts if p.relation == "promotes_to")
    assert (fact.actor, fact.object) == ("white", piece)
    assert verify(fact, line) is None
    assert verify(replace(fact, actor="black"), line) is not None


def test_queenside_castling_needs_rooks_path_cleared_too():
    line, facts, _ = checked_line("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1", ["b1a3"])
    fact = next(p for p in facts if p.relation == "clears_castling_path" and p.object == "c1")
    assert verify(fact, line) is None


def test_unchanged_bishop_relation_is_available_in_every_snapshot(sequence):
    line, _, _ = sequence
    assert line["nodes"][0]["relations"]["b2"]["piece_id"] == "white:bishop:b2"
    assert "d4" in line["nodes"][1]["relations"]["b2"]["attack_squares"]
    assert line["nodes"][2]["relations"]["b2"]["piece_id"] == "white:bishop:b2"


def test_attacked_queen_need_not_move_when_another_piece_mates():
    line, facts, _ = checked_line("7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1", ["e1e8"])
    assert chess.Board(line["nodes"][0]["fen"]).is_attacked_by(chess.BLACK, chess.A1)
    assert any(p.relation == "checkmates" and verify(p, line) is None for p in facts)


@pytest.mark.parametrize("moves", [["c3d5", "a1a8"], ["c3d5", "g8h8", "d5d8"]])
def test_illegal_suffix_is_not_accepted_as_a_complete_line(moves):
    with pytest.raises(ValueError):
        build_timeline(chess.Board(NA4), moves, "bad", 18)


def test_relationship_snapshot_rejects_wrong_identity_map():
    with pytest.raises(ValueError):
        relationship_snapshot(chess.Board(NA4), {})


def test_history_must_reproduce_all_rule_state():
    board = chess.Board()
    board.push_san("e4")
    assert input_board(board.fen(), {"initial_fen": chess.STARTING_FEN, "moves": ["e4"]})[1] == "complete_from_initial_position"
    with pytest.raises(ValueError):
        input_board(board.fen(), {"initial_fen": chess.STARTING_FEN, "moves": ["d4"]})


@pytest.mark.parametrize("fen", ["bad", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_fen_is_explicitly_rejected(fen):
    with pytest.raises(ValueError):
        input_board(fen, None)


def test_illegal_played_move_is_rejected_before_engine_start():
    with pytest.raises(ValueError, match="illegal_played_move"):
        explain_fen(NA4, "e4", config=config())


def test_terminal_position_does_not_need_engine():
    result = explain_fen("7k/8/8/8/8/8/8/K7 w - - 0 1", config=config())
    assert result["runtime"]["query_count"] == 0
    assert result["reason_codes"] == ["terminal_position"]


def score(value, kind="cp"):
    return {"kind": kind, "value": value, "pov": "white"}


@pytest.mark.parametrize("value,expected", [(70, "inferior"), (71, "equivalent"), (100, "equivalent"), (131, "better")])
def test_cp_equivalence_boundary(value, expected):
    assert comparison(score(100), score(value), 30) == expected


def test_mate_is_not_centipawns():
    assert comparison(score(1, "mate"), score(8000), 30) == "inferior"
    assert score_order(score(-10, "mate")) > score_order(score(-3, "mate"))


@pytest.mark.parametrize("changes", [{"nodes": 0}, {"root_cap": 1}, {"nodes": True}, {"stability_nodes": 1}, {"max_total_nodes": 1}])
def test_configuration_cannot_silently_break_budget_contract(changes):
    with pytest.raises(ValueError):
        config(**changes)
