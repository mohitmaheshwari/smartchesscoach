"""Mate read from the engine's score, and a threat met by taking the reply piece.

2026-11-17, from Mohit's own games (scope: docs/why_threat_line_scope.md,
"Fixes 2026-11-17"). Engine answers recorded from a real run (local Stockfish,
button config, depth 16) and replayed, keyed by position, restricted roots and
width, so these tests pin the reading of the lines, not the engine.

  5ec24941 m19  Rf2, Qd3# was mate in one; the button was silent (the mate
                walk needs a line after the mating move, and there is none).
  856f6111 m6   Ke8 allows mate in six; the button named a pawn on g6 (the
                walk reads six plies, the mate is at the eleventh).
  2d86e1f9 m17  Rf8 Nxf6: the threat line said "Nxf6 threatens Nh7+"; the
                defence is gxf6, the knight never makes that move.
  c31e86a3 m15  Nc6 Nc7 forks queen and rook; after Na6 the defence is Nxc7,
                so the threat is not "the same after the better move".
"""
import chess

from services.reasoning.contracts import SearchRecord
from services.reasoning.differential import explain_move
from services.reasoning.threat_line import threat_line
from test_reasoning_boundaries import config

RECORDED = {'ke8': {'r1bq1bnr/ppp2kp1/2n4p/3p4/2BpP3/8/PPP2PPP/RNBQK2R w KQ - 0 7|a2a3,a2a4,b1a3,b1c3,b1d2,b2b3,b2b4,c1d2,c1e3,c1f4,c1g5,c1h6,c2c3,c4a6,c4b3,c4b5,c4d3,c4e2,c4f1,d1d2,d1d3,d1d4,d1e2,d1f3,d1g4,d1h5,e1d2,e1e2,e1f1,e1g1,e4d5,e4e5,f2f3,f2f4,g2g3,g2g4,h1f1,h1g1,h2h3,h2h4|1': {'lines': [{'moves_san': ['exd5',
                                                                                                                                                                                                                                                                                                             'Na5',
                                                                                                                                                                                                                                                                                                             'Be2',
                                                                                                                                                                                                                                                                                                             'Nf6',
                                                                                                                                                                                                                                                                                                             'Qxd4',
                                                                                                                                                                                                                                                                                                             'Qxd5',
                                                                                                                                                                                                                                                                                                             'Qxd5+',
                                                                                                                                                                                                                                                                                                             'Nxd5',
                                                                                                                                                                                                                                                                                                             'Bd2',
                                                                                                                                                                                                                                                                                                             'Nc6',
                                                                                                                                                                                                                                                                                                             'Nc3',
                                                                                                                                                                                                                                                                                                             'Be6'],
                                                                                                                                                                                                                                                                                               'score': ['cp',
                                                                                                                                                                                                                                                                                                         516]}],
                                                                                                                                                                                                                                                                                    'status': 'complete_iteration'},
         'r1bq1bnr/ppp2kp1/2n4p/3p4/2BpP3/8/PPP2PPP/RNBQK2R w KQ - 0 7||1': {'lines': [{'moves_san': ['Bxd5+',
                                                                                                      'Kg6',
                                                                                                      'c3',
                                                                                                      'Nge7',
                                                                                                      'Bb3',
                                                                                                      'Kh7',
                                                                                                      'h4',
                                                                                                      'dxc3',
                                                                                                      'O-O',
                                                                                                      'Qxd1',
                                                                                                      'Rxd1',
                                                                                                      'g6'],
                                                                                        'score': ['cp',
                                                                                                  420]}],
                                                                             'status': 'complete_iteration'},
         'r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6|f7e8|1': {'lines': [{'moves_san': ['Ke8',
                                                                                                         'Qh5+',
                                                                                                         'g6',
                                                                                                         'Qxg6+',
                                                                                                         'Ke7',
                                                                                                         'Qf7+',
                                                                                                         'Kd6',
                                                                                                         'Bf4+',
                                                                                                         'Kc5',
                                                                                                         'Qd5+',
                                                                                                         'Kb6',
                                                                                                         'Qb5#'],
                                                                                           'score': ['mate',
                                                                                                     -6]}],
                                                                                'status': 'complete_iteration'},
         'r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6||3': {'lines': [{'moves_san': ['d5',
                                                                                                     'Bxd5+',
                                                                                                     'Kg6',
                                                                                                     'O-O',
                                                                                                     'Kh7',
                                                                                                     'f4',
                                                                                                     'Nf6',
                                                                                                     'Bxc6',
                                                                                                     'bxc6',
                                                                                                     'e5',
                                                                                                     'Nd5',
                                                                                                     'f5'],
                                                                                       'score': ['cp', 436]},
                                                                                      {'moves_san': ['Kg6',
                                                                                                     'Bd3',
                                                                                                     'Ne5',
                                                                                                     'Be2',
                                                                                                     'Kh7',
                                                                                                     'Qxd4',
                                                                                                     'Nc6',
                                                                                                     'Qd3',
                                                                                                     'Bc5',
                                                                                                     'a3',
                                                                                                     'd6',
                                                                                                     'b4'],
                                                                                       'score': ['cp', 400]},
                                                                                      {'moves_san': ['Ke7',
                                                                                                     'c3',
                                                                                                     'd3',
                                                                                                     'f4',
                                                                                                     'Qe8',
                                                                                                     'O-O',
                                                                                                     'Kd8',
                                                                                                     'Qxd3',
                                                                                                     'b6',
                                                                                                     'Be3',
                                                                                                     'Bb7',
                                                                                                     'e5'],
                                                                                       'score': ['cp', 249]}],
                                                                            'status': 'complete_iteration'},
         'r1bqkbnr/pppp2p1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R w KQ - 2 7|a2a3,a2a4,b1a3,b1c3,b1d2,b2b3,b2b4,c1d2,c1e3,c1f4,c1g5,c1h6,c2c3,c4a6,c4b3,c4b5,c4d3,c4d5,c4e2,c4e6,c4f1,c4f7,c4g8,d1d2,d1d3,d1d4,d1e2,d1f3,d1g4,e1d2,e1e2,e1f1,e1g1,e4e5,f2f3,f2f4,g2g3,g2g4,h1f1,h1g1,h2h3,h2h4|1': {'lines': [{'moves_san': ['O-O',
                                                                                                                                                                                                                                                                                                                     'Qh4',
                                                                                                                                                                                                                                                                                                                     'Nd2',
                                                                                                                                                                                                                                                                                                                     'Bc5',
                                                                                                                                                                                                                                                                                                                     'Nf3',
                                                                                                                                                                                                                                                                                                                     'Qh5',
                                                                                                                                                                                                                                                                                                                     'Be2',
                                                                                                                                                                                                                                                                                                                     'Nf6',
                                                                                                                                                                                                                                                                                                                     'b4',
                                                                                                                                                                                                                                                                                                                     'Bxb4',
                                                                                                                                                                                                                                                                                                                     'Nxd4',
                                                                                                                                                                                                                                                                                                                     'Qf7'],
                                                                                                                                                                                                                                                                                                       'score': ['cp',
                                                                                                                                                                                                                                                                                                                 373]}],
                                                                                                                                                                                                                                                                                            'status': 'complete_iteration'},
         'r1bqkbnr/pppp2p1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R w KQ - 2 7||1': {'lines': [{'moves_san': ['Qh5+',
                                                                                                    'g6',
                                                                                                    'Qxg6+',
                                                                                                    'Ke7',
                                                                                                    'Qf7+',
                                                                                                    'Kd6',
                                                                                                    'Bf4+',
                                                                                                    'Kc5',
                                                                                                    'Qd5+',
                                                                                                    'Kb6',
                                                                                                    'Qb5#'],
                                                                                      'score': ['mate', -6]}],
                                                                           'status': 'complete_iteration'}},
 'nc6': {'r1b1q1k1/ppNp2pp/2n2p2/2b5/3pr3/P5BP/1PP2PPN/R2Q1RK1 b - - 4 16||1': {'lines': [{'moves_san': ['Qd8',
                                                                                                         'b4',
                                                                                                         'Bf8',
                                                                                                         'Nxa8',
                                                                                                         'd6',
                                                                                                         'Nf3',
                                                                                                         'Bd7',
                                                                                                         'b5',
                                                                                                         'Ne7',
                                                                                                         'Nxd4',
                                                                                                         'Qxa8',
                                                                                                         'Bxd6'],
                                                                                           'score': ['cp',
                                                                                                     -579]}],
                                                                                'status': 'complete_iteration'},
         'r1b1q1k1/ppNp2pp/2n2p2/2b5/3pr3/P5BP/1PP2PPN/R2Q1RK1 w - - 5 17||1': {'lines': [{'moves_san': ['Nxe8',
                                                                                                         'Rxe8',
                                                                                                         'Qh5',
                                                                                                         'g6',
                                                                                                         'Qxc5',
                                                                                                         'Nd8',
                                                                                                         'Qb4',
                                                                                                         'Ne6',
                                                                                                         'Qb3',
                                                                                                         'Kg7',
                                                                                                         'a4',
                                                                                                         'Nc5'],
                                                                                           'score': ['cp',
                                                                                                     -915]}],
                                                                                'status': 'complete_iteration'},
         'r1b1q1k1/ppNp2pp/n4p2/2b5/3pr3/P5BP/1PP2PPN/R2Q1RK1 b - - 4 16||1': {'lines': [{'moves_san': ['Nxc7',
                                                                                                        'Bxc7',
                                                                                                        'b6',
                                                                                                        'Qd3',
                                                                                                        'Bb7',
                                                                                                        'Nf3',
                                                                                                        'Qf7',
                                                                                                        'b4',
                                                                                                        'Bf8',
                                                                                                        'Bg3',
                                                                                                        'Qd5',
                                                                                                        'c4'],
                                                                                          'score': ['cp',
                                                                                                    167]}],
                                                                               'status': 'complete_iteration'},
         'r1b1q1k1/ppNp2pp/n4p2/2b5/3pr3/P5BP/1PP2PPN/R2Q1RK1 w - - 5 17|c7e8|1': {'lines': [{'moves_san': ['Nxe8',
                                                                                                            'Rxe8',
                                                                                                            'Qh5',
                                                                                                            'g6',
                                                                                                            'Qd5+',
                                                                                                            'Kg7',
                                                                                                            'Qf3',
                                                                                                            'd3',
                                                                                                            'b4',
                                                                                                            'Bb6'],
                                                                                              'score': ['cp',
                                                                                                        -884]}],
                                                                                   'status': 'complete_iteration'}},
 'rf2': {'r1b2r2/ppp1k1p1/4n3/4p2Q/N5P1/1PP1b3/PB1q2B1/RK5R b - - 1 19|f8f2|1': {'lines': [{'moves_san': ['Rf2',
                                                                                                          'Qh4+',
                                                                                                          'Ng5',
                                                                                                          'Be4',
                                                                                                          'Qe2',
                                                                                                          'Ba3+',
                                                                                                          'Kf6',
                                                                                                          'Rg1',
                                                                                                          'Be6',
                                                                                                          'Bc5',
                                                                                                          'Bxc5',
                                                                                                          'Nxc5'],
                                                                                            'score': ['cp',
                                                                                                      451]}],
                                                                                 'status': 'complete_iteration'},
         'r1b2r2/ppp1k1p1/4n3/4p2Q/N5P1/1PP1b3/PB1q2B1/RK5R b - - 1 19||3': {'lines': [{'moves_san': ['Qd3#'],
                                                                                        'score': ['mate', 1]},
                                                                                       {'moves_san': ['Rf1+',
                                                                                                      'Bxf1',
                                                                                                      'Qd1+',
                                                                                                      'Bc1',
                                                                                                      'Qxc1#'],
                                                                                        'score': ['mate', 3]},
                                                                                       {'moves_san': ['Qxg2',
                                                                                                      'Qh4+',
                                                                                                      'Kd7',
                                                                                                      'Rd1+',
                                                                                                      'Kc6',
                                                                                                      'Bc1',
                                                                                                      'Bxc1',
                                                                                                      'Kxc1',
                                                                                                      'Qe4',
                                                                                                      'Kb2',
                                                                                                      'b5',
                                                                                                      'Kc1'],
                                                                                        'score': ['cp',
                                                                                                  704]}],
                                                                             'status': 'complete_iteration'},
         'r1b5/ppp1k1p1/4n3/4p2Q/N5P1/1PP1b3/PB1q1rB1/RK5R w - - 2 20|a2a3,a4b6,a4c5,b2a3,b2c1,b3b4,c3c4,g2b7,g2c6,g2d5,g2f1,g2f3,g2h3,g4g5,h1c1,h1d1,h1e1,h1f1,h1g1,h1h2,h1h3,h1h4,h5e5,h5e8,h5f5,h5f7,h5g5,h5g6,h5h2,h5h3,h5h4,h5h6,h5h7,h5h8|1': {'lines': [{'moves_san': ['Ba3+',
                                                                                                                                                                                                                                                                              'c5',
                                                                                                                                                                                                                                                                              'Be4',
                                                                                                                                                                                                                                                                              'Bd7',
                                                                                                                                                                                                                                                                              'Bc1',
                                                                                                                                                                                                                                                                              'Qe2',
                                                                                                                                                                                                                                                                              'Bxe3',
                                                                                                                                                                                                                                                                              'Qxe3',
                                                                                                                                                                                                                                                                              'Qh4+',
                                                                                                                                                                                                                                                                              'Kd6',
                                                                                                                                                                                                                                                                              'Bc2',
                                                                                                                                                                                                                                                                              'Qe2'],
                                                                                                                                                                                                                                                                'score': ['cp',
                                                                                                                                                                                                                                                                          475]}],
                                                                                                                                                                                                                                                     'status': 'complete_iteration'},
         'r1b5/ppp1k1p1/4n3/4p2Q/N5P1/1PP1b3/PB1q1rB1/RK5R w - - 2 20||1': {'lines': [{'moves_san': ['Be4',
                                                                                                     'b5',
                                                                                                     'Bc1',
                                                                                                     'Qe2',
                                                                                                     'Ba3+',
                                                                                                     'c5',
                                                                                                     'Qh4+',
                                                                                                     'Kd6',
                                                                                                     'Nb2',
                                                                                                     'Rf1+',
                                                                                                     'Rxf1',
                                                                                                     'Qxf1+'],
                                                                                       'score': ['cp', 506]}],
                                                                            'status': 'complete_iteration'}},
 'rf8': {'1r1q1r2/p3nkp1/5N1p/4p3/2bb4/5Q2/PP3PPP/R1B1R1K1 b - - 0 18||1': {'lines': [{'moves_san': ['gxf6',
                                                                                                     'Qh5+',
                                                                                                     'Ng6',
                                                                                                     'Be3',
                                                                                                     'Bxe3',
                                                                                                     'Rxe3',
                                                                                                     'Rg8',
                                                                                                     'Rd1',
                                                                                                     'Qe7',
                                                                                                     'f4',
                                                                                                     'Be6',
                                                                                                     'f5'],
                                                                                       'score': ['cp', 692]}],
                                                                            'status': 'complete_iteration'},
         '1r1q1r2/p3nkp1/5N1p/4p3/2bb4/5Q2/PP3PPP/R1B1R1K1 w - - 1 19||1': {'lines': [{'moves_san': ['Nh7+',
                                                                                                     'Kg8',
                                                                                                     'Nxf8',
                                                                                                     'Qxf8',
                                                                                                     'Qxf8+',
                                                                                                     'Kxf8',
                                                                                                     'Be3',
                                                                                                     'Rxb2',
                                                                                                     'Reb1',
                                                                                                     'Rxb1+',
                                                                                                     'Rxb1',
                                                                                                     'Bxa2'],
                                                                                       'score': ['cp', 404]}],
                                                                            'status': 'complete_iteration'}}}


