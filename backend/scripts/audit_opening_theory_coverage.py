"""
audit_opening_theory_coverage.py — measure how many opening-phase moves
across the 10 pinned audit games would match a position in
data/coaching/opening_theory_tree.json.

The theory tree has 176 critical positions across 26 openings. 125 have
explicit `fen_pattern` fields; 51 are derivable only from main_line +
moves_from_parent + continuation replay. This v1 audit ONLY consults
the 125 explicit-FEN positions — that's the conservative coverage number
to inform the wiring decision.

For each match, surfaces:
  - opening name + variation
  - critical position key (e.g. "after_Nc3")
  - key_decision text
  - whether the played move matched a best_moves entry, a mistake_moves
    entry, or neither (just "in this critical position")

Run inside the backend container:
  docker exec chess-coach-backend bash -c "cd /app/backend && python -m scripts.audit_opening_theory_coverage"

No DB writes; pure read.
"""
import asyncio
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, "/app/backend")

import chess
from motor.motor_asyncio import AsyncIOMotorClient


def _normalize_san(san: str) -> str:
    return (san or "").rstrip("+#!?")


def _replay_path(plies: List[str]) -> List[Tuple[str, str]]:
    """Replay a list of SAN plies from start position. Returns a list
    of (san_played, normalized_fen_after) tuples. Stops on any illegal
    move (returns the partial path up to that point)."""
    board = chess.Board()
    out: List[Tuple[str, str]] = []
    for san in plies:
        try:
            move = board.parse_san(san)
        except Exception:
            break
        board.push(move)
        fen = " ".join(board.fen().split()[:4])
        out.append((_normalize_san(san), fen))
    return out


def _derive_variation_fens(opening: Dict[str, Any], variation: Dict[str, Any]) -> Dict[str, str]:
    """For one variation, build {cp_key: derived_fen} by replaying the
    full ply path (main_line + moves_from_parent + continuation) and
    matching cp_key suffixes ("after_<SAN>") against the played SANs.
    Returns the deepest match for each cp_key (so 'after_Nc3' picks the
    last Nc3 along the path, since the variation may have multiple)."""
    ml = opening.get("main_line") or []
    mfp = variation.get("moves_from_parent") or []
    cont = variation.get("continuation") or []
    plies = list(ml) + list(mfp) + list(cont)
    path = _replay_path(plies)
    out: Dict[str, str] = {}
    for cp_key in (variation.get("critical_positions") or {}):
        if not cp_key.startswith("after_"):
            continue
        target_san = _normalize_san(cp_key[len("after_"):])
        # Find the DEEPEST ply matching this SAN.
        for i in range(len(path) - 1, -1, -1):
            if path[i][0] == target_san:
                out[cp_key] = path[i][1]
                break
    return out


def _derive_top_level_fens(opening: Dict[str, Any]) -> Dict[str, str]:
    """Same as _derive_variation_fens but for opening-level
    critical_positions, using just main_line as the path."""
    ml = opening.get("main_line") or []
    path = _replay_path(ml)
    out: Dict[str, str] = {}
    for cp_key in (opening.get("critical_positions") or {}):
        if not cp_key.startswith("after_"):
            continue
        target_san = _normalize_san(cp_key[len("after_"):])
        for i in range(len(path) - 1, -1, -1):
            if path[i][0] == target_san:
                out[cp_key] = path[i][1]
                break
    return out


PINNED_GAMES = [
    "game_85bd0169aa4f",
    "game_b5d23694a803",
    "game_f2c022e03856",
    "game_ef9f422a062d",
    "game_74fdbd74c468",
    "game_4177951c757f",
    "game_bc41022831e0",
    "game_4c0f48f6cc0a",
    "game_8efcc1db5aa4",
    "game_692ab776c5b1",
]


def _normalize_fen(fen: str) -> str:
    """Strip halfmove + fullmove counters so the FEN can compare to
    theory-tree patterns that omit them. Keeps placement, side-to-move,
    castling rights, and en-passant square — all of which DO matter."""
    if not fen:
        return ""
    parts = fen.split()
    # FEN: <placement> <stm> <castling> <ep> <halfmove> <fullmove>
    # Keep first 4 fields. Some theory patterns end at <ep>; some end
    # before it. Normalize to "placement stm castling ep".
    if len(parts) >= 4:
        return " ".join(parts[:4])
    return fen.strip()


