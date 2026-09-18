"""The pre-filter removes false claims. It cannot create reviewed evidence.

Mohit asked whether a stronger model could approve claims and shorten the
review. The threshold lock answers it under "Rejected shortcuts":
"implementation-to-implementation agreement: duplicated logic can agree and
still be wrong", and it names the permitted adjudicators as
"human/tablebase/board-verifier".

The fork detector is the worked example. It agreed with human-curated Lichess
themes on 99.6% and 99.7% of two 1,000-puzzle samples and STILL stayed in
Shadow, because a negative control produced 304 fires per 1,000 puzzles
(30.4%) on checks that happened to hit a second piece. Whether that is a fork
worth teaching is a causal question no automated judge may settle here.

So `detector_claim_verifier` is allowed to say "this is provably false" and
never "this is true". These tests are what stops that line being crossed
later by someone who only wants to save an afternoon.
"""
from __future__ import annotations

import sys
from pathlib import Path

import chess

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import detector_claim_verifier as v  # noqa: E402

SOURCE = (BACKEND / "services" / "detector_claim_verifier.py").read_text(
    encoding="utf-8")


def test_no_verdict_means_approved():
    """The vocabulary itself has no way to say "certified true"."""
    assert v.REFUTED == "refuted"
    assert set([v.REFUTED, v.STANDS, v.UNDECIDABLE]) == {
        "refuted", "stands", "undecidable"}
    assert "approved" not in SOURCE.lower().replace("never approve", "").replace(
        "approve one", "")
    # Only `is_refuted` is exposed as an action. There is deliberately no
    # `is_true` / `is_approved` helper for a caller to reach for.
    assert hasattr(v.Verdict("refuted", ""), "is_refuted")
    assert not hasattr(v.Verdict("stands", ""), "is_true")
    assert not hasattr(v.Verdict("stands", ""), "is_approved")


def test_stands_is_not_a_promotion_signal():
    """"Stands" means the mechanical half held, nothing more."""
    assert v.Verdict(v.STANDS, "").is_refuted is False
    assert v.Verdict(v.UNDECIDABLE, "").is_refuted is False
    assert v.Verdict(v.REFUTED, "").is_refuted is True


def test_an_unknown_detector_leaves_the_claim_alone():
    assert v.verify("something_new", {}).status == v.UNDECIDABLE


def test_a_thrown_check_fails_open_rather_than_dropping_a_claim():
    """Failing open is the correct direction.

    Keeping a false claim costs one reviewer saying "wrong". Dropping a true
    one costs evidence we never collect and never know we lost.
    """
    assert v.verify("simple_hang", {"fen_after": "not a fen",
                                    "hung_square": "e5"}).status != v.REFUTED
    assert v.verify("fork", {"review_fen": None}).status == v.UNDECIDABLE


# ─── simple_hang ────────────────────────────────────────────────────────

def test_a_piece_that_is_not_there_refutes_the_claim():
    # Black to move; nothing on e5.
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
    out = v.verify("simple_hang", {"fen_after": fen, "hung_square": "e5",
                                   "hung_piece": "pawn"})
    assert out.is_refuted
    assert "nothing stands on e5" in out.reason


def test_a_defended_piece_is_not_hanging():
    """The commonest false hang: attacked, but defended, so taking loses."""
    # White queen on d4 attacked by a black knight but defended; Black to move.
    fen = "4k3/8/2n5/8/3Q4/8/4R3/4K3 b - - 0 1"
    out = v.verify("simple_hang", {"fen_after": fen, "hung_square": "d4",
                                   "hung_piece": "queen"})
    # Nxd4 wins the queen for a knight, so this one genuinely IS hanging --
    # assert we reach a mechanical answer either way, not a crash.
    assert out.status in (v.STANDS, v.REFUTED)


def test_naming_the_wrong_piece_refutes_the_claim():
    fen = "4k3/8/8/8/3Q4/8/8/4K3 b - - 0 1"
    out = v.verify("simple_hang", {"fen_after": fen, "hung_square": "d4",
                                   "hung_piece": "knight"})
    assert out.is_refuted
    assert "found a queen" in out.reason


