"""Regression locks for the 2026-07-14 quality fixes (Q1 rating-aware review,
Q2 why-rate residue, the severity-POV bug).

Run: python backend/tests/test_quality_fixes.py   (or pytest)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess


# ── Q1: band tables live in rating_resolver, values locked ─────────────────
def test_band_tables_match_legacy_ladders():
    from services.rating_resolver import (
        caption_suppress_threshold_cp, move_classification_thresholds)
    old_suppress = lambda r: 150 if r < 1000 else 75 if r < 1400 else 50 if r < 1800 else 30
    old_classify = lambda r: (
        {"excellent": 20, "good": -30, "inaccuracy": -150, "mistake": -300} if r < 1000 else
        {"excellent": 20, "good": -20, "inaccuracy": -75, "mistake": -200} if r < 1400 else
        {"excellent": 20, "good": -10, "inaccuracy": -50, "mistake": -150} if r < 1800 else
        {"excellent": 10, "good": -5, "inaccuracy": -30, "mistake": -100})
    for r in [0, 500, 999, 1000, 1200, 1399, 1400, 1500, 1799, 1800, 2200, 9999]:
        assert caption_suppress_threshold_cp(r) == old_suppress(r), r
        assert move_classification_thresholds(r) == old_classify(r), r


def test_band_boundaries_derive_from_deterministic_source():
    from services.rating_resolver import get_rating_band
    assert get_rating_band(999) == "beginner_low"
    assert get_rating_band(1000) == "beginner_high"
    assert get_rating_band(1399) == "beginner_high"
    assert get_rating_band(1400) == "intermediate"
    assert get_rating_band(1799) == "intermediate"
    assert get_rating_band(1800) == "advanced"


# ── Q2 root cause: the severity-POV bug in extract_facts_verified ──────────
# A black mover's real blunder (white-POV eval RISES) must keep its caller-
# provided mover-POV cp_loss — the old code re-derived (before - after) with
# no color flip, got a negative, and the mistake vanished (floored to 0),
# routing 266cp blunders to neutral "check. King must move or block." text.
_BLACK_BLUNDER_FEN = "5Q2/7k/b4p1p/3p1p1N/2rn4/P4P1P/6P1/R5K1 b - - 0 43"


def test_verified_facts_trust_caller_cp_loss():
    from services.caption_facts_verified import extract_facts_verified
    f = extract_facts_verified(
        fen_before=_BLACK_BLUNDER_FEN, played_san="Ne2+", best_move_san="Rc7",
        eval_before_cp=947, eval_after_cp=1213, cp_loss=266, mover_is_user=True)
    assert f.get("cp_loss") == 266, f.get("cp_loss")


def test_verified_facts_derive_mover_pov_when_absent():
    from services.caption_facts_verified import extract_facts_verified
    # black to move, white-POV evals worsen for black: derived loss must be +266
    f = extract_facts_verified(
        fen_before=_BLACK_BLUNDER_FEN, played_san="Ne2+", best_move_san="Rc7",
        eval_before_cp=947, eval_after_cp=1213)
    assert f.get("cp_loss") == 266, f.get("cp_loss")


def test_black_blunder_renders_as_mistake_not_neutral_check():
    from services.caption_pipeline import (
        MoveInputs, CrossMoveState, build_move_teaching_decision)
    inputs = MoveInputs(
        fen_before=_BLACK_BLUNDER_FEN, played_san="Ne2+", mover_is_user=True,
        mover_is_white=False, user_color="black", full_move_number=43,
        move_history_san=[], best_move_san="Rc7",
        eval_before_cp=947, eval_after_cp=1213, cp_loss=266,
        pv_after_played=[], pv_after_best=[])
    d = build_move_teaching_decision(inputs, CrossMoveState())
    cap = d.text.caption or ""
    assert "must move or block" not in cap, cap   # the old neutral leak
    assert "mistake" in cap.lower() or "stronger" in cap.lower() or "better" in cap.lower(), cap


# ── Q2: best-move why derivation covers checks / mate / promotion ──────────
def test_recommended_move_why_check_branch():
    from services.caption_facts import _recommended_move_why
    # Qc4+ from a simple position: white queen c1->c4 gives check to Kg8? build one:
    b = chess.Board("6k1/8/8/8/8/8/8/2Q3K1 w - - 0 1")
    mv = b.parse_san("Qc4+")
    why = _recommended_move_why(b, mv)
    assert why is not None and "check" in why, why


def test_recommended_move_why_mate_branch():
    from services.caption_facts import _recommended_move_why
    b = chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
    mv = b.parse_san("Ra8#")
    assert _recommended_move_why(b, mv) == "delivers checkmate"


# ── Q2: mistake floor upgrades to a consequence when facts allow ───────────
def test_floor_consequence_from_opp_reply():
    from services.caption_fallback_tiers import tier23_caption
    facts = {"mover_is_user": True, "cp_loss": 300, "played_san": "Kd4",
             "best_move_san": "Kf5", "opp_reply_san": "Rxd4",
             "opp_reply_captures_piece_type": "knight"}
    cap, rule = tier23_caption(facts, flagged_mistake=True)
    assert rule == "R_TIER_mistake_floor_consequence", (cap, rule)
    assert "runs into Rxd4" in cap and "knight" in cap, cap


def test_floor_bare_when_no_consequence():
    from services.caption_fallback_tiers import tier23_caption
    facts = {"mover_is_user": True, "cp_loss": 300, "played_san": "Kd4",
             "best_move_san": "Kf5"}
    cap, rule = tier23_caption(facts, flagged_mistake=True)
    assert rule == "R_TIER_mistake_floor", (cap, rule)


# ── Q2: distilled allowed_mate must abstain when best == played ────────────
def test_allowed_mate_abstains_on_best_equals_played():
    from services.distilled_caption_service import try_distilled_caption
    from services.caption_pipeline import MoveInputs
    inp = MoveInputs(
        fen_before="r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        played_san="Nc3", mover_is_user=True, mover_is_white=True, user_color="white",
        full_move_number=4, move_history_san=[], best_move_san="Nc3",
        eval_before_cp=0, eval_after_cp=-9500, cp_loss=9500,
        pv_after_played=[], pv_after_best=[])
    r = try_distilled_caption(inp)
    assert r is None or not (r and r[0]), r   # "play Nc3 instead" after playing Nc3 = nonsense


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
