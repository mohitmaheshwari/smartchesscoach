"""A proven forced mate can be asked for as mate training.

The proof existed and the label did not. `forced_mate_puzzle_proof` and
`back_rank_mate_puzzle_proof` have been admitting positions for months, each
with its own independent verifier, and every one of them was filed under the
broad category `missed_tactic` -- correctly, because that is the cognitive_gap
`analysis_interpreter` assigns on purpose. The consequence was that no query
could ask for a mate. Counted on the live pools 2026-10-13: 358 of 50,678
`community_puzzles` rows and 344 of 53,610 `community_training_positions` rows
carry a mate quality_id, and 0 rows in either pool carry a mate-ish value in
`issue_type`, `pattern_type`, `legacy_issue_type`, `theme`, `motif` or
`verified_admission.broad_category`. 702 proven mates, none findable.

So `forced_mate` is a label derived from the proof that is already stored, and
these tests lock the two halves that make it useful:

  * it is NARROWER than the category the row is filed under, never a
    replacement -- a mate keeps serving `missed_tactic` too, so nothing is
    taken out of a pool that exists today;
  * it is only ever satisfied by a proven mate, including when verified
    admission is switched off, where the generic filters return True for
    everything.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import chess
import pytest

from services.back_rank_mate_puzzle_proof import BACK_RANK_MATE_QUALITY_ID
from services.forced_mate_puzzle_proof import FORCED_MATE_QUALITY_ID
from services.lesson_question_spec import (
    SINGLE_BEST,
    accepts_many_moves,
    canonical_category,
    get_spec,
)
from services.puzzle_extraction_service import (
    FORCED_MATE_PATTERN,
    FORCED_MATE_QUALITY_IDS,
    GAP_TO_PWC_PATTERNS,
    forced_mate_candidate,
    forced_mate_mongo_clause,
    is_forced_mate_quality,
    pattern_pool_clause,
    stored_pattern_label,
    verdict_serves_pattern,
    verified_mongo_clause,
)
from services.verified_puzzle_admission import AdmissionStatus
from services.verified_puzzle_builder import build_position_verdict


# A mate in one that is not a back-rank mate, so the forced-mate prover owns
# it rather than the narrower back-rank one.
MATE_IN_ONE = "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"
# A rook mate reached over a stored continuation, not immediately.
LONGER_MATE = "6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1"
# The classic back-rank geometry, which the other prover claims.
BACK_RANK = "4r1k1/ppp2Npp/3r4/3n1R2/2B5/P7/2P3PP/4R1K1 w - - 3 21"


def _mate_verdict(fen: str, played: str, best: str, pv=()):
    return build_position_verdict(
        source_kind="mate_fixture",
        source_ref=f"mate-{fen}",
        move_evaluation={
            "fen_before": fen,
            "move": played,
            "best_move_san": best,
            "cp_loss": 500,
            "pv_after_best": list(pv),
        },
        broad_category="missed_tactic",
    )


def _row(verdict, fen, best, issue_type="missed_tactic"):
    # `stored_verdict_is_structurally_current` re-checks the stored answer
    # against the stored board, so a fixture row has to carry both.
    return {"fen": fen,
            "best_move_san": best,
            "issue_type": issue_type,
            "approved": True,
            "verified_admission": verdict.to_document()}


# ── the label comes from the proof, and only from the proof ────────────────

def test_the_label_names_the_existing_mate_quality_ids():
    assert FORCED_MATE_PATTERN == "forced_mate"
    assert set(FORCED_MATE_QUALITY_IDS) == {
        FORCED_MATE_QUALITY_ID, BACK_RANK_MATE_QUALITY_ID,
    }
    assert is_forced_mate_quality(FORCED_MATE_QUALITY_ID)
    assert is_forced_mate_quality(BACK_RANK_MATE_QUALITY_ID)
    assert not is_forced_mate_quality("gap:piece_safety:simple_hang")
    assert not is_forced_mate_quality(None)
    assert not is_forced_mate_quality("")


@pytest.mark.parametrize(
    "fen,played,best,pv,expected_quality",
    [
        (MATE_IN_ONE, "Qg5", "Qg7#", (), FORCED_MATE_QUALITY_ID),
        (LONGER_MATE, "Ra2", "Kg1", ("Kg1", "Kh8", "Ra8#"), FORCED_MATE_QUALITY_ID),
        (BACK_RANK, "Kf1", "Rxe8#", (), BACK_RANK_MATE_QUALITY_ID),
    ],
)
def test_a_proven_mate_is_served_under_the_mate_label(
    fen, played, best, pv, expected_quality
):
    verdict = _mate_verdict(fen, played, best, pv)
    assert verdict.status == AdmissionStatus.BROAD
    assert verdict.quality_id == expected_quality
    # The broad category underneath is untouched -- that is the point.
    assert verdict.broad_category == "missed_tactic"
    row = _row(verdict, fen, best)
    assert stored_pattern_label(row) == FORCED_MATE_PATTERN
    assert verdict_serves_pattern(row, FORCED_MATE_PATTERN) is True


def test_a_mate_still_serves_the_broad_category_it_is_filed_under():
    # Narrower, not instead of. A mate leaving the missed_tactic pool would
    # make 358 live rows unreachable from the only focus the picker produces
    # for them, which is strictly worse than the bug being fixed.
    row = _row(_mate_verdict(MATE_IN_ONE, "Qg5", "Qg7#"), MATE_IN_ONE, "Qg7#")
    assert verdict_serves_pattern(row, "missed_tactic") is True
    assert verdict_serves_pattern(row, FORCED_MATE_PATTERN) is True


def test_a_non_mate_proof_is_never_served_as_mate_training():
    # A hanging piece: real, provable, and not a mate.
    verdict = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="hang-1",
        move_evaluation={
            "fen_before": "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w - - 0 1",
            "move": "Nxe5",
            "best_move_san": "Nc3",
            "cp_loss": 300,
            "pv_after_best": [],
        },
        broad_category="piece_safety",
    )
    row = _row(
        verdict,
        "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w - - 0 1",
        "Nc3",
        issue_type="piece_safety",
    )
    assert not is_forced_mate_quality(verdict.quality_id)
    assert stored_pattern_label(row) == "piece_safety"
    assert verdict_serves_pattern(row, FORCED_MATE_PATTERN) is False


def test_an_unproven_row_is_not_served_as_mate_training():
    # No verdict at all: the legacy shape. The generic filters let these
    # through when enforcement is off; the mate label must not.
    legacy = {"issue_type": "missed_tactic", "approved": True}
    assert stored_pattern_label(legacy) == "missed_tactic"
    assert verdict_serves_pattern(legacy, FORCED_MATE_PATTERN) is False


def test_mate_label_holds_even_when_admission_is_not_enforced(monkeypatch):
    # verdict_serves_pattern returns True for EVERYTHING when enforcement is
    # off. A mate drill that quietly served non-mates in that mode would be a
    # worse lie than serving nothing, so the mate branch is checked first.
    monkeypatch.setenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "false")
    mate = _row(_mate_verdict(MATE_IN_ONE, "Qg5", "Qg7#"), MATE_IN_ONE, "Qg7#")
    legacy = {"issue_type": "missed_tactic", "approved": True}
    assert verdict_serves_pattern(mate, FORCED_MATE_PATTERN) is True
    assert verdict_serves_pattern(legacy, FORCED_MATE_PATTERN) is False
    # ...while the generic patterns keep their permissive behaviour.
    assert verdict_serves_pattern(legacy, "missed_tactic") is True
    # The pool clause still proves the mate without the enforcement clause.
    assert verified_mongo_clause("missed_tactic") == {}
    assert pattern_pool_clause(FORCED_MATE_PATTERN) == forced_mate_mongo_clause()


# ── the queries a pool is actually asked ───────────────────────────────────

def test_the_pool_query_asks_for_the_proof_not_the_stored_label():
    # The stored `issue_type` on every live mate row is `missed_tactic`, so a
    # query for `issue_type == "forced_mate"` matches nothing. That was the
    # whole bug; the clause must not reintroduce it.
    clause = pattern_pool_clause(FORCED_MATE_PATTERN)
    assert "issue_type" not in clause
    assert clause == {
        "verified_admission.quality_id": {"$in": list(FORCED_MATE_QUALITY_IDS)}
    }
    # Every other pattern is unchanged.
    assert pattern_pool_clause("piece_safety") == {"issue_type": "piece_safety"}
    assert pattern_pool_clause("missed_tactic") == {"issue_type": "missed_tactic"}


def test_the_mate_clause_is_selective_and_demands_a_current_verdict():
    clause = verified_mongo_clause(FORCED_MATE_PATTERN)
    assert clause["verified_admission.quality_id"] == {
        "$in": list(FORCED_MATE_QUALITY_IDS)
    }
    assert clause["approved"] is True
    # GENERIC rows have no proven answer, so they are excluded here even
    # though calculation_depth accepts them.
    assert clause["verified_admission.status"]["$in"] == [
        AdmissionStatus.SPECIFIC.value, AdmissionStatus.BROAD.value,
    ]
    # Every structural field the generic clause requires is still required.
    for field in (
        "verified_admission.admission_version",
        "verified_admission.source_fingerprint",
        "verified_admission.analysis_fingerprint",
        "verified_admission.reconstructed_fen",
        "verified_admission.played_move_uci",
        "verified_admission.acceptable_moves_uci.0",
    ):
        assert field in clause


def test_other_patterns_clauses_are_untouched():
    assert verified_mongo_clause("piece_safety") == verified_mongo_clause("piece_safety")
    for pattern in ("piece_safety", "missed_tactic", "calculation_depth"):
        clause = verified_mongo_clause(pattern)
        assert "verified_admission.quality_id" not in clause
        assert clause["$or"][0]["verified_admission.broad_category"] == pattern


def test_the_pwc_pool_is_asked_for_the_pattern_type_its_mates_carry():
    # All 344 proven mates in community_training_positions are filed under
    # pattern_type "missed_tactic" (counted 2026-10-13). That collection
    # answers only exact-match queries reliably, so the request names the
    # pattern_type and the proof narrows the result.
    assert GAP_TO_PWC_PATTERNS[FORCED_MATE_PATTERN] == ["missed_tactic"]
    pwc_row = {
        "fen": MATE_IN_ONE,
        "best_move_san": "Qg7#",
        "pattern_type": "missed_tactic",
        "approved": True,
        "verified_admission": _mate_verdict(
            MATE_IN_ONE, "Qg5", "Qg7#").to_document(),
    }
    assert stored_pattern_label(pwc_row) == FORCED_MATE_PATTERN
    assert verdict_serves_pattern(pwc_row, FORCED_MATE_PATTERN) is True


# ── the candidate test the own-game path uses ──────────────────────────────

def test_the_candidate_test_does_not_read_a_gap_label():
    # No cognitive_gap identifies a missed mate -- on the live mate rows it is
    # `missed_tactic` or `tactical_oversight`, neither of which means "there
    # was a mate here". So the candidate test asks the prover.
    assert forced_mate_candidate({
        "fen_before": MATE_IN_ONE,
        "best_move_san": "Qg7#",
        "pv_after_best": [],
        "cp_loss": 500,
        "cognitive_gap": "tactical_oversight",
    }) is True
    assert forced_mate_candidate({
        "fen_before": MATE_IN_ONE,
        "best_move_san": "Qg5",
        "pv_after_best": [],
        "cp_loss": 500,
        "cognitive_gap": "missed_tactic",
    }) is False


def test_the_candidate_test_survives_missing_and_junk_fields():
    for evaluation in (
        {},
        {"fen_before": "not a fen", "best_move_san": "Qg7#", "cp_loss": 500},
        {"fen_before": MATE_IN_ONE, "best_move_san": None, "cp_loss": 500},
        {"fen_before": MATE_IN_ONE, "best_move_san": "Qg7#", "cp_loss": None},
        {"fen_before": MATE_IN_ONE, "best_move_san": "Qg7#", "cp_loss": "abc"},
    ):
        assert forced_mate_candidate(evaluation) is False

    # A junk continuation is coerced away rather than crashing, and a mate the
    # best move delivers on its own does not need one.
    assert forced_mate_candidate({
        "fen_before": MATE_IN_ONE, "best_move_san": "Qg7#",
        "pv_after_best": "not a list", "cp_loss": 500,
    }) is True
    # ...but a longer mate with no usable continuation is NOT claimed.
    assert forced_mate_candidate({
        "fen_before": LONGER_MATE, "best_move_san": "Kg1",
        "pv_after_best": "not a list", "cp_loss": 500,
    }) is False


def test_the_candidate_test_keeps_the_provers_cp_loss_floor():
    # detect_missed_mate requires cp_loss >= 100 so two near-equal mating
    # moves are not called a missed mate. The candidate test inherits it
    # rather than restating it.
    low = dict(fen_before=MATE_IN_ONE, best_move_san="Qg7#",
               pv_after_best=[], cp_loss=99)
    high = dict(low, cp_loss=100)
    assert forced_mate_candidate(low) is False
    assert forced_mate_candidate(high) is True


def test_the_own_game_matcher_routes_a_mate_request_to_the_prover():
    from services.coaching_puzzle_service import CoachingPuzzleService

    service = CoachingPuzzleService(db=None)
    mate_move = {
        "fen_before": MATE_IN_ONE,
        "best_move_san": "Qg7#",
        "pv_after_best": [],
        "cp_loss": 500,
        # The gap says nothing about a mate, which is exactly the point.
        "cognitive_gap": "tactical_oversight",
    }
    quiet_move = dict(mate_move, best_move_san="Qg5")
    assert service._move_matches_weakness(mate_move, FORCED_MATE_PATTERN) is True
    assert service._move_matches_weakness(quiet_move, FORCED_MATE_PATTERN) is False
    # And the broad request still behaves as it always did.
    assert service._move_matches_weakness(
        mate_move, "tactical_oversight") is True


def test_a_freshly_adjudicated_mate_matches_a_mate_request():
    from services.coaching_puzzle_service import (
        _verdict_matches_requested,
        _verified_pattern_from_verdict,
    )

    verdict = _mate_verdict(MATE_IN_ONE, "Qg5", "Qg7#")
    assert _verdict_matches_requested(verdict, FORCED_MATE_PATTERN) is True
    assert _verdict_matches_requested(verdict, "missed_tactic") is True
    assert _verified_pattern_from_verdict(verdict) == FORCED_MATE_PATTERN

    hang = build_position_verdict(
        source_kind="mate_fixture",
        source_ref="hang-2",
        move_evaluation={
            "fen_before": "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w - - 0 1",
            "move": "Nxe5",
            "best_move_san": "Nc3",
            "cp_loss": 300,
            "pv_after_best": [],
        },
        broad_category="piece_safety",
    )
    assert _verdict_matches_requested(hang, FORCED_MATE_PATTERN) is False


# ── what the card prints has to match what the grader accepts ──────────────

def test_the_card_asks_for_one_move_because_the_grader_accepts_one():
    spec = get_spec(FORCED_MATE_PATTERN)
    assert spec is not None, "a label with no question prints the generic fallback"
    assert spec.category == FORCED_MATE_PATTERN
    assert spec.accepts == SINGLE_BEST
    assert accepts_many_moves(FORCED_MATE_PATTERN) is False
    assert spec.task_line_for(SINGLE_BEST) == "One move is right here."
    # Measured: 10 of the 100 mate-in-one positions in the live pool have more
    # than one legal mating move, while the stored verdict accepts exactly
    # one. So the question may not promise that any mate will be marked right.
    assert "any" not in spec.question.lower()
    assert len(spec.reason_options) >= 2
    assert spec.expected_reason == spec.reason_options[0].id


def test_the_mate_label_is_a_category_not_an_alias():
    # _ALIASES is applied BEFORE BY_CATEGORY, so an alias of the same name
    # would shadow the spec and make it unreachable while appearing to exist.
    assert canonical_category(FORCED_MATE_PATTERN) == FORCED_MATE_PATTERN


def test_the_prescribed_page_announces_the_mate_lesson():
    from services.coaching_puzzle_service import (
        DEFAULT_COACHING,
        PATTERN_COACHING,
        WEAKNESS_TO_PATTERN_TYPES,
        WEAKNESS_TO_PUZZLE_THEMES,
    )

    coaching = PATTERN_COACHING.get(FORCED_MATE_PATTERN)
    assert coaching is not None, "without copy the page announces the default lesson"
    assert coaching != DEFAULT_COACHING
    assert coaching["lesson"] and coaching["what_to_look_for"]
    # The pool maps have to name values something is actually tagged with,
    # or the page loads empty under a confident banner.
    assert WEAKNESS_TO_PATTERN_TYPES[FORCED_MATE_PATTERN] == ["missed_tactic"]
    assert WEAKNESS_TO_PUZZLE_THEMES[FORCED_MATE_PATTERN] == [
        "mateIn1", "mateIn2", "mateIn3",
    ]


def test_the_lesson_copy_stays_in_easy_english():
    from services.coaching_puzzle_service import PATTERN_COACHING

    text = " ".join(str(v) for v in PATTERN_COACHING[FORCED_MATE_PATTERN].values())
    text += " " + get_spec(FORCED_MATE_PATTERN).question
    text += " " + " ".join(
        o.label + " " + o.belief_lead + " " + o.correction
        for o in get_spec(FORCED_MATE_PATTERN).reason_options
    )
    lowered = text.lower()
    for jargon in (
        "zugzwang", "zwischenzug", "prophylaxis", "fianchetto", "centipawn",
        "forced mate", "quiescence", "tempo", "initiative", "cp loss",
    ):
        assert jargon not in lowered, f"jargon reached the player: {jargon}"
    # No numbers: a count is the one thing a drill card must not promise.
    assert not any(ch.isdigit() for ch in text)


# ── the positions these fixtures stand for are really mates ────────────────

def test_the_fixtures_are_checkmates_by_maths_not_by_label():
    for fen, best in ((MATE_IN_ONE, "Qg7#"), (BACK_RANK, "Rxe8#")):
        board = chess.Board(fen)
        board.push(board.parse_san(best))
        assert board.is_checkmate()
    board = chess.Board(LONGER_MATE)
    for san in ("Kg1", "Kh8", "Ra8#"):
        board.push(board.parse_san(san))
    assert board.is_checkmate()
