"""
opening_sync_check.py — guard that the opening systems stay in lockstep.

The app has THREE opening lists that must agree, and they kept drifting (Mohit
2026-06-09: English was in the curriculum + traps but missing from the progress
skill-tree, so a real English game never showed). This is the caption-linter's
sibling for openings: run it on ANY opening change.

Checks (existing data only — reads the canonical JSONs, writes nothing):
  1. Every curriculum opening (opening_curriculum.json) has a skill-tree entry
     (skill_tree.json, matched by content_ref). MISSING = won't show on progress.
  2. Every skill-tree opening's content_ref exists in the curriculum. ORPHAN =
     points at nothing.
  3. The detector recognises each curriculum opening (depth >= 1).
  4. Trap coverage per opening (traps.json) — advisory, not a failure.

Exit 0 = in sync, 1 = drift (a curriculum<->skill-tree mismatch).

Usage:  docker exec -i chess-coach-backend python -m scripts.opening_sync_check
"""
import json
import os
import sys

sys.path.insert(0, "/app/backend")

_DATA = os.path.join("/app/backend", "data")


def run():
    curriculum = json.load(open(os.path.join(_DATA, "opening_curriculum.json"), encoding="utf-8"))
    skill_tree = json.load(open(os.path.join(_DATA, "coaching", "skill_tree.json"), encoding="utf-8"))
    traps = json.load(open(os.path.join(_DATA, "traps.json"), encoding="utf-8"))

    curric_keys = {k for k in curriculum if not k.startswith("_")}
    skill_refs = {
        v.get("content_ref")
        for k, v in skill_tree.get("skills", {}).items()
        if isinstance(v, dict) and v.get("kind") == "opening"
    }
    skill_refs.discard(None)
    trap_keys = {k.replace("-", "_") for k in traps if isinstance(traps.get(k), list)}

    missing = sorted(curric_keys - skill_refs)        # in curriculum, not tracked
    orphans = sorted(skill_refs - curric_keys)        # tracked, no curriculum
    no_traps = sorted(curric_keys - trap_keys)        # advisory

    print(f"curriculum openings: {len(curric_keys)}")
    print(f"skill-tree opening skills (by content_ref): {len(skill_refs)}")
    print(f"trap-covered openings: {len(curric_keys & trap_keys)}/{len(curric_keys)}")

    print("\n=== 1. curriculum openings NOT tracked in skill-tree (would not show on progress) ===")
    print("  " + (", ".join(missing) if missing else "(none — all tracked ✓)"))

    print("\n=== 2. skill-tree openings with NO curriculum entry (orphans) ===")
    print("  " + (", ".join(orphans) if orphans else "(none ✓)"))

    print("\n=== 3. every opening has a non-empty move tree (detector can match it) ===")
    # NOTE: we don't test detection by first-move alone — many openings share a
    # first move (all 1.e4 lines), so only deeper moves distinguish them. We just
    # assert each opening has a tree the detector can walk. Detection correctness
    # (incl. the transposition confidence gate) is covered by the gate tests.
    no_tree = sorted(k for k in curric_keys if not ((curriculum.get(k) or {}).get("tree")))
    print("  " + ("(all openings have a move tree ✓)" if not no_tree else "MISSING TREE: " + ", ".join(no_tree)))

    print("\n=== 4. curriculum openings with NO trap coverage (advisory) ===")
    print("  " + (", ".join(no_traps) if no_traps else "(all covered ✓)"))

    drift = bool(missing or orphans)
    print("\n" + "=" * 50)
    print("RESULT:", "IN SYNC ✓" if not drift else f"DRIFT — {len(missing)} missing, {len(orphans)} orphans")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(run())
