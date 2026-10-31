"""The differential why: the reason is what the reply does ONLY after the played move.

Every position here is from docs/qa/why_engine_regression_set.json and was
checked on the board by hand on 2026-10-31 before the module was written.
Board tests need no engine; the flow test drives explain_move with a scripted
search session, the same pattern as test_reasoning_reply_exclusion.py.
"""
from __future__ import annotations

import chess
import pytest

from services.reasoning.contracts import SearchRecord
from services.reasoning.differential import (
    build_facts, classify_gap, differential_causes, explain_move, reply_footprint, score_cp,
)
from test_reasoning_boundaries import config


def causes(fen, played, alt, reply):
    board = chess.Board(fen)
    p, a = board.parse_san(played), board.parse_san(alt)
    after = board.copy()
    after.push(p)
    r = after.parse_san(reply)
    return differential_causes(board, p, a, r.uci(), mover_is_user=True)


def test_check_only_after_the_played_move_is_the_cause():
    # ho01: Kc8 steps onto the e6-c8 diagonal, so the same capture now checks.
    out = causes("8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38", "Kc8", "Kd8", "Qxe6")
    assert [c["kind"] for c in out] == ["check"]
    assert out[0]["text"] == "After Kc8, Qxe6+ comes with check. After Kd8 it does not."


def test_recapture_on_the_exchange_square_cancels_and_the_new_attack_remains():
    # ho10: exd5 recaptures either piece; only after Nxd5 does the pawn hit c6.
    out = causes("2rqkb1r/1p2pp1p/p1bp1np1/3N4/1Q2P3/5N2/PPP2PPP/R1B2RK1 b k - 3 11", "Nxd5", "Bxd5", "exd5")
    assert [c["kind"] for c in out] == ["attacks"]
    assert out[0]["piece"] == "bishop" and out[0]["square"] == "c6"
    assert "After Nxd5, exd5 attacks your bishop on c6." in out[0]["text"]


def test_a_reply_that_hits_the_moved_piece_on_both_branches_is_not_a_reason():
    # ho09: c3 attacks the bishop after Bb4+ and the knight after Nd4. True, shared, silent.
    assert causes("2kr1b1r/ppp3pp/2n2q2/1B1p1b2/8/3P4/PPP1NPPP/R1BQK2R b KQ - 1 11", "Bb4+", "Nd4", "c3") == []


def test_a_capture_the_better_move_also_allows_is_not_a_reason():
    # ho12: Nd4 and Nb8 both leave e5 to Nxe5. The e5 pawn is not the difference.
    assert causes("r2qk2r/pbp1bpp1/1pn2n1p/3Pp3/1PB5/P1NPBN2/2P2PPP/R2QK2R b KQkq - 0 9", "Nd4", "Nb8", "Nxe5") == []


def test_lost_guard_names_the_piece_the_played_move_moved():
    # Mohit's c4: the c3 pawn guarded d4; after f3 it still does.
    out = causes("r1b2rk1/ppp5/5q1p/3pNpp1/3Pn3/2PB4/P1Q2PPP/R3K2R w KQ - 0 15", "c4", "f3", "c5")
    assert out[0]["kind"] == "lost_guard"
    assert out[0]["guard_square"] == "c3" and out[0]["guard_was_the_moved_piece"] is True
    assert out[0]["text"] == ("c4 moved the pawn that was guarding d4, so c5 hits your pawn on d4 "
                              "with nothing defending it.")


def test_a_recapture_after_the_played_capture_is_an_exchange_not_a_hanging_piece():
    # ho02: Nxf5 exf5 is a knight for a knight. ho15: Bxc3 bxc3 is a bishop for a knight.
    assert causes("1kqr1b1r/p1p1n1p1/1p3p1p/PNp2N2/2Q1P3/1P6/2P2PPP/R4RK1 b - - 0 21", "Nxf5", "Nc6", "exf5") == []
    assert causes("rn2k2r/pp3ppp/2p1pn2/q4b2/1b6/P1NP1N2/1PPBBPPP/R2Q1RK1 b kq - 0 9", "Bxc3", "Be7", "bxc3") == []


def test_a_pawn_chasing_a_knight_is_not_a_lost_guard():
    # ho07: after d3 the c1 bishop would guard g5, but h6 chases the knight either way.
    assert causes("r2qkb1r/ppp3pp/2n2n2/1B1p1bN1/4p3/8/PPPP1PPP/RNBQ1RK1 w kq - 0 8", "Nc3", "d3", "h6") == []


def ledger(fen, line):
    from services.reasoning.differential import exchange_ledger
    board = chess.Board(fen)
    return exchange_ledger(board, line.split(), board.turn)


