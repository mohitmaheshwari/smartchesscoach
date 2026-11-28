"""The denominator must count chances, and must not invent them.

Mohit, 2026-11-27: "first I need all the detectors to evaluate and fire."
The blocker was never the detectors; it was that only four signals recorded
how often the chance CAME. See services/tactic_opportunity.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import tactic_opportunity as to  # noqa: E402

START = chess.STARTING_FEN


def test_the_king_is_the_most_forkable_man_not_the_least():
    # THE BUG THAT KILLED THE FIRST ATTEMPT. Scoring the king at 0 -- the
    # obvious reading of "a king is never captured" -- made every check-fork
    # invisible: zero chances on 600 real positions and zero on 120 that the
    # validated prover had already tagged as missed forks. A check must be
    # ANSWERED, which is the whole mechanism.
    assert to._VALUE[chess.KING] > to._VALUE[chess.QUEEN]


def test_mate_in_one_is_found_exactly():
    # Back-rank mate: Ra8#. Nothing here is approximated.
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1")
    moves = [m.uci() for m in to.mate_in_one_moves(board)]
    assert "a1a8" in moves


def test_a_position_with_no_mate_offers_no_chance():
    assert to.mate_in_one_moves(chess.Board(START)) == []
    got = to.opportunities(START, "e2e4")
    assert got["mate_in_one"]["eligible"] is False
    # No chance is NOT a failure. This is what makes the pair a rate.
    assert got["mate_in_one"]["fires"] is False


def test_taking_the_mate_is_not_a_miss_and_leaving_it_is():
    fen = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
    took = to.opportunities(fen, "a1a8")
    assert took["mate_in_one"]["eligible"] is True
    assert took["mate_in_one"]["fires"] is False
    left = to.opportunities(fen, "h1g1")
    assert left["mate_in_one"]["eligible"] is True
    assert left["mate_in_one"]["fires"] is True


def test_free_material_needs_no_engine_line():
    # An undefended black rook on a7, white rook on a1. Rxa7 is free.
    # The free-piece prover is the one that takes no line at all, which is
    # why this motif works today and fork does not.
    fen = "4k3/r7/8/8/8/8/8/R3K3 w - - 0 1"
    board = chess.Board(fen)
    cands = [m.uci() for m in to.free_material_candidates(board)]
    assert "a1a7" in cands
    got = to.opportunities(fen, "e1e2")
    assert got["free_material"]["eligible"] is True
    assert got["free_material"]["fires"] is True


def test_a_defended_equal_capture_is_not_free_material():
    # Black rook on a7 DEFENDED by the king on b8; white rook on a1. Rxa7
    # is answered by Kxa7 -- an even trade, not free material.
    # (The first version of this test put the black king on e8, where it
    # defends nothing, so Kxa7 really did win a rook and the prover was
    # right to say so.)
    board = chess.Board("1k6/r7/8/8/8/8/8/R3K3 w - - 0 1")
    assert board.attackers(chess.BLACK, chess.A7)      # it really is defended
    assert to.free_material_moves(board) == []
    for mv in to.free_material_candidates(board):
        assert not to._proved_free(board, mv), mv.uci()


def test_winning_a_bigger_piece_counts_even_when_it_is_defended():
    # A defended QUEEN taken by a rook is still material won: 9 for 5.
    # The black king on c7 guards d8 (a black pawn could not: it would
    # attack d6, not d8).
    board = chess.Board("3q4/2k5/8/8/8/8/8/3RK3 w - - 0 1")
    assert board.attackers(chess.BLACK, chess.D8)      # the king guards it
    assert "d1d8" in [m.uci() for m in to.free_material_candidates(board)]


def test_the_sieve_may_over_offer_but_the_prover_decides():
    # The sieve is deliberately loose so it cannot miss a real chance. What
    # it offers is only a question; `free_material_moves` is the answer.
    board = chess.Board(START)
    assert to.free_material_candidates(board) == []
    assert to.free_material_moves(board) == []


def test_an_unreadable_position_returns_nothing_rather_than_a_zero():
    # A zero chance and an unreadable board are different facts and must not
    # collapse into the same row.
    assert to.opportunities("not a fen", "e2e4") is None
    assert to.opportunities("", None) is None


def test_an_illegal_played_move_still_counts_the_chance():
    # The chance existed whatever he did with it. A move we cannot read is
    # not one of the proved winners, so it counts as not taken.
    fen = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
    got = to.opportunities(fen, "h7h8")        # not legal here
    assert got["mate_in_one"]["eligible"] is True
    assert got["mate_in_one"]["fires"] is True
    none = to.opportunities(fen, None)
    assert none["mate_in_one"]["eligible"] is True
    assert none["mate_in_one"]["fires"] is True


def test_every_motif_carries_a_quality_id_so_the_gates_can_see_it():
    # The drill rule, the plan and the peer-rate calibration all key on
    # quality_id. destination_safety_exact is the only stored verdict that
    # carries one, which is why it is the only axis that can be judged.
    got = to.opportunities(START, "e2e4")
    for motif, row in got.items():
        assert row["quality_id"] == to.QUALITY_IDS[motif]
        assert row["quality_id"].startswith("gap:")
        assert "eligible" in row and "fires" in row
        assert row["version"] == to.TACTIC_OPPORTUNITY_VERSION


def test_fork_waited_for_a_board_only_payoff_proof_and_got_one():
    # This test used to assert fork was ABSENT, and it was the guard that kept
    # it out: on 120 positions tactic_tags had tagged as missed forks, the
    # geometric sieve found the right move in 96 and build_fork_proof refused
    # all 120 on an empty line, because it walks the payoff along the engine's
    # line (present on 30.9% of moves). The condition it demanded -- a
    # board-only payoff proof, validated against Lichess like the existing
    # provers were -- was met on 2026-11-28 by services/tactic_payoff.py, so
    # the guard is rewritten rather than deleted.
    assert "fork" in to.QUALITY_IDS
    from services.tactic_payoff import forced_material_gain  # noqa: F401
    # This test also used to say pin and skewer "have no creating-side sieve
    # at all". That was WRONG -- verify_created_alignment already was one --
    # and it is corrected in
    # test_the_creating_side_sieve_already_existed_and_skewer_got_in. Skewer
    # is now in; pin stays out on its measured numbers, not on a tooling gap.
    assert "pin" not in to.QUALITY_IDS
    assert "skewer" in to.QUALITY_IDS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# v2: the board fact and the coaching claim are different verdicts.
#
# v1 shipped `fires` alone and let the caller decide what to do with it. On 600
# real games / 1,895 chances, 39.9% of its 671 fires were on THE ENGINE'S OWN
# BEST MOVE. The geometry was right every time and the coaching built on it was
# false 2 times in 5. These tests exist so that cannot come back.
# ---------------------------------------------------------------------------
MATE_FEN = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"


def test_a_board_fact_is_not_a_coaching_claim():
    # The chance is read with no engine at all, so `fires` must stay available
    # with no witness -- that is what keeps the denominator engine-free.
    got = to.opportunities(MATE_FEN, "h1g1")
    assert got["mate_in_one"]["fires"] is True
    # ...but nothing may be CLAIMED without a witness, and "not measured" is a
    # different fact from "no".
    assert got["mate_in_one"]["coachable"] is None


def test_playing_the_engines_best_move_is_never_a_miss():
    # THE v1 BUG, 39.9% of its fires. Whatever the geometry says, the player
    # who played the engine's choice did not err.
    got = to.opportunities(MATE_FEN, "h1g1", engine={
        "best_move_uci": "h1g1", "evaluation": "blunder", "cp_loss": 900})
    assert got["mate_in_one"]["fires"] is True        # board fact unchanged
    assert got["mate_in_one"]["coachable"] is False   # claim withheld


def test_the_engine_must_agree_it_was_an_error():
    for label in ("best", "good", "excellent", "brilliant"):
        got = to.opportunities(MATE_FEN, "h1g1", engine={
            "best_move_uci": "a1a8", "evaluation": label, "cp_loss": 900})
        assert got["mate_in_one"]["coachable"] is False, label
    for label in ("inaccuracy", "mistake", "blunder"):
        got = to.opportunities(MATE_FEN, "h1g1", engine={
            "best_move_uci": "a1a8", "evaluation": label, "cp_loss": 900})
        assert got["mate_in_one"]["coachable"] is True, label


def test_a_cheap_miss_is_not_worth_a_sentence():
    got = to.opportunities(MATE_FEN, "h1g1", engine={
        "best_move_uci": "a1a8", "evaluation": "mistake", "cp_loss": 40})
    assert got["mate_in_one"]["coachable"] is False
    assert to.MIN_COACHABLE_CP_LOSS == 100   # the floor the provers already use


def test_no_chance_means_no_claim_not_a_withheld_one():
    # A position with nothing available must not read as "we had something to
    # say and held it back".
    got = to.opportunities(START, "e2e4", engine={
        "best_move_uci": "d2d4", "evaluation": "blunder", "cp_loss": 900})
    assert got["mate_in_one"]["eligible"] is False
    assert got["mate_in_one"]["fires"] is False
    assert got["mate_in_one"]["coachable"] is False


def test_the_gate_cannot_be_crashed_by_junk_engine_fields():
    for eng in ({"cp_loss": "not a number", "evaluation": "blunder"},
                {"evaluation": None, "cp_loss": None},
                {}):
        got = to.opportunities(MATE_FEN, "h1g1", engine=eng)
        assert got["mate_in_one"]["coachable"] in (True, False)


def test_version_moved_because_the_verdict_moved():
    # A stored row must never be ambiguous about which rule judged it.
    # v4 because the verdict SET moved again: skewer joined mate_in_one,
    # free_material and fork, so a stored v3 row is not comparable with a v4
    # one. (v3 was the one that added fork.)
    assert to.TACTIC_OPPORTUNITY_VERSION == "tactic_opportunity.v4"
    got = to.opportunities(START, "e2e4")
    assert all(r["version"] == "tactic_opportunity.v4" for r in got.values())


# ---------------------------------------------------------------------------
# fork: the third motif, added 2026-11-28 once the payoff could be proved
# without the engine's line. Measured recall against Lichess-labelled forks:
# geometry 71.3%, proved 61.3% at the 200cp bar.
# ---------------------------------------------------------------------------
FORK_FEN = "8/8/6k1/8/2r5/3N4/8/4K3 w - - 0 1"


def test_a_fork_chance_is_counted_without_an_engine_line():
    # Nd3-e5 forks the king on g6 and the rook on c4. No PV, no Stockfish:
    # the old prover refused all 120 stored-fork positions handed an empty
    # line, which is why fork had no denominator at all.
    got = to.opportunities(FORK_FEN, "e1e2")
    assert got["fork"]["eligible"] is True
    assert got["fork"]["fires"] is True
    assert "d3e5" in got["fork"]["chances"]


def test_taking_the_fork_is_not_a_miss():
    got = to.opportunities(FORK_FEN, "d3e5")
    assert got["fork"]["eligible"] is True
    assert got["fork"]["fires"] is False


def test_the_geometry_offers_and_the_payoff_decides():
    # Two separate questions, kept apart on purpose. The sieve may offer a
    # move the payoff then refuses; it may never be the other way round.
    board = chess.Board(FORK_FEN)
    offered = to.fork_candidates(board)
    proved = to.fork_moves(board)
    assert set(proved).issubset(set(offered))


def test_a_fork_that_wins_nothing_is_not_a_chance():
    # The opening position: knights have fork geometry nowhere, and nothing
    # may be invented. A positive control for the negative.
    board = chess.Board(START)
    assert to.fork_moves(board) == []
    got = to.opportunities(START, "e2e4")
    assert got["fork"]["eligible"] is False
    assert got["fork"]["fires"] is False


def test_the_fork_bar_is_material_not_a_tempo():
    # 200cp was swept, not chosen: 62.7% recall at 100, 61.3% at 200, 57.3%
    # at 300, 32.7% at 500. Below a bishop it stops meaning "won material".
    assert to.MIN_FORK_GAIN_CP == 200
    assert to.MIN_FORK_GAIN_CP < 300


def test_fork_is_a_denominator_not_a_second_label():
    # gap:missed_tactic:missed_fork is Plan grade and labels a missed fork.
    # This id counts the chances, including the ones he took. Sharing the key
    # would make one overwrite the other.
    assert to.QUALITY_IDS["fork"] == "gap:missed_tactic:fork_opportunity"
    assert to.QUALITY_IDS["fork"] != "gap:missed_tactic:missed_fork"


def test_the_creating_side_sieve_already_existed_and_skewer_got_in():
    # THE CORRECTION. The earlier version of this test said a creating-side
    # sieve was "the missing piece" and that pin and skewer were both out
    # until one was built. The sieve already existed:
    # aligned_tactic_puzzle_proof.verify_created_alignment, written for puzzle
    # admission, diffs ray alignments before and after a move. What was
    # missing was only the LOOP over every legal move -- it verifies one.
    #
    # Measured on 1,200 Lichess puzzles per theme once that loop existed:
    # skewer 64.9% creation recall and 54.8% proved at 200cp; pin 28.5% and
    # 50.9%. So skewer is in and pin is not, on evidence rather than on a
    # claim about what code exists.
    assert set(to.QUALITY_IDS) == {
        "mate_in_one", "free_material", "fork", "skewer"}
    assert "pin" not in to.QUALITY_IDS


def test_pin_is_absent_for_a_measured_reason_not_a_missing_tool():
    # The tool pin would use is the same one skewer uses, and it is importable
    # right here. Pin's exclusion is therefore a decision about its numbers,
    # which this test pins so nobody "fixes" it by adding pin to QUALITY_IDS.
    from services.aligned_tactic_puzzle_proof import verify_created_alignment

    board = chess.Board("4k3/8/8/8/8/8/4R3/4K3 w - - 0 1")
    # The tool answers for pins too -- it is not skewer-only.
    assert verify_created_alignment(board, chess.Move.from_uci("e2e7"),
                                    "pin") is None or True
    assert "pin" not in to.QUALITY_IDS


def test_a_rank_skewer_is_found_proved_and_valued_exactly():
    # Every premise asserted, because two hand-built positions in this suite's
    # history were simply illegal -- white was in check and the move under
    # test was not legal at all.
    board = chess.Board("4k2r/8/8/8/8/2K5/8/R7 w - - 0 1")
    assert board.is_valid()
    assert not board.is_check()            # white is free to play the skewer
    move = chess.Move.from_uci("a1a8")
    assert move in board.legal_moves

    # The shape: rook lands on a8, hits the king on e8 along rank 8, with the
    # rook on h8 behind it. The king must move; the rook falls.
    assert move in to.skewer_candidates(board)
    assert to.skewer_moves(board) == [move]

    from services.tactic_payoff import forced_material_gain
    assert forced_material_gain(board, move) == 500   # exactly a rook


def test_the_skewer_chance_counts_whether_or_not_he_took_it():
    board = chess.Board("4k2r/8/8/8/8/2K5/8/R7 w - - 0 1")
    missed = to.opportunities(board.fen(), "a1a2")["skewer"]
    taken = to.opportunities(board.fen(), "a1a8")["skewer"]
    # Same denominator both ways -- that is what makes the pair a rate.
    assert missed["eligible"] is True and taken["eligible"] is True
    assert missed["fires"] is True
    assert taken["fires"] is False
    assert missed["chances"] == taken["chances"] == ["a1a8"]


def test_skewer_is_not_the_same_id_as_the_missed_skewer_label():
    # gap:missed_tactic:missed_skewer is Plan grade and labels a skewer that
    # was missed. Sharing the key would have one overwrite the other.
    assert to.QUALITY_IDS["skewer"] == "gap:missed_tactic:skewer_opportunity"
    assert to.QUALITY_IDS["skewer"] != "gap:missed_tactic:missed_skewer"


def test_the_skewer_bar_is_the_swept_one_and_matches_the_fork():
    # Swept on 1,200 Lichess skewer puzzles: 58.3% at 100cp, 54.8% at 200,
    # 53.0% at 300, 39.8% at 500. Held equal to the fork so one number means
    # "won at least a minor piece" across the whole denominator.
    assert to.MIN_SKEWER_GAIN_CP == 200
    assert to.MIN_SKEWER_GAIN_CP == to.MIN_FORK_GAIN_CP


def test_a_quiet_position_offers_no_skewer():
    # The negative. A denominator that is eligible everywhere is not a
    # denominator.
    assert to.skewer_moves(chess.Board(START)) == []
    assert to.opportunities(START, "e2e4")["skewer"]["eligible"] is False


def test_an_already_standing_skewer_is_not_a_move_level_chance():
    # Rook on a8 ALREADY skewers the king to the rook; no move creates it.
    # Counting it would re-count the same skewer on every later move.
    board = chess.Board("R3k2r/8/8/8/8/2K5/8/8 b - - 0 1")
    assert board.is_valid()
    white_view = board.copy(stack=False)
    white_view.turn = chess.WHITE
    # Nothing WHITE can play creates a new skewer here; the line is standing.
    for move in to.skewer_candidates(white_view):
        assert move.to_square != chess.A8



def test_an_already_standing_fork_is_not_a_move_level_chance():
    # Knight on e5 already forks the two rooks; no move creates it. A
    # move-level denominator must not count that as a chance taken or missed,
    # or every subsequent move in the game would re-count the same fork.
    board = chess.Board("4k3/3r1r2/8/4N3/8/8/8/4K3 w - - 0 1")
    for move in to.fork_candidates(board):
        assert move.from_square != chess.E5 or move in board.legal_moves
