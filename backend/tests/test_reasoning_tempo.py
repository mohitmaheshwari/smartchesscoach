"""The tempo family: the move brings no piece out while the better move does.

The position is Mohit's 4...b6 (1.e4 d5 2.exd5 Qxd5 3.Nc3 Qe6+ 4.Be2 b6),
checked on the board with python-chess on 2026-11-02 before the module was
written. Board tests need no engine; the flow test drives explain_move with a
scripted search session, as test_reasoning_differential.py does.
"""
from __future__ import annotations

import chess

from services.reasoning.contracts import SearchRecord
from services.reasoning.differential import build_facts, explain_move
from services.reasoning.tempo import development_facts, forced_retreats, move_effect, tempo_claim
from test_reasoning_boundaries import config

B6 = "rnb1kbnr/ppp1pppp/4q3/8/8/2N5/PPPPBPPP/R1BQK1NR b KQkq - 3 4"


def effect(fen, san):
    board = chess.Board(fen)
    return move_effect(board, board.parse_san(san))


def test_the_root_facts_name_the_stuck_bishop_and_the_queen_in_the_pawns_way():
    f = development_facts(chess.Board(B6), chess.BLACK)
    assert f["undeveloped"] == ["b8", "g8", "c8", "f8"]
    assert f["stuck"] == ["f8"]
    paths = {p["pawn"]: p for p in f["freeing"]["f8"]}
    assert paths["e7"]["blocker"] == {"piece": "queen", "square": "e6"}
    assert paths["g7"]["blocker"] is None
    assert f["can_castle"] is True and f["castling_legal_now"] is False
    assert f["queen_out"] is True


def test_the_played_move_does_none_of_it_and_each_alternative_does_one_thing():
    assert effect(B6, "b6")["kinds"] == ["none"]
    assert effect(B6, "c6")["kinds"] == ["none"]
    assert effect(B6, "a6")["kinds"] == ["none"]
    assert effect(B6, "Nf6")["develops"] == "knight"
    assert effect(B6, "g6")["frees"] == {"piece": "bishop", "square": "f8"}
    assert effect(B6, "Qd6")["unblocks"] == {"pawn": "e7", "file": "e", "bishop_square": "f8"}


def test_a_developing_move_in_front_of_a_pawn_is_not_a_block():
    # Nf6 stands in front of f7 and Nc3 in front of c2; neither pawn frees a stuck bishop.
    after_nf6 = chess.Board(B6)
    after_nf6.push_san("Nf6")
    f = development_facts(after_nf6, chess.BLACK)
    assert f["freeing"] == {"f8": [
        {"pawn": "e7", "file": "e", "front": "e6", "blocker": {"piece": "queen", "square": "e6"}},
        {"pawn": "g7", "file": "g", "front": "g6", "blocker": None}]}
    white = development_facts(chess.Board(B6), chess.WHITE)
    assert white["freeing"] == {"c1": [
        {"pawn": "b2", "file": "b", "front": "b3", "blocker": None},
        {"pawn": "d2", "file": "d", "front": "d3", "blocker": None}]}


def test_forced_retreats_read_the_queen_being_chased_off_the_engine_line():
    board = chess.Board(B6)
    chased = forced_retreats(board, ["b6", "d4", "Nf6", "d5", "Qd6", "Nb5", "Qd7"], chess.BLACK)
    assert [(r["san"], r["chased_by"]) for r in chased] == [("Qd6", "d5"), ("Qd7", "Nb5")]
    quiet = forced_retreats(board, ["Nf6", "Nf3", "Qd6", "d4", "e6", "O-O", "a6", "Qd3"], chess.BLACK)
    assert quiet == []


def claim(played, alt, *, played_line, alt_line, move_class="inaccuracy"):
    board = chess.Board(B6)
    return tempo_claim(board, board.parse_san(played), board.parse_san(alt), played_line=played_line,
                       alt_line=alt_line, move_class=move_class, mover_is_user=True)