def test_ledger_reads_an_exchange_and_an_unanswered_capture_from_the_engine_line():
    from services.reasoning.differential import exchange_sentence, first_unshared_exchange
    fen = "r1bqkb1r/ppp2ppp/2n2n2/3pp1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 5"
    played = ledger(fen, "Bxd5 Nxd5 exd5 Qxg5 dxc6 Qxg2 Rf1 Bh3 Qe2 bxc6")
    better = ledger(fen, "exd5 Na5 Bb5+ c6 dxc6 bxc6 Bd3 Nd5 Nf3 Bd6")
    d5 = next(g for g in played if g["square"] == "d5")
    assert d5["mover_won"] == ["pawn", "knight"] and d5["mover_lost"] == ["bishop"] and d5["net_cp"] == 100
    loss = first_unshared_exchange(played, better, losing=True)
    assert loss["square"] == "g5" and loss["net_cp"] == -300 and loss["mover_won"] == []
    said = exchange_sentence(loss, played_san="Bxd5", reply_san="Nxd5", alt_san="exd5", received=True, mover_is_user=True)
    assert said["text"] == "After Bxd5, Nxd5 leads to Qxg5, which takes your knight on g5 with nothing taking back."
    assert said["mechanism"] == "WINS_MATERIAL" and said["victim_piece"] == "knight" and said["ply"] == 3
    # The line regains a knight on c6, so the whole-line claim drops "nothing taking back"
    # and stands on the eval gap instead.
    from services.reasoning.differential import material_claim
    claim = material_claim(played, better, played_plies=10, alt_plies=10, received=True, gap=647, move_class="blunder",
                           played_san="Bxd5", reply_san="Nxd5", alt_san="exd5", mover_is_user=True)
    assert claim["text"] == "After Bxd5, Nxd5 leads to Qxg5, which takes your knight on g5."
    assert material_claim(played, better, played_plies=10, alt_plies=10, received=True, gap=60, move_class="inaccuracy",
                          played_san="Bxd5", reply_san="Nxd5", alt_san="exd5", mover_is_user=True) is None


def test_a_gain_the_line_gives_back_elsewhere_becomes_the_net_in_words():
    # ho08: Rxc2 takes a rook, bxa4 takes the queen, Rxc8 takes the queen back: a pawn up in the end.
    from services.reasoning.differential import material_claim, material_words
    fen = "2q5/3k1p1p/p2pb1p1/1p2p3/Q7/1P6/P1r2PPP/R1R3K1 w - - 0 23"
    better = ledger(fen, "Rxc2 bxa4 Rxc8 Kxc8 bxa4 Kc7 Rc1+ Kb6 a3")
    played = ledger(fen, "Qa3 Qc5 Qxc5 Rxc5 Rxc5 dxc5 Kf1 a5 Ke1")
    claim = material_claim(played, better, played_plies=9, alt_plies=9, received=False, gap=133, move_class="mistake",
                           played_san="Qa3", reply_san="Qc5", alt_san="Rxc2", mover_is_user=True)
    assert claim["series"] is True
    assert claim["text"] == "Rxc2 starts a series of exchanges that leaves you a pawn up."
    assert material_words(100) == "a pawn" and material_words(300) == "a piece" and material_words(500) == "a rook"


def test_a_capture_on_the_last_ply_of_the_line_is_unknown_not_a_claim():
    # ho05: Bxf1 sits at the horizon; Rxf1 answers it one ply later.
    from services.reasoning.differential import closed_groups, material_claim
    fen = "2q5/4kp1p/p2pb1p1/4p3/Qp6/1P6/P1r2PPP/R1R3K1 w - - 2 25"
    played_line = "Re1 Qc5 Rf1 Bd7 Qxa6 Bb5 Qb7+ Kf8 a4 Bxf1".split()
    played = ledger(fen, " ".join(played_line))
    assert [g["square"] for g in closed_groups(played, len(played_line))] == ["a6"]   # Rxf1 is legal: f1 is open
    # A final capture with no legal recapture is closed and may be claimed.
    bxd5 = ledger("r1bqkb1r/ppp2ppp/2n2n2/3pp1N1/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 5",
                  "Bxd5 Nxd5 exd5 Qxg5 dxc6 Qxg2 Rf1 Bh3 Qe2 bxc6")
    assert next(g for g in bxd5 if g["square"] == "c6")["open"] is False
    better = ledger(fen, "Rxc2 Qxc2 Qxb4 Bd5 Qh4+ Kd7 Qa4+ Qc6 Qg4+ Be6")
    assert material_claim(played, better, played_plies=10, alt_plies=10, received=True, gap=673, move_class="blunder",
                          played_san="Re1", reply_san="Qc5", alt_san="Rxc2", mover_is_user=True) is None


