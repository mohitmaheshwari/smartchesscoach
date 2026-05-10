"""
Regression test: Category 1 (severity-vs-mate forced-mate guard).

Now correctly mirrors the FULL V5 severity decision path:
  1. Skip non-user moves (opp_X severities aren't user-coached)
  2. cp_loss recompute from eval_before + eval_after
  3. Mate-sentinel guard (Category 1 fix)
  4. cp_loss ladder
  5. is_book_opening_move override (existing production behavior)

user_color is read from the game record by game_id, not heuristically
guessed. Eliminates the "10 reclassifications" noise from earlier
versions where the heuristic mismatched stored opp_X bugs.

Usage:
    python scripts/verify_severity_fix_against_corpus.py \\
        --bug-file /tmp/parth_full_with_fen.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Mirrors the patched ladder in services/game_decryption_v5_service.py.
_MATE_SENTINEL_CP = 3000


def _classify_severity_v5(
    eval_before: float,
    eval_after: float,
    cp_loss_stored: int,
    user_color: str,
) -> str:
    cp_loss = max(abs(cp_loss_stored or 0), 0)
    if eval_before is not None and eval_after is not None:
        user_eval_before = eval_before if user_color == "white" else -eval_before
        user_eval_after = eval_after if user_color == "white" else -eval_after
        derived_loss = max(0, user_eval_before - user_eval_after)
        cp_loss = max(cp_loss, derived_loss)

    user_post_eval = None
    if eval_after is not None:
        user_post_eval = eval_after if user_color == "white" else -eval_after

    if user_post_eval is not None and user_post_eval <= -_MATE_SENTINEL_CP:
        return "blunder"
    if cp_loss < 30:
        return "good"
    if cp_loss < 100:
        return "inaccuracy"
    if cp_loss < 250:
        return "mistake"
    return "blunder"


def _apply_book_override(
    severity: str,
    fen_before: str,
    move_san: str,
    move_index: int,
    cp_loss: int,
    opening_name: Optional[str],
    move_history: Optional[list] = None,
) -> str:
    """Mirror the production override at game_decryption_v5_service:2509.
    If severity is inaccuracy/mistake AND we're in opening AND the move
    is a known book move, downgrade to good.

    move_history is the list of SAN moves played up to (not including)
    the candidate move — passed explicitly because boards reconstructed
    from FEN have empty move_stack.
    """
    if severity not in ("inaccuracy", "mistake"):
        return severity
    if move_index >= 20:
        return severity
    try:
        from services.game_decryption_v5_service import is_book_opening_move
        board = chess.Board(fen_before)
        if is_book_opening_move(
            board, move_san, move_index,
            opening_name, cp_loss or 0,
            move_history=move_history,
        ):
            return "good"
    except Exception:
        pass
    return severity


async def _load_user_colors(db, game_ids: list) -> Dict[str, str]:
    """Look up user_color for each game_id in one query."""
    if not game_ids:
        return {}
    out: Dict[str, str] = {}
    async for g in db.games.find(
        {"game_id": {"$in": list(set(game_ids))}},
        {"_id": 0, "game_id": 1, "user_color": 1},
    ):
        gid = g.get("game_id")
        col = (g.get("user_color") or "").lower()
        if gid and col in ("white", "black"):
            out[gid] = col
    return out


async def _load_pgns(db, game_ids: list) -> Dict[str, str]:
    """Look up PGN for each game_id so we can reconstruct move history."""
    if not game_ids:
        return {}
    out: Dict[str, str] = {}
    async for g in db.games.find(
        {"game_id": {"$in": list(set(game_ids))}},
        {"_id": 0, "game_id": 1, "pgn": 1},
    ):
        gid = g.get("game_id")
        pgn = g.get("pgn")
        if gid and pgn:
            out[gid] = pgn
    return out


def _move_history_up_to(pgn: str, target_move_number: int, target_move_san: str) -> Optional[list]:
    """Replay PGN, return the SAN list of moves played BEFORE the
    matching (move_number, move_san) — i.e., the prior moves to feed
    the book detector. Returns None if no match found."""
    import io
    import chess.pgn
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None
    if game is None:
        return None
    target_norm = (target_move_san or "").rstrip("!?+#")
    board = game.board()
    history: list = []
    for move in game.mainline_moves():
        try:
            san = board.san(move)
        except Exception:
            return None
        san_norm = san.rstrip("!?+#")
        if board.fullmove_number == target_move_number and san_norm == target_norm:
            return history
        history.append(san)
        try:
            board.push(move)
        except Exception:
            return None
    return None


async def run(args):
    data = json.loads(Path(args.bug_file).read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []

    # Pull user_color for every game referenced by bugs.
    game_ids = [
        (bug.get("context") or {}).get("game_id")
        for bug in bugs
        if (bug.get("context") or {}).get("game_id")
    ]
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    user_color_by_game = await _load_user_colors(db, game_ids)
    pgn_by_game = await _load_pgns(db, game_ids)
    client.close()

    n_total = 0
    n_skip_no_evals = 0
    n_skip_opp = 0
    n_skip_no_color = 0
    n_audited = 0
    n_upgraded_to_blunder = 0
    n_other_change = 0
    n_no_change = 0
    upgrades = []
    others = []

    for bug in bugs:
        n_total += 1
        position = bug.get("position") or {}
        ctx = bug.get("context") or {}
        eb = position.get("eval_before")
        ea = position.get("eval_after")
        cpl = position.get("cp_loss")
        stored_severity = (bug.get("severity") or "").strip().lower()
        fen = (position.get("fen") or "").strip()

        if eb is None or ea is None or stored_severity in ("", "unknown", "context"):
            n_skip_no_evals += 1
            continue

        # opp_X severities aren't classified by the user-side ladder we
        # patched. They go through a separate opponent ladder (lines
        # 2491-2498 in V5 service). Skip them — Category 1 fix doesn't
        # apply.
        if stored_severity.startswith("opp_"):
            n_skip_opp += 1
            continue

        game_id = ctx.get("game_id")
        user_color = user_color_by_game.get(game_id) if game_id else None
        if not user_color:
            n_skip_no_color += 1
            continue

        new_severity = _classify_severity_v5(eb, ea, cpl, user_color)

        # Apply the book-opening override (matches production).
        move_san = position.get("move_san") or ""
        move_number = position.get("move_number") or 0
        # move_index = ply index. For full move number M with white-to-
        # move turn, idx = (M-1)*2; black-to-move, idx = (M-1)*2+1.
        # We have the FEN — read its turn to compute.
        move_index = (move_number - 1) * 2 if move_number else 0
        try:
            move_index += 0 if chess.Board(fen).turn == chess.WHITE else 1
        except Exception:
            pass

        opening_name = None
        # Reconstruct move history from PGN so the book check can fire
        # the way it does in production (where board.move_stack is built
        # incrementally). When boards come from FEN, move_stack is empty
        # — without this, the detector sees only the candidate move.
        prior_history = None
        pgn_text = pgn_by_game.get(game_id) if game_id else None
        if pgn_text and move_san and move_number:
            prior_history = _move_history_up_to(pgn_text, move_number, move_san)
        new_severity = _apply_book_override(
            new_severity, fen, move_san, move_index, cpl, opening_name,
            move_history=prior_history,
        )

        n_audited += 1
        record = {
            "feedback_id": bug.get("feedback_id"),
            "move_san": move_san,
            "move_number": move_number,
            "stored_severity": stored_severity,
            "new_severity": new_severity,
            "eval_before": eb,
            "eval_after": ea,
            "cp_loss": cpl,
            "user_color": user_color,
            "user_note": (bug.get("issue") or "")[:200],
            "fen": (fen or "")[:80],
        }
        if stored_severity in ("good", "inaccuracy") and new_severity == "blunder":
            n_upgraded_to_blunder += 1
            upgrades.append(record)
        elif stored_severity != new_severity:
            n_other_change += 1
            others.append(record)
        else:
            n_no_change += 1

    print("=" * 70)
    print("REGRESSION TEST v2 (full V5 path, user_color from game record)")
    print("=" * 70)
    print(f"  total bugs:                                {n_total}")
    print(f"  skipped (no eval data / unknown sev):      {n_skip_no_evals}")
    print(f"  skipped (opp_X severity, not user move):   {n_skip_opp}")
    print(f"  skipped (no user_color in game record):    {n_skip_no_color}")
    print(f"  audited (user moves):                      {n_audited}")
    print(f"    upgraded good/inacc -> blunder:          {n_upgraded_to_blunder}")
    print(f"    other reclassification:                  {n_other_change}")
    print(f"    no change (matches stored):              {n_no_change}")
    print()
    if upgrades:
        print("=== UPGRADES (Category 1 wins) ===")
        for ex in upgrades:
            print(f"\n  {ex['feedback_id']} (move {ex['move_number']} {ex['move_san']}, user={ex['user_color']})")
            print(f"    {ex['stored_severity']} -> {ex['new_severity']}")
            print(f"    eval_before={ex['eval_before']:.0f}  eval_after={ex['eval_after']:.0f}  cp_loss={ex['cp_loss']}")
            print(f"    parth: \"{ex['user_note']}\"")
            print(f"    fen: {ex['fen']}")
        print()
    if others:
        print("=== OTHER RECLASSIFICATIONS ===")
        for ex in others:
            print(f"\n  {ex['feedback_id']} (move {ex['move_number']} {ex['move_san']}, user={ex['user_color']})")
            print(f"    {ex['stored_severity']} -> {ex['new_severity']}")
            print(f"    eval_before={ex['eval_before']:.0f}  eval_after={ex['eval_after']:.0f}  cp_loss={ex['cp_loss']}")
            print(f"    parth: \"{ex['user_note']}\"")
            print(f"    fen: {ex['fen']}")
        print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bug-file", required=True)
    asyncio.run(run(p.parse_args()))
