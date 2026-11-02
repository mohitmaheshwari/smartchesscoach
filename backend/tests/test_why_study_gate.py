"""The gate that stands between a model's reason and a card.

Board-fact claims are replayed with python-chess alone. The two engine kinds
run only where a Stockfish binary is present (the container has one; locally
STOCKFISH_PATH names it).

The position is 6.b3 from the b6 game (set entry mohit_b3): after either b3 or
d4, Black's Qg6 attacks the undefended g2 pawn; after b3 White's queen on d1
cannot move; after d4 the pawn is poisoned (Qd2, Qxg2, Bb5+ and Qxg2).
"""
from __future__ import annotations

import os
import sys

import pytest

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services import why_study as ws  # noqa: E402

FEN = "rn2kbnr/pbp1pppp/1p2q3/8/8/2N2P2/PPPPB1PP/R1BQK1NR w KQkq - 1 6"
ENGINE = os.environ.get("STOCKFISH_PATH") or ("/usr/games/stockfish" if os.path.exists("/usr/games/stockfish") else None)
needs_engine = pytest.mark.skipif(not (ENGINE and os.path.exists(ENGINE)), reason="no Stockfish here")


def ok(claim):
    passed, why = ws.check_claim(claim, FEN)
    assert passed, why


def fails(claim, fragment):
    passed, why = ws.check_claim(claim, FEN)
    assert not passed
    assert fragment in (why or "")


class TestBoardFactClaims:
    def test_the_queen_on_g6_attacks_g2_after_b3(self):
        ok({"kind": "attacks", "after": ["b3", "Qg6"], "subject": "g6", "target": "g2"})

    def test_g2_has_no_defender_after_b3_qg6(self):
        ok({"kind": "undefended", "after": ["b3", "Qg6"], "target": "g2"})

    def test_whites_queen_cannot_move_after_b3(self):
        ok({"kind": "no_legal_moves", "after": ["b3"], "subject": "d1"})

    def test_but_it_can_after_d4(self):
        fails({"kind": "no_legal_moves", "after": ["d4"], "subject": "d1"}, "can move")

    def test_bb5_is_check_in_the_poisoned_pawn_line(self):
        ok({"kind": "gives_check", "after": ["d4", "Qg6", "Qd2", "Qxg2", "Bb5+"]})

    def test_white_cannot_castle_now(self):
        ok({"kind": "castling_illegal", "after": [], "side": "white"})

    def test_a_wrong_attack_is_refused(self):
        fails({"kind": "attacks", "after": ["b3", "Qg6"], "subject": "g6", "target": "h2"}, "does not attack")

    def test_a_defended_square_is_refused(self):
        # after d4 Qg6 Qd2 Qxg2 Bb5+, the queen on g2 is attacked by Qd2: claim g2 undefended is about Black's queen now
        passed, why = ws.check_claim({"kind": "undefended", "after": ["d4", "Qg6", "Qd2", "Qxg2", "Bb5+"], "target": "g2"}, FEN)
        assert passed  # Black's queen on g2 has no defender, which is the point

    def test_an_illegal_move_in_the_claim_is_refused(self):
        fails({"kind": "attacks", "after": ["b3", "Qg6", "Qd2"], "subject": "d2", "target": "g2"}, "not legal")

    def test_an_unknown_kind_is_refused(self):
        fails({"kind": "wins", "after": []}, "unknown claim kind")

    def test_controls_covers_an_empty_square_and_attacks_does_not(self):
        # after d4 the pawn on d4 covers e5, which is empty
        ok({"kind": "controls", "after": ["d4"], "subject": "d4", "target": "e5"})
        fails({"kind": "attacks", "after": ["d4"], "subject": "d4", "target": "e5"}, "nothing on e5")
        fails({"kind": "controls", "after": ["d4"], "subject": "d4", "target": "d5"}, "does not cover")

    def test_blocks_own_pawn_in_the_b6_position(self):
        b6 = "rnb1kbnr/ppp1pppp/4q3/8/8/2N5/PPPPBPPP/R1BQK1NR b KQkq - 3 4"
        passed, why = ws.check_claim({"kind": "blocks_own_pawn", "after": [], "subject": "e6", "target": "e7"}, b6)
        assert passed, why
        passed, why = ws.check_claim({"kind": "blocks_own_pawn", "after": [], "subject": "e6", "target": "d7"}, b6)
        assert not passed


