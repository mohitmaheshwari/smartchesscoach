"""Traps found in a player's own games, Stage A (docs/trap_lesson_from_games_scope.md).

The windows are Mohit's stored move_evaluations (his own moves, three in a row
ending in the losing move), copied 2026-11-17. Maia is replaced by a fixed
share so the tests pin the board rule; the real share was measured separately
(856f6111 Ke8 61%, c209379f Qxa2 94%).
"""
import copy

from services.game_trap_finder import NATURAL_MIN, find_offer_traps, share_words

WINDOWS = {'CASTLE': {'color': 'black',
            'win': [{'best_move': 'Bxe4',
                     'cp_loss': 7,
                     'eval_after': 19,
                     'eval_before': 15,
                     'fen_after': 'r2qk2r/ppp1ppbp/2n3p1/5b2/3Pp3/2B1PN2/PPP1BPPP/R2QK2R w KQkq - 0 9',
                     'fen_before': 'r2qk2r/ppp1ppbp/2n3p1/3p1b2/3PN3/2B1PN2/PPP1BPPP/R2QK2R b KQkq - 0 8',
                     'move': 'dxe4',
                     'move_number': 8,
                     'pv_after_played': []},
                    {'best_move': 'e5',
                     'cp_loss': 315,
                     'eval_after': 312,
                     'eval_before': -7,
                     'fen_after': 'r2qk2r/ppp2pbp/2n1p1p1/5b2/3Pp3/2B1P3/PPPNBPPP/R2QK2R w KQkq - 0 10',
                     'fen_before': 'r2qk2r/ppp1ppbp/2n3p1/5b2/3Pp3/2B1P3/PPPNBPPP/R2QK2R b KQkq - 1 9',
                     'move': 'e6',
                     'move_number': 9,
                     'pv_after_played': ['g4', 'Bxg4', 'Bxg4', 'f5']},
                    {'best_move': 'e5',
                     'cp_loss': 267,
                     'eval_after': 299,
                     'eval_before': 22,
                     'fen_after': 'r2q1rk1/ppp2pbp/2n1p1p1/5b2/3Pp3/2B1P2P/PPPNBPP1/R2QK2R w KQ - 1 11',
                     'fen_before': 'r2qk2r/ppp2pbp/2n1p1p1/5b2/3Pp3/2B1P2P/PPPNBPP1/R2QK2R b KQkq - 0 10',
                     'move': 'O-O',
                     'move_number': 10,
                     'pv_after_played': ['g4', 'Qh4', 'gxf5', 'Rad8']}]},
 'KE8': {'color': 'black',
         'win': [{'best_move': 'Be7',
                  'cp_loss': 38,
                  'eval_after': -133,
                  'eval_before': -175,
                  'fen_after': 'r1bqkbnr/pppp1pp1/2n4p/6N1/3pP3/8/PPP2PPP/RNBQKB1R w KQkq - 0 5',
                  'fen_before': 'r1bqkbnr/pppp1ppp/2n5/6N1/3pP3/8/PPP2PPP/RNBQKB1R b KQkq - 1 4',
                  'move': 'h6',
                  'move_number': 4,
                  'pv_after_played': ['Nf3', 'Bc5', 'Bd3', 'd6', 'c3', 'dxc3', 'Nxc3', 'Nge7', 'Bf4', 'Ng6']},
                 {'best_move': 'Kxf7',
                  'cp_loss': 0,
                  'eval_after': -307,
                  'eval_before': -305,
                  'fen_after': 'r1bq1bnr/pppp1kp1/2n4p/8/3pP3/8/PPP2PPP/RNBQKB1R w KQ - 0 6',
                  'fen_before': 'r1bqkbnr/pppp1Np1/2n4p/8/3pP3/8/PPP2PPP/RNBQKB1R b KQkq - 0 5',
                  'move': 'Kxf7',
                  'move_number': 5,
                  'pv_after_played': []},
                 {'best_move': 'd5',
                  'cp_loss': 1304,
                  'eval_after': 9940,
                  'eval_before': -303,
                  'fen_after': 'r1bqkbnr/pppp2p1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R w KQ - 2 7',
                  'fen_before': 'r1bq1bnr/pppp1kp1/2n4p/8/2BpP3/8/PPP2PPP/RNBQK2R b KQ - 1 6',
                  'move': 'Ke8',
                  'move_number': 6,
                  'pv_after_played': ['Qh5+',
                                      'g6',
                                      'Qxg6+',
                                      'Ke7',
                                      'Qf7+',
                                      'Kd6',
                                      'Bf4+',
                                      'Kc5',
                                      'Qd5+',
                                      'Kb6']}]},
 'QXA2': {'color': 'black',
          'win': [{'best_move': 'Qb6',
                   'cp_loss': 63,
                   'eval_after': 278,
                   'eval_before': 211,
                   'fen_after': 'rnb1k1nr/pppp1ppp/8/4p3/1bPP4/2N1P3/Pq1B1PPP/R2QKBNR w KQkq - 2 6',
                   'fen_before': 'rnb1kbnr/pppp1ppp/8/4p3/2PP4/2N1P3/Pq1B1PPP/R2QKBNR b KQkq - 1 5',
                   'move': 'Bb4',
                   'move_number': 5,
                   'pv_after_played': ['Rb1', 'Qxc3', 'Bxc3', 'Bxc3+']},
                  {'best_move': 'exd4',
                   'cp_loss': 40,
                   'eval_after': 158,
                   'eval_before': 128,
                   'fen_after': 'rnb1k1nr/pppp1ppp/8/4p3/2PP4/2b1P3/Pq1B1PPP/2RQKBNR w Kkq - 0 7',
                   'fen_before': 'rnb1k1nr/pppp1ppp/8/4p3/1bPP4/2N1P3/Pq1B1PPP/2RQKBNR b Kkq - 3 6',
                   'move': 'Bxc3',
                   'move_number': 6,
                   'pv_after_played': ['Bxc3', 'Qa3', 'dxe5', 'Nc6']},
                  {'best_move': 'Qa3',
                   'cp_loss': 380,
                   'eval_after': 531,
                   'eval_before': 150,
                   'fen_after': 'rnb1k1nr/pppp1ppp/8/4p3/2PP4/2B1P3/q4PPP/2RQKBNR w Kkq - 0 8',
                   'fen_before': 'rnb1k1nr/pppp1ppp/8/4p3/2PP4/2B1P3/Pq3PPP/2RQKBNR b Kkq - 0 7',
                   'move': 'Qxa2',
                   'move_number': 7,
                   'pv_after_played': ['Ra1', 'Qxa1', 'Bxa1', 'd5']}]}}


