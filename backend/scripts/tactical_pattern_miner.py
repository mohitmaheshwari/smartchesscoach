"""
Tactical pattern miner — clusters mistake/blunder positions across
the 2985-game corpus by board-shape signatures, surfacing the
recurring tactical shapes our detectors don't yet catch.

For each user mistake / blunder / inaccuracy in decryption_v5_data,
we extract a coarse signature like:

   blunder | middlegame | played=N | best=Q | cap_played=N | cap_best=Y |
   chk_given=N | chk_recv=N | queens=Y

Then group by signature and rank by frequency. The most common
signatures are the recurring shapes — each one is a candidate for
a new detector or a sharpened existing detector.

Secondary outputs:
  - Top 'best-move motifs' — what was the engine's best in these
    positions? (capture, check, fork-like move, etc.)
  - Hanging-piece signatures — positions where the user's played
    move left an own piece undefended-and-attacked (≥minor)
  - 'Same square' clusters — destinations the engine wanted to use
    repeatedly (e.g., Nd5, Bxh6) that the user never played

Usage:
    python scripts/tactical_pattern_miner.py
    python scripts/tactical_pattern_miner.py --limit 200
    python scripts/tactical_pattern_miner.py --severity blunder
    python scripts/tactical_pattern_miner.py --output /tmp/tactics.txt
"""

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import chess

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _piece_letter(san: str) -> str:
    """First letter of SAN piece, or 'p' for pawn moves."""
    if not san:
        return "?"
    s = san.replace("+", "").replace("#", "").replace("!", "").replace("?", "")
    if s and s[0].isupper() and s[0] in "NBRQK":
        return s[0]
    return "p"


def _is_capture(san: str) -> bool:
    return "x" in (san or "")


def _gives_check(san: str) -> bool:
    return "+" in (san or "") or "#" in (san or "")


def _dest_square(san: str) -> str:
    """Best-effort destination square from SAN."""
    if not san:
        return "?"
    s = san.replace("+", "").replace("#", "").replace("!", "").replace("?", "")
    s = s.replace("=Q", "").replace("=R", "").replace("=B", "").replace("=N", "")
    if s in ("O-O", "O-O-O", "0-0", "0-0-0"):
        return "castle"
    # last 2 chars are usually the destination
    if len(s) >= 2 and s[-2].isalpha() and s[-1].isdigit():
        return s[-2:]
    return "?"


def _user_in_check(fen: str) -> bool:
    try:
        b = chess.Board(fen)
        return b.is_check()
    except Exception:
        return False


def _has_queens(fen: str) -> bool:
    try:
        b = chess.Board(fen)
        return bool(b.pieces(chess.QUEEN, chess.WHITE) or b.pieces(chess.QUEEN, chess.BLACK))
    except Exception:
        return False


