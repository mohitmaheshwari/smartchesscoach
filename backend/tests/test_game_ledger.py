"""The ledger records what happened, for both players, with its evidence.

Built on game 56b6c294 (Mohit, Black), whose moves 16 and 17 were checked by
hand with the engine on 2026-10-21: 16...Ng5 left the queen on h4 to be
trapped by Rh1, and White played 17.f4 instead.
"""
import chess

from services.game_ledger import (
    OPENING_LAST_MOVE,
    build_ledger,
    build_timeline,
)

FEN_16 = "r4rk1/ppp2ppp/6b1/3pb3/4P1Bq/P1N4n/1PP2PK1/R1BQ1R2 b - - 1 16"


def _rows():
    """Black's rows for moves 16 and 17, white-relative evals as stored."""
    board = chess.Board(FEN_16)
    board.push_san("Ng5")
    board.push_san("f4")
    fen_17 = board.fen()
    board.push_san("Bxc3")
    board.push_san("fxg5")
    fen_18 = board.fen()
    return [
        {"move": "Ng5", "move_number": 16, "fen_before": FEN_16,
         "eval_before": -633, "eval_after": 307, "cp_loss": 952,
         "best_move": "Bxc3", "evaluation": "blunder",
         "pv_after_played": ["Rh1", "Qxg4+", "Qxg4", "Nxe4"]},
        {"move": "Bxc3", "move_number": 17, "fen_before": fen_17,
         "eval_before": -581, "eval_after": -650, "cp_loss": 0,
         "best_move": "Bxc3", "evaluation": "best", "pv_after_played": []},
        {"move": "Bxe4+", "move_number": 18, "fen_before": fen_18,
         "eval_before": -735, "eval_after": -728, "cp_loss": 0,
         "best_move": "Bxe4+", "evaluation": "best", "pv_after_played": []},
    ]


def _ledger(**kw):
    return build_ledger(move_evaluations=_rows(), observations=[], user_color="black",
                        outcome="win", **kw)


def _event(ledger, side, san):
    return next(e for e in ledger["events"] if e["side"] == side and e["san"] == san)


class TestTimeline:
    def test_the_opponents_moves_are_recovered_from_the_boards(self):
        points = build_timeline(_rows(), "black")
        assert [(p["side"], p["san"]) for p in points] == [
            ("you", "Ng5"), ("them", "f4"), ("you", "Bxc3"), ("them", "fxg5"), ("you", "Bxe4+"),
        ]

    def test_evaluations_are_from_the_players_side(self):
        points = build_timeline(_rows(), "black")
        assert points[0]["eval_before"] == 633 and points[0]["eval_after"] == -307


class TestYourMistake:
    def test_ng5_is_a_decisive_mistake(self):
        e = _event(_ledger(), "you", "Ng5")
        assert e["kind"] == "your_mistake" and e["decisive"] is True

    def test_the_trapped_queen_is_proved_on_the_board(self):
        e = _event(_ledger(), "you", "Ng5")
        assert e["danger"] == {"kind": "queen_trapped", "reply": "Rh1"}

    def test_it_happened_but_was_not_punished(self):
        e = _event(_ledger(), "you", "Ng5")
        assert e["happened"] is True
        assert e["punished"] is False
        assert e["evidence"]["their_reply"] == "f4"


class TestTheirMistake:
    def test_f4_is_their_mistake_and_you_took_it(self):
        e = _event(_ledger(), "them", "f4")
        assert e["kind"] == "their_mistake"
        assert e["taken"] is True and e["your_answer"] == "Bxc3"
        # What they should have played is the stored punishing reply.
        assert e["evidence"]["their_best"] == "Rh1"


class TestOpeningAndFinish:
    def test_the_opening_is_cut_at_the_earlier_of_the_two(self):
        assert _ledger(phase_exit_move=9)["opening"]["last_move"] == 9
        assert _ledger(phase_exit_move=30)["opening"]["last_move"] == OPENING_LAST_MOVE

    def test_the_name_falls_back_to_the_book_record(self):
        dev = {"deviation": {"last_opening_name": "Queen's Gambit", "played_san": "a3",
                             "expected_san": "e3", "user_move_number": 6}}
        opening = _ledger(opening_deviation=dev)["opening"]
        assert opening["name"] == "Queen's Gambit"
        assert opening["left_book"] == {"played": "a3", "book": "e3", "move_number": 6}

    def test_a_given_name_wins(self):
        assert _ledger(opening_name="Queen's Pawn Opening")["opening"]["name"] == "Queen's Pawn Opening"

    def test_a_winning_position_kept_to_the_end(self):
        assert _ledger()["finish"]["kept_winning"] is True


