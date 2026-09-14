import chess
import pytest

from services.caption_facts import (
    FORCED_MATE_STORY_QUALITY_ID,
    MULTI_MOVE_MATERIAL_QUALITY_ID,
    QUEEN_SAFETY_QUALITY_ID,
    UNPUNISHED_OPPONENT_QUALITY_ID,
    build_verified_line_cause,
    build_verified_teaching_opportunities,
)
from services.caption_pipeline import (
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
    build_teaching_opportunity_comparisons,
)
from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    grade_for,
    is_authorized,
)
from services.game_review_planner import build_teaching_opportunity_shadow_summary
from services.game_review_contracts import ReviewContractViolation


def _cause(**kwargs):
    result = build_verified_line_cause(
        include_branch_evidence=True,
        **kwargs,
    )
    assert result is not None
    assert result.branch_evidence is not None
    return result


def _families(cause, *, mover_is_user=True):
    return build_verified_teaching_opportunities(
        fen_before=cause.branch_evidence.played_trace.initial_fen,
        mover_is_user=mover_is_user,
        cause=cause,
    )


def test_forced_mate_is_terminally_proved_and_story_key_is_stable():
    cause = _cause(
        fen_before="r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        played_san="Rg4",
        best_move_san="Nf4+",
        pv_after_played=("Rf8", "Rxg7", "Rxf3", "Kg2"),
        pv_after_best=("Kh6", "Nf5#"),
        cp_loss=10173,
    )

    opportunities = _families(cause)
    mate = next(item for item in opportunities if item.family == "forced_mate_story")
    assert mate.quality_id == FORCED_MATE_STORY_QUALITY_ID
    assert cause.branch_evidence.best_trace.checkmate is True
    assert mate.story_key == _families(cause)[0].story_key

    comparison = build_teaching_opportunity_comparisons((mate,))[0]
    assert comparison.headline == "A checkmating finish was here"
    assert comparison.stronger_line_moves[-1].endswith("#")
    assert "ends in checkmate" in comparison.stronger_summary


def test_material_family_requires_and_replays_more_than_one_capture():
    cause = _cause(
        fen_before="r1bqk1nr/pppp1ppp/2n5/2b1p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4",
        played_san="Nf6",
        best_move_san="Qxg5",
        pv_after_played=("Nxf7", "Bxf2+", "Kf1", "Qe7"),
        pv_after_best=("O-O", "Qg6", "b4", "Bb6"),
        cp_loss=550,
    )

    opportunity = next(
        item
        for item in _families(cause)
        if item.family == "multi_move_material_accounting"
    )
    assert opportunity.quality_id == MULTI_MOVE_MATERIAL_QUALITY_ID
    assert len(cause.played_captures) == 2
    assert opportunity.settled_material_edge_cp >= 300
    assert opportunity.consequence_owner == "player"
    comparison = build_teaching_opportunity_comparisons((opportunity,))[0]
    assert comparison.played_line_moves == cause.played_line_san
    assert "whole capture sequence" in comparison.headline.lower()
    assert "centipawn" not in str(comparison.contract_dict()).lower()


def test_capture_activity_without_settled_piece_size_edge_is_not_a_lesson():
    cause = _cause(
        fen_before="r2r2k1/pbq2pbp/1p1ppnp1/8/4PB2/1PN4N/1P3PPP/2RQ1RK1 w - - 4 17",
        played_san="Qc2",
        best_move_san="Nd5",
        pv_after_played=("Nxe4", "f3", "Nxc3", "bxc3"),
        pv_after_best=("Qb8", "Nc7", "Bxe4", "f3"),
        cp_loss=209,
    )

    assert all(
        item.family != "multi_move_material_accounting"
        for item in _families(cause)
    )


