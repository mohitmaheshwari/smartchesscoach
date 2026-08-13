"""
Regression tests for the motif got_positions contract fix (2026-08-13).

THE BUG THIS LOCKS OUT
----------------------
`compute_game_motifs` stored `fen` = the position AFTER the user's blunder, but
`solution` = the best move in the position BEFORE it. The two do not belong together.
Measured on production: 511 of 558 stored fork positions (92%) had a `solution` that was
ILLEGAL in the stored `fen`. `PrescribedTraining` graded users against those moves.

These are pure-logic tests — no Mongo, no Stockfish, no live server — so they run in CI.
"""
import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.motif_profile_service import (  # noqa: E402
    compute_game_motifs,
    get_drills,
    count_unresolved_drills,
    merge_motifs,
)


# A REAL fork, verified to make the detector fire — otherwise the invariant tests
# below would pass vacuously on an empty got_positions list.
#
#   Black (the user) to move. Rook on h7 is safe.
#   Black plays Rh8?? and White answers Nf7, forking the queen on d8 and the rook on h8.
#   Nf7 is legal ONLY after Rh8 — which is precisely the property the old contract
#   destroyed by storing one FEN for two different moves.
FEN_BEFORE = "3q4/k6r/8/4N3/8/8/8/4K3 b - - 0 1"
BLUNDER = "Rh8"
BEST = "Qd5"
OPP_FORK = "Nf7"


def _play(fen, san):
    b = chess.Board(fen)
    b.push_san(san)
    return b.fen()


FEN_AFTER = _play(FEN_BEFORE, BLUNDER)


def _mk_eval(cp_loss=400, move_number=21):
    return {
        "move_number": move_number,
        "move": BLUNDER,
        "best_move": BEST,
        "fen_before": FEN_BEFORE,
        "fen_after": FEN_AFTER,
        "cp_loss": cp_loss,
        "pv_after_played": [OPP_FORK],
        "is_opponent_move": False,
    }


def _fork_positions(out):
    """Fail loudly if the detector produced nothing — a vacuous pass here would
    hide exactly the regression these tests exist to catch."""
    positions = out["fork"]["got_positions"]
    assert positions, "fixture no longer triggers the fork detector — fix the fixture"
    return positions


def _legal(fen, san):
    if not fen or not san:
        return False
    try:
        chess.Board(fen).parse_san(san)
        return True
    except Exception:
        return False


# ─── the invariant that was violated in production ────────────────────────────

def test_stored_record_keeps_each_move_with_its_own_position():
    """fen_before must accept solution AND user_blunder_move.
    fen_after must accept opp_creates_motif. This is the whole bug."""
    out = compute_game_motifs([_mk_eval()], game_id="game_test_1")
    for p in _fork_positions(out):
        assert _legal(p["fen_before"], p["solution"]), \
            f"solution {p['solution']} illegal in fen_before"
        assert _legal(p["fen_before"], p["user_blunder_move"]), \
            f"blunder {p['user_blunder_move']} illegal in fen_before"
        assert _legal(p["fen_after"], p["opp_creates_motif"]), \
            f"opp move {p['opp_creates_motif']} illegal in fen_after"
        # and the pairing must be genuinely crossed — the pre-fix bug
        assert not _legal(p["fen_after"], p["solution"]), \
            "fixture too weak: solution happens to be legal in fen_after too"


def test_legacy_fen_field_keeps_its_original_meaning():
    """`fen` must remain the alias of fen_after. Silently repointing it would break
    any reader we have not found."""
    out = compute_game_motifs([_mk_eval()], game_id="g1")
    for p in _fork_positions(out):
        assert p["fen"] == p["fen_after"] == FEN_AFTER
        assert p["fen"] != p["fen_before"]


def test_provenance_is_carried():
    out = compute_game_motifs([_mk_eval(move_number=17)], game_id="game_abc")
    for p in _fork_positions(out):
        assert p["game_id"] == "game_abc"
        assert p["move_number"] == 17
        assert p["contract_version"] == 2


# ─── get_drills(): the normalized read contract ───────────────────────────────

def _profile(positions):
    return {"fork": {"made_sound": 0, "made_tunnel": 0, "got": len(positions),
                     "got_positions": positions}}


