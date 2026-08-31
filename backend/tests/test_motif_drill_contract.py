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
import asyncio
from types import SimpleNamespace

import chess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.motif_profile_service import (  # noqa: E402
    compute_game_motifs,
    get_drills,
    count_unresolved_drills,
    merge_motifs,
    motif_drill_sequence_is_verified,
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
        # A row derived straight from one game's move_evaluations has no
        # (fen_after, move) join to be ambiguous about, so it is "exact" by
        # construction and get_drills() may name its game.
        assert p["provenance"] == "exact"


def test_no_game_id_means_no_provenance_claim():
    """Legacy call sites pass no game_id. Such a row must NOT claim "exact" --
    it has no attribution to offer, and get_drills() must withhold it rather
    than invent one."""
    out = compute_game_motifs([_mk_eval()])          # no game_id
    for p in _fork_positions(out):
        assert p.get("game_id") is None
        assert "provenance" not in p, "must not claim provenance without a game_id"

    prof = _profile(list(_fork_positions(out)))
    for d in get_drills(prof, "fork"):
        assert d["provenance"] == "unstamped"
        assert d["game_id"] is None and d["move_number"] is None


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


def test_ambiguous_provenance_never_leaks_a_game_or_move_number():
    """373 of 3,395 production rows match more than one game on (fen_after, move) —
    one matches 32. Those rows are still legally playable, but they cannot name a
    game or a date. The reader must not hand a caller an attribution to print."""
    base = {
        "fen": FEN_AFTER, "fen_before": FEN_BEFORE, "fen_after": FEN_AFTER,
        "solution": BEST, "user_blunder_move": BLUNDER, "opp_creates_motif": OPP_FORK,
    }
    prof = _profile([
        {**base, "provenance": "ambiguous", "candidate_game_count": 32,
         "game_id": None, "move_number": None},
        {**base, "provenance": "exact", "game_id": "g_known", "move_number": 21},
    ])
    drills = get_drills(prof, "fork")
    assert len(drills) == 2, "ambiguous rows are still playable — do not drop them"

    ambiguous = [d for d in drills if d["provenance"] == "ambiguous"][0]
    exact = [d for d in drills if d["provenance"] == "exact"][0]

    assert ambiguous["game_id"] is None and ambiguous["move_number"] is None
    assert _legal(ambiguous["position_fen"], ambiguous["solution_san"])
    assert exact["game_id"] == "g_known" and exact["move_number"] == 21


def test_unstamped_legacy_rows_are_not_treated_as_exact():
    """A row backfilled before the ambiguity check has no provenance stamp. It must
    not be allowed to masquerade as a known attribution."""
    prof = _profile([{
        "fen": FEN_AFTER, "fen_before": FEN_BEFORE, "fen_after": FEN_AFTER,
        "solution": BEST, "user_blunder_move": BLUNDER, "opp_creates_motif": OPP_FORK,
        "game_id": "g_maybe_wrong", "move_number": 21,
    }])
    d = get_drills(prof, "fork")[0]
    assert d["provenance"] == "unstamped"
    assert d["game_id"] is None and d["move_number"] is None


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


def test_verified_motif_sequence_requires_two_agreeing_geometry_walks():
    fork = {
        "position_fen": FEN_BEFORE,
        "solution_san": BEST,
        "user_blunder_move": BLUNDER,
        "opp_creates_motif": OPP_FORK,
    }
    pin = {
        "position_fen": "4k3/7p/2n5/8/2B5/8/8/4K3 b - - 0 1",
        "solution_san": "Kd7",
        "user_blunder_move": "h6",
        "opp_creates_motif": "Bb5",
    }
    skewer = {
        "position_fen": "k3r3/7p/2q5/8/2B5/8/8/6K1 b - - 0 1",
        "solution_san": "Kb7",
        "user_blunder_move": "h6",
        "opp_creates_motif": "Bb5",
    }

    assert motif_drill_sequence_is_verified(fork, "fork")
    assert motif_drill_sequence_is_verified(pin, "pin")
    assert motif_drill_sequence_is_verified(skewer, "skewer")
    assert not motif_drill_sequence_is_verified(fork, "pin")
    assert not motif_drill_sequence_is_verified(
        {**fork, "opp_creates_motif": "Nf3"},
        "fork",
    )


def test_enforced_route_serves_individually_verified_own_game_row(monkeypatch):
    pytest.importorskip("bcrypt")
    from routes import player

    class _Profiles:
        async def find_one(self, query, projection=None):
            return {
                "motif_profile": _profile([{
                    "fen": FEN_AFTER,
                    "fen_before": FEN_BEFORE,
                    "fen_after": FEN_AFTER,
                    "solution": BEST,
                    "user_blunder_move": BLUNDER,
                    "opp_creates_motif": OPP_FORK,
                    "provenance": "exact",
                    "game_id": "g1",
                    "move_number": 21,
                }])
            }

    async def resolve(db, puzzle_id, *, user_id=None):
        assert puzzle_id == "g1_m21"
        assert user_id == "u1"
        return {
            "fen": FEN_BEFORE,
            "best_move_san": BEST,
            "best_move_uci": "d8d5",
        }

    monkeypatch.setenv("VERIFIED_PUZZLE_ADMISSION_ENFORCED", "true")
    monkeypatch.setattr(player, "db", SimpleNamespace(player_profiles=_Profiles()))
    monkeypatch.setattr(
        "services.verified_puzzle_runtime.resolve_verified_puzzle",
        resolve,
    )

    result = asyncio.run(player.get_motif_drill(
        "fork",
        user=SimpleNamespace(user_id="u1"),
    ))

    assert result["gated"] is False
    assert result["count"] == 1
    assert result["drills"][0]["source"] == "own_verified"


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
