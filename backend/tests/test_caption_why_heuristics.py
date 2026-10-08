"""A why has to be about THIS position.

Mohit, 2026-09-30: "if they are not position specific, it might just fill in
something that's completely irrelevant, and universal principles also looks
like blubbering for no real reason."

These lock that decision into the one module both the audit and the review
queue import, so the two cannot drift apart again.
"""
from __future__ import annotations

from services.caption_why_heuristics import (
    has_causal_connector, has_concrete_consequence, has_principle_ending, has_why,
)


# ── the shape that started all of this ────────────────────────────────

def test_the_bare_comparison_has_no_why():
    """725 stored cards say exactly this, and it teaches nothing."""
    assert has_why("You played h6; Na5 was the stronger move here.", "h6", "Na5") is False
    assert has_why("Qe2 is a mistake. O-O was better.", "Qe2", "O-O") is False


def test_an_empty_caption_is_not_a_why():
    assert has_why("", "e4", "d4") is False
    assert has_why("   ", "e4", "d4") is False


# ── what does count ───────────────────────────────────────────────────

def test_naming_a_square_beyond_the_moves_counts():
    assert has_why("Nf3 leaves d4 undefended.", "Nf3", "c3") is True


def test_naming_a_piece_counts():
    assert has_why("This drops the bishop.", "Bc4", "Be2") is True


def test_a_causal_connector_counts():
    assert has_why("Ra1 loses to Qxf2+.", "Ra1", "Rf1") is True
    assert has_causal_connector("because it opens the file") is True


def test_the_moves_themselves_are_not_evidence():
    """Stripping the SANs is the whole point of H1: a caption made only of the
    two move names has said nothing about the board."""
    assert has_concrete_consequence("You played e4; d4 was stronger.", "e4", "d4") is False


# ── H3 is measured but no longer buys a pass ──────────────────────────

def test_a_principle_alone_is_not_a_why():
    caption = ("Bg5 is a mistake. Nf3 was better. "
               "Always develop your pieces before attacking.")
    assert has_principle_ending(caption) is True, "the detector itself still works"
    assert has_why(caption, "Bg5", "Nf3") is False, \
        "a universal principle bought a pass; it must not"


def test_a_principle_under_a_real_why_still_passes():
    """The rule removes the principle as a ROUTE, not as a closing line."""
    caption = ("Bg5 leaves the knight on f3 hanging. "
               "Always check what a move stops defending.")
    assert has_why(caption, "Bg5", "Nf3") is True


def test_the_principle_detector_is_still_exported():
    """The audit reports the three rates separately and the split is worth
    seeing, so removing the function would lose real information."""
    assert has_principle_ending("Never leave a piece undefended.") is True
    assert has_principle_ending("Nf3 is a mistake.") is False


# ── the two consumers must agree ──────────────────────────────────────

def test_the_audit_and_the_queue_share_one_definition():
    """If these ever diverge, the audit measures a rule the queue does not
    enforce, which is how the two drifted apart before 2026-09-22."""
    import importlib.util
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "audit_why", backend / "scripts" / "audit_captions_for_why.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    caption, played, best = "You played h6; Na5 was the stronger move here.", "h6", "Na5"
    agreed = (audit.has_concrete_consequence(caption, played, best)
              or audit.has_causal_connector(caption))
    assert agreed == has_why(caption, played, best)
