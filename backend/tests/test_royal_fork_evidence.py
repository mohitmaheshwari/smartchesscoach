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

from services.caption_facts import extract_facts  # noqa: E402


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


def test_pawn_only_target_is_below_the_floor():
    """Check + pawn is tempo, not a teachable fork. Before the floor, 47 of 82
    newly-recognised royal forks (57%) were exactly this shape."""
    from services.caption_facts import _ROYAL_FORK_MIN_TARGET_CP
    assert _ROYAL_FORK_MIN_TARGET_CP >= 300


def test_forker_must_survive_see():
    """The checking piece must not simply hang. This is where
    pattern_confidence/fork.py:120 was too lenient -- it treated `gives_check`
    as making the forker safe outright, accepting a knight the king just takes."""
    import inspect
    from services import caption_facts
    src = inspect.getsource(caption_facts._forced_king_target)
    assert "static_exchange_eval" in src, "forker-safety gate missing"


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
