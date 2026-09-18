"""A card may not ask one thing and be marked by another.

Measured on the five piece-safety positions served to one account on
2026-09-17, before this existed:

    legal  keep-every-piece-safe  accepted by the grader
      22            9                      1   (Qe5)
      28            8                      1   (exd4)
      28            5                      1   (Qxg5)
      37           19                      1   (Bf7+)
      33           12                      1   (d4)

The card printed "Which move keeps every piece safe?". On the fourth position
eighteen moves answered that question correctly and were marked wrong.

Two separate faults produced it, and both are locked here:

1. The question was hardcoded in the adapter and in PrescribedTraining.jsx,
   so every category printed the piece-safety question -- including the six
   that are nothing to do with piece safety.
2. The grader chose its family from whether the stored row happened to carry
   a `quality_id`. Community rows never do, so all of them fell through to
   single-best grading beneath a question promising otherwise.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.lesson_question_spec import (  # noqa: E402
    ANY_SAFE,
    EXACTLY_ONE,
    MORE_THAN_ONE,
    SINGLE_BEST,
    BY_CATEGORY,
    canonical_category,
    describe,
    get_spec,
    spec_or_fallback,
)


def test_every_category_we_serve_has_a_spec():
    """The categories that actually carry stored positions.

    Counted on production 2026-09-17 across community_puzzles and
    community_training_positions. The 17 keys in tactical_patterns.json
    (knight_fork, skewer, deflection...) hold zero positions between them, so
    they are deliberately absent -- a spec for them would be authored content
    no player can reach.
    """
    for category in (
        "piece_safety",
        "calculation_depth",
        "missed_tactic",
        "tactical_oversight",
        "king_safety",
        "opening_knowledge",
        "endgame_technique",
    ):
        assert get_spec(category) is not None, category


def test_the_spellings_the_two_pools_use_resolve_to_one_spec():
    """`issue_type` and `pattern_type` disagree; callers should not have to."""
    assert canonical_category("undefended_piece") == "piece_safety"
    assert canonical_category("hanging_piece") == "piece_safety"
    assert canonical_category("poor_piece_safety") == "piece_safety"
    assert canonical_category("tactical_miss") == "missed_tactic"
    assert get_spec("undefended_piece") is get_spec("piece_safety")


def test_a_question_promising_several_moves_is_graded_as_several():
    """The whole point. Only an any_safe category may say more than one works."""
    for category, spec in BY_CATEGORY.items():
        promises_many = MORE_THAN_ONE in spec.task_line
        assert promises_many == (spec.accepts == ANY_SAFE), (
            f"{category}: task line and grading family disagree"
        )


def test_a_single_best_category_never_implies_a_choice():
    for category, spec in BY_CATEGORY.items():
        if spec.accepts != SINGLE_BEST:
            continue
        assert spec.task_line == EXACTLY_ONE, category


def test_an_any_safe_category_has_honest_wording_for_a_best_move_surface():
    """The same concept is trained on two graders.

    /training/prescribed marks the one stored best move. Printing "more than
    one move works" there would be the identical fault in a new place, so an
    any_safe spec has to carry wording for that surface too.
    """
    for category, spec in BY_CATEGORY.items():
        if spec.accepts != ANY_SAFE:
            continue
        assert spec.best_move_question, category
        assert spec.question_for(SINGLE_BEST) == spec.best_move_question
        assert spec.task_line_for(SINGLE_BEST) == EXACTLY_ONE
        assert MORE_THAN_ONE not in spec.question_for(SINGLE_BEST)


def test_no_category_counts_the_players_options_at_them():
    """The counter sentence is gone and does not come back.

    "Of the 38 moves you can play here, 13 leave a piece where it can be
    taken" reads as "the other 25 are fine" on a card that then accepted one.
    It is also the maths-instead-of-language failure this product keeps
    repeating.
    """
    for category, spec in BY_CATEGORY.items():
        blob = f"{spec.question} {spec.task_line} {spec.best_move_question}"
        assert "moves you can play" not in blob, category
        assert not any(ch.isdigit() for ch in blob), (
            f"{category}: a lesson question should not contain a count"
        )


def test_no_reason_option_is_answerable_without_the_board():
    """The pair it replaced was "keeps my pieces protected" against "it looks
    active, even if a piece can be taken". Nobody picks the second, so the
    question measured nothing. Every option must now be a heuristic a real
    600-1500 player holds.
    """
    give_aways = (
        "even if a piece can be taken",
        "even if it can be taken",
        "i am not sure",
    )
    for category, spec in BY_CATEGORY.items():
        assert len(spec.reason_options) >= 2, category
        for option in spec.reason_options:
            lowered = option.label.lower()
            for phrase in give_aways:
                assert phrase not in lowered, f"{category}: {option.label}"

    ids = {
        option.id
        for spec in BY_CATEGORY.values()
        for option in spec.reason_options
    }
    assert "looks_active" not in ids, "the transparently-wrong option is gone"


def test_every_option_that_can_be_wrong_carries_its_own_correction():
    """The coaching travels with the option.

    `teaching_engine` used to hold the corrections in a lookup of its own,
    keyed by reason id. Changing the options there would have orphaned them in
    silence -- the follow-up comes back empty and nothing fails. Authoring
    them beside the option is what stops that, so it is checked.
    """
    from services.lesson_question_spec import FALLBACK, ReasonOption

    specs = dict(BY_CATEGORY)
    specs["<fallback>"] = FALLBACK  # it was authored as bare tuples once
    for category, spec in specs.items():
        for option in spec.reason_options:
            assert isinstance(option, ReasonOption), f"{category}: {option!r}"
            assert option.belief_lead, f"{category}/{option.id}"
        for option in spec.reason_options[1:]:
            assert option.correction, f"{category}/{option.id}"
            assert option.misconception_id, f"{category}/{option.id}"


def test_every_string_a_player_reads_passes_the_coaching_lint():
    """scripts/pwc_coaching_lint.py, pointed at this copy.

    It catches snake_case leaking through, jargon above the 600-1500 band, a
    pawn described as a piece, and empty fields that render as nothing. The
    lint already guards the caption templates; there is no reason the lesson
    questions should be the one coaching surface it never sees.
    """
    from importlib.machinery import SourceFileLoader

    from services.lesson_question_spec import FALLBACK

    lint = SourceFileLoader(
        "pwc_coaching_lint", str(BACKEND / "scripts" / "pwc_coaching_lint.py")
    ).load_module()

    # Every band, not just the default wording -- a band variant is a string
    # a player reads, and sourcing the band list from the picker means a band
    # added there cannot slip past the lint unlinted.
    from services.primary_weakness_picker import RATING_BANDS

    problems = []
    for spec in list(BY_CATEGORY.values()) + [FALLBACK]:
        texts = [spec.question, spec.task_line, spec.reason_prompt,
                 spec.best_move_question]
        texts += [spec.question_for_band(band) for band in RATING_BANDS]
        for option in spec.reason_options:
            texts += [option.label, option.belief_lead, option.correction]
        for text in texts:
            if not text:
                continue
            for problem in lint.lint_text(text, expect_text=True) or []:
                problems.append(f"{spec.category or 'fallback'}: {problem}")
    assert not problems, problems


def test_the_engine_no_longer_keeps_its_own_concept_reason_text():
    src = io.open(
        BACKEND / "services" / "teaching_engine.py", encoding="utf-8"
    ).read()
    assert "activity_before_safety" not in src
    assert "Activity was the right instinct" not in src
    assert "reason_belief_lead" in src and "reason_correction" in src


def test_each_category_asks_its_own_question():
    """One hardcoded prompt used to serve all of them."""
    questions = [spec.question for spec in BY_CATEGORY.values()]
    assert len(set(questions)) == len(questions)


def test_an_unknown_category_promises_nothing():
    spec = spec_or_fallback("something_we_have_never_described")
    assert spec.accepts == SINGLE_BEST
    assert MORE_THAN_ONE not in spec.task_line
    assert get_spec("something_we_have_never_described") is None


def test_the_grader_routes_on_the_spec_not_on_a_stored_quality_id():
    """The wedge, in the source.

    `_diagnostic_quality_id` is set only on own-game rows that carry their own
    proof. Community rows -- which is what almost everyone is served -- have
    none, so keying the any_safe grader on it meant the loose grader existed
    and never ran for anybody.
    """
    src = io.open(
        BACKEND / "services" / "personalized_lesson_adapter.py", encoding="utf-8"
    ).read()
    assert 'accepts_any_safe = str(item.get("_accepts") or "") == ANY_SAFE' in src
    assert 'if item.get("_diagnostic_quality_id") or accepts_any_safe:' in src, (
        "an any_safe item must reach the safety grader even with no quality_id"
    )


def test_the_adapter_does_not_keep_its_own_copy_of_the_question():
    """The property is "the spec owns the wording", not one literal line.

    This used to assert `"prompt": spec.question`. The prompt now resolves
    through `question_for_band` so an expert does not read the beginner
    sentence, which is the same property one indirection further on — so the
    check moved rather than relaxed: the spec still owns every word, and no
    question string may be written in the adapter.
    """
    src = io.open(
        BACKEND / "services" / "personalized_lesson_adapter.py", encoding="utf-8"
    ).read()
    assert "Which move keeps every piece safe?" not in src
    assert "question = spec.question_for_band(band)" in src
    assert '"prompt": question,' in src
    # No literal question may be authored here — the spec is the only owner.
    assert "Play a move that" not in src


def test_the_workspace_renders_the_task_line_not_a_count():
    src = io.open(
        BACKEND.parent
        / "frontend"
        / "src"
        / "components"
        / "training"
        / "PersonalizedLessonWorkspace.jsx",
        encoding="utf-8",
    ).read()
    assert "leave a piece where it can be taken" not in src
    assert "item?.task_line" in src


def test_the_pattern_page_no_longer_asks_an_ungradeable_question():
    """"Which of your pieces has no defender?" is a fine coaching question and
    an impossible one to mark, because the page grades a move.
    """
    src = io.open(
        BACKEND.parent / "frontend" / "src" / "pages" / "PrescribedTraining.jsx",
        encoding="utf-8",
    ).read()
    assert "Which of your pieces has no defender?" not in src
    assert "currentPuzzle?.question" in src, (
        "the backend serves the question now; the map is only a fallback"
    )


def test_ask_one_question_narrows_instead_of_restating_the_prompt():
    src = io.open(
        BACKEND / "services" / "teaching_engine.py", encoding="utf-8"
    ).read()
    assert "Which of your moves stays off them?" not in src, (
        "that restated the prompt and handed over the answer set at once"
    )
    assert "_one_question_about_the_board" in src


def test_describe_is_stable_for_the_admin_surfaces():
    doc = describe()
    assert set(doc) == set(BY_CATEGORY)
    for category, entry in doc.items():
        assert entry["question"]
        assert entry["accepts"] in (ANY_SAFE, SINGLE_BEST)
        assert entry["expected_reason"] == BY_CATEGORY[category].expected_reason
        assert entry["reason_options"][0]["id"] == entry["expected_reason"]


def test_an_expert_is_not_told_to_check_whether_his_piece_hangs():
    """A 2196 and a 900 were reading the identical sentence.

    Measured 2026-09-18: the strongest and weakest accounts on the platform
    were both served "Play a move that leaves nothing of yours hanging." The
    material differs — each gets positions from their own games — but the
    question did not, and to a 2100 that reads as a product that has not
    noticed who he is. The picker's own impact table already weights
    piece_safety 1.00 for a beginner and 0.30 for an expert.
    """
    from services.lesson_question_spec import spec_or_fallback

    spec = spec_or_fallback("piece_safety")
    beginner = spec.question_for_band("beginner")
    expert = spec.question_for_band("expert")
    advanced = spec.question_for_band("advanced")

    assert beginner == spec.question
    assert expert != beginner, "an expert must not read the beginner question"
    assert advanced != beginner
    # The expert wording must not reduce it to a one-move oversight, which is
    # the thing that is almost never their actual error.
    assert "hanging" not in expert.lower()


def test_an_unknown_band_falls_back_rather_than_failing():
    from services.lesson_question_spec import spec_or_fallback

    spec = spec_or_fallback("piece_safety")
    for band in (None, "", "unknown", "?"):
        assert spec.question_for_band(band) == spec.question


def test_only_categories_whose_meaning_changes_carry_a_band_variant():
    """The single_best six all say "find it", which is as true at 900 as 2100."""
    from services.lesson_question_spec import BY_CATEGORY, spec_or_fallback

    for category, spec in BY_CATEGORY.items():
        if category == "piece_safety":
            continue
        assert spec.question_for_band("expert") == spec.question, category


def test_the_descriptor_actually_asks_for_the_band():
    """A bank nothing reads is the failure this whole file exists to stop."""
    src = io.open(
        BACKEND / "services" / "personalized_lesson_adapter.py", encoding="utf-8"
    ).read()
    assert "question_for_band(band)" in src
    assert '"prompt": question,' in src
    assert "get_coaching_rating" in src


def test_a_band_variant_describes_the_grader_it_is_actually_marked_by():
    """The band may change the wording. It may not change the promise.

    Caught during review of this very change: the first expert wording read
    "still leaves everything defended once the line plays out", and the
    grader (`grade_destination_safety_candidate`) checks one thing -- whether
    the piece you MOVED survives the full exchange on the square it LANDED
    on, within a 150cp floor.

    So "everything" was wrong (it is one piece), "defended" was wrong (a
    piece can be safe and undefended), and a wording like "comes out even"
    would have been wrong the other way, since the floor permits giving a
    pawn. Every one of those makes the printed question and the grader
    disagree, which is the single fault this whole file exists to prevent.
    """
    from services.destination_safety_detector import SEE_FLOOR_CP
    from services.lesson_question_spec import BY_CATEGORY, _QUESTION_BY_BAND

    # If the floor moves to 0 the wording below has to be revisited, so tie
    # the claim to the constant rather than leaving it a stale comment.
    assert SEE_FLOOR_CP > 100, (
        "the floor permits losing a pawn; a band variant saying the exchange "
        "comes out even would over-promise"
    )

    over_promises = ("everything", "every piece", "all your pieces", "nothing else")
    for category, by_band in _QUESTION_BY_BAND.items():
        assert category in BY_CATEGORY, category
        for band, wording in by_band.items():
            low = wording.lower()
            for phrase in over_promises:
                assert phrase not in low, (
                    f"{category}/{band}: the grader checks the moved piece on "
                    f"its landing square, not {phrase!r}"
                )
            assert "comes out even" not in low, f"{category}/{band}"
            # It must still be about where the move lands, like the task line
            # that accompanies it on the card.
            assert "lands" in low or "landing" in low, (
                f"{category}/{band}: destination safety is a claim about the "
                "square the piece arrives on; say so"
            )


def test_advanced_and_expert_are_not_given_a_distinction_we_cannot_grade():
    """They share a grader, so they share a sentence.

    Two near-identical strings would read as a difference the product can
    make and cannot -- the same filler failure as 190 golden_* concept ids
    sharing one generic text.
    """
    from services.lesson_question_spec import spec_or_fallback

    spec = spec_or_fallback("piece_safety")
    assert spec.question_for_band("advanced") == spec.question_for_band("expert")
