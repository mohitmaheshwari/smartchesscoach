"""A recommended move's reason must come from the board, not the phrase bank.

Mohit 2026-09-29, on "Opponent's Qa5 is a major blunder. Play Ra1 -- it puts
your rook on a line where none of your own pawns are in the way": "again, no
why here."

On `2r2rk1/p4ppp/8/q7/6P1/1P1R2QP/nKP2P2/7R w - - 6 26` the reason is sitting
on the board: Ra1 hits the knight on a2, which the rook AND the king on b2
attack while only the queen on a5 defends it. The old branch asked "is it
defended?" as a boolean, got yes, and fell through to the open-file phrase.

Everything here is checked by counting squares. Nothing reads a phrase bank.
"""
import re

import chess

from services.caption_facts import PIECE_TYPE_NAMES, _recommended_move_why

REPORTED = "2r2rk1/p4ppp/8/q7/6P1/1P1R2QP/nKP2P2/7R w - - 6 26"
PATTERN = re.compile(r"^attacks the (\w+) on ([a-h][1-8]), which only their (\w+) defends$")
NAME_TO_TYPE = {name: t for t, name in PIECE_TYPE_NAMES.items()}


def _why(fen, san):
    board = chess.Board(fen)
    return _recommended_move_why(board, board.parse_san(san))


class TestTheReportedPosition:
    def test_the_counts_are_what_the_sentence_claims(self):
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Ra1"))
        attackers = {chess.square_name(s) for s in board.attackers(chess.WHITE, chess.A2)}
        defenders = {chess.square_name(s) for s in board.attackers(chess.BLACK, chess.A2)}
        assert attackers == {"a1", "b2"}, "rook and king both hit a2"
        assert defenders == {"a5"}, "only the queen defends it"

    def test_the_reason_names_the_knight_and_its_only_defender(self):
        match = PATTERN.match(_why(REPORTED, "Ra1") or "")
        assert match, f"got {_why(REPORTED, 'Ra1')!r}"
        piece, square, defender = match.groups()
        assert (piece, square, defender) == ("knight", "a2", "queen")

    def test_it_no_longer_reaches_for_the_open_file_phrase(self):
        assert "none of your own pawns" not in (_why(REPORTED, "Ra1") or "")

    def test_it_does_not_promise_to_win_the_piece(self):
        # The opponent moves next and can simply play Nb4 or Nc3. An earlier
        # version said "wins the knight on a2" and Stockfish refused 18 of 40
        # sampled claims. A count is true whatever they answer.
        why = _why(REPORTED, "Ra1") or ""
        assert "wins" not in why
        board = chess.Board(REPORTED)
        board.push(board.parse_san("Ra1"))
        escapes = [m for m in board.legal_moves if m.from_square == chess.A2]
        assert escapes, "the knight really can run, which is why we do not claim a win"


class TestTheOldBranchesAreUntouched:
    def test_an_undefended_piece_still_reads_as_a_plain_attack(self):
        why = _why("6k1/5ppp/8/3n4/8/8/5PPP/3R2K1 w - - 0 1", "Rd4")
        assert why == "attacks the knight on d5"

    def test_nothing_to_hit_still_falls_back_to_the_principle(self):
        why = _why("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "Rd4")
        assert why is None or "pawns are in the way" in why


class TestItStaysQuietWhenTheCountIsNotDecisive:
    def test_two_defenders_is_not_an_outnumbered_target(self):
        # Knight on d5 defended by BOTH pawns c6 and e6: no lone defender to
        # point at, so this reason must not fire.
        fen = "6k1/8/2p1p3/3n4/8/8/5PPP/3R2K1 w - - 0 1"
        board = chess.Board(fen)
        board.push(board.parse_san("Rd4"))
        defenders = [d for d in board.attackers(chess.BLACK, chess.D5)]
        assert len(defenders) == 2
        assert not PATTERN.match(_why(fen, "Rd4") or "")

    def test_a_single_attacker_is_not_outnumbering_anything(self):
        # Rook alone hits the defended knight: one attacker, one defender.
        fen = "6k1/8/4p3/3n4/8/8/5PPP/3R2K1 w - - 0 1"
        board = chess.Board(fen)
        board.push(board.parse_san("Rd4"))
        assert len(list(board.attackers(chess.WHITE, chess.D5))) == 1
        assert not PATTERN.match(_why(fen, "Rd4") or "")
