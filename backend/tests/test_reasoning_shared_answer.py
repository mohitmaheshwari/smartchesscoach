"""Same reply, different answer (services/reasoning/shared_answer.py).

Scope: docs/why_shared_answer_scope.md. The branch dicts for 18.Qd2 are the
reply locator's output from a real run on the production engine (button
config, depth 16, 2026-11-27). The legal-answer case uses a constructed
position and a replayed restricted search, so it pins the module's reading of
a line, not the engine.
"""
import chess

from services.reasoning.contracts import SearchRecord
from services.reasoning.differential import build_facts
from services.reasoning.shared_answer import shared_answer
from services.why_words import _RELATION, conveys_relation

QD2_FEN = "2r1r1k1/pp2bpp1/1q3n1p/n2P4/7B/2N2B2/PPQ2PPP/1K1R3R w - - 0 18"


def _branch(move_san, reply_uci, reply_san, line, cp):
    return {"move_san": move_san, "status": "measured", "reply_uci": reply_uci, "reply_san": reply_san,
            "line_san": list(line), "score": {"kind": "cp", "value": cp, "pov": "white"}}


QD2_PLAYED = _branch("Qd2", "a5c4", "Nc4", ["Nc4", "Qc1", "Ba3", "Na4", "Qb4", "Rd4", "Bxb2"], -308)
QD2_BETTER = _branch("d6", "a5c4", "Nc4", ["Nc4", "Qb3", "Qxb3", "axb3", "Nxd6", "Bxf6"], 85)


class Replay:
    def __init__(self, table=None):
        self.table = dict(table or {})
        self.records = []

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        key = (board.fen(), tuple(sorted(m.uci() for m in roots)))
        lines = []
        if key in self.table:
            sans, value = self.table[key]
            walker, ucis = board.copy(), []
            for san in sans:
                mv = walker.parse_san(san)
                ucis.append(mv.uci())
                walker.push(mv)
            lines = [{"root_uci": ucis[0], "moves_uci": ucis, "moves_san": list(sans),
                      "score": {"kind": "cp", "value": value, "pov": "white"}, "depth": 16, "nodes": 1}]
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), list(key[1]), 1, width,
                              "complete_iteration" if lines else "unavailable", lines)
        self.records.append(record)
        return record


def _run(fen, played, alt, pb, ab, *, gap=None, mover_is_user=True, table=None):
    root = chess.Board(fen)
    return shared_answer(Replay(table), root, root.parse_san(played), root.parse_san(alt),
                         played_branch=pb, alt_branch=ab, depth=16, mover_is_user=mover_is_user,
                         gap_cp=gap)


def test_qd2_the_answer_is_gone_because_the_queen_left():
    out = _run(QD2_FEN, "Qd2", "d6", QD2_PLAYED, QD2_BETTER, gap=394)
    assert out["fires"], out
    assert out["gone"] == {"kind": "moved_away", "piece": "queen", "from": "c2"}
    assert out["answer"]["text"] == (
        "d6 was the move. Both moves allow Nc4, but after d6 you answer it with Qb3 and trade queens. "
        "After Qd2, your queen is no longer on c2, so Qb3 is not possible.")
    assert out["answer"]["line_san"] == ["d6", "Nc4", "Qb3"]


def test_qd2_on_the_opponents_card_says_their():
    out = _run(QD2_FEN, "Qd2", "d6", QD2_PLAYED, QD2_BETTER, gap=394, mover_is_user=False)
    assert "they answer it with Qb3" in out["answer"]["text"]
    assert "their queen is no longer on c2" in out["answer"]["text"]


def test_different_replies_are_not_this_case():
    other = dict(QD2_BETTER, reply_uci="e7d6", reply_san="Bxd6", line_san=["Bxd6", "Qb3"])
    assert _run(QD2_FEN, "Qd2", "d6", QD2_PLAYED, other, gap=394)["why_not"] == "different_replies"


def test_same_answer_on_both_branches_is_not_the_difference():
    played = dict(QD2_PLAYED, line_san=["Nc4", "Qb3"])
    # Qb3 is not legal after Qd2 Nc4, but the rule reads the lines: the same
    # answer on both branches is never the difference.
    assert _run(QD2_FEN, "Qd2", "d6", played, QD2_BETTER, gap=394)["why_not"] == "same_answer_both"


def test_close_branches_do_not_fire():
    close = dict(QD2_PLAYED, score={"kind": "cp", "value": -50, "pov": "white"})
    assert _run(QD2_FEN, "Qd2", "d6", close, QD2_BETTER, gap=394)["why_not"] == "branches_close"


def test_swing_must_be_half_the_gap():
    # 393 of swing on a 1000 gap is not the reason.
    assert _run(QD2_FEN, "Qd2", "d6", QD2_PLAYED, QD2_BETTER, gap=1000)["why_not"] == "branches_close"


# Constructed: both Nc3 and Na3 allow ...Rb2; the answer Kf1 exists after both,
# but after Na3 the rook goes on to take the knight on a3.
K_FEN = "1r4k1/5ppp/8/8/8/8/5PPP/RN4K1 w - - 0 1"
K_PLAYED = _branch("Na3", "b8b2", "Rb2", ["Rb2", "Nb5", "Rb3"], -300)
K_BETTER = _branch("Nc3", "b8b2", "Rb2", ["Rb2", "Kf1", "h6"], 0)


def _after(fen, *sans):
    b = chess.Board(fen)
    for s in sans:
        b.push_san(s)
    return b.fen()


def test_legal_answer_that_fails_names_the_capture():
    key = (_after(K_FEN, "Na3", "Rb2"), ("g1f1",))
    table = {key: (["Kf1", "Rb3", "Ke1", "Rxa3", "Kd2", "Ra4"], -300)}
    out = _run(K_FEN, "Na3", "Nc3", K_PLAYED, K_BETTER, gap=300, table=table)
    assert out["fires"], out
    assert out["answer"]["text"] == (
        "Nc3 was the move. Both moves allow Rb2, but after Nc3 you answer it with Kf1. "
        "After Na3, Kf1 fails: Rxa3 wins your knight on a3.")


def test_legal_answer_that_still_works_does_not_fire():
    key = (_after(K_FEN, "Na3", "Rb2"), ("g1f1",))
    table = {key: (["Kf1", "h6", "Ke1", "h5"], -20)}
    out = _run(K_FEN, "Na3", "Nc3", K_PLAYED, K_BETTER, gap=300, table=table)
    assert out["why_not"] == "answer_still_works"


def test_facts_carry_the_relation_and_the_words_check_holds():
    out = _run(QD2_FEN, "Qd2", "d6", QD2_PLAYED, QD2_BETTER, gap=394)
    result = {"found": True, "input": {"mover_is_user": True, "played_san": "Qd2"}, "better_move": "d6",
              "mechanism": "SHARED_REPLY", "direction": "missed", "consequence": out["answer"]["consequence"],
              "shared_answer_facts": out["answer"]["facts"]}
    facts = build_facts(result)
    assert facts["relation"] == _RELATION["SHARED_REPLY"]
    assert facts["the_answer_after_the_better_move"] == "Qb3"
    assert facts["the_answer_trades"] == "queens"
    assert conveys_relation("SHARED_REPLY", out["answer"]["text"]) is None
    # A rewrite that keeps only the shared part has dropped the finding.
    assert conveys_relation("SHARED_REPLY", "Both moves allow Nc4, and d6 was better.") is not None