def test_ledger_names_a_lost_exchange_and_ignores_an_even_trade():
    from services.reasoning.differential import exchange_sentence, first_unshared_exchange
    fen = "rn1q1rk1/b2b1ppp/1p1p1n2/PPp1pP2/4P3/3B1N1P/1B1P2P1/RN1QK2R w KQ - 0 14"
    played = ledger(fen, "axb6 Qxb6 Nc3 c4 Rxa7 Rxa7 Bxc4 Nc6 g4 d5")
    better = ledger(fen, "Nc3 bxa5 Bc4 Bc8 d3 Nbd7 Bc1 Bb7 Bg5 d5")
    assert next(g for g in played if g["square"] == "b6")["net_cp"] == 0          # pawn for pawn
    loss = first_unshared_exchange(played, better, losing=True)
    assert loss["square"] == "a7"
    text = exchange_sentence(loss, played_san="axb6", reply_san="Qxb6", alt_san="Nc3", received=True, mover_is_user=True)["text"]
    assert text == "After axb6, the exchange on a7 costs you a rook for a bishop."
    even = ledger("rn2k2r/pp3ppp/2p1pn2/q4b2/1b6/P1NP1N2/1PPBBPPP/R2Q1RK1 b kq - 0 9", "Bxc3 bxc3 O-O Rb1 Qc7")
    assert first_unshared_exchange(even, [], losing=True) is None


def test_ledger_shares_the_same_exchange_across_branches():
    from services.reasoning.differential import first_unshared_exchange
    fen = "8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38"
    played = ledger(fen, "Kc8 Qxe6+ Kd8 Qxh6")
    better = ledger(fen, "Kd8 Qxe6 Qe2")
    loss = first_unshared_exchange(played, better, losing=True)
    assert loss["square"] == "h6"                 # e6 falls on both branches; h6 only after Kc8


def test_owner_words_follow_whose_move_it_is():
    board = chess.Board("8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38")
    p, a = board.parse_san("Kc8"), board.parse_san("Kd8")
    after = board.copy()
    after.push(p)
    out = differential_causes(board, p, a, after.parse_san("Qxe6").uci(), mover_is_user=False)
    assert out[0]["owner"] == "their"


def test_footprint_keys_cancel_by_square_and_moved_piece():
    board = chess.Board("2kr1b1r/ppp3pp/2n2q2/1B1p1b2/8/3P4/PPP1NPPP/R1BQK2R b KQ - 1 11")
    board.push_san("Bb4+")
    fp = reply_footprint(board, board.parse_san("c3"), chess.parse_square("b4"))
    assert ("attacks_moved_piece",) in fp
    assert not any(k[0] == "attacks" for k in fp)


def test_scores_and_classes():
    assert score_cp({"kind": "cp", "value": 42, "pov": "white"}) == 42
    assert score_cp({"kind": "mate", "value": 3, "pov": "white"}) == 9997
    assert score_cp({"kind": "mate", "value": -2, "pov": "white"}) == -9998
    assert classify_gap(10, 1200) == "good"
    assert classify_gap(62, 1200) == "inaccuracy"
    assert classify_gap(134, 1200) == "mistake"
    assert classify_gap(385, 1200) == "blunder"
    assert classify_gap(None, 1200) == "unknown"


class ScriptedSession:
    """Root: best 'Kd8' at +50, played 'Kc8' at -381 (gap 431). After Kc8 the
    reply Qxe6+ is worth 300 to White and 146 without it (drop 154). After Kd8
    the reply is Qxe6 at 100, 60 without it."""

    def __init__(self, pov):
        self.pov = pov
        self.config = config(rank_width=3)
        self.records = []
        self.executed_queries = 0
        self.requested_nodes = 0
        self.root = chess.Board("8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38")

    def _line(self, board, sans, value):
        walker = board.copy()
        ucis = []
        for san in sans:
            mv = walker.parse_san(san)
            ucis.append(mv.uci())
            walker.push(mv)
        return {"root_uci": ucis[0], "moves_uci": ucis, "moves_san": list(sans),
                "score": {"kind": "cp", "value": value, "pov": "black"}, "depth": 20, "nodes": 1}

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        self.executed_queries += 1
        lines = []
        if board.fen() == self.root.fen():
            lines = [self._line(board, ["Kd8", "Qxe6", "Qe2"], 50), self._line(board, ["Kc8", "Qxe6+", "Kd8"], -381)]
            if roots:
                lines = [l for l in lines if l["root_uci"] in {m.uci() for m in roots}]
            lines = lines[:width]
        else:
            after_kc8 = self.root.copy(); after_kc8.push_san("Kc8")
            after_kd8 = self.root.copy(); after_kd8.push_san("Kd8")
            if board.fen() == after_kc8.fen():
                lines = [self._line(board, ["Qxe6+", "Kd8", "Qxh6"], -300) if not roots else self._line(board, ["Qxb7+", "Kxb7"], -146)]
            elif board.fen() == after_kd8.fen():
                lines = [self._line(board, ["Qxe6", "Qe2"], -100) if not roots else self._line(board, ["Qf8+", "Kc7"], -60)]
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots],
                              nodes or 100, width, "complete_iteration" if lines else "unavailable", lines,
                              requested_depth=depth)
        self.records.append(record)
        return record


