"""Boundary tests for services/caption_pipeline + services/severity.

These are pure-function pytest tests anchoring the canonical surfaces
that v83-v99 hardened. They exist as a regression safety net for the
v100 extraction work: the public contract here must not drift, even
as inline V5 blocks migrate into caption_pipeline.

What's anchored:
  - classify_severity tier thresholds (v92 single canonical evaluator)
  - opp_ prefix convention + mate-sentinel escape hatch
  - classify_severity_practical win-prob delta + decisiveness overlay (v96)
  - Mohit's locked examples: +4.0->+3.3 soften, +2.0->+0.2 serious
  - Black-mover sign flip into mover POV
  - compute_severity_for_move forced-recapture detection
  - compute_severity_for_move opp vs user eval routing (v98)
  - inject_practical_severity_facts contract (v99 caption-tone wiring)
  - JSON severity_tiers parity audit across R12 + R_PROMOTED
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import chess  # noqa: E402

from services.caption_pipeline import (  # noqa: E402
    compute_severity_for_move,
    inject_practical_severity_facts,
)
from services.severity import (  # noqa: E402
    MATE_SENTINEL_CP,
    PRACTICAL_WP_THRESHOLDS,
    SEVERITY_THRESHOLDS,
    TIER_ORDER,
    classify_severity,
    classify_severity_practical,
    validate_json_severity_tiers,
    win_prob_from_cp,
)


# ────────────────────────────────────────────────────────────────────
# classify_severity — v92 canonical evaluator
# ────────────────────────────────────────────────────────────────────


class TestClassifySeverityCanonical:
    """v92 — single canonical severity evaluator. THE thresholds."""

    @pytest.mark.parametrize("cp_loss,expected", [
        (0,    "good"),
        (29,   "good"),
        (30,   "inaccuracy"),
        (99,   "inaccuracy"),
        (100,  "mistake"),
        (249,  "mistake"),
        (250,  "serious"),
        (399,  "serious"),
        (400,  "blunder"),
        (1500, "blunder"),
    ])
    def test_user_tier_boundaries(self, cp_loss, expected):
        result = classify_severity(cp_loss, mover_is_user=True)
        assert result.tier == expected
        assert result.user_facing_tier == expected  # user side: tier == user_facing

    @pytest.mark.parametrize("cp_loss,expected_opp_facing", [
        (29,   "context"),          # good → context for opp
        (30,   "opp_inaccuracy"),
        (100,  "opp_mistake"),
        (250,  "opp_serious"),
        (400,  "opp_blunder"),
    ])
    def test_opp_user_facing_prefix(self, cp_loss, expected_opp_facing):
        """opp side gets 'opp_' prefix; 'good' becomes 'context'."""
        result = classify_severity(cp_loss, mover_is_user=False)
        assert result.user_facing_tier == expected_opp_facing

    def test_mate_walked_into_overrides_low_cp_loss(self):
        """User played a move that walks into a mate sequence; engine
        stored small cp_loss (fb_a9ac9f02affa case). Must still classify
        as blunder via the mate-sentinel escape hatch."""
        result = classify_severity(
            cp_loss=50,
            mover_is_user=True,
            user_post_eval_cp=-MATE_SENTINEL_CP - 100,
        )
        assert result.tier == "blunder"
        assert result.walked_into_mate is True

    def test_negative_cp_loss_normalised_to_zero(self):
        """Defensive: engine should never give negative loss, but if
        it does we clamp to 0 not crash."""
        result = classify_severity(cp_loss=-50, mover_is_user=True)
        assert result.cp_loss == 0
        assert result.tier == "good"

    def test_thresholds_dict_locked_values(self):
        """Mohit-locked values — drifting these silently is a regression."""
        assert SEVERITY_THRESHOLDS == {
            "inaccuracy": 30,
            "mistake":    100,
            "serious":    250,
            "blunder":    400,
        }
        assert MATE_SENTINEL_CP == 3000
        assert TIER_ORDER == ["good", "inaccuracy", "mistake", "serious", "blunder"]


# ────────────────────────────────────────────────────────────────────
# win_prob_from_cp — v96 sigmoid
# ────────────────────────────────────────────────────────────────────


class TestWinProbFromCp:
    def test_zero_cp_is_half(self):
        assert win_prob_from_cp(0) == pytest.approx(0.5)

    def test_positive_cp_above_half(self):
        wp = win_prob_from_cp(200)
        assert 0.60 < wp < 0.65  # sigmoid(0.5) ≈ 0.622

    def test_negative_cp_below_half(self):
        wp = win_prob_from_cp(-200)
        assert 0.35 < wp < 0.40
        assert wp == pytest.approx(1.0 - win_prob_from_cp(200))

    def test_extreme_cp_does_not_overflow(self):
        wp_huge = win_prob_from_cp(100_000)
        wp_huge_neg = win_prob_from_cp(-100_000)
        # Capped at ±5000 internally — sigmoid(12.5) is ~1.0 but finite.
        assert 0.99 < wp_huge <= 1.0
        assert 0.0 <= wp_huge_neg < 0.01


# ────────────────────────────────────────────────────────────────────
# classify_severity_practical — v96 win-prob delta + decisiveness
# ────────────────────────────────────────────────────────────────────


class TestClassifySeverityPractical:
    """v96 — practical severity from |Δwin_prob| + decisiveness overlay.
    Mohit's locked examples (2026-05-25) tested here verbatim."""

    def test_missing_evals_returns_neutral_fallback(self):
        result = classify_severity_practical(
            cp_loss=150,
            mover_is_user=True,
            mover_is_white=True,
            eval_before_cp=None,
            eval_after_cp=None,
        )
        assert result.practical_tier == result.canonical_tier == "mistake"
        assert result.mover_winprob_before == 0.5
        assert result.mover_winprob_after == 0.5
        assert result.winprob_delta == 0.0
        assert result.state_before == "balanced"
        assert result.state_after == "balanced"
        assert result.decisiveness_changed is False
        assert result.stayed_winning is False

    def test_mohit_example_softens_winning_drift(self):
        """+4.0 → +3.3 (white POV, white mover) should soften:
        small Δwp, stayed winning. Canonical inaccuracy → practical good."""
        result = classify_severity_practical(
            cp_loss=70,
            mover_is_user=True,
            mover_is_white=True,
            eval_before_cp=400,
            eval_after_cp=330,
        )
        assert result.canonical_tier == "inaccuracy"
        assert result.practical_tier == "good"
        assert result.stayed_winning is True
        assert result.decisiveness_changed is False

    def test_mohit_example_lost_winning_bumps_to_serious(self):
        """+2.0 → +0.2 (white POV, white mover) lost the winning edge:
        canonical mistake should bump practical to serious."""
        result = classify_severity_practical(
            cp_loss=180,
            mover_is_user=True,
            mover_is_white=True,
            eval_before_cp=200,
            eval_after_cp=20,
        )
        assert result.canonical_tier == "mistake"
        assert result.practical_tier == "serious"
        assert result.state_before == "winning"
        assert result.state_after == "balanced"
        assert result.decisiveness_changed is True
        assert result.stayed_winning is False

    def test_black_mover_sign_flip(self):
        """Engine evals are white POV. A black mover going from
        -300cp (winning for black) to -50cp (balanced) should be
        detected as 'winning → balanced' from mover POV via the
        sign-flip in classify_severity_practical."""
        result = classify_severity_practical(
            cp_loss=250,
            mover_is_user=True,
            mover_is_white=False,
            eval_before_cp=-300,  # winning for black (+300 mover POV)
            eval_after_cp=-50,    # balanced for black (+50 mover POV)
        )
        assert result.state_before == "winning"
        assert result.state_after == "balanced"
        assert result.decisiveness_changed is True
        assert result.stayed_winning is False

    def test_stayed_winning_blocks_decisiveness_changed(self):
        """+5.0 → +3.0 stays winning for white — decisiveness_changed
        must be False, stayed_winning True."""
        result = classify_severity_practical(
            cp_loss=200,
            mover_is_user=True,
            mover_is_white=True,
            eval_before_cp=500,
            eval_after_cp=300,
        )
        assert result.state_before == "winning"
        assert result.state_after == "winning"
        assert result.stayed_winning is True
        assert result.decisiveness_changed is False

    def test_practical_never_exceeds_canonical_when_no_lost_winning(self):
        """Cap rule: when the move didn't lose the winning edge, the
        practical tier must NOT outrank the canonical tier."""
        # Balanced → balanced (0 → -50): no decisiveness change.
        # Even if Δwp were huge, practical stays ≤ canonical.
        result = classify_severity_practical(
            cp_loss=50,  # inaccuracy canonical
            mover_is_user=True,
            mover_is_white=True,
            eval_before_cp=0,
            eval_after_cp=-50,
        )
        # canonical "inaccuracy"; practical must be ≤ inaccuracy.
        assert TIER_ORDER.index(result.practical_tier) <= TIER_ORDER.index("inaccuracy")

    def test_practical_thresholds_dict_locked(self):
        assert PRACTICAL_WP_THRESHOLDS == {
            "inaccuracy": 0.05,
            "mistake":    0.15,
            "serious":    0.30,
            "blunder":    0.50,
        }