class TestQueenTrapProof:
    def test_a_queen_that_can_trade_itself_off_is_not_trapped(self):
        from services.game_ledger import _queen_trapped_after
        # White queen on a1 is attacked, and every square she can reach is
        # covered -- including b2, where she would take Black's queen and be
        # taken back by the c3 pawn. That is a trade of queens, not a trap.
        board = chess.Board("rk6/5K2/8/8/4b3/2p5/1q6/Q6r w - - 0 1")
        assert board.is_valid() and not board.is_check()
        queen_moves = [m for m in board.legal_moves if m.from_square == chess.A1]
        assert all(board.is_attacked_by(chess.BLACK, m.to_square) for m in queen_moves)
        assert _queen_trapped_after(board, chess.WHITE) is False

    def test_a_queen_in_check_is_not_called_trapped(self):
        from services.game_ledger import _queen_trapped_after
        board = chess.Board("4r1k1/8/8/8/8/8/8/4K2Q w - - 0 1")
        assert board.is_check()
        assert _queen_trapped_after(board, chess.WHITE) is False


class TestMissedMate:
    def test_a_lost_forced_mate_is_its_own_event(self):
        rows = _rows()
        rows[0] = {**rows[0], "mate_info": {"before": -3, "after": None}}
        ledger = build_ledger(move_evaluations=rows, observations=[], user_color="black",
                              outcome="win")
        e = _event(ledger, "you", "Ng5")
        assert e["kind"] == "missed_mate" and e["happened"] is False


class TestAllowedMate:
    def test_a_mate_for_the_opponent_after_the_move_is_the_danger(self):
        rows = _rows()
        rows[0] = {**rows[0], "mate_info": {"before": None, "after": 4}}
        ledger = build_ledger(move_evaluations=rows, observations=[], user_color="black",
                              outcome="win")
        assert _event(ledger, "you", "Ng5")["danger"]["kind"] == "mate_allowed"


class TestBoxedIn:
    def _timeline(self, fen, moves, player_is_white):
        """A timeline from a start position and a list of SAN moves, with a
        steadily rising player evaluation."""
        board = chess.Board(fen)
        points, value = [], 0
        for san in moves:
            mover_is_player = (board.turn == chess.WHITE) == player_is_white
            move = board.parse_san(san)
            before = value
            value += 60 if mover_is_player else 0
            points.append({"side": "you" if mover_is_player else "them",
                           "move_number": board.fullmove_number, "san": san,
                           "uci": move.uci(), "fen_before": board.fen(),
                           "eval_before": before, "eval_after": value})
            board.push(move)
        return points

    FEN = "6k1/8/8/8/8/6K1/r7/R7 w - - 0 1"
    # White's rook moves first, so it counts as developed; then Black checks
    # five times in a row while the player's evaluation keeps rising -- enough
    # to be credited as "you shut it in" if the checks were counted.
    MOVES = ["Rd1", "Ra3+", "Kf4", "Ra4+", "Kf5", "Ra5+", "Kf6", "Ra6+", "Kf5", "Ra5+"]

    def test_the_scenario_really_leaves_the_rook_no_safe_square(self):
        """So the next test exercises the rule rather than passing vacuously."""
        board = chess.Board(self.FEN)
        for san in self.MOVES:
            board.push_san(san)
            if board.turn == chess.WHITE:
                rook = next(iter(board.pieces(chess.ROOK, chess.WHITE)))
                assert board.is_check()
                assert not [m for m in board.legal_moves if m.from_square == rook
                            and not board.attackers(chess.BLACK, m.to_square)]

    def test_checks_do_not_make_a_piece_look_boxed_in(self):
        """Game 8874941e: a rook on d1 looked boxed in through four checks,
        free each time the check ended."""
        from services.game_ledger import boxed_in_episodes
        timeline = self._timeline(self.FEN, self.MOVES, player_is_white=False)
        assert boxed_in_episodes(timeline, player_is_white=False) == []


class TestATimelineWithAGap:
    def test_a_missing_opponent_move_does_not_break_the_ledger(self):
        """Four production games had an opponent move the timeline could not
        rebuild; the boxed-in tracker then pushed an illegal move and the
        whole plan failed."""
        from services.game_ledger import boxed_in_episodes
        board = chess.Board()
        board.push_san("e4")
        after_e4 = board.fen()
        board.push_san("e5")
        board.push_san("Nf3")
        board.push_san("Nc6")       # the gap: this move is missing below
        gap_fen = board.fen()
        timeline = [
            {"side": "you", "move_number": 1, "san": "e4", "uci": "e2e4",
             "fen_before": chess.STARTING_FEN, "eval_before": 0, "eval_after": 20},
            {"side": "them", "move_number": 1, "san": "e5", "uci": "e7e5",
             "fen_before": after_e4, "eval_before": 20, "eval_after": 20},
            # Nf3 and ...Nc6 were never reconstructed; the next point is
            # White's third move from the real position.
            # Nxe5 needs the knight that went to f3 in the missing moves, so
            # on a stale board it is not even pseudo-legal -- the crash.
            {"side": "you", "move_number": 3, "san": "Nxe5", "uci": "f3e5",
             "fen_before": gap_fen, "eval_before": 20, "eval_after": 30},
        ]
        assert boxed_in_episodes(timeline, player_is_white=True) == []
