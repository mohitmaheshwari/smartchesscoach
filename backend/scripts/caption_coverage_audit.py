"""
Caption coverage audit — turns 2985 analyzed games into a detector
backlog by reporting which caption sources fire how often, where the
'good_generic' fallback dominates, and where the engine_fallback hits.

Output is a human-readable report:

  1. Coverage by source label (template:* / opening:* / middlegame:* /
     endgame:* / good_castle / good_capture / etc. / engine_fallback /
     silent)
  2. Per-source examples (top 5 sample positions per source)
  3. 'good_generic' hot spots — positions where the routine-move
     fallback fires repeatedly. These are detector candidates.
  4. Phase distribution of uncovered moves (opening / middlegame /
     endgame).

Usage:
    python scripts/caption_coverage_audit.py
    python scripts/caption_coverage_audit.py --limit 100   # quick subset
    python scripts/caption_coverage_audit.py --output /tmp/coverage.txt
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

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _build_v5_from_pgn_and_stockfish(pgn: str, stockfish_moves: list, user_color: str) -> list:
    """Walk the full PGN to build a list of v5-shaped records covering
    BOTH colours' moves. Stockfish's move_evaluations only stores the
    user's own moves, so without this the opp moves are missing from
    history_san and opening_book can never match.

    For each ply:
      - san, fen_before, move_number derived from python-chess walk
      - is_user_move from ply parity vs user_color
      - if it's a user move, attach severity/best_move/pv from the
        matching stockfish record (matched by SAN + move_number)
      - if it's an opp move, mark as severity="best" so it just
        contributes to history_san without triggering caption logic
    """
    if not pgn:
        return []
    try:
        import io
        import chess
        import chess.pgn
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game:
            return []
    except Exception:
        return []

    # Index user-move stockfish records by (move_number, move_san) for fast lookup
    sf_index = {}
    for me in stockfish_moves:
        san = me.get("move_san") or me.get("move") or ""
        mn = me.get("move_number")
        if san and mn is not None:
            sf_index[(mn, san)] = me

    out = []
    board = game.board()
    ply = 0
    for move in game.mainline_moves():
        ply += 1
        is_white_move = board.turn == chess.WHITE
        san = board.san(move)
        fen_before = board.fen()
        full_move_number = (ply + 1) // 2  # ply 1,2 → mn 1; ply 3,4 → mn 2
        is_user_move = (
            (user_color == "white" and is_white_move)
            or (user_color == "black" and not is_white_move)
        )
        rec = {
            "move_number": full_move_number,
            "move_san": san,
            "is_user_move": is_user_move,
            "fen_before": fen_before,
        }
        if is_user_move:
            me = sf_index.get((full_move_number, san)) or {}
            raw_eval = (me.get("evaluation") or "good").lower()
            severity_map = {
                "best": "best", "brilliant": "best", "excellent": "best",
                "good": "good", "inaccuracy": "inaccuracy",
                "mistake": "mistake", "blunder": "blunder",
            }
            rec["severity"] = severity_map.get(raw_eval, "good")
            rec["best_move_san"] = me.get("best_move_san") or me.get("best_move") or ""
            rec["pv_after_best"] = me.get("pv_after_best") or []
            rec["pv_after_played"] = me.get("pv_after_played") or []
        else:
            rec["severity"] = "best"
            rec["best_move_san"] = ""
            rec["pv_after_best"] = []
            rec["pv_after_played"] = []
        # Phase
        if full_move_number <= 12:
            rec["phase"] = "opening"
        elif full_move_number <= 30:
            rec["phase"] = "middlegame"
        else:
            rec["phase"] = "endgame"
        out.append(rec)
        board.push(move)
    return out


def _adapt_stockfish_record(me: dict, user_color: str) -> dict:
    """Convert one stockfish_analysis.move_evaluations record to the
    V5-shaped record the audit pipeline expects. Field-name and
    semantic adaptation only — no inference beyond what's stored."""
    san = me.get("move_san") or me.get("move") or ""
    best_san = me.get("best_move_san") or me.get("best_move") or ""
    fen_before = me.get("fen_before") or ""

    # Prefer the record's own is_user_move if analysis_worker set it;
    # fall back to FEN side-to-move parsing.
    if "is_user_move" in me:
        is_user_move = bool(me.get("is_user_move"))
    else:
        is_user_move = False
        if fen_before:
            try:
                import chess
                b = chess.Board(fen_before)
                mover = "white" if b.turn else "black"
                is_user_move = (mover == (user_color or "white"))
            except Exception:
                pass

    # severity = MoveClassification string already lower-case ("blunder",
    # "mistake", "inaccuracy", "good", "excellent", "best"); map
    # excellent/best → "best", good → "good".
    raw_eval = (me.get("evaluation") or "good").lower()
    severity_map = {
        "best": "best",
        "brilliant": "best",
        "excellent": "best",
        "good": "good",
        "inaccuracy": "inaccuracy",
        "mistake": "mistake",
        "blunder": "blunder",
    }
    severity = severity_map.get(raw_eval, "good")

    # Phase: opening ≤12, middlegame 13-30, endgame 31+
    mn = me.get("move_number") or 0
    if mn <= 12:
        phase = "opening"
    elif mn <= 30:
        phase = "middlegame"
    else:
        phase = "endgame"

    return {
        "move_number": mn,
        "move_san": san,
        "is_user_move": is_user_move,
        "severity": severity,
        "phase": phase,
        "best_move_san": best_san,
        "pv_after_best": me.get("pv_after_best") or [],
        "pv_after_played": me.get("pv_after_played") or [],
        "fen_before": fen_before,
    }


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Lazy import so the script can be run from a clean checkout
    from services.decryption_voice.per_move_caption import caption_for_move

    # Cover EVERY analyzed game: prefer decryption_v5_data when present,
    # else fall back to stockfish_analysis.move_evaluations. The latter
    # exists for the full analyzed corpus (~2985 games); V5 ran on a
    # subset only.
    cursor = db.game_analyses.find(
        {
            "$or": [
                {"decryption_v5_data": {"$exists": True, "$ne": []}},
                {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}},
            ]
        },
        {
            "_id": 0,
            "game_id": 1,
            "decryption_v5_data": 1,
            "decryption_block": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    )
    if args.limit and args.limit > 0:
        cursor = cursor.limit(args.limit)
    games_from_v5 = 0
    games_from_stockfish = 0
    # Diagnostics for the opening_book fire rate
    diag = {
        "ob_attempts": 0,        # times caption_for_move was invoked with mn<=12
        "ob_no_history": 0,      # invocations where history_san was empty
        "ob_empty_san": 0,       # records skipped due to empty san
        "ob_no_fen": 0,          # records skipped due to empty fen_before
        "first_stockfish_dump": True,
    }

    # Cache user_color per game.
    user_colors = {}

    source_counts = Counter()
    severity_x_source = defaultdict(Counter)  # severity → source counts
    phase_x_source = defaultdict(Counter)
    sample_by_source = defaultdict(list)  # source → list of (game_id, move_n, san, fen, text)
    generic_by_signature = Counter()  # signature → count (for hot-spot mining)
    generic_examples = defaultdict(list)
    games_processed = 0
    moves_processed = 0

    async for ga in cursor:
        gid = ga["game_id"]
        if gid not in user_colors:
            g = await db.games.find_one({"game_id": gid}, {"_id": 0, "user_color": 1})
            user_colors[gid] = (g or {}).get("user_color", "white")
        user_color = user_colors[gid]

        v5 = ga.get("decryption_v5_data") or []
        if v5:
            games_from_v5 += 1
        else:
            # Fall back to stockfish_analysis.move_evaluations. CRITICAL:
            # stockfish only stores the USER's moves, so we have to walk
            # the PGN to recover the opp moves — otherwise history_san
            # is half-empty and opening_book can never match.
            sf = (ga.get("stockfish_analysis") or {}).get("move_evaluations") or []
            if not sf:
                continue
            # Need PGN to interleave opp moves
            game_doc = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1})
            pgn = (game_doc or {}).get("pgn") or ""
            v5 = _build_v5_from_pgn_and_stockfish(pgn, sf, user_color)
            if not v5:
                # No PGN — fall back to user-only adapter (history will be
                # incomplete but at least we get something).
                v5 = [_adapt_stockfish_record(me, user_color) for me in sf]
            games_from_stockfish += 1
        moments_index = {}
        for m in ((ga.get("decryption_block") or {}).get("moments") or []):
            moments_index[(m.get("move_number"), m.get("move_san"))] = m

        history_san = []
        for rec in v5:
            san = rec.get("move_san")
            mn = rec.get("move_number")
            if not san or mn is None:
                if not san:
                    diag["ob_empty_san"] += 1
                history_san.append(san or "")
                continue
            is_user_move = bool(rec.get("is_user_move"))
            if not is_user_move:
                # Track history for opening recognition but skip
                # opp moves from coverage stats — we care about user
                # experience.
                history_san.append(san)
                continue

            severity = rec.get("severity") or "unknown"
            phase = rec.get("phase") or "unknown"
            best_san = rec.get("best_move_san")
            pv_best = rec.get("pv_after_best") or []
            pv_played = rec.get("pv_after_played") or []
            fen_before = rec.get("fen_before") or ""

            # Reset per-iteration so a stale `result` from the previous
            # move doesn't leak into the override-path sample text.
            result = None
            sample_text = ""

            override = moments_index.get((mn, san))
            if override and override.get("text"):
                source = override.get("source", "decryption_block")
                sample_text = override.get("text", "")
            else:
                if mn <= 12:
                    diag["ob_attempts"] += 1
                    if not history_san:
                        diag["ob_no_history"] += 1
                if not fen_before:
                    diag["ob_no_fen"] += 1
                try:
                    result = caption_for_move(
                        fen_before=fen_before,
                        move_san=san,
                        move_number=mn,
                        severity=severity,
                        best_move_san=best_san,
                        pv_after_best=pv_best,
                        pv_after_played=pv_played,
                        user_color=user_color,
                        is_user_move=True,
                        move_history_san=list(history_san),
                    )
                except Exception:
                    result = None
                source = result.source if result else "silent"
                sample_text = result.text if result else ""

            source_counts[source] += 1
            severity_x_source[severity][source] += 1
            phase_x_source[phase][source] += 1
            moves_processed += 1

            if len(sample_by_source[source]) < 5:
                sample_by_source[source].append({
                    "game_id": gid,
                    "move": f"M{mn} {san}",
                    "fen": fen_before,
                    "text": (sample_text or "")[:80],
                })

            # Hot-spot mining for good_generic — group by (piece-letter,
            # destination-square) so we see which routine moves keep
            # falling through. e.g., 'N→f6' or 'K→g1'.
            if source == "good_generic":
                # Cheap signature: first letter of SAN (piece) + dest square.
                # For pawn moves, use 'p' + dest.
                if san and san[0].isupper():
                    sig = f"{san[0]}→{san[-2:]}"
                else:
                    sig = f"p→{san[:2] if not san[-1].isalpha() else san[-2:]}"
                generic_by_signature[sig] += 1
                if len(generic_examples[sig]) < 3:
                    generic_examples[sig].append({
                        "game_id": gid,
                        "move": f"M{mn} {san}",
                        "fen": fen_before,
                    })

            history_san.append(san)
        games_processed += 1
        if games_processed % 100 == 0:
            print(f"  ... {games_processed} games processed", flush=True)

    client.close()

    # ── Build report ─────────────────────────────────────────────────
    lines = []
    lines.append("=" * 78)
    lines.append("CAPTION COVERAGE AUDIT")
    lines.append("=" * 78)
    lines.append(f"  games processed:  {games_processed}")
    lines.append(f"    via V5 data:    {games_from_v5}")
    lines.append(f"    via stockfish:  {games_from_stockfish}")
    lines.append(f"  user moves total: {moves_processed}")
    lines.append("")
    lines.append("DIAGNOSTICS:")
    lines.append(f"  opening_book attempts (mn<=12):  {diag['ob_attempts']}")
    lines.append(f"  attempts with empty history:     {diag['ob_no_history']}")
    lines.append(f"  records with empty fen_before:   {diag['ob_no_fen']}")
    lines.append(f"  records with empty move_san:     {diag['ob_empty_san']}")
    lines.append("")

    # Coverage table. Three exclusion categories:
    #   - good_generic / engine_fallback / silent: detector gap (need work)
    #   - engine_review_needed: deliberately empty, flagged for human coach
    #     in the review tab. Counts as "needs review" not "covered".
    lines.append("COVERAGE BY SOURCE (most common first):")
    total = sum(source_counts.values()) or 1
    deterministic_count = 0
    review_count = 0
    EXCLUDED_FROM_DETERMINISTIC = {
        "engine_fallback", "silent", "good_generic", "engine_review_needed",
    }
    for src, n in source_counts.most_common():
        pct = 100.0 * n / total
        if src in ("engine_fallback", "silent", "good_generic"):
            marker = " ← needs work"
        elif src == "engine_review_needed":
            marker = " ← review tab"
        else:
            marker = ""
        lines.append(f"  {n:6d}  {pct:5.1f}%  {src}{marker}")
        if src not in EXCLUDED_FROM_DETERMINISTIC:
            deterministic_count += n
        if src == "engine_review_needed":
            review_count = n
    det_pct = 100.0 * deterministic_count / total
    review_pct = 100.0 * review_count / total
    lines.append("")
    lines.append(f"  SUBSTANTIVE COVERAGE:    {deterministic_count}/{total}  ({det_pct:.1f}%)")
    lines.append(f"  FOR HUMAN COACH REVIEW:  {review_count}/{total}  ({review_pct:.1f}%)")
    lines.append("")

    # Severity x source
    lines.append("BY SEVERITY (rows = severity, cols = source-cluster):")
    cluster_for = lambda s: (
        "template" if s.startswith("template:")
        else "opening" if s.startswith("opening:")
        else "middlegame" if s.startswith("middlegame:")
        else "endgame" if s.startswith("endgame:")
        else "good_specific" if s.startswith("good_") and s != "good_generic"
        else "good_generic" if s == "good_generic"
        else "engine_fallback" if s == "engine_fallback"
        else "silent" if s == "silent"
        else "other"
    )
    cluster_order = ["template", "opening", "middlegame", "endgame", "good_specific", "good_generic", "engine_fallback", "silent", "other"]
    sev_table = defaultdict(lambda: defaultdict(int))
    for sev, ctr in severity_x_source.items():
        for src, n in ctr.items():
            sev_table[sev][cluster_for(src)] += n
    header = f"  {'severity':<14}" + "".join(f"{c:>14}" for c in cluster_order)
    lines.append(header)
    for sev in ("blunder", "mistake", "inaccuracy", "good", "best", "book", "context", "unknown"):
        if sev not in sev_table:
            continue
        row = f"  {sev:<14}"
        for c in cluster_order:
            row += f"{sev_table[sev][c]:>14}"
        lines.append(row)
    lines.append("")

    # Top 'good_generic' signatures — highest-leverage detector candidates
    lines.append("TOP 'good_generic' SIGNATURES (uncovered routine moves):")
    lines.append("These are the highest-leverage spots to add detectors.")
    for sig, n in generic_by_signature.most_common(25):
        lines.append(f"  {n:5d}  {sig}")
        for ex in generic_examples[sig][:1]:
            lines.append(f"          example: {ex['game_id']}  {ex['move']}")
            lines.append(f"          fen: {ex['fen']}")
    lines.append("")

    # Sample positions per source
    lines.append("SAMPLE POSITIONS BY SOURCE (5 each):")
    for src in source_counts.most_common():
        src_label, _ = src
        lines.append(f"  {src_label}:")
        for ex in sample_by_source[src_label]:
            lines.append(f"    {ex['game_id']}  {ex['move']}: {ex['text']}")
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
    p.add_argument("--output", default=None, help="write report to file")
    args = p.parse_args()
    asyncio.run(main(args))
