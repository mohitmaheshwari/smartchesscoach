"""The opportunity behind the better move, read from a Stockfish line.

Scope: docs/why_opportunity_line_scope.md. The engine answers are replayed from
a real run (local Stockfish, button config, depth 16, 2026-11-17), keyed by
the position and the restricted roots, so the tests pin the module's reading
of the lines, not the engine. alt_cp / played_cp are the root search's scores
from the same run.
"""
import chess

from services.reasoning.contracts import SearchRecord
from services.reasoning.differential import build_facts
from services.reasoning.opportunity_line import opportunity_line
from services.why_words import _RELATION, conveys_relation

S12_FEN = "r3r1k1/1p3p1p/2pn2p1/p7/7P/qPB1PP2/2PKQ1P1/4R2R b - - 3 25"
S63_FEN = "r1bqkbnr/p1p3pp/2p2p2/3Pp3/3P4/5N2/PPP2PPP/RNBQK2R b KQkq - 0 6"
BG5_FEN = "r1bqk2r/pppp1ppp/2n2n2/2b5/2B1P3/2N2N2/PP3PPP/R1BQK2R w KQkq - 1 7"
QC2_FEN = "rnbq1rk1/pppp1p2/4p2p/6p1/2PPn3/2P3B1/P4PPP/R2QKBNR w KQ - 0 9"
HO02_FEN = "1kqr1b1r/p1p1n1p1/1p3p1p/PNp2N2/2Q1P3/1P6/2P2PPP/R4RK1 b - - 0 21"

# (fen, roots) -> (line, score kind, score value); scores from the mover's side.
RECORDED = {
    # 2026-11-16 sample #12: after Rad8 and a pass, Nc4 is mate; after Qc5 it is met by Qxc4.
    ("3rr1k1/1p3p1p/2pn2p1/p7/7P/qPB1PP2/2PKQ1P1/4R2R b - - 5 26", ()): (["Nc4#"], "mate", 1),
    ("r3r1k1/1p3p1p/2pn2p1/p1q5/7P/1PB1PP2/2PKQ1P1/4R2R b - - 5 26", ()):
        (["Rad8", "Bd4", "Nb5", "Qd3", "Qb4+", "c3"], "cp", 509),
    ("r3r1k1/1p3p1p/2pn2p1/p1q5/7P/1PB1PP2/2PKQ1P1/4R2R b - - 5 26", ("d6c4",)):
        (["Nc4+", "Qxc4", "Qxc4", "bxc4", "a4", "Ke2"], "cp", -615),
    # Sample #63: e4 hits the knight on f3; after exd4 exf3 is not legal.
    ("r1bqkbnr/p1p3pp/2p2p2/3P4/3Pp3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 7", ()):
        (["exf3", "Qxf3", "Qxd5", "Qg3", "Bf5", "O-O"], "cp", 598),
    ("r1bqkbnr/p1p3pp/2p2p2/3P4/3p4/5N2/PPP2PPP/RNBQK2R b KQkq - 1 7", ()):
        (["Qe7+", "Kf1", "cxd5", "Qxd4", "Qd7", "Nc3"], "cp", 114),
    # codex_bg5: e5 hits the knight on f6.
    ("r1bqk2r/pppp1ppp/2n2n2/2b1P3/2B5/2N2N2/PP3PPP/R1BQK2R w KQkq - 1 8", ()):
        (["exf6", "Qxf6", "O-O", "O-O", "Nd5", "Qf5"], "cp", 727),
    ("r1bqk2r/pppp1ppp/2n2n2/2b3B1/2B1P3/2N2N2/PP3PPP/R2QK2R w KQkq - 3 8", ()):
        (["e5", "Nxe5", "Nxe5", "O-O", "O-O", "c6"], "cp", 489),
    # mohit_qc2: Bd3 hits the knight on e4, and so does Qc2.
    ("rnbq1rk1/pppp1p2/4p2p/6p1/2PPn3/2PB2B1/P4PPP/R2QK1NR w KQ - 2 10", ()):
        (["Bxe4", "f5", "Qh5", "Qe7", "Bc2", "f4"], "cp", 645),
    ("rnbq1rk1/pppp1p2/4p2p/6p1/2PPn3/2P3B1/P1Q2PPP/R3KBNR w KQ - 2 10", ()):
        (["Qxe4", "f5", "Qc2", "Qe7", "h4", "d6"], "cp", 604),
    # ho02: Nc6 threatens a pawn; the move cost more than that.
    ("1kqr1b1r/p1p3p1/1pn2p1p/PNp2N2/2Q1P3/1P6/2P2PPP/R4RK1 b - - 2 22", ()):
        (["Nxa5", "Qe2", "c6", "Na3", "g6", "Nh4"], "cp", 106),
}


