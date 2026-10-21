"""The sentence a player reads -- locked, not reviewed.

Mohit's rule is that a rendered string gets a test rather than my judgement,
because review passes and code ships. The bans here are his, collected:

  no digits, no percentages, ever                 (2026-09-25)
  short sentences, one idea each, common words    (the 600-1500 audience)
  no chess jargon; "material" is jargon even
  though it is the correct term -- say "something
  for free"                                       (he flagged that word)
  keep the universal-principle ending             (2026-10-xx)
  never restate the destination square            ("e4 puts your pawn on e4")
  no failure tally                                (never a scoreboard)

The word "only" is banned here too, for a reason this file's module docstring
records: five of the real cases lose two guards to one move, so "the only
thing guarding it" would be a false claim on them.

Every shape is rendered from a real position taken from the corpus, so these
are the strings that actually ship, not strings written for a test.
"""
import re
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.contrastive_reasoner import q_abandoned_own_defender  # noqa: E402
from services.self_removal_caption import (  # noqa: E402
    PRINCIPLE,
    render_self_removal_caption,
)

# Real cards, one per shape, each read off the board in the measurement run.
CARDS = {
    # e6 pawn guards d5, pushes to e5, d5 still has the f6 knight -> short of help
    "SHORT_QUIET": (
        "r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7",
        "e5", ["dxe5", "Nxe5", "Nxd5", "Nxf3+", "Bxf3", "O-O"]),
    # b2 pawn guards the c3 knight, pushes to b4, nothing left, Qxc3 quiet
    "NO_GUARD": (
        "r3k1nr/ppp2pp1/2np1qbp/2bQ4/2B1P3/P1N2N1P/1P3PP1/R1B1R1K1 w kq - 1 12",
        "b4", ["Qxc3", "Bd2", "Bxf2+", "Kxf2"]),
    # queen on e2 helps guard the e3 bishop; Qc4 leaves the f-pawn, Rxe3+ check
    "SHORT_CHECK": (
        "rn3k2/ppp1r2p/6p1/2P5/6bq/2P1B2N/PP2QPPP/RN2KB1R w KQ - 3 13",
        "Qc4", ["Rxe3+", "Kd2", "Re7", "Qf4+"]),
}

JARGON = [
    "material", "centipawn", "cp", "tempo", "prophylaxis", "zugzwang",
    "initiative", "compensation", "fianchetto", "zwischenzug", "en prise",
    "overloaded", "undermining", "deflection", "interference",
]


def render(fen, played, line, mover_is_user=True):
    board = chess.Board(fen)
    after = board.copy()
    after.push(board.parse_san(played))
    ctx = {"before": board, "after": after, "played_san": played,
           "best_san": "", "pv_best": [], "pv_played": list(line)}
    answer = q_abandoned_own_defender(ctx)
    assert answer is not None, f"the question must fire on {played}"
    return render_self_removal_caption(
        board, answer, line_san=line, mover_is_user=mover_is_user)


@pytest.fixture(scope="module")
def rendered():
    out = {}
    for shape, (fen, played, line) in CARDS.items():
        card = render(fen, played, line)
        assert card is not None, f"{shape} must render"
        out[shape] = card
    return out


class TestEveryShapeIsReachable:
    def test_each_card_renders_the_shape_it_was_chosen_for(self, rendered):
        for shape, card in rendered.items():
            assert card["shape"] == shape, (
                f"{shape} card rendered as {card['shape']}: {card['caption']}")

    def test_every_shape_has_a_principle(self):
        for shape in ("NO_GUARD", "SHORT_QUIET", "SHORT_CHECK"):
            assert shape in PRINCIPLE


class TestNoDigitEverReachesThePlayer:
    def test_no_digits_outside_square_names(self, rendered):
        """Square names carry a digit by nature. Everything else must not."""
        for shape, card in rendered.items():
            stripped = re.sub(r"\b[a-h][1-8]\b", "", card["caption"])
            assert not re.search(r"\d", stripped), (
                f"{shape} has a number: {card['caption']}")

    def test_no_percent_sign(self, rendered):
        for card in rendered.values():
            assert "%" not in card["caption"]

    def test_no_counting_words(self, rendered):
        """A count turns coaching into a report. The shapes exist so the card
        never has to say how many guards there were.

        "once" is not on this list: "Once you pushed it" is "as soon as", not
        a tally. The first version of this test banned it and failed a card
        that was perfectly fine.
        """
        banned = (" two ", " three ", " twice ", " second ", " both ")
        for shape, card in rendered.items():
            low = f" {card['caption'].lower()} "
            for word in banned:
                assert word not in low, f"{shape} counts: {card['caption']}"


