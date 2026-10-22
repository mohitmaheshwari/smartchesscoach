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


def _splice() -> str:
    text = V5.read_text(encoding="utf-8")
    start = text.index("# The LLM caption, if the analysis wrote one")
    return text[start:start + 2600]


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
        body = _splice()
        assert "_llm_cap or _decision.text.caption" in body, (
            "a refused LLM caption must leave the deterministic one standing")

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

    def test_the_visual_fields_still_come_from_the_decision(self):
        body = _splice()
        assert '"arrows": _decision.visual.arrows' in body
        assert '"best_move_arrows": _decision.visual.best_move_arrows' in body

    def test_the_facts_still_come_from_the_decision(self):
        text = V5.read_text(encoding="utf-8")
        assert "caption_facts = _decision.debug_facts" in text
