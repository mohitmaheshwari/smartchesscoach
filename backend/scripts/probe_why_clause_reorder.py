"""Stateless probe for the why_clauses_user predicate ordering.

Mohit 2026-06-01 (feedback batch fb_457d / fb_3efc / fb_3d53 / fb_1cd7
/ fb_79c3 — see [memory/project_caption_filed_for_future.md] item #2):
when both "why played wrong" facts AND "why alternative is better"
facts are present, the central caption pipeline currently picks the
alternative-promotion variant because the predicate list at
R12_blunder.json:146-189 puts it higher.

This script doesn't need Mongo or stockfish. It feeds synthetic fact
dicts through resolve_why_clause and prints which variant wins.
Used to:

  1. Baseline the CURRENT selection on representative fact sets
  2. Apply the reorder
  3. Re-run and diff
  4. Confirm: failure-mode variants win when both flavors of fact are
     present; alternative-promotion variants still win when only those
     facts are present

If both checks pass, the reorder is safe. snapshot_surface1 is the
fuller regression net but needs production Mongo access.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_templates import resolve_why_clause


# ── Representative fact dicts ───────────────────────────────────────────
#
# Each entry is (name, facts_dict, expected_variant_before, expected_after).
# Before/after are filled in by running the script twice — once on the
# current JSON, once after the reorder.

CASES = [
    # CASE 1 — both flavours present.
    # Played move walks into opp's attack on its destination square,
    # AND the engine's better move would have been a pawn kick.
    # Currently: pawn_kicks fires (wrong). After reorder: attacks_played
    # should fire (right).
    {
        "name": "both_present_pawnkick_and_attacks_played",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 200,
            # Alternative-promotion facts (h4 attacks Bg3):
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
            # Failure-mode facts (opp reply attacks played piece):
            "opp_reply_san": "Nb7",
            "opp_reply_attacks_played_piece": True,
            "target_square": "b2",
            "moving_piece_type": "bishop",
        },
    },

    # CASE 2 — only alternative-promotion facts present.
    # Played move was just suboptimal; nothing concrete to say about
    # the failure. Should still produce the pawn_kicks caption.
    {
        "name": "only_pawn_kick_present",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 60,
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
        },
    },

    # CASE 3 — only failure-mode facts present.
    # No alternative-promotion fact at all. Should produce attacks_played.
    {
        "name": "only_attacks_played",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 200,
            "opp_reply_san": "Nb7",
            "opp_reply_attacks_played_piece": True,
            "target_square": "b2",
            "moving_piece_type": "bishop",
        },
    },

    # CASE 4 — played hangs material AND alternative would have been a
    # pawn kick. Should fire why_user_hanging after reorder.
    {
        "name": "both_present_pawnkick_and_hanging",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 300,
            "pawn_kicks_piece_square": "g3",
            "pawn_kicks_piece_type": "bishop",
            "pieces_now_undefended_present": True,
            "piece_type": "bishop",
            "square": "b2",
        },
    },

    # CASE 5 — played walks into mate.
    # check fact only. Always fires why_user_check.
    {
        "name": "only_opp_check",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 800,
            "opp_reply_san": "Qh5+",
            "opp_reply_san_is_check": True,
        },
    },

    # CASE 6 — alternative would be missed knight outpost; played hangs
    # a piece. Should fire why_user_hanging after reorder.
    {
        "name": "both_present_outpost_and_hanging",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 250,
            "knight_outpost_destination": "d5",
            "knight_outpost_defender_piece": "pawn",
            "knight_outpost_defender_square": "e4",
            "pieces_now_undefended_present": True,
            "piece_type": "knight",
            "square": "f6",
        },
    },

    # CASE 7 — guard against degenerate fires. cp_loss < 50, only
    # opp_reply_attacks_played_piece, no other facts. Existing rule
    # gates attacks_played at cp_loss >= 50 — should NOT fire here.
    {
        "name": "below_cp_threshold_no_fire",
        "facts": {
            "mover_is_user": True,
            "played_san": "Bb2",
            "best_move_san": "h4",
            "cp_loss": 30,
            "opp_reply_san": "Nf3",
            "opp_reply_attacks_played_piece": True,
            "target_square": "e5",
            "moving_piece_type": "knight",
        },
    },
]


def run(label: str):
    print(f"\n=== Selection: {label} ===")
    for c in CASES:
        text = resolve_why_clause("R12_blunder", "why_clauses_user", c["facts"])
        # text is the rendered template; we want the variant name. The
        # quickest signal: prefix it. Truncate for readability.
        snippet = (text or "<no fire>")[:80]
        print(f"  {c['name']:>42}: {snippet}")


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "current"
    run(label)
