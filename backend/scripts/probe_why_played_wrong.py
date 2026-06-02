"""Stateless probe for the two-clause 'why played wrong' system.

Mohit 2026-06-02. Replaces probe_why_clause_reorder.py from the
reverted attempt. Tests the 4 outcomes defined in
docs/why_played_wrong_spec.md by feeding synthetic fact dicts
through render_rule and inspecting the produced caption.

Doesn't need Mongo / Stockfish. Runs against the local R12 JSON
exactly as the live system would, but with hand-crafted facts so
we know which outcome each case targets.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_templates import render_rule


COMMON = {
    "mover_is_user": True,
    "played_san": "Bb2",
    "best_move_san": "h4",
    "best_move_san_differs": True,
    "cp_loss": 201,
}


CASES = [
    # OUTCOME 1: failure ✓ + alternative ✓
    # Played walks into opp attack on its destination square (failure
    # via opp_reply_attacks_played_piece), AND the engine's best move
    # is a pawn that kicks an enemy piece (alternative via
    # pawn_kicks_piece_square).
    #
    # Expected caption shape:
    #   "Bb2 walks into Nb7 attacking the bishop on b2. h4 was better — {alt}."
    {
        "name": "1_failure_plus_alternative",
        "facts": {
            **COMMON,
            # failure-mode facts:
            "opp_reply_san": "Nb7",
            "opp_reply_attacks_played_piece": True,
            "target_square": "b2",
            "moving_piece_type": "bishop",
            # alternative-promotion facts:
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
        },
    },

    # OUTCOME 2: failure ✓ + alternative ✗
    # Played hangs material (failure via pieces_now_undefended_present)
    # but no alternative-promotion fact fires. Should produce the
    # failure clause + a teaching principle.
    #
    # Expected caption shape:
    #   "Bb2 leaves your bishop on b2 undefended. Every move, scan: ..."
    {
        "name": "2_failure_plus_principle",
        "facts": {
            **COMMON,
            "pieces_now_undefended_present": True,
            "moving_piece_type": "bishop",
            "target_square": "b2",
            "lost_defender_lead_clause": None,
        },
    },

    # OUTCOME 3: failure ✗ + alternative ✓ (existing behavior, no change)
    # Played move is just suboptimal; no failure-mode fact fires.
    # Should produce the existing alternative-only caption shape.
    #
    # Expected caption shape:
    #   "Bb2 is a mistake. h4 was better — it attacks the bishop on g3..."
    {
        "name": "3_alternative_only",
        "facts": {
            **COMMON,
            "cp_loss": 80,
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
        },
    },

    # OUTCOME 4: failure ✗ + alternative ✗
    # Nothing concrete; below suppression threshold. Should be silent
    # (suppression kicks in when cp_loss < 250 + no why_clause + balanced).
    #
    # Expected: None (suppressed).
    {
        "name": "4_silent_no_facts",
        "facts": {
            **COMMON,
            "cp_loss": 60,
        },
    },

    # OUTCOME 5: opp side, sanity check we didn't break opp captions
    # by adding the user-side failure resolution.
    {
        "name": "5_opp_side_unchanged",
        "facts": {
            **COMMON,
            "mover_is_user": False,
            "played_san": "Bg3",
            "best_move_san": "Bxf4",
            "opp_has_concrete_why": True,
            "opp_user_reply_tactic_kind": "piece_capture",
            "opp_user_reply_tactic_target_piece": "bishop",
            "opp_user_reply_tactic_target_square": "g3",
        },
    },

    # OUTCOME 6 — REAL-WORLD FROM BUG: the m20 Bb2 position
    # (game_85bd0169aa4f). Both failure (opp Nb7-style attacking the
    # played bishop) AND alternative (h4 attacks Bg3) present in
    # real life per the snapshot.
    {
        "name": "6_real_world_m20_Bb2",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "best_move_san_differs": True,
            "cp_loss": 201,
            # failure: opp Rb1 attacks the played piece on b2
            "opp_reply_san": "Rb1",
            "opp_reply_attacks_played_piece": True,
            "target_square": "b2",
            "moving_piece_type": "bishop",
            # alternative: h4 attacks Bg3
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
        },
    },

    # OUTCOME 7 — PHASE 2 NEW FACT: m24 Qb8 from the same bug batch.
    # Black played Qb8 → white plays Nb7 forking queen on c8 and
    # rook on a8. The played piece (queen) isn't directly attacked
    # at b8, so opp_reply_attacks_played_piece=False. But fork
    # detection should fire on (queen, rook) targets and produce
    # the "allows Nb7 forking your queen on c8 and rook on a8"
    # caption.
    #
    # No alternative-promotion fact (no easy pawn kick from this
    # position) → teaching principle should fire.
    {
        "name": "7_fork_real_world_m24_Qb8",
        "facts": {
            "mover_is_user": True,
            "played_san": "Qb8",
            "best_move_san": "Be7",
            "best_move_san_differs": True,
            "cp_loss": 124,
            # failure: Nb7 forks queen + rook
            "opp_reply_san": "Nb7",
            "opp_reply_creates_fork": True,
            "fork_target_1": "queen",
            "fork_target_1_square": "c8",
            "fork_target_2": "rook",
            "fork_target_2_square": "a8",
        },
    },

    # OUTCOME 8 — fork ALONE (no alternative fact, teaching principle).
    # Same as 7 but spelled out explicitly: failure ✓, alt ✗, principle ✓.
    {
        "name": "8_fork_only_principle",
        "facts": {
            **COMMON,
            "played_san": "Qb8",
            "best_move_san": "Be7",
            "opp_reply_san": "Nb7",
            "opp_reply_creates_fork": True,
            "fork_target_1": "queen",
            "fork_target_1_square": "c8",
            "fork_target_2": "rook",
            "fork_target_2_square": "a8",
        },
    },
]


def main():
    for c in CASES:
        try:
            out = render_rule("R12_blunder", c["facts"])
        except Exception as e:
            out = f"<ERROR: {e}>"
        snippet = out if out is not None else "<suppressed>"
        print(f"\n{c['name']}:")
        print(f"  {snippet}")


if __name__ == "__main__":
    main()