@needs_engine
class TestEngineClaims:
    def test_taking_on_g2_after_d4_qg6_qd2_loses_the_queen(self):
        with ws.open_engine(ENGINE) as eng:
            passed, why = ws.check_claim(
                {"kind": "capture_loses", "after": ["d4", "Qg6", "Qd2"], "capture_san": "Qxg2", "swing_cp_min": 500},
                FEN, eng=eng, depth=14)
        assert passed, why

    def test_d4_is_better_than_b3_for_white(self):
        with ws.open_engine(ENGINE) as eng:
            passed, why = ws.check_claim(
                {"kind": "line_better", "worse_line": ["b3"], "better_line": ["d4"], "side": "white", "by_cp_min": 100},
                FEN, eng=eng, depth=14)
            assert passed, why
            # the lines the wrong way round are refused, not silently inverted
            passed, why = ws.check_claim(
                {"kind": "line_better", "worse_line": ["d4"], "better_line": ["b3"], "side": "white", "by_cp_min": 100},
                FEN, eng=eng, depth=14)
        assert not passed and "ahead by" in why


CLAIMS = [
    {"kind": "attacks", "label": "the queen on g6 attacks the pawn on g2", "after": ["b3", "Qg6"], "subject": "g6", "target": "g2"},
    {"kind": "undefended", "label": "nothing guards g2", "after": ["b3", "Qg6"], "target": "g2"},
    {"kind": "no_legal_moves", "label": "the queen on d1 cannot move after b3", "after": ["b3"], "subject": "d1"},
    {"kind": "gives_check", "label": "Bb5+ is check", "after": ["d4", "Qg6", "Qd2", "Qxg2", "Bb5+"]},
]
GOOD = ("After b3, Qg6 attacks the pawn on g2 and nothing guards it. The queen on d1 cannot move to help. "
        "d4 opens the queen's road: after d4, taking on g2 with Qxg2 loses the queen to Bb5+.")


def _text_failures(text, claims=CLAIMS, mover_is_user=False):
    return ws.gate_text(text, claims, fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=mover_is_user)


class TestTheWords:
    def test_a_reason_built_from_its_claims_passes(self):
        assert _text_failures(GOOD) == []

    def test_a_number_is_refused_but_a_square_is_not(self):
        assert any("number" in f for f in _text_failures(GOOD + " That is about 2 pawns."))
        assert not any("number" in f for f in _text_failures(GOOD))

    def test_a_piece_the_claims_never_name_is_refused(self):
        bad = GOOD.replace("queen on d1", "rook on a1")
        assert bad != GOOD
        assert any("not in its claims" in f for f in _text_failures(bad))

    def test_the_better_move_must_be_named(self):
        assert any("better move" in f for f in _text_failures("After b3, Qg6 attacks the pawn on g2 and nothing guards it."))

    def test_the_wrong_owner_on_a_square_is_refused(self):
        # The mover is the opponent here: White's queen on d1 is "the opponent's queen", not "your queen".
        # Both sides own a queen, so the token guard alone cannot see it; the square does.
        bad = GOOD.replace("The queen on d1 cannot move", "Your queen on d1 cannot move")
        assert any("ownership" in f for f in _text_failures(bad, mover_is_user=False))
        # From the mover's own seat the same sentence is right.
        assert not any("ownership" in f for f in _text_failures(bad, mover_is_user=True))
        # and the right owner passes from the opponent's seat
        right = GOOD.replace("The queen on d1 cannot move", "The opponent's queen on d1 cannot move")
        assert not any("ownership" in f for f in _text_failures(right, mover_is_user=False))

    def test_reading_level_never_holds_a_true_reason(self):
        # Five short sentences are fine; a long sentence or a hard word is a note, not a failure.
        long = GOOD + " One more. And another. And a sixth sentence here."
        assert not any("sentences" in f for f in _text_failures(long))
        hard = GOOD.replace("nothing guards it", "it is undefended")
        assert not any("undefended" in f for f in _text_failures(hard))


