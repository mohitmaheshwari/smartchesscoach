"""
snapshot_pwc.py — PWC live-coaching regression net.

Captures the output of v5_teaching_decision_for_live_move() across a
fixed corpus of representative move scenarios. Used to verify that
future changes to caption_pipeline.py (or live_v5_teaching.py) don't
silently drift PWC behaviour.

The corpus mirrors the V5-review pinned-games approach
(scripts/snapshot_captions.py) but for PWC's live path: each scenario
is a synthesised user_doc + session_doc + move inputs that exercises
a specific A-helper or detector. Output is sorted by scenario_id for
deterministic diff.

Why this exists:
  - V5 review snapshots cover the batch caption pipeline. PWC has its
    own path through live_v5_teaching (suppression, necessity gate,
    resolver) that V5 snapshots can't catch.
  - When auto-propagation kicks in — a new helper added to
    caption_pipeline.py and called from build_move_teaching_decision
    — V5 review snapshot would catch drift on the review side. THIS
    tool catches drift on the PWC side.

Usage:
  python -m scripts.snapshot_pwc --tag baseline_pwc_v100
  python -m scripts.snapshot_pwc --tag post_b_adoption
  python -m scripts.snapshot_pwc --diff baseline_pwc_v100 post_b_adoption

The snapshot captures the FIELDS of the returned v5_block that matter
for downstream consumers (caption_messages collection, frontend):
  - principle_id (which principle fired)
  - anchor_name / anchor_detail (deterministic_draft is computed from
    these so omitted for cleaner diff)
  - shape_pattern_id (which shape fired, if any)
  - polish_status (always "draft" today, but captured for future)
  - state_key (set-keyed suppression key, if any)
  - principle_suppress_policy
  - is_coach_move_teaching

Plus a hash of the deterministic_draft for "did the text change" check
without exposing the full text (which is locale-formatted via
templates that may change cosmetically without behaviour change).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

from services.live_v5_teaching import v5_teaching_decision_for_live_move


# ─── Corpus ─────────────────────────────────────────────────────────
# Each entry is a self-contained PWC call scenario. Add new entries
# here as new A-helpers or detectors are added; the diff catches drift.
PWC_CORPUS: List[Dict[str, Any]] = [
    {
        "scenario_id": "01_starting_e4_clean",
        "comment": "Clean opening move — should NOT fire V5 teaching",
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "played_san": "e4",
        "best_move_san": "e4",
        "eval_before_cp": 0, "eval_after_cp": 0, "cp_loss": 0,
        "pv_after_played": [], "pv_after_best": [],
        "move_history_san": [],
        "full_move_number": 1, "mover_is_user": True,
        "user_rating": 1200, "user_color": "white",
    },
    {
        "scenario_id": "02_clean_developing_nc3",
        "comment": "Develop knight in opening, cp_loss small",
        "fen_before": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        "played_san": "Nc3",
        "best_move_san": "exd5",
        "eval_before_cp": 30, "eval_after_cp": 15, "cp_loss": 15,
        "pv_after_played": ["dxe4"], "pv_after_best": ["Qxd5", "Nc3", "Qa5"],
        "move_history_san": ["e4", "d5"],
        "full_move_number": 2, "mover_is_user": True,
        "user_rating": 1200, "user_color": "white",
    },
    {
        "scenario_id": "03_mistake_nf3_when_nxe5_wins_material",
        "comment": "Real mistake: misses a capture (TAC_CHECKS_CAPTURES_THREATS)",
        "fen_before": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        "played_san": "Nf3",
        "best_move_san": "Nxe5",
        "eval_before_cp": 200, "eval_after_cp": 0, "cp_loss": 200,
        "pv_after_played": ["Nf6"],
        "pv_after_best": ["Nxe5", "Nxe5", "Bc4"],
        "move_history_san": ["e4", "e5", "Nc3"],
        "full_move_number": 3, "mover_is_user": True,
        "user_rating": 1200, "user_color": "white",
    },
    {
        "scenario_id": "04_blunder_lost_winning",
        "comment": "Lost-winning blunder: eval +400 → -50, cp_loss=450",
        "fen_before": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1",
        "played_san": "Nxe5",
        "best_move_san": "O-O",
        "eval_before_cp": 400, "eval_after_cp": -50, "cp_loss": 450,
        "pv_after_played": ["Nxe5"],
        "pv_after_best": ["O-O", "O-O", "d3"],
        "move_history_san": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "Nc3", "Nf6"],
        "full_move_number": 5, "mover_is_user": True,
        "user_rating": 1200, "user_color": "white",
    },
    {
        "scenario_id": "05_black_mover_inaccuracy",
        "comment": "Black mover: sign-flip on eval interpretation",
        "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "played_san": "Qf6",
        "best_move_san": "Nc6",
        "eval_before_cp": -50, "eval_after_cp": 80, "cp_loss": 130,
        "pv_after_played": ["Nf3"], "pv_after_best": ["Nc6", "Nf3", "Bc5"],
        "move_history_san": ["e4", "e5"],
        "full_move_number": 2, "mover_is_user": True,
        "user_rating": 1200, "user_color": "black",
    },
    {
        "scenario_id": "06_low_rating_filtering",
        "comment": "800-rated player + mid cp_loss — practical_tier softens to good if stayed-winning",
        "fen_before": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 1",
        "played_san": "Nf3",
        "best_move_san": "Bc4",
        "eval_before_cp": 350, "eval_after_cp": 280, "cp_loss": 70,
        "pv_after_played": [], "pv_after_best": ["Bc4", "Bc5", "O-O"],
        "move_history_san": ["e4", "e5", "Nc3", "Nc6"],
        "full_move_number": 3, "mover_is_user": True,
        "user_rating": 800, "user_color": "white",
    },
    {
        "scenario_id": "07_endgame_critical_mistake",
        "comment": "Endgame mistake: should fire endgame-loose-pawn detector",
        "fen_before": "8/5kpp/8/8/8/3K4/PPP5/8 w - - 0 1",
        "played_san": "Kd4",
        "best_move_san": "b4",
        "eval_before_cp": 100, "eval_after_cp": -150, "cp_loss": 250,
        "pv_after_played": ["Ke6"],
        "pv_after_best": ["b4", "Ke6", "a4"],
        "move_history_san": [],
        "full_move_number": 30, "mover_is_user": True,
        "user_rating": 1500, "user_color": "white",
    },
]


def _hash_text(text: Optional[str]) -> str:
    """Stable 8-char hex hash of caption text. None → 'none'."""
    if not text:
        return "none"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _user_doc(rating: int, color: str) -> Dict[str, Any]:
    """Build a synthetic user_doc with the PWC v5 feature flag enabled."""
    return {
        "user_id": "snapshot_user",
        "feature_flags": {"pwc_v5_teaching": {"enabled": True}},
        "color_played": color,
        "rating": rating,
    }


def _session_doc(color: str) -> Dict[str, Any]:
    return {
        "session_id": "snapshot_session",
        "user_id": "snapshot_user",
        "user_color": color,
    }


def _snapshot_scenario(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Run one corpus entry through v5_teaching_decision_for_live_move
    and capture the regression-relevant fields of the result."""
    try:
        result = v5_teaching_decision_for_live_move(
            fen_before=entry["fen_before"],
            played_san=entry["played_san"],
            best_move_san=entry.get("best_move_san"),
            eval_before_cp=entry.get("eval_before_cp"),
            eval_after_cp=entry.get("eval_after_cp"),
            cp_loss=entry.get("cp_loss", 0),
            pv_after_played=entry.get("pv_after_played") or [],
            pv_after_best=entry.get("pv_after_best") or [],
            move_history_san=entry.get("move_history_san") or [],
            full_move_number=entry.get("full_move_number"),
            mover_is_user=entry.get("mover_is_user", True),
            user_doc=_user_doc(
                entry.get("user_rating", 1200),
                entry.get("user_color", "white"),
            ),
            session_doc=_session_doc(entry.get("user_color", "white")),
            session_fired_principles=set(),
            session_fired_state_keys=set(),
            encounter_weights=None,
        )
    except Exception as e:
        return {
            "scenario_id": entry["scenario_id"],
            "error": f"{type(e).__name__}: {e}",
        }

    if result is None:
        return {
            "scenario_id": entry["scenario_id"],
            "v5_block_present": False,
        }

    return {
        "scenario_id": entry["scenario_id"],
        "v5_block_present": True,
        "anchor_name": result.get("anchor_name"),
        "principle_id": result.get("principle_id"),
        "shape_pattern_id": result.get("shape_pattern_id"),
        "polish_status": result.get("polish_status"),
        "state_key": result.get("state_key"),
        "principle_suppress_policy": result.get("principle_suppress_policy"),
        "is_coach_move_teaching": result.get("is_coach_move_teaching"),
        # Hash the deterministic_draft for change-detection without
        # making the diff brittle to cosmetic template edits.
        "deterministic_draft_hash": _hash_text(result.get("deterministic_draft")),
        "anchor_detail_hash": _hash_text(result.get("anchor_detail")),
    }


