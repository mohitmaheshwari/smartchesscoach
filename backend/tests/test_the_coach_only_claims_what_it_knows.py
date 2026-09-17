"""The coach may describe a pattern. It may not invent a history.

Mohit, 2026-09-17, on the Home page belief paragraph: *"there is a difference
between knowing you and write, and write some shit on the face of knowing
you."* He was right, and the measurement backed him:

  - The belief is chosen by exactly two inputs, the topic and a 3-way style
    label. With one topic cleared to coach from, 125 users were served by
    three paragraphs -- 76 of them sharing one, word for word.
  - Every one of the 21 paragraphs opened "At first, I thought X. I don't
    think that anymore." There was no first opinion. It is a fixed string,
    and it manufactures an observation history and a revised judgement that
    never happened.
  - Most then absolved the player -- "You are not careless", "You are not
    blind to it" -- for a diagnosis nothing had verified.
  - The page closed "I want to see if my theory is right." Nothing reads the
    belief back.

A hedged statement about a pattern is honest: it says this is what usually
sits behind this mistake. A claim about what I used to think about *you* is
not, and no amount of good writing makes it so. This file pins the
difference.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.home_coach_conversation import (  # noqa: E402
    _THEORY_BY_BAND,
    _THEORY_OF_WHY,
)

ALL_TEXTS = [
    (f"{topic}/{variant}", text)
    for topic, variants in _THEORY_OF_WHY.items()
    for variant, text in variants.items()
] + [
    (f"{topic}/band:{band}", text)
    for topic, bands in _THEORY_BY_BAND.items()
    for band, text in bands.items()
]

# Each of these asserts something about the player that nothing measured.
FABRICATED_HISTORY = (
    "at first, i thought",
    "i don't think that anymore",
    "i used to think",
    "i no longer think",
)

UNEARNED_ABSOLUTION = (
    "you are not careless",
    "you are not blind",
    "this is not a mistake in your skill",
    "that is not a knowledge problem",
    "you are not lazy",
)


def test_there_is_text_to_check():
    assert len(ALL_TEXTS) >= 20


def test_no_paragraph_claims_a_history_we_never_had():
    offenders = [
        name for name, text in ALL_TEXTS
        for phrase in FABRICATED_HISTORY
        if phrase in text.lower()
    ]
    assert not offenders, (
        "these claim a previous opinion the coach never formed: "
        f"{sorted(set(offenders))}"
    )


def test_no_paragraph_absolves_the_player_of_an_unverified_diagnosis():
    offenders = [
        name for name, text in ALL_TEXTS
        for phrase in UNEARNED_ABSOLUTION
        if phrase in text.lower()
    ]
    assert not offenders, sorted(set(offenders))


def test_every_paragraph_hedges():
    """It describes what usually sits behind a mistake, not a fact about them.

    The bank is hand-authored and shared by many players at once, so each
    line has to read as a tendency rather than a finding about the reader.
    """
    hedges = ("usually", "often", "tends to", "can ", "rarely", "almost never")
    missing = [
        name for name, text in ALL_TEXTS
        if not any(h in text.lower() for h in hedges)
    ]
    assert not missing, f"unhedged claims about the player: {missing}"


def _code_only(path) -> str:
    """Strip comments, so a check reads the code and not the note about it."""
    import io

    kept = [
        line for line in io.open(path, encoding="utf-8").read().splitlines()
        if not line.lstrip().startswith("#")
    ]
    return chr(10).join(kept)


def test_nothing_promises_a_verdict_on_the_belief():
    """The closing line said the theory would be checked. Nothing checks it."""
    src = _code_only(BACKEND / "services" / "home_coach_conversation.py")
    assert "see if my theory is right" not in src


def test_strength_overrides_style_where_the_tag_changes_meaning():
    """`piece_safety` at 1600+ is not the beginner mistake of the same name.

    The picker's own impact table weights it 1.00 for a beginner and 0.30 for
    an expert, with the comment that at that strength it means calculation
    errors rather than dropped pieces. Six of 52 active focuses sit at
    advanced or expert, so the text has to say the right thing to them.
    """
    bands = _THEORY_BY_BAND["piece_safety"]
    assert set(bands) == {"advanced", "expert"}
    for band, text in bands.items():
        assert "calcul" in text.lower(), band
        # And it must not repeat the beginner framing.
        assert "hanging for nothing" in text.lower() or "one-move" in text.lower()


def test_the_band_override_is_actually_consulted():
    import io

    src = io.open(
        BACKEND / "services" / "home_coach_conversation.py", encoding="utf-8"
    ).read()
    assert "_THEORY_BY_BAND.get(topic_key)" in src
    assert 'focus.get("rating_band")' in src
    order_style = src.index("theory = variants.get(style_variant)")
    order_band = src.index("if band_text:", order_style)
    assert order_style < order_band, "the band must be applied after the style"


def test_the_band_reaches_the_reader_that_needs_it():
    """It lives on the focus document; the bundle has to pass it through."""
    import io

    src = io.open(
        BACKEND / "services" / "focus_bridge.py", encoding="utf-8"
    ).read()
    assert '"rating_band": focus.get("rating_band")' in src


def test_no_paragraph_counts_at_the_player():
    """"You have done this 150 times" is arithmetic, not coaching.

    Mohit has raised this twice. Keeping it out of the belief bank is cheap.
    """
    for name, text in ALL_TEXTS:
        assert not re.search(r"\d", text), f"{name} contains a number"
