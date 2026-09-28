"""The denominator must be engine-gated, or it measures the detector.

docs/two_layer_coaching_scope.md. Measured on production 2026-09-28:

    loose  "a fork-shaped move exists"      12,013 chances, 11.2% taken,
                                            player spread 0.09 - 0.14
    gated  "the engine's best move IS one"   1,384 chances, 51.7% taken,
                                            player spread 0.38 - 0.58

The loose version looked like a finding. It is a fact about how generous
`detect_knight_fork` is. Every fixture below is a real position from a real
game, because a hand-built position whose move is not actually punished tests
nothing -- that mistake has already been made in this codebase.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from services.opportunity_gate import (  # noqa: E402
    MIN_CHANCES_TO_JUDGE,
    NOT_USABLE_AS_OPPORTUNITIES,
    observe,
    pooled_knowledge,
    shape_of_best_move,
    weakest_pattern,
)

# The engine's best move IS a fork, and the player played it.
TOOK_FEN = "rn1qk2r/pp3p2/2p1p3/3pPn2/3P4/2P2NB1/PP2Q1PP/RN3RK1 b kq - 0 17"
TOOK_BEST = "f5g3"

# The engine's best move IS a fork, and the player played something else.
MISSED_FEN = "r1bqk2r/ppp2ppp/2n2n2/2b1p3/4P3/5NP1/PPP2PBP/RNBQ1RK1 b kq - 0 7"
MISSED_BEST = "d8d1"
MISSED_PLAYED = "c5f2"

# THE TRAP. A fork-shaped move exists here (d8d1) but the engine wants d8e7.
# This position is why the module exists: counted loosely it is an opportunity
# the player "missed", and it is not an opportunity at all.
LOOSE_FEN = "r1bqk2r/ppp2ppp/2n5/4p3/4P1n1/5NP1/PPP3BP/RNBQ1RK1 b kq - 2 9"
LOOSE_BEST = "d8e7"
LOOSE_FORK_SHAPED = "d8d1"


def test_a_fork_the_engine_wanted_is_an_opportunity():
    assert shape_of_best_move(TOOK_FEN, TOOK_BEST) == "fork"


def test_a_fork_shaped_move_the_engine_did_NOT_want_is_not_one():
    """The 11.2% trap, held in a test. The shape exists in this position -- the
    assertion below proves it -- and it is still not an opportunity, because the
    engine wanted a different move."""
    from services import shape_detectors as sd
    import chess

    board = chess.Board(LOOSE_FEN)
    shaped = set()
    for fn in (sd.detect_knight_fork, sd.detect_bishop_fork, sd.detect_rook_fork,
               sd.detect_queen_fork, sd.detect_pawn_fork):
        for e in fn(board) or ():
            if e.get("executing_move"):
                shaped.add(str(e["executing_move"]))
    assert LOOSE_FORK_SHAPED in shaped, "fixture no longer contains the shape"

    assert shape_of_best_move(LOOSE_FEN, LOOSE_BEST) is None


def test_no_engine_move_means_no_opportunity():
    """A shape that exists is not a shape that was right. With nothing to gate
    against, the honest answer is silence."""
    assert shape_of_best_move(TOOK_FEN, None) is None
    assert shape_of_best_move(TOOK_FEN, "") is None


def test_an_illegal_or_unparseable_best_move_is_refused():
    assert shape_of_best_move(TOOK_FEN, "a1a8") is None
    assert shape_of_best_move(TOOK_FEN, "not-a-move") is None
    assert shape_of_best_move("not a fen", TOOK_BEST) is None


def test_taking_it_means_playing_the_engine_move():
    assert observe(TOOK_FEN, TOOK_BEST, TOOK_BEST) == {
        "pattern": "fork", "took": True}


def test_missing_it_is_recorded_as_a_chance_not_dropped():
    """A miss is the numerator's absence, not the denominator's. Dropping it
    would make every player look perfect.

    The pattern NAME is deliberately not asserted here -- see the precedence
    test below. What matters for the rate is that this counts as a chance and
    that it was not taken."""
    result = observe(MISSED_FEN, MISSED_BEST, MISSED_PLAYED)
    assert result is not None
    assert result["took"] is False
    assert result["pattern"]


def test_a_move_matching_two_shapes_gets_one_deterministic_name():
    """MISSED_BEST is Qxd1, which both forks and creates a pin. A move can be
    several things at once, so the order in the gate decides the name -- and it
    must decide the SAME way every time or the drill choice wobbles between
    runs. Alignments are asked first because they are the largest patterns.

    The name only chooses the exercise. The rate does not depend on it."""
    first = observe(MISSED_FEN, MISSED_BEST, MISSED_PLAYED)["pattern"]
    again = observe(MISSED_FEN, MISSED_BEST, MISSED_PLAYED)["pattern"]
    assert first == again == "pin"


def test_another_sound_move_still_counts_as_missing_THIS_chance():
    """The question is whether he saw this shape. A good move that found another
    way does not answer it."""
    assert observe(TOOK_FEN, TOOK_BEST, "e8f8")["took"] is False


def test_a_position_with_no_shape_is_not_a_chance():
    quiet = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    assert observe(quiet, "e2e4", "e2e4") is None


def test_the_rate_is_withheld_until_there_are_enough_chances():
    """Below the bar a rate is noise with a decimal point. The measured bar is
    the lowest at which the pooled rate behaves like a trait."""
    thin = [{"pattern": "fork", "took": True}] * (MIN_CHANCES_TO_JUDGE - 1)
    assert pooled_knowledge(thin)["judgeable"] is False
    enough = [{"pattern": "fork", "took": True}] * MIN_CHANCES_TO_JUDGE
    assert pooled_knowledge(enough)["judgeable"] is True


def test_pooling_counts_every_shape_together():
    rows = ([{"pattern": "fork", "took": True}] * 6
            + [{"pattern": "free_piece", "took": False}] * 4)
    pooled = pooled_knowledge(rows)
    assert pooled["chances"] == 10
    assert pooled["took"] == 6
    assert pooled["missed"] == 4
    assert pooled["by_pattern"]["free_piece"] == {"chances": 4, "took": 0}


def test_no_rate_is_reported_without_an_underscore():
    """The no-numbers rule: nothing here may be rendered, so the rate is marked
    internal the way every other service in this codebase marks them."""
    pooled = pooled_knowledge([{"pattern": "fork", "took": True}] * 5)
    for key, value in pooled.items():
        if isinstance(value, float):
            assert key.startswith("_"), key


def test_the_drill_is_chosen_from_the_weakest_shape():
    rows = ([{"pattern": "fork", "took": False}] * 8
            + [{"pattern": "free_piece", "took": True}] * 8)
    assert weakest_pattern(pooled_knowledge(rows)) == "fork"


def test_the_drill_ignores_a_shape_with_too_few_chances():
    """One missed skewer is not a curriculum."""
    rows = ([{"pattern": "fork", "took": False}] * 8
            + [{"pattern": "skewer", "took": False}])
    assert weakest_pattern(pooled_knowledge(rows)) == "fork"


def test_pin_and_skewer_are_found_by_asking_the_RIGHT_question():
    """`detect_pin` fired 5,286 times and named a move ZERO times, because a pin
    is a state and you cannot take a state. I read that as "pin is silent" and
    declared it so. Asked through verify_created_alignment -- does THIS MOVE
    create one -- pin is the largest pattern we have, at 2,771 gated chances
    against free_piece's 2,047."""
    from services.opportunity_gate import _CREATED_ALIGNMENTS

    assert "pin" in _CREATED_ALIGNMENTS
    assert "skewer" in _CREATED_ALIGNMENTS


def test_the_unusable_detectors_are_named_rather_than_forgotten():
    """Fifteen detectors fire and never name a move -- they describe a position
    rather than a move, so there is nothing for a player to take. Listed so the
    next reader does not have to rediscover why they are absent."""
    assert "weak_squares" in NOT_USABLE_AS_OPPORTUNITIES
    assert "king_pawn_lifted" in NOT_USABLE_AS_OPPORTUNITIES
    assert len(NOT_USABLE_AS_OPPORTUNITIES) >= 15
    # and the ones that DO work must not be in that list
    for usable in ("pin", "skewer", "fork", "free_piece", "hidden_attack"):
        assert usable not in NOT_USABLE_AS_OPPORTUNITIES, usable


def test_the_new_patterns_are_wired():
    """hidden_attack produces more gated chances (492) than knight_fork (454),
    and I had not wired it."""
    from services.opportunity_gate import _SHAPE_DETECTORS

    names = {name for name, _fn in _SHAPE_DETECTORS}
    assert {"hidden_attack", "remove_the_guard", "force_the_king"} <= names
