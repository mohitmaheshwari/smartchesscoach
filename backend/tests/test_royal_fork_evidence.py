"""
Royal forks in the canonical multi-target-attack evidence (2026-08-13).

THE GAP THIS CLOSES
-------------------
`_threats_created` skips the enemy king outright ("checks are handled by
is_check, not threats") because a king is not winnable material. Correct for
material accounting -- but it meant a check-plus-piece fork reached the grouper
with only ONE target and was discarded. Measured: the canonical detector
rejected the historically-correct fork move on 16 of 63 gold knight-fork
positions, every one a royal fork.

PIECE-AGNOSTIC BY CONSTRUCTION
------------------------------
A fork is "one piece attacks two valuable targets at once" -- knights have no
special claim on it. Measured on a 6,000-move corpus, royal forks by attacking
piece: queen 15, knight 13, rook 5, bishop 2. A knight-specific fix would have
caught 37% of them. These tests therefore assert the behaviour for several
attacker types, not just knights.

Pure logic -- no Mongo, no Stockfish, no server. Runs in CI.
"""
import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_facts import (  # noqa: E402
    extract_facts,
    extract_primary_reason,
    is_named_fork,
    named_fork_shapes,
)


def _shapes(fen_before, played_san):
    f = extract_facts(fen_before=fen_before, played_san=played_san,
                      cp_loss=0, mover_is_user=True)
    return f.get("multi_target_attack_evidence") or []


def _royal(fen_before, played_san, attacker=None):
    for sh in _shapes(fen_before, played_san):
        if not sh.get("includes_forced_king"):
            continue
        if attacker and sh.get("attacker_piece_type") != attacker:
            continue
        return sh
    return None


# ─── Fixtures: all four taken from REAL analysed games and verified against
# the board, not hand-written. Hand-built FENs kept coming out illegal.

# Knight royal fork: Nd3+ checks the king on e8 and hits the queen and rook.
ROYAL_KNIGHT = ("4k2r/2ppbpp1/3qp2p/1p1Pn3/P7/1P2B3/1Q3PPP/2R1K2R b Kk - 0 18", "Nd3+")
# QUEEN royal fork -- forks are not a knight concept. Qb5+ checks and hits a knight.
ROYAL_QUEEN = ("r3k2r/ppp2ppp/3p1q1n/n1b1p2b/2B1P3/1QPP1N1P/PP1N1PP1/R1B2RK1 w kq - 5 10", "Qb5+")
# Ordinary two-piece fork, no check: Nd5 hits the queen and the rook.
NORMAL_FORK = ("r1b3k1/ppq3pp/5r2/8/5b2/P1N2B2/1P3PP1/R2QRK2 w - - 2 21", "Nd5")
# A real check that is NOT a fork -- it must stay silent.
BARE_CHECK = ("r2qkbnr/ppp2pp1/3p3p/4p3/2BnP1b1/P1NP1N2/1PP2PPP/R1BQK2R w KQkq - 1 7", "Bxf7+")
# Check + PAWN. Geometrically a fork, but not worth naming as one.
PAWN_ONLY_ROYAL = ("r2q1bnr/ppp2kp1/7p/4p3/4P1Q1/P1NP4/1P3PPP/n1B2K1R w - - 0 11", "Qf5+")
# The checking knight is capturable at a profit -- the "fork" resolves by taking it.
UNSAFE_CHECKER = ("r2q1bnr/ppp2kp1/3p3p/4p3/3nP1b1/P1NP1N2/1PP2PPP/R1BQK2R w KQ - 0 8", "Nxe5+")


# ─── the shape is recognised, for more than one attacker type ────────────────

def test_knight_royal_fork_is_recognised():
    sh = _royal(*ROYAL_KNIGHT, attacker="knight")
    assert sh is not None, "knight royal fork not recognised"
    kinds = {t["piece_type"] for t in sh["attacked_targets"]}
    assert "king" in kinds and "queen" in kinds


def test_queen_royal_fork_is_recognised():
    """A fork is 'one piece attacks two valuable targets', not a knight move.
    Corpus split of royal forks by attacker: queen 15, knight 13, rook 5,
    bishop 2 -- a knight-only implementation would miss the majority."""
    sh = _royal(*ROYAL_QUEEN, attacker="queen")
    assert sh is not None, "queen royal fork not recognised -- detector is not piece-agnostic"
    kinds = {t["piece_type"] for t in sh["attacked_targets"]}
    assert "king" in kinds and "knight" in kinds


def test_king_target_carries_zero_value_and_is_flagged_forced():
    """A king can never be won. It must not leak into material arithmetic."""
    sh = _royal(*ROYAL_KNIGHT)
    assert sh is not None
    king = [t for t in sh["attacked_targets"] if t["piece_type"] == "king"]
    assert len(king) == 1
    assert king[0]["value_cp"] == 0, "a king must contribute no material value"
    assert king[0]["see_cp"] == 0
    assert king[0]["is_forced"] is True
    assert [t for t in sh["attacked_targets"] if not t["is_forced"]],         "a royal fork still needs a real winnable target"


# ─── the gates ───────────────────────────────────────────────────────────────

