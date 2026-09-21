"""The opportunity side of trapped-piece truth: traps the OPPONENT's piece.

Every position here is a real Lichess puzzle, identified by its puzzle id, and
every line is the stored solution. The negative cases are not invented: each
one is a puzzle from a DIFFERENT theme that the same escape enumeration fires
on when one gate is removed, which is what the gates are for.
"""

from __future__ import annotations

import chess

from services.board_concepts import enemy_trapped_pieces, trapped_pieces
from services.trapped_piece_puzzle_proof import (
    build_trapped_piece_opportunity_proof,
    build_trapped_piece_proof,
)


def _fires(fen: str, best: str, pv, played: str, cp_loss: int = 300):
    return build_trapped_piece_opportunity_proof(
        chess.Board(fen), played, best, pv, cp_loss
    )


# --- positives --------------------------------------------------------------

# 009FP. Bg5 attacks the queen on f6 along the d8-h4 diagonal, so the three
# squares the queen would retreat to are the same three squares the bishop now
# covers, and every other square it can reach is covered by a pawn or the white
# queen. Black has to give the queen up for the bishop.
TRAPPED_QUEEN_FEN = "r1b1k1nr/ppp2pbp/3p1qp1/4p3/2BnP3/N2P2QP/PPP2PP1/R1B1K2R w KQkq - 0 10"

# 01Bmi. The rook on a1 has no move at all: its own knight sits on b1 and its
# own pawn on a2. Bxb2 attacks it and there is nothing to be done.
BOXED_IN_ROOK_FEN = "rn1qk2r/ppp2ppp/5b2/3P4/4P3/5Q1P/PPP2PP1/RN2KB1R b KQkq - 0 10"

# 00AhO. Bb7 does not trap anything yet -- the queen still has a7. It is the
# SECOND initiator move, Ra8, that seals it. This is the case that a one-move
# test scores as a miss.
DELAYED_TRAP_FEN = "Q1b2rk1/2q2p1p/1p2pbp1/pP6/2P5/P2B1N2/5PPP/3R1RK1 b - - 0 20"

# 0BwIq. White has just pushed g4, taking the last flight square away from his
# own queen, and ...g6 attacks it. The double pawn push leaves an en passant
# square behind, which is why this position is here. It is reached by pushing
# g4 rather than by parsing a FEN, because `Board.fen()` drops an ep square
# that no legal capture can use -- and the real pipeline arrives here by
# pushing too, so the FEN round trip would quietly hide the whole case.
BEFORE_DOUBLE_PUSH_FEN = "r2r2k1/1pbq1pp1/p3p2p/P2pPn1Q/1P3P2/2N1P2R/3B2PP/R5K1 w - - 0 21"


def test_queen_with_every_retreat_covered_is_trapped():
    proof = _fires(TRAPPED_QUEEN_FEN, "c1g5", ["f6g5", "g3g5"], "c4f7")

    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "missed_tactic.trapped_enemy_piece"
    fact = proof.detector.facts[0]
    assert (fact["square"], fact["piece"], fact["color"]) == ("f6", "queen", "black")
    assert fact["trapping_move"] == "c1g5"
    assert fact["trap_ply_index"] == 0
    assert proof.verifier.acceptable_moves == ("c1g5",)


def test_rook_boxed_in_by_its_own_army_is_trapped():
    proof = _fires(BOXED_IN_ROOK_FEN, "f6b2", ["f3b3", "b2a1"], "h8g8")

    assert proof is not None
    assert proof.verifier.verified is True
    fact = proof.detector.facts[0]
    assert (fact["square"], fact["piece"]) == ("a1", "rook")


def test_trap_that_closes_later_in_the_stored_line_still_counts():
    proof = _fires(DELAYED_TRAP_FEN, "c8b7", ["a8a7", "f8a8", "a7a8", "b7a8"], "g8h8")

    assert proof is not None
    assert proof.verifier.verified is True
    fact = proof.detector.facts[0]
    assert (fact["square"], fact["piece"]) == ("a7", "queen")
    # Bb7 is what the player must find, but Ra8 two initiator plies later is
    # what actually springs the trap.
    assert fact["trapping_move"] == "f8a8"
    assert fact["trap_ply_index"] == 2
    assert proof.detector.acceptable_moves == ("c8b7",)


def test_en_passant_square_does_not_hide_a_trap_sprung_after_a_pawn_push():
    board = chess.Board(BEFORE_DOUBLE_PUSH_FEN)
    board.push(chess.Move.from_uci("g2g4"))
    assert board.ep_square == chess.G3, "fixture must carry the ep square"

    proof = build_trapped_piece_opportunity_proof(
        board, "g8h8", "g7g6", ["h5g6", "f7g6"], 300
    )

    assert proof is not None
    assert proof.verifier.verified is True
    fact = proof.detector.facts[0]
    assert (fact["square"], fact["piece"]) == ("h5", "queen")


