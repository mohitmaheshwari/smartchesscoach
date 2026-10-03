"""'Where the game turned' has to mean it, and each row has to say something.

Mohit 2026-09-26, on a review showing thirteen rows of move + badge and
nothing else: "this looks very very bad."

Two faults. Every row's text was None, because _get_short_description reads
plan.concept_id / plan.current_problem and those were emptied by the
2026-05-11 "legacy prose fields retired" migration. And the list showed every
mistake and every opponent slip -- median SEVEN a game, 24 of 150 games at
fifteen or more -- a tally of failures beside a game the player often won.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.game_summary_service import (  # noqa: E402
    _is_bare_verdict,
    _reason_for_moment,
    _strip_instruction_preamble,
)


def _card(**kw):
    base = {"move_san": "Bb2", "severity": "mistake", "is_user_move": True}
    base.update(kw)
    return base


class TestTheRowSaysSomething:
    def test_the_best_move_reason_is_attributed_not_borrowed(self):
        """The defect Mohit reported on 2026-10-02.

        caption_pipeline builds that instruction as "Next time, before you
        commit, look for a move that {best_move_why}", so stripping the
        preamble leaves a property of the move NOT played. Printed bare beside
        the played move under a MISTAKE badge it read as a claim about it:

            7. Ne4  MISTAKE  Attacks the rook on a8.

        Ne4 does not attack a8. The fact is kept -- it is true -- but it is
        given its owner.
        """
        row = _card(best_move_san="Nf5", caption_explanation={
            "transferable_instruction":
                "Next time, before you commit, look for a move that attacks "
                "the knight on f3.",
        })
        out = _reason_for_moment(row)
        assert out == "Nf5 was stronger — it attacks the knight on f3."
        assert not out.startswith("Attacks")

    def test_falls_back_to_the_caption_when_there_is_no_instruction(self):
        row = _card(caption="Bb2 is a mistake. h4 was better — it attacks the "
                            "bishop on g3.")
        assert _reason_for_moment(row) == "h4 was better — it attacks the bishop on g3."

    def test_skips_the_verdict_sentence_the_badge_already_shows(self):
        # "Bb2 is a mistake" beside a MISTAKE badge on move Bb2 is three
        # repetitions of one fact. An earlier regex attempt returned exactly
        # this string unchanged.
        row = _card(caption="Bb2 is a mistake. h4 was better.")
        assert _reason_for_moment(row) == "h4 was better."

    def test_a_caption_that_is_only_a_verdict_returns_nothing(self):
        # Better an honest blank than a row of filler.
        assert _reason_for_moment(
            _card(move_san="Bf6", caption="Bf6 is playable.")
        ) is None

    def test_an_effect_attributed_to_another_move_is_dropped(self):
        """Live on 2026-10-02: row "38. d3+  THEIR SLIP" carried "Bc5 leaves
        the bishop on c5 hanging -- you can win it with bxc5", which is about
        Bc5. Nothing checked the borrowed sentence was about the row's move."""
        assert _reason_for_moment(_card(
            move_san="d3+",
            caption="d3+ is a mistake. Bc5 leaves the bishop on c5 hanging.",
        )) is None

    def test_but_recommending_another_move_is_the_whole_point(self):
        """"h4 was better." on a Bb2 row names another move and must survive --
        it recommends it rather than claiming it did something here."""
        assert _reason_for_moment(
            _card(move_san="Bb2", caption="Bb2 is a mistake. h4 was better.")
        ) == "h4 was better."

    def test_a_sentence_opening_with_a_pronoun_is_dropped(self):
        """"It wins the rook on a8." -- the "it" is the better move, named in a
        sentence the row does not show, so alone it reads as the played move."""
        assert _reason_for_moment(_card(
            move_san="Ne4", caption="Ne4 is a mistake. It wins the rook on a8.",
        )) is None

    def test_a_hedge_that_denies_the_badge_is_removed_not_the_sentence(self):
        """"Kf1 isn't a blunder, but bxc5 wins the bishop" under a BLUNDER
        badge. The hedge contradicts the badge; the clause after it is real."""
        out = _reason_for_moment(_card(
            move_san="Kf1", severity="blunder",
            caption="Kf1 isn't a blunder, but bxc5 wins the bishop on c5.",
        ))
        assert out == "bxc5 wins the bishop on c5."
        # bxc5 is a PAWN capture. Capitalising it would name a bishop move.
        assert "Bxc5" not in out

    def test_no_caption_and_no_instruction(self):
        assert _reason_for_moment(_card()) is None
        assert _reason_for_moment(_card(caption="")) is None


class TestThePreamble:
    def test_strips_the_known_template(self):
        assert _strip_instruction_preamble(
            "Next time, before you commit, look for a move that wins material."
        ) == "Wins material."

    def test_leaves_anything_else_alone(self):
        # If the template is ever reworded this must degrade to keeping the
        # sentence, not to mangling it.
        text = "Look at what is left holding the square after the trade."
        assert _strip_instruction_preamble(text) == text

    def test_an_empty_remainder_keeps_the_original(self):
        raw = "Next time, before you commit, look for a move that"
        assert _strip_instruction_preamble(raw) == raw


class TestBareVerdictDetection:
    def test_counts_words_rather_than_matching_a_phrasing(self):
        assert _is_bare_verdict("Bb2 is a mistake", "Bb2") is True
        assert _is_bare_verdict("Nxe5 is playable", "Nxe5") is True
        assert _is_bare_verdict("Opponent's Na4 is a serious mistake", "Na4") is True

    def test_anything_with_real_content_survives(self):
        assert _is_bare_verdict("h4 was better — it attacks the bishop", "Bb2") is False
        assert _is_bare_verdict("Wins material", "Qxf3") is False

    def test_is_not_confused_by_a_missing_move(self):
        assert _is_bare_verdict("is a mistake", None) is True
        assert _is_bare_verdict("forks the king and rook", None) is False


class TestNoMangledPatterns:
    """Every regex in the module must be a regex, not a control character.

    Six `\b` word boundaries in this module were once written as the literal
    backspace character U+0008 -- the patterns compiled, matched nothing, and
    two guards were silently dead while their tests still passed because the
    tests exercised the functions rather than the patterns. Cheap to assert,
    impossible to spot by reading.
    """

    def test_module_source_has_no_control_characters(self):
        import inspect
        import services.game_summary_service as mod
        src = inspect.getsource(mod)
        bad = sorted({ord(c) for c in src if ord(c) < 9 or ord(c) in (11, 12)})
        assert not bad, f"control characters in source: {[hex(b) for b in bad]}"

    def test_every_compiled_pattern_is_clean(self):
        import re as _re
        import services.game_summary_service as mod
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, _re.Pattern):
                bad = [c for c in obj.pattern if ord(c) < 9 or ord(c) in (11, 12)]
                assert not bad, f"{name} contains a control character"
