"""An opponent card's arrows follow the words it ships with.

Mohit 2026-11-13: "game review doesn't build arrows when opponent makes
mistake". The pipeline chooses an opponent card's picture from its own
caption; the review service then replaces that caption (the stored model
sentence, the verify-softened sentence) and kept the old picture. On 3c8d0751,
6 of 13 opponent mistake/blunder cards had no arrow, and three more drew a
Black move under a sentence about White's.

Positions and lines below are those cards as stored.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_pipeline import repick_opponent_arrows  # noqa: E402

# 61.Ke7: their king walks into Qc5+, which wins the bishop on d5.
KE7 = dict(
    fen_before="7k/6p1/3K4/3B3p/3n4/2q5/8/8 w - - 4 61",
    played_san="Ke7",
    caption_facts={"user_best_reply_san": "Qc5+", "move_story": "punishment"},
    pv_after_played=["Qc5+", "Kd7", "Qxd5+", "Kc8", "Kh7", "Kb8", "Kh6", "Kc7", "h4", "Kc8"],
    cp_loss=9115,
    their_best_san="Ke5",
)
KE7_TEXT = ("Your opponent played Ke7 — it lets Qc5+ come in with check. "
            "Ke5 was stronger: it attacks the knight on d4.")

# 29.Bxb7: the soft sentence quotes the line's first move, Qg5+, while the
# next position's stored best move (the fact) is g5.
BXB7 = dict(
    fen_before="7k/ppp3pp/8/3B4/3nP3/5PK1/3q3P/8 w - - 0 29",
    played_san="Bxb7",
    caption_facts={"user_best_reply_san": "g5", "move_story": "neither"},
    pv_after_played=["Qg5+", "Kf2", "Qd2+", "Kg3", "g5", "Ba6", "Kg7", "h4"],
    cp_loss=9090,
    their_best_san="h4",
)
BXB7_TEXT = ("Your opponent played Bxb7 — it lets Qg5+ come in with check. "
             "h4 was stronger: it moves their pawn out of danger.")

# 7.Nf3: White's better move was e5-e6 and our best reply is e7-e6 -- the
# same two characters. The model sentence is about White's.
NF3 = dict(
    fen_before="rn1qkb1r/pppnpppp/6b1/4P3/2BP4/2N5/PP3PPP/R1BQK1NR w KQkq - 1 7",
    played_san="Nf3",
    caption_facts={"user_best_reply_san": "e6", "move_story": "neither"},
    pv_after_played=["e6", "h4", "Nb6", "Bb5+"],
    cp_loss=248,
    their_best_san="e6",
)
NF3_TEXT = ("Your opponent played Nf3 instead of e6, missing a pawn attack on "
            "your knight.")


def _pairs(arrows):
    return [(a["from"], a["to"]) for a in arrows]


def test_a_silent_rule_caption_replaced_by_a_reply_sentence_draws_the_reply():
    out = repick_opponent_arrows([], chosen_for="", final_text=KE7_TEXT, **KE7)
    assert ("c3", "c5") in _pairs(out), out


def test_the_reply_the_words_quote_is_drawn_even_when_the_fact_names_another():
    out = repick_opponent_arrows([], chosen_for="", final_text=BXB7_TEXT, **BXB7)
    assert ("d2", "g5") in _pairs(out), out
    assert all(a.get("teach") is True for a in out)


def test_a_move_both_sides_could_mean_draws_nothing_and_drops_the_old_arrow():
    old = [{"from": "e7", "to": "e6", "color": "blue", "teach": True}]
    out = repick_opponent_arrows(
        old, chosen_for="Your opponent played Nf3. That was a bad mistake. Play e6.",
        final_text=NF3_TEXT, **NF3)
    assert ("e7", "e6") not in _pairs(out), out


def test_unchanged_words_keep_the_pipeline_picture_exactly():
    old = [{"from": "e7", "to": "e6", "color": "blue", "teach": True}]
    text = "Your opponent played Nf3. That was a bad mistake. Play e6."
    assert repick_opponent_arrows(old, chosen_for=text, final_text=text, **NF3) == old


def test_no_record_of_the_chosen_words_keeps_the_picture():
    old = [{"from": "a1", "to": "a2", "color": "red", "teach": True}]
    assert repick_opponent_arrows(old, chosen_for=None, final_text=KE7_TEXT, **KE7) == old


def test_a_card_that_already_draws_keeps_its_picture_when_the_words_change():
    """Additive only. The first version swapped pictures and removed arrows on
    27 of 31 changed cards in 8 reviews, most of them true pictures the new
    words describe without spelling the move (7286e2f5 12.Kg8: "lets you check
    while attacking their bishop on c5", drawn f3-d5, d5-c5)."""
    old = [{"from": "c3", "to": "c5", "color": "blue", "teach": True},
           {"from": "c5", "to": "d5", "color": "green", "teach": True}]
    out = repick_opponent_arrows(
        old, chosen_for="Your opponent played Ke7. That was a big mistake.",
        final_text="Their king move lets you check while attacking their bishop.",
        **KE7)
    assert out == old


def test_words_that_name_no_reply_draw_nothing_new():
    """Negative control: a sentence with no move of ours earns no arrow."""
    out = repick_opponent_arrows(
        [], chosen_for="",
        final_text="Their king move leaves your pawn on c4 open to capture.",
        **BXB7)
    assert out == []