def test_queen_family_names_the_exact_queen_capture_not_a_universal_rule():
    cause = _cause(
        fen_before="3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1",
        played_san="Qxd5",
        best_move_san="Qa1",
        pv_after_played=("Rxd5",),
        pv_after_best=("Kf7",),
        cp_loss=800,
    )

    queen = next(
        item
        for item in _families(cause)
        if item.family == "queen_safety_or_greedy_capture"
    )
    assert queen.quality_id == QUEEN_SAFETY_QUALITY_ID
    assert queen.consequence_piece == "queen"
    assert queen.consequence_square == "d5"
    assert queen.consequence_owner == "player"
    assert queen.consequence_branch == "played"
    assert queen.consequence_ply == 2
    comparison = build_teaching_opportunity_comparisons((queen,))[0]
    rendered = str(comparison.contract_dict()).lower()
    assert "take your queen on d5" in rendered
    assert "avoid trading queens" not in rendered
    assert "always" not in rendered


def test_queen_safety_after_a_knight_move_never_teaches_queen_capture_advice():
    cause = _cause(
        fen_before="1k3r2/1ppbr2p/p1nb4/3p2p1/3P1p2/2PQ1P1P/PP1N2P1/2KR2N1 w - - 0 21",
        played_san="Ne2",
        best_move_san="Qf1",
        pv_after_played=("Bf5", "Nxf4", "Bxd3", "Nxd3"),
        pv_after_best=("Rfe8", "Nb3", "Bf5", "h4"),
        cp_loss=392,
    )

    queen = next(
        item
        for item in _families(cause)
        if item.family == "queen_safety_or_greedy_capture"
    )
    comparison = build_teaching_opportunity_comparisons((queen,))[0]

    assert queen.moving_piece == "knight"
    assert comparison.headline == "Your queen becomes the target"
    assert "queen capture" not in comparison.memory_cue.lower()
    assert "forcing" not in comparison.memory_cue.lower()
    assert comparison.played_summary == "Ne2 lets Bxd3 take your queen on d3."


def test_opponent_missed_chance_is_counterfactual_and_actor_safe():
    cause = _cause(
        fen_before="r3kbnr/pp1npp1p/2p5/8/3qB3/5Q2/PP1B1PPP/R3K1NR w KQkq - 0 13",
        played_san="Bf5",
        best_move_san="Bc3",
        pv_after_played=("e6", "Ne2", "Qxb2", "Bc3"),
        pv_after_best=("Qa4", "Bxh8", "Ngf6", "Bxf6"),
        cp_loss=468,
    )

    opponent = next(
        item
        for item in _families(cause, mover_is_user=False)
        if item.family == "unpunished_opponent_opportunity"
    )
    assert opponent.actor == "opponent"
    assert opponent.quality_id == UNPUNISHED_OPPONENT_QUALITY_ID
    comparison = build_teaching_opportunity_comparisons((opponent,))[0]
    assert comparison.played_summary == "They played Bf5 and missed the chance."
    assert comparison.stronger_summary.startswith(
        "They could have played Bc3, starting a line that takes your rook on h8"
    )
    assert "lost your rook" not in comparison.played_summary
    assert "strongest reply" not in comparison.memory_cue.lower()


def test_all_four_families_are_independently_shadow_and_copy_is_compact():
    quality_ids = (
        FORCED_MATE_STORY_QUALITY_ID,
        MULTI_MOVE_MATERIAL_QUALITY_ID,
        QUEEN_SAFETY_QUALITY_ID,
        UNPUNISHED_OPPONENT_QUALITY_ID,
    )
    for quality_id in quality_ids:
        assert grade_for(quality_id) == QualityGrade.SHADOW
        assert is_authorized(quality_id, QualitySurface.CAPTION) is False
        assert is_authorized(quality_id, QualitySurface.PLAN) is False


def test_incomplete_lines_create_no_teaching_opportunity():
    cause = build_verified_line_cause(
        fen_before="3rk3/8/8/3p4/8/8/8/3QK3 w - - 0 1",
        played_san="Qxd5",
        best_move_san="Qa1",
        pv_after_played=("not-a-move",),
        pv_after_best=("Kf7",),
        cp_loss=800,
        include_branch_evidence=True,
    )
    assert cause is None


def test_comparison_lines_replay_legally_from_the_same_root():
    cause = _cause(
        fen_before="r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        played_san="Rg4",
        best_move_san="Nf4+",
        pv_after_played=("Rf8", "Rxg7", "Rxf3", "Kg2"),
        pv_after_best=("Kh6", "Nf5#"),
        cp_loss=10173,
    )
    comparison = build_teaching_opportunity_comparisons(
        tuple(
            item
            for item in _families(cause)
            if item.family == "forced_mate_story"
        )
    )[0]
    for line in (
        comparison.played_line_moves,
        comparison.stronger_line_moves,
    ):
        board = chess.Board(cause.branch_evidence.played_trace.initial_fen)
        for san in line:
            board.push_san(san)