def _hanging_after(fen: str, played_san: str) -> bool:
    """Did the played move leave any of the user's own pieces (≥minor)
    undefended AND attacked? Cheap proxy for blunder-by-hanging."""
    try:
        b = chess.Board(fen)
        mv = b.parse_san(played_san)
        b.push(mv)
        # After our move it's opponent to move; we look at our (not-turn)
        # pieces and check if opp attacks any undefended ≥minor piece.
        our_color = not b.turn
        opp_color = b.turn
        for sq in chess.SQUARES:
            p = b.piece_at(sq)
            if not p or p.color != our_color:
                continue
            if p.piece_type in (chess.PAWN, chess.KING):
                continue
            attackers = b.attackers(opp_color, sq)
            if not attackers:
                continue
            defenders = b.attackers(our_color, sq)
            if not defenders:
                return True
            # Defended but attacker is cheaper (simplified) — treat as
            # hanging too if attacker piece value < defender's piece
            # value… but this gets noisy; keep simple for now.
        return False
    except Exception:
        return False


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cursor = db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True, "$ne": []}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
    )
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)

    severities_wanted = set(args.severity.split(",")) if args.severity else {"mistake", "blunder", "inaccuracy"}

    sig_counts = Counter()
    sig_examples = defaultdict(list)
    best_motif_counts = Counter()
    best_dest_counts = Counter()
    hanging_sig_counts = Counter()
    hanging_examples = defaultdict(list)
    moves_processed = 0
    games_processed = 0

    async for ga in cursor:
        gid = ga["game_id"]
        v5 = ga.get("decryption_v5_data") or []
        for rec in v5:
            if not rec.get("is_user_move"):
                continue
            sev = rec.get("severity") or "unknown"
            if sev not in severities_wanted:
                continue
            phase = rec.get("phase") or "unknown"
            played = rec.get("move_san") or ""
            best = rec.get("best_move_san") or ""
            fen_before = rec.get("fen_before") or ""

            played_piece = _piece_letter(played)
            best_piece = _piece_letter(best)
            cap_played = "Y" if _is_capture(played) else "N"
            cap_best = "Y" if _is_capture(best) else "N"
            chk_given = "Y" if _gives_check(best) else "N"
            chk_recv = "Y" if _user_in_check(fen_before) else "N"
            qs = "Y" if _has_queens(fen_before) else "N"

            sig = (
                f"{sev:9s} | {phase:10s} | played={played_piece} | best={best_piece} | "
                f"cap_played={cap_played} | cap_best={cap_best} | "
                f"chk_given={chk_given} | chk_recv={chk_recv} | queens={qs}"
            )
            sig_counts[sig] += 1
            if len(sig_examples[sig]) < 3:
                sig_examples[sig].append({
                    "game_id": gid,
                    "move": f"M{rec.get('move_number')} {played} (best={best})",
                    "fen": fen_before,
                })

            # Best-move motif: piece + capture/check
            motif = f"{best_piece}{'x' if cap_best == 'Y' else ''}{'+' if chk_given == 'Y' else ''}"
            best_motif_counts[motif] += 1

            # Best-move destination square — recurring engine ideas
            best_dest_counts[_dest_square(best)] += 1

            # Hanging-piece detection
            if _hanging_after(fen_before, played):
                hsig = f"{sev:9s} | {phase:10s} | played={played_piece} | hanging_after=Y"
                hanging_sig_counts[hsig] += 1
                if len(hanging_examples[hsig]) < 3:
                    hanging_examples[hsig].append({
                        "game_id": gid,
                        "move": f"M{rec.get('move_number')} {played}",
                        "fen": fen_before,
                    })

            moves_processed += 1
        games_processed += 1
        if games_processed % 100 == 0:
            print(f"  ... {games_processed} games processed", flush=True)

    client.close()

    # ── Build report ─────────────────────────────────────────────────
    lines = []
    lines.append("=" * 78)
    lines.append("TACTICAL PATTERN MINER")
    lines.append("=" * 78)
    lines.append(f"  games processed:        {games_processed}")
    lines.append(f"  user mistakes mined:    {moves_processed}")
    lines.append(f"  severity filter:        {sorted(severities_wanted)}")
    lines.append("")

    # 1. Top board-shape signatures
    lines.append("TOP MISTAKE SIGNATURES (recurring shapes — detector candidates):")
    lines.append("-" * 78)
    for sig, n in sig_counts.most_common(args.top):
        lines.append(f"  {n:5d}  {sig}")
        for ex in sig_examples[sig][:1]:
            lines.append(f"          example: {ex['game_id']}  {ex['move']}")
            lines.append(f"          fen: {ex['fen']}")
    lines.append("")

    # 2. Best-move motifs
    lines.append("BEST-MOVE MOTIFS (what the engine wanted instead):")
    lines.append("-" * 78)
    motif_total = sum(best_motif_counts.values()) or 1
    for motif, n in best_motif_counts.most_common(20):
        pct = 100.0 * n / motif_total
        lines.append(f"  {n:5d}  {pct:5.1f}%  best={motif}")
    lines.append("")

    # 3. Engine destination square clusters
    lines.append("ENGINE'S FAVOURITE DESTINATION SQUARES (top 30):")
    lines.append("(Squares the engine wanted to reach repeatedly — manoeuvre detectors.)")
    lines.append("-" * 78)
    for sq, n in best_dest_counts.most_common(30):
        lines.append(f"  {n:5d}  → {sq}")
    lines.append("")

    # 4. Hanging-piece patterns
    lines.append("HANGING-PIECE SIGNATURES (played move left a piece undefended & attacked):")
    lines.append("-" * 78)
    for sig, n in hanging_sig_counts.most_common(20):
        lines.append(f"  {n:5d}  {sig}")
        for ex in hanging_examples[sig][:1]:
            lines.append(f"          example: {ex['game_id']}  {ex['move']}")
            lines.append(f"          fen: {ex['fen']}")
    lines.append("")

    output = "\n".join(lines)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print()
        print(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="cap to first N games (0 = all)")
    p.add_argument("--severity", default="", help="comma-list (mistake,blunder,inaccuracy). Empty = all three.")
    p.add_argument("--top", type=int, default=40, help="rows in top-signatures table")
    p.add_argument("--output", default=None, help="write report to file")
    args = p.parse_args()
    asyncio.run(main(args))