def test_flow_measures_both_branches_and_explains_from_the_reply():
    fen = "8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38"
    out = explain_move(fen, "Kc8", config=config(rank_width=3), depth=20, rating=1200,
                       session_factory=lambda cfg, pov, hist: ScriptedSession(pov))
    assert out["class"] == "blunder" and out["gap_cp"] == 431
    assert out["better_move"] == "Kd8"
    assert out["played_branch"]["reply_san"] == "Qxe6+" and out["played_branch"]["drop_cp"] == 154
    assert out["alternative_branch"]["reply_san"] == "Qxe6" and out["alternative_branch"]["drop_cp"] == 40
    assert out["family"] == "missed"           # 154 / 431 is below the punished floor
    assert out["found"] is True and out["direction"] == "received"
    assert out["causes"][0]["kind"] == "check"
    assert out["text"].startswith("After Kc8, Qxe6+ comes with check. After Kd8 it does not.")
    assert out["arrows"][0]["from"] == "d7" and out["arrows"][1]["san"] == "Qxe6+"
    facts = out["facts"]
    assert facts["the_better_move"] == "Kd8" and facts["their_reply"] == "Qxe6+"
    assert facts["relation"] == "the reply comes with check only after the move played"
    assert "cp" not in str(facts) and "431" not in str(facts)


def test_flow_reports_the_engine_choice_as_good_without_a_reason():
    fen = "8/1p1k1Q2/2p1p2p/p3P1p1/P7/2P3PK/1q6/8 b - - 3 38"
    out = explain_move(fen, "Kd8", config=config(rank_width=3), depth=20, rating=1200,
                       session_factory=lambda cfg, pov, hist: ScriptedSession(pov))
    assert out["found"] is False and out["reason"] == "engine_choice" and out["family"] == "good"
    assert out["facts"] is None


def test_illegal_input_raises_instead_of_explaining():
    with pytest.raises(ValueError):
        explain_move(chess.STARTING_FEN, "Ke2", config=config(), depth=20,
                     session_factory=lambda cfg, pov, hist: ScriptedSession(pov))


def test_words_layer_refuses_a_piece_given_to_the_wrong_side():
    # Live, 2026-10-31, deploy-verify game move 15: facts said "their bishop", the model wrote "Your bishop".
    from services.why_words import validate
    facts = {"whose_move": "the reader's", "the_move_played": "Bxg4", "the_better_move": "gxf4",
             "this_happens_after_the_move_played": False, "the_move_that_does_it": "gxf4",
             "relation": "the piece is won -- it changes hands for nothing like it",
             "the_piece_involved": "their bishop", "the_square_it_is_on": "f4",
             "what_happens_to_the_material": "gxf4 takes their bishop on f4 for nothing."}
    assert validate(facts, "Your bishop on f4 is won, as gxf4 takes it for nothing.") == "swapped ownership of the bishop"
    assert validate(facts, "Their bishop on f4 is won, as gxf4 takes it for nothing.") is None
    # Both owners present in the facts (an exchange) may both be named.
    both = dict(facts, what_happens_to_the_material="the exchange on f4 costs you a rook for their bishop",
                the_piece_involved="your rook")
    assert validate(both, "The exchange on f4 costs you your rook for their bishop.") is None


def test_words_layer_accepts_the_cause_facts_and_refuses_added_chess():
    from services.why_words import validate
    facts = {"whose_move": "the reader's", "the_move_played": "Kc8", "the_better_move": "Kd8",
             "their_reply": "Qxe6+", "this_happens_after_the_move_played": True,
             "what_the_move_played_changed": "After Kc8, Qxe6+ comes with check. After Kd8 it does not.",
             "relation": "the reply comes with check only after the move played",
             "the_move_that_does_it": "Qxe6+"}
    assert validate(facts, "Kc8 puts the king where Qxe6 comes with check, so White keeps the move. Kd8 avoids that.") is None
    assert validate(facts, "Kc8 lets Qxe6 in, and Kd8 was the better square.") == "dropped the CHECK relation"
    assert "invented" in validate(facts, "Kc8 walks into Qxe6+ and then Qxh6 picks up the h6 pawn with check.")
