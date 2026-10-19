"""An endgame a curriculum can point at must always resolve to a lesson.

On 2026-10-19 twenty-four practice positions were appended to six lessons
without the fields the content contract requires. The validator duly marked
all six unpublishable, `get_lesson` then returned None for them,
`resolve_content_ref` returned None, and `resolve_endgame_destination`
raised -- so `/api/coach/personal-curriculum?surface=home` answered 500 for
every player whose next step was one of those six. Seven percent of accounts
were affected and the deploy gate caught it, not a test.

`test_public_endgame_catalog_contains_only_verified_lessons` already notices
that lessons went missing. It does not say what the loss costs, so nothing
connected a content edit to a dead home page. This closes that gap: the
reference a curriculum hands out must survive the whole lookup, because the
caller treats failure as a broken contract rather than as missing content.
"""
import pytest

from services.endgame_theory_service import (
    _CONTENT_REF_INDEX,
    get_lesson,
    resolve_content_ref,
)
from services.personal_curriculum import (
    LessonCapability,
    resolve_endgame_destination,
)


@pytest.mark.parametrize("content_ref", sorted(_CONTENT_REF_INDEX))
def test_every_curriculum_endgame_reference_reaches_a_lesson(content_ref):
    resolved = resolve_content_ref(content_ref)
    assert resolved is not None, (
        f"{content_ref!r} is offered to players but no longer resolves. "
        "The usual cause is a lesson that the content validator marked "
        "unpublishable, which makes the home curriculum return a 500."
    )
    assert get_lesson(resolved["category_key"], resolved["lesson_key"])

    destination = resolve_endgame_destination(
        content_ref,
        capability=LessonCapability.TEACH,
    )
    assert destination.href.startswith("/endgames/")
    assert destination.content_id == resolved["lesson_id"]
