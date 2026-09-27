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
    def test_prefers_the_purpose_built_instruction(self):
        row = _card(caption_explanation={
            "transferable_instruction":
                "Next time, before you commit, look for a move that attacks "
                "the knight on f3.",
        })
        assert _reason_for_moment(row) == "Attacks the knight on f3."

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

    def test_a_caption_naming_a_DIFFERENT_move_is_content(self):
        # "Bf6 is playable" on a Bb2 card is not restating the row -- it is
        # telling the player about another move, so it survives.
        assert _reason_for_moment(
            _card(move_san="Bb2", caption="Bf6 is playable.")
        ) == "Bf6 is playable."

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