class Replay:
    def __init__(self, table, pov):
        self.table, self.pov = table, pov
        self.config = config(rank_width=3)
        self.records, self.executed_queries, self.requested_nodes = [], 0, 0

    def query(self, board, purpose, *, roots=(), width=1, nodes=None, depth=None):
        self.executed_queries += 1
        hit = self.table.get(f"{board.fen()}|{','.join(sorted(m.uci() for m in roots))}|{width}")
        lines = []
        for entry in (hit or {}).get("lines", []):
            walker, ucis = board.copy(), []
            for san in entry["moves_san"]:
                mv = walker.parse_san(san)
                ucis.append(mv.uci())
                walker.push(mv)
            kind, value = entry["score"]
            lines.append({"root_uci": ucis[0], "moves_uci": ucis, "moves_san": list(entry["moves_san"]),
                          "score": {"kind": kind, "value": value, "pov": "white" if self.pov else "black"},
                          "depth": 16, "nodes": 1})
        status = (hit or {}).get("status", "unavailable") if lines else "unavailable"
        record = SearchRecord(str(len(self.records)), purpose, board.fen(), [m.uci() for m in roots],
                              nodes or 1, width, status, lines, requested_depth=depth)
        self.records.append(record)
        return record


def _explain(key, fen, played, alt):
    return explain_move(fen, played, config=config(rank_width=3), depth=16, rating=1300, mover_is_user=True,
                        alternative_san=alt, session_factory=lambda cfg, pov, hist: Replay(RECORDED[key], pov))


