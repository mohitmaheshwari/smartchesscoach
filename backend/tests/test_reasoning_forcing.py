"""Comparative certificates must survive board, provenance and scope checks."""
from copy import deepcopy
from dataclasses import asdict

import chess
import pytest

from services.reasoning.contracts import SearchRecord
from services.reasoning.forcing import (checking_threat_seeds, legal_threat_witness,
    mate_two_witness, sequence_certificate, sequence_hypothesis, threat_hypothesis, walk)
from services.reasoning.render import render
from services.reasoning.timeline import build_timeline
from services.reasoning.verify import verify, verify_dependencies
from test_reasoning_boundaries import NA4, QF8, config


class CertificateSearch:
    def __init__(self, *, supported=True, budget=True, max_plies=18):
        self.config = config(max_plies=max_plies)
        self.records, self.supported, self.budget = [], supported, budget

    def can_query(self, nodes=None):
        return self.budget

    def query(self, board, purpose, *, roots=(), width=1, nodes=None):
        if purpose == "uncovered_check_resource":
            moves, kind, value = [roots[0].uci(), "e7f6", "f5f6"], "mate", -2
        elif purpose == "added_cover_capture_response":
            moves, kind, value = [roots[0].uci(), "e4f5"], "cp", -500
        else:
            moves, kind, value = ["e8c8"], "cp", -1100
        walk(board, moves)
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots],
                              nodes or self.config.nodes, width, "complete_iteration" if self.supported else "unavailable")
        if self.supported:
            record.lines = [{"root_uci": moves[0], "moves_uci": moves,
                             "score": {"kind": kind, "value": value, "pov": "black"}}]
        self.records.append(record)
        return record


def build_case(fen, played, alternative, setup, *, threat=False, session=None):
    root = chess.Board(fen)
    session = session or CertificateSearch()
    timelines = {}

    def add_line(moves, record, **kwargs):
        line = build_timeline(root, moves, record.id, session.config.max_plies)
        timelines[line["id"]] = line
        return line

    builder = threat_hypothesis if threat else sequence_hypothesis
    h, facts = builder(root, played, alternative, setup, session, add_line)
    return h, facts, timelines, {r.id: r.document() for r in session.records}


def sequence_case():
    return build_case(NA4, "c3a4", "c3d5", "g4e2")


def threat_case(**kwargs):
    return build_case(QF8, "g7f8", "g7h7", "c7d7", threat=True, **kwargs)


def accepted(case):
    h, facts, lines, searches = case
    assert h is not None
    assert all(verify(p, lines[p.timeline_id]) is None for p in facts)
    documents = {p.id: asdict(p) for p in facts}
    assert verify_dependencies(h, documents, lines, searches) is None
    return h, documents, lines, searches


def test_na4_exchange_is_legal_while_nd5_adds_a_checking_capture():
    h, facts, lines, _ = accepted(sequence_case())
    assert h.objective["exchange_san"] == ["Bxd4", "Bxd1", "Raxd1"]
    assert h.objective["resource_san"] == "Nxe7+"
    assert h.objective["certificate"]["legal_check_evasions"] == ["g8h8"]
    assert h.unresolved  # This is a demonstrated exchange, not all-defence minimax.
    output = render(asdict(h), facts, "inferior", {})
    assert "Na4" in output["text"] and "no such checking capture" in output["text"]
    assert "exchanging queens" in output["text"]
    assert "must escape" not in output["text"]


def test_sequence_discovery_is_color_symmetric():
    board = chess.Board(NA4).mirror()
    mirror = lambda raw: chess.Move(chess.square_mirror(chess.Move.from_uci(raw).from_square),
                                   chess.square_mirror(chess.Move.from_uci(raw).to_square)).uci()
    case = build_case(board.fen(), *(mirror(m) for m in ("c3a4", "c3d5", "g4e2")))
    h, facts, _, _ = accepted(case)
    assert "White's" in render(asdict(h), facts, "inferior", {})["text"]


@pytest.mark.parametrize("field,value", [("resource_san", "Nxe7"), ("extra_piece", "rook"),
    ("exchange_san", ["Bxd4"]), ("target_square", "d4"), ("played_san", "Nd5")])
def test_sequence_metadata_is_verified_not_trusted(field, value):
    h, facts, lines, searches = accepted(sequence_case())
    h.objective[field] = value
    assert verify_dependencies(h, facts, lines, searches)


def test_qf8_seed_is_a_diagnostic_coverage_not_gained_hypothesis():
    root = chess.Board(QF8)
    seeds = checking_threat_seeds(root, "g7f8", "g7h7", "c7d7")
    seed = next(s for s in seeds if s["target_square"] == "f5")
    assert seed["origin_covered"] is False
    assert seed["status"] == "diagnostic_seed_only"
    witness = legal_threat_witness(root, seed, 16)
    assert witness["status"] == "legal_conditional_witness"
    assert witness["wait_uci"] == "a6a5"
    assert witness["mate_tree"]["all_evasions"] == ["e7f6"]
    assert witness["capture_answer_uci"] == "h7f5"
    assert legal_threat_witness(root, seed, 0) is None