# ────────────────────────────────────────────────────────────────────
# compute_severity_for_move — v100 step 2 extraction (caption_pipeline)
# ────────────────────────────────────────────────────────────────────


def _make_board(fen: str) -> chess.Board:
    return chess.Board(fen)


class TestComputeSeverityForMove:
    """The extracted V5-wiring helper that routes evals correctly for
    user vs opp moves and detects forced recapture."""

    def test_user_move_routes_user_eval_pov_to_practical(self):
        """User move (white) — practical severity must consume
        user_eval_*_white_pov, ignore opp_eval_*."""
        board = _make_board(chess.STARTING_FEN)
        played = chess.Move.from_uci("e2e4")
        result = compute_severity_for_move(
            cp_loss=180,
            opp_cp_loss=0,
            is_user=True,
            is_white=True,
            user_color="white",
            mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=200,
            user_eval_after_white_pov=20,
            opp_eval_before=-999,  # should be ignored for user moves
            opp_eval_after=-999,
            board_before=board,
            played_move=played,
            prev_move=None,
        )
        assert result.severity_canonical == "mistake"
        assert result.severity_user_facing == "mistake"
        # Practical should reflect user evals, not opp — lost-winning bump.
        assert result.practical.state_before == "winning"
        assert result.practical.state_after == "balanced"
        assert result.practical.practical_tier == "serious"
        assert result.is_forced_recapture is False

    def test_opp_move_routes_opp_eval_to_practical(self):
        """Opp move — practical severity must consume opp_eval_before/after,
        not the (None or stale) user evals."""
        board = _make_board(chess.STARTING_FEN)
        result = compute_severity_for_move(
            cp_loss=0,
            opp_cp_loss=150,
            is_user=False,
            is_white=False,  # opp is black here
            user_color="white",
            mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=None,
            user_eval_after_white_pov=None,
            opp_eval_before=-300,  # black mover POV = +300 (winning)
            opp_eval_after=-50,    # black mover POV = +50 (balanced)
            board_before=board,
            played_move=None,
            prev_move=None,
        )
        assert result.severity_canonical == "mistake"
        assert result.severity_user_facing == "opp_mistake"
        # Sign-flipped to black mover POV.
        assert result.practical.state_before == "winning"
        assert result.practical.state_after == "balanced"

    def test_forced_recapture_downgrades_user_facing_to_good(self):
        """Reviewer scenario: user recaptures on the square opp just
        captured, only one legal capture exists → forced. Cap should
        downgrade to 'good' and flag is_forced_recapture=True."""
        # Position: white knight on c3 has captured a black bishop on d5.
        # Black has only one piece (e6 pawn) that can recapture on d5.
        fen = "rnbqkbnr/ppp1pppp/8/3N4/8/8/PPPP1PPP/R1BQKB1R b KQkq - 0 1"
        board = _make_board(fen)
        prev_move = chess.Move.from_uci("c3d5")
        played_move = chess.Move.from_uci("e6d5")  # pawn captures back
        result = compute_severity_for_move(
            cp_loss=400,  # canonical blunder, but forced recapture
            opp_cp_loss=0,
            is_user=True,
            is_white=False,  # black is the user here
            user_color="black",
            mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=0,
            user_eval_after_white_pov=0,
            opp_eval_before=None,
            opp_eval_after=None,
            board_before=board,
            played_move=played_move,
            prev_move=prev_move,
        )
        assert result.is_forced_recapture is True
        assert result.severity_user_facing == "good"
        # Canonical tier still reflects raw cp_loss; only user_facing changes.
        assert result.severity_canonical == "blunder"

    def test_forced_recapture_not_triggered_when_multiple_captures_available(self):
        """When more than one piece can legally recapture, the move was
        a choice, not forced — must NOT downgrade."""
        # Black bishop just captured on d4. White has TWO legal
        # recapturers: c3 pawn (cxd4) and f3 knight (Nxd4).
        fen = "rnbqkbnr/ppp1pppp/8/8/3b4/2P2N2/PP1PPPPP/RNBQKB1R w KQkq - 0 1"
        board = _make_board(fen)
        prev_move = chess.Move.from_uci("e5d4")  # bishop landed on d4
        played_move = chess.Move.from_uci("c3d4")  # pawn recapture (one of two)
        result = compute_severity_for_move(
            cp_loss=120,
            opp_cp_loss=0,
            is_user=True,
            is_white=True,
            user_color="white",
            mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=0,
            user_eval_after_white_pov=-120,
            opp_eval_before=None,
            opp_eval_after=None,
            board_before=board,
            played_move=played_move,
            prev_move=prev_move,
        )
        assert result.is_forced_recapture is False
        assert result.severity_user_facing == "mistake"

    def test_forced_recapture_requires_prev_move(self):
        """No prev_move (game start, or opp didn't capture) → never
        forced. Defensive: guard against None prev_move."""
        board = _make_board(chess.STARTING_FEN)
        result = compute_severity_for_move(
            cp_loss=150,
            opp_cp_loss=0,
            is_user=True,
            is_white=True,
            user_color="white",
            mate_sentinel_eval_cp=None,
            user_eval_before_white_pov=0,
            user_eval_after_white_pov=-150,
            opp_eval_before=None,
            opp_eval_after=None,
            board_before=board,
            played_move=chess.Move.from_uci("e2e4"),
            prev_move=None,
        )
        assert result.is_forced_recapture is False


