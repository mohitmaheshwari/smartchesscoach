"""
Cognitive-gap classifier audit.

Background: the lab/session-summary surface tags games with cognitive
gaps like 'piece_activity' (rendered "passive pieces") and 'king_safety'
(rendered "king-safety slips"). Two real Parth-loss games revealed both
gaps mis-classified — Game 1 was lost via tactical sacrifices and a
queen blunder, but tagged 'passive pieces / king safety'. Game 2 was
won despite multiple ?? blunders, also tagged 'passive pieces / king
safety'.

Root cause located in analysis_interpreter.py:
  - GAP_PIECE_ACTIVITY (line 378-384) is a catch-all: any blunder
    where engine's best is non-forcing AND user's move is non-pawn.
    Catches calculation failures and labels them as positional.
  - GAP_KING_SAFETY (line 317-326) fires from POSITION pressure, not
    MOVE characteristics. If the user's king is already under pressure
    from earlier blunders, every subsequent mistake gets tagged
    king_safety regardless of whether the move had anything to do
    with the king.

This script walks N recent analyzed games and, for each tagged move,
runs a sanity verifier:

  - piece_activity should NOT fire when the user dropped material
    (that's a calculation/tactical gap, not a piece-activity habit)
  - king_safety should NOT fire when the user's move was not related
    to the king (didn't move the king, didn't change king's pawn
    shield, didn't fail to defend the king when threatened)

Outputs distribution of tags + samples of mis-fires per tag, so we
have hard data on how broken the classifier is before the fix.

Usage:
    python scripts/cognitive_gap_audit.py --output /tmp/gap_audit.txt
    python scripts/cognitive_gap_audit.py --limit 30
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import chess

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def _played_drops_material(
    fen_before: str, played_uci: str, threshold_cp: int = 100
) -> Tuple[bool, int]:
    """Did the played move drop ≥ threshold_cp of material to a
    forced opp recapture? Returns (dropped, cp_lost).

    cp_lost is the rough material delta from a worst-case opp response
    on the destination square (SEE-style). If positive, user is
    dropping that much material on the move."""
    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(played_uci)
        if mv not in board.legal_moves:
            return False, 0
        moving_piece = board.piece_at(mv.from_square)
        if not moving_piece:
            return False, 0
        attacker_value = _PIECE_VALUE.get(moving_piece.piece_type, 0)
        # Apply move
        board.push(mv)
        user_color = not board.turn  # the side that just moved
        # Did user's piece end up on a square attacked by opp?
        attackers = board.attackers(not user_color, mv.to_square)
        if not attackers:
            return False, 0
        # Cheapest opp attacker
        cheapest = min(
            _PIECE_VALUE.get(board.piece_at(a).piece_type, 99)
            for a in attackers
            if board.piece_at(a)
        )
        # Defenders of our piece on that square
        defenders = board.attackers(user_color, mv.to_square)
        # Net material lost: attacker_value - (anything we capture back)
        # Conservative: if no defenders, full attacker_value lost.
        if not defenders:
            return attacker_value > 0, attacker_value * 100  # convert to cp
        # With defenders, cp_lost = max(0, attacker_value - cheapest_attacker)
        cp_lost = max(0, attacker_value - cheapest) * 100
        return cp_lost >= threshold_cp, cp_lost
    except Exception:
        return False, 0


def _move_involves_king(played_uci: str, fen_before: str) -> bool:
    """Did the played move involve the user's king (move it OR break
    its pawn shield in front of a castled king)?"""
    if not played_uci or len(played_uci) < 4 or not fen_before:
        return False
    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(played_uci)
        moving_piece = board.piece_at(mv.from_square)
        if not moving_piece:
            return False
        if moving_piece.piece_type == chess.KING:
            return True
        # Pawn move from king's pawn-shield square (castled)?
        if moving_piece.piece_type != chess.PAWN:
            return False
        user_color = moving_piece.color
        king_sq = board.king(user_color)
        if king_sq is None:
            return False
        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)
        pf = chess.square_file(mv.from_square)
        pr = chess.square_rank(mv.from_square)
        # King near corner (likely castled), pawn one rank ahead of king
        # within 2 files = pawn shield
        castled_rank = 0 if user_color == chess.WHITE else 7
        if kr == castled_rank and abs(kf - pf) <= 2 and pr == kr + (1 if user_color == chess.WHITE else -1):
            return True
        return False
    except Exception:
        return False


def _move_against_king_threat(fen_before: str) -> bool:
    """Was there a king-related threat on the position to address —
    i.e., is opp threatening checkmate or material loss to a king
    attack? Cheap proxy: ≥3 opp attackers on squares adjacent to user
    king OR user is already in check."""
    if not fen_before:
        return False
    try:
        board = chess.Board(fen_before)
        if board.is_check():
            return True
        user_color = board.turn
        king_sq = board.king(user_color)
        if king_sq is None:
            return False
        opp = not user_color
        adj = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
        attacker_count = sum(1 for sq in adj if board.attackers(opp, sq))
        return attacker_count >= 3
    except Exception:
        return False


# ── Verifiers ──────────────────────────────────────────────────────


def verify_piece_activity(move_eval: Dict) -> Tuple[str, str]:
    """Returns (verdict, reason).
    verdict ∈ {'verified', 'suspicious', 'misfire'}.

    piece_activity should fire when the user's pieces are passive AND
    the engine's recommendation is a quiet improving move. It should
    NOT fire when the user just dropped material — that's a tactical
    or calculation gap, not piece activity.
    """
    fen_before = move_eval.get("fen_before") or ""
    played_uci = move_eval.get("move_uci") or ""
    best_san = move_eval.get("best_move_san") or move_eval.get("best_move") or ""
    cp_loss = move_eval.get("cp_loss") or 0
    severity = (move_eval.get("evaluation") or "").lower()

    # Check 1: did the user drop material on this move? if yes, misfire.
    dropped, cp_lost = _played_drops_material(fen_before, played_uci, threshold_cp=200)
    if dropped:
        return ("misfire", f"played move drops ~{cp_lost}cp of material — this is a calculation/tactical gap, not piece activity")

    # Check 2: did engine's best contain a tactic (capture/check)?
    if best_san and any(c in best_san for c in ("x", "+", "#")):
        return ("misfire", f"engine's best ({best_san}) is a forcing move — user missed a tactic, not 'piece activity'")

    # Check 3: was the played move itself a capture or check?
    # Captures aren't passive moves by definition.
    if "x" in (move_eval.get("move_san") or "") or "+" in (move_eval.get("move_san") or "") or "#" in (move_eval.get("move_san") or ""):
        return ("suspicious", f"played move {move_eval.get('move_san')} was a capture/check — calling this 'passive' is suspect")

    # Severity check: at blunder level it's almost never piece activity
    if severity == "blunder" and cp_loss >= 300:
        return ("suspicious", "blunder severity (>=300cp) is rarely a piece-activity issue; usually tactical")

    return ("verified", "no obvious mis-fire signal")


def verify_king_safety(move_eval: Dict) -> Tuple[str, str]:
    """king_safety should fire when the user's MOVE specifically
    relates to the king (moves it, breaks its shield, fails to address
    a king-side threat). Should NOT fire just because the king was
    under pressure from prior moves."""
    fen_before = move_eval.get("fen_before") or ""
    played_uci = move_eval.get("move_uci") or ""

    # Check 1: did the move involve the king or its pawn shield?
    if _move_involves_king(played_uci, fen_before):
        return ("verified", "move involved king or king's pawn shield")

    # Check 2: was there a king-related threat to address?
    if _move_against_king_threat(fen_before):
        # Was this a defensive move? Check played san for capture/check
        played_san = move_eval.get("move_san") or ""
        if "x" not in played_san and "+" not in played_san:
            return ("verified", "king under pressure pre-move and player ignored it")

    # Otherwise: king_safety tag fired but move had nothing to do with king
    return ("misfire", "move didn't involve king nor address a king-side threat")


def verify_other(move_eval: Dict, gap: str) -> Tuple[str, str]:
    """Lightweight verifier for the other gap types — just confirm
    severity and basic shape match."""
    return ("not_audited", f"verifier not implemented for {gap}")


VERIFIERS = {
    "piece_activity": verify_piece_activity,
    "king_safety": verify_king_safety,
}


# ── Runner ─────────────────────────────────────────────────────────


async def run(args) -> str:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Pull recent analyzed games
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    gap_total: Counter = Counter()
    verdict_per_gap: Dict[str, Counter] = defaultdict(Counter)
    misfire_examples: Dict[str, List[Dict]] = defaultdict(list)
    games_processed = 0
    moves_with_gap = 0

    async for ga in cursor:
        sa = ga.get("stockfish_analysis") or {}
        moves = sa.get("move_evaluations") or []
        for me in moves:
            gap = me.get("cognitive_gap")
            if not gap:
                continue
            moves_with_gap += 1
            gap_total[gap] += 1

            verifier = VERIFIERS.get(gap, lambda m: verify_other(m, gap))
            verdict, reason = verifier(me)
            verdict_per_gap[gap][verdict] += 1

            if verdict == "misfire" and len(misfire_examples[gap]) < 5:
                misfire_examples[gap].append({
                    "game_id": ga.get("game_id", "?"),
                    "move_san": me.get("move_san") or me.get("move"),
                    "best_san": me.get("best_move_san") or me.get("best_move"),
                    "severity": me.get("evaluation"),
                    "cp_loss": me.get("cp_loss"),
                    "fen": (me.get("fen_before") or "")[:60],
                    "reason": reason,
                })
        games_processed += 1
        if games_processed % 50 == 0:
            print(f"  ... {games_processed} games processed", flush=True)

    client.close()

    # ── Build report ────────────────────────────────────────────────
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("COGNITIVE GAP CLASSIFIER AUDIT")
    lines.append("=" * 78)
    lines.append(f"  games processed:   {games_processed}")
    lines.append(f"  moves with gap:    {moves_with_gap}")
    lines.append("")

    lines.append("GAP DISTRIBUTION:")
    lines.append("-" * 78)
    total = sum(gap_total.values()) or 1
    for gap, n in gap_total.most_common():
        pct = 100.0 * n / total
        lines.append(f"  {n:6d}  {pct:5.1f}%  {gap}")
    lines.append("")

    # Per-gap verifier accuracy where we have a verifier
    lines.append("VERIFIER ACCURACY (only for gaps with a verifier):")
    lines.append("-" * 78)
    for gap, counts in verdict_per_gap.items():
        if gap not in VERIFIERS:
            continue
        gtotal = sum(counts.values()) or 1
        verified = counts.get("verified", 0)
        suspicious = counts.get("suspicious", 0)
        misfire = counts.get("misfire", 0)
        lines.append(
            f"  {gap}:"
            f" verified {verified}/{gtotal} ({100.0*verified/gtotal:.1f}%)"
            f" | suspicious {suspicious}"
            f" | misfire {misfire}/{gtotal} ({100.0*misfire/gtotal:.1f}%)"
        )
    lines.append("")

    # Misfire samples
    if any(misfire_examples.values()):
        lines.append("MISFIRE SAMPLES (up to 5 per gap):")
        lines.append("-" * 78)
        for gap, samples in misfire_examples.items():
            if not samples:
                continue
            lines.append(f"  {gap}:")
            for s in samples:
                lines.append(
                    f"    {s['game_id']}  {s['move_san']} "
                    f"(best: {s['best_san']}, severity: {s['severity']}, cp_loss: {s['cp_loss']})"
                )
                lines.append(f"      reason: {s['reason']}")
                lines.append(f"      fen:    {s['fen']}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=50, help="cap to first N analyzed games (default 50)")
    p.add_argument("--output", default=None)
    args = p.parse_args()

    report = asyncio.run(run(args))
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print()
        print(report)