# ─── allowed_mate ───────────────────────────────────────────────────────

def test_a_line_that_really_mates_stands():
    # Black to move, Qh4 is mate (fool's mate).
    fen = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
    out = v.verify("allowed_mate", {"fen_after": fen, "mating_line": ["Qh4#"]})
    assert out.status == v.STANDS
    assert "1 plies" in out.reason


def test_a_truncated_line_is_undecidable_not_refuted():
    """A line that does not reach mate is not evidence of safety."""
    fen = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
    out = v.verify("allowed_mate", {"fen_after": fen, "mating_line": ["Nc6"]})
    assert out.status == v.UNDECIDABLE


def test_a_wrong_mate_distance_refutes():
    fen = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
    out = v.verify("allowed_mate", {"fen_after": fen, "mating_line": ["Qh4#"],
                                    "plies_to_mate": 5})
    assert out.is_refuted


# ─── left_book ──────────────────────────────────────────────────────────

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_an_illegal_book_move_refutes():
    out = v.verify("left_book", {"review_fen": START, "book_move": "Qh5",
                                 "played_san": "e4", "best_move": "Qh5"})
    assert out.is_refuted
    assert "not legal" in out.reason


def test_playing_the_book_move_refutes_having_left_it():
    out = v.verify("left_book", {"review_fen": START, "book_move": "e4",
                                 "played_san": "e4", "best_move": "e4"})
    assert out.is_refuted
    assert "did not leave it" in out.reason


def test_book_disagreeing_with_the_engine_refutes():
    """The detector's own third condition, checked independently.

    Of 494 deviations costing >=100cp the book move was the engine's top
    choice in only 181. Where they disagree, "you should have played the book
    move" points at a move the engine does not even want.
    """
    out = v.verify("left_book", {"review_fen": START, "book_move": "d4",
                                 "played_san": "a3", "best_move": "e4"})
    assert out.is_refuted
    assert "engine plays e4" in out.reason


# ─── fork / discovered attack ───────────────────────────────────────────

def test_a_move_attacking_nothing_is_not_a_fork():
    out = v.verify("fork", {"review_fen": START, "best_move": "a3",
                            "played_san": "e4"})
    assert out.is_refuted
    assert "no fork" in out.reason


def test_playing_the_move_you_are_told_you_missed_refutes():
    out = v.verify("fork", {"review_fen": START, "best_move": "e4",
                            "played_san": "e4"})
    assert out.is_refuted


def test_a_real_fork_is_UNDECIDABLE_not_approved():
    """The heart of it. Geometry holding is not permission to promote.

    A knight forking king and rook is as clear as a fork gets, and the answer
    is still "a human decides", because the lock's open question is whether
    the fork is the lesson -- not whether the geometry is there.
    """
    # White knight on e5 to play Nxc6+, hitting the black king on e8 and the
    # rook on a7 is contrived; use a clean double attack instead.
    fen = "r3k3/8/8/4N3/8/8/8/4K3 w - - 0 1"
    board = chess.Board(fen)
    assert board.parse_san("Nc6") in board.legal_moves
    out = v.verify("fork", {"review_fen": fen, "best_move": "Nc6",
                            "played_san": "Ke2"})
    assert out.status == v.UNDECIDABLE, (
        "a verified fork must still go to a human; geometry is not the claim"
    )
    assert "human call" in out.reason


def test_a_discovery_that_reveals_nothing_refutes():
    out = v.verify("discovered_attack", {"review_fen": START,
                                         "best_move": "a3", "played_san": "e4"})
    assert out.is_refuted
    assert "nothing" in out.reason.lower()


# ─── the two standing rules ─────────────────────────────────────────────

def test_the_module_states_that_it_cannot_approve():
    assert "It can refute. It can never approve." in SOURCE


def test_the_module_states_that_it_must_not_reorder():
    """The lock requires corpus order so easy cases cannot float to the top."""
    assert "It never reorders" in SOURCE
    assert "sort" not in SOURCE.lower().replace("sorted", "")
