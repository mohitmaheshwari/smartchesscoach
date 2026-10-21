"""A player who is about to be mated must be told so.

Measured 2026-10-21 over 400 games: 56 user cards let the opponent mate inside
the stored line and **41 of them (73.2%) never said the word**. Opponent cards
were fine (13 of 14 said it), so this is not the mate detector failing -- the
detector fires, `R01_mate` is selected, and then it renders a variant that
contains no facts at all.

The worst one found, verified on the board:

    r1bqk2r/pppp1pp1/2n5/4P2p/2BP1Qn1/5N2/PP3PPP/RN3RK1 b kq - 1 11
    Black played Nb4. Qxf7# is mate in ONE.

    the card said: "Those pieces did not arrive by accident -- every move your
                    opponent makes is part of a plan. Find theirs before you
                    follow your own."

The lesson is a good lesson. It is just missing the fact. `R01_mate.json`
selects the nine `mate_lesson` variants AHEAD of `user_allows_p1`, which is
the one that says "allows mate next move" -- so the teaching replaces the
warning instead of following it.

These tests assert the fact is present, the lesson is kept, and the mate is
counted correctly, so a future reorder cannot silently drop it again.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CAPTIONS = Path(__file__).resolve().parents[1] / "data" / "captions"
R01 = json.loads((CAPTIONS / "R01_mate.json").read_text(encoding="utf-8"))

# Every variant that fires when the USER let a mate in. Each one is a card
# shown to a player who is losing on the spot.
LESSON_VARIANTS = [
    c["variant"] for c in R01["select_variant"]
    if c.get("when", {}).get("mate_transition") == "allowed"
    and c.get("when", {}).get("mover_is_user") is True
    and "mate_lesson" in c.get("when", {})
]


class TestEveryAllowsMateVariantStatesTheMate:
    def test_the_lesson_variants_exist(self):
        assert LESSON_VARIANTS, "selection shape changed; this test is stale"

    @pytest.mark.parametrize("name", LESSON_VARIANTS)
    def test_it_names_the_move_and_the_mate(self, name):
        text = R01["variants"][name]
        assert "{played_san}" in text, (
            f"{name} never names the move: {text!r}")
        assert "{allows_mate_phrase}" in text, (
            f"{name} never tells the player a mate is coming: {text!r}")

    @pytest.mark.parametrize("name", LESSON_VARIANTS)
    def test_it_still_teaches_its_lesson(self, name):
        """The fix adds a fact; it must not delete the teaching."""
        text = R01["variants"][name]
        after = text.split("}", 2)[-1]
        assert len(after.split()) >= 8, (
            f"{name} lost its lesson when the fact was added: {text!r}")


class TestThePhraseCountsTheMateCorrectly:
    def test_mate_in_one_reads_as_next_move(self):
        from services.caption_rules import _allows_mate_phrase
        assert _allows_mate_phrase(1) == "allows mate next move"

    def test_a_longer_mate_is_counted(self):
        from services.caption_rules import _allows_mate_phrase
        assert _allows_mate_phrase(3) == "allows mate in 3"

    def test_an_unknown_count_still_warns(self):
        """No ply is a reason to be vaguer, never a reason to stay quiet."""
        from services.caption_rules import _allows_mate_phrase
        phrase = _allows_mate_phrase(None)
        assert "mate" in phrase
        assert "{" not in phrase

    def test_a_nonsense_count_does_not_produce_mate_in_zero(self):
        from services.caption_rules import _allows_mate_phrase
        for bad in (0, -2, "x"):
            phrase = _allows_mate_phrase(bad)
            assert "mate" in phrase, bad
            assert " 0" not in phrase and "-" not in phrase, (bad, phrase)


class TestTheFactReachesTheRenderer:
    def test_r01_render_supplies_the_phrase(self):
        """Built where the other mate facts are built, so one writer owns it."""
        import inspect

        from services.caption_rules import _r01_render
        src = inspect.getsource(_r01_render)
        assert "allows_mate_phrase" in src, (
            "the variants reference a fact nobody builds, which renders as a "
            "literal brace on a card about checkmate")
