"""
Export flagged decryption moments as a markdown report ready to paste
into a Claude Code chat.

Workflow (zero external cost):

  1. Run this on the server. Outputs a markdown file with every
     flagged moment — full position, both PVs in SAN, cp_loss, current
     engine_fallback text, existing override (if any).

  2. Open Claude Code on your machine. Paste the file's contents.

  3. Claude analyzes each moment, proposes:
        - one-off override captions (writes to proposed_overrides.json)
        - detector code changes (edits the dispatcher / templates
          and commits)

  4. Run apply_proposed_overrides.py (sister script) to bulk-insert
     the override JSON into coach_overrides. Pull + redeploy backend
     for the detector code changes.

  5. Re-run batch_voice_regen — queue clears.

Usage:
    python scripts/export_flagged_for_claude.py
    python scripts/export_flagged_for_claude.py --output /tmp/flagged.md
    python scripts/export_flagged_for_claude.py --limit 10
    python scripts/export_flagged_for_claude.py --include-overridden
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")


def _pv_uci_to_san(fen_before: str, first_san: Optional[str], pv_uci: List[str], max_ply: int = 6) -> str:
    """Convert (first move SAN + UCI continuation) into a SAN sequence
    starting from fen_before. Empty string on parse failure."""
    if not first_san:
        return ""
    try:
        board = chess.Board(fen_before)
        sans = []
        try:
            m = board.parse_san(first_san)
            sans.append(first_san)
            board.push(m)
        except Exception:
            return ""
        for uci in (pv_uci or [])[:max_ply]:
            try:
                mv = chess.Move.from_uci(uci)
                if mv not in board.legal_moves:
                    break
                sans.append(board.san(mv))
                board.push(mv)
            except Exception:
                break
        return " ".join(sans)
    except Exception:
        return ""


async def main(args) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Load all overrides once for fast lookup.
    overrides_by_key = {}
    async for ov in db.coach_overrides.find({}, {"_id": 0}):
        key = (ov.get("game_id"), ov.get("move_number"), ov.get("move_san"))
        overrides_by_key[key] = ov

    # Pull every analysis with at least one moment, walk them.
    rows: List[Dict] = []
    async for ga in db.game_analyses.find(
        {"decryption_block.moments.0": {"$exists": True}},
        {"_id": 0, "game_id": 1, "user_id": 1, "decryption_block": 1, "decryption_v5_data": 1},
    ):
        gid = ga.get("game_id")
        moments = (ga.get("decryption_block") or {}).get("moments") or []
        v5_records = ga.get("decryption_v5_data") or []
        for m in moments:
            if not m.get("needs_review"):
                continue
            # Look up the matching V5 record for richer fields.
            mn = m.get("move_number")
            ms = m.get("move_san")
            v5 = next(
                (r for r in v5_records
                 if r.get("is_user_move")
                 and r.get("move_number") == mn
                 and r.get("move_san") == ms),
                None,
            )
            ov = overrides_by_key.get((gid, mn, ms))
            if ov and not args.include_overridden:
                continue

            fen = m.get("fen_before") or ""
            user_color = "white" if (fen.split(" ") or [""])[1] == "w" else "black"
            best_san = (v5 or {}).get("best_move_san") or next(
                (c.get("san") for c in (m.get("candidates") or []) if c.get("isCorrect")),
                "",
            )
            pv_best_san = _pv_uci_to_san(
                fen, best_san, (v5 or {}).get("pv_after_best") or [],
            )
            pv_played_san = _pv_uci_to_san(
                fen, ms, (v5 or {}).get("pv_after_played") or [],
            )
            rows.append({
                "game_id": gid,
                "user_id": ga.get("user_id"),
                "move_number": mn,
                "move_san": ms,
                "user_color": user_color,
                "fen_before": fen,
                "best_move_san": best_san,
                "pv_after_best_san": pv_best_san,
                "pv_after_played_san": pv_played_san,
                "cp_loss": m.get("cp_loss"),
                "severity": m.get("severity"),
                "eval_before": (v5 or {}).get("eval_before"),
                "eval_after": (v5 or {}).get("eval_after"),
                "current_text": m.get("text"),
                "source": m.get("source"),
                "confidence": m.get("confidence"),
                "existing_override": (ov or {}).get("override_text") if ov else None,
                "existing_coach_note": (ov or {}).get("coach_note") if ov else None,
            })

    # Game metadata for opening name.
    game_meta = {}
    if rows:
        gids = list({r["game_id"] for r in rows})
        async for g in db.games.find(
            {"game_id": {"$in": gids}},
            {"_id": 0, "game_id": 1, "opening": 1, "user_color": 1, "result": 1},
        ):
            game_meta[g["game_id"]] = g

    client.close()

    # Sort by confidence ascending (worst first).
    rows.sort(key=lambda r: (r.get("confidence") or 0, r.get("game_id") or ""))
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    out_lines: List[str] = []
    out_lines.append("# Flagged decryption moments — Claude Code review packet")
    out_lines.append("")
    out_lines.append(f"Total flagged: **{len(rows)}**")
    out_lines.append("")
    out_lines.append("**Instructions for Claude**: For each moment below, identify the chess pattern "
                     "(reuse existing pattern names where possible: missed_fork, missed_pin, missed_skewer, "
                     "missed_back_rank, missed_discovery, missed_overload, missed_removal, hanging_piece, "
                     "trapped_piece, walked_into_fork, walked_into_pin, walked_into_capture, walked_into_mate, "
                     "pawn_race, combination, opposition, outside_passed_pawn). For each moment, output:")
    out_lines.append("")
    out_lines.append("1. **pattern_name** + 1-line summary")
    out_lines.append("2. **proposed_caption** in Indian English voice (short SVO, no idioms, names pieces and "
                     "squares only from the FEN/PVs)")
    out_lines.append("3. If the pattern recurs across moments, **propose a detector** (Python, deterministic, "
                     "uses python-chess). Apply it directly to `services/decryption_voice/concept_dispatcher.py` "
                     "or `services/chess_brain/detector_registry.py`.")
    out_lines.append("4. For one-offs that don't merit a detector, write the override to "
                     "`backend/scripts/proposed_overrides.json` (an array of "
                     "`{game_id, move_number, move_san, override_text, coach_note}`). I'll bulk-apply via "
                     "`apply_proposed_overrides.py`.")
    out_lines.append("")
    out_lines.append("---")
    out_lines.append("")

    for i, r in enumerate(rows, 1):
        meta = game_meta.get(r["game_id"]) or {}
        out_lines.append(f"## Moment {i}/{len(rows)} — {r['game_id']} · move {r['move_number']} {r['move_san']}")
        out_lines.append("")
        if meta.get("opening"):
            out_lines.append(f"**Opening**: {meta['opening']}")
        out_lines.append(f"**User color**: {r['user_color']}  ·  **Game result**: {meta.get('result', '?')}")
        out_lines.append(f"**FEN before**: `{r['fen_before']}`")
        out_lines.append("")
        out_lines.append(f"**Played**: `{r['move_san']}`  (cp_loss={r['cp_loss']}, severity={r['severity']})")
        out_lines.append(f"**Engine best**: `{r['best_move_san']}`")
        if r["eval_before"] is not None or r["eval_after"] is not None:
            out_lines.append(f"**Eval (white POV)**: before={r['eval_before']}  after={r['eval_after']}")
        out_lines.append("")
        if r["pv_after_best_san"]:
            out_lines.append(f"**Engine line if best had been played**: `{r['pv_after_best_san']}`")
        if r["pv_after_played_san"]:
            out_lines.append(f"**Engine line after the played move**: `{r['pv_after_played_san']}`")
        out_lines.append("")
        out_lines.append(f"**Current caption**: _{r['current_text']}_")
        out_lines.append(f"**Source**: {r['source']}  ·  **Confidence**: {r['confidence']}")
        if r["existing_override"]:
            out_lines.append("")
            out_lines.append(f"**Existing override (refine, don't replace)**: {r['existing_override']}")
            if r["existing_coach_note"]:
                out_lines.append(f"  - Coach note: {r['existing_coach_note']}")
        out_lines.append("")
        out_lines.append("---")
        out_lines.append("")

    output = "\n".join(out_lines)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote {len(rows)} moment(s) to {args.output}")
    else:
        # Print to stdout so the user can pipe / copy.
        print(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=None, help="write to file (default stdout)")
    p.add_argument("--limit", type=int, default=0, help="cap to first N moments")
    p.add_argument("--include-overridden", action="store_true",
                   help="include moments that already have overrides (default: skip)")
    args = p.parse_args()
    asyncio.run(main(args))
