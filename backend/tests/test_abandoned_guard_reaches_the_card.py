"""The clause has to reach the screen, and this is the test that says so.

Three separate wires had to be connected before any of this showed up on a
card, and each one failed silently:

  1 R12's lead slot and failure slot are rival template families and no
    variant carries both, so a failure clause took the sentence and the lead
    had nowhere to go
  2 Mohit's own card does not render through R12 at all -- with its real move
    history it goes R_TIER2_center -> R_PROMOTED_basic_mistake, which had no
    cause slot
  3 `promotion_facts` in apply_promotion_ladder_dispatch is a WHITELIST, so
    the promoted variant's predicate could not be true no matter what
    extract_facts produced

Every one of those left the facts correct, the tests green, and the player
reading the same sentence as before. So these tests assert the final string
from `build_move_teaching_decision`, not the facts dict -- a facts-level test
proves the fact and nothing about the card.

`user_color` is derived from the position here. Hardcoding it to "white" in a
black-side game makes the claim verifier reject every "your <piece>" claim and
sends the card to R_VERIFIER_RECOVERY, which is a measurement artefact that
cost an hour of blaming the wrong stage.
"""
import re
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# Mohit's card, 2026-10-21. Renders through R_PROMOTED_basic_mistake because
# of the move history, which is the whole reason wires 2 and 3 were needed.
MOHIT = dict(
    fen="r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7",
    played="e5", best="a6", cp_loss=100,
    pv_played=["dxe5", "Nxe5", "Nxd5", "Nxf3+", "Bxf3", "O-O"],
    pv_best=["b4", "O-O", "Na4", "Ne4", "Nd2"],
    history=["e4", "e6", "d4", "d5", "Nc3", "Nf6", "Nf3", "Bd6", "a3", "Nc6",
             "Be2", "Bf5"],
    move_number=7,
)

# The R12 side is measured in the corpus diff rather than pinned to one FEN
# here: its clause is the same string, asserted by
# TestBothRuleFilesCarryTheSameSentence, and the card that needed the harder
# wiring is Mohit's, which goes through R_PROMOTED_basic_mistake.


def decide(fen, played, best, cp_loss, pv_played, pv_best, history,
           move_number, mover_is_user=True):
    board = chess.Board(fen)
    mover_is_white = board.turn == chess.WHITE
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=fen, played_san=played, mover_is_user=mover_is_user,
            mover_is_white=mover_is_white,
            # the user IS the mover on a user card; see the module docstring
            user_color=("white" if mover_is_white == mover_is_user else "black"),
            full_move_number=move_number, move_history_san=list(history),
            best_move_san=best, cp_loss=cp_loss,
            pv_after_played=list(pv_played), pv_after_best=list(pv_best)),
        CrossMoveState())


@pytest.fixture(scope="module")
def mohit_card():
    return decide(MOHIT["fen"], MOHIT["played"], MOHIT["best"],
                  MOHIT["cp_loss"], MOHIT["pv_played"], MOHIT["pv_best"],
                  MOHIT["history"], MOHIT["move_number"])


class TestMohitsCardSaysWhyNow:
    """The card he sent back, which read "This move cost you something.
    Compare it with the engine's line below." and then, once the crash was
    fixed, "e5 is a mistake. a6 was better. Opening moves earn their keep by
    controlling the center, developing a piece, or improving king safety." --
    a true sentence about nothing in this position."""

    def test_the_facts_are_there(self, mohit_card):
        f = mohit_card.debug_facts or {}
        assert f.get("abandoned_guard_shape") == "SHORT_QUIET"
        assert f.get("abandoned_lost_piece") == "pawn"
        assert f.get("abandoned_lost_square") == "d5"
        assert f.get("abandoned_taken_san") == "Nxd5"
        assert f.get("abandoned_guard_verb") == "pushed"

    def test_the_card_names_the_cause(self, mohit_card):
        cap = mohit_card.text.caption
        assert "was guarding" in cap, cap
        assert "d5" in cap, cap

    def test_the_card_names_what_collects_it(self, mohit_card):
        assert "Nxd5" in mohit_card.text.caption

    def test_it_no_longer_shrugs(self, mohit_card):
        cap = mohit_card.text.caption.lower()
        for shrug in ("cost you something", "gave a lot away",
                      "compare it with the engine",
                      "opening moves earn their keep"):
            assert shrug not in cap, mohit_card.text.caption

    def test_it_still_names_the_better_move(self, mohit_card):
        assert "a6" in mohit_card.text.caption


