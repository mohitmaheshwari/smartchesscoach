"""The word cap, and the fact that it now announces itself.

Measured 2026-09-13 by re-rendering 150 games with the cap lifted (8,494
captions): p50 12 words, p90 22, p99 40, p99.5 44, max 94. Only 0.45% ran
past the old 45-word cap, but they were concentrated in R12_blunder -- the
rule that explains why a move was a mistake, and the one gaining why-clauses.
60 sits above the real shoulder without letting a caption become an essay.
"""
from __future__ import annotations

import logging

from services.caption_config import MAX_CAPTION_WORDS
from services.caption_renderer import _enforce_word_cap


def test_cap_is_above_the_measured_distribution():
    # p99.5 of natural caption length is 44 words; the cap must clear it.
    assert MAX_CAPTION_WORDS >= 45


def test_a_caption_inside_the_cap_is_untouched():
    text = " ".join(["word"] * (MAX_CAPTION_WORDS - 5)) + "."
    assert _enforce_word_cap(text, "R12_blunder") == text


def test_an_over_long_caption_is_cut_at_a_sentence_boundary():
    long_text = (" ".join(["alpha"] * (MAX_CAPTION_WORDS - 10)) + ". "
                 + " ".join(["beta"] * 20) + ".")
    out = _enforce_word_cap(long_text, "R12_blunder")
    assert len(out.split()) < len(long_text.split())
    assert out.endswith(".")
    assert "beta" not in out


def test_the_cut_is_announced(caplog):
    """A dropped coaching sentence must never be silent again.

    Cutting at a sentence boundary leaves no ellipsis, so the loss is
    invisible in the output -- this is how a "Play b4 ..." recommendation
    disappeared from an opponent-mistake caption with nothing to show for it.
    """
    long_text = (" ".join(["alpha"] * (MAX_CAPTION_WORDS - 10)) + ". "
                 + " ".join(["beta"] * 20) + ".")
    with caplog.at_level(logging.WARNING):
        _enforce_word_cap(long_text, "R12_blunder")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "caption truncated" in joined
    assert "R12_blunder" in joined
    assert "beta" in joined          # the dropped text is shown, not just counted
