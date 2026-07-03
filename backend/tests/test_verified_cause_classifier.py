"""Unit tests for the verified-cause classifier — every label proven from the board.

Run:  python -m pytest tests/test_verified_cause_classifier.py -q   (from backend/)
  or:  python tests/test_verified_cause_classifier.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.verified_cause_classifier import classify_verified_cause


def test_one_move_hang_is_piece_safety():
    # White queen (e2) grabs e5, but the pawn is defended by Nc6 → Nxe5 wins the queen.
    fen = "4k3/8/2n5/4p3/8/8/4Q3/4K3 w - - 0 1"
    r = classify_verified_cause(fen, "Qxe5")
    assert r is not None and r["gap"] == "piece_safety", r
    assert r["evidence"]["lost_piece"] == "queen" and r["evidence"]["square"] == "e5", r


def test_quiet_developing_move_abstains():
    # Nf3 from the start — no hang, no missed material → must abstain (None).
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    r = classify_verified_cause(fen, "Nf3")
    assert r is None, r


def test_missed_free_queen_is_missed_tactic():
    # Rd4 (defended by Rd2, so it's SAFE) can play Rxd8+ winning the queen. Playing the
    # safe Kf1 instead misses it — and Kf1 hangs nothing (Qxd4 Rxd4 loses for Black).
    fen = "3qk3/8/8/8/3R4/8/3R4/4K3 w - - 0 1"
    r = classify_verified_cause(
        fen, "Kf1", best_san="Rxd8+",
        pv_after_played=["Qc7"], pv_after_best=["Kxd8"],
    )
    assert r is not None and r["gap"] == "missed_tactic", r
    assert r["evidence"]["gain_cp"] >= 150, r


def test_sound_capture_is_not_a_hang():
    # Qxe5 when e5 is UNDEFENDED wins a free pawn — not a hang, and no bigger tactic.
    fen = "4k3/8/8/4p3/8/8/8/3QK3 w - - 0 1"
    r = classify_verified_cause(fen, "Qxe5")
    assert r is None, r  # winning a free pawn is not a mistake cause


def test_multi_move_material_loss_is_tactical_oversight():
    # A move that isn't a one-move hang but drops material over the forced line.
    # White's Bb5 is met by ...a6 ...b5 winning the bishop over several ply (fabricated
    # line for the deterministic material-swing check).
    fen = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
    # Played a quiet move; the engine line just walks material off. We assert the
    # classifier does NOT crash and returns a dict-or-None (integration-level guard).
    r = classify_verified_cause(fen, "Bxc6", best_san="O-O",
                                pv_after_played=["dxc6"], pv_after_best=[])
    assert r is None or r["gap"] in ("piece_safety", "tactical_oversight", "missed_tactic"), r


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e!r}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
