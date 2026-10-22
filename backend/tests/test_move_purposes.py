"""What the better move achieves: the vocabulary, and what it refuses to say.

The vocabulary was not invented. It came from reading 23 mined positions one
at a time and writing down, in words, what the better move did -- then
measuring every candidate on 7,346 flagged cards:

    attacks a piece that cannot escape  21.7%   avoids a square they attack 14.4%
    moves the attacked piece to safety  14.1%   check that worsens the king  7.1%
    defends the attacked piece           6.9%   a pawn attacks a piece       6.4%
    activates the rook                   6.3%   trades off their piece       5.9%
    denies their counterplay             4.3%   stops their passed pawn      3.5%

    at least one purpose 61.7%    two or more 23.5%

Two entries did not survive that measurement. `F` (supports our passed pawn)
fired on 0.4% -- 28 cards, not a detector. And `D` was split: it was the
biggest number and the loosest probe, merging "an enemy piece is hanging"
with "every retreat lands on a square we attack". Different lessons, and the
name overclaimed on the first. The trapped half now routes through
game_ledger._piece_trapped_after, which is already proven and stricter than
anything this file would have written.

Every case below is a real position from the mining set or from a card Mohit
flagged, and every assertion is checked against the board first.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.move_purposes import purposes_for, threat_check  # noqa: E402

# Mohit's card: 25.Bd6+ played, Qxg8 winning.
BD6 = "rk1q2r1/pp3Q2/2b2p2/4p3/1BPb4/7B/P1P2P1P/R3K2R w KQ - 1 25"
# 4...Nc6 played with the f6 knight attacked by the e5 pawn; Ne4 saves it.
NC6 = "rnbqkb1r/pppp1ppp/5n2/4P3/3p4/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 4"
# 11.O-O played; a3 hits the b4 bishop.
A3 = "r1b1k2r/pp3ppp/4p3/q2p4/1bPPn3/1P3N2/P2NBPPP/R2QK2R w KQkq - 0 11"
# 40.Rc1 steps into the d3 knight's reach; Rf1 does not.
RC1 = "2b5/7p/2R5/3p1pk1/8/2pn4/3r2P1/3R2K1 w - - 0 40"


def kinds(*args, **kw):
    return [p["kind"] for p in purposes_for(*args, **kw)]


class TestTheBoardSaysWhatTheseClaim:
    def test_the_f6_knight_really_is_attacked_and_e4_is_not(self):
        b = chess.Board(NC6)
        assert b.piece_at(chess.F6).piece_type == chess.KNIGHT
        assert chess.E5 in b.attackers(chess.WHITE, chess.F6)
        a = b.copy()
        a.push(a.parse_san("Ne4"))
        assert not a.attackers(chess.WHITE, chess.E4) or \
            a.attackers(chess.BLACK, chess.E4)

    def test_c1_really_is_in_the_knights_reach_and_f1_is_not(self):
        b = chess.Board(RC1)
        assert chess.D3 in b.attackers(chess.BLACK, chess.C1)
        assert chess.D3 not in b.attackers(chess.BLACK, chess.F1)


class TestItFindsWhatIsThere:
    def test_a_piece_in_danger_that_moves_away(self):
        assert "moves_to_safety" in kinds(NC6, "Nc6", "Ne4", ["exf6"], [])

    def test_a_pawn_that_attacks_a_piece(self):
        assert "pawn_attacks_piece" in kinds(A3, "O-O", "a3", [], [])

    def test_the_played_move_walking_onto_an_attacked_square(self):
        assert "avoids_attacked_square" in kinds(RC1, "Rc1", "Rf1", ["Nxc1"], [])

    def test_an_enemy_man_left_hanging_by_the_better_move(self):
        assert "wins_hanging_piece" in kinds(BD6, "Bd6+", "Qxg8",
                                             ["Qxd6", "Qxg8+"], [])


class TestItReturnsSeveralThingsRankedNotOneWinner:
    """23.5% of cards have more than one true purpose. The old code was an
    if-chain returning the first match, so a capture that also forked and
    defended reported only the capture."""

    def test_more_than_one_purpose_can_come_back(self):
        got = purposes_for(RC1, "Rc1", "Rf1", ["Nxc1"], [])
        assert len(got) >= 2, [p["kind"] for p in got]

    def test_they_are_ranked_strongest_first(self):
        got = purposes_for(RC1, "Rc1", "Rf1", ["Nxc1"], [])
        tiers = [p["tier"] for p in got]
        assert tiers == sorted(tiers, reverse=True), tiers

    def test_every_purpose_carries_its_own_proof(self):
        for p in purposes_for(RC1, "Rc1", "Rf1", ["Nxc1"], []):
            assert p["proof"], p
            assert isinstance(p["facts"], dict)


class TestTheMateTransitionBothWays:
    """23% of the residue, and the highest-stakes cards in the corpus at
    8,000-10,000cp. Both directions are already in `mate_info`."""

    def test_a_mate_that_was_available_and_given_up(self):
        got = purposes_for(BD6, "Bd6+", "Qxg8", [], [],
                           mate_info={"before": -4, "after": None})
        assert "missed_forced_mate" in [p["kind"] for p in got]

    def test_a_mate_that_was_walked_into(self):
        got = purposes_for(BD6, "Bd6+", "Qxg8", [], [],
                           mate_info={"before": None, "after": -10})
        assert "allowed_forced_mate" in [p["kind"] for p in got]

    def test_mate_outranks_everything_else(self):
        got = purposes_for(BD6, "Bd6+", "Qxg8", ["Qxd6", "Qxg8+"], [],
                           mate_info={"before": None, "after": -3})
        assert got[0]["kind"] == "allowed_forced_mate", [p["kind"] for p in got]

    def test_mate_on_both_sides_is_not_a_transition(self):
        """Already mated before and after is not a lesson about this move."""
        got = purposes_for(BD6, "Bd6+", "Qxg8", [], [],
                           mate_info={"before": -3, "after": -2})
        assert not [p for p in got if "mate" in p["kind"]]


class TestItRefusesToOverreach:
    def test_an_illegal_best_move_yields_nothing_rather_than_guessing(self):
        assert purposes_for(BD6, "Bd6+", "Qxz9", [], []) == []

    def test_a_broken_position_returns_empty_not_an_exception(self):
        assert purposes_for("not-a-fen", "e4", "d4", [], []) == []

    def test_no_best_move_means_no_purposes_about_one(self):
        assert purposes_for(BD6, "Bd6+", None, [], []) == []

    def test_a_threat_that_survives_the_better_move_is_not_answered(self):
        """answers_threat must prove the threat is GONE, never assume it."""
        got = kinds(BD6, "Bd6+", "Qxg8", [], [], threat="Qxg5")
        assert "answers_threat" not in got


class TestAThreatHasToThreatenSomething:
    """stockfish_service.get_threat returns the opponent's best reply and
    nothing more -- its own docstring says so -- and every position has one.
    Filed under `they_were_threatening`, that string told the model a quiet
    developing move was a threat, and the model wrote correct English for
    it: "your d6 didn't stop their knight from moving to f3".

    Measured over 8,200 faulted cards carrying a stored threat, judged on
    the board the engine computed it on: 79.6% threaten nothing.

    The board matters as much as the test. The old code probed fen_before
    with the turn flipped, which is a position that never occurred: the two
    boards disagree on 18.5% of cards, the flipped one calls 1,060 legal
    threats illegal, and it confirms 9.0% where the truth is 20.4%.
    """

    # Mohit's card, move 4: d6 played, c6 better, stored threat Nf3.
    QUIET = "rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/2PP4/PP3PPP/RNBQK1NR b KQkq - 0 4"

    def test_the_board_really_does_allow_nf3_after_d6(self):
        """So a refusal below is the test working, not the move being
        illegal."""
        b = chess.Board(self.QUIET)
        b.push_san("d6")
        assert b.parse_san("Nf3") in b.legal_moves

    def test_a_quiet_developing_reply_is_not_a_threat(self):
        assert threat_check(self.QUIET, "d6", "Nf3") is None

    def test_it_says_what_a_real_threat_wins(self):
        """White has just grabbed e5 and the e4 pawn is hanging."""
        fen = "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        got = threat_check(fen, "Nxe5", "Nxe4")
        assert got and got["move"] == "Nxe4"
        assert "pawn on e4" in got["it_would_win"]

    def test_mate_is_named_as_mate(self):
        """1.f3 e5 2.g4 Qh4#. The board here is after 1.f3 e5, so g4 is the
        played move and the mate is the reply to it."""
        fen = "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2"
        b = chess.Board(fen)
        b.push_san("g4")
        b.push_san("Qh4")
        assert b.is_checkmate()
        got = threat_check(fen, "g4", "Qh4")
        assert got and got["it_would_win"] == "mate", got

    def test_an_even_recapture_wins_nothing(self):
        """Taking a defended man with an equal one is a trade, not a
        threat."""
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        assert threat_check(fen, "Nc6", "Nxe5") is None

    def test_a_threat_read_on_the_wrong_board_is_refused(self):
        """Nf3 is legal for white before black moves too, so the old
        turn-flipped probe found it there. On the right board it still
        wins nothing -- and an unrelated SAN that is only legal on the
        flipped board gets no answer at all."""
        assert threat_check(self.QUIET, "d6", "Bxf7+") is None

    def test_the_purpose_no_longer_fires_on_a_non_threat(self):
        got = kinds(self.QUIET, "d6", "c6", ["Nf3", "O-O"], ["Nf3", "O-O"],
                    threat="Nf3")
        assert "answers_threat" not in got


class TestAnOfferTheEngineDeclines:
    """Mohit's Rousseau card. Black plays f5, exf5 takes it with nothing
    defending, and the engine answers d4. The authored caption's conclusion
    -- "exf5 is usually a mistake" -- is derivable from the stored line, so
    it belongs in a caption; the REASON (after exf5, e4 hits the knight on
    f3) needs a search of a line the engine never returns, so it belongs
    behind the Why button.

    Tightened before shipping: the loose shape fires on 16.3% of faulted
    cards, every pawn trade ever offered. Requiring the capture to win
    material statically gives 2.2%.
    """

    F5 = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"

    def test_the_board_really_does_offer_the_pawn_for_free(self):
        b = chess.Board(self.F5)
        b.push_san("f5")
        assert b.parse_san("exf5") in b.legal_moves
        # nothing of Black's defends f5
        assert not b.attackers(chess.BLACK, chess.F5)

    def test_it_fires_when_the_engine_answers_elsewhere(self):
        got = kinds(self.F5, "f5", "Nf6", ["d4", "exd4"], [])
        assert "offered_and_not_taken" in got, got

    def test_it_names_the_capture_and_the_answer(self):
        for p in purposes_for(self.F5, "f5", "Nf6", ["d4", "exd4"], []):
            if p["kind"] == "offered_and_not_taken":
                assert "exf5" in p["proof"]
                assert "d4" in p["proof"]
                return
        raise AssertionError("the purpose did not fire")

    def test_it_stands_down_when_the_engine_does_take(self):
        got = kinds(self.F5, "f5", "Nf6", ["exf5", "e4"], [])
        assert "offered_and_not_taken" not in got

    def test_it_claims_no_reason_it_has_not_proven(self):
        """The WHY is the button's job. The proof may not assert that the
        centre is deflected or that a knight gets hit -- neither is shown
        by the stored line."""
        for p in purposes_for(self.F5, "f5", "Nf6", ["d4", "exd4"], []):
            if p["kind"] == "offered_and_not_taken":
                low = p["proof"].lower()
                for word in ("centre", "center", "tempo", "gambit",
                             "deflect", "knight"):
                    assert word not in low, f"proof asserts '{word}'"

    def test_an_even_trade_offer_is_not_this_lesson(self):
        """A defended man taken by an equal man is a trade. If this fired
        there it would describe every pawn trade in the corpus -- the 16.3%
        the tightening removed."""
        fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"
        b = chess.Board(fen)
        b.push_san("d5")
        # d5 is attacked by exd5 and defended by Qxd5
        assert b.attackers(chess.WHITE, chess.D5)
        assert b.attackers(chess.BLACK, chess.D5)
        got = kinds(fen, "d5", "Nc6", ["Nc3", "Nf6"], [])
        assert "offered_and_not_taken" not in got

    def test_it_needs_the_engines_answer_and_will_not_guess(self):
        assert "offered_and_not_taken" not in kinds(self.F5, "f5", "Nf6",
                                                    [], [])

    def test_the_contradicting_framing_is_dropped_not_outranked(self):
        """On this card the list came back with "f5 is attacked and f6 is
        not" SECOND and the offer last. Ranking cannot settle that: if the
        engine declines the free man, the square being attacked is the
        point of the move, and telling the mover to go somewhere safe is
        false teaching. So the offer survives and the other goes."""
        got = kinds(self.F5, "f5", "Nf6", ["d4", "exd4"], ["Nf6", "d3"])
        assert "offered_and_not_taken" in got
        assert "avoids_attacked_square" not in got, got

    def test_it_only_drops_it_for_the_same_square(self):
        """A pawn offered on f5 says nothing about a piece that stepped
        onto an attacked square somewhere else, so the suppression is
        keyed to the square and not to the kind."""
        import services.move_purposes as mp
        src = mp.__file__
        with open(src, encoding="utf-8") as fh:
            body = fh.read()
        assert 'p.facts.get("played_square") in _offer_squares' in body

    def test_without_the_offer_the_attacked_square_fact_still_speaks(self):
        """The negative control for the suppression: remove the engine's
        answer so the offer cannot fire, and the other purpose must come
        back -- otherwise this dropped it for everyone."""
        got = kinds(self.F5, "f5", "Nf6", ["exf5", "e4"], ["Nf6", "d3"])
        assert "offered_and_not_taken" not in got
        assert "avoids_attacked_square" in got, got


class TestACheckThatAchievedNothing:
    """131 cards in the residue, and one of the few lessons in this file a
    900 can apply the same evening. "Achieved nothing" is proven by playing
    the check and their answer and comparing material, so a check that wins
    a man is left to the material purposes that already own it."""

    # 32.Rd8+ played, Kg3 better: a rook-and-pawn ending where the check is
    # answered by Kg7 and the rook has to come back.
    RD8 = "6k1/5p1p/3R2p1/p2P4/P2R4/5P1P/r1r3PK/8 w - - 1 32"

    def test_the_played_move_really_is_a_check(self):
        b = chess.Board(self.RD8)
        assert b.gives_check(b.parse_san("Rd8+"))

    def test_the_continuation_used_below_is_legal(self):
        """Guards against the fixture error that made this suite fail
        twice: a line copied from pv_after_BEST will not replay after the
        PLAYED move, and _material_swing correctly refuses it."""
        b = chess.Board(self.RD8)
        for san in ("Rd8+", "Kg7", "Kg1"):
            b.push(b.parse_san(san))

    def test_it_fires_and_names_the_answer(self):
        for p in purposes_for(self.RD8, "Rd8+", "Kg3", ["Kg7", "Kg1"], []):
            if p["kind"] == "played_check_achieved_nothing":
                assert "Kg7" in p["proof"]
                return
        raise AssertionError("the purpose did not fire")

    def test_a_quiet_move_is_not_a_pointless_check(self):
        got = kinds(self.RD8, "R8d7", "Kg3", ["Kf8"], [])
        assert "played_check_achieved_nothing" not in got

    def test_it_fires_on_a_second_position_where_nothing_changes_hands(self):
        """Bb5+ is blocked by Nc6 and no material moves, so the whole
        content of the move was the check."""
        fen = "rnbqk2r/ppp2ppp/3b4/3p4/3P4/2N5/PPP1BPPP/R1BQK2R w KQkq - 0 8"
        b = chess.Board(fen)
        for san in ("Bb5+", "Nc6", "Bg5"):
            b.push(b.parse_san(san))      # the line must replay
        got = kinds(fen, "Bb5+", "O-O", ["Nc6", "Bg5"], [])
        assert "played_check_achieved_nothing" in got, got

    def test_it_needs_their_answer_and_will_not_guess_one(self):
        assert "played_check_achieved_nothing" not in \
            kinds(self.RD8, "Rd8+", "Kg3", [], [])

    # The first version of this purpose called all three of these "wins
    # nothing", which understates giving a piece away and overstates an
    # even trade in the same breath. It measured two plies.
    TRADE = "2r3k1/p5p1/1p3nNp/1P6/3q4/b1NP1Q2/2PK1P1P/4R3 w - - 4 23"
    DROP = "2kr3r/1pp2pR1/p1nq4/3p4/3p3p/4PB2/PPP2P1P/R2Q3K w - - 0 20"

    def test_the_bishop_really_does_come_back_on_the_next_ply(self):
        """23.Ne7+ Bxe7 Rxe7: the knight is taken and the bishop is taken
        straight back, so nothing was given away on that square."""
        b = chess.Board(self.TRADE)
        for san in ("Ne7+", "Bxe7", "Rxe7"):
            b.push(b.parse_san(san))
        assert b.piece_at(chess.E7) == chess.Piece(chess.ROOK, chess.WHITE)

    def test_a_recaptured_checker_is_not_called_a_loss(self):
        got = kinds(self.TRADE, "Ne7+", "Nd1",
                    ["Bxe7", "Rxe7", "Qxc3+", "Ke2"], [])
        assert "played_check_loses_the_checker" not in got, got

    def test_nor_is_it_called_wins_nothing_when_the_line_costs_material(self):
        """That same line drops the c3 knight to Qxc3+ later. Whatever that
        is, it is not a wasted tempo, so this purpose stands down."""
        got = kinds(self.TRADE, "Ne7+", "Nd1",
                    ["Bxe7", "Rxe7", "Qxc3+", "Ke2"], [])
        assert "played_check_achieved_nothing" not in got, got

    def test_a_checker_that_is_simply_taken_says_so(self):
        """20.Bg4+ is answered by Kb8 here, but if they take the bishop and
        keep it, the sentence has to name that."""
        fen = "r1b2rk1/p4ppp/1pN1pn2/3p4/1b1P4/2N5/PPPB1PPP/R2QK2R w KQ - 1 11"
        b = chess.Board(fen)
        b.push(b.parse_san("Ne7+"))
        assert b.is_legal(b.parse_san("Bxe7"))
        for p in purposes_for(fen, "Ne7+", "Nxb4", ["Bxe7", "Qf3"], []):
            if p["kind"] == "played_check_loses_the_checker":
                assert "knight on e7" in p["proof"]
                assert "does not come back" in p["proof"]
                assert p["tier"] == 3
                return
        raise AssertionError("the purpose did not fire")


class TestCastlingIsItsOwnLesson:
    """Mohit's move-6 card: Ng4 played, O-O better, 127cp. It fired no
    purpose, so the model wrote from the stored line -- "it let your
    opponent play d4 and then Bb4+" -- reading the effect off the PV while
    the cause sat on the board, the king still on e8.

    100 cards in the residue are this shape. Everything the purpose claims
    is true of every castling move, so none of it needs the line.
    """

    # 6...Ng4 played, O-O better. The king has not moved.
    NG4 = "rnbqk2r/1pp2ppp/3p1n2/p1b1p3/P1B1P3/2PP1N2/1P3PPP/RNBQK2R b KQkq - 1 6"

    def test_the_king_really_is_still_at_home_and_may_castle(self):
        b = chess.Board(self.NG4)
        assert b.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK)
        assert b.parse_san("O-O") in b.legal_moves

    def test_it_fires_on_the_card_that_got_an_invented_caption(self):
        got = kinds(self.NG4, "Ng4", "O-O", ["d4", "exd4"], [])
        assert "castles_the_king_away" in got, got

    def test_it_says_the_king_leaves_e8_and_the_rook_comes_in(self):
        for p in purposes_for(self.NG4, "Ng4", "O-O", ["d4"], []):
            if p["kind"] == "castles_the_king_away":
                assert "e8" in p["proof"]
                assert "rook" in p["proof"]
                return
        raise AssertionError("the purpose did not fire")

    def test_the_e_file_still_has_a_pawn_so_it_claims_no_open_file(self):
        """e7 is empty here but e5 is a black pawn, so the file is not bare
        and the proof must not say it is."""
        b = chess.Board(self.NG4)
        assert b.piece_at(chess.E5) == chess.Piece(chess.PAWN, chess.BLACK)
        for p in purposes_for(self.NG4, "Ng4", "O-O", ["d4"], []):
            if p["kind"] == "castles_the_king_away":
                assert "no pawn is left" not in p["proof"]
                assert p["facts"]["file_is_open"] is False

    def test_a_plain_king_step_is_not_castling(self):
        fen = "6k1/5ppp/8/8/8/8/5PPP/4K3 w - - 0 30"
        assert "castles_the_king_away" not in kinds(fen, "f3", "Kd2", [], [])

    def test_moving_the_king_instead_is_a_different_lesson(self):
        """When the played move was also a king move, the reader's mistake
        was not leaving the king at home."""
        got = kinds(self.NG4, "Ke7", "O-O", ["d4"], [])
        assert "castles_the_king_away" not in got


class TestTheFloorLineIsTheInputForSmallLosses:
    """Measured over 6,371 faulted cards: 27.7% of the 40-99cp band has no
    punishment line at all, against 2.5% at 300cp+. The small band was never
    short of vocabulary -- the old analysis only searched a line for moves it
    had already called an inaccuracy or worse, so the cards a player reads
    most arrived with nothing to read. `eval_line_played` comes free from the
    evaluation search every move already gets, and these two cases are the
    difference it makes.
    """

    # 29...Nxc2 hangs the knight to Qc3+ picking it up two moves later. The
    # fork purpose can only be seen by walking the line.
    FORK = "8/5pk1/6p1/8/4P3/4n1Q1/PKPN3P/R7 b - - 0 29"
    LINE = ["Qc3+", "Kf8", "Qxc2", "Ke7"]

    def test_the_line_really_does_collect_the_knight(self):
        b = chess.Board(self.FORK)
        b.push(b.parse_san("Nxc2"))
        for san in self.LINE:
            b.push(b.parse_san(san))
        assert not b.pieces(chess.KNIGHT, chess.BLACK)
        assert b.piece_at(chess.C2) == chess.Piece(chess.QUEEN, chess.WHITE)

    def test_without_any_line_the_engine_has_nothing_to_say(self):
        assert kinds(self.FORK, "Nxc2", "Ng2", [], []) == []

    def test_the_floor_line_recovers_the_same_purpose(self):
        assert kinds(self.FORK, "Nxc2", "Ng2", [], [],
                     eval_line=self.LINE) == \
            kinds(self.FORK, "Nxc2", "Ng2", self.LINE, [])

    def test_a_real_punishment_line_is_never_overwritten_by_the_floor(self):
        """The floor is a fallback, not a replacement: the deeper search
        stays authoritative wherever it ran."""
        got = kinds(self.FORK, "Nxc2", "Ng2", self.LINE, [],
                    eval_line=["Ng2", "Kf6"])
        assert "played_allows_fork" in got