class Replay:
    def __init__(self, pov, overrides=None):
        self.pov = pov
        self.records = []
        self.table = dict(RECORDED)
        self.table.update(overrides or {})

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        key = (board.fen(), tuple(sorted(m.uci() for m in roots)))
        lines = []
        if key in self.table:
            sans, kind, value = self.table[key]
            walker, ucis = board.copy(), []
            for san in sans:
                mv = walker.parse_san(san)
                ucis.append(mv.uci())
                walker.push(mv)
            lines = [{"root_uci": ucis[0], "moves_uci": ucis, "moves_san": list(sans),
                      "score": {"kind": kind, "value": value, "pov": "white" if self.pov else "black"},
                      "depth": 16, "nodes": 1}]
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), list(key[1]), 1, width,
                              "complete_iteration" if lines else "unavailable", lines)
        self.records.append(record)
        return record


def _run(fen, played, alt, alt_cp, played_cp, *, mover_is_user=True, overrides=None):
    root = chess.Board(fen)
    session = Replay(root.turn, overrides)
    out = opportunity_line(session, root, root.parse_san(played), root.parse_san(alt), depth=16,
                           mover_is_user=mover_is_user, alt_cp=alt_cp, played_cp=played_cp)
    return out, session


def test_a_mate_the_better_move_threatens_is_named():
    out, _ = _run(S12_FEN, "Qc5", "Rad8", 707, 83)
    assert out["fires"] is True and out["mate_in"] == 1
    assert out["answer"]["text"] == "Rad8 was the move: it threatens Nc4#, which is mate."
    assert out["answer"]["consequence"]["mechanism"] == "MATE"


def test_a_material_threat_that_is_illegal_after_the_played_move():
    out, _ = _run(S63_FEN, "exd4", "e4", 51, -63)
    assert out["fires"] is True and out.get("threat_illegal_after_played_move") is True
    assert out["answer"]["text"] == "e4 was the move: it threatens exf3, which wins their knight on f3 for a pawn."
    assert out["answer"]["consequence"]["victim_piece"] == "knight"


def test_codex_bg5_names_the_pawn_attack_on_the_knight():
    out, _ = _run(BG5_FEN, "Bg5", "e5", 124, -24)
    assert out["fires"] is True
    assert out["answer"]["text"] == "e5 was the move: it threatens exf6, which wins their knight on f6 for a pawn."


def test_the_same_square_won_after_the_played_move_is_not_the_difference():
    # Bd3 threatens Bxe4, but Qc2 hits the same knight; Bxe4 being illegal
    # after Qc2 must not make the threat look new.
    out, _ = _run(QC2_FEN, "Qc2", "Bd3", 105, -5)
    assert out["fires"] is False and out["why_not"] == "same_square_won_after_played_move"


def test_a_threat_worth_less_than_the_gap_is_not_the_reason():
    out, _ = _run(HO02_FEN, "Nxf5", "Nc6", -225, -368)
    assert out["fires"] is False and out["why_not"] == "threat_smaller_than_gap"
    assert out["threat_wins_cp"] == 100


def test_a_pass_that_gains_little_is_silent():
    low = {("r1bqkbnr/p1p3pp/2p2p2/3P4/3Pp3/5N2/PPP2PPP/RNBQK2R b KQkq - 1 7", ()):
           (["exf3", "Qxf3", "Qxd5", "Qg3", "Bf5", "O-O"], "cp", 150)}
    out, _ = _run(S63_FEN, "exd4", "e4", 51, -63, overrides=low)
    assert out["fires"] is False and out["why_not"] == "pass_gains_little"


def test_a_checking_better_move_is_not_asked_and_costs_no_search():
    out, session = _run("4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "Kd2", "Ra8+", 900, 800)
    assert out["fires"] is False and out["why_not"] == "better_move_is_check"
    assert session.records == []


def test_opponent_cards_say_your():
    out, _ = _run(S63_FEN, "exd4", "e4", 51, -63, mover_is_user=False)
    assert out["answer"]["text"] == "e4 was the move: it threatens exf3, which wins your knight on f3 for a pawn."


def test_no_numbers_in_the_sentences():
    for args in ((S12_FEN, "Qc5", "Rad8", 707, 83), (S63_FEN, "exd4", "e4", 51, -63),
                 (BG5_FEN, "Bg5", "e5", 124, -24)):
        text = _run(*args)[0]["answer"]["text"]
        assert "cp" not in text and "pawns" not in text and "%" not in text


def test_the_words_layer_is_told_the_better_move_only_threatens():
    out, _ = _run(S12_FEN, "Qc5", "Rad8", 707, 83)
    result = {"found": True, "direction": "missed", "mechanism": "MATE", "text": out["answer"]["text"],
              "consequence": out["answer"]["consequence"], "better_move": "Rad8", "causes": [],
              "input": {"mover_is_user": True, "played_san": "Qc5"}}
    facts = build_facts(result)
    assert facts["the_threatened_move"] == "Nc4#"
    assert facts["relation"] == _RELATION["OPPORTUNITY"]
    # A rewrite that drops the threat is refused.
    assert conveys_relation("OPPORTUNITY", "Rad8 mates their king.") is not None
    assert conveys_relation("OPPORTUNITY", "Rad8 threatens Nc4, which is mate.") is None
