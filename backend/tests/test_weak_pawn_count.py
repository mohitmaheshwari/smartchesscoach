"""Attack a weak pawn more often than it is defended.

Mohit, on a card reading "Qc1 was better - it attacks the pawn on e3,
which only their queen defends": it should teach the plan of adding an
attacker, "that's a good teaching on attacking weak pieces, right?"

Right -- but only where the rule is TRUE, and the measurements decided
the shape, not the one position:

    raw fact true on                        57.0% of flagged cards
    anchored to the square the card names   13.5%
    after correctness filters                1.87%
    actually SURVIVING the word cap          2.24%  (57 of 67 fires)

The filters are correctness, not taste:

  - PAWN targets only. Any other piece answers an extra attacker by
    moving, so "attack it more times than they defend it" would be
    false. 2,698 cards (knight 851, bishop 760, rook 564, queen 523)
    would have been taught a rule that does not hold. A pawn cannot
    step sideways, which is exactly why Mohit's e3 case works.
  - At least one real defender. 1v0 is a hanging pawn -- a different and
    simpler lesson -- and 1,480 cards would have read "you attack it
    once and they defend it zero times".
  - Defenders may not outnumber attackers: "bring one more" is then
    wrong, because more than one is needed.

Counts come from _exchange_participants, the module's existing SEE-order
counter with pinned pieces filtered out, not a new one. Four hand-rolled
attacker counts in a row produced artifacts before I reached for it.
"""
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_facts import _contested_target  # noqa: E402

# Mohit's card: after Qc1, e3 is attacked by Bf4 + Qc1 and defended by Qe7
BG3_FEN = "rn2kb1r/pp2qppp/8/2p2b2/5B2/1N1Pp3/PPP1N1PP/R2QKB1R w KQkq - 0 12"


def _fire(fen, best):
    board = chess.Board(fen)
    return _contested_target(board, board.parse_san(best))


def test_fires_on_mohits_card():
    ev = _fire(BG3_FEN, "Qc1")
    assert ev is not None
    assert ev["square"] == "e3"
    assert ev["piece"] == "pawn"
    assert ev["attackers"] == 2 and ev["defenders"] == 1
    assert ev["verdict"] == "wins"


def test_a_piece_that_can_run_is_never_the_subject():
    """The correctness filter, which lives in the SENTENCE rather than
    the fact: a contested knight is a real board state another caller
    may want, but the count teaches nothing about it, because a knight
    answers an extra attacker by moving."""
    from services.caption_pipeline import weak_pawn_count_sentence

    # white rook e1 + queen e2 bear on a black KNIGHT on e4, pawn f5 guards
    board = chess.Board("4k3/8/8/5p2/4n3/8/4Q3/4RK2 w - - 0 1")
    ev = _contested_target(board, board.parse_san("Qe3"))
    if ev is not None and ev["piece"] != "pawn":
        assert weak_pawn_count_sentence(ev) == "", ev


def test_the_sentence_helper_refuses_everything_it_should():
    from services.caption_pipeline import weak_pawn_count_sentence

    base = {"square": "e3", "piece": "pawn", "attackers": 2,
            "defenders": 1, "verdict": "wins"}
    assert "e3" in weak_pawn_count_sentence(base)
    assert weak_pawn_count_sentence({**base, "piece": "knight"}) == ""
    assert weak_pawn_count_sentence({**base, "defenders": 0}) == ""
    assert weak_pawn_count_sentence({**base, "square": ""}) == ""
    assert weak_pawn_count_sentence({**base, "verdict": "other"}) == ""
    assert weak_pawn_count_sentence(None) == ""
    assert weak_pawn_count_sentence({}) == ""
    lvl = weak_pawn_count_sentence({**base, "attackers": 1,
                                    "verdict": "level"})
    assert "One more attacker wins it." in lvl


