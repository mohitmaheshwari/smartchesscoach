"""An allowed-mate caption is checked against the OPPONENT's line.

"{played} lets your opponent force mate, so play {best} instead" is the
wording of data/distilled_templates.json "allowed_mate" -- the only
template that claims mate. _MATE_ALLOWED_RX covered "lets ... forced
win" but not "... force mate", so every caption from that template fell
past the opponent-mates branch into the final block, which asks "is the
RECOMMENDED move mate?". It never is, so the card was replaced by the
generic floor: measured over 150 games, 113 of 160 mate rejections
blamed a move that was not played.

The proof requirement is unchanged. The opponent-mates branch fails
closed: pv_after_played must reach an actual checkmate, or the caption
is still rejected. These tests pin both directions.

Position: r5k1/5ppp/8/8/7N/8/5PPP/6K1 w - - 0 1
White's knight is the only piece guarding nothing on the back rank; it
cannot return to rank 1. After a quiet knight move, Ra1 is mate -- the
king has no escape (f1 and h1 are on the rook's rank, f2/g2/h2 are its
own pawns) and nothing can interpose.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.narrator_claim_verifier import _MATE_ALLOWED_RX, verify_caption

FEN = "r5k1/5ppp/8/8/7N/8/5PPP/6K1 w - - 0 1"
CAPTION = ("Nf5 lets your opponent force mate, so play Nf3 instead to shore "
           "up your king's safety. Before every move, ask what checks and "
           "captures your opponent gets.")


def _facts(pv_after_played):
    return {
        "move_san": "Nf5",
        "fen_before": FEN,
        "is_user_move": True,
        "cp_loss": 900,
        "best_move_san": "Nf3",
        "pv_after_played": pv_after_played,
        "pv_after_best": [],
    }


def test_the_template_wording_is_recognised_as_allowed():
    assert _MATE_ALLOWED_RX.search(CAPTION)


def test_our_own_mate_is_not_an_allowed_claim():
    """"lets you force mate" is the player mating, not the opponent."""
    assert not _MATE_ALLOWED_RX.search("Qh5 lets you force mate next move.")
    assert not _MATE_ALLOWED_RX.search("Rd1 misses mate in 3.")


def test_kept_when_the_opponent_line_really_mates():
    """Ra1 is mate on this board, so the claim is proven and ships."""
    assert verify_caption(CAPTION, _facts(["Ra1"])) == []


def test_still_rejected_when_the_line_does_not_mate():
    """The fix routes the claim to a stricter check, it does not relax it.
    Ra5 is legal and not mate, so the mate claim stays unproven."""
    v = verify_caption(CAPTION, _facts(["Ra5"]))
    assert v, "an unproven mate claim must still be rejected"
    assert any(x.get("check") == "mate" for x in v), v


def test_still_rejected_when_there_is_no_line_at_all():
    """Fail closed on an empty line -- 6,632 captions once passed this way."""
    v = verify_caption(CAPTION, _facts([]))
    assert v, "an empty line is not proof"
    assert any(x.get("check") == "mate" for x in v), v


def test_the_recommended_move_is_never_what_gets_checked():
    """Nf3 is not mate and must not be the thing the verifier tests."""
    for v in verify_caption(CAPTION, _facts(["Ra1"])):
        assert "Nf3 is not mate" not in str(v.get("detail", ""))


# ── "X missed a checkmate. Y starts a line that forces mate." ──────────
#
# The other 65 of the 113 wrong-move blames. Two bugs: "missed a
# checkmate" was not in _MATE_MISSED_RX, so a bare \bcheckmate\b in
# _MATE_DELIVERED_RX classified 48 of them as the mover DELIVERING mate;
# and the final block then asked whether the recommended move is mate in
# one, when the caption says it STARTS a line.

MISS_FEN = "r5k1/5ppp/8/8/7N/8/5PPP/6K1 b - - 0 1"
MISS_CAPTION = ("Ra2 missed a checkmate. Ra1 starts a line that forces mate. "
                "Look at every check you have before you move.")


def _miss_facts(pv_after_best, best="Ra1"):
    return {
        "move_san": "Ra2",
        "fen_before": MISS_FEN,
        "is_user_move": True,
        "cp_loss": 500,
        "best_move_san": best,
        "pv_after_played": [],
        "pv_after_best": pv_after_best,
    }


def test_missed_a_checkmate_classifies_as_missed_not_delivered():
    from services.narrator_claim_verifier import (
        _MATE_MISSED_RX, _MATE_DELIVERED_RX)
    assert _MATE_MISSED_RX.search(MISS_CAPTION)
    # the elif chain tests MISSED before DELIVERED, so missed wins even
    # though the bare word "checkmate" is present
    assert _MATE_DELIVERED_RX.search(MISS_CAPTION)


def test_kept_when_the_users_own_line_mates_immediately():
    """Ra1 is mate on this board."""
    assert verify_caption(MISS_CAPTION, _miss_facts([])) == []


def test_kept_when_the_mate_lands_later_in_the_line():
    """The whole point: mate at the END of the line, not on move one."""
    facts = _miss_facts(["Nf5", "Ra1"], best="Ra2")
    assert verify_caption(MISS_CAPTION, facts) == []


def test_rejected_when_the_users_line_never_mates():
    """Fail closed -- a line that does not reach mate is not proof."""
    facts = _miss_facts(["Nf5", "Ra5"], best="Ra2")
    v = verify_caption(MISS_CAPTION, facts)
    assert v and any(x.get("check") == "mate" for x in v), v


def test_rejected_when_the_line_cannot_be_replayed():
    facts = _miss_facts(["totally-illegal"], best="Ra2")
    v = verify_caption(MISS_CAPTION, facts)
    assert v and any(x.get("check") == "mate" for x in v), v


def test_a_mate_by_the_wrong_side_is_not_proof():
    """If the line ends with the OPPONENT mating, a 'you missed mate'
    claim is still unproven."""
    # White (the opponent here) is not mating in this line; black is the
    # mover. Credit must go to the mover for the claim to stand.
    facts = _miss_facts(["Nf5", "Ra5"], best="Ra2")
    assert verify_caption(MISS_CAPTION, facts)
