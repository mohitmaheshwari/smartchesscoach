"""The Socratic surface has to actually ask something.

R18_socratic_user_mistake is the rule that is supposed to put a question to
the player instead of handing them the answer -- the whole "teach how to
think, not tell the best move" direction runs through it. Every one of its 19
variants shipped `question` and `hint` as empty strings from the day the rule
was written, and R17_coach_move shipped `hint_for_user` empty on all 18 of its
variants.

Nothing failed. The renderer reads the key, gets "", and stores "". Measured
on production 2026-09-11, across 500 stored game reviews (29,302 move cards):

    socratic_coaching fired on   2,115 cards -- 2,115 had a narrative,
                                                    0 had a question
    coach_move_coaching fired on 14,635 cards --     0 had a hint

So on 16,750 stored coaching cards the field meant to carry the question was
empty every single time, and the frontend had already been changed (2026-08-03)
to stop gating on it so the card would render at all.

These tests hold the floor: every variant of both rules renders non-empty
prose in every field, and a question ends in a question mark. The mechanical
checks (jargon, snake_case leaks, a pawn called "the piece") live in
scripts/pwc_coaching_lint.py, which now has an R18 pass for the same reason.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_pipeline import populate_coach_extras, populate_socratic_extras

CAPTIONS = BACKEND / "data" / "captions"


def _variants(filename):
    cfg = json.loads((CAPTIONS / filename).read_text(encoding="utf-8"))
    return cfg["variants"]


R18_VARIANTS = _variants("R18_socratic_user_mistake.json")
R17_VARIANTS = _variants("R17_coach_move.json")

# Facts rich enough that no variant renders a placeholder as an empty string.
# Selection is forced per-variant by the caller below, so these only have to
# cover every placeholder any variant might reference.
BASE_FACTS = {
    "socratic_is_active": True,
    "played_san": "Nf3",
    "best_move_san": "Bb5",
    "socratic_hanging_piece": "rook",
    "socratic_hanging_square": "h1",
    "socratic_opponent_threat_text": "Qxh1",
    "socratic_problem_facts": ["the rook on h1 has no defender"],
    "socratic_recovery_facts": ["Rf1 keeps the rook"],
    "socratic_phase": "middlegame",
    "socratic_user_rating": 1200,
}


@pytest.mark.parametrize("name", sorted(R18_VARIANTS))
def test_every_user_mistake_variant_asks_the_player_something(name):
    body = R18_VARIANTS[name]
    for field in ("narrative", "plan", "question", "hint"):
        assert str(body.get(field) or "").strip(), (
            f"R18 variant {name!r} ships an empty {field}. A card that names "
            "the problem and asks nothing has stopped coaching halfway."
        )
    question = body["question"].strip()
    assert question.endswith("?"), (
        f"R18 variant {name!r} calls this a question but it does not ask "
        f"anything: {question!r}"
    )


@pytest.mark.parametrize("name", sorted(R17_VARIANTS))
def test_every_coach_move_variant_hands_the_player_something_to_do(name):
    body = R17_VARIANTS[name]
    assert str(body.get("hint_for_user") or "").strip(), (
        f"R17 variant {name!r} ships an empty hint_for_user. The coach has "
        "just explained its own move and given the player nothing to do."
    )


@pytest.mark.parametrize("severity", ["mistake", "blunder"])
def test_the_rendered_payload_carries_the_question_not_just_the_template(severity):
    # The template being authored is necessary but not sufficient: the value
    # has to survive selection and formatting to reach SocraticExtras, which
    # is what game_decryption_v5_service stores and the review card reads.
    facts = dict(BASE_FACTS, socratic_severity=severity,
                 socratic_fundamental_violated="hanging_pieces")
    extras = populate_socratic_extras(facts)
    assert extras is not None
    assert extras.narrative.strip()
    assert extras.question.strip().endswith("?")
    assert extras.hint.strip()
    # No placeholder may survive into user-facing text.
    for field in (extras.narrative, extras.plan, extras.question, extras.hint):
        assert "{" not in field and "}" not in field, field


def test_a_rendered_coach_move_carries_its_hint():
    extras = populate_coach_extras({
        "coach_move_is_active": True,
        "played_san": "Nf3",
        "moving_piece_type": "knight",
        "target_square": "f3",
        "phase": "opening",
    })
    assert extras is not None
    assert extras.hint_for_user.strip()
    assert "{" not in extras.hint_for_user
