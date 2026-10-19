"""You cannot walk into a mate you are already in.

`classify_severity` carries an escape hatch that forces "blunder" when the
eval after a move is a mate score, whatever the centipawn loss. It read only
the position after the move, so a player who was ALREADY being mated tripped
it on every legal move -- 568 of 973 such cards in a 1,200-game sample, about
half of them at eight pieces or more, and on 392 of them the pipeline's own
practical severity already said "good".

The hatch keeps doing its original job (fb_a9ac9f02affa: the stored cp_loss
is small while the eval is a mate, because the player really did step into
the net). These tests pin both sides of that line, and the unchanged
behaviour when the pre-move eval is unknown.
"""
from services.severity import (
    MATE_SENTINEL_CP,
    classify_severity,
    classify_severity_practical,
)


def test_stepping_into_a_mating_net_is_still_a_blunder():
    """The case the hatch was built for. Positive control."""
    result = classify_severity(
        cp_loss=50,
        mover_is_user=True,
        user_pre_eval_cp=-120,                       # losing, but not mated
        user_post_eval_cp=-MATE_SENTINEL_CP - 100,   # mated now
    )
    assert result.walked_into_mate is True
    assert result.tier == "blunder"


def test_a_move_made_while_already_being_mated_is_not_a_blunder():
    """The defect. Mate was unavoidable before the move was played."""
    result = classify_severity(
        cp_loss=10,                                  # under the 30cp floor
        mover_is_user=True,
        user_pre_eval_cp=-MATE_SENTINEL_CP - 400,    # already being mated
        user_post_eval_cp=-MATE_SENTINEL_CP - 100,
    )
    assert result.walked_into_mate is False
    assert result.tier == "good"
    # and it now agrees with what the centipawn loss alone would say
    assert result.tier == classify_severity(
        cp_loss=10, mover_is_user=True
    ).tier


def test_already_being_mated_still_reports_a_real_centipawn_loss():
    """The fix must not launder genuinely bad moves into 'good'.

    Severity falls back to cp_loss, so a large loss is still a blunder --
    what changes is that the mate score alone no longer decides it.
    """
    result = classify_severity(
        cp_loss=900,
        mover_is_user=True,
        user_pre_eval_cp=-MATE_SENTINEL_CP - 400,
        user_post_eval_cp=-MATE_SENTINEL_CP - 100,
    )
    assert result.walked_into_mate is False
    assert result.tier == "blunder"


def test_an_unknown_pre_move_eval_behaves_exactly_as_before():
    """Every existing caller omits the argument; none may change."""
    result = classify_severity(
        cp_loss=50,
        mover_is_user=True,
        user_post_eval_cp=-MATE_SENTINEL_CP - 100,
    )
    assert result.walked_into_mate is True
    assert result.tier == "blunder"


def test_the_practical_classifier_already_called_these_moves_fine():
    """Independent corroboration, from a classifier this change never touches.

    Practical severity scores the move by the swing in win probability. A
    player already being mated has nothing left to lose, so it reads such a
    move as 'good' -- which is what the displayed severity was contradicting
    on 392 of the 568 affected cards.
    """
    practical = classify_severity_practical(
        cp_loss=10,
        mover_is_user=True,
        mover_is_white=True,
        eval_before_cp=-MATE_SENTINEL_CP - 400,
        eval_after_cp=-MATE_SENTINEL_CP - 100,
    )
    assert practical.state_before == "losing"
    assert practical.state_after == "losing"
    assert practical.practical_tier == "good"