def test_a_plain_check_is_not_a_fork():
    """Bxf7+ is a real check from a real game with no winnable second target.
    It must not be captioned as a fork."""
    assert _royal(*BARE_CHECK) is None, "bare check registered as a fork"


def test_pawn_only_royal_fork_keeps_its_geometry_but_is_not_named():
    """Chess truth and product policy are separate layers.

    Qf5+ checks the king and attacks a pawn. That IS a fork -- the canonical
    evidence must say so. But ChessGuru does not NAME it, because the king wins
    no material and a pawn is not worth a fork lesson. It falls through to the
    ordinary check explanation instead of being silenced.
    """
    facts = extract_facts(fen_before=PAWN_ONLY_ROYAL[0], played_san=PAWN_ONLY_ROYAL[1],
                          cp_loss=0, mover_is_user=True)
    royal = [s for s in (facts.get("multi_target_attack_evidence") or [])
             if s.get("includes_forced_king")]

    # 1. the geometry is recorded -- the detector does not lie about chess
    assert royal, "check+pawn is still a fork; the evidence must record it"
    kinds = {t["piece_type"] for t in royal[0]["attacked_targets"]}
    assert "king" in kinds and "pawn" in kinds

    # 2. but it is not promoted into named teaching
    assert is_named_fork(royal[0]) is False
    assert named_fork_shapes(facts["multi_target_attack_evidence"]) == []

    # 3. and the caption routes to the honest check explanation, not silence
    reason = extract_primary_reason(facts)
    assert reason is not None, "must not go silent"
    assert reason["category"] == "check_extra",         f"expected fallback to check_extra, got {reason['category']}"


def test_check_plus_minor_piece_is_named():
    """The counterpart: 300 must not be so high that real forks are discarded.
    Qb5+ hits the king and a knight -- a 500 floor would wrongly reject it."""
    facts = extract_facts(fen_before=ROYAL_QUEEN[0], played_san=ROYAL_QUEEN[1],
                          cp_loss=0, mover_is_user=True)
    royal = [s for s in (facts.get("multi_target_attack_evidence") or [])
             if s.get("includes_forced_king")]
    assert royal, "queen royal fork not recognised"
    assert is_named_fork(royal[0]) is True,         "check + knight must stay eligible -- this is why the floor is 300, not 500"
    reason = extract_primary_reason(facts)
    assert reason and reason["category"] == "tactic_played"


def test_naming_rule_is_uniform_across_royal_and_normal():
    """One predicate, one rule: at least one WINNABLE target worth a minor piece
    or more. Applied to royal and normal shapes alike, so Gold-content selection
    cannot drift to a stricter bar than the caption layer.

    The asymmetric version (floor on royal only) inflated Gold-eligible
    candidates from 97 to 193 by admitting pawn+pawn forks."""
    facts = extract_facts(fen_before=NORMAL_FORK[0], played_san=NORMAL_FORK[1],
                          cp_loss=0, mover_is_user=True)
    normal = [s for s in (facts.get("multi_target_attack_evidence") or [])
              if not s.get("includes_forced_king")]
    assert normal, "fixture no longer produces a normal fork"
    # Nd5 hits a queen and a rook -- comfortably named.
    assert is_named_fork(normal[0]) is True

    # And the rule is stated once, not per-shape-type: a shape whose only
    # winnable targets are pawns is not named, royal or not.
    pawn_only_normal = {"includes_forced_king": False, "attacked_targets": [
        {"piece_type": "pawn", "value_cp": 100, "is_forced": False},
        {"piece_type": "pawn", "value_cp": 100, "is_forced": False}]}
    assert is_named_fork(pawn_only_normal) is False


def test_capturable_checker_is_rejected():
    """Nxe5+ checks and attacks a bishop, but the knight is capturable at a
    profit -- the opponent answers the check by taking it, and there is nothing
    to win. Must NOT register as a royal fork.

    This is exactly where pattern_confidence/fork.py:120 was too lenient: it
    treats `gives_check` as making the forker safe outright.
    """
    facts = extract_facts(fen_before=UNSAFE_CHECKER[0], played_san=UNSAFE_CHECKER[1],
                          cp_loss=0, mover_is_user=True)
    royal = [s for s in (facts.get("multi_target_attack_evidence") or [])
             if s.get("includes_forced_king")]
    assert royal == [], "a checker the opponent simply captures is not a fork"


# ─── the normal path is untouched ────────────────────────────────────────────

def test_normal_two_piece_fork_still_works_and_is_not_marked_royal():
    shapes = _shapes(*NORMAL_FORK)
    assert shapes, "ordinary knight fork stopped being recognised"
    sh = shapes[0]
    assert not sh.get("includes_forced_king")
    assert all(not t["is_forced"] for t in sh["attacked_targets"])


def test_every_target_entry_exposes_is_forced():
    """Consumers branch on this; it must always be present."""
    for fen, san in (NORMAL_FORK, ROYAL_KNIGHT, ROYAL_QUEEN):
        for sh in _shapes(fen, san):
            for t in sh["attacked_targets"]:
                assert "is_forced" in t


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