class TestTheWordingObeysTheVoiceRules:
    """The JSON templates are not covered by the caption-voice test, which only
    sees `self_removal_caption.py`. Locked here so the strings in
    R12_blunder.json and R_PROMOTED_basic_mistake.json cannot drift."""

    JARGON = ["material", "centipawn", "tempo", "initiative", "zugzwang",
              "prophylaxis", "compensation", "en prise", "overloaded"]

    def test_no_digits_outside_squares_and_san(self, mohit_card):
        cap = mohit_card.text.caption
        # strip square names and SAN tokens, which must carry digits
        stripped = re.sub(r"\b[KQRBNa-h][a-h]?x?[a-h][1-8](\+|#)?\b", "", cap)
        stripped = re.sub(r"\b[a-h][1-8]\b", "", stripped)
        stripped = re.sub(r"\bO-O(-O)?\b", "", stripped)
        assert not re.search(r"\d", stripped), f"number in: {cap}"

    def test_no_jargon(self, mohit_card):
        low = mohit_card.text.caption.lower()
        for term in self.JARGON:
            assert not re.search(rf"\b{re.escape(term)}\b", low), (
                f"{term!r} in: {mohit_card.text.caption}")

    def test_no_counting_words(self, mohit_card):
        low = f" {mohit_card.text.caption.lower()} "
        for word in (" two ", " three ", " twice ", " only "):
            assert word not in low, f"{word!r} in: {mohit_card.text.caption}"

    def test_within_the_word_cap(self, mohit_card):
        assert len(mohit_card.text.caption.split()) <= 60


class TestItStaysQuietWhereItShould:
    def test_a_good_opening_move_gets_no_cause_clause(self):
        d = decide(chess.STARTING_FEN, "e4", "d4", 0, ["e5", "Nf3", "Nc6"],
                   ["d4", "d5", "c4"], [], 1)
        f = d.debug_facts or {}
        assert not f.get("abandoned_guard_shape")
        assert "was guarding" not in (d.text.caption or "")

    def test_the_promoted_variant_cannot_fire_without_the_whitelist(self):
        """Guards wire 3 directly. `promotion_facts` is an explicit dict; if
        these keys stop being passed through, the promoted variant silently
        becomes unreachable again and every other test here still passes
        because R12 would cover its own cards."""
        import inspect

        from services.caption_pipeline import apply_promotion_ladder_dispatch
        src = inspect.getsource(apply_promotion_ladder_dispatch)
        for key in ("abandoned_guard_shape", "abandoned_guard_verb",
                    "abandoned_guard_piece", "abandoned_lost_piece",
                    "abandoned_lost_square", "abandoned_taken_san"):
            assert f'"{key}"' in src, (
                f"{key} is no longer passed to the promotion ladder, so "
                "R_PROMOTED_basic_mistake's with_abandoned_guard is dead")


class TestBothRuleFilesCarryTheSameSentence:
    """A player who meets this lesson on two different cards must read the
    same words, even though the two rules are separate template files."""

    def test_the_two_variants_agree(self):
        import json
        from pathlib import Path as _P

        root = _P(__file__).resolve().parents[1] / "data" / "captions"
        r12 = json.loads((root / "R12_blunder.json").read_text(encoding="utf-8"))
        pro = json.loads(
            (root / "R_PROMOTED_basic_mistake.json").read_text(encoding="utf-8"))
        a = r12["variants"]["failure_abandoned_own_guard"]
        b = pro["variants"]["with_abandoned_guard"]
        core = ("the {abandoned_guard_piece} that was guarding your "
                "{abandoned_lost_piece} on {abandoned_lost_square}, and "
                "{abandoned_taken_san} wins it")
        assert core in a, a
        assert core in b, b
