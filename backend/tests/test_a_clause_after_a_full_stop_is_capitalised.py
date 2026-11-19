"""A clause that lands at a sentence start is capitalised. SAN is never recased.

Found 2026-11-19, the moment `tactic:discovered_attack_with_stored_payoff`
reached Caption grade. Its clause is authored lowercase for the em-dash slot:

    {best_move_san} was better — {why_clause}

and the same clause is reused by sibling variants that put it after a full
stop:

    {best_move_san} was better. {why_clause}

which rendered, on game_73c3b9efff9c move 26:

    "b5 was a bad mistake. Bd7 was better — it brings a new piece into the
     game. it steps your bishop out of the way of your rook on d8 ..."

41 why-clauses share those slots, so the fix belongs at the join, not in the
authoring. `render_template` now capitalises the value of any slot the
template places at a sentence start.

The SAN half matters as much: chess case is meaning. "b5" is a pawn move and
"B5" is nothing; "exd5" is a capture and "Exd5" is nothing. Clauses that open
with a move must survive untouched.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.caption_templates import _sentence_cased  # noqa: E402


def _render(template, **facts):
    return template.format(**_sentence_cased(template, facts))


def test_a_clause_after_a_full_stop_gets_a_capital():
    out = _render("{best} was better. {why}",
                  best="Bd7", why="it steps your bishop out of the way.")
    assert out == "Bd7 was better. It steps your bishop out of the way."


def test_a_clause_after_an_em_dash_stays_lowercase():
    out = _render("{best} was better — {why}",
                  best="Bd7", why="it steps your bishop out of the way.")
    assert out == "Bd7 was better — it steps your bishop out of the way."


def test_a_slot_that_opens_the_template_gets_a_capital():
    assert _render("{why}", why="it hangs the rook.") == "It hangs the rook."


def test_question_and_exclamation_also_start_a_sentence():
    assert _render("What now? {why}", why="the rook is loose.") == \
        "What now? The rook is loose."
    assert _render("Careful! {why}", why="the rook is loose.") == \
        "Careful! The rook is loose."


def test_a_san_move_is_never_recased():
    # Case is meaning in SAN. Every one of these must come through intact.
    for san in ("b5", "exd5", "cxd5", "a8", "h4", "fxg7+", "e8=Q", "O-O",
                "O-O-O", "dxc3"):
        out = _render("{best} was better. {why}",
                      best="Nf3", why="%s was the move." % san)
        assert out == "Nf3 was better. %s was the move." % san, san


def test_an_already_capitalised_clause_is_untouched():
    assert _render("{best} was better. {why}", best="Nf3",
                   why="Their rooks can see each other.") == \
        "Nf3 was better. Their rooks can see each other."


def test_a_piece_letter_word_is_still_capitalised():
    # "Knight" is a word, not SAN. Only bare-move tokens are exempt.
    assert _render("{best} was better. {why}", best="Nf3",
                   why="knights belong in the centre.") == \
        "Nf3 was better. Knights belong in the centre."


def test_non_string_and_empty_values_do_not_raise():
    assert _render("{best} was better. {why}", best="Nf3", why="") == \
        "Nf3 was better. "
    assert _render("Count: {n}. {why}", n=3, why="that is too many.") == \
        "Count: 3. That is too many."


def test_the_callers_facts_are_not_mutated():
    facts = {"best": "Nf3", "why": "it hangs the rook."}
    _sentence_cased("{best} was better. {why}", facts)
    assert facts["why"] == "it hangs the rook."


def test_the_live_discovered_attack_clause_reads_correctly_in_both_slots():
    """The clause that exposed this, rendered from the shipped template."""
    from services.caption_templates import render_template

    facts = {
        "played_san": "b5",
        "severity_phrase": "was a bad mistake",
        "best_move_san": "Bd7",
        "missed_discovery_blocker_piece": "bishop",
        "missed_discovery_slider_piece": "rook",
        "missed_discovery_slider_square": "d8",
        "missed_discovery_target_piece": "knight",
        "missed_discovery_target_square": "a8",
    }
    clause = render_template(
        "R12_blunder", "why_user_missed_discovered_attack", facts)
    assert clause and clause[0].islower(), \
        "the clause itself is authored lowercase for the em-dash slot"

    facts["why_clause"] = clause
    after_stop = render_template("R12_blunder", "user_with_best_and_why", facts)
    after_dash = render_template("R12_blunder", "user_with_best_em_dash", facts)

    assert ". it steps" not in after_stop, after_stop
    assert ". It steps" in after_stop, after_stop
    assert "— it steps" in after_dash, after_dash
