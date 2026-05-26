"""
snapshot_captions.py — capture a byte-identical baseline of caption
output across the pinned games. Used to verify the v100 caption-pipeline
extraction does NOT change any user-visible output.

The snapshot covers:
  - Caption text (caption, rule_name)
  - Visual fields (caption_arrows, caption_highlight_squares,
    highlight_squares, shape_pattern_targets, shape_pattern_mover,
    shape_pattern_executing_move)
  - Severity surfaces (severity, severity_practical, severity_canonical,
    caption_tier, has_teaching_content)
  - Teaching anchors (principle_id_used, shape_pattern_id,
    shape_pattern_name)
  - Decisiveness fields used by R12 select_variant predicates
    (stayed_winning, decisiveness_changed, mover_state_before,
    mover_state_after)
  - caption_facts_primary_reason (consumed by caption_renderer.py
    Rule.category routing)
  - principles_violated as the sorted set of principle_ids fired

Output is sorted by (game_id, move_number) for deterministic diff.

Usage:
  python -m scripts.snapshot_captions --tag baseline_v99
  python -m scripts.snapshot_captions --tag post_extraction
  python -m scripts.snapshot_captions --diff baseline_v99 post_extraction

The snapshot file format is a JSON list of {game_id, move_number,
move_san, ...snapshot_fields}. Diff comparison is strict equality on
each entry — any difference is a regression to investigate.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


# The 10 pinned audit games. Matches the round_v78_audit_2026_05_23
# selection. Extend later if needed.
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


# Fields we snapshot per move. These are the ones a downstream consumer
# can read — change them and you've changed user-visible behaviour. Order
# matters for JSON stability (we sort by key when dumping, but listing
# here makes the contract explicit).
SNAPSHOT_FIELDS = [
    # text
    "caption", "rule_name",
    # visual
    "caption_arrows", "caption_highlight_squares", "highlight_squares",
    "shape_pattern_targets", "shape_pattern_mover",
    "shape_pattern_executing_move",
    # severity
    "severity", "severity_practical", "severity_canonical",
    "caption_tier", "has_teaching_content",
    # teaching anchors
    "principle_id_used", "principle_cue",
    "shape_pattern_id", "shape_pattern_name", "shape_pattern_desc",
    # decisiveness — feeds R12 / R_PROMOTED select_variant predicates
    "stayed_winning", "decisiveness_changed",
    "mover_state_before", "mover_state_after",
    # trap surfaces
    "trap_line_full",  # the per-step trap teaching text used by review UI
    # captured / target metadata
    "captured_piece_type", "is_best_move",
]


# caption_facts_primary_reason: a subset of keys consumed by
# caption_renderer.py Rule.category routing and select_variant
# predicates. Snapshot just the consumed keys so cosmetic
# changes inside the dict don't false-flag.
PRIMARY_REASON_KEYS = ["category", "priority_level", "ref_field"]


def _snapshot_move(game_id: str, move: Dict[str, Any]) -> Dict[str, Any]:
    """Build one snapshot entry from a v5_data move record."""
    out: Dict[str, Any] = {
        "game_id": game_id,
        "move_number": move.get("move_number"),
        "move_san": move.get("move_san"),
        "is_user_move": bool(move.get("is_user_move")),
        "is_white": bool(move.get("is_white")),
        "cp_loss": move.get("cp_loss"),
    }
    for f in SNAPSHOT_FIELDS:
        out[f] = move.get(f)
    # primary_reason — snapshot only consumed subset
    pr = move.get("caption_facts_primary_reason") or {}
    out["primary_reason_category"] = pr.get("category") if isinstance(pr, dict) else None
    out["primary_reason_priority"] = pr.get("priority_level") if isinstance(pr, dict) else None
    # principles fired — snapshot sorted ids (set semantics, deterministic)
    pv = move.get("caption_facts_principles_violated") or []
    if isinstance(pv, list):
        out["principles_fired_ids"] = sorted(
            (ev.get("principle_id") for ev in pv if isinstance(ev, dict) and ev.get("principle_id")),
            key=lambda s: s or "",
        )
    else:
        out["principles_fired_ids"] = []
    return out


async def _capture(tag: str, output_dir: Path) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    db = client["chess_coach"]

    rows: List[Dict[str, Any]] = []
    silent_count = 0
    total_moves = 0
    versions: List[int] = []
    for gid in PINNED_GAMES:
        g = await db.game_analyses.find_one({"game_id": gid})
        if not g:
            print(f"  [skip] {gid}: not found")
            continue
        versions.append(int(g.get("decryption_v5_version") or 0))
        moves = g.get("decryption_v5_data") or []
        if not isinstance(moves, list):
            continue
        for m in moves:
            if not isinstance(m, dict):
                continue
            total_moves += 1
            if not (m.get("caption") or "").strip():
                silent_count += 1
            rows.append(_snapshot_move(gid, m))

    rows.sort(key=lambda r: (r.get("game_id") or "", r.get("move_number") or 0))

    out_path = output_dir / f"{tag}.json"
    payload = {
        "tag": tag,
        "n_games": len(PINNED_GAMES),
        "n_moves": total_moves,
        "silent_count": silent_count,
        "versions": versions,
        "rows": rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    print(f"Wrote {out_path}")
    print(f"  games: {len(PINNED_GAMES)}  moves: {total_moves}  silent: {silent_count}")
    print(f"  versions seen: {sorted(set(versions))}")
    return 0


def _diff(tag_a: str, tag_b: str, output_dir: Path) -> int:
    path_a = output_dir / f"{tag_a}.json"
    path_b = output_dir / f"{tag_b}.json"
    if not path_a.exists():
        print(f"missing snapshot: {path_a}")
        return 2
    if not path_b.exists():
        print(f"missing snapshot: {path_b}")
        return 2
    with open(path_a, encoding="utf-8") as f:
        a = json.load(f)
    with open(path_b, encoding="utf-8") as f:
        b = json.load(f)

    # Aggregate sanity checks first
    print(f"=== aggregate ===")
    print(f"  n_moves:     A={a.get('n_moves')}  B={b.get('n_moves')}")
    print(f"  silent:      A={a.get('silent_count')}  B={b.get('silent_count')}")
    if a.get("silent_count") != b.get("silent_count"):
        print(f"  !! SILENT COUNT DRIFT — silence is sacred. Investigate.")

    # Build (game_id, move_number) keyed maps for symmetric diff
    def _key(r):
        # move_number alone collides (both colours share the full-move
        # number); include is_white to disambiguate ply.
        return (r.get("game_id"), r.get("move_number"), bool(r.get("is_white")))

    map_a = {_key(r): r for r in a.get("rows", [])}
    map_b = {_key(r): r for r in b.get("rows", [])}

    only_a = sorted(set(map_a) - set(map_b))
    only_b = sorted(set(map_b) - set(map_a))
    both = sorted(set(map_a) & set(map_b))

    diffs: List[str] = []
    for k in only_a:
        diffs.append(f"  ONLY IN {tag_a}: {k}")
    for k in only_b:
        diffs.append(f"  ONLY IN {tag_b}: {k}")

    # Per-field diff for shared keys
    n_diff = 0
    sample_diffs: List[str] = []
    for k in both:
        ra, rb = map_a[k], map_b[k]
        per_field: List[str] = []
        for field, va in ra.items():
            vb = rb.get(field)
            if va != vb:
                per_field.append(f"      {field}: {va!r} -> {vb!r}")
        if per_field:
            n_diff += 1
            if len(sample_diffs) < 30:
                gid, mvn, is_white = k
                colour = "white" if is_white else "black"
                sample_diffs.append(f"  DIFF {gid} m{mvn} {colour} {ra.get('move_san')}:\n" + "\n".join(per_field))

    print(f"=== per-move ===")
    print(f"  shared keys: {len(both)}  only_in_A: {len(only_a)}  only_in_B: {len(only_b)}")
    print(f"  with diffs:  {n_diff}")

    if not diffs and n_diff == 0:
        print("CLEAN — no regressions detected.")
        return 0

    print(f"=== samples ===")
    for d in diffs[:10]:
        print(d)
    for d in sample_diffs:
        print(d)
        print()
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="capture mode: save snapshot under this tag")
    parser.add_argument("--diff", nargs=2, metavar=("TAG_A", "TAG_B"),
                        help="diff mode: compare two captured snapshots")
    parser.add_argument("--output-dir", default="/app/backend/scripts/_snapshots",
                        help="directory where snapshots are stored")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.tag:
        return asyncio.run(_capture(args.tag, output_dir))
    elif args.diff:
        return _diff(args.diff[0], args.diff[1], output_dir)
    else:
        parser.error("provide either --tag or --diff")
        return 2


if __name__ == "__main__":
    sys.exit(main())
