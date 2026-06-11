"""
Regression: Play-with-Coach games must be enriched the same way imported games
are — every move carries `is_user_move`, user moves carry `move_uci`, a user
move with a real eval-drop gets a `cognitive_gap`, and accuracy uses the CAPS2
formula (never the linear collapse to 0/1).

Guards docs/pwc_live_analysis_reuse_scope.md. Pure (no DB / no HTTP / no
Stockfish) — builds a synthetic session move_history with python-chess.

Run: python3 tests/test_pwc_gap_enrichment.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess

from routes.coach_play import _build_enriched_coach_move_evaluations


def _make_move_history():
    """A real opening line; the user is White. We inject a 400cp eval drop on
    one user move so the gap classifier has a learning moment to tag."""
    sans = ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6", "dxc6", "Nxe5", "Qd4"]
    board = chess.Board()
    history = []
    for i, san in enumerate(sans):
        move = board.parse_san(san)
        uci = move.uci()
        fen_before = board.fen()
        board.push(move)
        fen_after = board.fen()
        by = "player" if i % 2 == 0 else "coach"  # White = user
        entry = {
            "move": san,
            "uci": uci,
            "by": by,
            "fen_before": fen_before,
            "fen_after": fen_after,
        }
        if by == "player":
            # Flat evals except a deliberate blunder on 5.Nxe5 (index 8):
            # eval drops 0.5 -> -3.5 from White's perspective (cp_loss 400).
            if i == 8:
                entry["eval_before"] = 0.5
                entry["eval_after"] = -3.5
                entry["evaluation"] = "blunder"
            else:
                entry["eval_before"] = 0.3
                entry["eval_after"] = 0.2
                entry["evaluation"] = "good"
        history.append(entry)
    return history


def test_enrichment():
    mh = _make_move_history()
    moves, accuracy, blunders, mistakes = _build_enriched_coach_move_evaluations(mh, "white")

    # 1. Every move carries is_user_move; both sides present (schema parity).
    assert all("is_user_move" in m for m in moves), "is_user_move missing on some move"
    user_moves = [m for m in moves if m["is_user_move"]]
    opp_moves = [m for m in moves if not m["is_user_move"]]
    assert len(user_moves) == 5 and len(opp_moves) == 5, (len(user_moves), len(opp_moves))

    # 2. move_uci populated on user moves (the field the gap classifier needs).
    assert all(m["move_uci"] for m in user_moves), "move_uci empty on a user move"

    # 3. The injected blunder (5.Nxe5) gets a cognitive_gap.
    blunder = next(m for m in user_moves if m["move"] == "Nxe5")
    assert blunder["cp_loss"] >= 300, blunder["cp_loss"]
    assert blunder.get("cognitive_gap"), "blunder user move was left untagged"

    # 4. Accuracy is a sane CAPS2 score — NOT the old linear collapse to 0/1.
    assert 0.0 < accuracy <= 100.0, accuracy
    assert blunders >= 1, blunders

    print(f"OK — {len(user_moves)} user / {len(opp_moves)} opp moves, "
          f"blunder tagged '{blunder['cognitive_gap']}', acc={accuracy}, "
          f"blunders={blunders}, mistakes={mistakes}")


if __name__ == "__main__":
    test_enrichment()
    print("PASS: test_pwc_gap_enrichment")