# --- curated negatives ------------------------------------------------------

# 001wr, theme `fork`. Qc5+ is check. While black is checking, white has no
# legal move with the bishop on c4 at all, so "every escape loses material" is
# true of it by saying nothing. The bishop is lost to tempo, not to geometry.
FORK_WITH_CHECK_FEN = "r4rk1/p3ppbp/Pp1q1np1/3PpbB1/2B5/2N2P2/1PPQ2PP/3RR1K1 b - - 0 18"

# 00ZeT, theme `pin`. Bb5 attacks a queen that is pinned to its king, so the
# queen is frozen for the same vacuous reason. The lesson there is the pin.
PIN_FEN = "1Q6/3kr3/2q4p/2p1pp1P/2Bb4/1P6/P6K/4R3 w - - 5 44"

# 0Ffq1, theme `trappedPiece`. The bishop on h5 is genuinely trapped, but it
# was already trapped before Qxc5 -- the g4 pawn did that. Qxc5 wins a knight;
# saying it traps the bishop would be a false claim about cause.
ALREADY_TRAPPED_FEN = "r2q1rk1/1p3p1p/1n4p1/2nPp2b/p1PQ2P1/2N5/PP2BP2/R3R1K1 w - - 0 20"


def test_a_piece_frozen_by_check_is_not_a_trapped_piece():
    board = chess.Board(FORK_WITH_CHECK_FEN)
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci("d6c5"))
    assert after.is_check()
    # Without the check gate the raw enumeration does claim a trapped piece.
    assert trapped_pieces(after, chess.WHITE)
    assert enemy_trapped_pieces(after, chess.BLACK) == []

    assert _fires(FORK_WITH_CHECK_FEN, "d6c5", ["g1h1", "c5c4"], "g8h8") is None


def test_a_pinned_piece_is_not_a_trapped_piece():
    board = chess.Board(PIN_FEN)
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci("c4b5"))
    assert after.is_pinned(chess.BLACK, chess.C6)
    # Without the pin gate the raw enumeration does claim a trapped queen.
    assert [item["square"] for item in trapped_pieces(after, chess.BLACK)] == ["c6"]
    assert enemy_trapped_pieces(after, chess.WHITE) == []

    assert _fires(PIN_FEN, "c4b5", ["c6b5", "b8b5"], "b8h8") is None


def test_a_piece_that_was_already_trapped_is_not_claimed_as_newly_trapped():
    assert _fires(ALREADY_TRAPPED_FEN, "d4c5", ["h5g4", "e2g4"], "d4e5") is None


def test_low_consequence_does_not_become_a_trapped_piece_lesson():
    assert _fires(TRAPPED_QUEEN_FEN, "c1g5", ["f6g5", "g3g5"], "c4f7", cp_loss=20) is None


def test_the_played_move_matching_the_best_move_is_not_a_missed_opportunity():
    assert _fires(TRAPPED_QUEEN_FEN, "c1g5", ["f6g5", "g3g5"], "c1g5") is None


def test_an_illegal_stored_line_is_rejected_rather_than_guessed_at():
    assert _fires(TRAPPED_QUEEN_FEN, "c1g5", ["a1a1"], "c4f7") is None


# --- the two sides stay separate -------------------------------------------

MISTAKE_SIDE_FEN = "3rkb1r/2p3p1/p7/Qp2p3/2b5/4B3/P1q2KPP/4R2R w k - 0 23"


def test_the_mistake_side_detector_is_untouched():
    """Bd2 traps White's OWN bishop. That proof must keep working as it did."""
    proof = build_trapped_piece_proof(chess.Board(MISTAKE_SIDE_FEN), "Bd2", "Kg1", 9287)

    assert proof is not None
    assert proof.verifier.verified is True
    assert proof.detector.concept_id == "piece_safety.trapped_piece"


def test_the_two_sides_do_not_answer_each_others_question():
    """The mistake side sees nothing in an opponent-trapping position."""
    board = chess.Board(TRAPPED_QUEEN_FEN)

    assert build_trapped_piece_proof(board, "Bg5", "Bg5", 300) is None


def test_enemy_trapped_pieces_needs_the_attacker_to_have_just_moved():
    """Called with the attacker still to move it must abstain, not guess."""
    board = chess.Board(TRAPPED_QUEEN_FEN)

    assert enemy_trapped_pieces(board, chess.WHITE) == []
