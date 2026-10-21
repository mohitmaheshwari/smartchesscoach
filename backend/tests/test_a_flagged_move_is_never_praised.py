"""Never praise a move the engine flagged.

Mohit, on v226: "a calm move on a mistake, what the hell?" and, on a 952cp
blunder, "same caption on a fucking blunder". Both read:

    "A calm move that keeps their position solid."

v226 fixed the crash path that caused that for USER cards. It never reached
the opponent path, because the never-silence floor reads the wrong field:

    caption_fallback_tiers.py
      line 77  cp = int(facts.get("mover_cp_loss") or facts.get("cp_loss") or 0)
      line 88  cp = int(facts.get("cp_loss") or 0)          <-- tier23_caption

and fourteen lines above the second one, the same file says why that is wrong:

    # mover_cp_loss is the mover's OWN loss. facts["cp_loss"] is 0 on an
    # opponent card...

So every opponent card read cp = 0, sailed under `cp < _GOOD_CP`, and got
praised. Measured over 300 games at cp_loss >= 100: 88 of 312 opponent cards
(28.2%) were praised, against 26 of 1,519 user cards (1.7%).

The floor itself is right and stays. A quiet move really is fine below 50cp,
and a plain description beats silence. It just has to be told how bad the move
was by the field that knows.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_fallback_tiers import _GOOD_CP, tier23_caption  # noqa: E402

# Phrases, not words. "a more active TRY WAS AVAILABLE" is the honest branch
# for a costly move and must not be mistaken for praise -- my first version of
# this list flagged it and failed two tests for the wrong reason.
PRAISE_PHRASES = (
    "a calm move",
    "position solid",
    "on a strong central square",
    "to a more active spot",
    "keeping it safe",
    "belong on open files",
    "on the open file",
)

BASE = {
    "played_san": "Bg3",
    "moving_piece_type": "bishop",
    "best_move_san": "Bc3",
}


def facts(**over):
    f = dict(BASE)
    f.update(over)
    return f


def praised(text):
    low = (text or "").lower()
    return any(w in low for w in PRAISE_PHRASES)


class TestAnOpponentMistakeIsNotCalledSolid:
    """The live bug: cp_loss is 0 on an opponent card, so the floor saw a
    quiet move where the engine saw a mistake."""

    def test_a_flagged_opponent_move_is_not_praised(self):
        text, rule = tier23_caption(
            facts(mover_is_user=False, cp_loss=0, mover_cp_loss=100))
        assert not praised(text), f"{rule}: {text!r}"

    def test_a_flagged_opponent_blunder_is_not_praised(self):
        text, rule = tier23_caption(
            facts(mover_is_user=False, cp_loss=0, mover_cp_loss=952,
                  moving_piece_type="king"))
        assert not praised(text), f"{rule}: {text!r}"

    def test_the_same_holds_for_a_user_card(self):
        text, rule = tier23_caption(facts(mover_is_user=True, cp_loss=400))
        assert not praised(text), f"{rule}: {text!r}"


class TestTheFloorStillSpeaksWhenTheMoveIsFine:
    """Silence is worse than a plain description, so the floor must keep
    working on genuinely quiet moves. A fix that just muted it would pass the
    tests above and lose the feature."""

    def test_a_quiet_opponent_move_still_gets_a_caption(self):
        text, rule = tier23_caption(
            facts(mover_is_user=False, cp_loss=0, mover_cp_loss=10))
        assert text.strip(), rule

    def test_a_quiet_user_move_still_gets_a_caption(self):
        text, rule = tier23_caption(facts(mover_is_user=True, cp_loss=10))
        assert text.strip(), rule

    def test_praise_is_allowed_below_the_good_bar(self):
        """The point is not to ban the words; it is to ban them on a move the
        engine faulted."""
        text, _ = tier23_caption(
            facts(mover_is_user=False, cp_loss=0, mover_cp_loss=_GOOD_CP - 1))
        assert text.strip()


class TestTheBoundary:
    def test_exactly_at_the_bar_is_not_praised(self):
        text, rule = tier23_caption(
            facts(mover_is_user=False, cp_loss=0, mover_cp_loss=_GOOD_CP))
        assert not praised(text), f"{rule}: {text!r}"

    def test_a_missing_mover_loss_falls_back_to_cp_loss(self):
        """User cards carry the loss in cp_loss and must keep working."""
        text, rule = tier23_caption(facts(mover_is_user=True, cp_loss=300))
        assert not praised(text), f"{rule}: {text!r}"

    def test_both_fields_absent_is_treated_as_quiet(self):
        """No information is not evidence of a mistake; the floor may speak."""
        text, _ = tier23_caption(facts(mover_is_user=True))
        assert text.strip()