class TestReadability:
    def test_a_sentence_over_fourteen_words_is_noted_with_its_number(self):
        r = ws.readability("After b3, Qg6 attacks the pawn on g2 and nothing guards it, and the queen on d1 cannot help.")
        assert r["longest_sentence_words"] > 14
        assert any("sentence 1 has" in n and "fourteen" in n for n in r["notes"])

    def test_a_hard_word_is_noted_with_the_plain_replacement(self):
        r = ws.readability("The g2 pawn is undefended. d4 is better.")
        assert r["hard_words"] == ["undefended"]
        assert any("nothing is guarding it" in n for n in r["notes"])

    def test_moves_and_squares_are_not_words_to_count_against_the_reader(self):
        r = ws.readability("After d4 Qg6 Qd2 Qxg2 Bb5+ c6 Qxg2, the queen is lost.")
        assert r["hard_words"] == [] and r["long_words"] == []
        assert r["longest_sentence_words"] <= 14

    def test_plain_short_text_has_no_notes(self):
        r = ws.readability("b3 moves a pawn while your pieces are still at home. Nf6 brings a piece out instead.")
        assert r["notes"] == [] and r["sentences"] == 2

    def test_the_prompts_own_example_passes_its_own_rules(self):
        start = ws.SYSTEM_PROMPT.index('"reason": "') + len('"reason": "')
        example = ws.SYSTEM_PROMPT[start:ws.SYSTEM_PROMPT.index('"', start)]
        assert ws.readability(example)["notes"] == []

    def test_the_gate_carries_notes_without_failing(self):
        text = GOOD.replace("nothing guards it", "it is undefended")
        gate = ws.run_gate({"no_lesson": False, "reason": text, "claims": CLAIMS},
                           fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=False)
        assert gate["passed"], gate["failures"]
        assert any("undefended" in n for n in gate["notes"])

    def test_the_rewrite_prompt_carries_the_previous_answer_and_the_fixes(self):
        text = ws.user_prompt({"fen_before": FEN}, previous={"reason": "old", "claims": []},
                              fixes=["sentence 1 has 19 words; the limit is fourteen. Split it."])
        assert "You already answered once" in text and '"reason": "old"' in text
        assert "fourteen" in text


class TestTheGate:
    def test_no_lesson_passes_without_claims(self):
        gate = ws.run_gate({"no_lesson": True, "no_lesson_why": "just worse", "reason": "", "claims": []},
                           fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=False)
        assert gate["passed"] and gate["no_lesson"]

    def test_a_reason_with_no_claims_is_held(self):
        gate = ws.run_gate({"no_lesson": False, "reason": "b3 is slow. d4 was better.", "claims": []},
                           fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=False)
        assert not gate["passed"] and "no claims" in gate["failures"][0]

    def test_one_false_claim_holds_the_whole_reason(self):
        claims = CLAIMS + [{"kind": "attacks", "label": "the bishop on b7 attacks g2", "after": ["b3", "Qg6"],
                            "subject": "b7", "target": "g2"}]
        gate = ws.run_gate({"no_lesson": False, "reason": GOOD, "claims": claims},
                           fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=False)
        assert not gate["passed"]
        assert gate["claims"][-1]["verified"] is False
        assert any("does not attack" in f for f in gate["failures"])

    def test_the_good_reason_passes_the_gate(self):
        gate = ws.run_gate({"no_lesson": False, "reason": GOOD, "claims": CLAIMS},
                           fen_before=FEN, played_san="b3", better_san="d4", mover_is_user=False)
        assert gate["passed"], gate["failures"]
        assert all(c["verified"] for c in gate["claims"])
