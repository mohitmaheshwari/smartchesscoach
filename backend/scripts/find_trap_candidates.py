"""Scan the 500-game corpus for trap-pattern candidates not yet in traps.json.

Methodology:
- Iterate v5 game_analyses (500 most recent).
- For each early blunder (move 3-15, cp_loss >= 300, played by *either* color),
  record: opening label, full PGN move-sequence prefix up to and including the
  blunder, the punishing best_move_san, fen_before, fen_after.
- Group by (opening, move_sequence_prefix) — same first-N-moves means same
  position class. A cluster with >=2 games + a clear punishment is a trap
  candidate.
- Cross-check against existing traps.json setup_moves to skip already-covered
  patterns.
- Write candidates MD with engine multipv=3 depth=15 per representative
  position so Mohit can decide which to author.

Run:
    docker cp backend/scripts/find_trap_candidates.py chess-coach-backend:/app/backend/scripts/
    docker exec chess-coach-backend python /app/backend/scripts/find_trap_candidates.py \\
        --out /tmp/trapwork/trap_candidates.md
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
from collections import defaultdict
from typing import Any

import chess
import chess.engine
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient


_STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
_TRAPS_JSON = "/app/backend/data/traps.json"


def _load_existing_setups() -> set[tuple[str, ...]]:
    """Return set of existing setup-move sequences from traps.json so we can
    skip clusters that match a trap we already cover."""
    try:
        with open(_TRAPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()
    out: set[tuple[str, ...]] = set()
    for _opening, traps in data.items():
        for t in traps:
            setup = tuple((t.get("setup_moves") or []))
            if setup:
                out.add(setup)
                # Also store prefixes of length 6/8 so partial matches catch
                for n in (6, 8, 10):
                    if len(setup) >= n:
                        out.add(setup[:n])
    return out


def _pgn_to_san_list(pgn_text: str) -> list[str]:
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return []
    if game is None:
        return []
    sans: list[str] = []
    b = game.board()
    for mv in game.mainline_moves():
        try:
            sans.append(b.san(mv))
            b.push(mv)
        except Exception:
            break
    return sans


def _engine_view(fen: str) -> dict[str, Any]:
    try:
        b = chess.Board(fen)
    except Exception:
        return {}
    try:
        with chess.engine.SimpleEngine.popen_uci(_STOCKFISH) as e:
            info = e.analyse(b, chess.engine.Limit(depth=15), multipv=3)
    except Exception as exc:
        return {"error": str(exc)}
    out = []
    for line in info:
        score = line.get("score")
        if score is None:
            continue
        cp = score.white().score(mate_score=10000)
        pv = line.get("pv") or []
        tmp = b.copy()
        sans = []
        for mv in pv[:8]:
            try:
                sans.append(tmp.san(mv))
                tmp.push(mv)
            except Exception:
                break
        out.append({"cp": cp, "pv": sans})
    return {"multipv": out}


async def main_async(out_path: str, max_games: int, min_cluster: int):
    url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db = AsyncIOMotorClient(url)["chess_coach"]
    existing_setups = _load_existing_setups()
    print(f"Loaded {len(existing_setups)} known setup signatures from traps.json")

    # Each candidate hit: {opening, prefix(tuple), blunder_san, best_san,
    #                     fen_before, fen_after, cp_loss, move_number,
    #                     blunderer_color, game_id}
    hits: list[dict[str, Any]] = []

    n_scanned = 0
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}, "decryption_v5_version": {"$gte": 53}}
    ).sort("created_at", -1).limit(max_games):
        n_scanned += 1
        gid = ga.get("game_id", "")
        gdoc = await db.games.find_one(
            {"game_id": gid}, {"_id": 0, "pgn": 1, "opening": 1, "user_color": 1}
        )
        if not gdoc:
            continue
        opening = gdoc.get("opening") or "Unknown"
        pgn_text = gdoc.get("pgn") or ""
        sans = _pgn_to_san_list(pgn_text)
        if not sans:
            continue

        # Walk the v5 move list and collect early blunders by either side.
        seen_in_game: set[tuple[int, str]] = set()
        for m in (ga.get("decryption_v5_data") or []):
            mn = m.get("move_number")
            if mn is None or mn < 3 or mn > 20:
                continue
            cpl = m.get("cp_loss")
            if cpl is None or cpl < 250:
                continue
            # Dedup within a single game (some v5 entries can appear twice
            # if both color perspectives were stored).
            dedup_key = (mn, m.get("move_san") or "")
            if dedup_key in seen_in_game:
                continue
            seen_in_game.add(dedup_key)
            # plies for move number N white = 2N-2, black = 2N-1 in 0-indexed
            # but our list is half-moves indexed by appearance. Match by reading
            # the ply count from is_white field on the v5 entry.
            is_white = m.get("is_white", True)
            ply_index = (mn - 1) * 2 + (0 if is_white else 1)
            if ply_index >= len(sans):
                continue
            # The blunder is sans[ply_index]; the prefix is sans[:ply_index]
            prefix = tuple(sans[:ply_index])
            blunder_san = sans[ply_index]
            best_san = m.get("best_move_san") or ""
            blunderer = "white" if is_white else "black"
            hits.append({
                "opening": opening,
                "prefix": prefix,
                "blunder_san": blunder_san,
                "best_san": best_san,
                "fen_before": m.get("fen_before", ""),
                "fen_after": m.get("fen_after", ""),
                "cp_loss": cpl,
                "move_number": mn,
                "blunderer_color": blunderer,
                "user_was_blunderer": bool(m.get("is_user_move")),
                "game_id": gid,
            })

    print(f"Scanned {n_scanned} games; collected {len(hits)} early-blunder hits")

    # Three-tier clustering:
    #   T1 strict: exact prefix + opening (catches verbatim repeats)
    #   T2 medium: opening + blunder_san + move_number (catches transposes)
    #   T3 loose:  opening + blunder_san (any move number)
    # Within each tier dedup by game_id so a single game can't pad a cluster.
    t1_raw: dict[tuple[str, tuple[str, ...]], dict[str, dict]] = defaultdict(dict)
    t2_raw: dict[tuple[str, str, int], dict[str, dict]] = defaultdict(dict)
    t3_raw: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for h in hits:
        gid = h["game_id"]
        t1_raw[(h["opening"], h["prefix"])].setdefault(gid, h)
        t2_raw[(h["opening"], h["blunder_san"], h["move_number"])].setdefault(gid, h)
        t3_raw[(h["opening"], h["blunder_san"])].setdefault(gid, h)
    t1 = {k: list(v.values()) for k, v in t1_raw.items()}
    t2 = {k: list(v.values()) for k, v in t2_raw.items()}
    t3 = {k: list(v.values()) for k, v in t3_raw.items()}

    def _setup_already_covered(prefix: tuple[str, ...]) -> bool:
        if prefix in existing_setups:
            return True
        for n in (6, 8, 10):
            if len(prefix) >= n and prefix[:n] in existing_setups:
                return True
        return False

    candidates: list[tuple[str, str, list[dict]]] = []  # (tier, label, group)
    seen_game_keys: set[tuple[str, int, str]] = set()  # (game_id, move_no, san) — avoid double-listing in lower tiers

    # Tier 1 first — exact prefix
    sorted_t1 = sorted(t1.items(), key=lambda kv: -len(kv[1]))
    for (opening, prefix), group in sorted_t1:
        if len(group) < min_cluster:
            continue
        if _setup_already_covered(prefix):
            continue
        pgn_pretty = []
        for j, san in enumerate(prefix):
            if j % 2 == 0:
                pgn_pretty.append(f"{(j // 2) + 1}.{san}")
            else:
                pgn_pretty[-1] += f" {san}"
        label = f"T1 strict — {opening} after {' '.join(pgn_pretty)}"
        candidates.append(("T1", label, group))
        for h in group:
            seen_game_keys.add((h["game_id"], h["move_number"], h["blunder_san"]))

    # Tier 2 — opening + blunder + move number, filtered to NEW games not in T1
    sorted_t2 = sorted(t2.items(), key=lambda kv: -len(kv[1]))
    for (opening, blunder_san, move_no), group in sorted_t2:
        # Keep group members not already shown
        new_members = [h for h in group if (h["game_id"], h["move_number"], h["blunder_san"]) not in seen_game_keys]
        if len(new_members) < min_cluster:
            continue
        label = f"T2 medium — {opening}, blunder `{blunder_san}` at move {move_no}"
        candidates.append(("T2", label, new_members))
        for h in new_members:
            seen_game_keys.add((h["game_id"], h["move_number"], h["blunder_san"]))

    # Tier 3 — opening + blunder san only, broader pattern (need >=3 to qualify)
    sorted_t3 = sorted(t3.items(), key=lambda kv: -len(kv[1]))
    t3_min = max(min_cluster + 1, 3)
    for (opening, blunder_san), group in sorted_t3:
        new_members = [h for h in group if (h["game_id"], h["move_number"], h["blunder_san"]) not in seen_game_keys]
        if len(new_members) < t3_min:
            continue
        label = f"T3 loose — {opening}, blunder `{blunder_san}` (any move number)"
        candidates.append(("T3", label, new_members))
        for h in new_members:
            seen_game_keys.add((h["game_id"], h["move_number"], h["blunder_san"]))

    print(f"Tier breakdown: T1={sum(1 for c in candidates if c[0]=='T1')} "
          f"T2={sum(1 for c in candidates if c[0]=='T2')} "
          f"T3={sum(1 for c in candidates if c[0]=='T3')}")
    print(f"Total candidate clusters: {len(candidates)}")

    # Build MD
    lines: list[str] = []
    lines.append("# Trap-pattern candidates — 500-game scan\n")
    lines.append(f"Scanned {n_scanned} games (v53+). Found {len(hits)} early-blunder hits "
                 f"(move 3-15, cp_loss >= 300, either color).")
    lines.append(f"Clustered to {len(candidates)} pattern candidates (>= {min_cluster} games each, "
                 f"not already in `traps.json`).\n")
    lines.append("**Methodology:** Same opening label + same first-N moves = same position class. "
                 "A cluster is a trap candidate if it repeats across multiple games AND has a clear "
                 "punishment move (the engine's best reply).\n")
    lines.append("**Note:** Not every cluster is a real trap. Some are just common opening blunders "
                 "(forgetting to develop, hanging a piece) that don't deserve a named-trap entry. "
                 "You decide which ones merit authoring.\n")
    lines.append("---\n")

    for i, (tier, label, group) in enumerate(candidates, 1):
        rep = group[0]
        eng = _engine_view(rep["fen_before"])

        lines.append(f"## Candidate #{i} [{tier}] — {label} ({len(group)} games)\n")
        # Show the most-common setup prefix in this group (median length, mode)
        prefix = rep["prefix"]
        pgn_pretty: list[str] = []
        for j, san in enumerate(prefix):
            if j % 2 == 0:
                pgn_pretty.append(f"{(j // 2) + 1}.{san}")
            else:
                pgn_pretty[-1] += f" {san}"
        lines.append(f"**Representative setup ({len(prefix)} half-moves):** `{' '.join(pgn_pretty)}`\n")

        lines.append(f"**Blunder pattern:** `{rep['blunder_san']}` (avg cp_loss "
                     f"{sum(h['cp_loss'] for h in group) // len(group)}, "
                     f"by {rep['blunderer_color']})\n")
        lines.append(f"**Engine's punishment (stored):** `{rep['best_san']}`\n")
        lines.append(f"**FEN before blunder:** `{rep['fen_before']}`\n")
        lines.append("**Live engine (depth 15, multipv 3):**\n")
        if eng.get("multipv"):
            for j, line in enumerate(eng["multipv"], 1):
                lines.append(f"- #{j} eval(W) `{line['cp']:+d}cp` PV: `{' '.join(line['pv'])}`")
        elif eng.get("error"):
            lines.append(f"- (engine error: {eng['error']})")
        lines.append("")

        lines.append("**Game IDs in cluster:**")
        for h in group[:8]:
            lines.append(f"- `{h['game_id'][:12]}` m{h['move_number']} "
                         f"{h['blunder_san']} cp_loss={h['cp_loss']} "
                         f"({'user' if h['user_was_blunderer'] else 'opp'})")
        if len(group) > 8:
            lines.append(f"- ...and {len(group) - 8} more")
        lines.append("")

        lines.append("**Author as trap?** (Mohit to decide)")
        lines.append("- [ ] Yes — this is a real trap pattern worth naming")
        lines.append("- [ ] No — common blunder, not a named trap")
        lines.append("- [ ] Already covered (note which trap in `traps.json` matches)")
        lines.append("")
        lines.append("---\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_path} with {len(candidates)} candidates")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="Output MD path")
    p.add_argument("--max-games", type=int, default=500)
    p.add_argument("--min-cluster", type=int, default=2,
                   help="Minimum games per cluster to surface (default 2)")
    args = p.parse_args()
    asyncio.run(main_async(args.out, args.max_games, args.min_cluster))


if __name__ == "__main__":
    main()