def _is_transposition_hint_cp(cp_key: str) -> bool:
    """The theory tree mixes two kinds of entries under critical_positions:
      - "after_<SAN>" → a real position you reach by playing the named
                        opening's main line. Anchors the opening.
      - "move<N>_<SAN>" → transposition hint: at ply N you could ALSO
                          play <SAN> to enter this opening. Shares FEN
                          with all other "alternative move <SAN>" entries
                          at the same ply, so they collide on lookup and
                          mis-attribute positions.
    Filter the second kind out — they're misleading once flattened to
    a {fen: opening} lookup.
    """
    return (
        cp_key.startswith("move1_")
        or cp_key.startswith("move2_")
        or cp_key.startswith("move3_")
    )


def _walk_theory_tree(tree: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    """Flatten the nested tree into {normalized_fen: position_record}.

    For each critical_position, the FEN comes from (in priority order):
      1. The explicit `fen_pattern` field, if present.
      2. Derivation by replaying main_line + moves_from_parent +
         continuation, matching the cp_key suffix to a played SAN.

    Returns (lookup_dict, stats) where stats tracks coverage breakdown:
      - explicit_fen: cps that had a fen_pattern
      - derived_fen : cps whose FEN was derived from replay
      - no_fen      : cps that had neither (cp_key not "after_<SAN>")
    """
    out: Dict[str, Dict[str, Any]] = {}
    stats = {"explicit_fen": 0, "derived_fen": 0, "no_fen": 0, "filtered_hint": 0}

    for opening_key, opening in tree.items():
        if opening_key == "_meta":
            continue
        common = opening.get("common_learnings") or []
        top_derived = _derive_top_level_fens(opening)
        # Top-level critical positions
        for cp_key, cp in (opening.get("critical_positions") or {}).items():
            if _is_transposition_hint_cp(cp_key):
                stats["filtered_hint"] += 1
                continue
            fen = cp.get("fen_pattern") or top_derived.get(cp_key)
            if not fen:
                stats["no_fen"] += 1
                continue
            if cp.get("fen_pattern"):
                stats["explicit_fen"] += 1
            else:
                stats["derived_fen"] += 1
            key = _normalize_fen(fen)
            out[key] = {
                "opening_key": opening_key,
                "opening_name": opening.get("name"),
                "variation_key": None,
                "variation_name": None,
                "cp_key": cp_key,
                "key_decision": cp.get("key_decision"),
                "best_moves": cp.get("best_moves") or cp.get("best_moves_white") or {},
                "mistake_moves": cp.get("mistake_moves") or {},
                "common_learnings": common,
            }
        # Nested variations
        for var_key, var in (opening.get("variations") or {}).items():
            var_derived = _derive_variation_fens(opening, var)
            for cp_key, cp in (var.get("critical_positions") or {}).items():
                if _is_transposition_hint_cp(cp_key):
                    stats["filtered_hint"] += 1
                    continue
                fen = cp.get("fen_pattern") or var_derived.get(cp_key)
                if not fen:
                    stats["no_fen"] += 1
                    continue
                if cp.get("fen_pattern"):
                    stats["explicit_fen"] += 1
                else:
                    stats["derived_fen"] += 1
                key = _normalize_fen(fen)
                out[key] = {
                    "opening_key": opening_key,
                    "opening_name": opening.get("name"),
                    "variation_key": var_key,
                    "variation_name": var.get("name"),
                    "cp_key": cp_key,
                    "key_decision": cp.get("key_decision"),
                    "best_moves": cp.get("best_moves") or cp.get("best_moves_white") or {},
                    "mistake_moves": cp.get("mistake_moves") or {},
                    "common_learnings": common,
                }
    return out, stats


def _match_quality(played_san: str, theory: Dict[str, Any]) -> str:
    """Classify the played move relative to the theory tree's best/mistake
    moves for this position. Returns 'best' / 'mistake' / 'critical_only'.
    """
    san = (played_san or "").rstrip("+#!?")
    for k in (theory.get("best_moves") or {}):
        if k.rstrip("+#!?") == san:
            return "best"
    for k in (theory.get("mistake_moves") or {}):
        if k.rstrip("+#!?") == san:
            return "mistake"
    return "critical_only"


async def main() -> None:
    # Load the theory tree.
    tree_path = "/app/backend/data/coaching/opening_theory_tree.json"
    with open(tree_path) as f:
        tree = json.load(f)
    flat, stats = _walk_theory_tree(tree)
    print(f"Loaded {len(flat)} theory positions")
    print(f"  explicit fen_pattern : {stats['explicit_fen']}")
    print(f"  derived from replay  : {stats['derived_fen']}")
    print(f"  no derivable FEN     : {stats['no_fen']}")
    print(f"  filtered (move_N_*)  : {stats['filtered_hint']}")
    print()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client["chess_coach"]

    total_opening_moves = 0
    total_matches = 0
    matches_by_quality = {"best": 0, "mistake": 0, "critical_only": 0}
    matches_by_opening: Dict[str, int] = {}
    samples: List[Dict[str, Any]] = []
    per_game: Dict[str, int] = {}

    # Mode: "pinned" (10 games) or "all" (every game with decryption_v5_data)
    mode = os.environ.get("AUDIT_MODE", "pinned")
    if mode == "all":
        cursor = db.game_analyses.find(
            {"decryption_v5_data": {"$exists": True}},
            {"_id": 0, "game_id": 1},
        )
        game_ids = [doc["game_id"] for doc in await cursor.to_list(length=None)]
        print(f"AUDIT_MODE=all — scanning {len(game_ids)} games with decryption_v5_data")
    else:
        game_ids = PINNED_GAMES
        print(f"AUDIT_MODE=pinned — scanning the 10 pinned authoring games")
    print()

    for gid in game_ids:
        g = await db.game_analyses.find_one({"game_id": gid})
        if not g or not isinstance(g.get("decryption_v5_data"), list):
            continue
        game_matches = 0
        for m in g["decryption_v5_data"]:
            if m.get("phase") != "opening":
                continue
            total_opening_moves += 1
            fen_after = m.get("fen_after") or ""
            key = _normalize_fen(fen_after)
            theory = flat.get(key)
            if not theory:
                continue
            total_matches += 1
            game_matches += 1
            q = _match_quality(m.get("move_san") or "", theory)
            matches_by_quality[q] += 1
            ok = theory["opening_key"]
            matches_by_opening[ok] = matches_by_opening.get(ok, 0) + 1
            # Collect ALL matches into a pool so we can take a random
            # representative sample at report time.
            samples.append({
                "game_id": gid,
                "move_number": m.get("move_number"),
                "played_san": m.get("move_san"),
                "is_user_move": m.get("is_user_move"),
                "fen_before": m.get("fen_before"),
                "fen_after": m.get("fen_after"),
                "current_caption": (m.get("caption") or "").strip(),
                "current_caption_tier": m.get("caption_tier"),
                "opening": theory["opening_name"],
                "variation": theory["variation_name"],
                "cp_key": theory["cp_key"],
                "match_quality": q,
                "key_decision": theory.get("key_decision"),
                "best_moves_idea": (
                    list(theory["best_moves"].values())[0].get("idea")
                    if theory["best_moves"] else None
                ),
            })
        per_game[gid] = game_matches

    print("=" * 72)
    print(f"AUDIT: theory-tree coverage across {len(PINNED_GAMES)} pinned games")
    print("=" * 72)
    print(f"Total opening-phase moves scanned: {total_opening_moves}")
    print(f"Total theory matches             : {total_matches}")
    print(f"  played move = a best_move      : {matches_by_quality['best']}")
    print(f"  played move = a mistake_move   : {matches_by_quality['mistake']}")
    print(f"  critical position, neither     : {matches_by_quality['critical_only']}")
    print()
    print("Matches by opening:")
    for ok, n in sorted(matches_by_opening.items(), key=lambda x: -x[1]):
        print(f"  {ok}: {n}")
    print()
    print("Matches per game (top 15 by hit count):")
    sorted_per_game = sorted(per_game.items(), key=lambda x: -x[1])[:15]
    for gid, n in sorted_per_game:
        print(f"  {gid}: {n}")
    print()
    # Random sample for spot-check rather than first-N.
    sample_n = int(os.environ.get("AUDIT_SAMPLE", "20"))
    random.seed(42)  # reproducible
    show = random.sample(samples, min(sample_n, len(samples)))

    print("-" * 72)
    print(f"RANDOM SAMPLES (n={len(show)}, seed=42) — eyeball each for tag accuracy:")
    print("-" * 72)
    for s in show:
        side = "user" if s["is_user_move"] else "opp "
        print(f"\n[{s['game_id'][:14]} m{s['move_number']} {side}] {s['played_san']}")
        print(f"  fen_after: {s['fen_after']}")
        print(f"  opening  : {s['opening']} ({s['variation'] or 'top-level'} / {s['cp_key']})")
        print(f"  match    : {s['match_quality']}")
        print(f"  key_q    : {s.get('key_decision')}")
        if s["best_moves_idea"]:
            print(f"  top idea : {s['best_moves_idea']}")
        print(f"  current  : [{s.get('current_caption_tier')}] {s['current_caption'][:95]}")


if __name__ == "__main__":
    asyncio.run(main())
