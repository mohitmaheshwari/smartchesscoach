"""An opponent's mistake must say WHY, not just that it happened.

Mohit, 2026-10-12, on game_8e1294767490 move 7 Bf5 (opponent, 320cp):

    "why is missing again for opponent, until player understands what
     the opponent mistake is why, he doesn't know chess better"

Traced on that card. The why was already computed and the layer could
not see the move was bad:

    stored opponent cp_loss   320
    facts['cp_loss']            0     <- what every mistake gate reads
    facts['opp_cp_loss']     None     <- never reached the facts dict
    facts['best_move_why']   'attacks the knight on b3'

extract_facts is handed inputs.cp_loss, which is 0 on an opponent card
because the opponent's loss travels in opp_cp_loss. So a 320cp blunder
fell through to the tier whose job is to DESCRIBE a move approvingly and
rendered "Your opponent develops the bishop, bringing a new piece into
the game." _better_suffix, the thing that attaches a why, opened with
`if not facts.get("mover_is_user"): return ""` -- the opponent side was
excluded twice over.

cp_loss itself is deliberately unchanged: 31 readers rely on it meaning
the user's loss. mover_cp_loss carries the mover's own loss beside it.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_fallback_tiers import _MISTAKE_CP, _better_suffix  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)

# the real stored position: Black to move, Bf5 played, c4 was the move
BF5_FEN = "rnbqkb1r/pp3ppp/8/2pp4/4p3/1NN5/PPPP1PPP/R1BQKB1R b KQkq - 1 7"
HIST = ["e4", "e5", "Nf3", "Nf6", "Nc3", "Nxe4", "Nxe4", "d5", "Nc3",
        "e4", "Nd4", "c5", "Nb3"]


def _opp_card(cp_loss=320, best="c4"):
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=BF5_FEN, played_san="Bf5",
            mover_is_user=False, mover_is_white=False, user_color="white",
            full_move_number=7, move_history_san=list(HIST),
            best_move_san=best, best_move_uci="c5c4",
            eval_before_cp=56, eval_after_cp=369,
            cp_loss=0, opp_cp_loss=cp_loss,
            pv_after_played=["d3", "exd3", "Bxd3", "Be6"],
            pv_after_best=["Qh5", "cxb3", "Qxd5", "bxc2"],
        ),
        CrossMoveState())


def _user_card(cp_loss=320):
    return build_move_teaching_decision(
        MoveInputs(
            fen_before=BF5_FEN, played_san="Bf5",
            mover_is_user=True, mover_is_white=False, user_color="black",
            full_move_number=7, move_history_san=list(HIST),
            best_move_san="c4", best_move_uci="c5c4",
            eval_before_cp=56, eval_after_cp=369,
            cp_loss=cp_loss, opp_cp_loss=0,
            pv_after_played=["d3", "exd3", "Bxd3", "Be6"],
            pv_after_best=["Qh5", "cxb3", "Qxd5", "bxc2"],
        ),
        CrossMoveState())


# ── the facts the layer was blind to ─────────────────────────────────

def test_the_movers_own_loss_reaches_the_facts_dict():
    """Without this every mistake gate reads 0 on an opponent card."""
    facts = _opp_card().debug_facts or {}
    assert facts.get("mover_cp_loss") == 320
    # cp_loss keeps its meaning: 31 readers depend on it
    assert facts.get("cp_loss") == 0


def test_user_side_mover_cp_loss_is_the_users_loss():
    facts = _user_card().debug_facts or {}
    assert facts.get("mover_cp_loss") == 320
    assert facts.get("cp_loss") == 320


def test_the_why_was_always_computed():
    """The point of the whole fix: nothing new is derived, a fact that
    already existed stops being thrown away."""
    facts = _opp_card().debug_facts or {}
    assert facts.get("best_move_why") == "attacks the knight on b3"


# ── the card itself ──────────────────────────────────────────────────

def test_opponent_card_states_the_why():
    d = _opp_card()
    caption = d.text.caption or ""
    assert "attacks the knight on b3" in caption, caption


def test_opponent_card_names_the_move_they_missed():
    caption = _opp_card().text.caption or ""
    assert "c4" in caption, caption


def test_opponent_card_does_not_address_the_reader_as_the_mover():
    """A card badged Opponent that says "c4 was better" tells the reader
    THEY should have played it. Same bug class as the hardcoded "You
    played Be7" on an opponent card, flagged live on eb189840 move 12."""
    caption = _opp_card().text.caption or ""
    assert "They missed c4" in caption, caption
    assert "c4 was better" not in caption, caption


def test_user_card_keeps_its_own_voice():
    """The opponent branch must not leak into user cards."""
    caption = _user_card().text.caption or ""
    assert "They missed" not in caption, caption
    assert "c4 was better" in caption, caption


# ── the gates still gate ─────────────────────────────────────────────

def test_a_small_opponent_loss_gets_no_better_move_sentence():
    """The say-better backstop's bar is 100cp, and it is the mover's own
    loss that must clear it."""
    caption = _opp_card(cp_loss=40).text.caption or ""
    assert "They missed c4" not in caption, caption


def test_better_suffix_reads_the_movers_own_loss():
    """_better_suffix owns the 25-120cp band. It used to bail on every
    opponent card before looking at anything else."""
    facts = {
        "best_move_san": "c4", "played_san": "Bf5",
        "best_move_why": "attacks the knight on b3",
        "mover_is_user": False, "cp_loss": 0, "mover_cp_loss": 60,
    }
    out = _better_suffix(facts)
    assert "attacks the knight on b3" in out, out
    assert "They had c4" in out, out


def test_better_suffix_still_bands_on_cp():
    base = {
        "best_move_san": "c4", "played_san": "Bf5",
        "best_move_why": "attacks the knight on b3",
        "mover_is_user": False, "cp_loss": 0,
    }
    assert _better_suffix({**base, "mover_cp_loss": 10}) == ""
    assert _better_suffix({**base, "mover_cp_loss": _MISTAKE_CP}) == ""
    assert _better_suffix({**base, "mover_cp_loss": 60}) != ""


def test_better_suffix_user_voice_unchanged():
    facts = {
        "best_move_san": "c4", "played_san": "Bf5",
        "best_move_why": "attacks the knight on b3",
        "mover_is_user": True, "cp_loss": 60, "mover_cp_loss": 60,
    }
    out = _better_suffix(facts)
    assert "Though c4 was a bit stronger" in out, out
    assert "They had" not in out, out


def test_no_why_means_no_invented_why():
    """A missing why must not become a fabricated one."""
    facts = {
        "best_move_san": "c4", "played_san": "Bf5",
        "best_move_why": "", "mover_is_user": False,
        "cp_loss": 0, "mover_cp_loss": 60,
    }
    assert _better_suffix(facts) == ""


def test_caption_stays_within_the_word_cap():
    from services.caption_config import MAX_CAPTION_WORDS

    caption = _opp_card().text.caption or ""
    assert len(caption.split()) <= MAX_CAPTION_WORDS, caption
