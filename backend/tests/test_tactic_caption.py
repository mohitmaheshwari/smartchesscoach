"""A proved tactic tag becomes the card's lead sentence and arrows.

Positions from Mohit's game 3c8d0751 (checked by hand 2026-11-13).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.move_observation_deriver import _tactic_tags_for  # noqa: E402
from services.tactic_caption import describe, pick_tag  # noqa: E402

KE7 = dict(fen_before="7k/6p1/3K4/3B3p/3n4/2q5/8/8 w - - 4 61", move="Ke7",
           best_move="Ke5", pv_after_best=["Qc5", "Kf4", "Qxd5"],
           pv_after_played=["Qc5+", "Kd7", "Qxd5+", "Kc8"], cp_loss=9115)
H4 = dict(fen_before="7k/4K1p1/8/3B3p/3n4/2q5/8/8 b - - 5 61", move="h4",
          best_move="Qc5+", pv_after_best=["Kd8", "Qxd5+", "Kc7", "Qc6+"],
          pv_after_played=["Bc4", "Qc5+"], cp_loss=178)


def _card(mv, user, story):
    t = pick_tag(_tactic_tags_for(mv), story)
    return describe(t, fen_before=mv["fen_before"], played_san=mv["move"],
                    mover_is_user=user)


def test_opponent_allowed_fork_names_your_answer_and_both_targets():
    text, arrows = _card(KE7, False, "punishment")
    assert text == ("Their Ke7 allows a fork: play Qc5+, because your queen on c5 "
                    "attacks their bishop on d5 and their king on e7 at once.")
    assert [(a["from"], a["to"]) for a in arrows] == [("c3", "c5"), ("c5", "d5"), ("c5", "e7")]


def test_your_missed_fork_names_the_better_move_and_both_targets():
    text, _ = _card(H4, True, "opportunity")
    assert text == ("You missed a fork: Qc5+ was better, because your queen on c5 "
                    "attacks their bishop on d5 and their king on e7 at once.")


def test_a_missed_tactic_is_drawn_only_while_it_is_still_on_the_shown_board():
    """h4 does not touch c3, c5, d5 or e7, and Qc5+ is still legal: drawn."""
    _, arrows = _card(H4, True, "opportunity")
    assert ("c3", "c5") in [(a["from"], a["to"]) for a in arrows]


def test_no_tag_means_no_sentence():
    """Negative control: 7.Nf3 carries no proved tactic."""
    mv = dict(fen_before="rn1qkb1r/pppnpppp/6b1/4P3/2BP4/2N5/PP3PPP/R1BQK1NR w KQkq - 0 7",
              move="Nf3", best_move="e6", pv_after_best=["fxe6", "Bxe6", "Nf6"], cp_loss=248)
    assert pick_tag(_tactic_tags_for(mv), "neither") is None


def test_a_tactic_later_in_the_line_never_leads_the_card():
    tags = [{"kind": "missed", "motif": "fork", "at_ply": 4, "move": "b4", "facts": {}}]
    assert pick_tag(tags, "opportunity") is None