def _find(key, share=0.9):
    w = WINDOWS[key]
    return find_offer_traps(w["win"], w["color"], lambda fen, uci: share)


def test_taking_the_pawn_the_offer_left_unguarded_is_a_trap():
    # c209379f m7: Rc1 takes the rook off a2's guard; Qxa2 Ra1 traps the queen.
    out = _find("QXA2")
    assert len(out) == 1
    f = out[0]
    assert f["kind"] == "offer_taken" and f["natural_san"] == "Qxa2" and f["offer_san"] == "Rc1"
    assert f["offer_moves_back"] == 2 and f["net_cp"] <= -200 and f["took"] == "p"
    assert f["holding_move"] == "Qa3"


def test_answering_the_check_after_a_sacrifice_is_a_trap():
    # 856f6111 m6: 5.Nxf7 gives the knight, 6.Bc4+ checks, Ke8 walks into mate.
    out = _find("KE8")
    assert len(out) == 1
    f = out[0]
    assert f["kind"] == "check_after_sacrifice" and f["offer_san"] == "Nxf7" and f["mate"] is True
    assert f["natural_san"] == "Ke8" and f["holding_move"] == "d5"


def test_a_quiet_move_that_shuts_in_a_piece_is_not_stage_a():
    # c96adfdb m10: h3 then g4 against the bishop. Stage B, not this rule.
    assert _find("CASTLE") == []


def test_a_move_few_players_would_choose_is_not_a_trap():
    assert _find("KE8", share=NATURAL_MIN - 0.01) == []
    assert _find("KE8", share=None) == []


KING_STEP = {'color': 'white',
 'win': [{'best_move': 'Rxc7',
          'cp_loss': 0,
          'eval_after': 255,
          'eval_before': 242,
          'fen_after': 'r3r3/p1R2p1k/6p1/8/8/Pb1B4/1P3PPP/5RK1 b - - 0 23',
          'fen_before': 'r3r3/p1p2p1k/2R3p1/8/8/Pb1B4/1P3PPP/5RK1 w - - 0 23',
          'move': 'Rxc7',
          'move_number': 23,
          'pv_after_played': []},
         {'best_move': 'Bc2',
          'cp_loss': 700,
          'eval_after': -440,
          'eval_before': 263,
          'fen_after': 'r3r3/5R1k/6p1/p7/8/Pb1B4/1P3PPP/5RK1 b - - 0 24',
          'fen_before': 'r3r3/2R2p1k/6p1/p7/8/Pb1B4/1P3PPP/5RK1 w - - 0 24',
          'move': 'Rxf7+',
          'move_number': 24,
          'pv_after_played': ['Bxf7', 'f4', 'Rad8', 'Bb5', 'Re3', 'b4', 'Be8', 'Bxe8', 'Rexe8', 'bxa5']},
         {'best_move': 'Rf6',
          'cp_loss': 859,
          'eval_after': -368,
          'eval_before': 485,
          'fen_after': 'r3r1k1/5R2/6B1/p7/8/Pb6/1P3PPP/5RK1 b - - 0 25',
          'fen_before': 'r3r1k1/5R2/6p1/p7/8/Pb1B4/1P3PPP/5RK1 w - - 1 25',
          'move': 'Bxg6',
          'move_number': 25,
          'pv_after_played': ['Bxf7', 'Bxf7+', 'Kxf7', 'h4', 'Re4', 'b4', 'a4', 'b5', 'Rc4', 'b6']}]}


def test_a_king_move_is_never_the_offer():
    # 4f24e726 m25 (another player, dry run 1): the opponent's Kg8 left g6
    # without the king's guard and Bxg6 lost; a blunder by them, not bait.
    out = find_offer_traps(KING_STEP["win"], KING_STEP["color"], lambda fen, uci: 0.9)
    assert out == []


def test_share_is_said_in_words_never_numbers():
    assert share_words(0.61) == "most players at your level"
    assert share_words(0.5) == "about half of players at your level"
    assert share_words(0.31) == "many players at your level"
