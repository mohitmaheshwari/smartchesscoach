from __future__ import annotations

from services.human_behavior_engine import MoveDistribution
from services.human_policy_runtime import MAIA2_PINNED_PACKAGE_VERSION
from services.puzzle_human_difficulty_shadow import (
    MEASURED_RATING_GRID,
    build_puzzle_human_difficulty_shadow,
)


FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
ENABLED = {
    "HUMAN_POLICY_EVIDENCE_ENABLED": "true",
    "PUZZLE_HUMAN_DIFFICULTY_SHADOW_ENABLED": "true",
}


class RatingAwareMaia:
    def available(self):
        return True

    def predict(self, ctx, top_k=20):
        probability = {800: 0.10, 1000: 0.20, 1200: 0.35, 1400: 0.50}[ctx.player_elo]
        return MoveDistribution(
            "maia2",
            MAIA2_PINNED_PACKAGE_VERSION,
            {"e2e4": probability, "d2d4": 0.08},
        )


def test_measured_grid_is_stored_as_shadow_without_authority():
    shadow, reason = build_puzzle_human_difficulty_shadow(
        fen=FEN,
        answer_uci="e2e4",
        maia=RatingAwareMaia(),
        env=ENABLED,
    )
    assert reason == "shadow_recorded"
    packet = shadow.contract_dict()
    assert packet["rating_grid"] == list(MEASURED_RATING_GRID)
    assert [item["answer_probability"] for item in packet["ratings"]] == [
        0.10, 0.20, 0.35, 0.50
    ]
    assert packet["shadow_only"] is True
    assert packet["changes_admission"] is False
    assert packet["changes_answer"] is False
    assert packet["changes_serving"] is False
    assert packet["chess_authority"] is False


def test_disabled_or_illegal_answer_abstains():
    assert build_puzzle_human_difficulty_shadow(
        fen=FEN, answer_uci="e2e4", maia=RatingAwareMaia(), env={}
    ) == (None, "disabled")
    assert build_puzzle_human_difficulty_shadow(
        fen=FEN, answer_uci="e2e5", maia=RatingAwareMaia(), env=ENABLED
    ) == (None, "illegal_answer")


def test_missing_answer_probability_is_partial_not_invented():
    class SparseMaia(RatingAwareMaia):
        def predict(self, ctx, top_k=20):
            probabilities = {"d2d4": 0.4}
            if ctx.player_elo == 1200:
                probabilities["e2e4"] = 0.2
            return MoveDistribution("maia2", MAIA2_PINNED_PACKAGE_VERSION, probabilities)

    shadow, reason = build_puzzle_human_difficulty_shadow(
        fen=FEN,
        answer_uci="e2e4",
        maia=SparseMaia(),
        env=ENABLED,
    )
    assert reason == "shadow_recorded"
    packet = shadow.contract_dict()
    assert packet["status"] == "partial"
    assert packet["ratings"][0]["answer_probability"] is None
    assert packet["ratings"][2]["answer_probability"] == 0.2