def _capture(tag: str, output_dir: Path) -> int:
    rows = [_snapshot_scenario(e) for e in PWC_CORPUS]
    rows.sort(key=lambda r: r.get("scenario_id", ""))

    surfaced = sum(1 for r in rows if r.get("v5_block_present"))
    suppressed = sum(1 for r in rows if r.get("v5_block_present") is False)
    errors = sum(1 for r in rows if "error" in r)

    payload = {
        "tag": tag,
        "n_scenarios": len(PWC_CORPUS),
        "surfaced": surfaced,
        "suppressed": suppressed,
        "errors": errors,
        "rows": rows,
    }
    out_path = output_dir / f"pwc_{tag}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    print(f"Wrote {out_path}")
    print(f"  scenarios: {len(PWC_CORPUS)}  surfaced: {surfaced}  "
          f"suppressed: {suppressed}  errors: {errors}")
    return 0


def _diff(tag_a: str, tag_b: str, output_dir: Path) -> int:
    path_a = output_dir / f"pwc_{tag_a}.json"
    path_b = output_dir / f"pwc_{tag_b}.json"
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

    print(f"=== aggregate ===")
    print(f"  surfaced:   A={a.get('surfaced')}  B={b.get('surfaced')}")
    print(f"  suppressed: A={a.get('suppressed')}  B={b.get('suppressed')}")
    print(f"  errors:     A={a.get('errors')}  B={b.get('errors')}")

    map_a = {r["scenario_id"]: r for r in a.get("rows", [])}
    map_b = {r["scenario_id"]: r for r in b.get("rows", [])}

    n_diff = 0
    samples = []
    for sid in sorted(set(map_a) | set(map_b)):
        ra = map_a.get(sid, {})
        rb = map_b.get(sid, {})
        if ra == rb:
            continue
        n_diff += 1
        if len(samples) < 20:
            per_field = []
            for k in set(ra) | set(rb):
                va, vb = ra.get(k), rb.get(k)
                if va != vb:
                    per_field.append(f"      {k}: {va!r} -> {vb!r}")
            samples.append(f"  DIFF {sid}:\n" + "\n".join(per_field))

    print(f"=== per-scenario ===")
    print(f"  total scenarios: {len(set(map_a) | set(map_b))}")
    print(f"  with diffs:      {n_diff}")

    if n_diff == 0:
        print("CLEAN — no PWC regressions detected.")
        return 0

    print("=== samples ===")
    for s in samples:
        print(s)
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
        return _capture(args.tag, output_dir)
    elif args.diff:
        return _diff(args.diff[0], args.diff[1], output_dir)
    else:
        parser.error("provide either --tag or --diff")
        return 2


if __name__ == "__main__":
    sys.exit(main())