def test_b6_against_nf6_fires_with_the_cause_the_better_move_and_the_chase():
    out = claim("b6", "Nf6", played_line=["b6", "d4", "Nf6", "d5", "Qd6", "Nb5", "Qd7"],
                alt_line=["Nf6", "Nf3", "Qd6", "d4", "e6", "O-O", "a6", "Qd3"])
    assert out["fires"] is True
    assert out["text"] == (
        "b6 does not bring a piece out. Your queen on e6 is standing where your e-pawn needs to go, "
        "so the bishop on f8 cannot move and you cannot castle. Nf6 brings the knight out. "
        "After b6, d5 makes your queen move again.")
    assert out["facts"]["the_piece_that_cannot_move"] == "your bishop on f8"
    assert out["facts"]["what_is_in_its_way"] == "your queen on e6, the square the e-pawn needs"
    assert out["facts"]["what_the_better_move_does"] == "brings the knight out"


def test_b6_against_qd6_says_the_queen_steps_out_of_the_way():
    out = claim("b6", "Qd6", played_line=["b6", "d4", "Bb7", "Nf3", "Bxf3", "gxf3", "Qd7"],
                alt_line=["Qd6", "d4", "Nf6", "Nf3", "e6", "O-O", "a6", "Re1"])
    assert out["fires"] is True
    assert "Qd6 steps out of the e-pawn's way." in out["text"]
    # Qd7 after gxf3: the queen is not attacked, so no chase is claimed.
    assert out["consequence"] is None and "makes your queen" not in out["text"]


def test_a_move_order_position_says_the_better_move_makes_the_same_threat_and_develops():
    # mohit_qc2: Qc2 and Bd3 both attack the knight on e4; only Bd3 brings a piece out.
    fen = "rnbq1rk1/pppp1p2/4p2p/6p1/2PPn3/2P3B1/P4PPP/R2QKBNR w KQ - 0 9"
    board = chess.Board(fen)
    out = tempo_claim(board, board.parse_san("Qc2"), board.parse_san("Bd3"),
                      played_line=["Qc2", "Nxg3", "hxg3", "Kg7", "Bd3"], alt_line=["Bd3", "Nxg3", "hxg3", "Kg7", "f4"],
                      move_class="mistake", mover_is_user=True)
    assert out["fires"] is True
    assert out["text"] == ("Qc2 brings the queen out before the pieces. "
                           "Bd3 makes the same threat to their knight on e4 and brings the bishop out.")
    assert out["facts"]["the_piece_both_moves_attack"] == "the opponent's knight on e4"
    # b6 and Nf6 attack nothing in common, so no such clause there.
    assert claim("b6", "Nf6", played_line=["b6"], alt_line=["Nf6"])["same_threat"] is None


def test_a_quiet_better_move_is_a_shared_property_and_stays_silent():
    out = claim("b6", "c6", played_line=["b6", "d4"], alt_line=["c6", "d4"])
    assert out["eligible"] is True and out["fires"] is False and out["why_not"] == "shared_quiet"


def test_the_family_never_fires_on_a_blunder_or_a_good_move():
    assert claim("b6", "Nf6", played_line=["b6"], alt_line=["Nf6"], move_class="blunder")["why_not"] == "class"
    assert claim("b6", "Nf6", played_line=["b6"], alt_line=["Nf6"], move_class="good")["why_not"] == "class"


def test_a_developing_played_move_is_not_a_tempo_loss():
    assert claim("Nf6", "Qd6", played_line=["Nf6"], alt_line=["Qd6"])["why_not"] == "played_develops"


def test_a_developed_position_is_out_of_scope():
    # Both sides developed; one knight at home is not "still developing".
    board = chess.Board("r1bq1rk1/pp2bppp/2n2n2/3p4/3P4/2N2N2/PP2BPPP/R1BQ1RK1 w - - 0 10")
    out = tempo_claim(board, board.parse_san("a3"), board.parse_san("Bg5"), played_line=["a3"], alt_line=["Bg5"],
                      move_class="inaccuracy", mover_is_user=True)
    assert out["why_not"] == "developed"


# ------------------------------------------------------------------ flow --