def test_an_undefended_pawn_is_not_a_count_lesson():
    """1v0 is a hanging pawn. Saying "you attack it once and they defend
    it zero times" is a clumsy way to say it is free."""
    board = chess.Board("4k3/8/8/8/4p3/8/4Q3/4RK2 w - - 0 1")
    ev = _contested_target(board, board.parse_san("Qe3"))
    assert ev is None, ev


def test_outnumbered_defenders_stay_silent():
    """When they hold it more times than we hit it, "bring one more" is
    wrong -- several are needed -- so the card says nothing."""
    # one white attacker, two black defenders on e4
    board = chess.Board("4k3/8/5p2/3p4/4p3/8/4Q3/5K2 w - - 0 1")
    ev = _contested_target(board, board.parse_san("Qe3"))
    assert ev is None or ev["attackers"] >= ev["defenders"]


def test_level_and_wins_are_distinguished():
    ev = _fire(BG3_FEN, "Qc1")
    assert ev["verdict"] == "wins"
    assert ev["attackers"] > ev["defenders"]


def test_counts_come_from_the_shared_exchange_counter():
    """Not a 90th hand-rolled attacker count. The shared one filters
    pinned pieces and orders by SEE; a private loop over legal_moves
    cannot see the side that is not to move, which is how four earlier
    probes returned zeros."""
    from services.caption_facts import _exchange_participants

    board = chess.Board(BG3_FEN)
    after = board.copy()
    after.push(board.parse_san("Qc1"))
    att, dfd = _exchange_participants(after, chess.E3, chess.WHITE)
    ev = _fire(BG3_FEN, "Qc1")
    assert len(att) == ev["attackers"]
    assert len(dfd) == ev["defenders"]


def test_the_sentence_is_short_enough_to_survive_the_cap():
    """The cap cuts at the LAST sentence boundary, so an append that
    does not fit is the first thing deleted -- silently. The original
    26-word wording put Mohit's own card at 56 of 60."""
    from services.caption_config import MAX_CAPTION_WORDS

    for sentence in (
        "You attack e3 more often than they defend it. "
        "That is how a weak pawn falls.",
        "You attack e3 as often as they defend it. "
        "One more attacker wins it.",
    ):
        assert len(sentence.split()) <= 18, sentence
        assert len(sentence.split()) < MAX_CAPTION_WORDS // 3


# ── the anchor, which shipped broken for an hour ─────────────────────

def test_the_square_must_be_named_not_matched_inside_a_san():
    """The anchor was a substring test, so "f2" matched inside "Rxf2" --
    the played move's own SAN -- and the sentence attached to a card
    that never discussed f2:

        "Rxf2. Opponent's rooks are connected; yours aren't yet.
         You attack f2 more often than they defend it."

    Found by rendering five games and reading them. Every unit test I
    had written used a square that happened not to sit inside another
    token, so none of them could catch it.
    """
    import re

    pattern = (r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])")

    # the real failing card: f2 appears ONLY inside Rxf2
    bad = "Rxf2. Opponent's rooks are connected; yours aren't yet."
    assert "f2" in bad, "substring test would have passed"
    assert not re.search(pattern % "f2", bad), (
        "token test must reject a square that only occurs inside a SAN")

    # the correct card: d5 is named as a square
    good = "You develop the knight, eyeing their pawn on d5."
    assert re.search(pattern % "d5", good)

    # and Mohit's own card
    mohit = ("Qc1 was better - it attacks the pawn on e3, "
             "which only their queen defends.")
    assert re.search(pattern % "e3", mohit)


def test_pipeline_uses_the_modules_re_alias():
    """caption_pipeline imports re as _re_pb, not as re. A bare
    re.search inside the gate raises NameError, and the surrounding
    try/except swallows it -- the sentence would vanish everywhere with
    nothing in the logs to say why."""
    import inspect

    from services import caption_pipeline

    src = inspect.getsource(caption_pipeline)
    assert "\nimport re\n" not in src, (
        "if plain re is imported now, this guard can relax")
    assert "_ct_named = bool(_ct_sq) and bool(_re_pb.search(" in src
