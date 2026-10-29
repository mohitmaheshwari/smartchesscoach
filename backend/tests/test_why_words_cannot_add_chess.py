"""The model phrases the engine's finding and may not add to it.

No LLM is called here. `write()` is one `call_llm` and a validator, and the
validator is the whole safety story, so it is what these exercise -- with the
sentences a model actually produced, not invented ones.

The two failures that shaped this module both have a case below:

  "Nc3 attacks your queen" for a FORCES_RETREAT. gpt-6-luna produced this from
  "Nc3 chases your queen" when `caption_polish` was pointed at the why
  sentences. The queen is OBLIGED TO MOVE; "attacks" is a weaker, different
  claim, and token containment cannot see it because neither word is a chess
  token.

  "Rxa7 wins their queen." refused as "truncated". caption_polish.validate has
  an absolute five-word floor, so every faithful rewrite of a four-word answer
  is rejected by construction -- it can never ship the clearest answers this
  feature produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.punishment_resolver import Punishment  # noqa: E402
from services.why_words import (  # noqa: E402
    _RELATION,
    _mechanism_of,
    build_facts,
    conveys_relation,
    validate,
)


def _facts(mechanism, direction="received", **kw):
    # Every build_facts argument comes out of kw BEFORE Punishment is built:
    # popping them afterwards passes them on to Punishment, which took
    # `mover_is_user` as an unexpected keyword and failed five tests.
    played_san = kw.pop("played_san", "Nf6")
    mover_is_user = kw.pop("mover_is_user", True)
    p = Punishment(direction=direction, mechanism=mechanism,
                   agent_move=kw.pop("agent_move", "Nc3"),
                   payoff_cp=kw.pop("payoff_cp", 300),
                   line=kw.pop("line", ["Nc3", "Qd8"]), **kw)
    return build_facts(p, played_san, mover_is_user=mover_is_user)


class TestItNeverShipsAChessClaimTheEngineDidNotMake:
    def test_an_invented_move_is_refused(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        assert validate(f, "After Nf6, Nc3 wins your rook, so play Bb5 first.")

    def test_an_invented_piece_is_refused(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        why = validate(f, "After Nf6, Nc3 wins your rook and traps the bishop.")
        assert why and "invented" in why

    def test_the_facts_own_pieces_and_moves_are_allowed(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        assert validate(f, "After Nf6, Nc3 wins your rook.") is None

    def test_a_san_implies_its_own_piece(self):
        """"Nc3" is a knight move, so the word "knight" is in the facts even
        though the string is not -- llm_caption._implied_pieces, reused."""
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        assert validate(f, "After Nf6, their knight takes your rook.") is None

    def test_it_refuses_to_talk_in_evaluations(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        assert validate(f, "After Nf6, Nc3 wins your rook, about 5 pawns of "
                            "material.")  # allow-cp-loss-phrase


class TestTheRelationHasToSurvive:
    MEASURED = "After Nf6, Nc3 attacks your queen."

    def test_the_measured_softening_is_refused(self):
        f = _facts("FORCES_RETREAT", victim_piece="queen")
        why = validate(f, self.MEASURED)
        assert why and "FORCES_RETREAT" in why

    def test_the_sentence_it_was_softened_from_passes(self):
        f = _facts("FORCES_RETREAT", victim_piece="queen")
        assert validate(f, "After Nf6, Nc3 chases your queen away.") is None

    def test_any_wording_that_keeps_the_meaning_passes(self):
        """The guard lists alternatives, not a required phrase: these are the
        same finding and the model should be free to choose between them."""
        f = _facts("FORCES_RETREAT", victim_piece="queen")
        for said in ("After Nf6, Nc3 forces your queen to move.",
                     "After Nf6, your queen has to move again.",
                     "After Nf6, Nc3 drives your queen back."):
            assert validate(f, said) is None, said

    def test_a_trapped_piece_may_not_become_a_mere_attack(self):
        f = _facts("TRAPPED", victim_piece="knight", victim_square="c6")
        assert validate(f, "After Nf6, Nc3 attacks your knight on c6.")
        assert validate(
            f, "After Nf6, your knight on c6 has nowhere safe to go.") is None

    def test_a_mate_may_not_become_a_material_claim(self):
        """This one found a real bug rather than confirming a guard: the first
        version of `conveys_relation` tested substrings, and "wins MATErial"
        satisfied the MATE alternative "mate". The check that exists to stop a
        mate becoming a material claim was passing that exact sentence."""
        f = _facts("MATE", victim_piece=None)
        assert validate(f, "After Nf6, Nc3 wins material.")
        assert validate(f, "After Nf6, Nc3 leads to checkmate.") is None
        assert validate(f, "After Nf6, Nc3 is mate.") is None
        assert validate(f, "After Nf6, your king is mated.") is None

    def test_a_mate_names_the_king_as_a_fact(self):
        """Containment refused "their king is mated" until the facts said
        "king" -- correct by its own rule and wrong about the position, since
        a mate always involves exactly that piece. It is the engine supplying
        the fact, not the model adding one."""
        assert _facts("MATE")["the_piece_involved"] == "your king"
        assert _facts("MATE", direction="missed")["the_piece_involved"] \
            == "their king"

    def test_a_named_mate_victim_is_not_overwritten(self):
        assert _facts("MATE", victim_piece="rook")["the_piece_involved"] \
            == "your rook"

    # The two sentences below are verbatim output from gpt-6-luna on real
    # positions, both of which passed validation when WINS_MATERIAL had no
    # relation guard. Containment was satisfied because each names the piece;
    # neither says anything is won. That mechanism is behind 191 of 255
    # answers, so the hole was in three quarters of the output.
    DROPPED_THE_CLAIM = (
        "After a4, f4+ is available. In the line, the king takes on e3, "
        "then their rook goes to d5.",
        "After their opponent played Nb4, Rxb2 is the move involving "
        "their knight.",
    )

    def test_naming_the_piece_is_not_claiming_it_is_won(self):
        f = _facts("WINS_MATERIAL", agent_move="Rxb2", played_san="Nb4",
                   victim_piece="knight", line=["Nxd3", "cxd3"])
        why = conveys_relation("WINS_MATERIAL", self.DROPPED_THE_CLAIM[1])
        assert why and "WINS_MATERIAL" in why

    def test_a_line_narration_cannot_be_built_at_all(self):
        """The relation guard does NOT catch this one, and cannot: "the king
        TAKES on e3" matches the win verb while what is taken is the king's own
        recapture. No word-level check ties a verb to the right piece.

        What stops it is that the line is not in the facts, so every SAN in it
        and the word "king" are both inventions."""
        f = _facts("WINS_MATERIAL", agent_move="f4+", played_san="a4",
                   victim_piece="rook", line=["Kf2", "fxe3+", "Kxe3", "Rd5"])
        assert conveys_relation("WINS_MATERIAL",
                                self.DROPPED_THE_CLAIM[0]) is None
        why = validate(f, self.DROPPED_THE_CLAIM[0])
        assert why and "invented" in why

    def test_the_line_is_never_handed_to_the_model(self):
        """It is the resolver's proof, which it has already replayed. Handing
        over a move list and asking why a move was bad is the failure
        llm_caption.py documents, and this file cited it and then did it."""
        import json
        f = _facts("WINS_MATERIAL", victim_piece="rook",
                   line=["Kf2", "fxe3+", "Kxe3", "Rd5"])
        flat = json.dumps(f)
        for san in ("Kf2", "fxe3+", "Kxe3", "Rd5"):
            assert san not in flat, san
        assert not any("line" in k for k in f)

    def test_the_ways_a_person_says_it_all_pass(self):
        for said in ("After Nf6, Nc3 wins your rook.",
                     "After Nf6, your rook is taken.",
                     "After Nf6, you lose the rook.",
                     "After Nf6, Nc3 captures your rook.",
                     "After Nf6, your rook drops."):
            assert conveys_relation("WINS_MATERIAL", said) is None, said

    def test_an_unknown_mechanism_is_not_guarded(self):
        """A mechanism with no stated relation must not be silently refused --
        that would turn every future mechanism into silence."""
        assert conveys_relation("SOMETHING_NEW", "anything at all") is None
        assert conveys_relation("", "anything at all") is None

    def test_every_relation_round_trips_to_its_mechanism(self):
        """`relation` is what the facts carry, and the guard has to find the
        mechanism back from it. A typo in either dict would silently disable
        the guard, which is the kind of failure that looks like a pass."""
        for mech in _RELATION:
            f = _facts(mech, victim_piece="queen")
            assert _mechanism_of(f) == mech, mech

    def test_the_mechanism_name_is_never_in_the_facts(self):
        """Jargon the model could copy into the answer. It gets the relation in
        plain words instead."""
        import json
        for mech in _RELATION:
            flat = json.dumps(_facts(mech, victim_piece="queen"))
            assert mech not in flat, mech
        # Only the UPPERCASE token is jargon. Asserting the lowercase form was
        # my own error: MATE lowercases to "mate", which the relation sentence
        # "the side that is mated cannot avoid checkmate" is supposed to
        # contain -- that is the plain-words wording, not leaked jargon.
        assert "FORCES_RETREAT" not in json.dumps(_facts("FORCES_RETREAT"))
        assert "forces_retreat" not in json.dumps(_facts("FORCES_RETREAT")).lower()


class TestAShortTrueAnswerIsNotAFailure:
    def test_a_four_word_answer_ships(self):
        """caption_polish refuses this by construction and that is the bug it
        has: "Rxa7 wins their queen." is the clearest output this feature
        produces."""
        f = _facts("WINS_MATERIAL", direction="missed",
                   agent_move="Rxa7", victim_piece="queen", played_san="Nxa7")
        assert validate(f, "Rxa7 wins their queen.") is None

    def test_an_empty_answer_is_still_refused(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        assert validate(f, "") == "empty"
        assert validate(f, "   ") == "empty"

    def test_a_rambling_answer_is_refused(self):
        f = _facts("WINS_MATERIAL", victim_piece="rook")
        long = "After Nf6, Nc3 wins your rook. " + ("and it is bad " * 20)
        why = validate(f, long)
        assert why and "too long" in why


class TestWhoseThingItIs:
    """`received` is their reply punishing our move; `missed` is what the
    better move would have collected. The owner of the piece flips between
    them, and flipping it the wrong way tells a player they lost a piece they
    actually won."""

    def test_received_takes_from_the_mover(self):
        f = _facts("WINS_MATERIAL", direction="received", victim_piece="rook")
        assert f["the_piece_involved"] == "your rook"

    def test_missed_takes_from_the_opponent(self):
        f = _facts("WINS_MATERIAL", direction="missed", victim_piece="rook")
        assert f["the_piece_involved"] == "their rook"

    def test_it_flips_again_when_the_move_is_the_opponents(self):
        """Their mistake gets the same button. The reader is then the side NOT
        moving, so "your" and "their" both swap."""
        f = _facts("WINS_MATERIAL", direction="received",
                   victim_piece="rook", mover_is_user=False)
        assert f["the_piece_involved"] == "their rook"

    def test_a_count_reads_as_a_person_would_say_it(self):
        f = _facts("WINS_MATERIAL", direction="missed",
                   victim_piece="two pawns")
        assert f["the_piece_involved"] == "two of their pawns"

    def test_the_reader_is_told_whose_move_it_is(self):
        assert _facts("MATE")["whose_move"] == "the reader's"
        assert _facts("MATE", mover_is_user=False)["whose_move"] \
            == "their opponent's"


class TestTheFactsCarryNoEvaluation:
    def test_payoff_centipawns_never_reach_the_model(self):
        """A centipawn figure is the one thing a 600-1500 player cannot use,
        and a model given a number will put it in a sentence."""
        import json
        f = _facts("WINS_MATERIAL", victim_piece="rook", payoff_cp=512)
        assert "512" not in json.dumps(f)
        assert not any("payoff" in k or "_cp" in k for k in f)


class TestItIsOffUntilTurnedOn:
    def test_disabled_returns_the_reason_and_no_text(self):
        import asyncio

        from services.why_words import write
        out = asyncio.run(write(_facts("WINS_MATERIAL", victim_piece="rook")))
        assert out["text"] is None
        assert out["refused"] == "disabled"

    def test_without_a_resolved_finding_it_declines(self, monkeypatch):
        """A model handed a move list and asked why a move was bad reads
        causality off the line -- the failure llm_caption.py documents. No
        finding, no call."""
        import asyncio

        import services.why_words as WW
        monkeypatch.setattr(WW, "WHY_WORDS_ENABLED", True)
        out = asyncio.run(WW.write({"relation": "", "the_move_played": "Nf6"}))
        assert out["text"] is None
        assert out["refused"] == "no resolved finding"