class ScriptedSession:
    """Answers explain_move's queries for the b6 position from fixed lines."""

    def __init__(self, config, mover, _fingerprint):
        self.config = config
        self.records = []
        self.executed_queries = 0
        self.requested_nodes = 0

    def _record(self, board, purpose, lines, roots, width, depth):
        self.executed_queries += 1
        rec = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in (roots or [])],
                           100, width or 1, "complete_iteration", lines, requested_depth=depth)
        self.records.append(rec)
        return rec

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        def line(score, *san):
            walker = board.copy()
            ucis = []
            for s in san:
                mv = walker.parse_san(s)
                ucis.append(mv.uci())
                walker.push(mv)
            return {"root_uci": ucis[0], "moves_uci": ucis, "moves_san": list(san),
                    "score": {"kind": "cp", "value": score, "pov": "black"}, "depth": 16, "nodes": 1}

        def _record(purpose_, lines):
            return self._record(board, purpose_, lines, roots, width, depth)
        self._record_lines = _record
        if purpose == "differential_root":
            return _record(purpose, [line(-113, "Nf6", "Nf3", "Qd6", "d4", "e6", "O-O", "a6", "Qd3"),
                                     line(-114, "Qd6", "d4", "Nf6", "Nf3", "e6", "O-O", "a6", "Re1"),
                                     line(-178, "b6", "d4", "Nf6", "d5", "Qd6", "Nb5", "Qd7", "Bf4")])
        if roots:
            return _record(purpose, [line(-150, board.san(roots[0]))])
        # Branch probes: the reply locator runs on the position after each root move.
        return _record(purpose, [line(-150, board.san(next(iter(board.legal_moves))))])


def test_explain_move_falls_through_the_material_families_to_tempo(monkeypatch):
    from services.reasoning import differential as mod

    def no_dependency(board, session, depth):
        return {"status": "no_dependency", "signal": None, "measurements": []}

    monkeypatch.setattr(mod, "probe_reply_dependency", no_dependency)
    r = explain_move(B6, "b6", config=config(), depth=16, rating=1200, session_factory=ScriptedSession)
    assert r["found"] is True and r["mechanism"] == "TEMPO" and r["direction"] == "missed"
    assert r["class"] == "inaccuracy" and r["better_move"] == "Nf6"
    assert r["text"].startswith("b6 does not bring a piece out. Your queen on e6 is standing where your e-pawn needs to go")
    assert r["text"].endswith("After b6, d5 makes your queen move again.")
    assert r["line_san"] == ["Nf6"] and len(r["arrows"]) == 1
    facts = build_facts(r)
    assert facts["the_move_that_does_it"] == "Nf6" and facts["this_happens_after_the_move_played"] is False
    assert facts["relation"].startswith("the move played brings no piece out")
    assert "the_captures_in_the_line" not in facts


def test_the_words_guard_keeps_the_tempo_relation_and_the_owners():
    from services.why_words import validate
    board = chess.Board(B6)
    out = tempo_claim(board, board.parse_san("b6"), board.parse_san("Nf6"),
                      played_line=["b6", "d4", "Nf6", "d5", "Qd6"], alt_line=["Nf6", "Nf3", "Qd6"],
                      move_class="inaccuracy", mover_is_user=True)
    facts = {"whose_move": "the reader's", "the_move_played": "b6", "the_better_move": "Nf6",
             "the_move_that_does_it": "Nf6", **out["facts"]}
    assert validate(facts, "b6 brings nothing out. Your queen on e6 is in your e-pawn's way, so the bishop "
                           "on f8 cannot move. Nf6 brings the knight out instead.") is None
    # "slow" conveys the relation; a sentence that only ranks the moves does not.
    assert validate(facts, "b6 is slow here. Nf6 was better.") is None
    assert validate(facts, "b6 was not the best choice. Nf6 was better.") == "dropped the TEMPO relation"
    assert validate(facts, "The opponent's queen on e6 blocks the bishop on f8; Nf6 brings a knight out.") \
        == "swapped ownership of the queen"
    assert validate(facts, "Nf6 brings the knight out and prepares Bb4.").startswith("invented chess")