def test_get_drills_pairs_position_fen_with_a_legal_solution():
    prof = _profile([{
        "fen": FEN_AFTER,
        "fen_before": FEN_BEFORE,
        "fen_after": FEN_AFTER,
        "solution": BEST,
        "user_blunder_move": BLUNDER,
        "opp_creates_motif": OPP_FORK,
        "game_id": "g1",
        "move_number": 21,
    }])
    drills = get_drills(prof, "fork")
    assert len(drills) == 1
    d = drills[0]
    assert d["position_fen"] == FEN_BEFORE
    assert _legal(d["position_fen"], d["solution_san"]), \
        "the whole point: solution_san must be legal in position_fen"


def test_get_drills_drops_unbackfilled_legacy_rows():
    """A pre-fix row has no fen_before. Serving it means serving an illegal move,
    so it must be dropped, not repaired by guessing."""
    prof = _profile([
        {"fen": FEN_AFTER, "solution": BEST,
         "user_blunder_move": BLUNDER, "opp_creates_motif": OPP_FORK},   # legacy, unresolved
        {"fen": FEN_AFTER, "fen_before": FEN_BEFORE, "fen_after": FEN_AFTER,
         "solution": BEST, "user_blunder_move": BLUNDER,
         "opp_creates_motif": OPP_FORK},                                 # backfilled
    ])
    drills = get_drills(prof, "fork")
    assert len(drills) == 1, "the legacy row must not be served"
    assert count_unresolved_drills(prof, "fork") == 1


def test_get_drills_returns_the_replay_fields_motifdrill_needs():
    """MotifDrill must replay user_blunder_move before opp_creates_motif.
    Before the fix get_drills never returned either field, so the trap panel
    was permanently dead."""
    prof = _profile([{
        "fen": FEN_AFTER, "fen_before": FEN_BEFORE,
        "fen_after": FEN_AFTER, "solution": BEST,
        "user_blunder_move": BLUNDER, "opp_creates_motif": OPP_FORK,
        "game_id": "g1", "move_number": 21,
    }])
    d = get_drills(prof, "fork")[0]
    assert d["user_blunder_move"] == BLUNDER
    assert d["opp_creates_motif"] == OPP_FORK
    assert d["fen_after"]


def test_get_drills_handles_empty_and_malformed_input():
    assert get_drills(None, "fork") == []
    assert get_drills({}, "fork") == []
    assert get_drills({"fork": {"got_positions": [None, "junk", {}]}}, "fork") == []


# ─── the replay chain MotifDrill performs in the browser ──────────────────────

def test_replaying_blunder_then_opponent_move_is_legal():
    """MotifDrill does: Chess(position_fen) -> move(user_blunder_move)
    -> move(opp_creates_motif). Playing opp_creates_motif directly from
    position_fen throws — which is exactly why the trap panel never rendered."""
    board = chess.Board(FEN_BEFORE)
    board.push_san(BLUNDER)
    board.push_san(OPP_FORK)          # must not raise

    try:
        chess.Board(FEN_BEFORE).push_san(OPP_FORK)   # the old, broken path
    except Exception:
        pass
    else:
        raise AssertionError(
            "fixture too weak: the opponent's move is legal without the blunder")


def test_the_fork_actually_forks_two_pieces():
    """Guards the fixture itself: after the replay, the knight must attack two
    pieces worth a minor piece or more. If this ever stops holding, the tests
    above are testing a shape that is not a fork."""
    board = chess.Board(FEN_BEFORE)
    board.push_san(BLUNDER)
    mv = board.parse_san(OPP_FORK)
    knight_color = board.turn
    board.push(mv)
    values = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    targets = [
        board.piece_at(sq) for sq in board.attacks(mv.to_square)
        if board.piece_at(sq) and board.piece_at(sq).color != knight_color
    ]
    valuable = [p for p in targets if values.get(p.piece_type, 0) >= 3]
    assert len(valuable) >= 2, f"not a two-piece fork: {[p.symbol() for p in targets]}"


# ─── merge must not drop the new fields ───────────────────────────────────────

def test_merge_motifs_preserves_the_new_contract_fields():
    game = compute_game_motifs([_mk_eval()], game_id="g1")
    merged = merge_motifs(None, game)
    positions = merged["fork"]["got_positions"]
    assert positions, "merge dropped the fork positions"
    for p in positions:
        assert "fen_before" in p and "fen_after" in p and p.get("contract_version") == 2


if __name__ == "__main__":
    # Runnable as a plain script so CI can execute it without pytest installed —
    # same pattern as tests/test_opening_name_alignment.py.
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
