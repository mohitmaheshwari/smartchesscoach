"""Review regressions: selection subject, mate distance and unambiguous actors."""
from dataclasses import asdict

import chess
import pytest

from services.reasoning.contracts import SearchRecord
from services.reasoning.engine import explain_fen
from services.reasoning.objectives import generate
from services.reasoning.render import add_resource, render
from services.reasoning.search import comparison
from services.reasoning.timeline import build_timeline, event_facts
from test_reasoning_boundaries import config, score


QUIET = "rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4"


class QuietSearch:
    """Deterministic legal branch fixtures isolate orchestration from Stockfish."""
    def __init__(self, settings, pov, history_id):
        self.config, self.pov = settings, pov
        self.records, self.executed_queries, self.requested_nodes = [], 0, 0

    def can_query(self, nodes=None):
        return False  # Additional exploration is deliberately unavailable.

    def query(self, board, purpose, *, roots=(), width=1, nodes=None):
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots], nodes or 100, width, "unavailable")
        if board.fen() == QUIET:
            moves = [m.uci() for m in roots] if roots else ["f1g2", "g1f3", "e2e4"]
            paths = {"f1g2": ["f1g2", "b8c6", "g1f3", "e8g8", "e1g1"],
                     "g1f3": ["g1f3", "b8c6", "f1g2", "e8g8", "e1g1"], "e2e4": ["e2e4", "d7d6"]}
            scores = {"f1g2": 35, "g1f3": 31, "e2e4": -20}
            record.lines = [{"root_uci": m, "moves_uci": paths[m], "score": score(scores[m])} for m in moves]
            record.status = "complete_iteration"
            self.executed_queries += 1
        self.records.append(record)
        return record

    def document(self):
        return {"source": "deterministic_test_fixture"}


def test_equivalent_played_root_is_the_teaching_subject(monkeypatch):
    monkeypatch.setattr("services.reasoning.engine.SearchSession", QuietSearch)
    result = explain_fen(QUIET, "Nf3", config=config())
    assert result["context"]["comparison"] == "equivalent"
    assert result["selected_teaching_point"]["root_uci"] == "g1f3"
    assert "Nf3" in result["coaching"]["text"]
    assert "g1" in result["coaching"]["text"]


@pytest.mark.parametrize("best,played", [(1, 6), (2, 9), (-10, -3)])
def test_same_sign_mate_distances_are_coaching_differences(best, played):
    assert comparison(score(best, "mate"), score(played, "mate"), 30) == "inferior"


def test_identical_mate_distances_remain_equivalent():
    assert comparison(score(6, "mate"), score(6, "mate"), 30) == "equivalent"


def test_immediate_mate_sentence_names_the_move_once():
    line = build_timeline(chess.Board("7k/6pp/8/8/3b4/8/8/QK2R3 w - - 0 1"), ["a1a8"], "mate", 18)
    facts = event_facts(line)
    hypotheses, extra = generate(line, facts)
    selected = next(h for h in hypotheses if h.objective["kind"] == "checkmates")
    text = render(asdict(selected), {p.id: asdict(p) for p in facts + extra}, "inferior", {})["text"]
    assert text.count("Qa8#") == 1


def test_later_black_e4_cannot_read_as_the_players_white_e4():
    line = build_timeline(chess.Board(QUIET), ["g1f3", "e5e4"], "resource", 18)
    fact = next(p for p in event_facts(line) if p.relation == "attacks_piece" and p.actor == "black")
    output = add_resource({"sentences": [{}], "text": "Nf3 clears g1. Remember this.", "teaching_habit": "Remember this."}, asdict(fact))
    assert "Black" in output["text"]
    assert "e4" in output["text"]
    assert "later" in output["text"].lower()
