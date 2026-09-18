"""The opening claim we can stand behind, and the three we cannot.

`services/opening_deviation.py` has recorded since May, on 98.9% of analyses,
exactly where a player left theory and what the book plays instead. Nothing in
the coaching path ever read it: `classify_opening_knowledge` works from board
geometry -- a flank pawn pushed two squares, a knight retreating -- so 81% of
opening_knowledge observations are the `unverified_hint` shrug while 4,005
named, checkable deviations sit in the database.

This connects them, and the interesting part is what it refuses to say.
Measured on production 2026-09-18:

    stored deviations                              4,005
    cost >= 100cp                                    494    (87% cost less)
    ...and the book move is also the engine's best   181

Mohit's own d3 Italian leaves book, recurs 41 times, and is completely sound.
A detector firing on "you left theory" would scold people for good moves
almost nine times in ten. And in the 63% where a costly deviation's book move
is NOT the engine's pick, naming it would point at a move that is not even
best -- one real case castled in the Italian for -567cp where the book says c3
and the engine says Bxf7. That is how king_safety reached 75.4% precision and
shadow.

So this fires about 181 times corpus-wide. Small, and true.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.cognitive_gap_subtypes import (  # noqa: E402
    LEFT_BOOK_MIN_CP_LOSS,
    LEFT_BOOK_SUBTYPE,
    classify,
)


def _ctx(move_number=4, played="Nxe5", book="c3"):
    return {"opening_deviation": {
        "in_book_through_user_move": move_number - 1,
        "deviation": {
            "user_move_number": move_number,
            "played_san": played,
            "expected_san": book,
            "last_opening_name": "Italian Game",
        },
    }}


def _mv(move_number=4, cp_loss=354, best="c3"):
    return {"move_number": move_number, "cp_loss": cp_loss, "best_move": best}


def _classify(mv, ctx):
    return classify("opening_knowledge", mv, None, None, context=ctx)


def test_the_claim_fires_when_all_three_conditions_hold():
    subtype, severity = _classify(_mv(), _ctx())
    assert subtype == LEFT_BOOK_SUBTYPE
    assert severity == "critical"


def test_leaving_book_for_free_is_not_a_mistake():
    """62.6% of real deviations cost under 30cp. The d3 Italian is sound."""
    for cp in (0, 5, 15, 29, 60, LEFT_BOOK_MIN_CP_LOSS - 1):
        subtype, _ = _classify(_mv(cp_loss=cp), _ctx())
        assert subtype is None, f"fired on a {cp}cp deviation"


def test_it_stays_silent_when_the_book_move_is_not_the_best_move():
    """The 63% case. Naming the book move there points at a move that is not
    even the strongest available, which is confident and wrong."""
    subtype, _ = _classify(_mv(best="Bxf7"), _ctx(book="c3"))
    assert subtype is None


def test_it_only_fires_on_the_move_that_actually_left_book():
    for n in (3, 5, 12):
        subtype, _ = _classify(_mv(move_number=n), _ctx(move_number=4))
        assert subtype is None, f"fired on move {n}"


def test_no_deviation_means_no_claim():
    for ctx in (None, {}, {"opening_deviation": None},
                {"opening_deviation": {"deviation": None}}):
        assert _classify(_mv(), ctx)[0] is None


def test_check_and_mate_marks_do_not_break_the_comparison():
    """Book stores `Qh5+`, the engine stores `Qh5`. Same move."""
    subtype, _ = _classify(_mv(best="Qh5"), _ctx(book="Qh5+"))
    assert subtype == LEFT_BOOK_SUBTYPE


def test_severity_follows_the_cost():
    assert _classify(_mv(cp_loss=120), _ctx())[1] == "moderate"
    assert _classify(_mv(cp_loss=300), _ctx())[1] == "critical"


def test_a_missing_or_unusable_cp_loss_never_fires():
    for cp in (None, "", "lots"):
        assert _classify({"move_number": 4, "cp_loss": cp, "best_move": "c3"},
                         _ctx())[0] is None


def test_the_other_opening_classifiers_still_run():
    """This is an addition, not a replacement -- the geometry heuristics keep
    whatever coverage they had for moves that are not the deviation."""
    subtype, _ = _classify(_mv(move_number=9), _ctx(move_number=4))
    assert subtype is None  # not the deviation, and no geometry match either
    import io
    src = io.open(BACKEND / "services" / "cognitive_gap_subtypes.py",
                  encoding="utf-8").read()
    assert "CLASSIFIER_REGISTRY.get(missed_pattern)" in src


def test_the_authorization_is_registered_and_deliberately_silent():
    """Shadow until a reviewed packet exists. Registering it as anything else
    would skip the exact process that keeps 75%-precision detectors quiet.
    """
    from services.detector_quality import gap_quality_id, get_authorization

    quality_id = gap_quality_id("opening_knowledge", LEFT_BOOK_SUBTYPE)
    auth = get_authorization(quality_id)
    assert auth.grade.value == "shadow"
    assert auth.limitations, "the limits are the honest part; keep them"


def test_the_stored_deviation_reaches_the_classifier():
    """It is a game-level fact; the per-move view cannot see it."""
    import io

    src = io.open(BACKEND / "services" / "move_observation_deriver.py",
                  encoding="utf-8").read()
    assert "opening_deviation: Optional[Dict[str, Any]] = None" in src
    assert 'context={"opening_deviation": opening_deviation}' in src
