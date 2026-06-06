"""Concise summary of authoring_safe_subset.py's JSON output.

Built 2026-06-06 after running authoring_safe_subset.py revealed it
writes only .json (no .md). This reads both safe + rejected JSONs
and prints two compact reviewable tables — one for PASS items, one
for REJECT items — so Mohit + Claude can eyeball the audit result
without paging through 190 full-text records.

Usage:

    docker exec -it chess-coach-backend \\
      python /app/backend/scripts/summarize_authoring_audit.py

Optional: filter to tonight's 21-batch only with --batch:

    docker exec -it chess-coach-backend \\
      python /app/backend/scripts/summarize_authoring_audit.py --batch
"""
import argparse
import json
from collections import Counter
from pathlib import Path


SNAP_DIR = Path("/app/backend/scripts/_snapshots")
SAFE_JSON = SNAP_DIR / "authoring_safe_subset.json"
REJECT_JSON = SNAP_DIR / "authoring_rejected.json"


TONIGHTS_BATCH = {
    "fb_9f984e9753fc", "fb_9c4ad043240b", "fb_0589638c6580",
    "fb_44ab295462d0", "fb_2ad6a3fb208e", "fb_4d2363f0539b",
    "fb_4a281910cfa1", "fb_1cfd93561e46", "fb_530303f85fc8",
    "fb_582837f50d6d", "fb_6785172554ab", "fb_22528b6266b1",
    "fb_771714e55f1f", "fb_2c60b3989eed", "fb_6609c44f669d",
    "fb_9d6b4ad725ae", "fb_644107b00f68", "fb_538530c45efb",
    "fb_68adf27b28c1", "fb_96c28ed0b759", "fb_afb6ebc3c0e2",
}


def _short(s, n=110):
    """Truncate to n chars on a single line for table cells."""
    if not s:
        return ""
    s = " ".join(s.split())  # collapse whitespace + newlines
    return s if len(s) <= n else s[:n - 3] + "..."


def main(args):
    if not SAFE_JSON.exists():
        print(f"FATAL: {SAFE_JSON} not found.")
        print("Run /app/backend/scripts/authoring_safe_subset.py first.")
        return
    safe = json.loads(SAFE_JSON.read_text())
    rejected = json.loads(REJECT_JSON.read_text()) if REJECT_JSON.exists() else []

    if args.batch:
        safe = [s for s in safe if s.get("feedback_id") in TONIGHTS_BATCH]
        rejected = [r for r in rejected if r.get("feedback_id") in TONIGHTS_BATCH]
        print(f"=== FILTERED to tonight's 21-batch ===")
    else:
        print(f"=== FULL AUDIT SUMMARY ===")

    print(f"  PASSED: {len(safe)}    REJECTED: {len(rejected)}")
    print()

    # ─── PASS list ─────────────────────────────────────────────────────
    print(f"━━━ PASSING ITEMS ({len(safe)}) ━━━")
    print()
    by_user = Counter(s.get("user_name", "?") for s in safe)
    print("Pass count by submitter:")
    for u, n in by_user.most_common():
        print(f"  {u:<20}: {n}")
    print()

    print(f"{'fb_id':<22} {'user':<14} {'san':<8} {'sev':<14} {'cp':<5} suggested (first 100ch)")
    print("-" * 130)
    for s in safe:
        fb_id = s.get("feedback_id", "?")
        user = (s.get("user_name") or "")[:13]
        san = s.get("move_san", "?")[:8]
        sev = (s.get("severity") or "?")[:14]
        cp = str(s.get("cp_loss") or 0)[:5]
        sugg = _short(s.get("suggested_caption", ""), 100)
        is_tonight = "*" if fb_id in TONIGHTS_BATCH else " "
        print(f"{is_tonight}{fb_id:<21} {user:<14} {san:<8} {sev:<14} {cp:<5} {sugg}")
    print()
    print("(* = part of tonight's 21-batch)")
    print()

    # ─── REJECT list ───────────────────────────────────────────────────
    print(f"━━━ REJECTED ITEMS ({len(rejected)}) ━━━")
    print()
    print(f"{'fb_id':<22} {'san':<8} {'sev':<14} {'cp':<5} reasons")
    print("-" * 130)
    for r in rejected:
        fb_id = r.get("feedback_id", "?")
        san = (r.get("move_san") or "?")[:8]
        sev = (r.get("severity") or "?")[:14]
        cp = str(r.get("cp_loss") or 0)[:5]
        reasons = " | ".join(r.get("reject_reasons", []))
        is_tonight = "*" if fb_id in TONIGHTS_BATCH else " "
        print(f"{is_tonight}{fb_id:<21} {san:<8} {sev:<14} {cp:<5} {_short(reasons, 80)}")
    print()
    print("(* = part of tonight's 21-batch)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true",
                        help="Filter to tonight's 21-item batch only")
    args = parser.parse_args()
    main(args)