def test_rc8_refutes_the_universal_mate_reading():
    node = walk(chess.Board(QF8), ["g7f8", "c7d7", "e8c8"])
    assert mate_two_witness(node, chess.Move.from_uci("d7f5")) is None


@pytest.mark.parametrize("transform", [chess.flip_vertical, chess.flip_horizontal])
def test_threat_discovery_uses_geometry_in_transformed_positions(transform):
    root = chess.Board(QF8)
    if transform is chess.flip_vertical:
        board = root.mirror()
    else:
        board = root.transform(transform)
    def mapped(raw):
        move = chess.Move.from_uci(raw)
        source = chess.scan_forward(transform(chess.BB_SQUARES[move.from_square])).__next__()
        target = chess.scan_forward(transform(chess.BB_SQUARES[move.to_square])).__next__()
        return chess.Move(source, target).uci()
    seeds = checking_threat_seeds(board, *(mapped(m) for m in ("g7f8", "g7h7", "c7d7")))
    witnesses = [legal_threat_witness(board, seed, 16) for seed in seeds]
    assert any(witness is not None for witness in witnesses)


def test_qf8_composes_missing_cover_check_capture_and_retained_support():
    h, facts, _, _ = accepted(threat_case())
    assert any(p["relation"] == "coverage_not_gained" and p["object"] == "f5" for p in facts.values())
    assert not any(p["relation"] == "coverage_abandoned" and p["object"] == "f5" and p["ply"] == 1 for p in facts.values())
    assert any(p["relation"] == "retained_coverage" and p["object"] == "f6" and p["data"]["square"] == "d5" for p in facts.values())
    assert h.objective["queen_exchange"] is True
    output = render(asdict(h), facts, "inferior", {})["text"]
    for text in ("Qf8", "Qh7", "f5", "Qd7", "Qf5+", "Qxf5 exf5", "trading queens", "knight on d5", "Rc8", "for example"):
        assert text in output
    assert "wins the queen" not in output
    assert h.objective["defence_scope"]["all_defences_exhausted"] is False


@pytest.mark.parametrize("settings", [{"supported": False}, {"budget": False}, {"max_plies": 3}])
def test_threat_abstains_without_legal_horizon_and_search_support(settings):
    h, _, _, _ = threat_case(session=CertificateSearch(**settings))
    assert h is None


@pytest.mark.parametrize("field,value", [("origin_covered", True), ("queen_exchange", False),
    ("score_pairs", []), ("mate_line_san", ["Qf5#"]), ("answer_line_san", ["Qxf5"]),
    ("target_square", "f6"), ("wait_san", "Rc8")])
def test_threat_metadata_cannot_strengthen_or_change_the_verified_story(field, value):
    h, facts, lines, searches = accepted(threat_case())
    h.objective[field] = value
    assert verify_dependencies(h, facts, lines, searches)


@pytest.mark.parametrize("mutation", ["pov", "fen", "root", "score", "incomplete"])
def test_threat_search_evidence_is_bound_to_the_compared_nodes(mutation):
    h, facts, lines, searches = accepted(threat_case())
    record = searches[h.objective["score_pairs"][0][1]]
    if mutation == "pov":
        record["lines"][0]["score"]["pov"] = "white"
    elif mutation == "fen":
        record["fen"] = QF8
    elif mutation == "root":
        record["root_moves"] = ["e8c8"]
    elif mutation == "score":
        record["lines"][0]["score"] = {"kind": "mate", "value": -1, "pov": "black"}
    else:
        record["status"] = "unavailable"
    assert verify_dependencies(h, facts, lines, searches)


def test_retained_support_cannot_be_changed_to_a_wrong_square():
    _, facts, lines, _ = threat_case()
    support = next(p for p in facts if p.relation == "retained_coverage")
    changed = deepcopy(support)
    object.__setattr__(changed, "object", "f5")
    assert verify(changed, lines[changed.timeline_id])


def test_an_ignoring_move_cannot_be_presented_as_an_earlier_defence():
    h, facts, lines, searches = accepted(threat_case())
    defence = h.objective["defence_scope"]
    searches[defence["search_id"]]["lines"][0]["root_uci"] = "a6a5"
    defence["first_reply_san"] = "a5"
    assert verify_dependencies(h, facts, lines, searches) == "earlier_defence_does_not_refute_mate_tree"


@pytest.mark.parametrize("builder", [sequence_case, threat_case])
@pytest.mark.parametrize("mutation", ["universal", "missing_dependency", "forged_certificate"])
def test_comparative_certificate_cannot_be_promoted_or_detached(builder, mutation):
    h, facts, lines, searches = accepted(builder())
    if mutation == "universal":
        h.wording_strength = "unavoidable"
    elif mutation == "missing_dependency":
        h.dependencies = []
    elif h.objective["kind"] == "comparative_sequence":
        h.objective["certificate"]["legal_check_evasions"] = []
    else:
        h.objective["certificate"]["mate_tree"]["lines"] = [["d7f5"]]
    assert verify_dependencies(h, facts, lines, searches)
