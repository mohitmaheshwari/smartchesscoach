"""Tactic tags: missed / found / allowed, proved on the board.

Scope: docs/observation_detectors_scope.md (signed 2026-11-13). Positions are
from Mohit's games, checked by hand on 2026-11-13.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tactic_tags import FOUND_MAX_CP_LOSS, tag_move  # noqa: E402
from services.move_observation_deriver import _tactic_tags_for  # noqa: E402

# 3c8d0751 61.Ke7: White's king walks into Qc5+, which hits the king and the
# bishop on d5 at once.
KE7_FEN = "7k/6p1/3K4/3B3p/3n4/2q5/8/8 w - - 4 61"
AFTER_KE7 = "7k/4K1p1/8/3B3p/3n4/2q5/8/8 b - - 5 61"


def _kinds(tags):
    return sorted((t["kind"], t["motif"], t["move"], t["at_ply"]) for t in tags)


def test_a_move_that_walks_into_a_fork_is_tagged_allowed():
    tags = tag_move(KE7_FEN, "Ke7", best="Ke5", pv_after_best=["Qc5", "Kf4", "Qxd5"],
                    pv_after_played=["Qc5+", "Kd7", "Qxd5+", "Kc8"], cp_loss=9115)
    assert ("allowed", "fork", "Qc5+", 0) in _kinds(tags)


def test_playing_the_fork_is_tagged_found():
    tags = tag_move(AFTER_KE7, "Qc5+", best="Qc5+",
                    pv_after_played=["Kd7", "Qxd5+", "Kc8"], cp_loss=0)
    assert ("found", "fork", "Qc5+", 0) in _kinds(tags)


def test_not_playing_the_fork_is_tagged_missed():
    # 61...h4 instead of Qc5+ (stored cp_loss 178).
    tags = tag_move(AFTER_KE7, "h4", best="Qc5+",
                    pv_after_best=["Kd8", "Qxd5+", "Kc7", "Qc6+"], cp_loss=178)
    assert ("missed", "fork", "Qc5+", 0) in _kinds(tags)


def test_a_found_tactic_must_be_close_to_best():
    """Every played fork in 40 of Mohit's games cost 50+ cp; praising those as
    found would sit under a Mistake badge."""
    assert FOUND_MAX_CP_LOSS == 49
    tags = tag_move(AFTER_KE7, "Qc5+", best="Qc5+",
                    pv_after_played=["Kd7", "Qxd5+", "Kc8"], cp_loss=120)
    assert not [t for t in tags if t["kind"] == "found"]


def test_a_quiet_pawn_move_gets_no_tag():
    """Negative control: 7.Nf3 of 3c8d0751; the engine's e6 hits a knight and a
    pawn and leads to a pawn trade -- not a proved tactic."""
    fen = "rn1qkb1r/pppnpppp/6b1/4P3/2BP4/2N5/PP3PPP/R1BQK1NR w KQkq - 0 7"
    assert tag_move(fen, "Nf3", best="e6", pv_after_best=["fxe6", "Bxe6", "Nf6"],
                    cp_loss=248) == []


def test_an_illegal_or_unreadable_move_is_never_tagged():
    assert tag_move(KE7_FEN, "Qh8", best="Ke5", cp_loss=500) == []
    assert tag_move("not a fen", "e4", best="d4", cp_loss=500) == []


def test_the_stored_observation_keeps_facts_but_not_the_long_replay():
    mv = {"fen_before": KE7_FEN, "move": "Ke7", "best_move": "Ke5",
          "pv_after_best": ["Qc5", "Kf4", "Qxd5"],
          "pv_after_played": ["Qc5+", "Kd7", "Qxd5+", "Kc8"], "cp_loss": 9115}
    tags = _tactic_tags_for(mv)
    fork = [t for t in tags if t["motif"] == "fork"][0]
    assert fork["kind"] == "allowed" and fork["at_ply"] == 0
    assert fork["facts"]["targets"] == ["d5", "e7"]
    assert "replayed_uci" not in fork["facts"]


def test_the_observation_step_never_breaks_on_bad_input():
    assert _tactic_tags_for(None) == []
    assert _tactic_tags_for({"fen_before": "x", "move": "e4"}) == []