# ────────────────────────────────────────────────────────────────────
# inject_practical_severity_facts — v100 step 3 extraction
# ────────────────────────────────────────────────────────────────────


class TestInjectPracticalSeverityFacts:
    """The v99 caption-tone wiring that lets R12 / R_PROMOTED
    softening rules fire. Six fields, in-place mutation, no return."""

    def test_stamps_all_six_fields(self):
        from services.severity import PracticalSeverity
        practical = PracticalSeverity(
            practical_tier="inaccuracy",
            canonical_tier="mistake",
            mover_winprob_before=0.72,
            mover_winprob_after=0.58,
            winprob_delta=-0.14,
            state_before="winning",
            state_after="balanced",
            decisiveness_changed=True,
            stayed_winning=False,
        )
        facts: dict = {}
        ret = inject_practical_severity_facts(facts, practical)
        assert ret is None  # mutates in place
        assert facts == {
            "severity_practical": "inaccuracy",
            "severity_canonical": "mistake",
            "mover_state_before": "winning",
            "mover_state_after":  "balanced",
            "stayed_winning":     False,
            "decisiveness_changed": True,
        }

    def test_does_not_pollute_unrelated_keys(self):
        from services.severity import PracticalSeverity
        practical = PracticalSeverity(
            practical_tier="good",
            canonical_tier="good",
            mover_winprob_before=0.5,
            mover_winprob_after=0.5,
            winprob_delta=0.0,
            state_before="balanced",
            state_after="balanced",
            decisiveness_changed=False,
            stayed_winning=False,
        )
        facts = {
            "rule_name": "R07_forced_recapture",
            "caption": "Forced recapture.",
            "cp_loss": 0,
        }
        inject_practical_severity_facts(facts, practical)
        # Original keys preserved.
        assert facts["rule_name"] == "R07_forced_recapture"
        assert facts["caption"] == "Forced recapture."
        assert facts["cp_loss"] == 0
        # Plus the six injected.
        assert facts["severity_practical"] == "good"
        assert facts["severity_canonical"] == "good"


