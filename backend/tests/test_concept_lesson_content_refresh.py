"""A concept lesson must notice when its own words change.

Two defects, found together on 2026-09-25 because Mohit's piece-safety lesson
was printing reason options that had been replaced in code weeks earlier. The
replacement exists because "nobody picks the second, so the question measured
nothing" -- and no player had ever seen the better pair.

  1. teaching_engine.start_personalized_lesson resolved a fresh descriptor for
     `endgame` only, and the refresh below it is gated on that descriptor
     being non-None. Concept sessions could never refresh.

  2. The concept descriptor took content_version from a hand-maintained
     `_meta.version` in the pattern file ("2.0.0"). The question, task line
     and reason options come from lesson_question_spec, a different module, so
     editing them moved nothing and a stale session compared equal to a fresh
     one.

Measured cost: 95 of 174 production learning_sessions were serving superseded
text, the oldest created 2026-08-31.
"""
import inspect
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import services.personalized_lesson_adapter as adapter  # noqa: E402
import services.teaching_engine as teaching_engine  # noqa: E402


def test_concept_sessions_are_resolved_for_refresh():
    """Defect 1. The refresh is gated on a resolved descriptor, so concept has
    to be in the set that resolves one."""
    source = inspect.getsource(teaching_engine.start_personalized_lesson)
    match = re.search(r"if content_kind in \(([^)]*)\)", source)
    assert match, "no content_kind membership test found; refresh gate changed shape"
    kinds = match.group(1)
    assert '"concept"' in kinds, kinds
    assert '"endgame"' in kinds, kinds


def test_the_review_reshape_stays_endgame_only():
    """That reshape keeps the last item and relabels it, which is meaningless
    for a concept lesson whose items are separate positions from real games."""
    source = inspect.getsource(teaching_engine.start_personalized_lesson)
    assert 'content_kind == "endgame" and bool((params or {}).get("review"))' in source


def test_content_version_is_hashed_not_declared():
    """Defect 2. A hand-maintained file version cannot track words that live in
    another module."""
    source = inspect.getsource(adapter._concept_descriptor)
    assert "_meta" not in source.split("content_version")[1][:200], (
        "content_version is reading a declared version again")
    assert "_content_version({" in source


def test_every_printed_field_is_in_the_fingerprint():
    """If the card prints it and lesson_question_spec owns it, changing it must
    move content_version -- otherwise the edit ships to nobody."""
    source = inspect.getsource(adapter._concept_descriptor)
    fingerprint = source.split("question_spec_fingerprint = {")[1].split("}")[0]
    for field in ("question", "task_line", "reason_prompt", "reason_options",
                  "accepts", "band"):
        assert field in fingerprint, field


def test_items_are_not_in_the_fingerprint():
    """Items are positions from the player's own games. Hashing them would
    regenerate the lesson whenever they play and lose progress mid-attempt for
    no teaching reason."""
    source = inspect.getsource(adapter._concept_descriptor)
    fingerprint = source.split("question_spec_fingerprint = {")[1].split("}")[0]
    assert '"items"' not in fingerprint


def test_hash_moves_when_the_words_move():
    a = adapter._content_version({"pattern": {"name": "x"},
                                  "question": {"question": "old"}})
    b = adapter._content_version({"pattern": {"name": "x"},
                                  "question": {"question": "new"}})
    assert a != b
    assert re.fullmatch(r"[0-9a-f]{16}", a), a


def test_hash_is_stable_for_identical_content():
    payload = {"pattern": {"name": "x"}, "question": {"question": "same"}}
    assert adapter._content_version(payload) == adapter._content_version(payload)