def _shadow_row(*, source_ply, actor="player", cause_kind="missed_forced_mate"):
    cause = _cause(
        fen_before="r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        played_san="Rg4",
        best_move_san="Nf4+",
        pv_after_played=("Rf8", "Rxg7", "Rxf3", "Kg2"),
        pv_after_best=("Kh6", "Nf5#"),
        cp_loss=10173,
    )
    comparison = build_teaching_opportunity_comparisons(
        tuple(
            item
            for item in _families(cause, mover_is_user=(actor == "player"))
            if item.family == "forced_mate_story"
        )
    )[0].contract_dict()
    comparison.update(
        {
            "source_ply": source_ply,
            "actor": actor,
            "cause_kind": cause_kind,
            "story_key": (
                f"{source_ply:02x}" + ("a" if actor == "player" else "b") * 62
            )[:64],
            "opportunity_fingerprint": (
                f"{source_ply:02x}"
                + ("c" if cause_kind == "missed_forced_mate" else "d") * 62
            )[:64],
        }
    )
    return comparison


def test_consecutive_mate_proofs_for_same_payoff_side_are_one_episode():
    # Player misses mate; on the very next ply the opponent allows the same
    # player-side mate. Those are two descriptions of one forcing episode.
    summary = build_teaching_opportunity_shadow_summary(
        (
            _shadow_row(
                source_ply=20,
                actor="player",
                cause_kind="missed_forced_mate",
            ),
            _shadow_row(
                source_ply=21,
                actor="opponent",
                cause_kind="allowed_forced_mate",
            ),
        )
    )

    assert summary["raw_count"] == 2
    assert summary["candidate_count"] == 1
    assert summary["deduplicated_by_family"]["forced_mate_story"] == 1


def test_mate_dedup_does_not_merge_opposite_sides_or_separate_episodes():
    opposite_sides = build_teaching_opportunity_shadow_summary(
        (
            _shadow_row(source_ply=20),
            _shadow_row(
                source_ply=21,
                actor="player",
                cause_kind="allowed_forced_mate",
            ),
        )
    )
    separate_episode = build_teaching_opportunity_shadow_summary(
        (
            _shadow_row(source_ply=20),
            _shadow_row(
                source_ply=22,
                actor="opponent",
                cause_kind="allowed_forced_mate",
            ),
        )
    )

    assert opposite_sides["candidate_count"] == 2
    assert separate_episode["candidate_count"] == 2


def test_shadow_summary_rejects_tampered_proof_identity():
    row = _shadow_row(source_ply=20)
    row["proof"]["version"] = "unreviewed.v999"

    with pytest.raises(ReviewContractViolation, match="Shadow contract is invalid"):
        build_teaching_opportunity_shadow_summary((row,))


def test_shared_pipeline_collects_review_shadow_only_when_explicitly_requested():
    kwargs = {
        "fen_before": "r5nr/pp4pp/n2N4/3N3k/7b/4BP2/PPP5/6RK w - - 2 26",
        "played_san": "Rg4",
        "mover_is_user": True,
        "mover_is_white": True,
        "user_color": "white",
        "full_move_number": 26,
        "move_history_san": [],
        "best_move_san": "Nf4+",
        "cp_loss": 10173,
        "pv_after_played": ["Rf8", "Rxg7", "Rxf3", "Kg2"],
        "pv_after_best": ["Kh6", "Nf5#"],
        "allow_fresh_engine_verification": False,
    }

    default_decision = build_move_teaching_decision(
        MoveInputs(**kwargs), CrossMoveState()
    )
    review_decision = build_move_teaching_decision(
        MoveInputs(**kwargs, collect_teaching_opportunity_shadow=True),
        CrossMoveState(),
    )

    assert default_decision.teaching_opportunity_comparisons == ()
    assert {
        item.family for item in review_decision.teaching_opportunity_comparisons
    } == {"forced_mate_story"}
