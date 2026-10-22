"""The LLM writes the caption; it may not add a chess fact the engine did not.

Mohit, 2026-10-22: "the answer for caption is LLM based, now", and earlier:
"the LLM would be only responsible for text generation, every detail would
come from our engine, nothing else".

That sentence is the whole safety story and this file enforces it. The model
may choose which fact matters, order the facts and phrase them. It may not
introduce a square, a piece or a move that is not in the bundle.

WHY A MODEL IS USED AT ALL, measured on Mohit's Bd6+ card with the same
model and only the facts differing:

    facts the pipeline had    "Bd6+ lets your bishop be taken by Qxd6. Qxg8
                               was better, sacrificing your queen to capture
                               a rook."
    plus the refutation        "...Qxg8 instead sacrifices your queen for the
                               rook and threatens mate with Bd6#."

The first is the vague caption already shipping. The model was never the
bottleneck; the facts were.

A REFUSAL IS NOT SILENCE. When validate() rejects a caption, `caption` comes
back None and the deterministic caption the V5 layer already produced stays
exactly as it is. Coverage is first-class here: a mediocre true sentence
beats nothing, and this layer may only ever replace, never erase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.llm_caption import build_facts, validate  # noqa: E402

PURPOSES = [
    {"kind": "wins_hanging_piece", "tier": 3,
     "facts": {"piece": "queen", "square": "d8"},
     "proof": "after the move, their queen on d8 is attacked and undefended"},
]
FACTS = build_facts("Bd6+", "Qxg8", PURPOSES, severity="blunder",
                    punishment_line=["Qxd6", "Qxg8+", "Kc7"],
                    opp_reply_is_clear=True)


class TestItAcceptsWhatTheFactsSupport:
    def test_a_caption_built_only_from_the_facts(self):
        assert validate(FACTS, (
            "Bd6+ gives up the bishop after Qxd6. Qxg8 was better because "
            "their queen on d8 is undefended.")) is None

    def test_a_piece_named_by_its_own_san_is_allowed(self):
        """Bd6+ IS a bishop move. The first version of this check rejected
        the word "bishop" on this card -- the model reading the facts
        correctly and the validator being wrong about what they contain."""
        assert validate(FACTS, (
            "The bishop on d6 is taken by Qxd6, so Qxg8 was stronger here "
            "for you.")) is None


class TestItRefusesWhatTheyDoNot:
    def test_an_invented_move(self):
        why = validate(FACTS, "Bd6+ loses to Rxh7 and then Nf6 mates soon.")
        assert why and "Rxh7" in why

    def test_an_invented_piece_and_square(self):
        why = validate(FACTS, "Bd6+ hangs a knight on f4 for nothing at all.")
        assert why and "knight" in why

    def test_talking_in_evaluations(self):
        """The repo has a commit hook against this phrasing: centipawns are
        not material. An earlier regex missed it because \\d+\\s* does not
        span the decimal in "4.4 pawns"."""
        phrase = "Bd6+ drops about 4.4 pawns of material here."  # allow-cp-loss-phrase
        assert validate(FACTS, phrase) == "talks in evaluations"

    def test_empty(self):
        assert validate(FACTS, "") == "empty"
        assert validate(FACTS, "   ") == "empty"

    def test_truncated(self):
        """A model that spends its budget thinking returns almost nothing,
        and an empty answer invents no chess -- so it would pass a check
        that only looked for inventions. That happened once already."""
        assert validate(FACTS, "Bd6+ is bad.") == "truncated"

    def test_too_long_for_a_caption(self):
        long = "Bd6+ gives up the bishop after Qxd6 and " + \
            "their queen on d8 is undefended " * 12
        why = validate(FACTS, long)
        assert why and "too long" in why


class TestTheFactBundleCarriesOnlyEngineTruth:
    def test_it_never_puts_evaluations_in_front_of_the_model(self):
        """Centipawns in the bundle come back as "you lost 4.4 pawns"."""
        flat = str(FACTS).lower()
        assert "cp_loss" not in flat
        assert "centipawn" not in flat

    def test_it_carries_whether_the_punishment_is_forced(self):
        """The only field separating "they win your rook" from "they might"."""
        assert FACTS["their_best_reply_is_clearly_best"] is True

    def test_purposes_arrive_ranked_with_their_proof(self):
        got = FACTS["what_the_better_move_achieves"]
        assert got and got[0]["detail"]
        assert got[0]["importance"] == 3

    def test_an_empty_bundle_is_refused_before_any_call(self):
        """No facts means nothing to write FROM, so the deterministic
        caption stands rather than the model being asked to improvise."""
        import asyncio
        from services.llm_caption import write_caption
        empty = build_facts("e4", "d4", [])
        out = asyncio.get_event_loop().run_until_complete(
            write_caption(empty)) if False else None
        # run without an event loop dependency:
        out = asyncio.run(write_caption(empty))
        assert out["caption"] is None
        assert out["refused"] in ("disabled", "no facts to write from")