class TestItNeverClaimsALoneGuard:
    def test_the_word_only_is_never_used(self, rendered):
        """Five real cases lose two guards to one move. "Only" would be false
        on them, so it is false everywhere."""
        for shape, card in rendered.items():
            assert "only" not in card["caption"].lower(), (
                f"{shape}: {card['caption']}")

    def test_the_short_of_help_shapes_do_not_say_nothing_guards_it(self, rendered):
        for shape in ("SHORT_QUIET", "SHORT_CHECK"):
            cap = rendered[shape]["caption"].lower()
            assert "nothing was guarding" not in cap, rendered[shape]["caption"]

    def test_the_no_guard_shape_does_say_so(self, rendered):
        assert "nothing was guarding" in rendered["NO_GUARD"]["caption"]


class TestItReadsLikeEasyEnglish:
    def test_sentences_stay_short(self, rendered):
        for shape, card in rendered.items():
            for sentence in re.split(r"(?<=[.!?])\s+", card["caption"]):
                if not sentence.strip():
                    continue
                n = len(sentence.split())
                assert n <= 16, f"{shape} sentence of {n} words: {sentence}"

    def test_words_stay_short(self, rendered):
        for shape, card in rendered.items():
            for word in re.findall(r"[A-Za-z]+", card["caption"]):
                assert len(word) <= 10, f"{shape} long word {word!r}"

    def test_under_the_caption_word_cap(self, rendered):
        for shape, card in rendered.items():
            assert card["words"] <= 60, f"{shape} is {card['words']} words"

    def test_no_jargon(self, rendered):
        for shape, card in rendered.items():
            low = card["caption"].lower()
            for term in JARGON:
                assert not re.search(rf"\b{re.escape(term)}\b", low), (
                    f"{shape} uses {term!r}: {card['caption']}")

    def test_it_ends_on_the_principle(self, rendered):
        for shape, card in rendered.items():
            assert card["caption"].rstrip().endswith(PRINCIPLE[shape])


class TestItExplainsRatherThanNarrates:
    def test_it_never_shrugs(self, rendered):
        """The exact sentence Mohit sent back, and its family."""
        shrugs = ("cost you something", "gave a lot away",
                  "compare it with the engine")
        for shape, card in rendered.items():
            low = card["caption"].lower()
            for s in shrugs:
                assert s not in low, f"{shape} shrugs: {card['caption']}"

    def test_it_names_a_guard_and_a_thing_guarded(self, rendered):
        for shape, card in rendered.items():
            assert "guard" in card["caption"].lower(), card["caption"]
            assert card["guard"] in card["caption"]
            assert card["lost"] in card["caption"]

    def test_it_never_restates_the_destination_square(self, rendered):
        """"e4 puts your pawn on e4". The card names where the guard came FROM
        and what it was holding, never where it went."""
        for shape, (fen, played, _line) in CARDS.items():
            board = chess.Board(fen)
            dest = chess.square_name(board.parse_san(played).to_square)
            cap = rendered[shape]["caption"]
            # the destination may coincide with the guarded square; only a
            # bare extra mention is the bug
            if dest != rendered[shape].get("square"):
                assert cap.count(dest) <= 1, f"{shape} repeats {dest}: {cap}"


class TestItWorksForBothSides:
    def test_an_opponent_card_flips_the_possessives(self):
        fen, played, line = CARDS["NO_GUARD"]
        ours = render(fen, played, line, mover_is_user=True)
        theirs = render(fen, played, line, mover_is_user=False)
        assert ours["caption"] != theirs["caption"]
        assert theirs["caption"].startswith("Their")
        assert "your" in theirs["caption"]

    def test_the_principle_is_the_same_for_both(self):
        fen, played, line = CARDS["NO_GUARD"]
        ours = render(fen, played, line, mover_is_user=True)
        theirs = render(fen, played, line, mover_is_user=False)
        assert ours["shape"] == theirs["shape"]