# ────────────────────────────────────────────────────────────────────
# JSON severity_tiers audit — v92 cross-file parity
# ────────────────────────────────────────────────────────────────────


_CAPTIONS_DIR = Path(_BACKEND_ROOT) / "data" / "captions"


def _load_severity_tiers(fname: str) -> list:
    """Pull the severity_tiers entries that have cp_loss gte thresholds
    (skip severity_practical-keyed entries — those are dispatch rules,
    not numeric tier definitions)."""
    path = _CAPTIONS_DIR / fname
    if not path.exists():
        pytest.skip(f"{fname} not present at {path}")
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    tiers = body.get("severity_tiers") or []
    # Filter to entries with cp_loss thresholds — those are the ones
    # validate_json_severity_tiers checks.
    return [t for t in tiers if isinstance(t, dict) and (t.get("when") or {}).get("cp_loss")]


class TestSeverityJsonAudit:
    """v92 — JSON predicate engine thresholds MUST match the canonical
    SEVERITY_THRESHOLDS dict. validate_json_severity_tiers is the
    audit helper used by regen scripts."""

    @pytest.mark.parametrize("fname", [
        "R12_blunder.json",
        "R_PROMOTED_basic_mistake.json",
    ])
    def test_json_thresholds_match_canonical(self, fname):
        tiers = _load_severity_tiers(fname)
        mismatches = validate_json_severity_tiers({fname: tiers})
        assert mismatches == [], (
            f"{fname} severity_tiers drift from SEVERITY_THRESHOLDS: "
            f"{mismatches}"
        )

    def test_validate_helper_flags_drift(self):
        """Sanity: the helper actually catches mismatches when they exist."""
        wrong = [{"when": {"cp_loss": {"gte": 999}}, "tier": "blunder"}]
        mismatches = validate_json_severity_tiers({"synthetic.json": wrong})
        assert len(mismatches) == 1
        assert "blunder" in mismatches[0][1]
        assert "999" in mismatches[0][1]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
