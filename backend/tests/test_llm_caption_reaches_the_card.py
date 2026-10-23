"""The LLM caption has to reach the card, and only the caption.

Three separate fixes in this repo have been correct code that reached
nothing: a rival template family, the wrong rule, a whitelist. The shape is
always the same -- the fact is computed, the wire is wrong, and the failure
is silent. This file is about the wire.

It also pins the boundary Mohit set: "arrows and all were building
excellent, so no code changes there please". The LLM caption replaces TEXT.
Arrows, highlights and best_move_arrows come from the rule cascade and are
untouched.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

V5 = Path(__file__).resolve().parents[1] / "services" / \
    "game_decryption_v5_service.py"


FRAMEWORK = Path(__file__).resolve().parents[1] / "services" / \
    "framework.py"


def _splice() -> str:
    """The wire now lives in framework.decide, not in the renderer.

    Mohit: "six writers, no man, no, clearly mentioned." The renderer used
    to call the cascade, look the LLM caption up and choose between them;
    all three moved inside the one face. These assertions follow the code
    rather than the file it used to live in -- the wire is still the thing
    being pinned, and it is still the thing that has silently failed three
    times in this repo.
    """
    text = FRAMEWORK.read_text(encoding="utf-8")
    start = text.index("def decide(")
    return text[start:text.index("def facts_for_move(")]


class TestTheWireIsRight:
    def test_it_looks_the_move_up_the_way_eval_lookup_is_keyed(self):
        """eval_lookup is keyed by the first FOUR fen fields. The first
        version of this splice used the full FEN, which finds nothing and
        fails silently -- the same shape as the last three wiring bugs."""
        body = _splice()
        assert "split()[:4]" in body, (
            "a full-FEN lookup misses every row and nothing reports it")

    def test_it_reads_the_field_the_worker_writes(self):
        assert '"llm_caption"' in _splice()

    def test_an_empty_or_missing_caption_falls_back(self):
        """A refused LLM caption must leave the cascade's words standing.

        Written as a guard now rather than an `or`: the face overwrites the
        caption only when it HAS one, which is the same contract expressed
        in the place the code moved to."""
        body = _splice()
        assert "if llm:" in body
        assert "decision.text.caption = llm" in body
        assert "decision.text.caption = None" not in body

    def test_the_rule_name_records_that_the_llm_wrote_it(self):
        """A card whose text came from a model must say so, or nobody can
        tell which surface produced a bad sentence."""
        assert "LLM_CAPTION" in _splice()


class TestItReplacesTextAndNothingElse:
    def test_arrows_are_not_touched_by_the_splice(self):
        body = _splice()
        # the splice may MENTION arrows in its comment, but must not assign
        assignments = re.findall(r'"(arrows|highlight_squares|'
                                 r'best_move_arrows)":\s*([^\n,]+)', body)
        for key, value in assignments:
            assert "_llm" not in value, (
                f"{key} must come from the rule cascade, not the LLM")

    def test_the_face_never_assigns_a_visual_field(self):
        """Stronger than the assertion it replaces. The renderer used to
        copy the decision's arrows into a payload, so the old test checked
        where they came FROM. The face returns the decision itself, so the
        test is that it assigns nothing visual at all."""
        body = _splice()
        for field in ("arrows", "highlight_squares", "best_move_arrows"):
            assert f"visual.{field} =" not in body, field

    def test_the_renderer_still_reads_the_visuals_from_the_decision(self):
        text = V5.read_text(encoding="utf-8")
        assert '"arrows": _decision.visual.arrows' in text
        assert '"best_move_arrows": _decision.visual.best_move_arrows' in text

    def test_the_facts_still_come_from_the_decision(self):
        text = V5.read_text(encoding="utf-8")
        assert "caption_facts = _decision.debug_facts" in text
