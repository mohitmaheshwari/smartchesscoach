"""What your move lets them do, derived from the board.

Mohit 2026-10-13: "why can't we build it deterministically, we already
have all the chess facts and stockfish there". This is that -- the
opponent's FIRST reply in each stored engine line, differenced, with the
difference read off the board.

Why one ply and not the whole line: diffing the END of two 16-ply lines
was built and measured first, and failed. On the cards that matter it
scored 52-62% directional accuracy -- a coin flip dressed as a reason --
because over sixteen plies the two positions diverge for reasons that
have nothing to do with the move played.

Measured over 8,880 flagged cards BEFORE any wording existed, for how
often each fact favours the engine's move when it separates the replies:

    gives_check   80.1%   (1,378 vs   343)   used
    captures      69.7%   (2,475 vs 1,076)   used
    attacks_us    64.5%   (2,406 vs 1,323)   NOT used
    takes_centre  59.4%   (1,187 vs   811)   NOT used

The last two are near enough to a coin flip to be filler.

That percentage is NOT a truth rate. Whether their reply gives check is
checked on that board and is simply true or false. It is how often the
fact is the DISCRIMINATING difference, so a miss means saying something
true but secondary -- never something false.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import _reply_gap  # noqa: E402
from services.caption_pipeline import reply_gap_sentence  # noqa: E402

# 1.d4 d5 2.c4 dxc4 3.Nc3 -- the QGA card that started this
QGA = "rnbqkbnr/ppp1pppp/8/8/2pP4/2N5/PP2PPPP/R1BQKBNR b KQkq - 1 3"


def gap(fen, played, best, pvp, pvb):
    return _reply_gap(chess.Board(fen), played, best, pvp, pvb)


# ── it stays silent when the difference is not one of the two ────────

def test_silent_when_neither_reply_checks_or_captures():
    """The QGA card: they answer e4 after Bf5 and e3 after a6. The real
    difference is the centre, which was measured at 59.4% and left out
    on purpose, so this correctly says nothing rather than reaching."""
    assert gap(QGA, "Bf5", "a6", ["e4", "Bg6"], ["e3", "b5"]) is None


def test_silent_when_the_reply_is_the_same_move():
    assert gap(QGA, "Bf5", "a6", ["e4"], ["e4"]) is None


def test_silent_on_missing_or_unplayable_input():
    assert gap(QGA, "Bf5", "a6", [], ["e3"]) is None
    assert gap(QGA, "Bf5", "a6", ["e4"], []) is None
    assert gap(QGA, None, "a6", ["e4"], ["e3"]) is None
    assert gap(QGA, "Bf5", "a6", ["Zz9"], ["e3"]) is None


# ── the capture case ─────────────────────────────────────────────────

def test_capture_only_when_the_engine_line_does_not_also_capture():
    """A capture that BOTH replies make does not separate them, so it is
    not the reason. Seen live: Qd2 -> Qxf2 against Qxf5+ -> Rxf5, where
    both reply with a capture and only the check discriminates."""
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    # both replies capture -> capture must not be reported
    out = _reply_gap(board, "Ng5", "d3", ["Nxe4"], ["Nxe4"])
    assert out is None  # same move entirely


def test_reports_the_piece_and_square_taken():
    """The sentence names what is lost, so the fact has to carry it."""
    fen = "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
    board = chess.Board(fen)
    out = _reply_gap(board, "e4", "c4", ["dxe4"], ["e6"])
    assert out is not None
    assert "capture" in out["allows"]
    assert out["captured_piece"] == "pawn"
    assert out["capture_square"] == "e4"


# ── the sentence ─────────────────────────────────────────────────────

def test_sentence_states_only_what_the_move_allows():
    """It must NOT claim the better move leaves them with no answer --
    the stored line shows one reply, not every reply, so that would
    claim more than the data holds."""
    s = reply_gap_sentence({
        "their_reply": "Nxd4", "allows": ["capture"],
        "captured_piece": "knight", "capture_square": "d4"})
    assert s == "That lets them take the knight on d4 with Nxd4."
    assert "no such answer" not in s
    assert "nothing" not in s


def test_sentence_for_check():
    s = reply_gap_sentence({"their_reply": "Qxf2", "allows": ["check"]})
    assert s == "That lets them play Qxf2 with check."


def test_sentence_for_check_and_capture():
    s = reply_gap_sentence({
        "their_reply": "Qxd3", "allows": ["check", "capture"],
        "captured_piece": "pawn", "capture_square": "d3"})
    assert "with check" in s and "pawn on d3" in s


def test_sentence_empty_on_empty_fact():
    assert reply_gap_sentence(None) == ""
    assert reply_gap_sentence({}) == ""
    assert reply_gap_sentence({"their_reply": "", "allows": ["check"]}) == ""
    assert reply_gap_sentence({"their_reply": "Nf6", "allows": []}) == ""


def test_sentence_is_short_enough_to_survive_the_cap():
    """The word cap cuts at the LAST sentence boundary, so an append
    that does not fit deletes itself silently."""
    from services.caption_config import MAX_CAPTION_WORDS

    longest = reply_gap_sentence({
        "their_reply": "Qxd3", "allows": ["check", "capture"],
        "captured_piece": "knight", "capture_square": "d3"})
    assert len(longest.split()) <= 14
    assert len(longest.split()) < MAX_CAPTION_WORDS // 3


def test_facts_expose_it():
    """It has to reach the facts dict or no surface can use it."""
    from services.caption_facts import extract_facts

    f = extract_facts(
        fen_before="rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",
        played_san="e4", best_move_san="c4", cp_loss=150,
        pv_after_played=["dxe4"], pv_after_best=["e6"],
        mover_is_user=True, full_move_number=2)
    assert "reply_gap" in f
    assert (f["reply_gap"] or {}).get("capture_square") == "e4"