def _threat(key, fen, played, alt, reply):
    root = chess.Board(fen)
    p, a = root.parse_san(played), root.parse_san(alt)
    after = root.copy()
    after.push(p)
    return threat_line(Replay(RECORDED[key], root.turn), root, p, a, after.parse_san(reply).uci(),
                       depth=16, mover_is_user=True)


def test_a_missed_mate_in_one_is_named():
    out = _explain("rf2", "r1b2r2/ppp1k1p1/4n3/4p2Q/N5P1/1PP1b3/PB1q2B1/RK5R b - - 1 19", "Rf2", "Qd3#")
    assert out["found"] is True and out["mechanism"] == "MATE" and out["direction"] == "missed"
    assert out["text"] == "Qd3# was checkmate."
    assert out["mate_from_score"] == {"side": "missed", "mate_in": 1}


def test_an_allowed_mate_beyond_the_six_ply_walk_outranks_the_pawn_on_the_way():
    out = _explain("ke8", "r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6", "Ke8", "d5")
    assert out["found"] is True and out["mechanism"] == "MATE" and out["direction"] == "received"
    assert out["text"] == "After Ke8, Qh5+ leads to mate."
    assert "pawn" not in out["text"]


def test_no_threat_when_the_defence_takes_the_reply_piece():
    out = _threat("rf8", "1r1q3r/p3nkp1/5n1p/4p3/2bbN3/5Q2/PP3PPP/R1B1R1K1 b - - 1 17", "Rf8", "Bd5", "Nxf6")
    assert out["fires"] is False and out["why_not"] == "defence_takes_the_reply"
    assert out["threat_san"] == "Nh7+"


def test_a_threat_met_by_taking_the_reply_after_the_better_move_is_the_difference():
    out = _threat("nc6", "rnb1q1k1/pp1p2pp/5p2/2bN4/3pr3/P5BP/1PP2PPN/R2Q1RK1 b - - 2 15", "Nc6", "Na6", "Nc7")
    assert out["fires"] is True and out["defence_takes_reply_after_better_move"] is True
    assert out["cause"]["text"] == ("After Nc6, Nc7 threatens Nxe8, which wins your queen on e8 for a knight. "
                                    "After Na6, your knight guards c7.")
    assert out["guard"]["square"] == "c7"
