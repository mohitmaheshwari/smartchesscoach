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
    assert comparison.stronger_summary.endswith("was the checkmating finish.")


def test_material_family_requires_and_replays_more_than_one_capture():
    cause = _cause(
        fen_before="2k3rr/ppp2R2/2np4/3N3p/1PPbP3/P2PB1qb/4K3/1R1Q4 b - - 1 24",
        played_san="Qxe3+",
        best_move_san="Bg4+",
        pv_after_played=("Nxe3", "Ne5", "Qb3", "Nxf7"),
        pv_after_best=("Kd2", "Bxe3+", "Nxe3", "Bxd1"),
        cp_loss=516,
    )

    opportunity = next(
        item
        for item in _families(cause)
        if item.family == "multi_move_material_accounting"
    )
    assert opportunity.quality_id == MULTI_MOVE_MATERIAL_QUALITY_ID
    assert len(cause.best_captures) == 3
    assert opportunity.visible_material_edge_cp >= 300
    assert opportunity.settled_material_edge_cp >= 300
    assert opportunity.consequence_owner == "player"
    comparison = build_teaching_opportunity_comparisons((opportunity,))[0]
    assert comparison.played_line_moves == cause.played_line_san
    assert len(comparison.played_line_moves) == 5
    assert "whole capture sequence" in comparison.headline.lower()
    rendered = str(comparison.contract_dict()).lower()
    assert "loses material for you" in comparison.played_summary.lower()
    assert "wins material for you" in comparison.stronger_summary.lower()
    assert all(word not in rendered for word in ("centipawn", "ahead", "behind", "level"))


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


def test_delayed_voluntary_queen_walk_in_is_not_blamed_on_the_root_move():
    cause = _cause(
        fen_before="1k3r2/1ppbr2p/p1nb4/3p2p1/3P1p2/2PQ1P1P/PP1N2P1/2KR2N1 w - - 0 21",
        played_san="Ne2",
        best_move_san="Qf1",
        pv_after_played=("Bf5", "Nxf4", "Bxd3", "Nxd3"),
        pv_after_best=("Rfe8", "Nb3", "Bf5", "h4"),
        cp_loss=392,
    )

    assert all(
        item.family != "queen_safety_or_greedy_capture"
        for item in _families(cause)
    )


def test_cooperative_opponent_line_is_not_presented_as_a_causal_chance():
    cause = _cause(
        fen_before="r3kbnr/pp1npp1p/2p5/8/3qB3/5Q2/PP1B1PPP/R3K1NR w KQkq - 0 13",
        played_san="Bf5",
        best_move_san="Bc3",
        pv_after_played=("e6", "Ne2", "Qxb2", "Bc3"),
        pv_after_best=("Qa4", "Bxh8", "Ngf6", "Bxf6"),
        cp_loss=468,
    )

    assert all(
        item.family != "unpunished_opponent_opportunity"
        for item in _families(cause, mover_is_user=False)
    )


def test_direct_opponent_capture_is_counterfactual_and_actor_safe():
    cause = _cause(
        fen_before="r1bqr1k1/pppn1pbp/3p1np1/3Pp3/4PB2/2NB1N2/PPP1QPPP/R4RK1 b - - 0 9",
        played_san="c6",
        best_move_san="exf4",
        pv_after_played=("dxc6", "bxc6", "Bg3", "Nh5"),
        pv_after_best=("Qd2", "Nh5", "g4", "Nhf6"),
        cp_loss=528,
    )

    opponent = next(
        item
        for item in _families(cause, mover_is_user=False)
        if item.family == "unpunished_opponent_opportunity"
    )
    assert opponent.actor == "opponent"
    assert opponent.quality_id == UNPUNISHED_OPPONENT_QUALITY_ID
    assert opponent.consequence_ply == 1
    comparison = build_teaching_opportunity_comparisons((opponent,))[0]
    assert comparison.played_summary == "They played c6 and missed the chance."
    assert comparison.stronger_summary == (
        "They could have played exf4, taking your bishop on f4 immediately."
    )
    assert "strongest reply" not in comparison.memory_cue.lower()


def test_greedy_queen_capture_describes_both_visible_lines_not_a_false_balance():
    cause = _cause(
        fen_before="6k1/2p4r/r7/pp1P2B1/2Q5/6P1/PP1K1P2/R7 w - - 0 30",
        played_san="Qxb5",
        best_move_san="Qg4",
        pv_after_played=("Rb6", "Qe8+", "Kg7", "Rc1"),
        pv_after_best=("Rh4", "Bxh4+", "Kf8", "Qc8+"),
        cp_loss=760,
    )

    queen = next(
        item
        for item in _families(cause)
        if item.family == "queen_safety_or_greedy_capture"
    )
    comparison = build_teaching_opportunity_comparisons((queen,))[0]
    rendered = str(comparison.contract_dict()).lower()

    assert comparison.headline == "Count beyond the queen capture"
    assert "shown line" in comparison.played_summary.lower()
    assert "shown line" in comparison.stronger_summary.lower()
    assert "no better off" not in rendered
    assert "material stays level" not in rendered


def test_allowed_mate_alternative_is_not_claimed_to_stop_all_future_mate():
    cause = _cause(
        fen_before="4Q2k/8/5K2/8/8/8/8/6r1 b - - 44 77",
        played_san="Rg8",
        best_move_san="Kh7",
        pv_after_played=("Qh5#",),
        pv_after_best=("Qe4+", "Kg8", "Qa8+", "Kh7"),
        cp_loss=9990,
    )

    mate = next(
        item for item in _families(cause) if item.family == "forced_mate_story"
    )
    comparison = build_teaching_opportunity_comparisons((mate,))[0]

    assert comparison.stronger_summary == (
        "Kh7 avoids the checkmate shown in this replay."
    )
    assert "stops" not in comparison.stronger_summary.lower()


def test_missed_mate_that_plays_stalemate_teaches_the_actual_draw():
    cause = _cause(
        fen_before="8/8/8/8/4k2K/5q2/8/8 b - - 15 77",
        played_san="Kf4",
        best_move_san="Qg2",
        pv_after_played=(),
        pv_after_best=("Kh5", "Kf5", "Kh4", "Qh2#"),
        cp_loss=9970,
    )

    mate = next(
        item for item in _families(cause) if item.family == "forced_mate_story"
    )
    comparison = build_teaching_opportunity_comparisons((mate,))[0]

    assert mate.played_terminal_state == "stalemate"
    assert comparison.headline == "This move ended the game in stalemate"
    assert comparison.played_summary == (
        "Kf4 leaves them no legal move, so the game is drawn."
    )
    assert comparison.stronger_summary.endswith("Qh2# was the checkmating finish.")
    assert "legal move" in comparison.memory_cue.lower()


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
