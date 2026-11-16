"""The threat behind the reply, read from a Stockfish line.

Scope: docs/why_threat_line_scope.md. The engine answers are replayed from a
real run (local Stockfish, button config, depth 16, 2026-11-16), keyed by the
position and the restricted roots, so the tests pin the module's reading of
the lines, not the engine.
"""
import chess

from services.reasoning.contracts import SearchRecord
from services.reasoning.threat_line import threat_line

QF8_FEN = "4r2r/2Q1bkq1/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR b - - 2 24"
HO05_FEN = "2q5/4kp1p/p2pb1p1/4p3/Qp6/1P6/P1r2PPP/R1R3K1 w - - 2 25"
PIN_FEN = "rnb2rk1/4b1pp/4pn2/qBppN3/8/1PN1P3/P4PPP/R1BQK2R w KQ - 1 12"
BXD5_FEN = "r1bqkb1r/ppp2ppp/2n2n2/3pp1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 5"

# (fen, roots) -> (line, score kind, score value); scores from the mover's side.
RECORDED = {
    # dev_qf8, Qf8 then Qd7: best defence, then the pass line (mate in two).
    ("4rq1r/3Qbk2/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR b - - 4 25", ()):
        (["Rc8", "Qf5+", "Bf6", "Qxf6+", "Ke8", "Qe6+"], "cp", -1023),
    ("4rq1r/3Qbk2/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR w - - 5 26", ()):
        (["Qf5+", "Bf6", "Qxf6#"], "mate", -2),
    # dev_qf8, Qh7 then Qd7: best defence, then Qf5+ alone after a pass.
    ("4r2r/3Qbk1q/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR b - - 4 25", ()):
        (["Kf8", "f4", "Qf7", "Nc7", "Bg5", "Qxd6+"], "cp", -855),
    ("4r2r/3Qbk1q/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR w - - 5 26", ("d7f5",)):
        (["Qf5+", "Qxf5", "exf5", "h5", "Rh3", "Bf6"], "cp", -545),
    # codex_bxd5, Bxd5 then Nxd5.
    ("r1bqkb1r/ppp2ppp/2n5/3np1N1/4P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 6", ()):
        (["exd5", "Qxg5", "dxc6", "Qxg2", "Rf1", "Bh3"], "cp", -596),
    ("r1bqkb1r/ppp2ppp/2n5/3np1N1/4P3/8/PPPP1PPP/RNBQK2R b KQkq - 1 6", ()):
        (["Qxg5", "g3", "Qg6", "d3", "Nde7", "Nc3"], "cp", -985),
    # codex_bxd5, exd5 then Nxd5: Qxg5 is met by Bxd5; the eval still falls.
    ("r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6", ()):
        (["Nxf7", "Kxf7", "Qf3+", "Ke6", "Nc3", "Nb4"], "cp", 114),
    ("r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R b KQkq - 1 6", ("d8g5",)):
        (["Qxg5", "Bxd5", "Qg6", "d3", "Bd7", "O-O"], "cp", -132),
    # ho05, Re1 then Qc5: Qxf2+ Kh1 Qxg2#; after Rxc2 the same Qxf2+ meets Rxf2.
    ("8/4kp1p/p2pb1p1/2q1p3/Qp6/1P6/P1r2PPP/R3R1K1 w - - 4 26", ()):
        (["Rf1", "Bd7", "Qxa6", "Bb5", "Qb7+", "Ke6"], "cp", -405),
    ("8/4kp1p/p2pb1p1/2q1p3/Qp6/1P6/P1r2PPP/R3R1K1 b - - 5 26", ()):
        (["Qxf2+", "Kh1", "Qxg2#"], "mate", -2),
    ("8/4kp1p/p2pb1p1/2q1p3/Qp6/1P6/P1R2PPP/R5K1 w - - 1 26", ()):
        (["Rxc5", "dxc5", "Qxa6", "c4", "Qb5", "Kf6"], "cp", 1030),
    ("8/4kp1p/p2pb1p1/2q1p3/Qp6/1P6/P1R2PPP/R5K1 b - - 2 26", ("c5f2",)):
        (["Qxf2+", "Rxf2", "e4", "Qxb4", "e3", "Re2"], "cp", 1151),
    # 3823bc89 m12, Bb2 then Ne4: the c3 knight is pinned by Qa5; Bd2 blocks the pin.
    ("rnb2rk1/4b1pp/4p3/qBppN3/4n3/1PN1P3/PB3PPP/R2QK2R w KQ - 3 13", ()):
        (["Bd3", "Nxc3", "Bxh7+", "Kxh7", "Qh5+", "Kg8"], "cp", -445),
    ("rnb2rk1/4b1pp/4p3/qBppN3/4n3/1PN1P3/PB3PPP/R2QK2R b KQ - 4 13", ()):
        (["Nxc3", "Qd2", "Nxb5", "Qxa5", "Rxa5", "h4"], "cp", -836),
    ("rnb2rk1/4b1pp/4p3/qBppN3/4n3/1PN1P3/P2B1PPP/R2QK2R w KQ - 3 13", ()):
        (["Nxd5", "Qa7", "Nxe7+", "Qxe7", "O-O", "Bb7"], "cp", 514),
    ("rnb2rk1/4b1pp/4p3/qBppN3/4n3/1PN1P3/P2B1PPP/R2QK2R b KQ - 4 13", ("e4c3",)):
        (["Nxc3", "a4", "Nxd1", "Bxa5", "Nxe3", "fxe3"], "cp", -680),
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


def _run(fen, played, alt, reply, *, mover_is_user=True, overrides=None):
    root = chess.Board(fen)
    p, a = root.parse_san(played), root.parse_san(alt)
    after = root.copy()
    after.push(p)
    session = Replay(root.turn, overrides)
    return threat_line(session, root, p, a, after.parse_san(reply).uci(), depth=16, mover_is_user=mover_is_user)


def test_a_mate_threat_is_named_with_the_square_the_better_move_guards():
    out = _run(QF8_FEN, "Qf8", "Qh7", "Qd7")
    assert out["fires"] is True
    cause = out["cause"]
    assert cause["kind"] == "threat" and cause["threat_san"] == "Qf5+"
    assert cause["consequence"]["mechanism"] == "MATE"
    assert out["guard"] == {"by": "better_move", "piece": "queen", "from": "h7"}
    assert cause["text"] == "After Qf8, Qd7 threatens Qf5+, and mate follows. After Qh7, your queen guards f5."


def test_the_guard_the_better_move_adds_is_named_though_the_king_guards_too():
    # The king guards f2 on both branches; the rook from Rxc2 is the new guard.
    out = _run(HO05_FEN, "Re1", "Rxc2", "Qc5")
    assert out["fires"] is True and out["mate_in"] == 2
    assert out["cause"]["text"] == ("After Re1, Qc5 threatens Qxf2+, and mate follows. "
                                    "After Rxc2, your rook guards f2.")


def test_no_guard_sentence_when_the_played_move_guards_the_square_as_often():
    # Bb2 and Bd2 both guard c3; Bd2's point is the pin it blocks, so
    # "After Bd2, your bishop guards c3" would misstate the difference.
    out = _run(PIN_FEN, "Bb2", "Bd2", "Ne4")
    assert out["fires"] is True and out["guard"] is None
    assert out["cause"]["text"] == "After Bb2, Ne4 threatens Nxc3, taking your knight on c3."


def test_a_material_threat_counts_only_the_exchange_it_starts():
    out = _run(BXD5_FEN, "Bxd5", "exd5", "Nxd5")
    assert out["fires"] is True
    assert out["cause"]["text"] == "After Bxd5, Nxd5 threatens Qxg5, taking your knight on g5."
    assert out["cause"]["consequence"]["victim_piece"] == "knight"


def test_the_eval_drop_of_a_pass_alone_does_not_make_the_threat_shared():
    # After exd5 Nxd5 the pass still costs White more than two pawns, but the
    # Qxg5 line wins nothing (Bxd5), so the threat is the difference.
    out = _run(BXD5_FEN, "Bxd5", "exd5", "Nxd5")
    assert out["threat_better_cp"] >= 200 and out["fires"] is True


def test_the_same_material_threat_after_the_better_move_is_not_the_difference():
    # Negative control: if Qxg5 also won the knight after exd5, stay silent.
    alt_pass = "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R b KQkq - 1 6"
    out = _run(BXD5_FEN, "Bxd5", "exd5", "Nxd5",
               overrides={(alt_pass, ("d8g5",)): (["Qxg5", "d3", "Qg6", "Nc3"], "cp", -400)})
    assert out["fires"] is False and out["why_not"] == "same_threat_after_better_move"


def test_a_pass_that_costs_little_is_not_a_threat():
    pass_p = "r1bqkb1r/ppp2ppp/2n5/3np1N1/4P3/8/PPPP1PPP/RNBQK2R b KQkq - 1 6"
    out = _run(BXD5_FEN, "Bxd5", "exd5", "Nxd5",
               overrides={(pass_p, ()): (["Qxg5", "g3", "Qg6", "d3"], "cp", -700)})
    assert out["fires"] is False and out["why_not"] == "pass_costs_little"


def test_a_checking_reply_is_left_alone():
    # ho03: 25...Bf4 26.Nh6+ -- a pass is illegal in check.
    out = _run("r5k1/4BN1p/pR2p1p1/3pb1N1/b7/3P4/5PPP/6K1 b - - 0 25", "Bf4", "Bg7", "Nh6+")
    assert out["fires"] is False and out["why_not"] == "reply_is_check"


def test_the_opponents_move_is_worded_from_the_readers_side():
    out = _run(QF8_FEN, "Qf8", "Qh7", "Qd7", mover_is_user=False)
    assert out["cause"]["text"].endswith("After Qh7, their queen guards f5.")


def test_no_number_reaches_the_sentence():
    for fen, played, alt, reply in ((QF8_FEN, "Qf8", "Qh7", "Qd7"), (BXD5_FEN, "Bxd5", "exd5", "Nxd5")):
        text = _run(fen, played, alt, reply)["cause"]["text"]
        words = [w for w in text.replace(",", " ").replace(".", " ").split()
                 if not any(c.isalpha() for c in w)]
        assert not words
